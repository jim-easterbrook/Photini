.. This is part of the Photini documentation.
   Copyright (C)  2021  Jim Easterbrook.
   See the file ../DOC_LICENSE.txt for copying condidions.

Ownership metadata
==================

The ``Ownership metadata`` tab (keyboard shortcut ``Alt+O``) allows you to edit ownership and copyright information about your photographs.

.. image:: ../images/screenshot_200.png

Most of this data will be the same for all your photographs, so Photini uses a "template" to apply the same text to all the selected images.
The ``Edit template`` button opens the dialog shown below.

.. image:: ../images/screenshot_201.png

Fill in any of the fields you want to use on every photograph.
The field labels are copied from the `IPTC standard`_, as is the help text which should pop up if you hover your mouse over a field.

.. image:: ../images/screenshot_202.png

Note that you can insert the year in which a photograph was taken with ``%Y``.
This is probably only useful in the ``Copyright Notice``, but is available for all fields.
(You can actually use any directive recognised by the `Python strftime function`_, such as ``%m`` for month number or ``%B`` for the month name.)

.. image:: ../images/screenshot_203.png

The ``Apply template`` button copies the template data to all the selected images, setting the correct year in the ``Copyright Notice``.
You can then add more information, or edit the existing information, in the usual way.

Although these fields are defined in an `IPTC standard`_, they are all stored in XMP metadata.
Some of them are also stored in "legacy" IPTC-IIM data.

.. _IPTC standard:            http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata
.. _Python strftime function: https://docs.python.org/3.6/library/datetime.html#strftime-strptime-behavior
