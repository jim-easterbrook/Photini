##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from __future__ import unicode_literals

import importlib
import logging
from optparse import OptionParser
import os
import pprint
import sys
import urllib
import warnings

import pkg_resources

from photini import __version__, build
from photini.configstore import BaseConfigStore
from photini.editsettings import EditSettings
from photini.ffmpeg import ffmpeg_version
from photini.gi import gi_version
from photini.imagelist import ImageList
from photini.loggerwindow import LoggerWindow
from photini.opencage import OpenCage
from photini.pyqt import (
    catch_all, Qt, QtCore, QtGui, QtNetwork, QNetworkProxy, QtSignal, QtSlot,
    QtWidgets, qt_version, width_for_text)
from photini.spelling import SpellCheck, spelling_version

try:
    from photini.gpximporter import GpxImporter
except ImportError as ex:
    print(str(ex))
    GpxImporter = None


logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class QTabBar(QtWidgets.QTabBar):
    def tabSizeHint(self, index):
        size = super(QTabBar, self).tabSizeHint(index)
        size.setWidth(max(size.width(), width_for_text(self, 'x' * 10)))
        return size


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
        self.socket.setParent(self)
        self.socket.readyRead.connect(self.read_data)
        self.socket.disconnected.connect(self.deleteLater)

    @QtSlot()
    @catch_all
    def read_data(self):
        file_list = []
        while self.socket.bytesAvailable():
            self.data += self.socket.readAll().data()
            while b'\n' in self.data:
                line, sep, self.data = self.data.partition(b'\n')
                string = line.decode('utf-8')
                file_list.append(string)
        if file_list:
            self.new_files.emit(file_list)


class InstanceServer(QtNetwork.QTcpServer):
    new_files = QtSignal(list)

    def __init__(self, *arg, **kw):
        super(InstanceServer, self).__init__(*arg, **kw)
        config = BaseConfigStore('instance')
        self.newConnection.connect(self.new_connection)
        if not self.listen(QtNetwork.QHostAddress.LocalHost):
            logger.error('Failed to start instance server:', self.errorString())
            return
        config.set('server', 'port', self.serverPort())
        config.save()

    @QtSlot()
    @catch_all
    def new_connection(self):
        window = self.parent().window()
        window.raise_()
        window.activateWindow()
        while self.hasPendingConnections():
            socket = self.nextPendingConnection()
            socket = ServerSocket(socket, parent=self)
            socket.new_files.connect(self.new_files)


def SendToInstance(files):
    config = BaseConfigStore('instance')
    port = config.get('server', 'port')
    if not port:
        return False
    socket = QtNetwork.QTcpSocket()
    socket.connectToHost(
        QtNetwork.QHostAddress.LocalHost, int(port), QtCore.QIODevice.WriteOnly)
    if not socket.waitForConnected(1000):
        logger.info('Connect to server: %s', socket.errorString())
        return False
    for path in files:
        data = os.path.abspath(path).encode('utf-8') + b'\n'
        while data:
            count = socket.write(data)
            if count < 1:
                logger.error('Write to server: %s', socket.errorString())
                break
            data = data[count:]
    socket.waitForBytesWritten()
    socket.close()
    return True

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, options, initial_files):
        super(MainWindow, self).__init__()
        self.setWindowTitle(translate(
            'MenuBar', "Photini photo metadata editor"))
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(pkg_resources.resource_string(
            'photini', 'data/icons/photini_48.png'))
        icon = QtGui.QIcon(pixmap)
        self.setWindowIcon(icon)
        self.selection = list()
        # logger window
        self.loggerwindow = LoggerWindow(options.verbose)
        self.loggerwindow.setWindowIcon(icon)
        # set network proxy
        proxies = urllib.request.getproxies()
        if 'http' in proxies:
            parsed = urllib.parse.urlparse(proxies['http'])
            QNetworkProxy.setApplicationProxy(QNetworkProxy(
                QNetworkProxy.HttpProxy, parsed.hostname, parsed.port))
        # create shared global objects
        self.app = QtWidgets.QApplication.instance()
        self.app.config_store = ConfigStore('editor', parent=self)
        self.app.spell_check = SpellCheck(parent=self)
        self.app.open_cage = OpenCage(parent=self)
        self.app.options = options
        # restore size
        size = self.width(), self.height()
        self.resize(*eval(
            self.app.config_store.get('main_window', 'size', str(size))))
        # image selector
        self.image_list = ImageList()
        self.image_list.selection_changed.connect(self.new_selection)
        self.image_list.image_list_changed.connect(self.new_image_list)
        self.image_list.new_metadata.connect(self.new_metadata)
        # start instance server
        instance_server = InstanceServer(parent=self)
        instance_server.new_files.connect(
            self.image_list.open_file_list, Qt.QueuedConnection)
        # update config file
        if self.app.config_store.config.has_section('tabs'):
            conv = {
                'descriptive_metadata': 'photini.descriptive',
                'technical_metadata'  : 'photini.technical',
                'map_google'          : 'photini.googlemap',
                'map_bing'            : 'photini.bingmap',
                'map_mapbox'          : 'photini.mapboxmap',
                'map_osm'             : 'photini.openstreetmap',
                'address'             : 'photini.address',
                'flickr_upload'       : 'photini.flickr',
                'import_photos'       : 'photini.importer',
                }
            for key in self.app.config_store.config.options('tabs'):
                if key in conv:
                    self.app.config_store.set(
                        'tabs', conv[key],
                        self.app.config_store.get('tabs', key))
                    self.app.config_store.config.remove_option('tabs', key)
        # prepare list of tabs and associated stuff
        self.tab_list = []
        default_modules = ['photini.descriptive',  'photini.ownership',
                           'photini.technical',
                           'photini.googlemap',    'photini.bingmap',
                           'photini.mapboxmap',    'photini.openstreetmap',
                           'photini.address',      'photini.flickr',
                           'photini.googlephotos', 'photini.importer']
        modules = eval(self.app.config_store.get(
            'tabs', 'modules', pprint.pformat(default_modules)))
        for n, module in enumerate(default_modules):
            if module not in modules:
                modules = list(modules)
                modules.insert(n, module)
                self.app.config_store.set(
                    'tabs', 'modules', pprint.pformat(modules))
        for module in modules:
            tab = {'module': module}
            try:
                mod = importlib.import_module(tab['module'])
                tab['class'] = mod.TabWidget
                tab['name'] = tab['class'].tab_name()
            except ImportError as ex:
                print(str(ex))
                tab['class'] = None
            self.tab_list.append(tab)
        # file menu
        file_menu = self.menuBar().addMenu(translate('MenuBar', 'File'))
        action = file_menu.addAction(translate('MenuBar', 'Open files'))
        action.setShortcuts(QtGui.QKeySequence.Open)
        action.triggered.connect(self.image_list.open_files)
        self.save_action = file_menu.addAction(
            translate('MenuBar', 'Save changes'))
        self.save_action.setShortcuts(QtGui.QKeySequence.Save)
        self.save_action.setEnabled(False)
        self.save_action.triggered.connect(self.image_list.save_files)
        self.fix_thumbs_action = file_menu.addAction(
            translate('MenuBar', 'Fix missing thumbnails'))
        self.fix_thumbs_action.setEnabled(False)
        self.fix_thumbs_action.triggered.connect(
            self.image_list.fix_missing_thumbs)
        action = file_menu.addAction(translate('MenuBar', 'Close all files'))
        action.triggered.connect(self.image_list.close_all_files)
        sep = file_menu.addAction(translate('MenuBar', 'Selected images'))
        sep.setSeparator(True)
        self.selected_actions = self.image_list.add_selected_actions(file_menu)
        if GpxImporter:
            self.import_gpx_action = file_menu.addAction(
                translate('MenuBar', 'Import GPX file'))
            self.import_gpx_action.triggered.connect(self.import_pgx_file)
        else:
            self.import_gpx_action = None
        file_menu.addSeparator()
        action = file_menu.addAction(translate('MenuBar', 'Quit'))
        action.setShortcuts(
            [QtGui.QKeySequence.Quit, QtGui.QKeySequence.Close])
        action.triggered.connect(
            QtWidgets.QApplication.instance().closeAllWindows)
        # options menu
        options_menu = self.menuBar().addMenu(translate('MenuBar', 'Options'))
        action = options_menu.addAction(translate('MenuBar', 'Settings'))
        action.triggered.connect(self.edit_settings)
        options_menu.addSeparator()
        for tab in self.tab_list:
            if tab['class']:
                name = tab['name'].replace('&', '')
            else:
                name = tab['module']
            tab['action'] = options_menu.addAction(name)
            tab['action'].setCheckable(True)
            if tab['class']:
                tab['action'].setChecked(eval(
                    self.app.config_store.get('tabs', tab['module'], 'True')))
            else:
                tab['action'].setEnabled(False)
            tab['action'].triggered.connect(self.add_tabs)
        # spelling menu
        languages = self.app.spell_check.available_languages()
        spelling_menu = self.menuBar().addMenu(translate('MenuBar', 'Spelling'))
        action = spelling_menu.addAction(
            translate('MenuBar', 'Enable spell check'))
        action.setEnabled(languages is not None)
        action.setCheckable(True)
        action.setChecked(self.app.spell_check.enabled)
        action.toggled.connect(self.app.spell_check.enable)
        language_menu = spelling_menu.addMenu(
            translate('MenuBar', 'Choose language'))
        language_menu.setEnabled(languages is not None)
        current_language = self.app.spell_check.current_language()
        if languages:
            language_group = QtWidgets.QActionGroup(self)
            for name, code in languages:
                if name != code:
                    name = code + ': ' + name
                action = language_menu.addAction(name)
                action.setCheckable(True)
                action.setChecked(code == current_language)
                action.setData(code)
                action.setActionGroup(language_group)
            language_group.triggered.connect(self.set_language)
        else:
            action = language_menu.addAction(
                translate('MenuBar', 'No dictionary installed'))
            action.setEnabled(False)
        # help menu
        help_menu = self.menuBar().addMenu(translate('MenuBar', 'Help'))
        action = help_menu.addAction(translate('MenuBar', 'About Photini'))
        action.triggered.connect(self.about)
        help_menu.addSeparator()
        action = help_menu.addAction(
            translate('MenuBar', 'Photini documentation'))
        action.triggered.connect(self.open_docs)
        # main application area
        self.central_widget = QtWidgets.QSplitter()
        self.central_widget.setOrientation(Qt.Vertical)
        self.central_widget.setChildrenCollapsible(False)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabBar(QTabBar())
        self.tabs.setElideMode(Qt.ElideRight)
        self.tabs.currentChanged.connect(self.new_tab)
        self.add_tabs(False)
        self.central_widget.addWidget(self.tabs)
        self.central_widget.addWidget(self.image_list)
        size = self.central_widget.sizes()
        self.central_widget.setSizes(eval(
            self.app.config_store.get('main_window', 'split', str(size))))
        self.central_widget.splitterMoved.connect(self.new_split)
        self.setCentralWidget(self.central_widget)
        # open files given on command line, after GUI is displayed
        self.initial_files = initial_files
        if self.initial_files:
            QtCore.QTimer.singleShot(0, self.open_initial_files)

    @QtSlot()
    @catch_all
    def open_initial_files(self):
        self.image_list.open_file_list(self.initial_files)

    @QtSlot(bool)
    @catch_all
    def add_tabs(self, checked):
        was_blocked = self.tabs.blockSignals(True)
        current = self.tabs.currentWidget()
        self.tabs.clear()
        idx = 0
        for tab in self.tab_list:
            if not tab['class']:
                self.app.config_store.set('tabs', tab['module'], 'True')
                continue
            use_tab = tab['action'].isChecked()
            self.app.config_store.set('tabs', tab['module'], str(use_tab))
            if not use_tab:
                continue
            if 'object' not in tab:
                tab['object'] = tab['class'](self.image_list)
            self.tabs.addTab(tab['object'], tab['name'])
            self.tabs.setTabToolTip(idx, tab['name'].replace('&', ''))
            idx += 1
        self.tabs.blockSignals(was_blocked)
        if current:
            self.tabs.setCurrentWidget(current)
        self.new_tab(-1)

    @QtSlot()
    @catch_all
    def open_docs(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(
            'http://photini.readthedocs.io/'))

    @QtSlot()
    @catch_all
    def import_pgx_file(self):
        importer = GpxImporter()
        importer.do_import(self)

    @catch_all
    def closeEvent(self, event):
        for n in range(self.tabs.count()):
            if self.tabs.widget(n).do_not_close():
                event.ignore()
                return
        self.image_list.unsaved_files_dialog(all_files=True, with_cancel=False)
        super(MainWindow, self).closeEvent(event)

    @QtSlot()
    @catch_all
    def edit_settings(self):
        dialog = EditSettings(self)
        dialog.exec_()
        self.tabs.currentWidget().refresh()

    @QtSlot(QtWidgets.QAction)
    @catch_all
    def set_language(self, action):
        self.app.spell_check.set_language(action.data())

    @QtSlot()
    @catch_all
    def about(self):
        text = """
<table width="100%"><tr>
<td align="center" width="70%">
<h1>Photini</h1>
<h3>version {0}</h3>
<h4>build {1}</h4>
</td>
<td align="center"><img src="{2}" /></td>
</tr></table>
<p>&copy; Jim Easterbrook <a href="mailto:jim@jim-easterbrook.me.uk">
jim@jim-easterbrook.me.uk</a><br /><br />
{3}<br />
{4}</p>
""".format(__version__, build,
           pkg_resources.resource_filename(
               'photini', 'data/icons/photini_128.png'),
           translate('MenuBar',
                     'An easy to use digital photograph metadata'
                     ' (Exif, IPTC, XMP) editing application.'),
           translate('MenuBar',
                     'Open source package available from {}.').format(
                         '<a href="https://github.com/jim-easterbrook/Photini">'
                         'github.com/jim-easterbrook/Photini</a>'),
           )
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle(translate('MenuBar', 'Photini: about'))
        dialog.setText(text)
        licence = pkg_resources.resource_string('photini', 'data/LICENSE.txt')
        dialog.setDetailedText(licence.decode('utf-8'))
        dialog.setInformativeText(translate(
            'MenuBar',
            'This program is released with a GNU General Public'
            ' License. For details click the "{}" button.').format(
                dialog.buttons()[0].text()))
        dialog.exec_()

    @QtSlot(int, int)
    @catch_all
    def new_split(self, pos, index):
        self.app.config_store.set(
            'main_window', 'split', str(self.central_widget.sizes()))

    @QtSlot(int)
    @catch_all
    def new_tab(self, index):
        current = self.tabs.currentWidget()
        if current:
            self.image_list.set_drag_to_map(None)
            current.refresh()
            self.image_list.emit_selection()

    @QtSlot(list)
    @catch_all
    def new_selection(self, selection):
        self.image_list.configure_selected_actions(self.selected_actions)
        if self.import_gpx_action:
            self.import_gpx_action.setEnabled(len(selection) > 0)
        self.tabs.currentWidget().new_selection(selection)

    @QtSlot()
    @catch_all
    def new_image_list(self):
        for image in self.image_list.images:
            thumb = image.metadata.thumbnail
            if not thumb or not thumb['image']:
                self.fix_thumbs_action.setEnabled(True)
                return
        self.fix_thumbs_action.setEnabled(False)

    @QtSlot(bool)
    @catch_all
    def new_metadata(self, unsaved_data):
        self.image_list.configure_selected_actions(self.selected_actions)
        self.save_action.setEnabled(unsaved_data)

    @catch_all
    def resizeEvent(self, event):
        size = self.width(), self.height()
        self.app.config_store.set('main_window', 'size', str(size))


app = None

def main(argv=None):
    global app
    if argv:
        sys.argv = argv
    # let Qt handle its options
    app = QtWidgets.QApplication(sys.argv)
    # get remaining argument list after Qt has swallowed its options
    sys.argv = app.arguments()
    # install translations
    # English translation as a fallback (to get correct plurals)
    lang_dir = pkg_resources.resource_filename('photini', 'data/lang')
    translator = QtCore.QTranslator(parent=app)
    if translator.load('photini.en', lang_dir):
        app.installTranslator(translator)
        translator = QtCore.QTranslator(parent=app)
    # localised translation, if it exists
    locale = QtCore.QLocale.system()
    if translator.load(locale, 'photini', '.', lang_dir):
        app.installTranslator(translator)
        translator = QtCore.QTranslator(parent=app)
    # parse remaining arguments
    version = 'Photini ' + __version__ + ', build ' + build
    version += '\n  Python ' + sys.version
    version += '\n  ' + gi_version
    version += '\n  ' + qt_version
    if spelling_version:
        version += '\n  ' + spelling_version
    if ffmpeg_version:
        version += '\n  ' + ffmpeg_version
    version += '\n  available styles: {}'.format(
        ', '.join(QtWidgets.QStyleFactory.keys()))
    version += '\n  using style: {}'.format(
        QtWidgets.QApplication.style().objectName())
    parser = OptionParser(
        usage=translate('CLIHelp', 'Usage: %prog [options] [file_name, ...]'),
        version=version,
        description=translate('CLIHelp', 'Photini photo metadata editor'))
    parser.add_option(
        '-t', '--test', action='store_true',
        help=translate('CLIHelp', 'test new features or API versions'))
    parser.add_option(
        '-u', '--utf_safe', action='store_true',
        help=translate(
            'CLIHelp', 'metadata is known to be ASCII or utf-8 encoded'))
    parser.add_option(
        '-v', '--verbose', action='count', default=0,
        help=translate('CLIHelp', 'increase number of logging messages'))
    options, args = parser.parse_args()
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
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())
