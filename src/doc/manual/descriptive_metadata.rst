.. This is part of the Photini documentation.
   Copyright (C)  2012-22  Jim Easterbrook.
   See the file ../DOC_LICENSE.txt for copying condidions.

Descriptive metadata
====================

The ``Descriptive metadata`` tab (keyboard shortcut ``Alt+D``) allows you to edit basic information about your photographs, such as the title and description.

.. image:: ../images/screenshot_07.png

The first thing I usually do with a new set of photographs is to set the copyright and creator/artist metadata.
Select all the images (keyboard shortcut ``Ctrl+A``) then click on the ``Auto`` button next to the ``Copyright`` text entry box.
The first time you do this Photini asks you to provide the name of the copyright holder.
This should probably be your name, but could be the name of a company.
Type in the name and click ``OK``.

The ``Auto`` button generates a standard copyright notice.
If you prefer a different wording you can change the template, as described in :doc:`configuration <configuration>`.

.. image:: ../images/screenshot_08.png

Next click on the ``Creator / Artist`` field's ``Auto`` button.
(Some software calls this field "author" or "byline".)
Now Photini will ask for the name of the creator.
Edit the name if required, then click ``OK``.
(More detailed ownership information can be added with the :doc:`ownership_metadata` tab.)

.. |hazard| unicode:: U+026A1

Note that all the image thumbnails now have a warning symbol (|hazard|) displayed next to them.
This shows that they have unsaved metadata edits.
The ``File`` menu ``Save images with new data`` item (keyboard shortcut ``Ctrl+S``) saves your edits and clears the warning symbols, as shown below.
I do this frequently to avoid losing any of my work.

.. image:: ../images/screenshot_09.png

Next I set the title.
Select all the images that should have the same title, then type the title in the ``Title / Object name`` text editing box.
Note that the title (and keywords) are stored in XMP and IPTC-IIM but not in Exif, so may not be visible to software that only handles Exif metadata (see :doc:`tag reference <tags>` for more detail).
You may prefer to leave the title and keywords fields blank.

The legacy IPTC-IIM standard has a maximum number of bytes for each data item.
If your text has more bytes then the excess is shown underlined in blue.
You can ignore this if you don't need compatibility with old software that relies on IPTC-IIM data.
This warning can be turned off in Photini's :doc:`configuration <configuration>`.

The ``Title / Object name`` field has an optional spell checker, enabled with the ``Spelling`` menu.
The word "Château-Gontier" is not in the British English dictionary, as indicated by the red underlining.
Right-clicking on a misspelled word shows a list of suggested alternatives, one of which can be chosen by clicking on it.

.. image:: ../images/screenshot_10.png

Now you can add more detail in the ``Description / Caption`` box.
There are probably only one or two photographs that share the same description, so select those images first.

.. image:: ../images/screenshot_11.png

If you select a group of images you may see ``<multiple values>`` displayed in some of the text boxes.
You can right-click on the box to bring up a context menu from which you can choose a value to be copied to all the selected photographs.
In this case there is only one choice as one photo has a description and the other does not.

.. image:: ../images/screenshot_10a.png

Next you can set a list of keywords for the image by typing them in the ``Keywords`` box.
Keywords should be separated by semi-colon (;) characters.
The ``<favourites>`` drop-down list can be used to select keywords from the ones you use most often.

.. image:: ../images/screenshot_12.png

Finally the ``Rating`` slider allows you to note any particularly good or bad pictures.
Good pictures can be given a one to five star rating.

.. image:: ../images/screenshot_13.png

Bad pictures can be given a ``reject`` rating.
This is stored in the metadata as a rating value of -1.

.. image:: ../images/screenshot_14.png

Multi-language data fields
^^^^^^^^^^^^^^^^^^^^^^^^^^

Some XMP data fields can store alternative language versions of the data.
If a file has multi-lingual data (set by another application) then Photini displays all the languages simultaneously.
In this contrived example the default English description has French and German alternatives.

.. image:: ../images/screenshot_15.png

Photini cannot correctly save this multi-lingual data at present.
All the text as shown is saved as the default language.
If you need proper multi-lingual data handling then please contact me.
I have some ideas about how it could be added, but as a monoglot Englishman I don't need the feature myself.

More information about the data fields
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Click on any field name below to see the IPTC definition and user notes for that field.
Although these fields are defined in an `IPTC standard`_, they are all stored in XMP metadata.
Most of them are also stored in "legacy" IPTC-IIM data.

`Title / Object Name <http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#title>`_
  IPTC ``Headline`` data, if present, is merged into this field.
  Not stored in Exif.
`Description / Caption <http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#description>`_
  The who, what and why of what the image depicts.
`Keywords <http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#keywords>`_
  Separate words or phrases with ``;`` characters. Not stored in Exif.
`Rating <http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#image-rating>`_
  Not stored in Exif or IPTC-IIM.
`Copyright <http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#copyright-notice>`_
  Who owns the copyright.
  This shows the same information as the :doc:`ownership_metadata` ``Copyright Notice`` field.
`Creator / Artist <http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#creator>`_
  Usually the photographer's name.
  If there is more than one creator, separate them with a ``;`` character.
  This shows the same information as the :doc:`ownership_metadata` ``Creator`` field.

.. _IPTC standard:            http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata
