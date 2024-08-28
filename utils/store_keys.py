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

from argparse import ArgumentParser
from configparser import ConfigParser
import datetime
import os
import random
import sys


def main(argv=None):
    if argv:
        sys.argv = argv
    parser = ArgumentParser(
        description='Obfuscate API keys for distribution')
    parser.add_argument('file', metavar='file', type=str, nargs=1,
                        help='raw keys.ini file')
    args = parser.parse_args()
    src_cfg = ConfigParser(interpolation=None)
    src_cfg.read(args.file)
    dst_cfg = ConfigParser(interpolation=None)
    # analyse keys
    charset = []
    offset = 0
    data = ''
    for section in src_cfg:
        if section == 'DEFAULT':
            continue
        dst_cfg[section] = {}
        for key, value in src_cfg[section].items():
            for c in value:
                if c not in charset:
                    charset.append(c)
            length = len(value)
            data += value
            dst_cfg[section][key] = repr((offset, length))
            offset += length
    # pad data with random values
    length = 1024
    data += ''.join(random.choices(charset, k=length - len(data)))
    # shuffle data with a repeatable random mapping
    today = datetime.date.today().isoformat()
    random.seed(today)
    mapping = random.sample(range(length), k=length)
    inverse_map = [None] * length
    for i, j in enumerate(mapping):
        inverse_map[j] = i
    data = ''.join([data[x] for x in inverse_map])
    dst_cfg['data'] = {'data': data, 'date': today}
    # store result
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    path = os.path.join(root, 'src', 'photini', 'data', 'keys.txt')
    with open(path, 'w') as f:
        # copy header
        with open(__file__) as hdr:
            for line in hdr.readlines():
                f.write(line)
                if not line.strip():
                    break
        dst_cfg.write(f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
