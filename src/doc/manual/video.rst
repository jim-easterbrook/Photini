.. This is part of the Photini documentation.
   Copyright (C)  2017-21  Jim Easterbrook.
   See the file ../DOC_LICENSE.txt for copying conditions.

Video file handling
===================

Although designed primarily for use with still images Photini can also be used with video files.
The :doc:`image_selector` ``Open images`` dialogue normally shows image files only (``.jpg``, ``.gif``, etc.) but has a drop down selector to choose video files (``.mov``, ``.mp4``, etc.) instead, or all file types.

The Exiv2_ metadata library cannot write to video files, so Photini will always use XMP sidecars for the metadata you write.
Video files can also be rather large, so rewriting them could take some time.
Photini can read some metadata from video files if you have installed FFmpeg_ on your computer.
(See :ref:`installation - optional dependencies<installation-optional>`.)

Most video files don't have thumbnails, but Photini may be able to create one if you have FFmpeg_ installed on your computer.
Right-click on the file and choose ``regenerate thumbnail`` from the popup menu.
If Photini is able to generate a thumbnail it will store it in the XMP sidecar file.

The :doc:`flickr` tab can upload video files, but expect it to be slow.
Video files can be very large.

.. _Exiv2:        http://www.exiv2.org/
.. _FFmpeg:       https://ffmpeg.org/
