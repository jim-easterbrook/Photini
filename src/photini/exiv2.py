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

exiv2_version = 'python-exiv2 {}, exiv2 {}'.format(
    exiv2.__version__, exiv2.versionString())

_iptc_encodings = {
    'ascii'    : (b'\x1b\x28\x42',),
    'iso8859-1': (b'\x1b\x2f\x41', b'\x1b\x2e\x41'),
    'utf-8'    : (b'\x1b\x25\x47', b'\x1b\x25\x2f\x49'),
    'utf-16-be': (b'\x1b\x25\x2f\x4c',),
    'utf-32-be': (b'\x1b\x25\x2f\x46',),
    }


class MetadataHandler(object):
    @classmethod
    def initialise(cls):
        exiv2.XmpParser.initialize()
        # Recent versions of Exiv2 have these namespaces defined, but
        # older versions may not recognise them. The xapGImg URL is
        # invalid, but Photini doesn't write xapGImg so it doesn't
        # matter. Exiv2 already has the Iptc4xmpExt namespace, but calls
        # it iptcExt which causes problems saving tags like
        # 'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:City'.
        # Re-registering it under its full name means I have to use
        # 'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:City' instead.
        for prefix, ns in (
                ('exifEX',      'http://cipa.jp/exif/1.0/'),
                ('Iptc4xmpExt', 'http://iptc.org/std/Iptc4xmpExt/2008-02-29/'),
                ('xapGImg',     'http://ns.adobe.com/xxx/'),
                ('xmpGImg',     'http://ns.adobe.com/xap/1.0/g/img/'),
                ('xmpRights',   'http://ns.adobe.com/xap/1.0/rights/'),
                ):
            exiv2.XmpProperties.registerNs(ns, prefix)
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
        self._exifData = self._image.exifData()
        self._iptcData = self._image.iptcData()
        self._xmpData = self._image.xmpData()
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
            self.clear_exif()
            self.clear_iptc()
        # transcode any non utf-8 strings (Xmp is always utf-8)
        for data in self._exifData, self._iptcData:
            for datum in data:
                if datum.typeId() not in (exiv2.asciiString, exiv2.string):
                    continue
                value = datum.toString()
                raw_value = value.encode('utf-8', errors='surrogateescape')
                for encoding in self.encodings:
                    try:
                        new_value = raw_value.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                    if new_value != value:
                        logger.info('%s: transcoded %s from %s',
                                    os.path.basename(self._path),
                                    str(datum.key()), encoding)
                        datum.setValue(new_value)
                    break

        # any sub images?
        self.ifd_list = ['Image']

    def clear_exif(self):
        self._exifData.clear()
        self._image.clearExifData()

    def clear_iptc(self):
        self._iptcData.clear()
        self._image.clearIptcData()

    def get_exif_tags(self):
        for datum in self._exifData:
            yield str(datum.key())

    def get_iptc_tags(self):
        for datum in self._iptcData:
            yield str(datum.key())

    def get_xmp_tags(self):
        for datum in self._xmpData:
            yield str(datum.key())

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

    def set_exif_thumbnail_from_buffer(self, buffer):
        thumb = exiv2.ExifThumb(self._exifData)
        thumb.setJpegThumbnail(buffer)

    def get_exif_value(self, tag):
        for datum in self._exifData:
            if datum.key() != tag:
                continue
            if tag in ('Exif.Canon.ModelID', 'Exif.CanonCs.LensType',
                       'Exif.Image.XPTitle', 'Exif.Image.XPComment',
                       'Exif.Image.XPAuthor', 'Exif.Image.XPKeywords',
                       'Exif.Image.XPSubject', 'Exif.NikonLd1.LensIDNumber',
                       'Exif.NikonLd2.LensIDNumber',
                       'Exif.NikonLd3.LensIDNumber', 'Exif.Pentax.ModelID',
                       'Exif.Photo.UserComment'):
                return datum._print()
            return datum.toString()
        return None

    def get_iptc_value(self, tag):
        result = []
        for datum in self._iptcData:
            if datum.key() != tag:
                continue
            value = datum.toString()
            if exiv2.IptcDataSets.dataSetRepeatable(datum.tag(),
                                                    datum.record()):
                result.append(value)
            else:
                return value
        return result or None

    def get_xmp_value(self, tag):
        for datum in self._xmpData:
            if datum.key() != tag:
                continue
            type_id = datum.typeId()
            if type_id == exiv2.xmpText:
                return datum.toString()
            if type_id == exiv2.langAlt:
                # just get 'x-default' value for now
                value = exiv2.LangAltValue.downCast(datum.value())
                return value.toString(0)
            if type_id in (exiv2.xmpAlt, exiv2.xmpBag, exiv2.xmpSeq):
                value = exiv2.XmpArrayValue.downCast(datum.value())
                result = []
                for n in range(value.count()):
                    result.append(value.toString(n))
                return result
            print('get_xmp_value', tag, '{:x}'.format(datum.typeId()), datum.getValue())
            return None
        return None

    def set_exif_value(self, tag, value):
        if not value:
            self.clear_tag(tag)
        else:
            datum = self._exifData[tag]
            datum.setValue(value)

    def set_iptc_value(self, tag, value):
        # clear any existing values (which might be repeated)
        self.clear_tag(tag)
        if not value:
            return
        if isinstance(value, str):
            # set a single value
            datum = self._iptcData[tag]
            datum.setValue(value)
            return
        # set a list/tuple of values
        key = exiv2.IptcKey(tag)
        for sub_value in value:
            datum = exiv2.Iptcdatum(key)
            datum.setValue(sub_value)
            if self._iptcData.add(datum) != 0:
                logger.error('%s: duplicated tag %s',
                             os.path.basename(self._path), tag)
                return

    def set_xmp_value(self, tag, value):
        if not value:
            self.clear_tag(tag)
            return
        if '[' in tag:
            # create XMP array
            container = tag.split('[')[0]
            for datum in self._xmpData:
                if datum.key().startswith(container):
                    # container already exists
                    break
            else:
                # XmpProperties uses 'iptcExt' namespace abbreviation
                key = exiv2.XmpKey(container.replace('Iptc4xmpExt', 'iptcExt'))
                type_id = exiv2.XmpProperties.propertyType(key)
                print('container type id {:x}'.format(type_id))
                self._xmpData[container] = exiv2.XmpArrayValue.create(type_id)
        datum = self._xmpData[tag]
        if isinstance(value, str):
            # set a single value
            datum.setValue(value)
            return
        # set a list/tuple of values
        type_id = datum.typeId()
        if type_id == exiv2.invalidTypeId:
            key = exiv2.XmpKey(datum.key())
            type_id = exiv2.XmpProperties.propertyType(key)
        if type_id in (exiv2.xmpAlt, exiv2.xmpBag, exiv2.xmpSeq):
            xmp_value = exiv2.XmpArrayValue.create(type_id)
            xmp_value = exiv2.XmpArrayValue.downCast(xmp_value)
            for sub_value in value:
                xmp_value.read(sub_value)
        else:
            print('set_xmp_value', tag, '{:x}'.format(type_id), value)
            return
        datum.setValue(xmp_value)

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

    def has_iptc(self):
        return self._iptcData.count() > 0

    def has_tag(self, tag):
        for datum in self._data_set(tag):
            if datum.key() == tag:
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
        assert False, 'Invalid tag ' + tag

    def save(self):
        self._image.setExifData(self._exifData)
        self._image.setIptcData(self._iptcData)
        self._image.setXmpData(self._xmpData)
        self._image.writeMetadata()
        return True

    def clear_maker_note(self):
        self.clear_tag('Exif.Image.Make')
        self._image.setExifData(self._exifData)
        self._image.writeMetadata()
        self._image.readMetadata()
        self._exifData = self._image.exifData()
        self.clear_tag('Exif.Photo.MakerNote')
        self._image.setExifData(self._exifData)
        self._exifData = self._image.exifData()

    @staticmethod
    def create_sc(path, image_md):
        # 10 is the image type defined in xmpsidecar.hpp
        # python-exiv2 doesn't wrap every image format
        image = exiv2.ImageFactory.create(10, path)
        image.writeMetadata()

    def merge_sc(self, other):
        pass
