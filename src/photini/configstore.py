# -*- coding: utf-8 -*-
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

import codecs
from configparser import RawConfigParser
import os
import stat
import sys

import appdirs
import pkg_resources

class BaseConfigStore(object):
    # the actual config store functionality
    def __init__(self, name, *arg, **kw):
        super(BaseConfigStore, self).__init__(*arg, **kw)
        self.dirty = False
        self.config = RawConfigParser()
        config_dir = os.environ.get('PHOTINI_CONFIG')
        if config_dir:
            config_dir = os.path.expanduser(config_dir)
        elif hasattr(appdirs, 'user_config_dir'):
            config_dir = appdirs.user_config_dir('photini')
        else:
            config_dir = appdirs.user_data_dir('photini')
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir, mode=stat.S_IRWXU)
        self.file_name = os.path.join(config_dir, name + '.ini')
        if os.path.isfile(self.file_name):
            kwds = {'encoding': 'utf-8'}
            with open(self.file_name, 'r', **kwds) as fp:
                self.config.read_file(fp)
        self.has_section = self.config.has_section

    def get(self, section, option, default=None):
        if self.config.has_option(section, option):
            return self.config.get(section, option)
        if default is not None:
            self.set(section, option, default)
        return default

    def set(self, section, option, value):
        if not self.config.has_section(section):
            self.config.add_section(section)
        elif (self.config.has_option(section, option) and
              self.config.get(section, option) == value):
            return
        self.config.set(section, option, value)
        self.dirty = True

    def delete(self, section, option):
        if not self.config.has_section(section):
            return
        if self.config.has_option(section, option):
            self.config.remove_option(section, option)
        if not self.config.options(section):
            self.config.remove_section(section)
        self.dirty = True

    def remove_section(self, section):
        if not self.config.has_section(section):
            return
        for option in self.config.options(section):
            self.config.remove_option(section, option)
        self.config.remove_section(section)
        self.dirty = True

    def save(self):
        if not self.dirty:
            return
        kwds = {'encoding': 'utf-8'}
        with open(self.file_name, 'w', **kwds) as fp:
            self.config.write(fp)
        os.chmod(self.file_name, stat.S_IRUSR | stat.S_IWUSR)
        self.dirty = False


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
        value = value.encode('ascii')
        value = codecs.decode(value, 'base64_codec')
        return value.decode('ascii')


# create single object for entire application
key_store = KeyStore()
