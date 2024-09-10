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
import sys

import PIL.Image, PIL.ImageChops


def main(argv=None):
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    src_dir = os.path.join(root, 'utils', 'make_icons')
    dst_dir = os.path.join(root, 'src', 'photini', 'data', 'map')
    # amount to pad images by to make them symmetric
    PAD = 40
    # open source file and pad it
    red_src = PIL.Image.open(os.path.join(src_dir, 'map_pin_red.png'))
    pad = PIL.Image.new('RGBA', (red_src.size[0] + PAD, red_src.size[1]))
    pad.paste(red_src, (PAD, 0))
    red_src = pad
    # make greyscale version
    marker_fg = red_src.convert('LA').convert('RGBA')
    path = os.path.join(dst_dir, 'pin_image.png')
    print('writing', path)
    marker_fg.save(path)
    # make colour infill alpha
    fg = red_src.getchannel('R')
    bg = red_src.convert('LA').getchannel('L')
    alpha = PIL.ImageChops.subtract(fg, bg, scale=0.35, offset=-160)
    path = os.path.join(dst_dir, 'pin_alpha.png')
    print('writing', path)
    alpha.save(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
