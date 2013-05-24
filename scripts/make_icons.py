#!/usr/bin/env python

##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-13  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import Image
import ImageChops
import ImageDraw
import ImageOps

def draw_marker(width, height, offset, filename):
    im = Image.new('L', (128, 256), 255)
    draw = ImageDraw.Draw(im)

    cx = (im.size[0] / 2) + 1.5
    cy = (im.size[1] / 4) + 1.5
    radius = width * 4 / 2
    offset = int(offset * 4)
    for thickness, colour in ((0, 0x60), (4, 0xE0)):
        ol = im.copy()
        r = radius + 0.5 - thickness
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour)
        x1 = offset + 0.5 - (thickness * 3 / 2)
        y1 = (height * 4) + 0.5 - (width * 2) - (thickness * 2)
        draw.polygon((cx + 0.5, cy + y1, cx - 0.5, cy + y1,
                      cx - x1, cy + 16.5, cx + x1, cy + 16.5),
                     fill=colour)
    del draw

    im = im.resize((im.size[0] / 4, im.size[1] / 4), Image.ANTIALIAS)
    ol = ol.resize(im.size, Image.ANTIALIAS)
    mask = Image.eval(ol, lambda x: (0, 255)[x < 210])
    im = Image.composite(im, ImageChops.constant(im, 0), mask)
    im = im.crop(im.getbbox())
    im.save(filename, transparency=0)

draw_marker(25, 37, 8.5, '../photini/data/bing_grey_marker.png')
draw_marker(25, 40, 12, '../photini/data/osm_grey_marker.png')
