##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-23  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
from collections import defaultdict
import logging
import os
import re

import chardet
import exiv2

from photini.pyqt import QtCore, QtGui, using_pyside

logger = logging.getLogger(__name__)

exiv2_version = 'python-exiv2 {}, exiv2 {}'.format(
    exiv2.__version__, exiv2.version())


class MetadataHandler(object):
    # static data about keys known to Exiv2
    data_sets = {}
    md_info = {}

    @classmethod
    def get_info(cls, tag_name):
        if tag_name in cls.md_info:
            return cls.md_info[tag_name]
        family, group, tag = tag_name.split('.')
        if family == 'Iptc':
            if group not in cls.data_sets:
                # get static info once, as it's computed each time
                if group == 'Application2':
                    cls.data_sets[group] = exiv2.IptcDataSets.application2RecordList()
                elif group == 'Envelope':
                    cls.data_sets[group] = exiv2.IptcDataSets.envelopeRecordList()
            for data_set in cls.data_sets[group]:
                # case insensitive as Iptc Sublocation is SubLocation in Exiv2
                if data_set['name'].lower() == tag.lower():
                    cls.md_info[tag_name] = data_set
                    break
        if tag_name not in cls.md_info:
            cls.md_info[tag_name] = {}
        return cls.md_info[tag_name]

    @classmethod
    def initialise(cls, config_store, verbosity):
        level = min(exiv2.LogMsg.Level.error, 4 - verbosity)
        level = max(exiv2.LogMsg.Level.debug, level)
        exiv2.LogMsg.setLevel(exiv2.LogMsg.Level(level))
        exiv2.XmpParser.initialize()
        if exiv2.__version_tuple__ < (0, 17) and exiv2.testVersion(0, 27, 4):
            exiv2.enableBMFF(True)
        if config_store:
            config_store.delete('metadata', 'enable_bmff')
        # Recent versions of Exiv2 have these namespaces defined, but
        # older versions may not recognise them. The xapGImg URL is
        # invalid, but Photini doesn't write xapGImg so it doesn't
        # matter.
        registered = exiv2.XmpProperties.registeredNamespaces()
        for prefix, ns in (
                ('exifEX',      'http://cipa.jp/exif/1.0/'),
                ('plus',        'http://ns.useplus.org/ldf/xmp/1.0/'),
                ('xmp',         'http://ns.adobe.com/xap/1.0/'),
                ('xapGImg',     'http://ns.adobe.com/xxx/'),
                ('xmpGImg',     'http://ns.adobe.com/xap/1.0/g/img/'),
                ('xmpRights',   'http://ns.adobe.com/xap/1.0/rights/'),
                ):
            if prefix not in registered:
                exiv2.XmpProperties.registerNs(ns, prefix)

    def __init__(self, path=None, buf=None):
        self._path = path
        # read metadata
        if buf:
            self._image = exiv2.ImageFactory.open(buf)
        else:
            self._image = exiv2.ImageFactory.open(self._path)
        if self._path:
            self._name = os.path.basename(self._path)
        else:
            self._name = 'data'
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
        if self.mime_type == 'image/generic':
            self.mime_type = None
        self.xmp_only = self.mime_type in (
            'application/rdf+xml', 'application/postscript')
        # Don't use Exiv2's converted values when accessing Xmp files
        if self.xmp_only:
            self.clear_exif()
            self.clear_iptc()
        # remove old software tag
        tag = 'Exif.Image.ProcessingSoftware'
        if (tag in self._exifData
                and str(self._exifData[tag].value()).startswith('Photini')):
            del self._exifData[tag]
        # transcode any non utf-8 strings (Xmp is always utf-8)
        encodings = []
        iptc_charset = self.get_iptc_encoding()
        if iptc_charset not in ('utf-8', 'ascii', None):
            iptc_charset = codecs.lookup(iptc_charset).name
            logger.info('%s: IPTC character set %s', self._name, iptc_charset)
            encodings.append(iptc_charset)
        for data, set_value in ((self._exifData, self.set_exif_value),
                                (self._iptcData, self.set_iptc_value)):
            new_data = defaultdict(list)
            for datum in data:
                if datum.typeId() not in (exiv2.TypeId.asciiString,
                                          exiv2.TypeId.string):
                    continue
                key = datum.key()
                if key in ('Iptc.Envelope.CharacterSet', 'Exif.Image.IPTCNAA'):
                    continue
                if '.0x' in key:
                    # unknown key type
                    continue
                raw_value = datum.value().data()
                if self.decode_string(key, raw_value, 'utf-8') is not None:
                    # no need to do anything
                    continue
                for encoding in encodings:
                    value = self.decode_string(key, raw_value, encoding)
                    if value:
                        break
                else:
                    encoding = chardet.detect(bytearray(raw_value))['encoding']
                    if encoding:
                        try:
                            encoding = codecs.lookup(encoding).name
                        except LookupError:
                            encoding = None
                    if encoding:
                        logger.info("%s: detected character set '%s'",
                                    self._name, encoding)
                        value = self.decode_string(key, raw_value, encoding)
                    else:
                        value = None
                    if value:
                        encodings.append(encoding)
                    else:
                        logger.warning('%s: failed to transcode %s',
                                       self._name, key)
                        value = bytes(raw_value).decode(
                            'utf-8', errors='replace')
                new_data[key].append(value)
            for key, value in new_data.items():
                if len(value) == 1:
                    set_value(key, value[0])
                else:
                    set_value(key, value)
        # assume no XMP thumbnails to replace or append
        self._xmp_thumb_idx = None
        # mapping Xmp data to type_id, initialised with some that exiv2
        # doesn't know, extended with ones read from files
        self._xmp_type_id = {
            'Xmp.iptc.AltTextAccessibility': exiv2.TypeId.langAlt,
            'Xmp.iptc.ExtDescrAccessibility': exiv2.TypeId.langAlt,
            'Xmp.iptcExt.ImageRegion': exiv2.TypeId.xmpBag,
            'Iptc4xmpExt:LocationName': exiv2.TypeId.langAlt,
            'Iptc4xmpExt:Name': exiv2.TypeId.langAlt,
            'Iptc4xmpExt:rCtype': exiv2.TypeId.xmpBag,
            'Iptc4xmpExt:rRole': exiv2.TypeId.xmpBag,
            'Iptc4xmpExt:rbVertices': exiv2.TypeId.xmpSeq,
            'Xmp.xmp.Thumbnails': exiv2.TypeId.xmpAlt,
            }

    def set_xmp_type(self, key, value):
        if value == exiv2.TypeId.xmpText:
            return
        sub_key = key.split('/')[-1]
        if sub_key in self._xmp_type_id:
            if value == self._xmp_type_id[sub_key]:
                return
            logger.warning('altered type_id %s', sub_key)
        self._xmp_type_id[sub_key] = value

    def get_xmp_type(self, key):
        value = exiv2.XmpProperties.propertyType(exiv2.XmpKey(key))
        if value != exiv2.TypeId.xmpText:
            # exiv2 knows what it should be
            self.set_xmp_type(key, value)
            return value
        sub_key = key.split('/')[-1]
        if sub_key in self._xmp_type_id:
            return self._xmp_type_id[sub_key]
        return exiv2.TypeId.xmpText

    def decode_string(self, tag, raw_value, encoding):
        try:
            result = codecs.decode(raw_value, encoding=encoding)
        except UnicodeDecodeError:
            return None
        if encoding != 'utf-8':
            logger.info(
                "%s: transcoded %s from '%s'", self._name, tag, encoding)
        return result

    def get_iptc_encoding(self):
        # IPTC-IIM uses ISO/IEC 2022 escape sequences to set the
        # character set. These are very flexible, and it's not obvious
        # which sequences, if any, are ever used in practice. The
        # sequence is escape, one or more intermediate bytes, then a
        # final byte.
        if 'Iptc.Envelope.CharacterSet' not in self._iptcData:
            return None
        iptc_charset_code = self._iptcData[
            'Iptc.Envelope.CharacterSet'].value().data()
        if len(iptc_charset_code) >= 3 and iptc_charset_code[0] == 0x1b:
            intermediate = iptc_charset_code[1:-1]
            final = iptc_charset_code[-1]
            if intermediate == b'\x25':
                # "other coding systems"
                if final == 0x47:
                    return 'utf-8'
            if intermediate in (b'\x28', b'\x29', b'\x2a', b'\x2b'):
                # "94-character set"
                if final == 0x4e:
                    return 'koi8_r'
                return 'ascii'
            if intermediate in (b'\x2c', b'\x2d', b'\x2e', b'\x2f'):
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
            # "multi-byte character set"
            if intermediate in (b'\x24\x28', b'\x24\x29',
                                b'\x24\x2a', b'\x24\x2b'):
                if final == 0x42:
                    return 'euc_jp'
            if intermediate == b'\x25\x2f':
                if final == 0x46:
                    return 'utf-32-be'
                if final == 0x4c:
                    return 'utf-16-be'
        logger.error('Unrecognised IPTC character set %s',
                     repr(bytes(iptc_charset_code)))
        return None

    def set_iptc_encoding(self):
        # escape % G, or \x1b \x25 \x47, selects UTF-8
        self.set_iptc_value('Iptc.Envelope.CharacterSet', '\x1b%G')

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
    def open_old(cls, path, *arg, quiet=False, **kw):
        try:
            return cls(path, *arg, **kw)
        except exiv2.Exiv2Error as ex:
            # expected if unrecognised file format
            if quiet:
                logger.info(str(ex))
            else:
                logger.warning(str(ex))
            return None
        except Exception as ex:
            logger.error('Exception opening %s', path)
            logger.exception(ex)
            return None

    def set_exif_thumbnail_from_buffer(self, buffer):
        thumb = exiv2.ExifThumb(self._exifData)
        thumb.setJpegThumbnail(buffer)

    def get_exif_comment(self, tag, value):
        if isinstance(value, exiv2.CommentValue):
            data = value.data()
            charset = value.charsetId()
        else:
            data = bytearray(len(value))
            value.copy(data, exiv2.ByteOrder.invalidByteOrder)
            if data[:5] == b'ASCII':
                charset = exiv2.CommentValue.CharsetId.ascii
            elif data[:3] == b'JIS':
                charset = exiv2.CommentValue.CharsetId.jis
            elif data[:7] == b'UNICODE':
                charset = exiv2.CommentValue.CharsetId.unicode
            else:
                charset = exiv2.CommentValue.CharsetId.undefined
        # ignore Exiv2's comment decoding, Python is better at unicode
        if not any(data):
            return None
        raw_value = data[8:]
        if charset == exiv2.CommentValue.CharsetId.ascii:
            encodings = ('ascii',)
        elif charset == exiv2.CommentValue.CharsetId.jis:
            # Exif standard says JIS X208-1990, but doesn't say what encoding
            encodings = ('iso2022_jp', 'euc_jp', 'shift_jis', 'cp932')
        elif charset == exiv2.CommentValue.CharsetId.unicode:
            # Exif refers to 1991 unicode, which predates UTF-8.
            # Check for BOM.
            if raw_value[:3] == b'\xef\xbb\xbf':
                raw_value = raw_value[3:]
                encodings = ('utf_8',)
            elif raw_value[:2] == b'\xff\xfe':
                raw_value = raw_value[2:]
                encodings = ('utf_16_le',)
            elif raw_value[:2] == b'\xfe\xff':
                raw_value = raw_value[2:]
                encodings = ('utf_16_be',)
            else:
                # If no BOM, utf-16 should be bigendian so try that first.
                encodings = ('utf_16_be', 'utf_16_le', 'utf_8')
        else:
            encodings = ()
            if charset != exiv2.CommentValue.CharsetId.undefined:
                logger.warning('%s: %s: unknown charset', self._name, tag)
                raw_value = data
        result = None
        for encoding in encodings:
            result = self.decode_string(tag, raw_value, encoding)
            if result:
                break
        else:
            detector = chardet.universaldetector.UniversalDetector()
            for i in range(0, len(raw_value), 100):
                detector.feed(raw_value[i:i+100])
                if detector.done:
                    break
            detector.close()
            encoding = detector.result['encoding']
            if encoding:
                result = self.decode_string(tag, raw_value, encoding)
        if result and '\0' in result:
            # terminating NULLs are allowed
            result = result.strip('\0')
            if '\0' in result:
                # NULLs within the string are not allowed
                result = None
        if not result:
            logger.error(
                '%s: %s: %d bytes binary data will be deleted when metadata'
                ' is saved', self._name, tag, value.size())
            return None
        return result

    def get_exif_value(self, tag):
        try:
            key = exiv2.ExifKey(tag)
        except exiv2.Exiv2Error:
            # old versions of libexiv2 don't recognise newer tags
            return None
        datum = self._exifData.findKey(key)
        if datum == self._exifData.end():
            return None
        if tag in ('Exif.Canon.ModelID', 'Exif.CanonCs.LensType',
                   'Exif.Canon.SerialNumber', 'Exif.CanonLe.LensSerialNumber',
                   'Exif.Image.XPTitle', 'Exif.Image.XPComment',
                   'Exif.Image.XPAuthor', 'Exif.Image.XPKeywords',
                   'Exif.Image.XPSubject', 'Exif.NikonLd1.LensIDNumber',
                   'Exif.Minolta.LensID', 'Exif.Nikon3.LensType',
                   'Exif.NikonLd2.LensIDNumber', 'Exif.NikonLd3.LensIDNumber',
                   'Exif.NikonLd4.LensIDNumber', 'Exif.OlympusEq.LensType',
                   'Exif.Olympus2.CameraID',
                   'Exif.Panasonic.InternalSerialNumber',
                   'Exif.Pentax.LensType', 'Exif.Pentax.ModelID',
                   'Exif.PentaxDng.LensType', 'Exif.PentaxDng.ModelID',
                   'Exif.Sony1.LensID', 'Exif.Sony1.SonyModelID',
                   'Exif.Sony2.LensID', 'Exif.Sony2.SonyModelID'):
            # use Exiv2's "interpreted string"
            if exiv2.__version_tuple__ >= (0, 16, 2):
                return datum.print(self._exifData)
            else:
                return datum._print(self._exifData)
        value = datum.value()
        if tag in ('Exif.Photo.UserComment',
                   'Exif.GPSInfo.GPSProcessingMethod'):
            return self.get_exif_comment(tag, value)
        if isinstance(value, exiv2.AsciiValue):
            return value.toString()
        if isinstance(value, exiv2.DataValue):
            result = bytearray(value.size())
            value.copy(result, exiv2.ByteOrder.invalidByteOrder)
            return result
        if isinstance(value, (exiv2.RationalValue, exiv2.URationalValue,
                              exiv2.ShortValue, exiv2.UShortValue,
                              exiv2.LongValue, exiv2.ULongValue)):
            if len(value) > 1:
                return list(value)
            if len(value) == 0:
                return None
            return value[0]
        logger.warning(
            '%s: %s: reading %s as string', self._name, tag, type(value))
        return value.toString()

    def decode_iptc_value(self, datum):
        type_id = datum.typeId()
        value = datum.value()
        if type_id == exiv2.TypeId.date:
            return value.getDate()
        if type_id == exiv2.TypeId.time:
            return value.getTime()
        return value.toString()

    def get_iptc_value(self, tag):
        result = None
        # findKey gets first matching datum and returns an iterator
        # which we use to search the rest of the data
        for datum in self._iptcData.findKey(exiv2.IptcKey(tag)):
            if result is None:
                # first datum
                result = self.decode_iptc_value(datum)
                if not exiv2.IptcDataSets.dataSetRepeatable(
                                        datum.tag(), datum.record()):
                    break
                result = [result]
            elif datum.key() == tag:
                result.append(self.decode_iptc_value(datum))
        return result

    _re_key_parts = re.compile(r'(.*?)(\[(\d+)\])?(/(.*))?$')

    def set_item(self, result, key, value):
        # break exiv2 tags into component parts
        match = self._re_key_parts.match(key)
        root = match.group(1)
        idx = match.group(3)
        node = match.group(5)
        if node:
            if idx:
                self.set_item(result[root][int(idx)-1], node, value)
            else:
                self.set_item(result[root], node, value)
        elif idx:
            result[root].append(value)
        else:
            result[root] = value

    def get_xmp_value(self, tag):
        # XMP has a nested structure of arbitrary depth. Exiv2 converts
        # this to "flat" tag names. This method converts back to nested
        # dicts and lists.
        result = {}
        for datum in self._xmpData:
            key = datum.key()
            if not key.startswith(tag):
                continue
            value = datum.value()
            type_id = value.typeId()
            if type_id == exiv2.TypeId.langAlt:
                value = dict(value)
            elif type_id in (exiv2.TypeId.xmpAlt, exiv2.TypeId.xmpBag,
                             exiv2.TypeId.xmpSeq):
                value = list(value)
            elif tag == 'Xmp.xmp.Thumbnails' and ':image' in key:
                # don't copy large string to unicode
                value = value.data()
            elif value.xmpStruct() == exiv2.XmpValue.XmpStruct.xsStruct:
                value = {}
            else:
                array_type = value.xmpArrayType()
                if array_type == exiv2.XmpValue.XmpArrayType.xaNone:
                    value = str(value)
                else:
                    value = []
                    type_id = {
                        exiv2.XmpValue.XmpArrayType.xaAlt: exiv2.TypeId.xmpAlt,
                        exiv2.XmpValue.XmpArrayType.xaBag: exiv2.TypeId.xmpBag,
                        exiv2.XmpValue.XmpArrayType.xaSeq: exiv2.TypeId.xmpSeq,
                        }[array_type]
            self.set_xmp_type(key, type_id)
            self.set_item(result, key, value)
        if tag in result:
            return result[tag]
        return None

    def select_exif_thumbnail(self):
        if self.xmp_only:
            return
        # try normal thumbnail
        thumb = exiv2.ExifThumb(self._exifData)
        data = thumb.copy()
        if data:
            logger.info('%s: trying thumbnail', self._name)
            yield data, 'thumbnail'
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
                logger.info('%s: trying preview %dx%d', self._name,
                            props[idx].width_, props[idx].height_)
                image = preview_manager.getPreviewImage(props[idx])
                yield image, 'preview ' + str(idx)

    def select_xmp_thumbnail(self, file_value):
        if not file_value:
            return
        # new thumbnail will be appended
        self._xmp_thumb_idx = len(file_value) + 1
        # make list of all thumbnails
        candidates = []
        for n, value in enumerate(file_value):
            candidate = dict((k.split(':')[1], v) for (k, v) in value.items())
            candidate['width'] = int(candidate['width'])
            candidate['height'] = int(candidate['height'])
            if max(candidate['width'], candidate['height']) == 160:
                # new thumbnail will replace this one
                self._xmp_thumb_idx = n + 1
                # try this one before any others
                logger.info('%s: trying xmp thumb %dx%d', self._name,
                            candidate['width'], candidate['height'])
                yield candidate['image'], 'xmp thumb ' + str(n)
            else:
                candidates.append(candidate)
        # Xmp spec says first thumbnail is default, so just try them in order
        for n, candidate in enumerate(candidates):
            logger.info('%s: trying xmp thumb %dx%d', self._name,
                        candidate['width'], candidate['height'])
            yield candidate['image'], 'xmp thumb ' + str(n)

    def get_previews(self):
        preview_manager = exiv2.PreviewManager(self._image)
        props = preview_manager.getPreviewProperties()
        idx = len(props)
        while idx:
            idx -= 1
            yield preview_manager.getPreviewImage(props[idx])

    def get_preview_imagedims(self):
        preview_manager = exiv2.PreviewManager(self._image)
        props = preview_manager.getPreviewProperties()
        for p in props:
            yield p.width_, p.height_

    def get_image_pixmap(self, orientation):
        mime_type = self.mime_type.split('/')
        if mime_type[0] != 'image':
            return None
        # In raw formats the image is often larger than the final area,
        # so we accept any preview or image that's up to 2% smaller than
        # the reported image size.
        image_dims = [self._image.pixelWidth(), self._image.pixelHeight()]
        if not all(image_dims):
            return None
        image_dims.sort()
        if mime_type[1].startswith('x-') or mime_type[1] == 'tiff':
            # probably a raw image format, try largest preview first
            preview_manager = exiv2.PreviewManager(self._image)
            props = preview_manager.getPreviewProperties()
            idx = len(props)
            while idx:
                idx -= 1
                preview_dims = [props[idx]['width'], props[idx]['height']]
                preview_dims.sort()
                if min(preview_dims[0] / image_dims[0],
                       preview_dims[1] / image_dims[1]) < 0.98:
                    break
                data = preview_manager.getPreviewImage(props[idx])
                buf = QtCore.QBuffer()
                # PySide insists on bytes, can't use buffer interface
                if using_pyside:
                    data = bytes(data)
                buf.setData(data)
                reader = QtGui.QImageReader(buf)
                reader.setAutoTransform(False)
                pixmap = QtGui.QPixmap.fromImageReader(reader)
                if pixmap.isNull():
                    logger.error('%s: %s', self._name, reader.errorString())
                    continue
                preview_dims = [pixmap.width(), pixmap.height()]
                return pixmap
        reader = QtGui.QImageReader(self._path)
        reader.setAutoTransform(False)
        pixmap = QtGui.QPixmap.fromImageReader(reader)
        if pixmap.isNull():
            logger.error('%s: %s', self._name, reader.errorString())
            return None
        if orientation and mime_type[1] in ('x-fuji-raf', 'x-kodak-dcr'):
            # image data still gets orientation applied somewhere
            transform = orientation.get_transform(inverted=True)
            pixmap = pixmap.transformed(transform)
        preview_dims = [pixmap.width(), pixmap.height()]
        preview_dims.sort()
        if min(preview_dims[0] / image_dims[0],
               preview_dims[1] / image_dims[1]) < 0.98:
            return None
        crop = [None, None, self._image.pixelWidth(), self._image.pixelHeight()]
        # look for Exif crop data
        for datum in self._exifData:
            key = str(datum.key())
            family, group, tag = key.split('.')
            if tag in ('DefaultCropOrigin', 'DefaultCropSize'):
                pos = self.get_exif_value(
                    '.'.join((family, group, 'DefaultCropOrigin')))
                if pos:
                    crop[0:2] = pos
                size = self.get_exif_value(
                    '.'.join((family, group, 'DefaultCropSize')))
                if size:
                    crop[2:4] = size
                break
        x, y, w_crop, h_crop = crop
        w_image, h_image = pixmap.width(), pixmap.height()
        if w_crop > w_image or h_crop > h_image:
            pass
        elif w_crop < w_image or h_crop < h_image:
            x = x or ((w_image - w_crop) // 2)
            y = y or ((h_image - h_crop) // 2)
            pixmap = pixmap.copy(x, y, w_crop, h_crop)
        return pixmap

    def set_exif_value(self, tag, value):
        if not value:
            self.clear_exif_tag(tag)
            return
        key = exiv2.ExifKey(tag)
        type_id = key.defaultTypeId()
        if type_id == exiv2.TypeId.unsignedByte:
            value = exiv2.DataValue(
                value, exiv2.ByteOrder.invalidByteOrder, type_id)
        elif type_id == exiv2.TypeId.asciiString:
            value = exiv2.AsciiValue(value)
        elif type_id == exiv2.TypeId.comment:
            # only comment value Photini writes is GPS processing method
            # which is certain to be ASCII
            value = 'charset=Ascii ' + value
            value = exiv2.CommentValue(value)
        elif type_id == exiv2.TypeId.unsignedShort:
            value = exiv2.UShortValue(value)
        elif type_id == exiv2.TypeId.unsignedLong:
            value = exiv2.ULongValue(value)
        elif type_id == exiv2.TypeId.unsignedRational:
            if isinstance(value, (list, tuple)):
                value = exiv2.URationalValue(
                    [(x.numerator, x.denominator) for x in value])
            else:
                value = exiv2.URationalValue(
                    [(value.numerator, value.denominator)])
        else:
            # unhandled type, use the string representation
            logger.warning('%s: %s: writing %s type as string',
                           self._name, tag, exiv2.TypeInfo.typeName(type_id))
        datum = self._exifData[tag]
        datum.setValue(value)

    @classmethod
    def iptc_max_len(cls, tag_name):
        data_set = cls.get_info(tag_name)
        if 'maxbytes' in data_set:
            return data_set['maxbytes']
        return None

    @classmethod
    def max_bytes(cls, name):
        result = []
        for mode, tag in cls._tag_list[name]:
            if mode == 'WA' and tag.split('.')[0] == 'Iptc':
                if tag in cls._multi_tags:
                    for sub_tag in cls._multi_tags[tag]:
                        if sub_tag:
                            result.append(cls.iptc_max_len(sub_tag))
                else:
                    result.append(cls.iptc_max_len(tag))
        result = [x for x in result if x]
        if result:
            return min(result)
        return None

    @classmethod
    def truncate_iptc(cls, tag, value):
        max_bytes = cls.iptc_max_len(tag)
        if max_bytes:
            value = value.encode('utf-8')[:max_bytes]
            value = value.decode('utf-8', errors='ignore')
        return value

    def set_iptc_value(self, tag, value):
        if not value:
            self.clear_iptc_tag(tag)
            return
        # make list of values
        key = exiv2.IptcKey(tag)
        type_id = exiv2.IptcDataSets.dataSetType(key.tag(), key.record())
        if type_id == exiv2.TypeId.date:
            values = [exiv2.DateValue(*value)]
        elif type_id == exiv2.TypeId.time:
            values = [exiv2.TimeValue(*value)]
        elif isinstance(value, (list, tuple)):
            values = [self.truncate_iptc(tag, x) for x in value]
        else:
            values = [self.truncate_iptc(tag, value)]
        # update or delete existing values
        datum = self._iptcData.findKey(key)
        while datum != self._iptcData.end():
            if datum.key() == tag:
                if values:
                    datum.setValue(values.pop(0))
                else:
                    datum = self._iptcData.erase(datum)
                    continue
            next(datum)
        # append remaining values
        while values:
            datum = exiv2.Iptcdatum(key)
            datum.setValue(values.pop(0))
            if self._iptcData.add(datum) != 0:
                logger.error('%s: duplicated tag %s', self._name, tag)
                return

    def set_xmp_value(self, tag, value):
        if not value:
            self.clear_xmp_tag(tag)
            return
        type_id = self.get_xmp_type(tag)
        if type_id == exiv2.TypeId.langAlt:
            self._xmpData[tag] = exiv2.LangAltValue(value)
        elif isinstance(value, dict):
            # clear any existing struct members
            self.clear_xmp_tag(tag, children_only=True)
            # create struct
            tmp = exiv2.XmpTextValue()
            tmp.setXmpStruct()
            self._xmpData[tag] = tmp
            # set struct members
            for k, v in value.items():
                self.set_xmp_value('{}/{}'.format(tag, k), v)
        elif not isinstance(value, (list, tuple)):
            # simple value
            self._xmpData[tag] = exiv2.XmpTextValue(str(value))
        elif not isinstance(value[0], dict):
            # simple array value
            self._xmpData[tag] = exiv2.XmpArrayValue(value, type_id)
        else:
            # clear any existing array elements
            self.clear_xmp_tag(tag, children_only=True)
            # create array
            array_type = {
                exiv2.TypeId.xmpAlt: exiv2.XmpValue.XmpArrayType.xaAlt,
                exiv2.TypeId.xmpBag: exiv2.XmpValue.XmpArrayType.xaBag,
                exiv2.TypeId.xmpSeq: exiv2.XmpValue.XmpArrayType.xaSeq,
                }[type_id]
            tmp = exiv2.XmpTextValue()
            tmp.setXmpArrayType(array_type)
            self._xmpData[tag] = tmp
            # set array elements
            for idx, element in enumerate(value):
                self.set_xmp_value('{}[{}]'.format(tag, idx+1), element)

    def clear_exif_tag(self, tag):
        datum = self._exifData.findKey(exiv2.ExifKey(tag))
        if datum != self._exifData.end():
            self._exifData.erase(datum)

    def clear_iptc_tag(self, tag):
        # findKey gets first matching datum and returns an iterator
        # which we use to search the rest of the data
        datum = self._iptcData.findKey(exiv2.IptcKey(tag))
        while datum != self._iptcData.end():
            if datum.key() == tag:
                datum = self._iptcData.erase(datum)
            else:
                next(datum)

    def clear_xmp_tag(self, tag, children_only=False):
        key = exiv2.XmpKey(tag)
        datum = self._xmpData.findKey(key)
        if datum == self._xmpData.end():
            return datum
        value = datum.value()
        type_id = value.typeId()
        if type_id == exiv2.TypeId.xmpText:
            # can be a struct or array
            if value.xmpStruct() == exiv2.XmpValue.XmpStruct.xsStruct:
                self.clear_xmp_struct(tag)
            elif value.xmpArrayType() != exiv2.XmpValue.XmpArrayType.xaNone:
                self.clear_xmp_array(tag)
        if children_only:
            return datum
        return self._xmpData.erase(datum)

    def clear_xmp_struct(self, tag):
        tag += '/'
        datum = self._xmpData.begin()
        while datum != self._xmpData.end():
            key = datum.key()
            if key.startswith(tag):
                datum = self.clear_xmp_tag(key)
            else:
                next(datum)

    def clear_xmp_array(self, tag):
        idx = 0
        while True:
            idx += 1
            key = exiv2.XmpKey('{}[{}]'.format(tag, idx))
            if self._xmpData.findKey(key) == self._xmpData.end():
                return
            while self.clear_xmp_tag(str(key)) != self._xmpData.end():
                pass

    def has_iptc(self):
        return self._iptcData.count() > 0

    def has_exif_tag(self, tag):
        return tag in self._exifData

    def save_file(self):
        try:
            self._image.writeMetadata()
        except exiv2.Exiv2Error as ex:
            logger.error(str(ex))
            return False
        except Exception as ex:
            logger.exception(ex)
            return False
        return True

    def clear_gps(self):
        for data in self._exifData, self._xmpData:
            pos = data.begin()
            while pos != data.end():
                tag = pos.key().split('.')[2]
                if tag.startswith('GPS'):
                    pos = data.erase(pos)
                else:
                    next(pos)

    def clear_maker_note(self):
        self.clear_exif_tag('Exif.Image.Make')
        self._image.writeMetadata()
        self._image.readMetadata()
        self._exifData = self._image.exifData()
        self.clear_exif_tag('Exif.Photo.MakerNote')

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
