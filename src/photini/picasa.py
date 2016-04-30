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

import six
import logging
import os
from six.moves.urllib.request import urlopen
import xml.etree.ElementTree as ET

import keyring
import requests
from requests_oauthlib import OAuth2Session

from .configstore import config_store, key_store
from .descriptive import MultiLineEdit
from .pyqt import Busy, Qt, QtCore, QtGui, QtWidgets
from .uploader import PhotiniUploader

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


# general node, can be any kind of element
class PicasaNode(object):
    _elements = {
        # name         namespace repeat node
        'access'    : ('gphoto', False, False),
        'category'  : ('atom',   False, False),
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


# special node for the album feed, to disambiguate 'thumbnail'
class FeedNode(PicasaNode):
    _elements = {
        # name         namespace repeat node
        'entry'     : ('atom',   True,  True),
        'thumbnail' : ('gphoto', False, False),
        'nickname'  : ('gphoto', False, False),
        }


class PicasaSession(object):
    token_url     = 'https://www.googleapis.com/oauth2/v4/token'
    album_feed    = 'https://picasaweb.google.com/data/feed/api/user/default'
    scope = {
        'read' : 'https://picasaweb.google.com/data/',
        'write': 'https://picasaweb.google.com/data/',
        }

    def __init__(self, auto_refresh=True):
        self.auto_refresh = auto_refresh
        self.session = None
        self.token = None

    def log_out(self):
        keyring.delete_password('photini', 'picasa')
        self.session = None

    def permitted(self, level):
        refresh_token = keyring.get_password('photini', 'picasa')
        if not refresh_token:
            self.session = None
            self.token = None
            return False
        if not self.token:
            # create expired token
            self.token = {
                'access_token'  : 'xxx',
                'refresh_token' : refresh_token,
                'expires_in'    : -30,
                }
            self.session = None
        if not self.session:
            # create new session
            client_id     = key_store.get('picasa', 'client_id')
            client_secret = key_store.get('picasa', 'client_secret')
            auto_refresh_kwargs = {
                'client_id'    : client_id,
                'client_secret': client_secret,
                }
            if self.auto_refresh:
                self.session = OAuth2Session(
                    client_id, token=self.token, token_updater=self._save_token,
                    auto_refresh_kwargs=auto_refresh_kwargs,
                    auto_refresh_url=self.token_url,
                    )
            else:
                self.session = OAuth2Session(client_id, token=self.token)
            # refresh manually to get a valid token now
            self.token = self.session.refresh_token(
                self.token_url, **auto_refresh_kwargs)
            self.session.headers.update({'GData-Version': 2})
            # verify the token
            resp = self._check_response(self.session.get(
                'https://www.googleapis.com/oauth2/v3/tokeninfo',
                params={'access_token': self.token['access_token']})).json()
            if resp['scope'] != self.scope[level] or resp['aud'] != client_id:
                return False
        return True

    def get_auth_url(self, level):
        logger.info('using %s', keyring.get_keyring().__module__)
        client_id = key_store.get('picasa', 'client_id')
        self.session = OAuth2Session(
            client_id, scope=self.scope[level],
            redirect_uri='urn:ietf:wg:oauth:2.0:oob')
        return self.session.authorization_url(
            'https://accounts.google.com/o/oauth2/v2/auth')[0]

    def get_access_token(self, auth_code):
        # Fix for requests-oauthlib bug #157
        # https://github.com/requests/requests-oauthlib/issues/157
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = 'True'
        client_id = key_store.get('picasa', 'client_id')
        client_secret = key_store.get('picasa', 'client_secret')
        self.token = self.session.fetch_token(
            self.token_url, code=auth_code,
            auth=requests.auth.HTTPBasicAuth(client_id, client_secret))
        self._save_token(self.token)
        self.session = None

    def _save_token(self, token):
        if self.auto_refresh:
            keyring.set_password('photini', 'picasa', token['refresh_token'])

    def edit_node(self, node):
        resp = self._check_response(self.session.put(
            node.get_link('edit'), node.to_string(),
            headers={'If-Match' : node.etag,
                     'Content-Type' : 'application/atom+xml'}))
        return PicasaNode(text=resp.text)

    def get_feed(self):
        resp = self._check_response(self.session.get(
            self.album_feed, params={'kind': 'album'}))
        return FeedNode(text=resp.text)

    def new_album(self, album):
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

    def do_upload(self, fileobj, image_type, image, params):
        # upload photo
        title = os.path.basename(image.path)
        try:
            photo = self.new_photo(title, params, fileobj, image_type)
        except Exception as ex:
            return str(ex)
        # set metadata
        photo.title.text = title
        title = image.metadata.title
        description = image.metadata.description
        if title and description:
            photo.summary.text = title.value + '\n\n' + description.value
        elif title:
            photo.summary.text = title.value
        elif description:
            photo.summary.text = description.value
        keywords = image.metadata.keywords
        if keywords:
            photo.group.keywords.text = ','.join(keywords.value)
        latlong = image.metadata.latlong
        if latlong:
            photo.where.Point.pos.text = '{:.6f} {:.6f}'.format(
                latlong.lat, latlong.lon)
        try:
            self.edit_node(photo)
        except Exception as ex:
            return str(ex)
        return ''

    def _check_response(self, resp):
        if resp.status_code >= 300:
            logger.warning(resp.content)
        resp.raise_for_status()
        return resp


class PicasaUploadConfig(QtWidgets.QWidget):
    delete_album = QtCore.pyqtSignal()
    new_album = QtCore.pyqtSignal()
    select_album = QtCore.pyqtSignal(six.text_type)
    update_album = QtCore.pyqtSignal(dict)

    def __init__(self, *arg, **kw):
        super(PicasaUploadConfig, self).__init__(*arg, **kw)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.widgets = {}
        ## album details, left hand side
        album_group = QtWidgets.QGroupBox(self.tr('Collection / Album'))
        album_group.setLayout(QtWidgets.QHBoxLayout())
        album_form_left = QtWidgets.QFormLayout()
        album_form_left.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        album_group.layout().addLayout(album_form_left)
        # album title / selector
        self.albums = QtWidgets.QComboBox()
        self.albums.setEditable(True)
        self.albums.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.albums.activated.connect(self.switch_album)
        self.albums.lineEdit().editingFinished.connect(self.new_title)
        album_form_left.addRow(self.tr('Title'), self.albums)
        # album description
        self.widgets['description'] = MultiLineEdit(spell_check=True)
        self.widgets['description'].editingFinished.connect(self.new_album_details)
        album_form_left.addRow(
            self.tr('Description'), self.widgets['description'])
        # album location
        self.widgets['location'] = QtWidgets.QLineEdit()
        self.widgets['location'].editingFinished.connect(self.new_album_details)
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
        buttons.addStretch(stretch=60)
        album_form_left.addRow(buttons)
        # new album
        new_album_button = QtWidgets.QPushButton(self.tr('New album'))
        new_album_button.clicked.connect(self.new_album)
        buttons.addWidget(new_album_button, stretch=20)
        # delete album
        delete_album_button = QtWidgets.QPushButton(self.tr('Delete album'))
        delete_album_button.clicked.connect(self.delete_album)
        buttons.addWidget(delete_album_button, stretch=20)
        ## album details, right hand side
        album_form_right = QtWidgets.QFormLayout()
        album_form_right.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        album_group.layout().addLayout(album_form_right)
        # album date
        self.widgets['timestamp'] = QtWidgets.QDateEdit()
        self.widgets['timestamp'].setMinimumDateTime(
            QtCore.QDateTime.fromTime_t(0))
        self.widgets['timestamp'].setCalendarPopup(True)
        self.widgets['timestamp'].editingFinished.connect(self.new_album_details)
        album_form_right.addRow(self.tr('Date'), self.widgets['timestamp'])
        # album thumbnail
        self.album_thumb = QtWidgets.QLabel()
        album_form_right.addRow(self.album_thumb)
        self.layout().addWidget(album_group)

    @QtCore.pyqtSlot()
    def new_title(self):
        value = self.albums.lineEdit().text()
        self.albums.setItemText(self.albums.currentIndex(), value)
        self.new_album_details()

    @QtCore.pyqtSlot(int)
    def new_access(self, index):
        self.new_album_details()

    @QtCore.pyqtSlot()
    def new_album_details(self):
        new_values = {
            'title'       : self.albums.itemText(self.albums.currentIndex()),
            'description' : self.widgets['description'].get_value(),
            'location'    : self.widgets['location'].text(),
            'access'      : self.widgets['access'].itemData(
                self.widgets['access'].currentIndex()),
            'timestamp'   : '{:d}'.format(
                self.widgets['timestamp'].dateTime().toTime_t() * 1000),
            }
        self.update_album.emit(new_values)

    @QtCore.pyqtSlot(int)
    def switch_album(self, index):
        self.select_album.emit(self.albums.itemData(index))

    def show_album(self, album):
        if album:
            self.albums.setCurrentIndex(self.albums.findData(album.id.text))
            self.widgets['description'].set_value(album.summary.text)
            self.widgets['location'].setText(album.location.text)
            self.widgets['access'].setCurrentIndex(
                self.widgets['access'].findData(album.access.text))
            self.widgets['timestamp'].setDateTime(
                QtCore.QDateTime.fromTime_t(int(album.timestamp.text) // 1000))
            if album.group.thumbnail is not None:
                QtWidgets.QApplication.processEvents()
                with Busy():
                    url = album.group.thumbnail[0].get('url')
                    image = QtGui.QPixmap()
                    image.loadFromData(urlopen(url).read())
                    self.album_thumb.setPixmap(image)
        else:
            self.widgets['description'].set_value(None)
            self.widgets['location'].clear()
            self.widgets['timestamp'].clear()
            self.album_thumb.clear()


class PicasaUploader(PhotiniUploader):
    session_factory = PicasaSession

    def __init__(self, *arg, **kw):
        config_store.remove_section('picasa')
        self.upload_config = PicasaUploadConfig()
        self.upload_config.delete_album.connect(self.delete_album)
        self.upload_config.new_album.connect(self.new_album)
        self.upload_config.select_album.connect(self.select_album)
        self.upload_config.update_album.connect(self.update_album)
        super(PicasaUploader, self).__init__(self.upload_config, *arg, **kw)
        self.service_name = self.tr('Google Photos')
        self.convert = {
            'types'   : ('bmp', 'gif', 'jpeg', 'png'),
            'msg'     : self.tr(
                'File "{0}" is of type "{1}", which Google Photos does not' +
                ' accept. Would you like to convert it to JPEG?'),
            'buttons' : QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Ignore,
            }
        # timer to store album data after it's edited
        self.album_changed = False
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.save_changes)

    def get_albums(self, feed=None):
        if not feed:
            feed = self.session.get_feed()
        for album in feed.entry:
            if not album.get_link('edit'):
                # ignore 'system' albums
                continue
            yield album

    def load_user_data(self):
        self.current_album = None
        self.upload_config.albums.clear()
        if self.connected:
            feed = self.session.get_feed()
            self.show_user(feed.nickname.text, feed.thumbnail.text)
            for album in self.get_albums(feed):
                self.upload_config.albums.addItem(
                    album.title.text, album.id.text)
            self.set_current_album()
        else:
            self.show_user(None, None)
            self.upload_config.show_album(None)

    def get_upload_params(self):
        return self.current_album

    def upload_finished(self):
        # reload current album metadata (to update thumbnail)
        with Busy():
            self.set_current_album(self.current_album.id.text)

    @QtCore.pyqtSlot()
    def new_album(self):
        with Busy():
            self.save_changes()
            if not self.session.permitted('write'):
                self.refresh()
                return
            self.current_album = None
            self.upload_config.show_album(None)
            QtWidgets.QApplication.processEvents()
            album = PicasaNode()
            album.title.text = self.tr('New album')
            album.category.set('scheme', nsmap['gd'] + '#kind')
            album.category.set('term', nsmap['gphoto'] + '#album')
            album = self.session.new_album(album)
            self.upload_config.albums.addItem(album.title.text, album.id.text)
            self.set_current_album(album.id.text)

    @QtCore.pyqtSlot()
    def delete_album(self):
        album = self.current_album
        if int(album.numphotos.text) > 0:
            if QtWidgets.QMessageBox.question(
                self, self.tr('Delete album'),
                self.tr("""Are you sure you want to delete the album "{0}"?
Doing so will remove the album and its photos from all Google products."""
                        ).format(album.title.text),
                QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.Cancel
                ) == QtWidgets.QMessageBox.Cancel:
                return
        with Busy():
            self.timer.stop()
            self.album_changed = False
            if not self.session.permitted('write'):
                self.refresh()
                return
            self.current_album = None
            self.upload_config.show_album(None)
            QtWidgets.QApplication.processEvents()
            self.session.delete_album(album)
            self.upload_config.albums.removeItem(
                self.upload_config.albums.findData(album.id.text))
            self.set_current_album()

    @QtCore.pyqtSlot(six.text_type)
    def select_album(self, album_id):
        with Busy():
            self.save_changes()
            if not self.session.permitted('read'):
                self.refresh()
                return
            self.current_album = None
            self.upload_config.show_album(None)
            QtWidgets.QApplication.processEvents()
            self.set_current_album(album_id)

    @QtCore.pyqtSlot(dict)
    def update_album(self, new_values):
        if not self.current_album:
            return
        if new_values['title'] != self.current_album.title.text:
            self.current_album.title.text = new_values['title']
            self.album_changed = True
        if new_values['description'] != (self.current_album.summary.text or ''):
            self.current_album.summary.text = new_values['description']
            self.album_changed = True
        if new_values['location'] != (self.current_album.location.text or ''):
            self.current_album.location.text = new_values['location']
            self.album_changed = True
        if new_values['access'] != self.current_album.access.text:
            self.current_album.access.text = new_values['access']
            self.album_changed = True
        if new_values['timestamp'] != self.current_album.timestamp.text:
            self.current_album.timestamp.text = new_values['timestamp']
            self.album_changed = True
        if self.album_changed:
            self.timer.start()

    def set_current_album(self, album_id=None):
        if self.upload_config.albums.count() == 0:
            self.new_album()
            return
        if album_id is None:
            album_id = self.upload_config.albums.itemData(0)
        self.current_album = None
        for album in self.get_albums():
            if album.id.text == album_id:
                self.upload_config.show_album(album)
                self.current_album = album
                return
        self.upload_config.show_album(None)

    def shutdown(self):
        self.save_changes()
        super(PicasaUploader, self).shutdown()

    def save_changes(self):
        self.timer.stop()
        if not self.album_changed:
            return
        self.album_changed = False
        with Busy():
            self.session.edit_node(self.current_album)
            self.set_current_album(self.current_album.id.text)
