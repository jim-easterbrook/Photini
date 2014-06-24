##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-14  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from ConfigParser import RawConfigParser
import os
import sys

import appdirs
from PyQt4 import QtCore

class ConfigStore(object):
    def __init__(self, name):
        self.config = RawConfigParser()
        self.file_opts = {}
        if sys.version_info[0] >= 3:
            self.file_opts['encoding'] = 'utf-8'
        if hasattr(appdirs, 'user_config_dir'):
            data_dir = appdirs.user_config_dir('photini')
        else:
            data_dir = appdirs.user_data_dir('photini')
        if not os.path.isdir(data_dir):
            os.makedirs(data_dir, mode=0700)
        self.file_name = os.path.join(data_dir, '%s.ini' % name)
        if name == 'editor':
            for old_file_name in (os.path.expanduser('~/photini.ini'),
                                  os.path.join(data_dir, 'photini.ini')):
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
            if sys.version_info[0] < 3:
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
        if sys.version_info[0] < 3:
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

    def save(self):
        self.config.write(open(self.file_name, 'w', **self.file_opts))
        os.chmod(self.file_name, 0600)
