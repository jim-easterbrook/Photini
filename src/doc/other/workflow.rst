.. This is part of the Photini documentation.
   Copyright (C)  2012-19  Jim Easterbrook.
   See the file DOC_LICENSE.txt for copying conditions.

Typical workflow
================

This is a suggestion for how to use Photini.
It roughly reflects what I do, but is just a guideline for beginners.
As you gain experience you may choose to do things differently.
There is no requirement to fill in all the metadata fields, nor to do them in any particular order.

Make a backup copy
------------------

Before editing any of your images' metadata you should make a backup copy.
Even if I could guarantee that Photini was bug free and would never corrupt an image file, you still might have a power cut or other computer failure at just the wrong time and ruin a photograph you can never take again.
Before you start, please make a backup copy of your photographs.

Load images
-----------

Select the ``File`` menu ``Open images`` item (keyboard shortcut ``Ctrl+O``).
This opens a file selection dialog with which you can navigate to your image folder and select one or more image files to open.
If you prefer, you can "drag and drop" image files from a file manager window to the Photini editor's image selector.

Photini doesn't set a limit to the number of files you can open simultaneously, but it's probably sensible not to open more than 30 or 40, depending on the memory capacity and processing power of your computer.
I usually load all the photographs taken on one day, or in one place.

Each image file is shown as a thumbnail image in the lower half of the Photini editor GUI.
You can adjust the space allocated to this area by clicking and dragging the bar between it and the upper tab area.
The thumbnails can be made larger or smaller with the ``thumbnail size`` slider.
Choose a size that allows you to see a reasonable number of images, yet still tell one from another.
Double click on any thumbnail to view the full size image in your default picture viewing program.

Set text metadata
-----------------

I usually start by setting the fields that are the same for all the photos I've loaded - ``Creator / Artist``, ``Copyright`` and ``Title / Object Name``.
First you need to select the images whose metadata you want to change.
Images are selected by clicking on their thumbnails.
Shift+click and Ctrl+click can be used to select multiple images in the usual way.
The quickest way to select all the images is the keyboard shortcut ``Ctrl+A``.

The ``Creator / Artist`` and ``Copyright`` fields have ``Auto`` buttons to help fill them in.
The first time you use these buttons Photini will ask for the names of the creator and the copyright owner.
For amateur photographers these will probably be the same person, but in some cases the copyright might be owned by a company or some other organisation.
The values you supply are saved for future use in Photini's configuration file.

If all your selected pictures have the same title then type it into the ``Title / Object Name`` field now.
Otherwise it's time to start selecting single images, or groups of images, and filling in the remaining text fields.

The ``Keywords`` field expects a list of words or short phrases, separated by semi-colon (;) characters.

Save your work so far
---------------------

.. |hazard| unicode:: U+026A1

As you proceed it's a good idea to save the images that have new metadata with the ``File`` menu ``Save images with new data`` item (keyboard shortcut ``Ctrl+S``).
Any images with unsaved metadata have thumbnails marked with a warning symbol (|hazard|).

Set geolocation
---------------

Amongst the commonly used image metadata items are the latitude and longitude of the position from which the photograph was taken.
(Some people argue that it should be the position of the subject of the photograph, but what about photographs of the Moon?)
Photini makes it easy to set the latitude and longitude of any photograph by dragging and dropping it onto a map.

There are currently four map tabs in the Photini editor, each of which gets maps (or aerial photographs) from a different provider: Google, Microsoft Bing, Mapbox, and Open Street Map.
(Each of these providers has terms and conditions you should read and accept before using their maps.)
The maps differ in appearance, and show different levels of detail for different parts of the world.
You should use the one that you like best, but it's very easy to switch to another at any time.

You may be able use the map's navigation and zoom controls to find the area you want, but usually you will need to use the search box.
Click on ``<new search>`` and type in a search term such as the name of a town.
Note that the search is biased towards the current map location, so you might want to zoom out and pan to the right continent before searching.
Type a search term into the box and hit return.
A list of results should appear very soon, from which you can choose the one you want.
Each map provider has its own search engine, so if you can't find the place you are looking for it might be worth trying a different provider.

.. |flag| unicode:: U+02690

Now zoom in and drag the map to home in on the place where your photographs were taken.
Select one or more images that have a particular location and drag them onto the map.
A marker should appear on the map and the latitude and longitude values will be displayed below the search box.
The marker can be dragged around the map to adjust its position - you may find it easier to select the map's aerial or satellite option, at the highest zoom available, to set the exact position.
Each image that has had a location set has its thumbnail marked with a flag symbol (|flag|).
