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

from datetime import datetime
import html
import logging
import os
import time
import xml.etree.ElementTree as ET

import requests
import requests_oauthlib
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from photini.metadata import Location
from photini.pyqt import (
    catch_all, DropDownSelector, execute, MultiLineEdit, QtCore,
    QtSlot, QtWidgets, SingleLineEdit, width_for_text)
from photini.uploader import ConfigFormLayout, PhotiniUploader, UploaderSession

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

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
        self.auth = requests_oauthlib.OAuth1(
            client_key=self.api_key, client_secret=self.api_secret,
            resource_owner_key=token, resource_owner_secret=token_secret)
        rsp = self.api_call('flickr.auth.oauth.checkToken')
        if not rsp:
            return False
        authorised = rsp['oauth']['perms']['_content'] == 'write'
        if authorised:
            self.cached_data['nsid'] = rsp['oauth']['user']['nsid']
        self.connection_changed.emit(authorised)
        return authorised

    def get_auth_url(self, redirect_uri):
        # initialise oauth1 session
        if self.api:
            self.api.close()
        self.api = requests_oauthlib.OAuth1Session(
            client_key=self.api_key, client_secret=self.api_secret,
            callback_uri=redirect_uri)
        try:
            self.api.fetch_request_token(
                self.oauth_url + 'request_token', timeout=20)
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
                self.oauth_url + 'access_token', verifier=oauth_verifier,
                timeout=20)
        except Exception as ex:
            logger.error(str(ex))
            self.close_connection()
            return
        self.set_password(
            token['oauth_token'] + '&' + token['oauth_token_secret'])
        self.open_connection()

    def api_call(self, method, post=False, auth=True, **params):
        if not self.api:
            self.api = requests.session()
        params['method'] = method
        params['format'] = 'json'
        params['nojsoncallback'] = '1'
        kwds = {'timeout': 20}
        if auth:
            kwds['auth'] = self.auth
        else:
            params['api_key'] = self.api_key
        url = 'https://www.flickr.com/services/rest'
        try:
            if post:
                rsp = self.api.post(url, data=params, **kwds)
            else:
                rsp = self.api.get(url, params=params, **kwds)
        except Exception as ex:
            logger.error(str(ex))
            self.close_connection()
            return {}
        if rsp.status_code != 200:
            logger.error('HTTP error %d', rsp.status_code)
            return {}
        rsp = rsp.json()
        if not ('stat' in rsp and rsp['stat'] == 'ok'):
            logger.error('%s: %s', method, rsp['message'])
            return {}
        return rsp

    def get_user(self):
        if 'user' in self.cached_data:
            return self.cached_data['user']
        name, picture = None, None
        # get nsid of logged in user
        nsid = self.cached_data['nsid']
        # get user info
        rsp = self.api_call('flickr.people.getInfo', auth=False, user_id=nsid)
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
        rsp = self.api.get(icon_url)
        if rsp.status_code == 200:
            picture = rsp.content
        else:
            logger.error('HTTP error %d (%s)', rsp.status_code, icon_url)
        self.cached_data['user'] = name, picture
        return self.cached_data['user']

    def get_albums(self):
        if 'albums' in self.cached_data:
            return self.cached_data['albums']
        self.cached_data['albums'] = []
        page = 1
        while True:
            rsp = self.api_call(
                'flickr.photosets.getList', auth=False,
                user_id=self.cached_data['nsid'],
                page=str(page), per_page='10')
            if not rsp:
                break
            for album in rsp['photosets']['photoset']:
                details = {
                    'title': album['title']['_content'],
                    'description': album['description']['_content'],
                    'photoset_id': album['id'],
                    }
                self.cached_data['albums'].append(details)
                yield details
            if rsp['photosets']['page'] == rsp['photosets']['pages']:
                break
            page += 1

    def find_photos(self, min_taken_date, max_taken_date):
        # search Flickr
        page = 1
        while True:
            rsp = self.api_call(
                'flickr.people.getPhotos',
                user_id=self.cached_data['nsid'],
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

    def progress(self, monitor):
        self.upload_progress.emit(
            {'value': monitor.bytes_read * 100 // monitor.len})

    def do_upload(self, fileobj, image_type, image, params):
        photo_id = params['photo_id']
        if params['function']:
            # upload or replace photo
            self.upload_progress.emit({'busy': False})
            url = 'https://up.flickr.com/services/{}/'.format(params['function'])
            if params['function'] == 'upload':
                data = {}
                # set some metadata with upload function
                for key in ('privacy', 'content_type', 'hidden',
                            'safety_level', 'meta'):
                    data.update(params[key])
                    del(params[key])
            else:
                data = {'photo_id': photo_id}
            data['async'] = '1'
            # get the headers (without 'photo') from a dummy Request, an idea
            # I've stolen from https://github.com/sybrenstuvel/flickrapi
            headers = self.api.prepare_request(
                requests.Request('POST', url, auth=self.auth, data=data)).headers
            # add photo to parameters now we've got the headers without it
            data = list(data.items()) + [('photo', ('dummy_name', fileobj))]
            data = MultipartEncoderMonitor(
                MultipartEncoder(fields=data), self.progress)
            headers = {'Authorization': headers['Authorization'],
                       'Content-Type': data.content_type}
            # post data
            rsp = self.api.post(url, data=data, headers=headers, timeout=20)
            if rsp.status_code != 200:
                return '{}: HTTP error {}'.format(
                    params['function'], rsp.status_code)
            # parse XML response
            rsp = ET.fromstring(rsp.text)
            status = rsp.attrib['stat']
            if status != 'ok':
                return params['function'] + ' ' + status
            ticket_id = rsp.find('ticketid').text
            # wait for processing to finish
            self.upload_progress.emit({'busy': True})
            while True:
                rsp = self.api_call('flickr.photos.upload.checkTickets',
                                    auth=False, tickets=ticket_id)
                if not rsp:
                    return 'Wait for processing failed'
                complete = rsp['uploader']['ticket'][0]['complete']
                if complete == 1:
                    photo_id = rsp['uploader']['ticket'][0]['photoid']
                    break
                elif complete != 0:
                    return 'Flickr file conversion failed'
                time.sleep(1)
        # store photo id in image keywords
        keyword = 'flickr:id=' + photo_id
        if not image.metadata.keywords:
            image.metadata.keywords = [keyword]
        elif keyword not in image.metadata.keywords:
            image.metadata.keywords = list(image.metadata.keywords) + [keyword]
        # set metadata after uploading image
        if 'hidden' in params:
            # flickr.photos.setSafetyLevel has different 'hidden' values
            # than upload function
            params['hidden']['hidden'] = str(int(params['hidden']['hidden']) - 1)
            if 'safety_level' in params:
                params['safety_level'].update(params['hidden'])
                del params['hidden']
        if 'privacy' in params and 'permissions' in params:
            del params['privacy']
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
        for key in params:
            if params[key] and key in metadata_set_func:
                rsp = self.api_call(metadata_set_func[key], post=True,
                                    photo_id=photo_id, **params[key])
                if not rsp:
                    return 'Failed to set ' + key
        # existing photo may have a location that needs deleting
        if params['function'] != 'upload' and (
                'location' in params and not params['location']):
            rsp = self.api_call('flickr.photos.getInfo', photo_id=photo_id)
            if 'photo' in rsp and 'location' in rsp['photo']:
                self.api_call('flickr.photos.geo.removeLocation',
                              post=True, photo_id=photo_id)
        # add to or remove from albums
        if 'albums' not in params:
            return ''
        current_albums = {}
        if params['function'] != 'upload':
            # get albums existing photo is in
            rsp = self.api_call(
                'flickr.photos.getAllContexts', photo_id=photo_id)
            if 'set' in rsp:
                for p_set in rsp['set']:
                    current_albums[p_set['id']] = p_set
        for widget in params['albums']:
            photoset_id = widget.property('photoset_id')
            if not photoset_id:
                # create new set
                rsp = self.api_call(
                    'flickr.photosets.create', post=True,
                    primary_photo_id=photo_id,
                    title=widget.text().replace('&&', '&'),
                    description=widget.toolTip())
                if rsp:
                    widget.setProperty('photoset_id', rsp['photoset']['id'])
            elif photoset_id in current_albums:
                # photo is already in the set
                del current_albums[photoset_id]
            else:
                # add to existing set
                self.api_call('flickr.photosets.addPhoto', post=True,
                              photo_id=photo_id, photoset_id=photoset_id)
        # remove from any other albums
        for p_set in current_albums.values():
            self.api_call('flickr.photosets.removePhoto', post=True,
                          photo_id=photo_id, photoset_id=p_set['id'])
        return ''


class PermissionWidget(DropDownSelector):
    def __init__(self, default='3'):
        super(PermissionWidget, self).__init__(
            ((translate('FlickrTab', 'Only you'), '0'),
             (translate('FlickrTab', 'Friends & family'), '1'),
             (translate('FlickrTab', 'People you follow'), '2'),
             (translate('FlickrTab', 'Any Flickr member'), '3')),
            default=default)


class HiddenWidget(QtWidgets.QCheckBox):
    def set_value(self, value):
        self.setChecked(value == '2')

    def value(self):
        return ('1', '2')[self.isChecked()]


class TabWidget(PhotiniUploader):
    session_factory = FlickrSession

    @staticmethod
    def tab_name():
        return translate('FlickrTab', '&Flickr upload')

    def config_columns(self):
        self.service_name = translate('FlickrTab', 'Flickr')
        self.replace_prefs = {'metadata': True}
        self.upload_prefs = {}
        ## first column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        group.setLayout(ConfigFormLayout(wrapped=True))
        # privacy
        self.widget['privacy'] = DropDownSelector(
            ((translate('FlickrTab', 'Public'), '1'),
             (translate('FlickrTab', 'Private'), '5'),
             (translate('FlickrTab', 'Friends'), '2'),
             (translate('FlickrTab', 'Family'), '3'),
             (translate('FlickrTab', 'Friends & family'), '4')), default='1')
        group.layout().addRow(translate('FlickrTab', 'Viewing privacy'),
                              self.widget['privacy'])
        # permissions
        self.widget['perm_comment'] = PermissionWidget()
        group.layout().addRow(translate('FlickrTab', 'Allow commenting'),
                              self.widget['perm_comment'])
        self.widget['perm_addmeta'] = PermissionWidget(default='2')
        group.layout().addRow(translate('FlickrTab', 'Allow tags and notes'),
                              self.widget['perm_addmeta'])
        # licence
        self.widget['license_id'] = DropDownSelector(())
        group.layout().addRow(translate('FlickrTab', 'Licence'),
                              self.widget['license_id'])
        column.addWidget(group, 0, 0)
        yield column
        ## second column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        group.setLayout(ConfigFormLayout(wrapped=True))
        # safety level
        self.widget['safety_level'] = DropDownSelector(
            ((translate('FlickrTab', 'Safe'), '1'),
             (translate('FlickrTab', 'Moderate'), '2'),
             (translate('FlickrTab', 'Restricted'), '3')),
            default='1')
        group.layout().addRow(translate('FlickrTab', 'Safety level'),
                              self.widget['safety_level'])
        self.widget['hidden'] = HiddenWidget(
            translate('FlickrTab', 'Hide from search'))
        group.layout().addRow(self.widget['hidden'])
        # content type
        self.widget['content_type'] = DropDownSelector(
            ((translate('FlickrTab', 'Photo'), '1'),
             (translate('FlickrTab', 'Screenshot'), '2'),
             (translate('FlickrTab', 'Art/Illustration'), '3')),
            default='1')
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
        button.clicked.connect(self.new_set)
        column.addWidget(button, 2, 0)
        yield column

    def get_fixed_params(self):
        albums = []
        for child in self.widget['albums'].children():
            if child.isWidgetType() and child.isChecked():
                albums.append(child)
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
            }[self.widget['privacy'].value()]
        permissions = dict(privacy)
        permissions['perm_comment'] = self.widget['perm_comment'].value()
        permissions['perm_addmeta'] = self.widget['perm_addmeta'].value()
        return {
            'privacy': privacy,
            'permissions': permissions,
            'safety_level': {
                'safety_level': self.widget['safety_level'].value(),
                },
            'hidden': {
                'hidden'      : self.widget['hidden'].value(),
                },
            'licence': {
                'license_id'  : self.widget['license_id'].value(),
                },
            'content_type': {
                'content_type': self.widget['content_type'].value(),
                },
            'albums': albums,
            }

    def clear_albums(self):
        for child in self.widget['albums'].children():
            if child.isWidgetType():
                self.widget['albums'].layout().removeWidget(child)
                child.setParent(None)

    def add_album(self, album, index=-1):
        widget = QtWidgets.QCheckBox(album['title'].replace('&', '&&'))
        if album['description']:
            widget.setToolTip(html.unescape(album['description']))
        widget.setProperty('photoset_id', album['photoset_id'])
        if index >= 0:
            self.widget['albums'].layout().insertWidget(index, widget)
        else:
            self.widget['albums'].layout().addWidget(widget)
        return widget

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
        execute(dialog)
        return 'omit'

    def finalise_config(self):
        # get licences
        rsp = self.session.api_call(
            'flickr.photos.licenses.getInfo', auth=False)
        if not rsp:
            return
        values = []
        for licence in rsp['licenses']['license']:
            if licence['id'] == '7':
                continue
            values.append((licence['name'], licence['id']))
        if values:
            self.widget['license_id'].set_values(values, default='0')
        # get user's default settings
        for key, function in (
                ('privacy', 'flickr.prefs.getPrivacy'),
                ('safety_level', 'flickr.prefs.getSafetyLevel'),
                ('hidden', 'flickr.prefs.getHidden'),
                ('content_type', 'flickr.prefs.getContentType'),
                ):
            rsp = self.session.api_call(function)
            if not rsp:
                return
            self.widget[key].set_value(str(rsp['person'][key]))

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
            if image.metadata.latlong:
                params['location'] = {
                    'lat': '{:.6f}'.format(
                        float(image.metadata.latlong['lat'])),
                    'lon': '{:.6f}'.format(
                        float(image.metadata.latlong['lon'])),
                    }
            else:
                # clear any existing location
                params['location'] = None
        return params

    def replace_dialog(self, image):
        return super(TabWidget, self).replace_dialog(image, (
            ('metadata', translate('FlickrTab', 'Replace metadata')),
            ('privacy', translate('FlickrTab', 'Change viewing privacy')),
            ('permissions',
             translate('FlickrTab', 'Change who can comment or tag'
                       ' (and viewing privacy)')),
            ('safety_level',
             translate('FlickrTab', 'Change safety level')),
            ('hidden',
             translate('FlickrTab', 'Change hide from search')),
            ('licence', translate('FlickrTab', 'Change licence')),
            ('content_type', translate('FlickrTab', 'Change content type')),
            ('albums', translate('FlickrTab', 'Change album membership'))))

    _address_map = {
        'CountryName':   ('country',),
        'ProvinceState': ('county', 'region'),
        'City':          ('neighbourhood', 'locality'),
        }

    def merge_metadata(self, photo_id, image):
        rsp = self.session.api_call(
            'flickr.photos.getInfo', photo_id=photo_id)
        if not rsp:
            return
        photo = rsp['photo']
        data = {
            'title': html.unescape(photo['title']['_content']),
            'description': html.unescape(photo['description']['_content']),
            'keywords': [x['raw'] for x in photo['tags']['tag']],
            }
        if photo['dates']['takenunknown'] == '0':
            granularity = int(photo['dates']['takengranularity'])
            if granularity >= 6:
                precision = 1
            elif granularity >= 4:
                precision = 2
            else:
                precision = 6
            data['date_taken'] = (
                datetime.strptime(photo['dates']['taken'], '%Y-%m-%d %H:%M:%S'),
                precision, None)
        if 'location' in photo:
            data['latlong'] = (photo['location']['latitude'],
                               photo['location']['longitude'])
            address = {}
            for key in photo['location']:
                if '_content' in photo['location'][key]:
                    address[key] = photo['location'][key]['_content']
            data['location_taken'] = Location.from_address(address,
                                                           self._address_map)
        self.merge_metadata_items(image, **data)

    @QtSlot()
    @catch_all
    def new_set(self):
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate('FlickrTab', 'Create new Flickr album'))
        dialog.setLayout(ConfigFormLayout())
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
        if execute(dialog) != QtWidgets.QDialog.Accepted:
            return
        title = title.toPlainText()
        if not title:
            return
        description = description.toPlainText()
        widget = self.add_album(
            {'title': title, 'description': description, 'photoset_id': None},
            index=0)
        widget.setChecked(True)
