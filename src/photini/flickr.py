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
    oauth_url  = 'https://www.flickr.com/services/oauth/'

    def open_connection(self):
        if not self.api:
            self.auth = requests_oauthlib.OAuth1(
                resource_owner_key=self.user_data['oauth_token'],
                resource_owner_secret=self.user_data['oauth_token_secret'],
                client_key=self.client_data['client_key'],
                client_secret=self.client_data['client_secret'])
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
        if rsp is None:
            self.close_connection()
        elif rsp['stat'] != 'ok':
            logger.error('%s: %s', method, rsp['message'])
            return None
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
            if not (rsp and 'photos' in rsp and rsp['photos']['photo']):
                return
            for photo in rsp['photos']['photo']:
                date_taken = datetime.strptime(
                    photo['datetaken'], '%Y-%m-%d %H:%M:%S')
                yield photo['id'], date_taken, photo['url_t']
            page += 1

    def upload_image(self, url, data, fileobj, image_type):
        self.open_connection()
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
        return '', rsp.find('ticketid').text

    metadata_set_func = {
        'privacy':      'flickr.photos.setPerms',
        'permissions':  'flickr.photos.setPerms',
        'content_type': 'flickr.photos.setContentType',
        'safety_level': 'flickr.photos.setSafetyLevel',
        'hidden':       'flickr.photos.setSafetyLevel',
        'licence':      'flickr.photos.licenses.setLicense',
        'metadata':     'flickr.photos.setMeta',
        'keywords':     'flickr.photos.setTags',
        'dates':        'flickr.photos.setDates',
        'location':     'flickr.photos.geo.setLocation',
        }

    def set_metadata(self, params, photo_id):
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
        for key in list(params):
            if params[key] and key in self.metadata_set_func:
                rsp = self.api_call(self.metadata_set_func[key], post=True,
                                    photo_id=photo_id, **params[key])
                if rsp is None:
                    return 'Failed to set ' + key
                del params[key]
        # existing photo may have a location that needs deleting
        if params['function'] != 'upload' and (
                'location' in params and not params['location']):
            rsp = self.api_call('flickr.photos.getInfo', photo_id=photo_id)
            if rsp and 'photo' in rsp and 'location' in rsp['photo']:
                rsp = self.api_call('flickr.photos.geo.removeLocation',
                                    post=True, photo_id=photo_id)
                if rsp is None:
                    return 'Failed to clear location'
            del params['location']
        return ''

    def set_albums(self, params, photo_id):
        current_albums = []
        if params['function'] != 'upload':
            # get albums existing photo is in
            rsp = self.api_call(
                'flickr.photos.getAllContexts', photo_id=photo_id)
            if rsp and 'set' in rsp:
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
                if rsp is None:
                    return 'Failed to create album'
                widget.setProperty('id', rsp['photoset']['id'])
            elif album_id in current_albums:
                # photo is already in the set
                current_albums.remove(album_id)
            else:
                # add to existing set
                rsp = self.api_call('flickr.photosets.addPhoto', post=True,
                                    photo_id=photo_id, photoset_id=album_id)
                if rsp is None:
                    return 'Failed to add to album'
        # remove from any other albums
        for album_id in current_albums:
            rsp = self.api_call('flickr.photosets.removePhoto', post=True,
                                photo_id=photo_id, photoset_id=album_id)
            if rsp is None:
                return 'Failed to remove from album'
        return ''

    def get_notes(self, photo_id, photo=[]):
        if not photo:
            rsp = self.api_call('flickr.photos.getInfo', photo_id=photo_id)
            if rsp:
                photo = rsp['photo']
        if 'notes' in photo:
            for note in photo['notes']['note']:
                note['content'] = note['_content']
                note['is_person'] = False
                yield note
        if not ('people' in photo and photo['people']['haspeople'] == 1):
            return
        rsp = self.api_call('flickr.photos.people.getList', photo_id=photo_id)
        if rsp:
            for note in rsp['people']['person']:
                if not all(k in note for k in ('x', 'y', 'w', 'h')):
                    continue
                note['content'] = note['realname']
                if note['added_by'] == self.user_data['user_nsid']:
                    note['authorrealname'] = self.user_data['fullname']
                else:
                    rsp = self.api_call(
                        'flickr.people.getInfo', user_id=note['added_by'])
                    note['authorrealname'] = (
                        rsp and rsp['person']['realname']) or ''
                note['is_person'] = True
                yield note

    def set_notes(self, params, photo_id):
        if params['function'] != 'upload':
            # delete non-existent notes
            for note in self.get_notes(photo_id):
                local_note = dict((k, note[k]) for k in (
                    'x', 'y', 'w', 'h', 'content', 'is_person'))
                if local_note in params['notes']:
                    params['notes'].remove(local_note)
                    continue
                if note['is_person']:
                    rsp = self.api_call(
                        'flickr.photos.people.delete',
                        post=True, photo_id=photo_id, user_id=note['nsid'])
                else:
                    rsp = self.api_call('flickr.photos.notes.delete',
                                        post=True, note_id=note['id'])
                if rsp is None:
                    return 'Failed to delete note'
        # add new notes
        for note in params['notes']:
            if not note['is_person']:
                rsp = self.api_call(
                    'flickr.photos.notes.add', post=True, photo_id=photo_id,
                    note_x=note['x'], note_y=note['y'], note_w=note['w'],
                    note_h=note['h'], note_text=note['content'])
            elif note['content'] == self.user_data['fullname']:
                rsp = self.api_call(
                    'flickr.photos.people.add', post=True, photo_id=photo_id,
                    person_x=note['x'], person_y=note['y'], person_w=note['w'],
                    person_h=note['h'], user_id=self.user_data['user_nsid'])
            if rsp is None:
                return 'Failed to add note'
        return ''

    def upload_files(self, upload_list):
        upload_count = 0
        uploads = list(upload_list)
        tickets = {}
        metadata = []
        ticket_poll = 0.0
        while uploads or tickets or metadata:
            if uploads:
                # upload an image
                image, convert, params = uploads.pop(0)
                upload_count += 1
                self.upload_progress.emit({
                    'label': '{} ({}/{})'.format(
                        os.path.basename(image.path),
                        upload_count, len(upload_list)),
                    'busy': True})
                if params['function']:
                    # upload or replace photo
                    data = {'async': '1'}
                    if params['function'] == 'upload':
                        # set some metadata with upload function
                        for key in ('privacy', 'content_type', 'hidden',
                                    'safety_level', 'metadata'):
                            data.update(params[key])
                            del params[key]
                    else:
                        # replace existing photo
                        data['photo_id'] = params['photo_id']
                    url = 'https://up.flickr.com/services/{}/'.format(
                        params['function'])
                    with self.open_file(image, convert) as (image_type, fileobj):
                        error, ticket_id = self.upload_image(
                            url, data, fileobj, image_type)
                    if error:
                        self.upload_progress.emit({'error': (image, error)})
                        continue
                    if image_type.startswith('video'):
                        # can't set permissions or privacy while video is
                        # being processed
                        if 'privacy' in params:
                            del params['privacy']
                        if 'permissions' in params:
                            del params['permissions']
                    # add ticket and details to ticket queue
                    tickets[ticket_id] = image, params
                else:
                    # add details to metadata queue
                    metadata.append((image, params))
            if tickets:
                # check images currently being processed
                pause = ticket_poll - time.time()
                if pause > 0:
                    time.sleep(pause)
                ticket_poll = time.time() + 1.0
                rsp = self.api_call('flickr.photos.upload.checkTickets',
                                    tickets=','.join(tickets.keys()))
                if rsp is None:
                    self.upload_progress.emit({
                        'error': (image, 'Wait for processing failed')})
                for ticket in rsp['uploader']['ticket']:
                    if ticket['complete'] != 1:
                        continue
                    image, params = tickets[ticket['id']]
                    params['photo_id'] = ticket['photoid']
                    del tickets[ticket['id']]
                    # add details to metadata queue
                    metadata.append((image, params))
                    # store photo id in image keywords, in main thread
                    self.upload_progress.emit({
                        'keyword': (image, 'flickr:id=' + params['photo_id'])})
            while metadata:
                # set remaining metadata after uploading image(s)
                image, params = metadata.pop(0)
                error = self.set_metadata(params, params['photo_id'])
                if error:
                    self.upload_progress.emit({'error': (image, error)})
                    continue
                # add notes
                if 'notes' in params:
                    error = self.set_notes(params, params['photo_id'])
                    if error:
                        self.upload_progress.emit({'error': (image, error)})
                        continue
                # add to or remove from albums
                if 'albums' in params:
                    error = self.set_albums(params, params['photo_id'])
                    if error:
                        self.upload_progress.emit({'error': (image, error)})


class HiddenWidget(QtWidgets.QCheckBox):
    def set_value(self, value):
        self.setChecked(value == '2')

    def get_value(self):
        return ('1', '2')[self.isChecked()]


class FlickrUser(UploaderUser):
    logger = logger
    config_section = 'flickr'
    oauth_url  = 'https://www.flickr.com/services/oauth/'
    max_size = {'image': {'bytes': 200 * (2 ** 20)},
                'video': {'bytes': 2 ** 30}}

    def on_connect(self, widgets):
        with self.session(parent=self) as session:
            # check auth
            connected = False
            rsp = session.api_call('flickr.auth.oauth.checkToken')
            if rsp is None:
                yield 'connected', False
            self.user_data['user_nsid'] = rsp['oauth']['user']['nsid']
            self.user_data['fullname'] = rsp['oauth']['user']['fullname']
            self.user_data['username'] = rsp['oauth']['user']['username']
            self.user_data['lang'] = None
            yield 'connected', rsp['oauth']['perms']['_content'] == 'write'
            # get user icon
            rsp = session.api_call(
                'flickr.people.getInfo', user_id=self.user_data['user_nsid'])
            if rsp and rsp['person']['iconserver'] != '0':
                icon_url = (
                    'http://farm{iconfarm}.staticflickr.com/'
                    '{iconserver}/buddyicons/{id}.jpg').format(**rsp['person'])
            else:
                icon_url = 'https://www.flickr.com/images/buddyicon.gif'
            rsp = session.check_response(
                session.api.get(icon_url), decode=False)
            picture = rsp and rsp.content
            yield 'user', (self.user_data['fullname'], picture)
            # get albums
            params = {'user_id': self.user_data['user_nsid'], 'per_page': '10'}
            page = 1
            while True:
                params['page'] = str(page)
                rsp = session.api_call('flickr.photosets.getList', **params)
                if rsp is None:
                    yield 'connected', False
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
            if rsp is None:
                yield 'connected', False
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
                if rsp is None:
                    yield 'connected', False
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
                callback_uri=redirect_uri,
                client_key=self.client_data['client_key'],
                client_secret=self.client_data['client_secret']) as session:
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
        return translate('FlickrTab', 'Flickr upload',
                         'Full name of tab shown as a tooltip')

    @staticmethod
    def tab_short_name():
        return translate('FlickrTab', '&Flickr',
                         'Shortest possible name used as tab label')

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

    def accepted_image_type(self, file_type):
        return file_type in ('image/gif', 'image/jpeg', 'image/png')

    def get_params(self, image, upload_prefs, replace_prefs, photo_id):
        params = {'photo_id': photo_id}
        # set upload function
        if upload_prefs['new_photo']:
            params['function'] = 'upload'
        elif upload_prefs['replace_image']:
            params['function'] = 'replace'
        else:
            params['function'] = None
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
            if gps and gps['exif:GPSLatitude']:
                params['location'] = {
                    'lat': '{:.6f}'.format(float(gps['exif:GPSLatitude'])),
                    'lon': '{:.6f}'.format(float(gps['exif:GPSLongitude'])),
                    }
            else:
                # clear any existing location
                params['location'] = None
        # privacy
        privacy = {
            '1': {'is_friend': '0', 'is_family': '0', 'is_public': '1'},
            '2': {'is_friend': '1', 'is_family': '0', 'is_public': '0'},
            '3': {'is_friend': '0', 'is_family': '1', 'is_public': '0'},
            '4': {'is_friend': '1', 'is_family': '1', 'is_public': '0'},
            '5': {'is_friend': '0', 'is_family': '0', 'is_public': '0'},
            }[self.widget['privacy'].get_value()]
        if upload_prefs['new_photo'] or replace_prefs['privacy']:
            params['privacy'] = privacy
        # permissions
        if upload_prefs['new_photo'] or replace_prefs['permissions']:
            params['permissions'] = {
                'perm_comment': self.widget['perm_comment'].get_value(),
                'perm_addmeta': self.widget['perm_addmeta'].get_value(),
                }
            params['permissions'].update(privacy)
        # safety level
        if upload_prefs['new_photo'] or replace_prefs['safety_level']:
            params['safety_level'] = {
                'safety_level': self.widget['safety_level'].get_value()}
        # hidden
        if upload_prefs['new_photo'] or replace_prefs['hidden']:
            params['hidden'] = {'hidden': self.widget['hidden'].get_value()}
        # licence
        if upload_prefs['new_photo'] or replace_prefs['licence']:
            params['licence'] = {
                'license_id': self.widget['license_id'].get_value()}
        # content type
        if upload_prefs['new_photo'] or replace_prefs['content_type']:
            params['content_type'] = {
                'content_type': self.widget['content_type'].get_value()}
        # albums
        if upload_prefs['new_photo'] or replace_prefs['albums']:
            params['albums'] = self.widget['albums'].get_checked_widgets()
        # notes
        if upload_prefs['new_photo'] or replace_prefs['notes']:
            params['notes'] = []
            for note in image.metadata.image_region.to_notes(image, 500):
                params['notes'].append(note)
                if note['is_person']:
                    # Flickr doesn't show box around person, so add one
                    note = dict(note)
                    note['is_person'] = False
                    params['notes'].append(note)
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
            ('albums', translate('FlickrTab', 'Change album membership')),
            ('notes', translate('FlickrTab', 'Replace image region notes'))))

    _address_map = {
        'Iptc4xmpExt:CountryName':   ('country',),
        'Iptc4xmpExt:ProvinceState': ('county', 'region'),
        'Iptc4xmpExt:City':          ('neighbourhood', 'locality'),
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
            gps = {'lat': photo['location']['latitude'],
                   'lng': photo['location']['longitude']}
            address = {}
            for key in photo['location']:
                if '_content' in photo['location'][key]:
                    address[key] = photo['location'][key]['_content']
            data['location_taken'] = [MD_Location.from_address(
                gps, address, self._address_map)]
        # get annotated image regions
        notes = session.get_notes(photo_id, photo=photo)
        if notes:
            data['image_region'] = image.metadata.image_region.from_notes(
                notes, image, 500)
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
