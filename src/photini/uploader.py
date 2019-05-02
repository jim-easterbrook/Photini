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
import six
import shutil
import threading
import webbrowser

import appdirs
import keyring

from photini.metadata import Metadata
from photini.pyqt import (
    Busy, catch_all, Qt, QtCore, QtGui, QtWidgets, StartStopButton)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

class UploaderSession(object):
    def __init__(self, auto_refresh=True):
        self.auto_refresh = auto_refresh
        self.api = None

    def log_out(self):
        keyring.delete_password('photini', self.name)
        self.api = None

    def get_password(self):
        return keyring.get_password('photini', self.name)

    def set_password(self, password):
        if self.auto_refresh:
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

    def __init__(self, session_factory):
        super(UploadWorker, self).__init__()
        self.session = session_factory(auto_refresh=False)
        self.fileobj = None
        self.thread = QtCore.QThread(self)
        self.moveToThread(self.thread)

    def abort_upload(self):
        if self.fileobj:
            self.fileobj.close()
            self.fileobj = None

    @QtCore.pyqtSlot(object, object, object)
    @catch_all
    def upload_file(self, image, convert, params):
        if not self.session.permitted('write'):
            self.upload_file_done.emit(image, 'not permitted')
            return
        if convert:
            path = convert(image)
        else:
            path = image.path
        with open(path, 'rb') as f:
            self.fileobj = FileObjWithCallback(f, self.upload_progress.emit)
            error = self.session.do_upload(
                self.fileobj, imghdr.what(path), image, params)
        if convert:
            os.unlink(path)
        if self.fileobj:
            self.fileobj = None
            # upload wasn't aborted
            self.upload_file_done.emit(image, error)


class PhotiniUploader(QtWidgets.QWidget):
    upload_file = QtCore.pyqtSignal(object, object, object)

    def __init__(self, upload_config_widget, image_list, *arg, **kw):
        super(PhotiniUploader, self).__init__(*arg, **kw)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.shutdown)
        logger.debug('using %s', keyring.get_keyring().__module__)
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        self.session = self.session_factory()
        self.upload_worker = None
        self.connected = False
        # user details
        self.user = {}
        user_group = QtWidgets.QGroupBox(translate('PhotiniUploader', 'User'))
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
        self.user_connect = QtWidgets.QPushButton()
        self.user_connect.setCheckable(True)
        self.user_connect.clicked.connect(self.connect_user)
        self.layout().addWidget(self.user_connect, 1, 0, 1, 2)
        # 'service' specific widget
        self.layout().addWidget(upload_config_widget, 0, 2, 2, 2)
        # upload button
        self.upload_button = StartStopButton(
            translate('PhotiniUploader', 'Start upload'),
            translate('PhotiniUploader', 'Stop upload'))
        self.upload_button.setEnabled(False)
        self.upload_button.click_start.connect(self.start_upload)
        self.upload_button.click_stop.connect(self.stop_upload)
        self.layout().addWidget(self.upload_button, 2, 3)
        # progress bar
        self.layout().addWidget(
            QtWidgets.QLabel(translate('PhotiniUploader', 'Progress')), 2, 0)
        self.total_progress = QtWidgets.QProgressBar()
        self.layout().addWidget(self.total_progress, 2, 1, 1, 2)
        # adjust spacing
        self.layout().setColumnStretch(2, 1)
        self.layout().setRowStretch(0, 1)

    def tr(self, *arg, **kw):
        return QtCore.QCoreApplication.translate('PhotiniUploader', *arg, **kw)

    @QtCore.pyqtSlot()
    @catch_all
    def shutdown(self):
        if self.upload_worker:
            self.upload_worker.abort_upload()
            self.upload_worker.thread.quit()
            self.upload_worker.thread.wait()

    def refresh(self, force=False):
        with Busy():
            self.connected = (self.user_connect.isChecked() and
                              self.session.permitted('read'))
            if self.connected:
                self.user_connect.setText(translate('PhotiniUploader', 'Log out'))
                if force:
                    # load_user_data can be slow, so only do it when forced
                    try:
                        self.load_user_data()
                    except Exception as ex:
                        logger.error(ex)
                        self.connected = False
            if not self.connected:
                self.user_connect.setText(translate('PhotiniUploader', 'Log in'))
                # clearing user data is quick so do it anyway
                self.load_user_data()
            self.user_connect.setChecked(self.connected)
            self.upload_config.setEnabled(self.connected and not self.upload_worker)
            self.user_connect.setEnabled(not self.upload_worker)
            # enable or disable upload button
            self.new_selection(self.image_list.get_selected_images())

    @QtCore.pyqtSlot(bool)
    @catch_all
    def connect_user(self, connect):
        if connect:
            self.authorise('read')
        else:
            self.session.log_out()
        self.refresh(force=True)

    def load_user_data(self):
        if self.connected:
            self.show_user(*self.session.get_user())
        else:
            self.show_user(None, None)
        self.get_album_list()

    def do_not_close(self):
        if not self.upload_worker:
            return False
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(translate(
            'PhotiniUploader', 'Photini: upload in progress'))
        dialog.setText(translate(
            'PhotiniUploader',
            '<h3>Upload to {} has not finished.</h3>').format(self.service_name))
        dialog.setInformativeText(
            translate('PhotiniUploader', 'Closing now will terminate the upload.'))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(
            QtWidgets.QMessageBox.Close | QtWidgets.QMessageBox.Cancel)
        dialog.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        result = dialog.exec_()
        return result == QtWidgets.QMessageBox.Cancel

    def show_user(self, name, picture):
        if name:
            self.user_name.setText(translate(
                'PhotiniUploader',
                'Logged in as {0} on {1}').format(name, self.service_name))
        else:
            self.user_name.setText(translate(
                'PhotiniUploader',
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
                'PhotiniUploader',
                'File "{0}" is of type "{1}", which {2} does not' +
                ' accept and Photini cannot convert.')
            buttons = QtWidgets.QMessageBox.Ignore
        elif (self.image_types['rejected'] == '*' or
              image.file_type in self.image_types['rejected']):
            msg = translate(
                'PhotiniUploader',
                'File "{0}" is of type "{1}", which {2} does not' +
                ' accept. Would you like to convert it to JPEG?')
            buttons = QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Ignore
        else:
            msg = translate(
                'PhotiniUploader',
                'File "{0}" is of type "{1}", which {2} may not' +
                ' handle correctly. Would you like to convert it to JPEG?')
            buttons = QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(
            translate('PhotiniUploader', 'Photini: incompatible type'))
        dialog.setText(
            translate('PhotiniUploader', '<h3>Incompatible image type.</h3>'))
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
        if self.upload_worker:
            # invoke worker method in this thread as worker thread is busy
            self.upload_worker.abort_upload()
            # reset GUI
            self.upload_file_done(None, '')

    @QtCore.pyqtSlot()
    @catch_all
    def start_upload(self):
        if not self.image_list.unsaved_files_dialog(with_discard=False):
            self.upload_button.setChecked(False)
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
        if not self.authorise('write'):
            self.refresh(force=True)
            self.upload_button.setChecked(False)
            return
        # start uploading in separate thread, so GUI can continue
        self.upload_worker = UploadWorker(self.session_factory)
        self.upload_file.connect(self.upload_worker.upload_file)
        self.upload_worker.upload_progress.connect(self.total_progress.setValue)
        self.upload_worker.upload_file_done.connect(self.upload_file_done)
        self.upload_worker.thread.start()
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
                'PhotiniUploader', 'Photini: upload error'))
            dialog.setText(translate(
                'PhotiniUploader', '<h3>File "{}" upload failed.</h3>').format(
                    os.path.basename(image.path)))
            dialog.setInformativeText(error)
            dialog.setIcon(QtWidgets.QMessageBox.Warning)
            dialog.setStandardButtons(QtWidgets.QMessageBox.Abort |
                                      QtWidgets.QMessageBox.Retry)
            dialog.setDefaultButton(QtWidgets.QMessageBox.Retry)
            if dialog.exec_() == QtWidgets.QMessageBox.Abort:
                self.upload_button.setChecked(False)
        else:
            self.uploads_done += 1
        if (self.upload_button.isChecked() and
                    self.uploads_done < len(self.upload_list)):
            # start uploading next file (or retry same file)
            self.next_upload()
            return
        self.upload_button.setChecked(False)
        self.total_progress.setValue(0)
        self.total_progress.setFormat('%p%')
        self.upload_config.setEnabled(True)
        self.user_connect.setEnabled(True)
        self.upload_finished()
        self.upload_file.disconnect()
        self.upload_worker.upload_progress.disconnect()
        self.upload_worker.upload_file_done.disconnect()
        self.upload_worker.thread.quit()
        self.upload_worker.thread.wait()
        self.upload_worker = None
        # enable or disable upload button
        self.new_selection(self.image_list.get_selected_images())

    def auth_dialog(self, auth_url):
        if webbrowser.open(auth_url, new=2, autoraise=0):
            info_text = translate('PhotiniUploader', 'use your web browser')
        else:
            info_text = translate(
                'PhotiniUploader', 'open "{0}" in a web browser').format(
                    auth_url)
        auth_code, OK = QtWidgets.QInputDialog.getText(
            self,
            translate('PhotiniUploader', 'Photini: authorise {}').format(
                self.service_name),
            translate('PhotiniUploader', """Please {0} to grant access to Photini,
then enter the verification code:""").format(info_text))
        if OK:
            return six.text_type(auth_code).strip()
        return None

    def authorise(self, level):
        with Busy():
            if self.session.permitted(level):
                return True
            # do full authentication procedure
            auth_url = self.session.get_auth_url(level)
        auth_code = self.auth_dialog(auth_url)
        if not auth_code:
            return False
        with Busy():
            return self.session.get_access_token(auth_code, level)

    @QtCore.pyqtSlot(list)
    @catch_all
    def new_selection(self, selection):
        self.upload_button.setEnabled(
            self.upload_button.isChecked() or (
                len(selection) > 0 and self.connected))
