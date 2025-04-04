.. This is part of the Photini documentation.
   Copyright (C)  2012-24  Jim Easterbrook.
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

Some of the field names in the table below lingk to their definition in the IPTC standard.
You may find this useful when deciding what to write in those fields.

.. list-table:: Primary tags
    :header-rows: 1

    * - Photini field
      - Exif tag
      - XMP tag
      - IPTC-IIM tag
    * - `Title / Object Name`_
      -
      - Xmp.dc.title
      - Iptc.Application2.ObjectName
    * - Headline_
      -
      - Xmp.photoshop.Headline
      - Iptc.Application2.Headline
    * - `Description / Caption`_
      - Exif.Image.ImageDescription
      - Xmp.dc.description
      - Iptc.Application2.Caption
    * - `Alt Text`_
      -
      - Xmp.iptc.AltTextAccessibility
      -
    * - `Extended Description`_
      -
      - Xmp.iptc.ExtDescrAccessibility
      -
    * - `Person(s) shown`_
      -
      - Xmp.iptcExt.PersonInImage
      -
    * - Rating_
      -
      - Xmp.xmp.Rating
      -
    * - Keywords_
      -
      - Xmp.dc.subject
      - Iptc.Application2.Keywords
    * - Hierarchical keywords
      -
      - Xmp.lr.hierarchicalSubject Xmp.digiKam.TagsList
      -
    * - Creator_
      - Exif.Image.Artist
      - Xmp.dc.creator
      - Iptc.Application2.Byline
    * - `Creator's Jobtitle`_
      -
      - Xmp.photoshop.AuthorsPosition
      - Iptc.Application2.BylineTitle
    * - `Credit Line`_
      -
      - Xmp.photoshop.Credit
      - Iptc.Application2.Credit
    * - `Copyright Notice`_
      - Exif.Image.Copyright
      - Xmp.dc.rights
      - Iptc.Application2.Copyright
    * - `Rights: Usage Terms`_
      -
      - Xmp.xmpRights.UsageTerms
      -
    * - `Rights: Web Statement`_
      -
      - Xmp.xmpRights.WebStatement
      -
    * - Instructions_
      -
      - Xmp.photoshop.Instructions
      - Iptc.Application2.SpecialInstructions
    * - `Contact Information`_
      -
      - Xmp.plus.Licensor
      - Iptc.Application2.Contact
    * - `Date / time Taken`_
      - Exif.Photo.DateTimeOriginal Exif.Photo.SubSecTimeOriginal
      - Xmp.photoshop.DateCreated
      - Iptc.Application2.DateCreated Iptc.Application2.TimeCreated
    * - Date / time Digitised
      - Exif.Photo.DateTimeDigitized Exif.Photo.SubSecTimeDigitized
      - Xmp.xmp.CreateDate
      - Iptc.Application2.DigitizationDate Iptc.Application2.DigitizationTime
    * - Date / time Modified
      - Exif.Image.DateTime Exif.Photo.SubSecTime
      - Xmp.xmp.ModifyDate
      -
    * - Orientation
      - Exif.Image.Orientation
      -
      -
    * - Camera
      - Exif.Image.Make Exif.Image.Model Exif.Photo.BodySerialNumber
      -
      -
    * - Lens
      - Exif.Photo.LensMake Exif.Photo.LensModel Exif.Photo.LensSerialNumber Exif.Photo.LensSpecification
      -
      -
    * - Focal length
      - Exif.Photo.FocalLength
      -
      -
    * - 35mm equiv
      - Exif.Photo.FocalLengthIn35mmFilm
      -
      -
    * - Aperture
      - Exif.Photo.FNumber Exif.Photo.ApertureValue
      -
      -
    * - `Image Regions`_
      -
      - Xmp.iptcExt.ImageRegion Xmp.mwg-rs.Regions Xmp.MP.RegionInfo
      -
    * - Latitude_, longitude_
      - Exif.GPSInfo.GPSLatitude Exif.GPSInfo.GPSLatitudeRef Exif.GPSInfo.GPSLongitude Exif.GPSInfo.GPSLongitudeRef
      -
      -
    * - Altitude_
      - Exif.GPSInfo.GPSAltitude Exif.GPSInfo.GPSAltitudeRef
      -
      -
    * - `Camera address`_
      -
      - Xmp.iptcExt.LocationCreated Xmp.iptc.Location Xmp.photoshop.City Xmp.photoshop.State Xmp.photoshop.Country Xmp.iptc.CountryCode
      - Iptc.Application2.SubLocation Iptc.Application2.City Iptc.Application2.ProvinceState Iptc.Application2.CountryName Iptc.Application2.CountryCode
    * - `Subject address`_
      -
      - Xmp.iptcExt.LocationShown
      -
    * - Thumbnail image
      - Exif.Thumbnail.Compression Exif.Thumbnail.ImageWidth Exif.Thumbnail.ImageLength
      -
      -

Secondary tags
--------------

Photini may read information from these tags and merge it with information from the primary tags.
These tags are deleted when the corresponding primary tags are saved.

.. list-table:: Secondary tags
    :header-rows: 1

    * - Photini field
      - Exif tag
      - XMP tag
    * - Title / Object Name
      - Exif.Image.XPTitle
      -
    * - Description / Caption
      - Exif.Image.XPComment Exif.Image.XPSubject Exif.Photo.UserComment
      - Xmp.exif.UserComment Xmp.tiff.ImageDescription
    * - Keywords
      - Exif.Image.XPKeywords
      -
    * - Rating
      - Exif.Image.Rating Exif.Image.RatingPercent
      - Xmp.MicrosoftPhoto.Rating
    * - Creator
      - Exif.Image.XPAuthor
      - Xmp.tiff.Artist
    * - Copyright
      -
      - Xmp.tiff.Copyright
    * - Contact Information
      -
      - Xmp.iptc.CreatorContactInfo
    * - Date / time Taken
      - Exif.Image.DateTimeOriginal
      - Xmp.exif.DateTimeOriginal
    * - Date / time Digitised
      -
      - Xmp.exif.DateTimeDigitized
    * - Date / time Modified
      -
      - Xmp.tiff.DateTime
    * - Lens
      - Exif.Image.LensInfo
      - Xmp.aux.Lens
    * - Focal length
      - Exif.Image.FocalLength
      -
    * - Aperture
      - Exif.Image.FNumber Exif.Image.ApertureValue
      -
    * - Thumbnail image
      -
      - Xmp.xmp.Thumbnails[n]/xapGImg

XMP only tags
-------------

These tags are read if present, but are only written if the file format doesn't support Exif, e.g. an XMP sidecar.

.. list-table:: XMP only tags
    :header-rows: 1

    * - Photini field
      - XMP tag
    * - Orientation
      - Xmp.tiff.Orientation
    * - Lens
      - Xmp.exifEX.LensMake Xmp.exifEX.LensModel Xmp.exifEX.LensSerialNumber Xmp.exifEX.LensSpecification
    * - Focal length
      - Xmp.exif.FocalLength
    * - 35mm equiv
      - Xmp.exif.FocalLengthIn35mmFilm
    * - Aperture
      - Xmp.exif.FNumber Xmp.exif.ApertureValue
    * - Latitude, longitude
      - Xmp.exif.GPSLatitude Xmp.exif.GPSLongitude
    * - Altitude
      - Xmp.exif.GPSAltitude Xmp.exif.GPSAltitudeRef
    * - Thumbnail image
      - Xmp.xmp.Thumbnails[n]/xmpGImg

Read only tags
--------------

Photini may read information from these tags and merge it with information from the primary tags.
These tags are not deleted when the corresponding primary tags are saved.

.. list-table:: Read only tags
    :header-rows: 1

    * - Photini field
      - Exif tag
      - XMP tag
    * - Title / Object Name
      -
      - Xmp.video.StreamName
    * - Description / Caption
      -
      - Xmp.video.Information
    * - Time zone offset[1]
      - Exif.Image.TimeZoneOffset Exif.NikonWt.Timezone
      - Xmp.video.TimeZone
    * - Creator
      - Exif.Photo.CameraOwnerName Exif.Canon.OwnerName
      -
    * - Date / time Taken
      -
      - Xmp.video.DateTimeOriginal Xmp.video.CreateDate Xmp.video.CreationDate Xmp.video.DateUTC Xmp.video.MediaCreateDate Xmp.video.TrackCreateDate
    * - Date / time Modified
      -
      - Xmp.video.ModificationDate Xmp.video.MediaModifyDate Xmp.video.TrackModifyDate
    * - Camera
      - Exif.Image.CameraSerialNumber Exif.Image.UniqueCameraModel Exif.Canon.ModelID Exif.Canon.SerialNumber Exif.Fujifilm.SerialNumber Exif.Nikon3.SerialNumber Exif.OlympusEq.CameraType Exif.OlympusEq.SerialNumber Exif.Pentax.ModelID Exif.Pentax.SerialNumber
      - Xmp.aux.SerialNumber Xmp.video.Make Xmp.video.Model
    * - Lens
      - Exif.Canon.LensModel Exif.CanonCs.Lens Exif.CanonCs.LensType Exif.Nikon3.Lens Exif.NikonLd1.LensIDNumber Exif.NikonLd2.LensIDNumber Exif.NikonLd3.LensIDNumber Exif.OlympusEq.LensModel Exif.OlympusEq.LensSerialNumber
      -
    * - Image Regions
      - Exif.Photo.SubjectArea
      -
    * - Latitude, longitude
      -
      - Xmp.video.GPSCoordinates
    * - Altitude
      -
      - Xmp.video.GPSCoordinates
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
