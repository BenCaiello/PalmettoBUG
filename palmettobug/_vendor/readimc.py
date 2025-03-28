'''
This is a "vendorized" version of readimc package: https://github.com/BodenmillerGroup/readimc

(
MIT License

Copyright (c) 2021 University of Zurich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
)

Changes:
    -- Kept only code needed for the MCDFile class of readimc  (the only part used by PalmettoBUG)
    -- unified code into one file (this file!) -- removing redundant / unused imports as they arose
    -- removed typing hints for Annotation, Panorama, Slide 
    -- switch to defusedxml for xml parsing and removed ET.Element type hinting
    -- add __all__ for docs
'''
__all__ = []
from warnings import warn
import mmap
import itertools
import re
from abc import ABC, abstractmethod
from os import PathLike
from typing import BinaryIO, List, Optional, Union, Dict, Tuple, Sequence
# from warnings import warn
import math
from dataclasses import dataclass, field

from pathlib import Path
import numpy as np
from imageio.v2 import imread

from xml.etree import ElementTree as ET


class AcquisitionBase(ABC):
    """Shared IMC acquisition metadata interface"""

    @property
    @abstractmethod
    def num_channels(self) -> int:
        """Number of channels"""
        raise NotImplementedError()

    @property
    @abstractmethod
    def channel_metals(self) -> Sequence[str]:
        """Symbols of metal isotopes (e.g. ``["Ag", "Ir"]``)"""
        raise NotImplementedError()

    @property
    @abstractmethod
    def channel_masses(self) -> Sequence[int]:
        """Atomic masses of metal isotopes (e.g. ``[107, 191]``)"""
        raise NotImplementedError()

    @property
    @abstractmethod
    def channel_labels(self) -> Sequence[str]:
        """Channel labels (user-provided)"""
        raise NotImplementedError()

    @property
    def channel_names(self) -> Sequence[str]:
        """Unique channel names in the format ``f"{metal}{mass}"`` (e.g.
        ``["Ag107", "Ir191"]``)"""
        return [
            f"{channel_metal}{channel_mass}"
            for channel_metal, channel_mass in zip(
                self.channel_metals, self.channel_masses
            )
        ]


@dataclass
class Acquisition(AcquisitionBase):
    """IMC acquisition metadata"""

    slide: "Slide"
    """Parent slide"""

    panorama: Optional["Panorama"]
    """Associated panorama"""

    id: int
    """Acquisition ID"""

    roi_points_um: Optional[
        Tuple[
            Tuple[float, float],
            Tuple[float, float],
            Tuple[float, float],
            Tuple[float, float],
        ]
    ]
    """User-provided ROI points, in micrometers

    Order: (top left, top right, bottom right, bottom left)"""

    metadata: Dict[str, str]
    """Full acquisition metadata"""

    _num_channels: int
    _channel_metals: List[str] = field(default_factory=list)
    _channel_masses: List[int] = field(default_factory=list)
    _channel_labels: List[str] = field(default_factory=list)

    @property
    def description(self) -> Optional[str]:
        """User-provided acquisition description"""
        return self.metadata.get("Description")

    @property
    def width_px(self) -> Optional[int]:
        """Acquisition width, in pixels"""
        value = self.metadata.get("MaxX")
        if value is not None:
            return int(value)
        return None

    @property
    def height_px(self) -> Optional[int]:
        """Acquisition height, in pixels"""
        value = self.metadata.get("MaxY")
        if value is not None:
            return int(value)
        return None

    @property
    def pixel_size_x_um(self) -> Optional[float]:
        """Width of a single pixel, in micrometers"""
        value = self.metadata.get("AblationDistanceBetweenShotsX")
        if value is not None:
            return float(value)
        return None

    @property
    def pixel_size_y_um(self) -> Optional[float]:
        """Height of a single pixel, in micrometers"""
        value = self.metadata.get("AblationDistanceBetweenShotsY")
        if value is not None:
            return float(value)
        return None

    @property
    def width_um(self) -> Optional[float]:
        """Acquisition width, in micrometers"""
        if self.width_px is not None and self.pixel_size_x_um is not None:
            return self.width_px * self.pixel_size_x_um
        return None

    @property
    def height_um(self) -> Optional[float]:
        """Acquisition height, in micrometers"""
        if self.height_px is not None and self.pixel_size_y_um is not None:
            return self.height_px * self.pixel_size_y_um
        return None

    @property
    def num_channels(self) -> int:
        return self._num_channels

    @property
    def channel_metals(self) -> Sequence[str]:
        return self._channel_metals

    @property
    def channel_masses(self) -> Sequence[int]:
        return self._channel_masses

    @property
    def channel_labels(self) -> Sequence[str]:
        return self._channel_labels

    @property
    def roi_coords_um(
        self,
    ) -> Optional[
        Tuple[
            Tuple[float, float],
            Tuple[float, float],
            Tuple[float, float],
            Tuple[float, float],
        ]
    ]:
        """ROI stage coordinates, in micrometers

        Order: (top left, top right, bottom right, bottom left)"""
        x1_str = self.metadata.get("ROIStartXPosUm")
        y1_str = self.metadata.get("ROIStartYPosUm")
        x3_str = self.metadata.get("ROIEndXPosUm")
        y3_str = self.metadata.get("ROIEndYPosUm")
        if (
            x1_str != x3_str
            and y1_str != y3_str
            and x1_str is not None
            and y1_str is not None
            and x3_str is not None
            and y3_str is not None
            and self.width_um is not None
            and self.height_um is not None
        ):
            x1, y1 = float(x1_str), float(y1_str)
            x3, y3 = float(x3_str), float(y3_str)
            # fix Fluidigm bug, where start positions are multiplied by 1000
            if abs(x1 / 1000.0 - x3) < abs(x1 - x3):
                x1 /= 1000.0
            if abs(y1 / 1000.0 - y3) < abs(y1 - y3):
                y1 /= 1000.0
            # calculate counter-clockwise rotation angle, in radians
            rotated_main_diag_angle = np.arctan2(y1 - y3, x1 - x3)
            main_diag_angle = np.arctan2(self.height_um, -self.width_um)
            angle = rotated_main_diag_angle - main_diag_angle
            # calculate missing points (generative approach)
            x2, y2 = self.width_um / 2.0, self.height_um / 2.0
            x4, y4 = -self.width_um / 2.0, -self.height_um / 2.0
            x2, y2 = (
                math.cos(angle) * x2 - math.sin(angle) * y2 + (x1 + x3) / 2.0,
                math.sin(angle) * x2 + math.cos(angle) * y2 + (y1 + y3) / 2.0,
            )
            x4, y4 = (
                math.cos(angle) * x4 - math.sin(angle) * y4 + (x1 + x3) / 2.0,
                math.sin(angle) * x4 + math.cos(angle) * y4 + (y1 + y3) / 2.0,
            )
            return ((x1, y1), (x2, y2), (x3, y3), (x4, y4))
        return None

@dataclass
class Panorama:
    """Panorama metadata (only for panoramas with panorama image data)"""

    slide: "Slide"
    """Parent slide"""

    id: int
    """Panorama ID"""

    metadata: Dict[str, str]
    """Full panorama metadata"""

    acquisitions: List[Acquisition] = field(default_factory=list)
    """List of acquisitions associated with this panorama"""

    @property
    def description(self) -> Optional[str]:
        """User-provided panorama description"""
        return self.metadata.get("Description")

    @property
    def width_um(self) -> Optional[float]:
        """Panorama width, in micrometers"""
        if self.points_um is not None:
            (x1, y1), (x2, y2), (x3, y3), (x4, y4) = self.points_um
            w1 = ((x1 - x2) ** 2.0 + (y1 - y2) ** 2.0) ** 0.5
            w2 = ((x3 - x4) ** 2.0 + (y3 - y4) ** 2.0) ** 0.5
            if abs(w1 - w2) > 0.001:
                raise ValueError(f"Panorama {self.id}: inconsistent image widths")
            return (w1 + w2) / 2.0
        return None

    @property
    def height_um(self) -> Optional[float]:
        """Panorama height, in micrometers"""
        if self.points_um is not None:
            (x1, y1), (x2, y2), (x3, y3), (x4, y4) = self.points_um
            h1 = ((x1 - x4) ** 2.0 + (y1 - y4) ** 2.0) ** 0.5
            h2 = ((x2 - x3) ** 2.0 + (y2 - y3) ** 2.0) ** 0.5
            if abs(h1 - h2) > 0.001:
                raise ValueError(f"Panorama {self.id}: inconsistent image heights")
            return (h1 + h2) / 2.0
        return None

    @property
    def points_um(
        self,
    ) -> Optional[
        Tuple[
            Tuple[float, float],
            Tuple[float, float],
            Tuple[float, float],
            Tuple[float, float],
        ]
    ]:
        """User-provided ROI points, in micrometers

        Order: (top left, top right, bottom right, bottom left)"""
        x1_str = self.metadata.get("SlideX1PosUm")
        y1_str = self.metadata.get("SlideY1PosUm")
        x2_str = self.metadata.get("SlideX2PosUm")
        y2_str = self.metadata.get("SlideY2PosUm")
        x3_str = self.metadata.get("SlideX3PosUm")
        y3_str = self.metadata.get("SlideY3PosUm")
        x4_str = self.metadata.get("SlideX4PosUm")
        y4_str = self.metadata.get("SlideY4PosUm")
        if (
            x1_str is not None
            and y1_str is not None
            and x2_str is not None
            and y2_str is not None
            and x3_str is not None
            and y3_str is not None
            and x4_str is not None
            and y4_str is not None
        ):
            return (
                (float(x1_str), float(y1_str)),
                (float(x2_str), float(y2_str)),
                (float(x3_str), float(y3_str)),
                (float(x4_str), float(y4_str)),
            )
        return None

@dataclass
class Slide:
    """Slide metadata"""

    id: int
    """Slide ID"""

    metadata: Dict[str, str]
    """Full slide metadata"""

    panoramas: List[Panorama] = field(default_factory=list)
    """List of panoramas associated with this slide"""

    acquisitions: List[Acquisition] = field(default_factory=list)
    """List of acquisitions associated with this slide"""

    @property
    def description(self) -> Optional[str]:
        """User-provided slide description"""
        return self.metadata.get("Description")

    @property
    def width_um(self) -> Optional[float]:
        """Slide width, in micrometers"""
        value = self.metadata.get("WidthUm")
        if value is not None:
            return float(value)
        return None

    @property
    def height_um(self) -> Optional[float]:
        """Slide height, in micrometers"""
        value = self.metadata.get("HeightUm")
        if value is not None:
            return float(value)
        return None

class IMCFile(ABC):
    """Shared IMC file interface"""

    def __init__(self, path: Union[str, PathLike]) -> None:
        super().__init__()
        self._path = Path(path)

    @property
    def path(self) -> Path:
        """Path to the IMC file"""
        return self._path

    @abstractmethod
    def read_acquisition(self, acquisition = None) -> np.ndarray:
        """Reads IMC acquisition data as numpy array.

        :param acquisition: the acquisition to read
        :return: the acquisition data as 32-bit floating point array,
            shape: (c, y, x)
        """
        raise NotImplementedError()

class MCDParserError(Exception):
    def __init__(self, *args) -> None:
        """Error occurring when parsing invalid IMC .mcd file metadata"""
        super(MCDParserError, self).__init__(*args)


class MCDParser:
    _XMLNS_REGEX = re.compile(r"{(?P<xmlns>.*)}")
    _CHANNEL_REGEX = re.compile(r"^(?P<metal>[a-zA-Z]+)\((?P<mass>[0-9]+)\)$")

    def __init__(self, schema_xml: str) -> None:
        """A class for parsing IMC .mcd file metadata

        :param schema_xml: IMC .mcd file metadata in proprietary XML format
        """
        self._schema_xml = schema_xml
        self._schema_xml_elem = ET.fromstring(self._schema_xml)
        m = self._XMLNS_REGEX.match(self._schema_xml_elem.tag)
        self._schema_xml_xmlns = m.group("xmlns") if m is not None else None

    @property
    def schema_xml(self) -> str:
        """Full IMC .mcd file metadata in proprietary XML format"""
        return self._schema_xml

    @property
    def schema_xml_elem(self):
        """Full IMC .mcd file metadata as Python ElementTree element"""
        return self._schema_xml_elem

    @property
    def schema_xml_xmlns(self) -> Optional[str]:
        """Value of the metadata `xmlns` XML namespace attribute"""
        return self._schema_xml_xmlns

    @property
    def metadata(self) -> str:
        """Legacy accessor for `schema_xml`"""
        warn(
            "`MCDParser.metadata` will be removed in future readimc releases; "
            "use `MCDFile.schema_xml` instead"
        )
        return self.schema_xml

    @property
    def metadata_elem(self):
        """Legacy accessor for `schema_xml_elem`"""
        warn(
            "`MCDParser.metadata_elem` will be removed in future readimc releases; "
            "use `MCDFile.schema_xml_elem` instead"
        )
        return self.schema_xml_elem

    @property
    def metadata_xmlns(self) -> Optional[str]:
        """Legacy accessor for `schema_xml_xmlns`"""
        warn(
            "`MCDParser.metadata_xmlns` will be removed in future readimc releases; "
            "use `MCDFile.schema_xml_xmlns` instead"
        )
        return self.schema_xml_xmlns

    def parse_slides(self):
        """Extract slide metadata"""
        slides = [
            self._parse_slide(slide_elem) for slide_elem in self._find_elements("Slide")
        ]
        slides.sort(key=lambda slide: slide.id)
        return slides

    def _parse_slide(self, slide_elem):
        slide = Slide(
            self._get_text_as_int(slide_elem, "ID"),
            self._get_metadata_dict(slide_elem),
        )
        panorama_elems = self._find_elements(f"Panorama[SlideID='{slide.id}']")
        for panorama_elem in panorama_elems:
            panorama = None
            panorama_id = self._get_text_as_int(panorama_elem, "ID")
            panorama_type = self._get_text_or_none(panorama_elem, "Type")
            if panorama_type != "Default":  # ignore "virtual" Panoramas
                panorama = self._parse_panorama(panorama_elem, slide)
                slide.panoramas.append(panorama)
            acquisition_roi_elems = self._find_elements(
                f"AcquisitionROI[PanoramaID='{panorama_id}']"
            )
            for acquisition_roi_elem in acquisition_roi_elems:
                acquisition_roi_id = self._get_text_as_int(acquisition_roi_elem, "ID")
                roi_point_elems = self._find_elements(
                    f"ROIPoint[AcquisitionROIID='{acquisition_roi_id}']"
                )
                roi_points_um = None
                if len(roi_point_elems) == 4:
                    roi_points_um = tuple(
                        (
                            self._get_text_as_float(roi_point_elem, "SlideXPosUm"),
                            self._get_text_as_float(roi_point_elem, "SlideYPosUm"),
                        )
                        for roi_point_elem in sorted(
                            roi_point_elems,
                            key=lambda roi_point_elem: self._get_text_as_int(
                                roi_point_elem, "OrderNumber"
                            ),
                        )
                    )
                acquisition_elems = self._find_elements(
                    f"Acquisition[AcquisitionROIID='{acquisition_roi_id}']"
                )
                for acquisition_elem in acquisition_elems:
                    acquisition = self._parse_acquisition(
                        acquisition_elem, slide, panorama, roi_points_um  # type: ignore
                    )
                    slide.acquisitions.append(acquisition)
                    if panorama is not None:
                        panorama.acquisitions.append(acquisition)
        for a, b in itertools.combinations(slide.acquisitions, 2):
            a_start = int(a.metadata["DataStartOffset"])
            a_end = int(a.metadata["DataEndOffset"])
            b_start = int(b.metadata["DataStartOffset"])
            b_end = int(b.metadata["DataEndOffset"])
            if b_start <= a_start < b_end or b_start < a_end <= b_end:
                warn(
                    f"Slide {slide.id} corrupted: "
                    f"overlapping memory blocks for acquisitions {a.id} and {b.id}"
                )
        slide.panoramas.sort(key=lambda panorama: panorama.id)
        slide.acquisitions.sort(key=lambda acquisition: acquisition.id)
        return slide

    def _parse_panorama(self, panorama_elem, slide):
        return Panorama(
            slide,
            self._get_text_as_int(panorama_elem, "ID"),
            self._get_metadata_dict(panorama_elem),
        )

    def _parse_acquisition(
        self,
        acquisition_elem,
        slide,
        panorama,
        roi_points_um: Optional[
            Tuple[
                Tuple[float, float],
                Tuple[float, float],
                Tuple[float, float],
                Tuple[float, float],
            ]
        ],
    ):
        acquisition_id = self._get_text_as_int(acquisition_elem, "ID")
        acquisition_channel_elems = self._find_elements(
            f"AcquisitionChannel[AcquisitionID='{acquisition_id}']"
        )
        acquisition_channel_elems.sort(
            key=lambda acquisition_channel_elem: self._get_text_as_int(
                acquisition_channel_elem, "OrderNumber"
            )
        )
        acquisition = Acquisition(
            slide,
            panorama,
            acquisition_id,
            roi_points_um,
            self._get_metadata_dict(acquisition_elem),
            len(acquisition_channel_elems) - 3,
        )
        for i, acquisition_channel_elem in enumerate(acquisition_channel_elems):
            channel_name = self._get_text(acquisition_channel_elem, "ChannelName")
            if i == 0 and channel_name != "X":
                raise MCDParserError(
                    f"First channel '{channel_name}' should be named 'X'"
                )
            if i == 1 and channel_name != "Y":
                raise MCDParserError(
                    f"Second channel '{channel_name}' should be named 'Y'"
                )
            if i == 2 and channel_name != "Z":
                raise MCDParserError(
                    f"Third channel '{channel_name}' should be named 'Z'"
                )
            if channel_name in ("X", "Y", "Z"):
                continue
            m = self._CHANNEL_REGEX.match(channel_name)
            if m is None:
                raise MCDParserError(
                    "Cannot extract channel information "
                    f"from channel name '{channel_name}' "
                    f"for acquisition {acquisition.id}"
                )
            channel_label = self._get_text(acquisition_channel_elem, "ChannelLabel")
            acquisition._channel_metals.append(m.group("metal"))
            acquisition._channel_masses.append(int(m.group("mass")))
            acquisition._channel_labels.append(channel_label)
        return acquisition

    def _find_elements(self, path: str):
        namespaces = None
        if self._schema_xml_xmlns is not None:
            namespaces = {"": self._schema_xml_xmlns}
        return self._schema_xml_elem.findall(path, namespaces=namespaces)

    def _get_text_or_none(self, parent_elem, tag: str) -> Optional[str]:
        namespaces = None
        if self._schema_xml_xmlns is not None:
            namespaces = {"": self._schema_xml_xmlns}
        elem = parent_elem.find(tag, namespaces=namespaces)
        return (elem.text or "") if elem is not None else None

    def _get_text(self, parent_elem, tag: str) -> str:
        text = self._get_text_or_none(parent_elem, tag)
        if text is None:
            raise MCDParserError(
                f"XML tag '{tag}' not found for parent XML tag '{parent_elem.tag}'"
            )
        return text

    def _get_text_as_int(self, parent_elem, tag: str) -> int:
        text = self._get_text(parent_elem, tag)
        try:
            return int(text)
        except ValueError as e:
            raise MCDParserError(
                f"Text '{text}' of XML tag '{tag}' cannot be converted to int "
                f"for parent XML tag '{parent_elem.tag}'"
            ) from e

    def _get_text_as_float(self, parent_elem, tag: str) -> float:
        text = self._get_text(parent_elem, tag)
        try:
            return float(text)
        except ValueError as e:
            raise MCDParserError(
                f"Text '{text}' of XML tag '{tag}' cannot be converted to "
                f"float for parent XML tag '{parent_elem.tag}'"
            ) from e

    def _get_metadata_dict(self, parent_elem) -> Dict[str, str]:
        metadata = {}
        for elem in parent_elem:
            tag = elem.tag
            if self._schema_xml_xmlns is not None:
                tag = tag.replace(f"{{{self._schema_xml_xmlns}}}", "")
            metadata[tag] = elem.text or ""
        return metadata

class MCDFile(IMCFile):
    def __init__(self, path: Union[str, PathLike]) -> None:
        """A class for reading IMC .mcd files

        :param path: path to the IMC .mcd file
        """
        super(MCDFile, self).__init__(path)
        self._fh: Optional[BinaryIO] = None
        self._schema_xml: Optional[str] = None
        self._slides = None

    @property
    def schema_xml(self) -> str:
        """Full metadata in proprietary XML format"""
        if self._schema_xml is None:
            raise IOError(f"MCD file '{self.path.name}' has not been opened")
        return self._schema_xml

    @property
    def metadata(self) -> str:
        """Legacy accessor for `schema_xml`"""
        warn(
            "`MCDFile.metadata` will be removed in future readimc releases; "
            "use `MCDFile.schema_xml` instead"
        )
        return self.schema_xml

    @property
    def slides(self):
        """Metadata on slides contained in this IMC .mcd file"""
        if self._slides is None:
            raise IOError(f"MCD file '{self.path.name}' has not been opened")
        return self._slides

    def __enter__(self) -> "MCDFile":
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def open(self) -> None:
        """Opens the IMC .mcd file for reading.

        It is good practice to use context managers whenever possible:

        .. code-block:: python

            with MCDFile("/path/to/file.mcd") as f:
                pass

        """
        if self._fh is not None:
            self._fh.close()
        self._fh = open(self._path, mode="rb")
        self._schema_xml = self._read_schema_xml()
        try:
            self._slides = MCDParser(self._schema_xml).parse_slides()
        except MCDParserError as e:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                "error parsing slide information from MCD-XML"
            ) from e

    def close(self) -> None:
        """Closes the IMC .mcd file.

        It is good practice to use context managers whenever possible:

        .. code-block:: python

            with MCDFile("/path/to/file.mcd") as f:
                pass

        """
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def read_acquisition(
        self, acquisition = None, strict: bool = True
    ) -> np.ndarray:
        """Reads IMC acquisition data as numpy array.

        :param acquisition: the acquisition to read
        :param strict: set this parameter to False to try to recover corrupted data
        :return: the acquisition data as 32-bit floating point array,
            shape: (c, y, x)
        """
        if acquisition is None:
            raise ValueError("acquisition")
        if self._fh is None:
            raise IOError(f"MCD file '{self.path.name}' has not been opened")
        try:
            data_start_offset = int(acquisition.metadata["DataStartOffset"])
            data_end_offset = int(acquisition.metadata["DataEndOffset"])
            value_bytes = int(acquisition.metadata["ValueBytes"])
        except (KeyError, ValueError) as e:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                "cannot locate acquisition image data"
            ) from e
        if data_start_offset >= data_end_offset:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                "invalid acquisition image data offsets"
            )
        if value_bytes <= 0:
            raise IOError("MCD file corrupted: invalid byte size")
        num_channels = acquisition.num_channels
        data_size = data_end_offset - data_start_offset
        bytes_per_pixel = (num_channels + 3) * value_bytes
        if data_size % bytes_per_pixel != 0:
            data_size += 1
        if data_size % bytes_per_pixel != 0:
            if strict:
                raise IOError(
                    f"MCD file '{self.path.name}' corrupted: "
                    "invalid acquisition image data size"
                )
            warn(
                f"MCD file '{self.path.name}' corrupted: "
                "invalid acquisition image data size"
            )
        num_pixels = data_size // bytes_per_pixel
        self._fh.seek(0)
        data = np.memmap(
            self._fh,
            dtype=np.float32,
            mode="r",
            offset=data_start_offset,
            shape=(num_pixels, num_channels + 3),
        )
        xs = data[:, 0].astype(int)
        ys = data[:, 1].astype(int)
        try:
            width = int(acquisition.metadata["MaxX"])
            height = int(acquisition.metadata["MaxY"])
            if width <= np.amax(xs) or height <= np.amax(ys):
                raise ValueError(
                    "data shape is incompatible with acquisition image dimensions"
                )
        except (KeyError, ValueError):
            warn(
                f"MCD file '{self.path.name}' corrupted: "
                "cannot read acquisition image dimensions; recovering from data shape"
            )
            width = np.amax(xs) + 1
            height = np.amax(ys) + 1
        if width * height != data.shape[0]:
            if strict:
                raise IOError(
                    f"MCD file '{self.path.name}' corrupted: "
                    "inconsistent acquisition image data size"
                )
            warn(
                f"MCD file '{self.path.name}' corrupted: "
                "inconsistent acquisition image data size"
            )
        img = np.zeros((num_channels, height, width), dtype=np.float32)
        img[:, ys, xs] = np.transpose(data[:, 3:])
        return img

    def read_slide(
        self, slide, raw: bool = False
    ) -> Union[np.ndarray, bytes, None]:
        """Reads and decodes a slide image as numpy array using the ``imageio``
        package.

        .. note::
            Slide images are stored as binary data within the IMC .mcd file in
            an arbitrary encoding. The ``imageio`` package can decode most
            commonly used image file formats, but may fail for more obscure,
            in which case an ``IOException`` is raised.

        :param slide: the slide to read
        :return: the slide image, or ``None`` if no image is available for the
            specified slide
        """
        try:
            data_start_offset = int(slide.metadata["ImageStartOffset"])
            data_end_offset = int(slide.metadata["ImageEndOffset"])
        except (KeyError, ValueError) as e:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                f"cannot locate image data for slide {slide.id}"
            ) from e
        if data_start_offset == data_end_offset == 0:
            return None
        data_start_offset += 161
        data_end_offset -= 1
        if data_start_offset >= data_end_offset:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                f"invalid image data offsets for slide {slide.id}"
            )
        try:
            return self._read_image(
                data_start_offset, data_end_offset - data_start_offset, raw
            )
        except Exception as e:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                f"cannot read image for slide {slide.id}"
            ) from e

    def read_panorama(
        self, panorama, raw: bool = False
    ) -> Union[np.ndarray, bytes, None]:
        """Reads and decodes a panorama image as numpy array using the
        ``imageio`` package.

        :param panorama: the panorama to read
        :return: the panorama image as numpy array
        """
        try:
            data_start_offset = int(panorama.metadata["ImageStartOffset"])
            data_end_offset = int(panorama.metadata["ImageEndOffset"])
        except (KeyError, ValueError) as e:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                f"cannot locate image data for panorama {panorama.id}"
            ) from e
        if data_start_offset == data_end_offset == 0:
            return None
        data_start_offset += 161
        data_end_offset -= 1
        if data_start_offset >= data_end_offset:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                f"invalid image data offsets for panorama {panorama.id}"
            )
        try:
            return self._read_image(
                data_start_offset, data_end_offset - data_start_offset, raw
            )
        except Exception as e:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                f"cannot read image for panorama {panorama.id}"
            ) from e

    def read_before_ablation_image(
        self, acquisition, raw: bool = False
    ) -> Union[np.ndarray, bytes, None]:
        """Reads and decodes a before-ablation image as numpy array using the
        ``imageio`` package.

        :param acquisition: the acquisition for which to read the
            before-ablation image
        :return: the before-ablation image as numpy array, or ``None`` if no
            before-ablation image is available for the specified acquisition
        """
        try:
            data_start_offset = int(
                acquisition.metadata["BeforeAblationImageStartOffset"]
            )
            data_end_offset = int(acquisition.metadata["BeforeAblationImageEndOffset"])
        except (KeyError, ValueError) as e:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                f"cannot locate before-ablation image data "
                f"for acquisition {acquisition.id}"
            ) from e
        if data_start_offset == data_end_offset == 0:
            return None
        data_start_offset += 161
        data_end_offset -= 1
        if data_start_offset >= data_end_offset:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                f"invalid before-ablation image data offsets "
                f"for acquisition {acquisition.id}"
            )
        try:
            return self._read_image(
                data_start_offset, data_end_offset - data_start_offset, raw
            )
        except Exception as e:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                f"cannot read before-ablation image "
                f"for acquisition {acquisition.id}"
            ) from e

    def read_after_ablation_image(
        self, acquisition, raw: bool = False
    ) -> Union[np.ndarray, bytes, None]:
        """Reads and decodes a after-ablation image as numpy array using the
        ``imageio`` package.

        :param acquisition: the acquisition for which to read the
            after-ablation image
        :return: the after-ablation image as numpy array, or ``None`` if no
            after-ablation image is available for the specified acquisition
        """
        try:
            data_start_offset = int(
                acquisition.metadata["AfterAblationImageStartOffset"]
            )
            data_end_offset = int(acquisition.metadata["AfterAblationImageEndOffset"])
        except (KeyError, ValueError) as e:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                f"cannot locate after-ablation image data "
                f"for acquisition {acquisition.id}"
            ) from e
        if data_start_offset == data_end_offset == 0:
            return None
        data_start_offset += 161
        data_end_offset -= 1
        if data_start_offset >= data_end_offset:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                f"invalid after-ablation image data offsets "
                f"for acquisition {acquisition.id}"
            )
        try:
            return self._read_image(
                data_start_offset, data_end_offset - data_start_offset, raw
            )
        except Exception as e:
            raise IOError(
                f"MCD file '{self.path.name}' corrupted: "
                f"cannot read after-ablation image "
                f"for acquisition {acquisition.id}"
            ) from e

    def _read_schema_xml(
        self,
        encoding: str = "utf-16-le",
        start_sub: str = "<MCDSchema",
        end_sub: str = "</MCDSchema>",
    ) -> str:
        if self._fh is None:
            raise IOError(f"MCD file '{self.path.name}' has not been opened")
        with mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            # V1 contains multiple MCDSchema entries
            # As per imctools, the latest entry should be taken
            start_sub_encoded = start_sub.encode(encoding=encoding)
            start_index = mm.rfind(start_sub_encoded)
            if start_index == -1:
                raise IOError(
                    f"MCD file '{self.path.name}' corrupted: "
                    f"start of XML document '{start_sub}' not found"
                )
            end_sub_encoded = end_sub.encode(encoding=encoding)
            end_index = mm.rfind(end_sub_encoded, start_index)
            if end_index == -1:
                raise IOError(
                    f"MCD file '{self.path.name}' corrupted: "
                    f"end of XML document '{end_sub}' not found"
                )
            mm.seek(start_index)
            data = mm.read(end_index + len(end_sub_encoded) - start_index)
        return data.decode(encoding=encoding)

    def _read_image(
        self, data_offset: int, data_size: int, raw: bool = False
    ) -> Union[np.ndarray, bytes]:
        if self._fh is None:
            raise IOError(f"MCD file '{self.path.name}' has not been opened")
        self._fh.seek(data_offset)
        data = self._fh.read(data_size)
        if raw:
            print('imread dependency is not used in this case from readimc -- consider removing!')
            return data
        else:
            print('imread dependency is used from readimc')
            return imread(data)

    def __repr__(self) -> str:
        return str(self._path)
