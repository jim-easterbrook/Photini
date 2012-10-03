Photini
=======

Easy to use digital photograph metadata (EXIF, IPTC, XMP) editing application.

Features
--------

![Text editing screenshot](http://github.com/jim-easterbrook/Photini/raw/master/doc/source/images/screenshot_text.png)

*   Easy to use graphical interface.
*   Set photo title, description, keywords, copyright and creator fields.
*   Can set metadata for multiple images simultaneously.

![Geolocation screenshot](http://github.com/jim-easterbrook/Photini/raw/master/doc/source/images/screenshot_map.png)

*   Search map to find places of interest.
*   Drag and drop images onto map to set GPS location.
*   Edit coordinates if required, or clear to unset GPS data.

*   Reads EXIF, IPTC or XMP metadata, writes all three to maximise compatibility with other software.
*   Planned tabs to adjust time & date and to use other map services.
*   Suggestions for further development welcome.

Dependencies
------------

*   Python, version 2.6+ (Python 3 is not yet supported): <http://python.org/>
*   PyQt, version 4+: <http://www.riverbankcomputing.co.uk/software/pyqt/intro>
*   pyexiv2, version 0.3.2: <http://tilloy.net/dev/pyexiv2/overview.html>.

Python and PyQt should be available from the repository of any modern Linux distribution. pyexiv2 is available from some Linux repositories, or from <http://tilloy.net/dev/pyexiv2/download.html>. If you need to build pyexiv2 you'll need to install boost.Python, libexiv2 and SCons. See <http://tilloy.net/dev/pyexiv2/developers.html#dependencies> for details and build instructions.

Python for Windows can be downloaded from <http://www.python.org/getit/windows/>. PyQt for Windows can be downloaded from <http://www.riverbankcomputing.co.uk/software/pyqt/download> and pyexiv2 for Windows can be downloaded from <http://tilloy.net/dev/pyexiv2/download.html>. Make sure you choose the Windows installers that match your Python version and system bit width. After installation of Python, make sure its directories (probably "C:\Python27" and "C:\Python27\Scripts") have been added to your PATH environment variable.

I hope that Photini will be a cross-platform application - do let me know if you try it on Windows or MacOS.

Warning
-------

This software is currently at a very early stage of development. I've put it on github as a backup, and so anyone interested can have a look and give me some early feedback. Before using it be sure to back up all your photographs (you do this anyway, right?) as I can't guarantee you won't accidentally damage them.

Legalese
--------

Photini - a simple photo metadata editor.  
<http://github.com/jim-easterbrook/Photini>  
Copyright (C) 2012  Jim Easterbrook  jim@jim-easterbrook.me.uk

This program is free software: you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

