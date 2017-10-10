#!/usr/bin/env python
# -*- coding: utf-8 -*-

##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-17  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import six
import logging
from optparse import OptionParser
import os
import sys
from six.moves.urllib.request import getproxies
from six.moves.urllib.parse import urlparse
import webbrowser

import pkg_resources

from photini.configstore import BaseConfigStore
from photini.bingmap import BingMap
from photini.descriptive import Descriptive
try:
    from photini.facebook import FacebookUploader
except ImportError:
    FacebookUploader = None
try:
    from photini.flickr import FlickrUploader
except ImportError:
    FlickrUploader = None
from photini.editsettings import EditSettings
from photini.googlemap import GoogleMap
from photini.importer import Importer
from photini.metadata import debug_metadata, gexiv2_version
from photini.openstreetmap import OpenStreetMap
from photini.imagelist import ImageList
from photini.loggerwindow import LoggerWindow
try:
    from photini.picasa import PicasaUploader
except ImportError:
    PicasaUploader = None
from photini.pyqt import (Qt, QtCore, QtGui, QNetworkProxy,
                          QtWidgets, qt_version_info, using_qtwebengine)
from photini.spelling import enchant_version, SpellCheck
from photini.technical import Technical
from photini import __version__, build

class QTabBar(QtWidgets.QTabBar):
    def tabSizeHint(self, index):
        size = super(QTabBar, self).tabSizeHint(index)
        size.setWidth(max(size.width(), 90))
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

    @QtCore.pyqtSlot()
    def save(self):
        super(ConfigStore, self).save()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, options, initial_files):
        super(MainWindow, self).__init__()
        self.setWindowTitle(self.tr("Photini photo metadata editor"))
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(pkg_resources.resource_string(
            'photini', 'data/icons/48/photini.png'))
        icon = QtGui.QIcon(pixmap)
        self.setWindowIcon(icon)
        self.selection = list()
        # logger window
        self.loggerwindow = LoggerWindow(options.verbose)
        self.loggerwindow.setWindowIcon(icon)
        # set network proxy
        proxies = getproxies()
        if 'http' in proxies:
            parsed = urlparse(proxies['http'])
            QNetworkProxy.setApplicationProxy(QNetworkProxy(
                QNetworkProxy.HttpProxy, parsed.hostname, parsed.port))
        # create shared global objects
        self.app = QtWidgets.QApplication.instance()
        self.app.config_store = ConfigStore('editor', parent=self)
        self.app.spell_check = SpellCheck(parent=self)
        self.app.test_mode = options.test
        # set debug mode
        if self.app.test_mode:
            debug_metadata()
        # restore size
        size = self.width(), self.height()
        self.resize(*eval(
            self.app.config_store.get('main_window', 'size', str(size))))
        # image selector
        self.image_list = ImageList()
        self.image_list.selection_changed.connect(self.new_selection)
        self.image_list.new_metadata.connect(self.new_metadata)
        # prepare list of tabs and associated stuff
        self.tab_list = (
            {'name'  : self.tr('&Descriptive metadata'),
             'key'   : 'descriptive_metadata',
             'class' : Descriptive},
            {'name'  : self.tr('&Technical metadata'),
             'key'   : 'technical_metadata',
             'class' : Technical},
            {'name'  : self.tr('Map (&Google)'),
             'key'   : 'map_google',
             'class' : GoogleMap},
            {'name'  : self.tr('Map (&Bing)'),
             'key'   : 'map_bing',
             'class' : BingMap},
            {'name'  : self.tr('Map (&OSM)'),
             'key'   : 'map_osm',
             'class' : OpenStreetMap},
            {'name'  : self.tr('&Flickr upload'),
             'key'   : 'flickr_upload',
             'class' : FlickrUploader},
            {'name'  : self.tr('Google &Photos upload'),
             'key'   : 'picasa_upload',
             'class' : PicasaUploader},
            {'name'  : self.tr('Faceboo&k upload'),
             'key'   : 'facebook_upload',
             'class' : FacebookUploader},
            {'name'  : self.tr('&Import photos'),
             'key'   : 'import_photos',
             'class' : Importer},
            )
        # file menu
        file_menu = self.menuBar().addMenu(self.tr('File'))
        open_action = QtWidgets.QAction(self.tr('Open images'), self)
        open_action.setShortcuts(QtGui.QKeySequence.Open)
        open_action.triggered.connect(self.image_list.open_files)
        file_menu.addAction(open_action)
        self.save_action = QtWidgets.QAction(
            self.tr('Save images with new data'), self)
        self.save_action.setShortcuts(QtGui.QKeySequence.Save)
        self.save_action.setEnabled(False)
        self.save_action.triggered.connect(self.image_list.save_files)
        file_menu.addAction(self.save_action)
        self.close_action = QtWidgets.QAction(
            self.tr('Close selected images'), self)
        self.close_action.setEnabled(False)
        self.close_action.triggered.connect(self.close_files)
        file_menu.addAction(self.close_action)
        close_all_action = QtWidgets.QAction(self.tr('Close all images'), self)
        close_all_action.triggered.connect(self.close_all_files)
        file_menu.addAction(close_all_action)
        file_menu.addSeparator()
        quit_action = QtWidgets.QAction(self.tr('Quit'), self)
        quit_action.setShortcuts(
            [QtGui.QKeySequence.Quit, QtGui.QKeySequence.Close])
        quit_action.triggered.connect(
            QtWidgets.QApplication.instance().closeAllWindows)
        file_menu.addAction(quit_action)
        # options menu
        options_menu = self.menuBar().addMenu(self.tr('Options'))
        settings_action = QtWidgets.QAction(self.tr('Settings'), self)
        settings_action.triggered.connect(self.edit_settings)
        options_menu.addAction(settings_action)
        options_menu.addSeparator()
        for tab in self.tab_list:
            name = tab['name'].replace('&', '')
            tab['action'] = QtWidgets.QAction(name, self)
            tab['action'].setCheckable(True)
            if tab['class']:
                tab['action'].setChecked(
                    eval(self.app.config_store.get('tabs', tab['key'], 'True')))
            else:
                tab['action'].setEnabled(False)
            tab['action'].triggered.connect(self.add_tabs)
            options_menu.addAction(tab['action'])
        # spelling menu
        languages = self.app.spell_check.available_languages()
        spelling_menu = self.menuBar().addMenu(self.tr('Spelling'))
        enable_action = QtWidgets.QAction(self.tr('Enable spell check'), self)
        enable_action.setEnabled(bool(languages))
        enable_action.setCheckable(True)
        enable_action.setChecked(self.app.spell_check.enabled)
        enable_action.toggled.connect(self.app.spell_check.enable)
        spelling_menu.addAction(enable_action)
        language_menu = QtWidgets.QMenu(self.tr('Choose language'), self)
        language_menu.setEnabled(bool(languages))
        language_group = QtWidgets.QActionGroup(self)
        current_language = self.app.spell_check.current_language()
        for tag in languages:
            language_action = QtWidgets.QAction(tag, self)
            language_action.setCheckable(True)
            language_action.setChecked(tag == current_language)
            language_action.setActionGroup(language_group)
            language_menu.addAction(language_action)
        language_group.triggered.connect(self.app.spell_check.set_language)
        spelling_menu.addMenu(language_menu)
        # help menu
        help_menu = self.menuBar().addMenu(self.tr('Help'))
        about_action = QtWidgets.QAction(self.tr('About Photini'), self)
        about_action.triggered.connect(self.about)
        help_menu.addAction(about_action)
        help_menu.addSeparator()
        help_action = QtWidgets.QAction(self.tr('Photini documentation'), self)
        help_action.triggered.connect(self.open_docs)
        help_menu.addAction(help_action)
        # main application area
        self.central_widget = QtWidgets.QSplitter()
        self.central_widget.setOrientation(Qt.Vertical)
        self.central_widget.setChildrenCollapsible(False)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabBar(QTabBar())
        self.tabs.setElideMode(Qt.ElideRight)
        self.tabs.currentChanged.connect(self.new_tab)
        self.add_tabs()
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

    @QtCore.pyqtSlot()
    def open_initial_files(self):
        self.image_list.open_file_list(self.initial_files)

    @QtCore.pyqtSlot()
    def add_tabs(self):
        was_blocked = self.tabs.blockSignals(True)
        current = self.tabs.currentWidget()
        self.tabs.clear()
        for tab in self.tab_list:
            if not tab['class']:
                self.app.config_store.set('tabs', tab['key'], 'True')
                continue
            use_tab = tab['action'].isChecked()
            self.app.config_store.set('tabs', tab['key'], str(use_tab))
            if not use_tab:
                continue
            if 'object' not in tab:
                tab['object'] = tab['class'](self.image_list)
            self.tabs.addTab(tab['object'], tab['name'])
        self.tabs.blockSignals(was_blocked)
        if current:
            self.tabs.setCurrentWidget(current)
        self.new_tab(-1)

    @QtCore.pyqtSlot()
    def open_docs(self):
        webbrowser.open_new('http://photini.readthedocs.io/')

    @QtCore.pyqtSlot()
    def close_files(self):
        self.image_list.close_files(False)

    @QtCore.pyqtSlot()
    def close_all_files(self):
        self.image_list.close_files(True)

    def closeEvent(self, event):
        for n in range(self.tabs.count()):
            if self.tabs.widget(n).do_not_close():
                event.ignore()
                return
        self.image_list.unsaved_files_dialog(all_files=True, with_cancel=False)
        super(MainWindow, self).closeEvent(event)

    @QtCore.pyqtSlot()
    def edit_settings(self):
        dialog = EditSettings(self)
        dialog.exec_()
        self.tabs.currentWidget().refresh()

    @QtCore.pyqtSlot()
    def about(self):
        text = self.tr("""
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
An easy to use digital photograph metadata editor.<br />
Open source package available from
<a href="https://github.com/jim-easterbrook/Photini">
github.com/jim-easterbrook/Photini</a>.</p>
<p>This program is released with a GNU General Public License. For
details click the 'show details' button.</p>
""").format(__version__, build,
            pkg_resources.resource_filename(
                'photini', 'data/icons/128/photini.png'))
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle(self.tr('Photini: about'))
        dialog.setText(text)
        licence = pkg_resources.resource_string('photini', 'data/LICENSE.txt')
        dialog.setDetailedText(licence.decode('utf-8'))
        dialog.exec_()

    @QtCore.pyqtSlot(int, int)
    def new_split(self, pos, index):
        self.app.config_store.set(
            'main_window', 'split', str(self.central_widget.sizes()))

    @QtCore.pyqtSlot(int)
    def new_tab(self, index):
        current = self.tabs.currentWidget()
        if current:
            self.image_list.set_drag_to_map(None)
            current.refresh()
            self.image_list.emit_selection()

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.close_action.setEnabled(len(selection) > 0)
        self.tabs.currentWidget().new_selection(selection)

    @QtCore.pyqtSlot(bool)
    def new_metadata(self, unsaved_data):
        self.save_action.setEnabled(unsaved_data)

    def resizeEvent(self, event):
        size = self.width(), self.height()
        self.app.config_store.set('main_window', 'size', str(size))

def main(argv=None):
    if argv:
        sys.argv = argv
    # let PyQt handle its options (need at least one argument after options)
    sys.argv.append('xxx')
    app = QtWidgets.QApplication(sys.argv)
    del sys.argv[-1]
    # install translations
    if qt_version_info < (5, 0):
        QtCore.QTextCodec.setCodecForTr(QtCore.QTextCodec.codecForName('utf-8'))
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
    # Qt's own translation, e.g. for 'apply' or 'cancel' buttons
    if qt_version_info < (5, 0):
        if translator.load(locale, 'qt', '_', QtCore.QLibraryInfo.location(
                QtCore.QLibraryInfo.TranslationsPath)):
            app.installTranslator(translator)
    # parse remaining arguments
    version = 'Photini ' + __version__ + ', build ' + build
    version += '\n  Python ' + sys.version
    version += '\n  ' + gexiv2_version
    version += '\n  PyQt {}, Qt {}, using {}'.format(
        QtCore.PYQT_VERSION_STR, QtCore.QT_VERSION_STR,
        ('QtWebKit', 'QtWebEngine')[using_qtwebengine])
    if enchant_version:
        version += '\n  ' + enchant_version
    if FlickrUploader:
        from photini.flickr import flickr_version
        version += '\n  ' + flickr_version
    version += '\n  available styles: {}'.format(
        ', '.join(QtWidgets.QStyleFactory.keys()))
    parser = OptionParser(
        usage=six.text_type(QtCore.QCoreApplication.translate(
            'main', 'Usage: %prog [options] [file_name, ...]')),
        version=version,
        description=six.text_type(QtCore.QCoreApplication.translate(
            'main', 'Photini photo metadata editor')))
    parser.add_option(
        '-t', '--test', action='store_true',
        help=six.text_type(QtCore.QCoreApplication.translate(
            'main', 'test new features or API versions')))
    parser.add_option(
        '-v', '--verbose', action='count', default=0,
        help=six.text_type(QtCore.QCoreApplication.translate(
            'main', 'increase number of logging messages')))
    options, args = parser.parse_args()
    # create GUI and run application event loop
    main = MainWindow(options, args)
    main.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())
