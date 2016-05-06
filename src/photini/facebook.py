##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2016  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
from collections import defaultdict
import logging
import os
from six.moves.urllib.request import urlopen

import keyring
import oauthlib
import pkg_resources
import requests
from requests_oauthlib import OAuth2Session
from requests_toolbelt import MultipartEncoder

from .configstore import config_store, key_store
from .descriptive import MultiLineEdit, SingleLineEdit
from .pyqt import Busy, Qt, QtCore, QtGui, QtWebKitWidgets, QtWidgets
from .uploader import PhotiniUploader

logger = logging.getLogger(__name__)

class FacebookSession(object):
    scope = {
        'read' : 'user_photos',
        'write': 'user_photos,publish_actions',
        }

    def __init__(self, auto_refresh=True):
        self.auto_refresh = auto_refresh
        self.session = None

    def log_out(self):
        keyring.delete_password('photini', 'facebook')
        self.session = None

    def permitted(self, level):
        access_token = keyring.get_password('photini', 'facebook')
        if not access_token:
            self.session = None
            return False
        if not self.session:
            token = {'access_token': access_token}
            self.session = OAuth2Session(token=token)
        try:
            permissions = self.get('https://graph.facebook.com/me/permissions')
        except Exception:
            permissions = None
        if not permissions:
            return False
        for required in self.scope[level].split(','):
            required = required.strip()
            if not required:
                continue
            found = False
            for permission in permissions['data']:
                if permission['permission'] != required:
                    continue
                if permission['status'] != 'granted':
                    return False
                break
            else:
                return False
        return True

    def get_auth_url(self, level):
        logger.info('using %s', keyring.get_keyring().__module__)
        app_id = key_store.get('facebook', 'app_id')
        client = oauthlib.oauth2.MobileApplicationClient(app_id)
        self.session = OAuth2Session(
            client=client, scope=self.scope[level],
            redirect_uri='https://www.facebook.com/connect/login_success.html',
            )
        return self.session.authorization_url(
            'https://www.facebook.com/dialog/oauth',
            auth_type='rerequest')[0]

    def get_access_token(self, url):
        token = self.session.token_from_fragment(url)
        self._save_token(token)
        self.session = None

    def get_user(self):
        rsp = self.get('https://graph.facebook.com/me',
                       params={'fields': 'name,picture'})
        if not rsp:
            return None, None
        if not rsp['picture']:
            return rsp['name'], None
        return rsp['name'], rsp['picture']['data']['url']

    def get_album(self, album_id, fields):
        picture = None
        album = self.get(
            'https://graph.facebook.com/v2.6/' + album_id,
            params={'fields': fields})
        if not album:
            return {}, picture
        if 'cover_photo' in album:
            picture = self.get(
                'https://graph.facebook.com/v2.6/' + album['cover_photo']['id'],
                params={'fields': 'picture'})
        if picture:
            picture = picture['picture']
        return album, picture

    def get_albums(self, fields):
        albums = self.get(
            'https://graph.facebook.com/me/albums', params={'fields': fields})
        while True:
            if not albums:
                return
            for album in albums['data']:
                yield album
            if 'paging' not in albums or 'next' not in albums['paging']:
                return
            albums = self.get(albums['paging']['next'])

    def get_places(self, latlong, distance, query):
        places = self.get(
            'https://graph.facebook.com/search',
            params={'q'       : query,
                    'type'    : 'place',
                    'center'  : str(latlong),
                    'distance': distance,
                    })
        while places:
            for place in places['data']:
                    yield place
            if 'paging' not in places or 'next' not in places['paging']:
                return
            places = self.get(places['paging']['next'])

    def get_cities(self, latlong):
        # get a list of possible place names by searching for anything nearby
        hist = defaultdict(int)
        for place in self.get_places(latlong, 1000, ''):
            for word in place['name'].split() + place['location']['city'].split():
                if word and word[0] in (',', '('):
                    word = word[1:]
                if word and word[-1] in (',', ')'):
                    word = word[:-1]
                if len(word) > 2:
                    hist[word.lower()] += 1
        if not hist:
            hist['city'] = 1
        words = list(hist.keys())
        words.sort(key=lambda x: -hist[x])
        # search for cities, regions etc. using possible place names
        threshold = hist[words[0]] // 4
        result = []
        for word in words[:5]:
            if hist[word] < threshold:
                break
            for place in self.get_places(latlong, 10000, word):
                if place in result:
                    continue
                if (place['category'] in ('City', 'Neighborhood', 'Country',
                                          'State/province/region') and
                        'latitude' in place['location'] and
                        'longitude' in place['location']):
                    result.append(place)
        return result

    def do_upload(self, fileobj, image_type, image, params):
        fields = {
            'photo'   : ('source', fileobj),
            'no_story': str(params['no_story']),
            }
        title = image.metadata.title
        description = image.metadata.description
        if title and description:
            caption = title.value + '\n\n' + description.value
        elif title:
            caption = title.value
        elif description:
            caption = description.value
        else:
            caption = ''
        if caption:
            fields['caption'] = caption
        date_taken = image.metadata.date_taken
        if date_taken:
            fields['backdated_time'] = date_taken.datetime.isoformat()
            if date_taken.precision <= 5:
                fields['backdated_time_granularity'] = (
                    'year', 'month', 'day', 'hour', 'min')[date_taken.precision - 1]
        latlong = image.metadata.latlong
        if latlong and params['geo_tag']:
            nearest = None, 1.0
            for place in self.get_cities(latlong):
                dist2 = ((latlong.lat - place['location']['latitude']) ** 2 +
                         (latlong.lon - place['location']['longitude']) ** 2)
                if dist2 < nearest[1]:
                    nearest = place, dist2
            nearest = nearest[0]
            if nearest:
                fields['place'] = nearest['id']
        data = MultipartEncoder(fields=fields)
        headers = {'Content-Type' : data.content_type}
        url = 'https://graph.facebook.com/v2.6/' + params['album_id'] + '/photos'
        try:
            self.post(url, data=data, headers=headers)
        except Exception as ex:
            return str(ex)
        return ''

    def get(self, *arg, **kw):
        rsp = self.session.get(*arg, **kw)
        rsp.raise_for_status()
        return rsp.json()

    def post(self, *arg, **kw):
        rsp = self.session.post(*arg, **kw)
        rsp.raise_for_status()

    def _save_token(self, token):
        if self.auto_refresh:
            keyring.set_password('photini', 'facebook', token['access_token'])


class FacebookLoginPopup(QtWidgets.QDialog):
    def __init__(self, *arg, **kw):
        super(FacebookLoginPopup, self).__init__(*arg, **kw)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.browser = QtWebKitWidgets.QWebView()
        self.browser.urlChanged.connect(self.auth_url_changed)
        self.layout().addWidget(self.browser)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        self.layout().addWidget(buttons)

    def load_url(self, auth_url):
        self.browser.load(QtCore.QUrl(auth_url))

    def auth_url_changed(self, url):
        if url.path() != '/connect/login_success.html':
            return
        self.browser.setHtml('<p></p>')
        self.result = url.toString()
        if 'access_token' in url.fragment():
            return self.accept()
        self.reject()


class FacebookUploadConfig(QtWidgets.QWidget):
    new_album = QtCore.pyqtSignal()
    select_album = QtCore.pyqtSignal(int)

    def __init__(self, *arg, **kw):
        super(FacebookUploadConfig, self).__init__(*arg, **kw)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.widgets = {}
        ## upload config
        config_group = QtWidgets.QGroupBox(self.tr('Options'))
        config_group.setLayout(QtWidgets.QFormLayout())
        self.layout().addWidget(config_group)
        # suppress feed story
        self.widgets['no_story'] = QtWidgets.QCheckBox()
        config_group.layout().addRow(
            self.tr('Suppress news feed story'), self.widgets['no_story'])
        label = config_group.layout().labelForField(self.widgets['no_story'])
        label.setWordWrap(True)
        label.setFixedWidth(90)
        # geotagging
        self.widgets['geo_tag'] = QtWidgets.QCheckBox()
        config_group.layout().addRow(
            self.tr('Set "city" from map coordinates'), self.widgets['geo_tag'])
        self.widgets['geo_tag'].setChecked(True)
        label = config_group.layout().labelForField(self.widgets['geo_tag'])
        label.setWordWrap(True)
        label.setFixedWidth(90)
        ## album details
        album_group = QtWidgets.QGroupBox(self.tr('Album'))
        album_group.setLayout(QtWidgets.QHBoxLayout())
        # left hand side
        album_form_left = QtWidgets.QFormLayout()
        album_form_left.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        album_group.layout().addLayout(album_form_left)
        # album title / selector
        self.widgets['album_choose'] = QtWidgets.QComboBox()
        self.widgets['album_choose'].activated.connect(self.select_album)
        album_form_left.addRow(self.tr('Title'), self.widgets['album_choose'])
        # album description
        self.widgets['album_description'] = QtWidgets.QPlainTextEdit()
        self.widgets['album_description'].setReadOnly(True)
        policy = self.widgets['album_description'].sizePolicy()
        policy.setVerticalStretch(1)
        self.widgets['album_description'].setSizePolicy(policy)
        album_form_left.addRow(self.tr('Description'), self.widgets['album_description'])
        # album location
        self.widgets['album_location'] = QtWidgets.QLineEdit()
        self.widgets['album_location'].setReadOnly(True)
        album_form_left.addRow(self.tr('Location'), self.widgets['album_location'])
        # right hand side
        album_form_right = QtWidgets.QVBoxLayout()
        album_group.layout().addLayout(album_form_right)
        # album thumbnail
        self.widgets['album_thumb'] = QtWidgets.QLabel()
        self.widgets['album_thumb'].setFixedSize(150, 150)
        self.widgets['album_thumb'].setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        album_form_right.addWidget(self.widgets['album_thumb'])
        album_form_right.addStretch(1)
        # new album
        new_album_button = QtWidgets.QPushButton(self.tr('New album'))
        new_album_button.clicked.connect(self.new_album)
        album_form_right.addWidget(new_album_button)
        self.layout().addWidget(album_group, stretch=1)

    def show_album(self, album, picture):
        if 'description' in album:
            self.widgets['album_description'].setPlainText(album['description'])
        else:
            self.widgets['album_description'].clear()
        if 'location' in album:
            self.widgets['album_location'].setText(album['location'])
        else:
            self.widgets['album_location'].clear()
        pixmap = QtGui.QPixmap()
        if picture:
            try:
                pixmap.loadFromData(urlopen(picture).read())
            except URLError as ex:
                self.logger.error('cannot read %s: %s', picture, str(ex))
        self.widgets['album_thumb'].setPixmap(pixmap)


class FacebookUploader(PhotiniUploader):
    session_factory = FacebookSession

    def __init__(self, *arg, **kw):
        self.upload_config = FacebookUploadConfig()
        self.upload_config.new_album.connect(self.new_album)
        self.upload_config.select_album.connect(self.select_album)
        super(FacebookUploader, self).__init__(self.upload_config, *arg, **kw)
        self.service_name = self.tr('Facebook')
        self.convert = {
            'types'   : ('bmp', 'gif', 'jpeg', 'png'),
            'msg'     : self.tr(
                'File "{0}" is of type "{1}", which Facebook does not' +
                ' accept. Would you like to convert it to JPEG?'),
            'buttons' : QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Ignore,
            }
        self.login_popup = None
        # add Facebook icon to connect button
        icon_file = pkg_resources.resource_filename(
            'photini', 'data/facebook_logo.png')
        self.user_connect.setIcon(QtGui.QIcon(QtGui.QPixmap(icon_file)))

    def auth_dialog(self, auth_url):
        if not self.login_popup:
            # create dialog with embedded browser
            self.login_popup = FacebookLoginPopup(self)
            self.login_popup.setWindowTitle(
                self.tr('Photini: authorise {}').format(self.service_name))
        self.login_popup.load_url(auth_url)
        if self.login_popup.exec_() != QtWidgets.QDialog.Accepted:
            return None
        return self.login_popup.result

    def load_user_data(self):
        self.upload_config.widgets['album_choose'].clear()
        self.upload_config.widgets['album_choose'].addItem(
            self.tr('<default>'), 'me')
        if self.connected:
            name, picture = self.session.get_user()
            self.show_user(name, picture)
            for album in self.session.get_albums('id,can_upload,name'):
                self.upload_config.widgets['album_choose'].addItem(
                    album['name'], album['id'])
                if not album['can_upload']:
                    idx = self.upload_config.widgets['album_choose'].count() - 1
                    self.upload_config.widgets['album_choose'].setItemData(
                        idx, 0, Qt.UserRole - 1)
            self.select_album()
        else:
            self.show_user(None, None)
            self.upload_config.show_album({}, None)

    def get_upload_params(self):
        idx = self.upload_config.widgets['album_choose'].currentIndex()
        return {
            'album_id': self.upload_config.widgets['album_choose'].itemData(idx),
            'no_story': self.upload_config.widgets['no_story'].isChecked(),
            'geo_tag' : self.upload_config.widgets['geo_tag'].isChecked(),
            }

    def upload_finished(self):
        # reload current album metadata (to update thumbnail)
        self.select_album()

    @QtCore.pyqtSlot()
    def new_album(self):
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(self.tr('Create new Facebook album'))
        dialog.setLayout(QtWidgets.QFormLayout())
        name = SingleLineEdit(spell_check=True)
        dialog.layout().addRow(self.tr('Title'), name)
        message = MultiLineEdit(spell_check=True)
        dialog.layout().addRow(self.tr('Description'), message)
        location = SingleLineEdit(spell_check=True)
        dialog.layout().addRow(self.tr('Location'), location)
        privacy = QtWidgets.QComboBox()
        for display_name, value in (
                (self.tr('Only me'),            '{value: "SELF"}'),
                (self.tr('All friends'),        '{value: "ALL_FRIENDS"}'),
                (self.tr('Friends of friends'), '{value: "FRIENDS_OF_FRIENDS"}'),
                (self.tr('Friends + networks'), '{value: "NETWORKS_FRIENDS"}'),
                (self.tr('Everyone'),           '{value: "EVERYONE"}'),
                ):
            privacy.addItem(display_name, value)
        dialog.layout().addRow(self.tr('Privacy'), privacy)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addRow(button_box)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        if not self.authorise('write'):
            self.refresh(force=True)
            return
        name = name.toPlainText().strip()
        if not name:
            return
        data = {'name': name}
        message = message.toPlainText().strip()
        if message:
            data['message'] = message
        location = location.toPlainText().strip()
        if location:
            data['location'] = location
        data['privacy'] = privacy.itemData(privacy.currentIndex())
        try:
            self.session.post('https://graph.facebook.com/me/albums', data=data)
        except Exception as ex:
            self.logger.error(str(ex))
            self.refresh(force=True)
            return
        self.load_user_data()

    @QtCore.pyqtSlot(int)
    def select_album(self, index=None):
        if not self.authorise('read'):
            self.refresh(force=True)
            return
        if index is None:
            index = self.upload_config.widgets['album_choose'].currentIndex()
        album_id = self.upload_config.widgets['album_choose'].itemData(index)
        if album_id == 'me':
            self.upload_config.show_album({}, None)
            return
        with Busy():
            album, picture = self.session.get_album(
                album_id, 'cover_photo,description,location,name')
            self.upload_config.show_album(album, picture)
