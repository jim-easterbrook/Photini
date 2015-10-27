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
import threading
import webbrowser

import six

from .pyqt import QtCore, QtWidgets, StartStopButton

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
    upload_finished = QtCore.pyqtSignal(object, str)

    def __init__(self, session, params):
        super(UploadWorker, self).__init__()
        self.session = session
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
            self.upload_finished.emit(image, error)


class PhotiniUploader(QtWidgets.QWidget):
    upload_file = QtCore.pyqtSignal(object, bool)

    def __init__(self, upload_config, session_factory, image_list, parent):
        super(PhotiniUploader, self).__init__(parent)
        self.upload_config = upload_config
        self.session_factory = session_factory
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        self.session = self.session_factory()
        self.upload_config.set_session(self.session)
        self.initialised = False
        self.upload_worker = None
        # 'service' specific widget
        self.layout().addWidget(self.upload_config, 0, 0, 1, 3)
        # upload button
        self.upload_button = StartStopButton(self.tr('Start upload'),
                                             self.tr('Stop upload'))
        self.upload_button.setEnabled(False)
        self.upload_button.click_start.connect(self.start_upload)
        self.upload_button.click_stop.connect(self.stop_upload)
        self.layout().addWidget(self.upload_button, 1, 2)
        # progress bar
        self.layout().addWidget(QtWidgets.QLabel(self.tr('Progress')), 1, 0)
        self.total_progress = QtWidgets.QProgressBar()
        self.layout().addWidget(self.total_progress, 1, 1)
        # adjust spacing
        self.layout().setColumnStretch(1, 1)
        self.layout().setRowStretch(0, 1)

    def shutdown(self):
        if self.upload_worker:
            self.upload_worker.abort_upload()
            self.upload_worker.thread.quit()
            self.upload_worker.thread.wait()

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
        if not self.upload_worker:
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
    def stop_upload(self):
        if self.upload_worker:
            # invoke worker method in this thread as worker thread is busy
            self.upload_worker.abort_upload()
            # reset GUI
            self.upload_finished(None, '')

    @QtCore.pyqtSlot()
    def start_upload(self):
        if not self.image_list.unsaved_files_dialog(with_discard=False):
            self.upload_button.setChecked(False)
            return
        # make list of items to upload
        self.upload_list = []
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
        if not self.upload_list or not self.session.authorise(self.auth_dialog):
            self.upload_button.setChecked(False)
            return
        # start uploading in separate thread, so GUI can continue
        self.upload_worker = UploadWorker(
            self.session, self.upload_config.get_upload_params())
        self.upload_file.connect(self.upload_worker.upload_file)
        self.upload_worker.upload_progress.connect(self.total_progress.setValue)
        self.upload_worker.upload_finished.connect(self.upload_finished)
        self.upload_worker.thread.start()
        self.upload_config.upload_started()
        self.uploads_done = 0
        self.next_upload()
        # we've passed the session object to a separate thread, so
        # create a new one for safety
        self.session = self.session_factory()
        self.session.authorise(self.auth_dialog)
        self.upload_config.set_session(self.session)

    def next_upload(self):
        image, convert = self.upload_list[self.uploads_done]
        self.total_progress.setFormat('{} ({}/{}) %p%'.format(
            os.path.basename(image.path),
            1 + self.uploads_done, len(self.upload_list)))
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
        self.upload_config.upload_finished()
        self.upload_file.disconnect()
        self.upload_worker.upload_progress.disconnect()
        self.upload_worker.upload_finished.disconnect()
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
            self.tr('Photini: authorise {}').format(self.upload_config.service_name),
            self.tr("""Please {0} to grant access to Photini,
then enter the verification code:""").format(info_text))
        if OK:
            return six.text_type(auth_code).strip()
        return None

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.upload_button.setEnabled(
            self.upload_button.isChecked() or (
                len(selection) > 0 and self.session.authorise()))
