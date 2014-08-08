##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-14  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from datetime import datetime
import logging
import os
import sys
import time
import webbrowser

import atom
import gdata.auth
import gdata.photos
import gdata.photos.service
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

from .descriptive import MultiLineEdit
from .utils import Busy

EPOCH = datetime.utcfromtimestamp(0)

logger = logging.getLogger(__name__)

class LoggingPhotosService(object):
    def __init__(self):
        self._service = gdata.photos.service.PhotosService(email='default')

    def __getattr__(self, name):
        self._next_call = getattr(self._service, name)
        return self._call

    def _call(self, *arg, **kw):
        try:
            return (self._next_call)(*arg, **kw)
        except Exception as ex:
            logger.exception(ex)

class MediaSourceWithCallback(object):
    def __init__(self, path, content_type, callback):
        self.file = open(path, 'rb')
        self.content_type = content_type
        self.content_length = os.path.getsize(path)
        self.file_handle = self
        self.callback = callback

    def read(self, size):
        if self.callback:
            self.callback(self.file.tell() * 100 / self.content_length)
        return self.file.read(size)

class UploadThread(QtCore.QThread):
    def __init__(self, pws, upload_list, feed_uri):
        QtCore.QThread.__init__(self)
        self.pws = pws
        self.upload_list = upload_list
        self.feed_uri = feed_uri

    finished = QtCore.pyqtSignal()
    def run(self):
        self.file_count = 0
        for params in self.upload_list:
            photo = gdata.photos.PhotoEntry()
            if not photo.title:
                photo.title = atom.Title()
            photo.title.text = os.path.basename(params['path'])
            if params['summary']:
                if not photo.summary:
                    photo.summary = atom.Summary()
                photo.summary.text = params['summary']
            if params['keywords']:
                if not photo.media:
                    photo.media = gdata.media.Group()
                if not photo.media.keywords:
                    photo.media.keywords = gdata.media.Keywords()
                photo.media.keywords.text = params['keywords']
            if params['latlong']:
                if not photo.geo:
                    photo.geo = gdata.geo.Where()
                if not photo.geo.Point:
                    photo.geo.Point = gdata.geo.Point()
                photo.geo.Point.pos = gdata.geo.Pos(text=params['latlong'])
            mediasource = MediaSourceWithCallback(
                params['path'], 'image/jpeg', self.callback)
            try:
                photo = self.pws.Post(
                    photo, uri=self.feed_uri, media_source=mediasource,
                    converter=gdata.photos.PhotoEntryFromString)
            except gdata.service.RequestError, e:
                raise gdata.photos.service.GooglePhotosException(e.args[0])
            self.file_count += 1
        self.finished.emit()

    progress_report = QtCore.pyqtSignal(float, float)
    def callback(self, progress):
        total_progress = (
            (self.file_count * 100) + progress) / len(self.upload_list)
        self.progress_report.emit(progress, total_progress)

def decode_text(obj):
    if not obj or obj.text is None:
        return ''
    return unicode(obj.text, 'utf-8')

class PicasaUploader(QtGui.QWidget):
    def __init__(self, config_store, image_list, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.image_list = image_list
        self.setLayout(QtGui.QGridLayout())
        self.pws = None
        self.widgets = {}
        self.current_album = None
        self.uploader = None
        ### album group
        self.album_group = QtGui.QGroupBox('Album')
        self.album_group.setLayout(QtGui.QHBoxLayout())
        self.layout().addWidget(self.album_group, 0, 0, 3, 3)
        ## album details, left hand side
        album_form_left = QtGui.QFormLayout()
        album_form_left.setFieldGrowthPolicy(
            QtGui.QFormLayout.AllNonFixedFieldsGrow)
        self.album_group.layout().addLayout(album_form_left)
        # album title / selector
        self.albums = QtGui.QComboBox()
        self.albums.setEditable(True)
        self.albums.setInsertPolicy(QtGui.QComboBox.NoInsert)
        self.albums.currentIndexChanged.connect(self.changed_album)
        self.albums.lineEdit().editingFinished.connect(self.new_title)
        album_form_left.addRow('Title', self.albums)
        # album description
        self.widgets['description'] = MultiLineEdit()
        self.widgets['description'].editingFinished.connect(self.new_description)
        album_form_left.addRow('Description', self.widgets['description'])
        # album location
        self.widgets['location'] = QtGui.QLineEdit()
        self.widgets['location'].editingFinished.connect(self.new_location)
        album_form_left.addRow('Place taken', self.widgets['location'])
        # album visibility
        self.widgets['access'] = QtGui.QComboBox()
        self.widgets['access'].addItem('Public on the web', 'public')
        self.widgets['access'].addItem('Limited, anyone with the link', 'private')
        self.widgets['access'].addItem('Only you', 'protected')
        self.widgets['access'].currentIndexChanged.connect(self.new_access)
        album_form_left.addRow('Visibility', self.widgets['access'])
        ## album buttons
        buttons = QtGui.QHBoxLayout()
        album_form_left.addRow('', buttons)
        # new album
        new_album_button = QtGui.QPushButton('New album')
        new_album_button.clicked.connect(self.new_album)
        buttons.addWidget(new_album_button)
        # delete album
        delete_album_button = QtGui.QPushButton('Delete album')
        delete_album_button.clicked.connect(self.delete_album)
        buttons.addWidget(delete_album_button)
        # other init
        self.clear_changes()
        ## album details, right hand side
        album_form_right = QtGui.QFormLayout()
        album_form_right.setFieldGrowthPolicy(
            QtGui.QFormLayout.AllNonFixedFieldsGrow)
        self.album_group.layout().addLayout(album_form_right)
        # album date
        self.widgets['timestamp'] = QtGui.QDateEdit()
        self.widgets['timestamp'].setCalendarPopup(True)
        self.widgets['timestamp'].editingFinished.connect(self.new_timestamp)
        album_form_right.addRow('Date', self.widgets['timestamp'])
        # album thumbnail
        self.album_thumb = QtGui.QLabel()
        album_form_right.addRow(self.album_thumb)
        ### upload button
        self.upload_button = QtGui.QPushButton('Upload\nnow')
        self.upload_button.setEnabled(False)
        self.upload_button.clicked.connect(self.upload)
        self.layout().addWidget(self.upload_button, 2, 3)
        ### progress bar
        self.layout().addWidget(QtGui.QLabel('Progress'), 3, 0)
        self.total_progress = QtGui.QProgressBar()
        self.layout().addWidget(self.total_progress, 3, 1, 1, 3)
        self.setEnabled(False)
        # adjust spacing
        self.layout().setColumnStretch(2, 1)
        self.layout().setRowStretch(1, 1)
        # timer to store album data after it's edited
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.save_changes)

    def clear_changes(self):
        self.changed_title = None
        self.changed_description = None
        self.changed_location = None
        self.changed_access = None
        self.changed_timestamp = None

    @QtCore.pyqtSlot()
    def new_title(self):
        value = unicode(self.albums.lineEdit().text())
        self.albums.setItemText(self.albums.currentIndex(), value)
        if value != decode_text(self.current_album.title):
            self.changed_title = value
        else:
            self.changed_title = None
        self.timer.start()

    @QtCore.pyqtSlot()
    def new_description(self):
        value = unicode(self.widgets['description'].text())
        if value != decode_text(self.current_album.summary):
            self.changed_description = value
        else:
            self.changed_description = None
        self.timer.start()

    @QtCore.pyqtSlot()
    def new_timestamp(self):
        value = '%d' % (
            (self.widgets['timestamp'].dateTime().toPyDateTime() - EPOCH
             ).total_seconds() * 1000)
        if value != decode_text(self.current_album.timestamp):
            self.changed_timestamp = value
        else:
            self.changed_timestamp = None
        self.timer.start()

    @QtCore.pyqtSlot()
    def new_location(self):
        value = unicode(self.widgets['location'].text())
        if value != decode_text(self.current_album.location):
            self.changed_location = value
        else:
            self.changed_location = None
        self.timer.start()

    @QtCore.pyqtSlot(int)
    def new_access(self, index):
        value = unicode(self.widgets['access'].itemData(index).toString())
        if value != decode_text(self.current_album.access):
            self.changed_access = value
        else:
            self.changed_access = None
        self.timer.start()

    @QtCore.pyqtSlot()
    def new_album(self):
        self.save_changes()
        with Busy():
            self.current_album = self.pws.InsertAlbum('New album', '')
        self.albums.insertItem(
            0, decode_text(self.current_album.title),
            self.current_album.gphoto_id.text)
        self.albums.setCurrentIndex(0)

    @QtCore.pyqtSlot()
    def delete_album(self):
        if int(self.current_album.numphotos.text) > 0:
            if QtGui.QMessageBox.question(
                self, 'Delete album',
                """Are you sure you want to delete the album "%s"?
Doing so will remove the album and its photos from all Google products.""" % (
    unicode(self.current_album.title.text, 'UTF-8')),
                QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel,
                QtGui.QMessageBox.Cancel
                ) == QtGui.QMessageBox.Cancel:
                return
        self.clear_changes()
        with Busy():
            self.pws.Delete(self.current_album)
        self.albums.removeItem(self.albums.currentIndex())
        if self.albums.count() == 0:
            self.new_album()

    def save_changes(self):
        no_change = True
        # title
        if self.changed_title:
            self.current_album.title.text = self.changed_title.encode('utf-8')
            no_change = False
        # description
        if self.changed_description:
            if not self.current_album.summary:
                self.current_album.summary.text = atom.summary()
            self.current_album.summary.text = self.changed_description.encode('utf-8')
            no_change = False
        # location
        if self.changed_location:
            if not self.current_album.location:
                self.current_album.location = gdata.photos.Location()
            self.current_album.location.text = self.changed_location.encode('utf-8')
            no_change = False
        # access
        if self.changed_access:
            self.current_album.access.text = self.changed_access.encode('utf-8')
            no_change = False
        # timestamp
        if self.changed_timestamp:
            self.current_album.timestamp.text = self.changed_timestamp.encode('utf-8')
            no_change = False
        # upload changes
        self.clear_changes()
        if no_change:
            return
        with Busy():
            self.current_album = self.pws.Put(
                self.current_album, self.current_album.GetEditLink().href,
                converter=gdata.photos.AlbumEntryFromString)

    def refresh(self):
        if self.pws:
            return
        with Busy():
            if not self.authorise():
                return
            albums = self.pws.GetUserFeed()
            for album in albums.entry:
                if not album.GetEditLink():
                    # ignore 'system' albums
                    continue
                self.albums.addItem(
                    unicode(album.title.text, 'UTF-8'), album.gphoto_id.text)
            if self.albums.count() == 0:
                self.new_album()
        self.setEnabled(True)

    @QtCore.pyqtSlot(int)
    def changed_album(self, index):
        self.save_changes()
        self.current_album = None
        album_id = unicode(self.albums.itemData(index).toString())
        with Busy():
            albums = self.pws.GetUserFeed()
            for album in albums.entry:
                if album.gphoto_id.text == album_id:
                    self.current_album = album
                    break
            else:
                return
            if self.current_album.media.thumbnail:
                media = self.pws.GetMedia(self.current_album.media.thumbnail[0].url)
                image = QtGui.QPixmap()
                image.loadFromData(media.file_handle.read())
                self.album_thumb.setPixmap(image)
            else:
                self.album_thumb.clear()
        self.widgets['timestamp'].setDateTime(datetime.utcfromtimestamp(
            float(self.current_album.timestamp.text) * 1.0e-3))
        value = decode_text(self.current_album.summary)
        if value:
            self.widgets['description'].setText(value)
        else:
            self.widgets['description'].clear()
        value = decode_text(self.current_album.location)
        if value:
            self.widgets['location'].setText(value)
        else:
            self.widgets['location'].clear()
        self.widgets['access'].setCurrentIndex(
            self.widgets['access'].findData(self.current_album.access.text))

    @QtCore.pyqtSlot()
    def upload(self):
        if not self.image_list.unsaved_files_dialog(with_discard=False):
            return
        # make list of items to upload
        upload_list = []
        for image in self.image_list.get_selected_images():
            title = image.metadata.get_item('title').as_str()
            description = image.metadata.get_item('description').as_str()
            if title and description:
                summary = '%s\n\n%s' % (title, description)
            elif title:
                summary = title
            else:
                summary = description
            keywords = image.metadata.get_item('keywords')
            if keywords.empty():
                keywords = None
            else:
                keywords = ', '.join(keywords.value)
            latlong = image.metadata.get_item('latlong')
            if latlong.empty():
                latlong = None
            else:
                latlong = '%f %f' % latlong.value
            upload_list.append({
                'path'     : image.path,
                'summary'  : summary,
                'keywords' : keywords,
                'latlong'  : latlong,
                })
        # pass the list to a separate thread, so GUI can continue
        if self.authorise():
            self.upload_button.setEnabled(False)
            self.album_group.setEnabled(False)
            self.uploader = UploadThread(
                self.pws, upload_list, self.current_album.GetFeedLink().href)
            self.uploader.progress_report.connect(self.upload_progress)
            self.uploader.finished.connect(self.upload_done)
            self.uploader.start()
            # we've passed the service handle to a new thread, so
            # create a new one for safety
            self.pws = None
            self.authorise()

    @QtCore.pyqtSlot(float, float)
    def upload_progress(self, progress, total_progress):
        self.total_progress.setValue(total_progress)

    @QtCore.pyqtSlot()
    def upload_done(self):
        # reload current album
        self.changed_album(self.albums.currentIndex())
        self.upload_button.setEnabled(True)
        self.album_group.setEnabled(True)
        self.total_progress.setValue(0)
        self.uploader = None

    def authorise(self):
        if self.pws:
            return True
        self.pws = LoggingPhotosService()
        self.pws.SetOAuthInputParameters(
            gdata.auth.OAuthSignatureMethod.HMAC_SHA1,
            b'991146392375.apps.googleusercontent.com',
            consumer_secret=b'gSCBPBV0tpArWOK2IDcEA6eG')
        key = self.config_store.get('picasa', 'key', '')
        secret = self.config_store.get('picasa', 'secret', '')
        if sys.version_info[0] < 3:
            key = str(key)
            secret = str(secret)
        if key and secret:
            token = gdata.auth.OAuthToken(
                key=key, secret=secret,
                scopes='https://picasaweb.google.com/data/',
                oauth_input_params=self.pws.GetOAuthInputParameters())
            self.pws.SetOAuthToken(token)
            return True
        request_token = self.pws.FetchOAuthRequestToken(
            scopes='https://picasaweb.google.com/data/',
            extra_parameters={'xoauth_displayname' : 'Photini'},
            oauth_callback='oob')
        self.pws.SetOAuthToken(request_token)
        auth_url = self.pws.GenerateOAuthAuthorizationURL()
        if webbrowser.open(auth_url, new=2, autoraise=0):
            info_text = 'use your web browser'
        else:
            info_text = 'open "%s" in a web browser' % auth_url
        auth_code, OK = QtGui.QInputDialog.getText(
            self,
            'Photini: authorise Picasa',
            """Please %s to grant access to Photini,
then enter the verification code:""" % info_text)
        if not OK:
            self.pws = None
            return False
        try:
            access_token = self.pws.UpgradeToOAuthAccessToken(
                oauth_verifier=str(auth_code))
        except gdata.service.TokenUpgradeFailed:
            self.pws = None
            return False
        self.config_store.set('picasa', 'key', access_token.key)
        self.config_store.set('picasa', 'secret', access_token.secret)
        return True

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.upload_button.setEnabled(
            len(selection) > 0 and self.pws and not self.uploader)
