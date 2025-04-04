'''
This module contains a single Analysis Class which handles the back-end of the main CATALYST-style Analysis pipeline of PalmettoBUG, and
is available in the public (non-GUI) API of PalmettoBUG.

This is used in the GUI by the fourth tab of the program. 


While PalmettoBUG as a whole, and this script, is licensed under the GPL3 license, large portion of this file can be considered to be derived
from the CATALYST R package::
    
    (https://github.com/HelenaLC/CATALYST/tree/main) license: GPL >= 2

functions that are clearly derived from CATALYST are marked with a::

    # *** deriv_CATLAYST (note)

Specfically, much of the functionality & form of the CATALYST package was consciously translated into python from R
Prominently, the panel / metadata structure, column names (such as the type / state/  none treatment of marker_class column), etc. of CATALYST 
is preserved as well as much of the functionalities of CATALYST.

Only a few functions (for example, the NRS plot and some of those involving specific data calculations preceding graphing) involved strict 
translation of R --> python. While for many, the appearance of the final plot was translated in whatever means would most closely replicate the 
result seen in CATALYST

Some functions are new / not in CATALYST (ex:  the cluster vs. cluster comparisons, like the violin/bar/heatmap) or implementated differently 
(for example, the FlowSOM performed here has scaling option inspired by pixie / ark-analysis [https://github.com/angelolab/ark-analysis -- MIT license])

The statistics block is made to have somewhat similar output as CATALYST / diffcyt (a similar R package: :

    https://github.com/lmweber/diffcyt [MIT + file license]),

however the implementation here is quite different.
'''

import os
from typing import Union
from pathlib import Path
import tempfile as tp
import tkinter as tk
import warnings

import numpy as np
import pandas as pd
import anndata as ann
import scanpy as sc 
import scipy
from scipy.stats import gaussian_kde
import matplotlib.pyplot as plt 
from matplotlib.patches import Patch
import seaborn as sns
import seaborn.objects as so 
import statsmodels.api as sm
import sklearn.preprocessing as skpre
from sklearn.manifold import MDS
from sklearn.decomposition import PCA
from sklearn.neighbors import KernelDensity
import skimage
import tifffile as tf

from .._vendor import sigfig
from .._vendor import fcsparser
#from .._vendor.flowsom import FlowSOM, plot_stars
## anticipate de-vendorization:
from flowsom import FlowSOM
from flowsom.pl import plot_stars
from .._vendor.qnorm import quantile_normalize
from ..Utils.sharedClasses import warning_window, Analysis_logger

warnings.filterwarnings("ignore", message = "Transforming to str index")   ## anndata implicit modification warning that is not necessary
warnings.filterwarnings("ignore", message = "Observation names are not unique")  ## anndata UserWarning that is not necessary
warnings.filterwarnings("ignore", message = "Modifying `X` on a view")    ## I always want to overwrite / modify the anndata object! -- except when I am intentionally using .copy()

plt.style.use('ggplot')

__all__ = ["Analysis"]

homedir = __file__.replace("\\","/")
homedir = homedir[:(homedir.rfind("/"))]
## do it twice to get up to the top level directory:
homedir = homedir[:(homedir.rfind("/"))]
temp_img_dir = homedir + "/Assets/temp_image.png"

def _py_catalyst_quantile_norm(pd_groupby) -> np.ndarray[float]:
    ''' 
    This is a helper function for the median / heatmap plotting function immediately below 
    '''
    pd_groupby = pd_groupby.copy()
    np_groupby = np.array(pd_groupby)
    np_groupby = np.median(np_groupby, axis = 0)
    np_groupby = _quant(np_groupby)
    return np_groupby

def _quant(array: np.ndarray[float], 
          lower: float = 0.01, 
          upper:float = 0.99, 
          axis: int = None,
          ) -> np.ndarray[float]:
    '''
    This is a helper function for _py_catalyst_quantile_norm
    '''
    quantiles = np.quantile(array, (lower, upper), axis = axis) 
    array = (array - quantiles[0])  / (quantiles[1] - quantiles[0])
    array = np.nan_to_num(array)
    array[array > 1] = 1
    array[array < 0] = 0
    return array

class Analysis:   
     ## helpful discussion for fixing sphinx errors https://stackoverflow.com/questions/66891018/sphinx-what-is-the-cause-for-warning-duplicate-object-description
     # Although I think the cause of my erros in this case is slightly different: it is because the autoapi is recoring attributes from __init__  
     # (which I don't want) creating duplication warnings with the properly named Attributes in the class docstring. I changed the class doc string to say 
     # "Key Attributes" for now, to silence the warnings, but Ideally I revert that while somehow blocking the attributes in __init__   
    '''
    This class is essentially a python port of CATALYST -- but with certain differences, include slightly different calculations / normalizations, 
    additional functions, and missing functions.::

        There are a few broad types of methods, "load_" , "do_" , and "plot_". Methods starting with "do_" tend to execute a transformation or 
        a calculation on the data (such as statistics, UMAP / PCA, or scaling). Those starting with "plot_" always generate a plot, usually returning
        a matplotlib figure.

    Input / Output:
        if a method contains a "filename" keyword arugment (with default = None), then supplying that argument will trigger the export of 
        the method's return data to the directory. As in, for a plotting method, supplying a filename means that the it will not only return a 
        matplotlib figure as usual, but will ALSO export the figure to the directory as a PNG file, at::

            self.save_dir/{filename}.png

        Methods that return data tables are similar, but export to self.data_table_dir (not self.save_dir)

    Key Attributes:         
        data (anndata.AnnData): This is an anndata object containing the numerical values of the channels in data.X, the event 
            anntotation in data.obs and the antigen annotations in .data.var. Pre-arcsinh transformed data lives in data.uns, 
            but is not used for any function in this pipeline.
            data.obs starts out with the same information as the metadata, except each unique entry in metadata
            (representing a unique sample_id) is replicated across all the sample_id events (there are usually >1 cell per image!). 
            At the same time, data.var starts out the same as panel (truly identical). As clusterings are performed, new columns can be \
            added to data.obs that did not initially exist in the metadata

        metadata & panel (pandas dataframes): these are the metadata and panel pandas dataframes that get loaded into data.obs and 
            data.var & represent the metadata.csv and Analysis_panel.csv files in the directory of the Analysis. 

        UMAP_embedding & PCA_embedding (anndata.AnnData): usually downsampled from data, these are anndata objects with UMAP or 
            PCA values for plotting in 2 dimensions

        directory (str): the path to the folder where the Analysis is initialized / performed. Used to find the input data and
            set up the directories for outputs. 

        save_dir (string): the path to the folder where plots generated by this class are saved
        
        data_table_dir (string): the path to the folder where datatables (such as exports or statistics) are saved

        clusterings_dir (string): folder where clustering .csv files are saved and expected to be for reload
    '''
    def __init__(self, in_gui = False):
        ''' 
        '''
        self._in_gui = in_gui   ## This toggles warnings from being in GUI pop ups (True) vs. being printed (False). 
        self.directory = None
        self.data = None
        self.back_up_data = None
        self.logger = None
        self.clusterings_dir = None
        self._scaling = "unscale"
        self.unscaled_data = None
        self._quantile_choice = None
        self.input_mask_folder = None
        self._distance_edt_data = None
        self.is_batched = 0 ## three states: 0,1,2 -- used to track the state of the batch correction / scaling

    def load_data(self, 
                  directory: Union[Path, str], 
                  save_dir: str = "Plots",
                  data_table_dir: str = "Data_tables",
                  csv: Union[str, Path, None] = None,
                  csv_additional_columns: list = [],
                  load_regionprops = True,
                  ) -> None:
        '''
        Load the data for an analysis       
        
        Args:
            directory (string or Path): the path to the directory where the Analysis is to be performed. If csv is None, then the expectation 
                    is that there should be .fcs files inside a subfolder of this directory (specifically inside a /Analysis_fcs subfolder)

            save_dir & data_table_dir (str): these allow you to specify what self.save_dir and self.data_table_dir will be WITHIN the main
                directory. By default save_dir == "Plots" and data_table_dir == "Data_tables". If you want export outside the main directory,
                Set these attributes later using a full file path string.

            csv (string/Path or None): the path to a csv file containing data ready to import into PalmettoBUG (the format for this kind of data 
                    matches what PalmettoBUG exports in an Analysis). If None (default) then presumes .fcs files are available in the appropriate 
                    folder (directory/Analysis_fcs) and will load from those files.

            csv_additional_columns (list): ONLY used if loading from csv -- this is a list of non-standard column names in csv that are to be treated 
                    as metadata (will end up in self.data.obs) and not as numerical data (destined for self.data.X). The "standard" metadata column
                    names are those commonly encountered in PalmettoBUG operation, such as "sample_id" or "leiden".
                    This is mainly intended to increase flexibility in cases where PalmettoBUG is being used outside the GUI & a novel metadata 
                    category is created.

            load_regionprops (boolean): whether to load the regionprops as well. This is important if you plan on doing any spatial analysis
                    as this loads the centroids, etc. It does not APPEND the regionprops to the anndata object (self.data), and you must call
                    append_regionprops in order to do that.

        Input/Output:
            Input: expects either a .csv file at the path defined by the [csv] argument, or expects a folder of only .fcs files located at [directory]/Analysis_fcs. 
        '''
        directory = str(directory)
        self.directory = directory
        
        self.directory  = self.directory.replace("\\" , "/")
        if csv is None:
            self.metadata = pd.read_csv(self.directory + '/metadata.csv')
            self.metadata['condition'] = self.metadata['condition'].astype('str')
            metadata_cat = pd.CategoricalDtype(categories = self.metadata['condition'].unique(), ordered = True)
            self.metadata['condition'] = self.metadata['condition'].astype(metadata_cat)
            self.metadata['patient_id'] = self.metadata['patient_id'].astype('str')
            self.metadata['sample_id'] = self.metadata['sample_id'].astype('str')
            self.panel = pd.read_csv(self.directory + '/Analysis_panel.csv')
        else:
            pass

        self.save_dir = self.directory + f"/{save_dir}"
        if not os.path.exists(self.save_dir):
            os.mkdir(self.save_dir)

        self.data_table_dir = self.directory + f"/{data_table_dir}"
        if not os.path.exists(self.data_table_dir):
            os.mkdir(self.data_table_dir)

        ## likely strictly unnecessary, as mergings can directly loaded or saved from pandas dataframes as people please without this folder being used
        if self._in_gui:
            if csv is not None:
                log_dir = directory[:directory.rfind("/")]
            else:
                log_dir = directory
            global Analysis_log
            Analysis_log = Analysis_logger(log_dir).return_log()
            self.logger = Analysis_log

            self.mergings_dir  = self.directory + "/mergings"
            if not os.path.exists(self.mergings_dir ):
                os.mkdir(self.mergings_dir )
        
        self.clusterings_dir  = self.directory + "/clusterings"

        if csv is None:
            self._load_fcs()
        else:
            self._load_csv(csv, additional_columns = csv_additional_columns)
        if load_regionprops:
            try:
                self.load_regionprops(auto_panel = False)
                    ## do this so that squidpy interoperativity is simpler / seam-less
                    #### append regionprops is a different matter though... require that to be chosen by the user
                self._spatial = True
            except Exception:
                print("Could not load regionprops data, presuming this is a solution-mode dataset -- Spatial analyses will not be possible.")
                self._spatial = False

    def _load_fcs(self) -> None:
        '''
        Helper for load_data that handles the loading of .fcs file information from directory/Analysis_fcs
        '''
        warnings.filterwarnings("ignore", message = "Passing a BlockManager")
        warnings.filterwarnings("ignore", message = "Transforming to str index")
        warnings.filterwarnings("ignore", message = "Observation names are not unique") 
        metadata = self.metadata
        panel = self.panel
        panel.index = panel['antigen']

        self.UMAP_embedding = None
        self.PCA_embedding = None
        self.fcs_directory = self.directory  + "/Analysis_fcs"
        self.fcs_dir_names = sorted(os.listdir(self.fcs_directory))

        if len(self.fcs_dir_names) != len(self.metadata):
            if self._in_gui:
                warning_window("Metadata file_name column and number of fcs files in analysis do not match -- \n" +
                               "only keeping data present in both for analysis!")
                Analysis_log.info("Metadata file_name column and number of fcs files in analysis do not match -- \n" +
                                  "only keeping data present in both for analysis!") 
            else:
                print("Metadata file_name column and number of fcs files in analysis do not match -- \n" +
                      "only keeping data present in both for analysis!") 
            new_fcs_filenames = []
            truth_array = np.zeros(len(self.metadata)).astype('bool')
            for i in list(self.metadata['file_name']):
                if i in self.fcs_dir_names:
                    new_fcs_filenames.append(i)
                    truth_array = truth_array + np.array(self.metadata['file_name'] == i).astype('bool')

            self.metadata = self.metadata[truth_array]
            self.fcs_dir_names = new_fcs_filenames

        self.fcs_path_list = ["".join([self.fcs_directory,"/",i]) for i in self.fcs_dir_names]

        intensities = pd.DataFrame()
        self.length_of_images = [0]
        length_of_images2 = []
        tally = 0
        warnings.filterwarnings("ignore", message = "The default channel names")
        for i in self.fcs_path_list:
            _, fcs_read_in = fcsparser.parse(i)
            tally = tally + len(fcs_read_in.index)
            self.length_of_images.append(tally)
            length_of_images2.append(len(fcs_read_in.index))
            intensities = pd.concat([intensities, fcs_read_in], axis = 0)
        warnings.filterwarnings("default", message = "The default channel names")

        if len(intensities.columns) > len(panel):
            try:
                intensities = intensities.drop("Object", axis = 1)   ## if Object column is in the fcs's drop it
            except KeyError:
                pass

        dropped_antigen_list = []
        for i in intensities.columns:
            if intensities[i].sum() == 0:
                intensities = intensities.drop(i, axis = 1)
                dropped_antigen_list.append(i)
        if len(dropped_antigen_list) > 0:
            if self._in_gui:
                warning_window(f"The following antigens had only 0 values! They were dropped from the experiment: \n\n {str(dropped_antigen_list)}")
                Analysis_log.info(f"The following antigens had only 0 values! They were dropped from the experiment: \n\n {str(dropped_antigen_list)}") 
            else:
                print(f"The following antigens had only 0 values! They were dropped from the experiment: \n\n {str(dropped_antigen_list)}")

        panel = panel.T.drop(dropped_antigen_list, axis = 1).T

        exprs = pd.DataFrame(np.arcsinh(intensities / 5))
        exprs.columns = panel["antigen"]

        metadata_long = pd.DataFrame()
        sample_id_array = np.zeros([0])
        counter = 0
        for i,ii in zip(self.length_of_images[:-1], self.length_of_images[1:]):
            slicer = np.full(shape = [ii - i], fill_value = counter)
            sample_id_array = np.append(sample_id_array,slicer)
            counter += 1
            
        metadata_long['sample_id'] = sample_id_array.astype('int').astype('str')

        meta_file_dict = {}
        meta_patient_dict = {}
        meta_condition_dict = {}
        for i,ii in enumerate(metadata["sample_id"]):
            meta_file_dict[ii]= list(metadata.iloc[i])[0]
            meta_patient_dict[ii]= list(metadata.iloc[i])[2]
            meta_condition_dict[ii]= list(metadata.iloc[i])[3]

        filenames = metadata_long.replace(meta_file_dict)
        patient_ids = metadata_long.replace(meta_patient_dict)
        conditions = metadata_long.replace(meta_condition_dict)

        metadata_long['file_name'] = filenames
        metadata_long['patient_id'] = patient_ids
        metadata_long['condition'] = conditions
        metadata_long.index = exprs.index

        self.metadata["number_of_cells"] = length_of_images2

        self.data = ann.AnnData(X = exprs, var = panel, obs = metadata_long)
        self.data.obs["sample_id"] =  self.data.obs["sample_id"].astype("category")
        self.data.obs["patient_id"] =  self.data.obs["patient_id"].astype("category")
        self.data.obs["condition"] =  self.data.obs["condition"].astype("category")
        self.data.obs = self.data.obs.reset_index().drop("index", axis = 1)

        self.data.uns['counts'] = np.array(intensities)   
                        # this will be the storage place for the pre-arcsinh transformed counts data (not really needed?)
        self.unscaled_data = None
        self._scaling = 'unscale'

    def _load_csv(self, 
                  csv_path: Union[Path, str], 
                  do_arcsinh: bool = False,
                  additional_columns = [],    ## in case you added a custom metadata column to the data -- list all additional columns here. 
                                                    # Must not have the same name as an antigen column (this parameter is currently not available in the GUI)
                  ) -> None:
        '''
        Helper for load_data that handles the loading of a csv file (this csv is usually exported from PalmettoBUG as well, and expects a
        particular format that PalmettoBUG can export)
        '''
        csv_path = str(csv_path)
        self.UMAP_embedding = None
        self.PCA_embedding = None
        data = pd.read_csv(csv_path)
        data.to_csv(self.directory + "/source_CSV.csv")

        marker_class_included = False
        marker_class = data.copy().iloc[-1,:]
        if np.array(marker_class == "na").sum() != 0: 
            marker_class_dict_rev = {"0.0" : 'none', "1.0" : 'type', "2.0" : ' state', "3.0" : "spatial_edt"}
            marker_class = marker_class[marker_class != "na"].astype('str').replace(marker_class_dict_rev)
            data = data.iloc[:-1, :]
            marker_class_included = True

        # self.data anndata object should be relatively easy:
        try:
            data = data.drop('distance_to_bmu', axis = 1)
        except KeyError:
            pass
        possible_metadata_columns = ["index",
                                     "metaclustering", 
                                     "clustering", 
                                     "merging", 
                                     "classification", 
                                     "sample_id", 
                                     "patient_id", 
                                     "condition",
                                     "file_name", 
                                     "leiden", 
                                     "spatial_leiden",
                                     "scaling"] + additional_columns
        actual_metadata_columns = [i for i in data.columns if i in possible_metadata_columns]
        for i in data.columns:
            if i in actual_metadata_columns:
                data[i] = data[i].astype('str')
            else:
                data[i] = data[i].astype('float')
        data_X = data.drop(actual_metadata_columns, axis = 1).astype('float')
        if do_arcsinh is True:
            data_arcsinh = np.arcsinh(np.array(data_X) / 5) # don't use arcsinh transform (or make optional), to avoid double transformations
                                                                # As exported data from PalmettoBUG is already arcsinh transformed
        else:
            data_arcsinh = np.array(data_X)
        obs = data[actual_metadata_columns]

        #self.directory = csv_path[:csv_path.rfind("/")]
        # now self.metadata
        try:
            self.metadata = pd.read_csv(self.directory + '/metadata.csv') 
        except Exception:
            filenames = obs['file_name'].unique()
            self.metadata = pd.DataFrame()
            self.metadata['file_name'] = filenames
            patient_dict = {}
            condition_dict = {}
            sample_dict = {}
            for i, ii, iii, iv in zip(obs['file_name'], obs['patient_id'], obs['condition'], obs['sample_id']):
                patient_dict[i] = ii
                condition_dict[i] = iii
                sample_dict[i] = iv
            self.metadata['sample_id'] = self.metadata['file_name'].replace(sample_dict).astype('int')
            self.metadata['patient_id'] = self.metadata['file_name'].replace(patient_dict).astype('category')
            self.metadata['condition'] = self.metadata['file_name'].replace(condition_dict).astype('str')

            self.metadata = self.metadata.sort_values('sample_id', ascending = True)
            self.metadata['sample_id'] = self.metadata['sample_id'].astype('category')
            metadata_cat = pd.CategoricalDtype(categories = self.metadata['condition'].unique(), ordered = True)
            self.metadata['condition'] = self.metadata['condition'].astype(metadata_cat)

            self.metadata.to_csv(self.directory + '/metadata.csv', index = False) 

        # now self.panel  (will assume ALL antigens are type, but export the self.panel to a file to allow editing of that)
        try:
            self.panel  = pd.read_csv(self.directory + '/Analysis_panel.csv') 
        except Exception:
            self.panel = pd.DataFrame()
            self.panel['fcs_colname'] = data_X.columns
            self.panel['antigen'] = data_X.columns
            if marker_class_included is True:
                self.panel['marker_class'] = list(marker_class)
            else:
                self.panel['marker_class'] = 'type'
                if self._in_gui:
                    warning_window("All antigens from the csv have been set to 'type' in the panel file! \n" +
                                    "Open the Analysis_panel.csv file, edit, & reload the experiment to change this!")
                else:
                    print("All antigens from the csv have been set to 'type' in the panel file! \n" +
                           "Open the Analysis_panel.csv file, edit, & reload the experiment to change this!")

            self.panel.to_csv(self.directory + '/Analysis_panel.csv', index = False) 
            
        var = self.panel.copy()
        var.index = var['antigen']
        self.data = ann.AnnData(data_arcsinh, var = var, obs = obs)
        self.data.uns['counts'] = np.array(data_X)
        self.metadata["number_of_cells"] = list(obs.groupby('sample_id', observed = True).count()['condition'])
        self.unscaled_data = None
        self._scaling = 'unscale'

        self.data.obs["sample_id"] =  self.data.obs["sample_id"].astype('str').astype("category")
        self.data.obs["patient_id"] =  self.data.obs["patient_id"].astype("category")
        self.data.obs["condition"] =  self.data.obs["condition"].astype("category")
        self.data.obs = self.data.obs.reset_index().drop("index", axis = 1)

    def load_regionprops(self, 
                         regionprops_directory: Union[Path, str, None] = None, 
                         auto_panel: bool = True,
                         ) -> pd.DataFrame:
        '''
        This method handles the loading of regionprops data 
        
        Args:
            regionprops_directory (Path, string, None): 
                The path to a folder containing the regionprops .csv files exported during region
                measurements. If None, then assumes this regionprops folder exists in the usual location of an analysis -- i.e., in a 
                /regionprops folder one folder above this class's self.directory

            auto_panel (bool): 
                If True, uses the automatic type / state / none assignments for each region property and proceeds immediately 
                into appending the regionproperties to the dataset. If False, then you can edit the returned dataframe to reflect your 
                desired marker_class assignments, and feed that into self.append_regionprops

        Returns:
            (pandas dataframe): 
                an automatic Regionprops_panel.csv file (mimics an Analysis_panel.csv file, treating each region property like 
                an antigen). Centroid-0 / centroid-1 are set to marker_class 'none', while all other regionprops are left as 'type' markers

        Input/Output:
            Input: 
                reads from the provided regionprops_directory. Expects only .csv files representing regionproperties -- all with the
                same columns of data to allow concatenation -- inside this folder.

            Output: 
                writes a file to  --  self.directory/Regionpprops_panel.csv -- which is the same format as the Analysis_panel.csv, having 
                a row for each "marker", with 3 columns for its name(s) and marker_class (type/state/none). But in this case, 
                the "markers" are not antigens, but regionproperties like eccentricity, area, etc. 

        '''
        try:
            self.data.var.T['axis_major_length']  
            if self._in_gui:  
                tk.messagebox.showwarning("Warning!", 
                    message = "Region property data already currently loaded! ('axis_major_length' column already present). \n" +
                            "Aborting Regionprops load to avoid duplicate data.")
            else:
                print("Region property data already currently loaded! ('axis_major_length' column already present). \n" +
                            "Aborting Regionprops load to avoid duplicate data.")
            return
        except KeyError:
            pass
        if regionprops_directory is None:
            regionprops_directory = self.directory[:self.directory.rfind("/")] + "/regionprops/"
        regionprops_directory = str(regionprops_directory)
        roi_areas = sorted(os.listdir(regionprops_directory))
        region_props_tables = ["".join([regionprops_directory,"/",ii]) for ii in roi_areas]
        regionprops = pd.DataFrame()
        for i in region_props_tables:
            read_in = pd.read_csv(i)
            regionprops = pd.concat([regionprops, read_in], axis = 0)

        regionprops.index = regionprops['Object']
        # drop centroid-0/1 from main dataframe and load instead as self.data.obsm['spatial'] for interoperability with squidpy --> could also lead to 
                # an alternate way to execute the spaceANOVA portion of the program
        X = np.array(regionprops['centroid-0'])
        Y = np.array(regionprops['centroid-1'])
        obsm_key = np.zeros([2, len(X)])
        obsm_key[0] = X
        obsm_key[1] = Y
        self.data.obsm['spatial'] = obsm_key.T
        self.data.uns['areas'] = regionprops['area']
        try:
            self.input_mask_folder = regionprops['mask_folder'].values[0]
            to_drop = ['Object', 'image_area', 'centroid-0', 'centroid-1', 'mask_folder']
        except Exception:
            to_drop = ['Object', 'image_area', 'centroid-0', 'centroid-1']

        regionprops = regionprops.drop(to_drop, axis = 1)

        self.regionprops_data = regionprops
        try:
            regionprops_panel = pd.read_csv(self.directory + '/Regionprops_panel.csv')
            if (self._in_gui) and (len(regionprops_panel.index) != len(regionprops.columns)):
                raise Exception 
        except Exception:
            regionprops_panel = pd.DataFrame()
            regionprops_panel['fcs_colname'] = regionprops.columns
            regionprops_panel['antigen'] = regionprops.columns
            regionprops_panel['marker_class'] = 'type'
            regionprops_panel.to_csv(self.directory + '/Regionprops_panel.csv', index = False) 
        if auto_panel is True:
            self.append_regionprops()
        return regionprops_panel

    def append_regionprops(self, 
                           regionprops_panel: Union[pd.DataFrame, str, Path, None] = None, 
                           ) -> None:
        ''' 
        Continuation of load_regionprops. Useful if you don't like the automatic type / state / none assignments for each region property.

        This adds the regionprops data & panel to the main anndata object in this class 
        
        NOTE: don't call more than once!! You can duplicate data columns that way.

        Reads in the Regionprops_panel from self.directory/Regionprops_panel.csv
        '''
        length_check = (len(self.regionprops_data) != len(self.data.obs))
        drop_check = (len(self.data.obs) < np.max(self.data.obs.index.astype('int')))
        if length_check and not drop_check:
            if self._in_gui: 
                tk.messagebox.showwarning("Warning!", message = "Region property data and currently loaded .fcs data do not match in length!" +
                                           "\nAborting regionprops load")
            else:
                print("Region property data and currently loaded .fcs data do not match in length!" +
                      "\nAborting regionprops load")
            return
        if regionprops_panel is None:
            self.regionprops_panel = pd.read_csv(self.directory + '/Regionprops_panel.csv')
        else:
            if isinstance(regionprops_panel, pd.DataFrame):
                self.regionprops_panel = regionprops_panel
            else:
                self.regionprops_panel = pd.read_csv(str(regionprops_panel))
        if drop_check:
            self.regionprops_data = self.regionprops_data.reset_index().drop('Object', axis = 1)
            self.regionprops_data = self.regionprops_data.loc[self.data.obs.index,:]

        self.regionprops_panel.index = self.regionprops_panel['antigen']
        self.panel = pd.concat([self.panel, self.regionprops_panel], axis = 0)

        if self.unscaled_data is None:
            new_X  = np.concatenate((self.data.X.copy(), np.array(self.regionprops_data)), axis = 1)
            self.data = ann.AnnData(X = new_X, var = self.panel, obs = self.data.obs, obsm = self.data.obsm, uns = self.data.uns, obsp = self.data.obsp)
        else:
            new_X  = np.concatenate((self.unscaled_data.copy(), np.array(self.regionprops_data)), axis = 1)
            self.data = ann.AnnData(X = new_X, var = self.panel, obs = self.data.obs, obsm = self.data.obsm, uns = self.data.uns, obsp = self.data.obsp)
            self.unscaled_data = None
            self.do_scaling(scaling_algorithm = self._scaling, upper_quantile = self._quantile_choice)
        if self._in_gui: 
            Analysis_log.info("Appended regionprops data.") 
    
    def filter_data(self, 
                   to_drop: str, 
                   column: str = "sample_id",
                   ) -> None:                                                # *** deriv_CATALYST (in name & effect, not actually translated)
        '''
        This function drops all rows matching sample_id_to_drop in the provided column from self.data. 
        It also clears any dimensinality reduction previously performed
        '''
        if self.back_up_data is None:
            self.back_up_data = self.data.copy()
            
        filterer = self.data.obs[column].astype('str') != str(to_drop) 
        if (column == "sample_id") or (column == "patient_id") or (column == "condition"):
            filter2 = (self.metadata[column].astype('str')  != str(to_drop))
            self.metadata = self.metadata[filter2].copy()

        self.data = self.data[filterer].copy()
        if self.unscaled_data is not None:
            self.unscaled_data = self.unscaled_data[filterer].copy()
        #self.data.obs = self.data.obs.reset_index().drop('index', axis = 1)

        if column in self.metadata.columns:
            self.metadata = self.metadata[self.metadata[column] != str(to_drop)]
        
        if self.UMAP_embedding is not None:
            filterer = (self.UMAP_embedding.obs[column].astype('str') != str(to_drop))
            self.UMAP_embedding = self.UMAP_embedding[filterer].copy()
        if self.PCA_embedding is not None:
            filterer = (self.PCA_embedding.obs[column].astype('str') != str(to_drop))
            self.PCA_embedding = self.PCA_embedding[filterer].copy()

    def do_COMBAT(self, 
                  batch_column: str, 
                  covariates = None,
                  ) -> None:
        ''' 
        Performs scanpy's combat implementation on self.data 
        '''
        #if self.unscaled_data is None:   ## now scaling the data will always undo a batch correction (since batch correction will never touch the scaling backup)
        #    self.unscaled_data = self.data.X.copy()
        self.data.X = sc.pp.combat(self.data.copy(), key = batch_column, covariates = covariates, inplace = False).copy()
        if self.is_batched > 0:
            print('Warning! You have performed a batch correction twice on the same data! Are you sure this was intentional?')
        if (self.unscaled_data is None) and (self.is_batched != 1):
            self.is_batched = 1    ## batch correction is permanent for this instance of an Analysis
            print('This batch correction is permanent (until Analysis reload)')
        else:
            self.is_batched = 2  ## batch correction will be lost if scaling is performed again (that would also reset self.is_batch = 0)
            print('This batch correction will be lost / overwritten if a further scaling of the data is performed')

    def do_scaling(self, 
                   scaling_algorithm: str = "%quantile", 
                   upper_quantile: float = 99.9, 
                   split_by_column: str = "",
                   ) -> None:
        '''
        This method allows the easy scaling / unscaling of the numerical data in self.data.X. The scaling is always performed down / within 
        columns such that different antigens end up on the same / more similar scale. 

        Args:
            scaling_algorithm (string): 
                one of ["%quantile", "min_max", "standard", "robust", "qnorm", and "unscale"]. If "unscale", will undo any 
                previous scaling -- unscaled data is saved before any other scaling method is performed, allowing easy reversion and 
                switching between scaling methods.
                If a scaling is ever applied after another scaling, the unscaled data is used in the calculations (it is as if the first 
                scaling never happened). Comparison of scaling methods:

                    >> %quantile: This is perhaps the most common method for this kind of data. In it, each column is divided by the value of 
                    its quantile % provided in the upper_quantile argument (this would be the same as dividing by the maximum of each 
                    column if upper_quantile == 100). Then all values > 1 as reduced to 1 so that the scale of the data is constrained.
                    This process is  somewhat reminiscent of thresholding the brightness of an image by choosing a maximum threshold. 

                    >> min_max: This scales each channel / antigen between 0 and 1 by this equation: (values - min) / (max - min). It is 
                    performed by skikit-learn's preprocessing min_max function. 

                    >> standard: This perform standard scaling (scaling as if the data is normally distributed with a mean of 0 and a variance 
                    of 1). It is performed by skikit-learn's preprocessing scale function

                    >> robust: This performs robust scaling using skikit-learn's preprocessing robust_scale function. It is more resistant to 
                    outliers & does not try to scale to normality, unlike standard scaling. 

                    >> qnorm: This method is known for its use in large genomics studies, and uses a particular quantile-based scaling method.
                        implemented by: https://github.com/Maarten-vd-Sande/qnorm. 

            upper_quantile (float): 
                ONLY USED with scaling_algorithm == "%quantile". Determines the upper quantile percentage used in that 
                scaling method
            
            split_by_column (string):
                If not == "", then will attempt to find a columnin self.data.obs matching the provided value, then will 
                split the dataset by unique groups in that column and will perform the selected scaling WITHIN those groups individually, 
                and on the entire dataset at once.     
        '''
        if scaling_algorithm not in ["%quantile", "min_max", "standard", "robust", "qnorm", "unscale"]:
            print(f'scaling_algorithm not in {str(["%quantile", "min_max", "standard", "robust", "qnorm", "unscale"])}! Exiting')
            return
        if self.unscaled_data is None:
            self.unscaled_data = self.data.X.copy()
        data_to_scale = self.unscaled_data.copy()

        def quantiler(data_to_scale):
            quantile_array = np.zeros(len(data_to_scale))
            for i,ii in enumerate(data_to_scale):
                quantile_array[i] = np.quantile(ii, upper_quantile / 100)     
            data_to_scale = (data_to_scale.T / quantile_array)
            data_to_scale[data_to_scale > 1] = 1
            return data_to_scale.T

        if scaling_algorithm == "min_max":
            if split_by_column == "":
                data_to_scale = skpre.minmax_scale(data_to_scale, axis = 0)
            else:
                for i in self.data.obs[split_by_column].unique():
                    slicer = self.data.obs[split_by_column] == i
                    data_to_scale[slicer] = skpre.minmax_scale(data_to_scale[slicer], axis = 0)
        elif scaling_algorithm == "%quantile":
            self._quantile_choice = upper_quantile
            if split_by_column == "":
                quantile_array = np.zeros(len(data_to_scale.T))
                for i,ii in enumerate(data_to_scale.T):
                    quantile_array[i] = np.quantile(ii, upper_quantile / 100)     
                data_to_scale = (data_to_scale / quantile_array)
                data_to_scale[data_to_scale > 1] = 1
            else:
                for i in self.data.obs[split_by_column].unique():
                    slicer = self.data.obs[split_by_column] == i
                    data_to_scale[slicer] = quantiler(data_to_scale[slicer])
        elif scaling_algorithm == "robust":
            if split_by_column == "":
                data_to_scale = skpre.robust_scale(data_to_scale, axis = 0)
            else:
                for i in self.data.obs[split_by_column].unique():
                    slicer = self.data.obs[split_by_column] == i
                    data_to_scale[slicer] = skpre.robust_scale(data_to_scale[slicer], axis = 0)
             # helpful article explaining what the robust function does under-the-hood -- realized that changing the quantiles did not 
             # make any sense... 
             #      https://medium.com/@reinapeh/16-data-feature-normalization-methods-using-python-with-examples-part-2-of-6-4224c9699253#:~:text=Quantile%20Transformation%20maps%20the%20data%20to%20a%20uniform%20distribution%20and
        elif scaling_algorithm == "standard":
            if split_by_column == "":
                data_to_scale = skpre.scale(data_to_scale, axis = 0)
            else:
                for i in self.data.obs[split_by_column].unique():
                    slicer = self.data.obs[split_by_column] == i
                    data_to_scale[slicer] = skpre.scale(data_to_scale[slicer], axis = 0)
        elif scaling_algorithm == "unscale":
            #self.data.X = self.unscaled_data.copy()
            self.unscaled_data = None
        elif scaling_algorithm == "qnorm":
            if split_by_column == "":
                data_to_scale = quantile_normalize(data_to_scale)
            else:
                for i in self.data.obs[split_by_column].unique():
                    slicer = self.data.obs[split_by_column] == i
                    data_to_scale[slicer] = quantile_normalize(data_to_scale[slicer])
        self.data.X = data_to_scale
        self._scaling = scaling_algorithm
        if self.is_batched == 2:
            print('Caution! Rescaling the data has overwritten / reset a prior batch correction!')
            self.is_batched = 0

    def do_leiden_clustering(self, 
                          seed: int = 1234, 
                          marker_class: str = "type",
                          min_dist: float = 0.1, 
                          n_neighbors: int = 15,
                          resolution: int = 1,
                          flavor = "leidenalg",
                          try_from_umap_embedding: bool = False,
                          ) -> None:
        '''Creates a UMAP from all the cells in the dataset and then performs leiden clustering. 
        An alternative to FlowSOM for clustering cells.

        Args:
            seed (int): 
                The random seed for all non-deterministic steps in the clustering pipeline.

            marker_class (string): 
                what channels/antigens to use in the clustering ("type", "state", "none", or all)

            min_dist (float): 
                used in constructing the umap on which the leiden clustering will be performed.

            n_neighbors (integer): 
                used in contructing the nieghbors on which the umap is constructed.

            resolution (integer): 
                used in the ledien clustering itself. Higher numbers favor the finding of more clusters.

            try_from_umap_embedding (boolean): 
                if a UMAP of the entire dataset has been previously performed, set this to True
                to skip the time-consuming steps required for UMAP, and simply use the previously calculated dimensionality 
                reduction. Will not filter for marker_class (assumes that was already done in the creation of the UMAP)
        '''
        panel = self.panel
        for_fs = self.data.copy()
        if (try_from_umap_embedding) and (len(self.UMAP_embedding) == len(self.data)):   ## UMAP cannot be downsampled for leiden.
            for_fs = self.UMAP_embedding
        else:
            if marker_class != "All":
                slicer = panel['marker_class'] == marker_class
                for_fs = for_fs[:,slicer]
            if slicer.sum() == 0:
                return False
            ## Note how no downsampling is applied here!
            sc.pp.neighbors(for_fs, n_neighbors = n_neighbors, random_state = seed)
            sc.tl.umap(for_fs, 
                        min_dist = min_dist, 
                        random_state = seed)
            for_obs_cat = pd.CategoricalDtype(categories = for_fs.obs['condition'].astype('str').unique(), ordered = True)
            for_fs.obs['condition'] = for_fs.obs['condition'].astype('str')
            for_fs.obs['condition'] = for_fs.obs['condition'].astype(for_obs_cat)
            for_fs.obs['true_index'] = for_fs.obs.index.astype('int').copy()
            self.UMAP_embedding = for_fs

        sc.tl.leiden(for_fs, 
                    resolution = resolution, 
                    random_state = seed,
                    flavor = flavor, 
                    n_iterations = 2)

        self.data.obs['leiden'] = list(for_fs.obs['leiden'].astype('int') + 1)
        self.data.obs['leiden'] = self.data.obs['leiden'].astype('category')
        self.UMAP_embedding.obs['leiden'] = list(for_fs.obs['leiden'].astype('int') + 1)
        self.UMAP_embedding.obs['leiden'] = self.UMAP_embedding.obs['leiden'].astype('category')
        self.UMAP_embedding.obs = self.UMAP_embedding.obs.reset_index()
        if self.PCA_embedding is not None:
            #print(self.PCA_embedding.obs.columns)
            try:
                self.PCA_embedding.obs = self.PCA_embedding.obs.drop('leiden',axis = 1)   ## drop if leiden already exists
            except Exception:
                pass
            self.PCA_embedding.obs['true_index'] = self.PCA_embedding.obs['true_index'].astype('int')
            self.PCA_embedding.obs = pd.merge(self.PCA_embedding.obs, for_fs.obs[['leiden', 'true_index']].astype('int'), on = 'true_index')
            self.PCA_embedding.obs['leiden'] = self.PCA_embedding.obs['leiden'].astype('category')
        return True

  
    def do_flowsom(self,
                   marker_class: str = "type",
                   n_clusters: int = 20, 
                   XY_dim: int = 10, 
                   rlen: int = 15, 
                   seed: int = 1234,
                   ) -> FlowSOM: # *** deriv_CATALYST (with Pixie / ark-analysis like quantiling & normalization)
        '''
        Executes FlowSOM clustering on the data.

        Args:
            marker_class (string): 
                what antigens / channels to use in clustering ("type", "state' , "none", or All).

            n_clusters (integer): 
                The final number of metaclusters that cells will be classified into in the "metaclustering" column. This is 
                achieved by merging the over-clustering produced by the SOM (the values in the "clustering" column) down to this number.

            XY_dim (integer): 
                This determines dimensions / points in the initial grid of the self-organizing map, and thereby the initial number 
                of clusters before merging into metaclusters. Specifically, XY_dim*XY_dim will equal the number of initial points in the 
                grid (X & Y dimensinos are often allowed to be specified separately, perhaps I will restore that ability, but don't see really 
                any circumstances where having different X / Y dimensions would be desirable)

            rlen (integer): 
                The number of training iterations. Higher numbers tend to fit the FlowSOM closer to the data / create a more stable
                FlowSOM output (less variation by random seed). However more training iterations takes more time to run. 

            seed (integer):
                the random seed for reproducibility of FlowSOM (which is a non-deterministic algorithm)

        Returns:
            (FlowSOM) The trained FlowSOM object, useful for accessing the various techniques & visualizations available in the FlowSOM package such as minimum spanning trees, etc.
        '''
        panel = self.panel
        for_fs = self.data.copy()
        if marker_class != "All":
            slicer = panel['marker_class'] == marker_class
            for_fs = for_fs[:,slicer].copy()
            if slicer.sum() == 0:
                return None

        ## scale within cells in the same way as the data is scaled within antigens (?? -- or just use min_max for everything)
        # if self._scaling != "unscale":   ### don't do scaling within cells if not scaled within antigens ?
        for_fs.X = skpre.minmax_scale(for_fs.X, axis = 1)               
 
        fs = FlowSOM(for_fs.copy(), 
                    n_clusters = n_clusters, 
                    cols_to_use = for_fs.var.index, 
                    xdim = XY_dim, 
                    ydim = XY_dim, 
                    rlen = rlen, 
                    seed = seed) 

        ## For output clusters, I want 1-indexing:
        fs.get_cluster_data().obs['metaclustering'] = fs.get_cluster_data().obs['metaclustering'] + 1
        fs.get_cell_data().obs['metaclustering'] = fs.get_cell_data().obs['metaclustering'] + 1
        fs.get_cell_data().obs['metaclustering'] = fs.get_cell_data().obs['metaclustering'].astype("category")

        #self.clustering_data = fs.get_cluster_data()
        self.clustering_cell_data = fs.get_cell_data()    # saving this may not be needed 
        self.clustering_cell_data.obs = self.clustering_cell_data.obs.drop('distance_to_bmu', axis = 1)
        self.data.obs = self.clustering_cell_data.obs  
        if self.UMAP_embedding is not None:
            merge_df  = pd.DataFrame(self.clustering_cell_data.obs.reset_index()[['index','metaclustering','clustering']])
            merge_df['true_index'] = merge_df['index'].astype('int')
            self.UMAP_embedding.obs['true_index'] = self.UMAP_embedding.obs['true_index'].astype('int')
            try: 
                self.UMAP_embedding.obs = self.UMAP_embedding.obs.drop(["metaclustering","clustering"], axis = 1)   
                                                                    ## if present, these columns should be dropped
            except KeyError:
                pass
            self.UMAP_embedding.obs = pd.merge(self.UMAP_embedding.obs, merge_df, on = 'true_index')
            self.UMAP_embedding.obs['metaclustering'] = self.UMAP_embedding.obs['metaclustering'].astype('category')
        if self.PCA_embedding is not None:
            merge_df  = pd.DataFrame(self.clustering_cell_data.obs.reset_index()[['index','metaclustering','clustering']])
            merge_df['true_index'] = merge_df['index'].astype('int')
            merge_df = merge_df.drop('index', axis = 1)
            self.PCA_embedding.obs['true_index'] = self.PCA_embedding.obs['true_index'].astype('int')
            try: 
                self.PCA_embedding.obs = self.PCA_embedding.obs.drop(["metaclustering","clustering"], axis = 1)  
                                                                        ## if present, these columns should be dropped
            except KeyError:
                pass
            self.PCA_embedding.obs = pd.merge(self.PCA_embedding.obs, merge_df, on = 'true_index')
            self.PCA_embedding.obs['metaclustering'] = self.PCA_embedding.obs['metaclustering'].astype('category') 
        return fs

    def _plot_stars_CNs(self, fs, filename: Union[str, None] = None):
        '''
        Plots the minimum spanning tree / star plot from the FlowSOM package
        '''
        figure = plot_stars(fs,
                         markers=None, 
                         background_values = fs.get_cluster_data().obs['metaclustering'], 
                         title=None)
        figure.set_size_inches(18,18)
        sns.move_legend(figure.axes[0], loc = 'lower right')
        if filename is not None:
            figure.savefig(self.save_dir + "/" + filename, bbox_inches = "tight") 
        plt.close()
        return figure

    def plot_cell_counts(self,
                         group_by: str = "sample_id", 
                         color_by: str = "condition", 
                         filename: Union[str, None] = None,
                         **kwargs) -> plt.figure:                                        # *** deriv_CATALYST (in terms of imitating output 
                                                                                                                # graph appearance)
        ''' 
        Plots cell counts per [group_by], colored by [color_by], as a bar plot 
        '''
        if color_by == 'NULL':
            color_by = None
        metadata = self.metadata
        group_by =  metadata[group_by]
        color_by = metadata[color_by].astype('category')
        plot = so.Plot(group_by, metadata["number_of_cells"], color = color_by, **kwargs)
        plot = plot.add(so.Bar(), so.Stack(), legend=True).label(title = "Countplot")
        if filename is not None:
            plot.save(self.save_dir + "/" + filename, bbox_inches = "tight") 

        fig = plt.figure()
        plot.on(fig).plot()

        plt.close()
        return fig

    def plot_MDS(self, 
                 marker_class: str = "type", 
                 color_by: str = "condition", 
                 print_stat: bool = False,
                 filename: Union[str, None] = None,
                 **kwargs) -> tuple[plt.figure, pd.DataFrame]:                 # *** deriv_CATALYST (plot appearance / output)
        ''' 
        Plots an MDS embedding of the sample_ids in the dataset as a scatterplot, only using the antigens with marker_class [antigens_to_show] 
        in the panel and colored by [color_by] 

        Also returns a dataframe of the MDS results to allow further examination / comparison of the sample_ids
        '''
        metadata = self.metadata.copy()
        panel = self.panel.copy()

        flowsom_clustering = self.data.copy()
        if marker_class != "All":  
            slicer = panel['marker_class'] == marker_class 
            flowsom_clustering = flowsom_clustering[:,slicer]
            panel = panel[slicer]

        median_df = pd.DataFrame(flowsom_clustering.X, columns = flowsom_clustering.var['antigen'])
        median_df['sample_id'] = list(flowsom_clustering.obs['sample_id'])

        median_df = median_df.groupby("sample_id", observed = False).median()
        
        MDSer = MDS(random_state = 149)
        output = pd.DataFrame(MDSer.fit_transform(np.array(median_df)))
        output.columns = ["MDS dim. 1", "MDS dim. 2"]
        output["sample_id"] = metadata["sample_id"]
        output["patient_id"] = metadata["patient_id"]
        output["condition"] = metadata["condition"]
        output["number_of_cells"] = metadata["number_of_cells"]
        output[color_by] = output[color_by].astype('category')
        if print_stat is True:
            output.to_csv(self.data_table_dir + "/MDS.csv", index = False)

        figure = plt.figure()
        plt.style.use('ggplot')
        ax = figure.gca()
        plot = sns.scatterplot(output, 
                               x = "MDS dim. 1", 
                               y = "MDS dim. 2", 
                               hue = color_by, 
                               size = "number_of_cells", 
                               ax = ax, 
                               **kwargs)
        sns.move_legend(plot, loc = "center right", bbox_to_anchor = (1.35,0.6))
        figure.suptitle("MDS plot by sample_id")
        if filename is not None:
            figure.savefig(self.save_dir + "/" + filename, bbox_inches = "tight") 
        plt.close()   
        return figure, output

    def plot_NRS(self,
                marker_class: str = "type", 
                filename: Union[str, None] = None, 
                **kwargs) -> plt.figure:                        # *** deriv_CATALYST (plot appearance / output as well as 
                                                                # translation of under-the-hood calculation of the Non-redundancy score)
        ''' 
        Plots the non-redundancy scores of each antigen in the category specified in [marker_class] as boxplots, with the distribution 
        deriving from the NRS scores from each sample_id
        '''
        data = self.data.copy()
        if marker_class != "All":    
            slicer = self.panel['marker_class'] == marker_class 
            data = data[:,slicer]
        n_components = 3
        array_list = []
        for i in data.obs['sample_id'].unique():
            sample_array = data.X[data.obs['sample_id'] == i,:]
            pca = PCA(svd_solver = "full")
            pca.fit(sample_array)
            nrs_scores = np.apply_along_axis(np.sum, 
                                    axis = 1, 
                                    arr = np.abs(np.linalg.eig(pca.get_covariance())[1][:,:n_components])*(pca.explained_variance_[:n_components]))  
                                        # A helpful discussion for me to understand what the rotation data was inside R's prcomp: 
                                        #       Igor F. (https://stats.stackexchange.com/users/169343/igor-f), 
                                        # When using the `prcomp` function in R, what is the difference between the `x` values and the `rotation` values?, 
                                        #       URL (version: 2021-02-21): https://stats.stackexchange.com/q/510464
            array_list.append(nrs_scores)

        array_out = np.array(array_list)

        df = pd.DataFrame(array_out, columns = data.var['antigen'])
        df_reordered = pd.DataFrame()
        for i in df.mean().sort_values(ascending = False).index:
            df_reordered[i] = df[i]

        figure = plt.figure()
        plt.style.use('ggplot')
        ax = figure.gca()
        sns.boxplot(df_reordered, ax = ax, fill = False, showmeans = True, **kwargs)
        ax.tick_params("x", labelrotation = 90)
        figure.suptitle(f"NRS Plot of {marker_class} markers")
        if filename is not None:
            figure.savefig(self.save_dir + "/" + filename, bbox_inches = "tight") 
        plt.close()   
        return figure
    
    def plot_ROI_histograms(self, 
                            color_by: str = "condition", 
                            marker_class: str = "All",
                            suptitle: bool = True,
                            filename: Union[str, None] = None, 
                            **kwargs) -> plt.figure:                            # *** deriv_CATALYST (plot appearance / output)
                                                                                # additionally, of seaborn 
                                                                                #   (https://github.com/mwaskom/seaborn [BSD3]) to some extent: 
                                                                                # KDE implementation to replicate seaborn plots 
                                                                                #   (plain seaborn plots did not work exactly as I had wanted)
        '''
        Plot kde-smoothed histograms of each antigen / channel's expression, with separate lines for separate ROIs, colored by [color_by] 
        '''
        data = self.data.copy()
        if marker_class != "All":    
            slicer = self.panel['marker_class'] == marker_class 
            data = data[:,slicer]
        metadata = self.metadata
        data.X = data.X / np.max(data.X, axis =  0)
        intense = pd.DataFrame(data.X, columns = data.var['antigen'])
        reshaped_for_histogram_tracings = pd.melt(intense.T.reset_index(), id_vars = ["antigen"]).drop("variable", axis = 1)
        reshaped_for_histogram_tracings.columns = ["antigen","exprs"]
        reshaped_for_histogram_tracings = reshaped_for_histogram_tracings.reset_index().drop("index", axis = 1)
        reshaped_for_histogram_tracings["imageID"] = list(np.repeat(data.obs['sample_id'], len(data.var.index)))
        zip_dict = {}
        for i,ii in zip(metadata["sample_id"],metadata[color_by]):
            zip_dict[str(i)] = ii
        reshaped_for_histogram_tracings[color_by] = reshaped_for_histogram_tracings["imageID"].astype('str').replace(zip_dict).astype('category')

        reshaped_for_histogram_tracings = reshaped_for_histogram_tracings[reshaped_for_histogram_tracings['antigen'] != "Time"]
        reshaped_for_histogram_tracings = reshaped_for_histogram_tracings[reshaped_for_histogram_tracings['antigen'] != "SampleID"]    
        for i in reshaped_for_histogram_tracings['antigen'].unique():
            if i[-2:] == "Di":
                try:
                    int(i[-4:-2])
                except ValueError:
                    pass
                else:
                    reshaped_for_histogram_tracings = reshaped_for_histogram_tracings[reshaped_for_histogram_tracings['antigen'] != i]
        
        kde_groupby_list = list(reshaped_for_histogram_tracings.groupby(["antigen"], observed = False))
        color_bank = [  '#0202BB','#DD0202', '#02AA02',        ## currently have 22 unique colors (probably, unecessarily too many) --> 
                                                               # consider how many I can expect needing
                    '#888644', '#DD8888', '#EE00EE', 
                    '#EE0033', '#884488', 
                    '#009200', '#EEEE33',
                    '#33EE33','#33EEEE',
                    "#555555",'#88FF44',
                    '#447788',
                    '#3333EE','#9999EE',
                    '#CCCCFF','#FFCCCC',
                    '#CCFFCC','#CC5599',
                    '#BBBBBB','#000000']
        
        color_dict = {}
        patch_bank1 = [Patch(color = "#E9E9E9", label = color_by)] 
        for i,ii in enumerate(reshaped_for_histogram_tracings[color_by].unique()):
            color_dict[ii] = color_bank[i]
            patch_bank1.append(Patch(color = color_bank[i], label = ii))
        length = len(kde_groupby_list)
        colwrap = 4
        row_num  = ((length - 1) // colwrap) + 1
        if (row_num == 1) and (colwrap > 2):
            colwrap = colwrap - 1
            row_num  = ((length - 1) // colwrap) + 1
        text_size = 8
        plt.style.use('ggplot')
        figX = colwrap * 2.35
        figY = row_num * 1.9
        fig, axs = plt.subplots(row_num, colwrap, figsize = [figX,figY])
        if isinstance(axs, np.ndarray):
            axs = axs.ravel()
        else:    ## only 1 panel /facet / ax
            axs = np.array([axs]) 
        for j,jj in enumerate(kde_groupby_list):
            new_groupby = list(jj[1].groupby(["imageID", color_by], observed = False))
            antigen = jj[0][0]
            axs[j].set_title(antigen, size = text_size)
            axs[j].set_ylabel(axs[j].get_ylabel(), size = text_size)
            axs[j].set_xlabel(axs[j].get_xlabel(), size = text_size)
            max_max = 0
            for i in new_groupby:
                df = i[1]
                condition = i[0][1]
                values = np.array(df['exprs'])
                minimum = np.min(values)
                maximum = np.max(values)
                max_max = np.max((maximum, max_max))
                plot_over = np.linspace(minimum, maximum, 200)
                try:
                    out = gaussian_kde(values)(plot_over)
                except Exception:
                    print(f"gaussian kde error for antigen {antigen}, condition {condition}!")
                    out = np.zeros(plot_over.shape)
                out = np.nan_to_num(out / np.max(out))   ## normalize between 0 -- > 1 to guarantee share y
                axs[j].plot(plot_over, out, color = color_dict[condition], alpha = 0.5, **kwargs)
            axs[j].set_yticks([0,0.5,1], labels = ["0","0.5","1"], size = text_size)
            axs[j].set_xticks([0,0.5,1], labels = ["0","0.5","1"], size = text_size)
            axs[j].set_xmargin(0.05)
            axs[j].set_ymargin(0.05)
            #axs[j].set_xlabel("normalized Exprs")
        for k in range(j+1,colwrap*row_num,1):
            axs[k].set_axis_off()
        maximum_legend = np.max([len(i) for i in reshaped_for_histogram_tracings[color_by].unique()])
        x_anchor = (1.0 + (maximum_legend * 0.02)) - ((colwrap - 3)*0.035)
        fig.legend(handles = [i for i in patch_bank1], 
                            bbox_to_anchor = (x_anchor, 
                                                0.9))
        fig.subplots_adjust(hspace = 0.5)
        sup_Y = 1.04 + (row_num * -0.01)
        if suptitle:
            fig.suptitle("KDE / Histogram plots of normalized Exprs of each marker \n facetted by sample_id ", y = sup_Y)
        fig.supxlabel("normalized Exprs")
        if filename is not None:
            fig.savefig(self.save_dir + "/" + filename, bbox_inches = "tight") 
        plt.close()
        return fig

    def do_UMAP(self, 
                marker_class: str = "type", 
                cell_number: int = 1000,
                seed: int = 0,
                n_neighbors = 15,
                min_dist: float = 0.1,
                **kwargs) -> None:                                # *** deriv_CATALYST ()
        '''
        Perform the calculations for a UMAP embedding.

        Args:
            marker_class (string): 
                none, type, state, or ALL >> what markers/antigens to use in the UMAP algorithm

            cell_number (integer): 
                The downsampling number. No more than this number of cells will be randomly taken from each sample_id in the process of downsampling

            seed (integer): 
                The random seed used for reproducibility in downsampling and running the UMAP

            kwargs: 
                passed as kwargs into scanpy.tl.umap() call
        '''
        warnings.filterwarnings("ignore", message = "Transforming to str index")
        panel = self.panel
        data = self.data.copy()
        if marker_class != "All":    
            slicer = panel['marker_class'] == marker_class 
            data = data[:,slicer]
        data = self._downsample_for_UMAP(data, max_number = cell_number, seed = seed)
        sc.pp.neighbors(data, n_neighbors = n_neighbors, random_state = seed)  
                     ## not loss of backwards replicability -- set to random_state to 0 to match umaps before 11-8-24
        sc.tl.umap(data, min_dist = min_dist, random_state = seed, **kwargs)
        for_obs_cat = pd.CategoricalDtype(categories = data.obs['condition'].astype('str').unique(), ordered = True)
        data.obs['condition'] = data.obs['condition'].astype('str')
        data.obs['condition'] = data.obs['condition'].astype(for_obs_cat)
        self.UMAP_embedding = data

    def do_PCA(self, 
               marker_class: str = 'type',
               cell_number: int = 1000, 
               seed: int = 0,
               ) -> None:                                               # *** deriv_CATALYST (ish, uses the same structure as UMAP but for PCA)
        '''
        Perform the calculations for a PCA embedding.

        Args:
            marker_class (string): 
                none, type, state, or ALL >> what markers/antigens to use in the UMAP algorithm

            cell_number (integer): 
                The downsampling number. No more than this number of cells will be randomly taken from each sample_id in the process of downsampling

            seed (integer): 
                The random seed used for reproducibility in downsampling and running the UMAP
        '''
        warnings.filterwarnings("ignore", message = "Transforming to str index")
        panel = self.panel
        data = self.data.copy()

        if marker_class != "All":   
            slicer = panel['marker_class'] == marker_class 
            data = data[:,slicer]

        data = self._downsample_for_UMAP(data, max_number = cell_number, seed = seed)
        for_obs_cat = pd.CategoricalDtype(categories = data.obs['condition'].astype('str').unique(), ordered = True)
        data.obs['condition'] = data.obs['condition'].astype('str')
        data.obs['condition'] = data.obs['condition'].astype(for_obs_cat)
        pca = PCA(svd_solver = "full")
        pca.fit(data.X.T)
        x = pca.components_[0]
        y = pca.components_[1]
        data.obsm['X_umap'] = np.array([x,y]).T
        self.PCA_embedding = data

    def _downsample_for_UMAP(self, 
                            anndata_in: ann.AnnData, 
                            max_number: int = 1000, 
                            seed: int = 42,
                            ) -> ann.AnnData:                 # *** deriv_CATALYST (implements the CATALYST-style downsampling with equal 
                                                                    # maximum cell number per sample_id)
        '''
        Helper for do_UMAP and do_PCA  methods, performs the downsampling of the data, where no more than the supplied max_number of cells
        will be randomly sampled from each sample_id of the anndata_in object. Returns the downsampled data as an anndata object.
        '''
        fs_anndata = anndata_in.copy()
        anndata_df = pd.DataFrame(fs_anndata.X, columns = fs_anndata.var['antigen'])
        anndata_df['sample_id'] = list(fs_anndata.obs['sample_id'])
        anndata_df.index = fs_anndata.obs.index.astype('int')
        sample_together = pd.DataFrame()
        for i in anndata_df['sample_id'].astype('str').unique():
            segment = anndata_df[anndata_df['sample_id'] == i]
            if len(segment) > 0:
                sample = segment.sample(n = min(max_number, len(segment)), random_state = seed)
                sample_together = pd.concat([sample_together, sample], axis = 0)
        sample_together = sample_together.reset_index().sort_values(by = 'index')
        sample_together.index = sample_together['index']
        sample_together = sample_together.drop(['index','sample_id'], axis = 1)
        fs_anndata.obs.index = fs_anndata.obs.index.astype('int')
        fs_anndata.obs['true_index'] = fs_anndata.obs.index.copy()
        sample_together['true_index'] = sample_together.index.copy()
        for_obs = pd.merge(fs_anndata.obs, sample_together[["true_index"]], on = "true_index")
        sample_together = sample_together.drop("true_index", axis = 1)
        for_obs.index = list(for_obs['true_index'])
        downsample_anndata = ann.AnnData(sample_together, obs = for_obs)   
        downsample_anndata.var =  pd.DataFrame(sample_together.columns)
        ## these columns are not always present:
        try:
            downsample_anndata.obs['metaclustering'] = downsample_anndata.obs['metaclustering'].astype('category')
        except KeyError:
            pass
        try:
            downsample_anndata.obs['merging'] = downsample_anndata.obs['merging'].astype('category')
        except KeyError:
            pass
        try:
            downsample_anndata.obs['classification'] = downsample_anndata.obs['classification'].astype('category')
        except KeyError:
            pass
        return downsample_anndata

    def plot_scatter(self, antigen1, antigen2, hue = None, filename = None, size = 1, alpha = 0.5, **kwargs):
        data = pd.DataFrame(self.data.X.copy(), columns = self.data.var['antigen'].copy())
        # hue_norm = None
        palette = None
        if hue is not None:
            if hue == "Density":
                density = KernelDensity()
                X = data.loc[:,[antigen1, antigen2]]
                density = density.fit(X)
                density = density.score_samples(X)
                to_scale = np.exp(density)
                to_scale = to_scale / np.quantile(to_scale, 0.99)
                to_scale[to_scale > 1] = 1
                data['Density'] = list(to_scale)
                # hue_norm = (0,1)
                palette = 'coolwarm'
            elif hue in self.data.obs.columns:
                data[hue] = list(self.data.obs[hue].copy())
        figure = plt.figure()
        ax = plt.gca()
        sns.scatterplot(data, 
                        x = antigen1, 
                        y = antigen2, 
                        hue = hue, 
                        palette = palette, 
                        # hue_norm = hue_norm, 
                        size = size, 
                        alpha = alpha,
                        ax = ax, 
                        **kwargs)
        if filename is not None:
            figure.savefig(self.save_dir + "/" + filename, bbox_inches = "tight")
        plt.close()  
        return figure

    def plot_UMAP(self,
                color_by: str = 'metaclustering', 
                palette = None,
                filename: Union[str, None] = None, 
                **kwargs) -> plt.figure:                                           # *** deriv_CATALYST (plot appearance / output)
        '''
        Plots a UMAP embedding as a scatterplot, colored by [color_by]
        '''
        self.UMAP_embedding.var.index = self.UMAP_embedding.var['antigen']
        plt.style.use('ggplot')
        figure = plt.figure()
        ax = figure.gca()
        sc.pl.umap(self.UMAP_embedding, 
                   color = color_by, 
                   cmap = palette, 
                   ax = ax, 
                   show = False, 
                   **kwargs)  
        if filename is not None:
            figure.savefig(self.save_dir + "/" + filename, bbox_inches = "tight")
        plt.close()  
        return figure
    
    def plot_PCA(self, 
                 color_by: str = 'metaclustering', 
                 palette = None,
                 filename: Union[str, None] = None, 
                 **kwargs) -> plt.figure:                                                                           # *** deriv_CATALYST()
        '''
        Plots a PCA embedding as a scatterplot, colored by [color_by]
        '''
        self.PCA_embedding.var.index = self.PCA_embedding.var['antigen']
        plt.style.use('ggplot')
        figure = plt.figure()
        ax = figure.gca()
        sc.pl.umap(self.PCA_embedding, 
                    color = color_by, 
                    cmap = palette, 
                    ax = ax, 
                    show = False, 
                    **kwargs)
        ax.set_xlabel('PC1')
        ax.set_ylabel('PC2')
        if filename is not None:
            figure.savefig(self.save_dir + "/" + filename, bbox_inches = "tight")
        plt.close()  
        return figure

    def plot_facetted_DR(self,
                         color_by: str, 
                         subsetting_column: str, 
                         kind: str = "UMAP",
                         suptitle: bool = True,
                         number_of_columns: int = 3, 
                         color_bank: Union[list[str], None] = None, 
                         filename: Union[str, None] = None, 
                         **kwargs) -> plt.figure:
        '''
        Plots a dimensionality reduction embedding (kind = 'PCA' or 'UMAP'), facetted by the supplied [subsetting_column], each UMAP colord 
        by the supplied [color_by]. 

        Args:
            color_by (str): 
                what column in self.data.obs, or which antigen name (values in self.data.var['antigen'], used to select the expression data in 
                matching column) to color the scatter plots in each facet with. 

            subsetting_column (str): 
                the column in self.data.obs on which to facet the plot. For every unique value in this column, a separate UMAP plot will be created,
                containing only the cells with that unique value displayed. Additionally, the first plot in the facet grid will always be a dimensinoality
                reduction plot containing all the cells. 
                NOTE: the plots will all have the same DR embedding, as dimensionality reduction IS NOT RUN for each subset of cells, instead the last DR (one the whole / 
                downsampled data) of the proper kind will be the embedding used for every cell

            kind (str): 
                "UMAP" or "PCA" -- which kind of dimensionality reduction to attempt to plot

            suptitle (bool): 
                whether or not ot include an automatically generated title. Default = True, but may want to set to False if the 
                suptitle is being placed in the wrong location on the plot (as happens when there are a very large number of subplots)

            number_of_columns (int): 
                how many columns to use in the figure's grid. The number of rows will be automatically determined from this. 
                If the number of total panels or rows is too low, this number may be reduced automatically. 

            color_bank (list of strings or None): 
                a list of strings representing colors that can be recognized by matplotlib.Patch, used to 
                determine the colors on the plot for each group in the color_by column, 
                ONLY if color_by is in self.data.obs.columns and NOT if colorby is in self.data.var['antigen']

            filename (str or None): 
                If not None, then will attempt to write the figure produced to self.save_dir/{filename}
                INCLUDE the file extension in this string! (usually .png)

            kwargs: 
                keyword arguments passed on to each matplotlib.axis.scatter() call. 

        Returns:
            a maptlotlib figure, the facetted plot of UMAPs. The first UMAP is always the un-facetted (all data together) UMAP

        Inputs / Outputs:
            Outputs: 
                if filename is provided, then the matplotlib figure will also be written as a file to -- self.save_dir/{filename}
        '''
        if number_of_columns <= 1:
            print("number_of_columns must be > 1!")
            return
        if kind == "UMAP":
            down_anndata = self.UMAP_embedding.copy()
        elif kind == "PCA":
            down_anndata = self.PCA_embedding.copy()
        downsample_UMAP_df = pd.DataFrame(down_anndata.obsm['X_umap'])
        for i in down_anndata.obs.columns:
            down_anndata.obs[i] = down_anndata.obs[i].astype('category')
        try:
            down_anndata.obs = down_anndata.obs.drop('index', axis = 1)
        except KeyError:
            pass
        
        down_anndata.obs.index = downsample_UMAP_df.index
        downsample_UMAP_df = pd.merge(downsample_UMAP_df.reset_index(), down_anndata.obs.reset_index(), on = 'index')
        if color_by in list(down_anndata.obs.columns):
            if color_bank is None:
                color_bank = ['#884488','#888644',             ## currently have 22 unique colors (probably, unecessarily too many) --> 
                                                               # consider how many I can expect needing
                        '#EE0033', '#EEEE33',
                        '#EE00EE', '#009200',
                        '#33EE33','#33EEEE',
                        "#555555",'#88FF44',
                        '#447788','#DD8888',
                        '#3333EE','#9999EE',
                        '#000092','#920000',
                        '#CCCCFF','#FFCCCC',
                        '#CCFFCC','#CC5599',
                        '#BBBBBB','#000000']
            color_dict = {}
            length_list  = [len(str(color_by))]
            patch_bank1 = [Patch(color = "#E9E9E9", label = color_by)]    # #E9E9E9 is the color of the legend background / close enough
            downsample_UMAP_df = downsample_UMAP_df.sort_values(color_by, ascending = True)
            for i,ii in enumerate(downsample_UMAP_df[color_by].astype('str').unique()):
                length_list.append(len(ii))
                if (i + 1) > len(color_bank):
                    color_bank = color_bank + color_bank   ## wrap the color aorund if overflow....
                color_dict[ii] = color_bank[i]
                label = Patch(color = color_bank[i], label = ii)
                patch_bank1.append(label)
            maximum_legend = np.array(length_list).max()
            downsample_UMAP_df['color'] = downsample_UMAP_df[color_by].astype('str').replace(color_dict)
        elif color_by in list(down_anndata.var['antigen']):
            downsample_UMAP_df['color'] = down_anndata.X[:,(down_anndata.var['antigen'] == color_by)]
            maximum_legend = len(color_by)
            patch_bank1 = [Patch(color = '#E9E9E9', label = color_by)]

        number_of_panels = len(downsample_UMAP_df[subsetting_column].unique()) + 1   ## plus one for the initial all together plot
        if number_of_panels < 3:
            if self._in_gui: 
                tk.messagebox.showwarning("Warning!", 
                    message = "only one class in subsetting column! no figure will be made (use a non-facetting function to plot this UMAP)")
            else:
                print("only one class in subsetting column! no figure will be made (use a non-facetting function to plot this UMAP)")
            return
        if int(number_of_panels) == int(number_of_columns):
            number_of_columns -= 1    ## automatically reshape if it is too small

        number_of_rows = (number_of_panels // number_of_columns) + 1            ## + 1 because the // operation rounds down
        if (number_of_rows == 1) and (number_of_columns > 2):
            number_of_columns -= 1  
            number_of_rows = (number_of_panels // number_of_columns) + 1  

        if int(number_of_panels % number_of_columns) == 0:
            number_of_rows = number_of_rows - 1   ## avoid a blank row at the end

        plt.style.use('ggplot')
        figX = number_of_columns * 2.35
        figY = number_of_rows * 1.9
        figure, axs = plt.subplots(number_of_rows,
                                   number_of_columns, 
                                   sharex = True, 
                                   sharey = True, 
                                   figsize = (figX, figY))
        axs = axs.ravel()
        axs[0].scatter(x = downsample_UMAP_df[0], 
                       y = downsample_UMAP_df[1], 
                       c = downsample_UMAP_df['color'], 
                       s = 1, 
                       alpha = 0.5, 
                       **kwargs)
        axs[0].set_title("All together", size = 10)
        try:
            downsample_UMAP_df[subsetting_column] = downsample_UMAP_df[subsetting_column].astype('int')
        except ValueError:
            # if the subsetting column can be converted to integers, in should be for the sake of properly ordering the values
            pass
    
        for i, ii in enumerate(downsample_UMAP_df[subsetting_column].sort_values().unique().astype('str')):
            subset_df = downsample_UMAP_df[downsample_UMAP_df[subsetting_column].astype('str') == ii]
            axs[i+1].scatter(x = subset_df[0], 
                            y = subset_df[1], 
                            c = subset_df['color'], 
                            s = 1, 
                            alpha = 0.5, 
                            **kwargs)
            axs[i+1].set_title(ii, size = 10)

        for k in range(i+2, number_of_rows*number_of_columns, 1):
            axs[k].set_axis_off()

        x_anchor = (((1.0 + (maximum_legend * 0.02))
                    - (number_of_columns-2)*(0.125 / (abs(number_of_columns - 3) + 1)))
                    - ((number_of_columns - 3)*0.035))
        
        figure.legend(handles = [i for i in patch_bank1], 
                    bbox_to_anchor = (x_anchor, 
                                        0.9)) # 0.9 sets the top of the legend to the top of the figure. 
                                            # This should work in most cases well enough (I think).
                                            # The first parameter scales with the lenght of the strings
                                            # in the legend, and the number of columns
        sup_Y = 1.02 + (number_of_rows * -0.01)
        if suptitle:
            figure.suptitle(f'{kind} plots subsetted by {subsetting_column}', y = sup_Y)
        if filename is not None:
            figure.savefig(self.save_dir + "/" + filename, bbox_inches = "tight")
        plt.close()  
        return figure      

    def plot_medians_heatmap(self,  
                             marker_class: str = "type", 
                             groupby: str = "metaclustering",  
                             subset_df: pd.DataFrame = None, 
                             subset_obs: pd.DataFrame = None, 
                             figsize: tuple[Union[int,float]] = (10,10),
                             filename: Union[str, None] = None, 
                             **kwargs) -> plt.figure:                                      # *** deriv_CATALYST (tries to imitate the heatmaps of 
                                                                                                                # CATALYST)
        ''' 
        Plots a heatmap in a manner similar to CATALYST by first taking the median of each channel in each category of [groupby] column, then
        %quantile normalizing the medians from 1%-99% across the entire set of medians.

        Args:
            filename (string): 
                the filename for exported heatmap

            marker_class (string): 
                none, type, state, or All >>> what markers / antigens to use in the heatmap

            groupby (string): 
                a name of a column in self.data.obs to group the data by (usually 'metaclustering','clustering','merging',
                'classification','leiden'). 
                groupby can be:

                        "metaclustering" --> cluster heatmap
                        "sample_id"   --> heatmap by ROI
                        "merging" / etc. --> heatmap by arbitrary column in self.data.obs

            subset_df (pandas DataFrame or None): 
                a dataframe equivalent to self.data.X with column names = self.data.var.index allows 
                custom / transformed / subsetted data to be introduced into this plotting method without needing to edit / transform
                self.data directly. If None, then self.data will be used to create the plot and subset_obs argument will be ignored.
                Requires a paired subset_obs dataframe.

            subset_obs (pandas dataframe or None): 
                an equivalent to self.data.obs, paired with subset_df argument

            figsize (tuple of numerics): 
                X / Y dimension sizes of the plot

            kwargs: 
                passed in seaborn.clustermap() call
        '''
        #show_cluster_centers = False
        warnings.filterwarnings("ignore", message = "divide by zero encountered in divide") ########## zero divisions are very common
        warnings.filterwarnings("ignore", message = "invalid value encountered in divide") 
        panel = self.panel
        if subset_df is not None:
            for_fs = subset_df.copy()
            if marker_class != "All":    ## None ==> show all
                slicer = panel['marker_class'] == marker_class 
                for_fs = for_fs.iloc[:,np.array(slicer)]
                antigens = for_fs.copy().columns
            for_fs['index'] = for_fs.index.astype('str')
            to_merge = pd.DataFrame(subset_obs[groupby]).reset_index()
            to_merge['index'] = to_merge['index'].astype('str')
            for_fs = for_fs.merge(to_merge, on = 'index')
            manipul_df = for_fs.copy().drop(["index", groupby], axis = 1)
            manipul_df['metacluster'] = for_fs[groupby]
            main_df = pd.DataFrame()
            for ii,i in enumerate(manipul_df.groupby("metacluster", observed = False).apply(_py_catalyst_quantile_norm, include_groups = False)):
                slice = pd.DataFrame(i, index = antigens, columns = [ii])
                main_df = pd.concat([main_df,slice], axis = 1)
            cluster_centers = main_df.T
        else:
            for_fs = self.data.copy()
            if marker_class != "All":    ## None ==> show all
                slicer = panel['marker_class'] == marker_class 
                for_fs = for_fs[:,slicer]
            manipul_df = pd.DataFrame(for_fs.X)
            manipul_df["metacluster"] = list(for_fs.obs[groupby])
            main_df = pd.DataFrame()
            for ii,i in enumerate(manipul_df.groupby("metacluster", observed = False).apply(_py_catalyst_quantile_norm, include_groups = False)):
                slice = pd.DataFrame(i, index = for_fs.var.index, columns = [ii])
                main_df = pd.concat([main_df,slice], axis = 1)
            cluster_centers = main_df.T

        #### different way to quantile after taking medians (along axis of clusters, instead of quantiling the global numbers as above):
        if groupby != "sample_id":
            if subset_df is not None:
                total = len(for_fs)
                counts = for_fs.groupby(groupby, observed = False).count() / total
                percents = [f'{i} ({str(round(ii*100, 1))}%)' for i,ii in zip(counts.index, counts['index'])]
                cluster_centers.index = percents
            else:
                percentiles = pd.DataFrame()
                '''
                if show_cluster_centers is True:     ### shows mean of metacluster centers
                    for_fs = self.clustering_data.copy()
                    obs = for_fs.obs
                    cluster_data = pd.DataFrame(for_fs.X.T * np.array(for_fs.obs['percentages'])).T  ## This is the data on the values of the centroids of each individual cluster
                    cluster_data[groupby] = list(obs[groupby])   ## don't know why converting to a list is necessary, but it is.... 
                                    # Answer: it has to do with indexes:  
                                    # https://stackoverflow.com/questions/61677569/cannot-set-pandas-column-values-using-series-sets-everything-to-np-nan-instead

                    cluster_centers = cluster_data.groupby(groupby, observed = False).mean()
                    cluster_centers.columns = for_fs.var.index
                '''
                percent_groupby = self.data.obs.groupby(groupby, observed = False).count()['file_name'] / len(self.data.obs)
                if groupby != "clustering":
                    percentiles['percents'] = [f'''{i} ({np.round(ii * 100, 1)}%)''' for i,ii in zip(percent_groupby.index, list(percent_groupby))]
                    percentiles['index'] = [i for i in percent_groupby.index]
                #else:
                #    percentiles['percents'] = [f'''{i} ({np.round(obs["percentages"].loc[i] * 100, 1)}%)''' for i in obs.index]
                #    percentiles['index'] = [i for i in obs.index]
                percentiles = percentiles.sort_values('index')
                cluster_centers.index = list(percentiles['percents'])   
        else:
            cluster_centers['sample_id'] = cluster_centers.reset_index()['index']
            cluster_centers.index = cluster_centers['sample_id']
            cluster_centers = cluster_centers.drop('sample_id', axis = 1)
        plot = sns.clustermap(cluster_centers, 
                             cmap = "coolwarm", 
                             linewidths = 0.01, 
                             xticklabels = True, 
                             yticklabels = True, 
                             figsize = figsize, 
                             **kwargs)
        plot.figure.suptitle(f"Scaled/Normalization Expression Medians of each {marker_class} Marker within each {groupby}", y = 1.03)
        warnings.filterwarnings("default", message = "divide by zero encountered in divide")  ## undo prior warnings modifications
        warnings.filterwarnings("default", message = "invalid value encountered in divide") 
        if filename is not None:
            plot.savefig(self.save_dir + "/" + filename, bbox_inches = "tight") 
            plt.close()  
            if  subset_df is None:
                return plot.figure
            else:
                return plot
        else:
            if subset_df is None:
                return plot.figure
            else:
                return plot
        
    def _plot_facetted_heatmap(self, 
                              filename: str, 
                              subsetting_column: str, 
                              groupby_column: str = "metaclustering", 
                              marker_class: str = "type", 
                              number_of_columns: int = 3, 
                              suptitle: bool = True,
                              **kwargs) -> str:
        '''
        Calls plot_medians_heatmap iteratively to plot a facetted heatmap, facetted on the unique categories in [subsetting_column].

        Unique in that this function only exports an .SVG file to the disk and return only the path to that file (does not return the plot 
        like the other functions)

        This function is old, and not well-tested / supported so it may have errors!
        '''
        try:
            import svg_stack # type: ignore
        except Exception:
            print("cannot make facetted heatmap without svg_stack package installed!")
            return
        
        if number_of_columns <= 1:
            print("number_of_columns must be greater than 1!")
            return

        analysis_anndata = self.data.copy()

        pre_heatmap_df = pd.DataFrame(analysis_anndata.X)
        pre_heatmap_df.columns = analysis_anndata.var.index
        heatmap_df = pd.concat([pre_heatmap_df.reset_index(), analysis_anndata.obs.reset_index()], axis = 1)
        ## need to add columns
        number_of_panels = len(heatmap_df[subsetting_column].unique()) + 1   ## plus one for the initial all together plot
        if number_of_panels > 15:
            number_of_columns = 4

        if number_of_panels < 3:
            if self._in_gui:
                tk.messagebox.showwarning("Warning!", 
                    message = "only one class in subsetting column! no figure will be made (use a non-facetting function to plot this UMAP)")
            else:
                print("only one class in subsetting column! no figure will be made (use a non-facetting function to plot this UMAP)")
            return
        if int(number_of_panels) == int(number_of_columns):
            number_of_columns -= 1    ## automatically reshape if it is too small

        number_of_rows = (number_of_panels // number_of_columns) + 1            ## plus because the // operation rounds down
        if (number_of_rows == 1) and (number_of_columns > 2):
            number_of_columns -= 1  
            number_of_rows = (number_of_panels // number_of_columns) + 1  

        if int(number_of_panels % number_of_columns) == 0:
            number_of_rows = number_of_rows - 1   ## avoid a blank row at the end
        temp_img_dir = tp.TemporaryDirectory().name
        if not os.path.exists(temp_img_dir):
            os.mkdir(temp_img_dir)
        temp_img_dir_svg = temp_img_dir + "/temp_image.svg"
        temp_img_dir_svg_all = temp_img_dir + "/temp_image_concat.svg"

        plt.style.use('ggplot')
        HeatFig = plt.figure()
        inter_fig = self.plot_medians_heatmap(filename = None, 
                                              marker_class = marker_class, 
                                              groupby = groupby_column,
                                              **kwargs)
        inter_fig.figure.suptitle('Whole Dataset', size = 10, y = 1.05)
        inter_fig.savefig(temp_img_dir_svg, bbox_inches = "tight") 
        plt.close()
        document = svg_stack.Document()
        row = svg_stack.HBoxLayout()

        row.addSVG(temp_img_dir_svg, alignment = svg_stack.AlignCenter)

        counter = 1
        row_counter = 0

        try:
            heatmap_df[subsetting_column] = heatmap_df[subsetting_column].astype('int')         ## for ordering items properly
        except ValueError:
            pass

        for i, ii in enumerate(heatmap_df[subsetting_column].sort_values().astype('str').unique()):
            if counter % number_of_columns == 0:    ## new row
                if row_counter > 0:   ### must keep concatenating rows (not overwriting)
                    document.setLayout(row)
                    document.save(temp_img_dir_svg)
                    row = svg_stack.HBoxLayout()

                    layer = svg_stack.VBoxLayout()
                    layer.addSVG(temp_img_dir_svg_all, alignment = svg_stack.AlignCenter)
                    layer.addSVG(temp_img_dir_svg, alignment = svg_stack.AlignCenter)
                    document.setLayout(layer)
                    document.save(temp_img_dir_svg_all)
                else:
                    document.setLayout(row)
                    document.save(temp_img_dir_svg_all)
                    row = svg_stack.HBoxLayout()
                    row_counter += 1

            subset_df = pre_heatmap_df[heatmap_df[subsetting_column].astype('str') == ii]
            subset_df = self.plot_medians_heatmap(filename = None, 
                                                  marker_class = marker_class, 
                                                  groupby = groupby_column, 
                                                  subset_df = subset_df, 
                                                  subset_obs = analysis_anndata.obs,
                                                  **kwargs)
            subset_df.figure.suptitle(f'{subsetting_column}: {ii}', size = 10, y = 1.05)
            subset_df.savefig(temp_img_dir_svg, bbox_inches = "tight") 
            counter += 1
            plt.close()
            row.addSVG(temp_img_dir_svg, alignment = svg_stack.AlignCenter)

        document.setLayout(row)
        document.save(temp_img_dir_svg)

        layer = svg_stack.VBoxLayout()
        layer.addSVG(temp_img_dir_svg_all, alignment = svg_stack.AlignCenter)
        layer.addSVG(temp_img_dir_svg, alignment = svg_stack.AlignCenter)
        document.setLayout(layer)
        document.save(temp_img_dir_svg_all)
    
        sup_Y = 1.0
        if suptitle:
            HeatFig.suptitle(f'Heatmap plots subsetted by {subsetting_column}', y = sup_Y)
        HeatFig.savefig(temp_img_dir_svg, bbox_inches = "tight")
        plt.close()  

        layer = svg_stack.VBoxLayout()
        layer.addSVG(temp_img_dir_svg, alignment = svg_stack.AlignCenter)
        layer.addSVG(temp_img_dir_svg_all, alignment = svg_stack.AlignCenter)
        document.setLayout(layer)
        document.save(self.save_dir + "/" + filename + ".svg")
        return self.save_dir + "/" + filename + ".svg"
       
    def do_cluster_merging(self, 
                            file_path: Union[str, Path], 
                            groupby_column: str = "metaclustering",
                            output_column: str = "merging",
                            ) -> None:                                           # *** deriv_CATALYST (in effect and in the merging.csv file structure, 
                                                                                                        # more than in the function itself)
        '''
        Creates a "merging"" column inside self.data.obs by merging & annotating an existing column in self.data.obs [groupby_column] with a 
        pandas dataframe with two columns:

            -- "original_cluster" (the values of the [groupby_column])

            -- "new_cluster" (The values for the new column that replace the corresponding original_cluster values)
            
        groupby_column: could be "leiden" to merge leiden (not tested), but usually "metaclustering" (default)
        '''
        merging_file_path = str(file_path)
        try:
            merging_table = pd.read_csv(merging_file_path)
        except Exception:
            print("merging file could not be loaded / does not exist!")
            return

        replace_dictionary = {}
        for i in merging_table.index:
            replace_dictionary[str(merging_table.loc[i,"original_cluster"])] = merging_table.loc[i,"new_cluster"]

        self.data.obs[output_column] = self.data.obs[groupby_column].astype('str').replace(replace_dictionary)
        if self.UMAP_embedding is not None:
            self.UMAP_embedding.obs[output_column] = self.UMAP_embedding.obs[groupby_column].astype('str').replace(replace_dictionary)
        if self.PCA_embedding is not None:
            self.PCA_embedding.obs[output_column] = self.PCA_embedding.obs[groupby_column].astype('str').replace(replace_dictionary)

    def plot_cluster_distributions(self, 
                                   groupby_column: str = "metaclustering", 
                                   marker_class: str = 'type', 
                                   plot_type: str = "violin", 
                                   comp_type: str = "raw",
                                   filename: Union[str, None] = None,
                                   **kwargs) -> plt.figure:
        '''
        Plot the distribution of marker expression within groups of cells. Violin or bar plots.

        Args:
            groupby_column (string): 
                The column in self.data.obs to group the cells by (usually a way of identifying cell types, 
                like metaclustering or merging, but can be a different grouping like sample_id)

            marker_class (string, "All","type","state", or "none"): 
                what type of antigen to include in the plot

            plot_type (string, "violin" or "bar"): 
                whether to plot a violin or bar plot

            comp_type (string, "vs" or "raw"): 
                whether to display the raw values of marker expression or to display the difference between each 
                cluster and the rest of the dataset. As in, if == "vs", then the data for each cluster will have the mean expression of rest 
                of the clusters substracted from it before plotting. 

            filename (string, or None): 
                If not None, the name of the .png file to be saved in experiment.save_dir

            kwargs: 
                passed into seaborn.catplot() call
        
        Returns:
            a matplotlib figure
        '''
        flowsom_clustering = self.data.copy()
        scale = self._scaling
        if scale == "unscale":
            scale = ""
        else:
            scale = "Scaled"

        if marker_class != "All":
            manipul_df = pd.DataFrame((flowsom_clustering.X.T[self.panel['marker_class'] == marker_class]).T)
            manipul_df.columns = self.panel[self.panel['marker_class'] == marker_class]['antigen']
        else:
            manipul_df = pd.DataFrame(flowsom_clustering.X)
            manipul_df.columns = self.panel['antigen']

        manipul_df[groupby_column] =  list(self.data.obs[groupby_column].astype('str'))

        if comp_type == "vs":
            for i in manipul_df[groupby_column].unique():
                slicer = (manipul_df[groupby_column] == i)
                not_slicer = (manipul_df[groupby_column] != i)
                groupby_column_copy = manipul_df[groupby_column].copy()
                intermediate = manipul_df.drop(groupby_column, axis = 1)
                intermediate[slicer] = (intermediate[slicer] - manipul_df[not_slicer].mean(axis = 0, numeric_only = True)).astype('float32')
                intermediate[groupby_column] = groupby_column_copy
                manipul_df = intermediate.copy()

            title_assistant = "minus the Mean Expression of the Other clusters"
            facet_title = "Difference from Mean"
            sharey = False
            manipul_df[groupby_column] =  list(self.data.obs[groupby_column])            

        elif comp_type == "raw":
            manipul_df[groupby_column] = list(self.data.obs[groupby_column])
            facet_title = scale  + " Expression"
            sharey = True
            title_assistant = ""
        
        data_long_form = pd.melt(manipul_df, id_vars = groupby_column)
        data_long_form[facet_title] = data_long_form['value']
        default_col_num = 3
        num_panels = len(data_long_form[groupby_column].unique())
        default_row_num = ((num_panels - 1)  // default_col_num) + 1
        if default_row_num == 1:
            col_num = default_col_num - 1
        else:
            col_num = default_col_num
        number_of_rows = ((num_panels - 1)  // col_num) + 1

        if plot_type == "violin":
            griddy = sns.catplot(data_long_form, y = facet_title, 
                            hue = "antigen", 
                            palette = 'tab20', inner = None, 
                            kind = plot_type, col = groupby_column, 
                            col_wrap = col_num, sharey = sharey, sharex = False, 
                            height = 4, aspect = 1.75, **kwargs)
            # griddy.tick_params("x", labelrotation = 90)
            griddy.refline(y = 0)
            sup_Y = 1.08 + (number_of_rows * -0.01)
            if comp_type == "vs":
                griddy.figure.suptitle(f"{scale} Expression of each marker by Cluster {title_assistant}", y = sup_Y)
            else:
                griddy.figure.suptitle("Expression of each marker in each Cluster", y = sup_Y)
            if filename is not None:
                griddy.savefig(f"{self.save_dir}/{plot_type}{filename}.png", bbox_inches = "tight") 
            plt.close()
            return griddy.figure
            
        elif plot_type == "bar":
            griddy = sns.catplot(data_long_form, y = facet_title, 
                            hue = "antigen", 
                            palette = 'tab20',
                            kind = plot_type, col = groupby_column, 
                            #errorbar = None,
                            col_wrap = col_num, sharey = sharey, sharex = False, 
                            height = 4, aspect = 1.75, **kwargs)
            #griddy.tick_params("x", labelrotation = 90)
            griddy.refline(y = 0)
            sup_Y = 1.03 + (number_of_rows * -0.01)
            griddy.figure.suptitle(f"{scale} Expression of each marker by Cluster {title_assistant}", y = sup_Y)
            if filename is not None:
                griddy.savefig(f"{self.save_dir}/{plot_type}{filename}.png", bbox_inches = "tight") 
            plt.close()
            return griddy.figure
        
    def plot_cluster_histograms(self,  
                                antigen,
                                groupby_column: str = 'metaclustering', 
                                filename: Union[str, None] = None,
                                **kwargs) -> plt.figure:                                             # *** deriv_CATALYST (ish, plot output)
        '''
        Plots kde-smoothed histogram of a particular marker / antigen's expression across all the clusters in the supplied [clustering] column
        '''
        data = self.data.copy()
        metadata = self.metadata.copy()
        data.X = data.X / np.max(data.X, axis = 0)    
        intense = pd.DataFrame(data.X,columns = data.var['antigen'])
        slicer =  data.var['antigen'] == antigen
        intense = intense.loc[:,slicer]
        reshaped_for_histogram_tracings = pd.melt(intense.T.reset_index(), id_vars = ["antigen"]).drop("variable", axis = 1)
        reshaped_for_histogram_tracings.columns = ["antigen","exprs"]
        reshaped_for_histogram_tracings = reshaped_for_histogram_tracings.reset_index().drop("index", axis = 1)
        clustering_array = data.obs[groupby_column]
        reshaped_for_histogram_tracings[groupby_column] = list(clustering_array)
        reshaped_for_histogram_tracings[groupby_column] = reshaped_for_histogram_tracings[groupby_column].astype('category')
        zip_dict = {}
        reshaped_for_histogram_tracings["imageID"] = list(data.obs['sample_id'])
        reshaped_for_histogram_tracings["imageID"] = reshaped_for_histogram_tracings["imageID"].astype('str')
        for i,ii in zip(metadata['sample_id'].astype('str'),metadata["condition"].astype('str')):
            zip_dict[i] = ii
        reshaped_for_histogram_tracings["condition"] = reshaped_for_histogram_tracings["imageID"].astype('str').replace(zip_dict).astype('category')
        color_bank = [  '#0202BB','#DD0202', 
                    '#02AA02', '#888644', 
                    '#DD8888', '#EE00EE', 
                    '#EE0033', '#884488', 
                    '#009200', '#EEEE33',
                    '#33EE33','#33EEEE',
                    "#555555",'#88FF44',
                    '#447788',
                    '#3333EE','#9999EE',
                    '#CCCCFF','#FFCCCC',
                    '#CCFFCC','#CC5599',
                    '#BBBBBB','#000000']
        color_dict = {}
        patch_bank1 = [Patch(color = "#E9E9E9", label = 'condition')] 
        for i,ii in enumerate(metadata['condition'].unique()):
            if i > len(color_bank):
                color_bank = color_bank + color_bank
            color_dict[ii] = color_bank[i]
            patch_bank1.append(Patch(color = color_bank[i], label = ii))
        
        length = len(reshaped_for_histogram_tracings[groupby_column].unique())
        colwrap = 4
        row_num  = ((length - 1) // colwrap) + 1
        if (row_num == 1) and (colwrap > 2):
            colwrap = colwrap - 1
            row_num  = ((length - 1) // colwrap) + 1
        text_size = 8
        figX = colwrap * 2.35
        figY = row_num * 1.9
        figure, axs = plt.subplots(row_num, colwrap, figsize = [figX,figY])
        if isinstance(axs, np.ndarray):
            axs = axs.ravel()
        else:    ## only 1 panel /facet / ax
            axs = np.array([axs]) 

        for i,ii in enumerate(reshaped_for_histogram_tracings[groupby_column].sort_values().unique()):
            axs[i].set_title(f'{groupby_column}: {ii}', size = text_size)
            df1 = reshaped_for_histogram_tracings[reshaped_for_histogram_tracings[groupby_column] == ii]
            minimum = np.min(intense)
            maximum = np.max(intense)
            plot_over = np.linspace(minimum, maximum, 200)
            for j,jj in enumerate(df1['imageID'].astype('int').sort_values().unique().astype('str')):
                condition = metadata[metadata['sample_id'].astype('str') == jj].loc[:,'condition'].values[0]
                df = df1[df1['imageID'].astype('str') == jj]
                values = np.array(df['exprs'])
                if (len(values) > 1) and (values.sum() != 0):
                    try:
                        out = gaussian_kde(values)(plot_over)
                        out = out / np.max(out)   ## normalize between 0 -- > 1 to guarantee share y
                        axs[i].plot(plot_over, out, color = color_dict[condition], **kwargs)
                    except scipy.linalg.LinAlgError:
                        warnings.warn(f'Linear Algebra Error in Gaussian KDE function from scipy! Grouping {jj} will not be available in the plot!')


            axs[i].set_yticks([0,0.5,1], labels = ["0","0.5","1"], size = text_size)
            axs[i].set_xticks([0,0.5,1], labels = ["0","0.5","1"], size = text_size)
            axs[i].set_xmargin(0.05)
            axs[i].set_ymargin(0.05)
        
        for k in range(i + 1, colwrap*row_num, 1):
            axs[k].set_axis_off()

        sup_Y = 1.12 + (row_num * -0.03)
        figure.suptitle(f"{antigen} Expression Histograms", y = sup_Y)
        maximum_legend = np.max([len(i) for i in reshaped_for_histogram_tracings['condition'].unique()])
        x_anchor = (1.0 + (maximum_legend * 0.02)) - ((colwrap - 3)*0.035)
        figure.legend(handles = [i for i in patch_bank1], bbox_to_anchor = (x_anchor, 0.9))
        if filename is not None:
            figure.savefig(self.save_dir + "/" + filename + ".png", bbox_inches = "tight") 
        plt.close()
        return figure
        
    def plot_cluster_abundance_1(self, 
                                 groupby_column: str = "metaclustering", 
                                 number_of_columns: int = 3,
                                 filename: Union[str, None] = None,
                                 **kwargs) -> plt.figure:                                # *** deriv_CATALYST (plot appearance / output)
        '''
        Plots a stacked barplot (where the stacks all add up to 1) of the ratios of each cell type from the supplied [groupby_column]
        column in each sample_id, facetted by condition.
        '''
        to_abundance_plots = self.data.obs.copy()
        abundance_plot_prep = to_abundance_plots.groupby(['sample_id', groupby_column, 'condition'], observed = False).count().reset_index()
        abundance_plot_prep['patient_id'] = abundance_plot_prep['patient_id'].astype('int')
        divisor = abundance_plot_prep[["sample_id","patient_id"]].groupby("sample_id", observed = False).sum().reset_index()
        div_dict = {}
        for i in divisor.index:
            div_dict[int(divisor["sample_id"][i])] = divisor["patient_id"][i]
        abundance_plot_prep["total"] =  (abundance_plot_prep["patient_id"].astype('int') 
                                             / abundance_plot_prep["sample_id"].astype('int').replace(div_dict))
        abundance_plot_prep[groupby_column] = abundance_plot_prep[groupby_column].astype('category')
        abundance_plot_prep = abundance_plot_prep[abundance_plot_prep['file_name'] != 0]
        number_of_panels = len(abundance_plot_prep['condition'].unique())
        if number_of_panels < number_of_columns:
            number_of_columns = number_of_panels
        number_of_rows = (number_of_panels // number_of_columns)
        if (number_of_panels % number_of_columns) != 0:
            number_of_rows += 1

        figure, axs = plt.subplots(number_of_rows,number_of_columns, sharex = False, sharey = False)         #, figsize = (figX, figY))
        if isinstance(axs, np.ndarray):
            axs = axs.ravel()
        else:    ## only 1 panel /facet / ax
            axs = np.array([axs]) 

        for i,ii in enumerate(abundance_plot_prep['condition'].unique()):
            for_facet = abundance_plot_prep[abundance_plot_prep['condition'] == ii].copy()
            for_facet['sample_id'] = for_facet['sample_id'].astype('str')
            plot = so.Plot(for_facet, x = "sample_id", y = "total", color = groupby_column).add(so.Bar(), so.Stack(), **kwargs)
            plot = plot.on(axs[i]).plot()
            axs[i].set_title(f"{ii}")
            if ((i + 1) % number_of_columns) != 1:
                yax = axs[i].yaxis
                yax.set_label_text("")
                yax.set_ticks([0.0], labels = "")
        sup_Y = 1.03 + (number_of_rows * -0.01)
        figure.suptitle("Proportion of each cluster each in sample", y = sup_Y)
        if filename is not None:
            figure.savefig(self.save_dir + "/" + filename, bbox_inches = "tight") 
        plt.close()
        return figure

    def plot_cluster_abundance_2(self, 
                                 groupby_column: str = "metaclustering", 
                                 hue: str = "condition", 
                                 plot_type: str = "barplot",
                                 filename: Union[str, None] = None,
                                 **kwargs) -> plt.figure:                                             # *** deriv_CATALYST (plot appearance / output)
        ''' 
        Plots the abundance of each celltype (from the supplied [meta_or_merge] column in self.data.obs) in each sample id as each a bar, 
        box, or a stripplot (with plot_type == "barplot","boxplot","stripplot"). 

        Separate boxplot / stripplots are made from each condition in the supplied [hue] column to allow comparisons.
        '''
        flowsom_clustering = self.data.copy()
        cluster_data = pd.DataFrame(flowsom_clustering.X) 
        obs = flowsom_clustering.obs.copy()
        cluster_data[groupby_column] = list(obs[groupby_column])  
        cluster_data["sample_id"] = list(obs["sample_id"].astype('int')) 
        cluster_data[hue] = list(obs[hue])
        try:
            cluster_data[hue] = cluster_data[hue].astype('int') ## for ordering items properly
        except ValueError:
            cluster_data[hue] = cluster_data[hue].astype('str')

        hue_cat = pd.CategoricalDtype(categories = cluster_data[hue].unique(), ordered = True)
        #cluster_data[hue]  = cluster_data[hue].astype(hue_cat)
        divisor = cluster_data.groupby("sample_id", observed = False).count().iloc[:,0]
        zip_dict = {}
        
        for i,ii in zip(cluster_data['sample_id'].astype('str').unique(), divisor):
            zip_dict[i] = ii
        
        cluster_data["sample_id"] = cluster_data["sample_id"].astype('category')
        #print(cluster_data)
        numerators = cluster_data.groupby(["sample_id",groupby_column], observed = False).count().loc[:,0]
        numerators = numerators.reset_index()
        numerators['divisor'] = numerators['sample_id'].astype('str').replace(zip_dict)
        numerators['proportions'] = (numerators[0] / numerators['divisor']) * 100
        zip_dict = {}
        
        for i,ii in zip(cluster_data['sample_id'].astype('str'), cluster_data[hue]):
            zip_dict[i] = ii
        
        numerators[hue] = numerators['sample_id'].astype('str').replace(zip_dict).astype(hue_cat)

        #print(numerators)
        #print(numerators[groupby_column].unique())
        #print(numerators[hue].unique())
        # print(numerators['proportions'].sum()  / len(numerators['sample_id'].unique()))    ## should add up to 100...
        griddy = sns.FacetGrid(numerators, col = groupby_column, col_wrap = 4, sharey = False)
        if plot_type == "boxplot":
            griddy.map_dataframe(sns.boxplot, x = hue, y = "proportions", hue = hue, palette='viridis', **kwargs)
            griddy.add_legend()
        elif plot_type == "stripplot":
            griddy.map_dataframe(sns.stripplot, x = hue, y = "proportions", hue = hue, palette='viridis', **kwargs)
            griddy.add_legend()
        elif plot_type == "barplot":
            griddy.map_dataframe(sns.barplot, x = hue, y = "proportions", hue = hue, palette='viridis', **kwargs)
            griddy.add_legend()
        plt.style.use('ggplot')
        if filename is not None:
            griddy.figure.savefig(self.save_dir + "/" + filename, bbox_inches = "tight") 
        plt.close()
        return griddy.figure

    def do_cluster_stats(self, 
                         groupby_column: str = "metaclustering", 
                         marker_class: str = 'type',
                         ) -> dict[Union[str, int], pd.DataFrame]:
        '''
        Calculated statistics by pairwise ANOVAs (effectively a t-test) between each cluster's marker expression and the marker expression of 
        the rest of the dataset. Instead of using all the cells individually, an average is taken of each sample_id 

        Args:
            groupby_column (string): 
                The column in the self.data.obs dataframe to group the cells for making comparison between unique value in 
                this column (usually a celltype column, like "metaclustering", but could be something else, like condition or sample_id)

            marker_class (string == "All", "type", "state", or "none" ): 
                what markers to include in the comparison. Usually "type", should typically match the markers used to generate the cell clustering / groupby being compared.

        Returns:
            a dictionary with keys = unique values of the groupby_column, and values = pandas dataframes containing the statistics for that 
            groupby_column value. This dictionary is also saved as self.df_out_dict, from which it is accessed by the self.plot_cluster_stats method
        '''
        data = self.data.copy()
        manipul_df = pd.DataFrame(data.X)
        if marker_class != "All":
            marker_slicer = np.array(self.panel['marker_class'] == marker_class)
            manipul_df = manipul_df.T[marker_slicer].T
            manipul_df.columns = data.var.index[marker_slicer]
        else:
            manipul_df.columns = data.var.index

        list_of_antigens = np.array((manipul_df.columns))        
        manipul_df[groupby_column] = list(data.obs[groupby_column])
        manipul_df["sample_id"] = list(data.obs["sample_id"])
        manipul_df = manipul_df.groupby(["sample_id", groupby_column], observed = False).mean(numeric_only = True).reset_index()
        cluster_dict = {}
        anti_cluster_dict = {}
        for i in manipul_df[groupby_column].unique():
            cluster_dict[i] = manipul_df[manipul_df[groupby_column] == i].drop(["sample_id", groupby_column], axis = 1)
            anti_cluster_dict[f"-{i}"] = manipul_df[manipul_df[groupby_column] != i].drop(["sample_id", groupby_column], axis = 1)

        df_out_dict = {}
        for i in cluster_dict:
            #whole_group_means = anti_cluster_dict[f"-{i}"].mean(axis = 0)   #### really whole group mean, except the group in question...
            means = cluster_dict[i].mean(axis = 0)
            stds = cluster_dict[i].std(axis = 0)
            mean_diff  = means - anti_cluster_dict[f"-{i}"].mean(axis = 0)
            ## previously manually did t-test --> now favor ANOVA
            n = len(cluster_dict[i])
            se = stds / np.sqrt(n)    ## still want se for plotting later (?!)
            anova = scipy.stats.f_oneway(cluster_dict[i], anti_cluster_dict[f"-{i}"], axis = 0)   # alt: kruskal
            my_pvalues = anova[1]
            my_t = anova[0]
            top_t_stats = np.flip(np.sort(np.abs(my_t)))[:]
            slicer = (np.abs(my_t) >= top_t_stats[-1])
            antigens = list_of_antigens[slicer]
            top_ts = my_t[slicer]
            adj_pvalues = scipy.stats.false_discovery_control(my_pvalues + 1e-25, method = 'bh')
            top_ps = adj_pvalues[slicer]
            mean_changes = mean_diff[slicer]
            top_ts = [sigfig.round(i, 4, warn = False) for i in top_ts]
            top_ps = [sigfig.round(i, 4, warn = False) for i in top_ps]
            mean_changes = [sigfig.round(i, 4, warn = False) for i in mean_changes]
            se = [sigfig.round(i, 4, warn = False) for i in se]
            out_df = pd.DataFrame([top_ts, 
                                   my_pvalues, 
                                   top_ps, 
                                   mean_changes, 
                                   se], 
                                   columns = antigens, 
                                   index = ["F_statistic", "p_values", "FDR_corrected","Difference in expression mean", "st_error"])
            out_df = out_df.T
            out_df["p_values"] = my_pvalues
            out_df["FDR_corrected"] = top_ps
            out_df = out_df.sort_values('p_values')
            out_df["p_values"] = [sigfig.round(i, 4, warn = False) for i in out_df["p_values"]]        
            df_out_dict[i] = out_df
            self.df_out_dict = df_out_dict

        return df_out_dict

    def plot_cluster_stats(self, 
                           statistic: str = "FDR_corrected",
                           filename: Union[str, None] = None,
                           **kwargs) -> plt.figure:
        '''
        Plots a heatmap of from cluster statistics calculated with the method self.do_cluster_stats. 
        
        Can select statistic ("F_statistic", "p_values", "FDR_corrected") to display. These options correspond to the names of column in the
        sub-dataframes of self.df_out_dict. 
        p_values and FDR-corrected p values are displayed after -Log() transformation
        '''
        df_out_dict = self.df_out_dict
        stat_df = pd.DataFrame()
        for j in df_out_dict.keys():
            stat_df[j] = df_out_dict[j][statistic].astype('float')
        df_array = np.array(stat_df)

        if (statistic == "p_values") or (statistic == "FDR_corrected"):
            df_array = -(np.log(df_array + 0.0000000000001))
            title_assistant = "Neg_log_"
        else:
            title_assistant = ""

        df_array = np.apply_along_axis(_quant, arr = df_array, axis = 0, upper = 0.9, lower = 0.1)
        
        new_df = pd.DataFrame(df_array, index = stat_df.index,  columns = stat_df.columns).T    ## quant 0-->1 same as min_max
        plot = sns.clustermap(new_df.T, cmap = "coolwarm", linewidths = 0.01, yticklabels = True, xticklabels = True, **kwargs)
        plot.figure.suptitle(f"-log {statistic.replace('_',' ')} p values for each ANOVA comparison, \n scaled within each cluster", y = 1.04)
        if filename is not None:
            plot.savefig(f"{self.save_dir}/{title_assistant}{filename}.png", bbox_inches = "tight") 
        plt.close()
        return plot.figure

    def do_abundance_ANOVAs(self, 
                            groupby_column: str = 'merging', 
                            variable: str = 'condition',
                            conditions: list[str] = [],
                            ) -> pd.DataFrame:                                      # *** deriv_CATALYST / diffcyt (ish, PalmettoBUG's version of 
                                                                                                                    # abundance statistics)
        '''
        Performs pairwise ANOVA tests (or effectively, a t-test) between two provided conditions in the self.data.obs['condition'] column, looking at 
        the abundance (as % in each sample_id) of the cell types specified in the groupby_column. 

        Args:
            groupby_column (str): 
                The colum in self.data.obs where the cell type information is contained

            variable (str): 
                The column in self.data.obs where the independent variable information is found (default = 'condition')

            condition1 / condition2 (strings or None): 
                list of unique values in self.data.obs[variable] to be compared by ANOVA if None, then wil perform an ANOVA test on all the conditions in the dataset. 

            filename (string or None): 
                The filename for the statistics table exported as a csv file to self.data_table_dir. If None, then no csv will be exported to self.data_table_dir

        Returns:
            (pandas dataframe) representing the statistics calculated by this function
        '''
        data = self.data
        merging_clusters = data.obs[groupby_column].unique()
        
        obs = data.obs.copy()
        obs[groupby_column] = obs[groupby_column].astype('category')

        if conditions == []:
            conditions = list(self.data.obs[variable].unique())
        
        condition_list = []
        for i in conditions:
            condition_data = obs[obs[variable] == i]
            
            sample_ids = condition_data['sample_id'].unique()
            sample_holder = np.zeros([len(sample_ids),len(merging_clusters)])
            for jj,j in enumerate(sample_ids):
                sample_data = condition_data[condition_data['sample_id'] == j]
                sample_data.loc[:,groupby_column] = sample_data[groupby_column].cat.set_categories(obs[groupby_column].cat.categories)
                cluster_counts = sample_data.groupby(groupby_column, observed = False).count()['file_name']   
                                                    ## column used to subset on is irrelevant (it just needs to exist...)
                total = len(sample_data)
                percentages = (cluster_counts / total) * 100
                sample_holder[jj,:] = percentages
                labeler = percentages.index
            condition_list.append(pd.DataFrame(sample_holder, columns = labeler))
        ANOVA_f, ANOVA_p = scipy.stats.f_oneway(*condition_list)
        output_df = pd.DataFrame()
        output_df.index = condition_list[0].columns.values
        output_df['f statistics'] = [sigfig.round(j,4, warn = False) for j in ANOVA_f]
        output_df['p_value'] = [sigfig.round(j,4, warn = False) for j in ANOVA_p] 
        p_adj = [sigfig.round(j,4, warn = False) for j in scipy.stats.false_discovery_control(ANOVA_p, method = 'bh')]
        output_df['p_adj'] = p_adj
        for i,ii in enumerate(condition_list):
            output_df[f'{conditions[i]} mean %'] = [sigfig.round(j,4, warn = False) for j in ii.mean()]
            output_df[f'{conditions[i]} stdev'] = [sigfig.round(j,4, warn = False) for j in ii.std()]

        output_df = output_df.sort_values('f statistics', ascending = False)        
        self.abundance_ANOVA_stat_table = output_df
        return output_df
    
    def do_count_GLM(self, 
                  conditions: list[str], 
                  variable: str = "condition", 
                  groupby_column: str = "merging",  
                  family = "Poisson", 
                  filename: Union[str, None] = None,
                  ) -> pd.DataFrame:
        '''
        Performs a statistical test on cell abundance / cell count using generalized linear models. 
        
        Cell counts are taken for each sample_id in each condition and then those aggreagated per-sample_id numbers are used in the GLM.

        Args:
            conditions (list of strings): 
                conditions to compare. In GUI, either pairwise or all possible conditions at once are compared.

            variable (string): 
                the column in self.data.obs that will be treated as the independent variable for the test. Almost always 'condition'

            groupby_column (string): 
                the column in self.data.obs that contains the cell type information from which counts / abundance will be calculated

            family (string -- "Poisson", "NegativeBinomial"): 
                The distribution to use in the GLM. Can be "Poisson" or "NegativeBinomial". Other distributions, such as "Gaussian" and "Binomial" are 
                no recommended or not currently configured properly. 

            filename (string or None):  
                the filename for the csv exported into self.data_table_dir. If None, no such file is exported

        Returns:
            pandas dataframe: Summary statistics from the results of the model

        Inputs/Outputs:
            Outputs: 
                If filename is provided (is not None), then exports the summary statistic table to self.data_table_dir/filename.csv
        '''
        GLM_dict = {"Poisson" : sm.families.Poisson,
                    "Binomial" : sm.families.Binomial, 
                    "NegativeBinomial" : sm.families.NegativeBinomial, 
                    "Gaussian" : sm.families.Gaussian}
        model = GLM_dict[family]()

        to_data = self.data.copy()
        to_data_X = pd.DataFrame(to_data.X, columns = to_data.var.index)
        to_data_metadata = to_data.obs.reset_index().drop('index', axis = 1)
        data = pd.concat([to_data_X,to_data_metadata], axis = 1)

        slicer = np.array([(str(i) in conditions) for i in data[variable].astype('str')])
        data = data[slicer]
        data['sample_id'] = data['sample_id'].astype('str').astype('category')

        special_category = pd.CategoricalDtype(list(data[variable].astype('str').unique()), ordered = True)
        data[variable] = data[variable].astype('str')
        data[variable] = data[variable].astype(special_category)

        data[groupby_column] = data[groupby_column].astype('str').str.replace(" ","_").str.replace("+","")
        try:
            uniques = data[groupby_column].astype('int').unique().astype('str') ## for ordering items properly
        except ValueError:
            uniques = data[groupby_column].unique().astype('str')
        uniques = [i.replace("-", "_") for i in uniques]

        if family == "Binomial":
            print("Binomial models not configured properly at the moment. Exiting")
            return None
            for ii,i in enumerate(uniques):
                try:
                    int(i)
                    use_i = f'{groupby_column}{i}'
                except ValueError:
                    use_i = i
                data.loc[:,use_i] = data[groupby_column] == i
                results = sm.GLM.from_formula(f"{use_i} ~ {variable}", data = data, family = model).fit()
                consistent_columns = ['comparison', f"{groupby_column}", "pvalue",
                                    f"{conditions[0]} avg", f"{conditions[0]} 95% CI +/-",
                                    f"{conditions[1]} avg", f"{conditions[1]} 95% CI +/-"]
                
                pvalue = sigfig.round(results.pvalues.iloc[1], 3, warn = False)
                condition1 = sigfig.round(results.params.iloc[0], 3, warn = False)     
                condition1_CI_plus_minus = sigfig.round((results.bse.iloc[0] * 1.96), 3, warn = False)       
                
                condition2 = sigfig.round(condition1 + results.params.iloc[1], 3, warn = False)         
                condition2_CI_plus_minus = sigfig.round((results.bse.iloc[1] * 1.96), 3, warn = False)      
                temp_row_array = np.array([f"{conditions[0]} vs. {conditions[1]}", i, pvalue, 
                                    condition1, condition1_CI_plus_minus,
                                    condition2, condition2_CI_plus_minus])
        
                temp_row = pd.DataFrame(temp_row_array[:, np.newaxis].T, columns = consistent_columns, index = [ii])
                if ii == 0:
                    output_df = temp_row
                else:
                    output_df = pd.concat([output_df, temp_row], axis = 0)
        
            output_df['p_adj'] = [sigfig.round(i, 
                                               3, 
                                               warn = False) for i in scipy.stats.false_discovery_control(output_df['pvalue'].astype('float') + 1e-25, 
                                                                                                          method = 'bh')]
            new_column_order = ['comparison', groupby_column, "pvalue", "p_adj",
                                    f"{conditions[0]} avg", f"{conditions[0]} 95% CI +/-",
                                    f"{conditions[1]} avg", f"{conditions[1]} 95% CI +/-"]
            to_return = pd.DataFrame()
            for i in new_column_order:
                to_return[i] = output_df[i]
            to_return['to_sort'] = to_return.loc[:, 'pvalue'].astype('float64')
            to_return = to_return.sort_values('to_sort')
            to_return = to_return.drop("to_sort", axis = 1)
        
        elif family != "Gaussian":
            new_obs_df = data.drop(["file_name"],axis = 1)
            new_obs_df['random_column_name'] = 0

            zip_dict = {}
            for m,mm in zip(new_obs_df['sample_id'], new_obs_df[variable]):
                zip_dict[m] = mm
        
            grouped = new_obs_df.groupby([groupby_column,'sample_id'], observed = False).count()
            to_drop_list = []
            if (len(new_obs_df.groupby([groupby_column,variable], observed = True).count()) != 
                len(new_obs_df.groupby([groupby_column,variable], observed = False).count())):
                for i in new_obs_df.groupby([groupby_column,variable], observed = False).count().index:
                    try:
                        new_obs_df.groupby([groupby_column,variable], observed = True).count().loc[i]
                    except Exception:
                        to_drop_list.append(i)
                        
            grouped = grouped.reset_index()
            grouped[variable] = grouped['sample_id'].astype('str').replace(zip_dict)
            for i in to_drop_list:
                slicer = (np.array(grouped[groupby_column] != i[0]).astype('int') + np.array(grouped[variable] != i[1]).astype('int')) != 0
                grouped = grouped[slicer]

            ready_for_GLM = grouped.pivot(columns = groupby_column, index = [variable, 'sample_id'], values = 'random_column_name').reset_index()
            ready_for_GLM['divisor'] = ready_for_GLM.drop(['sample_id', variable], axis = 1).sum(axis = 1, numeric_only = True).astype('int')
            
            if family == "Poisson":
                scale = None
            else:
                scale = "dev"

            ready_for_GLM.columns = [i.replace(" ","_").replace("+","plus").replace("-","_") for i in ready_for_GLM.columns.astype('str')]   
        
            for ii,i in enumerate(uniques):
                try:
                    int(i)
                except ValueError:
                    pass
                else:
                    old_column = ready_for_GLM[i].copy()
                    i = f'{groupby_column}{i}'
                    ready_for_GLM[i] = old_column
                to_do_stats = ready_for_GLM[ready_for_GLM[i].notna()].reset_index()
                to_do_stats[i] = to_do_stats[i].astype('int')
                remaining_conditions = to_do_stats[variable].astype('str').unique()
                special_category = pd.CategoricalDtype(remaining_conditions, ordered = True)
                to_do_stats[variable] = to_do_stats[variable].astype('str')
                to_do_stats[variable] = to_do_stats[variable].astype(special_category)
                offset = np.log(to_do_stats['divisor'].astype('int'))

                if len(remaining_conditions) == 1:
                    if self._in_gui:
                        tk.messagebox.showwarning("Warning!", message = f"{i} is only present in one condition! Skipping this cluster.")
                    else:
                        print(f"{i} is only present in one condition! Skipping this cluster.")
                    continue

                if len(remaining_conditions) == 2:
                    comparison = f"{remaining_conditions[0]} vs. {remaining_conditions[1]}"
                else:
                    comparison = "Multiple Conditions"

                results = sm.GLM.from_formula(f"{i} ~ {variable}", data = to_do_stats, family = model, offset = offset).fit(scale = scale)

                list_of_conditions_columns = [[f"{i} est. avg", f"{i} 95% CI +/-"] for i in conditions]
                consistent_columns = ['comparison', f"{groupby_column}", "pvalue"]
                for h in list_of_conditions_columns:
                    consistent_columns = consistent_columns + h
                                        
                pvalue = sigfig.round(results.pvalues.iloc[1], 3, warn = False)
                pre_pre_transform = results.params.iloc[0]
                condition_avg_and_CI_list = []

                k = 0
                for kk in conditions:
                    if kk not in list(to_do_stats[variable].astype('str').unique()):
                        condition_avg_and_CI_list.append(0.0)
                        condition_avg_and_CI_list.append(0.0)
                        continue
                    if k == 0:
                        pre_transform = np.exp(pre_pre_transform) * 100
                        condition1 = sigfig.round(pre_transform, 3, warn = False) 
                        condition_avg_and_CI_list.append(condition1)
                        condition1_CI_plus_minus = sigfig.round((np.exp(results.params.iloc[0] + results.bse.iloc[0]) 
                                                        - np.exp(results.params.iloc[0]- results.bse.iloc[0])) * 50, 
                                                        3, warn = False)
                        condition_avg_and_CI_list.append(condition1_CI_plus_minus)
                        k += 1
                    else:    
                        condition2 = sigfig.round(np.exp((results.params.iloc[0] + results.params.iloc[k])) * 100, 3, warn = False)     
                        condition_avg_and_CI_list.append(condition2)
                        condition2_CI_plus_minus = sigfig.round((np.exp(results.params.iloc[0] + results.params.iloc[k] + results.bse.iloc[k]) 
                                                                - np.exp(results.params.iloc[0] + results.params.iloc[k] - results.bse.iloc[k])) * 50, 
                                                                3, warn = False) 
                        condition_avg_and_CI_list.append(condition2_CI_plus_minus)
                        k += 1

                temp_row_array = np.array([comparison, i, pvalue] + condition_avg_and_CI_list)
                temp_row = pd.DataFrame(temp_row_array[:, np.newaxis].T, columns = consistent_columns, index = [ii])
                if ii > 0:
                    output_df = pd.concat([output_df, temp_row], axis = 0)
                else:
                    output_df = temp_row

            output_df['p_adj'] = [sigfig.round(i, 3, warn = False) 
                                for i in scipy.stats.false_discovery_control(output_df['pvalue'].astype('float') + 1e-25, method = 'bh')]
            new_column_order = ['comparison', groupby_column, "pvalue", "p_adj"] + consistent_columns[3:]
            to_return = pd.DataFrame()
            for i in new_column_order:
                to_return[i] = output_df[i]
            to_return['to_sort'] = to_return.loc[:, 'pvalue'].astype('float64')
            to_return = to_return.sort_values('to_sort')
            to_return = to_return.drop("to_sort", axis = 1)


        elif family == "Gaussian":
            new_obs_df = data.drop(["file_name"],axis = 1)
            new_obs_df['random_column_name'] = 0

            zip_dict = {}
            for m,mm in zip(new_obs_df['sample_id'], new_obs_df[variable]):
                zip_dict[m] = mm
        
            grouped = new_obs_df.groupby([groupby_column,'sample_id'], observed = False).count()
            to_drop_list = []
            if (len(new_obs_df.groupby([groupby_column,variable], observed = True).count()) != 
                len(new_obs_df.groupby([groupby_column,variable], observed = False).count())):
                for i in new_obs_df.groupby([groupby_column,variable], observed = False).count().index:
                    try:
                        new_obs_df.groupby([groupby_column,variable], observed = True).count().loc[i]
                    except Exception:
                        to_drop_list.append(i)
                        
            grouped = grouped.reset_index()
            grouped[variable] = grouped['sample_id'].astype('str').replace(zip_dict)
            for i in to_drop_list:
                slicer = (np.array(grouped[groupby_column] != i[0]).astype('int') + np.array(grouped[variable] != i[1]).astype('int')) != 0
                grouped = grouped[slicer]

            ready_for_GLM = grouped.pivot(columns = groupby_column, index = [variable, 'sample_id'], values = 'random_column_name').reset_index()
            ready_for_GLM['divisor'] = ready_for_GLM.drop(['sample_id', variable], axis  =1).sum(axis = 1, numeric_only = True).astype('int')
            for i in uniques:
                ready_for_GLM[i] = ready_for_GLM[i].astype('float')
                ready_for_GLM.loc[:, i] = ready_for_GLM[i] / ready_for_GLM['divisor'] 


            ready_for_GLM.columns = [i.replace(" ","_").replace("+","plus").replace("-","_") for i in ready_for_GLM.columns.astype('str')]

            for ii,i in enumerate(uniques):
                try:
                    int(i)
                except ValueError:
                    pass
                else:
                    old_column = ready_for_GLM[i].copy()
                    i = f'{groupby_column}{i}'
                    ready_for_GLM[i] = old_column

                to_do_stats = ready_for_GLM[ready_for_GLM[i].notna()].reset_index()
                remaining_conditions = to_do_stats[variable].astype('str').unique()
                special_category = pd.CategoricalDtype(remaining_conditions, ordered = True)
                to_do_stats[variable] = to_do_stats[variable].astype('str')
                to_do_stats[variable] = to_do_stats[variable].astype(special_category)
            
                if len(remaining_conditions) == 1:
                    if self._in_gui:
                        tk.messagebox.showwarning("Warning!", message = f"{i} is only present in one condition! Skipping this cluster.")
                    else:
                        print(f"{i} is only present in one condition! Skipping this cluster.")
                    continue

                if len(remaining_conditions) == 2:
                    comparison = f"{remaining_conditions[0]} vs. {remaining_conditions[1]}"
                else:
                    comparison = "Multiple Conditions"

                results = sm.GLM.from_formula(f"{i} ~ {variable}", data = to_do_stats, family = model).fit()

                list_of_conditions_columns = [[f"{i} est. avg", f"{i} 95% CI +/-"] for i in conditions]
                consistent_columns = ['comparison', f"{groupby_column}", "pvalue"]
                for h in list_of_conditions_columns:
                    consistent_columns = consistent_columns + h
                
                pvalue = sigfig.round(results.pvalues.iloc[1], 3, warn = False)
                pre_transform = results.params.iloc[0] * 100
                condition_avg_and_CI_list = []

                k = 0
                for kk in conditions:
                    if kk not in list(to_do_stats[variable].astype('str').unique()):
                        condition_avg_and_CI_list.append(0.0)
                        condition_avg_and_CI_list.append(0.0)
                        continue
                    if k == 0:
                        condition1 = sigfig.round(pre_transform, 3, warn = False) 
                        condition_avg_and_CI_list.append(condition1)
                        condition1_CI_plus_minus = sigfig.round(results.bse.iloc[0] * 100, 3, warn = False)
                        condition_avg_and_CI_list.append(condition1_CI_plus_minus)
                        k += 1
                    else:    
                        condition2 = sigfig.round((results.params.iloc[0] + results.params.iloc[1]) * 100, 3, warn = False)      
                        condition_avg_and_CI_list.append(condition2)
                        condition2_CI_plus_minus = sigfig.round(results.bse.iloc[1] * 100 , 3, warn = False) 
                        condition_avg_and_CI_list.append(condition2_CI_plus_minus)
                        k += 1
       
                temp_row_array = np.array([comparison, i, pvalue] + condition_avg_and_CI_list)

                temp_row = pd.DataFrame(temp_row_array[:, np.newaxis].T, columns = consistent_columns, index = [ii])
                if ii > 0:
                    output_df = pd.concat([output_df, temp_row], axis = 0)
                else:
                    output_df = temp_row

            output_df['p_adj'] = [sigfig.round(i, 3, warn = False) 
                                  for i in scipy.stats.false_discovery_control(output_df['pvalue'].astype('float') + 1e-25, method = 'bh')]
            new_column_order = ['comparison', groupby_column, "pvalue", "p_adj"] + consistent_columns[3:]
            to_return = pd.DataFrame()
            for i in new_column_order:
                to_return[i] = output_df[i]
            to_return['to_sort'] = to_return.loc[:, 'pvalue'].astype('float64')
            to_return = to_return.sort_values('to_sort')
            to_return = to_return.drop("to_sort", axis = 1)
            
        to_return = to_return.iloc[:,:]

        if filename is not None:
            to_return.to_csv(self.data_table_dir + f"/{filename}.csv", index = False)
        return to_return
    
    def do_state_exprs_ANOVAs(self,                     
                            marker_class: str = "state", 
                            groupby_column: str = 'merging', 
                            variable: str = 'condition', 
                            statistic: str = 'mean',
                            test: str = 'anova',
                            conditions: list[str] = [],
                            filename: Union[str, None] = None,
                            ) -> pd.DataFrame:                                          # *** deriv_CATALYST / diffcyt (ish, PalmettoBUG's 
                                                                                                        # version of state marker statistics)
        '''
        Performs statistical comparison of marker expression within cell types between conditions using ANOVA

        Aggregates marker expression using mean or median within each unique [sample_id + groupby] column combination and then compares across 
        conditions

        Args:
            marker_class (str): 
                one of -- "All", "type", "state", "none" -- determines what markers are compared. 
                See: self.data.var['marker_class'] or the Analysis_panel file

            groupby_column (str): 
                the column title of the cell type column in self.data.obs. Usually a string, but theoretically could be any allowed in a pandas dataframe column title. 

            variable (str): 
                the column of self.data.obs containing the independent variable / condition. Default = 'condition;

            statistic (str): 
                one of -- "mean", "median" -- which aggregation statistic to use

            conditions(list of str): 
                if empty (default) will use all the unique condiitons in self.data.obs[variable]. Otherwise, will only compared the conditions in the this 
                list -- values in this list should be values in self.data.obs[variable], values not in this will be ignored. 

            filename (str or None): 
                If not None, the name for saving the output datatable as a csv file in self.data_table_dir

        Returns:
            (pandas dataframe) the summary statistics of the ANOVA tests

        Inputs/Outputs:
            Outputs: 
                If filename is provided (is not None), then exports the summary statistic table to self.data_table_dir/filename.csv
        '''
        ind_var_column = variable
        stat_test_dict = {'anova':scipy.stats.f_oneway, 'kruskal':scipy.stats.kruskal}
        stat_test_labels_dict = {'anova':'F statistic','kruskal':'H statistic'}
        stat_func = stat_test_dict[test]
        stat_label = stat_test_labels_dict[test]
        split_by_sample_id = True    ## previously a boolean argument of the function -- toggled whether the data
                                        # introduced into the ANOVA what of every individual cell's expression
                                        # of aggregate statistics (mean / median) of the expression within each sample_id
        panel = self.panel.copy()
        data = self.data.copy()
        if len(conditions) == 0:
            conditions = data.obs[ind_var_column].unique()
        else:
            slicing_array = np.array([(i in conditions) for i in data.obs[ind_var_column].astype(str)])
            data = data[slicing_array]
        if groupby_column == "whole dataset":  #########
            groupby_column = "whole dataset"
            data.obs["whole dataset"] = "whole dataset"

        merging_clusters = data.obs[groupby_column].unique()
        
        data_df = pd.DataFrame(data.X, columns = data.var.index)
        if marker_class != "All":
            slicer = panel['marker_class'] == marker_class
            if slicer.sum() == 0:
                return None
            data_df = data_df.T[np.array(slicer)].T
            non_type_antigens = panel[slicer]['antigen']
        else:
            non_type_antigens = panel['antigen']

        data_df[groupby_column] = data.obs[groupby_column].values    
        data_df['sample_id'] = data.obs['sample_id'].astype('str').values
        data_df['sample_id'] = data_df['sample_id'].astype('category')
        data_df[ind_var_column] = data.obs[ind_var_column].values

        ind_var_to_sample_id = {}
        for i,ii in zip(data_df['sample_id'], data_df[ind_var_column]):
            ind_var_to_sample_id[i] = ii 
        
        if split_by_sample_id is True:
            stat_helper_label = "avg "
            if statistic == "median":
                data_df = data_df.groupby(['sample_id', groupby_column], observed = False).median(numeric_only = True).fillna(0).reset_index()
            elif statistic == "mean":
                data_df = data_df.groupby(['sample_id', groupby_column], observed = False).mean(numeric_only = True).fillna(0).reset_index()
        else:
            stat_helper_label = ""

        data_df[ind_var_column] = data_df['sample_id'].astype('str').replace(ind_var_to_sample_id)        
        grand_condition_list = []
        
        for j,jj in enumerate(merging_clusters):
            merging_data = data_df[data_df[groupby_column] == jj]
            condition_list = []
            for i in merging_data[ind_var_column].unique():
                condition_data = merging_data[merging_data[ind_var_column] == i]
                condition_list.append(condition_data.drop(['sample_id',groupby_column,ind_var_column], axis = 1))
            grand_condition_list.append(condition_list)
            ANOVA_f, ANOVA_p = stat_func(*condition_list)
            if j == 0:
                merging_array_F = ANOVA_f[np.newaxis,:]
                merging_array_p = ANOVA_p[np.newaxis,:]
            else:
                merging_array_F = np.concatenate([merging_array_F,ANOVA_f[np.newaxis,:]], axis = 0)
                merging_array_p = np.concatenate([merging_array_p,ANOVA_p[np.newaxis,:]], axis = 0)
                    
        p_value_df = pd.DataFrame(merging_array_p, columns = non_type_antigens)
        p_value_df[groupby_column] = merging_clusters
        p_value_df = pd.melt(p_value_df, id_vars = groupby_column)
        
        F_values_df = pd.DataFrame(merging_array_F, columns = non_type_antigens)
        F_values_df[groupby_column] = merging_clusters
        F_values_df = pd.melt(F_values_df, id_vars = groupby_column)
        
        final_df = pd.DataFrame()
        final_df['antigen'] = p_value_df['antigen']
        final_df[groupby_column] = p_value_df[groupby_column]
        final_df['p_value'] = [sigfig.round(i,4, warn = False) for i in p_value_df['value']]
        final_df['p_adj'] = [sigfig.round(i,4, warn = False) 
                             for i in scipy.stats.false_discovery_control(np.nan_to_num(np.array(final_df['p_value'] )) + 1e-25, method = 'bh')]
        final_df[stat_label] = [sigfig.round(i,4, warn = False) for i in F_values_df['value']]
        final_df = final_df.groupby(['antigen',groupby_column], observed = False).mean()
        condition_dict = {}
        for jj,j in enumerate(grand_condition_list):
            for i,ii in enumerate(j):
                ii[groupby_column] = data_df[groupby_column].astype('str')
                if statistic == "mean":
                    merging_mean_condition = pd.melt(ii.groupby(groupby_column, 
                                                                observed = True).mean(numeric_only = True).T.reset_index(), 
                                                    id_vars = 'antigen')
                    
                    merging_std_condition = pd.melt(ii.groupby(groupby_column, 
                                                               observed = True).std(numeric_only = True).T.reset_index(), 
                                                    id_vars = 'antigen')
                    
                    spread_stat = f'{stat_helper_label}stdev'

                elif statistic == "median":
                    merging_mean_condition = pd.melt(ii.groupby(groupby_column, 
                                                                observed = True).median(numeric_only = True).T.reset_index(), 
                                                     id_vars = 'antigen')
                    
                    merging_std_condition = pd.melt(ii.groupby(groupby_column, 
                                                        observed = True).quantile(q = 0.75, 
                                                                                  numeric_only = True).T.reset_index(), 
                                                    id_vars = 'antigen')
                    
                    merging_std_condition['value'] = (merging_std_condition['value'] 
                                        - pd.melt(ii.groupby(groupby_column, 
                                                             observed = True).quantile(q = 0.25, 
                                                                                       numeric_only = True).T.reset_index(), 
                                                   id_vars = 'antigen')['value'])
                    
                    spread_stat = f'{stat_helper_label}IQR'
                merging_mean_condition = merging_mean_condition.groupby(['antigen',groupby_column], observed = False).mean()   
                                ## These secondary groupby lines only serve to set up the multi-index (values should not change)
                merging_std_condition = merging_std_condition.groupby(['antigen',groupby_column], observed = False).mean()
        
                merging_mean_condition['stdev'] = merging_std_condition['value']
                if jj == 0:
                    condition_dict[str(i)] = merging_mean_condition
                else:
                    condition_dict[str(i)] = pd.concat([condition_dict[str(i)], merging_mean_condition], axis = 0)
                
        for i,ii in enumerate(condition_dict):
            condition_dict[ii] = condition_dict[ii].groupby(['antigen',groupby_column], observed = False).mean()
            stat_list = [sigfig.round(i, 4, warn = False) for i in list(condition_dict[ii]['value'])]
            final_df[f'{stat_helper_label}{conditions[i]} {statistic} exprs'] = stat_list
            dev_list = [sigfig.round(i, 4, warn = False) for i in list(condition_dict[ii]['stdev'])]
            final_df[f'{conditions[i]} {spread_stat}'] = dev_list

        output_stat_table = final_df.reset_index().sort_values(stat_label, ascending = False)
        if filename is not None:
            output_stat_table.to_csv(self.data_table_dir + f"/{filename}.csv", index = False)
        return output_stat_table
    
    def export_data(self, 
                    subset_columns: Union[list[str], None] = None, 
                    subset_types: Union[list[list[str]], None] = None, 
                    groupby_columns: Union[list[str], None] = None, 
                    statistic: str = 'mean',
                    include_marker_class_row: bool = False,
                    filename: Union[str, None] = None, 
                    ) -> pd.DataFrame:
        '''
        Exports currently loaded data from the Analysis, from self.data. 
        
        Preserves any previously performed scaling, dropped categories, & batch correction. Always of arcsinh(data / 5) transformed data. Can
        export the entirety of relevant self.data information, or export subsets of self.data, and/or export aggregate summary statistics for 
        groups within the data. 

        Args:
            subset_columns (list[str] or None): 
                a list of strings denoting the columns to subset the dataframe's rows on (here and in other arguments, non-string input is attepmted 
                to be cast to strings inside the function, as well as the corresponding column of the data). if this or subset_types is None, no subsetting occurs. 

            subset_types (list[list[str]] or None): 
                a list contains sub-lists for strings. The length of the upper list must be the length of
                the subset_columns list, as each sub-list contains strings corresponding to the rows to keep. 

                    As in: if subset_columns = ['column1', 'column3'] and subset_types = [['type2', 'type6'],['typeB', 'typeZ']],
                    then rows of type2 / type6 in column1 will be kept, and similarly rows of typeB / typeZ in column2.

                When > 1 columns / conditions are subsetted on, as in the above example, the rows that are kept are the union of 
                all the subsetting conditions WITHIN a given column, but the intersection BETWEEN what is kept from each column. 
                So in the above example, all rows of column1 == type2/6 that also have column2 == typeB/Z are the rows that are maintained.
                                                        
            groupby_columns (list[str] or None): 
                A list of strings indicating what columns of the data to groupby. If None, then grouping is not performed.
                Used like this:    self.data.obs.groupby(groupby_columns)              but on a dataframe containing the data.X values as well

            statistic (str): 
                Possible values: 'mean','median','sum','std','count'. Denotes the pandas groupby method to be used after grouping (ignored if groupby_columns is None).
                Numeric methods (mean, median, sum, std) are only applied to numeric columns, so only those columns + the groupby columns 
                will be in the final dataframe / csv

            include_marker_class_row (bool): 
                Whether to include the marker_class information as a row at the bottom of the table --> True to 
                include this row -- useful for reimport into PalmettoBUG.
                False to not include this row -- this is probably better for import into non-PalmettoBUG software for analysis,
                or at the least the user will need to remember to remove this row before analyzing!
                When the marker_class row is included, it is encoded as integers (to prevent mixed dtype issues/warnings on reload)
                
                    >>> 0 = 'none', 1 = 'type', 2 = 'state'

                metadata columns (which have no marker_class) have this row filled with 'na'. 
                NOT USED IN COMBINATION WITH GROUPING!

            filename: (str, or None): 
                the name of the csv file to save the exported dataframe inside the self.data_table_dir folder. If None, no export occurs, and the data table is only returned. 

        Returns:
            (pandas DataFrame) -- the pandas dataframe representing the exported data. 

        Inputs/Outputs:
            Outputs: 
                If filename is provided (is not None), then exports the data table to self.data_table_dir/filename.csv
        '''
        if filename is None:
            output_path =  None
        else:
            output_path = "".join([self.data_table_dir, "/", str(filename), ".csv"])
        data = self.data.copy()
        data.obs = data.obs.reset_index()    ## cell index included as 'index' column --> useful if dropping / filtering cells out of the dataset
        ## anndata to pd.DataFrame:
        data_points = pd.DataFrame(data.X)
        data_points.columns = data.var.index.astype('str')
        if (include_marker_class_row is True) & (groupby_columns is None):
            data_points = data_points.T
            marker_class_dict = {'none' : 0, 'type' : 1, 'state' : 2, 'spatial_edt' : 3}     # so not mixed type on read
            data_points['marker_class'] = list(data.var['marker_class'])
            data_points['marker_class'] = data_points['marker_class'].replace(marker_class_dict)
            data_points = data_points.T

        data.obs.columns = data.obs.columns.astype('str')
        data_col_list = [i for i in data.obs.columns]
        for i in data_col_list:
            if (include_marker_class_row is True) & (groupby_columns is None):
                data_points[str(i)] = list(data.obs[str(i)]) + ["na"]
            else:
                data_points[str(i)] = list(data.obs[str(i)])
            data.obs[i] = data.obs[i].astype('str')

        if self._scaling == "%quantile":
            data_points['scaling'] = str(self._scaling) + str(self._quantile_choice)
        else:
            data_points['scaling'] = self._scaling
        if (include_marker_class_row is True) & (groupby_columns is None):
            data_points.loc[data_points.index[-1],'scaling'] = "na"
        
        # subset:
        if (subset_types is not None) and (subset_columns is not None):
            counter1 = 0
            for i,ii in zip(subset_columns, subset_types):
                counter2 = 0
                for j in ii:
                    data_slice = data_points[data_points[str(i)].astype('str') == str(j)]    ## subsets for
                    if counter2 == 0:
                        new_data = data_slice.copy()
                        counter2 = 1
                    else:
                        new_data = new_data.merge(data_slice, how = 'outer')
                if counter1 == 0 :
                    counter1 = 1
                    output_df = new_data.copy()
                else:
                    output_df = output_df.merge(new_data, how = 'inner')
            data_points = output_df
                    
        if groupby_columns is None:
            if output_path is not None:
                if self._in_gui:
                    try:
                        data_points.to_csv(str(output_path), index = False)
                    except Exception:
                        tk.messagebox.showwarning("Error writing to csv!")
                else:
                    data_points.to_csv(str(output_path), index = False)

            return data_points

        else:
            groupby_object = data_points.groupby(groupby_columns, observed = False)

            if statistic == 'mean':
                groupby_object = groupby_object.mean(numeric_only = True)
            if statistic =='median':
                groupby_object = groupby_object.median(numeric_only = True)
            if statistic =='sum':
                groupby_object = groupby_object.sum(numeric_only = True)
            if statistic =='std':
                groupby_object = groupby_object.std(numeric_only = True)
            if statistic =='count':
                groupby_object = groupby_object.count()
                groupby_object = pd.DataFrame(groupby_object[groupby_object.columns[0]])
                groupby_object.columns = ['count']

            groupby_object = groupby_object.reset_index()

            for i in data_col_list:
                if (i in groupby_object.columns.astype('str')) and (i not in groupby_columns):
                    groupby_object = groupby_object.drop(i, axis = 1)


            if output_path is not None:
                if self._in_gui:
                    try:
                        groupby_object.to_csv(str(output_path), index = False)
                    except Exception:
                        tk.messagebox.showwarning("Error writing to csv!")
                else:
                    groupby_object.to_csv(str(output_path), index = False)

            return groupby_object
        
    def export_DR(self, 
                  kind: str = "umap", 
                  filename: Union[str, None] = None,
                  ) -> tuple[pd.DataFrame, str]:
        ''' 
        Exports a dimensionality reduction embedding (PCA or UMAP)

        Args:
            kind (str): 
                one of -- "umap", "pca" -- the type of embedding to export

            filename (str or None): 
                the filename of the csv file to export to self.data_table_dir. 
                if None, no export occurs, only the dataframe is returned

        Returns:
            (pandas dataframe) this contains three columns, the dim1/2 of the embedding + the cell number as in self.data (needed as downsampling is typically used for DR)

        Inputs/Outputs:
            Outputs: 
                If filename is provided (is not None), then exports the UMAP/PCA table to self.data_table_dir/filename.csv
        '''
        if kind == "umap":
            to_export = pd.DataFrame(self.UMAP_embedding.obsm['X_umap'], columns = ["UMAP1","UMAP2"])
            to_export['cell number from original data'] = list(self.UMAP_embedding.obs['index'])
        elif kind == "pca":
            to_export = pd.DataFrame(self.PCA_embedding.obsm['X_umap'], columns = ["PC1","PC2"])
            to_export['cell number from original data'] = list(self.PCA_embedding.obs['index'])
        else:
            print("kind must == 'umap', or 'pca'!")
            return
        if filename is not None:
            to_export.to_csv(self.data_table_dir + "/" + filename + ".csv", index = False)
        return to_export
    
    def export_clustering(self,  
                          groupby_column: str = "metaclustering",
                          identifier: str = "", 
                          ) -> tuple[pd.DataFrame, str]:              
                                                            # *** sets up a spaceanova (https://github.com/sealx017/SpaceANOVA [GPL2])-compatible / derived data table which can be
                                                            # read in as a clustering or used for the Spatial Analysis
        '''
        Saves a clustering to self.clusterings_dir as a csv. ALWAYS exports to the disk

        These saved clustering files are used for both reloading a clustering later and for loading info into a Spatial analysis.
        The filename of a clustering is its (groupby_column + identifier).csv

        Args:
            groupby_column (str): 
                the title of the column in the self.data.obs that represents a particular cell type clustering to save.
                this string forms the first part of the filename of the csv saved to self.clusterings_dir
                For the sake of reloading, expected to be one of: 
                       
                    -- "classification", "leiden", "merging", "metaclustering", "clustering" --

                If groupby_column == "", then all expected groupby columns, as listed above,
                will be attempted to be added to the exported file.

            identifier (str): 
                a string that forms the second part of the filename of the csv saved to self.clusterings_dir

        Returns:
            (pandas dataframe): the pandas dataframe that is written to the csv file at the export path

            (str): The path to the exported csv file

        Inputs/Outputs:
            Inputs: 
                Attempts to read from directory above self.directory / regionprops --> looking for regionproperty data to export with the 
                clustering, which can be used in spatial analysis. 

            Outputs: 
                Writes the clustering data table to self.clusterings_dir/{groupby_column}{identifier}.csv
        '''
        if not os.path.exists(self.clusterings_dir):
            os.mkdir(self.clusterings_dir)
        ##### Sets up a table for spatial analysis
        table = pd.DataFrame()
        table['cellType'] = self.data.obs[groupby_column].astype('str').copy()
        table['sample_id'] = self.data.obs['sample_id'].copy()
        table['condition'] = self.data.obs['condition'].copy()
        table['patient_id'] = self.data.obs['patient_id'].copy()
        table['file_name'] = self.data.obs['file_name'].copy()
        
        ## loading spaceANOVA from clustering has been superseded by loading from the Analysis onbject itself, therefore extraneous columns are no longer needed
        '''
        try:
            regionprops_directory = self.directory[:self.directory.rfind("/")] + "/regionprops/"
            roi_areas = os.listdir(regionprops_directory)
            area = []
            for i in roi_areas:
                regionprops = pd.read_csv("".join([regionprops_directory,i])) 
                area = area + list(regionprops['area'])
            area = np.array(area)
            table['cell_areas'] = area
            X = []
            Y = []
            for i in roi_areas:
                temp_file = pd.read_csv("".join([self.directory[:-4], "/regionprops/", i]))
                tempX = temp_file['centroid-0']
                tempY = temp_file['centroid-1']
                X = X + list(tempX)
                Y = Y + list(tempY)
            table["x"] = X
            table["y"] = Y
        except Exception:
            print("Spatial data not saved -- This save will not be usable for spatial analysis" 
                   "(ignore if this is solution mode / not an imaging experiment)")
            ## Stil create the columns, so that they can be dropped later & be used to see if spatial data is available without creating errors
            table['cell_areas'] = 0
            table["x"] = 0
            table["y"] = 0
        '''

        table["type"] = groupby_column
        # percentages are now directly calculated from the groupings, not from saved percentages.
        '''
        percentages = self.data.obs.groupby(groupby_column, observed = False).count()["sample_id"] / len(self.data.obs)
        zip_dict = {}
        for i,ii in zip(percentages.index, percentages):
            zip_dict[str(i)] = ii
        table['percentages'] = table['cellType'].replace(zip_dict)
        '''

        for_sampling = pd.DataFrame(self.data.X)
        table['watermark1'] = for_sampling.sample(1, random_state = 1066)[0].values[0]
        table['watermark2'] = for_sampling.sample(1, random_state = 1776)[0].values[0]
        table.to_csv(self.clusterings_dir + f"/{groupby_column}{identifier}.csv", index = False)
        return table, self.clusterings_dir + f"/{groupby_column}{identifier}.csv"

    def export_clustering_classy_masks(self, clustering = "merging", identifier = ""):
        '''
        Intent of this function is to write a "classy mask" folder from an annotation

        Uses: visualization, mainly. Perhaps could be used in extending masks
        '''
        # Step 0: set up naming & directory
        analyses_folder = self.directory[:self.directory.rfind("/")]
        interim = analyses_folder[:analyses_folder.rfind("/")]
        classy_mask_folder = interim[:interim.rfind("/")] + "/classy_masks"
        if len(identifier) > 0:
            identifier = f"_{identifier}"
        name = f'{clustering}_{self.input_mask_folder[(self.input_mask_folder.rfind("/") + 1):]}{identifier}'
        destination_folder = classy_mask_folder + f"/{name}"
        if not os.path.exists(destination_folder):
            os.mkdir(destination_folder)
        internal_folder = f'{destination_folder}/{name}'   ## this holds the .tiff files themselves
        if not os.path.exists(internal_folder):
            os.mkdir(internal_folder)

        # Step 1: use back-up data & recover labels (either 'none' if filtered/dropped before clustering, or clustering labels)
        if self.back_up_data is not None:
            data = self.back_up_data.obs.copy()
            unique_sample_ids = data['sample_id'].unique()
            data[clustering] = 'none'
            data.index = data.index.astype('str')
            data.loc[self.data.obs.index, clustering] = list(self.data.obs[clustering].astype('str'))
            data = data[[clustering,"file_name"]].copy()
        else:
            unique_sample_ids = self.data.obs['sample_id'].unique()
            data = self.data.obs[[clustering,"file_name"]].copy()
        
        # Step 2: Assign numbers to the labels, including 'none'
        unique_labels = data[clustering].unique()
        zip_dict = {}
        zip_dict2 = {}
        for i,ii in zip(unique_sample_ids, unique_labels):
            zip_dict[ii] = int(i) + 1   # 0 is a special number in images!
            zip_dict2[ii] = str(int(i) + 1)
        data['label'] = data[clustering].replace(zip_dict)
        data.drop("file_name", axis = 1).to_csv(f'{destination_folder}/{name}.csv', index = False)
        simple_df = pd.DataFrame()
        simple_df['biological_label'] = list(unique_labels)
        simple_df['class_number'] = simple_df.replace(zip_dict2)
        simple_df.to_csv(f'{destination_folder}/biological_labels.csv', index = False)

        # Step 3: Iterate through masks for this analysis, creating classy mask .tiffs
                # this iteration step would follow the same / similar methods as the classy mask functions that already exist
        for i in sorted(os.listdir(self.input_mask_folder)):
            mask = tf.imread(f"{self.input_mask_folder}/{i}").astype('int32')
            as_fcs = i[:i.rfind(".")] + ".fcs"
            temp_labels = list(data[data["file_name"] == as_fcs]['label'])
            regionprops = skimage.measure.regionprops(mask)
            if len(regionprops) != len(temp_labels):
                print(f"Error! Number of labels {len(temp_labels)} and number of masks {len(regionprops)} do not match for ROI = {i} in {self.input_mask_folder}! \n"
                "Aborting classy masking")     
                            ##>>## complete error message / in gui version (?), etc.
                return None
            for j,jj in zip(skimage.measure.regionprops(mask), list(data['label'])):
                box = j.bbox
                slicer = j.image
                mask[box[0]:box[2],box[1]:box[3]][slicer] = int(jj)
            tf.imwrite(f"{internal_folder}/{i}", mask)
        return data

    def load_clustering(self, path: Union[str, Path]) -> None:
        '''
        Looks in the self.clusterings_dir for a filename that matches [choice] and loads it at a clustering

        Expects to find a csv file with the same format as exported by self.export_clustering. Attempts to confirm that the data is unchanged
        from when the clustering was originally exported. This includes dropped data, batch correction & scaling -- so be sure
        that these are the same when loading a clustering. 

        Args:
            choice (str): 
                the filename for the csv to be loaded, which should exist in the self.clusterings_dir folder

        Returns:
            None (modifies self)

        Inputs/Outputs:
            Inputs: 
                Reads from path, presuming path is the full filename of a .csv file created by self.export_clustering()
            
        '''
        path = str(path)
        if path.rfind("/") == -1:
            path = self.clusterings_dir + "/" + path
        if not os.path.exists(path):
            print("This clustering does not exist!")
            return
        clustering_info = pd.read_csv(f'{path}')
        column_name = clustering_info["type"].values[0]
        for_sampling = pd.DataFrame(self.data.X)
        watermark1 = float(for_sampling.sample(1, random_state = 1066)[0].values[0])
        watermark2 = float(for_sampling.sample(1, random_state = 1776)[0].values[0])
        ## Extensive checks before loading the clustering:
        if len(self.data.obs) != len(clustering_info):
            if self._in_gui:
                warning_window("Length of the saved clustering and the length of the current single cell experiment do not match! \n\n Cancelling load")
            else:
                print("Length of the saved clustering and the length of the current single cell experiment do not match! \n\n Cancelling load")
            return
        if (np.array(self.data.obs['sample_id'].astype('str')) != np.array(clustering_info['sample_id'].astype('str'))).sum() > 0:
            if self._in_gui:
                warning_window("Warning! Sample_ids do not match between saved clustering and current experiment! \n\n Cancelling load")
            else:
                print("Sample_ids do not match between saved clustering and current experiment! \n\n Cancelling load")
            return
        if ((np.round(watermark1, 4) != np.round(clustering_info['watermark1'][0],4)) 
            or (np.round(watermark2,4) != np.round(clustering_info['watermark2'][0], 4))):
            if self._in_gui:
                warning_window("Caution: Has the data in the experiment changed from when the clustering was saved? Data watermarks did not match! \n"
                               "Data transformations that could cause this if they were not re-done to replicate: batch correction, scaling \n"
                               "Proceeding with clustering load.")
            else:
                print("Caution: Has the data in the experiment changed from when the clustering was saved? Data watermarks did not match! \n"
                      "Data transformations that could cause this if they were not re-done to replicate: batch correction, scaling \n"
                      "Proceeding with clustering load.")
        if (np.array(self.data.obs['condition'].astype('str')) != np.array(clustering_info['condition'].astype('str'))).sum() > 0:
            if self._in_gui:
                warning_window("Caution: Conditions do not match between saved clustering and current experiment! Be sure of any changes \n"
                               "Proceeding with clustering load.")
            else:
                print("Caution: Conditions do not match between saved clustering and current experiment! Be sure of any changes \n"
                     "Proceeding with clustering load.")
        if (np.array(self.data.obs['patient_id'].astype('str')) != np.array(clustering_info['patient_id'].astype('str'))).sum() > 0:
            if self._in_gui:
                warning_window("Caution: 'Patient_ids'  do not match between saved clustering and current experiment! Be sure of any changes \n"
                               "Proceeding with clustering load.")
            else:
                print("Caution: 'Patient_ids'  do not match between saved clustering and current experiment! Be sure of any changes \n"
                        "Proceeding with clustering load.")
        self.data.obs[column_name] = list(clustering_info['cellType'])    #### assumes no changes in the index
        ###>>>
        if self.UMAP_embedding is not None:
            try: 
                self.UMAP_embedding.obs = self.UMAP_embedding.obs.drop(column_name, axis = 1)   
                                                                    ## if present, these columns should be dropped
            except KeyError:
                pass
            merge_df = pd.DataFrame(self.data.obs[column_name].astype('category').copy())
            merge_df['true_index'] = merge_df.index.astype('int').copy()
            self.UMAP_embedding.obs['true_index'] = self.UMAP_embedding.obs['true_index'].astype('int')
            self.UMAP_embedding.obs = pd.merge(self.UMAP_embedding.obs, merge_df, on = "true_index")
        if self.PCA_embedding is not None:
            try: 
                self.PCA_embedding.obs = self.PCA_embedding.obs.drop(column_name, axis = 1)   
                                                                    ## if present, these columns should be dropped
            except KeyError:
                pass
            merge_df = pd.DataFrame(self.data.obs[column_name].astype('category').copy())
            merge_df['true_index'] = merge_df.index.astype('int').copy()
            self.PCA_embedding.obs['true_index'] = self.PCA_embedding.obs['true_index'].astype('int')
            self.PCA_embedding.obs = pd.merge(self.PCA_embedding.obs, merge_df, on = "true_index")
        return

    def load_classification(self, 
                            cell_classifications: Union[pd.DataFrame, Path, str], 
                            column: str = "labels", 
                            ) -> None:
        '''Load a cell classification from the output data table of classy mask generation using a pixel classifier.

        Args:
            cell_classifications (pandas dataframe, or string / Path): 
                either a pandas dataframe, or the path to a csv file from which a pandas dataframe will be read. The dataframe must contain one of 
                two columns: "label" and/or "classification" with cell type labels and be equal in length with self.data.obs

            column (str): 
                "classification" load attempt to load pixel classification numbers, "labels" to try to load biological labels first


        Returns:
            None  (modifies self)

        Inputs/Outputs:
            Inputs: 
                if cell_classifications is not a pandas dataframe, attempts to read a .csv from the path specified by cell_classifications
        '''
        if not isinstance(cell_classifications, pd.DataFrame):
            cell_classes_file_path = str(cell_classifications)
            cell_classes = pd.read_csv(cell_classes_file_path)

        if column == "labels":   ## if labels are not in the classification df, load the numbers as before
            try:
                cell_classes['labels']
            except KeyError:
                column = 'classification'

        cell_classes.index = cell_classes.reset_index().index
        if len(list(cell_classes[column])) == len(self.data.obs.index):
            self.data.obs['classification'] = list(cell_classes[column])
            if self.UMAP_embedding is not None:
                try: 
                    self.UMAP_embedding.obs = self.UMAP_embedding.obs.drop('classification', axis = 1)   
                                                                        ## if present, these columns should be dropped
                except KeyError:
                    pass
                merge_df = pd.DataFrame(self.data.obs['classification'].astype('category').copy())
                merge_df['true_index'] = merge_df.index.astype('int').copy()
                self.UMAP_embedding.obs['true_index'] = self.UMAP_embedding.obs['true_index'].astype('int')
                self.UMAP_embedding.obs = pd.merge(self.UMAP_embedding.obs, merge_df, on = "true_index")

            if self.PCA_embedding is not None:
                try: 
                    self.PCA_embedding.obs = self.PCA_embedding.obs.drop('classification', axis = 1)   
                                                                        ## if present, these columns should be dropped
                except KeyError:
                    pass
                merge_df = pd.DataFrame(self.data.obs['classification'].astype('category').copy())
                merge_df['true_index'] = merge_df.index.astype('int').copy()
                self.PCA_embedding.obs['true_index'] = self.PCA_embedding.obs['true_index'].astype('int')
                self.PCA_embedding.obs = pd.merge(self.PCA_embedding.obs, merge_df, on = "true_index")
        else:
            print("Number of Classified masks and the number of cells in the loaded dataset do not match!" +
                   "\nDid you not generate the classy masks from the same underlying masks that you used to do region measurements?"+
                   "\nIf you have dropped / filtered cells from the dataset, please load this cell classification BEFORE dropping cells.")
            return
