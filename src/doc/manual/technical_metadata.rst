.. This is part of the Photini documentation.
   Copyright (C)  2012-15  Jim Easterbrook.
   See the file ../DOC_LICENSE.txt for copying condidions.

Technical metadata
==================

The ``Technical metadata`` tab (keyboard shortcut ``Alt+T``) allows you to edit 'technical' information about your photographs, such as the date & time they were taken.
Generally you should not need to edit any of this data, as it should have been correctly set by your camera.

.. image:: ../images/screenshot_12.png

The date can be picked from a calendar widget that pops up when you click on the down arrow.
The time can be adjusted by clicking on the hour, minute or second and then using the up or down arrows.
You can also double click on any of the numbers to select it and type a new value in directly.
The date and time fields can be cleared with their ``clear`` buttons.

The ``Link ...`` tick-boxes allow the different date & time values to be changed simultaneously.
The ``Digitised`` and ``Modified`` date & time values can only be edited when their ``Link`` boxes are not ticked.

The ``Adjust times`` fields allow a constant offset to be applied to the time stamps of several pictures at once.
This can be useful if you forgot to set your camera's clock before a day's shooting!
Set the required offset hours, minutes & seconds, then use the ``+`` or ``-`` button to add or subtract that amount from each selected picture's timestamp.

The ``Orientation`` value sets the required rotation or reflection to display the image.
Note that this does not actually transform the image data.
Image display programs should rotate or reflect the image according to the orientation metadata, but not all of them do.

The ``Lens model`` dropdown list allows you to change the lens specification stored in the image metadata.
This should usually be left blank for cameras with non-removable lenses, but may be useful if you have an SLR that you use with lenses that its electronics doesn't recognise.

If the ``Link lens model ...`` tick-box is selected when you change the lens model then the focal length and aperture will be adjusted to fit the lens specification.
The focal length and aperture can also be edited directly, regardless of the tick-box status.

You can add details of all your lenses by selecting ``<add lens>`` from the dropdown list.

.. image:: ../images/screenshot_12a.png

This brings up a dialog box for you to enter the lens details.
You might want to start by dragging the edge of the box to make the text fields a bit larger.
Type all the relevant information into the appropriate boxes, leaving blank any information you don't have such as the serial number.
Only the ``Model name`` and ``Minimum focal length`` are required.

.. image:: ../images/screenshot_12b.png

The data you enter is stored in the Photini configuration file so you can easily apply it to images in future by selecting the lens you have defined from the dropdown list.
