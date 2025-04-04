'''
This module contains the classes / functions used in the back-end of image processing (its front end is the second tab of the program).

Many classes / functions in this file are available in the public (non-GUI) API of PalmettoBUG.



While the PalmettoBUG project as a whole is licensed under the GPL3 license, including this file, portions of this file ::

        {  functions marked with >>>> # ****stein_derived (notes)  }
                                                       
are derivative / partially copy&paste with modification from the steinbock package (Copyright University of Zurich, 2021, MIT license)
additionally the "Steinbock_Unhooked" module that is loaded into this script is ENTIRELY composed of modified steinbock package code

additionally, throughout the design of this script, concepts / structures from CATALYST (https://github.com/HelenaLC/CATALYST/tree/main) 
and steinbock are used, such as the panel / metadata file structures, column names, usage, etc.
'''

import os
import warnings
from typing import Union
from pathlib import Path
import tkinter as tk

import customtkinter as ctk
import skimage
# from cellpose import denoise, models                                              
import tifffile as tf
import pandas as pd
import numpy as np

from .._vendor import readimc
from .._vendor.fcsy import DataFrame
from .._vendor import fcsparser
from .._vendor import pyometiff as pot

from .._vendor import steinbock as stein_unhook 
from ..Utils.sharedClasses import DirSetup, TableLaunch, Analysis_logger, Project_logger, warning_window  

'''
try:
    import navis as nv       ### currently, there is an error in navis on small meshes (I think?) so recommend to not use this  TODO: reactivate once fixed?
except Exception:
    pass
'''

__all__ = ["ImageAnalysis", 
            "mask_expand", 
            "imc_entrypoint", 
            "read_txt_file",
            "txt_folder_to_tiff_folder",
            "setup_for_FCS"]

_in_gui = False
def toggle_in_gui():
    global _in_gui
    _in_gui = not _in_gui
    return _in_gui

def _my_auto_hpf(image: np.ndarray[float], hpf: float = 0.75):
    '''
    Assumes the image's channels are in the first layer of the numpy array
    '''
    for ii,i in enumerate(image):
        hpf_threshold = np.quantile(i, hpf)
        #print(hpf_threshold)
        image[ii,:,:] = stein_unhook.filter_hot_pixels(i,hpf_threshold)
        
    return image

def imc_entrypoint(directory: Union[Path, str], 
                   resolutions: list[float] = [1.0,1.0], 
                   from_mcds: bool = True,
                   ) -> "ImageAnalysis":
    '''
    This function is the entrypoint for a project using MCDs or TIFFs. It initializes and return an ImageAnalysis object using the 
    arguments passed in by the user.

    Args:
        directory (Path or string): 
            This is the path to a folder containing a subfolder /raw with either .tiff or .mcd files inside it

        resolutions (iterable of length two: float, float): 
            This is the [X, Y] resolutions of the images in micrometers / pixel. 
            The default is 1.0 microns / pixels for both dimensions, as has been usual for IMC. 

        from_mcds (boolean): 
            whether the /raw subfolder contains .mcd files (= True) or .tiff files (= False)
    '''
    directory = str(directory)
    try:
        resolutions[0] = float(resolutions[0])
        resolutions[1] = float(resolutions[1])
    except ValueError:
        print("Resolution X / Y must be numbers!")
        return
    directory = directory.replace("\\","/") 
    try:
        experiment = ImageAnalysis(directory, resolutions, from_mcds = from_mcds)
    except Exception as e:
        print(e)
        if from_mcds:
            if _in_gui:
                tk.messagebox.showwarning("Warning!", message = "Are you sure there are .mcd files in the 'raw' folder of your directory? \n" 
                            "Error in generating directory structure and preliminary panel file")
                return
            else:
                print("Are you sure there are .mcd files in the 'raw' folder of your directory? \n" 
                    "Error in generating directory structure and preliminary panel file")
                return 
             
        elif not from_mcds:
            if _in_gui:
                tk.messagebox.showwarning("Warning!", message = "Are you sure there are image files in the 'img' folder of your directory? \n" 
                        "Error in generating directory structure and preliminary panel file")
                return
            else:
                print("Are you sure there are image files in the 'img' folder of your directory? \n" 
                    "Error in generating directory structure and preliminary panel file")
                return      
    
    experiment.directory_object.makedirs()
    return experiment

def read_txt_file(path, num_meta_data_columns = 6):
    '''
    Reads a single txt file (these are backups for if mcd files become corrupted).

    Assumes that the txt file itself is not corrupted & has six [Arg: num_meta_data_columns] metadata columns before the channels.
    Also assumes a complete file with X / Y columns, whose values accurately correspond to the X / Y of the image to be generated. 
    '''
    image_df = pd.read_csv(str(path), delimiter = "\t")
    image_channels_only = image_df.iloc[:,num_meta_data_columns:]
    image_array = np.array(image_channels_only).reshape([image_df['X'].max() + 1,
                                                         image_df['Y'].max() + 1, 
                                                         len(image_channels_only.columns)])
    image_array = image_array.transpose([2,0,1])
    return image_array

def txt_folder_to_tiff_folder(txt_folder: Union[Path, str], 
                              tiff_folder: Union[Path, str],
                              panel: pd.DataFrame, 
                              hpf: Union[float, int] = 50, 
                              ome_tiff_metadata: bool = False, 
                              resolutions: list[float] = [1.0,1.0], 
                              ) -> None:
    '''
    Iteratively runs read_txt_file() on each file in a directory, and output .ome.tiffs (at least by file extension) to an output directory.

    To actually generate ometiff metadata to be included with the images, two things must occur:

        1. ome_tiff_metadata == True

        2. Resolutions Argument must be provided (default is 1 micrometer/pixel in both X an Y)

    Args:
        txt_folder (Path or str): 
            the path to a folder where the .txt files to be converted are. Assumes only .txt files are inside this folder

        tiff_folder (Path or str): 
            the path to the folder where the output .ome.tiff files will be written

        panel (pandas DataFrame): 
            the panel file. Used to filter out undesirable channels & construct ometiff metadata

        hpf (integer >= 0): 
            whether to run hot pixel filtering (if hpf != 0) and if hpf is run what threshold to use. 

        ome_tiff_metadata (boolean): 
            whether to generate metadata for the ome.tiff -- this does not change the output extension name, which will always be .ome.tiff, but 
            does determine whether the function will attempt to add metadata to the files. If True, then the resolutions argument must be provided, or an error will occur. 

        resolutions (list of two floats > 0): 
            the resolution of the images in X and Y dimensions, in micrometers per pixel. Only used if ome_tiff_metadata == True. 

    Inputs / Outputs:
        Inputs: 
            reads each file inside txt_folder (expecting all to be .txt files of the format exported during IMC as backups of .mcd files. )

        Outputs: 
            writes an .ome.tiff file in tiff_folder for each .txt file read in from txt_folder
    '''
    txt_folder = str(txt_folder)
    tiff_folder = str(tiff_folder)
    txt_files = ["".join([txt_folder, "/", i]) for i in sorted(os.listdir(txt_folder))]
    tiff_files_out = ["".join([tiff_folder, "/", i.rstrip("txt"),"ome.tiff"]) for i in sorted(os.listdir(txt_folder))]
    img_slicer = (panel['keep'] == 1)
    for i,ii in zip(txt_files, tiff_files_out):
        image = read_txt_file(i)[img_slicer,:,:]
        if (hpf > 0) and (hpf < 1):
            image = _my_auto_hpf(image, hpf)
        elif hpf != 0:
            image = stein_unhook.filter_hot_pixels(image,hpf)
        if ome_tiff_metadata:
            ome_metadata = _generate_ome_tiff_metadata(output_directory = ii[:-9],
                                                       filename = ii[ii.rfind("/") + 1:], 
                                                       resolutions = resolutions, 
                                                       panel_csv = panel,
                                                       )
            write_ome_tiff(image, ome_metadata, ii)
        else:
            tf.imwrite(ii, image)

def launch_denoise_seg_program(directory: Union[Path, str], 
                               resolutions: list[float] = [1.0, 1.0],
                               ) -> None:
    '''
    This launches the 'isoSegDenoise' sister program, with the provided directory pre-loaded.

    Args:
        directory (str or Path): 
            the directory to launch isoSegDenoise inside of

        resolutions (list of two floats > 0): 
            the resolution of the images in X and Y dimensions, in micrometers per pixel.
    '''
    directory = str(directory)
    if not os.path.exists(directory):
        return
    res1 = float(resolutions[0])
    res2 = float(resolutions[1])
    import subprocess
    try:
        subprocess.run(['segdenoise','-d', f'{directory}', '-r1', f'{str(res1)}', '-r2', f'{str(res2)}'])
        # Useful discussion for switching from shell = True to shell = False & using list[str] instead of string (as I had originally done)
        #       https://stackoverflow.com/questions/3172470/actual-meaning-of-shell-true-in-subprocess
    except Exception:
        print("Error in launching the Segmentation / Denoising process")

def _MCD_Generator(MCD_list: list[Path]):   # ****stein_derived 
                                            # (a substantially sipmlified / stripped down version of 
                                            #       steinbock.preprocessing.imc._try_preprocess_mcd_images_from_disk)
    '''
    A much simplified MCD reader compared to steinbock's, simiarly based on readimc.
    This is a helper function for when converting /raw folder MCDs to .ome.tiffs in the /img folder
    '''
    for i in MCD_list:
        with readimc.MCDFile(i) as mcd:
            for j in mcd.slides:
                for k in j.acquisitions:
                    try:
                        image = mcd.read_acquisition(k)
                        path = i
                        ROI = k.description
                        yield image, path, ROI, k
                    except Exception:
                        print(f"A ROI in the following MCD: \n {str(i)} \n failed to read!")

def _TIFF_Generator(TIFF_list: list[Path]):   # ****stein_derived 
                                                # (ish -- only in the sense of its structure: 
                                                # similar input, output, and generator design as _MCD_Generator)
    '''
    Similar to _MCD_Generator() above, this function is a helper for when converting from /raw folder Tiffs --> .ome.tiffs in the /img folder
    '''
    for i in TIFF_list:
        i = str(i)
        reader =  pot.OMETIFFReader(i)
        img_array, metadata, xml_metadata = reader.read()
        path = i[:i.rfind("/")]
        ROI = i[i.rfind("/"):]
        yield img_array, path, ROI, metadata

def _generate_ome_tiff_metadata(panel_csv: pd.DataFrame, 
                                output_directory: str, 
                                filename: str, 
                                resolutions: list[float],
                                ) -> dict:
    '''
    Generates .ome.tiff metadata for writing to .ome.tiff file type. (Helper function when converting from MCDs --> .ome.tiffs)
    
    Requires the panel_csv, an image, the output directory (like directory + '/img') and the file name
    The file name should not have the entire directory nor the suffix (as in, "C:/whatever/path/" and ".mcd" should NOT be included).
    The image should have the following order of dimensions: channels, Y, X (at least for current implementation, 
    update to be accurate after testing).

    resolutions are length per pixel in X and Y direstions (in uM)

    The fields chosen for the metadata were taken from a .ome.tiff file with multi-channels, 
    from a publicly available IMC experiment on Zenodo (should be: https://zenodo.org/records/8023452,
    Or perhaps instead was a tumor-sphere dataset from the Bodenmiller group [find] TODO). 
    '''
    ome_metadata = {}
    ome_metadata['Directory'] = str(output_directory)
    ome_metadata['Filename'] = filename
    ome_metadata['Extension'] = 'ome.tiff'
    ome_metadata['ImageType'] = 'ometiff'
    ome_metadata["PhysicalSizeX"] = resolutions[0]
    ome_metadata["PhysicalSizeXUnit"] = "micrometer"
    ome_metadata["PhysicalSizeY"] = resolutions[1]
    ome_metadata["PhysicalSizeYUnit"] = "micrometer"
    panel_csv = panel_csv[panel_csv['keep'] == 1].reset_index()
    channel_dict = {}
    for i,ii in enumerate(panel_csv['name']):
        channel_dict[ii] = {'Name':ii,'ID':str(i),'Fluor':str(panel_csv['channel'][i])}
    ome_metadata['Channels'] = channel_dict
    return ome_metadata

## originally made to test concurrent futures multi-threading of the I/O tasks. Turns out, multi-threading is quite inefficient....
def write_ome_tiff(image, ome_tiff_metadata, file_path) -> None:
    '''
    Takes in a image as a numpy array, metadata for the image (in the same format that pyometiff generates when reading an ome-tiff), and a filepath
    where the image will be written as an .ome.tiff 
    '''
    #image = image[:,np.newaxis,np.newaxis,:,:]
    writer = pot.OMETIFFWriter(
            fpath=file_path,
            dimension_order='CYX',   # 'CZTYX'
            array=image,
            metadata=ome_tiff_metadata,
            explicit_tiffdata=False)
    writer.write()

def mask_expand(distance: int, 
                image_source: Union[Path, str], 
                output_directory: Union[Path, str, None],
                ) -> None:                                   # ****stein_derived (ish -- 
                                                                # only in the sense that it conciously replicates a particular steinbock utility 
                                                                # using the same skimage function.  The actual implementation here is not very 
                                                                # similar to steinbocks')
    '''
    Function that expands the size of cell masks:

    Args:
        distance (integer):  
            the number of pixels to expand the masks by

        image_source (string or Path): 
            the file path to a folder containing the cell masks (as tiff files) to expand

        output_directory (string or Path): 
            the file path to a folder containing the cell masks (as tiff files) to expand

    Inputs / Outputs:
        Inputs: 
            reads every file in image_source folder (expecting .tiff format for all)
    
        Outputs: 
            writes a (.ome).tiff into the output_directory folder for each file read-in from image_source
            The filenames in the image_source folder as preserved in the output_directory, so if image_source == output_directory
            then the original masks will be overwritten. 
    '''
    from skimage.segmentation import expand_labels
    output_directory = str(output_directory).rstrip("/")
    image_source = str(image_source)
    if not os.path.exists(output_directory):
        os.mkdir(output_directory)

    for i in sorted(os.listdir(image_source)):
        read_dir = "".join([image_source, "/", i])
        out_dir = "".join([output_directory, "/", i])
        read_in_mask = tf.imread(read_dir)
        expanded_mask = expand_labels(read_in_mask, distance)
        tf.imwrite(out_dir, expanded_mask, photometric = "minisblack")

class ImageAnalysis:
    '''
    This handles Image Processing steps of PalmettoBUG, such as conversion from mcd's and segmentation measurements

    Key Attributes:
        directory (str): 
            the path to a folder containing a /raw/ subfolder where the MCD or TIFF files are

        directory_object (DirSetup): 
            this attribute is a sub-class from Utils/SharedClasses.py module. it coordinates directories of the typical
            PalmettoBUG project --

            *Key Subattributes*

            - (self.directory_object).main == self.directory >>> The highest-level directory of the project

            - raw_dir == {directory}/raw >>> the folder containing the MCD or TIFF files of raw data

            - img_dir == {directory}/images >>> the folder containing sub-folders of images (such as the img_dir/img sub-folde, which contains
                the initial images directly converted from the raw_dir)

            - masks_dir == {directory}/masks >>> the folder containing sub-folders of cell masks (such as the masks_dir/deepcell_masks sub-folder, 
                which contains the cell masks created by deepcell, before any modifications / expansions are performed on those masks.)

            - classy_masks_dir == {directory}/classy_masks >>> the folder containing sub-folders of classy cell masks. Each subfolder is named
                by convention using the pixel classifier + cell mask pair that the clasy masks were derived from.

            - px_classifiers_dir == {directory}/Pixel_Classification >>> the folder containing sub-folders of pixel classifiers

            - Analyses_dir == {directory}/Analyses >>> the folder containing sub-folders of Analysis directories. 
            
            - logs == {directory}/Logs --> the folder containing the .log files generated by the GUI

        from_mcds (boolean): 
            whether the files in directory/raw are MCD files (True), or are TIFF files (False)

        resolutions (list[float, float]): 
            the X and Y resolutions of the images, in micrometers / pixel

        panel (pandas dataframe): 
                This is a pandas dataframe read-in from & written to directory/panel.csv
                This is a steinbock-style panel (with changes), with four columns = "name","antigen","keep","segmentation"

        metadata (pandas dataframe): 
                This is the dataframe containing a CATALYST-style metadata file. It is really intended for the 
                Analysis portion of the program and is not used in image processing, however this class produces a preliminary
                version of this dataframe as a part of the transition from image processing --> analysis

                It has four columns -- 

                    "file_name" == the filenames of the .fcs files in the analysis

                    "sample_id" == numbers to identify each filename quickly (zero-indexed)

                    "patient_id" == a secondary grouping / covariate / batch

                    "condition" == the independent variable / treatment vs. control grouping

        Analysis_panel (pandas dataframe): 
                This is the dataframe containing a CATALYST-style panel file. It is really intended for the 
                Analysis portion of the program and is not used in image processing, however this class produces a preliminary
                version of this dataframe as a part of the transition from image processing --> analysis

                It has three columns:

                    "fcs_colname" == the name of the marker in the .fcs files. when coming straight from solution-mode fcs files, 
                    these names can be non-straightforward or confusing (often metal names. Ex: Ce140Di) When produced from an 
                    imaging experiment the fcs names are usually identical to the "antigen" names:

                    "antigen" == the name of the marker to use in analysis plots, usually its straightforward, biological name (ex: CD4)

                    "marker_class" == 'type','state', or 'none' -- used as in CATALYST-style workflow to determine how markers are used.

    '''
    def __init__(self, directory: Union[Path, str, None], resolutions: list[float,float] = [1.0, 1.0], from_mcds: bool = True):
        '''
        Directory can be set to None, on order to not set up the panel / directory. This allows this class to initialized without data, which can be 
        useful if not intending following the standard PalmettoBUG directory structure. X and Y are the resolution of the images (in micrometers), 
        and from_mcds indicates whether the /raw files are mcds (True) or .tiffs (False)
        '''
        self.from_mcds = from_mcds
        self.resolutions = resolutions   ## load these values later   (default of 1uM is assumed for now)
        self.metadata = pd.DataFrame()
        self.Analysis_panel = pd.DataFrame()
        if directory is not None:
            directory = str(directory)
            self.directory = directory
            self.directory_object = DirSetup(directory)
            self._panel_setup()

    def _panel_setup(self) -> None:
        '''
        This will either read in the panel.csv file in the top-level project folder, or failing that will attempt to generate a panel file automatically.

        Note:
            -- This method depends on the self.from_mcds attribute to know whether mcds or tiffs are in the /raw folder

            -- Any automatically generated panel file will have an entirely blank 'segmentation' column. This requires editing 
            before segmentation can be performed using deepcell or cellpose

            -- additionally, the automatically generated 'keep' column may not accurately reflect what you want, although it often does. 
        '''
        if self.from_mcds is True:
            MCD_list = stein_unhook.list_mcd_files(self.directory_object.main)
            try:
                self.panel = pd.read_csv("".join([self.directory_object.main, "/panel.csv"]))
            except FileNotFoundError:
                self.panel = stein_unhook.create_panel_from_mcd_files(MCD_list)
                self.panel = self.panel.drop(['ilastik','cellpose','deepcell'], axis = 1)     
                                    ######## remove unwanted columns from the underlying steinbock package implementation
                self.panel['segmentation'] = ""

                ## This auto-sets background channels to keep = 0 (based on duplicating entry in the channel / name columns)
                numbers_channel = self.panel['channel'].str.replace("[^0-9]","", regex = True)
                letters_channel = self.panel['channel'].str.replace("[0-9]","", regex = True)
                self.panel['channel_test'] = numbers_channel + letters_channel

                numbers_name = self.panel['name'].str.replace("[^0-9]","", regex = True)
                letters_name = self.panel['name'].str.replace("[0-9]","", regex = True)
                self.panel['name_test'] = numbers_name + letters_name
                
                keep = (self.panel['channel_test'] != self.panel['name_test'])
                self.panel['keep'] = keep
                self.panel['keep'] = self.panel['keep'].astype('int')
                self.panel = self.panel.drop(['channel_test','name_test'],axis=1)
        else:  ## if self.mcds is False, then loading from .tiffs
            try:  ## read in panel file if it already exists
                read_dir = "".join([self.directory_object.main, "/panel.csv"])
                self.panel = pd.read_csv(read_dir)      
            except FileNotFoundError:
                image_list = sorted(os.listdir(self.directory_object.main + "/raw"))
                reader_string = "".join([self.directory_object.main, "/raw/", image_list[0]])
                if image_list[0][-9:].lower() == ".ome.tiff":   
                    # when dealing with an .ome.tiff, I'd like to try to recover some useful metadata (only uses first image):
                    reader = pot.OMETIFFReader(reader_string) 
                    img_array, metadata, xml_metadata = reader.read()
                    try: 
                        channel_list = [i for i in metadata['Channels']]
                    except KeyError:
                        tiff_file1 = tf.imread(reader_string)
                        channel_list = [i for i in range(tiff_file1.shape[0])]
                else:            # this means we are dealing with a .tiff, and will not try to recover metadata
                    tiff_file1 = tf.imread(reader_string)
                    channel_list = [i for i in range(tiff_file1.shape[0])]
                #### now make the initial pd.DataFrame to hold the table widget:
                Init_Table = pd.DataFrame()
                Init_Table['channel'] = channel_list
                Init_Table['name'] = channel_list
                Init_Table['keep'] = 1         # default to keeping all channels
                Init_Table['segmentation'] = "" 
                self.panel = Init_Table
                Init_Table.to_csv(self.directory_object.main + "/panel.csv", index = False)   

    def panel_write(self) -> None:
        '''
        This method writes the self.panel dataframe to the disk at the expected location for future re-read 
        (panel.csv in the top-level folder of the project) 
        '''
        if _in_gui:
            try:
                self.panel.to_csv(self.directory_object.main + '/panel.csv', index = False)
                with open(self.directory_object.main + '/panel.csv') as file:
                    Project_logger(self.directory_object.main).return_log().info(f"Wrote panel file, with values: \n {file.read()}")
            except Exception:
                tk.messagebox.showwarning("Warning!", message = """Could not write panel file! \n 
                            Do you have the .csv open right now in excel or another program?""")
        else:
            self.panel.to_csv(self.directory_object.main + '/panel.csv', index = False)
            
     # This method writes from MCDs --> .ome.tiffs 
    def raw_to_img(self, 
                   hpf: int = 50, 
                   input_directory: Union[str, Path, None] = None, 
                   output_directory: Union[str, Path, None] = None,
                   ) -> None:
        '''
        This method converts/moves files from the /raw folder --> /images/img folder. It always exports in .ome.tiff format
        with two transformations of the images in the raw files:
        
            1. channels with 'keep' == 0 in the panel file will be dropped from the exported .ome.tiffs

            2. hot pixel filtering will be performed before exporting to the /images/img folder if hpf > 0

        It depends on self.from_mcds to know whether to expect MCd or TIFF files in the /raw folder.

        Args:
            hpf (int >= 0): 
                an integer denoting the threshold used for steinbock-style hot pixel filtering. This means that pixels
                that are brighter than each of their surrounding neighbor pixels by more than the inputted threshold 
                will have their values reduced to match the value of their brightest neighbor pixel. So lower 
                thresholds will more aggressively filter "hot" / bright pixels, while higher thresholds will filter less. 
                The default (50) matches the default value in steinbock. ** If hpf == 0, no hot pixel filtering will occur. **

            input_directory (str, Path, or None): 
                a path to the folder containing the .mcd or .tiff files to be converted and 
                hot-pixel filtered. Assumes that the folder chosen ONLY contains files (no sub-folders) and 
                that all of those files are of the appropriate format.

            output_directory (str, Path, or None): 
                A path to a folder to write the .ome.tiff files to. If None, then defaults 
                to the self.directory.main + "/images/img/" subfolder

        Returns:
            None: (its output is in writing to the disk, not returning a value)
        '''
        from_mcds = self.from_mcds
        if input_directory is None:
            input_directory = self.directory_object.main + "/raw/"
        else:
            input_directory = str(input_directory)

        if output_directory is None:
            output_directory =  "".join([self.directory_object.img_dir, '/img/'])
        else:
            output_directory = str(output_directory)
        if not os.path.exists(output_directory):
            os.mkdir(output_directory)

        if from_mcds is True:
            mcd_list = ["".join([input_directory,i]) for i in sorted(os.listdir(input_directory))]
            MCD_gen = _MCD_Generator(mcd_list)
        else:
            tiff_list = ["".join([input_directory,i]) for i in sorted(os.listdir(input_directory))]
            MCD_gen = _TIFF_Generator(tiff_list)

        i = 1
        counter = -1
        keep = (self.panel['keep'] == 1)
        while i == 1:
            try: 
                image, path, ROI, acquisition = next(MCD_gen)
                counter += 1
            except StopIteration:
                break
            # filter for keep channels
            if len(image) != len(self.panel):
                if _in_gui:
                    warning_window(f"""The number of channels in {ROI} of {path} does not match the number of channels 
                                   in the panel file! Skipping this ROI.""")
                else:
                    print(f"""The number of channels in {ROI} of {path} does not match the number of channels 
                          in the panel file! Skipping this ROI.""")
            else:   # proceed with conversion to TIFF
                image = image[keep]
                if (hpf > 0) and (hpf < 1):
                    image = _my_auto_hpf(image, hpf)
                elif hpf != 0:
                    image = stein_unhook.filter_hot_pixels(image,hpf)   ## stpi removed
                if from_mcds is True:
                    file_name = "".join([(str(path)[len(self.directory_object.main)+5:-4]), '_', ROI])   ### this is an awkard line -- 
                                                                                                        # len(directory) + 5, slices off the 
                                                                                                        # directory + /raw/ ,
                                                                                                        #  while -4 slices off the .mcd suffix
                    out = "".join([output_directory, file_name, ".ome.tiff"])
                    ome_tiff_metadata = _generate_ome_tiff_metadata(self.panel, 
                                                                    self.directory_object.img_dir, 
                                                                    file_name, 
                                                                    self.resolutions)
                    write_ome_tiff(image, ome_tiff_metadata, out)
                else:
                    if ROI.rfind(".ome.tif") == -1:
                        ROI = ROI[:ROI.rfind(".tif")]   ## remove existing extension (assumed to be a singular extension)
                        ROI = ROI + ".ome.tiff"
                    if ROI.rfind(".ome.tiff") == -1:   ## this means that the current format must be .ome.tif (one f, instead of two), so I add an "f" for consistency
                        ROI = ROI + "f"
                    out = "".join([output_directory, ROI])
                    ome_tiff_metadata = acquisition
                    if ome_tiff_metadata is None:
                        file_name = ROI[1:]
                        ome_tiff_metadata = _generate_ome_tiff_metadata(self.panel, 
                                                                    self.directory_object.img_dir, 
                                                                    file_name, 
                                                                    self.resolutions)
                    write_ome_tiff(image, ome_tiff_metadata, out)


    ### This function calculates and writes the intesities, regionprops csv files. 
    def make_segmentation_measurements(self, 
                                       input_img_folder: Union[Path, str], 
                                       input_mask_folder: Union[Path, str], 
                                       output_intensities_folder: Union[Path, str, None] = None, 
                                       output_regions_folder: Union[Path, str, None] = None, 
                                       statistic: str= "mean",
                                       re_do: bool = False, 
                                       advanced_regionprops: bool = False, 
                                        ) -> None:                              
                                                                                # ****stein_derived (implements parts of 
                                                                                # the steinbock.measurement module scripts
                                                                                # # *** marks directly copied/derived lines)
        '''
        This method measures statistics and regionproperties from cell masks + images, and writes these as intensity 
        and regionprops csv files in an output folder. This output folder is structured such that a PalmettoBUG-style 
        analysis can easily be launched from it. 

        It is derived & and relies upon steinbock region_measurements functions (and through them, skimage). 

        Args:
            input_img_folder (Path, str): 
                the file path to the folder containing the images to be used for measuring 
                statistics / intensities

            input_mask_folder (Path string): 
                the file path to the folder contianing the masks to be used for measuring both 
                stats / intensities AND region properties (the region properties depend only on 
                the shape of the masks, not of the channels of the matching images)

                NOTE! -- the input_img_folder and input_mask_folder are presumed to have the same number of files & these files share 
                filenames / order. This is the default way that PalmettoBUG / isoSegDenoise exports these files, but be 
                careful to make sure to change this to be the case if your data does not match this pattern!

            output_intensities_folder (Path, string, None): 
                the file path to the folder to export the intensity csv files (these 
                csv files are effectively like fcs files with events ['Object'] each with intensity measurements / statistics for each channel). 
                If None, then the self.directory_object.intensities_dir will be used -- this depends on having set up an analysis using 
                the self.make_analysis_dirs(analysis_name) method beforehand

            output_intensities_folder (Path, string, None): 
                the file path to the folder contianing the regionprops csv files for each mask. 
                Like the intensities csv's these are structured with measurements for each object/event/cell, but are measurements like area, perimeter, etc.
                If None, then will use the self.directory_object.regionprops_dir -- this depends on calling the self.make_analysis_dirs(analysis_name) method beforehand

            statistic (string): 
                The statistic to report for each cell/object for each channel in the instensity csv files.
                One of ["mean","median","min","max","sum","std","var"]. Default is "mean", and you will rarely need any of the other options. 

            re_do (boolean): 
                Determines whether to check if each intensities/regionprops csv has already been generated (by matching the file name) 
                and ONLY export NEW csv files (if = True).
                Alternatively, export every csv file regardless of whether or not the export folder already contains identically named files (if = False). 

                Consider re_do = True if you are adding new files to a large existing project and don't want the old files to be redone or are 
                generating advanced regionprops (saves time), 

                otherwise re_do = False is frequently better as writing each file without advanced regionprops is not a very long process & ensures 
                consistency at this step. 

            advanced_regionprops (boolean): 
                If True, will calculate a few 'advanced' region properties, like --> [number of branch points, tortuosity, etc...]
                of the masks. This is a slow process so the default advanced_regionprops = False is preferred unless these additional region properties are greatly desired. 

                WARNING!! -- This option is currently broken / unreliable (algorithms & packages used to derive these regionproperties appear to make errors
                in determining branching.)

        Returns:
            None -- (its output is in writing to the disk, not returning a value)
        '''
        input_img_folder = str(input_img_folder)
        input_mask_folder = str(input_mask_folder)

        if output_intensities_folder is None:
            output_intensities_folder = self.directory_object.intensities_dir
        if output_regions_folder is None:
            output_regions_folder = self.directory_object.regionprops_dir

        output_intensities_folder = str(output_intensities_folder)
        output_regions_folder = str(output_regions_folder)

        if not os.path.exists(output_intensities_folder):
            os.mkdir(output_intensities_folder) 
        if not os.path.exists(output_regions_folder):
            os.mkdir(output_regions_folder) 

        dict_of_choices = {       # ***
            "sum": stein_unhook.IntensityAggregation.SUM,
            "min": stein_unhook.IntensityAggregation.MIN,
            "max": stein_unhook.IntensityAggregation.MAX,
            "mean": stein_unhook.IntensityAggregation.MEAN,
            "median": stein_unhook.IntensityAggregation.MEDIAN,
            "std": stein_unhook.IntensityAggregation.STD,
            "var": stein_unhook.IntensityAggregation.VAR,
            }
        img_files = sorted(Path(input_img_folder).rglob("[!.]*.tiff"))   # ***
        mask_files = sorted(Path(input_mask_folder).rglob("[!.]*.tiff"))  # ***
        ints_folder = sorted(Path(output_intensities_folder).rglob("[!.]*.csv"))   # ***
        regions_folder = sorted(Path(output_regions_folder).rglob("[!.]*.csv"))    # ***
        if _in_gui:
            if (re_do is False) and (len(img_files) == len(ints_folder)) and (len(img_files) == len(regions_folder)):     
                tk.messagebox.showwarning("Warning!", 
                    message = "All images have intensity and region files written! Did you intend to redo these measurements?")  
                return

            if len(img_files) != len(mask_files):
                tk.messagebox.showwarning("Warning!", 
                    message = "The number of masks in the masks folder and images in the img folder must be the same! Have you deleted a file?")
                return
        else:
            if (re_do is False) and (len(img_files) == len(ints_folder)) and (len(img_files) == len(regions_folder)):     
                print("All images have intensity and region files written! Did you intend to redo these measurements?")  
                return

            if len(img_files) != len(mask_files):
                print("The number of masks in the masks folder and images in the img folder must be the same! Have you deleted a file?")
                return
        
        if re_do is False:
            def filterer(dest_folder, img_files, mask_files):
                ## originally written for the intensity folder first, hence the (ints_ and _int) pre-/suffixes
                ints_files = [str(i).replace("\\","/") for i in dest_folder]
                ints_files = [i[(i.rfind("/") + 1):i.rfind(".csv")] for i in ints_files]
                img_files_int = []
                mask_files_int = []
                for i,ii in zip(img_files, mask_files):
                    if str(i)[str(i).rfind("/"):] != str(ii)[str(ii).rfind("/"):]:
                        print("The image and masks filenames do not align!")
                    else:
                        j = str(i).replace("\\","/")
                        j = j[(j.rfind("/") + 1):j.rfind(".tiff")]
                        if j not in ints_files:
                            img_files_int.append(i)
                            mask_files_int.append(ii)
                return img_files_int, mask_files_int
            img_files_int, mask_files_int = filterer(ints_folder, img_files, mask_files)
            img_files_reg, mask_files_reg = filterer(regions_folder, img_files, mask_files)
            intensity_gen = stein_unhook.try_measure_intensities_from_disk(img_files_int,           # *** 
                                        mask_files_int, 
                                        self.panel[self.panel['keep'] == 1]['name'], 
                                        dict_of_choices[statistic])                     
            regionprops_gen = stein_unhook.try_measure_regionprops_from_disk(img_files_reg,         # ***
                                                                             mask_files_reg,["area", 
                                                                                    "perimeter",              
                                                                                    "centroid",
                                                                                    "axis_major_length",
                                                                                    "axis_minor_length",
                                                                                    "eccentricity"])
        
            def write_csvs(img_files, generator, out_directory, csv_type, input_mask_folder = input_mask_folder):
                ''''''
                for i in img_files:
                    img_file, mask_file, csv = next(generator)
                    if csv_type == "regions":
                        csv['image_area'] = tf.imread(mask_file).shape[0] * tf.imread(mask_file).shape[1]
                        csv['mask_folder'] = input_mask_folder
                    right_index1 = str(mask_file).rfind('/')
                    right_index2 = str(mask_file).rfind('\\')
                    right_index = np.max([right_index1,right_index2])
                    left_index = str(mask_file).rfind('.tiff')
                    file_name = str(mask_file)[right_index+1:left_index]
                    if (len(csv[csv.columns[0]]) != 0):           #### This means there are no cell masks in this file! 
                        csv.to_csv(("".join([out_directory, '/', file_name, ".csv"])),index = True)
                        print(f"{file_name} {csv_type} csv has been written!") 
                    else:
                        csv.to_csv(("".join([out_directory, '/', file_name, ".csv"])),index = True)
                        print(f"{file_name} {csv_type} csv has been written but it has no entries in it!") 

            write_csvs(img_files_int, intensity_gen, output_intensities_folder, csv_type = "intensities")
            write_csvs(img_files_reg, regionprops_gen, output_regions_folder, csv_type = "regions" )

        else:
            intensity_gen = stein_unhook.try_measure_intensities_from_disk(img_files,                      # *** 
                                                        mask_files, 
                                                        self.panel[self.panel['keep'] == 1]['name'], 
                                                        dict_of_choices[statistic])  
            regionprops_gen = stein_unhook.try_measure_regionprops_from_disk(img_files,                    # ***
                                                            mask_files,["area", 
                                                                        "perimeter",
                                                                        "centroid",
                                                                        "axis_major_length",
                                                                        "axis_minor_length",
                                                                        "eccentricity"])
            for i in img_files:
                img_file, mask_file, int_csv = next(intensity_gen)
                img_file, mask_file, regionprops = next(regionprops_gen)
                regionprops['image_area'] = tf.imread(mask_file).shape[0] * tf.imread(mask_file).shape[1]
                regionprops['mask_folder'] = input_mask_folder
                right_index1 = str(img_file).rfind('/')
                right_index2 = str(img_file).rfind('\\')
                right_index = np.max([right_index1,right_index2])
                left_index = str(img_file).rfind('.tiff')
                file_name = str(img_file)[right_index+1:left_index]
                if len(int_csv[int_csv.columns[0]]) != 0:           #### This means there are no cell masks in this file!
                    int_csv.to_csv(("".join([output_intensities_folder, '/', file_name, ".csv"])),index = True)
                    regionprops.to_csv(("".join([output_regions_folder, '/', file_name, ".csv"])),index = True)
                    print(f"{file_name} intensity & region properties csv's have been printed!") 
                else:
                    if _in_gui:
                        warning_window(f"""{file_name} has no cell masks in it! 
                            Re-run segmentation or delete image & its mask / csv's from the analysis! 
                            \n conversion to Analysis will fail in the creation of a 0 event fcs""")
                    print(f"""{file_name} has no cell masks in it! 
                        Re-run segmentation or delete image & its mask / csv's from the analysis! 
                        \n conversion to Analysis will fail in the creation of a 0 event fcs""")
                    
        if advanced_regionprops is True:
            print("Beginning advanced regionprop calculations -- this could take some time")
            self._advanced_regionprops(input_mask_folder, output_regions_folder)

    def _advanced_regionprops(self, 
                              input_mask_folder: Union[Path, str], 
                              output_regions_folder: Union[Path, str],
                              ) -> None:   
        '''
        Helper function for self.make_segmentation_measurements(). Calculates 'advanced' region properties: [n_slab, n_branch, tortuosity, cycles]

        WARNING!! -- Currently not accurate / functional (inaccurate, additional branches in simple tests). Error may propagate from NAVis library
        '''
        try:
            import navis as nv #type: ignore
        except Exception:
            print("Advanced Regionprops requires the navis package to be installed! Warning -- test of navis branching algorithm in simple cases had errors (note on 1/13/25)")
            return
        input_mask_folder = str(input_mask_folder)
        output_regions_folder = str(output_regions_folder)

        mask_files = ["".join([input_mask_folder,"/",i]) for i in sorted(os.listdir(input_mask_folder))]
        regionprops_files = ["".join([output_regions_folder,"/",i]) for i in sorted(os.listdir(output_regions_folder))]
        for i,ii in zip(mask_files, regionprops_files):
            image = tf.imread(i).astype('int')
            n_slab_list = []
            n_branch_list = []
            tortuosity_list = []
            cycle_list = []
            for kk,k in enumerate(skimage.measure.regionprops(image)):
                to_navis = image[k.bbox[0]:k.bbox[2],k.bbox[1]:k.bbox[3]]
                skeleton = skimage.morphology.skeletonize(to_navis).astype('int')
                to_navis = np.pad(skeleton[:,:,np.newaxis], 1)
                mesh = skimage.measure.marching_cubes(to_navis, spacing = (1.0, 1.0, 0.01))
                verts, faces, _, _ = mesh 
                try:
                    verts[:,2] = 0
                    meshy_neury = nv.MeshNeuron((verts, faces))   # type: ignore     # TODO: reactivate this function once fixed
                    tree_neuree = meshy_neury.skeletonize()   
                    n_slab_list.append((tree_neuree.nodes['type'] == 'slab').sum())
                    n_branch_list.append((tree_neuree.nodes['type'] == 'branch').sum())
                    cycles = tree_neuree.cycles
                    if cycles is not None:
                        cycle_list.append(cycles)
                    else:
                        cycle_list.append(0) 
                except Exception:
                    n_slab_list.append(0)
                    n_branch_list.append(0)
                    cycle_list.append(0)
                try:
                    tortuosity_list.append(nv.tortuosity(tree_neuree))     # type: ignore    # TODO: reactivate this function once fixed
                except Exception:
                    tortuosity_list.append(1)
            df = pd.read_csv(ii)
            df['n_slab'] = n_slab_list
            df['n_branch_list'] = n_branch_list
            df['tortuosity'] = tortuosity_list
            df['cycles'] = cycle_list
            df.to_csv(ii, index = False)    

    def to_analysis(self, Analysis_tab = None, metadata_from_save: bool = False) -> None:
        '''
        This function prepares / sets up an Analysis folder, by converting intensity csv files to fcs files and generating preliminary / semi-empty metadata / panel 
        pandas dataframes, which require editing before writing to the disk at the newly prepared self.Analysis_panel_dir and self.metadata_dir filepaths.

        Depends on self.make_analysis_dirs(analysis_name) being called first to set up the directory structure and direct the discovery
        of the intensity files which will be used to generate FCS files & the intial panel/metadata dataframes.

        DOES NOT export the panel / metadata files to the disk, but returns them, along with the file paths where they are expected to
        be wrtten to, in the following order: (panel dataframe, metadata dataframe, panel path, metadata path)

        Args:
            Analysis_tab / metadata_from_save (Only for use inside GUI): 
                IGNORED outside of GUI. in the GUI they assist in coordinating the widgets & choosing to load the Analysis_panel/metadata files 
                from the directory_object.Analyses_dir (if someone makes a second analysis in one project, instead of requiring a fresh panel/metadata 
                set up each time a new analysis is made). 
        '''
        #print(_in_gui)
        if not _in_gui:
            self._intense_to_fcs()
            if ((not os.path.exists(self.directory_object.Analyses_dir + "/Analysis_panel.csv")) 
                or (not os.path.exists(self.directory_object.Analyses_dir + "/metadata.csv"))):
                print("""Panel / Metadata could not be loaded from save (in Analyses directory) -- generating these from scratch""")
                panel_file = self._initial_Analysis_panel()
                metadata = self._initial_metadata_file()
            else:
                panel_file = pd.read_csv(self.directory_object.Analyses_dir + "/Analysis_panel.csv")
                metadata = pd.read_csv(self.directory_object.Analyses_dir + "/metadata.csv")
            self.Analysis_panel_dir = self.directory_object.Analysis_internal_dir + "/Analysis_panel.csv"
            self.metadata_dir = self.directory_object.Analysis_internal_dir + "/metadata.csv"
            return panel_file, metadata, self.Analysis_panel_dir, self.metadata_dir
    
        elif _in_gui:
            self._intense_to_fcs()
            Analysis_tab.analysiswidg.setup_dir_disp(self.directory_object.analysis_dir + "/main") 
            Analysis_tab.master.Spatial.widgets.setup_dir_disp(self.directory_object.analysis_dir + "/main")
            if metadata_from_save is True: 
                if ((not os.path.exists(self.directory_object.Analyses_dir + "/Analysis_panel.csv")) 
                or (not os.path.exists(self.directory_object.Analyses_dir + "/metadata.csv"))):
                    tk.messagebox.showwarning("Warning!",
                        message = """Loading Panel / Metadata from save option checked -- 
                                    but one or both of those files is not present in the /Analyses directory!""")
                self.Analysis_panel = pd.read_csv(self.directory_object.Analyses_dir + "/Analysis_panel.csv")
                self.metadata = pd.read_csv(self.directory_object.Analyses_dir + "/metadata.csv")

                analysis_logger = Analysis_logger(self.directory_object.Analysis_internal_dir).return_log()
                table_launcher = TableLaunchAnalysis(1, 1, 
                                                    self.directory_object.Analysis_internal_dir, 
                                                    self.Analysis_panel, "Analysis_panel.csv", 
                                                    self, Analysis_tab.master, 
                                                    self.directory_object.Analyses_dir, 
                                                    favor_table = True, 
                                                    logger = analysis_logger)
                table_launcher.add_table(1, 1, 
                                         self.directory_object.Analysis_internal_dir, 
                                         self.metadata, "metadata",
                                         favor_table = True)
            else:
                self._initial_Analysis_panel()
                analysis_logger = Analysis_logger(self.directory_object.Analysis_internal_dir).return_log()
                table_launcher = TableLaunchAnalysis(1, 1, 
                                                     self.directory_object.Analysis_internal_dir, 
                                                     self.Analysis_panel, 
                                                    "Analysis_panel.csv", 
                                                    self, 
                                                    Analysis_tab.master, 
                                                    self.directory_object.Analyses_dir, 
                                                    logger = analysis_logger)
                self._initial_metadata_file()
                table_launcher.add_table(1, 1, 
                                         self.directory_object.Analysis_internal_dir, 
                                         self.metadata, "metadata")

    def _intense_to_fcs(self, 
                        input_intensity_directory: Union[Path, str, None] = None, 
                        ouput_fcs_folder: Union[Path, str, None] = None,
                        ) -> None:
        '''
        Helper method for self.to_Analysis --> writes .fcs files from .csv files in the intensities folder.

        When called with default arguments, depends on self.make_analysis_dirs(analysis_name), however the input and output folders
        can be specified separately to allow its use in any context.

        Args:
            input_intensity_directory (Path, string, None): 
                the path to a folder where the intensity csv files are (exported by self.make_segmentation_measurements)
                If None, then a default path is presumed which requires a prior execution of the self.make_analysis_dirs(analysis_name) method

            ouput_fcs_folder (Path, string, None): 
                the path to a folder where the FCS files will be written to, with the same behaviour as (input_intensity_directory) - if None, a 
                default path self.directory_object.fcs_dir is presumed, etc.
        '''
        if input_intensity_directory is None:                               
            input_intensity_directory = self.directory_object.intensities_dir
        if ouput_fcs_folder is None:
            ouput_fcs_folder = self.directory_object.fcs_dir 
        input_intensity_directory = str(input_intensity_directory)
        ouput_fcs_folder = str(ouput_fcs_folder)
        if not os.path.exists(ouput_fcs_folder):
            os.mkdir(ouput_fcs_folder)

        for i in sorted(os.listdir(input_intensity_directory)):
            pd_df = pd.read_csv("".join([input_intensity_directory, "/", i]))
            fcs_df = DataFrame(pd_df, columns = pd_df.columns)
            filename = i[:i.rfind('.')]
            fcs_df.to_fcs("".join([ouput_fcs_folder, "/", filename, ".fcs"]))

    def _initial_Analysis_panel(self) -> pd.DataFrame:
        ''' 
        Helper method for self.to_Analysis generates an initial Analysis panel (marker_class column blank)
        '''
        self.Analysis_panel = self.panel.drop(['segmentation','channel'], axis = 1)
        self.Analysis_panel = self.Analysis_panel[self.Analysis_panel['keep'] == 1]
        self.Analysis_panel = self.Analysis_panel.reset_index().drop(['index','keep'], axis = 1)
        self.Analysis_panel['fcs_colname'] = self.Analysis_panel['name']
        self.Analysis_panel['antigen'] = self.Analysis_panel['name']
        self.Analysis_panel = self.Analysis_panel.drop('name', axis = 1)
        self.Analysis_panel['marker_class'] = 'none'  
        return self.Analysis_panel
    
    def _initial_metadata_file(self) -> pd.DataFrame:
        '''
        Helper method for self.to_Analysis --> generate the initial metadata file (patient and condition columns blank)
        '''
        file_list = sorted(os.listdir(self.directory_object.fcs_dir))
        metadata = pd.DataFrame()
        metadata['file_name']  = file_list
        metadata['sample_id'] = metadata.reset_index()['index']
        metadata['patient_id'] = '' 
        metadata['condition'] = 'treatment vs. control'   
        self.metadata = metadata
        return metadata
    
def setup_for_FCS(directory):
    '''
    This sets up a folder for single-cell analysis using the CATALYST-derived module of PalmettoBUG. 

    Can be used for a solution-mode experiment (direct from FCS files) or as part of the set up when transitioning from image processing to single-cell analysis.

    Returns:
        Analysis_panel (a pandas dataframe of the initially generated Analysis_panel file, needs the marker_class column to be filled in by the user)

        Analysis_panel_dir (a string, the path to where the Analysis_panel should be saved on the disk once it has been completed by the user)

        metadata (a pandas dataframe of the initially generated metadata file, needs the patient_id and condition columns to be filled in by the user)

        metadata_dir (a string, the path to where the metadata should be saved on the disk once it has been completed by the user)
    '''
    directory_name = directory[:directory.rfind("/")]

    directory_object = DirSetup(directory, kind = "Analysis")
    directory_object.make_analysis_dirs(directory_name)
    Analysis_panel_dir = directory_object.Analysis_internal_dir + "/Analysis_panel.csv"
    metadata_dir = directory_object.Analysis_internal_dir + "/metadata.csv"
    try:
        Analysis_panel = pd.read_csv(Analysis_panel_dir)
    except FileNotFoundError:
        fcs_files = sorted(os.listdir(directory_object.fcs_dir))
        warnings.filterwarnings("ignore", message = "The default channel names")
        _, dataframe1 = fcsparser.parse(directory_object.fcs_dir + "/" + fcs_files[0])
        warnings.filterwarnings("default", message = "The default channel names")
        Analysis_panel = pd.DataFrame()
        Analysis_panel['fcs_colnames'] = dataframe1.columns
        Analysis_panel['antigen'] = dataframe1.columns
        Analysis_panel['marker_class'] = "none"
        try:
            Analysis_panel = Analysis_panel.drop("Object", axis = 0) 
        except KeyError:
            pass
        Analysis_panel.to_csv(Analysis_panel_dir, index = False) 

    fcs_files = sorted(os.listdir(directory_object.fcs_dir))
    try:
        metadata = pd.read_csv(metadata_dir)
        
    except FileNotFoundError:
        metadata = pd.DataFrame()
        metadata['file_name']  = fcs_files
        metadata['sample_id'] = metadata.reset_index()['index']
        metadata['patient_id'] = 'na'      # manually set later
        metadata['condition'] = 'treatment vs. control'       # manually set later

    return Analysis_panel, Analysis_panel_dir, metadata, metadata_dir

class direct_to_Analysis(ImageAnalysis):
    ''' GUI only '''
    def __init__(self, 
                 master, 
                 directory: str, 
                 metadata_from_save: bool = False):      
        ## this is essentially its own, customized directory then panel/metadata setup (particularly the panel setup is customized)
        self.master = master
        directory_name = directory  #[:directory.rfind("/")]
        self.directory_object = DirSetup(directory, kind = "Analysis")
        self.directory_object.make_analysis_dirs(directory_name)
        if metadata_from_save is True:                           ## the loader from the common / saved metadata
            self.Analysis_panel_dir = self.directory_object.Analyses_dir + "/Analysis_panel.csv"
            self.metadata_dir = self.directory_object.Analyses_dir + "/metadata.csv"
        else:
            self.Analysis_panel_dir = self.directory_object.Analysis_internal_dir + "/Analysis_panel.csv"
            self.metadata_dir = self.directory_object.Analysis_internal_dir + "/metadata.csv"

        # read the first .fcs file to get the column names, then write panel file:
        # this has to be done differently than the prior ImageAnalysis class, as it is starting halfway 
        #   and without a pre-existing (steinbock-style) panel file
        try:
            self.Analysis_panel = pd.read_csv(self.Analysis_panel_dir)
        except FileNotFoundError:
            fcs_files = sorted(os.listdir(self.directory_object.fcs_dir))
            warnings.filterwarnings("ignore", message = "The default channel names")
            _, dataframe1 = fcsparser.parse(self.directory_object.fcs_dir + "/" + fcs_files[0])
            warnings.filterwarnings("default", message = "The default channel names")
            self.Analysis_panel = pd.DataFrame()
            self.Analysis_panel['fcs_colnames'] = dataframe1.columns
            self.Analysis_panel['antigen'] = dataframe1.columns
            self.Analysis_panel['marker_class'] = "none"
            try:
                self.Analysis_panel = self.Analysis_panel.drop("Object", axis = 0) 
            except KeyError:
                pass
            self.Analysis_panel.to_csv(self.Analysis_panel_dir, index = False) 

        # now do the metadata initialization and table launches (shared with the main pathway)
        analysis_logger = Analysis_logger(self.directory_object.Analysis_internal_dir).return_log()
        table_launcher = TableLaunchAnalysis(1, 1,  
                                             self.directory_object.Analysis_internal_dir, 
                                             self.Analysis_panel, 
                                             "Analysis_panel.csv", 
                                             self, 
                                             self.master, 
                                             alt_dir = self.directory_object.Analyses_dir, 
                                             logger = analysis_logger)
        fcs_files  = sorted(os.listdir(self.directory_object.fcs_dir))
        try:
            self.metadata = pd.read_csv(self.metadata_dir)
            
        except FileNotFoundError:
            self.metadata = pd.DataFrame()
            self.metadata['file_name']  = fcs_files
            self.metadata['sample_id'] = self.metadata.reset_index()['index']
            self.metadata['patient_id'] = 'na'      # manually set later
            self.metadata['condition'] = 'treatment vs. control'       # manually set later

        table_launcher.add_table(1, 1, 
                                 self.directory_object.main, 
                                 self.metadata, 
                                 "metadata")


class TableLaunchAnalysis(TableLaunch):
    ''' GUI only '''
    def __init__(self, width: int, 
                 height: int, 
                 directory: str, 
                 dataframe: pd.DataFrame,
                 table_type: str, 
                 experiment: ImageAnalysis, 
                 tab, 
                 alt_dir: Union[str, None] = None,
                 favor_table: bool = False, 
                 logger = None):
        ''''''
        super().__init__(width, 
                         height, 
                         directory, 
                         dataframe, 
                         table_type, 
                         experiment, 
                         favor_table = favor_table, 
                         logger = logger)
        self.geometry("+0+0")
        self.tab = tab
        self.alt_dir = alt_dir
        self.Analysis_internal_dir = directory 

        self.save_meta_panel = ctk.CTkCheckBox(master = self, 
            text = """Check to save metadata/Analysis_panel to \n Analyses directory \n (can be re-used when making another analysis)""", 
            onvalue = True, 
            offvalue = False)
        self.save_meta_panel.grid(column = 1, row = 2, pady = 15)

    def accept_and_return(self, experiment: ImageAnalysis) -> None:     
        #### overwrite the accept & return function from the parent to also populate the Analysis widgets
        save_or_not = self.save_meta_panel.get()
        for i in self.table_list:
            i.recover_input()
            if i.type == "Analysis_panel":
                try:
                    experiment.Analysis_panel = i.table_dataframe
                except AttributeError:
                    pass
                self.Analysis_panel_write(i.table_dataframe)
                if save_or_not is True:
                    self.Analysis_panel_write(i.table_dataframe, alt_directory = self.alt_dir)
            if i.type == "metadata":
                try:
                    experiment.metadata = i.table_dataframe    #### this is for the whole class analysis -- it is kind of awkward though
                except AttributeError:
                    pass
                self.metadata_write(i.table_dataframe)
                if save_or_not is True:
                    self.metadata_write(i.table_dataframe, alt_directory = self.alt_dir)
        if self.tab is not None:
            self.tab.py_exploratory.analysiswidg.initialize_experiment_and_buttons(experiment.directory_object.Analysis_internal_dir)
        self.after(200, self.destroy())