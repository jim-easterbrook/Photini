##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-15  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import urllib2
import webbrowser
import xml.etree.ElementTree

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt
import requests
from requests_oauthlib import OAuth2Session

from .descriptive import MultiLineEdit
from .utils import Busy, FileObjWithCallback

EPOCH = datetime.utcfromtimestamp(0)

logger = logging.getLogger(__name__)

nsmap = {
    'atom'   : 'http://www.w3.org/2005/Atom',
    'gd'     : 'http://schemas.google.com/g/2005',
    'georss' : 'http://www.georss.org/georss',
    'gml'    : 'http://www.opengis.net/gml',
    'gphoto' : 'http://schemas.google.com/photos/2007',
    'media'  : 'http://search.yahoo.com/mrss/',
    }

for prefix, uri in nsmap.items():
    xml.etree.ElementTree.register_namespace(prefix, uri)
xml.etree.ElementTree.register_namespace('', nsmap['atom'])

class BaseNode(object):
    def __init__(self, dom):
        self._dom = dom
        self.etag = dom.get('{' + nsmap['gd'] + '}etag')

    def __getattr__(self, name):
        if name not in self._elements:
            raise AttributeError(name)
        namespace, repeat, klass = self._elements[name]
        tag = '{' + nsmap[namespace] + '}' + name
        if repeat:
            result = self._dom.findall(tag)
            if klass:
                result = map(klass, result)
            return result
        result = self._dom.find(tag)
        if result is None:
            logger.debug('new %s:%s', self.__class__.__name__, name)
            result = xml.etree.ElementTree.SubElement(self._dom, tag)
        if klass:
            result = klass(result)
        return result

    def to_string(self):
        return xml.etree.ElementTree.tostring(self._dom, encoding='utf-8')

    def GetLink(self, link_type):
        for child in self._dom.findall('atom:link', nsmap):
            if child.get('rel').endswith(link_type):
                return child.get('href')
        return None

class PointNode(BaseNode):
    _elements = {'pos' : ('gml', False, None)}

class WhereNode(BaseNode):
    _elements = {'Point' : ('gml', False, PointNode)}

class GroupNode(BaseNode):
    _elements = {
        'keywords'  : ('media', False, None),
        'thumbnail' : ('media', True,  None),
        }

class PhotoNode(BaseNode):
    _elements = {
        'group'   : ('media',  False, GroupNode),
        'summary' : ('atom',   False, None),
        'title'   : ('atom',   False, None),
        'where'   : ('georss', False, WhereNode),
        }

class AlbumNode(BaseNode):
    _elements = {
        'access'    : ('gphoto', False, None),
        'category'  : ('atom',   False, None),
        'group'     : ('media',  False, GroupNode),
        'id'        : ('gphoto', False, None),
        'location'  : ('gphoto', False, None),
        'numphotos' : ('gphoto', False, None),
        'summary'   : ('atom',   False, None),
        'timestamp' : ('gphoto', False, None),
        'title'     : ('atom',   False, None),
        }

class AlbumsRoot(BaseNode):
    _elements = {'entry' : ('atom', True, AlbumNode)}

def request_with_check(cmd, *arg, **kw):
    resp = cmd(*arg, **kw)
    if resp.status_code >= 300:
        logger.warning(resp.content)
    resp.raise_for_status()
    if resp.text:
        return xml.etree.ElementTree.fromstring(resp.text.encode('utf-8'))
    return None

class UploadThread(QtCore.QThread):
    def __init__(self, session, upload_list, feed_uri):
        QtCore.QThread.__init__(self)
        self.session = session
        self.upload_list = upload_list
        self.feed_uri = feed_uri

    finished = QtCore.pyqtSignal()
    def run(self):
        self.file_count = 0
        for params in self.upload_list:
            title = os.path.basename(params['path'])
            with open(params['path'], 'rb') as f:
                fileobj = FileObjWithCallback(f, self.callback)
                dom = request_with_check(
                    self.session.post, self.feed_uri, data=fileobj,
                    headers={'Content-Type' : 'image/jpeg', 'Slug' : title})
            photo = PhotoNode(dom)
            photo.title.text = title
            if params['summary']:
                photo.summary.text = params['summary']
            if params['keywords']:
                photo.group.keywords.text = params['keywords']
            if params['latlong']:
                photo.where.Point.pos.text = params['latlong']
            dom = request_with_check(
                self.session.put, photo.GetLink('edit'), photo.to_string(),
                headers={'If-Match' : photo.etag,
                         'Content-Type' : 'application/atom+xml'})
            self.file_count += 1
        self.finished.emit()

    progress_report = QtCore.pyqtSignal(float, float)
    def callback(self, progress):
        total_progress = (
            (self.file_count * 100) + progress) / len(self.upload_list)
        self.progress_report.emit(progress, total_progress)

class PicasaUploader(QtGui.QWidget):
    album_feed    = 'https://picasaweb.google.com/data/feed/api/user/default'
    client_id     = '991146392375.apps.googleusercontent.com'
    client_secret = 'gSCBPBV0tpArWOK2IDcEA6eG'
    def __init__(self, config_store, image_list, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.image_list = image_list
        self.setLayout(QtGui.QGridLayout())
        self.session = None
        self.widgets = {}
        self.current_album = None
        self.uploader = None
        ### album group
        self.album_group = QtGui.QGroupBox(self.tr('Album'))
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
        album_form_left.addRow(self.tr('Title'), self.albums)
        # album description
        self.widgets['description'] = MultiLineEdit()
        self.widgets['description'].editingFinished.connect(self.new_description)
        album_form_left.addRow(
            self.tr('Description'), self.widgets['description'])
        # album location
        self.widgets['location'] = QtGui.QLineEdit()
        self.widgets['location'].editingFinished.connect(self.new_location)
        album_form_left.addRow(self.tr('Place taken'), self.widgets['location'])
        # album visibility
        self.widgets['access'] = QtGui.QComboBox()
        self.widgets['access'].addItem(self.tr('Public on the web'), 'public')
        self.widgets['access'].addItem(
            self.tr('Limited, anyone with the link'), 'private')
        self.widgets['access'].addItem(self.tr('Only you'), 'protected')
        self.widgets['access'].currentIndexChanged.connect(self.new_access)
        album_form_left.addRow(self.tr('Visibility'), self.widgets['access'])
        ## album buttons
        buttons = QtGui.QHBoxLayout()
        album_form_left.addRow('', buttons)
        # new album
        new_album_button = QtGui.QPushButton(self.tr('New album'))
        new_album_button.clicked.connect(self.new_album)
        buttons.addWidget(new_album_button)
        # delete album
        delete_album_button = QtGui.QPushButton(self.tr('Delete album'))
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
        album_form_right.addRow(self.tr('Date'), self.widgets['timestamp'])
        # album thumbnail
        self.album_thumb = QtGui.QLabel()
        album_form_right.addRow(self.album_thumb)
        ### upload button
        self.upload_button = QtGui.QPushButton(self.tr('Upload\nnow'))
        self.upload_button.setEnabled(False)
        self.upload_button.clicked.connect(self.upload)
        self.layout().addWidget(self.upload_button, 2, 3)
        ### progress bar
        self.layout().addWidget(QtGui.QLabel(self.tr('Progress')), 3, 0)
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
        value = self.albums.lineEdit().text()
        self.albums.setItemText(self.albums.currentIndex(), value)
        value = unicode(value)
        if value != self.current_album.title.text:
            self.changed_title = value
        else:
            self.changed_title = None
        self.timer.start()

    @QtCore.pyqtSlot()
    def new_description(self):
        value = unicode(self.widgets['description'].text())
        if value != self.current_album.summary.text:
            self.changed_description = value
        else:
            self.changed_description = None
        self.timer.start()

    @QtCore.pyqtSlot()
    def new_timestamp(self):
        value = '{0:d}'.format(
            (self.widgets['timestamp'].dateTime().toPyDateTime() - EPOCH
             ).total_seconds() * 1000)
        if value != self.current_album.timestamp.text:
            self.changed_timestamp = value
        else:
            self.changed_timestamp = None
        self.timer.start()

    @QtCore.pyqtSlot()
    def new_location(self):
        value = unicode(self.widgets['location'].text())
        if value != self.current_album.location.text:
            self.changed_location = value
        else:
            self.changed_location = None
        self.timer.start()

    @QtCore.pyqtSlot(int)
    def new_access(self, index):
##        value = unicode(self.widgets['access'].itemData(index).toString())
        value = unicode(self.widgets['access'].itemData(index))
        if value != self.current_album.access.text:
            self.changed_access = value
        else:
            self.changed_access = None
        self.timer.start()

    @QtCore.pyqtSlot()
    def new_album(self):
        self.save_changes()
        with Busy():
            self.albums_cache = None
            dom = xml.etree.ElementTree.Element('{' + nsmap['atom'] + '}entry')
            album = AlbumNode(dom)
            album.title.text = unicode(self.tr('New album'))
            album.category.set('scheme', 'http://schemas.google.com/g/2005#kind')
            album.category.set('term', 'http://schemas.google.com/photos/2007#album')
            dom = request_with_check(
                self.session.post, self.album_feed, album.to_string(),
                headers={'Content-Type' : 'application/atom+xml'})
            self.current_album = AlbumNode(dom)
        self.albums.insertItem(
            0, self.current_album.title.text, self.current_album.id.text)
        self.albums.setCurrentIndex(0)

    @QtCore.pyqtSlot()
    def delete_album(self):
        if int(self.current_album.numphotos.text) > 0:
            if QtGui.QMessageBox.question(
                self, self.tr('Delete album'),
                self.tr("""Are you sure you want to delete the album "{0}"?
Doing so will remove the album and its photos from all Google products."""
                        ).format(self.current_album.title.text),
                QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel,
                QtGui.QMessageBox.Cancel
                ) == QtGui.QMessageBox.Cancel:
                return
        self.clear_changes()
        with Busy():
            self.albums_cache = None
            request_with_check(
                self.session.delete, self.current_album.GetLink('edit'),
                headers={'If-Match' : self.current_album.etag})
        self.albums.removeItem(self.albums.currentIndex())
        if self.albums.count() == 0:
            self.new_album()

    def save_changes(self):
        no_change = True
        # title
        if self.changed_title:
            self.current_album.title.text = self.changed_title
            no_change = False
        # description
        if self.changed_description:
            self.current_album.summary.text = self.changed_description
            no_change = False
        # location
        if self.changed_location:
            self.current_album.location.text = self.changed_location
            no_change = False
        # access
        if self.changed_access:
            self.current_album.access.text = self.changed_access
            no_change = False
        # timestamp
        if self.changed_timestamp:
            self.current_album.timestamp.text = self.changed_timestamp
            no_change = False
        # upload changes
        self.clear_changes()
        if no_change:
            return
        with Busy():
            self.albums_cache = None
            dom = request_with_check(
                self.session.put, self.current_album.GetLink('edit'),
                self.current_album.to_string(),
                headers={'If-Match' : self.current_album.etag,
                         'Content-Type' : 'application/atom+xml'})
            self.current_album = AlbumNode(dom)

    def get_albums(self):
        if self.albums_cache is not None:
            return self.albums_cache
        dom = request_with_check(self.session.get, self.album_feed)
        self.albums_cache = AlbumsRoot(dom).entry
        return self.albums_cache

    def refresh(self):
        if self.session:
            return
        with Busy():
            if not self.authorise():
                return
            for album in self.get_albums():
                if not album.GetLink('edit'):
                    # ignore 'system' albums
                    continue
                self.albums.addItem(album.title.text, album.id.text)
            if self.albums.count() == 0:
                self.new_album()
        self.setEnabled(True)

    @QtCore.pyqtSlot(int)
    def changed_album(self, index):
        self.save_changes()
        self.current_album = None
        album_id = unicode(self.albums.itemData(index))
        with Busy():
            for album in self.get_albums():
                if album.id.text == album_id:
                    self.current_album = album
                    break
            else:
                return
            if self.current_album.group.thumbnail is not None:
                url = self.current_album.group.thumbnail[0].get('url')
                image = QtGui.QPixmap()
                image.loadFromData(urllib2.urlopen(url).read())
                self.album_thumb.setPixmap(image)
            else:
                self.album_thumb.clear()
        self.widgets['timestamp'].setDateTime(datetime.utcfromtimestamp(
            float(self.current_album.timestamp.text) * 1.0e-3))
        value = self.current_album.summary.text
        if value:
            self.widgets['description'].setText(value)
        else:
            self.widgets['description'].clear()
        value = self.current_album.location.text
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
                summary = '{0}\n\n{1}'.format(title, description)
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
                latlong = '{0} {1}'.format(*latlong.value)
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
                self.session, upload_list, self.current_album.GetLink('feed'))
            self.uploader.progress_report.connect(self.upload_progress)
            self.uploader.finished.connect(self.upload_done)
            self.uploader.start()
            # we've passed the session handle to a new thread, so
            # create a new one for safety
            self.session = None
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
        if self.session:
            return True
        self.albums_cache = None
        refresh_token = self.config_store.get('picasa', 'refresh_token')
        if refresh_token:
            # create expired token
            token = {
                'access_token'  : 'xxx',
                'refresh_token' : refresh_token,
                'expires_in'    : -30,
                }
        else:
            # do full authentication procedure
            oauth = OAuth2Session(
                self.client_id, redirect_uri='urn:ietf:wg:oauth:2.0:oob',
                scope='https://picasaweb.google.com/data/')
            auth_url, state = oauth.authorization_url(
                'https://accounts.google.com/o/oauth2/auth')
            if webbrowser.open(auth_url, new=2, autoraise=0):
                info_text = self.tr('use your web browser')
            else:
                info_text = self.tr('open "{0}" in a web browser').format(auth_url)
            auth_code, OK = QtGui.QInputDialog.getText(
                self,
                self.tr('Photini: authorise Picasa'),
                self.tr("""Please {0} to grant access to Photini,
then enter the verification code:""").format(info_text))
            if not OK:
                self.session = None
                return False
            token = oauth.fetch_token(
                'https://www.googleapis.com/oauth2/v3/token',
                code=str(auth_code).strip(), client_secret=self.client_secret)
            self.save_token(token)
        self.session = OAuth2Session(
            self.client_id, token=token, token_updater=self.save_token,
            auto_refresh_kwargs={
                'client_id'     : self.client_id,
                'client_secret' : self.client_secret},
            auto_refresh_url='https://www.googleapis.com/oauth2/v3/token',
            )
        self.session.headers.update({'GData-Version': 2})
        return True

    def save_token(self, token):
        self.config_store.set('picasa', 'refresh_token', token['refresh_token'])

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.upload_button.setEnabled(
            len(selection) > 0 and self.session and not self.uploader)
