# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import time
import urllib

import keyring
import PIL.Image as PIL
import requests

from photini import __version__
from photini.configstore import key_store
from photini.metadata import Metadata
from photini.pyqt import *
from photini.pyqt import using_pyside
from photini.widgets import Label, StartStopButton

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class UploadAborted(Exception):
    pass


class UploaderSession(QtCore.QObject):
    upload_progress = QtSignal(dict)
    new_token = QtSignal(dict)
    headers = {'User-Agent': 'Photini/' + __version__}

    def __init__(self, user_data={}, client_data={}, parent=None):
        super(UploaderSession, self).__init__(parent=parent)
        self.user_data = user_data
        self.client_data = client_data
        self.api = None
        self.open_connection()

    def open_connection(self):
        if not self.api:
            self.api = requests.Session()
            self.api.headers.update(self.headers)

    def close_connection(self):
        if self.api:
            self.api.close()
            self.api = None

    @staticmethod
    def check_response(rsp, decode=True):
        UploaderSession.check_interrupt()
        try:
            rsp.raise_for_status()
            if decode:
                rsp = rsp.json()
        except UploadAborted:
            raise
        except Exception as ex:
            logger.error(str(ex))
            return None
        return rsp

    @staticmethod
    def check_interrupt():
        if QtCore.QThread.currentThread().isInterruptionRequested():
            raise UploadAborted

    def progress(self, monitor):
        self.upload_progress.emit(
            {'value': monitor.bytes_read * 100 // monitor.len})

    def upload_files(self, upload_list):
        upload_count = 0
        for image, convert, params in upload_list:
            upload_count += 1
            self.upload_progress.emit({
                'label': '{} ({}/{})'.format(os.path.basename(image.path),
                                             upload_count, len(upload_list)),
                'busy': True})
            with self.open_file(image, convert) as (image_type, fileobj):
                error = self.do_upload(fileobj, image_type, image, params)
            if error:
                self.upload_progress.emit({'error': (image, error)})

    @contextmanager
    def open_file(self, image, convert):
        if convert:
            exiv_image, image_type = convert(image)
            exiv_io = exiv_image.io()
            fileobj = AbortableFileReader(io.BytesIO(exiv_io), exiv_io.size())
            try:
                yield image_type, fileobj
            finally:
                fileobj.close()
        else:
            fileobj = AbortableFileReader(
                open(image.path, 'rb'), os.stat(image.path).st_size)
            try:
                yield image.file_type, fileobj
            finally:
                fileobj.close()


class AbortableFileReader(object):
    def __init__(self, fileobj, size):
        super(AbortableFileReader, self).__init__()
        self._f = fileobj
        # requests library uses 'len' attribute instead of seeking to
        # end of file and back
        self.len = size

    # substitute read method
    def read(self, size):
        UploaderSession.check_interrupt()
        return self._f.read(size)

    # delegate all other attributes to file object
    def __getattr__(self, name):
        if name == 'getvalue':
            # don't allow requests library to suck in all data at once
            raise AttributeError(name)
        return getattr(self._f, name)


class UploadWorker(QtCore.QObject):
    finished = QtSignal()
    upload_progress = QtSignal(dict)

    def __init__(self, session, upload_list, *args, **kwds):
        super(UploadWorker, self).__init__(*args, **kwds)
        self.session = session
        self.upload_list = upload_list

    @QtSlot()
    @catch_all
    def start(self):
        with self.session(parent=self) as session:
            session.upload_progress.connect(self.upload_progress)
            try:
                session.upload_files(self.upload_list)
            except UploadAborted:
                pass
            except Exception as ex:
                logger.exception(ex)
        self.upload_progress.emit({'value': 0, 'label': None, 'busy': False})
        self.finished.emit()


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
        # dictionary of unavailable widgets (e.g. server version too low)
        self.unavailable = {}
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
        self.client_data = {'name': self.config_section}
        if key_store.config.has_section(self.config_section):
            for option in key_store.config.options(self.config_section):
                self.client_data[option] = key_store.get(
                    self.config_section, option)
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
        if keyring.get_password('photini', self.config_section):
            self.unauthorise()
            keyring.delete_password('photini', self.config_section)
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

    def unauthorise(self):
        pass

    def authorise(self):
        with Busy():
            # do full authentication procedure
            frob_or_uri = self.get_frob()
            if frob_or_uri:
                http_server = None
                auth_response = frob_or_uri
            else:
                # create temporary local web server
                http_server = HTTPServer(('127.0.0.1', 0), AuthRequestHandler)
                frob_or_uri = 'http://127.0.0.1:' + str(http_server.server_port)
            auth = self.auth_exchange(frob_or_uri)
            auth_url = next(auth)
            if not auth_url:
                self.logger.error('Failed to get auth URL')
                if http_server:
                    http_server.server_close()
                return
            if http_server:
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
        if http_server:
            server.finished.connect(dialog.close)
        execute(dialog)
        if http_server:
            auth_response = http_server.result
            server.running = False
        if not auth_response:
            return
        with Busy():
            try:
                auth.send(auth_response)
            except StopIteration:
                pass

    def get_frob(self):
        return None

    def get_password(self):
        return keyring.get_password('photini', self.config_section)

    def set_password(self, password):
        keyring.set_password('photini', self.config_section, password)


class AlbumList(QtWidgets.QWidget):
    def __init__(self, *arg, max_selected=0, **kw):
        super(AlbumList, self).__init__(*arg, **kw)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setSpacing(0)
        self.layout().setSizeConstraint(
            QtWidgets.QLayout.SizeConstraint.SetMinAndMaxSize)
        self.album_widgets = []
        self.max_selected = max_selected
        self.checked_widgets = []

    def add_album(self, album, index=-1):
        widget = QtWidgets.QCheckBox(album['title'].replace('&', '&&'))
        if album['description']:
            widget.setToolTip('<p>' + album['description'] + '</p>')
        widget.setEnabled(album['writeable'])
        widget.setProperty('id', album['id'])
        if self.max_selected:
            widget.stateChanged.connect(self.state_changed)
        if index >= 0:
            self.layout().insertWidget(index, widget)
            self.album_widgets.insert(index, widget)
        else:
            self.layout().addWidget(widget)
            self.album_widgets.append(widget)
        return widget

    @QtSlot(int)
    @catch_all
    def state_changed(self, state):
        for widget in list(self.checked_widgets):
            if not widget.isChecked():
                self.checked_widgets.remove(widget)
        for widget in self.get_checked_widgets():
            if widget not in self.checked_widgets:
                self.checked_widgets.append(widget)
        while len(self.checked_widgets) > self.max_selected:
            widget = self.checked_widgets.pop(0)
            widget.setChecked(False)

    def clear_albums(self):
        for widget in self.album_widgets:
            self.layout().removeWidget(widget)
            widget.setParent(None)
        self.album_widgets = []

    def get_checked_widgets(self):
        result = []
        for widget in self.album_widgets:
            if widget.isChecked():
                result.append(widget)
        return result

    def get_checked_ids(self):
        return [x.property('id') for x in self.get_checked_widgets()]


class PhotiniUploader(QtWidgets.QWidget):
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
        for layout, stretch in self.config_columns():
            self.config_layouts.append(layout)
            self.layout().addLayout(layout, 0, column_count)
            self.layout().setColumnStretch(column_count, stretch)
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

    def album_list(self, label=None, max_selected=0):
        # list of albums widget
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        group.setLayout(QtWidgets.QVBoxLayout())
        label = label or translate('UploaderTabsAll', 'Add to albums')
        group.layout().addWidget(QtWidgets.QLabel(label))
        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setFrameStyle(scrollarea.Shape.NoFrame)
        self.widget['albums'] = AlbumList(max_selected=max_selected)
        scrollarea.setWidget(self.widget['albums'])
        group.layout().addWidget(scrollarea)
        column.addWidget(group, 0, 0)
        return column

    @QtSlot()
    @catch_all
    def shutdown(self):
        self.stop_upload()
        while self.upload_worker and self.upload_worker.thread().isRunning():
            self.app.processEvents()

    @QtSlot(bool)
    @catch_all
    def connection_changed(self, connected):
        if 'albums' in self.widget:
            self.widget['albums'].clear_albums()
        self.user_widget.show_user(None, None)
        if connected:
            with Busy():
                for key, value in self.user_widget.on_connect(self.widget):
                    if key == 'connected':
                        connected = value
                        if not connected:
                            break
                    elif key == 'user':
                        self.user_widget.show_user(*value)
                    elif key == 'album':
                        self.widget['albums'].add_album(value)
                    self.app.processEvents()
        self.user_widget.connect_button.set_checked(connected)
        self.enable_config(connected and not self.upload_worker)
        self.user_widget.connect_button.setEnabled(not self.upload_worker)
        self.enable_upload_button()

    def enable_config(self, enabled):
        for layout in self.config_layouts:
            for idx in range(layout.count()):
                widget = layout.itemAt(idx).widget()
                if widget:
                    widget.setEnabled(enabled)
        for key in self.user_widget.unavailable:
            self.widget[key].setEnabled(
                enabled and not self.user_widget.unavailable[key])

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
                'name': os.path.basename(image.path),
                }

    def data_to_image(self, src):
        dst = dict(src)
        if dst['image']:
            return dst
        exiv_io = dst['data'].io()
        dst['image'] = PIL.open(io.BytesIO(exiv_io))
        dst['width'], dst['height'] = dst['image'].size
        return dst

    def image_to_data(self, src, mime_type=None, max_size=None):
        dst_mime_type = mime_type or src['mime_type']
        if src['data'] and src['mime_type'] == dst_mime_type and not (
                            max_size and src['data'].io().size() > max_size):
            return src
        src = self.data_to_image(src)
        w_src, h_src = src['width'], src['height']
        for scale in (1000, 680, 470, 330, 220, 150,
                      100, 68, 47, 33, 22, 15, 10, 7, 5, 3, 2, 1):
            dst = self.data_to_image(src)
            w_dst = w_src * scale // 1000
            h_dst = h_src * scale // 1000
            if scale != 1000:
                dst = self.resize_image(dst, w_dst, h_dst)
            dst_mime_type = mime_type or dst['mime_type']
            fmt = dst_mime_type.split('/')[1].upper()
            if dst_mime_type == 'image/jpeg':
                options = [{'quality': 95}, {'quality': 85}, {'quality': 75}]
            else:
                options = [{}]
            for option in options:
                dest_buf = io.BytesIO()
                dst['image'].save(dest_buf, format=fmt, **option)
                data = dest_buf.getbuffer()
                dst['data'] = src['metadata'].clone(data)
                dst['mime_type'] = dst_mime_type
                if not (max_size and dst['data'].io().size() > max_size):
                    logger.info('Converted %s from %dx%d to %dx%d JPEG',
                                src['name'], w_src, h_src, w_dst, h_dst)
                    return dst
        return None

    def resize_image(self, src, w, h):
        dst = self.data_to_image(src)
        dst['image'] = dst['image'].resize((w, h), resample=PIL.BICUBIC)
        dst['width'], dst['height'] = dst['image'].size
        dst['data'] = None
        dst['mime_type'] = 'image/jpeg'
        return dst

    def process_image(self, image):
        image = self.read_image(image)
        image = self.image_to_data(
            image, mime_type='image/jpeg',
            max_size=self.user_widget.max_size['image']['bytes'])
        return image['data'], image['mime_type']

    def copy_file_and_metadata(self, image):
        image = self.read_image(image)
        return image['data'], image['mime_type']

    def add_skip_button(self, dialog):
        return dialog.addButton(translate('UploaderTabsAll', 'Skip'),
                                dialog.ButtonRole.AcceptRole)

    def ask_resize_image(self, image, state, resizable=False, pixels=None):
        if 'ask_resize' not in state:
            state['ask_resize'] = True
        max_size = self.user_widget.max_size[image.file_type.split('/')[0]]
        if pixels:
            if 'pixels' not in max_size:
                return {}
            max_size = max_size['pixels']
            size = pixels
            text = translate(
                'UploaderTabsAll', 'File "{file_name}" has {size} pixels and'
                ' exceeds {service}\'s limit of {max_size} pixels.')
        else:
            max_size = max_size['bytes']
            size = os.stat(image.path).st_size
            text = translate(
                'UploaderTabsAll', 'File "{file_name}" has {size} bytes and'
                ' exceeds {service}\'s limit of {max_size} bytes.')
        if size <= max_size:
            return {}
        if resizable and not state['ask_resize']:
            return {'resize': True}
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(
            translate('UploaderTabsAll', 'Photini: too large'))
        dialog.setText('<h3>{}</h3>'.format(
            translate('UploaderTabsAll', 'File too large.')))
        text = text.format(
                file_name=os.path.basename(image.path), size=size,
                service=self.user_widget.service_name(), max_size=max_size)
        if resizable:
            text += ' ' + translate(
                'UploaderTabsAll', 'Would you like to resize it?')
            dialog.setStandardButtons(dialog.StandardButton.Yes |
                                      dialog.StandardButton.YesToAll)
        self.add_skip_button(dialog)
        dialog.setInformativeText(text)
        dialog.setIcon(dialog.Icon.Warning)
        result = execute(dialog)
        if result == dialog.StandardButton.Yes:
            return {'resize': True}
        if result == dialog.StandardButton.YesToAll:
            state['ask_resize'] = False
            return {'resize': True}
        return {'omit': True}

    def ask_convert_image(self, image, convertible=True, mime_type=None):
        mime_type = mime_type or image.file_type
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(translate(
            'UploaderTabsAll', 'Photini: incompatible type'))
        dialog.setText('<h3>{}</h3>'.format(translate(
            'UploaderTabsAll', 'Incompatible image type.')))
        dialog.setStandardButtons(dialog.StandardButton.Yes)
        dialog.setDefaultButton(dialog.StandardButton.Yes)
        self.add_skip_button(dialog)
        text = translate(
            'UploaderTabsAll', 'File "{file_name}" is of type "{file_type}",'
            ' which {service} may not handle correctly.'
            ).format(file_name=os.path.basename(image.path),
                     file_type=mime_type,
                     service=self.user_widget.service_name())
        if convertible:
            text += ' ' + translate(
                'UploaderTabsAll', 'Would you like to convert it to JPEG?')
            dialog.addButton(dialog.StandardButton.No)
        else:
            text += ' ' + translate(
                'UploaderTabsAll', 'Would you like to upload it anyway?')
        dialog.setInformativeText(text)
        dialog.setIcon(dialog.Icon.Warning)
        result = execute(dialog)
        if result == dialog.StandardButton.Yes:
            return ({}, {'convert': True})[convertible]
        if result == dialog.StandardButton.No:
            return {}
        return {'omit': True}

    def get_conversion_function(self, image, state, params):
        convert = {
            'omit': False,
            'resize': False,
            'convert': False,
            }
        mime_type = image.file_type
        if mime_type.startswith('video'):
            dims = image.metadata.dimensions
            if dims and dims['width'] and dims['height']:
                convert.update(self.ask_resize_image(
                    image, state, pixels=dims['width'] * dims['height']))
            if not any(convert.values()):
                convert.update(self.ask_resize_image(image, state))
            if not (any(convert.values()) or self.accepted_image_type(mime_type)):
                convert.update(self.ask_convert_image(
                    image, mime_type=mime_type, convertible=False))
            if any(convert.values()):
                return 'omit'
            return None
        readable = True
        try:
            tmp = self.data_to_image(self.read_image(image))
        except Exception as ex:
            logger.error(str(ex))
            readable = False
        if readable:
            convert.update(self.ask_resize_image(
                image, state, resizable=True,
                pixels=tmp['width'] * tmp['height']))
            mime_type = tmp['mime_type']
        if not (any(convert.values()) or self.accepted_image_type(mime_type)):
            convert.update(self.ask_convert_image(
                image, mime_type=mime_type, convertible=readable))
        if not any(convert.values()):
            convert.update(self.ask_resize_image(
                image, state, resizable=readable))
        if convert['omit']:
            return 'omit'
        if convert['resize'] or convert['convert']:
            return self.process_image
        if image.metadata.find_sidecar():
            # need to create file without sidecar
            return self.copy_file_and_metadata
        return None

    @QtSlot()
    @catch_all
    def stop_upload(self):
        if self.upload_worker:
            self.upload_worker.thread().requestInterruption()

    def get_selected_images(self):
        return self.app.image_list.get_selected_images()

    @QtSlot()
    @catch_all
    def start_upload(self):
        if not self.app.image_list.unsaved_files_dialog(with_discard=False):
            return
        # make list of items to upload
        upload_list = []
        state = {}
        for image in self.get_selected_images():
            params = self.get_upload_params(image, state)
            if params == 'abort':
                upload_list = []
                break
            if not params:
                continue
            convert = self.get_conversion_function(image, state, params)
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
            keywords = list(image.metadata.keywords)
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
        if 'error' in update:
            image, error = update['error']
            self.upload_error(os.path.basename(image.path), error)

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
                                  dialog.StandardButton.Ignore)
        dialog.setDefaultButton(dialog.StandardButton.Ignore)
        if execute(dialog) == dialog.StandardButton.Abort:
            self.stop_upload()

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

    def get_upload_params(self, image, first_time=True):
        # only used by Flickr & Ipernity, which have a lot in common
        # get user preferences for this upload
        upload_prefs, replace_prefs, photo_id = self.replace_dialog(image)
        if not upload_prefs:
            # user cancelled dialog or chose to do nothing
            return None
        # set service dependent params
        params = self.get_params(image, upload_prefs, replace_prefs, photo_id)
        # add common metadata
        if upload_prefs['new_photo'] or replace_prefs['metadata']:
            lang = self.user_widget.user_data['lang']
            # title & description
            params['metadata'] = {}
            if image.metadata.title:
                params['metadata']['title'] = image.metadata.title.best_match(lang)
            else:
                params['metadata']['title'] = image.name
            description = []
            if image.metadata.headline:
                description.append(image.metadata.headline)
            if image.metadata.description:
                description.append(image.metadata.description.best_match(lang))
            if description:
                params['metadata']['description'] = '\n\n'.join(description)
            # keywords
            keywords = []
            if image.metadata.keywords:
                keywords = image.metadata.keywords.human_tags()
                for keyword, (ns, predicate,
                              value) in image.metadata.keywords.machine_tags():
                    if (ns != self.user_widget.client_data['name'] or
                            predicate not in ('photo_id', 'doc_id', 'id')):
                        keywords.append(keyword)
                keywords = [x.replace('"', "'") for x in keywords]
                for n, keyword in enumerate(keywords):
                    if ',' in keyword:
                        keywords[n] = '"' + keyword + '"'
            keywords.append('uploaded:by=photini')
            params['keywords'] = {'keywords': ','.join(keywords)}
        return params

    def replace_dialog(self, image, options, replace=True):
        # has image already been uploaded?
        photo_id = self.uploaded_id(image)
        if not photo_id:
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
        return dict(self.upload_prefs), dict(self.replace_prefs), photo_id

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

    def uploaded_id(self, image):
        if not image.metadata.keywords:
            return None
        for keyword, (ns, predicate,
                      value) in image.metadata.keywords.machine_tags():
            if ns == self.user_widget.client_data['name'] and predicate in (
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
                photo_id = self.uploaded_id(image)
                if photo_id:
                    photo_ids[photo_id] = image
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
                                match.metadata.keywords) + [
                                    '{}:id={}'.format(
                                        self.user_widget.client_data['name'],
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
                value = [x for x in value if x != 'uploaded:by=photini']
            if value:
                old_value = getattr(md, key)
                if old_value:
                    value = old_value.merge(
                        '{}({})'.format(image.name, key),
                        self.user_widget.service_name(), value)
                setattr(md, key, value)

    def new_album_dialog(self):
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate('UploaderTabsAll', 'Create new album'))
        dialog.setLayout(FormLayout())
        return dialog

    def exec_album_dialog(self, dialog):
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addRow(button_box)
        return execute(dialog) == QtWidgets.QDialog.DialogCode.Accepted
