.. This is part of the Photini documentation.
   Copyright (C)  2025  Jim Easterbrook.
   See the file ../DOC_LICENSE.txt for copying conditions.

Map API keys
============

Photini's maps and address lookup tabs all rely on commercial online services.
Access to these services is controlled via "API keys".
The map services are all free of charge, up to a certain level of usage, while the address lookup (geolocation) service has a small charge per lookup.

By default Photini uses API keys provided by its developer, Jim Easterbrook.
This works well enough at present, but these keys could be disabled at any time.
For example:

* If usage increases sufficiently to cross the "free use" threshold then the relevant key will be disabled.
* If Jim's credit card expires or is cancelled then the relevant keys may become disabled.

Photini users are encouraged to obtain their own "personal" API keys (for the services they use) to reduce reliance on the default keys.
(There is nothing to stop you sharing your "personal" keys with trusted family and friends, if they also use Photini.)
Photini's API keys can be set via its :ref:`configuration<configuration-api-keys>` menu.

The tabs below describe how to set up an account and obtain an API key for each of the services Photini uses.
They are rather brief at present.
Please let me know if you encounter any problems and I'll try to improve these instructions.

.. tabs::

    .. tab:: Azure Maps

        Please see the `Azure Maps quickstart`_ page that guides you through the process of setting up an Azure account and getting a map API key.
        When you create an Azure account I suggest choosing a "pay as you go" account to avoid any difficulty changing account type later on.

        When you create an "Azure Maps Account resource" select the only "Subscription" and "Resource Group" you have, invent a suitable name, choose the "Region" closest to where you live, tick the "I confirm that I have read..." box and click ``Review + create`` followed by ``Create``.

        After clicking ``Go to resource`` the ``Settings -> Authentication`` menu shows a "Primary Key" and a "Secondary Key".
        Either of these can be copied to Photini's configuration dialog.

    .. tab:: Google Maps

        Please see `Getting started with Google Maps Platform`_ for details of how to set up a Google Maps account.
        Create a project, then enable these APIs:

        * Maps JavaScript API
        * Geocoding API
        * Maps Elevation API

        Now go to the ``Credentials`` page and click ``Create credentials -> API key`` to generate a new API key.
        Give it a name, if you like, then select ``Application restrictions -> None``, ``API restrictions -> Restrict key``, ``Select APIs -> Geocoding, Maps Elevation, Maps JavaScript``, then click on ``Create``.

        If all goes well you should now be shown an API key that you can copy and paste to Photini's configuration dialog.

        Even with these restrictions, Google may still occasionally send you emails warning of dire consequences if you don't restrict your API keys.
        They really want you to limit usage to a fixed IP address, but that's not useful if you use Photini from more than one location.

    .. tab:: Mapbox Maps

        Mapbox is delightfully to simple to set up, compared to Google and Azure.
        First go to `Create your account`_, fill in the form and click on ``Continue``.

        On your "Account overview" page click on ``View all tokens``, then ``Create a token``.
        Choose a name, deselect all "scopes" except ``Styles:tiles``, ``Styles:read``, and ``Fonts:read``, then click ``Create token``.
        This should take you to the "Access tokens" page, from where you can copy the new token to Photini's configuration dialog.

    .. tab:: OpenCage Geocoding

        First create an account via the `OpenCage Create account`_ page.
        You need to give an organisation or company name; I suggest "Personal" or similar.
        On the next page select "Reverse geocoding" as the primary use case, and enter "Python" in the software box, then click ``Continue``.

        On the "Your Dashboard" page select "Geocoding API" and copy the key to Photini's configuration dialog.
        After verifying that your key works, you should click ``Purchase a plan``, then choose ``One-time purchase`` and buy the "small one-time" option.
        This buys 10,000 address lookups, which should cover many years of use with Photini.

.. _Azure Maps quickstart:
    https://learn.microsoft.com/en-us/azure/azure-maps/quick-demo-map-app
.. _Create your account:
    https://account.mapbox.com/auth/signup/
.. _Getting started with Google Maps Platform:
    https://developers.google.com/maps/get-started
.. _OpenCage Create account:
    https://opencagedata.com/users/sign_up
