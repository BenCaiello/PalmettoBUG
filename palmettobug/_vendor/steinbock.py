'''
This module is a copy of steinbock functions used in PalmettoBUG. They are not directly imported because of a desire to reduce the number of 
imports and because of possible licensing conflicts (deepcell is not GPL compatible). 

While the project as a whole is licensed under the GPL3 license, the code contained in this file is directly copied / derived from a GPL compatible, 
permissively licensed project:

This code is directly copied from Steinbock (https://github.com/BodenmillerGroup/steinbock), with a few edits to "unhook" them from the rest of 
the package.

The code here is from the following files of Steinbock -- (date of copying not recalled precisely, but between March 2024 and August 2024):

    steinbock.segmentation.deepcell     (removed 9-5-2024 for possible GPL-license technicalities [separate program handling non-commercial licensed code from GPL main body])

    steinbock.measurement.intensities 

    steinbock.measurement.regionprops

    steinbock.measurement.neighbors     (removed 8-28-24)

    steinbock.preprocessing.imc

    steinbock.io


Edits:  --> removed mmap reading code (my program will not ever use that format, I think)
--> Removed the io.dtype calls in some of the np.array set ups --> replaced with simple dtype calls (astype / dtype --> 'int')
--> removed special Steinbock______Exceptions, and left them as plain Exceptions
--> In concatenating the files listed above, and removed redundant and unused code / imports
--> in the code taken from the io module (just the first two functions --> removed dtype & special exceptions)
--> add __all__ for docs

Edit 8/28/24 ---> removing code from steinbock.measurement.neighbors (not needed anymore in the program)

EDIT 2-7-2025 --> removed unused MCD / TXT file reading code, and some unused imports (including parst of readimc import), and Annotation typing from readimc
EDIT 3-25-25 --> fix import of MCDFile (from vendored readimc, not python package readimc)

Reasons: disconnect the files listed above from all other modules of steinbock.

Steinbock License: MIT license -->

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

'''
__all__ = []
import logging
from enum import Enum
from functools import partial
from os import PathLike
from pathlib import Path
import numpy as np
import pandas as pd
import scipy.ndimage
from scipy.ndimage import maximum_filter
from skimage.measure import regionprops_table
from typing import (
    Any,
    Dict,
    List,
    Generator,
    Optional,
    Sequence,
    Tuple,
    Union,
)
import tifffile as tf
from tempfile import TemporaryDirectory
from zipfile import ZipFile

#try:
from .readimc import MCDFile
    # from readimc.data import Acquisition
#    imc_available = True
#except Exception:
#    imc_available = False

__all__ = []

def _fix_image_shape(img_file: Union[str, PathLike], img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        img = img[np.newaxis, :, :]
    elif img.ndim == 4:
        if img.shape[-1] == 1:
            img = img[:, :, :, 0]
        elif img.shape[0] == 1:
            img = img[0, :, :, :]
        else:
            raise Exception(
                f"{img_file}: unsupported four-dimensional shape {img.shape}"
            )
    elif img.ndim == 5:
        size_t, size_z, size_c, size_y, size_x = img.shape
        if size_t != 1 or size_z != 1:
            raise Exception(
                f"{img_file}: unsupported TZCYX shape {img.shape}"
            )
        img = img[0, 0, :, :, :]
    elif img.ndim == 6:
        size_t, size_z, size_c, size_y, size_x, size_s = img.shape
        if size_t != 1 or size_z != 1 or size_s != 1:
            raise Exception(
                f"{img_file}: unsupported TZCYXS shape {img.shape}"
            )
        img = img[0, 0, :, :, :, 0]
    elif img.ndim != 3:
        raise Exception(
            f"{img_file}: unsupported number of dimensions ({img.ndim})"
        )
    return img

def read_image(
    img_file: Union[str, PathLike],
    native_dtype: bool = False,
) -> np.ndarray:
    img = tf.imread(img_file, squeeze=False)
    img = _fix_image_shape(img_file, img)
    return img

logger = logging.getLogger(__name__)

def _get_zip_file_member(path: Union[str, PathLike]) -> Optional[Tuple[Path, str]]:
    for parent_path in Path(path).parents:
        if parent_path.suffix == ".zip" and parent_path.is_file():
            member_path = Path(path).relative_to(parent_path)
            return parent_path, str(member_path)
    return None


def list_mcd_files(mcd_dir: Union[str, PathLike], unzip: bool = False) -> List[Path]:
    mcd_files = sorted(Path(mcd_dir).rglob("[!.]*.mcd"))
    if unzip:
        for zip_file in sorted(Path(mcd_dir).rglob("[!.]*.zip")):
            with ZipFile(zip_file) as fzip:
                for zip_info in sorted(fzip.infolist(), key=lambda x: x.filename):
                    if not zip_info.is_dir() and zip_info.filename.endswith(".mcd"):
                        mcd_files.append(zip_file / zip_info.filename)
    return mcd_files


def list_txt_files(txt_dir: Union[str, PathLike], unzip: bool = False) -> List[Path]:
    txt_files = sorted(Path(txt_dir).rglob("[!.]*.txt"))
    if unzip:
        for zip_file in sorted(Path(txt_dir).rglob("[!.]*.zip")):
            with ZipFile(zip_file) as fzip:
                for zip_info in sorted(fzip.infolist(), key=lambda x: x.filename):
                    if not zip_info.is_dir() and zip_info.filename.endswith(".txt"):
                        txt_files.append(zip_file / zip_info.filename)
    return txt_files


def _clean_panel(panel: pd.DataFrame) -> pd.DataFrame:
    panel.sort_values(
        "channel",
        key=lambda s: pd.to_numeric(s.str.replace("[^0-9]", "", regex=True)),
        inplace=True,
    )
    name_dupl_mask = panel["name"].duplicated(keep=False)
    name_suffixes = panel.groupby("name").cumcount().map(lambda i: f" {i + 1}")
    panel.loc[name_dupl_mask, "name"] += name_suffixes[name_dupl_mask]
    if "keep" not in panel:
        panel["keep"] = pd.Series([True] * len(panel.index), dtype=pd.BooleanDtype())
    if "ilastik" not in panel:
        panel["ilastik"] = pd.Series(dtype=pd.UInt8Dtype())
        panel.loc[panel["keep"], "ilastik"] = range(1, panel["keep"].sum() + 1)
    if "deepcell" not in panel:
        panel["deepcell"] = pd.Series(dtype=pd.UInt8Dtype())
    if "cellpose" not in panel:
        panel["cellpose"] = pd.Series(dtype=pd.UInt8Dtype())
    next_column_index = 0
    for column in ("channel", "name", "keep", "ilastik", "deepcell", "cellpose"):
        if column in panel:
            column_data = panel[column]
            panel.drop(columns=[column], inplace=True)
            panel.insert(next_column_index, column, column_data)
            next_column_index += 1
    return panel


def create_panel_from_imc_panel(
    imc_panel_file: Union[str, PathLike],
    imc_panel_channel_col: str = "Metal Tag",
    imc_panel_name_col: str = "Target",
    imc_panel_keep_col: str = "full",
    imc_panel_ilastik_col: str = "ilastik",
) -> pd.DataFrame:
    imc_panel = pd.read_csv(
        imc_panel_file,
        sep=",|;",
        dtype={
            imc_panel_channel_col: pd.StringDtype(),
            imc_panel_name_col: pd.StringDtype(),
            imc_panel_keep_col: pd.BooleanDtype(),
            imc_panel_ilastik_col: pd.BooleanDtype(),
        },
        engine="python",
        true_values=["1"],
        false_values=["0"],
    )
    for required_col in (imc_panel_channel_col, imc_panel_name_col):
        if required_col not in imc_panel:
            raise Exception(
                f"Missing '{required_col}' column in IMC panel"
            )
    for notnan_col in (
        imc_panel_channel_col,
        imc_panel_keep_col,
        imc_panel_ilastik_col,
    ):
        if notnan_col in imc_panel and imc_panel[notnan_col].isna().any():
            raise Exception(
                f"Missing values for '{notnan_col}' in IMC panel"
            )
    rename_columns = {
        imc_panel_channel_col: "channel",
        imc_panel_name_col: "name",
        imc_panel_keep_col: "keep",
        imc_panel_ilastik_col: "ilastik",
    }
    drop_columns = [
        panel_col
        for imc_panel_col, panel_col in rename_columns.items()
        if panel_col in imc_panel.columns and panel_col != imc_panel_col
    ]
    panel = imc_panel.drop(columns=drop_columns).rename(columns=rename_columns)
    for _, g in panel.groupby("channel"):
        panel.loc[g.index, "name"] = " / ".join(g["name"].dropna().unique())
        if "keep" in panel:
            panel.loc[g.index, "keep"] = g["keep"].any()
        if "ilastik" in panel:
            panel.loc[g.index, "ilastik"] = g["ilastik"].any()
    panel = panel.groupby(panel["channel"].values).aggregate("first")
    panel = _clean_panel(panel)  # ilastik column may be nullable uint8 now
    ilastik_mask = panel["ilastik"].fillna(False).astype(bool)
    panel["ilastik"] = pd.Series(dtype=pd.UInt8Dtype())
    panel.loc[ilastik_mask, "ilastik"] = range(1, ilastik_mask.sum() + 1)
    return panel

def create_panels_from_mcd_file(mcd_file: Union[str, PathLike]) -> List[pd.DataFrame]:
    panels = []
    with MCDFile(mcd_file) as f:
        for slide in f.slides:
            for acquisition in slide.acquisitions:
                panel = pd.DataFrame(
                    data={
                        "channel": pd.Series(
                            data=acquisition.channel_names,
                            dtype=pd.StringDtype(),
                        ),
                        "name": pd.Series(
                            data=acquisition.channel_labels,
                            dtype=pd.StringDtype(),
                        ),
                    },
                )
                panels.append(panel)
    return panels


def create_panel_from_mcd_files(
    mcd_files: Sequence[Union[str, PathLike]], unzip: bool = False
) -> pd.DataFrame:
    panels = []
    for mcd_file in mcd_files:
        zip_file_mcd_member = _get_zip_file_member(mcd_file)
        if zip_file_mcd_member is None:
            panels += create_panels_from_mcd_file(mcd_file)
        elif unzip:
            zip_file, mcd_member = zip_file_mcd_member
            with ZipFile(zip_file) as fzip:
                with TemporaryDirectory() as temp_dir:
                    extracted_mcd_file = fzip.extract(mcd_member, path=temp_dir)
                    panels += create_panels_from_mcd_file(extracted_mcd_file)
    panel = pd.concat(panels, ignore_index=True, copy=False)
    panel.drop_duplicates(inplace=True, ignore_index=True)
    return _clean_panel(panel)

def create_image_info(
    mcd_txt_file: Union[str, PathLike],
    acquisition,                   # removed 2-7-25   (type annotation): Optional[Acquisition]
    img: np.ndarray,
    recovery_file: Union[str, PathLike, None],
    recovered: bool,
    img_file: Union[str, PathLike],
) -> Dict[str, Any]:
    recovery_file_name = None
    if recovery_file is not None:
        recovery_file_name = Path(recovery_file).name
    image_info_row = {
        "image": Path(img_file).name,
        "width_px": img.shape[2],
        "height_px": img.shape[1],
        "num_channels": img.shape[0],
        "source_file": Path(mcd_txt_file).name,
        "recovery_file": recovery_file_name,
        "recovered": recovered,
    }
    if acquisition is not None:
        image_info_row.update(
            {
                "acquisition_id": acquisition.id,
                "acquisition_description": acquisition.description,
                "acquisition_start_x_um": (acquisition.roi_points_um[0][0]),
                "acquisition_start_y_um": (acquisition.roi_points_um[0][1]),
                "acquisition_end_x_um": (acquisition.roi_points_um[2][0]),
                "acquisition_end_y_um": (acquisition.roi_points_um[2][1]),
                "acquisition_width_um": acquisition.width_um,
                "acquisition_height_um": acquisition.height_um,
            }
        )
    return image_info_row

def filter_hot_pixels(img: np.ndarray, thres: float) -> np.ndarray:
    ### Editing for 2D arrays 1-9-24 ###
    if len(img.shape) == 3:
        kernel = np.ones((1, 3, 3), dtype=bool)
        kernel[0, 1, 1] = False
    elif len(img.shape) == 2:
        kernel = np.ones((3, 3), dtype=bool)
        kernel[1, 1] = False
    max_neighbor_img = maximum_filter(img, footprint=kernel, mode="mirror")
    return np.where(img - max_neighbor_img > thres, max_neighbor_img, img)

def preprocess_image(img: np.ndarray, hpf: Optional[float] = None) -> np.ndarray:
    img = img.astype(np.float32)
    if hpf is not None:
        img = filter_hot_pixels(img, hpf)
    return img  ### removed to_dtype call

def measure_regionprops(
    img: np.ndarray, mask: np.ndarray, skimage_regionprops: Sequence[str]
) -> pd.DataFrame:
    skimage_regionprops = list(skimage_regionprops)
    if "label" not in skimage_regionprops:
        skimage_regionprops.insert(0, "label")
    data = regionprops_table(
        mask.T.squeeze(),    ## formerly just mask
        intensity_image=img.T,  ## formerly np.moveaxis(img, 0, -1)
        properties=skimage_regionprops,
    )
    object_ids = data.pop("label")
    return pd.DataFrame(
        data=data,
        index=pd.Index(object_ids, dtype = 'int32', name="Object"),   ## removed dtype assignment
    )

def try_measure_regionprops_from_disk(
    img_files: Sequence[Union[str, PathLike]],
    mask_files: Sequence[Union[str, PathLike]],
    skimage_regionprops: Sequence[str],
    mmap: bool = False,
) -> Generator[Tuple[Path, Path, pd.DataFrame], None, None]:
    for img_file, mask_file in zip(img_files, mask_files):
        try:
            img = read_image(img_file)
            mask = read_image(mask_file).astype('int')
            regionprops = measure_regionprops(img, mask, skimage_regionprops)
            del img, mask
            yield Path(img_file), Path(mask_file), regionprops
            del regionprops
        except Exception as e:
            logger.exception(f"Error measuring regionprops in {img_file}: {e}")

##>>##

class IntensityAggregation(Enum):
    SUM = partial(scipy.ndimage.sum_labels)
    MIN = partial(scipy.ndimage.minimum)
    MAX = partial(scipy.ndimage.maximum)
    MEAN = partial(scipy.ndimage.mean)
    MEDIAN = partial(scipy.ndimage.median)
    STD = partial(scipy.ndimage.standard_deviation)
    VAR = partial(scipy.ndimage.variance)

def measure_intensites(
    img: np.ndarray,
    mask: np.ndarray,
    channel_names: Sequence[str],
    intensity_aggregation: IntensityAggregation,
) -> pd.DataFrame:
    object_ids = np.unique(mask[mask != 0])
    data = {
        channel_name: intensity_aggregation.value(img[i], labels=mask, index=object_ids)
        for i, channel_name in enumerate(channel_names)
    }
    return pd.DataFrame(
        data=data,
        index=pd.Index(object_ids, name="Object"),     ##### removed a (dtype =  io.maskdtype) call
    )


def try_measure_intensities_from_disk(
    img_files: Sequence[Union[str, PathLike]],
    mask_files: Sequence[Union[str, PathLike]],
    channel_names: Sequence[str],
    intensity_aggregation: IntensityAggregation,
    mmap: bool = False,
) -> Generator[Tuple[Path, Path, pd.DataFrame], None, None]:
    for img_file, mask_file in zip(img_files, mask_files):
        try:
            img = read_image(img_file)
            mask = read_image(mask_file).astype('int')
            intensities = measure_intensites(
                img, mask, channel_names, intensity_aggregation
            )
            del img, mask
            yield Path(img_file), Path(mask_file), intensities
            del intensities
        except Exception as e:
            logger.exception(f"Error measuring intensities in {img_file}: {e}")

##>>##

# as this is now handled by the separate cellpose / deepcell handling program / library it is no longer necessary to keep this code:
# it also means that the code can remain separate from any non-GPL compatible licenses (aka., deepcell / cellpose non-commercial licenses)
'''
if TYPE_CHECKING:
    from tensorflow.keras.models import Model  # type: ignore

# deepcell_available = find_spec("deepcell") is not None
def _mesmer_application(model=None):
    #from deepcell.applications import Mesmer
    from simpledeepcell.main import Mesmer # type: ignore

    app = Mesmer(model=model)

    def predict(
        img: np.ndarray,
        *,
        pixel_size_um: Optional[float] = None,
        segmentation_type: Optional[str] = None,
        preprocess_kwargs: Optional[Mapping[str, Any]] = None,
        postprocess_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> np.ndarray:
        #assert img.ndim == 3
        if pixel_size_um is None:
            raise Exception("Unknown pixel size")
        if segmentation_type is None:
            raise Exception("Unknown segmentation type")
        mask = app.predict(
            np.expand_dims(np.moveaxis(img, 0, -1), 0),
            batch_size=1,
            image_mpp=pixel_size_um,
            compartment=segmentation_type,
            preprocess_kwargs=preprocess_kwargs or {},
            postprocess_kwargs_whole_cell=postprocess_kwargs or {},
            postprocess_kwargs_nuclear=postprocess_kwargs or {},
        )[0, :, :, 0]
        #assert mask.shape == img.shape[1:]
        return mask

    return app, predict


class Application(Enum):
    MESMER = partial(_mesmer_application)

class AggregationFunction(Protocol):
    def __call__(self, img: np.ndarray, axis: Optional[int] = None) -> np.ndarray:
        ...

def create_segmentation_stack(
    img: np.ndarray,
    channelwise_minmax: bool = False,
    channelwise_zscore: bool = False,
    channel_groups: Optional[np.ndarray] = None,
    aggr_func: AggregationFunction = np.mean,
) -> np.ndarray:
    if channelwise_minmax:
        channel_mins = np.nanmin(img, axis=(1, 2))
        channel_maxs = np.nanmax(img, axis=(1, 2))
        channel_ranges = channel_maxs - channel_mins
        img -= channel_mins[:, np.newaxis, np.newaxis]
        img[channel_ranges > 0] /= channel_ranges[
            channel_ranges > 0, np.newaxis, np.newaxis
        ]
    if channelwise_zscore:
        channel_means = np.nanmean(img, axis=(1, 2))
        channel_stds = np.nanstd(img, axis=(1, 2))
        img -= channel_means[:, np.newaxis, np.newaxis]
        img[channel_stds > 0] /= channel_stds[channel_stds > 0, np.newaxis, np.newaxis]
    if channel_groups is not None:
        img = np.stack(
            [
                aggr_func(img[channel_groups == channel_group], axis=0)
                for channel_group in np.unique(channel_groups)
                if not np.isnan(channel_group)
            ]
        )
    return img

def try_segment_objects(
    img_files: Sequence[Union[str, PathLike]],
    application: Application,
    model: Optional["Model"] = None,
    channelwise_minmax: bool = False,
    channelwise_zscore: bool = False,
    channel_groups: Optional[np.ndarray] = None,
    aggr_func: AggregationFunction = np.mean,
    **predict_kwargs,
) -> Generator[Tuple[Path, np.ndarray], None, None]:
    app, predict = application.value(model=model)
    for img_file in img_files:
        try:
            img = create_segmentation_stack(
                read_image(img_file),
                channelwise_minmax=channelwise_minmax,
                channelwise_zscore=channelwise_zscore,
                channel_groups=channel_groups,
                aggr_func=aggr_func,
            )
            if img.shape[0] != 2:
                raise Exception(
                    f"Invalid number of aggregated channels: "
                    f"expected 2, got {img.shape[0]}"
                )
            mask = predict(img, **predict_kwargs)
            yield Path(img_file), mask
            del img, mask
        except Exception as e:
            logger.exception(f"Error segmenting objects in {img_file}: {e}")

'''