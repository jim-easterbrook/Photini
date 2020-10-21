##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-19  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import json
import subprocess
import sys

import six


def startupinfo():
    if sys.platform.startswith('win'):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    return None

try:
    ffmpeg_version = subprocess.check_output(
        ['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-version'],
        startupinfo=startupinfo())
    if not six.PY2:
        ffmpeg_version = ffmpeg_version.decode('utf-8')
    ffmpeg_version = ffmpeg_version.splitlines()[0]
except OSError as ex:
    print('ffmpeg not found')
    ffmpeg_version = None


class FFmpeg(object):
    @staticmethod
    def ffprobe(path, options=['-show_format', '-show_streams']):
        if not ffmpeg_version:
            return {}
        cmd = ['ffprobe', '-hide_banner', '-loglevel', 'warning']
        cmd += options
        cmd += ['-print_format', 'json', path]
        p = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            startupinfo=startupinfo())
        output, error = p.communicate()
        if p.returncode:
            if not six.PY2:
                error = error.decode('utf-8')
            error = error.splitlines()[0]
            raise RuntimeError('ffprobe: {}'.format(error))
        if not six.PY2:
            output = output.decode('utf-8')
        return json.loads(output)

    @staticmethod
    def get_dimensions(path):
        if not ffmpeg_version:
            return {}
        return FFmpeg.ffprobe(
            path, options=[
                '-show_entries', 'stream=width,height,duration',
                '-select_streams', 'v:0']
            )['streams'][0]

    @staticmethod
    def make_thumbnail(path, w, h, skip, quality):
        if not ffmpeg_version:
            return None
        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'warning']
        if skip > 0:
            cmd += ['-ss', str(skip)]
        cmd += ['-noautorotate', '-i', path, '-an', '-vframes', '1']
        cmd += ['-vf', ('scale={w}:{h}:force_original_aspect_ratio=decrease,'
                        'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2').format(w=w, h=h)]
        cmd += ['-sws_flags', 'sinc', '-f', 'image2pipe',
                '-vcodec', 'mjpeg', '-q:v', str(quality), 'pipe:1']
        p = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            startupinfo=startupinfo())
        output, error = p.communicate()
        if p.returncode:
            if not six.PY2:
                error = error.decode('utf-8')
            error = error.splitlines()[0]
            raise RuntimeError('ffmpeg: {}'.format(error))
        return output
