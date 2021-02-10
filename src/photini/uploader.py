# -*- coding: utf-8 -*-
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

from http.server import BaseHTTPRequestHandler, HTTPServer
import imghdr
import logging
import os
import shutil
import threading
import time
import urllib

import appdirs
import keyring

from photini.metadata import Metadata
from photini.pyqt import (
    Busy, catch_all, DisableWidget, Qt, QtCore, QtGui, QtSignal, QtSlot,
    QtWidgets, StartStopButton)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

class UploaderSession(QtCore.QObject):
    connection_changed = QtSignal(bool)

    @QtSlot()
    @catch_all
    def log_out(self):
        keyring.delete_password('photini', self.name)
        self.close_connection()

    def get_password(self):
        return keyring.get_password('photini', self.name)

    def set_password(self, password):
        keyring.set_password('photini', self.name, password)


class UploadAborted(Exception):
    pass


class FileObjWithCallback(object):
    def __init__(self, fileobj, callback):
        self._f = fileobj
        self._callback = callback
        # thread safe way to abort reading large file
        self._closing = threading.Event()
        self.abort = self._closing.set
        # requests library uses 'len' attribute instead of seeking to
        # end of file and back
        self.len = os.fstat(self._f.fileno()).st_size

    # substitute read method
    def read(self, size):
        if self._callback:
            self._callback(self._f.tell() * 100 // self.len)
        if self._closing.is_set():
            raise UploadAborted()
        return self._f.read(size)

    # delegate all other attributes to file object
    def __getattr__(self, name):
        return getattr(self._f, name)


class UploadWorker(QtCore.QObject):
    finished = QtSignal()
    upload_error = QtSignal(str, str)
    upload_progress = QtSignal(float, str)

    def __init__(self, session_factory, upload_list, *args, **kwds):
        super(UploadWorker, self).__init__(*args, **kwds)
        self.session_factory = session_factory
        self.upload_list = upload_list
        self.fileobj = None

    @QtSlot()
    @catch_all
    def start(self):
        session = self.session_factory()
        session.open_connection()
        upload_count = 0
        while upload_count < len(self.upload_list):
            image, convert, params = self.upload_list[upload_count]
            name = os.path.basename(image.path)
            self.upload_progress.emit(0.0, '{} ({}/{}) %p%'.format(
                name, 1 + upload_count, len(self.upload_list)))
            if convert:
                path = convert(image)
            else:
                path = image.path
            with open(path, 'rb') as f:
                self.fileobj = FileObjWithCallback(f, self.progress)
                try:
                    error = session.do_upload(
                        self.fileobj, imghdr.what(path), image, params)
                except UploadAborted:
                    break
                except Exception as ex:
                    error = str(ex)
                self.fileobj = None
            if convert:
                os.unlink(path)
            if error:
                self.retry = None
                self.upload_error.emit(name, error)
                # wait for response from user dialog
                while self.retry is None:
                    QtWidgets.QApplication.processEvents()
                if not self.retry:
                    break
            else:
                upload_count += 1
        self.upload_progress.emit(0.0, '%p%')
        session.close_connection()
        self.finished.emit()

    def progress(self, value):
        self.upload_progress.emit(value, '')

    @QtSlot(bool)
    @catch_all
    def abort_upload(self, retry):
        self.retry = retry
        if self.fileobj:
            # brutal way to interrupt an upload
            self.fileobj.abort()


class AuthRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format_, *args):
        logger.debug(format_, *args)

    @catch_all
    def do_GET(self):
        query = urllib.parse.urlsplit(self.path).query
        self.server.result = urllib.parse.parse_qs(query)
        logger.info('do_GET: %s', repr(self.server.result))
        title = translate('UploaderTabsAll', 'Close window')
        text = translate(
            'UploaderTabsAll', 'You may now close this browser window.')
        response = '''
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
"http://www.w3.org/TR/html4/strict.dtd">
<html>
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <title>{title}</title>
  </head>
  <body>
    <h1>{title}</h1>
    <p>{text}</p>
  </body>
</html>
'''.format(title=title, text=text)
        response = response.encode('utf-8')
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


class AuthServer(QtCore.QObject):
    finished = QtSignal()
    response = QtSignal(dict)

    @QtSlot()
    @catch_all
    def handle_requests(self):
        self.server.timeout = 10
        self.server.result = None
        # allow user 5 minutes to finish the process
        timeout = time.time() + 300
        while time.time() < timeout:
            self.server.handle_request()
            if self.server.result:
                self.response.emit(self.server.result)
                break
        self.server.server_close()
        self.finished.emit()


class PhotiniUploader(QtWidgets.QWidget):
    abort_upload = QtSignal(bool)

    def __init__(self, upload_config_widget, image_list, *arg, **kw):
        super(PhotiniUploader, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.app.aboutToQuit.connect(self.shutdown)
        logger.debug('using %s', keyring.get_keyring().__module__)
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        self.session = self.session_factory()
        self.session.connection_changed.connect(self.connection_changed)
        self.upload_worker = None
        # user details
        self.user = {}
        user_group = QtWidgets.QGroupBox(translate('UploaderTabsAll', 'User'))
        user_group.setLayout(QtWidgets.QVBoxLayout())
        self.user_photo = QtWidgets.QLabel()
        self.user_photo.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        user_group.layout().addWidget(self.user_photo)
        self.user_name = QtWidgets.QLabel()
        self.user_name.setWordWrap(True)
        self.user_name.setFixedWidth(80)
        user_group.layout().addWidget(self.user_name)
        user_group.layout().addStretch(1)
        self.layout().addWidget(user_group, 0, 0, 1, 2)
        # connect / disconnect button
        self.user_connect = StartStopButton(
            translate('UploaderTabsAll', 'Log in'),
            translate('UploaderTabsAll', 'Log out'))
        self.user_connect.click_start.connect(self.log_in)
        self.user_connect.click_stop.connect(self.session.log_out)
        self.layout().addWidget(self.user_connect, 1, 0, 1, 2)
        # 'service' specific widget
        self.layout().addWidget(upload_config_widget, 0, 2, 2, 2)
        # upload button
        self.upload_button = StartStopButton(
            translate('UploaderTabsAll', 'Start upload'),
            translate('UploaderTabsAll', 'Stop upload'))
        self.upload_button.setEnabled(False)
        self.upload_button.click_start.connect(self.start_upload)
        self.upload_button.click_stop.connect(self.stop_upload)
        self.layout().addWidget(self.upload_button, 2, 3)
        # progress bar
        self.layout().addWidget(
            QtWidgets.QLabel(translate('UploaderTabsAll', 'Progress')), 2, 0)
        self.total_progress = QtWidgets.QProgressBar()
        self.layout().addWidget(self.total_progress, 2, 1, 1, 2)
        # adjust spacing
        self.layout().setColumnStretch(2, 1)
        self.layout().setRowStretch(0, 1)
        # initialise as not connected
        self.connection_changed(False)

    def tr(self, *arg, **kw):
        return QtCore.QCoreApplication.translate('UploaderTabsAll', *arg, **kw)

    @QtSlot()
    @catch_all
    def shutdown(self):
        self.session.close_connection()

    @QtSlot(bool)
    @catch_all
    def connection_changed(self, connected):
        if connected:
            with Busy():
                self.show_user(*self.session.get_user())
                self.show_album_list(self.session.get_albums())
        else:
            self.show_user(None, None)
            self.show_album_list([])
        self.user_connect.set_checked(connected)
        self.upload_config.setEnabled(connected and not self.upload_worker)
        self.user_connect.setEnabled(not self.upload_worker)
        self.enable_upload_button()

    def refresh(self):
        if not self.user_connect.is_checked():
            self.log_in(do_auth=False)
        self.enable_upload_button()

    def do_not_close(self):
        if not self.upload_worker:
            return False
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(translate(
            'UploaderTabsAll', 'Photini: upload in progress'))
        dialog.setText(translate(
            'UploaderTabsAll',
            '<h3>Upload to {} has not finished.</h3>').format(self.service_name))
        dialog.setInformativeText(
            translate('UploaderTabsAll', 'Closing now will terminate the upload.'))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(
            QtWidgets.QMessageBox.Close | QtWidgets.QMessageBox.Cancel)
        dialog.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        result = dialog.exec_()
        return result == QtWidgets.QMessageBox.Cancel

    def show_user(self, name, picture):
        if name:
            self.user_name.setText(translate(
                'UploaderTabsAll',
                'Logged in as {0} on {1}').format(name, self.service_name))
        else:
            self.user_name.setText(translate(
                'UploaderTabsAll',
                'Not logged in to {}').format(self.service_name))
        pixmap = QtGui.QPixmap()
        if picture:
            pixmap.loadFromData(picture)
        self.user_photo.setPixmap(pixmap)

    def get_temp_filename(self, image, ext='.jpg'):
        temp_dir = appdirs.user_cache_dir('photini')
        if not os.path.isdir(temp_dir):
            os.makedirs(temp_dir)
        return os.path.join(temp_dir, os.path.basename(image.path) + ext)

    def copy_metadata(self, image, path):
        # copy metadata
        md = Metadata.clone(path, image.metadata)
        # save metedata, forcing IPTC creation
        md.dirty = True
        md.save(if_mode=True, sc_mode='none', force_iptc=True)

    def convert_to_jpeg(self, image):
        im = QtGui.QImage(image.path)
        path = self.get_temp_filename(image)
        im.save(path, format='jpeg', quality=95)
        self.copy_metadata(image, path)
        return path

    def copy_file_and_metadata(self, image):
        path = self.get_temp_filename(image, ext='')
        shutil.copyfile(image.path, path)
        self.copy_metadata(image, path)
        return path

    def is_convertible(self, image):
        if not image.file_type.startswith('image'):
            # can only convert images
            return False
        return QtGui.QImageReader(image.path).canRead()

    def get_conversion_function(self, image, params):
        if image.file_type in self.image_types['accepted']:
            if image.file_type.startswith('video'):
                # don't try to write metadata to videos
                return None
            if image.metadata.find_sidecar() or not image.metadata.iptc_in_file:
                # need to create file without sidecar and with IPTC
                return self.copy_file_and_metadata
            return None
        if not self.is_convertible(image):
            msg = translate(
                'UploaderTabsAll',
                'File "{0}" is of type "{1}", which {2} does not' +
                ' accept and Photini cannot convert.')
            buttons = QtWidgets.QMessageBox.Ignore
        elif (self.image_types['rejected'] == '*' or
              image.file_type in self.image_types['rejected']):
            msg = translate(
                'UploaderTabsAll',
                'File "{0}" is of type "{1}", which {2} does not' +
                ' accept. Would you like to convert it to JPEG?')
            buttons = QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Ignore
        else:
            msg = translate(
                'UploaderTabsAll',
                'File "{0}" is of type "{1}", which {2} may not' +
                ' handle correctly. Would you like to convert it to JPEG?')
            buttons = QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(
            translate('UploaderTabsAll', 'Photini: incompatible type'))
        dialog.setText(
            translate('UploaderTabsAll', '<h3>Incompatible image type.</h3>'))
        dialog.setInformativeText(msg.format(os.path.basename(image.path),
                                             image.file_type, self.service_name))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(buttons)
        dialog.setDefaultButton(QtWidgets.QMessageBox.Yes)
        result = dialog.exec_()
        if result == QtWidgets.QMessageBox.Ignore:
            return 'omit'
        if result == QtWidgets.QMessageBox.Yes:
            return self.convert_to_jpeg
        return None

    @QtSlot()
    @catch_all
    def stop_upload(self):
        self.abort_upload.emit(False)

    @QtSlot()
    @catch_all
    def start_upload(self):
        if not self.image_list.unsaved_files_dialog(with_discard=False):
            return
        # make list of items to upload
        upload_list = []
        for image in self.image_list.get_selected_images():
            params = self.get_upload_params(image)
            if not params:
                continue
            convert = self.get_conversion_function(image, params)
            if convert == 'omit':
                continue
            upload_list.append((image, convert, params))
        if not upload_list:
            self.upload_button.setChecked(False)
            return
        self.upload_button.set_checked(True)
        self.upload_config.setEnabled(False)
        self.user_connect.setEnabled(False)
        # do uploading in separate thread, so GUI can continue
        self.upload_worker = UploadWorker(self.session_factory, upload_list)
        thread = QtCore.QThread(self)
        self.upload_worker.moveToThread(thread)
        self.upload_worker.upload_error.connect(
            self.upload_error, Qt.BlockingQueuedConnection)
        self.abort_upload.connect(
            self.upload_worker.abort_upload, Qt.DirectConnection)
        self.upload_worker.upload_progress.connect(self.upload_progress)
        thread.started.connect(self.upload_worker.start)
        self.upload_worker.finished.connect(self.uploader_finished)
        self.upload_worker.finished.connect(thread.quit)
        self.upload_worker.finished.connect(self.upload_worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    @QtSlot(float, str)
    @catch_all
    def upload_progress(self, value, format_):
        self.total_progress.setValue(value)
        if format_:
            self.total_progress.setFormat(format_)

    @QtSlot(str, str)
    @catch_all
    def upload_error(self, name, error):
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle(translate(
            'UploaderTabsAll', 'Photini: upload error'))
        dialog.setText(translate(
            'UploaderTabsAll', '<h3>File "{}" upload failed.</h3>').format(
                name))
        dialog.setInformativeText(error)
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(QtWidgets.QMessageBox.Abort |
                                  QtWidgets.QMessageBox.Retry)
        dialog.setDefaultButton(QtWidgets.QMessageBox.Retry)
        self.abort_upload.emit(dialog.exec_() == QtWidgets.QMessageBox.Retry)

    @QtSlot()
    @catch_all
    def uploader_finished(self):
        self.upload_button.set_checked(False)
        self.upload_config.setEnabled(True)
        self.user_connect.setEnabled(True)
        self.upload_worker = None
        self.enable_upload_button()

    @QtSlot()
    @catch_all
    def log_in(self, do_auth=True):
        with DisableWidget(self.user_connect):
            with Busy():
                connect = self.session.open_connection()
            if connect is None:
                # can't reach server
                return
            if do_auth and not connect:
                self.authorise()

    def authorise(self):
        with Busy():
            # do full authentication procedure
            http_server = HTTPServer(('127.0.0.1', 0), AuthRequestHandler)
            redirect_uri = 'http://127.0.0.1:' + str(http_server.server_port)
            auth_url = self.session.get_auth_url(redirect_uri)
            if not auth_url:
                logger.error('Failed to get auth URL')
                http_server.server_close()
                return
            server = AuthServer()
            thread = QtCore.QThread(self)
            server.moveToThread(thread)
            server.server = http_server
            server.response.connect(self.auth_response)
            thread.started.connect(server.handle_requests)
            server.finished.connect(thread.quit)
            server.finished.connect(server.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.start()
            if QtGui.QDesktopServices.openUrl(QtCore.QUrl(auth_url)):
                return
            logger.error('Failed to open web browser')

    @QtSlot(dict)
    @catch_all
    def auth_response(self, result):
        with Busy():
            self.session.get_access_token(result)

    @QtSlot(list)
    @catch_all
    def new_selection(self, selection):
        self.enable_upload_button(selection=selection)

    def enable_upload_button(self, selection=None):
        if self.upload_button.is_checked():
            # can always cancel upload in progress
            self.upload_button.setEnabled(True)
            return
        if not self.user_connect.is_checked():
            # can't upload if not logged in
            self.upload_button.setEnabled(False)
            return
        if selection is None:
            selection = self.image_list.get_selected_images()
        self.upload_button.setEnabled(len(selection) > 0)
