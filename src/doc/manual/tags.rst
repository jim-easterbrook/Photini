.. This is part of the Photini documentation.
   Copyright (C)  2012-25  Jim Easterbrook.
   See the file ../DOC_LICENSE.txt for copying conditions.

Tag reference
=============

This section lists the "mapping" from Photini's field names (such as "Title / Object Name") to the Exif / XMP / IPTC-IIM tags the data is stored in.
The tag names are those used by the Exiv2 library.
See http://exiv2.org/metadata.html for more detail.

As far as possible Photini follows the `Metadata Working Group <https://en.wikipedia.org/wiki/Metadata_Working_Group>`_ (MWG) "Guidelines for Handling Image Metadata".
These specify the mapping between tags in Exif, XMP and IPTC-IIM, and say how software should reconcile any differences between information stored in equivalent tags.

Primary tags
------------

These tags are where Photini stores its metadata.
(Legacy IPTC-IIM data is only used if it already exists in the file, in line with the MWG guidelines, unless the "write unconditionally" user setting is enabled.)

Note that some fields, such as "Title / Object Name" and "Keywords", are not stored in Exif.
You may prefer not to use these fields to ensure compatibility with software that only handles Exif.

Some of the field names in the table below link to their definition in the IPTC standard.
You may find this useful when deciding what to write in those fields.

.. |wbr| unicode:: 0xAD
    :trim:

.. |lbr| raw:: html

    <div style="line-height: 0; padding: 0; margin: 0"></div>

.. list-table:: Primary tags
    :header-rows: 1
    :class: wrapped-table

    * - Photini field
      - Exif tag
      - XMP tag
      - IPTC-IIM tag
    * - `Title / Object Name`_
      -
      - Xmp.dc |wbr| .title
      - Iptc.Application2 |wbr| .ObjectName
    * - Headline_
      -
      - Xmp.photoshop |wbr| .Headline
      - Iptc.Application2 |wbr| .Headline
    * - `Description / Caption`_
      - Exif.Image |wbr| .ImageDescription
      - Xmp.dc |wbr| .description
      - Iptc.Application2 |wbr| .Caption
    * - `Alt Text`_
      -
      - Xmp.iptc |wbr| .AltTextAccessibility
      -
    * - `Extended Description`_
      -
      - Xmp.iptc |wbr| .ExtDescrAccessibility
      -
    * - `Person(s) shown`_
      -
      - Xmp.iptcExt |wbr| .PersonInImage
      -
    * - Rating_
      -
      - Xmp.xmp |wbr| .Rating
      -
    * - Keywords_
      -
      - Xmp.dc |wbr| .subject
      - Iptc.Application2 |wbr| .Keywords
    * - Hierarchical keywords
      -
      - Xmp.lr |wbr| .hierarchicalSubject |lbr|
        Xmp.digiKam |wbr| .TagsList
      -
    * - Creator_
      - Exif.Image |wbr| .Artist
      - Xmp.dc |wbr| .creator
      - Iptc.Application2 |wbr| .Byline
    * - `Creator's Jobtitle`_
      -
      - Xmp.photoshop |wbr| .AuthorsPosition
      - Iptc.Application2 |wbr| .BylineTitle
    * - `Credit Line`_
      -
      - Xmp.photoshop |wbr| .Credit
      - Iptc.Application2 |wbr| .Credit
    * - `Copyright Notice`_
      - Exif.Image |wbr| .Copyright
      - Xmp.dc |wbr| .rights
      - Iptc.Application2 |wbr| .Copyright
    * - `Rights: Usage Terms`_
      -
      - Xmp.xmpRights |wbr| .UsageTerms
      -
    * - `Rights: Web Statement`_
      -
      - Xmp.xmpRights |wbr| .WebStatement
      -
    * - Instructions_
      -
      - Xmp.photoshop |wbr| .Instructions
      - Iptc.Application2 |wbr| .SpecialInstructions
    * - `Contact Information`_
      -
      - Xmp.plus.Licensor
      - Iptc.Application2 |wbr| .Contact
    * - `Date / time Taken`_
      - Exif.Photo |wbr| .DateTimeOriginal |lbr|
        Exif.Photo |wbr| .SubSecTimeOriginal |lbr|
        Exif.Photo |wbr| .OffsetTimeOriginal
      - Xmp.photoshop |wbr| .DateCreated
      - Iptc.Application2 |wbr| .DateCreated |lbr|
        Iptc.Application2 |wbr| .TimeCreated
    * - Date / time Digitised
      - Exif.Photo |wbr| .DateTimeDigitized |lbr|
        Exif.Photo |wbr| .SubSecTimeDigitized |lbr|
        Exif.Photo |wbr| .OffsetTimeDigitized
      - Xmp.xmp |wbr| .CreateDate
      - Iptc.Application2 |wbr| .DigitizationDate |lbr|
        Iptc.Application2 |wbr| .DigitizationTime
    * - Date / time Modified
      - Exif.Image |wbr| .DateTime |lbr|
        Exif.Photo |wbr| .SubSecTime |lbr|
        Exif.Photo |wbr| .OffsetTime
      - Xmp.xmp |wbr| .ModifyDate
      -
    * - Orientation
      - Exif.Image |wbr| .Orientation
      -
      -
    * - Camera
      - Exif.Image |wbr| .Make |lbr|
        Exif.Image |wbr| .Model |lbr|
        Exif.Photo |wbr| .BodySerialNumber
      -
      -
    * - Lens
      - Exif.Photo |wbr| .LensMake |lbr|
        Exif.Photo |wbr| .LensModel |lbr|
        Exif.Photo |wbr| .LensSerialNumber |lbr|
        Exif.Photo |wbr| .LensSpecification
      -
      -
    * - Focal length
      - Exif.Photo |wbr| .FocalLength
      -
      -
    * - 35mm equiv
      - Exif.Photo |wbr| .FocalLengthIn35mmFilm
      -
      -
    * - Aperture
      - Exif.Photo |wbr| .FNumber |lbr|
        Exif.Photo |wbr| .ApertureValue
      -
      -
    * - `Image Regions`_
      -
      - Xmp.iptcExt |wbr| .ImageRegion |lbr|
        Xmp.mwg-rs |wbr| .Regions |lbr|
        Xmp.MP |wbr| .RegionInfo
      -
    * - Latitude_, longitude_
      - Exif.GPSInfo |wbr| .GPSLatitude |lbr|
        Exif.GPSInfo |wbr| .GPSLatitudeRef |lbr|
        Exif.GPSInfo |wbr| .GPSLongitude |lbr|
        Exif.GPSInfo |wbr| .GPSLongitudeRef
      -
      -
    * - Altitude_
      - Exif.GPSInfo |wbr| .GPSAltitude |lbr|
        Exif.GPSInfo |wbr| .GPSAltitudeRef
      -
      -
    * - `Camera address`_
      -
      - Xmp.iptcExt |wbr| .LocationCreated |lbr|
        Xmp.iptc |wbr| .Location |lbr|
        Xmp.photoshop |wbr| .City |lbr|
        Xmp.photoshop |wbr| .State |lbr|
        Xmp.photoshop |wbr| .Country |lbr|
        Xmp.iptc |wbr| .CountryCode
      - Iptc.Application2 |wbr| .SubLocation |lbr|
        Iptc.Application2 |wbr| .City |lbr|
        Iptc.Application2 |wbr| .ProvinceState |lbr|
        Iptc.Application2 |wbr| .CountryName |lbr|
        Iptc.Application2 |wbr| .CountryCode
    * - `Subject address`_
      -
      - Xmp.iptcExt |wbr| .LocationShown
      -
    * - Thumbnail image
      - Exif.Thumbnail |wbr| .Compression |lbr|
        Exif.Thumbnail |wbr| .ImageWidth |lbr|
        Exif.Thumbnail |wbr| .ImageLength
      -
      -

Secondary tags
--------------

Photini may read information from these tags and merge it with information from the primary tags.
These tags are deleted when the corresponding primary tags are saved.

.. list-table:: Secondary tags
    :header-rows: 1
    :class: wrapped-table

    * - Photini field
      - Exif tag
      - XMP tag
    * - Title / Object Name
      - Exif.Image |wbr| .XPTitle
      -
    * - Description / Caption
      - Exif.Image |wbr| .XPComment |lbr|
        Exif.Image |wbr| .XPSubject |lbr|
        Exif.Photo |wbr| .UserComment
      - Xmp.exif |wbr| .UserComment |lbr|
        Xmp.tiff |wbr| .ImageDescription
    * - Keywords
      - Exif.Image |wbr| .XPKeywords
      -
    * - Rating
      - Exif.Image |wbr| .Rating |lbr|
        Exif.Image |wbr| .RatingPercent
      - Xmp.MicrosoftPhoto |wbr| .Rating
    * - Creator
      - Exif.Image |wbr| .XPAuthor
      - Xmp.tiff |wbr| .Artist
    * - Copyright
      -
      - Xmp.tiff |wbr| .Copyright
    * - Contact Information
      -
      - Xmp.iptc |wbr| .CreatorContactInfo
    * - Date / time Taken
      - Exif.Image |wbr| .DateTimeOriginal
      - Xmp.exif |wbr| .DateTimeOriginal
    * - Date / time Digitised
      -
      - Xmp.exif |wbr| .DateTimeDigitized
    * - Date / time Modified
      -
      - Xmp.tiff |wbr| .DateTime
    * - Lens
      - Exif.Image |wbr| .LensInfo
      - Xmp.aux |wbr| .Lens
    * - Focal length
      - Exif.Image |wbr| .FocalLength
      -
    * - Aperture
      - Exif.Image |wbr| .FNumber |lbr|
        Exif.Image |wbr| .ApertureValue
      -
    * - Thumbnail image
      -
      - Xmp.xmp |wbr| .Thumbnails[n]/xapGImg

XMP only tags
-------------

These tags are read if present, but are only written if the file format doesn't support Exif, e.g. an XMP sidecar.

.. list-table:: XMP only tags
    :header-rows: 1
    :class: wrapped-table

    * - Photini field
      - XMP tag
    * - Orientation
      - Xmp.tiff |wbr| .Orientation
    * - Lens
      - Xmp.exifEX |wbr| .LensMake |lbr|
        Xmp.exifEX |wbr| .LensModel |lbr|
        Xmp.exifEX |wbr| .LensSerialNumber |lbr|
        Xmp.exifEX |wbr| .LensSpecification
    * - Focal length
      - Xmp.exif |wbr| .FocalLength
    * - 35mm equiv
      - Xmp.exif |wbr| .FocalLengthIn35mmFilm
    * - Aperture
      - Xmp.exif |wbr| .FNumber |lbr|
        Xmp.exif |wbr| .ApertureValue
    * - Latitude, longitude
      - Xmp.exif |wbr| .GPSLatitude |lbr|
        Xmp.exif |wbr| .GPSLongitude
    * - Altitude
      - Xmp.exif |wbr| .GPSAltitude |lbr|
        Xmp.exif |wbr| .GPSAltitudeRef
    * - Thumbnail image
      - Xmp.xmp |wbr| .Thumbnails[n]/xmpGImg

Read only tags
--------------

Photini may read information from these tags and merge it with information from the primary tags.
These tags are not deleted when the corresponding primary tags are saved.

.. list-table:: Read only tags
    :header-rows: 1
    :class: wrapped-table

    * - Photini field
      - Exif tag
      - XMP tag
    * - Title / Object Name
      -
      - Xmp.video |wbr| .StreamName
    * - Description / Caption
      -
      - Xmp.video |wbr| .Information
    * - Time zone offset[1]
      - Exif.Image |wbr| .TimeZoneOffset |lbr|
        Exif.NikonWt |wbr| .Timezone
      - Xmp.video |wbr| .TimeZone
    * - Creator
      - Exif.Photo |wbr| .CameraOwnerName |lbr|
        Exif.Canon |wbr| .OwnerName
      -
    * - Date / time Taken
      -
      - Xmp.video |wbr| .DateTimeOriginal |lbr|
        Xmp.video |wbr| .CreateDate |lbr|
        Xmp.video |wbr| .CreationDate |lbr|
        Xmp.video |wbr| .DateUTC |lbr|
        Xmp.video |wbr| .MediaCreateDate |lbr|
        Xmp.video |wbr| .TrackCreateDate
    * - Date / time Modified
      -
      - Xmp.video |wbr| .ModificationDate |lbr|
        Xmp.video |wbr| .MediaModifyDate |lbr|
        Xmp.video |wbr| .TrackModifyDate
    * - Camera
      - Exif.Image |wbr| .CameraSerialNumber |lbr|
        Exif.Image |wbr| .UniqueCameraModel |lbr|
        Exif.Canon |wbr| .ModelID |lbr|
        Exif.Canon |wbr| .SerialNumber |lbr|
        Exif.Fujifilm |wbr| .SerialNumber |lbr|
        Exif.Nikon3 |wbr| .SerialNumber |lbr|
        Exif.OlympusEq |wbr| .CameraType |lbr|
        Exif.OlympusEq |wbr| .SerialNumber |lbr|
        Exif.Pentax |wbr| .ModelID |lbr|
        Exif.Pentax |wbr| .SerialNumber
      - Xmp.aux |wbr| .SerialNumber |lbr|
        Xmp.video |wbr| .Make |lbr|
        Xmp.video |wbr| .Model
    * - Lens
      - Exif.Canon |wbr| .LensModel |lbr|
        Exif.CanonCs |wbr| .Lens |lbr|
        Exif.CanonCs |wbr| .LensType |lbr|
        Exif.Nikon3 |wbr| .Lens |lbr|
        Exif.NikonLd1 |wbr| .LensIDNumber |lbr|
        Exif.NikonLd2 |wbr| .LensIDNumber |lbr|
        Exif.NikonLd3 |wbr| .LensIDNumber |lbr|
        Exif.OlympusEq |wbr| .LensModel |lbr|
        Exif.OlympusEq |wbr| .LensSerialNumber
      -
    * - Image Regions
      - Exif.Photo |wbr| .SubjectArea
      -
    * - Latitude, longitude
      -
      - Xmp.video |wbr| .GPSCoordinates
    * - Altitude
      -
      - Xmp.video |wbr| .GPSCoordinates
    * - Thumbnail image
      - Exif.SubImage*
      -

[1] The time zone offset is not directly presented to the user.
It is applied to the Date / time Taken, Date / time Digitised and Date / time Modified fields if no other time zone information is available.

.. _Altitude:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#gps-altitude
.. _Alt Text:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#alt-text-accessibility
.. _Camera address:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#location-created
.. _Contact Information:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#licensor
.. _Copyright Notice:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#copyright-notice
.. _Creator:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#creator
.. _Creator's Jobtitle:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#creators-jobtitle
.. _Credit Line:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#credit-line
.. _Date / time Taken:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#date-created
.. _Description / Caption:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#description
.. _Extended Description:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#extended-description-accessibility
.. _Headline:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#headline
.. _Image Regions:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#image-region
.. _Instructions:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#instructions
.. _Keywords:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#keywords
.. _Latitude:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#gps-latitude
.. _longitude:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#gps-longitude
.. _Person(s) shown:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#person-shown-in-the-image
.. _Rating:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#image-rating
.. _Rights\: Usage Terms:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#rights-usage-terms
.. _Rights\: Web Statement:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#web-statement-of-rights
.. _Subject address:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#location-shown-in-the-image
.. _Title / Object Name:
    http://www.iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#title
