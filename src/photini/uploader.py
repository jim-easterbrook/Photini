# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-19  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import imghdr
import logging
import os
import shutil
import threading

import six
from six.moves.BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from six.moves.urllib import parse

import appdirs
import keyring

from photini.metadata import Metadata
from photini.pyqt import (
    Busy, catch_all, Qt, QtCore, QtGui, QtWidgets, StartStopButton)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

class UploaderSession(QtCore.QObject):
    connection_changed = QtCore.pyqtSignal(bool)

    @QtCore.pyqtSlot()
    @catch_all
    def log_out(self):
        keyring.delete_password('photini', self.name)
        self.disconnect()

    def get_password(self):
        return keyring.get_password('photini', self.name)

    def set_password(self, password):
        keyring.set_password('photini', self.name, password)


class FileObjWithCallback(object):
    def __init__(self, fileobj, callback):
        self._f = fileobj
        self._callback = callback
        self._closing = threading.Event()
        # requests library uses 'len' attribute instead of seeking to
        # end of file and back
        self.len = os.fstat(self._f.fileno()).st_size

    # thread safe close method
    def close(self):
        self._closing.set()

    # substitute read method
    def read(self, size):
        if self._callback:
            self._callback(self._f.tell() * 100 // self.len)
        if self._closing.is_set():
            self._f.close()
        return self._f.read(size)

    # delegate all other attributes to file object
    def __getattr__(self, name):
        return getattr(self._f, name)


class UploadWorker(QtCore.QObject):
    upload_progress = QtCore.pyqtSignal(float)
    upload_file_done = QtCore.pyqtSignal(object, six.text_type)

    def __init__(self, session_factory, *args, **kwds):
        super(UploadWorker, self).__init__(*args, **kwds)
        self.session_factory = session_factory
        self.session = None
        self.fileobj = None

    @QtCore.pyqtSlot()
    @catch_all
    def start(self):
        self.session = self.session_factory()
        self.session.connect()

    def abort_upload(self):
        if self.fileobj:
            self.fileobj.close()
            self.fileobj = None

    @QtCore.pyqtSlot(object, object, object)
    @catch_all
    def upload_file(self, image, convert, params):
        if convert:
            path = convert(image)
        else:
            path = image.path
        with open(path, 'rb') as f:
            self.fileobj = FileObjWithCallback(f, self.upload_progress.emit)
            try:
                error = self.session.do_upload(
                    self.fileobj, imghdr.what(path), image, params)
            except Exception as ex:
                error = str(ex)
        if convert:
            os.unlink(path)
        if self.fileobj:
            self.fileobj = None
            self.upload_file_done.emit(image, error)
        else:
            # upload was aborted
            self.upload_file_done.emit(None, '')


class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format_, *args):
        logger.debug(format_, *args)

    @catch_all
    def do_GET(self):
        query = parse.urlsplit(self.path).query
        result = parse.parse_qs(query)
        logger.info('do_GET: %s', repr(result))
        if result:
            self.server.response.emit(result)
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
    response = QtCore.pyqtSignal(dict)

    def __init__(self, *args, **kwds):
        super(AuthServer, self).__init__(*args, **kwds)
        self.server = HTTPServer(('127.0.0.1', 0), RequestHandler)
        self.port = self.server.server_port
        self.server.timeout = 1
        self.server.response = self.response
        self.running = True

    @QtCore.pyqtSlot()
    @catch_all
    def start(self):
        while self.running:
            self.server.handle_request()
        self.server.server_close()


class PhotiniUploader(QtWidgets.QWidget):
    upload_file = QtCore.pyqtSignal(object, object, object)

    def __init__(self, upload_config_widget, image_list, *arg, **kw):
        super(PhotiniUploader, self).__init__(*arg, **kw)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.shutdown)
        logger.debug('using %s', keyring.get_keyring().__module__)
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        self.session = self.session_factory()
        self.session.connection_changed.connect(self.connection_changed)
        self.upload_worker = None
        self.auth_server = None
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

    @QtCore.pyqtSlot()
    @catch_all
    def shutdown(self):
        self.session.disconnect()
        if self.auth_server:
            self.auth_server.running = False
            self.auth_server_thread.quit()
            self.auth_server_thread.wait()
        if self.upload_worker:
            self.upload_worker.abort_upload()
            self.upload_worker_thread.quit()
            self.upload_worker_thread.wait()

    @QtCore.pyqtSlot(bool)
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
        self.refresh()

    def refresh(self):
        # enable or disable upload button
        self.new_selection(self.image_list.get_selected_images())

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
            if image.metadata._sc or not image.metadata._if.has_iptc():
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

    @QtCore.pyqtSlot()
    @catch_all
    def stop_upload(self):
        self.upload_button.set_checked(False)
        if self.upload_worker:
            self.upload_worker.abort_upload()
            self.upload_button.setEnabled(False)

    @QtCore.pyqtSlot()
    @catch_all
    def start_upload(self):
        if not self.image_list.unsaved_files_dialog(with_discard=False):
            return
        # make list of items to upload
        self.upload_list = []
        for image in self.image_list.get_selected_images():
            params = self.get_upload_params(image)
            if not params:
                continue
            convert = self.get_conversion_function(image, params)
            if convert == 'omit':
                continue
            self.upload_list.append((image, convert, params))
        if not self.upload_list:
            self.upload_button.setChecked(False)
            return
        self.upload_button.set_checked(True)
        # start uploading in separate thread, so GUI can continue
        self.upload_worker = UploadWorker(self.session_factory)
        self.upload_worker_thread = QtCore.QThread(self)
        self.upload_worker.moveToThread(self.upload_worker_thread)
        self.upload_file.connect(self.upload_worker.upload_file)
        self.upload_worker.upload_progress.connect(self.total_progress.setValue)
        self.upload_worker.upload_file_done.connect(self.upload_file_done)
        self.upload_worker_thread.started.connect(self.upload_worker.start)
        self.upload_worker_thread.start()
        self.upload_config.setEnabled(False)
        self.user_connect.setEnabled(False)
        self.uploads_done = 0
        self.next_upload()

    def next_upload(self):
        image, convert, params = self.upload_list[self.uploads_done]
        self.total_progress.setFormat('{} ({}/{}) %p%'.format(
            os.path.basename(image.path),
            1 + self.uploads_done, len(self.upload_list)))
        self.total_progress.setValue(0)
        QtWidgets.QApplication.processEvents()
        self.upload_file.emit(image, convert, params)

    @QtCore.pyqtSlot(object, six.text_type)
    @catch_all
    def upload_file_done(self, image, error):
        if error:
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle(translate(
                'UploaderTabsAll', 'Photini: upload error'))
            dialog.setText(translate(
                'UploaderTabsAll', '<h3>File "{}" upload failed.</h3>').format(
                    os.path.basename(image.path)))
            dialog.setInformativeText(error)
            dialog.setIcon(QtWidgets.QMessageBox.Warning)
            dialog.setStandardButtons(QtWidgets.QMessageBox.Abort |
                                      QtWidgets.QMessageBox.Retry)
            dialog.setDefaultButton(QtWidgets.QMessageBox.Retry)
            if dialog.exec_() == QtWidgets.QMessageBox.Abort:
                self.upload_button.set_checked(False)
        else:
            self.uploads_done += 1
        if (self.upload_button.is_checked() and
                    self.uploads_done < len(self.upload_list)):
            # start uploading next file (or retry same file)
            self.next_upload()
            return
        self.upload_button.set_checked(False)
        self.total_progress.setValue(0)
        self.total_progress.setFormat('%p%')
        self.upload_config.setEnabled(True)
        self.user_connect.setEnabled(True)
        self.upload_worker_thread.quit()
        self.upload_worker = None
        # enable or disable upload button
        self.refresh()

    @QtCore.pyqtSlot()
    @catch_all
    def log_in(self):
        if not self.session.connect():
            self.authorise()

    def authorise(self):
        with Busy():
            # do full authentication procedure
            if self.auth_server:
                self.auth_server.running = False
                self.auth_server_thread.quit()
            self.auth_server = AuthServer()
            self.auth_server_thread = QtCore.QThread(self)
            self.auth_server.moveToThread(self.auth_server_thread)
            self.auth_server.response.connect(self.auth_response)
            self.auth_server_thread.started.connect(self.auth_server.start)
            self.auth_server_thread.start()
            redirect_uri = 'http://127.0.0.1:' + str(self.auth_server.port)
            auth_url = self.session.get_auth_url(redirect_uri)
            if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(auth_url)):
                logger.error('Failed to open web browser')
                self.auth_server.running = False
                self.auth_server = None
                self.auth_server_thread.quit()

    @QtCore.pyqtSlot(dict)
    @catch_all
    def auth_response(self, result):
        self.auth_server.running = False
        self.auth_server = None
        self.auth_server_thread.quit()
        with Busy():
            self.session.get_access_token(result)

    @QtCore.pyqtSlot(list)
    @catch_all
    def new_selection(self, selection):
        self.upload_button.setEnabled(
            self.upload_button.is_checked() or (
                len(selection) > 0 and self.user_connect.is_checked()))
