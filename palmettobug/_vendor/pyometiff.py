# ruff: noqa
'''
This file "vendorizes" the following package: https://github.com/filippocastelli/pyometiff

(GPL-3 license, Copyright (c) 2021, Filippo Maria Castelli) 
    -- PalmettoBUG is also GPL-3 licensed -- see the LICENSE file for text
    -- Note that half of the file is also licensed under BSD-3, as it was derived from a different package by the author(s) of pyometiff
            the BSD-3 code is separated from the rest by a notice and a line of hashtags: ######################################################
            except for a __future__ import statement that was moved to the otp of this file (creates an error if not)


Changes (date: precise day uncertain, edits made January-March 2025):
-- Only focused on the functions that I use in PalmettoBUG (OMETIFFReader and OMETIFFWriter) -- remove anything not needed for that
-- Joined all files into one (this one!) --> remove relative imports
-- Removed unused and most duplicate imports    (ex: renamed as for etree to be consistently "et")
-- Removed typing output statement from some functions to make pylance happy
-- added copy of BSD-3 license to relevant code section
-- Move a __future__ import from the BSD-3 licensed section to the top of the file
-- replaced assert --> if not...raise    (or similar replacement)
-- add __all__ (for docs)

'''
# This file is part of the pyometiff library.

# pyometiff is distributed under the GNU General Public License v3.0 (GNU GPLv3),
# specific files are distributed under different licenses, please refer to the
# file header.

# Modification and redistribution is possible under the terms of the applied 
# license agreement.

# This software is distributed WITHOUT ANY WARRANTY.
# See the GNU General Public License v3.0 for further details.

# A copy of the GNU General Public License v3.0 should be included in pyometiff,
# if you didn't receive a copy, visit <http://www.gnu.org/licenses/>.

# Copyright (c) 2021, Filippo Maria Castelli


from __future__ import annotations # needed for python < 3.10    ### moved from top of BSD-3 licensed code section (__future__ calls must be at the top)

__all__ = []

from pathlib import Path
import pathlib
from lxml import etree as et
import tifffile
import numpy as np
import logging
from typing import Union

class OMETIFFReader:
    def __init__(self,
                 fpath: pathlib.Path,
                 imageseries: int = 0):

        self.fpath = Path(fpath)
        self.imageseries = imageseries

    def read(self) -> tuple[np.ndarray, dict, str]:
        self.array, self.omexml_string = self._open_tiff(self.fpath)
        self.metadata = self.parse_metadata(self.omexml_string)
        return self.array, self.metadata, self.omexml_string

    def write_xml(self):
        if not hasattr(self, "omexml_string"):
            _, _, _ = self.read()
        xml_fpath = self.fpath.parent.joinpath(self.fpath.stem + ".xml")
        tree = et.ElementTree(et.fromstring(self.omexml_string.encode("utf-8")))
        tree.write(str(xml_fpath), encoding="utf-8", method="xml", pretty_print=True)

    def parse_metadata(self, omexml_string):
        if omexml_string is None:
            logging.warning("File {} has no OME-XML tags!".format(str(self.fpath)))
            return None
        self.ox = OMEXML(omexml_string)
        metadata = self._get_metadata_template()
        metadata["Directory"] = str(self.fpath.parent)
        metadata["Filename"] = str(self.fpath.name)
        metadata["Extension"] = "ome.tiff"
        metadata["ImageType"] = "ometiff"
        metadata["AcquisitionDate"] = self.ox.image(self.imageseries).AcquisitionDate
        metadata["Name"] = self.ox.image(self.imageseries).Name

        # image dimensions
        metadata["SizeT"] = self.ox.image(self.imageseries).Pixels.SizeT
        metadata["SizeZ"] = self.ox.image(self.imageseries).Pixels.SizeZ
        metadata["SizeC"] = self.ox.image(self.imageseries).Pixels.SizeC
        metadata["SizeX"] = self.ox.image(self.imageseries).Pixels.SizeX
        metadata["SizeY"] = self.ox.image(self.imageseries).Pixels.SizeY

        # physical size
        metadata["PhysicalSizeX"] = self.ox.image(self.imageseries).Pixels.PhysicalSizeX
        metadata["PhysicalSizeY"] = self.ox.image(self.imageseries).Pixels.PhysicalSizeY
        metadata["PhysicalSizeZ"] = self.ox.image(self.imageseries).Pixels.PhysicalSizeZ

        # time increment
        metadata["TimeIncrement"] = self.ox.image(self.imageseries).Pixels.TimeIncrement
        metadata["TimeIncrementUnit"] = self.ox.image(self.imageseries).Pixels.TimeIncrementUnit

        # physical size unit
        metadata["PhysicalSizeXUnit"] = self.ox.image(
            self.imageseries
        ).Pixels.PhysicalSizeXUnit
        metadata["PhysicalSizeYUnit"] = self.ox.image(
            self.imageseries
        ).Pixels.PhysicalSizeYUnit
        metadata["PhysicalSizeZUnit"] = self.ox.image(
            self.imageseries
        ).Pixels.PhysicalSizeZUnit

        # number of image series
        metadata["TotalSeries"] = self.ox.get_image_count()
        metadata["Sizes BF"] = [
            metadata["TotalSeries"],
            metadata["SizeT"],
            metadata["SizeZ"],
            metadata["SizeC"],
            metadata["SizeY"],
            metadata["SizeX"],
        ]

        # get number of image series
        metadata["TotalSeries"] = self.ox.get_image_count()
        metadata["Sizes BF"] = [
            metadata["TotalSeries"],
            metadata["SizeT"],
            metadata["SizeZ"],
            metadata["SizeC"],
            metadata["SizeY"],
            metadata["SizeX"],
        ]

        # get dimension order
        metadata["DimOrder BF"] = self.ox.image(self.imageseries).Pixels.DimensionOrder

        # reverse the order to reflect later the array shape
        dim_order: list = metadata["DimOrder BF"]
        metadata["DimOrder BF Array"] = dim_order[::-1] # pylint: disable=unsubscriptable-object

        # DimOrder custom field
        metadata["DimOrder"] = metadata["DimOrder BF Array"]

        # get all image IDs
        for i in range(self.ox.get_image_count()):
            metadata["ImageIDs"].append(i)

        # get information about the instrument and objective
        try:
            metadata["InstrumentID"] = self.ox.instrument(self.imageseries).get_ID()
        except (KeyError, AttributeError, IndexError) as e:
            print("Key not found:", e)
            metadata["InstrumentID"] = None
        try:
            metadata["DetectorModel"] = self.ox.instrument(
                self.imageseries
            ).Detector.get_Model()
            metadata["DetectorID"] = self.ox.instrument(
                self.imageseries
            ).Detector.get_ID()
            metadata["DetectorType"] = self.ox.instrument(
                self.imageseries
            ).Detector.get_Type()
        except (KeyError, AttributeError, IndexError) as e:
            print("Key not found:", e)
            metadata["DetectorModel"] = None
            metadata["DetectorID"] = None
            metadata["DetectorType"] = None

        try:
            metadata["MicroscopeType"] = self.ox.instrument(
                self.imageseries
            ).Microscope.get_Type()
        except (KeyError, AttributeError, IndexError) as e:
            print("key not found", e)

        try:
            metadata["ObjNA"] = self.ox.instrument(
                self.imageseries
            ).Objective.get_LensNA()
            metadata["ObjID"] = self.ox.instrument(self.imageseries).Objective.get_ID()
            metadata["ObjMag"] = self.ox.instrument(
                self.imageseries
            ).Objective.get_NominalMagnification()
        except (KeyError, AttributeError, IndexError) as e:
            print("Key not found:", e)
            metadata["ObjNA"] = None
            metadata["ObjID"] = None
            metadata["ObjMag"] = None

        # get channel names
        try:
            metadata["Channels"] = self._parse_channels(metadata["SizeC"], self.ox, self.imageseries)
        except (KeyError, AttributeError, IndexError) as e:
            metadata["Channels"] = None
        
        # for c in range(metadata["SizeC"]):
        #     channel_names.append(
        #         self.ox.image(self.imageseries).Pixels.Channel(c).Name
        #     )

        #     self.ox.image(self.imageseries).Pixels.Channel(c).
        metadata = self._remove_none_or_empty_dict(metadata)
        return metadata

    @classmethod
    def _parse_channels(cls, sizeC, ox, imageseries):
        channels_dict = {}
        for c in range(sizeC):
            channel_obj = ox.image(imageseries).Pixels.Channel(c)
            channel_name = channel_obj.Name
            channel_dict = {}
            for attr in ["Name",
                         "ID",
                         "SamplesPerPixel",
                         "IlluminationType,",
                         "PinHoleSize",
                         "PinHoleSizeUnit",
                         "AcquisitionMode",
                         "ContrastMethod",
                         "ExcitationWavelength",
                         "ExcitationWavelengthUnit",
                         "EmissionWavelength",
                         "EmissionWavelengthUnit",
                         "Fluor",
                         "NDFilter",
                         "PockelCellSetting",
                         "Color"
                         ]:
                if hasattr(channel_obj, attr):
                    val = getattr(channel_obj, attr)
                    channel_dict[attr] = val
                channel_dict = cls._remove_none_or_empty_dict(channel_dict)
            channels_dict[channel_name] = channel_dict

        return channels_dict

    @staticmethod
    def _remove_none_or_empty_dict(dictionary):
        return {key: item for key, item in dictionary.items() if (item != []) and (item is not None)}

    @classmethod
    def _open_tiff(cls, fpath: pathlib.Path) -> tuple[np.ndarray, str]:
        with tifffile.TiffFile(str(fpath)) as tif:
            omexml_string = tif.ome_metadata
            array = tif.asarray()

        # array = cls._adjust_array_dims(array)
        return array, omexml_string

    # @staticmethod
    # def _adjust_array_dims(array, n_ch=1, n_t=1, n_z=1):
    #     if n_ch == 1:
    #         array = np.expand_dims(array, axis=-3)
    #     if n_z == 1:
    #         array = np.expand_dims(array, axis=-4)
    #     if n_t == 1:
    #         array = np.expand_dims(array, axis=-5)
    #     return array

    @staticmethod
    def _get_metadata_template() -> dict:
        metadata = {
            "Directory": None,
            "Filename": None,
            "Extension": None,
            "ImageType": None,
            "AcqDate": None,
            "TotalSeries": None,
            "SizeX": None,
            "SizeY": None,
            "SizeZ": 1,
            "SizeC": 1,
            "SizeT": 1,
            "SizeS": 1,
            "SizeB": 1,
            "SizeM": 1,
            "PhysicalSizeX": None,
            "PhysicalSizeXUnit": None,
            "PhysicalSizeY": None,
            "PhysicalSizeYUnit": None,
            "PhysicalSizeZ": None,
            "PhysicalSizeZUnit": None,
            "Sizes BF": None,
            "DimOrder BF": None,
            "DimOrder BF Array": None,
            "ObjNA": [],
            "ObjMag": [],
            "ObjID": [],
            "ObjName": [],
            "ObjImmersion": [],
            "TubelensMag": [],
            "ObjNominalMag": [],
            "DetectorModel": [],
            "DetectorName": [],
            "DetectorID": [],
            "DetectorType": [],
            "InstrumentID": [],
            "MicroscopeType": [],
            "Channels": [],
            # 'ChannelNames': [],
            # 'ChannelColors': [],
            "ImageIDs": [],
            # "NumPy.dtype": None,
        }

        return metadata

BYTE_BOUNDARY = 2 ** 32

class InvalidDimensionOrderingError(Exception):
    """exception for invalid dimensional ordering"""

    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.message = message

    def __str__(self):
        return self.message


class OMETIFFWriter:
    def __init__(
            self,
            fpath: Path,
            array: Union[np.ndarray, None],
            metadata: dict,
            overwrite: bool = False,
            dimension_order: str = "STZCYX",
            photometric: str = "minisblack",
            explicit_tiffdata: bool = False,
            compression: str = None,
            arr_shape: Union[list, tuple] = None,
            bigtiff: bool = False,
    ):
        """
        OMETIFFWriter class for writing OME-TIFF files.

        :param fpath: path to the file to be written
        :param array: array to be written
        :param metadata: dictionary containing the metadata to be written
        :param overwrite: if True, overwrite the file if it already exists
        :param dimension_order: dimension ordering of the array
        :param photometric: photometric interpretation of the array, "minisblack" or "miniswhite"
        :param explicit_tiffdata: if True, explicitly write the tiffdata tag, otherwise it is written automatically [DEBUG ONLY]
        :param compression: compression type, if None, no compression is used
        :param arr_shape: shape of the array, if None, it is inferred from the array
        :param bigtiff: if True, use bigtiff format. File sizes exceeding 4GB will automatically be written in bigtiff format
        """

        self.fpath = Path(fpath)
        self.array = array
        self.metadata = metadata
        self.overwrite = overwrite
        self.dimension_order = dimension_order
        self.photometric = photometric
        self.explicit_tiffdata = explicit_tiffdata
        self.compression = compression
        self.arr_shape = arr_shape
        self.use_bigtiff = bigtiff
        self.init_file()

    def init_file(self):
        self._array, self._dimension_order = self._adjust_dims(
            array=self.array,
            dimension_order=self.dimension_order,
            shape=self.arr_shape
        )
        self._ox = self.gen_meta()
        self._xml = self._ox.to_xml().encode()

    def write(self):
        self.write_stack(self._array, self._xml)

    def write_xml(self, xml_fpath: Path = None):
        if xml_fpath is None:
            xml_fpath = self.fpath.parent.joinpath(self.fpath.stem + ".xml")

        # overwrite if xml already exist
        if xml_fpath.exists():
                xml_fpath.unlink()

        tree = et.ElementTree(et.fromstring(self._xml))
        tree.write(str(xml_fpath),
                   encoding="utf-8",
                   method="xml",
                   pretty_print=True,
                   xml_declaration=True)

    @staticmethod
    def _should_use_bigtiff(array):
        if array is None:
            return False
        else:
            file_size = array.size * array.itemsize
            return file_size > BYTE_BOUNDARY

    def write_stack(self, array, xml_meta):
        should_use_bigtiff = self._should_use_bigtiff(array)

        use_bigtiff = self.use_bigtiff or should_use_bigtiff

        if should_use_bigtiff and (self.use_bigtiff is False):
            logging.warning("array size is larger than 4GB, using BigTIFF")

        with tifffile.TiffWriter(str(self.fpath), bigtiff=use_bigtiff) as tif:
            tif.write(
                array, description=xml_meta, photometric=self.photometric, metadata=None, compression=self.compression
            )

    def gen_meta(self):
        ox = OMEXML()
        ox.image().set_ID("Image:0")

        pixels = ox.image().Pixels

        # pixels.ome_uuid = ox.uuidStr
        pixels.set_ID("Pixels:0")

        # trying first to set all items
        error_keys = []
        metadata_dict_cpy = self.metadata.copy()

        exp_keys = ["Channels", "Name", "AcquisitionDate"]
        pop_expected_keys = {key: metadata_dict_cpy.pop(key, None) for key in exp_keys}

        # set image acquisitiondate
        acq_date = pop_expected_keys["AcquisitionDate"]
        acq_date = acq_date if acq_date is not None else xsd_now()
        ox.image().set_AcquisitionDate(acq_date)

        img_name = pop_expected_keys["Name"]
        img_name = img_name if img_name is not None else "pyometiff_exported"

        ox.image().set_Name(img_name)

        for key, item in metadata_dict_cpy.items():
            try:
                setattr(pixels, key, item)
            except AttributeError:
                error_keys.append(key)
                print("could not set key {} to {}".format(key, str(item)))

        if self._array is not None:
            shape = self._array.shape
        else:
            shape = self.arr_shape

        def _dim_or_1(dim):
            idx = self._dimension_order.find(dim)
            return 1 if idx == -1 else shape[idx]

        pixels.channel_count = _dim_or_1("C")
        pixels.set_SizeT(_dim_or_1("T"))
        pixels.set_SizeC(_dim_or_1("C"))
        pixels.set_SizeZ(_dim_or_1("Z"))
        pixels.set_SizeY(_dim_or_1("Y"))
        pixels.set_SizeX(_dim_or_1("X"))
        
        # time increment
        time_increment = pop_expected_keys.get("TimeIncrement", None)
        time_increment_unit = pop_expected_keys.get("TimeIncrementUnit", None)
        
        if time_increment is not None:
            pixels.set_TimeIncrement(time_increment)
        if time_increment_unit is not None:
            pixels.set_TimeIncrementUnit(time_increment_unit)

        # this is reversed of what dimensionality of the ometiff file is saved as
        pixels.set_DimensionOrder(self._dimension_order[::-1])

        # convert numpy dtype to a compatibile pixeltype
        if self._array is not None:
            dtype = self._array.dtype
        else:
            dtype = np.dtype("uint16")
        pixels.set_PixelType(get_pixel_type(dtype))

        if pop_expected_keys["Channels"] is not None:
            channels_dict = pop_expected_keys["Channels"]
            if not (len(channels_dict.keys()) == pixels.SizeC):
                print("Channel label count is different than channel count")
                raise Exception
            self._parse_channel_dict(pixels, channels_dict)
        else:
            for i in range(pixels.SizeC):
                pixels.Channel(i).set_ID("Channel:0:" + str(i))
                pixels.Channel(i).set_Name("C:" + str(i))

        pixels.populate_TiffData(explicit=self.explicit_tiffdata)

        return ox

    @staticmethod
    def _parse_channel_dict(pixels, channels_dict):
        channel_names = list(channels_dict.keys())
        channels_ignored_keys = {}
        for idx, channel_name in enumerate(channel_names):
            channel_dict = channels_dict[channel_name]
            pixels.Channel(idx).set_ID("Channel:0" + str(idx))
            pixels.Channel(idx).set_Name(channel_name)

            if "SamplesPerPixel" not in channel_dict:
                pixels.Channel(idx).set_SamplesPerPixel(1)

            channel_ignored_keys = []
            for channel_key, item in channel_dict.items():
                try:
                    setattr(pixels.Channel(idx), channel_key, item)
                except AttributeError:
                    channel_ignored_keys.append(channel_key)

            channels_ignored_keys[channel_name] = channel_ignored_keys

    @staticmethod
    def _adjust_dims(array=None, dimension_order="ZYX", shape=None):
        if array is not None:
            array_shape = array.shape
        else:
            array_shape = shape
        ndims = len(array_shape)

        if not (ndims in (3, 4, 5)):
            print("Expected a 3, 4, or 5-dimensional array")
            raise Exception

        # no strange dim names
        if not (all(d in "STCZYX" for d in dimension_order)):
            raise InvalidDimensionOrderingError(
                "Invalid dimension_order {}".format(dimension_order)
            )

        # ends in YX
        if dimension_order[-2:] != "YX":
            raise InvalidDimensionOrderingError(
                "the last two dimensions are expected to be YX, they are {} instead. Please transpose your data".format(
                    dimension_order[-2:]
                )
            )

        # starts in S
        if dimension_order.find("S") > 0:
            raise InvalidDimensionOrderingError(
                "S must be the leading dim in dimension_order {}".format(
                    dimension_order
                )
            )

        # enough dimensions
        if len(dimension_order) < ndims:
            raise InvalidDimensionOrderingError(
                "dimension_order {} must have at least as many dimensions as array shape {}".format(
                    dimension_order, array_shape
                )
            )

        # no letter appears more than once
        if len(set(dimension_order)) != len(dimension_order):
            raise InvalidDimensionOrderingError(
                "A letter appears more than once in dimension_order {}".format(
                    dimension_order
                )
            )

        # trim dimension order to match array
        # if array is [T,C,Z,Y,X], dimension_order STCZYX becomes TCZYX
        if len(dimension_order) > ndims:
            dimension_order = dimension_order[-ndims:]

        # expand 3D data to 5D
        if ndims == 3:
            # expand double
            if array is not None:
                array = np.expand_dims(array, axis=0)
                array = np.expand_dims(array, axis=0)
            else:
                shape.insert(0, 1)
                shape.insert(0, 1)

            # prepend either TC, TZ or CZ
            if dimension_order[0] == "T":
                dimension_order = "CZ" + dimension_order
            elif dimension_order[0] == "C":
                dimension_order = "TZ" + dimension_order
            elif dimension_order[0] == "Z":
                dimension_order = "TC" + dimension_order

        # if it's 4D expand to 5D
        elif ndims == 4:
            if array is not None:
                array = np.expand_dims(array, axis=0)
            else:
                shape.insert(0, 1)
            # prepend either T, C, or Z
            first2 = dimension_order[:2]
            if first2 == "TC" or first2 == "CT":
                dimension_order = "Z" + dimension_order
            elif first2 == "TZ" or first2 == "ZT":
                dimension_order = "C" + dimension_order
            elif first2 == "CZ" or first2 == "ZC":
                dimension_order = "T" + dimension_order

        return array, dimension_order
    

#######################################################################################################################################################
# Code after this point has a different header (licensed under BSD-3)


# pyometiff is distributed under the GNU General Public
# License v3.0, but this file is licensed under the more permissive BSD
# license.  See the accompanying file LICENSE for details.
#
# Copyright (c) 2021 Filippo Maria Castelli
# All rights reserved.

# This file is based on CellProfiler/python-bioformats
# https://github.com/CellProfiler/python-bioformats/blob/master/bioformats/omexml.py
# commit 802eb4b

# ORIGINAL LICENSE

# Python-bioformats is distributed under the GNU General Public
# License, but this file is licensed under the more permissive BSD
# license.  See the accompanying file LICENSE ('''see triple quote comment below -- BSD-3 text copied from github repository linked above''') for details.
#
# Copyright (c) 2009-2014 Broad Institute
# All rights reserved.
'''
Copyright (c) 2009-2013 Broad Institute
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.

    * Redistributions in binary form must reproduce the above
      copyright notice, this list of conditions and the following
      disclaimer in the documentation and/or other materials provided
      with the distribution.

    * Neither the name of the Massachusetts Institute of Technology
      nor the Broad Institute nor the names of its contributors may be
      used to endorse or promote products derived from this software
      without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL MASSACHUSETTS
INSTITUTE OF TECHNOLOGY OR THE BROAD INSTITUTE BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE
GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''

"""omexml.py read and write OME xml
"""

import datetime
import logging
from functools import reduce
import re
import uuid
from xml.etree import ElementTree

from io import StringIO
import numpy as np

uenc = 'unicode'

logger = logging.getLogger(__file__)


def xsd_now():
    """Return the current time in xsd:dateTime format"""
    return datetime.datetime.now().isoformat()


#
# The namespaces
#
NS_BINARY_FILE = "http://www.openmicroscopy.org/Schemas/BinaryFile/2013-06"
NS_ORIGINAL_METADATA = "openmicroscopy.org/OriginalMetadata"
NS_DEFAULT = "http://www.openmicroscopy.org/Schemas/{ns_key}/2013-06"
NS_RE = r"http://www.openmicroscopy.org/Schemas/(?P<ns_key>.*)/[0-9/-]"

default_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Warning: this comment is an OME-XML metadata block, which contains
crucial dimensional parameters and other important metadata. Please edit
cautiously (if at all), and back up the original data before doing so.
For more information, see the OME-TIFF documentation:
https://docs.openmicroscopy.org/latest/ome-model/ome-tiff/ -->
<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.openmicroscopy.org/Schemas/OME/2016-06 http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd">
    <Image ID="Image:0" Name="default.png">
        <AcquisitionDate>{xsd_now()}</AcquisitionDate>
        <Pixels BigEndian="false"
                DimensionOrder="XYCZT"
                ID="Pixels:0"
                Interleaved="false"
                SizeC="1"
                SizeT="1"
                SizeX="512"
                SizeY="512"
                SizeZ="1"
                Type="uint8">
            <Channel ID="Channel:0:0" SamplesPerPixel="1">
                <LightPath/>
            </Channel>
        </Pixels>
    </Image>
</OME>"""

#
# These are the OME-XML pixel types - not all supported by subimager
#
PT_INT8 = "int8"
PT_INT16 = "int16"
PT_INT32 = "int32"
PT_UINT8 = "uint8"
PT_UINT16 = "uint16"
PT_UINT32 = "uint32"
PT_FLOAT = "float"
PT_BIT = "bit"
PT_DOUBLE = "double"
PT_COMPLEX = "complex"
PT_DOUBLECOMPLEX = "double-complex"

ometypedict = {
    np.dtype(np.int8): PT_INT8,
    np.dtype(np.int16): PT_INT16,
    np.dtype(np.int32): PT_INT32,
    np.dtype(np.uint8): PT_UINT8,
    np.dtype(np.uint16): PT_UINT16,
    np.dtype(np.uint32): PT_UINT32,
    np.dtype(np.float32): PT_FLOAT,
    np.dtype(np.float64): PT_DOUBLE,
    np.dtype(np.complex64): PT_COMPLEX,
    np.dtype(np.complex128): PT_DOUBLECOMPLEX
}


def get_pixel_type(npdtype):
    ptype = ometypedict.get(npdtype)
    if ptype is None:
        raise ValueError('OMEXML get_pixel_type unknown type: ' + npdtype.name)
    return ptype


#
# The allowed dimension types
#
DO_XYZCT = "XYZCT"
DO_XYZTC = "XYZTC"
DO_XYCTZ = "XYCTZ"
DO_XYCZT = "XYCZT"
DO_XYTCZ = "XYTCZ"
DO_XYTZC = "XYTZC"
#
# Original metadata corresponding to TIFF tags
# The text for these can be found in
# loci.formats.in.BaseTiffReader.initStandardMetadata
#
"""IFD # 254"""
OM_NEW_SUBFILE_TYPE = "NewSubfileType"
"""IFD # 256"""
OM_IMAGE_WIDTH = "ImageWidth"
"""IFD # 257"""
OM_IMAGE_LENGTH = "ImageLength"
"""IFD # 258"""
OM_BITS_PER_SAMPLE = "BitsPerSample"

"""IFD # 262"""
OM_PHOTOMETRIC_INTERPRETATION = "PhotometricInterpretation"
PI_WHITE_IS_ZERO = "WhiteIsZero"
PI_BLACK_IS_ZERO = "BlackIsZero"
PI_RGB = "RGB"
PI_RGB_PALETTE = "Palette"
PI_TRANSPARENCY_MASK = "Transparency Mask"
PI_CMYK = "CMYK"
PI_Y_CB_CR = "YCbCr"
PI_CIE_LAB = "CIELAB"
PI_CFA_ARRAY = "Color Filter Array"

"""BioFormats infers the image type from the photometric interpretation"""
OM_METADATA_PHOTOMETRIC_INTERPRETATION = "MetaDataPhotometricInterpretation"
MPI_RGB = "RGB"
MPI_MONOCHROME = "Monochrome"
MPI_CMYK = "CMYK"

"""IFD # 263"""
OM_THRESHHOLDING = "Threshholding"  # (sic)
"""IFD # 264 (but can be 265 if the orientation = 8)"""
OM_CELL_WIDTH = "CellWidth"
"""IFD # 265"""
OM_CELL_LENGTH = "CellLength"
"""IFD # 266"""
OM_FILL_ORDER = "FillOrder"
"""IFD # 279"""
OM_DOCUMENT_NAME = "Document Name"
"""IFD # 271"""
OM_MAKE = "Make"
"""IFD # 272"""
OM_MODEL = "Model"
"""IFD # 274"""
OM_ORIENTATION = "Orientation"
"""IFD # 277"""
OM_SAMPLES_PER_PIXEL = "SamplesPerPixel"
"""IFD # 280"""
OM_MIN_SAMPLE_VALUE = "MinSampleValue"
"""IFD # 281"""
OM_MAX_SAMPLE_VALUE = "MaxSampleValue"
"""IFD # 282"""
OM_X_RESOLUTION = "XResolution"
"""IFD # 283"""
OM_Y_RESOLUTION = "YResolution"
"""IFD # 284"""
OM_PLANAR_CONFIGURATION = "PlanarConfiguration"
PC_CHUNKY = "Chunky"
PC_PLANAR = "Planar"

"""IFD # 286"""
OM_X_POSITION = "XPosition"
"""IFD # 287"""
OM_Y_POSITION = "YPosition"
"""IFD # 288"""
OM_FREE_OFFSETS = "FreeOffsets"
"""IFD # 289"""
OM_FREE_BYTECOUNTS = "FreeByteCounts"
"""IFD # 290"""
OM_GRAY_RESPONSE_UNIT = "GrayResponseUnit"
"""IFD # 291"""
OM_GRAY_RESPONSE_CURVE = "GrayResponseCurve"
"""IFD # 292"""
OM_T4_OPTIONS = "T4Options"
"""IFD # 293"""
OM_T6_OPTIONS = "T6Options"
"""IFD # 296"""
OM_RESOLUTION_UNIT = "ResolutionUnit"
"""IFD # 297"""
OM_PAGE_NUMBER = "PageNumber"
"""IFD # 301"""
OM_TRANSFER_FUNCTION = "TransferFunction"

"""IFD # 305"""
OM_SOFTWARE = "Software"
"""IFD # 306"""
OM_DATE_TIME = "DateTime"
"""IFD # 315"""
OM_ARTIST = "Artist"
"""IFD # 316"""
OM_HOST_COMPUTER = "HostComputer"
"""IFD # 317"""
OM_PREDICTOR = "Predictor"
"""IFD # 318"""
OM_WHITE_POINT = "WhitePoint"
"""IFD # 322"""
OM_TILE_WIDTH = "TileWidth"
"""IFD # 323"""
OM_TILE_LENGTH = "TileLength"
"""IFD # 324"""
OM_TILE_OFFSETS = "TileOffsets"
"""IFD # 325"""
OM_TILE_BYTE_COUNT = "TileByteCount"
"""IFD # 332"""
OM_INK_SET = "InkSet"
"""IFD # 33432"""
OM_COPYRIGHT = "Copyright"
#
# Well row/column naming conventions
#
NC_LETTER = "letter"
NC_NUMBER = "number"


def page_name_original_metadata(index: int) -> str:
    """Get the key name for the page name metadata data for the indexed tiff page

    These are TIFF IFD #'s 285+

    index - zero-based index of the page
    """
    return "PageName #%d" % index


def get_text(node: ElementTree.Element) -> str:
    """Get the contents of text nodes in a parent node"""
    return node.text


def set_text(node: ElementTree.Element, text: str) -> None:
    """Set the text of a parent"""
    node.text = text


def get_qualified_name(namespace: str, tag_name: str) -> str:
    """Return the qualified name for a given namespace and tag name

    This is the ElementTree representation of a qualified name
    """
    return "{%s}%s" % (namespace, tag_name)


def split_qn(_qualified_name: str):
    """Split a qualified tag name or return None if namespace not present"""
    m = re.match('{(.*)}(.*)', _qualified_name)
    return m.group(1), m.group(2) if m else None


def get_namespaces(node: ElementTree.Element) -> dict[str, str]:
    """Get top-level XML namespaces from a node."""
    ns_lib = {'ome': None, 'sa': None, 'spw': None}
    for child in node.iter():
        ns = split_qn(child.tag)[0]
        match = re.match(NS_RE, ns)
        if match:
            ns_key = match.group('ns_key').lower()
            ns_lib[ns_key] = ns
    return ns_lib


def get_float_attr(node: ElementTree.Element, attribute: str) -> float | None:
    """Cast an element attribute to a float or return None if not present"""
    attr = node.get(attribute)
    return None if attr is None else float(attr)


def get_int_attr(node: ElementTree.ElementTree, attribute: str) -> int | None:
    """Cast an element attribute to an int or return None if not present"""
    attr = node.get(attribute)
    return None if attr is None else int(attr)


def make_text_node(parent: ElementTree.Element, namespace: str, tag_name: str, text: str) -> None:
    """Either make a new node and add the given text or replace the text

    parent - the parent node to the node to be created or found
    namespace - the namespace of the node's qualified name
    tag_name - the tag name of  the node's qualified name
    text - the text to be inserted
    """
    qname = get_qualified_name(namespace, tag_name)
    node = parent.find(qname)
    if node is None:
        node = ElementTree.SubElement(parent, qname)
    set_text(node, text)


class OMEXML(object):
    """Reads and writes OME-XML with methods to get and set it.

    The OMEXML class has four main purposes: to parse OME-XML, to output
    OME-XML, to provide a structured mechanism for inspecting OME-XML and to
    let the caller create and modify OME-XML.

    There are two ways to invoke the constructor. If you supply XML as a string
    or unicode string, the constructor will parse it and will use it as the
    base for any inspection and modification. If you don't supply XML, you'll
    get a bland OME-XML object which has a one-channel image. You can modify
    it programatically and get the modified OME-XML back out by calling to_xml.

    There are two ways to get at the XML. The arduous way is to get the
    root_node of the DOM and explore it yourself using the DOM API
    (http://docs.python.org/library/xml.dom.html#module-xml.dom). The easy way,
    where it's supported is to use properties on OMEXML and on some of its
    derived objects. For instance:

    >>> o = OMEXML()
    >>> print o.image().AcquisitionDate

    will get you the date that image # 0 was acquired.

    >>> o = OMEXML()
    >>> o.image().Name = "MyImage"

    will set the image name to "MyImage".

    You can add and remove objects using the "count" properties. Each of these
    handles hooking up and removing orphaned elements for you and should be
    less error prone than creating orphaned elements and attaching them. For
    instance, to create a three-color image:

    >>> o = OMEXML()
    >>> o.image().Pixels.channel_count = 3
    >>> o.image().Pixels.Channel(0).Name = "Red"
    >>> o.image().Pixels.Channel(1).Name = "Green"
    >>> o.image().Pixels.Channel(2).Name = "Blue"

    See the `OME-XML schema documentation <http://git.openmicroscopy.org/src/develop/components/specification/Documentation/Generated/OME-2011-06/ome.html>`_.

    """

    def __init__(self, xml: str | None = None) -> None:
        if xml is None:
            xml = default_xml
        if isinstance(xml, str):
            xml = xml.encode("utf-8")
        try:
            self.dom = ElementTree.ElementTree(ElementTree.fromstring(xml))
        except UnicodeEncodeError:
            xml = xml.encode("utf-8")
            self.dom = ElementTree.ElementTree(ElementTree.fromstring(xml))
        # determine OME namespaces
        self.namespaces = get_namespaces(self.dom.getroot())
        if self.namespaces['ome'] is None:
            raise Exception("Error: String not in OME-XML format")

        # # adapted from AICSIMAGEIO
        # omeElem = self.dom
        # if not omeElem.get("UUID"):
        #     omeElem.set('UUID', 'urn:uuid:'+str(uuid.uuid4()))
        # self.uuidStr = omeElem.get('UUID')

    def __str__(self) -> str:
        #
        # need to register the ome namespace because BioFormats expects
        # that namespace to be the default or to be explicitly named "ome"
        #
        for ns_key in ["ome", "sa", "spw"]:
            ns = self.namespaces.get(ns_key) or NS_DEFAULT.format(ns_key=ns_key)
            ElementTree.register_namespace(ns_key, ns)
        ElementTree.register_namespace("om", NS_ORIGINAL_METADATA)
        result = StringIO()
        ElementTree.ElementTree(self.root_node).write(result,
                                                      xml_declaration=True,
                                                      encoding=uenc,
                                                      method="xml")
        return result.getvalue()

    def to_xml(self, indent: str ="\t", newline: str ="\n", encoding: str =uenc) -> str:
        return str(self)

    def get_ns(self, key: str) -> str:
        return self.namespaces[key]

    @property
    def root_node(self) -> ElementTree.Element:
        return self.dom.getroot()

    def get_image_count(self) -> int:
        """The number of images (= series) specified by the XML"""
        return len(self.root_node.findall(get_qualified_name(self.namespaces['ome'], "Image")))

    def set_image_count(self, value: int) -> None:
        """Add or remove image nodes as needed"""
        if not (value > 0):
            raise Exception
        root = self.root_node
        if self.image_count > value:
            image_nodes = root.find(get_qualified_name(self.namespaces['ome'], "Image"))
            for image_node in image_nodes[value:]:
                root.remove(image_node)
        while self.image_count < value:
            new_image = self.Image(ElementTree.SubElement(root, get_qualified_name(self.namespaces['ome'], "Image")))
            new_image.ID = str(uuid.uuid4())
            new_image.Name = "default.png"
            new_image.AcquisitionDate = xsd_now()
            new_pixels = self.Pixels(
                ElementTree.SubElement(new_image.node, get_qualified_name(self.namespaces['ome'], "Pixels")))
            new_pixels.ID = str(uuid.uuid4())
            new_pixels.DimensionOrder = DO_XYCTZ
            new_pixels.PixelType = PT_UINT8
            new_pixels.SizeC = 1
            new_pixels.SizeT = 1
            new_pixels.SizeX = 512
            new_pixels.SizeY = 512
            new_pixels.SizeZ = 1
            new_channel = self.Channel(
                ElementTree.SubElement(new_pixels.node, get_qualified_name(self.namespaces['ome'], "Channel")))
            new_channel.ID = "Channel%d:0" % self.image_count
            new_channel.Name = new_channel.ID
            new_channel.SamplesPerPixel = 1

    image_count = property(get_image_count, set_image_count)

    @property
    def plates(self) -> "PlatesDucktype":
        return self.PlatesDucktype(self.root_node)

    @property
    def structured_annotations(self) -> "StructuredAnnotations":
        """Return the structured annotations container

        returns a wrapping of OME/StructuredAnnotations. It creates
        the element if it doesn't exist.
        """
        node = self.root_node.find(get_qualified_name(self.namespaces['sa'], "StructuredAnnotations"))
        if node is None:
            node = ElementTree.SubElement(
                self.root_node, get_qualified_name(self.namespaces['sa'], "StructuredAnnotations"))
        return self.StructuredAnnotations(node)

    class Image(object):
        """Representation of the OME/Image element"""

        def __init__(self, node: ElementTree.Element) -> None:
            """Initialize with the DOM Image node"""
            self.node = node
            self.namespaces = get_namespaces(self.node)

        def get_ID(self) -> str:
            return self.node.get("ID")

        def set_ID(self, value: str) -> None:
            self.node.set("ID", value)

        ID = property(get_ID, set_ID)

        def get_Name(self) -> str:
            return self.node.get("Name")

        def set_Name(self, value: str) -> None:
            self.node.set("Name", value)

        Name = property(get_Name, set_Name)

        def get_AcquisitionDate(self) -> str:
            """The date in ISO-8601 format"""
            acquired_date = self.node.find(get_qualified_name(self.namespaces["ome"], "AcquisitionDate"))
            if acquired_date is None:
                return None
            return get_text(acquired_date)

        def set_AcquisitionDate(self, date: str) -> None:
            acquired_date = self.node.find(get_qualified_name(self.namespaces["ome"], "AcquisitionDate"))
            if acquired_date is None:
                acquired_date = ElementTree.SubElement(
                    self.node, get_qualified_name(self.namespaces["ome"], "AcquisitionDate"))
            set_text(acquired_date, date)

        AcquisitionDate = property(get_AcquisitionDate, set_AcquisitionDate)

        @property
        def Pixels(self):
            """The OME/Image/Pixels element."""
            return OMEXML.Pixels(self.node.find(get_qualified_name(self.namespaces['ome'], "Pixels")))

        def roiref(self, index: int = 0) -> "OMEXML.ROIRef":
            """The OME/Image/ROIRef element"""
            return OMEXML.ROIRef(self.node.findall(get_qualified_name(self.namespaces['ome'], "ROIRef"))[index])

        def get_roiref_count(self) -> int:
            return len(self.node.findall(get_qualified_name(self.namespaces['ome'], "ROIRef")))

        def set_roiref_count(self, value: int) -> None:
            """Add or remove roirefs as needed"""
            if not (value > 0):
                raise Exception
            if self.roiref_count > value:
                roiref_nodes = self.node.find(get_qualified_name(self.namespaces['ome'], "ROIRef"))
                for roiref_node in roiref_nodes[value:]:
                    self.node.remove(roiref_node)
            while self.roiref_count < value:
                iteration = self.roiref_count - 1
                new_roiref = OMEXML.ROIRef(ElementTree.SubElement(self.node, get_qualified_name(self.namespaces['ome'], "ROIRef")))
                new_roiref.set_ID(value=iteration)

        roiref_count = property(get_roiref_count, set_roiref_count)

    def image(self, index: int = 0) -> Image:
        """Return an image node by index"""
        return self.Image(self.root_node.findall(get_qualified_name(self.namespaces['ome'], "Image"))[index])

    class Channel(object):
        """The OME/Image/Pixels/Channel element"""

        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.namespaces = get_namespaces(node)

        def get_ID(self) -> str:
            return self.node.get("ID")

        def set_ID(self, value: str) -> None:
            self.node.set("ID", value)

        ID = property(get_ID, set_ID)

        def get_Name(self) -> str:
            return self.node.get("Name")

        def set_Name(self, value: str) -> None:
            self.node.set("Name", value)

        Name = property(get_Name, set_Name)

        def get_SamplesPerPixel(self) -> int:
            return get_int_attr(self.node, "SamplesPerPixel")

        def set_SamplesPerPixel(self, value) -> None:
            self.node.set("SamplesPerPixel", str(value))

        SamplesPerPixel = property(get_SamplesPerPixel, set_SamplesPerPixel)

        # IllumationType
        def get_IlluminationType(self) -> str:
            return self.node.get("IlluminationType")

        def set_IlluminationType(self, value) -> None:
            self.node.set("IlluminationType", value)

        IlluminationType = property(get_IlluminationType, set_IlluminationType)

        # PinHoleSize
        def get_PinHoleSize(self) -> float:
            return get_float_attr(self.node, "PinHoleSize")

        def set_PinHoleSize(self, value) -> None:
            self.node.set("PinHoleSize", str(value))

        PinHoleSize = property(get_PinHoleSize, set_PinHoleSize)

        # PinHoleSizeUnit
        def get_PinHoleSizeUnit(self) -> str:
            return self.node.get("PinHoleSizeUnit")

        def set_PinHoleSizeUnit(self, value) -> None:
            self.node.set("PinHoleSizeUnit", value)

        PinHoleSizeUnit = property(get_PinHoleSizeUnit, set_PinHoleSizeUnit)

        # ContrastMethod
        def get_ContrastMethod(self) -> str:
            return self.node.get("ContrastMethod")

        def set_ContrastMethod(self, value: str) -> None:
            self.node.set("ContrastMethod", value)

        ContrastMethod = property(get_ContrastMethod, set_ContrastMethod)

        # ExcitationWavelength
        def get_ExcitationWavelength(self) -> float:
            return get_float_attr(self.node, "ExcitationWavelength")

        def set_ExcitationWavelength(self, value: float) -> None:
            self.node.set("ExcitationWavelength", str(value))

        ExcitationWavelength = property(get_ExcitationWavelength, set_ExcitationWavelength)

        # ExcitationWavelengthUnit
        def get_ExcitationWavelengthUnit(self) -> str:
            return self.node.get("ExcitationWavelengthUnit")

        def set_ExcitationWavelengthUnit(self, value: str) -> None:
            self.node.set("ExcitationWavelengthUnit", value)

        ExcitationWavelengthUnit = property(get_ExcitationWavelengthUnit, set_ExcitationWavelengthUnit)

        # EmissionWavelength
        def get_EmissionWavelength(self) -> float:
            return get_float_attr(self.node, "EmissionWavelength")

        def set_EmissionWavelength(self, value) -> None:
            self.node.set("EmissionWavelength", str(value))

        EmissionWavelength = property(get_EmissionWavelength, set_EmissionWavelength)

        # EmissionWavelengthUnit
        def get_EmissionWavelengthUnit(self) -> str:
            return self.node.get("EmissionWavelengthUnit")

        def set_EmissionWavelengthUnit(self, value: str) -> None:
            self.node.set("EmissionWavelengthUnit", value)

        EmissionWavelengthUnit = property(get_EmissionWavelengthUnit, set_EmissionWavelengthUnit)

        # Fluor
        def get_Fluor(self) -> str:
            return self.node.get("Fluor")

        def set_Fluor(self, value: str) -> None:
            self.node.set("Fluor", value)

        Fluor = property(get_Fluor, set_Fluor)

        # NDFilter
        def get_NDFilter(self) -> str:
            return self.node.get("NDFilter")

        def set_NDFilter(self, value: str) -> None:
            self.node.set("NDFilter", value)

        NDFilter = property(get_NDFilter, set_NDFilter)

        # PockelCellSetting
        def get_PockelCellSetting(self) -> str:
            return self.node.get("PockelCellSetting")

        def set_PockelCellSetting(self, value: str) -> None:
            self.node.set("PockelCellSetting", value)

        PockelCellSetting = property(get_PockelCellSetting, set_PockelCellSetting)

        # Color
        def get_Color(self) -> str:
            return self.node.get("Color")

        def set_Color(self, value: str) -> None:
            self.node.set("Color", value)

        Color = property(get_Color, set_Color)

    # ---------------------
    # The following section is from the Allen Institute for Cell Science version of this file
    # which can be found at https://github.com/AllenCellModeling/aicsimageio/blob/master/aicsimageio/vendor/omexml.py
    class TiffData(object):
        """The OME/Image/Pixels/TiffData element
        <TiffData FirstC="0" FirstT="0" FirstZ="0" IFD="0" PlaneCount="1">
            <UUID FileName="img40_1.ome.tif">urn:uuid:ef8af211-b6c1-44d4-97de-daca46f16346</UUID>
        </TiffData>
        For our purposes, there will be one TiffData per 2-dimensional image plane.
        """

        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.ns = get_namespaces(self.node)

        def get_FirstZ(self) -> int:
            """The Z index of the plane"""
            return get_int_attr(self.node, "FirstZ")

        def set_FirstZ(self, value: int) -> None:
            self.node.set("FirstZ", str(value))

        FirstZ = property(get_FirstZ, set_FirstZ)

        def get_FirstC(self) -> int:
            """The channel index of the plane"""
            return get_int_attr(self.node, "FirstC")

        def set_FirstC(self, value: int) -> None:
            self.node.set("FirstC", str(value))

        FirstC = property(get_FirstC, set_FirstC)

        def get_FirstT(self) -> int:
            """The T index of the plane"""
            return get_int_attr(self.node, "FirstT")

        def set_FirstT(self, value: int) -> None:
            self.node.set("FirstT", str(value))

        FirstT = property(get_FirstT, set_FirstT)

        def get_IFD(self) -> int:
            """plane index within tiff file"""
            return get_int_attr(self.node, "IFD")

        def set_IFD(self, value: int) -> None:
            self.node.set("IFD", str(value))

        IFD = property(get_IFD, set_IFD)

        def get_PlaneCount(self) -> int:
            """How many planes in this TiffData. Should always be 1"""
            return get_int_attr(self.node, "PlaneCount")

        def set_PlaneCount(self, value: int) -> None:
            self.node.set("PlaneCount", str(value))

        PlaneCount = property(get_PlaneCount, set_PlaneCount)

    class Plane(object):
        """The OME/Image/Pixels/Plane element

        The Plane element represents one 2-dimensional image plane. It
        has the Z, C and T indices of the plane and optionally has the
        X, Y, Z, exposure time and a relative time delta.
        """

        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.ns = get_namespaces(self.node)

        def get_TheZ(self) -> int:
            """The Z index of the plane"""
            return get_int_attr(self.node, "TheZ")

        def set_TheZ(self, value: int) -> None:
            self.node.set("TheZ", str(value))

        TheZ = property(get_TheZ, set_TheZ)

        def get_TheC(self) -> int:
            """The channel index of the plane"""
            return get_int_attr(self.node, "TheC")

        def set_TheC(self, value: int) -> None:
            self.node.set("TheC", str(value))

        TheC = property(get_TheC, set_TheC)

        def get_TheT(self):
            """The T index of the plane"""
            return get_int_attr(self.node, "TheT")

        def set_TheT(self, value):
            self.node.set("TheT", str(value))

        TheT = property(get_TheT, set_TheT)

        def get_DeltaT(self) -> float:
            """# of seconds since the beginning of the experiment"""
            return get_float_attr(self.node, "DeltaT")

        def set_DeltaT(self, value: float) -> None:
            self.node.set("DeltaT", str(value))

        DeltaT = property(get_DeltaT, set_DeltaT)

        def get_ExposureTime(self) -> float:
            exposure_time = self.node.get("ExposureTime")
            if exposure_time is not None:
                return float(exposure_time)
            return None

        def set_ExposureTime(self, value: float) -> None:
            """Units are seconds. Length of the exposure"""
            self.node.set("ExposureTime", str(value))

        ExposureTime = property(get_ExposureTime, set_ExposureTime)

        def get_PositionX(self) -> float:
            """X position of stage"""
            position_x = self.node.get("PositionX")
            if position_x is not None:
                return float(position_x)
            return None

        def set_PositionX(self, value: float) -> None:
            self.node.set("PositionX", str(value))

        PositionX = property(get_PositionX, set_PositionX)

        def get_PositionY(self) -> float:
            """Y position of stage"""
            return get_float_attr(self.node, "PositionY")

        def set_PositionY(self, value: float) -> None:
            self.node.set("PositionY", str(value))

        PositionY = property(get_PositionY, set_PositionY)

        def get_PositionZ(self) -> float:
            """Z position of stage"""
            return get_float_attr(self.node, "PositionZ")

        def set_PositionZ(self, value: float) -> None:
            self.node.set("PositionZ", str(value))

        PositionZ = property(get_PositionZ, set_PositionZ)

        def get_PositionXUnit(self) -> str:
            return self.node.get("PositionXUnit")

        def set_PositionXUnit(self, value: str) -> None:
            self.node.set("PositionXUnit", str(value))

        PositionXUnit = property(get_PositionXUnit, set_PositionXUnit)

        def get_PositionYUnit(self) -> str:
            return self.node.get("PositionYUnit")

        def set_PositionYUnit(self, value: str) -> None:
            self.node.set("PositionYUnit", str(value))

        PositionYUnit = property(get_PositionYUnit, set_PositionYUnit)

        def get_PositionZUnit(self) -> str:
            return self.node.get("PositionZUnit")

        def set_PositionZUnit(self, value: str) -> None:
            self.node.set("PositionZUnit", str(value))

        PositionZUnit = property(get_PositionZUnit, set_PositionZUnit)

    class Pixels(object):
        """The OME/Image/Pixels element

        The Pixels element represents the pixels in an OME image and, for
        an OME-XML encoded image, will actually contain the base-64 encoded
        pixel data. It has the X, Y, Z, C, and T extents of the image
        and it specifies the channel interleaving and channel depth.
        """

        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.namespaces = get_namespaces(self.node)

        def get_ID(self) -> str:
            return self.node.get("ID")

        def set_ID(self, value: str) -> None:
            self.node.set("ID", value)

        ID = property(get_ID, set_ID)

        def get_DimensionOrder(self) -> str:
            """The ordering of image planes in the file

            A 5-letter code indicating the ordering of pixels, from the most
            rapidly varying to least. Use the DO_* constants (for instance
            DO_XYZCT) to compare and set this.
            """
            return self.node.get("DimensionOrder")

        def set_DimensionOrder(self, value: str) -> None:
            self.node.set("DimensionOrder", value)

        DimensionOrder = property(get_DimensionOrder, set_DimensionOrder)

        def get_PixelType(self) -> str:
            """The pixel bit type, for instance PT_UINT8

            The pixel type specifies the datatype used to encode pixels
            in the image data. You can use the PT_* constants to compare
            and set the pixel type.
            """
            return self.node.get("Type")

        def get_PhysicalSizeXUnit(self) -> str:
            """The unit of length of a pixel in X direction."""
            return self.node.get("PhysicalSizeXUnit")

        def set_PhysicalSizeXUnit(self, value: str) -> None:
            self.node.set("PhysicalSizeXUnit", str(value))

        PhysicalSizeXUnit = property(get_PhysicalSizeXUnit, set_PhysicalSizeXUnit)

        def get_PhysicalSizeYUnit(self) -> str:
            """The unit of length of a pixel in Y direction."""
            return self.node.get("PhysicalSizeYUnit")

        def set_PhysicalSizeYUnit(self, value: str) -> None:
            self.node.set("PhysicalSizeYUnit", str(value))

        PhysicalSizeYUnit = property(get_PhysicalSizeYUnit, set_PhysicalSizeYUnit)

        def get_PhysicalSizeZUnit(self) -> str:
            """The unit of length of a voxel in Z direction."""
            return self.node.get("PhysicalSizeZUnit")

        def set_PhysicalSizeZUnit(self, value: str) -> None:
            self.node.set("PhysicalSizeZUnit", str(value))

        PhysicalSizeZUnit = property(get_PhysicalSizeZUnit, set_PhysicalSizeZUnit)

        def get_PhysicalSizeX(self) -> float:
            """The length of a single pixel in X direction."""
            return get_float_attr(self.node, "PhysicalSizeX")

        def set_PhysicalSizeX(self, value: float) -> None:
            self.node.set("PhysicalSizeX", str(value))

        PhysicalSizeX = property(get_PhysicalSizeX, set_PhysicalSizeX)

        def get_PhysicalSizeY(self) -> float:
            """The length of a single pixel in Y direction."""
            return get_float_attr(self.node, "PhysicalSizeY")

        def set_PhysicalSizeY(self, value: float) -> None:
            self.node.set("PhysicalSizeY", str(value))

        PhysicalSizeY = property(get_PhysicalSizeY, set_PhysicalSizeY)

        def get_PhysicalSizeZ(self) -> float:
            """The size of a voxel in Z direction or None for 2D images."""
            return get_float_attr(self.node, "PhysicalSizeZ")

        def set_PhysicalSizeZ(self, value: float) -> None:
            self.node.set("PhysicalSizeZ", str(value))

        PhysicalSizeZ = property(get_PhysicalSizeZ, set_PhysicalSizeZ)

        def set_PixelType(self, value: str) -> None:
            self.node.set("Type", value)

        PixelType = property(get_PixelType, set_PixelType)

        def get_SizeX(self) -> int:
            """The dimensions of the image in the X direction in pixels"""
            return get_int_attr(self.node, "SizeX")

        def set_SizeX(self, value: int) -> None:
            self.node.set("SizeX", str(value))

        SizeX = property(get_SizeX, set_SizeX)

        def get_SizeY(self) -> int:
            """The dimensions of the image in the Y direction in pixels"""
            return get_int_attr(self.node, "SizeY")

        def set_SizeY(self, value: int) -> None:
            self.node.set("SizeY", str(value))

        SizeY = property(get_SizeY, set_SizeY)

        def get_SizeZ(self) -> int:
            """The dimensions of the image in the Z direction in pixels"""
            return get_int_attr(self.node, "SizeZ")

        def set_SizeZ(self, value: int) -> None:
            self.node.set("SizeZ", str(value))

        SizeZ = property(get_SizeZ, set_SizeZ)

        def get_SizeT(self) -> int:
            """The dimensions of the image in the T direction in pixels"""
            return get_int_attr(self.node, "SizeT")

        def set_SizeT(self, value: int) -> None:
            self.node.set("SizeT", str(value))

        SizeT = property(get_SizeT, set_SizeT)

        def get_SizeC(self) -> int:
            """The dimensions of the image in the C direction in pixels"""
            return get_int_attr(self.node, "SizeC")

        def set_SizeC(self, value: int) -> None:
            self.node.set("SizeC", str(value))

        SizeC = property(get_SizeC, set_SizeC)

        def get_TimeIncrement(self) -> float:
            """The time increment between T planes"""
            return get_float_attr(self.node, "TimeIncrement")

        def set_TimeIncrement(self, value: float) -> None:
            self.node.set("TimeIncrement", str(value))

        TimeIncrement = property(get_TimeIncrement, set_TimeIncrement)

        def get_TimeIncrementUnit(self) -> str:
            """The unit of the time increment"""
            return self.node.get("TimeIncrementUnit")
        
        def set_TimeIncrementUnit(self, value: str) -> None:
            self.node.set("TimeIncrementUnit", value)

        TimeIncrementUnit = property(get_TimeIncrementUnit, set_TimeIncrementUnit)

        def get_channel_count(self) -> int:
            """The number of channels in the image

            You can change the number of channels in the image by
            setting the channel_count:

            pixels.channel_count = 3
            pixels.Channel(0).Name = "Red"
            ...
            """
            return len(self.node.findall(get_qualified_name(self.namespaces['ome'], "Channel")))

        def set_channel_count(self, value: int) -> None:
            if not (value > 0):
                raise Exception
            channel_count = self.channel_count
            if channel_count > value:
                channels = self.node.findall(get_qualified_name(self.namespaces['ome'], "Channel"))
                for channel in channels[value:]:
                    self.node.remove(channel)
            else:
                for _ in range(channel_count, value):
                    new_channel = OMEXML.Channel(
                        ElementTree.SubElement(self.node, get_qualified_name(self.namespaces['ome'], "Channel")))
                    new_channel.ID = str(uuid.uuid4())
                    new_channel.Name = new_channel.ID
                    new_channel.SamplesPerPixel = 1

        channel_count = property(get_channel_count, set_channel_count)

        def Channel(self, index: int = 0) -> "OMEXML.Channel":
            """Get the indexed channel from the Pixels element"""
            channel = self.node.findall(get_qualified_name(self.namespaces['ome'], "Channel"))[index]
            return OMEXML.Channel(channel)

        channel = Channel

        # integrated from AICSIMAGEIO
        def get_channel_names(self) -> list[str]:
            return [self.Channel(i).Name for i in range(self.get_channel_count())]

        def get_plane_count(self) -> int:
            """The number of planes in the image

            An image with only one plane or an interleaved color plane will
            often not have any planes.

            You can change the number of planes in the image by
            setting the plane_count:

            pixels.plane_count = 3
            pixels.Plane(0).TheZ=pixels.Plane(0).TheC=pixels.Plane(0).TheT=0
            ...
            """
            return len(self.node.findall(get_qualified_name(self.namespaces['ome'], "Plane")))

        def set_plane_count(self, value: int) -> None:
            if not (value >= 0):
                raise Exception
            plane_count = self.plane_count
            if plane_count > value:
                planes = self.node.findall(get_qualified_name(self.namespaces['ome'], "Plane"))
                for plane in planes[value:]:
                    self.node.remove(plane)
            else:
                for _ in range(plane_count, value):
                    new_plane = OMEXML.Plane(
                        ElementTree.SubElement(self.node, get_qualified_name(self.namespaces['ome'], "Plane")))

        plane_count = property(get_plane_count, set_plane_count)

        def Plane(self, index: int = 0) -> "OMEXML.Plane":
            """Get the indexed plane from the Pixels element"""
            plane = self.node.findall(get_qualified_name(self.namespaces['ome'], "Plane"))[index]
            return OMEXML.Plane(plane)

        plane = Plane

        def get_tiffdata_count(self) -> int:
            return len(self.node.findall(get_qualified_name(self.namespaces['ome'], "TiffData")))

        def set_tiffdata_count(self, value: int) -> None:
            if not (value >= 0):
                raise Exception
            tiffdatas = self.node.findall(get_qualified_name(self.namespaces['ome'], "TiffData"))
            for td in tiffdatas:
                self.node.remove(td)
            for _ in range(0, value):
                new_tiffdata = OMEXML.TiffData(
                    ElementTree.SubElement(self.node, get_qualified_name(self.namespaces['ome'], "TiffData")))

        tiffdata_count = property(get_tiffdata_count, set_tiffdata_count)

        # changed from tiffdata to Tiffdata
        def Tiffdata(self, index: int = 0) -> "OMEXML.TiffData":
            tiffData = self.node.findall(get_qualified_name(self.namespaces['ome'], "TiffData"))[index]
            return OMEXML.TiffData(tiffData)

        # adaoted from AICSIMAGEIO
        def populate_TiffData(self, explicit: bool = False) -> None:
            if (self.SizeC is None) or (self.SizeZ is None) or (self.SizeT is None):
                raise Exception
            total = self.SizeC * self.SizeT * self.SizeZ

            # bye bye old tiffdatas
            tiffdatas = self.node.findall(get_qualified_name(self.namespaces['ome'], "TiffData"))

            if explicit:
                for td in tiffdatas:
                    self.node.remove(td)

                sizes = {
                    "Z": self.SizeZ,
                    "C": self.SizeC,
                    "T": self.SizeT}

                setters = {
                    "Z": OMEXML.TiffData.set_FirstZ,
                    "C": OMEXML.TiffData.set_FirstC,
                    "T": OMEXML.TiffData.set_FirstT,
                }
                dims = self.DimensionOrder[-3:]
                ifd = 0
                for i in range(sizes[dims[2]]):
                    for j in range(sizes[dims[1]]):
                        for k in range(sizes[dims[0]]):
                            new_tiffdata = OMEXML.TiffData(
                                ElementTree.SubElement(self.node, get_qualified_name(self.namespaces['ome'], "TiffData")))
                            setters[dims[2]](new_tiffdata, i)
                            setters[dims[1]](new_tiffdata, j)
                            setters[dims[0]](new_tiffdata, k)
                            new_tiffdata.set_IFD(ifd)
                            new_tiffdata.set_PlaneCount(1)
                            # child element <UUID FileName=""></UUID> is omitted here for single file ome tiffs
                            # UUID has an optional FileName attribute for image data that
                            # are split among several files but we do not currently support it.
                            # uuidelem = ElementTree.SubElement(new_tiffdata.node, qn(self.ns['ome'], "UUID"))
                            # uuidelem.text = self.ome_uuid
                            ifd = ifd + 1
            else:
                # implicit only supports single-stack OME-XMLs (no multiple image stacks in same file)
                new_tiffdata = OMEXML.TiffData(
                    ElementTree.SubElement(self.node, get_qualified_name(self.namespaces["ome"], "TiffData"))
                )
                new_tiffdata.set_IFD(0)
                new_tiffdata.set_PlaneCount(total)

    class Instrument(object):
        """Representation of the OME/Instrument element"""

        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.namespaces = get_namespaces(self.node)

        def get_ID(self) -> str:
            return self.node.get("ID")

        def set_ID(self, value: str) -> None:
            self.node.set("ID", value)

        ID = property(get_ID, set_ID)

        @property
        def Detector(self) -> "OMEXML.Detector":
            return OMEXML.Detector(self.node.find(get_qualified_name(self.namespaces['ome'], "Detector")))

        @property
        def Objective(self) -> "OMEXML.Objective":
            return OMEXML.Objective(self.node.find(get_qualified_name(self.namespaces['ome'], "Objective")))

        @property
        def Microscope(self) -> "OMEXML.Microscope":
            return OMEXML.Microscope(self.node.find(get_qualified_name(self.namespaces['ome'], "Microscope")))

    def instrument(self, index: int = 0) -> "OMEXML.Instrument":
        return self.Instrument(self.root_node.findall(get_qualified_name(self.namespaces['ome'], "Instrument"))[index])

    class Objective(object):
        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.namespaces = get_namespaces(self.node)

        def get_ID(self) -> str:
            return self.node.get("ID")

        def set_ID(self, value: str) -> None:
            self.node.set("ID", value)

        ID = property(get_ID, set_ID)

        def get_LensNA(self) -> float:
            return self.node.get("LensNA")

        def set_LensNA(self, value: float) -> None:
            self.node.set("LensNA", value)

        LensNA = property(get_LensNA, set_LensNA)

        def get_NominalMagnification(self) -> float:
            return self.node.get("NominalMagnification")

        def set_NominalMagnification(self, value: float) -> None:
            self.node.set("NominalMagnification", value)

        NominalMagnification = property(get_NominalMagnification, set_NominalMagnification)

        def get_WorkingDistanceUnit(self) -> str:
            return get_int_attr(self.node, "WorkingDistanceUnit")

        def set_WorkingDistanceUnit(self, value: str) -> None:
            self.node.set("WorkingDistanceUnit", str(value))

        WorkingDistanceUnit = property(get_WorkingDistanceUnit, set_WorkingDistanceUnit)

    class Detector(object):
        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.namespaces = get_namespaces(self.node)

        def get_ID(self) -> str:
            return self.node.get("ID")

        def set_ID(self, value: str) -> None:
            self.node.set("ID", value)

        ID = property(get_ID, set_ID)

        def get_Gain(self) -> float:
            return self.node.get("Gain")

        def set_Gain(self, value: float) -> None:
            self.node.set("Gain", value)

        Gain = property(get_Gain, set_Gain)

        def get_Model(self) -> str:
            return self.node.get("Model")

        def set_Model(self, value: str) -> None:
            self.node.set("Model", value)

        Model = property(get_Model, set_Model)

        def get_Type(self) -> str:
            return self.node.get("Type")

        def set_Type(self, value: str) -> None:
            self.node.set("Type", str(value))

        Type = property(get_Type, set_Type)

    class Microscope(object):

        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.ns = get_namespaces(self.node)

        def get_Type(self) -> str:
            return self.node.get("Type")

        def set_Type(self, value: str) -> None:
            self.node.set("Type", str(value))

        Type = property(get_Type, set_Type)

        def get_Manufacturer(self) -> str:
            return self.node.get("Manufacturer")

        def set_Manufacturer(self, value: str) -> None:
            self.node.set("Manufacturer", str(value))

        Manufacturer = property(get_Manufacturer, set_Manufacturer)

        def get_Model(self) -> str:
            return self.node.get("Model")

        def set_Model(self, value: str) -> None:
            self.node.set("Model", str(value))

        Model = property(get_Model, set_Model)

        def get_SerialNumber(self) -> str:
            return self.node.get("SerialNumber")

        def set_SerialNumber(self, value: str) -> None:
            self.node.set("SerialNumber", str(value))

        SerialNumber = property(get_SerialNumber, set_SerialNumber)

        def get_LotNumber(self) -> str:
            return self.node.get("LotNumber")

        def set_LotNumber(self, value: str) -> None:
            self.node.set("LotNumber", str(value))

        LotNumber = property(get_LotNumber, set_LotNumber)

    class StructuredAnnotations(dict):
        """The OME/StructuredAnnotations element

        Structured annotations let OME-XML represent metadata from other file
        formats, for example the tag metadata in TIFF files. The
        StructuredAnnotations element is a container for the structured
        annotations.

        Images can have structured annotation references. These match to
        the IDs of structured annotations in the StructuredAnnotations
        element. You can get the structured annotations in an OME-XML document
        using a dictionary interface to StructuredAnnotations.

        Pragmatically, TIFF tag metadata is stored as key/value pairs in
        OriginalMetadata annotations - in the context of CellProfiler,
        callers will be using these to read tag data that's not represented
        in OME-XML such as the bits per sample and min and max sample values.

        """

        def __init__(self, node: ElementTree.Element) -> None:
            super().__init__()
            self.node = node
            self.ns = get_namespaces(self.node)

        def __getitem__(self, key: str) -> ElementTree.Element:
            for child in self.node:
                if child.get("ID") == key:
                    return child
            raise IndexError('ID "%s" not found' % key)

        def __contains__(self, key: str) -> bool:
            return self.has_key(key)

        def keys(self) -> list[str]:
            return filter(lambda x: x is not None,
                          [child.get("ID") for child in self.node])

        def has_key(self, key: str) -> bool:
            for child in self.node:
                if child.get("ID") == key:
                    return True
            return False

        def add_original_metadata(self, key: str | int, value: str) -> str:
            """Create an original data key/value pair

            key - the original metadata's key name, for instance OM_PHOTOMETRIC_INTERPRETATION

            value - the value, for instance, "RGB"

            returns the ID for the structured annotation.
            """
            xml_annotation = ElementTree.SubElement(
                self.node, get_qualified_name(self.ns['sa'], "XMLAnnotation"))
            node_id = str(uuid.uuid4())
            xml_annotation.set("ID", node_id)
            xa_value = ElementTree.SubElement(xml_annotation, get_qualified_name(self.ns['sa'], "Value"))
            ov = ElementTree.SubElement(
                xa_value, get_qualified_name(NS_ORIGINAL_METADATA, "OriginalMetadata"))
            ov_key = ElementTree.SubElement(ov, get_qualified_name(NS_ORIGINAL_METADATA, "Key"))
            set_text(ov_key, key)
            ov_value = ElementTree.SubElement(
                ov, get_qualified_name(NS_ORIGINAL_METADATA, "Value"))
            set_text(ov_value, value)
            return node_id

        def iter_original_metadata(self):
            """An iterator over the original metadata in structured annotations

            returns (<annotation ID>, (<key, value>))

            where <annotation ID> is the ID attribute of the annotation (which
            can be used to tie an annotation to an image)

                  <key> is the original metadata key, typically one of the
                  OM_* names of a TIFF tag
                  <value> is the value for the metadata
            """
            #
            # Here's the XML we're traversing:
            #
            # <StructuredAnnotations>
            #    <XMLAnnotation>
            #        <Value>
            #            <OriginalMetadta>
            #                <Key>Foo</Key>
            #                <Value>Bar</Value>
            #            </OriginalMetadata>
            #        </Value>
            #    </XMLAnnotation>
            # </StructuredAnnotations>
            #
            for annotation_node in self.node.findall(get_qualified_name(self.ns['sa'], "XMLAnnotation")):
                # <XMLAnnotation/>
                annotation_id = annotation_node.get("ID")
                for xa_value_node in annotation_node.findall(get_qualified_name(self.ns['sa'], "Value")):
                    # <Value/>
                    for om_node in xa_value_node.findall(
                            get_qualified_name(NS_ORIGINAL_METADATA, "OriginalMetadata")):
                        # <OriginalMetadata>
                        key_node = om_node.find(get_qualified_name(NS_ORIGINAL_METADATA, "Key"))
                        value_node = om_node.find(get_qualified_name(NS_ORIGINAL_METADATA, "Value"))
                        if key_node is not None and value_node is not None:
                            key_text = get_text(key_node)
                            value_text = get_text(value_node)
                            if key_text is not None and value_text is not None:
                                yield annotation_id, (key_text, value_text)
                            else:
                                logger.warning("Original metadata was missing key or value:" + om_node.toxml())
            return

        def has_original_metadata(self, key: str) -> bool:
            """True if there is an original metadata item with the given key"""
            return any([k == key
                        for annotation_id, (k, v)
                        in self.iter_original_metadata()])

        def get_original_metadata_value(self, key: str, default: str | None = None):
            """Return the value for a particular original metadata key

            key - key to search for
            default - default value to return if not found
            """
            for annotation_id, (k, v) in self.iter_original_metadata():
                if k == key:
                    return v
            return default

        def get_original_metadata_refs(self, ids: list[str]) -> dict[str, str]:
            """For a given ID, get the matching original metadata references

            ids - collection of IDs to match

            returns a dictionary of key to value
            """
            d = {}
            for annotation_id, (k, v) in self.iter_original_metadata():
                if annotation_id in ids:
                    d[k] = v
            return d

        @property
        def OriginalMetadata(self) -> "OMEXML.OriginalMetadata":
            return OMEXML.OriginalMetadata(self)

    class OriginalMetadata(dict):
        """View original metadata as a dictionary

        Original metadata holds "vendor-specific" metadata including TIFF
        tag values.
        """

        def __init__(self, structured_annotations: "OMEXML.StructuredAnnotations") -> None:
            """Initialized with the structured_annotations class instance"""
            super().__init__()
            self.structured_annotations = structured_annotations

        def __getitem__(self, key: str) -> str:
            return self.structured_annotations.get_original_metadata_value(key)

        def __setitem__(self, key: str, value: str) -> None:
            self.structured_annotations.add_original_metadata(key, value)

        def __contains__(self, key: str) -> bool:
            return self.has_key(key)

        def __iter__(self):
            for annotation_id, (key, value) in self.structured_annotations.iter_original_metadata():
                yield key

        def __len__(self) -> int:
            return len(list(self.structured_annotations.iter_original_metadata()))

        def keys(self) -> list[str]:
            return [key
                    for annotation_id, (key, value)
                    in self.structured_annotations.iter_original_metadata()]

        def has_key(self, key: str) -> bool:
            for annotation_id, (k, value) in self.structured_annotations.iter_original_metadata():
                if k == key:
                    return True
            return False

        def iteritems(self):
            for annotation_id, (key, value) in self.structured_annotations.iter_original_metadata():
                yield key, value

    class PlatesDucktype(object):
        """It looks like a list of plates"""

        def __init__(self, root: ElementTree.Element) -> None:
            self.root = root
            self.namespaces = get_namespaces(self.root)

        def __getitem__(self, key: int | slice) -> "OMEXML.Plate" | list["OMEXML.Plate"]:
            plates = self.root.findall(get_qualified_name(self.namespaces['spw'], "Plate"))
            if isinstance(key, slice):
                return [OMEXML.Plate(plate) for plate in plates[key]]
            return OMEXML.Plate(plates[key])

        def __len__(self) -> int:
            return len(self.root.findall(get_qualified_name(self.namespaces['spw'], "Plate")))

        def __iter__(self):
            for plate in self.root.iterfind(get_qualified_name(self.namespaces['spw'], "Plate")):
                yield OMEXML.Plate(plate)

        def newPlate(self, name: str, plate_id: str =str(uuid.uuid4())) -> "OMEXML.Plate":
            new_plate_node = ElementTree.SubElement(
                self.root, get_qualified_name(self.namespaces['spw'], "Plate"))
            new_plate = OMEXML.Plate(new_plate_node)
            new_plate.ID = plate_id
            new_plate.Name = name
            return new_plate

    class Plate(object):
        """The SPW:Plate element

        This represents the plate element of the SPW schema:
        http://www.openmicroscopy.org/Schemas/SPW/2007-06/
        """

        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.namespaces = get_namespaces(self.node)

        def get_ID(self) -> str:
            return self.node.get("ID")

        def set_ID(self, value: str) -> None:
            self.node.set("ID", value)

        ID = property(get_ID, set_ID)

        def get_Name(self) -> str:
            return self.node.get("Name")

        def set_Name(self, value: str) -> None:
            self.node.set("Name", value)

        Name = property(get_Name, set_Name)

        def get_Status(self) -> str:
            return self.node.get("Status")

        def set_Status(self, value: str) -> None:
            self.node.set("Status", value)

        Status = property(get_Status, set_Status)

        def get_ExternalIdentifier(self) -> str:
            return self.node.get("ExternalIdentifier")

        def set_ExternalIdentifier(self, value: str) -> None:
            return self.node.set("ExternalIdentifier", value)

        ExternalIdentifier = property(get_ExternalIdentifier, set_ExternalIdentifier)

        def get_ColumnNamingConvention(self) -> str:
            # Consider a default if not defined of NC_NUMBER
            return self.node.get("ColumnNamingConvention")

        def set_ColumnNamingConvention(self, value: str) -> None:
            if not (value in (NC_LETTER, NC_NUMBER)):
                raise Exception
            self.node.set("ColumnNamingConvention", value)

        ColumnNamingConvention = property(get_ColumnNamingConvention,
                                          set_ColumnNamingConvention)

        def get_RowNamingConvention(self) -> str:
            # Consider a default if not defined of NC_LETTER
            return self.node.get("RowNamingConvention")

        def set_RowNamingConvention(self, value: str) -> None:
            if not (value in (NC_LETTER, NC_NUMBER)):
                raise Exception
            self.node.set("RowNamingConvention", value)

        RowNamingConvention = property(get_RowNamingConvention,
                                       set_RowNamingConvention)

        def get_WellOriginX(self) -> float:
            return get_float_attr(self.node, "WellOriginX")

        def set_WellOriginX(self, value: float) -> None:
            self.node.set("WellOriginX", str(value))

        WellOriginX = property(get_WellOriginX, set_WellOriginX)

        def get_WellOriginY(self):
            return get_float_attr(self.node, "WellOriginY")

        def set_WellOriginY(self, value):
            self.node.set("WellOriginY", str(value))

        WellOriginY = property(get_WellOriginY, set_WellOriginY)

        def get_Rows(self) -> int:
            return get_int_attr(self.node, "Rows")

        def set_Rows(self, value: int) -> None:
            self.node.set("Rows", str(value))

        Rows = property(get_Rows, set_Rows)

        def get_Columns(self) -> int:
            return get_int_attr(self.node, "Columns")

        def set_Columns(self, value: int) -> None:
            self.node.set("Columns", str(value))

        Columns = property(get_Columns, set_Columns)

        def get_Description(self) -> str:
            description = self.node.find(get_qualified_name(self.namespaces['spw'], "Description"))
            if description is None:
                return None
            return get_text(description)

        def set_Description(self, text: str) -> None:
            make_text_node(self.node, self.namespaces['spw'], "Description", text)

        Description = property(get_Description, set_Description)

        def get_Well(self) -> "OMEXML.WellsDucktype":
            """The well dictionary / list"""
            return OMEXML.WellsDucktype(self)

        Well = property(get_Well)

        def get_well_name(self, well: "OMEXML.Well") -> str:
            """Get a well's name, using the row and column convention"""
            result = "".join([
                "%02d" % (i + 1) if convention == NC_NUMBER
                else "ABCDEFGHIJKLMNOP"[i]
                for i, convention
                in ((well.Row, self.RowNamingConvention or NC_LETTER),
                    (well.Column, self.ColumnNamingConvention or NC_NUMBER))])
            return result

    class WellsDucktype(dict):
        """The WellsDucktype lets you retrieve and create wells

        The WellsDucktype looks like a dictionary but lets you reference
        the wells in a plate using indexing. Types of indexes:

        list indexing: e.g. plate.Well[14] gets the 14th well as it appears
                       in the XML
        dictionary_indexing:
            by well name - e.g. plate.Well["A08"]
            by row and column - e.g. plate.Well[1,3] (B03)
            by ID - e.g. plate.Well["Well:0:0:0"]
        If the ducktype is unable to parse a well name, it assumes you're
        using an ID.
        """

        def __init__(self, plate: "OMEXML.Plate") -> None:
            super().__init__()
            self.plate_node = plate.node
            self.plate = plate
            self.ns = get_namespaces(self.plate_node)

        def __len__(self) -> int:
            return len(self.plate_node.findall(get_qualified_name(self.ns['spw'], "Well")))

        def __getitem__(self, key: str) ->"OMEXML.Well" | None:
            all_wells = self.plate_node.findall(get_qualified_name(self.ns['spw'], "Well"))
            if isinstance(key, slice):
                return [OMEXML.Well(w) for w in all_wells[key]]
            if hasattr(key, "__len__") and len(key) == 2:
                well = OMEXML.Well(None)
                for w in all_wells:
                    well.node = w
                    if well.Row == key[0] and well.Column == key[1]:
                        return well
            if isinstance(key, int):
                return OMEXML.Well(all_wells[key])
            well = OMEXML.Well(None)
            for w in all_wells:
                well.node = w
                if self.plate.get_well_name(well) == key:
                    return well
                if well.ID == key:
                    return well
            return None

        def __iter__(self):
            """Return the standard name for all wells on the plate

            for instance, 'B03' for a well with Row=1, Column=2 for a plate
            with the standard row and column naming convention
            """
            all_wells = self.plate_node.findall(get_qualified_name(self.ns['spw'], "Well"))
            well = OMEXML.Well(None)
            for w in all_wells:
                well.node = w
                yield self.plate.get_well_name(well)

        def new(self, row, column, well_id=str(uuid.uuid4())) -> "OMEXML.Well":
            """Create a new well at the given row and column

            row - index of well's row
            column - index of well's column
            well_id - the ID attribute for the well
            """
            well_node = ElementTree.SubElement(
                self.plate_node, get_qualified_name(self.ns['spw'], "Well"))
            well = OMEXML.Well(well_node)
            well.Row = row
            well.Column = column
            well.ID = well_id
            return well

    class Well(object):
        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node

        def get_Column(self) -> int:
            return get_int_attr(self.node, "Column")

        def set_Column(self, value: int) -> None:
            self.node.set("Column", str(value))

        Column = property(get_Column, set_Column)

        def get_Row(self) -> int:
            return get_int_attr(self.node, "Row")

        def set_Row(self, value: int) -> None:
            self.node.set("Row", str(value))

        Row = property(get_Row, set_Row)

        def get_ID(self) -> str:
            return self.node.get("ID")

        def set_ID(self, value: str) -> None:
            self.node.set("ID", value)

        ID = property(get_ID, set_ID)

        def get_Sample(self) -> "OMEXML.WellSampleDucktype":
            return OMEXML.WellSampleDucktype(self.node)

        Sample = property(get_Sample)

        def get_ExternalDescription(self) -> str:
            return self.node.get("ExternalDescription")

        def set_ExternalDescription(self, value: str) -> None:
            return self.node.set("ExternalDescription", value)

        ExternalDescription = property(get_ExternalDescription, set_ExternalDescription)

        def get_ExternalIdentifier(self) -> str:
            return self.node.get("ExternalIdentifier")

        def set_ExternalIdentifier(self, value: str) -> None:
            return self.node.set("ExternalIdentifier", value)

        ExternalIdentifier = property(get_ExternalIdentifier, set_ExternalIdentifier)

        def get_Color(self) -> int:
            return int(self.node.get("Color"))

        def set_Color(self, value: int) -> None:
            self.node.set("Color", str(value))

        Color = property(get_Color, set_Color)

    class WellSampleDucktype(list):
        """The WellSample elements in a well

        This is made to look like an indexable list so that you can do
        things like:
        wellsamples[0:2]
        """

        def __init__(self, well_node: ElementTree.Element) -> None:
            super().__init__()
            self.well_node = well_node
            self.ns = get_namespaces(self.well_node)

        def __len__(self) -> int:
            return len(self.well_node.findall(get_qualified_name(self.ns['spw'], "WellSample")))

        def __getitem__(self, key: int | slice) -> "OMEXML.WellSample" | list["OMEXML.WellSample"]:
            all_samples = self.well_node.findall(get_qualified_name(self.ns['spw'], "WellSample"))
            if isinstance(key, slice):
                return [OMEXML.WellSample(s)
                        for s in all_samples[key]]
            return OMEXML.WellSample(all_samples[int(key)])

        def __iter__(self):
            """Iterate through the well samples."""
            all_samples = self.well_node.findall(get_qualified_name(self.ns['spw'], "WellSample"))
            for s in all_samples:
                yield OMEXML.WellSample(s)

        def new(self, wellsample_id: str =str(uuid.uuid4()), index: int | None = None) -> "OMEXML.WellSample":
            """Create a new well sample
            """
            if index is None:
                index = reduce(max, [s.Index for s in self], -1) + 1
            new_node = ElementTree.SubElement(
                self.well_node, get_qualified_name(self.ns['spw'], "WellSample"))
            wellsample = OMEXML.WellSample(new_node)
            wellsample.ID = wellsample_id
            wellsample.Index = index

    class WellSample(object):
        """The WellSample is a location within a well"""

        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.namespaces = get_namespaces(self.node)

        def get_ID(self) -> str:
            return self.node.get("ID")

        def set_ID(self, value: str) -> None:
            self.node.set("ID", value)

        ID = property(get_ID, set_ID)

        def get_PositionX(self) -> float:
            return get_float_attr(self.node, "PositionX")

        def set_PositionX(self, value: float) -> None:
            self.node.set("PositionX", str(value))

        PositionX = property(get_PositionX, set_PositionX)

        def get_PositionY(self) -> float:
            return get_float_attr(self.node, "PositionY")

        def set_PositionY(self, value: float) -> None:
            self.node.set("PositionY", str(value))

        PositionY = property(get_PositionY, set_PositionY)

        def get_Timepoint(self) -> int:
            return self.node.get("Timepoint")

        def set_Timepoint(self, value: int) -> None:
            if isinstance(value, datetime.datetime):
                value = value.isoformat()
            self.node.set("Timepoint", value)

        Timepoint = property(get_Timepoint, set_Timepoint)

        def get_Index(self) -> int:
            return get_int_attr(self.node, "Index")

        def set_Index(self, value: int) -> None:
            self.node.set("Index", str(value))

        Index = property(get_Index, set_Index)

        def get_ImageRef(self) -> str:
            """Get the ID of the image of this site"""
            ref = self.node.find(get_qualified_name(self.namespaces['spw'], "ImageRef"))
            if ref is None:
                return None
            return ref.get("ID")

        def set_ImageRef(self, value: str) -> None:
            """Add a reference to the image of this site"""
            ref = self.node.find(get_qualified_name(self.namespaces['spw'], "ImageRef"))
            if ref is None:
                ref = ElementTree.SubElement(self.node, get_qualified_name(self.namespaces['spw'], "ImageRef"))
            ref.set("ID", value)

        ImageRef = property(get_ImageRef, set_ImageRef)

    class ROIRef(object):

        def __init__(self, node: ElementTree.Element):
            self.node = node
            self.namespaces = get_namespaces(self.node)

        def get_ID(self) -> str:
            return self.node.get("ID")

        def set_ID(self, value: int) -> None:
            """
            ID will automatically be in the format "ROI:value"
            and must match the ROI ID (that uses the same
            formatting)
            """
            self.node.set("ID", "ROI:" + str(value))

        ID = property(get_ID, set_ID)

    def get_roi_count(self) -> int:
        return len(self.root_node.findall(get_qualified_name(self.namespaces['ome'], "ROI")))

    def set_roi_count(self, value: int) -> None:
        """Add or remove roi nodes as needed"""
        if not (value > 0):
            raise Exception
        root = self.root_node
        if self.roi_count > value:
            roi_nodes = root.find(get_qualified_name(self.namespaces['ome'], "ROI"))
            for roi_node in roi_nodes[value:]:
                root.remove(roi_node)
        while (self.roi_count < value):
            iteration = self.roi_count - 1

            new_roi = self.ROI(ElementTree.SubElement(root, get_qualified_name(self.namespaces['ome'], "ROI")))
            new_roi.ID = str(iteration)
            new_roi.Name = "Marker " + str(iteration)
            new_Union = self.Union(
                ElementTree.SubElement(new_roi.node, get_qualified_name(self.namespaces['ome'], "Union")))
            new_Rectangle = self.Rectangle(
                ElementTree.SubElement(new_Union.node, get_qualified_name(self.namespaces['ome'], "Rectangle")))
            new_Rectangle.set_ID("Shape:" + str(iteration) + ":0")
            new_Rectangle.set_TheZ(0)
            new_Rectangle.set_TheC(0)
            new_Rectangle.set_TheT(0)
            new_Rectangle.set_StrokeColor(-16776961)  # Default = Red
            new_Rectangle.set_StrokeWidth(20)
            new_Rectangle.set_Text(str(iteration))
            new_Rectangle.set_Width(512)
            new_Rectangle.set_Height(512)
            new_Rectangle.set_X(0)
            new_Rectangle.set_Y(0)

    roi_count = property(get_roi_count, set_roi_count)

    def roi(self, index: int = 0) -> "OMEXML.ROI":
        """Return an ROI node by index"""
        return self.ROI(self.root_node.findall(get_qualified_name(self.namespaces['ome'], "ROI"))[index])

    class ROI(object):

        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.namespaces = get_namespaces(self.node)

        def get_ID(self) -> str:
            return self.node.get("ID")

        def set_ID(self, value: int) -> None:
            """
            ID will automatically be in the format "ROI:value"
            and must match the ROIRef ID (that uses the same
            formatting)
            """
            self.node.set("ID", "ROI:" + str(value))

        ID = property(get_ID, set_ID)

        def get_Name(self) -> str:
            return self.node.get("Name")

        def set_Name(self, value: str) -> None:
            self.node.set("Name", str(value))

        Name = property(get_Name, set_Name)

        @property
        def Union(self) -> "OMEXML.Union":
            """The OME/ROI/Union element."""
            return OMEXML.Union(self.node.find(get_qualified_name(self.namespaces['ome'], "Union")))

    class Union(object):

        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.namespaces = get_namespaces(self.node)

        def Rectangle(self) -> "OMEXML.Rectangle":
            """The OME/ROI/Union element. Currently only rectangle ROIs are available."""
            return OMEXML.Rectangle(self.node.find(get_qualified_name(self.namespaces['ome'], "Rectangle")))

    class Rectangle(object):

        def __init__(self, node: ElementTree.Element) -> None:
            self.node = node
            self.namespaces = get_namespaces(self.node)

        def get_ID(self) -> str:
            return self.node.get("ID")

        def set_ID(self, value: str) -> None:
            self.node.set("ID", str(value))

        ID = property(get_ID, set_ID)

        def get_StrokeColor(self) -> int:
            return self.node.get("StrokeColor")

        def set_StrokeColor(self, value: int) -> None:
            self.node.set("StrokeColor", str(value))

        StrokeColor = property(get_StrokeColor, set_StrokeColor)

        def get_StrokeWidth(self) -> int:
            return self.node.get("StrokeWidth")

        def set_StrokeWidth(self, value : int) -> None:
            """
            Colour is set using RGBA to integer conversion calculated using function from:
            https://docs.openmicroscopy.org/omero/5.5.1/developers/Python.html
            
            RGB colours: Red=-16776961, Green=16711935, Blue=65535
            """
            self.node.set("StrokeWidth", str(value))

        StrokeWidth = property(get_StrokeWidth, set_StrokeWidth)

        def get_Text(self) -> str:
            return self.node.get("Text")

        def set_Text(self, value: str) -> None:
            self.node.set("Text", str(value))

        Text = property(get_Text, set_Text)

        def get_Height(self) -> int:
            return self.node.get("Height")

        def set_Height(self, value: int) -> None:
            self.node.set("Height", str(value))

        Height = property(get_Height, set_Height)

        def get_Width(self) -> int:
            return self.node.get("Width")

        def set_Width(self, value: int) -> None:
            self.node.set("Width", str(value))

        Width = property(get_Width, set_Width)

        def get_X(self) -> int:
            return self.node.get("X")

        def set_X(self, value: int) -> None:
            self.node.set("X", str(value))

        X = property(get_X, set_X)

        def get_Y(self) -> int:
            return self.node.get("Y")

        def set_Y(self, value: int) -> None:
            self.node.set("Y", str(value))

        Y = property(get_Y, set_Y)

        def get_TheZ(self) -> int:
            """The Z index of the plane"""
            return get_int_attr(self.node, "TheZ")

        def set_TheZ(self, value: int) -> None:
            self.node.set("TheZ", str(value))

        TheZ = property(get_TheZ, set_TheZ)

        def get_TheC(self) -> int:
            """The channel index of the plane"""
            return get_int_attr(self.node, "TheC")

        def set_TheC(self, value: int) -> None:
            self.node.set("TheC", str(value))

        TheC = property(get_TheC, set_TheC)

        def get_TheT(self) -> int:
            """The T index of the plane"""
            return get_int_attr(self.node, "TheT")

        def set_TheT(self, value: int) -> None:
            self.node.set("TheT", str(value))

        TheT = property(get_TheT, set_TheT)
