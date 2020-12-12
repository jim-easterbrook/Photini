Notes
=====

Reminders for what to do when translations are updated.

New content on Transifex::

   tx pull -f                           # get all content from Transifex
   python3 utils/lang_update.py -s      # update from source, strip line numbers
   git commit ...                       # commit changes to git

Edit translation locally::

   tx pull -f -l xx                     # get language xx from Transifex
   python3 utils/lang_update.py -l xx   # update from source
   linguist-qt5 src/lang/xx/photini.ts  # edit translation
   tx push -t -l xx                     # push translation back to Transifex

When program or documentation source changes::

   python3 utils/lang_update.py         # update templates from source
   tx push -s                           # push templates to Transifex

Before a new release of Photini::

   tx pull -f                           # get all content from Transifex
   python3 utils/lang_update.py         # update from source
   python3 utils/build_lang.py          # "compile" language files
