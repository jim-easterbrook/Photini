#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2020-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This program is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see
#  <http://www.gnu.org/licenses/>.

import os
import sys

from PIL import Image
from sphinx.application import Sphinx


def prepare_images(root):
    src_dir = os.path.join(root, '..', 'screenshots')
    dst_dir = os.path.join(root, 'src', 'doc', 'images')
    if not os.path.isdir(src_dir):
        return
    for name in os.listdir(src_dir):
        if not name.endswith('.png'):
            continue
        src_path = os.path.join(src_dir, name)
        dst_path = os.path.join(dst_dir, name)
        if (os.path.exists(dst_path) and
                os.path.getmtime(dst_path) > os.path.getmtime(src_path)):
            continue
        print('resizing', name)
        im = Image.open(src_path)
        w, h = im.size
        im = im.resize((w * 2 // 3, h * 2 // 3), Image.Resampling.LANCZOS)
        # crop image where alpha channel is very low
        alpha = im.getchannel('A')
        alpha = Image.eval(alpha, lambda x: x - 4)
        im = im.crop(alpha.getbbox())
        im.save(dst_path)


def main(argv=None):
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    prepare_images(root)
    src_dir = os.path.join(root, 'src', 'doc')
    dst_dir = os.path.join(root, 'doc', 'html')
    doctree_dir = os.path.join(root, 'doctrees', 'html')
    app = Sphinx(src_dir, src_dir, dst_dir, doctree_dir, 'html')
    app.build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
