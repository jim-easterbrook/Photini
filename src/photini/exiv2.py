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

import codecs
import locale
import logging
import os
import random
import shutil
import string
import sys

import exiv2

logger = logging.getLogger(__name__)

exiv2_version_info = tuple(map(int, exiv2.version().split('.')))
exiv2_version = 'python-exiv2 {}, exiv2 {}'.format(
    exiv2.__version__, exiv2.version())


class MetadataHandler(object):
    @classmethod
    def initialise(cls, config_store, verbosity):
        exiv2.LogMsg.setLevel(
            max(exiv2.LogMsg.debug, min(exiv2.LogMsg.error, 4 - verbosity)))
        exiv2.XmpParser.initialize()
        if config_store and exiv2_version_info >= (0, 27, 4):
            exiv2.enableBMFF(config_store.get('metadata', 'enable_bmff', False))
        # Recent versions of Exiv2 have these namespaces defined, but
        # older versions may not recognise them. The xapGImg URL is
        # invalid, but Photini doesn't write xapGImg so it doesn't
        # matter. Exiv2 already has the Iptc4xmpExt namespace, but calls
        # it iptcExt which causes problems saving tags like
        # 'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:City'.
        # Re-registering it under its full name means I have to use
        # 'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:City' instead.
        registered = exiv2.XmpProperties.registeredNamespaces()
        for prefix, ns in (
                ('exifEX',      'http://cipa.jp/exif/1.0/'),
                ('Iptc4xmpExt', 'http://iptc.org/std/Iptc4xmpExt/2008-02-29/'),
                ('plus',        'http://ns.useplus.org/ldf/xmp/1.0/'),
                ('xapGImg',     'http://ns.adobe.com/xxx/'),
                ('xmpGImg',     'http://ns.adobe.com/xap/1.0/g/img/'),
                ('xmpRights',   'http://ns.adobe.com/xap/1.0/rights/'),
                ):
            if prefix == 'Iptc4xmpExt' or prefix not in registered:
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
        
    def __init__(self, path, buf=None):
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
                # no need to transcode anything
                return
            if iptc_charset:
                encodings = [iptc_charset]

    def get_iptc_encoding(self):
        # IPTC-IIM uses ISO/IEC 2022 escape sequences to set the
        # character set. These are very flexible, and it's not obvious
        # which sequences, if any, are ever used in practice. The
        # sequence is escape, one or more intermediate bytes, then a
        # final byte.
        iptc_charset_code = self.get_raw_value('Iptc.Envelope.CharacterSet')
        if not iptc_charset_code or len(iptc_charset_code) < 3:
            return None
        if iptc_charset_code[0] != 0x1b:
            # first byte isn't escape
            return None
        intermediate = iptc_charset_code[1:-1]
        final = iptc_charset_code[-1]
        if len(intermediate) == 1:
            if intermediate[0] == 0x25:
                # "other coding systems"
                if final == 0x47:
                    return 'utf-8'
            if intermediate[0] in (0x28, 0x29, 0x2a, 0x2b):
                # "94-character set"
                if final == 0x4e:
                    return 'koi8_r'
                return 'ascii'
            if intermediate[0] in (0x2c, 0x2d, 0x2e, 0x2f):
                # "96-character set"
                if final == 0x40:
                    return 'iso_8859_5'
                if final == 0x41:
                    return 'iso_8859_1'
                if final == 0x42:
                    return 'iso_8859_2'
                if final == 0x43:
                    return 'iso_8859_3'
                if final == 0x44:
                    return 'iso_8859_4'
                if final == 0x46:
                    return 'iso_8859_7'
                if final == 0x47:
                    return 'iso_8859_6'
                if final == 0x48:
                    return 'iso_8859_8'
        elif len(intermediate) == 2:
            # "multi-byte character set"
            if (intermediate[0] == 0x24
                    and intermediate[1] in (0x28, 0x29, 0x2a, 0x2b)):
                if final == 0x42:
                    return 'euc_jp'
            if intermediate == b'\x25\x2f':
                if final == 0x46:
                    return 'utf-32-be'
                if final == 0x4c:
                    return 'utf-16-be'
        logger.error('Unrecognised IPTC character set %s',
                     repr(iptc_charset_code))
        return None

    def set_iptc_encoding(self):
        # escape % G, or \x1b \x25 \x47, selects UTF-8
        self.set_value('Iptc.Envelope.CharacterSet', '\x1b%G')

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
    def open_old(cls, *arg, quiet=False, **kw):
        try:
            return cls(*arg, **kw)
        except exiv2.Exiv2Error as ex:
            # expected if unrecognised file format
            if not quiet:
                logger.warning(str(ex))
            return None
        except Exception as ex:
            logger.exception(ex)
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
            return dict(exiv2.LangAltValue(datum.value()))
        return list(exiv2.XmpArrayValue(datum.value()))

    def get_raw_value(self, tag):
        if tag not in self._iptcData:
            return None
        datum = self._iptcData[tag]
        return datum.toString().encode('utf-8', errors='surrogateescape')

    def get_exif_thumbnails(self):
        # try normal thumbnail
        thumb = exiv2.ExifThumb(self._exifData)
        data = thumb.copy()
        if data:
            logger.info('%s: trying thumbnail', os.path.basename(self._path))
            yield bytes(data), 'thumbnail'
        # try preview images
        preview_manager = exiv2.PreviewManager(self._image)
        props = preview_manager.getPreviewProperties()
        if not props:
            return
        # get largest acceptable images
        idx = len(props)
        while idx > 0:
            idx -= 1
            if max(props[idx].width_, props[idx].height_) <= 640:
                logger.info('%s: trying preview %d',
                            os.path.basename(self._path), idx)
                image = preview_manager.getPreviewImage(props[idx])
                yield bytes(image.copy()), 'preview ' + str(idx)

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

    # maximum length of Iptc data
    _max_bytes = {
        'Iptc.Application2.Byline'             :   32,
        'Iptc.Application2.BylineTitle'        :   32,
        'Iptc.Application2.Caption'            : 2000,
        'Iptc.Application2.City'               :   32,
        'Iptc.Application2.Contact'            :  128,
        'Iptc.Application2.Copyright'          :  128,
        'Iptc.Application2.CountryCode'        :    3,
        'Iptc.Application2.CountryName'        :   64,
        'Iptc.Application2.Credit'             :   32,
        'Iptc.Application2.Headline'           :  256,
        'Iptc.Application2.Keywords'           :   64,
        'Iptc.Application2.ObjectName'         :   64,
        'Iptc.Application2.Program'            :   32,
        'Iptc.Application2.ProgramVersion'     :   10,
        'Iptc.Application2.ProvinceState'      :   32,
        'Iptc.Application2.SpecialInstructions':  256,
        'Iptc.Application2.SubLocation'        :   32,
        'Iptc.Envelope.CharacterSet'           :   32,
        }

    @classmethod
    def max_bytes(cls, name):
        # try IPTC-IIM key
        tag = 'Iptc.Application2.' + name
        if tag in cls._max_bytes:
            return cls._max_bytes[tag]
        # try Photini metadata item
        result = None
        if name in cls._tag_list:
            for mode, tag in cls._tag_list[name]:
                if mode == 'WA' and tag in cls._max_bytes:
                    if result:
                        result = min(result, cls._max_bytes[tag])
                    else:
                        result = cls._max_bytes[tag]
        return result

    @classmethod
    def truncate_iptc(cls, tag, value):
        if tag in cls._max_bytes:
            value = value.encode('utf-8')[:cls._max_bytes[tag]]
            value = value.decode('utf-8')
        return value

    def set_iptc_value(self, tag, value):
        # clear any existing values (which might be repeated)
        self.clear_tag(tag)
        if not value:
            return
        if isinstance(value, str):
            # set a single value
            datum = self._iptcData[tag]
            datum.setValue(self.truncate_iptc(tag, value))
            return
        # set a list/tuple of values
        key = exiv2.IptcKey(tag)
        for sub_value in value:
            datum = exiv2.Iptcdatum(key)
            datum.setValue(self.truncate_iptc(tag, sub_value))
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
        # set a list/tuple/dict of values
        type_id = datum.typeId()
        if type_id == exiv2.TypeId.invalidTypeId:
            type_id = exiv2.XmpProperties.propertyType(exiv2.XmpKey(tag))
        if type_id in (exiv2.TypeId.xmpAlt, exiv2.TypeId.xmpBag,
                       exiv2.TypeId.xmpSeq):
            datum.setValue(exiv2.XmpArrayValue(value, type_id))
        elif type_id == exiv2.TypeId.langAlt:
            datum.setValue(exiv2.LangAltValue(value))
        else:
            logger.error('%s: %s: setting type "%s" from %s',
                         os.path.basename(self._path), tag,
                         exiv2.TypeId(type_id).name, type(value))
            datum.setValue(';'.join(value))

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

    def _data_set(self, tag):
        family = tag.split('.')[0]
        if family == 'Exif':
            return self._exifData
        if family == 'Iptc':
            return self._iptcData
        return self._xmpData

    def save_file(self, path=None):
        if path:
            image = exiv2.ImageFactory.open(path)
            image.readMetadata()
            image.setExifData(self._exifData)
            image.setIptcData(self._iptcData)
            image.setXmpData(self._xmpData)
            if self._image.iccProfileDefined():
                # copy ICC profile
                image.setIccProfile(self._image.iccProfile())
        else:
            image = self._image
        try:
            image.writeMetadata()
        except exiv2.Exiv2Error as ex:
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
                continue
            s_datum = self._xmpData[tag]
            s_datum.setValue(o_datum.value())
