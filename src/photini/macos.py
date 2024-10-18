#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2024  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This file is part of Photini.
#
#  Photini is free software: you can redistribute it and/or modify it
#  under the terms of the GNU General Public License as published by the
#  Free Software Foundation, either version 3 of the License, or (at
#  your option) any later version.
#
#  Photini is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Photini.  If not, see <http://www.gnu.org/licenses/>.

import os
import plistlib
import shutil

from photini import __version__, __version_tuple__


def post_install(exec_path, icon_path, remove, generic_name, comment):
    if os.geteuid() == 0:
        # running as root
        app_dir = '/Applications/Photini.app'
    else:
        app_dir = os.path.expanduser('~/Applications/Photini.app')
    if remove:
        if os.path.exists(app_dir):
            print('Deleting', app_dir)
            shutil.rmtree(app_dir)
            return 0
        print('No Photini app found.')
        return 1
    # create application file
    path = os.path.join(app_dir, 'Contents', 'MacOS')
    os.makedirs(path, exist_ok=True)
    print('Copying', exec_path, 'to', path)
    shutil.copy(exec_path, path)
    # copy icon file
    path = os.path.join(app_dir, 'Contents', 'Resources')
    os.makedirs(path, exist_ok=True)
    print('Copying', icon_path, 'to', path)
    shutil.copy(icon_path, path)
    # create property list
    info = {
        'CFBundleDevelopmentRegion': 'en-GB',
        'CFBundleDisplayName': generic_name,
        'CFBundleDocumentTypes': [{
            'LSHandlerRank': 'Alternate',
            'LSItemContentTypes': ['public.image'],
            'NSExportableTypes': ['public.image'],
            }],
        'CFBundleExecutable': os.path.basename(exec_path),
        'CFBundleIconFile': os.path.basename(icon_path),
        'CFBundleIdentifier': 'uk.me.jim-easterbrook.Photini',
        'CFBundleInfoDictionaryVersion': '6.0',
        'CFBundleName': 'Photini',
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': '{}.{}.{}'.format(*__version_tuple__[:3]),
        'CFBundleTypeRole': 'Editor',
        'CFBundleVersion': __version__.replace('.post', 'd'),
        'NSHumanReadableCopyright': 'Copyright (C) 2024  Jim Easterbrook',
        }
    path = os.path.join(app_dir, 'Contents', 'Info.plist')
    print('Creating', path)
    with open(path, 'wb') as fp:
        plistlib.dump(info, fp)
    return 0
