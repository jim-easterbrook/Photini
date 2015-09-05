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

import six
from datetime import datetime
import imghdr
import logging
import os
from six.moves.urllib.request import urlopen
import webbrowser
import xml.etree.ElementTree as ET

import keyring
import requests
from requests_oauthlib import OAuth2Session

from .configstore import key_store
from .descriptive import MultiLineEdit
from .pyqt import Qt, QtCore, QtGui, QtWidgets
from .utils import Busy, FileObjWithCallback

EPOCH = datetime.utcfromtimestamp(0)

logger = logging.getLogger(__name__)

nsmap = {
    'atom'   : 'http://www.w3.org/2005/Atom',
    'gd'     : 'http://schemas.google.com/g/2005',
    'georss' : 'http://www.georss.org/georss',
    'gml'    : 'http://www.opengis.net/gml',
    'gphoto' : 'http://schemas.google.com/photos/2007',
    'media'  : 'http://search.yahoo.com/mrss/',
    }

for prefix, uri in nsmap.items():
    if prefix == 'atom':
        prefix = ''
    ET.register_namespace(prefix, uri)

class PicasaNode(object):
    _elements = {
        # name         namespace repeat node
        'access'    : ('gphoto', False, False),
        'category'  : ('atom',   False, False),
        'entry'     : ('atom',   True,  True),
        'group'     : ('media',  False, True),
        'id'        : ('gphoto', False, False),
        'keywords'  : ('media',  False, False),
        'location'  : ('gphoto', False, False),
        'numphotos' : ('gphoto', False, False),
        'Point'     : ('gml',    False, True),
        'pos'       : ('gml',    False, False),
        'summary'   : ('atom',   False, False),
        'thumbnail' : ('media',  True,  False),
        'timestamp' : ('gphoto', False, False),
        'title'     : ('atom',   False, False),
        'where'     : ('georss', False, True),
        }

    def __init__(self, dom=None, text=None):
        if text is not None:
            self._dom = ET.fromstring(text.encode('utf-8'))
        elif dom is not None:
            self._dom = dom
        else:
            self._dom = ET.Element('{' + nsmap['atom'] + '}entry')
        self.etag = self._dom.get('{' + nsmap['gd'] + '}etag')

    def __getattr__(self, name):
        if name not in self._elements:
            raise AttributeError(name)
        namespace, repeat, node = self._elements[name]
        tag = '{' + nsmap[namespace] + '}' + name
        if repeat:
            result = self._dom.findall(tag)
            if node:
                result = list(map(PicasaNode, result))
            return result
        result = self._dom.find(tag)
        if result is None:
            logger.debug('new %s', name)
            result = ET.SubElement(self._dom, tag)
        if node:
            result = PicasaNode(result)
        return result

    def to_string(self):
        return ET.tostring(self._dom, encoding='utf-8')

    def get_link(self, link_type):
        for child in self._dom.findall('atom:link', nsmap):
            if child.get('rel').endswith(link_type):
                return child.get('href')
        return None


class PicasaSession(object):
    auth_base_url = 'https://accounts.google.com/o/oauth2/auth'
    token_url     = 'https://www.googleapis.com/oauth2/v3/token'
    auth_scope    = 'https://picasaweb.google.com/data/'
    album_feed    = 'https://picasaweb.google.com/data/feed/api/user/default'

    def __init__(self):
        self.session = None

    def valid(self):
        refresh_token = keyring.get_password('photini', 'picasa')
        if refresh_token and self.session:
            return True
        self.session = None
        return False

    def authorise(self, auth_dialog):
        refresh_token = keyring.get_password('photini', 'picasa')
        if refresh_token and self.session:
            return True
        client_id     = key_store.get('picasa', 'client_id')
        client_secret = key_store.get('picasa', 'client_secret')
        if refresh_token:
            # create expired token
            token = {
                'access_token'  : 'xxx',
                'refresh_token' : refresh_token,
                'expires_in'    : -30,
                }
        else:
            # do full authentication procedure
            oauth = OAuth2Session(
                client_id, redirect_uri='urn:ietf:wg:oauth:2.0:oob',
                scope=self.auth_scope)
            auth_url, state = oauth.authorization_url(self.auth_base_url)
            auth_code = auth_dialog(auth_url)
            if not auth_code:
                self.session = None
                return False
            # Fix for requests-oauthlib bug #157
            # https://github.com/requests/requests-oauthlib/issues/157
            os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = 'True'
            token = oauth.fetch_token(
                self.token_url, code=auth_code, client_secret=client_secret)
            self._save_token(token)
        self.session = OAuth2Session(
            client_id, token=token, token_updater=self._save_token,
            auto_refresh_kwargs={
                'client_id'     : client_id,
                'client_secret' : client_secret},
            auto_refresh_url=self.token_url,
            )
        self.session.headers.update({'GData-Version': 2})
        return True

    def _save_token(self, token):
        keyring.set_password('photini', 'picasa', token['refresh_token'])

    def edit_node(self, node):
        resp = self._check_response(self.session.put(
            node.get_link('edit'), node.to_string(),
            headers={'If-Match' : node.etag,
                     'Content-Type' : 'application/atom+xml'}))
        return PicasaNode(text=resp.text)

    def get_albums(self):
        resp = self._check_response(self.session.get(self.album_feed))
        return PicasaNode(text=resp.text).entry

    def new_album(self, title):
        album = PicasaNode()
        album.title.text = title
        album.category.set('scheme', nsmap['gd'] + '#kind')
        album.category.set('term', nsmap['gphoto'] + '#album')
        resp = self._check_response(self.session.post(
            self.album_feed, album.to_string(),
            headers={'Content-Type' : 'application/atom+xml'}))
        return PicasaNode(text=resp.text)

    def delete_album(self, album):
        self._check_response(self.session.delete(
            album.get_link('edit'), headers={'If-Match' : album.etag}))

    def new_photo(self, title, album, data, image_type):
        resp = self._check_response(self.session.post(
            album.get_link('feed'), data=data,
            headers={'Content-Type' : 'image/' + image_type, 'Slug' : title}))
        return PicasaNode(text=resp.text)

    def _check_response(self, resp):
        if resp.status_code >= 300:
            logger.warning(resp.content)
        resp.raise_for_status()
        return resp


class UploadThread(QtCore.QThread):
    def __init__(self, picasa, upload_list, album):
        QtCore.QThread.__init__(self)
        self.picasa = picasa
        self.upload_list = upload_list
        self.album = album

    finished = QtCore.pyqtSignal()
    def run(self):
        self.file_count = 0
        for image, convert in self.upload_list:
            # upload photo
            title = os.path.basename(image.path)
            if convert:
                path = image.as_jpeg()
            else:
                path = image.path
            with open(path, 'rb') as f:
                fileobj = FileObjWithCallback(f, self.callback)
                photo = self.picasa.new_photo(
                    title, self.album, fileobj, imghdr.what(path))
            if convert:
                os.unlink(path)
            # set metadata
            photo.title.text = title
            title = image.metadata.title
            description = image.metadata.description
            if title and description:
                photo.summary.text = '{0}\n\n{1}'.format(title, description)
            elif title:
                photo.summary.text = title
            elif description:
                photo.summary.text = description
            keywords = image.metadata.keywords
            if keywords:
                photo.group.keywords.text = ','.join(keywords)
            latlong = image.metadata.latlong
            if latlong:
                photo.where.Point.pos.text = '{0} {1}'.format(*latlong.members())
            self.picasa.edit_node(photo)
            self.file_count += 1
        self.finished.emit()

    progress_report = QtCore.pyqtSignal(float, float)
    def callback(self, progress):
        total_progress = (
            (self.file_count * 100) + progress) / len(self.upload_list)
        self.progress_report.emit(progress, total_progress)

class PicasaUploader(QtWidgets.QWidget):
    def __init__(self, config_store, image_list, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        config_store.remove_section('picasa')
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        self.picasa = PicasaSession()
        self.widgets = {}
        self.current_album = None
        self.uploader = None
        ### album group
        self.album_group = QtWidgets.QGroupBox(self.tr('Album'))
        self.album_group.setLayout(QtWidgets.QHBoxLayout())
        self.layout().addWidget(self.album_group, 0, 0, 3, 3)
        ## album details, left hand side
        album_form_left = QtWidgets.QFormLayout()
        album_form_left.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.album_group.layout().addLayout(album_form_left)
        # album title / selector
        self.albums = QtWidgets.QComboBox()
        self.albums.setEditable(True)
        self.albums.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.albums.currentIndexChanged.connect(self.changed_album)
        self.albums.lineEdit().editingFinished.connect(self.new_title)
        album_form_left.addRow(self.tr('Title'), self.albums)
        # album description
        self.widgets['description'] = MultiLineEdit()
        self.widgets['description'].editingFinished.connect(self.new_description)
        album_form_left.addRow(
            self.tr('Description'), self.widgets['description'])
        # album location
        self.widgets['location'] = QtWidgets.QLineEdit()
        self.widgets['location'].editingFinished.connect(self.new_location)
        album_form_left.addRow(self.tr('Place taken'), self.widgets['location'])
        # album visibility
        self.widgets['access'] = QtWidgets.QComboBox()
        self.widgets['access'].addItem(self.tr('Public on the web'), 'public')
        self.widgets['access'].addItem(
            self.tr('Limited, anyone with the link'), 'private')
        self.widgets['access'].addItem(self.tr('Only you'), 'protected')
        self.widgets['access'].currentIndexChanged.connect(self.new_access)
        album_form_left.addRow(self.tr('Visibility'), self.widgets['access'])
        ## album buttons
        buttons = QtWidgets.QHBoxLayout()
        album_form_left.addRow('', buttons)
        # new album
        new_album_button = QtWidgets.QPushButton(self.tr('New album'))
        new_album_button.clicked.connect(self.new_album)
        buttons.addWidget(new_album_button)
        # delete album
        delete_album_button = QtWidgets.QPushButton(self.tr('Delete album'))
        delete_album_button.clicked.connect(self.delete_album)
        buttons.addWidget(delete_album_button)
        # other init
        self.clear_changes()
        ## album details, right hand side
        album_form_right = QtWidgets.QFormLayout()
        album_form_right.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.album_group.layout().addLayout(album_form_right)
        # album date
        self.widgets['timestamp'] = QtWidgets.QDateEdit()
        self.widgets['timestamp'].setCalendarPopup(True)
        self.widgets['timestamp'].editingFinished.connect(self.new_timestamp)
        album_form_right.addRow(self.tr('Date'), self.widgets['timestamp'])
        # album thumbnail
        self.album_thumb = QtWidgets.QLabel()
        album_form_right.addRow(self.album_thumb)
        ### upload button
        self.upload_button = QtWidgets.QPushButton(self.tr('Upload\nnow'))
        self.upload_button.setEnabled(False)
        self.upload_button.clicked.connect(self.upload)
        self.layout().addWidget(self.upload_button, 2, 3)
        ### progress bar
        self.layout().addWidget(QtWidgets.QLabel(self.tr('Progress')), 3, 0)
        self.total_progress = QtWidgets.QProgressBar()
        self.layout().addWidget(self.total_progress, 3, 1, 1, 3)
        self.setEnabled(False)
        # adjust spacing
        self.layout().setColumnStretch(2, 1)
        self.layout().setRowStretch(1, 1)
        # timer to store album data after it's edited
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.save_changes)

    def clear_changes(self):
        self.changed_title = None
        self.changed_description = None
        self.changed_location = None
        self.changed_access = None
        self.changed_timestamp = None

    @QtCore.pyqtSlot()
    def new_title(self):
        value = self.albums.lineEdit().text()
        self.albums.setItemText(self.albums.currentIndex(), value)
        if value != self.current_album.title.text:
            self.changed_title = value
        else:
            self.changed_title = None
        self.timer.start()

    @QtCore.pyqtSlot()
    def new_description(self):
        value = self.widgets['description'].get_value()
        if value != self.current_album.summary.text:
            self.changed_description = value
        else:
            self.changed_description = None
        self.timer.start()

    @QtCore.pyqtSlot()
    def new_timestamp(self):
        value = '{0:d}'.format(
            (self.widgets['timestamp'].dateTime().toPyDateTime() - EPOCH
             ).total_seconds() * 1000)
        if value != self.current_album.timestamp.text:
            self.changed_timestamp = value
        else:
            self.changed_timestamp = None
        self.timer.start()

    @QtCore.pyqtSlot()
    def new_location(self):
        value = self.widgets['location'].text()
        if value != self.current_album.location.text:
            self.changed_location = value
        else:
            self.changed_location = None
        self.timer.start()

    @QtCore.pyqtSlot(int)
    def new_access(self, index):
        value = self.widgets['access'].itemData(index)
        if value != self.current_album.access.text:
            self.changed_access = value
        else:
            self.changed_access = None
        self.timer.start()

    @QtCore.pyqtSlot()
    def new_album(self):
        self.save_changes()
        with Busy():
            self.current_album = self.picasa.new_album(self.tr('New album'))
        self.albums.insertItem(
            0, self.current_album.title.text, self.current_album.id.text)
        self.albums.setCurrentIndex(0)

    @QtCore.pyqtSlot()
    def delete_album(self):
        if int(self.current_album.numphotos.text) > 0:
            if QtWidgets.QMessageBox.question(
                self, self.tr('Delete album'),
                self.tr("""Are you sure you want to delete the album "{0}"?
Doing so will remove the album and its photos from all Google products."""
                        ).format(self.current_album.title.text),
                QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.Cancel
                ) == QtWidgets.QMessageBox.Cancel:
                return
        self.clear_changes()
        with Busy():
            self.picasa.delete_album(self.current_album)
        self.albums.removeItem(self.albums.currentIndex())
        if self.albums.count() == 0:
            self.new_album()

    def save_changes(self):
        no_change = True
        # title
        if self.changed_title:
            self.current_album.title.text = self.changed_title
            no_change = False
        # description
        if self.changed_description:
            self.current_album.summary.text = self.changed_description
            no_change = False
        # location
        if self.changed_location:
            self.current_album.location.text = self.changed_location
            no_change = False
        # access
        if self.changed_access:
            self.current_album.access.text = self.changed_access
            no_change = False
        # timestamp
        if self.changed_timestamp:
            self.current_album.timestamp.text = self.changed_timestamp
            no_change = False
        # upload changes
        self.clear_changes()
        if no_change:
            return
        with Busy():
            self.current_album = self.picasa.edit_node(self.current_album)

    def refresh(self):
        if self.picasa.valid():
            return
        self.albums.clear()
        QtWidgets.QApplication.processEvents()
        if not self.picasa.authorise(self.auth_dialog):
            self.setEnabled(False)
            return
        with Busy():
            for album in self.picasa.get_albums():
                if not album.get_link('edit'):
                    # ignore 'system' albums
                    continue
                self.albums.addItem(album.title.text, album.id.text)
            if self.albums.count() == 0:
                self.new_album()
        self.setEnabled(True)

    def do_not_close(self):
        if not self.uploader or self.uploader.isFinished():
            return False
        dialog = QtWidgets.QMessageBox()
        dialog.setWindowTitle(self.tr('Photini: upload in progress'))
        dialog.setText(self.tr('<h3>Upload to Picasa has not finished.</h3>'))
        dialog.setInformativeText(
            self.tr('Closing now will terminate the upload.'))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(
            QtWidgets.QMessageBox.Close | QtWidgets.QMessageBox.Cancel)
        dialog.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        result = dialog.exec_()
        return result == QtWidgets.QMessageBox.Cancel

    @QtCore.pyqtSlot(int)
    def changed_album(self, index):
        self.save_changes()
        self.current_album = None
        self.album_thumb.clear()
        self.widgets['description'].set_value(None)
        self.widgets['location'].clear()
        self.widgets['timestamp'].clear()
        if not self.picasa.valid():
            return
        album_id = self.albums.itemData(index)
        with Busy():
            for album in self.picasa.get_albums():
                if album.id.text == album_id:
                    self.current_album = album
                    break
            else:
                return
            if self.current_album.group.thumbnail is not None:
                url = self.current_album.group.thumbnail[0].get('url')
                image = QtGui.QPixmap()
                image.loadFromData(urlopen(url).read())
                self.album_thumb.setPixmap(image)
        self.widgets['timestamp'].setDateTime(datetime.utcfromtimestamp(
            float(self.current_album.timestamp.text) * 1.0e-3))
        value = self.current_album.summary.text
        if value:
            self.widgets['description'].set_value(value)
        value = self.current_album.location.text
        if value:
            self.widgets['location'].setText(value)
        self.widgets['access'].setCurrentIndex(
            self.widgets['access'].findData(self.current_album.access.text))

    @QtCore.pyqtSlot()
    def upload(self):
        if not self.image_list.unsaved_files_dialog(with_discard=False):
            return
        # make list of items to upload
        upload_list = []
        for image in self.image_list.get_selected_images():
            image_type = imghdr.what(image.path)
            if image_type in ('bmp', 'gif', 'jpeg', 'png'):
                convert = False
            else:
                dialog = QtWidgets.QMessageBox()
                dialog.setWindowTitle(self.tr('Photini: incompatible type'))
                dialog.setText(self.tr('<h3>Incompatible image type.</h3>'))
                dialog.setInformativeText(self.tr(
                    'File "{0}" is of type "{1}", which Picasa does not accept. Would you like to convert it to JPEG?').format(
                        os.path.basename(image.path), image_type))
                dialog.setIcon(QtWidgets.QMessageBox.Warning)
                dialog.setStandardButtons(QtWidgets.QMessageBox.Yes |
                                          QtWidgets.QMessageBox.Ignore)
                dialog.setDefaultButton(QtWidgets.QMessageBox.Yes)
                if dialog.exec_() != QtWidgets.QMessageBox.Yes:
                    continue
                convert = True
            upload_list.append((image, convert))
        if not upload_list:
            return
        # pass the list to a separate thread, so GUI can continue
        if self.picasa.authorise(self.auth_dialog):
            self.upload_button.setEnabled(False)
            self.album_group.setEnabled(False)
            self.uploader = UploadThread(
                self.picasa, upload_list, self.current_album)
            self.uploader.progress_report.connect(self.upload_progress)
            self.uploader.finished.connect(self.upload_done)
            self.uploader.start()
            # we've passed the picasa session to another thread, so
            # create a new one for safety
            self.picasa = PicasaSession()
            self.picasa.authorise(self.auth_dialog)

    @QtCore.pyqtSlot(float, float)
    def upload_progress(self, progress, total_progress):
        self.total_progress.setValue(total_progress)

    @QtCore.pyqtSlot()
    def upload_done(self):
        # reload current album
        self.changed_album(self.albums.currentIndex())
        self.upload_button.setEnabled(True)
        self.album_group.setEnabled(True)
        self.total_progress.setValue(0)
        self.uploader = None

    def auth_dialog(self, auth_url):
        if webbrowser.open(auth_url, new=2, autoraise=0):
            info_text = self.tr('use your web browser')
        else:
            info_text = self.tr('open "{0}" in a web browser').format(auth_url)
        auth_code, OK = QtWidgets.QInputDialog.getText(
            self,
            self.tr('Photini: authorise Picasa'),
            self.tr("""Please {0} to grant access to Photini,
then enter the verification code:""").format(info_text))
        if OK:
            return str(auth_code).strip()
        return None

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.upload_button.setEnabled(
            len(selection) > 0 and self.picasa.valid() and not self.uploader)
