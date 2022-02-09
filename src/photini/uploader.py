# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-22  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import imghdr
import logging
import os
import re
import shutil
import threading
import time
import urllib

import appdirs
import keyring
import requests

from photini.configstore import key_store
from photini.metadata import Metadata
from photini.pyqt import (
    Busy, catch_all, DisableWidget, execute, Qt, QtCore, QtGui, QtSignal,
    QtSlot, QtWidgets, StartStopButton, UnBusy, width_for_text)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

class UploaderSession(QtCore.QObject):
    connection_changed = QtSignal(bool)
    upload_progress = QtSignal(dict)

    def __init__(self, *arg, **kwds):
        super(UploaderSession, self).__init__(*arg, **kwds)
        self.api = None
        # get api client id and secret
        for option in key_store.config.options(self.name):
            setattr(self, option, key_store.get(self.name, option))

    @QtSlot()
    @catch_all
    def log_out(self):
        keyring.delete_password('photini', self.name)
        self.close_connection()

    def close_connection(self):
        self.connection_changed.emit(False)
        if self.api:
            self.api.close()
            self.api = None

    def get_password(self):
        return keyring.get_password('photini', self.name)

    def set_password(self, password):
        keyring.set_password('photini', self.name, password)

    def get_frob(self):
        return None


class UploadAborted(Exception):
    pass


class AbortableFileReader(object):
    def __init__(self, fileobj):
        self._f = fileobj
        # thread safe way to abort reading large file
        self._closing = threading.Event()
        self.abort = self._closing.set
        # requests library uses 'len' attribute instead of seeking to
        # end of file and back
        self.len = os.fstat(self._f.fileno()).st_size

    # substitute read method
    def read(self, size):
        if self._closing.is_set():
            raise UploadAborted()
        return self._f.read(size)

    # delegate all other attributes to file object
    def __getattr__(self, name):
        return getattr(self._f, name)


class UploadWorker(QtCore.QObject):
    finished = QtSignal()
    upload_error = QtSignal(str, str)
    upload_progress = QtSignal(dict)

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
        session.upload_progress.connect(self.upload_progress)
        upload_count = 0
        while upload_count < len(self.upload_list):
            image, convert, params = self.upload_list[upload_count]
            name = os.path.basename(image.path)
            self.upload_progress.emit({
                'label': '{} ({}/{})'.format(
                     name, 1 + upload_count, len(self.upload_list)),
                })
            if convert:
                path = convert(image)
            else:
                path = image.path
            with open(path, 'rb') as f:
                self.fileobj = AbortableFileReader(f)
                try:
                    error = session.do_upload(
                        self.fileobj, imghdr.what(path), image, params)
                except UploadAborted:
                    break
                except Exception as ex:
                    error = str(ex)
                self.upload_progress.emit({'busy': False})
                self.fileobj = None
            if convert:
                os.unlink(path)
            if error:
                if not session.api:
                    break
                self.retry = None
                self.upload_error.emit(name, error)
                # wait for response from user dialog
                while self.retry is None:
                    QtWidgets.QApplication.processEvents()
                if not self.retry:
                    break
            else:
                upload_count += 1
        self.upload_progress.emit({'value': 0, 'label': None, 'busy': False})
        session.close_connection()
        self.finished.emit()

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


class ConfigFormLayout(QtWidgets.QFormLayout):
    def __init__(self, wrapped=False, **kwds):
        super(ConfigFormLayout, self).__init__(**kwds)
        if wrapped:
            self.setRowWrapPolicy(self.WrapAllRows)
        self.setFieldGrowthPolicy(self.AllNonFixedFieldsGrow)


class PhotiniUploader(QtWidgets.QWidget):
    abort_upload = QtSignal(bool)

    def __init__(self, image_list, *arg, **kw):
        super(PhotiniUploader, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.app.aboutToQuit.connect(self.shutdown)
        logger.debug('using %s', keyring.get_keyring().__module__)
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        self.session = self.session_factory()
        self.session.connection_changed.connect(self.connection_changed)
        self.upload_worker = None
        # dictionary of all widgets with parameter settings
        self.widget = {}
        # dictionary of control buttons
        self.buttons = {}
        ## first column
        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.layout().addLayout(layout, 0, 0)
        # user details
        self.user = {}
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 17))
        group.setLayout(QtWidgets.QVBoxLayout())
        self.user_photo = QtWidgets.QLabel()
        self.user_photo.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        group.layout().addWidget(self.user_photo)
        self.user_name = QtWidgets.QLabel()
        self.user_name.setWordWrap(True)
        self.user_name.setMinimumWidth(10)
        group.layout().addWidget(self.user_name)
        group.layout().addStretch(1)
        layout.addWidget(group, 0, 0)
        layout.setRowStretch(0, 1)
        # connect / disconnect button
        self.buttons['connect'] = StartStopButton(
            translate('UploaderTabsAll', 'Log in'),
            translate('UploaderTabsAll', 'Log out'))
        self.buttons['connect'].click_start.connect(self.log_in)
        self.buttons['connect'].click_stop.connect(self.session.log_out)
        layout.addWidget(self.buttons['connect'], 1, 0)
        ## middle columns are 'service' specific
        self.config_layouts = []
        column_count = 1
        for layout in self.config_columns():
            self.config_layouts.append(layout)
            self.layout().addLayout(layout, 0, column_count)
            column_count += 1
        ## last column is list of albums
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setLayout(QtWidgets.QVBoxLayout())
        # list of albums widget
        group.layout().addWidget(
            QtWidgets.QLabel(translate('UploaderTabsAll', 'Add to albums')))
        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setFrameStyle(QtWidgets.QFrame.NoFrame)
        scrollarea.setStyleSheet("QScrollArea {background-color: transparent}")
        self.widget['albums'] = QtWidgets.QWidget()
        self.widget['albums'].setLayout(QtWidgets.QVBoxLayout())
        self.widget['albums'].layout().setSpacing(0)
        self.widget['albums'].layout().setSizeConstraint(
            QtWidgets.QLayout.SetMinAndMaxSize)
        scrollarea.setWidget(self.widget['albums'])
        self.widget['albums'].setAutoFillBackground(False)
        group.layout().addWidget(scrollarea)
        column.addWidget(group, 0, 0)
        self.config_layouts.append(column)
        self.layout().addLayout(column, 0, column_count)
        column_count += 1
        ## bottom row
        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.layout().addLayout(layout, 1, 0, 1, column_count)
        # progress bar
        self.progress_label = QtWidgets.QLabel()
        layout.addWidget(self.progress_label, 0, 0)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setFormat('%p%')
        layout.addWidget(self.progress_bar, 0, 1)
        layout.setColumnStretch(1, 1)
        self.upload_progress({'label': None, 'value': 0})
        # upload button
        self.buttons['upload'] = StartStopButton(
            translate('UploaderTabsAll', 'Start upload'),
            translate('UploaderTabsAll', 'Stop upload'))
        self.buttons['upload'].setEnabled(False)
        self.buttons['upload'].click_start.connect(self.start_upload)
        self.buttons['upload'].click_stop.connect(self.stop_upload)
        layout.addWidget(self.buttons['upload'], 0, 2)
        # initialise as not connected
        self.connection_changed(False)

    def tr(self, *arg, **kw):
        return QtCore.QCoreApplication.translate('UploaderTabsAll', *arg, **kw)

    @QtSlot()
    @catch_all
    def shutdown(self):
        if self.upload_worker:
            self.stop_upload()
        while self.upload_worker and self.upload_worker.thread().isRunning():
            self.app.processEvents()
        self.session.close_connection()

    @QtSlot(bool)
    @catch_all
    def connection_changed(self, connected):
        self.clear_albums()
        if connected:
            with Busy():
                self.show_user(*self.session.get_user())
                self.app.processEvents()
                for album in self.session.get_albums():
                    self.add_album(album)
                    self.app.processEvents()
                self.finalise_config()
        else:
            self.show_user(None, None)
        self.buttons['connect'].set_checked(connected)
        self.enable_config(connected and not self.upload_worker)
        self.buttons['connect'].setEnabled(not self.upload_worker)
        self.enable_upload_button()

    def finalise_config(self):
        # allow derived class to make any changes that require a connection
        pass

    def enable_config(self, enabled):
        for layout in self.config_layouts:
            for idx in range(layout.count()):
                widget = layout.itemAt(idx).widget()
                if widget:
                    widget.setEnabled(enabled)

    def refresh(self):
        if not self.buttons['connect'].is_checked():
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
        result = execute(dialog)
        return result == QtWidgets.QMessageBox.Cancel

    def show_user(self, name, picture):
        if name:
            self.user_name.setText(translate(
                'UploaderTabsAll',
                'Logged in as<br>{0} on {1}').format(name, self.service_name))
        else:
            self.user_name.setText(translate(
                'UploaderTabsAll',
                'Not logged in to {}').format(self.service_name))
        pixmap = QtGui.QPixmap()
        if picture:
            pixmap.loadFromData(picture)
        self.user_photo.setPixmap(pixmap)

    def get_temp_filename(self, image, ext='.jpg'):
        temp_dir = os.path.join(appdirs.user_cache_dir('photini'), 'uploader')
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

    def accepted_file_type(self, file_type):
        return file_type in ('image/gif', 'image/jpeg', 'image/png',
                             'video/mp4', 'video/quicktime', 'video/riff')

    def rejected_file_type(self, file_type):
        return file_type in ('image/x-canon-cr2',)

    def get_conversion_function(self, image, params):
        if self.accepted_file_type(image.file_type):
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
        elif self.rejected_file_type(image.file_type):
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
        result = execute(dialog)
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
            self.buttons['upload'].setChecked(False)
            return
        self.buttons['upload'].set_checked(True)
        self.enable_config(False)
        self.buttons['connect'].setEnabled(False)
        self.upload_progress({'busy': True})
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

    @QtSlot(dict)
    @catch_all
    def upload_progress(self, update):
        if 'busy' in update:
            if update['busy']:
                self.progress_bar.setMaximum(0)
            else:
                self.progress_bar.setMaximum(100)
        if 'value' in update:
            self.progress_bar.setValue(update['value'])
        if 'label' in update:
            if update['label']:
                elided = self.progress_label.fontMetrics().elidedText(
                    update['label'], Qt.ElideLeft,
                    width_for_text(self.progress_label, 'X' * 20))
                self.progress_label.setText(elided)
            else:
                self.progress_label.setText(translate(
                    'UploaderTabsAll', 'Progress'))

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
        self.abort_upload.emit(execute(dialog) == QtWidgets.QMessageBox.Retry)

    @QtSlot()
    @catch_all
    def uploader_finished(self):
        self.buttons['upload'].set_checked(False)
        self.enable_config(True)
        self.buttons['connect'].setEnabled(True)
        self.upload_worker = None
        self.enable_upload_button()

    @QtSlot()
    @catch_all
    def log_in(self, do_auth=True):
        with DisableWidget(self.buttons['connect']):
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
            frob = self.session.get_frob()
            if frob is not None:
                auth_url = self.session.get_auth_url(frob)
                if not auth_url:
                    logger.error('Failed to get auth URL')
                    return
            else:
                # create temporary local web server
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
            if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(auth_url)):
                logger.error('Failed to open web browser')
                return
        if not frob:
            # server will call auth_response with a token
            return
        # wait for user to authorise in web browser
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle(translate(
            'UploaderTabsAll', 'Photini: authorise'))
        dialog.setText(translate(
            'UploaderTabsAll', '<h3>Authorisation required</h3>'))
        dialog.setInformativeText(translate(
            'UploaderTabsAll', 'Please use your web browser to authorise'
            ' Photini, and then close this dialog.'))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(QtWidgets.QMessageBox.Ok)
        execute(dialog)
        with Busy():
            self.session.get_access_token(frob)

    @QtSlot(dict)
    @catch_all
    def auth_response(self, result):
        with Busy():
            self.session.get_access_token(result)

    def new_selection(self, selection):
        self.enable_upload_button(selection=selection)

    def enable_upload_button(self, selection=None):
        if self.buttons['upload'].is_checked():
            # can always cancel upload in progress
            self.buttons['upload'].setEnabled(True)
            return
        if not self.buttons['connect'].is_checked():
            # can't upload if not logged in
            self.buttons['upload'].setEnabled(False)
            return
        if selection is None:
            selection = self.image_list.get_selected_images()
        self.buttons['upload'].setEnabled(len(selection) > 0)
        if 'sync' in self.buttons:
            self.buttons['sync'].setEnabled(
                len(selection) > 0 and self.buttons['connect'].is_checked())

    def get_upload_params(self, image):
        # get user preferences for this upload
        upload_prefs, replace_prefs, photo_id = self.replace_dialog(image)
        if not upload_prefs:
            # user cancelled dialog or chose to do nothing
            return None
        # get config params that apply to all photos
        fixed_params = self.get_fixed_params()
        # set params
        params = self.get_variable_params(
            image, upload_prefs, replace_prefs, photo_id)
        if upload_prefs['new_photo']:
            # apply all "fixed" params
            params.update(fixed_params)
        else:
            # only apply the "fixed" params the user wants to change
            for key in fixed_params:
                if replace_prefs[key]:
                    params[key] = fixed_params[key]
        # add metadata
        if upload_prefs['new_photo'] or replace_prefs['metadata']:
            # title & description
            params['meta'] = {
                'title'      : image.metadata.title or image.name,
                'description': image.metadata.description or '',
                }
            # keywords
            keywords = ['uploaded:by=photini']
            for keyword in image.metadata.keywords or []:
                ns, predicate, value = self.machine_tag(keyword)
                if (ns in ('flickr', 'ipernity')
                        and predicate in ('photo_id', 'doc_id', 'id')):
                    # Photini "internal" tag
                    continue
                keyword = keyword.replace('"', "'")
                if ',' in keyword:
                    keyword = '"' + keyword + '"'
                keywords.append(keyword)
            params['keywords'] = {'keywords': ','.join(keywords)}
        return params

    def replace_dialog(self, image, options, replace=True):
        # has image already been uploaded?
        for keyword in image.metadata.keywords or []:
            photo_id = self.uploaded_id(keyword)
            if photo_id:
                break
        else:
            # new upload
            return {'new_photo': True}, {}, None
        # get user preferences
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate('UploaderTabsAll', 'Replace photo'))
        dialog.setLayout(QtWidgets.QVBoxLayout())
        message = QtWidgets.QLabel(translate(
            'UploaderTabsAll', 'File {0} has already been uploaded to {1}.'
            ' How would you like to update it?').format(
                os.path.basename(image.path), self.service_name))
        message.setWordWrap(True)
        dialog.layout().addWidget(message)
        replace_options = {}
        for key, label in options:
            replace_options[key] = QtWidgets.QCheckBox(label)
        for key in self.replace_prefs:
            replace_options[key].setChecked(self.replace_prefs[key])
        upload_options = {}
        if replace:
            upload_options['replace_image'] = QtWidgets.QRadioButton(
                translate('UploaderTabsAll', 'Replace image'))
        upload_options['new_photo'] = QtWidgets.QRadioButton(
            translate('UploaderTabsAll', 'Upload as new photo'))
        upload_options['no_upload'] = QtWidgets.QRadioButton(
            translate('UploaderTabsAll', 'No image upload'))
        for key in self.upload_prefs:
            if self.upload_prefs[key]:
                upload_options[key].setChecked(True)
                break
        else:
            upload_options['no_upload'].setChecked(True)
        two_columns = QtWidgets.QHBoxLayout()
        column = QtWidgets.QVBoxLayout()
        for key in replace_options:
            upload_options['new_photo'].toggled.connect(
                replace_options[key].setDisabled)
            column.addWidget(replace_options[key])
        two_columns.addLayout(column)
        column = QtWidgets.QVBoxLayout()
        for key in upload_options:
            column.addWidget(upload_options[key])
        column.addStretch(1)
        two_columns.addLayout(column)
        dialog.layout().addLayout(two_columns)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addWidget(button_box)
        if execute(dialog) != QtWidgets.QDialog.Accepted:
            return {}, {}, photo_id
        for key in replace_options:
            self.replace_prefs[key] = replace_options[key].isChecked()
        for key in upload_options:
            self.upload_prefs[key] = upload_options[key].isChecked()
        if self.upload_prefs['no_upload'] and not any(
                self.replace_prefs.values()):
            # user chose to do nothing
            return {}, {}, photo_id
        return self.upload_prefs, self.replace_prefs, photo_id

    def date_range(self, image):
        precision = min(image.metadata.date_taken['precision'], 6)
        min_taken_date = image.metadata.date_taken.truncate_datetime(
            image.metadata.date_taken['datetime'], precision)
        if precision >= 6:
            max_taken_date = min_taken_date + timedelta(seconds=1)
        elif precision >= 5:
            max_taken_date = min_taken_date + timedelta(minutes=1)
        elif precision >= 4:
            max_taken_date = min_taken_date + timedelta(hours=1)
        elif precision >= 3:
            max_taken_date = min_taken_date + timedelta(days=1)
        elif precision >= 2:
            max_taken_date = min_taken_date + timedelta(days=31)
        else:
            max_taken_date = min_taken_date + timedelta(days=366)
        max_taken_date -= timedelta(seconds=1)
        return min_taken_date, max_taken_date

    def find_local(self, unknowns, date_taken, icon_url):
        candidates = []
        for candidate in unknowns:
            if not candidate.metadata.date_taken:
                continue
            min_taken_date, max_taken_date = self.date_range(candidate)
            if date_taken < min_taken_date or date_taken > max_taken_date:
                continue
            candidates.append(candidate)
        if not candidates:
            return None
        # get user to choose matching image file
        rsp = requests.get(icon_url)
        if rsp.status_code == 200:
            remote_icon = rsp.content
        else:
            logger.error('HTTP error %d (%s)', rsp.status_code, icon_url)
            return None
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate('UploaderTabsAll', 'Select an image'))
        dialog.setLayout(ConfigFormLayout(wrapped=False))
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(remote_icon)
        label = QtWidgets.QLabel()
        label.setPixmap(pixmap)
        dialog.layout().addRow(label, QtWidgets.QLabel(translate(
            'UploaderTabsAll',
            'Which image file matches\nthis picture on {}?'.format(
                self.service_name))))
        divider = QtWidgets.QFrame()
        divider.setFrameStyle(QtWidgets.QFrame.HLine)
        dialog.layout().addRow(divider)
        buttons = {}
        for candidate in candidates:
            label = QtWidgets.QLabel()
            pixmap = candidate.image.pixmap()
            if pixmap:
                label.setPixmap(pixmap)
            else:
                label.setText(candidate.image.text())
            button = QtWidgets.QPushButton(
                os.path.basename(candidate.path))
            button.setToolTip(candidate.path)
            button.setCheckable(True)
            button.clicked.connect(dialog.accept)
            dialog.layout().addRow(label, button)
            buttons[button] = candidate
        button = QtWidgets.QPushButton(translate('UploaderTabsAll', 'No match'))
        button.setDefault(True)
        button.clicked.connect(dialog.reject)
        dialog.layout().addRow('', button)
        with UnBusy():
            if execute(dialog) == QtWidgets.QDialog.Accepted:
                for button, candidate in buttons.items():
                    if button.isChecked():
                        return candidate
        return None

    _machine_tag = re.compile('^(.+):(.+)=(.+)$')

    @classmethod
    def machine_tag(cls, keyword):
        match = cls._machine_tag.match(keyword)
        if not match:
            return None, None, None
        return match.groups()

    def uploaded_id(self, keyword):
        ns, predicate, value = self.machine_tag(keyword)
        if ns == self.session.name and predicate in (
                'photo_id', 'doc_id', 'id'):
            return value
        return None

    @QtSlot()
    @catch_all
    def sync_metadata(self):
        with Busy():
            # make list of known photo ids
            photo_ids = {}
            unknowns = []
            for image in self.image_list.get_selected_images():
                for keyword in image.metadata.keywords or []:
                    photo_id = self.uploaded_id(keyword)
                    if photo_id:
                        photo_ids[photo_id] = image
                        break
                else:
                    unknowns.append(image)
            # try to find unknowns on remote
            for image in unknowns:
                # get possible date range
                if not image.metadata.date_taken:
                    continue
                min_taken_date, max_taken_date = self.date_range(image)
                # search remote service
                for photo_id, date_taken, icon_url in self.session.find_photos(
                        min_taken_date, max_taken_date):
                    if photo_id in photo_ids:
                        continue
                    # find local image that matches remote date & icon
                    match = self.find_local(unknowns, date_taken, icon_url)
                    if match:
                        match.metadata.keywords = list(
                            match.metadata.keywords or []) + [
                                '{}:id={}'.format(self.session.name, photo_id)]
                        photo_ids[photo_id] = match
                        unknowns.remove(match)
            # merge remote metadata into file
            for photo_id, image in photo_ids.items():
                self.merge_metadata(photo_id, image)

    def merge_metadata_items(self, image, title=None, description=None,
                             keywords=[], date_taken=None, latlong=None,
                             location_taken=None):
        md = image.metadata
        # sync title
        if title:
            old_value = md.title
            md.title = title
            if old_value:
                md.title = md.title.merge(
                    image.name + '(title)', 'file value', old_value)
        # sync description
        if description:
            old_value = md.description
            md.description = description
            if old_value:
                md.description = md.description.merge(
                    image.name + '(description)', 'file value', old_value)
        # sync keywords
        keywords = [x for x in keywords if x != 'uploaded:by=photini']
        if keywords:
            old_value = md.keywords
            md.keywords = keywords
            if old_value:
                md.keywords = md.keywords.merge(
                    image.name + '(keywords)', 'file value', old_value)
        # sync date_taken
        if date_taken:
            date_taken, precision, tz_offset = date_taken
            old_value = md.date_taken
            if old_value:
                if precision is None:
                    precision = old_value['precision']
                if tz_offset is None:
                    tz_offset = old_value['tz_offset']
            md.date_taken = date_taken, precision, tz_offset
            if old_value:
                md.date_taken = md.date_taken.merge(
                    image.name + '(date_taken)', 'file value', old_value)
        # sync location
        if latlong:
            old_value = md.latlong
            md.latlong = latlong
            if old_value:
                md.latlong = md.latlong.merge(
                    image.name + '(latlong)', 'file value', old_value)
        # sync address
        if location_taken:
            old_value = md.location_taken
            md.location_taken = location_taken
            if old_value:
                md.location_taken = md.location_taken.merge(
                    image.name + '(location_taken)', 'file value', old_value)
