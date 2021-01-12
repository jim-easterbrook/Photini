Photini
=======

A free, easy to use, digital photograph metadata (Exif, IPTC, XMP) editing application.

"Metadata" is said to mean "data about data".
In the context of digital photographs this means information that isn't essential in order to display the image, but tells you something about it.
For example a title and description of the scene or the date & time and the GPS coordinates of the camera's position when the picture was taken.

   "[Photini] doesn't try to be an all-singing, all-dancing image management powerhouse - it just lets you add information to photos, quickly and easily."
   
   -- `Linux Format`_ magazine, January 2013

Why is it called Photini?
Read my `blog post`_ on how I chose a name.

.. contents::
   :backlinks: top

Features
--------

.. image:: http://photini.readthedocs.io/en/latest/_images/screenshot_11.png
   :alt: Text editing screenshot

*   Easy to use graphical interface.
*   Set photo title, description, keywords, copyright and creator fields.
*   Some support for video files.
*   Spell checking of some fields (optional).
*   Can set metadata for multiple images simultaneously.
*   Can adjust picture date & time and time zone (of multiple images simultaneously).
*   Reads Exif, IPTC and XMP metadata, writes all three to maximise compatibility with other software.
*   Writes metadata to image files or to XMP "sidecar" files.
*   Can import photographs from many digital cameras.
*   Upload to Flickr_ and/or `Google Photos`_ with reuse of metadata.

.. image:: http://photini.readthedocs.io/en/latest/_images/screenshot_136.png
   :alt: Geotagging screenshot

*   Geotagging - search map to find named places.
*   Choice of map providers - instantly switch to compare details.
*   Drag and drop images on to map to set GPS location.
*   Edit coordinates if required, or clear to unset GPS data.
*   Convert GPS coordinates to street address.
*   Suggestions for further development welcome.

Dependencies
------------

An "all in one" installer for Windows is available that installs Photini and all its dependencies.
Some Linux distributions include Photini in their standard "repository".
Users of other operating systems will need to install at least the following:

*   Python3: http://python.org/
*   PyQt5 or PySide2: http://www.riverbankcomputing.co.uk/software/pyqt/ or https://doc.qt.io/qtforpython/
*   gexiv2 (GObject Exiv2 wrapper), version 0.10+: https://wiki.gnome.org/Projects/gexiv2
*   PyGObject (Python GObject bindings): https://pygobject.readthedocs.io/

For a full list of dependencies, please see the `installation documentation`_.

Documentation
-------------

.. warning::
   This program, like all software, may have bugs.
   Before using it be sure to back up all your photographs (you do this anyway, right?) as I can't guarantee you won't accidentally damage them.

Photini's documentation is at http://photini.readthedocs.io/.
It includes detailed installation instructions and a full user manual.

.. _readme-getting_help:

Getting help
------------

If you encounter any problems installing or running Photini, please email jim@jim-easterbrook.me.uk and I'll respond as soon as I can.
There is also an email list or forum for discussions about Photini at https://groups.google.com/forum/#!forum/photini.
If you discover a bug and have a GitHub account then please file a bug report on the GitHub `"issues" page`_.

Internationalisation
--------------------

Work has begun on providing Photini in multiple languages.
I rely on users to do the translation, as I am not fluent in any language other than English.
If you'd like to help, please join the `Photini team on Transifex`_.
For more details, see the `localisation documentation`_.

.. _readme-legalese:

Licence
-------

| Photini - a simple photo metadata editor.
| http://github.com/jim-easterbrook/Photini
| Copyright (C) 2012-21  Jim Easterbrook  jim@jim-easterbrook.me.uk

| German translation by Jan Rimmek
| Spanish translation by Esteban Martinena & Cristos Ruiz
| Polish translation by "itdawid"
| Czech translation by Pavel Fric
| Catalan translation by Joan Juvanteny

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

Service terms and conditions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use of the Google map tab is subject to the `Google Maps Terms of Use`_ and `Google Privacy Policy`_.

Use of the Bing map tab is subject to the `Microsoft Bing Maps Terms of Use`_ and `Microsoft Privacy Statement`_.

Use of the Mapbox map tab is subject to the `Mapbox terms of service`_ and `Mapbox privacy policy`_.

The Flickr upload tab uses the Flickr API but is not endorsed or certified by Flickr.

Privacy statement
^^^^^^^^^^^^^^^^^

Photini does not directly gather any information from its users, but the online services it can use (maps, Flickr, and Google Photos) may do so.
You should read these services' privacy policies before using them.

Photini stores user preferences in a text file on the user's computer.
The default location of this file is ``$HOME/.config/photini/`` (Linux) or ``%USERPROFILE%\AppData\Local\photini\`` (Windows).
OAuth_ access tokens for Flickr and Google Photos are securely stored on the user's computer using `Python keyring`_.


Documentation licence
^^^^^^^^^^^^^^^^^^^^^

Permission is granted to copy, distribute and/or modify the Photini documentation under the terms of the GNU Free Documentation License, Version 1.3 or any later version published by the Free Software Foundation; with no Invariant Sections, no Front-Cover Texts, and no Back-Cover Texts.
A copy of the license is included in the documentation section entitled "GNU Free Documentation License".

.. _blog post:     http://jim-jotting.blogspot.co.uk/2012/10/photini-whats-in-name.html
.. _Flickr:        http://www.flickr.com/
.. _Google Photos: https://photos.google.com/
.. _Google Maps Terms of Use:
                   http://www.google.com/help/terms_maps.html
.. _Google Privacy Policy:
                   http://www.google.com/policies/privacy/
.. _installation documentation:
                   http://photini.readthedocs.io/en/latest/other/installation.html
.. _"issues" page: https://github.com/jim-easterbrook/Photini/issues
.. _Linux Format:  http://www.linuxformat.com/archives?issue=166
.. _localisation documentation:
                   http://photini.readthedocs.io/en/latest/other/localisation.html
.. _Mapbox terms of service:
                   https://www.mapbox.com/tos/
.. _Mapbox privacy policy:
                   https://www.mapbox.com/privacy/
.. _Microsoft Bing Maps Terms of Use:
                   http://www.microsoft.com/maps/assets/docs/terms.aspx
.. _Microsoft Privacy Statement:
                   http://www.microsoft.com/en-us/privacystatement/
.. _OAuth:         http://oauth.net/
.. _OpenStreetMap licence:
                   http://www.openstreetmap.org/copyright
.. _Photini team on Transifex:
                   https://www.transifex.com/projects/p/photini/
.. _Python keyring:
                   https://pypi.python.org/pypi/keyring#what-is-python-keyring-lib
