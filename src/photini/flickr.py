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

from __future__ import unicode_literals

from datetime import datetime, timedelta
import html
import logging
import os
import time
import xml.etree.ElementTree as ET

import requests
import requests_oauthlib
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from photini.metadata import DateTime, LatLon, Location
from photini.pyqt import (
    Busy, catch_all, DropDownSelector, execute, MultiLineEdit, Qt, QtCore,
    QtGui, QtSignal, QtSlot, QtWidgets, SingleLineEdit, width_for_text)
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

    def api_call(self, method, auth=True, **params):
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
        kwds['params'] = params
        try:
            rsp = self.api.get('https://www.flickr.com/services/rest', **kwds)
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
        if 'sets' in self.cached_data:
            return self.cached_data['sets']
        self.cached_data['sets'] = []
        sets = self.api_call('flickr.photosets.getList', auth=False,
                             user_id=self.cached_data['nsid'])
        if not sets:
            return self.cached_data['sets']
        for item in sets['photosets']['photoset']:
            self.cached_data['sets'].append((
                item['title']['_content'], item['description']['_content'],
                item['id']))
        return self.cached_data['sets']

    def get_info(self, photo_id):
        rsp = self.api_call(
            'flickr.photos.getInfo', photo_id=photo_id, auth=False)
        if not rsp:
            return None
        return rsp['photo']

    def find_photos(self, min_taken_date, max_taken_date):
        # search Flickr
        page = 1
        while True:
            with Busy():
                rsp = self.api_call(
                    'flickr.people.getPhotos', auth=False,
                    user_id=self.cached_data['nsid'],
                    page=page, extras='date_taken,url_t',
                    min_taken_date=min_taken_date.strftime('%Y-%m-%d %H:%M:%S'),
                    max_taken_date=max_taken_date.strftime('%Y-%m-%d %H:%M:%S'))
                if not ('photos' in rsp and rsp['photos']['photo']):
                    return
            for photo in rsp['photos']['photo']:
                yield photo
            page += 1

    def progress(self, monitor):
        self.upload_progress.emit(
            {'value': monitor.bytes_read * 100 // monitor.len})

    def do_upload(self, fileobj, image_type, image, params):
        photo_id = params['photo_id']
        if params['function']:
            # upload or replace photo
            url = 'https://up.flickr.com/services/{}/'.format(params['function'])
            if params['function'] == 'upload':
                data = {}
                # set some metadata with upload function
                for key in ('visibility', 'content_type', 'safety_level',
                            'meta'):
                    if key in params and params[key]:
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
            data['photo'] = ('dummy_name', fileobj)
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
        keyword = '{}={}'.format(ID_TAG, photo_id)
        if not image.metadata.keywords:
            image.metadata.keywords = [keyword]
        elif keyword not in image.metadata.keywords:
            image.metadata.keywords = list(image.metadata.keywords) + [keyword]
        # set metadata after uploading image
        metadata_set_func = {
            'visibility':   'flickr.photos.setPerms',
            'permissions':  'flickr.photos.setPerms',
            'content_type': 'flickr.photos.setContentType',
            'safety_level': 'flickr.photos.setSafetyLevel',
            'licence':      'flickr.photos.licenses.setLicense',
            'meta':         'flickr.photos.setMeta',
            'tags':         'flickr.photos.setTags',
            'dates':        'flickr.photos.setDates',
            'location':     'flickr.photos.geo.setLocation',
            }
        for key in params:
            if params[key] and key in metadata_set_func:
                rsp = self.api_call(metadata_set_func[key],
                                    photo_id=photo_id, **params[key])
                if not rsp:
                    return 'Failed to set ' + key
        # existing photo may have a location that needs deleting
        if params['function'] != 'upload' and (
                'location' in params and not params['location']):
            self.api_call(
                'flickr.photos.getInfo', auth=False, photo_id=photo_id)
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


class PermissionWidget(DropDownSelector):
    def __init__(self, default='3'):
        super(PermissionWidget, self).__init__(
            ((translate('FlickrTab', 'Only you'), '0'),
             (translate('FlickrTab', 'Friends and family'), '1'),
             (translate('FlickrTab', 'People you follow'), '2'),
             (translate('FlickrTab', 'Any Flickr member'), '3')),
            default=default)


class ConfigFormLayout(QtWidgets.QFormLayout):
    def __init__(self, wrapped=False, **kwds):
        super(ConfigFormLayout, self).__init__(**kwds)
        if wrapped:
            self.setRowWrapPolicy(self.WrapAllRows)
        self.setFieldGrowthPolicy(self.AllNonFixedFieldsGrow)


class TabWidget(PhotiniUploader):
    session_factory = FlickrSession

    @staticmethod
    def tab_name():
        return translate('FlickrTab', '&Flickr upload')

    def config_columns(self):
        self.service_name = translate('FlickrTab', 'Flickr')
        self.replace_prefs = {'set_metadata': True}
        # dictionary of all widgets with parameter settings
        self.widget = {}
        ## first column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        group.setLayout(ConfigFormLayout(wrapped=True))
        # visibility
        self.widget['visibility'] = DropDownSelector(
            ((translate('FlickrTab', 'Public'),
              {'is_friend': '0', 'is_family': '0', 'is_public': '1'}),
             (translate('FlickrTab', 'Private'),
              {'is_friend': '0', 'is_family': '0', 'is_public': '0'}),
             (translate('FlickrTab', 'Friends'),
              {'is_friend': '1', 'is_family': '0', 'is_public': '0'}),
             (translate('FlickrTab', 'Family'),
              {'is_friend': '0', 'is_family': '1', 'is_public': '0'}),
             (translate('FlickrTab', 'Friends and family'),
              {'is_friend': '1', 'is_family': '1', 'is_public': '0'})),
            default={'is_friend': '0', 'is_family': '0', 'is_public': '1'})
        group.layout().addRow(translate('FlickrTab', 'Viewing privacy'),
                              self.widget['visibility'])
        # permissions
        self.widget['perm_comment'] = PermissionWidget()
        group.layout().addRow(translate('FlickrTab', 'Allow commenting'),
                              self.widget['perm_comment'])
        self.widget['perm_addmeta'] = PermissionWidget(default='2')
        group.layout().addRow(translate('FlickrTab', 'Allow tags and notes'),
                              self.widget['perm_addmeta'])
        column.addWidget(group, 0, 0)
        # synchronise metadata
        self.sync_button = QtWidgets.QPushButton(
            translate('FlickrTab', 'Synchronise'))
        self.sync_button.clicked.connect(self.sync_metadata)
        column.addWidget(self.sync_button, 1, 0)
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
        self.widget['hidden'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Hidden from search'))
        group.layout().addRow(self.widget['hidden'])
        # licence
        self.widget['license_id'] = DropDownSelector(
            ((translate('FlickrTab', 'All rights reserved'), '0'),
             (translate('FlickrTab', 'Public domain mark'), '10'),
             (translate('FlickrTab', 'Public domain dedication (CC0)'), '9'),
             (translate('FlickrTab', 'Attribution'), '4'),
             (translate('FlickrTab', 'Attribution-ShareAlike'), '5'),
             (translate('FlickrTab', 'Attribution-NoDerivs'), '6'),
             (translate('FlickrTab', 'Attribution-NonCommercial'), '2'),
             (translate(
                 'FlickrTab', 'Attribution-NonCommercial-ShareAlike'), '1'),
             (translate(
                 'FlickrTab', 'Attribution-NonCommercial-NoDerivs'), '3')),
            default='0')
        group.layout().addRow(translate('FlickrTab', 'Licence'),
                              self.widget['license_id'])
        # content type
        self.widget['content_type'] = DropDownSelector(
            ((translate('FlickrTab', 'Photo'), '1'),
             (translate('FlickrTab', 'Screenshot'), '2'),
             (translate('FlickrTab', 'Art/Illustration'), '3')),
            default='1')
        group.layout().addRow(translate('FlickrTab', 'Content type'),
                              self.widget['content_type'])
        column.addWidget(group, 0, 0)
        # create new set
        button = QtWidgets.QPushButton(translate('FlickrTab', 'New album'))
        button.clicked.connect(self.new_set)
        column.addWidget(button, 2, 0)
        yield column
        ## 3rd column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setLayout(QtWidgets.QVBoxLayout())
        # list of sets widget
        group.layout().addWidget(
            QtWidgets.QLabel(translate('FlickrTab', 'Add to albums')))
        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setFrameStyle(QtWidgets.QFrame.NoFrame)
        scrollarea.setStyleSheet("QScrollArea {background-color: transparent}")
        self.widget['sets'] = QtWidgets.QWidget()
        self.widget['sets'].setLayout(QtWidgets.QVBoxLayout())
        self.widget['sets'].layout().setSpacing(0)
        self.widget['sets'].layout().setSizeConstraint(
            QtWidgets.QLayout.SetMinAndMaxSize)
        scrollarea.setWidget(self.widget['sets'])
        self.widget['sets'].setAutoFillBackground(False)
        group.layout().addWidget(scrollarea)
        column.addWidget(group, 0, 0)
        yield column

    def get_fixed_params(self):
        sets = []
        for child in self.widget['sets'].children():
            if child.isWidgetType() and child.isChecked():
                sets.append(child)
        permissions = dict(self.widget['visibility'].value())
        permissions['perm_comment'] = self.widget['perm_comment'].value()
        permissions['perm_addmeta'] = self.widget['perm_addmeta'].value()
        return {
            'visibility': self.widget['visibility'].value(),
            'permissions': permissions,
            'safety_level': {
                'safety_level': self.widget['safety_level'].value(),
                'hidden'      : str(int(self.widget['hidden'].isChecked())),
                },
            'licence': {
                'license_id'  : self.widget['license_id'].value(),
                },
            'content_type': {
                'content_type': self.widget['content_type'].value(),
                },
            'sets': sets,
            }

    def clear_sets(self):
        for child in self.widget['sets'].children():
            if child.isWidgetType():
                self.widget['sets'].layout().removeWidget(child)
                child.setParent(None)

    def add_set(self, title, description, photoset_id, index=-1):
        widget = QtWidgets.QCheckBox(title.replace('&', '&&'))
        if description:
            widget.setToolTip(html.unescape(description))
        widget.setProperty('photoset_id', photoset_id)
        if index >= 0:
            self.widget['sets'].layout().insertWidget(index, widget)
        else:
            self.widget['sets'].layout().addWidget(widget)
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

    def show_album_list(self, albums):
        self.clear_sets()
        for item in albums:
            self.add_set(*item)

    def get_upload_params(self, image):
        option, photo_id = self._replace_dialog(image)
        if not any(option.values()):
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
        fixed_params = self.get_fixed_params()
        if option['new_photo']:
            params.update(fixed_params)
        else:
            if option['set_visibility']:
                params['visibility'] = fixed_params['visibility']
            if option['set_permissions']:
                params['permissions'] = fixed_params['permissions']
            if option['set_safety_level']:
                params['safety_level'] = fixed_params['safety_level']
            if option['set_licence']:
                params['licence'] = fixed_params['licence']
            if option['set_type']:
                params['content_type'] = fixed_params['content_type']
            if option['set_albums']:
                params['sets'] = fixed_params['sets']
        # add metadata
        if option['new_photo'] or option['set_metadata']:
            # title & description
            params['meta'] = {
                'title'      : image.metadata.title or image.name,
                'description': image.metadata.description or '',
                }
            # keywords
            keywords = ['uploaded:by=photini']
            for keyword in image.metadata.keywords or []:
                if not keyword.startswith(ID_TAG):
                    keyword = keyword.replace('"', "'")
                    if ',' in keyword:
                        keyword = '"' + keyword + '"'
                    keywords.append(keyword)
            params['tags'] = {'tags': ','.join(keywords)}
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

    def _replace_dialog(self, image):
        # has image already been uploaded?
        for keyword in image.metadata.keywords or []:
            name_pred, sep, photo_id = keyword.partition('=')
            if name_pred == ID_TAG:
                break
        else:
            # new upload
            return {'new_photo': True}, None
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
            translate('FlickrTab', 'Change visibility'))
        widget['set_permissions'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Change who can comment or tag'))
        widget['set_safety_level'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Change safety level'))
        widget['set_licence'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Change the licence'))
        widget['set_type'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Change content type'))
        widget['set_albums'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Change album membership'))
        widget['replace_image'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Replace image'))
        widget['new_photo'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'Upload as new photo'))
        widget['no_upload'] = QtWidgets.QCheckBox(
            translate('FlickrTab', 'No image upload'))
        widget['no_upload'].setChecked(True)
        button_group = QtWidgets.QButtonGroup()
        button_group.addButton(widget['replace_image'])
        button_group.addButton(widget['new_photo'])
        button_group.addButton(widget['no_upload'])
        for key in self.replace_prefs:
            widget[key].setChecked(self.replace_prefs[key])
        two_columns = QtWidgets.QHBoxLayout()
        column = QtWidgets.QVBoxLayout()
        for key in ('set_metadata', 'set_visibility', 'set_permissions',
                    'set_safety_level', 'set_licence', 'set_type',
                    'set_albums'):
            widget['new_photo'].toggled.connect(widget[key].setDisabled)
            column.addWidget(widget[key])
        two_columns.addLayout(column)
        column = QtWidgets.QVBoxLayout()
        for key in ('replace_image', 'new_photo', 'no_upload'):
            column.addWidget(widget[key])
        column.addStretch(1)
        two_columns.addLayout(column)
        dialog.layout().addLayout(two_columns)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addWidget(button_box)
        if execute(dialog) != QtWidgets.QDialog.Accepted:
            return {}, photo_id
        for key in widget:
            if key != 'no_upload':
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
        dialog.setLayout(ConfigFormLayout(wrapped=True))
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
        if execute(dialog) == QtWidgets.QDialog.Accepted:
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
        widget = self.add_set(title, description, None, index=0)
        widget.setChecked(True)

    def new_selection(self, selection):
        super(TabWidget, self).new_selection(selection)
        self.sync_button.setEnabled(
            len(selection) > 0 and self.user_connect.is_checked())
