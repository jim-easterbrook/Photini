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

from datetime import datetime
import html
import logging
import os
import time
import xml.etree.ElementTree as ET

import requests
import requests_oauthlib
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from photini.pyqt import (
    catch_all, execute, FormLayout, QtCore, QtSlot, QtWidgets, width_for_text)
from photini.uploader import PhotiniUploader, UploaderSession, UploaderUser
from photini.types import MD_Location
from photini.widgets import DropDownSelector, MultiLineEdit, SingleLineEdit

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

# Flickr API: https://www.flickr.com/services/api/
# OAuth1Session: https://requests-oauthlib.readthedocs.io/en/latest/api.html
# requests: https://docs.python-requests.org/

class FlickrSession(UploaderSession):
    name = 'flickr'
    oauth_url  = 'https://www.flickr.com/services/oauth/'

    def open_connection(self):
        if not self.api:
            self.auth = requests_oauthlib.OAuth1(
                resource_owner_key=self.user_data['oauth_token'],
                resource_owner_secret=self.user_data['oauth_token_secret'],
                **self.client_data)
            super(FlickrSession, self).open_connection()

    def api_call(self, method, post=False, **params):
        self.open_connection()
        params['method'] = method
        params['format'] = 'json'
        params['nojsoncallback'] = '1'
        kwds = {'timeout': 20, 'auth': self.auth}
        url = 'https://www.flickr.com/services/rest'
        if post:
            rsp = self.api.post(url, data=params, **kwds)
        else:
            rsp = self.api.get(url, params=params, **kwds)
        rsp = self.check_response(rsp)
        if not rsp:
            print('close_connection', method)
            self.close_connection()
        elif rsp['stat'] != 'ok':
            logger.error('%s: %s', method, rsp['message'])
            return {}
        return rsp

    def find_photos(self, min_taken_date, max_taken_date):
        # search Flickr
        user_id = self.user_data['user_nsid']
        page = 1
        while True:
            rsp = self.api_call(
                'flickr.people.getPhotos', user_id=user_id,
                page=page, extras='date_taken,url_t',
                min_taken_date=min_taken_date.strftime('%Y-%m-%d %H:%M:%S'),
                max_taken_date=max_taken_date.strftime('%Y-%m-%d %H:%M:%S'))
            if not ('photos' in rsp and rsp['photos']['photo']):
                return
            for photo in rsp['photos']['photo']:
                date_taken = datetime.strptime(
                    photo['datetaken'], '%Y-%m-%d %H:%M:%S')
                yield photo['id'], date_taken, photo['url_t']
            page += 1

    def upload_image(self, url, data, fileobj, image_type):
        # get the headers (without 'photo') from a dummy Request, an idea
        # I've stolen from https://github.com/sybrenstuvel/flickrapi
        request = requests.Request('POST', url, auth=self.auth, data=data)
        headers = self.api.prepare_request(request).headers
        # add photo to parameters now we've got the headers without it
        data = dict(data)
        data['photo'] = 'dummy_name', fileobj, image_type
        data = MultipartEncoderMonitor(
            MultipartEncoder(fields=data), self.progress)
        headers = {'Authorization': headers['Authorization'],
                   'Content-Type': data.content_type}
        # post data, without additional auth
        self.upload_progress.emit({'busy': False})
        rsp = self.check_response(
            self.api.post(url, data=data, headers=headers, timeout=20),
            decode=False)
        self.upload_progress.emit({'busy': True})
        if not rsp:
            return 'Flickr upload failed', None
        # parse XML response
        rsp = ET.fromstring(rsp.text)
        status = rsp.attrib['stat']
        if status != 'ok':
            return 'Flickr upload: ' + status, None
        ticket_id = rsp.find('ticketid').text
        # wait for processing to finish
        while True:
            rsp = self.api_call('flickr.photos.upload.checkTickets',
                                tickets=ticket_id)
            if not rsp:
                return 'Wait for processing failed', None
            complete = rsp['uploader']['ticket'][0]['complete']
            if complete == 1:
                return '', rsp['uploader']['ticket'][0]['photoid']
            elif complete != 0:
                return 'Flickr file conversion failed', None
            time.sleep(1)

    metadata_set_func = {
        'privacy':      'flickr.photos.setPerms',
        'permissions':  'flickr.photos.setPerms',
        'content_type': 'flickr.photos.setContentType',
        'safety_level': 'flickr.photos.setSafetyLevel',
        'hidden':       'flickr.photos.setSafetyLevel',
        'licence':      'flickr.photos.licenses.setLicense',
        'meta':         'flickr.photos.setMeta',
        'keywords':     'flickr.photos.setTags',
        'dates':        'flickr.photos.setDates',
        'location':     'flickr.photos.geo.setLocation',
        }

    def set_metadata(self, params, photo_id):
        for key in list(params):
            if params[key] and key in self.metadata_set_func:
                rsp = self.api_call(self.metadata_set_func[key], post=True,
                                    photo_id=photo_id, **params[key])
                if not rsp:
                    return 'Failed to set ' + key
                del params[key]
        # existing photo may have a location that needs deleting
        if params['function'] != 'upload' and (
                'location' in params and not params['location']):
            rsp = self.api_call('flickr.photos.getInfo', photo_id=photo_id)
            if 'photo' in rsp and 'location' in rsp['photo']:
                rsp = self.api_call('flickr.photos.geo.removeLocation',
                                    post=True, photo_id=photo_id)
                if not rsp:
                    return 'Failed to clear location'
            del params['location']
        return ''

    def set_albums(self, params, photo_id):
        current_albums = []
        if params['function'] != 'upload':
            # get albums existing photo is in
            rsp = self.api_call(
                'flickr.photos.getAllContexts', photo_id=photo_id)
            if 'set' in rsp:
                for album in rsp['set']:
                    current_albums.append(album['id'])
        for widget in params['albums']:
            album_id = widget.property('id')
            if not album_id:
                # create new set
                rsp = self.api_call(
                    'flickr.photosets.create', post=True,
                    primary_photo_id=photo_id,
                    title=widget.property('title'),
                    description=widget.property('description'))
                if not rsp:
                    return 'Failed to create album'
                widget.setProperty('id', rsp['photoset']['id'])
            elif album_id in current_albums:
                # photo is already in the set
                current_albums.remove(album_id)
            else:
                # add to existing set
                rsp = self.api_call('flickr.photosets.addPhoto', post=True,
                                    photo_id=photo_id, photoset_id=album_id)
                if not rsp:
                    return 'Failed to add to album'
        # remove from any other albums
        for album_id in current_albums:
            rsp = self.api_call('flickr.photosets.removePhoto', post=True,
                                photo_id=photo_id, photoset_id=album_id)
            if not rsp:
                return 'Failed to remove from album'
        return ''

    def upload_files(self, upload_list):
        for image, convert, params in upload_list:
            photo_id = params['photo_id']
            upload_data = {}
            if params['function']:
                # upload or replace photo
                if params['function'] == 'upload':
                    # set some metadata with upload function
                    for key in ('privacy', 'content_type', 'hidden',
                                'safety_level', 'meta'):
                        upload_data.update(params[key])
                        del params[key]
                else:
                    # replace existing photo
                    upload_data['photo_id'] = photo_id
                upload_data['async'] = '1'
            if 'hidden' in params:
                # flickr.photos.setSafetyLevel has different 'hidden' values
                # than upload function
                params['hidden']['hidden'] = str(
                    int(params['hidden']['hidden']) - 1)
                if 'safety_level' in params:
                    params['safety_level'].update(params['hidden'])
                    del params['hidden']
            if 'privacy' in params and 'permissions' in params:
                del params['privacy']
            if 'keywords' in params:
                params['keywords'] = {'tags': params['keywords']['keywords']}
            retry = True
            while retry:
                error = ''
                if not upload_data:
                    # no image conversion required
                    convert = None
                # UploadWorker converts image to fileobj
                fileobj, image_type = yield image, convert
                if upload_data:
                    # upload or replace photo
                    url = 'https://up.flickr.com/services/{}/'.format(
                        params['function'])
                    error, photo_id = self.upload_image(
                        url, upload_data, fileobj, image_type)
                    if not error:
                        # don't retry
                        upload_data = {}
                        # store photo id in image keywords, in main thread
                        self.upload_progress.emit({
                            'keyword': (image, 'flickr:id=' + photo_id)})
                # set metadata after uploading image
                if not error:
                    error = self.set_metadata(params, photo_id)
                # add to or remove from albums
                if 'albums' in params and not error:
                    error = self.set_albums(params, photo_id)
                retry = yield error


class HiddenWidget(QtWidgets.QCheckBox):
    def set_value(self, value):
        self.setChecked(value == '2')

    def get_value(self):
        return ('1', '2')[self.isChecked()]


class FlickrUser(UploaderUser):
    logger = logger
    name = 'flickr'
    oauth_url  = 'https://www.flickr.com/services/oauth/'
    max_size = {'image': {'bytes': 200 * (2 ** 20)},
                'video': {'bytes': 2 ** 30}}

    def on_connect(self, widgets):
        with self.session(parent=self) as session:
            # check auth
            connected = False
            rsp = session.api_call('flickr.auth.oauth.checkToken')
            if rsp:
                self.user_data['user_nsid'] = rsp['oauth']['user']['nsid']
                self.user_data['fullname'] = rsp['oauth']['user']['fullname']
                self.user_data['username'] = rsp['oauth']['user']['username']
                self.user_data['lang'] = None
                connected = rsp['oauth']['perms']['_content'] == 'write'
            yield 'connected', connected
            # get user icon
            rsp = session.api_call(
                'flickr.people.getInfo', user_id=self.user_data['user_nsid'])
            if rsp and rsp['person']['iconserver'] != '0':
                icon_url = (
                    'http://farm{iconfarm}.staticflickr.com/'
                    '{iconserver}/buddyicons/{id}.jpg').format(**rsp['person'])
            else:
                icon_url = 'https://www.flickr.com/images/buddyicon.gif'
            rsp = FlickrSession.check_response(
                session.api.get(icon_url), decode=False)
            picture = rsp and rsp.content
            yield 'user', (self.user_data['fullname'], picture)
            # get albums
            params = {'user_id': self.user_data['user_nsid'], 'per_page': '10'}
            page = 1
            while True:
                params['page'] = str(page)
                rsp = session.api_call('flickr.photosets.getList', **params)
                if not rsp:
                    break
                for album in rsp['photosets']['photoset']:
                    yield 'album', {
                        'title': album['title']['_content'],
                        'description': album['description']['_content'],
                        'id': album['id'],
                        'writeable': True,
                        }
                if rsp['photosets']['page'] == rsp['photosets']['pages']:
                    break
                page += 1
            # get licences
            rsp = session.api_call('flickr.photos.licenses.getInfo')
            if not rsp:
                return
            values = []
            for licence in rsp['licenses']['license']:
                licence['id'] = str(licence['id'])
                if licence['id'] == '7':
                    continue
                values.append((licence['name'], licence['id']))
            if values:
                widgets['license_id'].set_values(values, default='0')
            yield None, None
            # get user's default settings
            for key, function in (
                    ('privacy', 'flickr.prefs.getPrivacy'),
                    ('safety_level', 'flickr.prefs.getSafetyLevel'),
                    ('hidden', 'flickr.prefs.getHidden'),
                    ('content_type', 'flickr.prefs.getContentType'),
                    ):
                rsp = session.api_call(function)
                if not rsp:
                    return
                widgets[key].set_value(str(rsp['person'][key]))
                yield None, None

    def load_user_data(self):
        stored_token = self.get_password()
        if not stored_token:
            return False
        token, token_secret = stored_token.split('&')
        self.user_data['oauth_token'] = token
        self.user_data['oauth_token_secret'] = token_secret
        return True

    @staticmethod
    def service_name():
        return translate('FlickrTab', 'Flickr')

    def new_session(self, **kw):
        return FlickrSession(
            user_data=self.user_data, client_data=self.client_data, **kw)

    def auth_exchange(self, redirect_uri):
        with requests_oauthlib.OAuth1Session(
                callback_uri=redirect_uri, **self.client_data) as session:
            try:
                session.fetch_request_token(
                    self.oauth_url + 'request_token', timeout=20)
                result = yield session.authorization_url(
                    self.oauth_url + 'authorize', perms='write')
                oauth_verifier = str(result['oauth_verifier'][0])
                token = session.fetch_access_token(
                    self.oauth_url + 'access_token', verifier=oauth_verifier,
                    timeout=20)
            except Exception as ex:
                logger.error(str(ex))
                return
        self.set_password(
            token['oauth_token'] + '&' + token['oauth_token_secret'])
        self.user_data.update(token)
        self.connection_changed.emit(True)


class TabWidget(PhotiniUploader):
    logger = logger

    def __init__(self, *arg, **kw):
        self.user_widget = FlickrUser()
        super(TabWidget, self).__init__(*arg, **kw)

    @staticmethod
    def tab_name():
        return translate('FlickrTab', '&Flickr upload')

    def config_columns(self):
        self.replace_prefs = {'metadata': True}
        self.upload_prefs = {}
        ## first column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        group.setLayout(FormLayout(wrapped=True))
        # privacy
        self.widget['privacy'] = DropDownSelector(
            'privacy', values = (
                (translate('FlickrTab', 'Public'), '1'),
                (translate('FlickrTab', 'Private'), '5'),
                (translate('FlickrTab', 'Friends'), '2'),
                (translate('FlickrTab', 'Family'), '3'),
                (translate('FlickrTab', 'Friends & family'), '4')),
            default='1', with_multiple=False)
        group.layout().addRow(translate('FlickrTab', 'Viewing privacy'),
                              self.widget['privacy'])
        # permissions
        values = ((translate('FlickrTab', 'Only you'), '0'),
                  (translate('FlickrTab', 'Friends & family'), '1'),
                  (translate('FlickrTab', 'People you follow'), '2'),
                  (translate('FlickrTab', 'Any Flickr member'), '3'))
        self.widget['perm_comment'] = DropDownSelector(
            'perm_comment', values=values, default='3', with_multiple=False)
        group.layout().addRow(translate('FlickrTab', 'Allow commenting'),
                              self.widget['perm_comment'])
        self.widget['perm_addmeta'] = DropDownSelector(
            'perm_addmeta', values=values, default='2', with_multiple=False)
        group.layout().addRow(translate('FlickrTab', 'Allow tags and notes'),
                              self.widget['perm_addmeta'])
        # licence
        self.widget['license_id'] = DropDownSelector(
            'license_id', with_multiple=False)
        group.layout().addRow(translate('FlickrTab', 'Licence'),
                              self.widget['license_id'])
        column.addWidget(group, 0, 0)
        yield column, 0
        ## second column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        group.setLayout(FormLayout(wrapped=True))
        # safety level
        self.widget['safety_level'] = DropDownSelector(
            'safety_level', values=(
                (translate('FlickrTab', 'Safe'), '1'),
                (translate('FlickrTab', 'Moderate'), '2'),
                (translate('FlickrTab', 'Restricted'), '3')),
            default='1', with_multiple=False)
        group.layout().addRow(translate('FlickrTab', 'Safety level'),
                              self.widget['safety_level'])
        self.widget['hidden'] = HiddenWidget(
            translate('FlickrTab', 'Hide from search'))
        group.layout().addRow(self.widget['hidden'])
        # content type
        self.widget['content_type'] = DropDownSelector(
            'content_type', values=(
                (translate('FlickrTab', 'Photo'), '1'),
                (translate('FlickrTab', 'Screenshot'), '2'),
                (translate('FlickrTab', 'Art/Illustration'), '3'),
                (translate('FlickrTab', 'Virtual Photography'), '4')),
            default='1', with_multiple=False)
        group.layout().addRow(translate('FlickrTab', 'Content type'),
                              self.widget['content_type'])
        column.addWidget(group, 0, 0)
        # synchronise metadata
        self.buttons['sync'] = QtWidgets.QPushButton(
            translate('FlickrTab', 'Synchronise'))
        self.buttons['sync'].clicked.connect(self.sync_metadata)
        column.addWidget(self.buttons['sync'], 1, 0)
        # create new set
        button = QtWidgets.QPushButton(translate('FlickrTab', 'New album'))
        button.clicked.connect(self.new_album)
        column.addWidget(button, 2, 0)
        yield column, 0
        ## last column is list of albums
        yield self.album_list(), 1

    def get_fixed_params(self):
        albums = self.widget['albums'].get_checked_widgets()
        # is_public etc are optional parameters to
        # https://up.flickr.com/services/upload/ but required for
        # flickr.photos.setPerms. perm_comment and perm_addmeta are
        # optional for flickr.photos.setPerms but not accepted by
        # https://up.flickr.com/services/upload/
        privacy = {
            '1': {'is_friend': '0', 'is_family': '0', 'is_public': '1'},
            '2': {'is_friend': '1', 'is_family': '0', 'is_public': '0'},
            '3': {'is_friend': '0', 'is_family': '1', 'is_public': '0'},
            '4': {'is_friend': '1', 'is_family': '1', 'is_public': '0'},
            '5': {'is_friend': '0', 'is_family': '0', 'is_public': '0'},
            }[self.widget['privacy'].get_value()]
        permissions = dict(privacy)
        permissions['perm_comment'] = self.widget['perm_comment'].get_value()
        permissions['perm_addmeta'] = self.widget['perm_addmeta'].get_value()
        return {
            'privacy': privacy,
            'permissions': permissions,
            'safety_level': {
                'safety_level': self.widget['safety_level'].get_value(),
                },
            'hidden': {
                'hidden'      : self.widget['hidden'].get_value(),
                },
            'licence': {
                'license_id'  : self.widget['license_id'].get_value(),
                },
            'content_type': {
                'content_type': self.widget['content_type'].get_value(),
                },
            'albums': albums,
            }

    def accepted_image_type(self, file_type):
        return file_type in ('image/gif', 'image/jpeg', 'image/png')

    def get_variable_params(self, image, upload_prefs, replace_prefs, photo_id):
        params = {}
        # set upload function
        if upload_prefs['new_photo']:
            params['function'] = 'upload'
            photo_id = None
        elif upload_prefs['replace_image']:
            params['function'] = 'replace'
        else:
            params['function'] = None
        params['photo_id'] = photo_id
        # add metadata
        if upload_prefs['new_photo'] or replace_prefs['metadata']:
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
            gps = image.metadata.gps_info
            if gps and gps['lat']:
                params['location'] = {
                    'lat': '{:.6f}'.format(float(gps['lat'])),
                    'lon': '{:.6f}'.format(float(gps['lon'])),
                    }
            else:
                # clear any existing location
                params['location'] = None
        return params

    def replace_dialog(self, image):
        return super(TabWidget, self).replace_dialog(image, (
            ('metadata', translate('FlickrTab', 'Replace metadata')),
            ('privacy', translate('FlickrTab', 'Change viewing privacy')),
            ('permissions', translate(
                'FlickrTab',
                'Change who can comment or tag (and viewing privacy)')),
            ('safety_level', translate('FlickrTab', 'Change safety level')),
            ('hidden', translate('FlickrTab', 'Change hide from search')),
            ('licence', translate('FlickrTab', 'Change licence')),
            ('content_type', translate('FlickrTab', 'Change content type')),
            ('albums', translate('FlickrTab', 'Change album membership'))))

    _address_map = {
        'CountryName':   ('country',),
        'ProvinceState': ('county', 'region'),
        'City':          ('neighbourhood', 'locality'),
        }

    def merge_metadata(self, session, photo_id, image):
        rsp = session.api_call('flickr.photos.getInfo', photo_id=photo_id)
        if not rsp:
            return
        photo = rsp['photo']
        data = {
            'title': html.unescape(photo['title']['_content']),
            'description': html.unescape(photo['description']['_content']),
            'keywords': [x['raw'] for x in photo['tags']['tag']
                         if x['machine_tag'] == 0],
            }
        if photo['dates']['takenunknown'] == '0':
            granularity = int(photo['dates']['takengranularity'])
            if granularity >= 6:
                precision = 1
            elif granularity >= 4:
                precision = 2
            else:
                precision = 6
            data['date_taken'] = {
                'datetime': datetime.strptime(photo['dates']['taken'],
                                              '%Y-%m-%d %H:%M:%S'),
                'precision': precision, 'tz_offset': None}
        if 'location' in photo:
            data['gps_info'] = {'lat': photo['location']['latitude'],
                                'lon': photo['location']['longitude'],
                                'method': 'MANUAL'}
            address = {}
            for key in photo['location']:
                if '_content' in photo['location'][key]:
                    address[key] = photo['location'][key]['_content']
            data['location_taken'] = MD_Location.from_address(
                address, self._address_map)
        self.merge_metadata_items(image, data)

    @QtSlot()
    @catch_all
    def new_album(self):
        dialog = self.new_album_dialog()
        title = SingleLineEdit('title', spell_check=True)
        dialog.layout().addRow(translate('FlickrTab', 'Title'), title)
        description = MultiLineEdit('description', spell_check=True)
        dialog.layout().addRow(translate(
            'FlickrTab', 'Description'), description)
        dialog.layout().addRow(QtWidgets.QLabel(translate(
            'FlickrTab', 'Album will be created when photos are uploaded')))
        if not self.exec_album_dialog(dialog):
            return
        album = {
            'title': title.toPlainText(),
            'description': description.toPlainText(),
            'id': None,
            'writeable': True,
            }
        if not album['title']:
            return
        widget = self.widget['albums'].add_album(album, index=0)
        # set properties to be used when album is actually created
        widget.setProperty('title', album['title'])
        widget.setProperty('description', album['description'])
        widget.setChecked(True)
