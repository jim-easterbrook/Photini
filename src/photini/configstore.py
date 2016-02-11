# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-16  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import six
from six.moves.configparser import RawConfigParser
import os
import stat
import sys

import appdirs
import pkg_resources

from .pyqt import QtCore

class ConfigStore(object):
    def __init__(self, name):
        self.config = RawConfigParser()
        self.file_opts = {}
        if not six.PY2:
            self.file_opts['encoding'] = 'utf-8'
        if hasattr(appdirs, 'user_config_dir'):
            config_dir = appdirs.user_config_dir('photini')
        else:
            config_dir = appdirs.user_data_dir('photini')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir, mode=stat.S_IRWXU)
        self.file_name = os.path.join(config_dir, name + '.ini')
        if name == 'editor':
            for old_file_name in (os.path.expanduser('~/photini.ini'),
                                  os.path.join(config_dir, 'photini.ini')):
                if os.path.exists(old_file_name):
                    self.config.read(old_file_name, **self.file_opts)
                    self.save()
                    os.unlink(old_file_name)
        self.config.read(self.file_name, **self.file_opts)
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(3000)
        self.timer.timeout.connect(self.save)
        self.has_section = self.config.has_section

    def get(self, section, option, default=None):
        if self.config.has_option(section, option):
            result = self.config.get(section, option)
            if six.PY2:
                return result.decode('utf-8')
            return result
        if default is not None:
            self.set(section, option, default)
        return default

    def set(self, section, option, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        if (self.config.has_option(section, option) and
                self.config.get(section, option) == value):
            return
        if six.PY2:
            value = value.encode('utf-8')
        self.config.set(section, option, value)
        self.timer.start()

    def remove_section(self, section):
        if not self.config.has_section(section):
            return
        for option in self.config.options(section):
            self.config.remove_option(section, option)
        self.config.remove_section(section)
        self.timer.start()

    def shutdown(self):
        if self.timer.isActive():
            self.timer.stop()
            self.save()

    def save(self):
        self.config.write(open(self.file_name, 'w', **self.file_opts))
        os.chmod(self.file_name, stat.S_IRUSR | stat.S_IWUSR)


class KeyStore(object):
    """Store OAuth2 client ids and client 'secrets'.

    Google recognise that client secrets can't be kept secret in an
    application that runs on a user's computer. See
    https://developers.google.com/identity/protocols/OAuth2InstalledApp
    for more background. However, they also say the secret "may not be
    embedded in open source projects" (see section 4.b.1 of
    https://developers.google.com/terms/).

    Photini stores the client credentials in a separate file, using mild
    obfuscation to hide the actual values. If this is insufficient to
    satisfy Google then the keys file will have to be removed from open
    source and distributed by other means. Or users will need to create
    their own by registering as a developer at Google.

    The position with Flickr keys is less clear, but there's no harm in
    obfuscating them as well.

    """
    def __init__(self):
        self.config = RawConfigParser()
        if sys.version_info >= (3, 2):
            data = pkg_resources.resource_string('photini', 'data/keys.txt')
            data = data.decode('utf-8')
            self.config.read_string(data)
        else:
            data = pkg_resources.resource_stream('photini', 'data/keys.txt')
            self.config.readfp(data)

    def get(self, section, option):
        value = self.config.get(section, option)
        if not six.PY2:
            value = value.encode('ASCII')
        value = codecs.decode(value, 'base64_codec')
        if not six.PY2:
            return value.decode('ASCII')
        return value


# create single objects for entire application
config_store = ConfigStore('editor')
key_store = KeyStore()
