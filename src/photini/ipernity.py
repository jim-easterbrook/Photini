##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2022  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import hashlib
import logging
import os
import time

try:
    import PIL.Image as PIL
except ImportError:
    PIL = None
import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from photini.pyqt import *
from photini.uploader import PhotiniUploader, UploaderSession
from photini.widgets import (
    DropDownSelector, Label, MultiLineEdit, SingleLineEdit)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

# Ipernity API: http://www.ipernity.com/help/api
# requests: https://docs.python-requests.org/

class IpernitySession(UploaderSession):
    name = 'ipernity'

    def open_connection(self):
        self.cached_data = {}
        self.auth_token = self.get_password()
        if not self.auth_token:
            return False
        rsp = self.api_call('auth.checkToken')
        authorised = rsp and rsp['auth']['permissions']['doc'] == 'write'
        if authorised:
            self.cached_data['user_id'] = rsp['auth']['user']['user_id']
        self.connection_changed.emit(authorised)
        return authorised

    def get_frob(self):
        rsp = self.api_call('auth.getFrob', auth=False)
        if not rsp:
            return ''
        return rsp['auth']['frob']

    def get_auth_url(self, frob):
        params = {'frob': frob, 'perm_doc': 'write'}
        params = self.sign_request('', False, params)
        request = requests.Request(
            'GET', 'http://www.ipernity.com/apps/authorize', params=params)
        return request.prepare().url

    def get_access_token(self, frob):
        if not frob:
            return
        rsp = self.api_call('auth.getToken', auth=False, frob=frob)
        if not rsp:
            return
        self.set_password(rsp['auth']['token'])
        self.open_connection()

    def sign_request(self, method, auth, params):
        params = dict(params)
        params['api_key'] = self.api_key
        if auth:
            params['auth_token'] = self.auth_token
        string = ''
        for key in sorted(params):
            string += key + params[key]
        string += method + self.api_secret
        params['api_sig'] = hashlib.md5(string.encode('utf-8')).hexdigest()
        return params

    def api_call(self, method, post=False, auth=True, **params):
        if not self.api:
            self.api = requests.session()
        url = 'http://api.ipernity.com/api/' + method
        params = self.sign_request(method, auth, params)
        try:
            if post:
                rsp = self.api.post(url, timeout=20, data=params)
            else:
                rsp = self.api.get(url, timeout=20, params=params)
        except Exception as ex:
            logger.error(str(ex))
            self.close_connection()
            return {}
        if rsp.status_code != 200:
            logger.error('HTTP error %s: %d', method, rsp.status_code)
            return {}
        rsp = rsp.json()
        if rsp['api']['status'] != 'ok':
            logger.error('API error %s: %s', method, str(rsp['api']))
            return {}
        return rsp

    def get_user(self):
        if 'user' in self.cached_data:
            return self.cached_data['user']
        name, picture = None, None
        # get user info
        rsp = self.api_call(
            'user.get', auth=False, user_id=self.cached_data['user_id'])
        if not rsp:
            return name, picture
        self.cached_data['is_pro'] = rsp['user']['is_pro']
        name = rsp['user']['username']
        icon_url = rsp['user']['icon']
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
            # get list of album ids
            rsp = self.api_call(
                'album.getList', empty='1', page=str(page), per_page='10')
            if not rsp:
                break
            albums = rsp['albums']
            # get details of each album
            for album in albums['album']:
                rsp = self.api_call('album.get', album_id=album['album_id'])
                if not rsp:
                    continue
                details = {
                    'title': rsp['album']['title'],
                    'description': rsp['album']['description'],
                    'album_id': rsp['album']['album_id'],
                    }
                self.cached_data['albums'].append(details)
                yield details
            if int(albums['page']) >= int(albums['pages']):
                break
            page += 1

    def find_photos(self, min_taken_date, max_taken_date):
        # search Ipernity
        params = {
            'user_id': self.cached_data['user_id'],
            'media': 'photo,video',
            'created_min': min_taken_date.strftime('%Y-%m-%d %H:%M:%S'),
            'created_max': max_taken_date.strftime('%Y-%m-%d %H:%M:%S'),
            'extra': 'dates',
            'thumbsize': '100',
            }
        while True:
            rsp = self.api_call('doc.search', **params)
            if not (rsp and 'doc' in rsp['docs'] and rsp['docs']['doc']):
                return
            for photo in rsp['docs']['doc']:
                date_taken = datetime.strptime(
                    photo['dates']['created'], '%Y-%m-%d %H:%M:%S')
                yield photo['doc_id'], date_taken, photo['thumb']['url']
            page = int(rsp['docs']['page'])
            if page == int(rsp['docs']['pages']):
                return
            params['page'] = str(page + 1)

    def progress(self, monitor):
        self.upload_progress.emit(
            {'value': monitor.bytes_read * 100 // monitor.len})

    def do_upload(self, fileobj, image_type, image, params):
        doc_id = params['doc_id']
        if params['function']:
            # upload or replace photo
            self.upload_progress.emit({'busy': False})
            url = 'http://api.ipernity.com/api/' + params['function']
            if params['function'] == 'upload.file':
                data = {}
                # set some metadata with upload function
                for key in ('visibility', 'permissions', 'licence', 'meta',
                            'dates', 'location'):
                    if key in params and params[key]:
                        data.update(params[key])
                        del(params[key])
            else:
                data = {'doc_id': doc_id}
            data['async'] = '1'
            # sign the request before including the file to upload
            data = self.sign_request(params['function'], True, data)
            # create multi-part data encoder
            data = list(data.items()) + [('file', ('dummy_name', fileobj))]
            data = MultipartEncoderMonitor(
                MultipartEncoder(fields=data), self.progress)
            headers = {'Content-Type': data.content_type}
            # post data
            rsp = self.api.post(url, data=data, headers=headers, timeout=20)
            if rsp.status_code != 200:
                logger.error('HTTP error %d', rsp.status_code)
                return 'HTTP error {}'.format(rsp.status_code)
            # parse response
            rsp = rsp.json()
            if rsp['api']['status'] != 'ok':
                return params['function'] + ' ' + str(rsp['api'])
            ticket = rsp['ticket']
            # wait for processing to finish
            self.upload_progress.emit({'busy': True})
            # upload.checkTickets returns an eta but it's very
            # unreliable (e.g. saying 360 seconds for something that
            # then takes 15). Easier to poll every two seconds.
            while True:
                time.sleep(2)
                rsp = self.api_call('upload.checkTickets', tickets=ticket)
                if not rsp:
                    return 'Wait for processing failed'
                if rsp['tickets']['done'] != '0':
                    break
            doc_id = rsp['tickets']['ticket'][0]['doc_id']
        # store photo id in image keywords, in main thread
        self.upload_progress.emit({'keyword': (image, 'ipernity:id=' + doc_id)})
        # set remaining metadata after uploading image
        if 'visibility' in params and 'permissions' in params:
            params['permissions'].update(params['visibility'])
            del params['visibility']
        metadata_set_func = {
            'visibility' : 'doc.setPerms',
            'permissions': 'doc.setPerms',
            'licence'    : 'doc.setLicense',
            'meta'       : 'doc.set',
            'keywords'   : 'doc.tags.edit',
            'location'   : 'doc.setGeo',
            }
        for key in params:
            if params[key] and key in metadata_set_func:
                rsp = self.api_call(metadata_set_func[key], post=True,
                                    doc_id=doc_id, **params[key])
                if not rsp:
                    return 'Failed to set ' + key
        # add to or remove from albums
        if 'albums' not in params:
            return ''
        current_albums = []
        if params['function'] != 'upload.file':
            # get albums existing photo is in
            rsp = self.api_call('doc.getContainers', doc_id=doc_id)
            if not rsp:
                return 'Failed to get album list'
            for album in rsp['albums']['album']:
                current_albums.append(album['album_id'])
        for album_id in params['albums']:
            if album_id in current_albums:
                # photo is already in the set
                current_albums.remove(album_id)
            else:
                # add to existing album
                rsp = self.api_call('album.docs.add', post=True,
                                    album_id=album_id, doc_id=doc_id)
                if not rsp:
                    return 'Failed to set album'
        # remove from any other albums
        for album_id in current_albums:
            self.api_call('album.docs.remove', post=True,
                          album_id=album_id, doc_id=doc_id)
        return ''


class PermissionWidget(DropDownSelector):
    def __init__(self, *args, default='5'):
        super(PermissionWidget, self).__init__(
            *args, values=(
                (translate('IpernityTab', 'Only you'), '0'),
                (translate('IpernityTab', 'Family & friends'), '3'),
                (translate('IpernityTab', 'Contacts'), '4'),
                (translate('IpernityTab', 'Everyone'), '5')),
            default=default, with_multiple=False)


class LicenceWidget(DropDownSelector):
    def __init__(self, *args, default='0'):
        super(LicenceWidget, self).__init__(
            *args, values=(
                (translate('IpernityTab',
                           'Copyright (all rights reserved)'), '0'),
                (translate('IpernityTab', 'Attribution'), '1'),
                (translate('IpernityTab', 'Attribution + non commercial'), '3'),
                (translate('IpernityTab', 'Attribution + no derivative'), '5'),
                (translate('IpernityTab', 'Attribution + share alike'), '9'),
                (translate('IpernityTab',
                           'Attribution + non commercial + no derivative'), '7'),
                (translate('IpernityTab',
                           'Attribution + non commercial + share alike'), '11'),
                (translate(
                    'IpernityTab',
                    'Free use (copyright surrendered, no licence)'), '255')),
            default=default, with_multiple=False)


class TabWidget(PhotiniUploader):
    logger = logger
    session_factory = IpernitySession

    @staticmethod
    def tab_name():
        return translate('IpernityTab', '&Ipernity upload')

    def config_columns(self):
        self.service_name = translate('IpernityTab', 'Ipernity')
        self.replace_prefs = {'metadata': True}
        self.upload_prefs = {}
        ## first column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        # "who can" group spans two columns
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 46))
        group.setLayout(QtWidgets.QGridLayout())
        group.layout().addWidget(QtWidgets.QLabel(
            translate('IpernityTab', 'Who can:')), 0, 0)
        # visibility
        self.widget['visibility'] = DropDownSelector(
            'visibility', values=(
                (translate('IpernityTab', 'Everyone (public)'), '4'),
                (translate('IpernityTab', 'Only you (private)'), '0'),
                (translate('IpernityTab', 'Friends'), '2'),
                (translate('IpernityTab', 'Family'), '1'),
                (translate('IpernityTab', 'Family & friends'), '3')),
            default='4', with_multiple=False)
        self.widget['visibility'].new_value.connect(self.new_value)
        group.layout().addWidget(QtWidgets.QLabel(
            translate('IpernityTab', 'see the photo')), 1, 0)
        group.layout().addWidget(self.widget['visibility'], 2, 0)
        # comment permission
        self.widget['perm_comment'] = PermissionWidget('perm_comment')
        self.widget['perm_comment'].new_value.connect(self.new_value)
        group.layout().addWidget(QtWidgets.QLabel(
            translate('IpernityTab', 'post a comment')), 1, 1)
        group.layout().addWidget(self.widget['perm_comment'], 2, 1)
        # keywords & notes permission
        self.widget['perm_tag'] = PermissionWidget('perm_tag', default='4')
        self.widget['perm_tag'].new_value.connect(self.new_value)
        group.layout().addWidget(QtWidgets.QLabel(
            translate('IpernityTab', 'add keywords, notes')), 3, 0)
        group.layout().addWidget(self.widget['perm_tag'], 4, 0)
        # people permission
        self.widget['perm_tagme'] = PermissionWidget('perm_tagme', default='4')
        self.widget['perm_tagme'].new_value.connect(self.new_value)
        group.layout().addWidget(QtWidgets.QLabel(
            translate('IpernityTab', 'identify people')), 3, 1)
        group.layout().addWidget(self.widget['perm_tagme'], 4, 1)
        group.layout().setRowStretch(5, 1)
        column.addWidget(group, 0, 0, 1, 2)
        # left hand column group
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        group.setLayout(FormLayout(wrapped=True))
        # licence
        self.widget['license'] = LicenceWidget('license')
        self.widget['license'].new_value.connect(self.new_value)
        group.layout().addRow(
            translate('IpernityTab', 'Licence'), self.widget['license'])
        column.addWidget(group, 1, 0, 2, 1)
        # synchronise metadata
        self.buttons['sync'] = QtWidgets.QPushButton(
            translate('IpernityTab', 'Synchronise'))
        self.buttons['sync'].clicked.connect(self.sync_metadata)
        column.addWidget(self.buttons['sync'], 1, 1)
        # create new album
        new_album_button = QtWidgets.QPushButton(
            translate('IpernityTab', 'New album'))
        new_album_button.clicked.connect(self.new_album)
        column.addWidget(new_album_button, 2, 1)
        column.setRowStretch(0, 1)
        yield column

    @QtSlot(str, object)
    @catch_all
    def new_value(self, key, value):
        self.app.config_store.set('ipernity', key, value)

    def finalise_config(self):
        if not self.app.config_store.has_section('ipernity'):
            return
        for key in self.app.config_store.config.options('ipernity'):
            if key in self.widget:
                self.widget[key].set_value(
                    self.app.config_store.get('ipernity', key))

    def get_fixed_params(self):
        albums = []
        for child in self.widget['albums'].children():
            if child.isWidgetType() and child.isChecked():
                albums.append(child.property('album_id'))
        visibility = {
            '0': {'is_friend': '0', 'is_family': '0', 'is_public': '0'},
            '1': {'is_friend': '0', 'is_family': '1', 'is_public': '0'},
            '2': {'is_friend': '1', 'is_family': '0', 'is_public': '0'},
            '3': {'is_friend': '1', 'is_family': '1', 'is_public': '0'},
            '4': {'is_friend': '0', 'is_family': '0', 'is_public': '1'},
            }[self.widget['visibility'].get_value()]
        return {
            'visibility': visibility,
            'permissions': {
                'perm_comment': self.widget['perm_comment'].get_value(),
                'perm_tag'    : self.widget['perm_tag'].get_value(),
                'perm_tagme'  : self.widget['perm_tagme'].get_value(),
                },
            'licence': {
                'license': self.widget['license'].get_value(),
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
            widget.setToolTip('<p>' + album['description'] + '</p>')
        widget.setProperty('album_id', album['album_id'])
        if index >= 0:
            self.widget['albums'].layout().insertWidget(index, widget)
        else:
            self.widget['albums'].layout().addWidget(widget)
        return widget

    def accepted_file_type(self, file_type):
        if self.session.cached_data['is_pro'] == '0':
            # guest user can not upload video
            return file_type.split('/')[0] == 'image'
        # ipernity accepts most RAW formats!
        return file_type.split('/')[0] in ('image', 'video')

    def resize_file(self, image):
        src_path = image.path
        dest_path = self.get_temp_filename(image, ext='_small.jpg')
        # convert to JPEG
        if image.file_type != 'image/jpeg':
            src_path = self.convert_to_jpeg(image)
        # scale image
        for scale in (1000, 680, 470, 330, 220, 150,
                      100, 68, 47, 33, 22, 15, 10):
            if PIL:
                # use Pillow for good quality
                im = PIL.open(src_path)
                if scale != 1000:
                    w, h = im.size
                    im = im.resize((w * scale // 1000, h * scale // 1000),
                                   resample=PIL.BICUBIC)
            else:
                # use Qt, lower quality but available
                im = QtGui.QImage(image.path)
                if scale != 1000:
                    w, h = im.width(), im.height()
                    im = im.scaled(
                        w * scale // 1000, h * scale // 1000,
                        Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            # try different JPEG quality levels
            for quality in (95, 85, 75):
                im.save(dest_path, format='JPEG', quality=quality)
                self.copy_metadata(image, dest_path)
                size = os.stat(dest_path).st_size
                if size < self.max_size:
                    if src_path != image.path:
                        os.unlink(src_path)
                    return dest_path
        return None

    def get_conversion_function(self, image, params):
        if not params['function']:
            return None
        convert = super(
            TabWidget, self).get_conversion_function(image, params)
        if convert == 'omit':
            return convert
        if self.session.cached_data['is_pro'] == '0':
            # guest user file limit is 2.5 MB
            self.max_size = (2 ** 20) * 5 // 2
        else:
            self.max_size = 2 ** 30
        size = os.stat(image.path).st_size
        if size < self.max_size:
            return convert
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(translate('IpernityTab', 'Photini: too large'))
        dialog.setText('<h3>{}</h3>'.format(
            translate('IpernityTab', 'File too large.')))
        dialog.setInformativeText(translate(
            'IpernityTab',
            'File "{0}" has {1} bytes which exceeds Ipernity\'s limit of' +
            ' {2} bytes. Would you like to resize it?').format(
                os.path.basename(image.path), size, self.max_size))
        dialog.setIcon(QtWidgets.QMessageBox.Question)
        dialog.setStandardButtons(
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Ignore)
        if execute(dialog) == QtWidgets.QMessageBox.Ignore:
            return 'omit'
        return self.resize_file

    def get_variable_params(self, image, upload_prefs, replace_prefs, doc_id):
        params = {}
        # set upload function
        if upload_prefs['new_photo']:
            params['function'] = 'upload.file'
            doc_id = None
        else:
            params['function'] = None
        params['doc_id'] = doc_id
        # add metadata
        if upload_prefs['new_photo'] or replace_prefs['metadata']:
            # date_taken
            date_taken = image.metadata.date_taken
            if date_taken:
                params['dates'] = {
                    'created_at':
                    date_taken['datetime'].strftime('%Y-%m-%d %H:%M:%S')
                    }
            # location
            if image.metadata.latlong:
                params['location'] = {
                    'lat': '{:.6f}'.format(
                        float(image.metadata.latlong['lat'])),
                    'lng': '{:.6f}'.format(
                        float(image.metadata.latlong['lon'])),
                    }
            else:
                # clear any existing location
                params['location'] = {'lat': '-999', 'lng': '-999'}
        return params

    def replace_dialog(self, image):
        return super(TabWidget, self).replace_dialog(image, (
            ('metadata', translate('IpernityTab', 'Replace metadata')),
            ('visibility', translate('IpernityTab', 'Change who can see it')),
            ('permissions',
             translate('IpernityTab', 'Change who can comment or tag')),
            ('licence', translate('IpernityTab', 'Change the licence')),
            ('albums', translate('IpernityTab', 'Change album membership'))
            ), replace=False)

    def merge_metadata(self, doc_id, image):
        rsp = self.session.api_call('doc.get', doc_id=doc_id, extra='tags,geo')
        if not rsp:
            return
        photo = rsp['doc']
        data = {
            'title': photo['title'],
            'description': photo['description'],
            'keywords': [x['tag'] for x in photo['tags']['tag']
                         if x['type'] == 'keyword'],
            'date_taken': {
                'datetime': datetime.strptime(photo['dates']['created'],
                                              '%Y-%m-%d %H:%M:%S'),
                'precision': 6, 'tz_offset': None}
            }
        if 'geo' in photo:
            data['latlong'] = {'lat': photo['geo']['lat'],
                               'lon': photo['geo']['lng']}
        self.merge_metadata_items(image, data)

    @QtSlot()
    @catch_all
    def new_album(self):
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate(
            'IpernityTab', 'Create new Ipernity album'))
        dialog.setLayout(FormLayout())
        title = SingleLineEdit('title', spell_check=True)
        dialog.layout().addRow(translate('IpernityTab', 'Title'), title)
        description = MultiLineEdit('description', spell_check=True)
        dialog.layout().addRow(translate(
            'IpernityTab', 'Description'), description)
        perm_comment = PermissionWidget('comment')
        dialog.layout().addRow(Label(translate(
            'IpernityTab', 'Who can comment on album'), lines=2), perm_comment)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addRow(button_box)
        if execute(dialog) != QtWidgets.QDialog.Accepted:
            return
        params = {
            'title': title.toPlainText(),
            'description': description.toPlainText(),
            'perm_comment': perm_comment.get_value(),
            }
        if not params['title']:
            return
        rsp = self.session.api_call('album.create', post=True, **params)
        if not rsp:
            return
        widget = self.add_album(
            {'title': params['title'],
             'description': params['description'],
             'album_id': rsp['album']['album_id']}, index=0)
        widget.setChecked(True)
