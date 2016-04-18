.. This is part of the Photini documentation.
   Copyright (C)  2012-16  Jim Easterbrook.
   See the file ../DOC_LICENSE.txt for copying condidions.

Tag reference
=============

This section lists the "mapping" from Photini's field names (such as "Title / Object Name") to the Exif / XMP / IPTC tags the data is stored in.
The tag names are those used by the Exiv2 library.
See http://exiv2.org/metadata.html for more detail.

As far as possible Photini follows the `Metadata Working Group <http://www.metadataworkinggroup.org/>`_ (MWG) `Guidelines for Handling Image Metadata <http://www.metadataworkinggroup.org/specs/>`_.
These specify the mapping between tags in Exif, XMP and IPTC, and say how software should reconcile any differences between information stored in equivalent tags.

Primary tags
------------

These tags are where Photini stores its metadata.
(IPTC tags are only used if they already exist in the file, in line with the MWG guidelines, unless the "write unconditionally" user setting is enabled.)

Note that "Title / Object Name" and "Keywords" are not stored in Exif.
You may prefer not to use these fields to ensure compatibility with software that only handles Exif.

=====================  ==================================  =========================  ==================
Photini field          Exif tag                            XMP tag                    IPTC tag
=====================  ==================================  =========================  ==================
Title / Object Name                                        Xmp.dc.title               Iptc.Application2.ObjectName
Description / Caption  Exif.Image.ImageDescription         Xmp.dc.description         Iptc.Application2.Caption
Keywords                                                   Xmp.dc.subject             Iptc.Application2.Keywords
Copyright              Exif.Image.Copyright                Xmp.dc.rights              Iptc.Application2.Copyright
Creator / Artist       Exif.Image.Artist                   Xmp.dc.creator             Iptc.Application2.Byline
Date / time Taken      | Exif.Photo.DateTimeOriginal       Xmp.photoshop.DateCreated  | Iptc.Application2.DateCreated
                       | Exif.Photo.SubSecTimeOriginal                                | Iptc.Application2.TimeCreated
Date / time Digitised  | Exif.Photo.DateTimeDigitized      Xmp.xmp.CreateDate         | Iptc.Application2.DigitizationDate
                       | Exif.Photo.SubSecTimeDigitized                               | Iptc.Application2.DigitizationTime
Date / time Modified   | Exif.Image.DateTime               Xmp.xmp.ModifyDate
                       | Exif.Photo.SubSecTime
Orientation            Exif.Image.Orientation
Aperture               Exif.Photo.FNumber
Focal length           | Exif.Photo.FocalLength
                       | Exif.Photo.FocalLengthIn35mmFilm
Lens maker name        Exif.Photo.LensMake
Lens model name        Exif.Photo.LensModel
Lens serial number     Exif.Photo.LensSerialNumber
Lens specification     Exif.Photo.LensSpecification
Latitude, longitude    | Exif.GPSInfo.GPSLatitude
                       | Exif.GPSInfo.GPSLatitudeRef
                       | Exif.GPSInfo.GPSLongitude
                       | Exif.GPSInfo.GPSLongitudeRef
=====================  ==================================  =========================  ==================

Secondary tags
--------------

Photini may read information from these tags and merge it with information from the primary tags.
These tags are deleted when the corresponding primary tags are saved.

=====================  ===========================  ================================  ==================
Photini field          Exif tag                     XMP tag                           IPTC tag
=====================  ===========================  ================================  ==================
Title / Object Name    Exif.Image.XPTitle                                             Iptc.Application2.Headline
Description / Caption  | Exif.Image.XPComment       Xmp.tiff.ImageDescription
                       | Exif.Image.XPSubject
Keywords               Exif.Image.XPKeywords
Copyright                                           Xmp.tiff.Copyright
Creator / Artist       Exif.Image.XPAuthor          Xmp.tiff.Artist
Date / time Taken      Exif.Image.DateTimeOriginal  Xmp.exif.DateTimeOriginal
Date / time Digitised                               Xmp.exif.DateTimeDigitized
Date / time Modified                                Xmp.tiff.DateTime
Orientation                                         Xmp.tiff.Orientation
Aperture               | Exif.Image.FNumber         | Xmp.exif.FNumber
                       | Exif.Image.ApertureValue   | Xmp.exif.ApertureValue
                       | Exif.Photo.ApertureValue
Focal length           Exif.Image.FocalLength       | Xmp.exif.FocalLength
                                                    | Xmp.exif.FocalLengthIn35mmFilm
Lens maker name
Lens model name        | Exif.Canon.LensModel
                       | Exif.CanonCs.LensType
Lens serial number
Lens specification     | Exif.CanonCs.Lens
                       | Exif.CanonCs.MaxAperture
                       | Exif.CanonCs.MinAperture
                       | Exif.CanonCs.ShortFocal
Latitude, longitude                                 | Xmp.exif.GPSLatitude
                                                    | Xmp.exif.GPSLongitude
=====================  ===========================  ================================  ==================

