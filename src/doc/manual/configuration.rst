.. This is part of the Photini documentation.
   Copyright (C)  2012-15  Jim Easterbrook.
   See the file ../DOC_LICENSE.txt for copying condidions.

Configuration
=============

If there are tabs in the Photini GUI that you don't use, you can remove them by deselecting their entry in the ``Options`` menu.

The ``Options`` menu also has a ``Settings`` item which opens the dialog shown below.

.. image:: ../images/screenshot_36.png

This allows you to edit the names used to auto-generate some descriptive metadata, reset the Flickr or Picasa authorisation (requiring you to re-authenticate next time you use them) and adjust how Photini uses "sidecar" files and IPTC metadata.

Sidecar files allow metadata to be stored without needing to write to the actual image file.
If you deselect "write to image" then sidecars will always be created.
Otherwise, you can choose to have them always created (storing data in parallel with the image file), only created when necessary (e.g. an image file is write protected), or deleted when possible (if metadata can be copied to the image file the sidecar is deleted).

.. versionadded:: 15.08.0.dev311
   The `Metadata Working Group <http://www.metadataworkinggroup.org/specs/>`_ recommends that IPTC metadata is not written to files unless already present.
   Photini has an option to always write IPTC metadata.
   You may need this if you use some other software that reads IPTC but not Exif or XMP.

Spell checking
^^^^^^^^^^^^^^

The ``Spelling`` menu allows you to enable or disable spell checking on Photini's text fields, and to select the language dictionary to use.
The available languages depend on what dictionaries you have installed.
See the `PyEnchant documentation <http://pythonhosted.org/pyenchant/tutorial.html#adding-language-dictionaries>`_ for details of how to add dictionaries.