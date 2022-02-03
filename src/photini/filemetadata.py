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

import logging
import os
import sys

try:
    from photini.exiv2 import MetadataHandler, exiv2_version, exiv2_version_info
except ImportError as ex1:
    print(str(ex1))
    try:
        from photini.gexiv2 import MetadataHandler, exiv2_version, exiv2_version_info
        print('Use of GExiv2 library will be withdrawn in a future release'
              ' of Photini.\nPlease install python-exiv2 soon.')
    except (ImportError, ValueError) as ex2:
        print(str(ex2))
        raise ex1 from None

logger = logging.getLogger(__name__)


class ImageMetadata(MetadataHandler):
    def clear_multi_group(self, tag, stop=0):
        # count entries
        idx = 1
        while any(self.get_group(tag, idx=idx)):
            idx += 1
        # delete entries
        while idx > stop + 1:
            idx -= 1
            self.clear_group(tag, idx=idx)

    def clear_group(self, tag, idx=1):
        for t in self._multi_tags[tag]:
            sub_tag = t.format(idx=idx)
            self.clear_value(sub_tag)

    def clear_value(self, tag):
        if not (tag and self.has_tag(tag)):
            return
        self.clear_tag(tag)

    def get_multi_group(self, tag):
        result = []
        for idx in range(1, 100):
            value = self.get_group(tag, idx=idx)
            if not any(value):
                break
            result.append(value)
        return result

    def get_group(self, tag, idx=1):
        result = []
        for x in self._multi_tags[tag]:
            result.append(self.get_value(x, idx=idx))
        if tag == 'Exif.Thumbnail.ImageWidth':
            result.append(self._get_exif_thumbnail())
        return result

    def get_value(self, tag, idx=1):
        if not tag:
            return None
        if 'idx' in tag:
            tag = tag.format(idx=idx)
        if self.is_exif_tag(tag):
            return self.get_exif_value(tag)
        if self.is_iptc_tag(tag):
            return self.get_iptc_value(tag)
        if self.is_xmp_tag(tag):
            return self.get_xmp_value(tag)
        assert False, 'Invalid tag ' + tag

    def _get_exif_thumbnail(self):
        # try normal thumbnail
        data = self.get_exif_thumbnail()
        if data:
            return data
        # try previews
        return self.get_preview_thumbnail()

    def set_multi_group(self, tag, value):
        # delete unwanted old entries
        self.clear_multi_group(tag, stop=len(value))
        # set new entries
        for idx, sub_value in enumerate(value, 1):
            if not any(sub_value):
                # set a place holder
                sub_value = [' ']
            self.set_group(tag, sub_value, idx=idx)

    def set_group(self, tag, value, idx=1):
        for sub_tag, sub_value in zip(self._multi_tags[tag], value):
            self.set_value(sub_tag, sub_value, idx=idx)
        if tag == 'Exif.Thumbnail.ImageWidth' and value[3]:
            self.set_exif_thumbnail_from_buffer(value[3])

    def set_value(self, tag, value, idx=1):
        if not tag:
            return
        if 'idx' in tag:
            tag = tag.format(idx=idx)
        if self.is_exif_tag(tag):
            self.set_exif_value(tag, value)
        elif self.is_iptc_tag(tag):
            self.set_iptc_value(tag, value)
        elif self.is_xmp_tag(tag):
            self.set_xmp_value(tag, value)
        else:
            assert False, 'Invalid tag ' + tag

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

    def set_multiple(self, tag, value):
        if not tag:
            return
        if not value:
            self.clear_value(tag)
            return
        if self.is_iptc_tag(tag) and tag in self._max_bytes:
            value = [x.encode('utf-8')[:self._max_bytes[tag]] for x in value]
            value = [x.decode('utf-8') for x in value]
        self.set_tag_multiple(tag, value)

    _iptc_encodings = {
        'ascii'    : (b'\x1b\x28\x42',),
        'iso8859-1': (b'\x1b\x2f\x41', b'\x1b\x2e\x41'),
        'utf-8'    : (b'\x1b\x25\x47', b'\x1b\x25\x2f\x49'),
        'utf-16-be': (b'\x1b\x25\x2f\x4c',),
        'utf-32-be': (b'\x1b\x25\x2f\x46',),
        }

    def get_iptc_encoding(self):
        iptc_charset_code = self.get_raw_value('Iptc.Envelope.CharacterSet')
        for charset, codes in self._iptc_encodings.items():
            if iptc_charset_code in codes:
                return charset
        return None

    def set_iptc_encoding(self, encoding='utf-8'):
        self.set_value('Iptc.Envelope.CharacterSet',
                       self._iptc_encodings[encoding][0].decode('ascii'))

    def save(self, file_times=None, force_iptc=False):
        if self.read_only:
            return False
        if force_iptc:
            self.set_iptc_encoding()
        else:
            self.clear_iptc()
        if self.xmp_only:
            self.clear_exif()
            self.clear_iptc()
        if not super(ImageMetadata, self).save():
            return False
        if file_times:
            os.utime(self._path, file_times)
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
            family, group, tagname = tag.split('.', 2)
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
        'Exif.GPSInfo.GPSLatitude': (
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
        'Exif.Photo.LensMake': (
            'Exif.Photo.LensMake', 'Exif.Photo.LensModel',
            'Exif.Photo.LensSerialNumber'),
        'Exif.Thumbnail.ImageWidth': (
            'Exif.Thumbnail.ImageWidth', 'Exif.Thumbnail.ImageLength',
            'Exif.Thumbnail.Compression'),
        'Iptc.Application2.Contact': ('Iptc.Application2.Contact',),
        'Iptc.Application2.DateCreated': (
            'Iptc.Application2.DateCreated', 'Iptc.Application2.TimeCreated'),
        'Iptc.Application2.DigitizationDate': (
            'Iptc.Application2.DigitizationDate',
            'Iptc.Application2.DigitizationTime'),
        'Iptc.Application2.SubLocation': (
            'Iptc.Application2.SubLocation', 'Iptc.Application2.City',
            'Iptc.Application2.ProvinceState', 'Iptc.Application2.CountryName',
            'Iptc.Application2.CountryCode'),
        'Iptc.Application2.Program': (
            'Iptc.Application2.Program', 'Iptc.Application2.ProgramVersion'),
        'Xmp.aux.Lens': ('', 'Xmp.aux.Lens'),
        'Xmp.aux.SerialNumber': ('', '', 'Xmp.aux.SerialNumber'),
        'Xmp.exif.FNumber': ('Xmp.exif.FNumber', 'Xmp.exif.ApertureValue'),
        'Xmp.exif.GPSAltitude': (
            'Xmp.exif.GPSAltitude', 'Xmp.exif.GPSAltitudeRef'),
        'Xmp.exif.GPSLatitude': (
            'Xmp.exif.GPSLatitude', 'Xmp.exif.GPSLongitude'),
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
        'Xmp.Iptc4xmpExt.LocationShown': (
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:Sublocation',
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:City',
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:ProvinceState',
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:CountryName',
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:CountryCode',
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:WorldRegion',
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:LocationId'),
        'Xmp.Iptc4xmpExt.LocationCreated': (
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:Sublocation',
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:City',
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:ProvinceState',
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:CountryName',
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:CountryCode',
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:WorldRegion',
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:LocationId'),
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
        'latlong'        : (('WA', 'Exif.GPSInfo.GPSLatitude'),
                            ('WX', 'Xmp.exif.GPSLatitude')),
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
        'location_shown' : (('WA', 'Xmp.Iptc4xmpExt.LocationShown'),),
        'location_taken' : (('WA', 'Xmp.Iptc4xmpExt.LocationCreated'),
                            ('WA', 'Xmp.iptc.Location'),
                            ('WA', 'Iptc.Application2.SubLocation')),
        'orientation'    : (('WA', 'Exif.Image.Orientation'),
                            ('WX', 'Xmp.tiff.Orientation')),
        'rating'         : (('WA', 'Xmp.xmp.Rating'),
                            ('W0', 'Exif.Image.Rating'),
                            ('W0', 'Exif.Image.RatingPercent'),
                            ('W0', 'Xmp.MicrosoftPhoto.Rating')),
        'software'       : (('WA', 'Exif.Image.ProcessingSoftware'),
                            ('WA', 'Iptc.Application2.Program'),
                            ('WX', 'Xmp.xmp.CreatorTool')),
        # Both xmpGImg and xapGImg namespaces are specified in different
        # Adobe documents I've seen. xmpGImg appears to be more recent,
        # so we write that but read either.
        'thumbnail'      : (('WA', 'Exif.Thumbnail.ImageWidth'),
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
                if tag not in self._multi_tags:
                    file_value = self.get_value(tag)
                elif 'idx' in self._multi_tags[tag][0]:
                    file_value = self.get_multi_group(tag)
                else:
                    file_value = self.get_group(tag)
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
                if tag not in self._multi_tags:
                    self.clear_value(tag)
                elif 'idx' in self._multi_tags[tag][0]:
                    self.clear_multi_group(tag)
                else:
                    self.clear_group(tag)
                continue
            if self.is_exif_tag(tag):
                file_value = value.to_exif()
            elif self.is_iptc_tag(tag):
                file_value = value.to_iptc()
            elif self.is_xmp_tag(tag):
                file_value = value.to_xmp()
            else:
                assert False, 'Invalid tag ' + tag
            if tag not in self._multi_tags:
                self.set_value(tag, file_value)
            elif 'idx' in self._multi_tags[tag][0]:
                self.set_multi_group(tag, file_value)
            else:
                self.set_group(tag, file_value)


class SidecarMetadata(ImageMetadata):
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
            cls.create_sc(sc_path, image_md)
            return cls(sc_path)
        except Exception as ex:
            logger.exception(ex)
            return None

    def delete(self):
        os.unlink(self._path)
        return None

    def clear_dates(self):
        if exiv2_version_info < (1, 0, 0):
            # workaround for bug in exiv2 xmp timestamp altering
            # see https://github.com/Exiv2/exiv2/issues/1998
            for name in ('date_digitised', 'date_modified', 'date_taken'):
                self.write(name, None)
            self.save()
