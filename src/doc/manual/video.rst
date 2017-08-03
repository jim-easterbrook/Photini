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

The :doc:`flickr` and :doc:`picasa` tabs can upload video files, but expect it to be slow.
Video files can be very large.

Compiling Exiv2 on Linux
------------------------

The following instructions assume some familiarity with compiling and installing software on Linux systems.
The examples shown are for one particular system at one particular time.
It is unlikely that exactly the same commands will work on your machine.
Don't blindly copy and paste them.

Before attempting to compile Exiv2 with video support you should get Photini running with the versions of Exiv2 and GExiv2 installed by your system's package manager.
You can test if you already have video support by attempting to open a video file using the ``exiv2`` command line tool::

   jim@mole ~/Pictures/from_camera/2017/2017_06_07 $ exiv2 -pa MVI_2964.MOV
   Exiv2 exception in print action for file MVI_2964.MOV:
   MVI_2964.MOV: The file contains data of an unknown image type
   jim@mole ~/Pictures/from_camera/2017/2017_06_07 $ 

Clearly this version of Exiv2 cannot read video files.

Before compiling Exiv2 we need to know where its library is installed::

   jim@mole ~/Documents $ which exiv2
   /usr/bin/exiv2
   jim@mole ~/Documents $ ldd /usr/bin/exiv2
           linux-vdso.so.1 =>  (0x00007ffd1cdea000)
           libexiv2.so.14 => /usr/lib/x86_64-linux-gnu/libexiv2.so.14 (0x00007efd0143f000)
           libstdc++.so.6 => /usr/lib/x86_64-linux-gnu/libstdc++.so.6 (0x00007efd010bd000)
           libgcc_s.so.1 => /lib/x86_64-linux-gnu/libgcc_s.so.1 (0x00007efd00ea6000)
           libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007efd00adc000)
           libz.so.1 => /lib/x86_64-linux-gnu/libz.so.1 (0x00007efd008c2000)
           libexpat.so.1 => /lib/x86_64-linux-gnu/libexpat.so.1 (0x00007efd00698000)
           libdl.so.2 => /lib/x86_64-linux-gnu/libdl.so.2 (0x00007efd00494000)
           libm.so.6 => /lib/x86_64-linux-gnu/libm.so.6 (0x00007efd0018b000)
           /lib64/ld-linux-x86-64.so.2 (0x0000556ffdaed000)
   jim@mole ~/Documents $ 

You can see that it's installed under ``/usr/lib``.
The default when building from source would be to use ``/usr/local/lib``.

The source code of Exiv2 can be downloaded from http://exiv2.org/download.html.
After extracting the archive (e.g. ``tar xf exiv2-0.26-trunk.tar.gz``) change to the ``exiv2-trunk`` and run ``configure`` to prepare the compilation.
We need to set two configuration options: ``--enable-video`` to enable Exiv2 to read video files, and ``--prefix=/usr`` to install in the same directory as the current version::

   jim@mole ~/Documents/exiv2-trunk $ ./configure --enable-video --prefix=/usr

You may need to install some more dependencies before ``configure`` will run correctly.
Don't forget to install the "development headers" versions of packages such as ``libexpat``.

After configuration is successful you can compile and install::

   jim@mole ~/Documents/exiv2-trunk $ make
   jim@mole ~/Documents/exiv2-trunk $ sudo make install

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

Once again we need to specify the installation directory when running ``configure``.
We also need to tell it to generate the "introspection bindings" used by Python::

   jim@mole ~/Documents/gexiv2-0.10.6 $ ./configure --enable-introspection --prefix=/usr

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
     pgi 0.0.11.1, GExiv2 0.10.3, GObject 2.0
     PyQt 5.5.1, Qt 5.5.1, using QtWebKit
     enchant 1.6.8
     flickrapi 2.2.1
   jim@mole ~/Documents/gexiv2-0.10.6 $ 

In this case it's still picking up version 0.10.3, so we need to remove the version installed from the system repository::

   jim@mole ~/Documents/gexiv2-0.10.6 $ sudo apt-get remove gir1.2-gexiv2-0.10

Now Photini picks up the correct version::

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
