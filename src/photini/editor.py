#!/usr/bin/env python

##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-13  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

"""
usage: editor.py [options]
options are:
  -h       | --help        display this help
  -v       | --verbose     increase number of logging messages
  -V       | --version     display version information and exit
"""

from __future__ import unicode_literals

import logging
from optparse import OptionParser
import os
import sys
if sys.version_info[0] >= 3:
    from urllib.request import getproxies
    from urllib.parse import urlparse
else:
    from urllib import getproxies
    from urlparse import urlparse 
import webbrowser

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt
from PyQt4.QtNetwork import QNetworkProxy

from .configstore import ConfigStore
from .bingmap import BingMap
from .descriptive import Descriptive
try:
    from .flickr import FlickrUploader
except ImportError:
    FlickrUploader = None
from .editsettings import EditSettings
from .googlemap import GoogleMap
try:
    from .importer import Importer
except ImportError:
    Importer = None
from .openstreetmap import OpenStreetMap
from .imagelist import ImageList
from .loggerwindow import LoggerWindow
try:
    from .picasa import PicasaUploader
except ImportError:
    PicasaUploader = None
from .technical import Technical
from .utils import data_dir
from . import __version__

class MainWindow(QtGui.QMainWindow):
    def __init__(self, verbose):
        QtGui.QMainWindow.__init__(self)
        self.setWindowTitle("Photini photo metadata editor")
        self.selection = list()
        # logger window
        self.loggerwindow = LoggerWindow(verbose)
        self.logger = logging.getLogger(self.__class__.__name__)
        # config store
        self.config_store = ConfigStore('editor')
        # set network proxy
        proxies = getproxies()
        if 'http' in proxies:
            parsed = urlparse(proxies['http'])
            QNetworkProxy.setApplicationProxy(QNetworkProxy(
                QNetworkProxy.HttpProxy, parsed.hostname, parsed.port))
        # restore size
        size = self.width(), self.height()
        self.resize(*eval(
            self.config_store.get('main_window', 'size', str(size))))
        # image selector
        self.image_list = ImageList(self.config_store)
        self.image_list.selection_changed.connect(self.new_selection)
        self.image_list.new_metadata.connect(self.new_metadata)
        # prepare list of tabs and associated stuff
        self.tab_list = (
            {'name' : '&Descriptive metadata', 'class' : Descriptive},
            {'name' : '&Technical metadata',   'class' : Technical},
            {'name' : 'Map (&Google)',         'class' : GoogleMap},
            {'name' : 'Map (&Bing)',           'class' : BingMap},
            {'name' : 'Map (&OSM)',            'class' : OpenStreetMap},
            {'name' : '&Flickr upload',        'class' : FlickrUploader},
            {'name' : '&Picasa upload',        'class' : PicasaUploader},
            {'name' : '&Import from camera',   'class' : Importer},
            )
        for tab in self.tab_list:
            tab['key'] = tab['name'].replace('&', '').replace(' ', '_')
            tab['key'] = tab['key'].replace('(', '').replace(')', '').lower()
            if tab['class']:
                tab['object'] = tab['class'](self.config_store, self.image_list)
            else:
                tab['object'] = None
        # file menu
        file_menu = self.menuBar().addMenu('File')
        open_action = QtGui.QAction('Open images', self)
        open_action.setShortcuts(['Ctrl+O'])
        open_action.triggered.connect(self.image_list.open_files)
        file_menu.addAction(open_action)
        self.save_action = QtGui.QAction('Save images with new data', self)
        self.save_action.setShortcuts(['Ctrl+S'])
        self.save_action.setEnabled(False)
        self.save_action.triggered.connect(self.image_list.save_files)
        file_menu.addAction(self.save_action)
        self.close_action = QtGui.QAction('Close selected images', self)
        self.close_action.setEnabled(False)
        self.close_action.triggered.connect(self.close_files)
        file_menu.addAction(self.close_action)
        close_all_action = QtGui.QAction('Close all images', self)
        close_all_action.triggered.connect(self.close_all_files)
        file_menu.addAction(close_all_action)
        file_menu.addSeparator()
        quit_action = QtGui.QAction('Quit', self)
        quit_action.setShortcuts(['Ctrl+Q', 'Ctrl+W'])
        quit_action.triggered.connect(
            QtGui.QApplication.instance().closeAllWindows)
        file_menu.addAction(quit_action)
        # options menu
        options_menu = self.menuBar().addMenu('Options')
        settings_action = QtGui.QAction('Settings', self)
        settings_action.triggered.connect(self.edit_settings)
        options_menu.addAction(settings_action)
        options_menu.addSeparator()
        for tab in self.tab_list:
            tab['action'] = QtGui.QAction(tab['name'].replace('&', ''), self)
            tab['action'].setCheckable(True)
            if tab['class']:
                tab['action'].setChecked(
                    eval(self.config_store.get('tabs', tab['key'], 'True')))
            else:
                tab['action'].setEnabled(False)
            tab['action'].triggered.connect(self.add_tabs)
            options_menu.addAction(tab['action'])
        # help menu
        help_menu = self.menuBar().addMenu('Help')
        about_action = QtGui.QAction('About Photini', self)
        about_action.triggered.connect(self.about)
        help_menu.addAction(about_action)
        help_menu.addSeparator()
        help_action = QtGui.QAction('Photini documentation', self)
        help_action.triggered.connect(self.open_docs)
        help_menu.addAction(help_action)
        # main application area
        self.central_widget = QtGui.QSplitter()
        self.central_widget.setOrientation(Qt.Vertical)
        self.central_widget.setChildrenCollapsible(False)
        self.tabs = QtGui.QTabWidget()
        self.tabs.currentChanged.connect(self.new_tab)
        self.add_tabs()
        self.central_widget.addWidget(self.tabs)
        self.central_widget.addWidget(self.image_list)
        size = self.central_widget.sizes()
        self.central_widget.setSizes(eval(
            self.config_store.get('main_window', 'split', str(size))))
        self.central_widget.splitterMoved.connect(self.new_split)
        self.setCentralWidget(self.central_widget)

    def add_tabs(self):
        current = self.tabs.currentWidget()
        self.tabs.clear()
        for tab in self.tab_list:
            use_tab = tab['action'].isChecked()
            self.config_store.set('tabs', tab['key'], str(use_tab))
            if tab['object'] and use_tab:
                self.tabs.addTab(tab['object'], tab['name'])
        if current:
            self.tabs.setCurrentWidget(current)

    def open_docs(self):
        webbrowser.open_new('http://jim-easterbrook.github.com/Photini/')
    
    def close_files(self):
        self._close_files(False)

    def close_all_files(self):
        self._close_files(True)

    def _close_files(self, all_files):
        if self.image_list.unsaved_files_dialog(all_files=all_files):
            self.image_list.close_files(all_files)

    def closeEvent(self, event):
        self.image_list.unsaved_files_dialog(with_cancel=False)
        self.loggerwindow.shutdown()
        QtGui.QMainWindow.closeEvent(self, event)

    def edit_settings(self):
        dialog = EditSettings(self, self.config_store)
        dialog.exec_()

    @QtCore.pyqtSlot()
    def about(self):
        dialog = QtGui.QMessageBox()
        dialog.setWindowTitle('Photini: about')
        dialog.setText(
            open(os.path.join(data_dir, 'about.html')).read() % (__version__))
        dialog.setDetailedText(
            open(os.path.join(data_dir, 'LICENSE.txt')).read())
        dialog.exec_()

    @QtCore.pyqtSlot(int, int)
    def new_split(self, pos, index):
        self.config_store.set(
            'main_window', 'split', str(self.central_widget.sizes()))

    @QtCore.pyqtSlot(int)
    def new_tab(self, index):
        current = self.tabs.currentWidget()
        if current:
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
        self.config_store.set('main_window', 'size', str(size))

def main(argv=None):
    if argv:
        sys.argv = argv
    # let PyQt handle its options (need at least one argument after options)
    sys.argv.append('xxx')
    app = QtGui.QApplication(sys.argv)
    del sys.argv[-1]
    # parse remaining arguments
    parser = OptionParser(version='Photini %s' % (__version__),
                          description='Photini photo metadata editor')
    parser.add_option('-v', '--verbose', action='count', default=0,
                      help='increase number of logging messages')
    options, args = parser.parse_args()
    if len(args) != 0:
        parser.error('incorrect number of arguments')
    # create GUI and run application event loop
    main = MainWindow(options.verbose)
    main.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())
