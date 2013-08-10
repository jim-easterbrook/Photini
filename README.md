Photini
=======

Easy to use digital photograph metadata (EXIF, IPTC, XMP) editing application.

"It doesn't try to be an all-singing, all-dancing image management powerhouse &mdash; it just lets you add information to photos, quickly and easily." &mdash; [Linux Format](http://www.linuxformat.com/) magazine, January 2013 

Features
--------

![Text editing screenshot](http://github.com/jim-easterbrook/Photini/raw/master/doc_src/images/screenshot_11.png)

*   Easy to use graphical interface.
*   Set photo title, description, keywords, copyright and creator fields.
*   Can set metadata for multiple images simultaneously.
*   Can adjust picture data & time.
*   Upload to [Flickr](http://www.flickr.com/) and/or [Picasa](http://picasaweb.google.com/) with reuse of metadata.

![Geolocation screenshot](http://github.com/jim-easterbrook/Photini/raw/master/doc_src/images/screenshot_19.png)

*   Search map to find places of interest.
*   Choice of map providers - instantly switch to compare details.
*   Drag and drop images onto map to set GPS location.
*   Edit coordinates if required, or clear to unset GPS data.
*   Reads EXIF, IPTC or XMP metadata, writes all three to maximise compatibility with other software.
*   Suggestions for further development welcome.

Documentation
-------------

Photini's documentation is a long way from complete, but you can read what's been written so far at <http://jim-easterbrook.github.com/Photini/doc/html/>.

Dependencies
------------

*   Python, version 2.6+ (Python 3 is not yet supported): <http://python.org/>
*   PyQt, version 4+: <http://www.riverbankcomputing.co.uk/software/pyqt/intro>
*   GExiv2, version 0.5+: <http://redmine.yorba.org/projects/gexiv2/wiki> *or* pyexiv2, version 0.3.2: <http://tilloy.net/dev/pyexiv2/overview.html>.
*   python-flickrapi (optional): <http://stuvel.eu/flickrapi>
*   gdata-python-client (optional): <http://code.google.com/p/gdata-python-client/>

For details of how to download and install these, please see the documentation.

I hope that Photini will be a cross-platform application - do let me know if you try it on Windows or MacOS.

Warning
-------

This program is currently at an early stage of development, but it is already usable. However, like all other software, it has bugs. Before using it be sure to back up all your photographs (you do this anyway, right?) as I can't guarantee you won't accidentally damage them.

Legalese
--------

Photini - a simple photo metadata editor.  
<http://github.com/jim-easterbrook/Photini>  
Copyright (C) 2012-13  Jim Easterbrook  jim@jim-easterbrook.me.uk

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

### Map terms and conditions

Use of the Google map tab is subject to the [Google Maps Terms of Use](http://www.google.com/help/terms_maps.html).

Use of the Bing map tab is subject to the [Microsoft Bing Maps Terms of Use](http://www.microsoft.com/maps/assets/docs/terms.aspx).

Use of the OpenStreetMap tab is subject to the [Nominatim usage policy](http://wiki.openstreetmap.org/wiki/Nominatim_usage_policy) and the [CloudMade Terms and Conditions](http://cloudmade.com/terms_conditions).