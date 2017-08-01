.. This is part of the Photini documentation.
   Copyright (C)  2017  Jim Easterbrook.
   See the file ../DOC_LICENSE.txt for copying condidions.

Video file handling
===================

Although designed primarily for use with still images Photini can also be used with video files.
The :doc:`image_selector` ``Open images`` dialogue normally shows image files only (``.jpg``, ``.gif``, etc.) but has a drop down selector to choose video files (``.mov``, ``.mp4``, etc.) instead, or all file types.

The `Exiv2`_ metadata library cannot write to video files, so Photini will always use XMP sidecars for the metadata you write.
If you compile your own copy of `Exiv2`_ you can configure it to be able to read some metadata from video files.
This may enable Photini to read date & time, and possibly GPS location data.

The image selector currently does not show a thumbnail for video files.

The :doc:`flickr`, :doc:`facebook`, and :doc:`picasa` tabs can all upload video files, but expect it to be slow.
Video files can be very large.

.. _Exiv2:        http://www.exiv2.org/
