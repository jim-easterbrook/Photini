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
import shutil
import subprocess
import tempfile


def post_install(exec_path, icon_path, remove, generic_name, comment):
    icon_name = 'photini.png'
    desktop_name = 'photini.desktop'

    def remove_icons(root):
        path = os.path.join(root, 'icons')
        for root, dirs, files in os.walk(path, topdown=False):
            if icon_name in files:
                path = os.path.join(root, icon_name)
                print('Deleting', path)
                os.unlink(path)

    def remove_desktop(root):
        path = os.path.join(root, 'applications', desktop_name)
        if os.path.exists(path):
            print('Deleting', path)
            os.unlink(path)
            return True
        return False

    if os.geteuid() == 0:
        # running as root
        root_dir = '/usr/local/share'
        # clean up anything in '/usr/share'
        remove_icons('/usr/share')
        remove_desktop('/usr/share')
    else:
        root_dir = os.path.expanduser('~/.local/share')
    if remove:
        remove_icons(root_dir)
        if remove_desktop(root_dir):
            return 0
        print('No "desktop" file found.')
        return 1
    # copy icons
    icon_theme = os.path.basename(icon_path)
    dest_root = os.path.join(root_dir, 'icons', icon_theme)
    for root, dirs, files in os.walk(icon_path):
        for name in files:
            src = os.path.join(root, name)
            dst = root.replace(icon_path, dest_root)
            os.makedirs(dst, exist_ok=True)
            dst = os.path.join(dst, name)
            print('Writing', dst)
            shutil.copy(src, dst)
    # create desktop file
    with tempfile.TemporaryDirectory() as temp_dir:
        path = os.path.join(temp_dir, 'photini.desktop')
        print('Creating', path)
        with open(path, 'w') as file:
            file.write('''[Desktop Entry]
Type=Application
Name=Photini
Terminal=false
Categories=Graphics;Photography;
MimeType=image/jpeg;image/jpeg2000;image/tiff;image/png;image/gif;image/x-dcraw;application/rdf+xml;
''')
            file.write('Exec={} %F\n'.format(exec_path))
            file.write('Icon={}\n'.format(os.path.splitext(icon_name)[0]))
            file.write('GenericName={}\n'.format(generic_name))
            file.write('Comment={}\n'.format(comment))
        app_dir = os.path.join(root_dir, 'applications')
        print('Installing', path, 'to', app_dir)
        cmd = ['desktop-file-install', '--rebuild-mime-info-cache',
               '--dir={}'.format(app_dir), path]
        return subprocess.call(cmd)
    return 0
