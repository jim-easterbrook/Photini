# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-15  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import os
import webbrowser

import six

from .pyqt import QtCore, QtWidgets
from .utils import FileObjWithCallback

class UploadWorker(QtCore.QObject):
    upload_progress = QtCore.pyqtSignal(float)
    upload_finished = QtCore.pyqtSignal(object, str)

    @QtCore.pyqtSlot(object, object)
    def init_upload(self, session, params):
        self.session = session
        self.params = params

    @QtCore.pyqtSlot(object, bool)
    def upload_file(self, image, convert):
        if convert:
            path = image.as_jpeg()
        else:
            path = image.path
        with open(path, 'rb') as f:
            fileobj = FileObjWithCallback(f, self.upload_progress.emit)
            error = self.session.do_upload(
                fileobj, imghdr.what(path), image, self.params)
        if convert:
            os.unlink(path)
        self.upload_finished.emit(image, error)


class PhotiniUploader(QtWidgets.QWidget):
    init_upload = QtCore.pyqtSignal(object, object)
    upload_file = QtCore.pyqtSignal(object, bool)

    def __init__(self, upload_config, session_factory, image_list, parent):
        super(PhotiniUploader, self).__init__(parent)
        self.upload_config = upload_config
        self.session_factory = session_factory
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        self.upload_list = []
        self.session = self.session_factory()
        self.upload_config.set_session(self.session)
        self.initialised = False
        # 'service' specific widget
        self.layout().addWidget(self.upload_config, 0, 0, 2, 2)
        # upload button
        self.upload_button = QtWidgets.QPushButton(self.tr('Upload\nnow'))
        self.upload_button.setEnabled(False)
        self.upload_button.clicked.connect(self.upload)
        self.layout().addWidget(self.upload_button, 1, 2)
        # progress bar
        self.layout().addWidget(QtWidgets.QLabel(self.tr('Progress')), 2, 0)
        self.total_progress = QtWidgets.QProgressBar()
        self.layout().addWidget(self.total_progress, 2, 1, 1, 2)
        # adjust spacing
        self.layout().setColumnStretch(1, 1)
        self.layout().setRowStretch(0, 1)
        # create separate thread to upload images
        self.upload_thread = QtCore.QThread()
        self.upload_worker = UploadWorker()
        self.upload_worker.moveToThread(self.upload_thread)
        self.init_upload.connect(self.upload_worker.init_upload)
        self.upload_file.connect(self.upload_worker.upload_file)
        self.upload_worker.upload_progress.connect(self.total_progress.setValue)
        self.upload_worker.upload_finished.connect(self.upload_finished)
        self.upload_thread.start()

    def __del__(self):
        self.upload_thread.quit()
        self.upload_thread.wait()

    def refresh(self):
        if self.initialised and self.session.authorise():
            return
        self.upload_config.clear_sets()
        QtWidgets.QApplication.processEvents()
        if not self.session.authorise(self.auth_dialog):
            self.setEnabled(False)
            return
        self.setEnabled(True)
        self.upload_config.load_sets()
        self.initialised = True

    def do_not_close(self):
        if not self.upload_list:
            return False
        dialog = QtWidgets.QMessageBox()
        dialog.setWindowTitle(self.tr('Photini: upload in progress'))
        dialog.setText(self.tr('<h3>Upload to {} has not finished.</h3>').format(
            self.upload_config.service_name))
        dialog.setInformativeText(
            self.tr('Closing now will terminate the upload.'))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(
            QtWidgets.QMessageBox.Close | QtWidgets.QMessageBox.Cancel)
        dialog.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        result = dialog.exec_()
        return result == QtWidgets.QMessageBox.Cancel

    @QtCore.pyqtSlot()
    def upload(self):
        if not self.image_list.unsaved_files_dialog(with_discard=False):
            return
        # make list of items to upload
        self.upload_list = []
        self.uploads_done = []
        for image in self.image_list.get_selected_images():
            image_type = imghdr.what(image.path)
            if image_type in self.upload_config.convert['types']:
                convert = False
            else:
                dialog = QtWidgets.QMessageBox()
                dialog.setWindowTitle(self.tr('Photini: incompatible type'))
                dialog.setText(self.tr('<h3>Incompatible image type.</h3>'))
                dialog.setInformativeText(self.upload_config.convert['msg'].format(
                        os.path.basename(image.path), image_type))
                dialog.setIcon(QtWidgets.QMessageBox.Warning)
                dialog.setStandardButtons(self.upload_config.convert['buttons'])
                dialog.setDefaultButton(QtWidgets.QMessageBox.Yes)
                result = dialog.exec_()
                if result == QtWidgets.QMessageBox.Ignore:
                    continue
                convert = result == QtWidgets.QMessageBox.Yes
            self.upload_list.append((image, convert))
        # start uploading in separate thread, so GUI can continue
        if self.upload_list and self.session.authorise(self.auth_dialog):
            self.upload_button.setEnabled(False)
            self.upload_config.upload_started()
            self.init_upload.emit(
                self.session, self.upload_config.get_upload_params())
            self.next_upload()
            # we've passed the session object to a separate thread, so
            # create a new one for safety
            self.session = self.session_factory()
            self.session.authorise(self.auth_dialog)
            self.upload_config.set_session(self.session)

    def next_upload(self):
        image, convert = self.upload_list[len(self.uploads_done)]
        self.total_progress.setFormat('{} ({}/{}) %p%'.format(
            os.path.basename(image.path),
            len(self.uploads_done) + 1, len(self.upload_list)))
        self.total_progress.setValue(0)
        QtWidgets.QApplication.processEvents()
        self.upload_file.emit(image, convert)

    @QtCore.pyqtSlot(object, str)
    def upload_finished(self, image, error):
        if error:
            dialog = QtWidgets.QMessageBox()
            dialog.setWindowTitle(self.tr('Photini: upload error'))
            dialog.setText(self.tr('<h3>File "{}" upload failed.</h3>').format(
                os.path.basename(image.path)))
            dialog.setInformativeText(error)
            dialog.setIcon(QtWidgets.QMessageBox.Warning)
            dialog.setStandardButtons(QtWidgets.QMessageBox.Abort |
                                      QtWidgets.QMessageBox.Retry)
            dialog.setDefaultButton(QtWidgets.QMessageBox.Retry)
            if dialog.exec_() == QtWidgets.QMessageBox.Abort:
                self.upload_list = []
        else:
            self.uploads_done.append(image)
        if len(self.uploads_done) < len(self.upload_list):
            # start uploading next file
            self.next_upload()
        else:
            self.init_upload.emit(None, None)
            self.upload_list = []
            self.uploads_done = []
            self.upload_button.setEnabled(True)
            self.total_progress.setValue(0)
            self.total_progress.setFormat('%p%')
            self.upload_config.upload_finished()

    def auth_dialog(self, auth_url):
        if webbrowser.open(auth_url, new=2, autoraise=0):
            info_text = self.tr('use your web browser')
        else:
            info_text = self.tr('open "{0}" in a web browser').format(auth_url)
        auth_code, OK = QtWidgets.QInputDialog.getText(
            self,
            self.tr('Photini: authorise {}').format(self.upload_config.service_name),
            self.tr("""Please {0} to grant access to Photini,
then enter the verification code:""").format(info_text))
        if OK:
            return six.text_type(auth_code).strip()
        return None

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.upload_button.setEnabled(
            len(selection) > 0 and self.session.authorise() and not self.upload_list)
