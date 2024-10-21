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
        icon_dir = os.path.join(root, 'icons', 'hicolor')
        if not os.path.isdir(icon_dir):
            return
        for size in os.listdir(icon_dir):
            path = os.path.join(icon_dir, size, 'apps', 'photini.png')
            if os.path.exists(path):
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
    for size in os.listdir(icon_path):
        src = os.path.join(icon_path, size, 'photini.png')
        dst = os.path.join(root_dir, 'icons', 'hicolor', size, 'apps')
        os.makedirs(dst, exist_ok=True)
        dst = os.path.join(dst, 'photini.png')
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
