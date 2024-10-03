##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import ast
import codecs
from configparser import ConfigParser, RawConfigParser
import os
import pprint
import random
import stat

import platformdirs


def get_config_dir():
    config_dir = os.environ.get('PHOTINI_CONFIG')
    if config_dir:
        config_dir = os.path.expanduser(config_dir)
    else:
        config_dir = platformdirs.user_config_dir('photini')
    if not os.path.isdir(config_dir):
        os.makedirs(config_dir, mode=stat.S_IRWXU)
    return config_dir


class BaseConfigStore(object):
    # the actual config store functionality
    def __init__(self, name, *arg, **kw):
        super(BaseConfigStore, self).__init__(*arg, **kw)
        self.dirty = False
        self.config = RawConfigParser()
        self.file_name = os.path.join(get_config_dir(), name + '.ini')
        if os.path.isfile(self.file_name):
            kwds = {'encoding': 'utf-8'}
            with open(self.file_name, 'r', **kwds) as fp:
                self.config.read_file(fp)
        self.has_section = self.config.has_section

    def get(self, section, option, default=None):
        if self.config.has_option(section, option):
            value = self.config.get(section, option)
            if not value:
                return None
            try:
                value = ast.literal_eval(value)
            except Exception:
                pass
            return value
        if default is not None:
            self.set(section, option, default)
        return default

    def set(self, section, option, value):
        value = pprint.pformat(value)
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
    """Store API keys and other 'secret' data.

    No data is really secret in an application running on a user's
    computer. Photini stores the data in a randomly shuffled data block
    so they won't be recognised by bots scraping GitHub.

    The utils/store_keys.py script generates the shuffled data file that
    this class reads and unshuffles.

    """
    def __init__(self):
        cfg = ConfigParser(interpolation=None)
        cfg.read(os.path.join(os.path.dirname(__file__), 'data', 'keys.txt'))
        data = cfg['data']['data']
        length = len(data)
        random.seed(cfg['data']['date'], version=2)
        mapping = random.sample(range(length), k=length)
        data = ''.join([data[x] for x in mapping])
        self.config = ConfigParser(interpolation=None)
        for section in cfg:
            if section in ('DEFAULT', 'data'):
                continue
            self.config[section] = {}
            for key in cfg[section]:
                offset, length = eval(cfg[section][key])
                self.config[section][key] = data[offset:offset+length]

    def get(self, section, option):
        return self.config[section][option]


# create single object for entire application
key_store = KeyStore()
