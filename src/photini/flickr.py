##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from datetime import datetime, timedelta
import html
import logging
import os
import xml.etree.ElementTree as ET

import requests
from requests_oauthlib import OAuth1Session
from requests_toolbelt import MultipartEncoder

from photini.configstore import key_store
from photini.metadata import DateTime, LatLon, Location
from photini.pyqt import (Busy, catch_all, MultiLineEdit, Qt, QtCore, QtGui,
                          QtSignal, QtSlot, QtWidgets, SingleLineEdit)
from photini.uploader import PhotiniUploader, UploaderSession

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

ID_TAG = 'flickr:photo_id'

# Flickr API: https://www.flickr.com/services/api/
# OAuth1Session: https://requests-oauthlib.readthedocs.io/en/latest/api.html
# requests: https://docs.python-requests.org/

class FlickrSession(UploaderSession):
    name = 'flickr'
    oauth_url  = 'https://www.flickr.com/services/oauth/'

    def open_connection(self):
        self.cached_data = {}
        stored_token = self.get_password()
        if not stored_token:
            return False
        token, token_secret = stored_token.split('&')
        api_key    = key_store.get('flickr', 'api_key')
        api_secret = key_store.get('flickr', 'api_secret')
        self.api = OAuth1Session(
            client_key=api_key, client_secret=api_secret,
            resource_owner_key=token, resource_owner_secret=token_secret,
            )
        self.connection_changed.emit(self.api.authorized)
        return self.api.authorized

    def get_auth_url(self, redirect_uri):
        # initialise oauth1 session
        api_key    = key_store.get('flickr', 'api_key')
        api_secret = key_store.get('flickr', 'api_secret')
        if self.api:
            self.api.close()
        self.api = OAuth1Session(
            client_key=api_key, client_secret=api_secret,
            callback_uri=redirect_uri)
        try:
            self.api.fetch_request_token(self.oauth_url + 'request_token')
            return self.api.authorization_url(
                self.oauth_url + 'authorize', perms='write')
        except Exception as ex:
            logger.error(str(ex))
            self.close_connection()
        return ''

    def get_access_token(self, result):
        oauth_verifier = str(result['oauth_verifier'][0])
        try:
            token = self.api.fetch_access_token(
                self.oauth_url + 'access_token', verifier=oauth_verifier)
        except Exception as ex:
            logger.error(str(ex))
            self.close_connection()
            return
        self.set_password(
            token['oauth_token'] + '&' + token['oauth_token_secret'])
        self.connection_changed.emit(self.api.authorized)

    def api_call(self, method, **params):
        params['method'] = method
        params['format'] = 'json'
        params['nojsoncallback'] = '1'
        try:
            rsp = self.api.get('https://www.flickr.com/services/rest',
                                timeout=5, params=params)
        except Exception as ex:
            logger.error(str(ex))
            self.close_connection()
            return {}
        if rsp.status_code != 200:
            logger.error('HTTP error %d', rsp.status_code)
            return {}
        rsp = rsp.json()
        if not ('stat' in rsp and rsp['stat'] == 'ok'):
            logger.error('API error %s: %s', rsp['stat'], rsp['message'])
            return {}
        return rsp

    def get_user(self):
        if 'user' in self.cached_data:
            return self.cached_data['user']
        name, picture = None, None
        # get nsid of logged in user
        rsp = self.api_call('flickr.auth.oauth.checkToken')
        if not rsp:
            return name, picture
        nsid = rsp['oauth']['user']['nsid']
        # get user info
        rsp = self.api_call('flickr.people.getInfo', user_id=nsid)
        if not rsp:
            return name, picture
        person = rsp['person']
        name = person['realname']['_content']
        if person['iconserver'] != '0':
            icon_url = 'http://farm{}.staticflickr.com/{}/buddyicons/{}.jpg'.format(
                person['iconfarm'], person['iconserver'], nsid)
        else:
            icon_url = 'https://www.flickr.com/images/buddyicon.gif'
        # get icon
        rsp = requests.get(icon_url)
        if rsp.status_code == 200:
            picture = rsp.content
        else:
            logger.error('HTTP error %d (%s)', rsp.status_code, icon_url)
        self.cached_data['user'] = name, picture
        return self.cached_data['user']

    def get_albums(self):
        if 'sets' in self.cached_data:
            return self.cached_data['sets']
        self.cached_data['sets'] = []
        sets = self.api_call('flickr.photosets.getList')
        if not sets:
            return self.cached_data['sets']
        for item in sets['photosets']['photoset']:
            self.cached_data['sets'].append((
                item['title']['_content'], item['description']['_content'],
                item['id']))
        return self.cached_data['sets']

    def get_info(self, photo_id):
        rsp = self.api_call('flickr.photos.getInfo', photo_id=photo_id)
        if not rsp:
            return None
        return rsp['photo']

    def find_photos(self, min_taken_date, max_taken_date):
        # search Flickr
        page = 1
        while True:
            with Busy():
                rsp = self.api_call(
                    'flickr.people.getPhotos',
                    user_id='me', page=page, extras='date_taken,url_t',
                    min_taken_date=min_taken_date.strftime('%Y-%m-%d %H:%M:%S'),
                    max_taken_date=max_taken_date.strftime('%Y-%m-%d %H:%M:%S'))
                if not ('photos' in rsp and rsp['photos']['photo']):
                    return
            for photo in rsp['photos']['photo']:
                yield photo
            page += 1


    def do_upload(self, fileobj, image_type, image, params):
        photo_id = params['photo_id']
        if params['function']:
            # upload or replace photo
            url = 'https://up.flickr.com/services/{}/'.format(params['function'])
            if params['function'] == 'upload':
                data = {}
                # set some metadata with upload function
                for key in ('permissions', 'content_type', 'hidden', 'meta'):
                    if key in params and params[key]:
                        data.update(params[key])
                        del(params[key])
            else:
                data = {'photo_id': photo_id}
            # get the headers (without 'photo') from a dummy Request, an idea
            # I've stolen from https://github.com/sybrenstuvel/flickrapi
            headers = requests.Request(
                'POST', url, data=data, auth=self.api.auth).prepare().headers
            # add photo to parameters now we've got the headers without it
            data['photo'] = ('dummy_name', fileobj)
            data = MultipartEncoder(fields=data)
            headers = {'Authorization': headers['Authorization'],
                       'Content-Type': data.content_type}
            # use requests to post data
            rsp = requests.post(url, data=data, headers=headers)
            if rsp.status_code != 200:
                logger.error('HTTP error %d', rsp.status_code)
                return {}
            # parse XML response
            rsp = ET.fromstring(rsp.text)
            status = rsp.attrib['stat']
            if status != 'ok':
                return params['function'] + ' ' + status
            photo_id = rsp.find('photoid').text
        fileobj._callback(100)
        # store photo id in image keywords
        keyword = '{}={}'.format(ID_TAG, photo_id)
        if not image.metadata.keywords:
            image.metadata.keywords = [keyword]
        elif keyword not in image.metadata.keywords:
            image.metadata.keywords = list(image.metadata.keywords) + [keyword]
        # set metadata after uploading image
        metadata_set_func = {
            'permissions':  'flickr.photos.setPerms',
            'content_type': 'flickr.photos.setContentType',
            'hidden':       'flickr.photos.setSafetyLevel',
            'meta':         'flickr.photos.setMeta',
            'tags':         'flickr.photos.setTags',
            'dates':        'flickr.photos.setDates',
            'location':     'flickr.photos.geo.setLocation',
            }
        for key in params:
            if params[key] and key in metadata_set_func:
                self.api_call(metadata_set_func[key],
                              photo_id=photo_id, **params[key])
        # existing photo may have a location that needs deleting
        if params['function'] != 'upload' and (
                'location' in params and not params['location']):
            rsp = self.api_call('flickr.photos.getInfo', photo_id=photo_id)
            if 'photo' in rsp and 'location' in rsp['photo']:
                self.api_call(
                    'flickr.photos.geo.removeLocation', photo_id=photo_id)
        # add to or remove from sets
        if 'sets' not in params:
            return ''
        current_sets = {}
        if params['function'] != 'upload':
            # get sets existing photo is in
            rsp = self.api_call(
                'flickr.photos.getAllContexts', photo_id=photo_id)
            if 'set' in rsp:
                for p_set in rsp['set']:
                    current_sets[p_set['id']] = p_set
        for widget in params['sets']:
            photoset_id = widget.property('photoset_id')
            if not photoset_id:
                # create new set
                rsp = self.api_call(
                    'flickr.photosets.create', primary_photo_id=photo_id,
                    title=widget.text().replace('&&', '&'),
                    description=widget.toolTip())
                if rsp:
                    widget.setProperty('photoset_id', rsp['photoset']['id'])
            elif photoset_id in current_sets:
                # photo is already in the set
                del current_sets[photoset_id]
            else:
                # add to existing set
                self.api_call('flickr.photosets.addPhoto',
                              photo_id=photo_id, photoset_id=photoset_id)
        # remove from any other sets
        for p_set in current_sets.values():
            self.api_call('flickr.photosets.removePhoto',
                          photo_id=photo_id, photoset_id=p_set['id'])
        return ''


class FlickrUploadConfig(QtWidgets.QWidget):
    new_set = QtSignal()
    sync_metadata = QtSignal()

    def __init__(self, *arg, **kw):
        super(FlickrUploadConfig, self).__init__(*arg, **kw)
        self.setLayout(QtWidgets.QGridLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        # privacy settings
        self.privacy = {}
        privacy_group = QtWidgets.QGroupBox(
            translate('FlickrTab', 'Who can see the photos?'))
        privacy_group.setLayout(QtWidgets.QVBoxLayout())
        self.privacy['private'] = QtWidgets.QRadioButton(
            translate('FlickrTab', 'Only you'))
        privacy_group.layout().addWidget(self.privacy['private'])
        ff_group = QtWidgets.QGroupBox()
        ff_group.setFlat(True)
        ff_group.setLayout(QtWidgets.QVBoxLayout())
        ff_group.layout().setContentsMargins(10, 0, 0, 0)
        self.privacy['friends'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Your friends'))
        ff_group.layout().addWidget(self.privacy['friends'])
        self.privacy['family'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Your family'))
        ff_group.layout().addWidget(self.privacy['family'])
        privacy_group.layout().addWidget(ff_group)
        self.privacy['public'] = QtWidgets.QRadioButton(
            translate('FlickrTab', 'Anyone'))
        self.privacy['public'].toggled.connect(self.enable_ff)
        self.privacy['public'].setChecked(True)
        privacy_group.layout().addWidget(self.privacy['public'])
        self.hidden = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Hidden from search'))
        privacy_group.layout().addWidget(self.hidden)
        privacy_group.layout().addStretch(1)
        self.layout().addWidget(privacy_group, 0, 0, 3, 1)
        # content type
        self.content_type = {}
        content_group = QtWidgets.QGroupBox(
            translate('FlickrTab', 'Content type'))
        content_group.setLayout(QtWidgets.QVBoxLayout())
        self.content_type['photo'] = QtWidgets.QRadioButton(
            translate('FlickrTab', 'Photo'))
        self.content_type['photo'].setChecked(True)
        content_group.layout().addWidget(self.content_type['photo'])
        self.content_type['screenshot'] = QtWidgets.QRadioButton(
            translate('FlickrTab', 'Screenshot'))
        content_group.layout().addWidget(self.content_type['screenshot'])
        self.content_type['other'] = QtWidgets.QRadioButton(
            translate('FlickrTab', 'Art/Illustration'))
        content_group.layout().addWidget(self.content_type['other'])
        content_group.layout().addStretch(1)
        self.layout().addWidget(content_group, 0, 1)
        # synchronise metadata
        self.sync_button = QtWidgets.QPushButton(
            translate('FlickrTab', 'Synchronise'))
        self.sync_button.clicked.connect(self.sync_metadata)
        self.layout().addWidget(self.sync_button, 1, 1)
        # create new set
        new_set_button = QtWidgets.QPushButton(
            translate('FlickrTab', 'New album'))
        new_set_button.clicked.connect(self.new_set)
        self.layout().addWidget(new_set_button, 2, 1)
        # list of sets widget
        sets_group = QtWidgets.QGroupBox(
            translate('FlickrTab', 'Add to albums'))
        sets_group.setLayout(QtWidgets.QVBoxLayout())
        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setFrameStyle(QtWidgets.QFrame.NoFrame)
        scrollarea.setStyleSheet("QScrollArea { background-color: transparent }")
        self.sets_widget = QtWidgets.QWidget()
        self.sets_widget.setLayout(QtWidgets.QVBoxLayout())
        self.sets_widget.layout().setSpacing(0)
        self.sets_widget.layout().setSizeConstraint(
            QtWidgets.QLayout.SetMinAndMaxSize)
        scrollarea.setWidget(self.sets_widget)
        self.sets_widget.setAutoFillBackground(False)
        sets_group.layout().addWidget(scrollarea)
        self.layout().addWidget(sets_group, 0, 2, 3, 1)
        self.layout().setColumnStretch(2, 1)

    @QtSlot(bool)
    @catch_all
    def enable_ff(self, value):
        self.privacy['friends'].setEnabled(self.privacy['private'].isChecked())
        self.privacy['family'].setEnabled(self.privacy['private'].isChecked())

    def get_fixed_params(self):
        is_public = str(int(self.privacy['public'].isChecked()))
        is_family = str(int(self.privacy['private'].isChecked() and
                            self.privacy['family'].isChecked()))
        is_friend = str(int(self.privacy['private'].isChecked() and
                            self.privacy['friends'].isChecked()))
        if self.content_type['photo'].isChecked():
            content_type = '1'
        elif self.content_type['screenshot'].isChecked():
            content_type = '2'
        else:
            content_type = '3'
        hidden = str(int(self.hidden.isChecked()))
        return {
            'permissions': {
                'is_public': is_public,
                'is_friend': is_friend,
                'is_family': is_family,
                },
            'content_type': {'content_type': content_type},
            'hidden'      : {'hidden'      : hidden},
            }

    def clear_sets(self):
        for child in self.sets_widget.children():
            if child.isWidgetType():
                self.sets_widget.layout().removeWidget(child)
                child.setParent(None)

    def checked_sets(self):
        result = []
        for child in self.sets_widget.children():
            if child.isWidgetType() and child.isChecked():
                result.append(child)
        return result

    def add_set(self, title, description, photoset_id, index=-1):
        widget = QtWidgets.QCheckBox(title.replace('&', '&&'))
        if description:
            widget.setToolTip(html.unescape(description))
        widget.setProperty('photoset_id', photoset_id)
        if index >= 0:
            self.sets_widget.layout().insertWidget(index, widget)
        else:
            self.sets_widget.layout().addWidget(widget)
        return widget


class TabWidget(PhotiniUploader):
    session_factory = FlickrSession

    @staticmethod
    def tab_name():
        return translate('FlickrTab', '&Flickr upload')

    def __init__(self, *arg, **kw):
        self.service_name = translate('FlickrTab', 'Flickr')
        self.upload_config = FlickrUploadConfig()
        super(TabWidget, self).__init__(self.upload_config, *arg, **kw)
        self.upload_config.new_set.connect(self.new_set)
        self.upload_config.sync_metadata.connect(self.sync_metadata)
        self.image_types = {
            'accepted': ('image/gif', 'image/jpeg', 'image/png',
                         'video/mp4', 'video/quicktime', 'video/riff'),
            'rejected': ('image/x-canon-cr2',),
            }
        self.replace_prefs = {
            'set_metadata'  : True,
            'set_visibility': False,
            'set_type'      : False,
            'set_albums'    : False,
            'replace_image' : False,
            'new_photo'     : False,
            }

    def get_conversion_function(self, image, params):
        if not params['function']:
            return None
        convert = super(
            TabWidget, self).get_conversion_function(image, params)
        if convert == 'omit':
            return convert
        max_size = 2 ** 30
        size = os.stat(image.path).st_size
        if size < max_size:
            return convert
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(
            translate('FlickrTab', 'Photini: too large'))
        dialog.setText(
            translate('FlickrTab', '<h3>File too large.</h3>'))
        dialog.setInformativeText(
            translate('FlickrTab',
                      'File "{0}" has {1} bytes and exceeds Flickr\'s limit' +
                      ' of {2} bytes.').format(
                          os.path.basename(image.path), size, max_size))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(QtWidgets.QMessageBox.Ignore)
        dialog.exec_()
        return 'omit'

    def show_album_list(self, albums):
        self.upload_config.clear_sets()
        for item in albums:
            self.upload_config.add_set(*item)

    def get_upload_params(self, image):
        option, photo_id = self._replace_dialog(image)
        if not option or not any(option.values()):
            # user chose to do nothing
            return None
        # set upload function
        if option['new_photo']:
            params = {'function': 'upload'}
            photo_id = None
        elif option['replace_image']:
            params = {'function': 'replace'}
        else:
            params = {'function': None}
        params['photo_id'] = photo_id
        # set config params that apply to all photos
        fixed_params = self.upload_config.get_fixed_params()
        if option['new_photo'] or option['set_visibility']:
            params['permissions'] = fixed_params['permissions']
            params['hidden'] = fixed_params['hidden']
        if option['new_photo'] or option['set_type']:
            params['content_type'] = fixed_params['content_type']
        # add metadata
        if option['new_photo'] or option['set_metadata']:
            # title & description
            params['meta'] = {
                'title'      : image.metadata.title or image.name,
                'description': image.metadata.description or '',
                }
            # keywords
            params['tags'] = {'tags': 'uploaded:by=photini,'}
            for keyword in image.metadata.keywords or []:
                if not keyword.startswith(ID_TAG):
                    keyword = keyword.replace('"', "'")
                    if ',' in keyword:
                        keyword = '"' + keyword + '"'
                    params['tags']['tags'] += keyword + ','
            # date_taken
            date_taken = image.metadata.date_taken
            if date_taken:
                params['dates'] = {
                    'date_taken':
                    date_taken['datetime'].strftime('%Y-%m-%d %H:%M:%S')
                    }
                if date_taken['precision'] <= 1:
                    params['dates']['date_taken_granularity'] = '6'
                elif date_taken['precision'] <= 2:
                    params['dates']['date_taken_granularity'] = '4'
            # location
            if image.metadata.latlong:
                params['location'] = {
                    'lat': '{:.6f}'.format(image.metadata.latlong['lat']),
                    'lon': '{:.6f}'.format(image.metadata.latlong['lon']),
                    }
            else:
                # clear any existing location
                params['location'] = None
        # make list of sets to add photos to
        if option['new_photo'] or option['set_albums']:
            params['sets'] = self.upload_config.checked_sets()
        return params

    def _replace_dialog(self, image):
        # has image already been uploaded?
        for keyword in image.metadata.keywords or []:
            name_pred, sep, photo_id = keyword.partition('=')
            if name_pred == ID_TAG:
                break
        else:
            # new upload
            return {
                'set_metadata'  : True,
                'set_visibility': True,
                'set_type'      : True,
                'set_albums'    : True,
                'replace_image' : False,
                'new_photo'     : True,
                }, None
        # get user preferences
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate('FlickrTab', 'Replace photo'))
        dialog.setLayout(QtWidgets.QVBoxLayout())
        message = QtWidgets.QLabel(translate(
            'FlickrTab', 'File {0} has already been uploaded to Flickr.'
            ' How would you like to update it?').format(
                os.path.basename(image.path)))
        message.setWordWrap(True)
        dialog.layout().addWidget(message)
        widget = {}
        widget['set_metadata'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Replace metadata'))
        widget['set_visibility'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Change who can see it'))
        widget['set_type'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Change content type'))
        widget['set_albums'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Change album membership'))
        widget['replace_image'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Replace image'))
        widget['new_photo'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Upload as new photo'))
        widget['new_photo'].toggled.connect(widget['set_metadata'].setDisabled)
        widget['new_photo'].toggled.connect(widget['set_visibility'].setDisabled)
        widget['new_photo'].toggled.connect(widget['set_type'].setDisabled)
        widget['new_photo'].toggled.connect(widget['set_albums'].setDisabled)
        no_upload = QtWidgets.QCheckBox(
            translate('FlickrTab', 'No image upload'))
        no_upload.setChecked(True)
        button_group = QtWidgets.QButtonGroup()
        button_group.addButton(widget['replace_image'])
        button_group.addButton(widget['new_photo'])
        button_group.addButton(no_upload)
        for key in ('set_metadata', 'set_visibility', 'set_type',
                    'set_albums', 'replace_image', 'new_photo'):
            dialog.layout().addWidget(widget[key])
            widget[key].setChecked(self.replace_prefs[key])
        dialog.layout().addWidget(no_upload)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addWidget(button_box)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return None, photo_id
        for key in self.replace_prefs:
            self.replace_prefs[key] = widget[key].isChecked()
        return dict(self.replace_prefs), photo_id

    def _find_on_flickr(self, image):
        # get possible date range
        if not image.metadata.date_taken:
            return
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
        # search Flickr
        for photo in self.session.find_photos(min_taken_date, max_taken_date):
            yield photo

    def _find_local(self, photo, unknowns):
        granularity = int(photo['datetakengranularity'])
        min_taken_date = datetime.strptime(
            photo['datetaken'], '%Y-%m-%d %H:%M:%S')
        if granularity <= 0:
            max_taken_date = min_taken_date + timedelta(seconds=1)
        elif granularity <= 4:
            max_taken_date = min_taken_date + timedelta(days=31)
        else:
            max_taken_date = min_taken_date + timedelta(days=366)
        candidates = []
        for candidate in unknowns:
            if not candidate.metadata.date_taken:
                continue
            date_taken = candidate.metadata.date_taken['datetime']
            if date_taken < min_taken_date or date_taken > max_taken_date:
                continue
            candidates.append(candidate)
        if not candidates:
            return None
        rsp = requests.get(photo['url_t'])
        if rsp.status_code == 200:
            flickr_icon = rsp.content
        else:
            logger.error('HTTP error %d (%s)', rsp.status_code, photo['url_t'])
            return None
        # get user to choose matching image file
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate('FlickrTab', 'Select an image'))
        dialog.setLayout(QtWidgets.QFormLayout())
        dialog.layout().setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(flickr_icon)
        label = QtWidgets.QLabel()
        label.setPixmap(pixmap)
        dialog.layout().addRow(label, QtWidgets.QLabel(translate(
            'FlickrTab', 'Which image file matches\nthis picture on Flickr?')))
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
        button = QtWidgets.QPushButton(translate('FlickrTab', 'No match'))
        button.setDefault(True)
        button.clicked.connect(dialog.reject)
        dialog.layout().addRow('', button)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            for button, candidate in buttons.items():
                if button.isChecked():
                    return candidate
        return None

    _address_map = {
        'CountryName':   ('country',),
        'ProvinceState': ('county', 'region'),
        'City':          ('neighbourhood', 'locality'),
        }

    def _merge_metadata(self, photo_id, image):
        photo = self.session.get_info(photo_id)
        if not photo:
            return
        md = image.metadata
        # sync title
        title = html.unescape(photo['title']['_content'])
        if md.title:
            md.title = md.title.merge(
                image.name + '(title)', 'flickr title', title)
        else:
            md.title = title
        # sync description
        description = html.unescape(photo['description']['_content'])
        if md.description:
            md.description = md.description.merge(
                image.name + '(description)', 'flickr description', description)
        else:
            md.description = description
        # sync keywords
        tags = []
        for tag in photo['tags']['tag']:
            if tag['raw'] == 'uploaded:by=photini':
                continue
            if md.location_taken and tag['raw'] in (
                    md.location_taken['CountryCode'],
                    md.location_taken['CountryName'],
                    md.location_taken['ProvinceState'],
                    md.location_taken['City']):
                continue
            tags.append(tag['raw'])
        md.keywords = md.keywords.merge(
            image.name + '(keywords)', 'flickr tags', tags)
        # sync location
        if 'location' in photo:
            location = photo['location']
            latlong = LatLon((location['latitude'], location['longitude']))
            if md.latlong:
                md.latlong = md.latlong.merge(
                    image.name + '(latlong)', 'flickr location', latlong)
            else:
                md.latlong = latlong
            address = {}
            for key in location:
                if '_content' in location[key]:
                    address[key] = location[key]['_content']
            location_taken = Location.from_address(address, self._address_map)
            if md.location_taken:
                md.location_taken = md.location_taken.merge(
                    image.name + '(location_taken)', 'flickr location',
                    location_taken)
            else:
                md.location_taken = location_taken
        # sync date_taken
        if photo['dates']['takenunknown'] == '0':
            granularity = int(photo['dates']['takengranularity'])
            if granularity >= 6:
                precision = 1
            elif granularity >= 4:
                precision = 2
            else:
                precision = 6
            date_taken = DateTime((
                datetime.strptime(
                    photo['dates']['taken'], '%Y-%m-%d %H:%M:%S'),
                precision, None))
            if md.date_taken:
                md.date_taken = md.date_taken.merge(
                    image.name + '(date_taken)', 'flickr date taken', date_taken)
            else:
                md.date_taken = date_taken

    @QtSlot()
    @catch_all
    def sync_metadata(self):
        # make list of known photo ids
        photo_ids = {}
        unknowns = []
        for image in self.image_list.get_selected_images():
            for keyword in image.metadata.keywords or []:
                name_pred, sep, value = keyword.partition('=')
                if name_pred == ID_TAG:
                    photo_ids[value] = image
                    break
            else:
                unknowns.append(image)
        # try to find unknowns on Flickr
        for image in unknowns:
            for photo in self._find_on_flickr(image):
                if photo['id'] in photo_ids:
                    continue
                match = self._find_local(photo, unknowns)
                if match:
                    match.metadata.keywords = list(
                        match.metadata.keywords or []) + [
                            '{}={}'.format(ID_TAG, photo['id'])]
                    photo_ids[photo['id']] = match
                    unknowns.remove(match)
        # merge Flickr metadata into file
        with Busy():
            for photo_id, image in photo_ids.items():
                self._merge_metadata(photo_id, image)

    @QtSlot()
    @catch_all
    def new_set(self):
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate('FlickrTab', 'Create new Flickr album'))
        dialog.setLayout(QtWidgets.QFormLayout())
        title = SingleLineEdit(spell_check=True)
        dialog.layout().addRow(translate('FlickrTab', 'Title'), title)
        description = MultiLineEdit(spell_check=True)
        dialog.layout().addRow(translate(
            'FlickrTab', 'Description'), description)
        dialog.layout().addRow(QtWidgets.QLabel(translate(
            'FlickrTab', 'Album will be created when photos are uploaded')))
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addRow(button_box)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        title = title.toPlainText()
        if not title:
            return
        description = description.toPlainText()
        widget = self.upload_config.add_set(title, description, None, index=0)
        widget.setChecked(True)

    @QtSlot(list)
    @catch_all
    def new_selection(self, selection):
        super(TabWidget, self).new_selection(selection)
        self.upload_config.sync_button.setEnabled(
            len(selection) > 0 and self.user_connect.is_checked())
