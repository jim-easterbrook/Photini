.. This is part of the Photini documentation.
   Copyright (C)  2012-21  Jim Easterbrook.
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
Rating                                                   Xmp.xmp.Rating
Copyright              Exif.Image.Copyright              Xmp.dc.rights                   Iptc.Application2.Copyright
Creator / Artist       Exif.Image.Artist                 Xmp.dc.creator                  Iptc.Application2.Byline
Date / time Taken      Exif.Photo.DateTimeOriginal       Xmp.photoshop.DateCreated       Iptc.Application2.DateCreated
                       Exif.Photo.SubSecTimeOriginal                                     Iptc.Application2.TimeCreated
Date / time Digitised  Exif.Photo.DateTimeDigitized      Xmp.xmp.CreateDate              Iptc.Application2.DigitizationDate
                       Exif.Photo.SubSecTimeDigitized                                    Iptc.Application2.DigitizationTime
Date / time Modified   Exif.Image.DateTime               Xmp.xmp.ModifyDate
                       Exif.Photo.SubSecTime
Orientation            Exif.Image.Orientation
Camera maker name      Exif.Image.Make
Camera model name      Exif.Image.Model
Camera serial number   Exif.Photo.BodySerialNumber
Lens maker name        Exif.Photo.LensMake
Lens model name        Exif.Photo.LensModel
Lens serial number     Exif.Photo.LensSerialNumber
Lens specification     Exif.Photo.LensSpecification
Focal length           Exif.Photo.FocalLength
35mm equiv             Exif.Photo.FocalLengthIn35mmFilm
Aperture               Exif.Photo.FNumber
Latitude, longitude    Exif.GPSInfo.GPSLatitude
                       Exif.GPSInfo.GPSLatitudeRef
                       Exif.GPSInfo.GPSLongitude
                       Exif.GPSInfo.GPSLongitudeRef
Altitude               Exif.GPSInfo.GPSAltitude
                       Exif.GPSInfo.GPSAltitudeRef
Camera address                                           Xmp.iptcExt.LocationCreated
                                                         Xmp.iptc.Location               Iptc.Application2.SubLocation
                                                         Xmp.photoshop.City              Iptc.Application2.City
                                                         Xmp.photoshop.State             Iptc.Application2.ProvinceState
                                                         Xmp.photoshop.Country           Iptc.Application2.CountryName
                                                         Xmp.iptc.CountryCode            Iptc.Application2.CountryCode
Subject address                                          Xmp.iptcExt.LocationShown
Thumbnail image        Exif.Thumbnail.Compression
                       Exif.Thumbnail.ImageWidth
                       Exif.Thumbnail.ImageLength
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
Rating                 Exif.Image.Rating                Xmp.MicrosoftPhoto.Rating
                       Exif.Image.RatingPercent
Copyright                                               Xmp.tiff.Copyright
Creator / Artist       Exif.Image.XPAuthor              Xmp.tiff.Artist
Date / time Taken      Exif.Image.DateTimeOriginal      Xmp.exif.DateTimeOriginal
Date / time Digitised                                   Xmp.exif.DateTimeDigitized
Date / time Modified                                    Xmp.tiff.DateTime
Lens model name                                         Xmp.aux.Lens
Lens specification     Exif.Image.LensInfo
Focal length           Exif.Image.FocalLength
Aperture               Exif.Image.FNumber               Xmp.exif.ApertureValue
                       Exif.Image.ApertureValue
                       Exif.Photo.ApertureValue
Thumbnail image                                         Xmp.xmp.Thumbnails[n]/xapGImg
=====================  ===============================  ==============================  ==================

XMP only tags
-------------

These tags are read if present, but are only written if the file format doesn't support Exif, e.g. an XMP sidecar.

=====================  ========  ================================  ==================
Photini field          Exif tag  XMP tag                           IPTC tag
=====================  ========  ================================  ==================
Orientation                      Xmp.tiff.Orientation
Lens maker name                  Xmp.exifEX.LensMake
Lens model name                  Xmp.exifEX.LensModel
Lens serial number               Xmp.exifEX.LensSerialNumber
Lens specification               Xmp.exifEX.LensSpecification
Focal length                     Xmp.exif.FocalLength
35mm equiv                       Xmp.exif.FocalLengthIn35mmFilm
Aperture                         Xmp.exif.FNumber
Latitude, longitude              Xmp.exif.GPSLatitude
                                 Xmp.exif.GPSLongitude
Altitude                         Xmp.exif.GPSAltitude
                                 Xmp.exif.GPSAltitudeRef
Thumbnail image                  Xmp.xmp.Thumbnails[n]/xmpGImg
=====================  ========  ================================  ==================

Read only tags
--------------

Photini may read information from these tags and merge it with information from the primary tags.
These tags are not deleted when the corresponding primary tags are saved.

=====================  ===============================  ================================  ==================
Photini field          Exif tag                         XMP tag                           IPTC tag
=====================  ===============================  ================================  ==================
Time zone offset[1]    Exif.Image.TimeZoneOffset
                       Exif.NikonWt.Timezone
Camera model name      Exif.Image.UniqueCameraModel
                       Exif.Canon.ModelID
                       Exif.OlympusEq.CameraType
                       Exif.Pentax.ModelID
Camera serial number   Exif.Image.CameraSerialNumber    Xmp.aux.SerialNumber
                       Exif.Canon.SerialNumber
                       Exif.Fujifilm.SerialNumber
                       Exif.Nikon3.SerialNumber
                       Exif.OlympusEq.SerialNumber
                       Exif.Pentax.SerialNumber
Lens model name        Exif.Canon.LensModel
                       Exif.CanonCs.LensType
                       Exif.OlympusEq.LensModel
Lens serial number     Exif.OlympusEq.LensSerialNumber
                       Exif.NikonLd1.LensIDNumber
                       Exif.NikonLd2.LensIDNumber
                       Exif.NikonLd3.LensIDNumber
Lens specification     Exif.CanonCs.Lens
                       Exif.Nikon3.Lens
Thumbnail image        Exif.SubImage*
=====================  ===============================  ================================  ==================

[1] The time zone offset is not directly presented to the user.
It is applied to the Date / time Taken, Date / time Digitised and Date / time Modified fields if no other time zone information is available.
