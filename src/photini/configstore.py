##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-25  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
from configparser import ConfigParser, RawConfigParser
from datetime import datetime, timedelta
import logging
import os
import pprint
import random
import re
import shutil
import stat

import platformdirs

logger = logging.getLogger(__name__)


def get_config_dir():
    config_dir = os.environ.get('PHOTINI_CONFIG')
    if config_dir:
        config_dir = os.path.expanduser(config_dir)
    else:
        config_dir = platformdirs.user_config_dir('photini')
    if not os.path.isdir(config_dir):
        os.makedirs(config_dir, mode=stat.S_IRWXU)
    return config_dir


class ConfigFileHandler(object):
    def __init__(self, name):
        self.root = get_config_dir()
        self.name = name
        self.path = os.path.join(self.root, self.name)

    def backups(self):
        result = []
        for name in os.listdir(self.root):
            if re.match(r'\d{4}-\d{2}-\d{2}$', name):
                result.append(name)
        result.sort(reverse=True)
        return result

    def restore(self):
        backups = []
        for backup in self.backups():
            path = os.path.join(self.root, backup, self.name)
            if os.path.isfile(path):
                backups.append(backup)
        if not backups:
            print('No backup of "{}" available.'.format(self.name))
            return
        choice = input('Restore "{}"? [y/n]: '.format(self.name))
        if choice not in ('y', 'Y'):
            return
        print('Available backups:')
        for idx, backup in enumerate(backups):
            print('{:3d}: {}'.format(idx + 1, backup))
        choice = input('Backup number [{}-{}]: '.format(1, len(backups)))
        try:
            choice = int(choice) - 1
        except ValueError:
            return
        if choice < 0 or choice >= len(backups):
            return
        backup = backups[choice]
        print('Using {}/{}'.format(backup, self.name))
        path = os.path.join(self.root, backup, self.name)
        shutil.copy(path, self.root)

    def read_path(self, path, callback, **kwds):
        if not os.path.exists(path):
            return False
        try:
            with open(path, 'r', **kwds) as fp:
                callback(fp)
            return True
        except Exception as ex:
            logger.error('File "%s": %s', path, str(ex))
        return False

    def read(self, callback, **kwds):
        if self.read_path(self.path, callback, **kwds):
            return
        # attempt to read a backup
        for backup in self.backups():
            if self.read_path(os.path.join(self.root, backup, self.name),
                              callback, **kwds):
                logger.error(
                    'File "%s": read from backup %s', self.name, backup)
                return

    def write(self, callback, **kwds):
        with open(self.path, 'w', **kwds) as fp:
            callback(fp)
        # make file private to user
        os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        # copy file to backup directory
        today = datetime.today()
        backup_dir = os.path.join(self.root, today.strftime('%Y-%m-%d'))
        if not os.path.isdir(backup_dir):
            os.makedirs(backup_dir, mode=stat.S_IRWXU)
        shutil.copy(self.path, backup_dir)
        # remove unneeded backups
        keep_list = []
        for i in range(7):
            keep_list.append((today - timedelta(days=i)).strftime('%Y-%m-%d'))
        today = today.replace(day=15)
        for i in range(6):
            keep_list.append((today - timedelta(days=i*30)).strftime('%Y-%m'))
        today = today.replace(month=6)
        for i in range(5):
            keep_list.append((today - timedelta(days=i*365)).strftime('%Y'))
        keep_list = list(reversed(keep_list))
        for backup in reversed(self.backups()):
            for keep in keep_list:
                if backup.startswith(keep):
                    keep_list.remove(keep)
                    break
            else:
                shutil.rmtree(os.path.join(self.root, backup))


class BaseConfigStore(object):
    # the actual config store functionality
    def __init__(self, name, *arg, **kw):
        super(BaseConfigStore, self).__init__(*arg, **kw)
        self.dirty = False
        self.config = RawConfigParser()
        self.file_handler = ConfigFileHandler(name + '.ini')
        self.file_handler.read(self.config.read_file, encoding='utf-8')
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
        if not self.config.has_option(section, option):
            return
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
        self.file_handler.write(self.config.write, encoding='utf-8')
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
