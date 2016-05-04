# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-16  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import threading
from six.moves.urllib.request import urlopen
from six.moves.urllib.error import URLError
import webbrowser

import six

from .pyqt import Busy, Qt, QtCore, QtGui, QtWidgets, StartStopButton

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
    upload_file_done = QtCore.pyqtSignal(object, str)

    def __init__(self, session_factory, params):
        super(UploadWorker, self).__init__()
        self.session = session_factory(auto_refresh=False)
        self.params = params
        self.fileobj = None
        self.thread = QtCore.QThread()
        self.moveToThread(self.thread)

    def abort_upload(self):
        if self.fileobj:
            self.fileobj.close()
            self.fileobj = None

    @QtCore.pyqtSlot(object, bool)
    def upload_file(self, image, convert):
        if not self.session.permitted('write'):
            self.upload_file_done.emit(image, 'not permitted')
            return
        if convert:
            path = image.as_jpeg()
        else:
            path = image.path
        with open(path, 'rb') as f:
            self.fileobj = FileObjWithCallback(f, self.upload_progress.emit)
            error = self.session.do_upload(
                self.fileobj, imghdr.what(path), image, self.params)
        if convert:
            os.unlink(path)
        if self.fileobj:
            self.fileobj = None
            # upload wasn't aborted
            self.upload_file_done.emit(image, error)


class PhotiniUploader(QtWidgets.QWidget):
    upload_file = QtCore.pyqtSignal(object, bool)

    def __init__(self, upload_config_widget, image_list, *arg, **kw):
        super(PhotiniUploader, self).__init__(*arg, **kw)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        self.session = self.session_factory()
        self.upload_worker = None
        self.connected = False
        # user details
        self.user = {}
        user_group = QtWidgets.QGroupBox(self.tr('User'))
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
        self.upload_button = StartStopButton(self.tr('Start upload'),
                                             self.tr('Stop upload'))
        self.upload_button.setEnabled(False)
        self.upload_button.click_start.connect(self.start_upload)
        self.upload_button.click_stop.connect(self.stop_upload)
        self.layout().addWidget(self.upload_button, 2, 3)
        # progress bar
        self.layout().addWidget(QtWidgets.QLabel(self.tr('Progress')), 2, 0)
        self.total_progress = QtWidgets.QProgressBar()
        self.layout().addWidget(self.total_progress, 2, 1, 1, 2)
        # adjust spacing
        self.layout().setColumnStretch(2, 1)
        self.layout().setRowStretch(0, 1)

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
                self.user_connect.setText(self.tr('Log out'))
                if force:
                    # load_user_data can be slow, so only do it when forced
                    try:
                        self.load_user_data()
                    except Exception as ex:
                        self.logger.error(ex)
                        self.connected = False
            if not self.connected:
                self.user_connect.setText(self.tr('Connect'))
                # clearing user data is quick so do it anyway
                self.load_user_data()
            self.user_connect.setChecked(self.connected)
            self.upload_config.setEnabled(self.connected and not self.upload_worker)
            self.user_connect.setEnabled(not self.upload_worker)
            # enable or disable upload button
            self.new_selection(self.image_list.get_selected_images())

    @QtCore.pyqtSlot(bool)
    def connect_user(self, connect):
        if connect:
            self.authorise('read')
        else:
            self.session.log_out()
        self.refresh(force=True)

    def do_not_close(self):
        if not self.upload_worker:
            return False
        dialog = QtWidgets.QMessageBox()
        dialog.setWindowTitle(self.tr('Photini: upload in progress'))
        dialog.setText(self.tr('<h3>Upload to {} has not finished.</h3>').format(
            self.service_name))
        dialog.setInformativeText(
            self.tr('Closing now will terminate the upload.'))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(
            QtWidgets.QMessageBox.Close | QtWidgets.QMessageBox.Cancel)
        dialog.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        result = dialog.exec_()
        return result == QtWidgets.QMessageBox.Cancel

    def show_user(self, name, picture):
        if name:
            self.user_name.setText(self.tr(
                'Connected to {0} on {1}').format(name, self.service_name))
        else:
            self.user_name.setText(self.tr(
                'Not connected to {}').format(self.service_name))
        pixmap = QtGui.QPixmap()
        if picture:
            try:
                pixmap.loadFromData(urlopen(picture).read())
            except URLError as ex:
                self.logger.error('cannot read %s: %s', picture, str(ex))
        self.user_photo.setPixmap(pixmap)

    @QtCore.pyqtSlot()
    def stop_upload(self):
        if self.upload_worker:
            # invoke worker method in this thread as worker thread is busy
            self.upload_worker.abort_upload()
            # reset GUI
            self.upload_file_done(None, '')

    @QtCore.pyqtSlot()
    def start_upload(self):
        if not self.image_list.unsaved_files_dialog(with_discard=False):
            self.upload_button.setChecked(False)
            return
        # make list of items to upload
        self.upload_list = []
        for image in self.image_list.get_selected_images():
            image_type = imghdr.what(image.path)
            if image_type in self.convert['types']:
                convert = False
            else:
                dialog = QtWidgets.QMessageBox(parent=self)
                dialog.setWindowTitle(self.tr('Photini: incompatible type'))
                dialog.setText(self.tr('<h3>Incompatible image type.</h3>'))
                dialog.setInformativeText(self.convert['msg'].format(
                        os.path.basename(image.path), image_type))
                dialog.setIcon(QtWidgets.QMessageBox.Warning)
                dialog.setStandardButtons(self.convert['buttons'])
                dialog.setDefaultButton(QtWidgets.QMessageBox.Yes)
                result = dialog.exec_()
                if result == QtWidgets.QMessageBox.Ignore:
                    continue
                convert = result == QtWidgets.QMessageBox.Yes
            self.upload_list.append((image, convert))
        if not self.upload_list:
            self.upload_button.setChecked(False)
            return
        if not self.authorise('write'):
            self.refresh(force=True)
            self.upload_button.setChecked(False)
            return
        # start uploading in separate thread, so GUI can continue
        self.upload_worker = UploadWorker(self.session_factory, self.get_upload_params())
        self.upload_file.connect(self.upload_worker.upload_file)
        self.upload_worker.upload_progress.connect(self.total_progress.setValue)
        self.upload_worker.upload_file_done.connect(self.upload_file_done)
        self.upload_worker.thread.start()
        self.upload_config.setEnabled(False)
        self.user_connect.setEnabled(False)
        self.uploads_done = 0
        self.next_upload()

    def next_upload(self):
        image, convert = self.upload_list[self.uploads_done]
        self.total_progress.setFormat('{} ({}/{}) %p%'.format(
            os.path.basename(image.path),
            1 + self.uploads_done, len(self.upload_list)))
        self.total_progress.setValue(0)
        QtWidgets.QApplication.processEvents()
        self.upload_file.emit(image, convert)

    @QtCore.pyqtSlot(object, str)
    def upload_file_done(self, image, error):
        if error:
            dialog = QtWidgets.QMessageBox(self)
            dialog.setWindowTitle(self.tr('Photini: upload error'))
            dialog.setText(self.tr('<h3>File "{}" upload failed.</h3>').format(
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
            info_text = self.tr('use your web browser')
        else:
            info_text = self.tr('open "{0}" in a web browser').format(auth_url)
        auth_code, OK = QtWidgets.QInputDialog.getText(
            self,
            self.tr('Photini: authorise {}').format(self.service_name),
            self.tr("""Please {0} to grant access to Photini,
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
            self.session.get_access_token(auth_code)
            return self.session.permitted(level)

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.upload_button.setEnabled(
            self.upload_button.isChecked() or (
                len(selection) > 0 and self.connected))
