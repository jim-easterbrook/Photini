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

from fractions import Fraction
import imghdr
import logging
import math
import mimetypes
import os
import re

from photini import __version__
from photini.ffmpeg import FFmpeg
from photini.filemetadata import (
    exiv2_version_info, ImageMetadata, SidecarMetadata)
from photini.types import *

logger = logging.getLogger(__name__)


class FFMPEGMetadata(object):
    _tag_list = {
        'altitude':       ('com.apple.quicktime.location.ISO6709',
                           'location'),
        'camera_model':   ('model',
                           'Model',
                           'com.apple.quicktime.model'),
        'copyright':      ('com.apple.quicktime.copyright',
                           'copyright',
                           'Copyright'),
        'creator':        ('com.apple.quicktime.author',
                           'artist'),
        'date_digitised': ('DateTimeDigitized',),
        'date_modified':  ('DateTime',),
        'date_taken':     ('com.apple.quicktime.creationdate',
                           'date',
                           'creation_time',
                           'DateTimeOriginal'),
        'description':    ('comment',),
        'latlong':        ('com.apple.quicktime.location.ISO6709',
                           'location'),
        'orientation':    ('rotate',),
        'rating':         ('com.apple.quicktime.rating.user',),
        'title':          ('title',),
        }

    def __init__(self, path):
        self._path = path
        self.md = {}
        raw = FFmpeg.ffprobe(path)
        if 'format' in raw and 'tags' in raw['format']:
            self.md.update(self.read_tags('format', raw['format']['tags']))
        if 'streams' in raw:
            for stream in raw['streams']:
                if 'tags' in stream:
                    self.md.update(self.read_tags(
                        'stream[{}]'.format(stream['index']), stream['tags']))

    def read_tags(self, label, tags):
        result = {}
        for key, value in tags.items():
            result['ffmpeg/{}/{}'.format(label, key)] = value
        return result

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
        for part_tag in self._tag_list[name]:
            for tag in self.md:
                if tag.split('/')[2] != part_tag:
                    continue
                try:
                    value = type_.from_ffmpeg(self.md[tag], tag)
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


class Metadata(object):
    # type of each Photini data field's data
    _data_type = {
        'altitude'       : MD_Altitude,
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
        'focal_length'   : MD_Rational,
        'focal_length_35': MD_Int,
        'headline'       : MD_String,
        'instructions'   : MD_String,
        'keywords'       : MD_MultiString,
        'latlong'        : MD_LatLon,
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

    def __init__(self, path, notify=None, utf_safe=False):
        super(Metadata, self).__init__()
        # create metadata handlers for image file, video file, and sidecar
        self._path = path
        self._notify = notify
        self._utf_safe = utf_safe
        video_md = None
        self._sc = SidecarMetadata.open_old(self.find_sidecar())
        self._if = ImageMetadata.open_old(path, utf_safe=utf_safe)
        self.mime_type = self.get_mime_type()
        if self.mime_type.split('/')[0] == 'video':
            video_md = FFMPEGMetadata.open_old(path)
        self.dirty = False
        self.iptc_in_file = self._if and self._if.has_iptc()
        # get maker note info
        if self._if:
            self._maker_note = {
                'make': (self._if.has_tag('Exif.Photo.MakerNote') and
                         self._if.get_value('Exif.Image.Make')),
                'delete': False,
                }
        # read Photini metadata items
        for name in self._data_type:
            # read data values from first file that has any
            values = []
            for handler in self._sc, video_md, self._if:
                if not handler:
                    continue
                values = handler.read(name, self._data_type[name])
                if values:
                    break
            # choose result and merge in non-matching data so user can review it
            value = None
            if values:
                info = '{}({})'.format(os.path.basename(self._path), name)
                tag, value = values[0]
                logger.debug('%s: set from %s', info, tag)
            for tag2, value2 in values[1:]:
                value = value.merge(info, tag2, value2)
            super(Metadata, self).__setattr__(name, value)
        # merge in camera timezone if needed
        if not self.timezone:
            return
        for name in ('date_digitised', 'date_modified', 'date_taken'):
            value = getattr(self, name)
            if value['tz_offset'] is None:
                value = dict(value)
                value['tz_offset'] = self.timezone
                info = '{}({})'.format(os.path.basename(self._path), name)
                logger.info('%s: merged camera timezone offset', info)
                super(Metadata, self).__setattr__(
                    name, self._data_type[name](value))

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
        if not self._maker_note['make']:
            return True
        if not camera_model:
            return False
        return self._maker_note['make'] == camera_model['make']

    def set_delete_makernote(self):
        self._maker_note['delete'] = True

    @classmethod
    def clone(cls, path, other):
        if other._if:
            # use exiv2 to clone image file metadata
            other._if.save_file(path)
        self = cls(path)
        if other._sc and self._if:
            # merge in sidecar data
            self._if.merge_sc(other._sc)
        # copy Photini metadata items
        for name in cls._data_type:
            value = getattr(other, name)
            setattr(self, name, value)
        return self

    def _handler_save(self, handler, *arg, **kw):
        # store Photini metadata items
        for name in self._data_type:
            value = getattr(self, name)
            handler.write(name, value)
        # save file
        return handler.save(*arg, **kw)

    def save(self, if_mode=True, sc_mode='auto',
             force_iptc=False, file_times=None):
        if not self.dirty:
            return
        self.software = 'Photini editor v' + __version__
        OK = False
        force_iptc = force_iptc or self.iptc_in_file
        try:
            # save to image file
            if if_mode and self._if:
                if self._maker_note['delete']:
                    if not self.camera_change_ok(self.camera_model):
                        self._if.clear_maker_note()
                    self._maker_note['delete'] = False
                OK = self._handler_save(
                    self._if, file_times=file_times, force_iptc=force_iptc)
                if OK:
                    self.iptc_in_file = force_iptc
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

    def get_crop_factor(self):
        md = self._if or self._sc
        if not md:
            return None
        # get relevant metadata
        resolution = {}
        sensor_size = {}
        resolution_source = None, None
        for key in md.get_all_tags():
            family, group, tag = key.split('.', 2)
            if tag in ('FocalPlaneXResolution', 'FocalPlaneYResolution',
                       'FocalPlaneResolutionUnit'):
                resolution[key] = md.get_value(key)
                resolution_source = family, group
            if tag in ('PixelXDimension', 'PixelYDimension',
                       'ImageWidth', 'ImageLength'):
                sensor_size[key] = md.get_value(key)
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
        sensor_size['x'], sensor_size['y'] = md.get_preview_imagedims()
        for x_key in sensor_size:
            if 'PixelXDimension' in x_key:
                y_key = x_key.replace('PixelXDimension', 'PixelYDimension')
            elif 'ImageWidth' in x_key:
                y_key = x_key.replace('ImageWidth', 'ImageLength')
            else:
                continue
            if y_key not in sensor_size:
                continue
            sensor_size['x'] = max(sensor_size['x'], int(sensor_size[x_key]))
            sensor_size['y'] = max(sensor_size['y'], int(sensor_size[y_key]))
        if not sensor_size['x'] or not sensor_size['y']:
            return None
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
            result = mimetypes.guess_type(self._path)[0]
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
        if not self.dirty:
            self.dirty = True
            if self._notify:
                self._notify(self.dirty)

    def changed(self):
        return self.dirty
