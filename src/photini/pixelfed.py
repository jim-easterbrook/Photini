##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2023  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import logging
import os

from mastodon import Mastodon
from mastodon.errors import MastodonNetworkError
import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from photini.configstore import BaseConfigStore, key_store
from photini.pyqt import (
    catch_all, execute, FormLayout, QtCore, QtSlot, QtWidgets, width_for_text)
from photini.uploader import (
    PhotiniUploader, UploadAborted, UploaderSession, UploaderUser)
from photini.widgets import DropDownSelector, MultiLineEdit

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

# Pixelfed API: https://docs.pixelfed.org/technical-documentation/api/
# Mastodon.py docs: https://mastodonpy.readthedocs.io/


class Session(requests.Session):
    def __init__(self, *args, call_back=None, **kw):
        super(Session, self).__init__(*args, **kw)
        self._call_back = call_back

    def request(self, *args, data=None, headers=None, files=None, **kw):
        if files:
            # replace data and files with a mult-part encoder
            data.update(files)
            data = MultipartEncoder(fields=data)
            if self._call_back:
                data = MultipartEncoderMonitor(data, self._call_back)
            files = None
            headers['Content-Type'] = data.content_type
        return super(Session, self).request(
            *args, data=data, headers=headers, **kw)


class PixelfedSession(UploaderSession):
    name = 'pixelfed'

    def authorised(self):
        return True

    def open_connection(self):
        if self.api:
            return
        self.session = Session(call_back=self.progress)
        self.api = Mastodon(
            session=self.session, **self.client_data, **self.user_data)

    def close_connection(self):
        if self.api:
            self.session.close()
            self.api = None

    def get_user(self):
        name, picture = None, None
        account = self.api.account_verify_credentials()
        name = account['display_name']
        # get icon
        icon_url = account['avatar_static']
        rsp = requests.get(icon_url)
        if rsp.status_code == 200:
            picture = rsp.content
        else:
            logger.error('HTTP error %d (%s)', rsp.status_code, icon_url)
        return name, picture

    def get_albums(self):
        return []

    def progress(self, monitor):
        self.upload_progress.emit(
            {'value': monitor.bytes_read * 100 // monitor.len})

    def do_upload(self, fileobj, image_type, image, params):
        self.upload_progress.emit({'busy': False})
        try:
            media = self.api.media_post(
                fileobj, mime_type=image_type, **params['media'])
        except MastodonNetworkError as ex:
            if isinstance(ex.__context__, UploadAborted):
                raise ex.__context__
            raise
        self.upload_progress.emit({'busy': True})
        status = self.api.status_post(
            params['status'], media_ids=[media], **params['options'])
        return ''


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
                    return self.other_text.text()
                return button.text()
        return None


class PixelfedUser(UploaderUser):
    name       = 'pixelfed'
    scopes     = ['read', 'write']

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
            instance_data = {'api_base_url': 'https://' + instance}
            for option in key_store.config.options(section):
                instance_data[option] = key_store.get(section, option)
            self.instances.append(instance)
            self.instance_data[instance] = instance_data
        # locally registered instances
        self.local_config = BaseConfigStore('pixelfed')
        for instance in self.local_config.config.sections():
            if instance in self.instances:
                continue
            instance_data = {'api_base_url': 'https://' + instance}
            for option in self.local_config.config.options(instance):
                instance_data[option] = self.local_config.get(instance, option)
            self.instances.append(instance)
            self.instance_data[instance] = instance_data
        # last used instance
        self.instance = self.config_store.get('pixelfed', 'instance')
        if not self.instance:
            return False
        self.client_data = self.instance_data[self.instance]
        # get user access token
        access_token = self.get_password()
        if not access_token:
            return False
        self.user_data['access_token'] = access_token
        return True

    def service_name(self):
        if self.user_data:
            # logged in to a particular server
            return self.instance
        return translate('PixelfedTab', 'Pixelfed')

    def new_session(self, **kw):
        session = PixelfedSession(
            user_data=self.user_data, client_data=self.client_data, **kw)
        return session

    def authorise(self):
        dialog = ChooseInstance(
            parent=self.parentWidget(), default=self.instance,
            instances=self.instances)
        instance = dialog.execute()
        if not instance:
            return
        if not self.register_app(instance):
            return
        self.instance = instance
        self.config_store.set('pixelfed', 'instance', instance)
        super(PixelfedUser, self).authorise()

    def register_app(self, instance):
        if instance in self.instance_data:
            self.client_data = self.instance_data[instance]
            return True
        # create new registration
        instance_data = {'api_base_url': 'https://' + instance}
        api_base_url = 'https://' + instance
        try:
            client_id, client_secret = Mastodon.create_app(
                'Photini', scopes=self.scopes,
                redirect_uris='http://127.0.0.1',
                website='https://photini.readthedocs.io/',
                api_base_url=instance_data['api_base_url'])
        except MastodonNetworkError as ex:
            # user probably mistyped instance url
            logger.error(str(ex))
            return False
        # store result
        self.local_config.set(instance, 'client_id', client_id)
        self.local_config.set(instance, 'client_secret', client_secret)
        self.local_config.save()
        instance_data['client_id'] = client_id
        instance_data['client_secret'] = client_secret
        self.instances.append(instance)
        self.instance_data[instance] = instance_data
        self.client_data = instance_data
        return True

    def get_auth_url(self, redirect_uri):
        self.redirect_uri = redirect_uri
        with self.session(parent=self) as session:
            return session.api.auth_request_url(
                scopes=self.scopes, redirect_uris=redirect_uri)

    def get_access_token(self, result):
        with self.session(parent=self) as session:
            access_token = session.api.log_in(
                code=result['code'][0], redirect_uri=self.redirect_uri,
                scopes=self.scopes)
        self.user_data['access_token'] = access_token
        self.set_password(access_token)
        self.connection_changed.emit(True)


class TabWidget(PhotiniUploader):
    logger = logger

    def __init__(self, *arg, **kw):
        self.user_widget = PixelfedUser()
        super(TabWidget, self).__init__(*arg, **kw)

    @staticmethod
    def tab_name():
        return translate('PixelfedTab', '&Pixelfed upload')

    def config_columns(self):
        ## first column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        group.setLayout(FormLayout(wrapped=True))
        # visibility
        self.widget['visibility'] = DropDownSelector(
            'visibility', values = (
                (translate('PixelfedTab', 'Public'), 'public'),
                (translate('PixelfedTab', 'Followers only'), 'private'),
                (translate('PixelfedTab', 'Mentioned only'), 'direct'),
                (translate('PixelfedTab', 'Hidden from timeline'), 'unlisted')),
            default='public', with_multiple=False)
        group.layout().addRow(translate('PixelfedTab', 'Post visibility'),
                              self.widget['visibility'])
        # sensitive
        self.widget['sensitive'] = QtWidgets.QCheckBox(
            translate('PixelfedTab', 'Sensitive post'))
        group.layout().addRow(self.widget['sensitive'])
        column.addWidget(group, 0, 0)
        yield column
        ## last column is just empty space
        yield QtWidgets.QGridLayout()

    def accepted_image_type(self, file_type):
        return file_type in self.instance_config['media_attachments'][
            'supported_mime_types']

    def finalise_config(self, session):
        self.instance_config = session.api.instance()['configuration']
        self.max_size = {
            'image': self.instance_config['media_attachments'][
                'image_size_limit'],
            'image_pixels': self.instance_config['media_attachments'][
                'image_matrix_limit'],
            'video': self.instance_config['media_attachments'][
                'video_size_limit'],
            'video_pixels': self.instance_config['media_attachments'][
                'video_matrix_limit'],
            }

    def ask_resize_image(self, image, resizable=False):
        if image.file_type.split('/')[0] == 'video':
            return super(TabWidget, self).ask_resize_image(
                image, resizable=resizable)
        return self.convert_to_jpeg

    def get_upload_params(self, image):
        params = {'media': {}, 'options': {}}
        params['media']['file_name'] = os.path.basename(image.path)
        # 'description' is the ALT text for an image
        description = []
        if image.metadata.alt_text:
            description.append(image.metadata.alt_text.default_text())
        if image.metadata.alt_text_ext:
            description.append(image.metadata.alt_text_ext.default_text())
        if description:
            params['media']['description'] = '\n\n'.join(description)
        # 'status' is the text that accompanies the media
        description = []
        if image.metadata.title:
            description.append(image.metadata.title.default_text())
        if image.metadata.headline:
            description.append(image.metadata.headline)
        if image.metadata.description:
            description.append(image.metadata.description.default_text())
        if description:
            params['status'] = '\n\n'.join(description)
        else:
            params['status'] = params['media']['file_name']
        params['options']['visibility'] = self.widget['visibility'].get_value()
        params['options']['sensitive'] = self.widget['sensitive'].isChecked()
        return params
