# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-23  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from contextlib import contextmanager
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import logging
import os
import re
import threading
import time
import urllib

import keyring
try:
    import PIL.Image as PIL
except ImportError:
    PIL = None
import requests

from photini.configstore import key_store
from photini.metadata import Metadata
from photini.pyqt import *
from photini.widgets import Label, StartStopButton

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

class UploaderSession(QtCore.QObject):
    upload_progress = QtSignal(dict)
    new_token = QtSignal(dict)

    def __init__(self, user_data={}, client_data={}, parent=None):
        super(UploaderSession, self).__init__(parent=parent)
        self.user_data = user_data
        self.client_data = client_data
        self.api = None
        self.open_connection()

    def close_connection(self):
        if self.api:
            self.api.close()
            self.api = None

    def progress(self, monitor):
        self.upload_progress.emit(
            {'value': monitor.bytes_read * 100 // monitor.len})


class UploadAborted(Exception):
    pass


class AbortableFileReader(QtCore.QObject):
    def __init__(self, fileobj, size, *args, **kwds):
        super(AbortableFileReader, self).__init__(*args, **kwds)
        self._f = fileobj
        # requests library uses 'len' attribute instead of seeking to
        # end of file and back
        self.len = size
        # thread safe way to abort reading large file
        self._closing = threading.Event()

    @QtSlot()
    @catch_all
    def abort_upload(self):
        self._closing.set()

    # substitute read method
    def read(self, size):
        if self._closing.is_set():
            raise UploadAborted()
        return self._f.read(size)

    # delegate all other attributes to file object
    def __getattr__(self, name):
        if name == 'getvalue':
            # don't allow requests library to suck in all data at once
            raise AttributeError(name)
        return getattr(self._f, name)


class UploadWorker(QtCore.QObject):
    finished = QtSignal()
    upload_error = QtSignal(str, str)
    upload_progress = QtSignal(dict)
    _abort_upload = QtSignal()

    def __init__(self, session, upload_list, *args, **kwds):
        super(UploadWorker, self).__init__(*args, **kwds)
        self.session = session
        self.upload_list = upload_list

    @contextmanager
    def open_file(self, image, convert):
        if convert:
            exiv_image, image_type = convert(image)
            exiv_io = exiv_image.io()
            exiv_io.open()
            fileobj = AbortableFileReader(
                io.BytesIO(exiv_io.mmap()), exiv_io.size(), parent=self)
            try:
                yield image_type, fileobj
            finally:
                fileobj.close()
                exiv_io.munmap()
                exiv_io.close()
        else:
            fileobj = AbortableFileReader(
                open(image.path, 'rb'), os.stat(image.path).st_size,
                parent=self)
            try:
                yield image.file_type, fileobj
            finally:
                fileobj.close()

    @QtSlot()
    @catch_all
    def start(self):
        with self.session(parent=self) as session:
            session.upload_progress.connect(self.upload_progress)
            upload_count = 0
            while upload_count < len(self.upload_list):
                image, convert, params = self.upload_list[upload_count]
                name = os.path.basename(image.path)
                self.upload_progress.emit({
                    'label': '{} ({}/{})'.format(
                         name, 1 + upload_count, len(self.upload_list)),
                    })
                try:
                    with self.open_file(image, convert) as (image_type, fileobj):
                        self._abort_upload.connect(
                            fileobj.abort_upload, Qt.ConnectionType.DirectConnection)
                        error = session.do_upload(
                            fileobj, image_type, image, params)
                except UploadAborted:
                    error = 'UploadAborted'
                except RuntimeError as ex:
                    error = str(ex)
                except Exception as ex:
                    logger.exception(ex)
                    error = '{}: {}'.format(type(ex), str(ex))
                self.upload_progress.emit({'busy': False})
                if error == 'UploadAborted':
                    break
                elif error:
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
        self.finished.emit()

    @QtSlot(bool)
    @catch_all
    def abort_upload(self, retry):
        self.retry = retry
        self._abort_upload.emit()


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

    @QtSlot()
    @catch_all
    def handle_requests(self):
        self.running = True
        self.server.timeout = 10
        self.server.result = None
        while self.running:
            self.server.handle_request()
            if self.server.result:
                break
        self.server.server_close()
        self.finished.emit()


class UploaderUser(QtWidgets.QGridLayout):
    connection_changed = QtSignal(bool)

    def __init__(self, *arg, **kw):
        super(UploaderUser, self).__init__(*arg, **kw)
        self.setContentsMargins(0, 0, 0, 0)
        # user details
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 17))
        group.setLayout(QtWidgets.QVBoxLayout())
        self.user_photo = QtWidgets.QLabel()
        self.user_photo.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        group.layout().addWidget(self.user_photo)
        self.user_name = QtWidgets.QLabel()
        self.user_name.setWordWrap(True)
        self.user_name.setMinimumWidth(10)
        group.layout().addWidget(self.user_name)
        group.layout().addStretch(1)
        self.addWidget(group, 0, 0)
        self.setRowStretch(0, 1)
        # connect / disconnect button
        self.connect_button = StartStopButton(
            translate('UploaderTabsAll', 'Log in'),
            translate('UploaderTabsAll', 'Log out'))
        self.connect_button.click_start.connect(self.log_in)
        self.connect_button.click_stop.connect(self.log_out)
        self.addWidget(self.connect_button, 1, 0)
        # other init
        self.client_data = {}
        if key_store.config.has_section(self.name):
            for option in key_store.config.options(self.name):
                self.client_data[option] = key_store.get(self.name, option)
        self.user_data = {}

    @contextmanager
    def session(self, **kw):
        try:
            session = self.new_session(**kw)
            yield session
        finally:
            session.close_connection()

    def show_user(self, name, picture):
        if name:
            name = name[:10].replace(' ', '\xa0') + name[10:]
            self.user_name.setText(translate(
                'UploaderTabsAll', 'Logged in as {user} on {service}'
                ).format(user=name, service=self.service_name()))
        else:
            self.user_name.setText(translate(
                'UploaderTabsAll', 'Not logged in to {service}'
                ).format(service=self.service_name()))
        pixmap = QtGui.QPixmap()
        if picture:
            pixmap.loadFromData(picture)
            max_width = self.user_photo.frameRect().width()
            if pixmap.width() > max_width:
                pixmap = pixmap.scaledToWidth(
                    max_width, Qt.TransformationMode.SmoothTransformation)
        self.user_photo.setPixmap(pixmap)

    @QtSlot()
    @catch_all
    def log_out(self):
        if keyring.get_password('photini', self.name):
            keyring.delete_password('photini', self.name)
        self.user_data = {}
        self.connection_changed.emit(False)

    @QtSlot()
    @catch_all
    def log_in(self, do_auth=True):
        with DisableWidget(self.connect_button):
            if self.load_user_data():
                self.connection_changed.emit(True)
            elif do_auth:
                self.authorise()

    def authorise(self):
        with Busy():
            # do full authentication procedure
            frob = self.get_frob()
            if frob:
                auth_url = self.get_auth_url(frob)
                if not auth_url:
                    self.logger.error('Failed to get auth URL')
                    return
                auth_response = frob
            else:
                auth_response = None
                # create temporary local web server
                http_server = HTTPServer(('127.0.0.1', 0), AuthRequestHandler)
                redirect_uri = 'http://127.0.0.1:' + str(http_server.server_port)
                auth_url = self.get_auth_url(redirect_uri)
                if not auth_url:
                    self.logger.error('Failed to get auth URL')
                    http_server.server_close()
                    return
                server = AuthServer()
                thread = QtCore.QThread(self)
                server.moveToThread(thread)
                server.server = http_server
                thread.started.connect(server.handle_requests)
                server.finished.connect(thread.quit)
                server.finished.connect(server.deleteLater)
                thread.finished.connect(thread.deleteLater)
                thread.start()
            if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(auth_url)):
                self.logger.error('Failed to open web browser')
                return
        # wait for user to authorise in web browser
        dialog = QtWidgets.QMessageBox(self.parentWidget())
        dialog.setWindowTitle(
            translate('UploaderTabsAll', 'Photini: authorise'))
        dialog.setText('<h3>{}</h3>'.format(translate(
            'UploaderTabsAll', 'Authorisation required')))
        dialog.setInformativeText(translate(
            'UploaderTabsAll', 'Please use your web browser to authorise'
            ' Photini, and then close this dialog.'))
        dialog.setIcon(dialog.Icon.Warning)
        dialog.setStandardButtons(dialog.StandardButton.Ok)
        if not frob:
            server.finished.connect(dialog.close)
        execute(dialog)
        if not frob:
            auth_response = http_server.result
            server.running = False
        if auth_response:
            with Busy():
                self.get_access_token(auth_response)

    def get_frob(self):
        return None

    def get_password(self):
        return keyring.get_password('photini', self.name)

    def set_password(self, password):
        keyring.set_password('photini', self.name, password)


class PhotiniUploader(QtWidgets.QWidget):
    abort_upload = QtSignal(bool)

    def __init__(self, *arg, **kw):
        super(PhotiniUploader, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.app.aboutToQuit.connect(self.shutdown)
        self.logger.debug('using %s', keyring.get_keyring().__module__)
        self.setLayout(QtWidgets.QGridLayout())
        self.upload_worker = None
        # dictionary of all widgets with parameter settings
        self.widget = {}
        # dictionary of control buttons
        self.buttons = {}
        ## first column is "user" widget
        self.user_widget.connection_changed.connect(self.connection_changed)
        self.layout().addLayout(self.user_widget, 0, 0)
        ## remaining columns are 'service' specific
        self.config_layouts = []
        column_count = 1
        for layout in self.config_columns():
            self.config_layouts.append(layout)
            self.layout().addLayout(layout, 0, column_count)
            column_count += 1
        self.layout().setColumnStretch(column_count - 1, 1)
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

    def album_list(self):
        # list of albums widget
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setLayout(QtWidgets.QVBoxLayout())
        group.layout().addWidget(QtWidgets.QLabel(
            translate('UploaderTabsAll', 'Add to albums')))
        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setFrameStyle(scrollarea.Shape.NoFrame)
        scrollarea.setStyleSheet("QScrollArea {background-color: transparent}")
        self.widget['albums'] = QtWidgets.QWidget()
        self.widget['albums'].setLayout(QtWidgets.QVBoxLayout())
        self.widget['albums'].layout().setSpacing(0)
        self.widget['albums'].layout().setSizeConstraint(
            QtWidgets.QLayout.SizeConstraint.SetMinAndMaxSize)
        scrollarea.setWidget(self.widget['albums'])
        self.widget['albums'].setAutoFillBackground(False)
        group.layout().addWidget(scrollarea)
        column.addWidget(group, 0, 0)
        return column

    @QtSlot()
    @catch_all
    def shutdown(self):
        if self.upload_worker:
            self.stop_upload()
        while self.upload_worker and self.upload_worker.thread().isRunning():
            self.app.processEvents()

    @QtSlot(bool)
    @catch_all
    def connection_changed(self, connected):
        if 'albums' in self.widget:
            self.clear_albums()
        self.user_widget.show_user(None, None)
        if connected:
            with Busy():
                with self.user_widget.session(parent=self) as session:
                    connected = session.authorised()
                    if connected:
                        self.user_widget.show_user(*session.get_user())
                        self.app.processEvents()
                        for album in session.get_albums():
                            self.add_album(album)
                            self.app.processEvents()
                        self.finalise_config(session)
        self.user_widget.connect_button.set_checked(connected)
        self.enable_config(connected and not self.upload_worker)
        self.user_widget.connect_button.setEnabled(not self.upload_worker)
        self.enable_upload_button()

    def finalise_config(self, session):
        # allow derived class to make any changes that require a connection
        pass

    def enable_config(self, enabled):
        for layout in self.config_layouts:
            for idx in range(layout.count()):
                widget = layout.itemAt(idx).widget()
                if widget:
                    widget.setEnabled(enabled)

    def refresh(self):
        if not self.user_widget.connect_button.is_checked():
            self.user_widget.log_in(do_auth=False)
        self.enable_upload_button()

    def do_not_close(self):
        if not self.upload_worker:
            return False
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(
            translate('UploaderTabsAll', 'Photini: upload in progress'))
        dialog.setText('<h3>{}</h3>'.format(translate(
            'UploaderTabsAll',  'Upload to {service} has not finished.'
            ).format(service=self.user_widget.service_name())))
        dialog.setInformativeText(translate(
            'UploaderTabsAll', 'Closing now will terminate the upload.'))
        dialog.setIcon(dialog.Icon.Warning)
        dialog.setStandardButtons(
            dialog.StandardButton.Close | dialog.StandardButton.Cancel)
        dialog.setDefaultButton(dialog.StandardButton.Cancel)
        result = execute(dialog)
        return result == dialog.StandardButton.Cancel

    def read_image(self, image):
        with open(image.path, 'rb') as f:
            data = f.read()
        return {'image': None,
                'width': None,
                'height': None,
                'data': image.metadata.clone(data),
                'mime_type': image.file_type,
                'metadata': image.metadata,
                }

    def data_to_image(self, src):
        dst = dict(src)
        if dst['image']:
            return dst
        exiv_io = dst['data'].io()
        exiv_io.open()
        data = exiv_io.mmap()
        if PIL:
            # use Pillow for good quality
            dst['image'] = PIL.open(io.BytesIO(data))
            dst['image'].load()
            dst['width'], dst['height'] = dst['image'].size
        else:
            # use Qt, lower quality but available
            buf = QtCore.QBuffer()
            buf.setData(bytes(data))
            reader = QtGui.QImageReader(buf)
            im = reader.read()
            if im.isNull():
                raise RuntimeError(reader.errorString())
            dst['image'] = im
            dst['width'] = dst['image'].width()
            dst['height'] = dst['image'].height()
        exiv_io.munmap()
        exiv_io.close()
        return dst

    def image_to_data(self, src, mime_type=None, max_size=None):
        dst_mime_type = mime_type or src['mime_type']
        if src['data'] and src['mime_type'] == dst_mime_type and not (
                            max_size and src['data'].io().size() > max_size):
            return src
        w, h = src['width'], src['height']
        for scale in (1000, 680, 470, 330, 220, 150,
                      100, 68, 47, 33, 22, 15, 10, 7, 5, 3, 2, 1):
            dst = self.data_to_image(src)
            if scale != 1000:
                dst = self.resize_image(
                    dst, w * scale // 1000, h * scale // 1000)
            dst_mime_type = mime_type or dst['mime_type']
            fmt = dst_mime_type.split('/')[1].upper()
            if dst_mime_type == 'image/jpeg':
                options = [{'quality': 95}, {'quality': 85}, {'quality': 75}]
            else:
                options = [{}]
            for option in options:
                if PIL:
                    dest_buf = io.BytesIO()
                    dst['image'].save(dest_buf, format=fmt, **option)
                    data = dest_buf.getbuffer()
                else:
                    dest_buf = QtCore.QBuffer()
                    dest_buf.open(dest_buf.OpenModeFlag.WriteOnly)
                    writer = QtGui.QImageWriter(dest_buf, fmt.encode('ascii'))
                    writer.setQuality(option['quality'])
                    if not writer.write(dst['image']):
                        raise RuntimeError(writer.errorString())
                    data = dest_buf.data().data()
                dst['data'] = src['metadata'].clone(data)
                dst['mime_type'] = dst_mime_type
                if not (max_size and dst['data'].io().size() > max_size):
                    return dst
        return None

    def resize_image(self, src, w, h):
        dst = self.data_to_image(src)
        if PIL:
            dst['image'] = dst['image'].resize(
                (w, h), resample=PIL.BICUBIC)
            dst['width'], dst['height'] = dst['image'].size
        else:
            dst['image'] = dst['image'].scaled(
                w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            dst['width'] = dst['image'].width()
            dst['height'] = dst['image'].height()
        dst['data'] = None
        dst['mime_type'] = 'image/jpeg'
        return dst

    def convert_to_jpeg(self, image):
        image = self.read_image(image)
        image = self.image_to_data(
            image, mime_type='image/jpeg', max_size=self.max_size['image'])
        return image['data'], image['mime_type']

    def copy_file_and_metadata(self, image):
        image = self.read_image(image)
        return image['data'], image['mime_type']

    def add_skip_button(self, dialog):
        return dialog.addButton(translate('UploaderTabsAll', 'Skip'),
                                dialog.ButtonRole.AcceptRole)

    def ask_resize_image(self, image, resizable=False):
        max_size = self.max_size[image.file_type.split('/')[0]]
        size = os.stat(image.path).st_size
        if size <= max_size:
            return None
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(
            translate('UploaderTabsAll', 'Photini: too large'))
        dialog.setText('<h3>{}</h3>'.format(
            translate('UploaderTabsAll', 'File too large.')))
        text = translate(
            'UploaderTabsAll', 'File "{file_name}" has {size} bytes and exceeds'
            ' {service}\'s limit of {max_size} bytes.').format(
                file_name=os.path.basename(image.path), size=size,
                service=self.user_widget.service_name(), max_size=max_size)
        if resizable:
            text += ' ' + translate(
                'UploaderTabsAll', 'Would you like to resize it?')
            dialog.setStandardButtons(dialog.StandardButton.Yes)
        self.add_skip_button(dialog)
        dialog.setInformativeText(text)
        dialog.setIcon(dialog.Icon.Warning)
        if execute(dialog) == dialog.StandardButton.Yes:
            return self.convert_to_jpeg
        return 'omit'

    def ask_convert_image(self, image):
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(translate(
            'UploaderTabsAll', 'Photini: incompatible type'))
        dialog.setText('<h3>{}</h3>'.format(translate(
            'UploaderTabsAll', 'Incompatible image type.')))
        dialog.setInformativeText(translate(
            'UploaderTabsAll', 'File "{file_name}" is of type "{file_type}",'
            ' which {service} may not handle correctly. Would you like to'
            ' convert it to JPEG?'
            ).format(file_name=os.path.basename(image.path),
                     file_type=image.file_type,
                     service=self.user_widget.service_name()))
        dialog.setIcon(dialog.Icon.Warning)
        dialog.setStandardButtons(dialog.StandardButton.Yes |
                                  dialog.StandardButton.No)
        self.add_skip_button(dialog)
        dialog.setDefaultButton(dialog.StandardButton.Yes)
        result = execute(dialog)
        if result == dialog.StandardButton.Yes:
            return self.convert_to_jpeg
        if result == dialog.StandardButton.No:
            return None
        return 'omit'

    def get_conversion_function(self, image, params):
        if image.file_type.startswith('video'):
            # videos in most formats are accepted, as long as not too large
            return self.ask_resize_image(image)
        convert = None
        if not self.accepted_image_type(image.file_type):
            convert = self.ask_convert_image(image)
        if not convert:
            convert = self.ask_resize_image(image, resizable=True)
        if (not convert) and image.metadata.find_sidecar():
            # need to create file without sidecar
            convert = self.copy_file_and_metadata
        return convert

    @QtSlot()
    @catch_all
    def stop_upload(self):
        self.abort_upload.emit(False)

    @QtSlot()
    @catch_all
    def start_upload(self):
        if not self.app.image_list.unsaved_files_dialog(with_discard=False):
            return
        # make list of items to upload
        upload_list = []
        for image in self.app.image_list.get_selected_images():
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
        self.user_widget.connect_button.setEnabled(False)
        self.upload_progress({'busy': True})
        # do uploading in separate thread, so GUI can continue
        self.upload_worker = UploadWorker(self.user_widget.session, upload_list)
        thread = QtCore.QThread(self)
        self.upload_worker.moveToThread(thread)
        self.upload_worker.upload_error.connect(
            self.upload_error, Qt.ConnectionType.BlockingQueuedConnection)
        self.abort_upload.connect(
            self.upload_worker.abort_upload, Qt.ConnectionType.DirectConnection)
        self.upload_worker.upload_progress.connect(self.upload_progress)
        thread.started.connect(self.upload_worker.start)
        self.upload_worker.finished.connect(self.uploader_finished)
        self.upload_worker.finished.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    @QtSlot(dict)
    @catch_all
    def upload_progress(self, update):
        if 'keyword' in update:
            # store photo id in image keywords, in main thread
            image, keyword = update['keyword']
            keywords = list(image.metadata.keywords or [])
            if keyword not in keywords:
                image.metadata.keywords = keywords + [keyword]
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
                    update['label'], Qt.TextElideMode.ElideLeft,
                    width_for_text(self.progress_label, 'X' * 20))
                self.progress_label.setText(elided)
            else:
                self.progress_label.setText(
                    translate('UploaderTabsAll', 'Progress'))

    @QtSlot(str, str)
    @catch_all
    def upload_error(self, name, error):
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle(
            translate('UploaderTabsAll', 'Photini: upload error'))
        dialog.setText('<h3>{}</h3>'.format(translate(
            'UploaderTabsAll', 'File "{file_name}" upload failed.'
            ).format(file_name=name)))
        dialog.setInformativeText(error)
        dialog.setIcon(dialog.Icon.Warning)
        dialog.setStandardButtons(dialog.StandardButton.Abort |
                                  dialog.StandardButton.Retry)
        dialog.setDefaultButton(dialog.StandardButton.Retry)
        self.abort_upload.emit(execute(dialog) == dialog.StandardButton.Retry)

    @QtSlot()
    @catch_all
    def uploader_finished(self):
        self.buttons['upload'].set_checked(False)
        self.enable_config(True)
        self.user_widget.connect_button.setEnabled(True)
        self.upload_worker = None
        self.enable_upload_button()

    def new_selection(self, selection):
        self.enable_upload_button(selection=selection)

    def enable_upload_button(self, selection=None):
        if self.buttons['upload'].is_checked():
            # can always cancel upload in progress
            self.buttons['upload'].setEnabled(True)
            return
        if not self.user_widget.connect_button.is_checked():
            # can't upload if not logged in
            self.buttons['upload'].setEnabled(False)
            return
        if selection is None:
            selection = self.app.image_list.get_selected_images()
        self.buttons['upload'].setEnabled(len(selection) > 0)
        if 'sync' in self.buttons:
            self.buttons['sync'].setEnabled(
                len(selection) > 0 and self.user_widget.connect_button.is_checked())

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
            params['meta'] = {}
            if image.metadata.title:
                params['meta']['title'] = image.metadata.title.default_text()
            else:
                params['meta']['title'] = image.name
            description = []
            if image.metadata.headline:
                description.append(image.metadata.headline)
            if image.metadata.description:
                description.append(image.metadata.description.default_text())
            if description:
                params['meta']['description'] = '\n\n'.join(description)
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
            'UploaderTabsAll', 'File {file_name} has already been uploaded to'
            ' {service}. How would you like to update it?').format(
                file_name=os.path.basename(image.path),
                service=self.user_widget.service_name()))
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
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addWidget(button_box)
        if execute(dialog) != QtWidgets.QDialog.DialogCode.Accepted:
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
            self.logger.error('HTTP error %d (%s)', rsp.status_code, icon_url)
            return None
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate('UploaderTabsAll', 'Select an image'))
        dialog.setLayout(FormLayout())
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(remote_icon)
        label = QtWidgets.QLabel()
        label.setPixmap(pixmap)
        dialog.layout().addRow(label, Label(translate(
            'UploaderTabsAll',
            'Which image file matches this picture on {service}?').format(
                service=self.user_widget.service_name()), lines=2))
        buttons = {}
        frame = QtWidgets.QFrame()
        frame.setLayout(FormLayout())
        for candidate in candidates:
            label = QtWidgets.QLabel()
            pixmap = candidate.image.pixmap()
            if pixmap:
                label.setPixmap(pixmap)
            else:
                label.setText(candidate.image.text())
            button = QtWidgets.QPushButton(
                os.path.basename(candidate.path))
            button.setToolTip('<p>' + candidate.path + '</p>')
            button.setCheckable(True)
            button.clicked.connect(dialog.accept)
            frame.layout().addRow(label, button)
            buttons[button] = candidate
        button = QtWidgets.QPushButton(translate('UploaderTabsAll', 'No match'))
        button.setDefault(True)
        button.clicked.connect(dialog.reject)
        frame.layout().addRow('', button)
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidget(frame)
        dialog.layout().addRow(scroll_area)
        with UnBusy():
            if execute(dialog) == QtWidgets.QDialog.DialogCode.Accepted:
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
        if ns == self.user_widget.name and predicate in (
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
            for image in self.app.image_list.get_selected_images():
                for keyword in image.metadata.keywords or []:
                    photo_id = self.uploaded_id(keyword)
                    if photo_id:
                        photo_ids[photo_id] = image
                        break
                else:
                    unknowns.append(image)
            with self.user_widget.session(parent=self) as session:
                if unknowns:
                    # get date range of photos without an id
                    search_min, search_max = datetime.max, datetime.min
                    for image in unknowns:
                        if not image.metadata.date_taken:
                            continue
                        min_taken_date, max_taken_date = self.date_range(image)
                        search_min = min(search_min, min_taken_date)
                        search_max = max(search_max, max_taken_date)
                    # search remote service
                    for photo_id, date_taken, icon_url in session.find_photos(
                            search_min, search_max):
                        if photo_id in photo_ids:
                            continue
                        # find local image that matches remote date & icon
                        match = self.find_local(unknowns, date_taken, icon_url)
                        if match:
                            match.metadata.keywords = list(
                                match.metadata.keywords or []) + [
                                    '{}:id={}'.format(self.user_widget.name,
                                                      photo_id)]
                            photo_ids[photo_id] = match
                            unknowns.remove(match)
                # merge remote metadata into file
                for photo_id, image in photo_ids.items():
                    self.merge_metadata(session, photo_id, image)

    def merge_metadata_items(self, image, data):
        md = image.metadata
        for key, value in data.items():
            if key == 'keywords':
                value = value or []
                value = [x for x in value if x != 'uploaded:by=photini']
            if value:
                old_value = getattr(md, key)
                if old_value:
                    value = old_value.merge(
                        '{}({})'.format(image.name, key),
                        self.user_widget.service_name(), value)
                setattr(md, key, value)
