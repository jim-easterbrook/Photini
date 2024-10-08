.. This is part of the Photini documentation.
   Copyright (C)  2019-24  Jim Easterbrook.
   See the file ../DOC_LICENSE.txt for copying conditions.

Extending Photini
=================

It is possible to add new functionality to Photini by providing a new "tab".
This is of limited usefulness as the new functionality can only use existing Photini metadata items, unless you want to try "monkey patching" the ``photini.metadata`` module.

Because the tabs are loaded dynamically at run-time the new tab does not need to be part of the Photini Python package.
For example, if the package ``mypackage`` provides a Photini tab in the module ``mypackage.photini``, then adding ``mypackage.photini`` to the tab modules list (see :ref:`configuration-tabs`) will make the tab available in Photini.

.. code-block:: guess

    [tabs]
    modules = ['photini.descriptive',
             'photini.ownership',
             'photini.technical',
             'mypackage.photini',
             'photini.googlemap',
             'photini.bingmap',
             'photini.azuremap',
             'photini.mapboxmap',
             'photini.address',
             'photini.regions',
             'photini.flickr',
             'photini.ipernity',
             'photini.pixelfed',
             'photini.importer',
             'photini.googlephotos']

You can add your module anywhere in the configuration file's module list.
The user can then set the tab order by drag and drop.

Every Photini tab has to have the following interface:

.. code-block:: python

   class TabWidget(QtWidgets.QWidget):
       @staticmethod
       def tab_name():
           return 'Tab name'

       def __init__(self, *arg, **kw):
           super(TabWidget, self).__init__(*arg, **kw)
           self.app = QtWidgets.QApplication.instance()
           # Add child widgets here. self.app has several useful attributes
           # such as the configuration and image_list objects.

       def refresh(self):
           # Called when the user selects the tab. If your tab does something
           # slow, such as contacting a server, then do it here rather than in
           # __init__. You might also want to update your tab to synchronise with
           # changes made in another tab, like the map tabs do. Otherwise, just
           # update the displayed metadata.
           self.new_selection(self.app.image_list.get_selected_images())

       def do_not_close(self):
           # Return True if your tab is busy (e.g. uploading photographs) and
           # wants to stop the user closing the Photini program.
           return False

       def new_selection(self, selection):
           # Called when the image thumbnail area has a new selection. Most tabs
           # will need to update their displayed metadata to suit the selection.

The ``tab_name`` method returns the label given to the tab.
It should be as short as possible.

When the user defines any new metadata you should get the current selection from the ``self.app.image_list`` and set the metadata on every image in the selection.

It's probably easiest to start with a copy of the Photini tab module most like what you want to do, strip out the bits you don't need and then add your own stuff.
