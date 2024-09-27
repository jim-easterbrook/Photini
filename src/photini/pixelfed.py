##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2023-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import datetime
import itertools
import logging
import math
import os
import re

import requests
from requests_oauthlib import OAuth2Session
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from photini.configstore import BaseConfigStore, key_store
from photini.pyqt import *
from photini.uploader import (
    PhotiniUploader, UploadAborted, UploaderSession, UploaderUser)
from photini.widgets import (
    DropDownSelector, Label, MultiLineEdit, SingleLineEdit)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

# Pixelfed API: https://docs.pixelfed.org/technical-documentation/api/
# Endpoint list: https://github.com/pixelfed/pixelfed/blob/dev/routes/api.php


class PixelfedSession(UploaderSession):
    def open_connection(self):
        if self.api:
            return
        auto_refresh_kwargs = {
            'client_id': self.client_data['client_id'],
            'client_secret': self.client_data['client_secret'],
            }
        self.api = OAuth2Session(
            client_id=self.client_data['client_id'],
            token=self.user_data['token'],
            auto_refresh_url=self.client_data['api_base_url'] + '/oauth/token',
            auto_refresh_kwargs=auto_refresh_kwargs,
            token_updater=self.save_token)
        self.api.headers.update(self.headers)

    def save_token(self, token):
        self.user_data['token'] = token
        self.new_token.emit(token)

    @staticmethod
    def check_response(rsp, decode=True):
        UploaderSession.check_interrupt()
        try:
            rsp.raise_for_status()
            # some wrong api calls return the instance home page
            if rsp.headers['Content-Type'].startswith('text/html'):
                logger.error('Response is HTML')
                return None
            if decode:
                rsp = rsp.json()
        except UploadAborted:
            raise
        except Exception as ex:
            logger.error(str(ex))
            return None
        return rsp

    def api_call(self, endpoint, method='GET', **params):
        self.open_connection()
        url = self.client_data['api_base_url'] + endpoint
        rsp = self.check_response(self.api.request(method, url, **params))
        if rsp is None:
            self.close_connection()
        elif 'error' in rsp:
            logger.error('%s: %s', endpoint, rsp['error'])
            return None
        return rsp

    def upload_files(self, upload_list):
        media_ids = []
        licence = None
        upload_count = 0
        for image, convert, params in upload_list:
            upload_count += 1
            self.upload_progress.emit({
                'label': '{} ({}/{})'.format(os.path.basename(image.path),
                                             upload_count, len(upload_list)),
                'busy': True})
            default_licence = params['default_license']
            licence = licence or default_licence
            # set licence
            if params['license'] != licence:
                data = {'license': params['license']}
                rsp = self.api_call(
                    '/api/v1/accounts/update_credentials', 'PATCH', data=data)
                if rsp:
                    licence = params['license']
            # upload media
            fields = dict(params['media'])
            with self.open_file(image, convert) as (image_type, fileobj):
                fields['file'] = (params['file_name'], fileobj, image_type)
                data = MultipartEncoderMonitor(
                    MultipartEncoder(fields=fields), self.progress)
                self.upload_progress.emit({'busy': False})
                endpoint = '/api/v1/media'
                if (self.client_data['version']['mastodon'] >= (3, 1, 3) or
                    (self.client_data['version']['pixelfed'] and
                     self.client_data['version']['pixelfed'] >= (0, 11, 3))):
                    endpoint = '/api/v2/media'
                rsp = self.api_call(
                    endpoint, method='POST', data=data,
                    headers={'Content-Type': data.content_type})
            self.upload_progress.emit({'busy': True})
            if rsp is None:
                self.upload_progress.emit({
                    'error': (image, 'Image upload failed')})
                return
            media_ids.append((image, rsp['id']))
        # reset licence
        if licence != default_licence:
            data = {'license': default_licence}
            rsp = self.api_call(
                '/api/v1/accounts/update_credentials', 'PATCH', data=data)
        # upload status
        data = dict(params['status'])
        data['media_ids[]'] = [x[1] for x in media_ids]
        rsp = self.api_call(
            '/api/v1/statuses', method='POST', data=data)
        if rsp is None:
            self.upload_progress.emit({'error': (image, 'Post status failed')})
            return
        # store photo ids in image keywords, in main thread
        for image, media_id in media_ids:
            self.upload_progress.emit({
                'keyword': (image, '{}:id={}'.format(
                    self.client_data['name'], media_id))})


class ChooseInstance(QtWidgets.QDialog):
    def __init__(self, default=None, instances=[], **kw):
        super(ChooseInstance, self).__init__(**kw)
        self.setWindowTitle(translate(
            'PixelfedTab', 'Photini: choose instance'))
        self.setLayout(QtWidgets.QVBoxLayout())
        # text
        self.layout().addWidget(QtWidgets.QLabel(
            '<h3>{}</h3>'.format(translate(
            'PixelfedTab', 'Choose an instance'))))
        self.layout().addWidget(QtWidgets.QLabel(translate(
            'PixelfedTab', 'Which Pixelfed instance hosts your account?')))
        # list of instances
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.layout().addWidget(scroll_area)
        panel = QtWidgets.QWidget()
        panel.setLayout(QtWidgets.QGridLayout())
        self.buttons = []
        row = 0
        for instance in instances:
            button = QtWidgets.QRadioButton(instance)
            button.setChecked(instance == default)
            self.buttons.append(button)
            panel.layout().addWidget(button, row, 0, 1, 2)
            row += 1
        # any other instance
        button = QtWidgets.QRadioButton(translate('PixelfedTab', 'Other'))
        self.buttons.append(button)
        button.setEnabled(False)
        panel.layout().addWidget(button, row, 0)
        self.other_text = QtWidgets.QLineEdit()
        self.other_text.textChanged.connect(self.text_changed)
        panel.layout().addWidget(self.other_text, row, 1)
        # add panel to scroll area now its size is known
        scroll_area.setWidget(panel)
        # ok & cancel buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = button_box.addButton(
            QtWidgets.QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout().addWidget(button_box)
        for button in self.buttons:
            button.toggled.connect(self.button_toggled)
        self.button_toggled()

    @QtSlot(str)
    @catch_all
    def text_changed(self, value):
        self.buttons[-1].setChecked(bool(value))
        self.buttons[-1].setEnabled(bool(value))

    @QtSlot(bool)
    @catch_all
    def button_toggled(self, value=None):
        for button in self.buttons:
            if button.isChecked():
                self.ok_button.setEnabled(True)
                return
        self.ok_button.setEnabled(False)

    def execute(self):
        if execute(self) != QtWidgets.QDialog.DialogCode.Accepted:
            return None
        for button in self.buttons:
            if button.isChecked():
                if button == self.buttons[-1]:
                    return self.other_text.text().strip().strip('/')
                return button.text()
        return None


class PixelfedUser(UploaderUser):
    new_instance_config = QtSignal(dict)
    logger = logger
    config_section = 'pixelfed'
    scopes = ['read', 'write']

    def on_connect(self, widgets):
        with self.session(parent=self) as session:
            yield 'connected', session.api.authorized
            # get user info
            account = session.api_call('/api/v1/accounts/verify_credentials')
            if not account:
                self.log_out()
                yield 'connected', False
            self.user_data['id'] = account['id']
            self.user_data['lang'] = account['source']['language']
            # get icon
            icon_url = account['avatar_static']
            rsp = session.check_response(
                session.api.get(icon_url), decode=False)
            yield 'user', (account['display_name'], rsp and rsp.content)
            # get instance info
            self.client_data['version'] = {'mastodon': None, 'pixelfed': None}
            self.instance_config = session.api_call('/api/v2/instance')
            if not self.instance_config:
                self.instance_config = session.api_call('/api/v1/instance')
            if not self.instance_config:
                yield 'connected', False
            self.new_instance_config.emit(self.instance_config)
            widgets['status'].set_length(self.instance_config[
                'configuration']['statuses']['max_characters'])
            version = self.instance_config['version']
            logger.info('server version "%s"', version)
            match = re.match(r'(\d+)\.(\d+)\.(\d+)', version)
            if match:
                self.client_data['version']['mastodon'] = tuple(
                    int(x) for x in match.groups())
            match = re.search(r'Pixelfed\s+(\d+)\.(\d+)\.(\d+)', version)
            if match:
                self.client_data['version']['pixelfed'] = tuple(
                    int(x) for x in match.groups())
            self.unavailable['albums'] = not (
                self.client_data['version']['pixelfed']
                and self.client_data['version']['pixelfed'] >= (0, 11, 4))
            self.unavailable['comments_disabled'] = self.unavailable['albums']
            self.unavailable['license'] = not (
                self.client_data['version']['pixelfed']
                and self.client_data['version']['pixelfed'] >= (0, 11, 1))
            self.unavailable['new_album'] = not (
                self.client_data['version']['pixelfed']
                and self.client_data['version']['pixelfed'] >= (99, 0, 0))
            self.unavailable['sync_remote'] = not (
                self.client_data['version']['pixelfed']
                and self.client_data['version']['pixelfed'] >= (0, 10, 6))
            media = self.instance_config['configuration']['media_attachments']
            self.max_size = {
                'image': {'bytes': media['image_size_limit'],
                          'pixels': media['image_matrix_limit']},
                'video': {'bytes': media['video_size_limit'],
                          'pixels': media['video_matrix_limit']},
                }
            yield None, None
            # get user preferences
            prefs = session.api_call('/api/v1/preferences')
            if prefs is None:
                yield 'connected', False
            if prefs['posting:default:language']:
                self.user_data['lang'] = prefs['posting:default:language']
            widgets['sensitive'].setChecked(
                prefs['posting:default:sensitive'])
            widgets['visibility'].set_value(
                prefs['posting:default:visibility'])
            if self.client_data['version']['pixelfed']:
                self.compose_settings = session.api_call(
                    '/api/v1.1/compose/settings')
                if self.compose_settings is None:
                    yield 'connected', False
                if 'default_license' in self.compose_settings:
                    widgets['license'].set_value(
                        int(self.compose_settings['default_license']))
                if 'default_scope' in self.compose_settings:
                    widgets['visibility'].set_value(
                        self.compose_settings['default_scope'])
            else:
                self.compose_settings = {
                    'max_altext_length': 5000,
                    'default_license': widgets['license'].get_value(),
                    'media_descriptions': True,
                    }
            yield None, None
            # get collections
            if self.unavailable['albums']:
                return
            for collection in session.api_call(
                    '/api/v1.1/collections/accounts/{}'.format(
                        self.user_data['id'])) or []:
                if collection:
                    yield 'album', {
                        'title': collection['title'] or 'Untitled',
                        'description': collection['description'],
                        'id': collection['id'],
                        # default max collection length is 100
                        'writeable': collection['post_count'] < 100,
                        }

    def load_user_data(self):
        self.config_store = QtWidgets.QApplication.instance().config_store
        # get list of known instances
        self.instances = []
        self.instance_data = {}
        # registered instances
        for section in key_store.config.sections():
            name, sep, instance = section.partition(' ')
            if name != 'pixelfed':
                continue
            instance_data = {'name': instance,
                             'api_base_url': 'https://' + instance}
            for option in key_store.config.options(section):
                instance_data[option] = key_store.get(section, option)
            self.instances.append(instance)
            self.instance_data[instance] = instance_data
        # locally registered instances
        self.local_config = BaseConfigStore('pixelfed')
        for instance in self.local_config.config.sections():
            if instance in self.instances:
                continue
            instance_data = {'name': instance,
                             'api_base_url': 'https://' + instance}
            for option in self.local_config.config.options(instance):
                instance_data[option] = self.local_config.get(instance, option)
            self.instances.append(instance)
            self.instance_data[instance] = instance_data
        # last used instance
        instance = self.config_store.get('pixelfed', 'instance')
        if not instance:
            return False
        self.client_data = self.instance_data[instance]
        # get user access token
        token = self.get_password()
        if not token:
            return False
        self.user_data['token'] = eval(token)
        return True

    def service_name(self):
        if 'token' in self.user_data:
            # logged in to a particular server
            return self.client_data['name']
        return translate('PixelfedTab', 'Pixelfed')

    def new_session(self, **kw):
        session = PixelfedSession(
            user_data=self.user_data, client_data=self.client_data, **kw)
        session.new_token.connect(self.new_token)
        return session

    def authorise(self):
        dialog = ChooseInstance(
            parent=self.parentWidget(), default=self.client_data['name'],
            instances=self.instances)
        instance = dialog.execute()
        if not instance:
            return
        if not self.register_app(instance):
            return
        self.config_store.set('pixelfed', 'instance', instance)
        super(PixelfedUser, self).authorise()

    def register_app(self, instance):
        if instance in self.instance_data:
            self.client_data = self.instance_data[instance]
            return True
        # create new registration
        api_base_url = 'https://' + instance
        data = {
            'client_name': 'Photini',
            'scopes': ' '.join(self.scopes),
            'redirect_uris': 'http://127.0.0.1',
            'website': 'https://photini.readthedocs.io/',
            }
        rsp = PixelfedSession.check_response(requests.post(
            api_base_url + '/api/v1/apps', data=data, timeout=20))
        if not rsp:
            return False
        client_id = rsp['client_id']
        client_secret = rsp['client_secret']
        # store result
        self.local_config.set(instance, 'client_id', client_id)
        self.local_config.set(instance, 'client_secret', client_secret)
        self.local_config.save()
        self.client_data = {
            'name': instance,
            'api_base_url': api_base_url,
            'client_id': client_id,
            'client_secret': client_secret,
            }
        self.instances.append(instance)
        self.instance_data[instance] = self.client_data
        return True

    def auth_exchange(self, redirect_uri):
        with OAuth2Session(self.client_data['client_id'],
                           redirect_uri=redirect_uri,
                           scope=self.scopes) as session:
            authorization_url, state = session.authorization_url(
                self.client_data['api_base_url'] + '/oauth/authorize')
            result = yield authorization_url
            # often get more scopes than asked for, which upsets
            # requests_oauthlib
            os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
            token = session.fetch_token(
                self.client_data['api_base_url'] + '/oauth/token',
                client_secret=self.client_data['client_secret'],
                code=result['code'][0])
        if 'access_token' not in token:
            logger.info('No access token received')
            return
        self.new_token(token)
        self.connection_changed.emit(True)

    def unauthorise(self):
        if (self.client_data['version']['pixelfed']
                and self.client_data['version']['pixelfed'] < (0, 12)):
            return
        data = {
            'client_id': self.client_data['client_id'],
            'client_secret': self.client_data['client_secret'],
            'token': self.user_data['token']['access_token']
            }
        PixelfedSession.check_response(requests.post(
            self.client_data['api_base_url'] + '/oauth/revoke', data=data))

    @QtSlot(dict)
    @catch_all
    def new_token(self, token):
        self.user_data['token'] = token
        self.set_password(repr(token))


class ThumbList(QtWidgets.QWidget):
    def __init__(self, *arg, scroll_area=None, **kw):
        super(ThumbList, self).__init__(*arg, **kw)
        self.scroll_area = scroll_area
        self.app = QtWidgets.QApplication.instance()
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().addStretch(1)
        self.image_selection = []
        self.max_media_attachments = 4

    @QtSlot(dict)
    @catch_all
    def new_instance_config(self, config):
        self.max_media_attachments = config[
            'configuration']['statuses']['max_media_attachments']
        self.new_selection(self.app.image_list.get_selected_images())

    def get_selected_images(self):
        return [x[0] for x in self.image_selection]

    def new_selection(self, selection):
        width = self.layout().contentsRect().width()
        n = len(self.image_selection)
        while n:
            n -= 1
            if self.image_selection[n][0] not in selection:
                image, widget = self.image_selection.pop(n)
                self.layout().removeWidget(widget)
                widget.setParent(None)
        selection = selection[:self.max_media_attachments]
        added = False
        for image in selection:
            if image not in self.get_selected_images():
                widget = QtWidgets.QLabel()
                widget.setWordWrap(True)
                widget.setFrameStyle(widget.Shape.Box)
                widget.setStyleSheet('QLabel {background-color: black;}')
                widget.setToolTip(image.name)
                widget.setAlignment(Qt.AlignmentFlag.AlignHCenter |
                                    Qt.AlignmentFlag.AlignVCenter)
                widget.setFixedSize(width, width)
                image.load_thumbnail(label=widget)
                self.layout().insertWidget(self.layout().count() - 1, widget)
                self.image_selection.append((image, widget))
                added = True
        if added and self.scroll_area:
            QtCore.QTimer.singleShot(1, self.scroll_to_last_widget)

    @QtSlot()
    @catch_all
    def scroll_to_last_widget(self):
        scroll_bar = self.scroll_area.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())


class ScrollArea(QtWidgets.QScrollArea):
    @catch_all
    def resizeEvent(self, event):
        super(ScrollArea, self).resizeEvent(event)
        self.widget().setFixedWidth(self.viewport().contentsRect().width())


class TabWidget(PhotiniUploader):
    logger = logger

    def __init__(self, *arg, **kw):
        self.user_widget = PixelfedUser()
        super(TabWidget, self).__init__(*arg, **kw)

    @staticmethod
    def tab_name():
        return translate('PixelfedTab', 'Pixelfed upload',
                         'Full name of tab shown as a tooltip')

    @staticmethod
    def tab_short_name():
        return translate('PixelfedTab', '&Pixelfed',
                         'Shortest possible name used as tab label')

    def config_columns(self):
        self.replace_prefs = {'description': True}
        self.upload_prefs = {}
        ## first column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        scroll_area = ScrollArea()
        scroll_area.setMinimumWidth(width_for_text(scroll_area, 'x' * 14))
        self.widget['thumb_list'] = ThumbList(scroll_area=scroll_area)
        self.user_widget.new_instance_config.connect(
            self.widget['thumb_list'].new_instance_config)
        scroll_area.setWidget(self.widget['thumb_list'])
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        column.addWidget(scroll_area, 0, 0)
        yield column, 0
        ## second column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setLayout(FormLayout(wrapped=True))
        sub_grid = QtWidgets.QGridLayout()
        sub_grid.setContentsMargins(0, 0, 0, 0)
        sub_grid.addWidget(
            Label(translate('PixelfedTab', 'Caption'), layout=group.layout()),
            0, 0)
        self.widget['auto_status'] = QtWidgets.QPushButton(
            translate('PixelfedTab', 'Generate'))
        self.widget['auto_status'].clicked.connect(self.auto_status)
        sub_grid.addWidget(self.widget['auto_status'], 0, 2)
        self.widget['status'] = MultiLineEdit(
            'status', spell_check=True,
            length_check=1000, length_always=True, length_bytes=False)
        policy = self.widget['status'].sizePolicy()
        policy.setVerticalStretch(1)
        self.widget['status'].setSizePolicy(policy)
        sub_grid.addWidget(self.widget['status'], 1, 0, 1, 3)
        sub_grid.setColumnStretch(1, 1)
        group.layout().addRow(sub_grid)
        self.widget['spoiler_text'] = SingleLineEdit(
            'spoiler_text', spell_check=True,
            length_check=140, length_always=True, length_bytes=False)
        self.widget['spoiler_text'].textChanged.connect(self.new_spoiler_text)
        group.layout().addRow(
            translate('PixelfedTab', 'Spoiler'), self.widget['spoiler_text'])
        column.addWidget(group, 0, 0)
        yield column, 1
        ## third column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        group.setLayout(FormLayout(wrapped=True))
        # visibility
        self.widget['visibility'] = DropDownSelector(
            'visibility', values = (
                (translate('PixelfedTab', 'Public'), 'public'),
                (translate('PixelfedTab', 'Unlisted'), 'unlisted'),
                (translate('PixelfedTab', 'Followers only'), 'private')),
            default='public', with_multiple=False)
        group.layout().addRow(translate('PixelfedTab', 'Post visibility'),
                              self.widget['visibility'])
        # sensitive
        self.widget['sensitive'] = QtWidgets.QCheckBox(
            translate('PixelfedTab', 'Sensitive post'))
        group.layout().addRow(self.widget['sensitive'])
        # comments disabled
        self.widget['comments_disabled'] = QtWidgets.QCheckBox(
            translate('PixelfedTab', 'Disable comments'))
        group.layout().addRow(self.widget['comments_disabled'])
        # licence
        self.widget['license'] = DropDownSelector(
            'license', values=(
                (translate('PixelfedTab', 'All Rights Reserved'), 1),
                (translate('PixelfedTab', 'Public Domain Work'), 5),
                (translate('PixelfedTab',
                           'Public Domain Dedication (CC0)'), 6),
                (translate('PixelfedTab', 'Attribution'), 11),
                (translate('PixelfedTab', 'Attribution-ShareAlike'), 12),
                (translate('PixelfedTab', 'Attribution-NonCommercial'), 13),
                (translate('PixelfedTab',
                           'Attribution-NonCommercial-ShareAlike'), 14),
                (translate('PixelfedTab', 'Attribution-NoDerivs'), 15),
                (translate('PixelfedTab',
                           'Attribution-NonCommercial-NoDerivs'), 16),
                ),
            default=1, with_multiple=False)
        group.layout().addRow(
            translate('PixelfedTab', 'Licence'), self.widget['license'])
        column.addWidget(group, 0, 0)
        # create new collection
        self.widget['new_album'] = QtWidgets.QPushButton(
            translate('PixelfedTab', 'New collection'))
        self.widget['new_album'].clicked.connect(self.new_album)
        column.addWidget(self.widget['new_album'], 1, 0)
        # update alt text
        self.widget['sync_remote'] = QtWidgets.QPushButton(
            translate('PixelfedTab', 'Update remote'))
        self.widget['sync_remote'].clicked.connect(self.sync_remote)
        column.addWidget(self.widget['sync_remote'], 2, 0)
        yield column, 0
        ## last column is list of albums
        yield self.album_list(
            label=translate('PixelfedTab', 'Add to collections'),
            max_selected=3), 0

    @QtSlot()
    @catch_all
    def new_spoiler_text(self):
        if self.widget['spoiler_text'].get_value():
            self.widget['sensitive'].setChecked(True)
            self.widget['sensitive'].setEnabled(False)
        else:
            self.widget['sensitive'].setEnabled(True)

    def accepted_image_type(self, file_type):
        return file_type in self.user_widget.instance_config[
            'configuration']['media_attachments']['supported_mime_types']

    def process_image(self, image):
        image = self.read_image(image)
        image = self.data_to_image(image)
        # reduce image size
        w, h = image['width'], image['height']
        shrink = math.sqrt(float(w * h) /
                           float(self.user_widget.max_size['image']['pixels']))
        if shrink > 1.0:
            w = int(float(w) / shrink)
            h = int(float(h) / shrink)
            logger.info('Resizing %s to %dx%d pixels', image['name'], w, h)
            image = self.resize_image(image, w, h)
        # convert to jpeg and reduce size if necessary
        image = self.image_to_data(
            image, mime_type='image/jpeg',
            max_size=self.user_widget.max_size['image']['bytes'])
        return image['data'], image['mime_type']

    def get_selected_images(self):
        return self.widget['thumb_list'].get_selected_images()

    @QtSlot()
    @catch_all
    def sync_remote(self):
        image_list = {}
        for image in self.app.image_list.get_selected_images():
            if not image.metadata.keywords:
                continue
            for keyword, (ns, predicate,
                          value) in image.metadata.keywords.machine_tags():
                if (ns == self.user_widget.client_data['name']
                        and predicate != 'id'):
                    image_list[value] = image
        if not image_list:
            return
        with Busy():
            with self.user_widget.session(parent=self) as session:
                for media_id, image in image_list.items():
                    data = {'description': self.alt_text(image)}
                    session.api_call(
                        '/api/v1/media/{}'.format(media_id), 'PUT', data=data)

    def alt_text(self, image):
        description = []
        lang = self.user_widget.user_data['lang']
        max_len = int(self.user_widget.compose_settings['max_altext_length'])
        if image.metadata.alt_text:
            text = image.metadata.alt_text.best_match(lang)
            description.append(text)
            max_len -= len(text) + 2
        if image.metadata.alt_text_ext:
            text = image.metadata.alt_text_ext.best_match(lang)
            if len(text) <= max_len:
                description.append(text)
        if description:
            return '\n\n'.join(description)
        return ''

    def get_upload_params(self, image, state):
        if 'ask_alt_text' not in state:
            state['ask_alt_text'] = self.user_widget.compose_settings[
                                                        'media_descriptions']
        params = {'media': {}, 'status': {}}
        params['file_name'] = os.path.basename(image.path)
        # 'description' is the ALT text for an image
        params['media']['description'] = self.alt_text(image)
        if state['ask_alt_text'] and not params['media']['description']:
            dialog = QtWidgets.QMessageBox(parent=self)
            dialog.setWindowTitle(
                translate('PixelfedTab', 'Photini: alt text'))
            dialog.setText('<h3>{}</h3>'.format(
                translate('PixelfedTab', 'Missing alt text.')))
            dialog.setInformativeText(translate(
                'PixelfedTab', 'File "{file_name}" does not have any'
                ' "alt text" for accessibility.'
                ' Would you like to upload it anyway?').format(
                    file_name=os.path.basename(image.path)))
            dialog.setStandardButtons(dialog.StandardButton.Yes |
                                      dialog.StandardButton.YesToAll |
                                      dialog.StandardButton.Abort)
            dialog.setIcon(dialog.Icon.Warning)
            result = execute(dialog)
            if result == dialog.StandardButton.YesToAll:
                state['ask_alt_text'] = False
            elif result == dialog.StandardButton.Abort:
                return 'abort'
        focus = image.metadata.image_region.get_focus(image)
        if focus:
            params['media']['focus'] = '{:f},{:f}'.format(*focus)
        params['license'] = self.widget['license'].get_value()
        params['default_license'] = int(
            self.user_widget.compose_settings['default_license'])
        # 'status' is the text that accompanies the media
        for key in ('status', 'spoiler_text', 'visibility'):
            params['status'][key] = self.widget[key].get_value()
        params['status']['status'] = params[
            'status']['status'] or params['file_name']
        params['status']['sensitive'] = ('0', '1')[
            self.widget['sensitive'].isChecked()]
        if not self.user_widget.unavailable['comments_disabled']:
            params['status']['comments_disabled'] = ('0', '1')[
                self.widget['comments_disabled'].isChecked()]
        if not self.user_widget.unavailable['albums']:
            # collections to add post to
            album_ids = self.widget['albums'].get_checked_ids()
            if album_ids:
                params['status']['collection_ids[]'] = album_ids
        return params

    def enable_upload_button(self, selection=None):
        selection = selection or self.app.image_list.get_selected_images()
        super(TabWidget, self).enable_upload_button(selection=selection)
        if (self.buttons['upload'].isEnabled()
                and len(selection) > self.widget[
                    'thumb_list'].max_media_attachments
                and not self.buttons['upload'].is_checked()):
            self.buttons['upload'].setEnabled(False)
        self.widget['thumb_list'].new_selection(selection)
        enabled = self.widget['status'].isEnabled()
        self.widget['sync_remote'].setEnabled(enabled and bool(selection))
        self.widget['auto_status'].setEnabled(
            enabled and (len(selection) > 0 and len(selection) <=
                         self.widget['thumb_list'].max_media_attachments))

    @QtSlot()
    @catch_all
    def auto_status(self):
        result = {
            'title': [], 'headline': [], 'description': [], 'keywords': [],
            'date_taken': []}
        for image in self.get_selected_images():
            for key in result:
                result[key].append(getattr(image.metadata, key))
        lang = self.user_widget.user_data['lang']
        result['title'] = [x.best_match(lang) for x in result['title'] if x]
        result['headline'] = [str(x) for x in result['headline'] if x]
        result['description'] = [
            x.best_match(lang) for x in result['description'] if x]
        result['keywords'] = [x.human_tags() for x in result['keywords'] if x]
        result['keywords'] = list(itertools.chain(*result['keywords']))
        result['date_taken'] = [
            x.to_ISO_8601(precision=3) for x in result['date_taken'] if x]
        strings = []
        for key in ('title', 'headline', 'description'):
            if not result[key]:
                continue
            string = result[key][0]
            for text in result[key][1:]:
                if string in text:
                    string = text
                elif text not in string:
                    string += '\n' + text
            strings.append(string)
        if result['keywords']:
            # remove punctuation
            keywords = [re.sub(r'[^\w\s]', '', x, re.UNICODE)
                        for x in result['keywords']]
            # convert to #CamelCase
            keywords = ['#' + ''.join([(y, y.capitalize())[y[0].islower()]
                                       for y in x.split()]) for x in keywords]
            strings.append(' '.join(set(keywords)))
        if strings and result['date_taken']:
            start = min(result['date_taken'])
            stop = max(result['date_taken'])
            if stop != start:
                strings[0] = '{}..{}: {}'.format(start, stop, strings[0])
            elif start != datetime.date.today().isoformat():
                strings[0] = '{}: {}'.format(start, strings[0])
        self.widget['status'].set_value('\n\n'.join(strings))

    @QtSlot()
    @catch_all
    def new_album(self):
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate('PixelfedTab', 'Create new collection'))
        dialog.setLayout(FormLayout())
        title = SingleLineEdit(
            'title', spell_check=True,
            length_check=50, length_always=True, length_bytes=False)
        dialog.layout().addRow(translate('PixelfedTab', 'Title'), title)
        description = MultiLineEdit(
            'description', spell_check=True,
            length_check=500, length_always=True, length_bytes=False)
        dialog.layout().addRow(
            translate('PixelfedTab', 'Description'), description)
        visibility = DropDownSelector(
            'visibility', values = (
                (translate('PixelfedTab', 'Public'), 'public'),
                (translate('PixelfedTab', 'Followers only'), 'private'),
                (translate('PixelfedTab', 'Draft'), 'draft')),
            default='public', with_multiple=False)
        dialog.layout().addRow(
            translate('PixelfedTab', 'Collection visibility'), visibility)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addRow(button_box)
        if execute(dialog) != QtWidgets.QDialog.DialogCode.Accepted:
            return
        data = {
            'title': title.toPlainText(),
            'description': description.toPlainText(),
            'visibility': visibility.get_value(),
            }
        if not data['title']:
            return
        # currently no known endpoint to create a collection
        return
        with self.user_widget.session(parent=self) as session:
            # this endpoint doesn't exist
            album = session.api_call('/api/v1.1/collections/create')
            # this endpoint updates an existing album
            album = session.api_call(
                '/api/v1.1/collections/update/{}'.format(
                    album['id']), data=data)
        widget = self.widget['albums'].add_album(
            {'title': album['title'], 'description': album['description'],
             'id': album['id'], 'writeable': True},
            index=0)
        widget.setChecked(True)
