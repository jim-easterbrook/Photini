.. This is part of the Photini documentation.
   Copyright (C)  2017-19  Jim Easterbrook.
   See the file ../DOC_LICENSE.txt for copying conditions.

Video file handling
===================

Although designed primarily for use with still images Photini can also be used with video files.
The :doc:`image_selector` ``Open images`` dialogue normally shows image files only (``.jpg``, ``.gif``, etc.) but has a drop down selector to choose video files (``.mov``, ``.mp4``, etc.) instead, or all file types.

The Exiv2_ metadata library cannot write to video files, so Photini will always use XMP sidecars for the metadata you write.
Video files can also be rather large, so rewriting them could take some time.

Photini can read some metadata from video files if you have installed FFmpeg_ on your computer.
(See :ref:`installation - optional dependencies<installation-optional>`.)
An alternative is to compile Exiv2_ with video reading capability, but this is only available in some versions of Exiv2.
It is unlikely that the Exiv2 library installed with your operating system has been compiled with video capability, so you will probably need to compile it yourself.

Most video files don't have thumbnails, but Photini may be able to create one if you have FFmpeg_ installed on your computer.
Right-click on the file and choose ``regenerate thumbnail`` from the popup menu.
If Photini is able to generate a thumbnail it will store it in the XMP sidecar file.

The :doc:`flickr` tab can upload video files, but expect it to be slow.
Video files can be very large.

Compiling Exiv2 on Linux
------------------------

The following instructions assume some familiarity with compiling and installing software on Linux systems.
The examples shown are for one particular system at one particular time.
It is unlikely that exactly the same commands will work on your machine.
Don't blindly copy and paste them.

.. note::
   Replacing the Exiv2 library installed with your operating system may affect the operation of other programs.

Before attempting to compile Exiv2 with video support you should get Photini running with the versions of Exiv2 and GExiv2 installed by your system's package manager.
You can test if you already have video support by attempting to open a video file using the ``exiv2`` command line tool::

   jim@mole ~/Pictures/from_camera/2017/2017_06_07 $ exiv2 -pa MVI_2964.MOV
   Exiv2 exception in print action for file MVI_2964.MOV:
   MVI_2964.MOV: The file contains data of an unknown image type
   jim@mole ~/Pictures/from_camera/2017/2017_06_07 $ 

Clearly this version of Exiv2 cannot read video files.

The source code of Exiv2 can be downloaded from http://exiv2.org/download.html.
Video support is deprecated in version 0.27.1 and will probably be removed in a later version.
After extracting the archive (e.g. ``tar xf exiv2-0.27.1-Source.tar.gz``) change to the ``exiv2-0.27.1-Source`` directory.

Before compiling Exiv2 it's worth finding out where its files are put by the standard system installer::

   jim@mole ~/Documents/exiv2-0.27.1-Source $ dpkg-query -L libexiv2-14
   /.
   /usr
   /usr/share
   /usr/share/doc
   /usr/share/doc/libexiv2-14
   /usr/share/doc/libexiv2-14/copyright
   /usr/share/doc/libexiv2-14/changelog.Debian.gz
   /usr/lib
   /usr/lib/x86_64-linux-gnu
   /usr/lib/x86_64-linux-gnu/libexiv2.so.14.0.0
   /usr/lib/x86_64-linux-gnu/libexiv2.so.14
   jim@mole ~/Documents/exiv2-0.27.1-Source $

This shows that the "installation prefix" should be set to ``/usr`` rather than the default ``/usr/local``.
In addition, the "library directory" is ``/usr/lib/x86_64-linux-gnu`` instead of the more usual ``/usr/lib``. ::

   jim@mole ~/Documents/exiv2-0.27.1-Source $ mkdir build
   jim@mole ~/Documents/exiv2-0.27.1-Source $ cd build
   jim@mole ~/Documents/exiv2-0.27.1-Source/build $ cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_INSTALL_LIBDIR=/usr/lib/x86_64-linux-gnu -DEXIV2_ENABLE_VIDEO=yes -DEXIV2_BUILD_SAMPLES=no ..

You may need to install some more dependencies before ``cmake`` will run correctly.
Don't forget to install the "development headers" versions of packages such as ``libexpat``.

After configuration is successful you can compile and install::

   jim@mole ~/Documents/exiv2-0.27.1-Source/build $ make
   jim@mole ~/Documents/exiv2-0.27.1-Source/build $ sudo make install

Once compiled and installed we can try opening a video file again::

   jim@mole ~/Pictures/from_camera/2017/2017_06_07 $ exiv2 -pa MVI_2964.MOV
   Xmp.video.FileSize                           XmpText     7  18.2563
   Xmp.video.FileName                           XmpText    17  MVI_2964.MOV
   Xmp.video.MimeType                           XmpText    15  video/quicktime
   Xmp.video.MajorBrand                         XmpText    25  Apple QuickTime (.MOV/QT)
   Xmp.video.MinorVersion                       XmpText     9  537331968
   Xmp.video.CompatibleBrands                   XmpSeq      2  Apple QuickTime (.MOV/QT), Canon Digital Camera
   Xmp.video.CompressorVersion                  XmpText    30  CanonAVC0010/02.00.00/00.00.00
   Xmp.video.PreviewDate                        XmpText     1  0
   Xmp.video.PreviewVersion                     XmpText     1  0
   Xmp.video.PreviewAtomType                    XmpText     0  
   Xmp.video.MovieHeaderVersion                 XmpText     1  0
   Xmp.video.DateUTC                            XmpText    10  3579686878
   Xmp.video.ModificationDate                   XmpText    10  3579686878
   ...
   Xmp.audio.Balance                            XmpText     1  0
   Xmp.audio.Compressor                         XmpText     4  sowt
   Xmp.audio.ChannelType                        XmpText     1  2
   Xmp.audio.BitsPerSample                      XmpText     2  16
   Xmp.audio.SampleRate                         XmpText     5  48000
   Xmp.video.AspectRatio                        XmpText     4  16:9
   jim@mole ~/Pictures/from_camera/2017/2017_06_07 $ 

Compiling GExiv2 on Linux
-------------------------

Now that we have a video-capable version of Exiv2 we need to compile GExiv2 to use it.
Download the GExiv2 source from https://download.gnome.org/sources/gexiv2/0.10/, then extract the archive and change to its directory.

Once again we need to check where files are put by the standard system installer::

   jim@mole ~/Documents/gexiv2-0.10.6 $ dpkg-query -L gir1.2-gexiv2-0.10
   /.
   /usr
   /usr/share
   /usr/share/doc
   /usr/share/doc/gir1.2-gexiv2-0.10
   /usr/share/doc/gir1.2-gexiv2-0.10/copyright
   /usr/lib
   /usr/lib/python2.7
   /usr/lib/python2.7/dist-packages
   /usr/lib/python2.7/dist-packages/gi
   /usr/lib/python2.7/dist-packages/gi/overrides
   /usr/lib/python2.7/dist-packages/gi/overrides/GExiv2.py
   /usr/lib/x86_64-linux-gnu
   /usr/lib/x86_64-linux-gnu/girepository-1.0
   /usr/lib/x86_64-linux-gnu/girepository-1.0/GExiv2-0.10.typelib
   /usr/lib/python3
   /usr/lib/python3/dist-packages
   /usr/lib/python3/dist-packages/gi
   /usr/lib/python3/dist-packages/gi/overrides
   /usr/lib/python3/dist-packages/gi/overrides/GExiv2.py
   /usr/share/doc/gir1.2-gexiv2-0.10/changelog.Debian.gz
   jim@mole ~/Documents/gexiv2-0.10.6 $

As before ``/usr`` is the base directory, but the typelib file is installed in the "library directory" ``/usr/lib/x86_64-linux-gnu``.
We also need to tell configure to generate the "introspection bindings" used by Python::

   jim@mole ~/Documents/gexiv2-0.10.6 $ ./configure --enable-introspection --prefix=/usr --libdir=/usr/lib/x86_64-linux-gnu

Once again you may need to install additional dependencies::

   jim@mole ~/Documents/gexiv2-0.10.6 $ sudo apt-get install libglib2.0-dev libgirepository1.0-dev

Once configuration is successful the software can be compiled and installed as normal::

   jim@mole ~/Documents/gexiv2-0.10.6 $ make
   jim@mole ~/Documents/gexiv2-0.10.6 $ sudo make install

You can check what version of GExiv2 Photini is using as follows::

   jim@mole ~/Documents/gexiv2-0.10.6 $ python3 -m photini.editor --version
   Photini 2017.8.0, build 873 (93457b4)
     Python 3.5.2 (default, Nov 17 2016, 17:05:23) 
   [GCC 5.4.0 20160609]
     pgi 0.0.11.1, GExiv2 0.10.6, GObject 2.0
     PyQt 5.5.1, Qt 5.5.1, using QtWebKit
     enchant 1.6.8
     flickrapi 2.2.1
   jim@mole ~/Documents/gexiv2-0.10.6 $ 

.. _Exiv2:        http://www.exiv2.org/
.. _FFmpeg:       https://ffmpeg.org/
