##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
##
##  This program is free software: you can redistribute it and/or
##  modify it under the terms of the GNU General Public License as
##  published by the Free Software Foundation, either version 3 of the
##  License, or (at your option) any later version.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
##  General Public License for more details.
##
##  You should have received a copy of the GNU General Public License
##  along with this program.  If not, see
##  <http://www.gnu.org/licenses/>.

import codecs
import importlib
import locale
import logging
from optparse import OptionParser
import os
import sys
import warnings

import platformdirs

from photini import __version__
from photini.configstore import BaseConfigStore
from photini.editsettings import EditSettings
from photini.imagelist import ImageList
from photini.loggerwindow import full_version_info, LoggerWindow
from photini.metadata import ImageMetadata
from photini.photinimap import MapIconFactory
from photini.pyqt import *
from photini.pyqt import QtNetwork, qt_version_info, QtWebEngineCore
from photini.spelling import SpellCheck

try:
    from photini.gpximporter import GpxImporter
except ImportError as ex:
    print(str(ex))
    GpxImporter = None


logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class ConfigStore(BaseConfigStore, QtCore.QObject):
    # add timer to save config after it's changed
    def __init__(self, name, *arg, **kw):
        super(ConfigStore, self).__init__(name, *arg, **kw)
        QtCore.QCoreApplication.instance().aboutToQuit.connect(self.save)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(3000)
        self.timer.timeout.connect(self.save)

    def set(self, section, option, value):
        super(ConfigStore, self).set(section, option, value)
        self.timer.start()

    def remove_section(self, section):
        super(ConfigStore, self).remove_section(section)
        self.timer.start()

    @QtSlot()
    @catch_all
    def save(self):
        super(ConfigStore, self).save()


class ServerSocket(QtCore.QObject):
    new_files = QtSignal(list)

    def __init__(self, socket, *arg, **kw):
        super(ServerSocket, self).__init__(*arg, **kw)
        self.socket = socket
        self.data = b''
        self.socket.readyRead.connect(self.read_data)
        self.socket.disconnected.connect(self.socket_disconnected)

    @QtSlot()
    @catch_all
    def read_data(self):
        self.data += self.socket.readAll().data()

    @QtSlot()
    @catch_all
    def socket_disconnected(self):
        while self.socket.bytesAvailable():
            self.read_data()
        file_list = [x.decode('utf-8') for x in self.data.split(b'\n') if x]
        if file_list:
            self.new_files.emit(file_list)
        self.socket.deleteLater()


class InstanceServer(QtNetwork.QLocalServer):
    new_files = QtSignal(list)

    def __init__(self, *arg, **kw):
        super(InstanceServer, self).__init__(*arg, **kw)
        config = BaseConfigStore('instance')
        self.newConnection.connect(self.new_connection)
        self.setSocketOptions(self.SocketOption.UserAccessOption)
        name = 'photini_' + str(
            QtWidgets.QApplication.instance().applicationPid())
        if not self.listen(name):
            logger.error('Failed to start instance server:', self.errorString())
            return
        config.set('server', 'name', name)
        config.save()

    @QtSlot()
    @catch_all
    def new_connection(self):
        window = self.parent().window()
        window.setWindowState(
            (window.windowState() & ~Qt.WindowState.WindowMinimized) |
            Qt.WindowState.WindowActive)
        window.raise_()
        while self.hasPendingConnections():
            socket = self.nextPendingConnection()
            socket = ServerSocket(socket, parent=self)
            socket.new_files.connect(self.new_files)


def SendToInstance(files):
    config = BaseConfigStore('instance')
    name = config.get('server', 'name')
    if not name:
        return False
    sock = QtNetwork.QLocalSocket()
    sock.connectToServer(name)
    while not sock.waitForConnected(500):
        error = sock.error()
        if error != sock.LocalSocketError.SocketTimeoutError:
            return False
    for path in files:
        data = os.path.abspath(path).encode('utf-8') + b'\n'
        sock.write(data)
    sock.flush()
    sock.waitForBytesWritten(-1)
    sock.disconnectFromServer()
    return True


class MenuBar(QtWidgets.QMenuBar):
    def __init__(self, *args, **kwds):
        super(MenuBar, self).__init__(*args, **kwds)
        self.app = QtWidgets.QApplication.instance()
        # file menu
        file_menu = self.addMenu(translate('MenuBar', 'File'))
        action = file_menu.addAction(translate('MenuBar', 'Open files'))
        action.setShortcuts(QtGui.QKeySequence.StandardKey.Open)
        action.triggered.connect(self.app.image_list.open_files)
        self.save_action = file_menu.addAction(
            translate('MenuBar', 'Save changes'))
        self.save_action.setShortcuts(QtGui.QKeySequence.StandardKey.Save)
        self.save_action.setEnabled(False)
        self.save_action.triggered.connect(self.app.image_list.save_files)
        self.fix_thumbs_action = file_menu.addAction(
            translate('MenuBar', 'Fix missing thumbnails'))
        self.fix_thumbs_action.setEnabled(False)
        self.fix_thumbs_action.triggered.connect(
            self.app.image_list.fix_missing_thumbs)
        action = file_menu.addAction(translate('MenuBar', 'Close all files'))
        action.triggered.connect(self.app.image_list.close_all_files)
        file_menu.addSeparator()
        sep = QtWidgets.QWidgetAction(self)
        sep.setDefaultWidget(QtWidgets.QLabel(
            translate('MenuBar', 'Selected images')))
        file_menu.addAction(sep)
        self.selected_actions = self.app.image_list.add_selected_actions(file_menu)
        file_menu.addSeparator()
        action = file_menu.addAction(translate('MenuBar', 'Quit'))
        action.setShortcuts([QtGui.QKeySequence.StandardKey.Quit,
                             QtGui.QKeySequence.StandardKey.Close])
        action.triggered.connect(self.app.closeAllWindows)
        # options menu
        options_menu = self.addMenu(translate('MenuBar', 'Options'))
        action = options_menu.addAction(translate('MenuBar', 'Settings'))
        action.triggered.connect(self.edit_settings)
        options_menu.addSeparator()
        for module in self.parent().modules:
            tab = self.parent().tab_info[module]
            tab['action'] = options_menu.addAction(tab['name'])
            tab['action'].setCheckable(True)
            if tab['class']:
                tab['action'].setChecked(
                    self.app.config_store.get('tabs', module, True))
            else:
                tab['action'].setEnabled(False)
            tab['action'].triggered.connect(self.parent().add_tabs)
        # spelling menu
        languages = self.app.spell_check.available_languages()
        spelling_menu = self.addMenu(translate('MenuBar', 'Spelling'))
        action = spelling_menu.addAction(
            translate('MenuBar', 'Enable spell check'))
        action.setEnabled(languages is not None)
        action.setCheckable(True)
        action.setChecked(self.app.spell_check.enabled)
        action.toggled.connect(self.app.spell_check.enable)
        current_language = self.app.spell_check.current_language()
        if languages:
            language_group = QtGui2.QActionGroup(self)
            for language in sorted(languages):
                language_menu = spelling_menu.addMenu(language)
                for country, code in languages[language]:
                    if country:
                        name = '{}: {}'.format(language, country)
                    else:
                        name = language
                    action = language_menu.addAction(name)
                    action.setCheckable(True)
                    action.setChecked(code == current_language)
                    action.setData(code)
                    action.setActionGroup(language_group)
            language_group.triggered.connect(self.set_language)
        # help menu
        help_menu = self.addMenu(translate('MenuBar', 'Help'))
        action = help_menu.addAction(translate('MenuBar', 'About Photini'))
        action.triggered.connect(self.about)
        action = help_menu.addAction(translate('MenuBar', 'Check for update'))
        action.triggered.connect(self.check_update)
        help_menu.addSeparator()
        action = help_menu.addAction(
            translate('MenuBar', 'Photini documentation'))
        action.triggered.connect(self.open_docs)
        # connect signals
        self.app.image_list.selection_changed.connect(self.new_selection)
        self.app.image_list.image_list_changed.connect(self.new_image_list)
        self.app.image_list.new_metadata.connect(self.new_metadata)

    @QtSlot()
    @catch_all
    def edit_settings(self):
        dialog = EditSettings(self)
        execute(dialog)
        self.parent().tabs.currentWidget().refresh()

    @QtSlot(QtGui2.QAction)
    @catch_all
    def set_language(self, action):
        self.app.spell_check.set_language(action.data())

    @QtSlot()
    @catch_all
    def about(self):
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        with open(os.path.join(data_dir, 'icons', 'linux', '128x128',
                               'photini.png'), 'rb') as f:
            icon = f.read()
        text = """
<table width="100%"><tr>
<td align="center" width="70%">
<h1>Photini</h1>
<h3>version: {}</h3>
</td>
<td align="center"><img src="data:image/png;base64,{}" /></td>
</tr></table>
<p>&copy; Jim Easterbrook <a href="mailto:jim@jim-easterbrook.me.uk">
jim@jim-easterbrook.me.uk</a><br /><br />
{}<br />
{}</p>
""".format(__version__,
           codecs.encode(icon, 'base64').decode('ascii'),
           translate('MenuBar', 'An easy to use digital photograph metadata'
                     ' (Exif, IPTC, XMP) editing application.'),
           translate(
               'MenuBar', 'Open source package available from {url}.').format(
                   url='<a href="https://github.com/jim-easterbrook/Photini">'
                   'github.com/jim-easterbrook/Photini</a>'),
           )
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle(translate('MenuBar', 'Photini: about'))
        dialog.setText(text)
        with open(os.path.join(data_dir, 'LICENSE.txt'), 'r') as f:
            licence = f.read()
        dialog.setDetailedText(licence)
        dialog.setInformativeText(translate(
            'MenuBar', 'This program is released with a GNU General Public'
            ' License. For details click the "{details}" button.').format(
                details=dialog.buttons()[0].text()))
        execute(dialog)

    @QtSlot()
    @catch_all
    def check_update(self):
        import requests
        with Busy():
            try:
                rsp = requests.get(
                    'https://pypi.org/pypi/photini/json', timeout=20)
            except:
                logger.error(str(ex))
                return
        if rsp.status_code != 200:
            logger.error('HTTP error %d', rsp.status_code)
            return
        release = rsp.json()['info']['version']
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle(translate('MenuBar', 'Photini: version check'))
        dialog.setText(translate(
            'MenuBar', 'You are currently running Photini version {version}.'
            ' The latest release is {release}.').format(
                version=__version__, release=release))
        execute(dialog)

    @QtSlot()
    @catch_all
    def open_docs(self):
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl('http://photini.readthedocs.io/'))

    @QtSlot(list)
    @catch_all
    def new_selection(self, selection):
        self.app.image_list.configure_selected_actions(self.selected_actions)

    @QtSlot()
    @catch_all
    def new_image_list(self):
        for image in self.app.image_list.images:
            thumb = image.metadata.thumbnail
            if not thumb or not thumb['image']:
                self.fix_thumbs_action.setEnabled(True)
                return
        self.fix_thumbs_action.setEnabled(False)

    @QtSlot(bool)
    @catch_all
    def new_metadata(self, unsaved_data):
        self.app.image_list.configure_selected_actions(self.selected_actions)
        self.save_action.setEnabled(unsaved_data)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, options, initial_files):
        super(MainWindow, self).__init__()
        self.setWindowTitle(translate(
            'MenuBar', "Photini photo metadata editor"))
        icon = QtGui.QIcon()
        root_dir = os.path.join(
            os.path.dirname(__file__), 'data', 'icons', 'linux')
        for size in os.listdir(root_dir):
            path = os.path.join(root_dir, size, 'photini.png')
            if os.path.exists(path):
                icon.addFile(path)
        self.setWindowIcon(icon)
        self.selection = list()
        # create shared global objects
        self.app = QtWidgets.QApplication.instance()
        self.app.loggerwindow = LoggerWindow(options.verbose)
        self.app.loggerwindow.setWindowIcon(icon)
        self.app.config_store = ConfigStore('editor', parent=self)
        self.app.spell_check = SpellCheck(parent=self)
        if GpxImporter:
            self.app.gpx_importer = GpxImporter(parent=self)
        else:
            self.app.gpx_importer = None
        self.app.options = options
        self.app.image_list = ImageList()
        self.app.image_list.selection_changed.connect(self.new_selection)
        self.app.map_icon_factory = MapIconFactory(parent=self)
        # parse locale IETF / BCP 47 name
        # see https://en.wikipedia.org/wiki/IETF_language_tag
        self.app.language = {
            'bcp47': QtCore.QLocale.system().bcp47Name(),
            'primary': None,
            'region': None,
            }
        subtags = self.app.language['bcp47'].split('-')
        if len(subtags[0]) > 1:
            self.app.language['primary'] = subtags[0]
        for idx in range(1, len(subtags)):
            if len(subtags[idx]) == 1:
                # ignore extension and private-use subtags
                subtags = subtags[:idx]
                break
        while len(subtags[-1]) >= 4:
            # ignore variant subtags
            subtags = subtags[:-1]
        if len(subtags) > 1:
            self.app.language['region'] = subtags[-1]
        # initialise metadata handler
        ImageMetadata.initialise(self.app.config_store, options.verbose)
        # initialise web engine
        profile = QtWebEngineCore.QWebEngineProfile.defaultProfile()
        logger.debug('maps user agent: %s', profile.httpUserAgent())
        profile.setCachePath(
            os.path.join(platformdirs.user_cache_dir('photini'), 'WebEngine'))
        settings = profile.settings()
        settings.setAttribute(
            settings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(
            settings.WebAttribute.LocalContentCanAccessFileUrls, True)
        # restore size and state
        size = self.width(), self.height()
        self.resize(*self.app.config_store.get('main_window', 'size', size))
        window_state = Qt.WindowState(
            self.app.config_store.get('main_window', 'state', 0))
        full_screen = window_state & (
            Qt.WindowState.WindowMaximized | Qt.WindowState.WindowFullScreen)
        if full_screen:
            self.setWindowState(self.windowState() | full_screen)
        # start instance server
        instance_server = InstanceServer(parent=self)
        instance_server.new_files.connect(self.app.image_list.open_file_list,
                                          Qt.ConnectionType.QueuedConnection)
        # prepare list of tabs and associated stuff
        self.tab_info = {}
        default_modules = ['photini.descriptive',  'photini.keywords',
                           'photini.ownership',    'photini.technical',
                           'photini.regions',      'photini.googlemap',
                           'photini.bingmap',      'photini.azuremap',
                           'photini.mapboxmap',    'photini.address',
                           'photini.flickr',       'photini.ipernity',
                           'photini.googlephotos', 'photini.pixelfed',
                           'photini.importer']
        self.modules = self.app.config_store.get(
            'tabs', 'modules', default_modules)
        if 'photini.openstreetmap' in self.modules:
            self.modules.remove('photini.openstreetmap')
            self.app.config_store.delete('tabs', 'photini.openstreetmap')
        # insert any new tabs straight after first tab
        idx = min(1, len(self.modules))
        self.modules[idx:idx] = [x for x in default_modules
                                 if x not in self.modules]
        self.app.config_store.set('tabs', 'modules', self.modules)
        for module in self.modules:
            tab = {}
            try:
                mod = importlib.import_module(module)
                tab['class'] = mod.TabWidget
                tab['label'] = tab['class'].tab_short_name()
                tab['name'] = tab['class'].tab_name()
            except ImportError as ex:
                print(str(ex))
                tab['class'] = None
                tab['name'] = module
            self.tab_info[module] = tab
        # menu bar
        self.setMenuBar(MenuBar(parent=self))
        # main application area
        self.central_widget = QtWidgets.QSplitter()
        self.central_widget.setOrientation(Qt.Orientation.Vertical)
        self.central_widget.setChildrenCollapsible(False)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.currentChanged.connect(self.new_tab)
        self.tabs.setMovable(True)
        self.tabs.tabBar().tabMoved.connect(self.tab_moved)
        self.add_tabs()
        self.central_widget.addWidget(self.tabs)
        self.central_widget.addWidget(self.app.image_list)
        size = self.central_widget.sizes()
        self.central_widget.setSizes(
            self.app.config_store.get('main_window', 'split', size))
        self.central_widget.splitterMoved.connect(self.new_split)
        self.setCentralWidget(self.central_widget)
        # open files given on command line, after GUI is displayed
        self.initial_files = initial_files
        if self.initial_files:
            QtCore.QTimer.singleShot(0, self.open_initial_files)

    @QtSlot()
    @catch_all
    def open_initial_files(self):
        self.app.image_list.open_file_list(self.initial_files, select=False)

    @QtSlot()
    @catch_all
    def add_tabs(self):
        was_blocked = self.tabs.blockSignals(True)
        current = self.tabs.currentWidget()
        self.tabs.clear()
        for module in self.modules:
            tab = self.tab_info[module]
            if not tab['class']:
                self.app.config_store.set('tabs', module, True)
                continue
            use_tab = tab['action'].isChecked()
            self.app.config_store.set('tabs', module, use_tab)
            if not use_tab:
                continue
            if 'object' not in tab:
                tab['object'] = tab['class'](self.app.image_list)
            idx = self.tabs.addTab(tab['object'], tab['label'])
            self.tabs.setTabToolTip(idx, tab['name'])
            self.tabs.tabBar().setTabData(idx, module)
        self.tabs.blockSignals(was_blocked)
        if current:
            self.tabs.setCurrentWidget(current)
        self.new_tab(-1)

    @catch_all
    def closeEvent(self, event):
        for n in range(self.tabs.count()):
            if self.tabs.widget(n).do_not_close():
                event.ignore()
                return
        self.app.image_list.unsaved_files_dialog(
            all_files=True, with_cancel=False)
        super(MainWindow, self).closeEvent(event)

    @QtSlot(int, int)
    @catch_all
    def new_split(self, pos, index):
        self.app.config_store.set(
            'main_window', 'split', self.central_widget.sizes())

    @QtSlot(int)
    @catch_all
    def new_tab(self, index):
        current = self.tabs.currentWidget()
        if current:
            self.app.image_list.set_drag_to_map(None)
            current.refresh()

    @QtSlot(int, int)
    @catch_all
    def tab_moved(self, new_pos, old_pos):
        tab_bar = self.tabs.tabBar()
        modules = []
        for n in range(tab_bar.count()):
            modules.append(tab_bar.tabData(n))
        modules += [x for x in self.modules if x not in modules]
        self.modules = modules
        self.app.config_store.set('tabs', 'modules', self.modules)

    @QtSlot(list)
    @catch_all
    def new_selection(self, selection):
        self.tabs.currentWidget().new_selection(selection)

    @catch_all
    def resizeEvent(self, event):
        window_state = self.windowState()
        self.app.config_store.set(
            'main_window', 'state', flag_to_int(window_state))
        if window_state & (Qt.WindowState.WindowMinimized |
                           Qt.WindowState.WindowMaximized |
                           Qt.WindowState.WindowFullScreen):
            return
        size = self.width(), self.height()
        self.app.config_store.set('main_window', 'size', size)


app = None

def main(argv=None):
    global app
    if argv:
        sys.argv = argv
    if qt_version_info < (6, 0):
        QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QtWidgets.QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # let Qt handle its options
    app = QtWidgets.QApplication(sys.argv)
    # get remaining argument list after Qt has swallowed its options
    sys.argv = app.arguments()
    # install translations
    lang_dir = os.path.join(os.path.dirname(__file__), 'data', 'lang')
    locale.setlocale(locale.LC_ALL, '')
    langs = [x.replace('-', '_') for x in QtCore.QLocale.system().uiLanguages()]
    # always have English translation as a fallback (to get correct plurals)
    if 'en' not in langs:
        langs += ['en']
    # create translators in language preference order
    translators = []
    if qt_version_info < (5, 15):
        loaded = []
    for lang in langs:
        translator = QtCore.QTranslator()
        if translator.load('photini.' + lang, lang_dir):
            if qt_version_info < (5, 15):
                lang = lang.split('_')[0]
                if lang not in loaded:
                    loaded.append(lang)
                    translators.append(translator)
            else:
                if translator.language() not in [
                        x.language() for x in translators]:
                    translators.append(translator)
    # install translators in reverse order, so preferred language is used first
    for translator in reversed(translators):
        translator.setParent(app)
        app.installTranslator(translator)
    # parse remaining arguments
    version = full_version_info()
    parser = OptionParser(
        usage=translate('CLIHelp', 'Usage: %prog [options] [file_name, ...]'),
        version=version,
        description=translate('CLIHelp', 'Photini photo metadata editor'))
    parser.add_option(
        '-t', '--test', action='store_true',
        help=translate('CLIHelp', 'test new features or API versions'))
    parser.add_option(
        '-v', '--verbose', action='count', default=0,
        help=translate('CLIHelp', 'increase number of logging messages'))
    options, args = parser.parse_args()
    if sys.platform == 'win32':
        # args might not be utf-8 encoded
        lang, encoding = locale.getdefaultlocale()
        if encoding.lower() not in ('utf-8', 'utf_8', 'utf8'):
            args = [x.encode(encoding).decode('utf-8') for x in args]
    # if an instance of Photini is already running, send it the list of
    # files to open
    if SendToInstance(args):
        return 0
    # ensure warnings are visible in test mode
    if options.test:
        warnings.simplefilter('default')
    # create GUI and run application event loop
    main = MainWindow(options, args)
    main.show()
    result = execute(app)
    os.unlink(BaseConfigStore('instance').file_name)
    return result

if __name__ == "__main__":
    sys.exit(main())
