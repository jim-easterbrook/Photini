##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-19  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import codecs
import locale
import logging
import os

import six

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
        ('exifEX',  'http://cipa.jp/exif/1.0/'),
        ('video',   'http://www.video/'),
        ('xapGImg', 'http://ns.adobe.com/xxx/'),
        ('xmpGImg', 'http://ns.adobe.com/xap/1.0/g/img/')):
    GExiv2.Metadata.register_xmp_namespace(name, prefix)

# Gexiv2 won't register the 'Iptc4xmpExt' namespace as its abbreviated
# version 'iptcExt' is already defined. This kludge registers it by
# reading some data with the full namespace
data = XMP_WRAPPER.format(
    'xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/"')
if six.PY2:
    data = data.decode('utf-8')
# open the data to register the namespace
GExiv2.Metadata().open_buf(data.encode('utf-8'))
del data


class Exiv2Metadata(GExiv2.Metadata):
    def __init__(self, path, buf=None):
        super(Exiv2Metadata, self).__init__()
        self._path = path
        if buf:
            # read metadata from buffer
            self.open_buf(buf)
        else:
            # read metadata from file
            self.open_path(self._path)
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

    def _decode_string(self, value):
        if not value:
            return value
        for encoding in self._encodings:
            try:
                return value.decode(encoding)
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
        if not self.has_tag(tag):
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
                    return b''.join(map(six.int2byte, map(int, result.split())))
                if self.get_tag_type(tag) == 'Comment':
                    # GExiv2 adds original charset information
                    parts = result.split('"')
                    if parts[0] == 'charset=':
                        result = parts[2][1:]
                if not six.PY2:
                    result = result.encode('ascii', 'backslashreplace')
                return result
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

    def get_string(self, tag, idx=1):
        if tag in self._multi_tags:
            return [self._get_string(sub_tag.format(idx=idx))
                    for sub_tag in self._multi_tags[tag]]
        return self._get_string(tag)

    def _get_string(self, tag):
        if not self.has_tag(tag):
            return None
        if tag in ('Exif.Image.XPTitle',  'Exif.Image.XPComment',
                   'Exif.Image.XPAuthor', 'Exif.Image.XPKeywords',
                   'Exif.Image.XPSubject'):
            # UCS2 encoded Exif data
            result = self.get_raw(tag)
            if not result:
                return None
            return result.decode('utf-16-le', errors='ignore').strip('\x00')
        if tag == 'Exif.Photo.UserComment':
            # first 8 bytes should be the encoding charset
            result = self.get_raw(tag)
            if not result:
                return None
            charset = result[:8].decode(
                'ascii', 'replace').strip('\x00').lower()
            if charset in self._charset_map:
                result = result[8:].decode(self._charset_map[charset])
            elif charset == '':
                result = self._decode_string(result[8:])
            else:
                result = result.decode('ascii', 'replace')
            return result.strip('\x00')
        try:
            result = self.get_tag_string(tag)
            if six.PY2:
                result = self._decode_string(result)
            return result
        except UnicodeDecodeError:
            pass
        # attempt to read raw data instead
        result = self.get_raw(tag)
        if not result:
            return None
        return self._decode_string(result).strip('\x00')

    def get_multiple(self, tag, idx=1):
        if tag in self._multi_tags:
            return [self._get_multiple(sub_tag.format(idx=idx))
                    for sub_tag in self._multi_tags[tag]]
        return self._get_multiple(tag)

    def _get_multiple(self, tag):
        if not self.has_tag(tag):
            return []
        try:
            result = self.get_tag_multiple(tag)
            if six.PY2:
                result = list(map(self._decode_string, result))
            return result
        except UnicodeDecodeError:
            pass
        # attempt to read raw data instead, only gets the first value
        result = self.get_raw(tag)
        if not result:
            return []
        logger.info('potential multi-data loss %s %s',
                    os.path.basename(self._path), tag)
        return [self._decode_string(result).strip('\x00')]

    # maximum length of Iptc data
    _max_bytes = {
        'Iptc.Application2.Byline'           :   32,
        'Iptc.Application2.Caption'          : 2000,
        'Iptc.Application2.City'             :   32,
        'Iptc.Application2.Copyright'        :  128,
        'Iptc.Application2.CountryCode'      :    3,
        'Iptc.Application2.CountryName'      :   64,
        'Iptc.Application2.Headline'         :  256,
        'Iptc.Application2.Keywords'         :   64,
        'Iptc.Application2.ObjectName'       :   64,
        'Iptc.Application2.Program'          :   32,
        'Iptc.Application2.ProgramVersion'   :   10,
        'Iptc.Application2.ProvinceState'    :   32,
        'Iptc.Application2.SubLocation'      :   32,
        'Iptc.Envelope.CharacterSet'         :   32,
        }

    if gexiv2_version >= (0, 10, 3):
        _xmp_struct_type = {
            'Xmp.iptcExt.LocationCreated': GExiv2.StructureType.BAG,
            'Xmp.iptcExt.LocationShown'  : GExiv2.StructureType.BAG,
            'Xmp.xmp.Thumbnails'         : GExiv2.StructureType.ALT,
            }

    def set_string(self, tag, value, idx=1):
        if tag in self._multi_tags:
            sub_tag = self._multi_tags[tag][0].format(idx=idx)
            if any(value) and '/' in sub_tag:
                # create XMP structure/container
                for t in self.get_xmp_tags():
                    if t.startswith(tag):
                        # container already exists
                        break
                else:
                    if gexiv2_version >= (0, 10, 3):
                        self.set_xmp_tag_struct(tag, self._xmp_struct_type[tag])
                    else:
                        self.set_tag_string(tag, '')
            for sub_tag, sub_value in zip(self._multi_tags[tag], value):
                self._set_string(sub_tag.format(idx=idx), sub_value)
            return
        self._set_string(tag, value)

    def _set_string(self, tag, value):
        if not value:
            self.clear_value(tag)
            return
        if tag in self._max_bytes:
            value = value.encode('utf-8')[:self._max_bytes[tag]]
            if not six.PY2:
                value = value.decode('utf-8', errors='ignore')
        elif six.PY2:
            value = value.encode('utf-8')
        self.set_tag_string(tag, value)

    def set_multiple(self, tag, value, idx=1):
        if tag in self._multi_tags:
            for sub_tag, sub_value in zip(self._multi_tags[tag], value):
                self._set_multiple(sub_tag.format(idx=idx), sub_value)
            return
        self._set_multiple(tag, value)

    def _set_multiple(self, tag, value):
        if not value:
            self.clear_value(tag)
            return
        if self.is_iptc_tag(tag) and tag in self._max_bytes:
            value = [x.encode('utf-8')[:self._max_bytes[tag]] for x in value]
            if not six.PY2:
                value = [x.decode('utf-8') for x in value]
        elif six.PY2:
            value = [x.encode('utf-8') for x in value]
        self.set_tag_multiple(tag, value)

    def save(self, file_times=None, force_iptc=False):
        self.has_iptc = self.has_iptc or force_iptc
        if self.xmp_only:
            self.clear_exif()
            self.clear_iptc()
        elif not self.has_iptc:
            self.clear_iptc()
        try:
            self.save_file(self._path)
            if file_times:
                os.utime(self._path, file_times)
        except Exception as ex:
            logger.exception(ex)
            return False
        # check that data really was saved
        OK = True
        saved_tags = ImageMetadata.open_old(self._path).get_all_tags()
        for tag in self.get_all_tags():
            if tag in ('Exif.Image.GPSTag',):
                # some tags disappear with good reason
                continue
            if tag not in saved_tags:
                logger.warning('tag not saved: %s', tag)
                OK = False
        return OK

    def get_all_tags(self):
        return self.get_exif_tags() + self.get_iptc_tags() + self.get_xmp_tags()

    # some tags are always read & written in groups, but are represented
    # by a single name
    _multi_tags = {
        'Exif.GPSInfo.GPSAltitude': (
            'Exif.GPSInfo.GPSAltitude', 'Exif.GPSInfo.GPSAltitudeRef'),
        'Exif.GPSInfo.GPSCoordinates': (
            'Exif.GPSInfo.GPSLatitude', 'Exif.GPSInfo.GPSLatitudeRef',
            'Exif.GPSInfo.GPSLongitude', 'Exif.GPSInfo.GPSLongitudeRef'),
        'Exif.Image.DateTime': (
            'Exif.Image.DateTime', 'Exif.Photo.SubSecTime'),
        'Exif.Image.DateTimeOriginal': ('Exif.Photo.DateTimeOriginal',),
        'Exif.Image.FNumber': (
            'Exif.Image.FNumber', 'Exif.Image.ApertureValue'),
        'Exif.Photo.DateTimeDigitized': (
            'Exif.Photo.DateTimeDigitized', 'Exif.Photo.SubSecTimeDigitized'),
        'Exif.Photo.DateTimeOriginal': (
            'Exif.Photo.DateTimeOriginal', 'Exif.Photo.SubSecTimeOriginal'),
        'Exif.Photo.FNumber': (
            'Exif.Photo.FNumber', 'Exif.Photo.ApertureValue'),
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
        'Xmp.exif.FNumber': ('Xmp.exif.FNumber', 'Xmp.exif.ApertureValue'),
        'Xmp.exif.GPSAltitude': (
            'Xmp.exif.GPSAltitude', 'Xmp.exif.GPSAltitudeRef'),
        'Xmp.exif.GPSCoordinates': (
            'Xmp.exif.GPSLatitude', 'Xmp.exif.GPSLongitude'),
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
        'Xmp.xmp.Thumbnails': (
            'Xmp.xmp.Thumbnails[1]/xmpGImg:image',
            'Xmp.xmp.Thumbnails[1]/xmpGImg:format',
            'Xmp.xmp.Thumbnails[1]/xmpGImg:width',
            'Xmp.xmp.Thumbnails[1]/xmpGImg:height'),
        'Xmp.xmp.ThumbnailsXap': (
            'Xmp.xmp.Thumbnails[1]/xapGImg:image',
            'Xmp.xmp.Thumbnails[1]/xapGImg:format',
            'Xmp.xmp.Thumbnails[1]/xapGImg:width',
            'Xmp.xmp.Thumbnails[1]/xapGImg:height'),
        }

    # Mapping of tags to Photini data fields Each field has a list of
    # (mode, tag) pairs. The mode is a string containing the read mode
    # (RA (always), or RN (never)) and write mode (WA (always), WX (if
    # Exif not supported), W0 (clear the tag), or WN (never). The order
    # of the tags sets the precedence when values conflict.
    _tag_list = {
        'altitude'       : (('RA.WA', 'Exif.GPSInfo.GPSAltitude'),
                            ('RA.WX', 'Xmp.exif.GPSAltitude')),
        'aperture'       : (('RA.WA', 'Exif.Photo.FNumber'),
                            ('RA.W0', 'Exif.Image.FNumber'),
                            ('RA.WX', 'Xmp.exif.FNumber')),
        'camera_model'   : (('RA.WN', 'Exif.Image.Model'),
                            ('RA.WN', 'Exif.Image.UniqueCameraModel'),
                            ('RA.WN', 'Exif.Canon.ModelID'),
                            ('RA.WN', 'Xmp.video.Model')),
        'copyright'      : (('RA.WA', 'Exif.Image.Copyright'),
                            ('RA.WA', 'Xmp.dc.rights'),
                            ('RA.W0', 'Xmp.tiff.Copyright'),
                            ('RA.WA', 'Iptc.Application2.Copyright')),
        'creator'        : (('RA.WA', 'Exif.Image.Artist'),
                            ('RA.W0', 'Exif.Image.XPAuthor'),
                            ('RA.WA', 'Xmp.dc.creator'),
                            ('RA.W0', 'Xmp.tiff.Artist'),
                            ('RA.WA', 'Iptc.Application2.Byline')),
        'date_digitised' : (('RA.WA', 'Exif.Photo.DateTimeDigitized'),
                            ('RA.WA', 'Xmp.xmp.CreateDate'),
                            ('RA.W0', 'Xmp.exif.DateTimeDigitized'),
                            ('RA.WN', 'Xmp.video.DateUTC'),
                            ('RA.WA', 'Iptc.Application2.DigitizationDate')),
        'date_modified'  : (('RA.WA', 'Exif.Image.DateTime'),
                            ('RA.WA', 'Xmp.xmp.ModifyDate'),
                            ('RA.WN', 'Xmp.video.ModificationDate'),
                            ('RA.W0', 'Xmp.tiff.DateTime')),
        'date_taken'     : (('RA.WA', 'Exif.Photo.DateTimeOriginal'),
                            ('RA.W0', 'Exif.Image.DateTimeOriginal'),
                            ('RA.WA', 'Xmp.photoshop.DateCreated'),
                            ('RA.W0', 'Xmp.exif.DateTimeOriginal'),
                            ('RA.WN', 'Xmp.video.DateUTC'),
                            ('RA.WA', 'Iptc.Application2.DateCreated')),
        'description'    : (('RA.WA', 'Exif.Image.ImageDescription'),
                            ('RA.W0', 'Exif.Image.XPComment'),
                            ('RA.W0', 'Exif.Image.XPSubject'),
                            ('RA.W0', 'Exif.Photo.UserComment'),
                            ('RA.WA', 'Xmp.dc.description'),
                            ('RA.W0', 'Xmp.tiff.ImageDescription'),
                            ('RA.WA', 'Iptc.Application2.Caption')),
        'dimension_x'    : (('RA.WN', 'Exif.Image.ImageWidth'),
                            ('RA.WN', 'Exif.Photo.PixelXDimension'),
                            ('RA.WN', 'Xmp.tiff.ImageWidth'),
                            ('RA.WN', 'Xmp.exif.PixelXDimension')),
        'dimension_y'    : (('RA.WN', 'Exif.Image.ImageLength'),
                            ('RA.WN', 'Exif.Photo.PixelYDimension'),
                            ('RA.WN', 'Xmp.tiff.ImageLength'),
                            ('RA.WN', 'Xmp.exif.PixelYDimension')),
        'focal_length'   : (('RA.WA', 'Exif.Photo.FocalLength'),
                            ('RA.W0', 'Exif.Image.FocalLength'),
                            ('RA.WX', 'Xmp.exif.FocalLength')),
        'focal_length_35': (('RA.WA', 'Exif.Photo.FocalLengthIn35mmFilm'),
                            ('RA.WX', 'Xmp.exif.FocalLengthIn35mmFilm')),
        'keywords'       : (('RA.WA', 'Xmp.dc.subject'),
                            ('RA.WA', 'Iptc.Application2.Keywords'),
                            ('RA.W0', 'Exif.Image.XPKeywords')),
        'latlong'        : (('RA.WA', 'Exif.GPSInfo.GPSCoordinates'),
                            ('RA.WX', 'Xmp.exif.GPSCoordinates'),
                            ('RA.WN', 'Xmp.video.GPSCoordinates')),
        'lens_make'      : (('RA.WA', 'Exif.Photo.LensMake'),
                            ('RA.WX', 'Xmp.exifEX.LensMake')),
        'lens_model'     : (('RA.WA', 'Exif.Photo.LensModel'),
                            ('RA.WX', 'Xmp.exifEX.LensModel'),
                            ('RA.W0', 'Exif.Canon.LensModel'),
                            ('RA.W0', 'Exif.OlympusEq.LensModel'),
                            ('RA.W0', 'Xmp.aux.Lens'),
                            ('RN.W0', 'Exif.CanonCs.LensType')),
        'lens_serial'    : (('RA.WA', 'Exif.Photo.LensSerialNumber'),
                            ('RA.WX', 'Xmp.exifEX.LensSerialNumber'),
                            ('RA.W0', 'Exif.OlympusEq.LensSerialNumber'),
                            ('RA.W0', 'Xmp.aux.SerialNumber')),
        'lens_spec'      : (('RA.WA', 'Exif.Photo.LensSpecification'),
                            ('RA.WX', 'Xmp.exifEX.LensSpecification'),
                            ('RA.W0', 'Exif.Image.LensInfo'),
                            ('RA.W0', 'Exif.CanonCs.Lens'),
                            ('RA.W0', 'Exif.Nikon3.Lens'),
                            ('RN.W0', 'Exif.CanonCs.ShortFocal'),
                            ('RN.W0', 'Exif.CanonCs.MaxAperture'),
                            ('RN.W0', 'Exif.CanonCs.MinAperture')),
        'location_shown' : (('RA.WA', 'Xmp.iptcExt.LocationShown'),),
        'location_taken' : (('RA.WA', 'Xmp.iptcExt.LocationCreated'),
                            ('RA.WA', 'Xmp.iptc.Location'),
                            ('RA.WA', 'Iptc.Application2.Location')),
        'orientation'    : (('RA.WA', 'Exif.Image.Orientation'),
                            ('RA.WX', 'Xmp.tiff.Orientation')),
        'rating'         : (('RA.WA', 'Xmp.xmp.Rating'),
                            ('RA.W0', 'Exif.Image.Rating'),
                            ('RA.W0', 'Exif.Image.RatingPercent'),
                            ('RA.W0', 'Xmp.MicrosoftPhoto.Rating')),
        'resolution_x'   : (('RA.WN', 'Exif.Image.FocalPlaneXResolution'),
                            ('RA.WN', 'Exif.Photo.FocalPlaneXResolution'),
                            ('RA.WN', 'Xmp.exif.FocalPlaneXResolution')),
        'resolution_y'   : (('RA.WN', 'Exif.Image.FocalPlaneYResolution'),
                            ('RA.WN', 'Exif.Photo.FocalPlaneYResolution'),
                            ('RA.WN', 'Xmp.exif.FocalPlaneYResolution')),
        'resolution_unit': (('RA.WN', 'Exif.Image.FocalPlaneResolutionUnit'),
                            ('RA.WN', 'Exif.Photo.FocalPlaneResolutionUnit'),
                            ('RA.WN', 'Xmp.exif.FocalPlaneResolutionUnit')),
        'software'       : (('RA.WA', 'Exif.Image.ProcessingSoftware'),
                            ('RA.WA', 'Iptc.Application2.Program')),
        # Both xmpGImg and xapGImg namespaces are specified in different
        # Adobe documents I've seen. xmpGImg appears to be more recent,
        # so we write that but read either.
        'thumbnail'      : (('RA.WA', 'Exif.Thumbnail.Compression'),
                            ('RA.WX', 'Xmp.xmp.Thumbnails'),
                            ('RA.W0', 'Xmp.xmp.ThumbnailsXap')),
        'timezone'       : (('RA.WN', 'Exif.Image.TimeZoneOffset'),
                            ('RA.WN', 'Exif.CanonTi.TimeZone'),
                            ('RA.WN', 'Exif.NikonWt.Timezone')),
        'title'          : (('RA.WA', 'Xmp.dc.title'),
                            ('RA.WA', 'Iptc.Application2.ObjectName'),
                            ('RA.W0', 'Exif.Image.XPTitle'),
                            ('RA.W0', 'Iptc.Application2.Headline')),
        }

    def read(self, name, type_):
        result = []
        for mode, tag in self._tag_list[name]:
            if mode.split('.')[0] == 'RN':
                continue
            if self.xmp_only and not self.is_xmp_tag(tag):
                continue
            try:
                value = type_.read(self, tag)
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
            write_mode = mode.split('.')[1]
            if write_mode == 'WN':
                continue
            if self.xmp_only and not self.is_xmp_tag(tag):
                continue
            if ((not value) or (write_mode == 'W0') or
                (write_mode == 'WX' and not self.xmp_only)):
                self.clear_value(tag)
            else:
                value.write(self, tag)


class ImageMetadata(Exiv2Metadata):
    _repeatable = (
        'Iptc.Application2.Byline',
        'Iptc.Application2.BylineTitle',
        'Iptc.Application2.Contact',
        'Iptc.Application2.Keywords',
        'Iptc.Application2.LocationCode',
        'Iptc.Application2.LocationName',
        'Iptc.Application2.ObjectAttribute',
        'Iptc.Application2.ReferenceNumber',
        'Iptc.Application2.ReferenceService',
        'Iptc.Application2.Subject',
        'Iptc.Application2.SuppCategory',
        'Iptc.Application2.Writer',
        'Iptc.Envelope.Destination',
        'Iptc.Envelope.ProductId',
        )

    _iptc_encodings = {
        'ascii'    : (b'\x1b\x28\x42',),
        'iso8859-1': (b'\x1b\x2f\x41', b'\x1b\x2e\x41'),
        'utf-8'    : (b'\x1b\x25\x47', b'\x1b\x25\x2f\x49'),
        'utf-16-be': (b'\x1b\x25\x2f\x4c',),
        'utf-32-be': (b'\x1b\x25\x2f\x46',),
        }

    def __init__(self, *args, **kwds):
        super(ImageMetadata, self).__init__(*args, **kwds)
        # Exiv2 misleadingly says Xmp files (application/rdf+xml)
        # support Exif and IPTC.
        self.xmp_only = ((not self.get_supports_exif()) or
                         (self.get_mime_type() == 'application/rdf+xml'))
        if self.xmp_only:
            self.using_iptc = False
        else:
            self.using_iptc = self.has_iptc()
        # convert IPTC data to utf-8
        if self.using_iptc:
            self.transcode_iptc()
        # set character set to utf-8 from now on
        self._set_string('Iptc.Envelope.CharacterSet',
                         self._iptc_encodings['utf-8'][0].decode('ascii'))

    def transcode_iptc(self):
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
        for tag in self.get_iptc_tags():
            if tag not in tags and self.get_tag_type(tag) == 'String':
                tags.append(tag)
        for tag in tags[1:]:
            try:
                if tag in self._repeatable:
                    if not six.PY2 and not using_pgi:
                        # PyGObject segfaults if strings are not utf-8
                        logger.info('potential multi-data loss %s %s',
                                    os.path.basename(self._path), tag)
                        value = [self._get_string(tag)]
                    else:
                        value = self._get_multiple(tag)
                    self._set_multiple(tag, value)
                else:
                    self._set_string(tag, self._get_string(tag))
            except Exception as ex:
                logger.exception(ex)
        if iptc_charset:
            # restore self._encodings
            self._encodings = old_encodings

    @classmethod
    def open_old(cls, path):
        try:
            return cls(path)
        except GLib.GError:
            # expected if unrecognised file format
            return None
        except Exception as ex:
            logger.exception(ex)
            return None

    def merge_sc(self, other):
        # merge sidecar data into image file data, ignoring thumbnails
        # allow exiv2 to infer Exif tags from XMP
        for tag in other.get_exif_tags():
            if tag.startswith('Exif.Thumbnail'):
                continue
            # ignore inferred datetime values the exiv2 gets wrong
            # (I think it's adding the local timezone offset)
            if tag in ('Exif.Image.DateTime', 'Exif.Photo.DateTimeOriginal',
                       'Exif.Photo.DateTimeDigitized'):
                self.clear_tag(tag)
            else:
                self._set_string(tag, other._get_string(tag))
        # copy all XMP tags except inferred Exif tags
        for tag in other.get_xmp_tags():
            if tag.startswith('Xmp.xmp.Thumbnails'):
                continue
            ns = tag.split('.')[1]
            if ns in ('exif', 'exifEX', 'tiff', 'aux'):
                # exiv2 will already have supplied the equivalent Exif tag
                pass
            elif self.get_tag_type(tag) == 'XmpText':
                self._set_string(tag, other._get_string(tag))
            else:
                self._set_multiple(tag, other._get_multiple(tag))


class VideoHeaderMetadata(ImageMetadata):
    @classmethod
    def open_old(cls, path):
        # scan first 256 KB of file for embedded JPEG images
        with open(path, 'rb') as f:
            data = f.read(256 * 1024)
        result = None
        soi = 0
        while True:
            soi = data.find(b'\xff\xd8\xff', soi)
            if soi < 0:
                break
            eoi = data.find(b'\xff\xd9', soi + 6)
            if eoi < 0:
                break
            try:
                segment = cls(path, buf=data[soi:eoi])
            except GLib.GError:
                # expected if unrecognised data format
                segment = None
            except Exception as ex:
                logger.exception(ex)
                segment = None
            if segment and len(segment.get_all_tags()) > 1:
                if result:
                    result.merge_segment(segment)
                else:
                    result = segment
                    result.segment = soi, eoi
            soi += 3
        return result

    def merge_segment(self, other):
        for tag in other.get_all_tags():
            other_value = other._get_string(tag)
            if not self.has_tag(tag):
                self._set_string(tag, other_value)
            elif self._get_string(tag) != other_value:
                logger.warning('Ignoring repeated video header tag %s: %s',
                               tag, other_value)

    def save(self, *args, **kwds):
        # definitely read-only
        return False

    def get_exif_thumbnail(self):
        if not self.segment:
            return None
        soi, eoi = self.segment
        with open(self._path, 'rb') as f:
            data = f.read(eoi)
        return data[soi:]


class SidecarMetadata(Exiv2Metadata):
    using_iptc = False
    xmp_only = True

    @classmethod
    def open_old(cls, path):
        for base in (os.path.splitext(path)[0], path):
            for ext in ('.xmp', '.XMP', '.Xmp'):
                sc_path = base + ext
                if os.path.exists(sc_path):
                    try:
                        return cls(sc_path)
                    except Exception as ex:
                        logger.exception(ex)
                        return None
        return None

    @classmethod
    def open_new(cls, path, image_md):
        sc_path = path + '.xmp'
        try:
            with open(sc_path, 'w') as of:
                of.write(XMP_WRAPPER.format(
                    'xmlns:xmp="http://ns.adobe.com/xap/1.0/"'))
            if image_md:
                # let exiv2 copy as much metadata as it can into sidecar
                image_md.save_file(sc_path)
            self = cls(sc_path)
            self.set_string(
                'Xmp.xmp.CreatorTool', 'Photini editor v' + __version__)
            return self
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
                if mode in ('RA.WA', 'RA.W0'):
                    self.clear_value(tag)
        self.save()
