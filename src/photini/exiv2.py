##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import codecs
import locale
import logging
import os
from pprint import pprint
import random
import shutil
import string
import sys

import exiv2

logger = logging.getLogger(__name__)

_iptc_encodings = {
    'ascii'    : (b'\x1b\x28\x42',),
    'iso8859-1': (b'\x1b\x2f\x41', b'\x1b\x2e\x41'),
    'utf-8'    : (b'\x1b\x25\x47', b'\x1b\x25\x2f\x49'),
    'utf-16-be': (b'\x1b\x25\x2f\x4c',),
    'utf-32-be': (b'\x1b\x25\x2f\x46',),
    }

XMP_WRAPPER = '''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 4.4.0-Exiv2">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      {}/>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''


class MetadataHandler(object):
    @classmethod
    def initialise(cls):
        exiv2.XmpParser.initialize()
        # make list of possible character encodings
        cls.encodings = ['utf-8', 'iso8859-1', 'ascii']
        char_set = locale.getdefaultlocale()[1]
        if char_set:
            try:
                name = codecs.lookup(char_set).name
                if name not in cls.encodings:
                    cls.encodings.append(name)
            except LookupError:
                pass
        
    def __init__(self, path, buf=None, utf_safe=False):
        self._path = path
        # read metadata
        if buf:
            self._image = exiv2.ImageFactory.open(buf)
        else:
            self._image = exiv2.ImageFactory.open(self._path)
        self._image.readMetadata()
        access_mode = {
            'exif': self._image.checkMode(exiv2.mdExif),
            'iptc': self._image.checkMode(exiv2.mdIptc),
            'xmp': self._image.checkMode(exiv2.mdXmp),
            }
        self.read_only = not any(
            [x in (exiv2.amWrite, exiv2.amReadWrite)
             for x in access_mode.values()])
        self.mime_type = self._image.mimeType()
        self.xmp_only = self.mime_type in (
            'application/rdf+xml', 'application/postscript')
        # Don't use Exiv2's converted values when accessing Xmp files
        if self.xmp_only:
            self._image.clearExifData()
            self._image.clearIptcData()
        self._exifData = self._image.exifData()
        self._iptcData = self._image.iptcData()
        self._xmpData = self._image.xmpData()
        # transcode any non utf-8 strings (Xmp is always utf-8)
        for data in self._exifData, self._iptcData:
            for item in data:
                if item.typeId() not in (exiv2.asciiString, exiv2.string):
                    continue
                value = item.toString()
                raw_value = value.encode('utf-8', errors='surrogateescape')
                for encoding in self.encodings:
                    try:
                        new_value = raw_value.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                    if new_value != value:
                        logger.info('%s: transcoded %s from %s',
                                    os.path.basename(self._path),
                                    str(item.key()), encoding)
                        item.setValue(new_value)
                    break

        # any sub images?
        self.ifd_list = ['Image']

    @classmethod
    def open_old(cls, *arg, **kw):
        try:
            return cls(*arg, **kw)
        except Exception as ex:
            logger.exception(ex)
            return None

    def get_exif_thumbnail(self):
        # try normal thumbnail
        thumb = exiv2.ExifThumb(self._exifData)
        data = thumb.copy()
        if data:
            return data
##        # try subimage thumbnails
        return None

    def get_exif_value(self, tag):
        for item in self._exifData:
            if str(item.key()) != tag:
                continue
            if tag in ('Exif.Canon.ModelID', 'Exif.CanonCs.LensType',
                       'Exif.Image.XPTitle', 'Exif.Image.XPComment',
                       'Exif.Image.XPAuthor', 'Exif.Image.XPKeywords',
                       'Exif.Image.XPSubject', 'Exif.NikonLd1.LensIDNumber',
                       'Exif.NikonLd2.LensIDNumber',
                       'Exif.NikonLd3.LensIDNumber', 'Exif.Pentax.ModelID',
                       'Exif.Photo.UserComment'):
                return item._print()
            return item.toString()
        return None

    def get_iptc_value(self, tag):
        result = []
        for item in self._iptcData:
            if str(item.key()) != tag:
                continue
            if item.typeId() != exiv2.string:
                return item.toString()
            result.append(item.toString())
        return result or None

    def get_xmp_value(self, tag):
        for item in self._xmpData:
            if str(item.key()) != tag:
                continue
            item_id = item.typeId()
            if item_id == exiv2.xmpText:
                return item.toString()
            if item_id == exiv2.langAlt:
                # just get 'x-default' value for now
                value = exiv2.LangAltValue.downCast(item.value())
                return value.toString(0)
            if item_id in (exiv2.xmpAlt, exiv2.xmpBag, exiv2.xmpSeq):
                value = exiv2.XmpArrayValue.downCast(item.value())
                result = []
                for n in range(value.count()):
                    result.append(value.toString(n))
                return result
            print(tag, '{:x}'.format(item.typeId()), item.getValue())
            return None
        return None

    def clear_tag(self, tag):
        family = tag.split('.')[0]
        if family == 'Exif':
            data = self._exifData
            key = exiv2.ExifKey(tag)
        elif family == 'Iptc':
            data = self._iptcData
            key = exiv2.IptcKey(tag)
        elif family == 'Xmp':
            data = self._xmpData
            key = exiv2.XmpKey(tag)
        while True:
            pos = data.findKey(key)
            if pos == data.end():
                break
            data.erase(pos)

    def has_tag(self, tag):
        for item in self._data_set(tag):
            if str(item.key()) == tag:
                return True
        return False

    @staticmethod
    def is_exif_tag(tag):
        return tag.split('.')[0] == 'Exif'

    @staticmethod
    def is_iptc_tag(tag):
        return tag.split('.')[0] == 'Iptc'

    @staticmethod
    def is_xmp_tag(tag):
        return tag.split('.')[0] == 'Xmp'

    def _data_set(self, tag):
        family = tag.split('.')[0]
        if family == 'Exif':
            return self._exifData
        if family == 'Iptc':
            return self._iptcData
        if family == 'Xmp':
            return self._xmpData
        return []

    def save(self):
        return True

    def delete_makernote(self, camera_model):
        pass

    def merge_sc(self, other):
        pass
