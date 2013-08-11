##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-13  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import os
import time
import webbrowser

import atom
import gdata.auth
import gdata.photos
import gdata.photos.service
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

from photini.descriptive import MultiLineEdit

EPOCH = datetime.datetime.utcfromtimestamp(0)

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
            if params['title']:
                if not photo.summary:
                    photo.summary = atom.Summary()
                photo.summary.text = params['title']
            if params['keywords']:
                if not photo.media:
                    photo.media = gdata.media.Group()
                if not photo.media.keywords:
                    photo.media.keywords = gdata.media.Keywords()
                photo.media.keywords.text = u', '.join(
                    params['keywords'].split(';'))
            if params['lat'] is not None and params['lng'] is not None:
                if not photo.geo:
                    photo.geo = gdata.geo.Where()
                if not photo.geo.Point:
                    photo.geo.Point = gdata.geo.Point()
                photo.geo.Point.pos = gdata.geo.Pos(text='%f %f' % (
                    params['lat'].degrees, params['lng'].degrees))
            mediasource = MediaSourceWithCallback(
                params['path'], 'image/jpeg', self.callback)
            try:
                photo = self.pws.Post(
                    photo, uri=self.feed_uri, media_source=mediasource,
                    converter=gdata.photos.PhotoEntryFromString)
            except gdata.service.RequestError, e:
                raise gdata.photos.service.GooglePhotosException(e.args[0])
            if params['description']:
                comment = self.pws.InsertComment(
                    photo.GetPostLink().href, params['description'])
            self.file_count += 1
        self.finished.emit()

    progress_report = QtCore.pyqtSignal(float, float)
    def callback(self, progress):
        total_progress = (
            (self.file_count * 100) + progress) / len(self.upload_list)
        self.progress_report.emit(progress, total_progress)

class AlbumButtons(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        layout = QtGui.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # new album
        self.new = QtGui.QPushButton('New album')
        layout.addWidget(self.new)
        # delete album
        self.delete = QtGui.QPushButton('Delete album')
        layout.addWidget(self.delete)
        # a bit of space
        layout.addSpacing(20)
        # save changes
        self.save = QtGui.QPushButton('Save changes')
        layout.addWidget(self.save)
        # discard changes
        self.discard = QtGui.QPushButton('Discard changes')
        layout.addWidget(self.discard)
        # other init
        self.changed = None
        self.set_changed(False)

    def set_changed(self, value):
        if self.changed == value:
            return
        self.changed = value
        self.save.setEnabled(self.changed)
        self.discard.setEnabled(self.changed)

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
        album_group = QtGui.QGroupBox('Album')
        album_group.setLayout(QtGui.QHBoxLayout())
        self.layout().addWidget(album_group, 0, 0, 3, 1)
        ## album details
        album_form = QtGui.QWidget()
        album_form.setLayout(QtGui.QFormLayout())
        album_group.layout().addWidget(album_form)
        # album title / selector
        self.albums = QtGui.QComboBox()
        self.albums.setEditable(True)
        self.albums.setInsertPolicy(QtGui.QComboBox.NoInsert)
        self.albums.currentIndexChanged.connect(self.changed_album)
        self.albums.lineEdit().editingFinished.connect(self.new_title)
        album_form.layout().addRow('Title', self.albums)
        # album date
        self.widgets['timestamp'] = QtGui.QDateEdit()
        self.widgets['timestamp'].editingFinished.connect(self.new_timestamp)
        album_form.layout().addRow('Date', self.widgets['timestamp'])
        # album description
        self.widgets['description'] = MultiLineEdit()
        self.widgets['description'].editingFinished.connect(self.new_description)
        album_form.layout().addRow('Description', self.widgets['description'])
        # album location
        self.widgets['location'] = QtGui.QLineEdit()
        self.widgets['location'].editingFinished.connect(self.new_location)
        album_form.layout().addRow('Place taken', self.widgets['location'])
        # album visibility
        self.widgets['access'] = QtGui.QComboBox()
        self.widgets['access'].addItem('Public on the web', 'public')
        self.widgets['access'].addItem('Limited, anyone with the link', 'private')
        self.widgets['access'].addItem('Only you', 'protected')
        self.widgets['access'].currentIndexChanged.connect(self.new_access)
        album_form.layout().addRow('Visibility', self.widgets['access'])
        # album buttons
        self.buttons = AlbumButtons()
        self.buttons.new.clicked.connect(self.new_album)
        self.buttons.delete.clicked.connect(self.delete_album)
        self.buttons.save.clicked.connect(self.save_changes)
        self.buttons.discard.clicked.connect(self.discard_changes)
        album_form.layout().addRow(self.buttons)
        ## album thumbnail
        self.album_thumb = QtGui.QLabel()
        self.album_thumb.setAlignment(Qt.AlignTop)
        album_group.layout().addWidget(self.album_thumb)
        ### upload button
        self.upload_button = QtGui.QPushButton('Upload now')
        self.upload_button.setEnabled(False)
        self.upload_button.clicked.connect(self.upload)
        self.layout().addWidget(self.upload_button, 2, 3)
        ### progress bars
        self.layout().addWidget(QtGui.QLabel('File progress'), 3, 0, 1, 4)
        self.file_progress = QtGui.QProgressBar()
        self.layout().addWidget(self.file_progress, 4, 0, 1, 4)
        self.layout().addWidget(QtGui.QLabel('Overall progress'), 5, 0, 1, 4)
        self.total_progress = QtGui.QProgressBar()
        self.layout().addWidget(self.total_progress, 6, 0, 1, 4)
        self.setEnabled(False)
        # adjust spacing
        self.layout().setRowStretch(1, 1)

    @QtCore.pyqtSlot()
    def new_title(self):
        value = unicode(self.albums.lineEdit().text())
        if value == self.current_album.title.text:
            return
        self.albums.setItemText(self.albums.currentIndex(), value)
        self.current_album.title.text = value
        self.buttons.set_changed(True)

    @QtCore.pyqtSlot()
    def new_description(self):
        value = unicode(self.widgets['description'].text())
        if value == self.current_album.summary.text:
            return
        self.current_album.summary.text = value
        self.buttons.set_changed(True)

    @QtCore.pyqtSlot()
    def new_timestamp(self):
        value = '%d' % (
            (self.widgets['timestamp'].dateTime().toPyDateTime() - EPOCH
             ).total_seconds() * 1000)
        if value == self.current_album.timestamp.text:
            return
        self.current_album.timestamp.text = value
        self.buttons.set_changed(True)

    @QtCore.pyqtSlot()
    def new_location(self):
        value = unicode(self.widgets['location'].text())
        if value == self.current_album.location.text:
            return
        self.current_album.location.text = value
        self.buttons.set_changed(True)

    @QtCore.pyqtSlot(int)
    def new_access(self, index):
        value = unicode(self.widgets['access'].itemData(index).toString())
        if value == self.current_album.access.text:
            return
        self.current_album.access.text = value
        self.buttons.set_changed(True)

    @QtCore.pyqtSlot()
    def new_album(self):
        self.current_album = self.pws.InsertAlbum('New album', '')
        self.albums.insertItem(
            0, unicode(self.current_album.title.text, 'UTF-8'),
            self.current_album.gphoto_id.text)
        self.albums.setCurrentIndex(0)
        self.albums.lineEdit().selectAll()

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
        self.pws.Delete(self.current_album)
        self.albums.removeItem(self.albums.currentIndex())
        if self.albums.count() == 0:
            self.new_album()

    @QtCore.pyqtSlot()
    def save_changes(self):
        self.current_album = self.pws.Put(
            self.current_album, self.current_album.GetEditLink().href,
            converter=gdata.photos.AlbumEntryFromString)
        self.buttons.set_changed(False)

    @QtCore.pyqtSlot()
    def discard_changes(self):
        self.changed_album(self.albums.currentIndex())
        self.buttons.set_changed(False)

    def refresh(self):
        if self.pws:
            return
        QtGui.QApplication.setOverrideCursor(Qt.WaitCursor)
        if not self.authorise():
            QtGui.QApplication.restoreOverrideCursor()
            return
        albums = self.pws.GetUserFeed()
        for album in albums.entry:
            self.albums.addItem(
                unicode(album.title.text, 'UTF-8'), album.gphoto_id.text)
        if self.albums.count() == 0:
            self.new_album()
        QtGui.QApplication.restoreOverrideCursor()
        self.setEnabled(True)

    @QtCore.pyqtSlot(int)
    def changed_album(self, index):
        self.current_album = None
        album_id = unicode(self.albums.itemData(index).toString())
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
        self.widgets['timestamp'].setDate(datetime.date.fromtimestamp(
            float(self.current_album.timestamp.text) * 1.0e-3))
        if self.current_album.summary.text:
            self.widgets['description'].setText(
                unicode(self.current_album.summary.text, 'UTF-8'))
        else:
            self.widgets['description'].clear()
        if self.current_album.location and self.current_album.location.text:
            self.widgets['location'].setText(
                unicode(self.current_album.location.text, 'UTF-8'))
        else:
            self.widgets['location'].clear()
        self.widgets['access'].setCurrentIndex(
            self.widgets['access'].findData(self.current_album.access.text))
        self.buttons.set_changed(False)

    @QtCore.pyqtSlot()
    def upload(self):
        if not self.image_list.unsaved_files_dialog(with_discard=False):
            return
        # make list of items to upload
        upload_list = []
        for image in self.image_list.get_selected_images():
            title = image.metadata.get_item('title')
            description = image.metadata.get_item('description')
            keywords = image.metadata.get_item('keywords')
            lat = image.metadata.get_item('latitude')
            lng = image.metadata.get_item('longitude')
            upload_list.append({
                'path'        : image.path,
                'title'       : title,
                'description' : description,
                'keywords'    : keywords,
                'lat'         : lat,
                'lng'         : lng,
                })
        # pass the list to a separate thread, so GUI can continue
        if self.authorise():
            self.upload_button.setEnabled(False)
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
        self.file_progress.setValue(progress)
        self.total_progress.setValue(total_progress)

    @QtCore.pyqtSlot()
    def upload_done(self):
        self.upload_button.setEnabled(True)
        self.file_progress.setValue(0)
        self.total_progress.setValue(0)
        self.uploader = None

    def authorise(self):
        if self.pws:
            return True
        self.pws = gdata.photos.service.PhotosService(email='default')
        self.pws.SetOAuthInputParameters(
            gdata.auth.OAuthSignatureMethod.HMAC_SHA1,
            '991146392375.apps.googleusercontent.com',
            consumer_secret='gSCBPBV0tpArWOK2IDcEA6eG')
        key = self.config_store.get('picasa', 'key', '')
        secret = self.config_store.get('picasa', 'secret', '')
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
        print auth_url
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
