Flickr uploader
===============

The ``Flickr upload`` tab (keyboard shortcut ``Alt+F``) allows you to upload your photographs to `Flickr <http://www.flickr.com/>`_.
Flickr is a popular online photograph sharing service.

Unlike some other Flickr uploaders, Photini uses the descriptive metadata you've created to set Flickr's title, description and tags.
This means you don't have to retype all that information!

Note that the Flickr upload tab is only enabled if you have installed python-flickrapi.
See :ref:`installation <installation-flickr>` for more detail.

The first time you select Photini's Flickr upload tab it will ask you to authorise Photini to access Flickr.
It does this by connecting your web browser to Flickr, from where you can log in and then give Photini permission to access Flickr on your behalf.
With python-flickrapi v1.4 you can then close your web browser and return to Photini.
With v2.0 you need to copy a verification code from your browser to Photini, as shown in the screen grab.

.. image:: ../images/screenshot_22.png

To upload one or more photographs to Flickr, select them in the image selector area, then choose which (if any) of your sets (or albums) to add them to and set any of the other attributes, then click on the ``Upload now`` button.
You can create a new set before uploading with the "new set" button.

.. image:: ../images/screenshot_23.png

During uploading Photini displays a progress bar.
Uploading takes place in the background, so you can continue to use other tabs while the upload is in progress.

.. image:: ../images/screenshot_24.png
