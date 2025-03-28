# ruff: noqa
'''
This file is an "vendorizing" of the fcsy package: https://github.com/nehcgnay/fcsy

(
MIT License

Copyright (c) 2018, yc

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
    -- add __all__ (for the sake of autoapi docs -- I don't really want to include any of the vendor files)
    -- Only kept the part needed for PalmettoBUG (DataFrame and its required code)
    -- merged all necessary files into this one
    -- Removing bespoke typing hints (._typing import commented out, all uses of them deleted in main text)
    -- removed now unused / duplicate imports



'''
__all__ = []


__version__ = "0.10.0"

from typing import Union
from io import BytesIO, StringIO
import struct
import re
from abc import abstractmethod, ABC
from contextlib import contextmanager
from functools import update_wrapper, partial

import numpy as np
import pandas as pd

#from ._typing import ReadFcsBuffer, WriteFcsBuffer, UpdateFcsBuffer
#from ._typing import ReadFcsBuffer as ReadFcsBufferType
#from ._typing import WriteFcsBuffer as WriteFcsBufferType

__all__ = ["DataFrame"]

try:
    import boto3  # type: ignore
except ImportError:
    boto3 = None

class ReadFcsBuffer(ABC):
    @abstractmethod
    def seek(self, position: int):
        pass

    @abstractmethod
    def read(self, number: int):
        pass

    @abstractmethod
    def close(self):
        pass


class WriteFcsBuffer(ABC):
    @abstractmethod
    def seek(self, position: int):
        pass

    @abstractmethod
    def write(self, __b: str):
        pass

    @abstractmethod
    def tell(self):
        pass

    @abstractmethod
    def close(self):
        pass


class S3ReadBuffer(ReadFcsBuffer):
    def __init__(self, path, bucket):
        if boto3 is None:
            raise ImportError(
                "This module requires boto3. Please use 'pip install fcsy[boto3] or install boto3 manually"
            )
        super().__init__()
        self.path = path
        self.bucket = bucket
        self.position = 0
        self.s3 = boto3.client("s3")

    def seek(self, position: int):
        self.position = position

    def read(self, number: int):
        resp = self.s3.get_object(
            Bucket=self.bucket,
            Key=self.path,
            Range=f"bytes={self.position}-{self.position+number}",
        )
        self.position += number
        return resp["Body"].read(number)

    def close(self):
        pass


class S3WriteBuffer(WriteFcsBuffer):
    def __init__(self, path, bucket):
        if boto3 is None:
            raise ImportError(
                "This module requires boto3. Please use 'pip install fcsy[boto3] or install boto3 manually"
            )
        super().__init__()
        self.path = path
        self.bucket = bucket
        self.s3 = boto3.client("s3")
        self.buffer = BytesIO()

    def seek(self, position: int):
        self.buffer.seek(position)

    def tell(self):
        return self.buffer.tell()

    def write(self, bytes):
        self.buffer.write(bytes)

    def close(self):
        self.seek(0)
        self.s3.upload_fileobj(self.buffer, self.bucket, self.path)


def read_path(path):
    if path.startswith("s3://"):
        match = re.match(r"s3://(.*?)/(.*?)$", path)
        return {
            "mode": "s3",
            "contents": {"bucket": match.group(1), "key": match.group(2)},
        }
    else:
        return {"mode": "local", "contents": {"path": path}}


def create_open_func(
    parser_class,
    *args,
    **kwargs,
):
    @contextmanager
    def func(path, *func_args, **func_kwargs):
        obj = parser_class(path, *args, **kwargs)
        try:
            yield obj
        finally:
            obj.close()

    return func


class Bufferize:
    def __init__(self, func, mode="rb") -> None:
        update_wrapper(self, func)
        self.func = func
        self.mode = mode

    def __get__(self, obj, objtype):
        return partial(self.__call__, obj)

    def __call__(self, obj, filepath_or_buffer, *args, **kwargs):
        if type(filepath_or_buffer) is str:
            path = read_path(filepath_or_buffer)
            if path["mode"] == "s3":
                if self.mode == "rb":
                    buffer_class = S3ReadBuffer
                elif self.mode == "wb":
                    buffer_class = S3WriteBuffer
                else:
                    raise ValueError("invalid s3 buffer mode")

                open_func = create_open_func(
                    buffer_class, bucket=path["contents"]["bucket"]
                )
                with open_func(path["contents"]["key"], self.mode) as fp:
                    return self.func(obj, fp, *args, **kwargs)
            else:
                with open(filepath_or_buffer, self.mode) as fp:
                    return self.func(obj, fp, *args, **kwargs)
        else:
            return self.func(obj, filepath_or_buffer, *args, **kwargs)


def bufferize(func=None, mode="rb"):
    if func:
        return Bufferize(func)
    else:

        def wrapper(func):
            return Bufferize(func, mode=mode)

        return wrapper
    
class HeaderSegment:
    ranges = {
        "version": (0, 5),
        "text_start": (10, 17),
        "text_end": (18, 25),
        "data_start": (26, 33),
        "data_end": (34, 41),
        "analysis_start": (42, 49),
        "analysis_end": (50, 57),
    }

    def __init__(
        self,
        text_start: int,
        text_end,
        data_start,
        data_end,
        analysis_start=0,
        analysis_end=0,
        ver: str = "FCS3.1",
    ) -> None:
        self.ver = ver
        self.text_start = text_start
        self.text_end = text_end
        self.data_start = data_start
        self.data_end = data_end
        self.analysis_start = analysis_start
        self.analysis_end = analysis_end

    def asdict(self):
        return {
            "text_start": self.text_start,
            "text_end": self.text_end,
            "data_start": self.data_start,
            "data_end": self.data_end,
            "analysis_start": self.analysis_start,
            "analysis_end": self.analysis_end,
        }

    @classmethod
    def from_string(cls, s: bytes):
        s = s.decode("UTF-8")
        v = dict()
        for key, value in cls.ranges.items():
            v[key] = s[value[0] : value[1] + 1].strip()
            if key != "version":
                v[key] = int(v[key])

        ver = v.pop("version")
        return HeaderSegment(
            v["text_start"],
            v["text_end"],
            v["data_start"],
            v["data_end"],
            v["analysis_start"],
            v["analysis_end"],
            ver=ver,
        )

    def _write_locations(self, sp: StringIO, type: str):
        sp.seek(self.ranges[f"{type}_start"][0])
        start_str = str(self.asdict()[f"{type}_start"])
        end_str = str(self.asdict()[f"{type}_end"])

        if len(start_str) > 8 or len(end_str) > 8:
            start_str = "0"
            end_str = "0"

        sp.write((8 - len(start_str)) * " " + start_str)
        sp.seek(self.ranges[f"{type}_end"][0])
        sp.write((8 - len(end_str)) * " " + end_str)

    def to_string(self):
        header = None
        with StringIO() as sp:
            sp.write(self.ver)
            sp.write(" " * 4)
            for t in ["text", "data", "analysis"]:
                self._write_locations(sp, t)
            header = sp.getvalue()

        return header


class TextSegment:
    def __init__(
        self,
        tot: int,
        pnn: list,
        pns: list,
        pnr: list,
        pne: list = None,
        mode: str = "L",
        next_data: int = 0,
        byte_order: str = "1,2,3,4",
        text_start=256,
        delim="/",
        datatype="F",
        data_start=None,
        data_end=None,
        analysis_start=None,
        analysis_end=None,
        stext_start=None,
        stext_end=None,
    ) -> None:
        self.tot = tot
        self.pnn = pnn
        self.pns = pns
        self.pnb = "32"
        self.pne = pne
        self.pnr = pnr
        self.mode = mode
        self.next_data = next_data
        self.byte_order = "1,2,3,4"
        self.text_start = text_start
        self.delim = delim
        self.datatype = datatype
        self.endian = {"1,2,3,4": "<", "4,3,2,1": ">"}[byte_order]
        self._data_start = data_start
        self._data_end = data_end
        self._analysis_start = analysis_start
        self._analysis_end = analysis_end
        self._stext_start = stext_start
        self._stext_end = stext_end
        self.text = self.build()

    def build(self):
        text = {}
        text["BYTEORD"] = self.byte_order
        text["DATATYPE"] = self.datatype
        text["MODE"] = self.mode
        text["NEXTDATA"] = str(self.next_data)
        text["BEGINANALYSIS"] = (
            str(self._analysis_start) if self._analysis_start is not None else "0"
        )
        text["ENDANALYSIS"] = (
            str(self._analysis_end) if self._analysis_end is not None else "0"
        )
        text["BEGINDATA"] = (
            str(self._data_start) if self._data_start is not None else "0"
        )
        text["ENDDATA"] = str(self._data_end) if self._data_end is not None else "0"
        text["BEGINSTEXT"] = (
            str(self._stext_start) if self._stext_start is not None else "0"
        )
        text["ENDSTEXT"] = str(self._stext_end) if self._stext_end is not None else "0"

        text["PAR"] = str(len(self.pnn))
        text["TOT"] = str(self.tot)

        for i, _ in enumerate(self.pnn):
            text["P%dB" % (i + 1)] = self.pnb
            text["P%dE" % (i + 1)] = self.pne
            text["P%dR" % (i + 1)] = str(int(self.pnr[i]))
            text["P%dN" % (i + 1)] = self.pnn[i]
            text["P%dS" % (i + 1)] = self.pns[i]

        if self._data_start is None and self._data_end is None:
            max_text_end = self.cal_max_text_ends(text, self.delim, self.text_start)
            datasize = 4 * len(self.pnn) * self.tot  # 4 is bytes to hold float
            data_start, data_end = self.cal_datapos(max_text_end + 1, datasize)
            text["BEGINDATA"] = data_start
            text["ENDDATA"] = data_end
        return text

    @property
    def data_start(self):
        return int(self.text["BEGINDATA"])

    @property
    def data_end(self):
        return int(self.text["ENDDATA"])

    @property
    def text_end(self):
        return len(self.dict_to_string(self.text, self.delim)) + self.text_start - 1

    @classmethod
    def cal_max_text_ends(cls, text, delim, text_start):
        s = cls.dict_to_string(
            {
                **text,
                "BEGINANALYSIS": "99999999",
                "ENDANALYSIS": "99999999",
                "BEGINDATA": "99999999",
                "ENDDATA": "99999999",
                "BEGINSTEXT": "99999999",
                "ENDSTEXT": "99999999",
            },
            delim,
        )
        return text_start + len(s) - 1

    def to_string(self):
        return self.dict_to_string(self.text, self.delim)

    def update_pns(self, mappings):
        for k, v in mappings.items():
            self.pns[self.pns.index(k)] = v
        self.text = self.build()

    def update_pnn(self, mappings):
        for k, v in mappings.items():
            self.pnn[self.pnn.index(k)] = v
        self.text = self.build()

    @classmethod
    def from_string(self, s):
        delim = s[:1]
        keyvalarray = s[1:].split(delim)
        for num, i in enumerate(keyvalarray):
            try:
                keyvalarray[num] = i.decode("UTF-8")
            except UnicodeDecodeError:
                # print(num, i)
                pass

        vars = {}
        for k, v in zip(keyvalarray[::2], keyvalarray[1::2]):
            vars[k[1:]] = v

        long_channels = list()
        short_channels = list()
        max_values = list()
        for n in range(int(vars.pop("PAR"))):
            short_channels.append(vars.pop("P%dN" % (n + 1)))
            long_channels.append(
                vars.pop("P%dS" % (n + 1)) if "P%dS" % (n + 1) in vars else " "
            )
            max_values.append(int(vars.pop("P%dR" % (n + 1))))

        return TextSegment(
            int(vars["TOT"]),
            short_channels,
            long_channels,
            max_values,
            mode=vars["MODE"],
            next_data=vars["NEXTDATA"],
            byte_order=vars["BYTEORD"],
            delim=delim.decode("UTF-8"),
            datatype=vars["DATATYPE"],
            data_start=vars["BEGINDATA"],
            data_end=vars["ENDDATA"],
            analysis_start=vars["BEGINANALYSIS"],
            analysis_end=vars["ENDANALYSIS"],
            stext_start=vars["BEGINSTEXT"],
            stext_end=vars["ENDSTEXT"],
        )

    @classmethod
    def dict_to_string(cls, dict_, delim):
        # print('convert', dict_)
        s = delim
        for i in dict_:
            # print(type(i), type(dict_[i]), type(delim), i, dict_[i])
            s += "$%s%s%s%s" % (i, delim, dict_[i], delim)
        return s

    @classmethod
    def cal_datapos(cls, textend, datasize):
        start = 0
        end = 0
        start_new = textend + 1
        end_new = start_new + datasize - 1

        while True:
            inc_start = len(str(start_new)) - len(str(start))
            inc_end = len(str(end_new)) - len(str(end))
            start = start_new
            end = end_new

            if inc_start + inc_end > 0:
                start_new = inc_start + inc_end + start
                end_new = start_new + datasize - 1
            else:
                break

        return start, end


class DataSegment:
    def __init__(
        self, values: np.ndarray, datatype, num_dims, num_rows, endian
    ) -> None:
        self.values = values
        self.datatype = datatype
        self.num_dims = num_dims
        self.num_rows = num_rows
        self.endian = endian

    def to_string(self):
        format_ = self.endian + self.datatype.lower()
        return self.values.astype(format_).tobytes()

    @classmethod
    def from_string(cls, s: str, datatype, num_dims, num_rows, endian):
        data = BytesIO(s)
        format_ = endian + str(num_dims) + datatype.lower()
        datasize = struct.calcsize(format_)
        events = []
        for e in range(num_rows):
            read_data = data.read(datasize)
            event = struct.unpack(format_, read_data)
            events.append(event)
        values = np.array(events, dtype=np.float32 if datatype == "F" else np.float64)
        return DataSegment(values, datatype, num_dims, num_rows, endian)


class Fcs:
    def __init__(
        self,
        values: np.ndarray,
        short_channels: list,
        long_channels: list = None,
        ver: str = "FCS3.1",
        mode: str = "L",
        byte_order: str = "1,2,3,4",
        text_start: int = 256,
        datatype: str = "F",
    ) -> None:
        self.values = values
        self.short_channels = short_channels
        if long_channels is not None:
            self.long_channels = long_channels
        else:
            self.long_channels = [" " for _ in range(len(short_channels))]
        self.ver = ver
        self.mode = mode
        self.byte_order = byte_order

        self.tseg = TextSegment(
            values.shape[0],
            self.short_channels,
            self.long_channels,
            values.max(axis=0),
            mode=mode,
            byte_order=byte_order,
            text_start=text_start,
            datatype=datatype,
        )

        self.hseg = HeaderSegment(
            self.tseg.text_start,
            self.tseg.text_end,
            self.tseg.data_start,
            self.tseg.data_end,
            ver=self.ver,
        )

        self.dseg = DataSegment(
            values, datatype, values.shape[1], values.shape[0], self.tseg.endian
        )

    @classmethod
    @bufferize
    def from_file(cls, filepath_or_buffer):
        header = HeaderSegment.from_string(filepath_or_buffer.read(58))
        filepath_or_buffer.seek(header.text_start)
        fseg = TextSegment.from_string(
            filepath_or_buffer.read(header.text_end - header.text_start + 1)
        )
        data_start = header.data_start if header.data_start != 0 else fseg.data_start
        data_end = header.data_end if header.data_end != 0 else fseg.data_end
        filepath_or_buffer.seek(data_start)
        data = DataSegment.from_string(
            filepath_or_buffer.read(data_end - data_start + 1),
            fseg.datatype,
            len(fseg.pnn),
            fseg.tot,
            fseg.endian,
        )

        return Fcs(data.values, fseg.pnn, fseg.pns)

    @classmethod
    @bufferize
    def read_data_segment(cls, filepath_or_buffer, hseg, tseg):
        data_start = hseg.data_start if hseg.data_start != 0 else tseg.data_start
        data_end = hseg.data_end if hseg.data_end != 0 else tseg.data_end
        filepath_or_buffer.seek(data_start)
        return DataSegment.from_string(
            filepath_or_buffer.read(data_end - data_start + 1),
            tseg.datatype,
            len(tseg.pnn),
            tseg.tot,
            tseg.endian,
        )

    @classmethod
    @bufferize
    def read_header_segment(cls, filepath_or_buffer):
        filepath_or_buffer.seek(0)
        return HeaderSegment.from_string(filepath_or_buffer.read(58))

    @classmethod
    @bufferize
    def read_text_segment(cls, filepath_or_buffer):
        header = HeaderSegment.from_string(filepath_or_buffer.read(58))
        filepath_or_buffer.seek(header.text_start)
        fseg = TextSegment.from_string(
            filepath_or_buffer.read(header.text_end - header.text_start + 1)
        )

        return fseg

    @classmethod
    def write_bytes(cls, f, s):
        if not type(s) == bytes:
            f.write(s.encode("UTF-8"))
        else:
            f.write(s)

    @classmethod
    @bufferize(mode="rb+")
    def write_text_segment(cls, filepath_or_buffer, text_segment):
        filepath_or_buffer.seek(58)
        cls.write_bytes(
            filepath_or_buffer,
            " " * (text_segment.text_start - filepath_or_buffer.tell()),
        )
        cls.write_bytes(filepath_or_buffer, text_segment.to_string())
        cls.write_bytes(
            filepath_or_buffer,
            " " * (text_segment.data_start - filepath_or_buffer.tell()),
        )

    @classmethod
    @bufferize(mode="rb+")
    def write_header_segment(cls, filepath_or_buffer, header_segment):
        filepath_or_buffer.seek(0)
        cls.write_bytes(filepath_or_buffer, header_segment.to_string())

    @bufferize(mode="wb")
    def export(self, filepath_or_buffer):
        self.write_bytes(filepath_or_buffer, self.hseg.to_string())
        self.write_text_segment(filepath_or_buffer, self.tseg)
        self.write_bytes(filepath_or_buffer, self.dseg.to_string())

    @property
    def count(self):
        return self.tseg.tot

class DataFrame(pd.DataFrame):
    @property
    def _constructor(self):
        return DataFrame

    def to_fcs(self, filepath_or_buffer: Union[str]):

        """
        write fcs.

        :param filepath_or_buffer:
            String, or file-like object implementing a ``write()`` function.
            The string could be a s3 url with the format:
            ``s3://{bucket}/{key}``.
        :type param filepath_or_buffer: str or file-like object
        """

        long_channels = None
        if isinstance(self.columns, pd.MultiIndex):
            short_channels = self.columns.get_level_values("short").values
            long_channels = self.columns.get_level_values("long").values
        else:
            short_channels = self.columns

        Fcs(self.values, short_channels, long_channels).export(filepath_or_buffer)

    @classmethod
    def from_fcs(
        cls, filepath_or_buffer: Union[str], channel_type: str = "short"
    ):
        """
        Read dataframe from fcs.

        :param filepath_or_buffer: str or file-like object.
            String, or file-like object implementing a ``read()`` function.
            The string could be a s3 url with the format:
            ``s3://{bucket}/{key}``.
        :type filepath_or_buffer: str or file-like object
        :param channel_type: {"short", "long", "multi"}, defaults to "short".
            "short" and "long" refer to short ($PnN) and long ($PnS) name of parameter n, respectively.
            See FCS3.1 data standard for detailed explanation.
        :type channel_type: str, optional
        :return: the dataframe contains the fcs channels and data
        :rtype: DataFrame
        """

        fcs = Fcs.from_file(filepath_or_buffer)
        colmap = {
            "short": fcs.short_channels,
            "long": fcs.long_channels,
            "multi": pd.MultiIndex.from_tuples(
                list(zip(fcs.short_channels, fcs.long_channels)),
                names=["short", "long"],
            ),
        }
        return DataFrame(fcs.values, columns=colmap[channel_type])