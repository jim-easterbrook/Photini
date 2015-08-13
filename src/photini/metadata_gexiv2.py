# -*- coding: utf-8 -*-
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

import logging
import sys

try:
    import pgi
    pgi.install_as_gi()
except ImportError:
    pass
from gi.repository import GObject, GExiv2
import six

# pydoc gi.repository.GExiv2.Metadata is useful to see methods available

class MetadataHandler(object):
    def __init__(self, path):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.path = path
        self._md = GExiv2.Metadata()
        self._md.open_path(self.path)
        # adopt some GExiv2.Metadata methods
        self.get_exif_tags    = self._md.get_exif_tags
        self.get_iptc_tags    = self._md.get_iptc_tags
        self.get_xmp_tags     = self._md.get_xmp_tags
        if six.PY3:
            self.get_tag_string   = self._get_tag_string
            self.get_tag_multiple = self._get_tag_multiple
        else:
            self.get_tag_string   = self._md.get_tag_string
            self.get_tag_multiple = self._md.get_tag_multiple
        self.set_tag_string   = self._md.set_tag_string
        self.set_tag_multiple = self._md.set_tag_multiple
        self.clear_tag        = self._md.clear_tag

    def _get_tag_string(self, tag):
        try:
            result = self._md.get_tag_string(tag)
        except UnicodeDecodeError:
            return ''
        return result

    def _get_tag_multiple(self, tag):
        try:
            result = self._md.get_tag_multiple(tag)
        except UnicodeDecodeError:
            return []
        return result

    def save(self):
        try:
            self._md.save_file(self.path)
        except GObject.GError as ex:
            self.logger.exception(ex)
            return False
        return True

    def copy(self, other, exif=True, iptc=True, xmp=True, comment=True):
        # copy from other to self
        if exif:
            for tag in other._md.get_exif_tags():
                self._md.set_tag_string(
                    tag, other._md.get_tag_string(tag))
        if iptc:
            for tag in other._md.get_iptc_tags():
                self._md.set_tag_multiple(
                    tag, other._md.get_tag_multiple(tag))
        if xmp:
            for tag in other._md.get_xmp_tags():
                self._md.set_tag_multiple(
                    tag, other._md.get_tag_multiple(tag))
        if comment:
            value = other._md.get_comment()
            if value:
                self._md.set_comment(value)

    def get_tags(self):
        return self.get_exif_tags() + self.get_iptc_tags() + self.get_xmp_tags()
