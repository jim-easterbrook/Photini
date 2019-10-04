.. This is part of the Photini documentation.
   Copyright (C)  2012-19  Jim Easterbrook.
   See the file ../DOC_LICENSE.txt for copying conditions.

Tag reference
=============

This section lists the "mapping" from Photini's field names (such as "Title / Object Name") to the Exif / XMP / IPTC tags the data is stored in.
The tag names are those used by the Exiv2 library.
See http://exiv2.org/metadata.html for more detail.

As far as possible Photini follows the `Metadata Working Group <https://en.wikipedia.org/wiki/Metadata_Working_Group>`_ (MWG) "Guidelines for Handling Image Metadata".
These specify the mapping between tags in Exif, XMP and IPTC, and say how software should reconcile any differences between information stored in equivalent tags.

Primary tags
------------

These tags are where Photini stores its metadata.
(IPTC tags are only used if they already exist in the file, in line with the MWG guidelines, unless the "write unconditionally" user setting is enabled.)

Note that "Title / Object Name" and "Keywords" are not stored in Exif.
You may prefer not to use these fields to ensure compatibility with software that only handles Exif.

=====================  ================================  ==============================  ==================
Photini field          Exif tag                          XMP tag                         IPTC tag
=====================  ================================  ==============================  ==================
Title / Object Name                                      Xmp.dc.title                    Iptc.Application2.ObjectName
Description / Caption  Exif.Image.ImageDescription       Xmp.dc.description              Iptc.Application2.Caption
Keywords                                                 Xmp.dc.subject                  Iptc.Application2.Keywords
Copyright              Exif.Image.Copyright              Xmp.dc.rights                   Iptc.Application2.Copyright
Creator / Artist       Exif.Image.Artist                 Xmp.dc.creator                  Iptc.Application2.Byline
Date / time Taken      Exif.Photo.DateTimeOriginal       Xmp.photoshop.DateCreated       Iptc.Application2.DateCreated
                       Exif.Photo.SubSecTimeOriginal                                     Iptc.Application2.TimeCreated
Date / time Digitised  Exif.Photo.DateTimeDigitized      Xmp.xmp.CreateDate              Iptc.Application2.DigitizationDate
                       Exif.Photo.SubSecTimeDigitized                                    Iptc.Application2.DigitizationTime
Date / time Modified   Exif.Image.DateTime               Xmp.xmp.ModifyDate
                       Exif.Photo.SubSecTime
Orientation            Exif.Image.Orientation            Xmp.tiff.Orientation
Aperture               Exif.Photo.FNumber                Xmp.exif.FNumber
Focal length           Exif.Photo.FocalLength            Xmp.exif.FocalLength
35mm equiv             Exif.Photo.FocalLengthIn35mmFilm  Xmp.exif.FocalLengthIn35mmFilm
Lens maker name        Exif.Photo.LensMake
Lens model name        Exif.Photo.LensModel
Lens serial number     Exif.Photo.LensSerialNumber
Lens specification     Exif.Photo.LensSpecification
Latitude, longitude    Exif.GPSInfo.GPSLatitude          Xmp.exif.GPSLatitude
                       Exif.GPSInfo.GPSLatitudeRef       Xmp.exif.GPSLongitude
                       Exif.GPSInfo.GPSLongitude
                       Exif.GPSInfo.GPSLongitudeRef
Altitude               Exif.GPSInfo.GPSAltitude          Xmp.exif.GPSAltitude
                       Exif.GPSInfo.GPSAltitudeRef       Xmp.exif.GPSAltitudeRef
Camera address                                           Xmp.iptcExt.LocationCreated
                                                         Xmp.iptc.Location               Iptc.Application2.SubLocation
                                                         Xmp.photoshop.City              Iptc.Application2.City
                                                         Xmp.photoshop.State             Iptc.Application2.ProvinceState
                                                         Xmp.photoshop.Country           Iptc.Application2.CountryName
                                                         Xmp.iptc.CountryCode            Iptc.Application2.CountryCode
Subject address                                          Xmp.iptcExt.LocationShown
=====================  ================================  ==============================  ==================

Secondary tags
--------------

Photini may read information from these tags and merge it with information from the primary tags.
These tags are deleted when the corresponding primary tags are saved.

=====================  ===============================  ==============================  ==================
Photini field          Exif tag                         XMP tag                         IPTC tag
=====================  ===============================  ==============================  ==================
Title / Object Name    Exif.Image.XPTitle                                               Iptc.Application2.Headline
Description / Caption  Exif.Image.XPComment             Xmp.tiff.ImageDescription
                       Exif.Image.XPSubject
                       Exif.Photo.UserComment
Keywords               Exif.Image.XPKeywords
Copyright                                               Xmp.tiff.Copyright
Creator / Artist       Exif.Image.XPAuthor              Xmp.tiff.Artist
Date / time Taken      Exif.Image.DateTimeOriginal      Xmp.exif.DateTimeOriginal
Date / time Digitised                                   Xmp.exif.DateTimeDigitized
Date / time Modified                                    Xmp.tiff.DateTime
Aperture               Exif.Image.FNumber               Xmp.exif.ApertureValue
                       Exif.Image.ApertureValue
                       Exif.Photo.ApertureValue
Focal length           Exif.Image.FocalLength
Lens model name        Exif.Canon.LensModel
                       Exif.OlympusEq.LensModel
Lens serial number     Exif.OlympusEq.LensSerialNumber
Lens specification     Exif.Image.LensInfo
                       Exif.CanonCs.Lens
                       Exif.Nikon3.Lens
=====================  ===============================  ==============================  ==================

Read only tags
--------------

Photini may read information from these tags and merge it with information from the primary tags.
These tags are not deleted when the corresponding primary tags are saved.

=====================  =========================  ================================  ==================
Photini field          Exif tag                   XMP tag                           IPTC tag
=====================  =========================  ================================  ==================
Date / time Taken                                 Xmp.video.DateUTC
Date / time Digitised                             Xmp.video.DateUTC
Date / time Modified                              Xmp.video.ModificationDate
Latitude, longitude                               Xmp.video.GPSCoordinates
Time zone offset[1]    Exif.Image.TimeZoneOffset
                       Exif.NikonWt.Timezone
=====================  =========================  ================================  ==================

[1] The time zone offset is not directly presented to the user.
It is applied to the Date / time Taken, Date / time Digitised and Date / time Modified fields if no other time zone information is available.

Delete only tags
----------------

These tags are not read but are deleted when the corresponding primary tags are saved.

=====================  =========================  ================================  ==================
Photini field          Exif tag                   XMP tag                           IPTC tag
=====================  =========================  ================================  ==================
Lens model name        Exif.CanonCs.LensType
Lens specification     Exif.CanonCs.ShortFocal
                       Exif.CanonCs.MaxAperture
                       Exif.CanonCs.MinAperture
=====================  =========================  ================================  ==================
