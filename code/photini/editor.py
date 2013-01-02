#!/usr/bin/env python

##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
"""

import getopt
import os
import sys
import urllib2
import webbrowser

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt
from PyQt4.QtNetwork import QNetworkProxy

from configstore import ConfigStore
from bingmap import BingMap
from dateandtime import DateAndTime
from flickr import FlickrUploader
from googlemap import GoogleMap
from openstreetmap import OpenStreetMap
from imagelist import ImageList
from textmetadata import TextMetadata
from utils import data_dir
from version import version, release

class MainWindow(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.setWindowTitle("Photini photo metadata editor")
        self.selection = list()
        # config store
        self.config_store = ConfigStore()
        # set network proxy
        proxies = urllib2.getproxies()
        if 'http' in proxies:
            scheme, host, port = proxies['http'].split(':')
            QNetworkProxy.setApplicationProxy(
                QNetworkProxy(QNetworkProxy.HttpProxy, host[2:], int(port)))
        # restore size
        size = self.width(), self.height()
        self.resize(*eval(
            self.config_store.get('main_window', 'size', str(size))))
        # image selector
        self.image_list = ImageList(self.config_store)
        self.image_list.selection_changed.connect(self.new_selection)
        self.image_list.new_metadata.connect(self.new_metadata)
        # textual metadata editors
        self.text_edit = TextMetadata(self.config_store, self.image_list)
        self.date_time = DateAndTime(self.config_store, self.image_list)
        # map metadata editor(s)
        self.google_map = GoogleMap(self.config_store, self.image_list)
        self.bing_map = BingMap(self.config_store, self.image_list)
        self.open_street_map = OpenStreetMap(self.config_store, self.image_list)
        # Flickr uploader
        self.flickr = FlickrUploader(self.config_store, self.image_list)
        # main application area
        self.central_widget = QtGui.QSplitter()
        self.central_widget.setOrientation(Qt.Vertical)
        self.central_widget.setChildrenCollapsible(False)
        self.tabs = QtGui.QTabWidget()
        self.tabs.addTab(self.text_edit, '&Text metadata')
        self.tabs.addTab(self.date_time, '&Date && time')
        self.tabs.addTab(self.google_map, 'Map (&Google)')
        self.tabs.addTab(self.bing_map, 'Map (&Bing)')
        self.tabs.addTab(self.open_street_map, 'Map (&OSM)')
        self.tabs.addTab(self.flickr, '&Flickr uploader')
        self.tabs.currentChanged.connect(self.new_tab)
        self.central_widget.addWidget(self.tabs)
        self.central_widget.addWidget(self.image_list)
        size = self.central_widget.sizes()
        self.central_widget.setSizes(eval(
            self.config_store.get('main_window', 'split', str(size))))
        self.central_widget.splitterMoved.connect(self.new_split)
        self.setCentralWidget(self.central_widget)
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
        quit_action.triggered.connect(QtGui.qApp.closeAllWindows)
        file_menu.addAction(quit_action)
        # help menu
        help_menu = self.menuBar().addMenu('Help')
        about_action = QtGui.QAction('About Photini', self)
        about_action.triggered.connect(self.about)
        help_menu.addAction(about_action)
        help_menu.addSeparator()
        help_action = QtGui.QAction('Photini documentation', self)
        help_action.triggered.connect(self.open_docs)
        help_menu.addAction(help_action)

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
        QtGui.QMainWindow.closeEvent(self, event)

    @QtCore.pyqtSlot()
    def about(self):
        dialog = QtGui.QMessageBox()
        dialog.setWindowTitle('Photini: about')
        dialog.setText(
            open(os.path.join(data_dir, 'about.html')).read() % (
                version, release))
        dialog.setDetailedText(
            open(os.path.join(data_dir, 'LICENSE.txt')).read())
        dialog.exec_()

    @QtCore.pyqtSlot(int, int)
    def new_split(self, pos, index):
        self.config_store.set(
            'main_window', 'split', str(self.central_widget.sizes()))

    @QtCore.pyqtSlot(int)
    def new_tab(self, index):
        self.tabs.currentWidget().refresh()
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
    if argv is None:
        argv = sys.argv
    # let PyQt handle its options
    app = QtGui.QApplication(argv)
    # parse remaining arguments
    try:
        opts, args = getopt.getopt(argv[1:], "h", ["help"])
    except getopt.error, msg:
        print >>sys.stderr, 'Error: %s\n' % msg
        print >>sys.stderr, __doc__.strip()
        return 1
    # process options
    for o, a in opts:
        if o in ("-h", "--help"):
            print __doc__.strip()
            return 0
    # create GUI and run application event loop
    main = MainWindow()
    main.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())
