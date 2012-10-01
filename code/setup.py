#!/usr/bin/env python

from distutils.core import setup

# This installs the Photini editor as 'editor.py'. This is probably a
# bad idea for two reasons: the name isn't obviously related to
# Photini and the name ends in .py. Probably ought to write shell
# scripts (with platform dependent names) to run the python editor and
# install them instead.

setup(name='Photini',
      version='0.1',
      author='Jim Easterbrook',
      author_email='jim@jim-easterbrook.me.uk',
      url='https://github.com/jim-easterbrook/Photini',
      description='Simple photo metadata editor',
      long_description="""
Photini is a GUI program to create and edit metadata for digital
photographs. It can set textual information such as title, description
and copyright as well as geolocation information by browsing a map or
setting coordinates directly. It reads metadata in EXIF, IPTC or XMP
format and writes it to all three, to maximise compatibility with
other software.
""",
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Intended Audience :: End Users/Desktop',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2 :: Only',
          ],
      packages=['photini'],
      package_data={'photini' : ['googlemap.js'],},
      scripts=['editor.py'],
      )
