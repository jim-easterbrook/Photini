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
from fractions import Fraction
import imghdr
import logging
import math
import mimetypes
import os
import re

from photini import __version__
from photini.exiv2 import MetadataHandler, exiv2_version, exiv2_version_info
from photini.ffmpeg import FFmpeg
from photini.types import *

logger = logging.getLogger(__name__)


class FFMPEGMetadata(object):
    # some tags are always read in groups, but are represented by a
    # single name
    _multi_tags = {
        'ffmpeg/streams[0]/tags/model': (
            'ffmpeg/streams[0]/tags/make', 'ffmpeg/streams[0]/tags/model'),
        'ffmpeg/format/tags/com.apple.quicktime.model': (
            'ffmpeg/format/tags/com.apple.quicktime.make',
            'ffmpeg/format/tags/com.apple.quicktime.model'),
        'ffmpeg/streams[0]/coded_dims': (
            'ffmpeg/streams[0]/coded_width', 'ffmpeg/streams[0]/coded_height'),
        'ffmpeg/streams[0]/dims': (
            'ffmpeg/streams[0]/width', 'ffmpeg/streams[0]/height',
            'ffmpeg/streams[0]/nb_frames', 'ffmpeg/streams[0]/avg_frame_rate'),
        }

    _tag_list = {
        'camera_model':   ('ffmpeg/streams[0]/tags/model',
                           'ffmpeg/format/tags/com.apple.quicktime.model'),
        'copyright':      ('ffmpeg/format/tags/com.apple.quicktime.copyright',
                           'ffmpeg/format/tags/copyright'),
        'creator':        ('ffmpeg/format/tags/com.apple.quicktime.author',
                           'ffmpeg/format/tags/artist'),
        'date_modified':  ('ffmpeg/streams[0]/tags/datetime',),
        'date_digitised': ('ffmpeg/streams[0]/tags/datetimedigitized',),
        'date_taken':     ('ffmpeg/streams[0]/tags/datetimeoriginal',
                           'ffmpeg/streams[0]/tags/creation_time',
                           'ffmpeg/format/tags/creation_time'),
        'description':    ('ffmpeg/format/tags/comment',),
        'dimensions':     ('ffmpeg/streams[0]/dims',
                           'ffmpeg/streams[0]/coded_dims'),
        'gps_info':       ('ffmpeg/format/tags/location',),
        'orientation':    ('ffmpeg/streams[0]/tags/rotate',),
        'rating':         ('ffmpeg/format/tags/com.apple.quicktime.rating.user',),
        'title':          ('ffmpeg/streams[0]/tags/title',),
        }

    def __init__(self, path):
        self._path = path
        self.md = {}
        raw = FFmpeg.ffprobe(path)
        self.md = self.read_data('ffmpeg', raw)

    def read_data(self, label, value):
        result = {}
        for sub_label, sub_value in self.iter_over(label, value):
            if isinstance(sub_value, (dict, list)):
                result.update(self.read_data(sub_label, sub_value))
            else:
                result[sub_label] = sub_value
        return result

    def iter_over(self, label, value):
        if isinstance(value, list):
            for idx, sub_value in enumerate(value):
                yield '{}[{}]'.format(label, idx), sub_value
        else:
            for sub_key, sub_value in value.items():
                yield label + '/' + sub_key.lower(), sub_value

    @classmethod
    def open_old(cls, path):
        try:
            return cls(path)
        except RuntimeError as ex:
            logger.error(str(ex))
        except Exception as ex:
            logger.exception(ex)
        return None

    def read(self, name, type_):
        if name not in self._tag_list:
            return []
        result = []
        for tag in self._tag_list[name]:
            try:
                if tag in self._multi_tags:
                    file_value = self.get_group(tag)
                    if not any(file_value):
                        continue
                else:
                    file_value = self.get_value(tag)
                    if not file_value:
                        continue
                value = type_.from_ffmpeg(file_value, tag)
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

    def get_group(self, tag):
        result = []
        for sub_tag in self._multi_tags[tag]:
            result.append(self.get_value(sub_tag))
        return result

    def get_value(self, tag):
        if tag and tag in self.md:
            return self.md[tag]
        return None


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
        for sub_tag in self._multi_tags[tag]:
            if sub_tag:
                self.clear_value(sub_tag.format(idx=idx))

    def clear_value(self, tag):
        {'Exif': self.clear_exif_tag,
         'Iptc': self.clear_iptc_tag,
         'Xmp': self.clear_xmp_tag}[tag.split('.')[0]](tag)

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
        if tag.startswith('Exif.Thumbnail'):
            result = self._get_exif_thumbnail(*result)
        elif tag.startswith('Xmp.xmp.Thumbnails'):
            w, h, fmt, data = result
            if data:
                data = bytes(data, 'ascii')
                data = codecs.decode(data, 'base64_codec')
                fmt, image = self._decode_thumbnail(data, 'thumbnail')
                result = w, h, fmt, data, image
        return result

    def get_value(self, tag, idx=1):
        if not tag:
            return None
        if 'idx' in tag:
            tag = tag.format(idx=idx)
        family = tag.split('.')[0]
        if family == 'Exif':
            return self.get_exif_value(tag)
        if family == 'Iptc':
            return self.get_iptc_value(tag)
        return self.get_xmp_value(tag)

    def _get_exif_thumbnail(self, w, h, fmt):
        for data, label in self.get_exif_thumbnails():
            if data:
                fmt, image = self._decode_thumbnail(data, label)
                if image:
                    return w, h, fmt, data, image
        return None, None, None, None, None

    def _decode_thumbnail(self, data, label):
        try:
            return MD_Thumbnail.image_from_data(data)
        except Exception as ex:
            logger.error('%s: %s: %s', self._name, label, str(ex))
        return None, None

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
            if sub_tag:
                self.set_value(sub_tag, sub_value, idx=idx)
        if tag == 'Exif.Thumbnail.*' and value[3]:
            self.set_exif_thumbnail_from_buffer(value[3])

    def set_value(self, tag, value, idx=1):
        if not tag:
            return
        if 'idx' in tag:
            tag = tag.format(idx=idx)
        family = tag.split('.')[0]
        if family == 'Exif':
            self.set_exif_value(tag, value)
        elif family == 'Iptc':
            self.set_iptc_value(tag, value)
        else:
            self.set_xmp_value(tag, value)

    def save(self, file_times=None, write_iptc=False):
        if self.read_only:
            return False
        if self.xmp_only:
            self.clear_exif()
            self.clear_iptc()
        elif write_iptc:
            self.set_iptc_encoding()
        else:
            self.clear_iptc()
        if not self.save_file():
            return False
        if not self._path:
            return True
        if file_times:
            os.utime(self._path, file_times)
        # check that data really was saved
        OK = True
        saved_tags = self.open_old(self._path).get_all_tags()
        for tag in self.get_all_tags():
            if tag in saved_tags:
                continue
            if tag in ('Exif.Image.GPSTag', 'Exif.MakerNote.ByteOrder',
                       'Exif.MakerNote.Offset', 'Exif.Photo.MakerNote',
                       'Exif.Image.IPTCNAA'):
                # some tags disappear with good reason
                continue
            family, group, tagname = tag.split('.', 2)
            if family == 'Exif' and group[:5] in (
                    'Canon', 'Casio', 'Fujif', 'Minol', 'Nikon', 'Olymp',
                    'Panas', 'Penta', 'Samsu', 'Sigma', 'Sony1'):
                # maker note tags are often not saved
                logger.warning('%s: tag not saved: %s', self._name, tag)
                continue
            logger.error('%s: tag not saved: %s', self._name, tag)
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
        'Exif.Canon.LensModel*': ('', 'Exif.Canon.LensModel'),
        'Exif.Canon.ModelID*': (
            '', 'Exif.Canon.ModelID', 'Exif.Canon.SerialNumber'),
        'Exif.CanonCs.Lens*': ('', 'Exif.CanonCs.LensType',
                               '', 'Exif.CanonCs.Lens'),
        'Exif.Fujifilm.SerialNumber*': ('', '', 'Exif.Fujifilm.SerialNumber'),
        'Exif.GPSInfo.GPS*': (
            'Exif.GPSInfo.GPSVersionID', 'Exif.GPSInfo.GPSProcessingMethod',
            'Exif.GPSInfo.GPSAltitude', 'Exif.GPSInfo.GPSAltitudeRef',
            'Exif.GPSInfo.GPSLatitude', 'Exif.GPSInfo.GPSLatitudeRef',
            'Exif.GPSInfo.GPSLongitude', 'Exif.GPSInfo.GPSLongitudeRef'),
        'Exif.Image.DateTime*': (
            'Exif.Image.DateTime', 'Exif.Photo.SubSecTime'),
        'Exif.Image.DateTimeOriginal*': ('Exif.Image.DateTimeOriginal', ''),
        'Exif.Image.FNumber*': (
            'Exif.Image.FNumber', 'Exif.Image.ApertureValue'),
        'Exif.Image.Lens*': ('', '', '', 'Exif.Image.LensInfo'),
        'Exif.Image.Make*': (
            'Exif.Image.Make', 'Exif.Image.Model',
            'Exif.Photo.BodySerialNumber'),
        'Exif.Image.UniqueCameraModel*': (
            '', 'Exif.Image.UniqueCameraModel', 'Exif.Image.CameraSerialNumber'),
        'Exif.Nikon3.Lens*': ('', '', '', 'Exif.Nikon3.Lens'),
        'Exif.Nikon3.SerialNumber*': ('', '', 'Exif.Nikon3.SerialNumber'),
        'Exif.NikonLd1.LensIDNumber*': ('', 'Exif.NikonLd1.LensIDNumber'),
        'Exif.NikonLd2.LensIDNumber*': ('', 'Exif.NikonLd2.LensIDNumber'),
        'Exif.NikonLd3.LensIDNumber*': ('', 'Exif.NikonLd3.LensIDNumber'),
        'Exif.OlympusEq.Camera*': (
            '', 'Exif.OlympusEq.CameraType', 'Exif.OlympusEq.SerialNumber'),
        'Exif.OlympusEq.LensModel*': (
            '', 'Exif.OlympusEq.LensModel', 'Exif.OlympusEq.LensSerialNumber'),
        'Exif.Pentax.ModelID*': (
            '', 'Exif.Pentax.ModelID', 'Exif.Pentax.SerialNumber'),
        'Exif.Photo.DateTimeDigitized*': (
            'Exif.Photo.DateTimeDigitized', 'Exif.Photo.SubSecTimeDigitized'),
        'Exif.Photo.DateTimeOriginal*': (
            'Exif.Photo.DateTimeOriginal', 'Exif.Photo.SubSecTimeOriginal'),
        'Exif.Photo.FNumber*': (
            'Exif.Photo.FNumber', 'Exif.Photo.ApertureValue'),
        'Exif.Photo.Lens*': (
            'Exif.Photo.LensMake', 'Exif.Photo.LensModel',
            'Exif.Photo.LensSerialNumber', 'Exif.Photo.LensSpecification'),
        'Exif.Thumbnail.*': (
            'Exif.Thumbnail.ImageWidth', 'Exif.Thumbnail.ImageLength',
            'Exif.Thumbnail.Compression'),
        'Iptc.Application2.Contact*': ('', '', '', 'Iptc.Application2.Contact'),
        'Iptc.Application2.DateCreated*': (
            'Iptc.Application2.DateCreated', 'Iptc.Application2.TimeCreated'),
        'Iptc.Application2.DigitizationDate*': (
            'Iptc.Application2.DigitizationDate',
            'Iptc.Application2.DigitizationTime'),
        'Iptc.Application2.Location*': (
            'Iptc.Application2.SubLocation', 'Iptc.Application2.City',
            'Iptc.Application2.ProvinceState', 'Iptc.Application2.CountryName',
            'Iptc.Application2.CountryCode'),
        'Iptc.Application2.Program*': (
            'Iptc.Application2.Program', 'Iptc.Application2.ProgramVersion'),
        'Xmp.aux.Lens*': ('', 'Xmp.aux.Lens'),
        'Xmp.aux.SerialNumber*': ('', '', 'Xmp.aux.SerialNumber'),
        'Xmp.exif.FNumber*': ('Xmp.exif.FNumber', 'Xmp.exif.ApertureValue'),
        'Xmp.exif.GPS*': (
            'Xmp.exif.GPSVersionID', 'Xmp.exif.GPSProcessingMethod',
            'Xmp.exif.GPSAltitude', 'Xmp.exif.GPSAltitudeRef',
            'Xmp.exif.GPSLatitude', 'Xmp.exif.GPSLongitude'),
        'Xmp.exifEX.Lens*': (
            'Xmp.exifEX.LensMake', 'Xmp.exifEX.LensModel',
            'Xmp.exifEX.LensSerialNumber', 'Xmp.exifEX.LensSpecification'),
        'Xmp.iptc.CreatorContactInfo*': (
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiAdrExtadr',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiAdrCity',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiAdrCtry',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiEmailWork',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiTelWork',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiAdrPcode',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiAdrRegion',
            'Xmp.iptc.CreatorContactInfo/Iptc4xmpCore:CiUrlWork'),
        'Xmp.iptc.Location*': (
            'Xmp.iptc.Location', 'Xmp.photoshop.City', 'Xmp.photoshop.State',
            'Xmp.photoshop.Country', 'Xmp.iptc.CountryCode'),
        'Xmp.Iptc4xmpExt.LocationShown*': (
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:Sublocation',
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:City',
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:ProvinceState',
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:CountryName',
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:CountryCode',
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:WorldRegion',
            'Xmp.Iptc4xmpExt.LocationShown[{idx}]/Iptc4xmpExt:LocationId'),
        'Xmp.Iptc4xmpExt.LocationCreated*': (
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:Sublocation',
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:City',
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:ProvinceState',
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:CountryName',
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:CountryCode',
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:WorldRegion',
            'Xmp.Iptc4xmpExt.LocationCreated[1]/Iptc4xmpExt:LocationId'),
        'Xmp.video.Dims*': ('Xmp.video.Width', 'Xmp.video.Height',
                            None, 'Xmp.video.FrameRate'),
        'Xmp.video.Make*': ('Xmp.video.Make', 'Xmp.video.Model'),
        'Xmp.xmp.Thumbnails*': (
            'Xmp.xmp.Thumbnails[1]/xmpGImg:width',
            'Xmp.xmp.Thumbnails[1]/xmpGImg:height',
            'Xmp.xmp.Thumbnails[1]/xmpGImg:format',
            'Xmp.xmp.Thumbnails[1]/xmpGImg:image'),
        'Xmp.xmp.ThumbnailsXap*': (
            'Xmp.xmp.Thumbnails[1]/xapGImg:width',
            'Xmp.xmp.Thumbnails[1]/xapGImg:height',
            'Xmp.xmp.Thumbnails[1]/xapGImg:format',
            'Xmp.xmp.Thumbnails[1]/xapGImg:image'),
        'Xmp.xmpRights.*': (
            'Xmp.xmpRights.UsageTerms',
            'Xmp.xmpRights.WebStatement',
            'Xmp.plus.Licensor[1]/plus:LicensorURL'),
        }

    # Mapping of tags to Photini data fields Each field has a list of
    # (mode, tag) pairs. The mode is a string containing the write mode
    # (WA (always), WX (if Exif not supported), W0 (clear the tag), or
    # WN (never). The order of the tags sets the precedence when values
    # conflict.
    _tag_list = {
        'alt_text'       : (('WA', 'Xmp.iptc.AltTextAccessibility'),),
        'alt_text_ext'   : (('WA', 'Xmp.iptc.ExtDescrAccessibility'),),
        'aperture'       : (('WA', 'Exif.Photo.FNumber*'),
                            ('W0', 'Exif.Image.FNumber*'),
                            ('WX', 'Xmp.exif.FNumber*')),
        'camera_model'   : (('WA', 'Exif.Image.Make*'),
                            ('WN', 'Exif.Image.UniqueCameraModel*'),
                            ('WN', 'Exif.Canon.ModelID*'),
                            ('WN', 'Exif.Fujifilm.SerialNumber*'),
                            ('WN', 'Exif.Nikon3.SerialNumber*'),
                            ('WN', 'Exif.OlympusEq.Camera*'),
                            ('WN', 'Exif.Pentax.ModelID*'),
                            ('WN', 'Xmp.aux.SerialNumber*'),
                            ('WN', 'Xmp.video.Make*')),
        'contact_info'   : (('WA', 'Xmp.iptc.CreatorContactInfo*'),
                            ('WA', 'Iptc.Application2.Contact*')),
        'copyright'      : (('WA', 'Xmp.dc.rights'),
                            ('WA', 'Exif.Image.Copyright'),
                            ('W0', 'Xmp.tiff.Copyright'),
                            ('WA', 'Iptc.Application2.Copyright')),
        'creator'        : (('WA', 'Exif.Image.Artist'),
                            ('W0', 'Exif.Image.XPAuthor'),
                            ('WN', 'Exif.Photo.CameraOwnerName'),
                            ('WN', 'Exif.Canon.OwnerName'),
                            ('WA', 'Xmp.dc.creator'),
                            ('W0', 'Xmp.tiff.Artist'),
                            ('WA', 'Iptc.Application2.Byline')),
        'creator_title'  : (('WA', 'Xmp.photoshop.AuthorsPosition'),
                            ('WA', 'Iptc.Application2.BylineTitle')),
        'credit_line'    : (('WA', 'Xmp.photoshop.Credit'),
                            ('WA', 'Iptc.Application2.Credit')),
        'date_digitised' : (('WA', 'Exif.Photo.DateTimeDigitized*'),
                            ('WA', 'Xmp.xmp.CreateDate'),
                            ('W0', 'Xmp.exif.DateTimeDigitized'),
                            ('WA', 'Iptc.Application2.DigitizationDate*')),
        'date_modified'  : (('WA', 'Exif.Image.DateTime*'),
                            ('WA', 'Xmp.xmp.ModifyDate'),
                            ('W0', 'Xmp.tiff.DateTime'),
                            ('WN', 'Xmp.video.ModificationDate'),
                            ('WN', 'Xmp.video.MediaModifyDate'),
                            ('WN', 'Xmp.video.TrackModifyDate')),
        'date_taken'     : (('WA', 'Exif.Photo.DateTimeOriginal*'),
                            ('W0', 'Exif.Image.DateTimeOriginal*'),
                            ('WA', 'Xmp.photoshop.DateCreated'),
                            ('W0', 'Xmp.exif.DateTimeOriginal'),
                            ('WA', 'Iptc.Application2.DateCreated*'),
                            ('WN', 'Xmp.video.DateTimeOriginal'),
                            ('WN', 'Xmp.video.CreateDate'),
                            ('WN', 'Xmp.video.CreationDate'),
                            ('WN', 'Xmp.video.DateUTC'),
                            ('WN', 'Xmp.video.MediaCreateDate'),
                            ('WN', 'Xmp.video.TrackCreateDate')),
        'description'    : (('WA', 'Xmp.dc.description'),
                            ('WA', 'Exif.Image.ImageDescription'),
                            ('W0', 'Exif.Image.XPComment'),
                            ('W0', 'Exif.Image.XPSubject'),
                            ('W0', 'Exif.Photo.UserComment'),
                            ('W0', 'Xmp.exif.UserComment'),
                            ('W0', 'Xmp.tiff.ImageDescription'),
                            ('WA', 'Iptc.Application2.Caption'),
                            ('WN', 'Xmp.video.Information')),
        'dimensions'     : (('WN', 'Xmp.video.Dims*'),),
        'focal_length'   : (('WA', 'Exif.Photo.FocalLength'),
                            ('W0', 'Exif.Image.FocalLength'),
                            ('WX', 'Xmp.exif.FocalLength')),
        'focal_length_35': (('WA', 'Exif.Photo.FocalLengthIn35mmFilm'),
                            ('WX', 'Xmp.exif.FocalLengthIn35mmFilm')),
        'gps_info'       : (('WA', 'Exif.GPSInfo.GPS*'),
                            ('WX', 'Xmp.exif.GPS*'),
                            ('WN', 'Xmp.video.GPSCoordinates')),
        'headline'       : (('WA', 'Xmp.photoshop.Headline'),
                            ('WA', 'Iptc.Application2.Headline')),
        'instructions'   : (('WA', 'Xmp.photoshop.Instructions'),
                            ('WA', 'Iptc.Application2.SpecialInstructions')),
        'keywords'       : (('WA', 'Xmp.dc.subject'),
                            ('WA', 'Iptc.Application2.Keywords'),
                            ('W0', 'Exif.Image.XPKeywords')),
        'lens_model'     : (('WA', 'Exif.Photo.Lens*'),
                            ('WX', 'Xmp.exifEX.Lens*'),
                            ('W0', 'Exif.Image.Lens*'),
                            ('WN', 'Exif.Canon.LensModel*'),
                            ('WN', 'Exif.CanonCs.Lens*'),
                            ('WN', 'Exif.OlympusEq.LensModel*'),
                            ('WN', 'Exif.Nikon3.Lens*'),
                            ('WN', 'Exif.NikonLd1.LensIDNumber*'),
                            ('WN', 'Exif.NikonLd2.LensIDNumber*'),
                            ('WN', 'Exif.NikonLd3.LensIDNumber*'),
                            ('W0', 'Xmp.aux.Lens*')),
        'location_shown' : (('WA', 'Xmp.Iptc4xmpExt.LocationShown*'),),
        'location_taken' : (('WA', 'Xmp.Iptc4xmpExt.LocationCreated*'),
                            ('WA', 'Xmp.iptc.Location*'),
                            ('WA', 'Iptc.Application2.Location*')),
        'orientation'    : (('WA', 'Exif.Image.Orientation'),
                            ('WX', 'Xmp.tiff.Orientation')),
        'rating'         : (('WA', 'Xmp.xmp.Rating'),
                            ('W0', 'Exif.Image.Rating'),
                            ('W0', 'Exif.Image.RatingPercent'),
                            ('W0', 'Xmp.MicrosoftPhoto.Rating')),
        'rights'         : (('WA', 'Xmp.xmpRights.*'),),
        'software'       : (('WA', 'Exif.Image.Software'),
                            ('WA', 'Iptc.Application2.Program*'),
                            ('WX', 'Xmp.xmp.CreatorTool')),
        # Both xmpGImg and xapGImg namespaces are specified in different
        # Adobe documents I've seen. xmpGImg appears to be more recent,
        # so we write that but read either.
        'thumbnail'      : (('WA', 'Exif.Thumbnail.*'),
                            ('WX', 'Xmp.xmp.Thumbnails*'),
                            ('W0', 'Xmp.xmp.ThumbnailsXap*')),
        'timezone'       : (('WN', 'Exif.Image.TimeZoneOffset'),
                            ('WN', 'Exif.CanonTi.TimeZone'),
                            ('WN', 'Exif.NikonWt.Timezone'),
                            ('WN', 'Xmp.video.TimeZone')),
        'title'          : (('WA', 'Xmp.dc.title'),
                            ('WA', 'Iptc.Application2.ObjectName'),
                            ('W0', 'Exif.Image.XPTitle'),
                            ('WN', 'Xmp.video.StreamName')),
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
                    self._name, name, tag, str(ex)))
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
            family = tag.split('.')[0]
            if family == 'Exif':
                file_value = value.to_exif()
            elif family == 'Iptc':
                file_value = value.to_iptc()
            else:
                file_value = value.to_xmp()
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
            return cls(path=path)
        except Exception as ex:
            logger.exception(ex)
            return None

    @classmethod
    def open_new(cls, path, image_md):
        sc_path = path + '.xmp'
        try:
            cls.create_sc(sc_path, image_md)
            return cls(path=sc_path)
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


class Metadata(object):
    # type of each Photini data field's data
    _data_type = {
        'alt_text'       : MD_LangAlt,
        'alt_text_ext'   : MD_LangAlt,
        'aperture'       : MD_Aperture,
        'camera_model'   : MD_CameraModel,
        'contact_info'   : MD_ContactInformation,
        'copyright'      : MD_LangAlt,
        'creator'        : MD_MultiString,
        'creator_title'  : MD_String,
        'credit_line'    : MD_String,
        'date_digitised' : MD_DateTime,
        'date_modified'  : MD_DateTime,
        'date_taken'     : MD_DateTime,
        'description'    : MD_LangAlt,
        'dimensions'     : MD_Dimensions,
        'focal_length'   : MD_Rational,
        'focal_length_35': MD_Int,
        'gps_info'       : MD_GPSinfo,
        'headline'       : MD_String,
        'instructions'   : MD_String,
        'keywords'       : MD_Keywords,
        'lens_model'     : MD_LensModel,
        'location_shown' : MD_MultiLocation,
        'location_taken' : MD_Location,
        'orientation'    : MD_Orientation,
        'rating'         : MD_Rating,
        'rights'         : MD_Rights,
        'software'       : MD_Software,
        'thumbnail'      : MD_Thumbnail,
        'timezone'       : MD_Timezone,
        'title'          : MD_LangAlt,
        }

    def __init__(self, path, notify=None):
        super(Metadata, self).__init__()
        # create metadata handlers for image file, video file, and sidecar
        self._path = path
        self._notify = notify
        video_md = None
        self._if = None
        self._sc = SidecarMetadata.open_old(self.find_sidecar())
        self._if = ImageMetadata.open_old(
            path, quiet=self.get_mime_type().split('/')[0] == 'video')
        self.mime_type = self.get_mime_type()
        if self.mime_type.split('/')[0] == 'video':
            video_md = FFMPEGMetadata.open_old(path)
        self.dirty = False
        self.iptc_in_file = self._if and self._if.has_iptc()
        # get maker note info
        if self._if:
            self._maker_note = {
                'make': (self._if.has_exif_tag('Exif.Photo.MakerNote') and
                         self._if.get_value('Exif.Image.Make')),
                'delete': False,
                }
        # read Photini metadata items
        for name in ['timezone'] + list(self._data_type):
            # read data values from first file that has any
            values = []
            for handler in self._sc, video_md, self._if:
                if not handler:
                    continue
                values += handler.read(name, self._data_type[name])
                if values and handler == self._sc:
                    break
            # merge in camera timezone
            if (name in ('date_digitised', 'date_modified', 'date_taken')
                    and self.timezone):
                for n, (tag, value) in enumerate(values):
                    if not (tag.startswith('Exif') or
                            tag.startswith('Xmp.video')):
                        continue
                    value = dict(value)
                    value['tz_offset'] = self.timezone
                    values[n] = (tag, self._data_type[name](value))
                    logger.info('%s: merged camera timezone offset', tag)
            # choose result and merge in non-matching data so user can review it
            value = None
            if values:
                info = '{}({})'.format(os.path.basename(self._path), name)
                tag, value = values[0]
                logger.debug('%s: set from %s', info, tag)
            for tag2, value2 in values[1:]:
                value = value.merge(info, tag2, value2)
            super(Metadata, self).__setattr__(name, value)

    def find_sidecar(self):
        for base in (os.path.splitext(self._path)[0], self._path):
            for ext in ('.xmp', '.XMP', '.Xmp'):
                sc_path = base + ext
                if os.path.exists(sc_path):
                    return sc_path
        return None

    # Exiv2 uses the Exif.Image.Make value to decode Exif.Photo.MakerNote
    # If we change Exif.Image.Make we should delete Exif.Photo.MakerNote
    def camera_change_ok(self, camera_model):
        if not (self._if and self._maker_note['make']):
            return True
        if not camera_model:
            return False
        return self._maker_note['make'] == camera_model['make']

    def set_delete_makernote(self):
        if self._if:
            self._maker_note['delete'] = True

    def clone(self, data):
        image = ImageMetadata(buf=data)
        if self._if:
            image._image.setMetadata(self._if._image)
        if self._sc:
            image.merge_sc(self._sc)
        image.save_file()
        return image._image

    def _handler_save(self, handler, *arg, **kw):
        # store Photini metadata items
        for name in self._data_type:
            value = getattr(self, name)
            handler.write(name, value)
        # save file
        return handler.save(*arg, **kw)

    def save(self, if_mode=True, sc_mode='auto',
             iptc_mode='preserve', file_times=None):
        if not self.dirty:
            return
        self.software = 'Photini editor v' + __version__
        OK = False
        write_iptc = (iptc_mode == 'create'
                      or (iptc_mode == 'preserve' and self.iptc_in_file))
        try:
            # save to image file
            if if_mode and self._if:
                if self._maker_note['delete']:
                    if not self.camera_change_ok(self.camera_model):
                        self._if.clear_maker_note()
                    self._maker_note['delete'] = False
                OK = self._handler_save(
                    self._if, file_times=file_times, write_iptc=write_iptc)
                if OK:
                    self.iptc_in_file = write_iptc
            if not OK:
                # can't write to image file so must create side car
                sc_mode = 'always'
            # create side car
            if sc_mode == 'always' and not self._sc:
                self._sc = SidecarMetadata.open_new(self._path, self._if)
            # save or delete side car
            if self._sc:
                if sc_mode == 'delete':
                    self._if.merge_sc(self._sc)
                    self._sc = self._sc.delete()
                else:
                    # workaround for bug in exiv2 xmp timestamp altering
                    self._sc.clear_dates()
                    OK = self._handler_save(self._sc, file_times=file_times)
        except Exception as ex:
            logger.exception(ex)
            return
        if OK:
            self.dirty = False
            if self._notify:
                self._notify(self.dirty)

    def get_preview_images(self):
        md = self._if
        if not md:
            return
        for result in md.get_preview_images():
            yield result

    def get_sensor_size(self):
        md = self._if or self._sc
        if not md:
            return 0, 0
        # get largest preview
        sensor_size = {}
        sensor_size['x'], sensor_size['y'] = md.get_preview_imagedims()
        # search metadata for something larger
        for key in md.get_all_tags():
            family, group, tag = key.split('.', 2)
            if tag in ('PixelXDimension', 'ImageWidth'):
                sensor_size['x'] = max(sensor_size['x'], int(md.get_value(key)))
            elif tag in ('PixelYDimension', 'ImageLength'):
                sensor_size['y'] = max(sensor_size['y'], int(md.get_value(key)))
        return sensor_size

    def get_crop_factor(self):
        md = self._if or self._sc
        if not md:
            return None
        # get relevant metadata
        sensor_size = self.get_sensor_size()
        if not sensor_size['x'] or not sensor_size['y']:
            return None
        resolution = {}
        resolution_source = None, None
        for key in md.get_all_tags():
            family, group, tag = key.split('.', 2)
            if tag in ('FocalPlaneXResolution', 'FocalPlaneYResolution',
                       'FocalPlaneResolutionUnit'):
                resolution[key] = md.get_value(key)
                resolution_source = family, group
        # convert resolution values
        if not resolution:
            return None
        family, group = resolution_source
        for tag in ('FocalPlaneXResolution', 'FocalPlaneYResolution',
                    'FocalPlaneResolutionUnit'):
            key = '.'.join((family, group, tag))
            if key not in resolution:
                return None
            resolution[tag] = resolution[key]
        resolution['x'] = safe_fraction(resolution['FocalPlaneXResolution'])
        resolution['y'] = safe_fraction(resolution['FocalPlaneYResolution'])
        resolution['unit'] = int(resolution['FocalPlaneResolutionUnit'])
        # find largest image dimensions
        w = sensor_size['x'] / resolution['x']
        h = sensor_size['y'] / resolution['y']
        d = math.sqrt((h ** 2) + (w ** 2))
        if resolution['unit'] == 3:
            # unit is cm
            d *= 10.0
        elif resolution['unit'] in (None, 1, 2):
            # unit is (assumed to be) inches
            d *= 25.4
        else:
            logger.info('Unknown resolution unit %d', resolution['unit'])
            return None
        # 35 mm film diagonal is 43.27 mm
        crop_factor = 43.27 / d
        # round to 2 digits
        scale = 10 ** int(math.log10(crop_factor))
        crop_factor = round(crop_factor / scale, 1) * scale
        return crop_factor

    def get_mime_type(self):
        result = None
        if self._if:
            result = self._if.mime_type
        if not result:
            result = mimetypes.guess_type(self._path, strict=False)[0]
        if not result:
            result = imghdr.what(self._path)
            if result:
                result = 'image/' + result
        # anything not recognised is assumed to be 'raw'
        if not result:
            result = 'image/raw'
        return result

    def __setattr__(self, name, value):
        if name not in self._data_type:
            return super(Metadata, self).__setattr__(name, value)
        if value in (None, '', [], {}):
            value = None
        elif not isinstance(value, self._data_type[name]):
            new_value = self._data_type[name](value)
            value = self._data_type[name](value) or None
        if getattr(self, name) == value:
            return
        super(Metadata, self).__setattr__(name, value)
        if name == 'gps_info':
            # erase other GPS stuff such as direction and speed
            if self._if:
                self._if.clear_gps()
            if self._sc:
                self._sc.clear_gps()
        if not self.dirty:
            self.dirty = True
            if self._notify:
                self._notify(self.dirty)

    def changed(self):
        return self.dirty
