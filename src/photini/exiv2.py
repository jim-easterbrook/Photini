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
import random
import shutil
import string
import sys

import exiv2
if exiv2.__version__ < '0.8.3':
    raise ImportError(
        'exiv2 version {} is less than 0.8.3'.format(exiv2.__version__))

logger = logging.getLogger(__name__)

exiv2_version_info = tuple([int(x) for x in exiv2.versionString().split('.')])
exiv2_version = 'python-exiv2 {}, exiv2 {}'.format(
    exiv2.__version__, exiv2.versionString())


class MetadataHandler(object):
    @classmethod
    def initialise(cls, config_store, verbosity):
        exiv2.LogMsg.setLevel(
            max(exiv2.LogMsg.debug, min(exiv2.LogMsg.error, 4 - verbosity)))
        exiv2.XmpParser.initialize()
        if exiv2_version_info >= (0, 27, 4):
            exiv2.enableBMFF(config_store.get('metadata', 'enable_bmff', False))
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
            'exif': self._image.checkMode(exiv2.MetadataId.Exif),
            'iptc': self._image.checkMode(exiv2.MetadataId.Iptc),
            'xmp': self._image.checkMode(exiv2.MetadataId.Xmp),
            }
        self.read_only = not any(
            [x in (exiv2.AccessMode.Write, exiv2.AccessMode.ReadWrite)
             for x in access_mode.values()])
        self.mime_type = self._image.mimeType()
        self.xmp_only = self.mime_type in (
            'application/rdf+xml', 'application/postscript')
        # Don't use Exiv2's converted values when accessing Xmp files
        if self.xmp_only:
            self.clear_exif()
            self.clear_iptc()
        # transcode any non utf-8 strings (Xmp is always utf-8)
        encodings = self.encodings
        for data in self._exifData, self._iptcData:
            for datum in data:
                if datum.typeId() not in (exiv2.TypeId.asciiString,
                                          exiv2.TypeId.string):
                    continue
                value = datum.toString()
                raw_value = value.encode('utf-8', errors='surrogateescape')
                for encoding in self.encodings:
                    try:
                        new_value = raw_value.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                    if encoding != 'utf-8':
                        logger.info('%s: transcoded %s from %s',
                                    os.path.basename(self._path),
                                    str(datum.key()), encoding)
                    break
                else:
                    logger.warning('%s: failed to transcode %s',
                                   os.path.basename(self._path),
                                   str(datum.key()))
                    new_value = raw_value.decode('utf-8', errors='replace')
                datum.setValue(new_value)
            iptc_charset = self.get_iptc_encoding()
            if iptc_charset in ('utf-8', 'ascii'):
                # no need to translate anything
                return
            if iptc_charset:
                encodings = [iptc_charset]

    def clear_exif(self):
        self._exifData.clear()
        self._image.clearExifData()

    def clear_iptc(self):
        self._iptcData.clear()
        self._image.clearIptcData()

    def get_exif_tags(self):
        for datum in self._exifData:
            yield datum.key()

    def get_iptc_tags(self):
        for datum in self._iptcData:
            yield datum.key()

    def get_xmp_tags(self):
        for datum in self._xmpData:
            yield datum.key()

    @classmethod
    def open_old(cls, *arg, **kw):
        try:
            return cls(*arg, **kw)
        except exiv2.AnyError:
            # expected if unrecognised file format
            return None
        except Exception as ex:
            logger.exception(ex)
            return None

    def get_exif_thumbnail(self):
        thumb = exiv2.ExifThumb(self._exifData)
        data = thumb.copy()
        if data:
            return bytes(data)
        return None

    def set_exif_thumbnail_from_buffer(self, buffer):
        thumb = exiv2.ExifThumb(self._exifData)
        thumb.setJpegThumbnail(buffer)

    def get_exif_comment(self, datum):
        value = exiv2.CommentValue(datum.value()).comment()
        raw_value = value.encode('utf-8', errors='surrogateescape').strip(b'\0')
        try:
            return raw_value.decode('utf-8')
        except UnicodeDecodeError:
            logger.error(
                '%s: %s: %d bytes binary data will be deleted when metadata'
                ' is saved',
                os.path.basename(self._path), datum.key(), datum.size())
        return None

    def get_exif_value(self, tag):
        if tag not in self._exifData:
            return None
        datum = self._exifData[tag]
        if tag in ('Exif.Canon.ModelID', 'Exif.CanonCs.LensType',
                   'Exif.Image.XPTitle', 'Exif.Image.XPComment',
                   'Exif.Image.XPAuthor', 'Exif.Image.XPKeywords',
                   'Exif.Image.XPSubject', 'Exif.NikonLd1.LensIDNumber',
                   'Exif.NikonLd2.LensIDNumber',
                   'Exif.NikonLd3.LensIDNumber', 'Exif.Pentax.ModelID'):
            # use Exiv2's "interpreted string"
            return datum._print()
        type_id = datum.typeId()
        if tag == 'Exif.Photo.UserComment' and type_id in (
                exiv2.TypeId.comment, exiv2.TypeId.undefined):
            return self.get_exif_comment(datum)
        if type_id == exiv2.TypeId.signedRational:
            value = exiv2.RationalValue(datum.value())
        elif type_id == exiv2.TypeId.unsignedRational:
            value = exiv2.URationalValue(datum.value())
        elif type_id == exiv2.TypeId.signedShort:
            value = exiv2.ShortValue(datum.value())
        elif type_id == exiv2.TypeId.unsignedShort:
            value = exiv2.UShortValue(datum.value())
        elif type_id == exiv2.TypeId.signedLong:
            value = exiv2.LongValue(datum.value())
        elif type_id == exiv2.TypeId.unsignedLong:
            value = exiv2.ULongValue(datum.value())
        else:
            # probably a string value, so use the string
            return datum.toString()
        if len(value) > 1:
            return list(value)
        return value[0]

    def get_iptc_value(self, tag):
        result = None
        # findKey gets first matching datum and returns an iterator
        # which we use to search the rest of the data
        for datum in self._iptcData.findKey(exiv2.IptcKey(tag)):
            if result:
                if datum.key() == tag:
                    result.append(datum.toString())
            else:
                result = datum.toString()
                if not exiv2.IptcDataSets.dataSetRepeatable(
                                        datum.tag(), datum.record()):
                    break
                result = [result]
        return result

    def get_xmp_value(self, tag):
        if tag not in self._xmpData:
            return None
        datum = self._xmpData[tag]
        type_id = datum.typeId()
        if type_id == exiv2.TypeId.xmpText:
            return datum.toString()
        if type_id == exiv2.TypeId.langAlt:
            value = exiv2.LangAltValue(datum.value())
            # concatenate all values, with language identifiers
            result = []
            for lang, text in value.items():
                if lang == 'x-default':
                    result = [text] + result
                else:
                    result.append('[{}] {}'.format(lang, text))
            return '; '.join(result)
        return list(exiv2.XmpArrayValue(datum.value()))

    def get_raw_value(self, tag):
        if tag not in self._iptcData:
            return None
        datum = self._iptcData[tag]
        return datum.toString().encode('utf-8', errors='surrogateescape')

    def get_preview_thumbnail(self):
        preview_manager = exiv2.PreviewManager(self._image)
        props = preview_manager.getPreviewProperties()
        if not props:
            return None
        # get largest acceptable image
        idx = len(props)
        while idx > 0:
            idx -= 1
            if max(props[idx].width_, props[idx].height_) <= 640:
                break
        image = preview_manager.getPreviewImage(props[idx])
        return bytes(image.copy())

    def get_preview_imagedims(self):
        preview_manager = exiv2.PreviewManager(self._image)
        props = preview_manager.getPreviewProperties()
        if not props:
            return 0, 0
        return props[-1].width_, props[-1].height_

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
                if type_id not in (exiv2.TypeId.xmpAlt, exiv2.TypeId.xmpBag,
                                   exiv2.TypeId.xmpSeq):
                    if container == 'Xmp.xmp.Thumbnails':
                        type_id = exiv2.TypeId.xmpAlt
                    else:
                        type_id = exiv2.TypeId.xmpSeq
                self._xmpData[container] = exiv2.XmpArrayValue(type_id)
        datum = self._xmpData[tag]
        if isinstance(value, str):
            # set a single value
            datum.setValue(value)
            return
        # set a list/tuple of values
        type_id = datum.typeId()
        if type_id == exiv2.TypeId.invalidTypeId:
            key = exiv2.XmpKey(datum.key())
            type_id = exiv2.XmpProperties.propertyType(key)
        if type_id in (exiv2.TypeId.xmpAlt, exiv2.TypeId.xmpBag,
                       exiv2.TypeId.xmpSeq):
            xmp_value = exiv2.XmpArrayValue(type_id)
            for sub_value in value:
                xmp_value.read(sub_value)
        else:
            return
        datum.setValue(xmp_value)

    def clear_tag(self, tag):
        data = self._data_set(tag)
        while tag in data:
            del data[tag]
        # possibly delete Xmp container(s)
        for sep in ('/', '['):
            if sep not in tag:
                return
            container = tag.split(sep)[0] + sep
            for datum in data:
                if datum.key().startswith(container):
                    # container is not empty
                    return
            container = tag.split(sep)[0]
            if container in data:
                del data[container]

    def has_iptc(self):
        return self._iptcData.count() > 0

    def has_tag(self, tag):
        data = self._data_set(tag)
        return tag in data

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
        return self.save_file(self._path)

    def save_file(self, path):
        if path == self._path:
            image = self._image
        else:
            image = exiv2.ImageFactory.open(path)
            image.readMetadata()
            image.setExifData(self._exifData)
            image.setIptcData(self._iptcData)
            image.setXmpData(self._xmpData)
            if self._image.iccProfileDefined():
                # copy ICC profile
                image.setIccProfile(self._image.iccProfile())
        try:
            image.writeMetadata()
        except exiv2.AnyError as ex:
            logger.error(str(ex))
            return False
        except Exception as ex:
            logger.exception(ex)
            return False
        return True

    def clear_maker_note(self):
        self.clear_tag('Exif.Image.Make')
        self._image.writeMetadata()
        self._image.readMetadata()
        self._exifData = self._image.exifData()
        self.clear_tag('Exif.Photo.MakerNote')

    @staticmethod
    def create_sc(path, image_md):
        image = exiv2.ImageFactory.create(exiv2.ImageType.xmp, path)
        image.writeMetadata()
        if image_md:
            # let exiv2 copy as much metadata as it can into sidecar
            image.setMetadata(image_md._image)
            image.writeMetadata()

    def merge_sc(self, other):
        # open other image and read its metadata
        image = exiv2.ImageFactory.open(other._path)
        image.readMetadata()
        # copy Exif data inferred by libexiv2
        for o_datum in image.exifData():
            tag = o_datum.key()
            s_datum = self._exifData[tag]
            s_datum.setValue(o_datum.value())
        # copy Xmp data, except inferred Exif data
        for o_datum in image.xmpData():
            tag = o_datum.key()
            if tag.startswith('Xmp.xmp.Thumbnails'):
                continue
            ns = tag.split('.')[1]
            if ns in ('exif', 'exifEX', 'tiff', 'aux'):
                # exiv2 will already have supplied the equivalent Exif tag
                pass
            s_datum = self._xmpData[tag]
            s_datum.setValue(o_datum.value())
