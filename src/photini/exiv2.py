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

from __future__ import unicode_literals

from contextlib import contextmanager
import codecs
import locale
import logging
import os
import random
import shutil
import string
import sys

from photini import __version__
from photini.gi import gexiv2_version, GLib, GObject, GExiv2, using_pgi

logger = logging.getLogger(__name__)

# pydoc gi.repository.GExiv2.Metadata is useful to see methods available

XMP_WRAPPER = '''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 4.4.0-Exiv2">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      {}/>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''

# Recent versions of Exiv2 have these namespaces defined, but older
# versions may not recognise them. The xapGImg URL is invalid, but
# Photini doesn't write xapGImg so it doesn't matter.
for prefix, name in (
        ('exifEX',    'http://cipa.jp/exif/1.0/'),
        ('xapGImg',   'http://ns.adobe.com/xxx/'),
        ('xmpGImg',   'http://ns.adobe.com/xap/1.0/g/img/'),
        ('xmpRights', 'http://ns.adobe.com/xap/1.0/rights/')):
    GExiv2.Metadata.register_xmp_namespace(name, prefix)

# Gexiv2 won't register the 'Iptc4xmpExt' namespace as its abbreviated
# version 'iptcExt' is already defined. This kludge registers it by
# reading some data with the full namespace
data = XMP_WRAPPER.format(
    'xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/"')
# open the data to register the namespace
GExiv2.Metadata().open_buf(data.encode('utf-8'))
del data


@contextmanager
def temp_rename(path):
    # Rename path to an ascii-safe file, further up the directory path
    # if necessary, then restore to the original name and directory on
    # completion. Only needed for workaround for bug in GExiv2 on
    # Windows
    dir_name, file_name = os.path.split(path)
    while dir_name.encode('ascii', 'replace').decode('ascii') != dir_name:
        dir_name = os.path.dirname(dir_name)
    while True:
        tmp_path = os.path.join(dir_name, file_name)
        if (tmp_path.encode('ascii', 'replace').decode('ascii') == tmp_path
                and not os.path.exists(tmp_path)):
            break
        file_name = ''.join(
            random.choices(string.ascii_lowercase, k=8)) + '.tmp'
    try:
        logger.warning('Renaming %s to %s', path, tmp_path)
        shutil.move(path, tmp_path)
        yield tmp_path
    finally:
        logger.warning('Renaming %s to %s', tmp_path, path)
        shutil.move(tmp_path, path)


class Exiv2Metadata(GExiv2.Metadata):
    def __init__(self, path, buf=None):
        super(Exiv2Metadata, self).__init__()
        self._path = path
        # workaround for bug in GExiv2 on Windows
        # https://gitlab.gnome.org/GNOME/gexiv2/-/issues/59
        self._gexiv_unsafe = False
        if sys.platform == 'win32' and gexiv2_version <= (0, 12, 1):
            try:
                self._path.encode('ascii')
            except UnicodeEncodeError:
                self._gexiv_unsafe = True
        if self._gexiv_unsafe and not buf:
            with open(self._path, 'rb') as f:
                buf = f.read()
        if buf:
            # read metadata from buffer
            self.open_buf(buf)
        else:
            # read metadata from file
            self.open_path(self._path)
        self.read_only = not any((self.get_supports_exif(),
                                  self.get_supports_iptc(),
                                  self.get_supports_xmp()))
        self.xmp_only = self.get_mime_type() in (
            'application/rdf+xml', 'application/postscript')
        # Don't use Exiv2's converted values when accessing Xmp files
        if self.xmp_only:
            self.clear_exif()
            self.clear_iptc()
        # any sub images?
        self.ifd_list = ['Image']
        if self.has_tag('Exif.Image.SubIFDs'):
            subIFDs = self.get_tag_string('Exif.Image.SubIFDs').split()
            self.ifd_list += ['SubImage{}'.format(1 + i)
                              for i in range(len(subIFDs))]
        largest = 0
        main_ifd = None
        for ifd in self.ifd_list:
            w = self.get_tag_string('Exif.{}.ImageWidth'.format(ifd))
            h = self.get_tag_string('Exif.{}.ImageLength'.format(ifd))
            if not (w and h):
                continue
            size = max(int(w), int(h))
            if size > largest:
                largest = size
                main_ifd = ifd
        if main_ifd:
            self.ifd_list.remove(main_ifd)
            self.ifd_list = [main_ifd] + self.ifd_list
        # make list of possible character encodings
        self._encodings = ['utf-8', 'iso8859-1', 'ascii']
        char_set = locale.getdefaultlocale()[1]
        if char_set:
            try:
                name = codecs.lookup(char_set).name
                if name not in self._encodings:
                    self._encodings.append(name)
            except LookupError:
                pass

    def get_exif_thumbnail(self):
        # try normal thumbnail
        data = super(Exiv2Metadata, self).get_exif_thumbnail()
        if using_pgi and isinstance(data, tuple):
            # get_exif_thumbnail returns (OK, data) tuple
            data = data[data[0]]
        if data:
            return data
        # try subimage thumbnails
        if self.has_tag('Exif.Thumbnail.SubIFDs'):
            subIFDs = self.get_tag_string('Exif.Thumbnail.SubIFDs').split()
            for idx in range(len(subIFDs)):
                ifd = 'SubThumb{}'.format(1 + idx)
                start = self.get_tag_string(
                    'Exif.{}.JPEGInterchangeFormat'.format(ifd))
                length = self.get_tag_string(
                    'Exif.{}.JPEGInterchangeFormatLength'.format(ifd))
                if not (start and length):
                    continue
                start = int(start)
                length = int(length)
                with open(self._path, 'rb') as f:
                    buf = f.read(start + length)
                return buf[start:]
        # try "main" image
        w = self.get_tag_string('Exif.Image.ImageWidth')
        h = self.get_tag_string('Exif.Image.ImageLength')
        if w and h and max(int(w), int(h)) <= 512:
            with open(self._path, 'rb') as f:
                buf = f.read()
            return buf
        return None

    def _decode_string(self, value):
        if not value:
            return value
        for encoding in self._encodings:
            try:
                result = value.decode(encoding)
                logger.info('Decoded %s string "%s"', encoding, result)
                return result
            except UnicodeDecodeError:
                continue
        return value.decode('utf-8', 'replace')

    def clear_value(self, tag, idx=1, place_holder=False):
        if tag in self._multi_tags:
            for t in self._multi_tags[tag]:
                sub_tag = t.format(idx=idx)
                self._clear_value(sub_tag)
            if place_holder:
                self.set_tag_string(sub_tag, ' ')
            return
        self._clear_value(tag)

    def _clear_value(self, tag):
        if not (tag and self.has_tag(tag)):
            return
        self.clear_tag(tag)

    def get_raw(self, tag):
        if not self.has_tag(tag):
            return None
        try:
            if gexiv2_version < (0, 10, 3):
                try:
                    result = self.get_tag_string(tag)
                except UnicodeDecodeError:
                    return None
                if not result:
                    return None
                if self.get_tag_type(tag) == 'Byte':
                    # data is a string of space separated numbers
                    return bytes(map(int, result.split()))
                if self.get_tag_type(tag) == 'Comment':
                    # GExiv2 adds original charset information
                    parts = result.split('"')
                    if parts[0] == 'charset=':
                        result = parts[2][1:]
                return result.encode('ascii', 'backslashreplace')
            result = self.get_tag_raw(tag).get_data()
            if not result:
                return None
            if isinstance(result, list):
                # pgi returns a list of ints, or ctypes pointers in some versions
                if isinstance(result[0], int):
                    result = bytearray(result)
                else:
                    # some other type we can't handle
                    logger.info('Unknown data type %s in tag %s',
                                type(result[0]), tag)
                    return None
        except Exception as ex:
            logger.exception(ex)
            return None
        return result

    _charset_map = {
        'ascii'  : 'ascii',
        'unicode': 'utf-16-be',
        'jis'    : 'euc_jp',
        }

    def get_multi_group(self, tag_group):
        result = []
        for idx in range(1, 20):
            value = [self.get_string(x.format(idx=idx)) for x in tag_group]
            if not any(value):
                return result
            result.append(value)

    def get_group(self, tag_group):
        if 'idx' in tag_group[0]:
            return self.get_multi_group(tag_group)
        return [self.get_string(x) for x in tag_group]

    def get_string(self, tag):
        if not (tag and self.has_tag(tag)):
            return None
        if tag in ('Exif.Canon.ModelID', 'Exif.CanonCs.LensType',
                   'Exif.Image.XPTitle', 'Exif.Image.XPComment',
                   'Exif.Image.XPAuthor', 'Exif.Image.XPKeywords',
                   'Exif.Image.XPSubject',
                   'Exif.NikonLd1.LensIDNumber', 'Exif.NikonLd2.LensIDNumber',
                   'Exif.NikonLd3.LensIDNumber', 'Exif.Pentax.ModelID'):
            return self.get_tag_interpreted_string(tag)
        if tag == 'Exif.Photo.UserComment':
            # first 8 bytes should be the encoding charset
            result = self.get_raw(tag)
            if not result:
                return None
            try:
                charset = result[:8].decode(
                    'ascii', 'replace').strip('\x00').lower()
                if charset in self._charset_map:
                    result = result[8:].decode(self._charset_map[charset])
                elif charset == '':
                    result = self._decode_string(result[8:])
                else:
                    result = result.decode('ascii', 'replace')
                if result:
                    result = result.strip('\x00')
                if not result:
                    return None
                return result
            except UnicodeDecodeError:
                logger.error('%s: %d bytes binary data will be deleted'
                             ' when metadata is saved', tag, len(result))
                raise
        try:
            return self.get_tag_string(tag)
        except UnicodeDecodeError:
            pass
        # attempt to read raw data instead
        result = self.get_raw(tag)
        if not result:
            return None
        return self._decode_string(result).strip('\x00')

    def get_multiple(self, tag):
        if not (tag and self.has_tag(tag)):
            return []
        try:
            return self.get_tag_multiple(tag)
        except UnicodeDecodeError:
            pass
        # attempt to read raw data instead, only gets the first value
        result = self.get_raw(tag)
        if not result:
            return []
        logger.info('potential multi-data loss %s %s',
                    os.path.basename(self._path), tag)
        return [self._decode_string(result).strip('\x00')]

    def set_group(self, tag, value, idx=1):
        sub_tag = self._multi_tags[tag][0].format(idx=idx)
        if any(value) and '[' in sub_tag:
            # create XMP array
            for t in self.get_xmp_tags():
                if t.startswith(tag):
                    # container already exists
                    break
            else:
                if gexiv2_version >= (0, 10, 3):
                    type_ = self.get_tag_type(tag)
                    if type_ == 'XmpBag':
                        type_ = GExiv2.StructureType.BAG
                    elif type_ == 'XmpSeq':
                        type_ = GExiv2.StructureType.SEQ
                    else:
                        type_ = GExiv2.StructureType.ALT
                    self.set_xmp_tag_struct(tag, type_)
                else:
                    self.set_tag_string(tag, '')
        for sub_tag, sub_value in zip(self._multi_tags[tag], value):
            self.set_string(sub_tag.format(idx=idx), sub_value)

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

    def set_string(self, tag, value):
        if not tag:
            return
        if not value:
            self._clear_value(tag)
            return
        if tag in self._max_bytes:
            value = value.encode('utf-8')[:self._max_bytes[tag]]
            value = value.decode('utf-8', errors='ignore')
        self.set_tag_string(tag, value)

    def set_multiple(self, tag, value):
        if not tag:
            return
        if not value:
            self._clear_value(tag)
            return
        if self.is_iptc_tag(tag) and tag in self._max_bytes:
            value = [x.encode('utf-8')[:self._max_bytes[tag]] for x in value]
            value = [x.decode('utf-8') for x in value]
        self.set_tag_multiple(tag, value)

    def save(self, file_times=None, force_iptc=False):
        if self.read_only:
            return False
        if force_iptc:
            self.set_string('Iptc.Envelope.CharacterSet',
                             self._iptc_encodings['utf-8'][0].decode('ascii'))
        else:
            self.clear_iptc()
        if self.xmp_only:
            self.clear_exif()
            self.clear_iptc()
        try:
            if self._gexiv_unsafe:
                with temp_rename(self._path) as tmp_file:
                    self.save_file(tmp_file)
            else:
                self.save_file(self._path)
            if file_times:
                os.utime(self._path, file_times)
        except GLib.GError as ex:
            logger.error(str(ex))
            return False
        except Exception as ex:
            logger.exception(ex)
            return False
        # check that data really was saved
        OK = True
        saved_tags = self.open_old(self._path).get_all_tags()
        for tag in self.get_all_tags():
            if tag in saved_tags:
                continue
            if tag in ('Exif.Image.GPSTag', 'Exif.MakerNote.ByteOrder',
                       'Exif.MakerNote.Offset', 'Exif.Photo.MakerNote'):
                # some tags disappear with good reason
                continue
            family, group, tagname = tag.split('.')
            if family == 'Exif' and group[:5] in (
                    'Canon', 'Casio', 'Fujif', 'Minol', 'Nikon', 'Olymp',
                    'Panas', 'Penta', 'Samsu', 'Sigma', 'Sony1'):
                # maker note tags are often not saved
                logger.warning(
                    '%s: tag not saved: %s', os.path.basename(self._path), tag)
                continue
            logger.error(
                '%s: tag not saved: %s', os.path.basename(self._path), tag)
            OK = False
        return OK

    def get_all_tags(self):
        result = []
        if not self.xmp_only:
            result += self.get_exif_tags()
            result += self.get_iptc_tags()
        result += self.get_xmp_tags()
        return result

    # some tags are always read & written in groups, but are represented
    # by a single name
    _multi_tags = {
        'Exif.Canon.LensModel': ('', 'Exif.Canon.LensModel'),
        'Exif.Canon.ModelID': (
            '', 'Exif.Canon.ModelID', 'Exif.Canon.SerialNumber'),
        'Exif.CanonCs.LensType': ('', 'Exif.CanonCs.LensType'),
        'Exif.Fujifilm.SerialNumber': ('', '', 'Exif.Fujifilm.SerialNumber'),
        'Exif.GPSInfo.GPSAltitude': (
            'Exif.GPSInfo.GPSAltitude', 'Exif.GPSInfo.GPSAltitudeRef'),
        'Exif.GPSInfo.GPSCoordinates': (
            'Exif.GPSInfo.GPSLatitude', 'Exif.GPSInfo.GPSLatitudeRef',
            'Exif.GPSInfo.GPSLongitude', 'Exif.GPSInfo.GPSLongitudeRef'),
        'Exif.Image.DateTime': ('Exif.Image.DateTime', 'Exif.Photo.SubSecTime'),
        'Exif.Image.DateTimeOriginal': ('Exif.Image.DateTimeOriginal', ''),
        'Exif.Image.FNumber': (
            'Exif.Image.FNumber', 'Exif.Image.ApertureValue'),
        'Exif.Image.Make': (
            'Exif.Image.Make', 'Exif.Image.Model',
            'Exif.Photo.BodySerialNumber'),
        'Exif.Image.UniqueCameraModel': (
            '', 'Exif.Image.UniqueCameraModel', 'Exif.Image.CameraSerialNumber'),
        'Exif.Nikon3.SerialNumber': ('', '', 'Exif.Nikon3.SerialNumber'),
        'Exif.NikonLd1.LensIDNumber': ('', 'Exif.NikonLd1.LensIDNumber'),
        'Exif.NikonLd2.LensIDNumber': ('', 'Exif.NikonLd2.LensIDNumber'),
        'Exif.NikonLd3.LensIDNumber': ('', 'Exif.NikonLd3.LensIDNumber'),
        'Exif.OlympusEq.CameraType': (
            '', 'Exif.OlympusEq.CameraType', 'Exif.OlympusEq.SerialNumber'),
        'Exif.OlympusEq.LensModel': (
            '', 'Exif.OlympusEq.LensModel', 'Exif.OlympusEq.LensSerialNumber'),
        'Exif.Pentax.ModelID': (
            '', 'Exif.Pentax.ModelID', 'Exif.Pentax.SerialNumber'),
        'Exif.Photo.DateTimeDigitized': (
            'Exif.Photo.DateTimeDigitized', 'Exif.Photo.SubSecTimeDigitized'),
        'Exif.Photo.DateTimeOriginal': (
            'Exif.Photo.DateTimeOriginal', 'Exif.Photo.SubSecTimeOriginal'),
        'Exif.Photo.FNumber': (
            'Exif.Photo.FNumber', 'Exif.Photo.ApertureValue'),
        'Exif.Photo.FocalPlaneResolution': (
            'Exif.Photo.FocalPlaneXResolution',
            'Exif.Photo.FocalPlaneYResolution',
            'Exif.Photo.FocalPlaneResolutionUnit'),
        'Exif.Photo.LensMake': (
            'Exif.Photo.LensMake', 'Exif.Photo.LensModel',
            'Exif.Photo.LensSerialNumber'),
        'Exif.Photo.PixelDimensions': (
            'Exif.Photo.PixelXDimension', 'Exif.Photo.PixelYDimension'),
        'Exif.Thumbnail': (
            'Exif.Thumbnail.ImageWidth', 'Exif.Thumbnail.ImageLength',
            'Exif.Thumbnail.Compression'),
        'Exif.{ifd}.FocalPlaneResolution': (
            'Exif.{ifd}.FocalPlaneXResolution',
            'Exif.{ifd}.FocalPlaneYResolution',
            'Exif.{ifd}.FocalPlaneResolutionUnit'),
        'Exif.{ifd}.ImageDimensions': (
            'Exif.{ifd}.ImageWidth', 'Exif.{ifd}.ImageLength'),
        'Iptc.Application2.Contact': ('Iptc.Application2.Contact',),
        'Iptc.Application2.DateCreated': (
            'Iptc.Application2.DateCreated', 'Iptc.Application2.TimeCreated'),
        'Iptc.Application2.DigitizationDate': (
            'Iptc.Application2.DigitizationDate',
            'Iptc.Application2.DigitizationTime'),
        'Iptc.Application2.Location': (
            'Iptc.Application2.SubLocation', 'Iptc.Application2.City',
            'Iptc.Application2.ProvinceState', 'Iptc.Application2.CountryName',
            'Iptc.Application2.CountryCode'),
        'Iptc.Application2.Program': (
            'Iptc.Application2.Program', 'Iptc.Application2.ProgramVersion'),
        'Xmp.aux.Lens': ('', 'Xmp.aux.Lens'),
        'Xmp.aux.SerialNumber': ('', '', 'Xmp.aux.SerialNumber'),
        'Xmp.exif.FNumber': ('Xmp.exif.FNumber', 'Xmp.exif.ApertureValue'),
        'Xmp.exif.FocalPlaneResolution': ('Xmp.exif.FocalPlaneXResolution',
                                          'Xmp.exif.FocalPlaneYResolution',
                                          'Xmp.exif.FocalPlaneResolutionUnit'),
        'Xmp.exif.GPSAltitude': (
            'Xmp.exif.GPSAltitude', 'Xmp.exif.GPSAltitudeRef'),
        'Xmp.exif.GPSCoordinates': (
            'Xmp.exif.GPSLatitude', 'Xmp.exif.GPSLongitude'),
        'Xmp.exif.PixelDimensions': (
            'Xmp.exif.PixelXDimension', 'Xmp.exif.PixelYDimension'),
        'Xmp.exifEX.LensMake': (
            'Xmp.exifEX.LensMake', 'Xmp.exifEX.LensModel',
            'Xmp.exifEX.LensSerialNumber'),
        'Xmp.iptc.CreatorContactInfo': (
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiAdrExtadr',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiAdrCity',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiAdrCtry',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiEmailWork',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiTelWork',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiAdrPcode',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiAdrRegion',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiUrlWork',
            ),
        'Xmp.iptc.Location': (
            'Xmp.iptc.Location', 'Xmp.photoshop.City', 'Xmp.photoshop.State',
            'Xmp.photoshop.Country', 'Xmp.iptc.CountryCode'),
        'Xmp.iptcExt.LocationShown': (
            'Xmp.iptcExt.LocationShown[{idx}]/Iptc4xmpExt:Sublocation',
            'Xmp.iptcExt.LocationShown[{idx}]/Iptc4xmpExt:City',
            'Xmp.iptcExt.LocationShown[{idx}]/Iptc4xmpExt:ProvinceState',
            'Xmp.iptcExt.LocationShown[{idx}]/Iptc4xmpExt:CountryName',
            'Xmp.iptcExt.LocationShown[{idx}]/Iptc4xmpExt:CountryCode',
            'Xmp.iptcExt.LocationShown[{idx}]/Iptc4xmpExt:WorldRegion',
            'Xmp.iptcExt.LocationShown[{idx}]/Iptc4xmpExt:LocationId'),
        'Xmp.iptcExt.LocationCreated': (
            'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:Sublocation',
            'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:City',
            'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:ProvinceState',
            'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:CountryName',
            'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:CountryCode',
            'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:WorldRegion',
            'Xmp.iptcExt.LocationCreated[1]/Iptc4xmpExt:LocationId'),
        'Xmp.tiff.ImageDimensions': (
            'Xmp.tiff.ImageWidth', 'Xmp.tiff.ImageLength'),
        'Xmp.xmp.Thumbnails': (
            'Xmp.xmp.Thumbnails[1]/xmpGImg:width',
            'Xmp.xmp.Thumbnails[1]/xmpGImg:height',
            'Xmp.xmp.Thumbnails[1]/xmpGImg:format',
            'Xmp.xmp.Thumbnails[1]/xmpGImg:image'),
        'Xmp.xmp.ThumbnailsXap': (
            'Xmp.xmp.Thumbnails[1]/xapGImg:width',
            'Xmp.xmp.Thumbnails[1]/xapGImg:height',
            'Xmp.xmp.Thumbnails[1]/xapGImg:format',
            'Xmp.xmp.Thumbnails[1]/xapGImg:image'),
        }

    # Mapping of tags to Photini data fields Each field has a list of
    # (mode, tag) pairs. The mode is a string containing the write mode
    # (WA (always), WX (if Exif not supported), W0 (clear the tag), or
    # WN (never). The order of the tags sets the precedence when values
    # conflict.
    _tag_list = {
        'altitude'       : (('WA', 'Exif.GPSInfo.GPSAltitude'),
                            ('WX', 'Xmp.exif.GPSAltitude')),
        'aperture'       : (('WA', 'Exif.Photo.FNumber'),
                            ('W0', 'Exif.Image.FNumber'),
                            ('WX', 'Xmp.exif.FNumber')),
        'camera_model'   : (('WA', 'Exif.Image.Make'),
                            ('WN', 'Exif.Image.UniqueCameraModel'),
                            ('WN', 'Exif.Canon.ModelID'),
                            ('WN', 'Exif.Fujifilm.SerialNumber'),
                            ('WN', 'Exif.Nikon3.SerialNumber'),
                            ('WN', 'Exif.OlympusEq.CameraType'),
                            ('WN', 'Exif.Pentax.ModelID'),
                            ('WN', 'Xmp.aux.SerialNumber')),
        'contact_info'   : (('WA', 'Xmp.iptc.CreatorContactInfo'),
                            ('WA', 'Iptc.Application2.Contact')),
        'copyright'      : (('WA', 'Exif.Image.Copyright'),
                            ('WA', 'Xmp.dc.rights'),
                            ('W0', 'Xmp.tiff.Copyright'),
                            ('WA', 'Iptc.Application2.Copyright')),
        'creator'        : (('WA', 'Exif.Image.Artist'),
                            ('W0', 'Exif.Image.XPAuthor'),
                            ('WA', 'Xmp.dc.creator'),
                            ('W0', 'Xmp.tiff.Artist'),
                            ('WA', 'Iptc.Application2.Byline')),
        'creator_title'  : (('WA', 'Xmp.photoshop.AuthorsPosition'),
                            ('WA', 'Iptc.Application2.BylineTitle')),
        'credit_line'    : (('WA', 'Xmp.photoshop.Credit'),
                            ('WA', 'Iptc.Application2.Credit')),
        'date_digitised' : (('WA', 'Exif.Photo.DateTimeDigitized'),
                            ('WA', 'Xmp.xmp.CreateDate'),
                            ('W0', 'Xmp.exif.DateTimeDigitized'),
                            ('WA', 'Iptc.Application2.DigitizationDate')),
        'date_modified'  : (('WA', 'Exif.Image.DateTime'),
                            ('WA', 'Xmp.xmp.ModifyDate'),
                            ('W0', 'Xmp.tiff.DateTime')),
        'date_taken'     : (('WA', 'Exif.Photo.DateTimeOriginal'),
                            ('W0', 'Exif.Image.DateTimeOriginal'),
                            ('WA', 'Xmp.photoshop.DateCreated'),
                            ('W0', 'Xmp.exif.DateTimeOriginal'),
                            ('WA', 'Iptc.Application2.DateCreated')),
        'description'    : (('WA', 'Exif.Image.ImageDescription'),
                            ('W0', 'Exif.Image.XPComment'),
                            ('W0', 'Exif.Image.XPSubject'),
                            ('W0', 'Exif.Photo.UserComment'),
                            ('WA', 'Xmp.dc.description'),
                            ('W0', 'Xmp.exif.UserComment'),
                            ('W0', 'Xmp.tiff.ImageDescription'),
                            ('WA', 'Iptc.Application2.Caption')),
        'focal_length'   : (('WA', 'Exif.Photo.FocalLength'),
                            ('W0', 'Exif.Image.FocalLength'),
                            ('WX', 'Xmp.exif.FocalLength')),
        'focal_length_35': (('WA', 'Exif.Photo.FocalLengthIn35mmFilm'),
                            ('WX', 'Xmp.exif.FocalLengthIn35mmFilm')),
        'instructions'   : (('WA', 'Xmp.photoshop.Instructions'),
                            ('WA', 'Iptc.Application2.SpecialInstructions')),
        'keywords'       : (('WA', 'Xmp.dc.subject'),
                            ('WA', 'Iptc.Application2.Keywords'),
                            ('W0', 'Exif.Image.XPKeywords')),
        'latlong'        : (('WA', 'Exif.GPSInfo.GPSCoordinates'),
                            ('WX', 'Xmp.exif.GPSCoordinates')),
        'lens_model'     : (('WA', 'Exif.Photo.LensMake'),
                            ('WX', 'Xmp.exifEX.LensMake'),
                            ('WN', 'Exif.Canon.LensModel'),
                            ('WN', 'Exif.CanonCs.LensType'),
                            ('WN', 'Exif.OlympusEq.LensModel'),
                            ('WN', 'Exif.NikonLd1.LensIDNumber'),
                            ('WN', 'Exif.NikonLd2.LensIDNumber'),
                            ('WN', 'Exif.NikonLd3.LensIDNumber'),
                            ('W0', 'Xmp.aux.Lens')),
        'lens_spec'      : (('WA', 'Exif.Photo.LensSpecification'),
                            ('WX', 'Xmp.exifEX.LensSpecification'),
                            ('W0', 'Exif.Image.LensInfo'),
                            ('WN', 'Exif.CanonCs.Lens'),
                            ('WN', 'Exif.Nikon3.Lens')),
        'location_shown' : (('WA', 'Xmp.iptcExt.LocationShown'),),
        'location_taken' : (('WA', 'Xmp.iptcExt.LocationCreated'),
                            ('WA', 'Xmp.iptc.Location'),
                            ('WA', 'Iptc.Application2.Location')),
        'orientation'    : (('WA', 'Exif.Image.Orientation'),
                            ('WX', 'Xmp.tiff.Orientation')),
        'rating'         : (('WA', 'Xmp.xmp.Rating'),
                            ('W0', 'Exif.Image.Rating'),
                            ('W0', 'Exif.Image.RatingPercent'),
                            ('W0', 'Xmp.MicrosoftPhoto.Rating')),
        'resolution'     : (('WN', 'Exif.Photo.FocalPlaneResolution'),
                            ('WN', 'Exif.{ifd}.FocalPlaneResolution'),
                            ('WN', 'Xmp.exif.FocalPlaneResolution')),
        'sensor_size'    : (('WN', 'Exif.Photo.PixelDimensions'),
                            ('WN', 'Exif.{ifd}.ImageDimensions'),
                            ('WN', 'Xmp.exif.PixelDimensions'),
                            ('WN', 'Xmp.tiff.ImageDimensions')),
        'software'       : (('WA', 'Exif.Image.ProcessingSoftware'),
                            ('WA', 'Iptc.Application2.Program'),
                            ('WX', 'Xmp.xmp.CreatorTool')),
        # Both xmpGImg and xapGImg namespaces are specified in different
        # Adobe documents I've seen. xmpGImg appears to be more recent,
        # so we write that but read either.
        'thumbnail'      : (('WA', 'Exif.Thumbnail'),
                            ('WX', 'Xmp.xmp.Thumbnails'),
                            ('W0', 'Xmp.xmp.ThumbnailsXap')),
        'timezone'       : (('WN', 'Exif.Image.TimeZoneOffset'),
                            ('WN', 'Exif.CanonTi.TimeZone'),
                            ('WN', 'Exif.NikonWt.Timezone')),
        'title'          : (('WA', 'Xmp.dc.title'),
                            ('W0', 'Xmp.photoshop.Headline'),
                            ('WA', 'Iptc.Application2.ObjectName'),
                            ('W0', 'Exif.Image.XPTitle'),
                            ('W0', 'Iptc.Application2.Headline')),
        'usageterms'     : (('WA', 'Xmp.xmpRights.UsageTerms'),),
        }

    def read(self, name, type_):
        result = []
        for mode, tag in self._tag_list[name]:
            try:
                if tag in self._multi_tags:
                    tag_group = self._multi_tags[tag]
                    if 'ifd' in tag:
                        tag_group = [
                            x.format(ifd=self.ifd_list[0]) for x in tag_group]
                        tag = tag.format(ifd=self.ifd_list[0])
                    file_value = self.get_group(tag_group)
                    if tag == 'Exif.Thumbnail':
                        file_value.append(self.get_exif_thumbnail())
                elif self.is_exif_tag(tag):
                    if 'ifd' in tag:
                        tag = tag.format(ifd=self.ifd_list[0])
                    file_value = self.get_string(tag)
                elif self.is_iptc_tag(tag):
                    file_value = self.get_multiple(tag)
                elif self.get_tag_type(tag) == 'LangAlt':
                    file_value = self.get_multiple(tag)
                    if file_value:
                        file_value = file_value[0]
                elif self.get_tag_type(tag) in ('XmpBag', 'XmpSeq'):
                    file_value = self.get_multiple(tag)
                else:
                    file_value = self.get_string(tag)
                value = type_.from_exiv2(file_value, tag)
            except ValueError as ex:
                logger.error('{}({}), {}: {}'.format(
                    os.path.basename(self._path), name, tag, str(ex)))
                continue
            except Exception as ex:
                logger.exception(ex)
                continue
            if value:
                result.append((tag, value))
        return result

    def write(self, name, value):
        for mode, tag in self._tag_list[name]:
            if mode == 'WN':
                continue
            if ((not value) or (mode == 'W0')
                    or (mode == 'WX' and not self.xmp_only)):
                self.clear_value(tag)
            else:
                value.write(self, tag)

    # Exiv2 uses the Exif.Image.Make value to decode Exif.Photo.MakerNote
    # If we change Exif.Image.Make we should delete Exif.Photo.MakerNote
    def camera_change_ok(self, camera_model):
        if not (self.has_tag('Exif.Photo.MakerNote')
                and self.has_tag('Exif.Image.Make')):
            return True
        if not camera_model:
            return False
        return self.get_string('Exif.Image.Make') == camera_model['make']

    def delete_makernote(self, camera_model):
        if self.camera_change_ok(camera_model):
            return
        self._clear_value('Exif.Image.Make')
        self.save_file(self._path)
        self.open_path(self._path)
        self._clear_value('Exif.Photo.MakerNote')
        self.save_file(self._path)


class ImageMetadata(Exiv2Metadata):
    _iptc_encodings = {
        'ascii'    : (b'\x1b\x28\x42',),
        'iso8859-1': (b'\x1b\x2f\x41', b'\x1b\x2e\x41'),
        'utf-8'    : (b'\x1b\x25\x47', b'\x1b\x25\x2f\x49'),
        'utf-16-be': (b'\x1b\x25\x2f\x4c',),
        'utf-32-be': (b'\x1b\x25\x2f\x46',),
        }

    def __init__(self, *args, utf_safe=False, **kwds):
        super(ImageMetadata, self).__init__(*args, **kwds)
        # convert IPTC data to utf-8
        if self.has_iptc() and not self.xmp_only:
            self.transcode_iptc(utf_safe)

    def transcode_iptc(self, utf_safe):
        iptc_charset_code = self.get_raw('Iptc.Envelope.CharacterSet')
        for charset, codes in self._iptc_encodings.items():
            if iptc_charset_code in codes:
                iptc_charset = charset
                break
        else:
            iptc_charset = None
        if iptc_charset in ('utf-8', 'ascii'):
            # no need to translate anything
            return
        if iptc_charset:
            # temporarily make it the only member of self._encodings
            old_encodings = self._encodings
            self._encodings = [iptc_charset]
        # transcode every string tag except Iptc.Envelope.CharacterSet
        logger.info('Transcoding IPTC data to UTF-8')
        tags = ['Iptc.Envelope.CharacterSet']
        multiple = []
        for tag in self.get_iptc_tags():
            if tag in tags:
                multiple.append(tag)
            elif self.get_tag_type(tag) == 'String':
                tags.append(tag)
        for tag in tags[1:]:
            try:
                if tag in multiple:
                    # PyGObject segfaults if strings are not utf-8
                    if using_pgi or utf_safe:
                        value = self.get_multiple(tag)
                    else:
                        logger.warning('%s: ignoring multiple %s values',
                                       os.path.basename(self._path), tag)
                        logger.warning(
                            'Try running Photini with the --utf_safe option.')
                        value = [self.get_string(tag)]
                    self.set_multiple(tag, value)
                else:
                    self.set_string(tag, self.get_string(tag))
            except Exception as ex:
                logger.exception(ex)
        if iptc_charset:
            # restore self._encodings
            self._encodings = old_encodings

    @classmethod
    def open_old(cls, *arg, **kw):
        try:
            return cls(*arg, **kw)
        except GLib.GError:
            # expected if unrecognised file format
            return None
        except Exception as ex:
            logger.exception(ex)
            return None

    def merge_sc(self, other):
        # merge sidecar data into image file data, ignoring thumbnails
        raw_sc = GExiv2.Metadata()
        raw_sc.open_path(other._path)
        # allow exiv2 to infer Exif tags from XMP
        for tag in raw_sc.get_exif_tags():
            if tag.startswith('Exif.Thumbnail'):
                continue
            # ignore inferred datetime values the exiv2 gets wrong
            # (I think it's adding the local timezone offset)
            if tag in ('Exif.Image.DateTime', 'Exif.Photo.DateTimeOriginal',
                       'Exif.Photo.DateTimeDigitized'):
                self.clear_tag(tag)
            else:
                value = raw_sc.get_tag_string(tag)
                if value:
                    self.set_tag_string(tag, value)
        # copy all XMP tags except inferred Exif tags
        for tag in raw_sc.get_xmp_tags():
            if tag.startswith('Xmp.xmp.Thumbnails'):
                continue
            ns = tag.split('.')[1]
            if ns in ('exif', 'exifEX', 'tiff', 'aux'):
                # exiv2 will already have supplied the equivalent Exif tag
                pass
            elif self.get_tag_type(tag) == 'XmpText':
                value = raw_sc.get_tag_string(tag)
                if value:
                    self.set_tag_string(tag, value)
            else:
                value = raw_sc.get_tag_multiple(tag)
                if value:
                    self.set_tag_multiple(tag, value)


class Preview(object):
    def __init__(self, md, buf):
        self.md = md
        self.buf = buf

    def get_data(self):
        return self.buf

    def get_height(self):
        return self.md.get_pixel_height()

    def get_mime_type(self):
        return self.md.get_mime_type()

    def get_width(self):
        return self.md.get_pixel_width()


class VideoHeaderMetadata(Exiv2Metadata):
    def __init__(self, props, *args, **kwds):
        super(VideoHeaderMetadata, self).__init__(*args, **kwds)
        self._props = props
        # definitely read-only
        self.read_only = True

    @classmethod
    def open_old(cls, path):
        # scan first 2 MB of file for embedded JPEG images
        with open(path, 'rb') as f:
            data = f.read(2 * 1024 * 1024)
        segments = []
        soi = 0
        while True:
            soi = data.find(b'\xff\xd8\xff', soi)
            if soi < 0:
                break
            eoi = data.find(b'\xff\xd9', soi + 6)
            if eoi < 0:
                break
            segments.append(data[soi:eoi])
            soi += 3
        # get preview properties of each segment
        props = []
        for segment in segments:
            try:
                md = Exiv2Metadata(path, buf=segment)
            except GLib.GError:
                # expected if unrecognised data format
                md = None
            except Exception as ex:
                logger.exception(ex)
                md = None
            if md:
                props.append(Preview(md, segment))
        if not props:
            return None
        # choose largest preview to be the master image
        dim = 0
        master = None
        for prop in props:
            new_dim = max(prop.get_height(), prop.get_width())
            if new_dim > dim:
                dim = new_dim
                master = prop
        if not master:
            return None
        return cls(props, path, buf=master.buf)

    def read(self, name, type_):
        result = super(VideoHeaderMetadata, self).read(name, type_)
        if name == 'thumbnail':
            try:
                value = type_.from_video_header(self._props)
                if value:
                    result.append(('Preview', value))
            except ValueError as ex:
                logger.error('{}({}), {}: {}'.format(
                    os.path.basename(self._path), name, 'Preview', str(ex)))
            except Exception as ex:
                logger.exception(ex)
        return result


class SidecarMetadata(Exiv2Metadata):
    @classmethod
    def open_old(cls, path):
        if not path:
            return None
        try:
            return cls(path)
        except Exception as ex:
            logger.exception(ex)
            return None

    @classmethod
    def open_new(cls, path, image_md):
        sc_path = path + '.xmp'
        try:
            if image_md and gexiv2_version >= (0, 10, 6):
                image_md.save_external(sc_path)
            else:
                with open(sc_path, 'w') as of:
                    of.write(XMP_WRAPPER.format(
                        'xmlns:xmp="http://ns.adobe.com/xap/1.0/"'))
                if image_md:
                    # let exiv2 copy as much metadata as it can into sidecar
                    image_md.save_file(sc_path)
            return cls(sc_path)
        except Exception as ex:
            logger.exception(ex)
            return None

    def delete(self):
        os.unlink(self._path)
        return None

    def clear_dates(self):
        # workaround for bug in exiv2 xmp timestamp altering
        for name in ('date_digitised', 'date_modified', 'date_taken'):
            for mode, tag in self._tag_list[name]:
                if mode in ('WA', 'W0'):
                    self.clear_value(tag)
        self.save()
