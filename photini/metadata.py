##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-13  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import datetime
import fractions
import os
import sys

from PyQt4 import QtCore

try:
    from .metadata_gexiv2 import MetadataHandler
except ImportError as e:
    try:
        from .metadata_pyexiv2 import MetadataHandler
    except ImportError:
        # raise exception on the one we really wanted
        raise e
from .version import version

class GPSvalue(object):
    def __init__(self, degrees=0.0, latitude=True):
        self.degrees = degrees
        self.latitude = latitude

    def from_xmp_string(self, value):
        degrees, residue = value.split(',')
        minutes = residue[:-1]
        direction = residue[-1]
        self.degrees = float(degrees) + (float(minutes) / 60.0)
        if direction in ('S', 'W'):
            self.degrees = -self.degrees
        self.latitude = direction in ('S', 'N')
        return self

    def to_xmp_string(self):
        if self.degrees >= 0.0:
            ref = ('E', 'N')[self.latitude]
            value = self.degrees
        else:
            ref = ('W', 'S')[self.latitude]
            value = -self.degrees
        degrees = int(value)
        minutes = (value - degrees) * 60.0
        return '%d,%.13f%s' % (degrees, minutes, ref)

    def from_exif_string(self, value, direction):
        parts = map(fractions.Fraction, value.split())
        self.degrees = float(parts[0])
        if len(parts) > 1:
            self.degrees += float(parts[1]) / 60.0
        if len(parts) > 2:
            self.degrees += float(parts[2]) / 3600.0
        if direction in ('S', 'W'):
            self.degrees = -self.degrees
        self.latitude = direction in ('S', 'N')
        return self

    def to_exif_string(self):
        if self.degrees >= 0.0:
            ref = ('E', 'N')[self.latitude]
            value = self.degrees
        else:
            ref = ('W', 'S')[self.latitude]
            value = -self.degrees
        degrees = int(value)
        value = (value - degrees) * 60.0
        minutes = int(value)
        seconds = (value - minutes) * 60.0
        degrees = fractions.Fraction(degrees).limit_denominator(1000000)
        minutes = fractions.Fraction(minutes).limit_denominator(1000000)
        seconds = fractions.Fraction(seconds).limit_denominator(1000000)
        return '%d/%d %d/%d %d/%d' % (
            degrees.numerator, degrees.denominator,
            minutes.numerator, minutes.denominator,
            seconds.numerator, seconds.denominator), ref

class Metadata(QtCore.QObject):
    _keys = {
        'date_digitised' : (('Exif.Photo.DateTimeDigitized',     True),),
        'date_modified'  : (('Exif.Image.DateTime',              True),),
        'date_taken'     : (('Exif.Photo.DateTimeOriginal',      True),
                            ('Exif.Image.DateTimeOriginal',      True),),
        'title'          : (('Xmp.dc.title',                     True),
                            ('Iptc.Application2.ObjectName',     True),
                            ('Exif.Image.ImageDescription',      True),),
        'creator'        : (('Xmp.dc.creator',                   True),
                            ('Xmp.tiff.Artist',                  False),
                            ('Iptc.Application2.Byline',         True),
                            ('Exif.Image.Artist',                True),),
        'description'    : (('Xmp.dc.description',               True),
                            ('Iptc.Application2.Caption',        True),),
        'keywords'       : (('Xmp.dc.subject',                   True),
                            ('Iptc.Application2.Keywords',       True),),
        'copyright'      : (('Xmp.dc.rights',                    True),
                            ('Xmp.tiff.Copyright',               False),
                            ('Iptc.Application2.Copyright',      True),
                            ('Exif.Image.Copyright',             True),),
        'latitude'       : (('Exif.GPSInfo.GPSLatitude',         True),
                            ('Xmp.exif.GPSLatitude',             True),),
        'longitude'      : (('Exif.GPSInfo.GPSLongitude',        True),
                            ('Xmp.exif.GPSLongitude',            True),),
        'orientation'    : (('Exif.Image.Orientation',           True),),
        'soft_full'      : (('Exif.Image.ProcessingSoftware',    True),),
        'soft_name'      : (('Iptc.Application2.Program',        True),),
        'soft_vsn'       : (('Iptc.Application2.ProgramVersion', True),),
        }
    _list_items = ('keywords',)
    def __init__(self, path, parent=None):
        QtCore.QObject.__init__(self, parent)
        # create metadata handlers for image file and sidecar (if present)
        self._path = path
        self._if = MetadataHandler(path)
        self._sc = None
        for base in (os.path.splitext(path)[0], path):
            for ext in ('.xmp', '.XMP'):
                if not self._sc:
                    self.sc_path = base + ext
                    if os.path.exists(self.sc_path):
                        self._sc = MetadataHandler(self.sc_path)
        self._unsaved = False

    def create_side_car(self):
        self.sc_path = self._path + '.xmp'
        with open(self.sc_path, 'w') as of:
            of.write('<x:xmpmeta x:xmptk="XMP Core 4.4.0-Exiv2" ')
            of.write('xmlns:x="adobe:ns:meta/">\n')
            of.write('</x:xmpmeta>')
        self._sc = MetadataHandler(self.sc_path)
        self._sc.copy(self._if, comment=False)

    def save(self, if_mode, sc_mode):
        if not self._unsaved:
            return
        self.set_item('soft_full', 'Photini editor v%s' % (version))
        self.set_item('soft_name', 'Photini editor')
        self.set_item('soft_vsn', '%s' % (version))
        if sc_mode == 'delete' and self._sc:
            self._if.copy(self._sc, comment=False)
        OK = False
        if if_mode:
            OK = self._if.save()
        if sc_mode == 'delete' and self._sc and OK:
            os.unlink(self.sc_path)
            self._sc = None
        if sc_mode == 'auto' and not self._sc and not OK:
            self.create_side_car()
        if sc_mode == 'always' and not self._sc:
            self.create_side_car()
        if self._sc:
            OK = self._sc.save()
        self._set_unsaved(not OK)

    # tag lists: merge tags from sidecar and image file
    def get_exif_tags(self):
        result = self._if.get_exif_tags()
        if self._sc:
            for tag in self._sc.get_exif_tags():
                if tag not in result:
                    result.append(tag)
        return result

    def get_iptc_tags(self):
        result = self._if.get_iptc_tags()
        if self._sc:
            for tag in self._sc.get_iptc_tags():
                if tag not in result:
                    result.append(tag)
        return result

    def get_xmp_tags(self):
        result = self._if.get_xmp_tags()
        if self._sc:
            for tag in self._sc.get_xmp_tags():
                if tag not in result:
                    result.append(tag)
        return result

    # getters: use sidecar if tag is present, otherwise use image file
    def get_exif_tag_string(self, tag):
        if self._sc and tag in self._sc.get_exif_tags():
            return self._sc.get_exif_tag_string(tag)
        return self._if.get_exif_tag_string(tag)

    def get_iptc_tag_multiple(self, tag):
        if self._sc and tag in self._sc.get_iptc_tags():
            return self._sc.get_iptc_tag_multiple(tag)
        return self._if.get_iptc_tag_multiple(tag)

    def get_xmp_tag_string(self, tag):
        if self._sc and tag in self._sc.get_xmp_tags():
            return self._sc.get_xmp_tag_string(tag)
        return self._if.get_xmp_tag_string(tag)

    def get_xmp_tag_multiple(self, tag):
        if self._sc and tag in self._sc.get_xmp_tags():
            return self._sc.get_xmp_tag_multiple(tag)
        return self._if.get_xmp_tag_multiple(tag)

    # setters: set in both sidecar and image file
    def set_exif_tag_string(self, tag, value):
        if self._sc:
            self._sc.set_exif_tag_string(tag, value)
        self._if.set_exif_tag_string(tag, value)

    def set_exif_tag_long(self, tag, value):
        if self._sc:
            self._sc.set_exif_tag_long(tag, value)
        self._if.set_exif_tag_long(tag, value)

    def set_iptc_tag_multiple(self, tag, value):
        if self._sc:
            self._sc.set_iptc_tag_multiple(tag, value)
        self._if.set_iptc_tag_multiple(tag, value)

    def set_xmp_tag_string(self, tag, value):
        if self._sc:
            self._sc.set_xmp_tag_string(tag, value)
        self._if.set_xmp_tag_string(tag, value)

    def set_xmp_tag_multiple(self, tag, value):
        if self._sc:
            self._sc.set_xmp_tag_multiple(tag, value)
        self._if.set_xmp_tag_multiple(tag, value)

    def clear_tag(self, tag):
        if self._sc:
            self._sc.clear_tag(tag)
        self._if.clear_tag(tag)

    def get_tags(self):
        return self.get_exif_tags() + self.get_iptc_tags() + self.get_xmp_tags()

    def has_GPS(self):
        return (('Xmp.exif.GPSLatitude' in self.get_xmp_tags()) or
                ('Exif.GPSInfo.GPSLatitude' in self.get_exif_tags()))

    def get_item(self, name):
        for key, required in self._keys[name]:
            family, group, tag = key.split('.')
            if key in self.get_xmp_tags():
                if tag.startswith('GPS'):
                    return GPSvalue().from_xmp_string(
                        self.get_xmp_tag_string(key))
                return u'; '.join(self.get_xmp_tag_multiple(key))
            if key in self.get_iptc_tags():
                return u'; '.join(self.get_iptc_tag_multiple(key))
            if key in self.get_exif_tags():
                if tag.startswith('DateTime'):
                    return datetime.datetime.strptime(
                        self.get_exif_tag_string(key), '%Y:%m:%d %H:%M:%S')
                if tag == 'Orientation':
                    return int(self.get_exif_tag_string(key))
                if group == 'GPSInfo':
                    return GPSvalue().from_exif_string(
                        self.get_exif_tag_string(key),
                        self.get_exif_tag_string('%sRef' % key))
                t = self.get_exif_tag_string(key)
                if sys.version_info[0] >= 3:
                    return self.get_exif_tag_string(
                        key).encode('iso8859_1').decode('utf8')
                return unicode(self.get_exif_tag_string(key), 'iso8859_1')
        return None

    def set_item(self, name, value):
        if value == self.get_item(name):
            return
        if name in self._list_items:
            value = map(lambda x: x.strip(), value.split(';'))
            for i in reversed(range(len(value))):
                if not value[i]:
                    del value[i]
        elif isinstance(value, (str, unicode)):
            value = [value.strip()]
        if not value:
            self.del_item(name)
            return
        for key, required in self._keys[name]:
            if required or key in self.get_tags():
                family, group, tag = key.split('.')
                if family == 'Xmp':
                    if isinstance(value, GPSvalue):
                        self.set_xmp_tag_string(key, value.to_xmp_string())
                    else:
                        self.set_xmp_tag_multiple(key, value)
                elif family == 'Iptc':
                    self.set_iptc_tag_multiple(key, value)
                elif family == 'Exif':
                    if isinstance(value, GPSvalue):
                        string, ref = value.to_exif_string()
                        self.set_exif_tag_string(key, string)
                        self.set_exif_tag_string('%sRef' % key, ref)
                    elif isinstance(value, datetime.datetime):
                        self.set_exif_tag_string(
                            key, value.strftime('%Y:%m:%d %H:%M:%S'))
                    elif isinstance(value, int):
                        self.set_exif_tag_long(key, value)
                    else:
                        self.set_exif_tag_string(key, value[0])
        self._set_unsaved(True)

    def del_item(self, name):
        changed = False
        for key, required in self._keys[name]:
            if key in self.get_tags():
                self.clear_tag(key)
                changed = True
        if changed:
            self._set_unsaved(True)

    new_status = QtCore.pyqtSignal(bool)
    def _set_unsaved(self, status):
        self._unsaved = status
        self.new_status.emit(self._unsaved)

    def changed(self):
        return self._unsaved
