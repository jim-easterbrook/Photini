Configuration
=============

If there are tabs in the Photini GUI that you don't use, you can remove them by deselecting their entry in the ``Options`` menu.

The ``Options`` menu also has a ``Settings`` item which opens the dialog shown below.

.. image:: ../images/screenshot_36.png

This allows you to edit the names used to auto-generate some descriptive metadata, reset the Flickr or Picasa authorisation (requiring you to re-authenticate next time you use them) and adjust how Photini uses "sidecar" files.

Sidecar files allow metadata to be stored without needing to write to the actual image file.
If you deselect "write to image" then sidecars will always be created.
Otherwise, you can choose to have them always created (storing data in parallel with the image file), only created when necessary (e.g. an image file is write protected), or deleted when possible (if metadata can be copied to the image file the sidecar is deleted).