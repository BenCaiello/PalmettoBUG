'''
This module is the back-end functions for using pixel classifiers, such as mask extension by pixel classifiers, cell classification 
by pixel classifiers, etc.

It, however, does not contain the WholeClassAnalysis class which coordinates analysis of classes as a whole.

Many of the functions in this module are available through the public (non-GUI) API of PalmettoBUG.


This file is licensed under the GPL3 license. No significant portion of the code here is believed to be derived from another project 
(in the sense of needing to be separately / simultaneously licensed)
'''
import os
import tkinter as tk
from typing import Union
from pathlib import Path
import seaborn as sns 

import matplotlib.pyplot as plt
import skimage
#import scipy
import numpy as np
import pandas as pd
import tifffile as tf
import cv2 as cv
import anndata 

from .._vendor import pyometiff as pot
#from .._vendor.flowsom import FlowSOM 

## anticipate de-vendorization:
from flowsom import FlowSOM

from ..Analysis_functions.Analysis import _quant
from ..Utils.Exceptions import NoSharedFilesError

pd.set_option('future.no_silent_downcasting', True)

__all__ = ["plot_classes",
            "merge_classes", 
            "merge_folder",
            "slice_folder",
            "mode_classify_folder",
            "secondary_flowsom",
            "classify_from_secondary_flowsom",
            "extend_masks_folder"]

_in_gui = False
def toggle_in_gui():
    global _in_gui
    _in_gui = not _in_gui

def plot_classes(class_map_folder, output_folder):
    '''
    Goal: allow classy masks and pixel classification outputs to be written as .png files
    '''
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    for i in sorted(os.listdir(class_map_folder)):
        px_class = tf.imread(f"{class_map_folder}/{i}").astype('int')
        figure = tf.imshow(px_class)[0]
        figure.savefig(f"{output_folder}/{i[:-5]}.png", bbox_inches = "tight")
        plt.close()

def merge_classes(classifier_mask: np.ndarray[int], 
                  merging_table: pd.DataFrame,
                  ) -> np.ndarray[int]:
    '''
    This function takes in a classifier output (numpy array, dtype = int) and a merging table (pandas DataFrame with a particular format) 
    and outputs a new numpy array where all classses in the original array have been converted to the corresponding value in the merging 
    column of the merging-table dataframe. 
    '''
    classifier_mask = classifier_mask.copy()
    new_mask = np.zeros(classifier_mask.shape)
    for i,ii in zip(merging_table['class'], merging_table["merging"]):
        new_mask[classifier_mask == i] = ii
    return new_mask.astype('int')


def merge_folder(folder_to_merge: Union[Path, str], 
                 merging_table: pd.DataFrame, 
                 output_folder: Union[Path, str] = None,
                 ) -> None:
    '''
    This function performs merge_classes() [see function above] on all the images in a provided folder, exporting the merged class map to a 
    specified output folder. if output_folder is None --> then the output is placed in a "/merged_classification_maps" in the same folder as 
    the input folder. 

    Args:
        folder_to_merge (Path or string): 
            the path to the folder containing the classification maps to merge

        merging_table (pandas dataframe): 
            A pandas dataframe containing a 'class' column that denoting a class in the input class maps, and a 
            'merging' column denoting the new values of that class in the merged output class maps. Usually there is also a 'label' column, 
            which denotes the biological label, as a string, that corresponds to each class merging. 

        output_folder (Path, string, or None): 
            the path to a the folder where the merged classification maps are to be exported, with the same 
            filenames as the original folder. If None, then the output folder will be a folder parallel to the input folder (as in, both 
            folder will be in the same parent directory), with the name "/merged_classification_maps". 

    Inputs / Outputs:
        Inputs: 
            reads every file inside folder_to_merge one by one (assumes each is a .tiff file, and there are no subfolders!)

        Outputs: 
            writes a new .tiff file into output_folder for every file in folder_to_merge (preserving the same filenames)
    '''
    folder_to_merge = str(folder_to_merge)
    if output_folder is None:
        output_folder = folder_to_merge[:folder_to_merge.rfind("/")] + "/merged_classification_maps"
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    for i in sorted(os.listdir(folder_to_merge)):
        class_map = tf.imread("".join([folder_to_merge,"/",i])).astype('int32')
        merged = merge_classes(class_map, merging_table = merging_table)
        tf.imwrite("".join([output_folder, "/", i]), merged.astype('int32')) 


def slice_folder(class_to_keep: Union[int, list[int]], 
                 class_map_folder: Union[Path, str], 
                 image_folder: Union[Path, str], 
                 output_folder: Union[Path, str], 
                 padding: int = 5, 
                 zero_out: bool = False,
                 ) -> None:
    '''
    This function performs slice_image_by_region() [see function below] on every image in a folder. 
    This means that each image in the folder will be reduced to the bounding box that contains only the specified classes_to_keep.

    For example: you could use this function, after classifying villi regions of an intestinal tissue section, to reduce the images
    to the minimal rectangle that contains all of the villi class, reducing or removing the unwanted regions of the image.

    Args:
        class_to_keep (integer or a list of integers): 
            The class(s) -- as in, the integer values of the class maps -- to subset the images on

        class_map_folder (Path or string): 
            the path to a folder containing the classification maps (as tiffs) that will determine where the images are sliced / subsetted

        image_folder (Path or string): 
            the path to a folder containing the images to be sliced / subsetted

        output_folder (Path or string): 
            the path to a folder where the sliced / subsetted images will be exported as tiffs

        padding (integer > 0): 
            how many pixels to pad the minimal boudning box of the classes_to_keep in each image. Set to 0 to not pad at all

        zero_out (boolean): 
            If True, all pixels not in class_to_keep will have their channels values set to zero, leaving only the classes of 
            interest contributing information to the image. Default is False, which retains the values of pixels not in classes_to_keep 
            as long as they fall within the minimal bounding box of the classes of interest. 

    Returns:
        None

    Inputs / Outputs:
        Inputs: 
            reads every file in the image_folder (as .tiff files), and every file in the class_map_folder (also as .tiff)
            These provided folders MUST NOT have files besides .tiff nor have any subfolders.

        Outputs: 
            outputs a .tiff file to output_folder for every file read-in from image_folder/class_map_folder
    '''
    class_map_folder = str(class_map_folder)
    image_folder = str(image_folder)
    output_folder = str(output_folder)

    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    classifier_maps = [i for i in sorted(os.listdir(class_map_folder)) if i[-5:] == '.tiff']
    images = [i for i in sorted(os.listdir(image_folder)) if i[-5:] == '.tiff']
    for i, ii in zip(classifier_maps, images):
        if i != ii:
            if _in_gui:
                tk.messagebox.showwarning("Warning!", message = "Mismatch in names between images and classifier maps! Exiting filtering step")
            else:
                print("Mismatch in names between images and classifier maps! Exiting filtering step")
            return
        class_map = tf.imread("".join([class_map_folder,"/",i])).astype('int')
        reader =  pot.OMETIFFReader("".join([image_folder,"/",ii]))
        image, metadata, xml_metadata = reader.read()
        sliced_image = slice_image_by_region(class_to_keep, class_map, image, padding = padding, zero_out = zero_out)
        if len(sliced_image) == 0:
            print(f'an error occurred while processing image {i}. A sliced version of this image will not be exported to the output folder')
        else:
            metadata['SizeX'] = sliced_image.shape[1]
            metadata['SizeY'] = sliced_image.shape[2]
            ## for some reason, when dropped all non-class pixels to 0, the size of the files double & display differently in the directory
            writer = pot.OMETIFFWriter(
                fpath= "".join([output_folder,"/",i]),
                dimension_order='CYX',
                array=sliced_image,
                metadata=metadata,
                explicit_tiffdata=False)
            writer.write()


def slice_image_by_region(class_to_keep: Union[int, list[int]], 
                          class_map: np.ndarray[int], 
                          image: np.ndarray[float], 
                          padding: int = 5, 
                          zero_out: bool = False,
                          ) -> np.ndarray[float]:
    '''
    This function cuts down the size of an image by slicing to the minimal bounding box (+ padding) that contains all of the pixels of a 
    given class. It returns the sliced array.

    Use case: This is primarily to allow users to remove unwanted / uninteresting  tissue regions from the analysis to speed it up and remove 
    unhelpful data. 

    Recommended pipeline: make manual tissue region masks or use the masks from a SUPERVISED pixel classifier trained on the different tissue
    regions, then use this function to slice out only regions of interest. Then proceed with the next steps of the analysis with the smaller, 
    streamlined images.
    
    Args:
        class_to_keep (int or list of ints):
             the integer(s) of the class(es) to slice the image by

        class_map (numpy array):
             the image's pixel classification masks/map >> it must have the same X,Y dimensions as the image

        image (numpy array):
             the image to be sliced down >> usually this is multidimensional with order = (channels, X, Y)  

        padding (int):
             the number of pixels to pad the edges with

        zero_out (bool):
             whether to zero-out all pixels that are not of the kept classes (default behaviour is not to do this)

    Returns:
        numpy array:
            This is the sliced / subsetted numpy array representing the sliced image. If the length of the array is 0, This means some kind of 
            error occurred, whether the image & class map shapes could not be aligned or their were no pixels with values in class_to_keep.
            A message should be printed when this occurs.
    '''
    class_map = class_map.copy()
    # first merge the desired class labels and convert them all to 1's
    class_map = class_map.astype('int')    ## be sure that the classes are integers >> this can change when reading from a file
    
    if class_map.shape[0] != image.shape[1]:  ## if the shape of the class map is not compatible with the image, try transposing:
        class_map = class_map.T
        if class_map.shape[0] != image.shape[1]:
            print("The shapes of a classifier map and its image could not be aligned! Image filtering exited")
            return np.array([])
    
    if isinstance(class_to_keep, list):
        final_class = np.zeros(class_map.shape)
        for i in class_to_keep:
            class_array = (class_map == i).astype('int')
            final_class = (final_class + class_array).astype('int')
    else:
        final_class = (class_map == class_to_keep).astype('int')

    if final_class.sum() == 0:     ## this means the image contians no instances of the desired class
        print("This image contained no pixels of the desired classes (so would be 'sliced' to zero pixels).")
        return np.array([])
    else:
        regionprops = skimage.measure.regionprops(final_class)[0]
        box = regionprops.bbox
        ## padding does not pass the edge of the image:
        bound_1 = max((box[0] - padding), 0)
        bound_2 = min((box[2] + padding), class_map.shape[0])
        bound_3 = max((box[1] - padding), 0)
        bound_4 = min((box[3] + padding), class_map.shape[1])

        ## slice image
        new_image = image[:,bound_1:bound_2,bound_3:bound_4]
        if zero_out is True:
            slicer = final_class[bound_1:bound_2,bound_3:bound_4].astype('float')
            slicer = slicer[np.newaxis,:,:]
            new_image = new_image*slicer
        return new_image 


def mode_classify_folder(mask_folder: Union[Path, str], 
                         classifier_map_folder: Union[Path, str], 
                         output_folder: Union[Path, str], 
                         merging_table: Union[pd.DataFrame, None] = None,
                         ) -> pd.DataFrame:
    '''
    This function classifies cells using a pixel classifier and also creates "classy mask" .tiff files which can be useful for merging / expanding
    cell masks. 

    Args:
        mask_folder (Path or string): 
            the path to the folder containing cell masks (such as those produced by deepcell or cellpose) to be classified

        classifier_map_folder (Path or string): 
            the path to the folder containing the classifier maps that will be used to classify the masks

        output_folder (Path or string):  
            the path to the folder where the 'classy mask' tiff files will be exported

    Returns:
        pandas dataframe: 
            A dataframe with a single column, that denotes the calculated classification for every cell in the dataset. Can be added
            later to a Analysis as an alternative to FlowSOM-based classification of cells.

    Inputs / Outputs:
        Inputs: 
            reads all .tiff files that are in both mask_folder, classifier_map_folder (as in, a file with the same name is in both)

        Outputs: 
            for every read-in file, exports a .tiff into output_folder
    '''
    mask_folder = str(mask_folder)
    classifier_map_folder = str(classifier_map_folder)
    output_folder = str(output_folder)
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    
    ## prevent unintentional overwriting of variables outside the function:
    masks = [i for i in sorted(os.listdir(mask_folder)) if i[-5:] == ".tiff"]
    classifier_masks = [i for i in sorted(os.listdir(classifier_map_folder)) if i[-5:] == ".tiff"]

    overlapping = [i for i in masks if i in classifier_masks]
    if not ((len(overlapping) == len(masks)) and (len(overlapping) == len(classifier_masks))):
        if len(overlapping) == 0:
            raise NoSharedFilesError
        print("warning! the files in the masks and classifier maps folders do not all match! \n"
              f"The files that are present in both folders are the only ones that will be used: \n\n {str(overlapping)}")

    merged_classifier_map_folder = classifier_map_folder[:classifier_map_folder.rfind("/")] + "/merged_classification_maps"
    if not os.path.exists(merged_classifier_map_folder):
        os.mkdir(merged_classifier_map_folder)

    cell_class_df_total = pd.DataFrame()
    for i in overlapping:
        mask = tf.imread("".join([mask_folder,"/",i])).astype('int')
        class_map = tf.imread("".join([classifier_map_folder,"/",i])).astype('int')
        output, merged_classifier_mask, cell_class_df = make_cell_classification_mask(mask, 
                                                                                      class_map, 
                                                                                      merging_table = merging_table)
        if merged_classifier_mask is not None:
            tf.imwrite("".join([merged_classifier_map_folder, "/", i]), merged_classifier_mask.astype('int32')) 
        cell_class_df_total = pd.concat([cell_class_df_total, cell_class_df], axis = 0)
        tf.imwrite("".join([output_folder, "/", i]), output.astype('int32'))  
    return cell_class_df_total 

def make_cell_classification_mask(mask: np.ndarray[Union[float, int]], 
                                  classifier_map: np.ndarray[int], 
                                  merging_table: pd.DataFrame = None, 
                                  ) -> tuple[np.ndarray[float], np.ndarray[int], pd.DataFrame]:
    '''
    This function takes a mesmer-style segmentation (unique float/integer labels for every region) and a classifier map and creates a 
    version of the mask where each region is labeled instead by the mode-based integer classification of the cell-regions.

    Cells that do not fall into any class (mode in drop_list) are given a classNumber = (len(merging_table) + 1)   

    Args:
        mask (numpy array): 
            The array representation of the cell mask, usually read from a .tiff file. Often with datatype float, but 
            every number in the array should effectively be an integer (e.g., 1.0)

        classifier_mask (numpy array): 
            the array representation of the pixel classification output.

        merging_table (pandas dataframe or None): 
            a dataframe indicating how to merge different classification values in the classifier_mask. 
            Particularly needed when using unsupervised classifiers with 'excess' clusters. If None, then no merging will 
            occur & number_of_classes must be provided.
    
    Returns:
        tuple(np.ndarray, np.ndarray, pd.DataFrame):

            1. an array of integers where every cell region from the input mask array has its pixels replaced with that cell region's mode in the 
            classifier_mask array

            2. an array of integers representing the merging of the input classifier_map using the merging_table to rename and merge pixel 
            classifications. 

            3. a pandas dataframe with a single column of integers with a length equal to the number of cell regions in input mask. It represents 
            the mode based classification of all the cells and can be used in a PalmettoBUG.Analysis to group cells without using the primary 
            clustering FlowSOM method, by inserting it as a column in data.obs.
    '''
    mask = mask.copy()
    classifier_map = classifier_map.copy()

    if merging_table is not None:
        classifier_map = merge_classes(classifier_map, merging_table)
        merged_classifier_map = classifier_map.copy()
    else:
        merged_classifier_map = None
            
    regionprops = skimage.measure.regionprops(mask)
    cell_class_list = []
    for ii,i in enumerate(regionprops):
        box = i.bbox
        slicer = i.image
        single_cell = classifier_map[box[0]:box[2],box[1]:box[3]][slicer]
        counts = np.unique(single_cell, return_counts = True)
        classes = counts[0]
        counts = counts[1]
        mode_num = np.argmax(counts)
        mode = classes[mode_num]
        if mode == 0:   ## this only occurs if there is a 'background' class, after merging
           mode = 1
        mask[box[0]:box[2],box[1]:box[3]][slicer] = mode
        cell_class_list.append(mode)
    cell_class_df = pd.DataFrame()
    cell_class_df['classification'] = cell_class_list
    classy_mask = mask
    return classy_mask, merged_classifier_map, cell_class_df

def _find_region_probabilities(mask: np.ndarray[float], 
                               classifier_map: np.ndarray[int], 
                               number_of_classes: Union[int, None] = None,
                               ) -> np.ndarray[float]:
    '''
    This function finds the probability of every cell mask being a particular class by pixel percentage. It return as a numpy array where 
    the first axis (rows) are each cell, and the columns are the class probabilities (ratio of pixels of a particular class) for that cell.
    Be careful with zero-indexing! This function assumes the class parameter is 1-indexed (this is intentional, as 0 is a special index when 
    dealing with cell masks)

    This is primarily a helper function for the secondary FlowSOM function.

    Args:
        mask (numpy array): 
            The array representation of the cell mask, usually read from a .tiff file. Often with datatype float, but every 
            number in the array should effectively be an integer (e.g., 1.0)

        classifier_map (numpy array): 
            the array representation of the pixel classification output.

        number_of_classes (integer, or None): 
            The number of classes in the original pixel classifier. If None, will be the maximum value in 
            the classifier_map. Whenever possible, this value should be provided! Particularly when performing this over 
            multiple images that are meant to be part of one analysis step, since if an image happens to miss the highest class,
            then an error will occur.

    Returns:
        (numpy array): 
            has a dimension 1 length equal to the number of cell regions in the input mask, and dimension 2 length equal to the 
            number_of_classes. Each row represents a cell, with the values of each column representing the fraction of pixels in the cell 
            region of the corresponding class. USES 1-INDEXING: column 1 is the fraction of pixels of class 1, etc. 
    '''
    mask = mask.copy()
    classifier_map = classifier_map.copy()
    if number_of_classes is None:
        number_of_classes = np.max(classifier_map)    ### this depends on the assumption that the image contains the maximum class....
    if number_of_classes < np.max(classifier_map):
        number_of_classes = np.max(classifier_map)       ## for supervised classifiers (where background is an extra class)
    
    regionprops = skimage.measure.regionprops(mask)
    output_array = np.zeros([len(regionprops),number_of_classes])   ## for every mask region, list a probability for each class
    
    for ii,i in enumerate(regionprops):
        box = i.bbox
        slicey = i.image
        single_cell = classifier_map[box[0]:box[2],box[1]:box[3]][slicey]
        counts = np.unique(single_cell, return_counts = True)
        classes = counts[0]
        counts = counts[1]
        probability_slice = np.zeros([number_of_classes])
        total_counts = np.sum(counts)
        probabilities = counts / total_counts
        for j,jj in zip(classes - 1, probabilities):     ## zero-indexing affects this --> I want my classes to be 1-indexed (so... classes - 1)
            probability_slice[j] = jj
        output_array[ii] = probability_slice
    return output_array

def secondary_flowsom(mask_folder: Union[Path, str], 
                      classifier_map_folder: Union[Path, str], 
                      number_of_classes: Union[int, None] = None,
                      XY_dim: int = 10, 
                      n_clusters: int = 10, 
                      rlen: int = 50,
                      seed: int = 42,
                      ) -> tuple[FlowSOM, pd.DataFrame]:
    '''
    This function performs a FlowSOM clustering on all the cell regions of a dataset, using the fraction of each pixel class in each cell as 
    its inputs. It is intended as a secondary step of the unsupervised, Pixie-like cell classification pipeline available in PalmettoBUG. 
    Modeled intentionally after the steps of Pixie / Ark-Analysis by the Angelo lab:

            (https://github.com/angelolab/ark-analysis). 

    It is intended to be part of an alternate way to classify cells using pixel classifiers instead of a direct CATALYST-style FlowSOM on the
    cell regions themselves.

    Note that for FlowSOM integer parameters (XY_dim, n_clusters, seed) some reasonable defaults are provided, but these default -- especially 
    n_clusters -- may not be ideal for your data.  

    Args:
        mask_folder (Path or string): 
            the path to a folder containing the cell masks to cluster with FlowSOM

        classifier_map_folder (Path or string): 
            The path to a folder containing ht epixel classification maps to be used to classify the cells' masks. 

                NOTE! >>> The files in mask_folder & classifier_map_folder should have the same filenames names and be in the same order! 

        number_of_classes (integer or None): 
            the number of classes in the pixel classifier that generated the maps in classifier_map_folder. 
            If None, this will be empirically determined by reading every classification map in the folder and updating 

        XY_dim (integer): 
            the XY and dimensions of the original FlowSOM grid. (XY_dim * XY_dim) is the number of clusters generated by the 
            FlowSOM algorithm before merging to metaclusters. 

        n_clusters (integer):  
            The number of final metaclusters for the FlowSOM algorithm to output.

        rlen (integer): 
            The number of training iterations of the Self-Organizing Map

        seed (integer): 
            the random state seed to run the FlowSOM algorithm with. For reproducibility of results. 

    Returns:
        tuple(FlowSOM, pandas dataframe):

            1. FlowSOM ('fs') --> a FlowSOM object, trained & predicting from the provided cell information. fs.get_cell_data() or 
            fs.get_cluster_data() supply anndata objects with information
            see: https://flowsom.readthedocs.io/en/latest/generated/flowsom.FlowSOM.html for information about this class

            2. pandas dataframe ('anndata_fs') -->  a pandas dataframe with a single integer column with length equal to the number of cell 
            regions in the masks of the mask_folder, with values reflecting the metacluster prediciton of the FlowSOM algorithm for 
            each cell region. Once these values are merged into biologically relevant labels they can be inserted as column of 
            data.obs in a PalmettoBUG.Analysis created from the same masks 
    '''
    mask_folder = str(mask_folder)
    classifier_map_folder = str(classifier_map_folder)
    masks = [i for i in sorted(os.listdir(mask_folder)) if i[-5:] == ".tiff"]
    classifier_maps = [i for i in sorted(os.listdir(classifier_map_folder)) if i[-5:] == ".tiff"]

    overlapping = [i for i in masks if i in classifier_maps]
    if not ((len(overlapping) == len(masks)) and (len(overlapping) == len(classifier_maps))):
        if len(overlapping) == 0:
            raise NoSharedFilesError
        print("warning! the files in the masks and classifier maps folders do not all match! \n" 
              f"The files that are present in both folders are the only ones that will be used: \n\n {str(overlapping)}")

    if number_of_classes is None:
        for i in classifier_maps:
            classifier_map = tf.imread("".join([classifier_map_folder,"/",i])).astype("int")
            if number_of_classes is None:                    ## the first classification map
                number_of_classes = np.max(classifier_map)    
            if number_of_classes < np.max(classifier_map):
                number_of_classes = np.max(classifier_map) 

    counter = 0
    for i in overlapping: 
        mask = tf.imread("".join([mask_folder,"/",i])).astype("int")
        classifier_map = tf.imread("".join([classifier_map_folder,"/",i])).astype("int")
        mask_probabilities = _find_region_probabilities(mask, classifier_map, number_of_classes = number_of_classes)
        if counter == 0:
            output_array = mask_probabilities.copy()
            counter += 1
        else:
            output_array = np.append(output_array, mask_probabilities, axis = 0)

    anndata_df = pd.DataFrame()
    anndata_df.index = [i for i in range(1,number_of_classes + 1)]
    my_anndata = anndata.AnnData(output_array, var = anndata_df)
    fs = FlowSOM(my_anndata.copy(), 
                 n_clusters = n_clusters, 
                 cols_to_use = my_anndata.var.index, 
                 xdim = XY_dim, 
                 ydim = XY_dim, 
                 rlen = rlen, 
                 seed = seed)
    return fs, anndata_df


def classify_from_secondary_flowsom(mask_folder: Union[Path, str], 
                                    output_folder: Union[Path, str], 
                                    flowsom_data: FlowSOM,
                                    ) -> pd.DataFrame:
    '''
    This function takes the classifications from a secondary FlowSOM and a folder of matching cell masks, and creates 'classy' masks form that. 
    Additionally, returns a single-solumn dataframe with all the classifications from the FlowSOM (this can be  more directly accessed with 
    (flowsom_data.get_cell_data().obs['metaclustering'] + 1)).

        NOTE! >>> The classy masks are 1-indexed because 0 is a special number (background) in images, while the FlowSOM classes are 0-indexed 
                like the majority of python. This is why (flowsom_data.get_cell_data().obs['metaclustering'] + 1) describes the classes 
                accurately in the classy masks, and not just flowsom_data.get_cell_data().obs['metaclustering']. 

    Usually, the classifications here are an intermediate step, with overclustering / excessive clustering being performed as is usual for 
    FlowSOM clustering, and manual merging being a necessary step afterwards to derive biologically useful labels for the cells. 

    Args:
        mask_folder (str or Path): 
            the directory path to a folder containing the cell mask .tiffs that are to be classified with the secondary 
            FlowSOM output. 

            NOTE! >>> the FlowSOM must have been trained / predicted from the same cell masks in the same file order, or the 
                    classification will invalid. 

        output_folder (str or Path): 
            the path to a folder where the "classy masks" will be exported.

        flowsom_data (FlowSOM): 
            The trained/predicted FlowSOM object from which the predictions will be derived. 

    Returns:
        pandas dataframe: 
            a single-column of integers pandas dataframe containing the cell classification assignments from the FlowSOM. 
            It should represent (flowsom_data.get_cell_data().obs['metaclustering'] + 1), where 'flowsom_data' is the input argument 
            to the function.

    Inputs / Outputs:
        Inputs: 
            reads every file in the mask_folder as .tiff file (MUST NOT have other files / subfolders)

        Outputs: 
            for every file read-in, writes a .tiff file inside output_folder
    '''
    mask_folder = str(mask_folder)
    output_folder = str(output_folder)
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    
    ## prevent unintentional overwriting of variables outside the function:
    mesmer_masks = [i for i in sorted(os.listdir(mask_folder)) if i[-5:] == ".tiff"]
    metaclustering_for_all_cells = list(flowsom_data.get_cell_data().obs['metaclustering'] + 1)

    start = 0
    cell_class_list = []
    for j in mesmer_masks:
        mask = tf.imread("".join([mask_folder,"/",j])).astype('int')   
        regionprops = skimage.measure.regionprops(mask)
        end = start + len(regionprops)
        metaclusterings = metaclustering_for_all_cells[start:end]
        start = end
        for ii,i in zip(metaclusterings, regionprops):
            box = i.bbox
            slice = i.image
            mask[box[0]:box[2],box[1]:box[3]][slice] = ii
            cell_class_list.append(ii)
        tf.imwrite("".join([output_folder, "/", j]), mask.astype('int32'))   

    cell_class_df = pd.DataFrame()
    cell_class_df['classification'] = cell_class_list  
    return cell_class_df     

def _heatmap_secondary_flowsom(classy_mask_folder: Union[Path, str], #### superseded --> could edit (to make percentages empirical and not from training fs) and restore (?)
                              img_folder: Union[Path, str], 
                              panel: Union[pd.DataFrame, Path, str], 
                              flowsom_data: FlowSOM, 
                              output_path: Union[Path, str, None] = None, 
                              type_array: Union[None, np.ndarray[bool]] = None, 
                              classifier_name: Union[str, None] = None,
                              ) -> plt.figure:
    '''
    After the primary flowSOM and the creation of classy masks from it, this wil read in the classy masks + original images, and output a 
    heatmap showing the expression of markers in each class (as mean of the within-marker scaled expression). Useful for visualizing what 
    each class is for a merging to biological labels.

    Args:
        classy_mask_folder (str or Path): 
            The path to the folder containing the "classy masks" as .tiff files. They will be used as the class 
            regions to measure from the images in img_dir.

        img_folder (str or Path): 
            The path to a folder of images whose channels will be read to derive the heatmap values

        panel (str/Path or pandas dataframe): 
            Either a pandas dataframe, or the path to one, which provides the names of the channels in the 
            images. Normally, this is the project panel file

            NOTE! >>> panel is presumed to have 'keep' and 'name' columns where rows where keep == 1 are presumed to be the 
                channels in the images, and 'name' contains the names used to label the channels in the heatmap.

        flowsom_data (FlowSOM object): 
            a FlowSOM object, whose predictions were used to generate the files in the classy_mask_folder folder

        output_path (str/Path, or None): 
            either the path to where the heatmap should be saved, or None if you don't want the heatmap to be 
            saved to the disk. Should be the entire file path, including extension (usually .png)

        type_array (None, or boolean numpy array): 
            If None, than all the channels of the images will be used in the heatmap. Else, a boolean 
            numpy array with length equal to the number of channels where the channels will be sliced using this array before 
            shaping / plotting the data (False = corresponding channel dropped from heatmap).
            For example, if you have generated an Analysis panel with 'type', 'state', and 'none' markers you can use this to 
            only plot 'type' markers:
                    >>> type_array = np.array(Analysis_panel['marker_class'] == type)

        classifier_name (string or None): 
            If not None, will be used as the title of the heatmap

    Returns:
        maptlotlib.pyplot figure: the heatmap figure
        str or None: the filepath to where the plot was saved (or None, if not saved)

    Inputs / Outputs:
        Inputs: 
            Reads in the .tiffs for every file present in both classy_mask_folder and img_folder.

        Outputs: 
            if output_path is not None, saves a the plot at output_path
    '''
    classy_mask_folder = str(classy_mask_folder)
    img_folder = str(img_folder)
    if output_path is not None:
        output_path = str(output_path)
    if not isinstance(panel, pd.DataFrame):
        panel = pd.read_csv(str(panel))
    numpy_seed = (panel[panel['keep'] == 1]['name'].values)
    if type_array is not None:
        numpy_seed = numpy_seed[type_array]
    numpy_seed = numpy_seed[:,np.newaxis]

    classy_masks = sorted(os.listdir(classy_mask_folder))
    images = sorted(os.listdir(img_folder))

    overlapping = [i for i in classy_masks if i in images]
    if not ((len(overlapping) == len(classy_masks)) and (len(overlapping) == len(images))):
        if len(overlapping) == 0:
            raise NoSharedFilesError
        print("warning! the files in the classy masks and images folders do not all match! \n"
              f"The files that are present in both folders are the only ones that will be used: \n\n {str(overlapping)}")
    
    class_list = []
    for i in overlapping:
        classy_mask = tf.imread(f'{classy_mask_folder}/{i}')
        image = np.transpose(tf.imread(f'{img_folder}/{i}'), (1,2,0))
        regionprops = skimage.measure.regionprops(classy_mask, intensity_image = image)
        class_list = class_list + [j + 1 for j in range(0, len(regionprops))]
        for k in regionprops:
            if type_array is not None:
                numpy_seed = np.concatenate((numpy_seed, k.intensity_mean[type_array][:,np.newaxis]), axis = 1)
            else:
                numpy_seed = np.concatenate((numpy_seed, k.intensity_mean[:,np.newaxis]), axis = 1)
    
    classification_df = pd.DataFrame(numpy_seed[:,1:], index = numpy_seed[:,0]).T.astype('float')
    classification_df['classification'] = class_list
    classification_df['classification'] = classification_df['classification'].astype('category')
    class_centers = classification_df.groupby('classification', observed = False).median()
    intermediate = _quant(class_centers)
    class_centers = pd.DataFrame(intermediate, columns = class_centers.columns, index = class_centers.index)
    
    percentages = flowsom_data.get_cluster_data().obs.groupby('metaclustering').sum()['percentages'] * 100
    percentages = [np.round(i, 1) for i in percentages]
    class_centers.index = [f'{str(i)} ({ii} %)' for i,ii in zip(class_centers.index, percentages)]
    plot = sns.clustermap(class_centers, cmap = "coolwarm", linewidths = 0.01, xticklabels = True)
    if classifier_name is not None:
        plot.figure.suptitle(classifier_name, y = 1.03)
    if output_path is not None:
        plot.savefig(output_path)
    plt.close()
    return plot, output_path

def extend_masks_folder(classifier_map_folder: Union[Path, str], 
                        mask_folder: Union[Path, str], 
                        classy_mask_folder: Union[Path, str], 
                        output_directory_folder: Union[Path, str], 
                        merge_list: Union[list[int], None] = None, 
                        connectivity: int = 1,
                        ) -> None:
    '''
    Expands cell masks into a matching region of pixel classification. Can be used, for example, to segment
    irregularly shaped cell types into non-circular masks. Operates on a whole folder of images.

    Args:
        classifier_map_folder (str or Path): 
            the path to a folder of a pixel classifier's output (as .tiff files)

        mask_folder (str or Path): 
            the path to a folder of cell masks (segmentation output as .tiff files) to extend

        classy_mask_folder (str or Path): 
            The path to a folder of "classy masks" as .tiff files
            NOTE! >>> The files in classifier_map_folder, mask_folder, classy_mask_folder should all align with each other, as in:

                --> same file names in the same order

                --> the classy masks should be derived from the masks
                
                --> the numbers of the classy masks should match the numbers of the pixel classifications in the classifier_map_folder 
                    (as in, class 1 should mean the same biological thing in both: for example if class 1 is astrocyte in the class 
                    maps, class 1 must mean astrocyte in the classy masks too in order to have a valid merging/expansion on class 1)

        output_directory_folder (str or Path): 
            the path to a folder where you want to save the expanded cell masks

        merge_list (list of integers, or None): 
            a list of the classes to merge / extend the masks on. if None, then all classes are used -- if 
            there are background classes in the pixel classifier's output, then leaving merge_list = None
            is HIGHLY discouraged, as you are likely to end up with wildly large cell masks.

        connectivity (integer): 
            values = 1 or 2. This determines whether, when performing the final scikit-image watershedding step of the 
            merge / expansion, pixel are considered connected when touching diagonally (2) or not (1). This means 
            connectivity = 2 will (slightly) more aggressively extend the cell masks than connectivity = 1. 
            See: https://scikit-image.org/docs/stable/api/skimage.segmentation.html#skimage.segmentation.watershed 
            for details of the internal function in which the conectivity parameter is used. 

    Returns:
        None

    Inputs / Outputs:
        Inputs: 
            for every .tiff file shared between all three (classifier_map_folder, mask_folder, classy_mask_folder) input folders. As in,
            every filename present in all three (assumed to be from the same image), this funciton reads in those files. 

        Outputs: 
            For every shared .tiff file read in (really set of three from all input folders), will output one .tiff 
            file in the output_directory_folder
    '''
    classifier_map_folder = str(classifier_map_folder)
    mask_folder = str(mask_folder)
    classy_mask_folder = str(classy_mask_folder)
    output_directory_folder = str(output_directory_folder)
    if not os.path.exists(output_directory_folder):
        os.mkdir(output_directory_folder)

    mesmer_masks = [i for i in sorted(os.listdir(mask_folder)) if i[-5:] == ".tiff"]
    classifier_masks = [i for i in sorted(os.listdir(classifier_map_folder)) if i[-5:] == ".tiff"]
    classy_mesmer_masks = [i for i in sorted(os.listdir(classy_mask_folder)) if i[-5:] == ".tiff"]
    classifier_masks.sort()
    mesmer_masks.sort()
    classy_mesmer_masks.sort()

    overlapping = [i for i in mesmer_masks if (i in classy_mesmer_masks) and (i in classifier_masks)]
    if not ((len(overlapping) == len(mesmer_masks)) and 
            (len(overlapping) == len(classy_mesmer_masks)) and 
            (len(overlapping) == len(classifier_masks))):
        if len(overlapping) == 0:
            raise NoSharedFilesError
        print("warning! the files in the masks, classy masks and classification maps folders do not all match! \n"
              f"The files that are present in all three folders are the only ones that will be used: \n\n {str(overlapping)}")

    for i in overlapping:
        classifier_mask = tf.imread("".join([classifier_map_folder,"/",i])).astype('int')
        cell_mask = tf.imread("".join([mask_folder,"/",i])).astype('int')
        classified_cell_mask = tf.imread("".join([classy_mask_folder,"/",i])).astype('int')
        merged_class_mask = extend_classifier_masks(classifier_mask, cell_mask, classified_cell_mask, 
                                                    connectivity = connectivity, 
                                                    merge_list = merge_list)
        tf.imwrite("".join([output_directory_folder,"/",i]), merged_class_mask.astype('int32'))


def extend_classifier_masks(classifier_map: np.ndarray[int], 
                            cell_mask: np.ndarray[float], 
                            classy_mask: np.ndarray[int], 
                            merge_list: Union[list[int], None] = None,
                            connectivity: int = 1,
                            ) -> np.ndarray[int]:
    '''
    A kind of helper function for the function above (extend_masks_folder), only applied to a single cell mask + classy + 
    mask + class map set.
    It "extends" the cell masks by:

        1. iterating through each class in merge_list

        2. For all the cell masks that were classified as the class of interest, find the centroids

        3. Watershedd from all the centroids into the Union(matching class, matchings class masks) in order to expand the masks
        >>> Note that if two cell masks of the same class border each other, then the shape of the original mask areas can be changed in
        this process (one cell can steal a bit from its neighbor)

    Args:
        classifier_map (numpy array): 
            The pixel classifier output for a single image

        cell_mask (numpy array): 
            The cell masks (segmentation algorithm output) for a single image

        classy_mask (numpy array): 
            The "classy masks" for a single image, where the cell mask regions uqniue ids have been replaced with a 
            single classfication for each cell id. 
            NOTE >>> these three arguments must be the same shape / be from the same image!

        merge_list (list of integers, or None): 
            The pixel classification that you want matching classy masks to be extended into. If None, 
            extend all pixel classes 

        connectivity (integer): 
            1 or 2. Determines if diagonally & orthogonally adjacent pixels are considered touching (2) or only 
            orthogonally adjacent pixels are considered touching (1) for the purposes of the watershedding algorithm. 

    Returns:
        numpy array: the new cell masks for the image, having been extended by the algorithm. 
    '''
    classifier_map = classifier_map.copy()
    cell_mask = cell_mask.copy()
    classy_mask = classy_mask.copy()
    ## first, set the classifier_map regions inside the classy_mesmer_mask equal 
    #       to the values of the classy_mesmer_mask (prevents duplication of areas)
    classifier_map[classy_mask > 0] = classy_mask[classy_mask > 0]
    if merge_list is None:
        new_merge_list = np.unique(classy_mask)
        dropped_list = []
    else:
        new_merge_list = [i for i in np.unique(classy_mask) if i in merge_list]  ## filter what gets merged based on 
        dropped_list = [i for i in np.unique(classy_mask) if i not in merge_list]
    
    output = np.zeros(classifier_map.shape)
    for i in new_merge_list:
        if i != 0:
            # binarize classifier map, with this class = 1, every other class + background = 0
            one_class_array = classifier_map.copy()
            one_class_array[classifier_map != i] = 0
            one_class_array[classifier_map == i] = 1
                                                    ## to prevent this class from invading cells of class "0"
            one_class_array[cell_mask > 0] = 0   ## first set all regions inside original deepcells masks to zero 
            one_class_array[classy_mask == i] = 1 ## then restore the areas inside classy_masks that match classs
        
            # drop cells not in the class from the cell masks:
            one_class_masks = cell_mask.copy()
            one_class_masks[classy_mask != i] = 0
    
            ## do the merging
            this_class_merging = _extend_classifier_binary_helper(one_class_array, one_class_masks, connectivity = connectivity)

            restore_original_cells = one_class_masks > 0     # this and the following line prevents an artifact of watershedding that can change the original segmentation masks.
            this_class_merging[restore_original_cells] = one_class_masks[restore_original_cells]

            output = output + this_class_merging
        else:   # if cells are class '0' they need to be handled, too
            inside_masks = (cell_mask > 0).astype('int')
            insde_classy_masks = (classy_mask > 0).astype('bool')
            one_class_masks = cell_mask.copy()
            one_class_masks[classy_mask != i] = 0
            one_class_masks[classy_mask == i] = 1001   ## zeroed out classes' cells are not deleted, but saved as class 1001  
                                                        # (a sufficiently high number of nights that it should never conflict
                                                        # with user choices for classes). It should be advertised as a special number (?)
            one_class_masks[insde_classy_masks] = 0
            inside_masks = one_class_masks * inside_masks     ## zero out all inside_masks regions that are not classified as 1, 
                                                                    # while maintaining the original number for those
            output = output + inside_masks

    for i in dropped_list:   ### handle the masks of ignored classes (basically just copy them over into the new merged masks)
        inside_masks = (cell_mask > 0).astype('int')
        one_class_masks = cell_mask.copy()
        one_class_masks[classy_mask != i] = 0
        inside_masks = one_class_masks * inside_masks 
        output = output + inside_masks
    return output.astype('int')
        
def _extend_classifier_binary_helper(classifier_map: np.ndarray[int], 
                                     cell_mask: np.ndarray[int], 
                                     connectivity: int = 1,
                                     ) -> np.ndarray[int]:
    '''
    A Helper function for the function above (extend_classifier_masks), for extending a single class / cell mask pair after they have 
    been binarized and restricted with classy mask input.

    Args:
        classifier_map (numpy array): 
            The binarized classification map, with every pixel of a desired class OR any pixel within the 
            matching classy mask regions set to 1, and all other pixels set to 0.

        cell_mask (numpy array): 
            The cell mask after being restricte to only cells that were classified as the desired class (other cell 
            mask pixel set to 0)

        connectivity (integer): 
            1 or 2. Determines if diagonally & orthogonally adjacent pixels are considered touching (2) or only 
            orthogonally adjacent pixels are considered touching (1) for the purposes of the watershedding algorithm. 

    Returns:
        numpy array: the extended cell masks for the class
    '''
    classifier_map = classifier_map.copy()
    cell_mask = cell_mask.copy()
    # merge the two masks
    uni_mask = (cell_mask > 0).astype('int')
    uni_mask = cv.bitwise_or(uni_mask, classifier_map.astype('int')).astype('float')
    
    # find centroids of mesmer masks
    cell_regions = skimage.measure.regionprops(cell_mask)
    centroids = []
    labels = []
    for i in cell_regions:
        centroids.append(i.centroid)
        labels.append(i.label)
    label_array = np.array(labels).astype('int')
    centroid_array = np.round(np.array(centroids)).astype('int')
    
    # Use the centroid coordinates [X,Y] to plot them onto a blank array the size of the image 
    #               (centroids >0 counting up from 1, while everything else = 0)
    image_centroids = np.zeros((cell_mask.shape[0], cell_mask.shape[1]))
    for i,ii in zip(centroid_array, label_array):
        image_centroids[i[0],i[1]] = ii
    
    # Watershed from the centroids, following the merged classifier/mesmer mask
    watershed_img = np.zeros((cell_mask.shape[0], cell_mask.shape[1]))
    segmented_with_class = skimage.segmentation.watershed(watershed_img, 
                                            mask = uni_mask, 
                                            markers = image_centroids.astype('int'), 
                                            connectivity = connectivity)   ## this function resets the index on the labels...
    # Put the indexes / labels back to where they were:
    if np.unique(cell_mask)[0] == 0:
        unique_masks = np.unique(cell_mask)[1:]
        unique_new_masks = np.unique(segmented_with_class)[1:]
    else:
        unique_masks = np.unique(cell_mask)
        unique_new_masks = np.unique(segmented_with_class)

    for i,ii in zip(unique_masks, unique_new_masks):
        segmented_with_class[segmented_with_class == ii] = i

    return segmented_with_class