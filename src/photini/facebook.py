##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2016-17  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import math
import os
from six.moves.urllib.parse import unquote

import oauthlib
try:
    import PIL.Image as PIL
except ImportError:
    PIL = None
import pkg_resources
import requests
from requests_oauthlib import OAuth2Session
from requests_toolbelt import MultipartEncoder

from photini.configstore import key_store
from photini.pyqt import (
    Busy, MultiLineEdit, Qt, QtCore, QtGui, QtWebEngineWidgets,
    QtWebKitWidgets, QtWidgets, SingleLineEdit)
from photini.uploader import PhotiniUploader, UploaderSession

logger = logging.getLogger(__name__)
cities_cache = []

class FacebookSession(UploaderSession):
    name = 'facebook'
    scope = {
        'read' : ('user_photos',),
        'write': ('user_photos', 'publish_actions'),
        }

    def permitted(self, level):
        access_token = self.get_password()
        if not access_token:
            self.api = None
            return False
        if not self.api:
            self.api = OAuth2Session(token={'access_token': access_token})
        try:
            permissions = self.get('https://graph.facebook.com/me/permissions')
        except Exception:
            permissions = None
        if not permissions:
            return False
        for required in self.scope[level]:
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
        app_id = key_store.get('facebook', 'app_id')
        client = oauthlib.oauth2.MobileApplicationClient(app_id)
        self.api = OAuth2Session(
            client=client, scope=','.join(self.scope[level]),
            redirect_uri='https://www.facebook.com/connect/login_success.html',
            )
        result = self.api.authorization_url(
            'https://www.facebook.com/dialog/oauth',
            display='popup', auth_type='rerequest')[0]
        # use unquote to prevent "redirect_uri URL is not properly
        # formatted" error on Windows
        return unquote(result)

    def get_access_token(self, url, level):
        token = self.api.token_from_fragment(url)
        self.set_password(token['access_token'])
        self.api = None
        return self.permitted(level)

    def get_user(self):
        rsp = self.get('https://graph.facebook.com/me',
                       params={'fields': 'name,picture'})
        if not rsp:
            return None, None
        if rsp['picture']:
            url = rsp['picture']['data']['url']
            try:
                pic_rsp = self.api.get(url)
                pic_rsp.raise_for_status()
                return rsp['name'], pic_rsp.content
            except Exception as ex:
                logger.error('cannot read %s: %s', url, str(ex))
        return rsp['name'], None

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
                    'fields'  : 'category,id,location,name',
                    })
        while places:
            for place in places['data']:
                yield place
            if 'paging' not in places or 'next' not in places['paging']:
                return
            places = self.get(places['paging']['next'])

    def distance(self, a, b):
        # calculate approximate separation in metres of two nearby
        # lat/long values
        dx = (a.lon - b['longitude']) * 111320.0
        dy = (a.lat - b['latitude']) * 111320.0 * math.cos(math.radians(a.lat))
        return math.sqrt((dx * dx) + (dy * dy))

    def is_city(self, place):
        return (place['category'] in ('City', 'Neighborhood', 'Country',
                                      'State/province/region') and
                'latitude' in place['location'] and
                'longitude' in place['location'])

    def get_cities(self, latlong, city=None):
        # check cache for similar latlong
        nearest = None, 1.0e12
        for cache in cities_cache:
            dist = self.distance(latlong, cache['location'])
            if dist < nearest[1]:
                nearest = cache['cities_list'], dist
        if nearest[1] < 500:
            return nearest[0]
        elif nearest[1] < 1000:
            # initialise result to include nearby places
            result = list(nearest[0])
        else:
            result = []
        if city:
            # look for actual city
            for word in city.split(','):
                for place in self.get_places(latlong, 10000, word):
                    if place not in result and self.is_city(place):
                        result.append(place)
        else:
            # get a list of possible place names by searching for anything nearby
            hist = defaultdict(int)
            for place in self.get_places(latlong, 1000, ''):
                words = []
                if 'name' in place:
                    words += place['name'].split()
                if 'location' in place and 'city' in place['location']:
                    words += place['location']['city'].split()
                for word in words:
                    if word and word[0] in (',', '('):
                        word = word[1:]
                    if word and word[-1] in (',', ')'):
                        word = word[:-1]
                    if len(word) > 2:
                        hist[word.lower()] += 1
                if place not in result and self.is_city(place):
                    result.append(place)
            if not hist:
                hist['city'] = 1
            words = list(hist.keys())
            words.sort(key=lambda x: -hist[x])
            # search for cities, regions etc. using possible place names
            threshold = hist[words[len(words) // 2]]
            for word in words[:5]:
                if hist[word] <= threshold:
                    break
                for place in self.get_places(latlong, 10000, word):
                    if place not in result and self.is_city(place):
                        result.append(place)
        cities_cache.append({
            'location'   : {'latitude': latlong.lat, 'longitude': latlong.lon},
            'cities_list': result,
            })
        return result

    def do_upload(self, fileobj, image_type, image, params):
        fields = {
            'photo'   : ('source', fileobj),
            'no_story': str(params['no_story']),
            }
        title = image.metadata.title
        description = image.metadata.description
        if title and description:
            caption = title + '\n\n' + description
        elif title:
            caption = title
        elif description:
            caption = description
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
            city = None
            if image.metadata.location_taken:
                city = image.metadata.location_taken.city
            if image.metadata.location_shown:
                city = city or image.metadata.location_shown.city
            nearest = None, 1.0e12
            for place in self.get_cities(latlong, city=city):
                dist = self.distance(latlong, place['location'])
                if dist < nearest[1]:
                    nearest = place, dist
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
        rsp = self.api.get(*arg, **kw)
        rsp.raise_for_status()
        return rsp.json()

    def post(self, *arg, **kw):
        rsp = self.api.post(*arg, **kw)
        rsp.raise_for_status()
        return rsp.json()


if QtWebEngineWidgets:
    WebViewBase = QtWebEngineWidgets.QWebEngineView
else:
    WebViewBase = QtWebKitWidgets.QWebView

class WebView(WebViewBase):
    def sizeHint(self):
        return QtCore.QSize(580, 490)


class FacebookLoginPopup(QtWidgets.QDialog):
    def __init__(self, *arg, **kw):
        super(FacebookLoginPopup, self).__init__(*arg, **kw)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.browser = WebView()
        self.browser.urlChanged.connect(self.auth_url_changed)
        self.layout().addWidget(self.browser)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        self.layout().addWidget(buttons)

    def load_url(self, auth_url):
        self.browser.load(QtCore.QUrl(auth_url))

    @QtCore.pyqtSlot(QtCore.QUrl)
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
            self.tr('Set "city" from location metadata'), self.widgets['geo_tag'])
        self.widgets['geo_tag'].setChecked(True)
        label = config_group.layout().labelForField(self.widgets['geo_tag'])
        label.setWordWrap(True)
        label.setFixedWidth(90)
        # optimise
        self.widgets['optimise'] = QtWidgets.QCheckBox()
        config_group.layout().addRow(
            self.tr('Optimise image size'), self.widgets['optimise'])
        label = config_group.layout().labelForField(self.widgets['optimise'])
        label.setWordWrap(True)
        label.setFixedWidth(90)
        if PIL:
            self.widgets['optimise'].setChecked(True)
        else:
            self.widgets['optimise'].setEnabled(False)
            label.setEnabled(False)
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
            rsp = requests.get(picture)
            if rsp.status_code == 200:
                pixmap.loadFromData(rsp.content)
            else:
                logger.error('HTTP error %d (%s)', rsp.status_code, picture)
        self.widgets['album_thumb'].setPixmap(pixmap)


class FacebookUploader(PhotiniUploader):
    session_factory = FacebookSession

    def __init__(self, *arg, **kw):
        self.upload_config = FacebookUploadConfig()
        super(FacebookUploader, self).__init__(self.upload_config, *arg, **kw)
        self.upload_config.new_album.connect(self.new_album)
        self.upload_config.select_album.connect(self.select_album)
        self.service_name = self.tr('Facebook')
        self.image_types = {
            'accepted': ('image/jpeg', 'image/png'),
            'rejected': ('image/x-portable-anymap', 'image/x-canon-cr2'),
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

    def get_album_list(self, album_id=None):
        self.upload_config.widgets['album_choose'].clear()
        self.upload_config.widgets['album_choose'].addItem(
            self.tr('<default>'), 'me')
        if self.connected:
            selected = 0
            for album in self.session.get_albums('id,can_upload,name'):
                self.upload_config.widgets['album_choose'].addItem(
                    album['name'], album['id'])
                idx = self.upload_config.widgets['album_choose'].count() - 1
                if not album['can_upload']:
                    self.upload_config.widgets['album_choose'].setItemData(
                        idx, 0, Qt.UserRole - 1)
                elif album['id'] == album_id or not selected:
                    selected = idx
            self.upload_config.widgets['album_choose'].setCurrentIndex(selected)
            self.select_album(selected)
        else:
            self.upload_config.show_album({}, None)

    def optimise(self, image):
        try:
            im = PIL.open(image.path)
        except OSError:
            # PIL didn't recognise the file, so go via Qt
            path = self.convert_to_jpeg(image)
            im = PIL.open(path)
            im.load()
            os.unlink(path)
        # scale to one of Facebook's preferred sizes
        w, h = im.size
        old_size = max(w, h)
        new_size = None
        if old_size in (2048, 960, 720):
            pass
        elif old_size > 960:
            new_size = 2048
        elif old_size > 720:
            new_size = 960
        elif old_size > 360:
            new_size = 720
        if new_size:
            if w >= h:
                h = int((float(new_size * h) / float(w)) + 0.5)
                w = new_size
            else:
                w = int((float(new_size * w) / float(h)) + 0.5)
                h = new_size
            im = im.resize((w, h), PIL.ANTIALIAS)
        # save as temporary jpeg file
        path = self.get_temp_filename(image)
        im.save(path, format='jpeg', quality=95)
        # copy metadata although Facebook wipes most of it at present
        self.copy_metadata(image, path)
        return path

    def get_conversion_function(self, image):
        if (PIL and self.upload_config.widgets['optimise'].isChecked() and
                    self.is_convertible(image)):
            return self.optimise
        return super(FacebookUploader, self).get_conversion_function(image)

    def get_upload_params(self):
        idx = self.upload_config.widgets['album_choose'].currentIndex()
        return {
            'album_id': self.upload_config.widgets['album_choose'].itemData(idx),
            'no_story': self.upload_config.widgets['no_story'].isChecked(),
            'geo_tag' : self.upload_config.widgets['geo_tag'].isChecked(),
            }

    def upload_finished(self):
        # reload current album metadata (to update thumbnail)
        self.select_album(
            self.upload_config.widgets['album_choose'].currentIndex())

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
            album = self.session.post(
                'https://graph.facebook.com/me/albums', data=data)
        except Exception as ex:
            logger.error(str(ex))
            self.refresh(force=True)
            return
        self.get_album_list(album_id=album['id'])

    @QtCore.pyqtSlot(int)
    def select_album(self, index):
        if not self.authorise('read'):
            self.refresh(force=True)
            return
        album_id = self.upload_config.widgets['album_choose'].itemData(index)
        if album_id == 'me':
            self.upload_config.show_album({}, None)
            return
        with Busy():
            album, picture = self.session.get_album(
                album_id, 'cover_photo,description,location,name')
            self.upload_config.show_album(album, picture)
