Photini
=======

An easy to use digital photograph metadata (EXIF, IPTC, XMP) editing application.

"Metadata" is said to mean "data about data".
In the context of digital photographs this means information that isn't essential in order to display the image, but tells you something about it.
For example a title and description of the scene or the date & time and the GPS coordinates of the camera's position when the picture was taken.

   "It doesn't try to be an all-singing, all-dancing image management powerhouse - it just lets you add information to photos, quickly and easily."
   
   -- `Linux Format <http://www.linuxformat.com/>`_ magazine, January 2013 

Features
--------

.. image:: http://jim-easterbrook.github.io/Photini/doc/html/_images/screenshot_11.png
   :alt: Text editing screenshot

*   Easy to use graphical interface.
*   Set photo title, description, keywords, copyright and creator fields.
*   Can set metadata for multiple images simultaneously.
*   Can adjust picture data & time.
*   Reads EXIF, IPTC or XMP metadata, writes all three to maximise compatibility with other software.
*   Writes metadata to image files or XMP "sidecar" files.
*   Can import photographs from a many digital cameras.
*   Upload to `Flickr <http://www.flickr.com/>`_ and/or `Picasa <http://picasaweb.google.com/>`_ with reuse of metadata.

.. image:: http://jim-easterbrook.github.io/Photini/doc/html/_images/screenshot_19.png
   :alt: Geotagging screenshot

*   Geotagging - search map to find named places.
*   Choice of map providers - instantly switch to compare details.
*   Drag and drop images onto map to set GPS location.
*   Edit coordinates if required, or clear to unset GPS data.
*   Suggestions for further development welcome.

Dependencies
------------

*   Python, version 2.6+ (including Python 3): http://python.org/
*   PyQt, version 4+: http://www.riverbankcomputing.co.uk/software/pyqt/intro
*   appdirs: http://pypi.python.org/pypi/appdirs/
*   gexiv2 (GObject Exiv2 wrapper), version 0.5+: https://wiki.gnome.org/Projects/gexiv2
*   Python GObject bindings:

    *   PyGObject: https://wiki.gnome.org/Projects/PyGObject *or*
    *   pgi: https://pypi.python.org/pypi/pgi/
*   python-flickrapi (optional): https://pypi.python.org/pypi/flickrapi/
*   gdata-python-client (optional): https://pypi.python.org/pypi/gdata/
*   python-gphoto2 (optional): https://pypi.python.org/pypi/gphoto2/

For details of how to download and install these, please see the `documentation <http://jim-easterbrook.github.io/Photini/doc/html/installation.html>`_.

I hope that Photini will be a cross-platform application - do let me know if you try it on Windows or MacOS.

Documentation
-------------

Photini's documentation is a long way from complete, but you can read what's been written so far at http://jim-easterbrook.github.io/Photini/doc/html/.

.. _readme-warning:

Warning
-------

This program is still under development. It is already usable but, like all other software, it has bugs. Before using it be sure to back up all your photographs (you do this anyway, right?) as I can't guarantee you won't accidentally damage them.

.. _readme-legalese:

Legalese
--------

| Photini - a simple photo metadata editor.
| http://github.com/jim-easterbrook/Photini
| Copyright (C) 2012-14  Jim Easterbrook  jim@jim-easterbrook.me.uk

This program is free software: you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see http://www.gnu.org/licenses/.

Map terms and conditions
^^^^^^^^^^^^^^^^^^^^^^^^

Use of the Google map tab is subject to the `Google Maps Terms of Use <http://www.google.com/help/terms_maps.html>`_.

Use of the Bing map tab is subject to the `Microsoft Bing Maps Terms of Use <http://www.microsoft.com/maps/assets/docs/terms.aspx>`_.

Use of the OpenStreetMap tab is subject to the `Nominatim usage policy <http://wiki.openstreetmap.org/wiki/Nominatim_usage_policy>`_ and the `MapQuest Terms and Conditions <http://developer.mapquest.com/web/info/terms-of-use>`_.
