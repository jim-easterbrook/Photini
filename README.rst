Photini
=======

A free, easy to use, digital photograph metadata (EXIF, IPTC, XMP) editing application.

"Metadata" is said to mean "data about data".
In the context of digital photographs this means information that isn't essential in order to display the image, but tells you something about it.
For example a title and description of the scene or the date & time and the GPS coordinates of the camera's position when the picture was taken.

   "It doesn't try to be an all-singing, all-dancing image management powerhouse - it just lets you add information to photos, quickly and easily."
   
   -- `Linux Format`_ magazine, January 2013

Why is it called Photini?
Read my `blog post`_ on how I chose a name.

Features
--------

.. image:: http://photini.readthedocs.io/en/latest/_images/screenshot_11.png
   :alt: Text editing screenshot

*   Easy to use graphical interface.
*   Set photo title, description, keywords, copyright and creator fields.
*   Spell checking of some fields (optional).
*   Can set metadata for multiple images simultaneously.
*   Can adjust picture date & time.
*   Reads EXIF, IPTC and XMP metadata, writes all three to maximise compatibility with other software.
*   Writes metadata to image files or to XMP "sidecar" files.
*   Can import photographs from many digital cameras.
*   Upload to Flickr_ and/or Facebook_ and/or `Google Photos`_ and Picasa_ with reuse of metadata.

.. image:: http://photini.readthedocs.io/en/latest/_images/screenshot_19.png
   :alt: Geotagging screenshot

*   Geotagging - search map to find named places.
*   Choice of map providers - instantly switch to compare details.
*   Drag and drop images on to map to set GPS location.
*   Edit coordinates if required, or clear to unset GPS data.
*   Suggestions for further development welcome.

Dependencies
------------

An "all in one" installer for Windows is available that installs Photini and all its dependencies.
Users of other operating systems will need to install the following:

*   Python, version 2.6+ (including Python 3): http://python.org/
*   PyQt, version 4 or 5: http://www.riverbankcomputing.co.uk/software/pyqt/intro
*   six, version 1.9+: https://pypi.python.org/pypi/six/
*   appdirs, version 1.3+: http://pypi.python.org/pypi/appdirs/
*   gexiv2 (GObject Exiv2 wrapper), version 0.5+: https://wiki.gnome.org/Projects/gexiv2
*   Python GObject bindings:

    *   PyGObject: https://wiki.gnome.org/Projects/PyGObject **or**
    *   pgi: https://pypi.python.org/pypi/pgi/
*   PyEnchant (optional): http://pythonhosted.org/pyenchant/
*   python-keyring (optional), version 4.0+: https://pypi.python.org/pypi/keyring
*   python-flickrapi (optional), version 2.0+: https://pypi.python.org/pypi/flickrapi/
*   requests & requests-oauthlib (optional): https://github.com/kennethreitz/requests & https://github.com/requests/requests-oauthlib
*   python-gphoto2 (optional), version 0.10+: https://pypi.python.org/pypi/gphoto2/

For details of how to download and install these, please see the `installation documentation`_.

Documentation
-------------

.. warning::
   This program is still under development.
   It is already usable but, like all other software, it has bugs.
   Before using it be sure to back up all your photographs (you do this anyway, right?) as I can't guarantee you won't accidentally damage them.

Photini's documentation is a long way from complete, but you can read what's been written so far at http://photini.readthedocs.io/.

.. _readme-getting_help:

Getting help
------------

If you encounter any problems installing or running Photini, please email jim@jim-easterbrook.me.uk and I'll respond as soon as I can.
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
| Copyright (C) 2012-16  Jim Easterbrook  jim@jim-easterbrook.me.uk

| German translation by Jan Rimmek
| Spanish translation by Esteban Martinena & Cristos Ruiz
| Polish translation by "itdawid"

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

Use of the Google map tab is subject to the `Google Maps Terms of Use`_ and `Google Privacy Policy`_.

Use of the Bing map tab is subject to the `Microsoft Bing Maps Terms of Use`_ and `Microsoft Privacy Statement`_.

Use of the OpenStreetMap tab is subject to the `Nominatim usage policy`_ and the `MapQuest Terms of Use`_.

Privacy statement
^^^^^^^^^^^^^^^^^

Photini does not directly gather any information from its users, but the online services it can use (maps, Flickr, Facebook and Google Photos/Picasa) may do so.
You should read these services' privacy policies before using them.

Photini stores user preferences in a text file on the user's computer.
This file can be found in ``$HOME/.config/photini/`` (Linux) or ``%USERPROFILE%\AppData\Local\photini\`` (Windows).
OAuth_ access tokens for Flickr, Facebook & Google Photos are securely stored on the user's computer using `Python keyring`_.


Documentation licence
^^^^^^^^^^^^^^^^^^^^^

Permission is granted to copy, distribute and/or modify the Photini documentation under the terms of the GNU Free Documentation License, Version 1.3 or any later version published by the Free Software Foundation; with no Invariant Sections, no Front-Cover Texts, and no Back-Cover Texts.
A copy of the license is included in the documentation section entitled "GNU Free Documentation License".

.. _blog post:     http://jim-jotting.blogspot.co.uk/2012/10/photini-whats-in-name.html
.. _Facebook:      https://www.facebook.com/
.. _Flickr:        http://www.flickr.com/
.. _Google Maps Terms of Use:
                   http://www.google.com/help/terms_maps.html
.. _Google Photos: https://photos.google.com/
.. _Google Privacy Policy:
                   http://www.google.com/policies/privacy/
.. _installation documentation:
                   http://photini.readthedocs.io/en/latest/other/installation.html
.. _"issues" page: https://github.com/jim-easterbrook/Photini/issues
.. _Linux Format:  http://www.linuxformat.com/archives?issue=166
.. _localisation documentation:
                   http://photini.readthedocs.io/en/latest/other/localisation.html
.. _MapQuest Terms of Use:
                   http://hello.mapquest.com/terms-of-use
.. _Microsoft Bing Maps Terms of Use:
                   http://www.microsoft.com/maps/assets/docs/terms.aspx
.. _Microsoft Privacy Statement:
                   http://www.microsoft.com/en-us/privacystatement/
.. _Nominatim usage policy:
                   http://wiki.openstreetmap.org/wiki/Nominatim_usage_policy
.. _OAuth:         http://oauth.net/
.. _Photini team on Transifex:
                   https://www.transifex.com/projects/p/photini/
.. _Picasa:        http://picasaweb.google.com/
.. _Python keyring:
                   https://pypi.python.org/pypi/keyring#what-is-python-keyring-lib
