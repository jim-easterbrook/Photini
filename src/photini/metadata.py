##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-26  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
from contextlib import contextmanager
from fractions import Fraction
import logging
import math
import mimetypes
import os
import re

import exiv2
import filetype

from photini import __version__
from photini.exiv2 import MetadataHandler
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
            'ffmpeg/streams[0]/width', 'ffmpeg/streams[0]/height'),
        'ffmpeg/streams[0]/duration_ts': (
            'ffmpeg/streams[0]/duration_ts', 'ffmpeg/streams[0]/time_base'),
        'ffmpeg/streams[0]/frames': (
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
        'video_duration': ('ffmpeg/streams[0]/duration',
                           'ffmpeg/streams[0]/duration_ts',
                           'ffmpeg/streams[0]/frames'),
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
    def clear_match(self, tag):
        family = tag.split('.')[0]
        data = {'Exif': self._exifData,
                'Iptc': self._iptcData,
                'Xmp': self._xmpData}[family]
        regexp = self._match_tags[tag][0]
        datum = data.begin()
        while datum != data.end():
            if regexp.match(datum.key()):
                datum = data.erase(datum)
            else:
                next(datum)

    def clear_value(self, tag):
        {'Exif': self.clear_exif_tag,
         'Iptc': self.clear_iptc_tag,
         'Xmp': self.clear_xmp_tag}[tag.split('.')[0]](tag)

    def get_match(self, tag):
        result = {}
        family = tag.split('.')[0]
        data = {'Exif': self._exifData,
                'Iptc': self._iptcData,
                'Xmp': self._xmpData}[family]
        decode = {'Exif': self.decode_exif_value,
                  'Iptc': self.decode_iptc_value,
                  'Xmp': self.decode_xmp_value}[family]
        regexp = self._match_tags[tag][0]
        for datum in data:
            key = datum.key()
            match = regexp.match(key)
            if match:
                result[match.group(1)] = decode(key, datum)
        return result

    def get_value(self, tag):
        if not tag:
            return None
        family = tag.split('.')[0]
        if family == 'Exif':
            return self.get_exif_value(tag)
        if family == 'Iptc':
            return self.get_iptc_value(tag)
        return self.get_xmp_value(tag)

    def get_image_size(self):
        return {'width': self._image.pixelWidth(),
                'height': self._image.pixelHeight()}

    def get_exif_thumbnail(self):
        for data, label in self.select_exif_thumbnail():
            if data:
                try:
                    return MD_Thumbnail.from_data(data)
                except Exception as ex:
                    logger.error('%s: %s: %s', self._name, label, str(ex))
        return {}

    def set_exif_thumbnail(self, file_value):
        thumb = exiv2.ExifThumb(self._exifData)
        if not file_value:
            thumb.erase()
            return
        thumb.setJpegThumbnail(file_value['ImageData'], (72, 1), (72, 1), 2)
        self.set_exif_value('Exif.Thumbnail.ImageWidth',
                            file_value['ImageWidth'])
        self.set_exif_value('Exif.Thumbnail.ImageLength',
                            file_value['ImageLength'])

    def get_xmp_thumbnail(self):
        file_value = self.get_xmp_value('Xmp.xmp.Thumbnails')
        for data, label in self.select_xmp_thumbnail(file_value):
            if data:
                try:
                    data = codecs.decode(data, 'base64_codec')
                    return MD_Thumbnail.from_data(data)
                except Exception as ex:
                    logger.error('%s: %s: %s', self._name, label, str(ex))
        return {}

    def set_xmp_thumbnail(self, file_value):
        if not file_value:
            # don't clear XMP thumbnails
            return
        tag = 'Xmp.xmp.Thumbnails'
        if self._xmp_thumb_idx:
            # replace or append one thumbnail of the array
            tag = '{}[{}]'.format(tag, self._xmp_thumb_idx)
            file_value = file_value[0]
        self.set_xmp_value(tag, file_value)

    def set_match(self, tag, value):
        fmt = self._match_tags[tag][1]
        for key in value:
            sub_tag = fmt.format(key)
            self.set_value(sub_tag, value[key])

    def set_value(self, tag, value):
        if not tag:
            return
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
        if exiv2.__version_tuple__ >= (0, 18):
            buf = self._image.data()
        else:
            buf = memoryview(self._image.io())
        saved_tags = self.__class__(buf=buf).get_all_tags()
        for tag in self.get_all_tags():
            if tag in saved_tags:
                continue
            if tag in ('Exif.Image.ExifTag', 'Exif.Image.GPSTag',
                       'Exif.MakerNote.ByteOrder', 'Exif.MakerNote.Offset',
                       'Exif.Photo.MakerNote', 'Exif.Image.IPTCNAA'):
                # some tags disappear with good reason
                continue
            family, group, tagname = tag.split('.', 2)
            if family == 'Exif' and exiv2.ExifTags.isMakerGroup(group):
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

    # some data requires dedicated functions to read and write it
    _function_tags = {
        'Exif.Thumbnail': (get_exif_thumbnail, set_exif_thumbnail),
        'Xmp.Thumbnail': (get_xmp_thumbnail, set_xmp_thumbnail),
        'exiv2.pixelWidthHeight': (get_image_size, ),
        }
    # Some tags are always read & written in groups, but are represented
    # by a single name. These return a dict of matching keys and values
    _match_tags = {
        'Exif.Any.Timezone': (re.compile(r'(.*[Tt]ime[Zz]one.*)'),),
        'Exif.Canon.Camera': (
            re.compile(r'Exif\.Canon\.(ModelID|SerialNumber)'),),
        'Exif.Canon.Lens': (re.compile(r'Exif\.Canon(?:|Cs|Le)\.(Lens.*)'),),
        'Exif.FocalPlaneResolution': (
            re.compile(r'(Exif\..*?\.FocalPlane.*Resolution.*)'),),
        'Exif.Fujifilm.Camera': (
            re.compile(r'Exif\.Fujifilm\.(SerialNumber)'),),
        'Exif.GPSInfo.GPS': (
            re.compile(r'Exif\.GPSInfo\.(GPS.*)'), 'Exif.GPSInfo.{}'),
        'Exif.Image.ApertureValue': (
            re.compile(r'Exif\.Image\.(ApertureValue)'),),
        'Exif.Image.Camera1': (
            re.compile(r'Exif\.Image\.(?:Camera)?(Make|Model|SerialNumber)'),
            'Exif.Image.{}'),
        'Exif.Image.Camera2': (re.compile(r'Exif\.Image\.(.*CameraModel)'),),
        'Exif.Image.DateTime': (
            re.compile(r'Exif\..*\.((Date|SubSec|Offset)Time)'), 'Exif.{}'),
        'Exif.Image.FNumber': (
            re.compile(r'Exif\.Image\.(ApertureValue|FNumber)'),),
        'Exif.Image.FocalLength': (
            re.compile(r'Exif\.Image\.(FocalLength.*)'), 'Exif.Image.{}'),
        'Exif.Image.Lens': (re.compile(r'Exif\.Image\.(Lens.*)'),),
        'Exif.ImageWidthLength': (
            re.compile(r'(Exif\..*?Image.*?\.Image(Width|Length))'),),
        'Exif.Minolta.Lens': (re.compile(r'Exif\.Minolta\.(Lens.*)'),),
        'Exif.Nikon.Camera': (re.compile(r'Exif\.Nikon3\.(Serial.*)'),),
        'Exif.Nikon.Lens': (
            re.compile(r'Exif\.Nikon(?:Ld.|3)\.(Lens(?:|ID.*)$)'),),
        'Exif.Olympus.Camera': (re.compile(
            r'Exif\.Olympus.*?\.(CameraID|CameraType|SerialNumber.*)'),),
        'Exif.Olympus.Lens': (re.compile(r'Exif\.OlympusEq\.(Lens.*)'),),
        'Exif.Panasonic.Camera': (re.compile(
            r'Exif\.Panasonic\.(InternalSerialNumber)'),),
        'Exif.Pentax.Camera': (re.compile(
            r'Exif\.Pentax.*?\.(ModelID|SerialNumber)'),),
        'Exif.Pentax.Lens': (re.compile(r'Exif\.Pentax.*?\.(LensType)'),),
        'Exif.Photo.ApertureValue': (
            re.compile(r'Exif\.Photo\.(ApertureValue)'),),
        'Exif.Photo.Camera': (re.compile(r'Exif\.Photo\.(BodySerialNumber)'),),
        'Exif.Photo.DateTimeDigitized': (
            re.compile(r'Exif\..*\.(.*Time)Digitized'), 'Exif.{}Digitized'),
        'Exif.Photo.DateTimeOriginal': (
            re.compile(r'Exif\..*\.(.*Time)Original'), 'Exif.{}Original'),
        'Exif.Photo.FNumber': (re.compile(
            r'Exif\.Photo\.(ApertureValue|FNumber)'), 'Exif.Photo.{}'),
        'Exif.Photo.FocalLength': (
            re.compile(r'Exif\.Photo\.(FocalLength.*)'), 'Exif.Photo.{}'),
        'Exif.Photo.Lens': (
            re.compile(r'Exif\.Photo\.Lens(.*)'), 'Exif.Photo.Lens{}'),
        'Exif.PixelXYDimension': (
            re.compile(r'Exif\..*?\.(Pixel(X|Y)Dimension)'),),
        'Exif.Sigma.Camera': (re.compile(r'Exif\.Sigma\.(SerialNumber)'),),
        'Exif.Sony.Camera': (re.compile(
            r'Exif\.Sony\d\.(SonyModelID|SerialNumber)'),),
        'Exif.Sony.Lens': (re.compile(r'Exif\.Sony\d\.(Lens.*)'),),
        'Iptc.Application2.DateCreated': (
            re.compile(r'Iptc\.Application2\.(.*)Created'),
            'Iptc.Application2.{}Created'),
        'Iptc.Application2.DigitizationDate': (
            re.compile(r'Iptc\.Application2\.Digitization(.*)'),
            'Iptc.Application2.Digitization{}'),
        'Iptc.Application2.Location': (
            re.compile(r'Iptc\.Application2\.(SubLocation|City|ProvinceState'
                       '|CountryName|CountryCode)'),
            'Iptc.Application2.{}'),
        'Iptc.Application2.Program': (re.compile(
            r'Iptc\.Application2\.(Program.*)'), 'Iptc.Application2.{}'),
        'Xmp.aux.Camera': (re.compile(r'Xmp\.aux\.(SerialNumber)'),),
        'Xmp.aux.Lens': (re.compile(r'Xmp\.aux\.(Lens.*)'),),
        'Xmp.exif.ApertureValue': (re.compile(r'Xmp\.exif\.(ApertureValue)'),),
        'Xmp.exif.FNumber': (re.compile(
            r'Xmp\.exif\.(ApertureValue|FNumber)'), 'Xmp.exif.{}'),
        'Xmp.exif.GPS': (re.compile(r'Xmp\.exif\.(GPS.*)'), 'Xmp.exif.{}'),
        'Xmp.exif.FocalLength': (
            re.compile(r'Xmp\.exif\.(FocalLength.*)'), 'Xmp.exif.{}'),
        'Xmp.exifEX.Lens': (
            re.compile(r'Xmp\.exifEX\.Lens(.*)'), 'Xmp.exifEX.Lens{}'),
        'Xmp.IPTCLegacy.Location': (
            re.compile(r'Xmp\.(iptc.Location|photoshop.City|photoshop.State'
                       '|photoshop.Country|iptc.CountryCode)'), 'Xmp.{}'),
        'Xmp.PixelXYDimension': (
            re.compile(r'Xmp\.exif\.(Pixel(X|Y)Dimension)'),),
        'Xmp.xmpRights': (
            re.compile(r'Xmp\.xmpRights\.(.*)'), 'Xmp.xmpRights.{}'),
        'Xmp.video.Camera': (re.compile(r'Xmp\.video\.(Make|Model)'),),
        'Xmp.video.WidthHeight': (re.compile(r'Xmp\.video\.(Width|Height)'),),
        }
    # Mapping of tags to Photini data fields Each field has a list of
    # (mode, tag) pairs. The mode is a string containing the write mode
    # (WA (always), WX (if Exif not supported), W0 (clear the tag), or
    # WN (never). The order of the tags sets the precedence when values
    # conflict.
    _tag_list = {
        'alt_text'       : (('WA', 'Xmp.iptc.AltTextAccessibility'),),
        'alt_text_ext'   : (('WA', 'Xmp.iptc.ExtDescrAccessibility'),),
        'aperture'       : (('WA', 'Exif.Photo.FNumber'),
                            ('WN', 'Exif.Photo.ApertureValue'),
                            ('W0', 'Exif.Image.FNumber'),
                            ('WN', 'Exif.Image.ApertureValue'),
                            ('WX', 'Xmp.exif.FNumber'),
                            ('WN', 'Xmp.exif.ApertureValue')),
        'camera_model'   : (('WA', 'Exif.Image.Camera1'),
                            ('W0', 'Exif.Image.Camera2'),
                            ('W0', 'Exif.Photo.Camera'),
                            ('WN', 'Exif.Canon.Camera'),
                            ('WN', 'Exif.Fujifilm.Camera'),
                            ('WN', 'Exif.Nikon.Camera'),
                            ('WN', 'Exif.Olympus.Camera'),
                            ('WN', 'Exif.Panasonic.Camera'),
                            ('WN', 'Exif.Pentax.Camera'),
                            ('WN', 'Exif.Sigma.Camera'),
                            ('WN', 'Exif.Sony.Camera'),
                            ('WN', 'Xmp.aux.Camera'),
                            ('W0', 'Xmp.video.Camera')),
        'contact_info'   : (('WA', 'Xmp.plus.Licensor'),
                            ('W0', 'Xmp.iptc.CreatorContactInfo')),
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
        'date_digitised' : (('WA', 'Exif.Photo.DateTimeDigitized'),
                            ('WA', 'Xmp.xmp.CreateDate'),
                            ('W0', 'Xmp.exif.DateTimeDigitized'),
                            ('WA', 'Iptc.Application2.DigitizationDate')),
        'date_modified'  : (('WA', 'Exif.Image.DateTime'),
                            ('WA', 'Xmp.xmp.ModifyDate'),
                            ('W0', 'Xmp.tiff.DateTime'),
                            ('W0', 'Xmp.video.ModificationDate'),
                            ('W0', 'Xmp.video.MediaModifyDate'),
                            ('W0', 'Xmp.video.TrackModifyDate')),
        'date_taken'     : (('WA', 'Exif.Photo.DateTimeOriginal'),
                            ('WA', 'Xmp.photoshop.DateCreated'),
                            ('W0', 'Xmp.exif.DateTimeOriginal'),
                            ('WA', 'Iptc.Application2.DateCreated'),
                            ('W0', 'Xmp.video.DateTimeOriginal'),
                            ('W0', 'Xmp.video.CreateDate'),
                            ('W0', 'Xmp.video.CreationDate'),
                            ('W0', 'Xmp.video.DateUTC'),
                            ('W0', 'Xmp.video.MediaCreateDate'),
                            ('W0', 'Xmp.video.TrackCreateDate')),
        'description'    : (('WA', 'Xmp.dc.description'),
                            ('WA', 'Exif.Image.ImageDescription'),
                            ('W0', 'Exif.Image.XPComment'),
                            ('W0', 'Exif.Image.XPSubject'),
                            ('W0', 'Exif.Photo.UserComment'),
                            ('W0', 'Xmp.exif.UserComment'),
                            ('W0', 'Xmp.tiff.ImageDescription'),
                            ('WA', 'Iptc.Application2.Caption'),
                            ('W0', 'Xmp.video.Information')),
        'dimensions'     : (('W0', 'Xmp.video.WidthHeight'),
                            ('WN', 'exiv2.pixelWidthHeight'),
                            ('WN', 'Exif.ImageWidthLength'),
                            ('WN', 'Exif.PixelXYDimension'),
                            ('WN', 'Xmp.PixelXYDimension')),
        'focal_length'   : (('WA', 'Exif.Photo.FocalLength'),
                            ('W0', 'Exif.Image.FocalLength'),
                            ('WX', 'Xmp.exif.FocalLength')),
        'gps_info'       : (('WA', 'Exif.GPSInfo.GPS'),
                            ('WX', 'Xmp.exif.GPS'),
                            ('W0', 'Xmp.video.GPSCoordinates')),
        'headline'       : (('WA', 'Xmp.photoshop.Headline'),
                            ('WA', 'Iptc.Application2.Headline')),
        'image_region'   : (('WA', 'Xmp.iptcExt.ImageRegion'),
                            ('WA', 'Xmp.mwg-rs.Regions'),
                            ('WA', 'Xmp.MP.RegionInfo')),
        'instructions'   : (('WA', 'Xmp.photoshop.Instructions'),
                            ('WA', 'Iptc.Application2.SpecialInstructions')),
        'keywords'       : (('WA', 'Xmp.dc.subject'),
                            ('WA', 'Iptc.Application2.Keywords'),
                            ('W0', 'Exif.Image.XPKeywords')),
        'lens_model'     : (('WA', 'Exif.Photo.Lens'),
                            ('WX', 'Xmp.exifEX.Lens'),
                            ('W0', 'Exif.Image.Lens'),
                            ('WN', 'Exif.Canon.Lens'),
                            ('WN', 'Exif.Minolta.Lens'),
                            ('WN', 'Exif.Nikon.Lens'),
                            ('WN', 'Exif.Olympus.Lens'),
                            ('WN', 'Exif.Pentax.Lens'),
                            ('WN', 'Exif.Sony.Lens'),
                            ('W0', 'Xmp.aux.Lens')),
        'location_shown' : (('WA', 'Xmp.iptcExt.LocationShown'),),
        'location_taken' : (('WA', 'Xmp.iptcExt.LocationCreated'),
                            ('WA', 'Xmp.IPTCLegacy.Location'),
                            ('WA', 'Iptc.Application2.Location')),
        'nested_tags'    : (('WA', 'Xmp.lr.hierarchicalSubject'),
                            ('WA', 'Xmp.digiKam.TagsList')),
        'orientation'    : (('WA', 'Exif.Image.Orientation'),
                            ('WX', 'Xmp.tiff.Orientation')),
        'people'         : (('WA', 'Xmp.iptcExt.PersonInImage'),),
        'rating'         : (('WA', 'Xmp.xmp.Rating'),
                            ('W0', 'Exif.Image.Rating'),
                            ('W0', 'Exif.Image.RatingPercent'),
                            ('W0', 'Xmp.MicrosoftPhoto.Rating')),
        'resolution'     : (('WN', 'Exif.FocalPlaneResolution'),),
        'rights'         : (('WA', 'Xmp.xmpRights'),),
        'software'       : (('WA', 'Exif.Image.Software'),
                            ('WA', 'Iptc.Application2.Program'),
                            ('WX', 'Xmp.xmp.CreatorTool')),
        'thumbnail'      : (('WA', 'Exif.Thumbnail'),
                            ('WX', 'Xmp.Thumbnail')),
        'timezone'       : (('WN', 'Exif.Any.Timezone'),),
        'title'          : (('WA', 'Xmp.dc.title'),
                            ('WA', 'Iptc.Application2.ObjectName'),
                            ('W0', 'Exif.Image.XPTitle'),
                            ('W0', 'Xmp.video.StreamName')),
        'video_duration' : (('WN', 'Xmp.video.Duration'),),
        }

    def read(self, name, type_):
        result = []
        for mode, tag in self._tag_list[name]:
            try:
                if tag in self._function_tags:
                    file_value = self._function_tags[tag][0](self)
                elif tag in self._match_tags:
                    file_value = self.get_match(tag)
                else:
                    file_value = self.get_value(tag)
                value = type_.from_exiv2(file_value, tag)
            except ValueError as ex:
                logger.error('{}({}), {}: {}'.format(
                    self._name, name, tag, str(ex)))
                logger.exception(ex)
                continue
            except Exception as ex:
                logger.exception(ex)
                continue
            if value:
                result.append((tag, value))
        return result

    def write(self, name, value, changed):
        for mode, tag in self._tag_list[name]:
            if mode == 'WN':
                continue
            if ((not value) or (mode == 'W0')
                    or (mode == 'WX' and not self.xmp_only)):
                if tag in self._function_tags:
                    file_value = self._function_tags[tag][1](self, None)
                elif tag in self._match_tags:
                    self.clear_match(tag)
                else:
                    self.clear_value(tag)
                continue
            file_value = value.to_exiv2(tag)
            if tag in self._function_tags:
                file_value = self._function_tags[tag][1](self, file_value)
            elif tag in self._match_tags:
                if changed:
                    # wipe any tags in the group that we don't save
                    self.clear_match(tag)
                self.set_match(tag, file_value)
            else:
                self.set_value(tag, file_value)


class SidecarMetadata(ImageMetadata):
    pass


class MetadataOpener(object):
    def __init__(self, path, *arg, **kw):
        self.path = path
        self.arg = arg
        self.kw = kw
        self.quiet = False

    @contextmanager
    def open(self, write=False):
        result = None
        if self.path:
            try:
                result = self.handler(self.path, *self.arg, **self.kw)
            except exiv2.Exiv2Error as ex:
                # expected if unrecognised file format
                name = os.path.basename(self.path)
                if self.quiet:
                    logger.info('%s: %s', name, str(ex))
                else:
                    logger.warning('%s: %s', name, str(ex))
                self.path = None
            except Exception as ex:
                logger.error('Exception opening %s', self.path)
                logger.exception(ex)
                self.path = None
        try:
            yield result
        finally:
            pass


class VideoHandler(MetadataOpener):
    handler = FFMPEGMetadata


class SidecarHandler(MetadataOpener):
    handler = SidecarMetadata

    @contextmanager
    def open(self, write=False):
        # workaround for bug in exiv2 xmp timestamp altering
        # see https://github.com/Exiv2/exiv2/issues/1998
        if write and not exiv2.testVersion(0, 28, 0):
            with super(SidecarHandler, self).open(write=write) as result:
                if result:
                    for name in ('date_digitised', 'date_modified',
                                 'date_taken'):
                        result.write(name, None, True)
                    result.save()
        with super(SidecarHandler, self).open(write=write) as result:
            try:
                yield result
            finally:
                pass

    def create_sidecar(self, image_handler):
        if self.path or not image_handler.path:
            return
        sc_path = image_handler.path + '.xmp'
        try:
            with image_handler.open() as image_md:
                self.handler.create_sc(sc_path, image_md)
            self.path = sc_path
        except Exception as ex:
            logger.error('Exception creating %s', sc_path)
            logger.exception(ex)

    def delete_sidecar(self):
        if not self.path:
            return
        os.unlink(self.path)
        self.path = None


class ImageHandler(MetadataOpener):
    handler = ImageMetadata

    def __init__(self, path, *arg, **kw):
        super(ImageHandler, self).__init__(path, *arg, **kw)
        # guess mime type from file name
        self.mime_type = mimetypes.guess_type(path, strict=False)[0]
        # guess mime type from first few bytes of data
        if not self.mime_type:
            kind = filetype.guess(path)
            if kind:
                self.mime_type = kind.mime
        # anything not recognised is assumed to be 'raw'
        if not self.mime_type:
            self.mime_type = 'image/raw'
        self.quiet = self.mime_type and self.mime_type.split('/')[0] == 'video'
        # other init
        self.maker_note = {'make': '', 'delete': False}
        self.iptc_in_file = False
        self.unread = True

    @contextmanager
    def open(self, write=False):
        with super(ImageHandler, self).open(write=write) as result:
            if result and self.unread:
                self.unread = False
                # get some stuff from file now it's open
                self.mime_type = result.mime_type
                self.maker_note['make'] = (
                    result.has_exif_tag('Exif.Photo.MakerNote') and
                    result.get_value('Exif.Image.Make'))
                self.iptc_in_file = result.has_iptc()
            if result and write and self.maker_note['delete']:
                result.clear_maker_note()
                self.maker_note['delete'] = False
            try:
                yield result
            finally:
                pass


class Metadata(object):
    # type of each Photini data field's data
    _data_type = {
        'alt_text'       : MD_LangAlt,
        'alt_text_ext'   : MD_LangAlt,
        'aperture'       : MD_Aperture,
        'camera_model'   : MD_CameraModel,
        'contact_info'   : MD_ContactInformation,
        'copyright'      : MD_LangAlt,
        'creator'        : MD_Creator,
        'creator_title'  : MD_String,
        'credit_line'    : MD_String,
        'date_digitised' : MD_DateTime,
        'date_modified'  : MD_DateTime,
        'date_taken'     : MD_DateTime,
        'description'    : MD_LangAlt,
        'dimensions'     : MD_Dimensions,
        'focal_length'   : MD_FocalLength,
        'gps_info'       : MD_GPSinfo,
        'headline'       : MD_String,
        'image_region'   : MD_ImageRegion,
        'instructions'   : MD_String,
        'keywords'       : MD_Keywords,
        'lens_model'     : MD_LensModel,
        'location_shown' : MD_MultiLocation,
        'location_taken' : MD_SingleLocation,
        'nested_tags'    : MD_HierarchicalTags,
        'orientation'    : MD_Orientation,
        'people'         : MD_MultiString,
        'rating'         : MD_Rating,
        'resolution'     : MD_Resolution,
        'rights'         : MD_Rights,
        'software'       : MD_Software,
        'thumbnail'      : MD_Thumbnail,
        'timezone'       : MD_Timezone,
        'title'          : MD_LangAlt,
        'video_duration' : MD_VideoDuration,
        }

    def __init__(self, path, notify=None):
        super(Metadata, self).__init__()
        # create metadata handlers for image file, video file, and sidecar
        self._path = path
        self._notify = notify
        self._if = ImageHandler(path)
        self._sc = SidecarHandler(self.find_sidecar())
        if self._if.mime_type.split('/')[0] == 'video':
            video_md = VideoHandler(path)
        else:
            video_md = VideoHandler(None)
        self.dirty = False
        self._changed = {}
        # read Photini metadata items
        values = defaultdict(list)
        names = list(self._data_type)
        for file_handler in self._sc, video_md, self._if:
            with file_handler.open() as handler:
                if not handler:
                    continue
                for name in list(names):
                    values[name] += handler.read(name, self._data_type[name])
                    if (name != 'dimensions' and values[name]
                            and file_handler == self._sc):
                        # ignore values from image or video file
                        names.remove(name)
        self.mime_type = self._if.mime_type
        # choose values and merge in non-matching data so user can review it
        for name in self._data_type:
            value = self._data_type[name](None)
            if values[name]:
                info = '{}({})'.format(os.path.basename(self._path), name)
                tag, value = values[name][0]
                logger.debug('%s: set from %s', info, tag)
            for tag2, value2 in values[name][1:]:
                value = value.merge(info, tag2, value2)
            super(Metadata, self).__setattr__(name, value)
        # merge image dimensions into image regions
        if not self.image_region['AppliedToDimensions']:
            dims = {'w': self.dimensions['width'],
                    'h': self.dimensions['height']}
            super(Metadata, self).__setattr__(
                'image_region', self.image_region.set_dimensions(dims))
        # merge people in regions into people in image
        if self.image_region:
            name = 'people'
            value = list(self[name])
            for region in self.image_region:
                for person in region['Iptc4xmpExt:PersonInImage']:
                    if person not in value:
                        value.append(person)
                        logger.info('%s(%s): merged "%s" from image region',
                                    os.path.basename(self._path), name, person)
            super(Metadata, self).__setattr__(
                name, self._data_type[name](value))
        # merge in camera timezone
        if self.timezone:
            for name in ('date_digitised', 'date_modified', 'date_taken'):
                value = self[name]
                if value['tz_offset'] is not None:
                    continue
                value = dict(value)
                value['tz_offset'] = self.timezone
                super(Metadata, self).__setattr__(
                    name, self._data_type[name](value))
                logger.info('%s(%s): merged camera timezone offset',
                            os.path.basename(self._path), name)

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
        if not (self._if.maker_note['make']):
            return True
        if not camera_model:
            return False
        return self._if.maker_note['make'] == camera_model['Make']

    def set_delete_makernote(self):
        self._if.maker_note['delete'] = True

    def clone(self, data):
        image = ImageMetadata(buf=data)
        with self._if.open() as handler:
            if handler:
                image._image.setMetadata(handler._image)
        with self._sc.open() as handler:
            if handler:
                image.merge_sc(handler)
        image.save_file()
        if exiv2.__version_tuple__ >= (0, 18):
            data = image._image.data()
        else:
            data = memoryview(image._image.io())
        return data

    def _handler_save(self, file_handler, *arg, **kw):
        with file_handler.open(write=True) as handler:
            if not handler:
                return False
            # store Photini metadata items
            for name in self._data_type:
                value = getattr(self, name)
                handler.write(name, value, self._changed.get(name))
            # save file
            return handler.save(*arg, **kw)

    def save(self, if_mode=True, sc_mode='auto',
             iptc_mode='preserve', file_times=None):
        if not self.dirty:
            return
        self.software = 'Photini editor v' + __version__
        OK = False
        write_iptc = (iptc_mode == 'create'
                      or (iptc_mode == 'preserve' and self._if.iptc_in_file))
        try:
            # save to image file
            if if_mode:
                if (self._if.maker_note['delete'] and
                        self.camera_change_ok(self.camera_model)):
                    self._if.maker_note['delete'] = False
                OK = self._handler_save(
                    self._if, file_times=file_times, write_iptc=write_iptc)
                if OK:
                    self._if.iptc_in_file = write_iptc
            if not OK:
                # can't write to image file so must create side car
                sc_mode = 'always'
            # create side car
            if not self._sc.path:
                if sc_mode == 'always':
                    self._sc.create_sidecar(self._if)
            # save or delete side car
            if self._sc.path:
                if sc_mode == 'delete':
                    self._sc.delete_sidecar()
                else:
                    OK = self._handler_save(self._sc, file_times=file_times)
        except Exception as ex:
            logger.exception(ex)
            return
        if OK:
            self.dirty = False
            self._changed = {}
            if self._notify:
                self._notify(self.dirty)

    def get_image_pixmap(self):
        with self._if.open() as handler:
            if handler:
                return handler.get_image_pixmap(self.orientation)
        return None

    def get_crop_factor(self):
        image_size = self.dimensions.sensor_dims()
        resolution = self.resolution
        if not (image_size and resolution):
            return None
        # get sensor diagonal in mm
        w = image_size['w']
        h = image_size['h']
        w /= resolution['x']
        h /= resolution['y']
        d = math.sqrt((h ** 2) + (w ** 2))
        if resolution['unit'] == 3:
            # unit is cm
            d *= 10.0
        elif resolution['unit'] == 4:
            # unit is mm
            pass
        elif resolution['unit'] == 5:
            # unit is µm
            d /= 1000.0
        elif resolution['unit'] in (1, 2):
            # unit is (assumed to be) inches
            d *= 25.4
        else:
            logger.error('Unknown resolution unit %d', resolution['unit'])
            return None
        # 35 mm film diagonal is 43.27 mm
        return 43.27 / d

    # allow attributes to be accessed in dict like fashion
    def __getitem__(self, name):
        if name in self._data_type:
            return getattr(self, name)
        raise KeyError(name)

    def __setitem__(self, name, value):
        if name in self._data_type:
            return setattr(self, name, value)
        raise KeyError(name)

    def __contains__(self, name):
        return name in self._data_type

    def __setattr__(self, name, value):
        if name not in self._data_type:
            return super(Metadata, self).__setattr__(name, value)
        if not isinstance(value, self._data_type[name]):
            value = self._data_type[name](value)
        if getattr(self, name) == value:
            return
        super(Metadata, self).__setattr__(name, value)
        self.set_changed(True)
        self._changed[name] = True

    def set_changed(self, changed):
        if changed != self.dirty:
            self.dirty = changed
            if self._notify:
                self._notify(self.dirty)

    def changed(self):
        return self.dirty
