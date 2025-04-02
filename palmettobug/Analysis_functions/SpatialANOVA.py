'''
This module handles the back-end of the spatial analysis functions of PalmettoBUG (spaceANOVA), which are used in the fifth & final tab
of the GUI. 

The SpatialAnalysis Class and some of the functions in this file are available in the public (non-GUI) API of PalmettoBUG.


While this project is licensed under GPL3 license, substantial portions of this script are derived (by translation) of two R packages

spatstat (https://github.com/spatstat), GPL >=2 license
spaceanova (https://github.com/sealx017/SpaceANOVA), GPL2 license, but the code of this script was made in collaboration with
the author, Souvik Seal, at the Medical University of South Carolina who authorised this translation's release as GPL on the date 9 / 10 / 2024

While the entire concept of this code owes itself to the spaceanova package, it is hard to pinpoint specific functions that derived from that 
package as much of the implementation details are rather different than the original in many places while at the same time many Key concepts 
do carry over including:

    the type of output plots (heatmaps, K / L / g tracings with f-values displayed in parallel), 

    the type of inputs (permutation correction, fixed_r, etc.), 

    certain restrictions (like a minimum number of cells per image [10] required for a calculation to proceed), 

    and the fundamental caculations (K / L / g followed by functional ANOVA).

Where possible, functions with substantial portion clearly derived from spatstat are marked with::

     # *** deriv_spatstat

The entire SpatialAnalysis class can be considered to derive from the spaceanova package
'''

import os
from typing import Union
from pathlib import Path 
# import copy

import numpy as np
import pandas as pd
import skfda
from skfda.inference.anova import oneway_anova
import scipy
from scipy.spatial.distance import cdist
from scipy.interpolate import make_smoothing_spline
import matplotlib.pyplot as plt
import seaborn as sns
import seaborn.objects as so

from .._vendor import sigfig

__all__ = []

class SpatialANOVA():
    '''
    The primary coordinating class for the spatial analysis options. The __init__ method for this class does nothing, separating the 
    creation of this class from needing to set it up with data. 

    Attributes:
        output_dir: the upper-levelk folder where the outputs of the spatial analysis will be written. Will contain two subfolders:
                -- /cell_maps & /Functional_plots, where the respective cell map and functional plot PNG files are saved.
                -- statistics dataframes and their matching heatmaps are saved in self.output_dir itself
        
        max / step / fixed_r: these are integers and a range object, where fixed_r = range(0, max, step). Determines at what distances
                calculations are performed

        condition1 / condition2: these are strings that denote which conditions are going to be compared. If both are None, will do 
                multi-comparison of all available condition groups

        data_table / areas / filenames: pandas dataframes/series from the loaded data. data_table contains the main data, areas / filenames 
                contain information used for cell map plotting (areas used for size of dots, filenames for subsetting data & plot titles.). 

    '''
    def __init__(self):
        self.max = None
        self.step = 1
        self.fixed_r = None
        self.condition1 = None
        self.condition2 = None
        self.threshold = 10

    def init_data(self, 
                  space_anova_table: pd.DataFrame, 
                  output_directory: str, 
                  plot_cell_maps: bool = True,
                  ) -> None:
        '''
        Args:
            space_anova_table (pandas dataframe): this has a particular format / expected columns:
                    rows >>> each row represents a cell event in the dataset. 
                    columns === 'x' >>> this a column containing the x-coordinates of the centroid of the cell in question
                            === 'y' >>> the y-coordinates of the centroid
                            === 'condition' >>> the experimental condition that the cell is from
                            === ' celltype' >>> the cell type (ex: T cell, astrocyte, etc.)
                            === 'sample_id' >>> a column of integers identifying the different images the data is from
                            === 'patient_id' >>> a column of an additional category (such as batch or patient ID) to group images
                                        'patient_id' MUST be in the dataframe, even if it is an empty column .
                            (if plot_cell_maps is True ----- these columns are only needed by the self.plot_cell_maps method):
                            === 'cell_areas' >>> the areas of the cell regions in the dataset (As pixels)
                            === 'file_name' >>> the names of the original image files that the data is from

            output_directory (string or Path): The path to a folder where the outputs of spatial analysis will be placed
                    if this folder does not already exist, will attempt to create it.

            plot_cell_maps (boolean): If True, will expect to cell_areas & file_name columns in the space_anova_table   
                    (may remove -- seems unneeded anymore)

        '''
        self.exp = None
        if plot_cell_maps is True:
            self.data_table = space_anova_table.drop(['cell_areas','file_name'], axis = 1)
            self.areas = space_anova_table['cell_areas'].astype('float')
            self.filenames = space_anova_table['file_name']
        else:
            self.data_table = space_anova_table
        self.data_table['x'] = self.data_table['x'].astype('float')
        self.data_table['y'] = self.data_table['y'].astype('float')
        self.data_table['condition'] = self.data_table['condition'].astype('str')
        self.data_table['cellType'] = self.data_table['cellType'].astype('str')
        self.data_table['sample_id'] = self.data_table['sample_id'].astype('str')
        self.data_table['patient_id'] = self.data_table['patient_id'].astype('str')
        output_directory = str(output_directory)
        self.output_dir = output_directory
        if not os.path.exists(output_directory):
            os.mkdir(output_directory)
        if not os.path.exists(output_directory + "/cell_maps"):
            os.mkdir(output_directory + "/cell_maps")
        if not os.path.exists(output_directory + "/Functional_plots"):
            os.mkdir(output_directory + "/Functional_plots")
    
    def init_analysis(self, analysis, output_directory, cellType_key = None):
        '''
        Alternative way of loading Spatial data, from the main anndata object of the Analysis class, instead of from an exported table / csv.

        Advantages: 
            can load new spatial analysis quickly without needing to save / reload a csv file
        Disadvantages:
            Reloading the same spatial analysis in a entirely different session more complicated

        '''
        self.exp = analysis
        try:
            self.areas = self.exp.data.uns['areas']    ## will need to add Analysis.data.uns['areas'] ... 
            self.filenames = self.exp.data.obs['file_name']
        except Exception:
            print("areas not found in anndata -- plotting cell maps will not be available")
        self.cellType_key = cellType_key
        self.data_table = None

        output_directory = str(output_directory)
        self.output_dir = output_directory
        if not os.path.exists(output_directory):
            os.mkdir(output_directory)
        if not os.path.exists(output_directory + "/cell_maps"):
            os.mkdir(output_directory + "/cell_maps")
        if not os.path.exists(output_directory + "/Functional_plots"):
            os.mkdir(output_directory + "/Functional_plots")

    def _retrieve_data_table(self, for_cell_maps = False):
        ''''''
        if self.exp is None:     ### we've loaded from a pandas dataframe, not from an anndata object
            pass
        else:
            if self.exp.back_up_data is not None:
                self.filenames = self.exp.back_up_data.obs['file_name']
                self.data_table = pd.DataFrame()
                self.data_table['x'] = self.exp.back_up_data.obsm['spatial'][:,0]
                self.data_table['y'] = self.exp.back_up_data.obsm['spatial'][:,1]
                self.data_table['condition'] = list(self.exp.back_up_data.obs['condition'].astype('str'))
                self.data_table['sample_id']  = list(self.exp.back_up_data.obs['sample_id'].astype('str'))
                self.data_table['patient_id'] = list(self.exp.back_up_data.obs['patient_id'].astype('str'))
                self.data_table['cellType'] = 'dropped'
                self.data_table.index = self.data_table.index.astype('str')
                self.data_table.loc[self.exp.data.obs.index,['cellType']] = list(self.exp.data.obs[self.cellType_key].astype('str'))
            else:
                self.data_table = pd.DataFrame()
                self.data_table['x'] = self.exp.data.obsm['spatial'][:,0]
                self.data_table['y'] = self.exp.data.obsm['spatial'][:,1]
                self.data_table['condition'] = list(self.exp.data.obs['condition'].astype('str'))
                self.data_table['cellType'] = list(self.exp.data.obs[self.cellType_key].astype('str'))
                self.data_table['sample_id']  = list(self.exp.data.obs['sample_id'].astype('str'))
                self.data_table['patient_id'] = list(self.exp.data.obs['patient_id'].astype('str'))
        return self.data_table

    def set_conditions(self, 
                       condition1: str, 
                       condition2: str,
                       ) -> None: 
        '''
        Select the two conditions to be compared in the analysis
        '''
        self.condition1 = condition1
        self.condition2 = condition2

    def set_fixed_r(self, 
                    min: int = 0,
                    max: int = 100, 
                    step: int = 1,
                    ) -> range:
        '''
        Select the radii (in pixels) to be examined. The starting (minimum) radii is always 0 
        '''
        self.fixed_r = range(min, max + step, step)
        self.min = min
        self.step = step
        self.max = max
        return self.fixed_r

    def _drop_data(self, 
                  to_drop: Union[str, int],
                  column: Union[str, int], 
                  ) -> None:
        ''' 
        (deprecated)
        A simple function to help drop unwanted images / types / conditions from the data table (must be called BEFORE self._ingest_data / self.do_spatial_analysis) 

        WARNING: only works if the data loaded into this class is from a pandas dataframe. If loaded from an anndata object, you must edit that anndata object directly
        This is because the usual anndata object that can be loaded into this is the .data attribute of a palmettobug Analysis class, which should be edited from the
        Analysis class and not from here. 

        '''
        type_of_inupt = type(to_drop)
        indexer = self.data_table[column].astype(type_of_inupt) != to_drop
        self.data_table = self.data_table[indexer]
        self.areas = self.areas[indexer]
         
    def _ingest_data(self, space_anova_table) -> tuple[list[pd.DataFrame],dict]:
        '''
        This function begins the data processing, and outputs a couple useful intermediates (however, more of a helper function):

        Returns:
            self._split_by_image:  a list of pd.DataFrames, one DataFrame for each sample_id in the dataset. In the order of 
                    space_anova_table['sample_id'].unique()    
                    [which should be / is assumed to be ascending integer order, the same as the sample_ids]

            self._group_img_dict: a dictionary that maps the sample_id's to their associated conditions. This allows the 'condition' column to be 
                    dropped in each dataframe of the _split_by_image object, while still allowing easy regeneration of each image's 
                    original grouping down the line. 

        '''
        condition1 = self.condition1
        condition2 = self.condition2            
        if not ((condition1 is None) and (condition2 is None)): 
            slice1 = space_anova_table['condition'] == condition1
            slice2 = space_anova_table['condition'] == condition2
            final_slicer = (slice1 + slice2)
            space_anova_table = space_anova_table[final_slicer]
        
        self._split_by_image = []
        for i in space_anova_table['sample_id'].unique():
            self._split_by_image.append(space_anova_table[space_anova_table['sample_id'] == i].drop(['condition','patient_id'], axis = 1))
        
        for_group_img_dict = space_anova_table.drop(['patient_id','x','y','cellType'], axis = 1).drop_duplicates()
        self._group_img_dict = {}
        for i,ii in zip(for_group_img_dict['condition'], for_group_img_dict['sample_id']):
            self._group_img_dict[ii] = i
        return self._split_by_image, self._group_img_dict

    def do_spatial_analysis(self, 
                            condition1: Union[str, None] = None, 
                            condition2: Union[str, None] = None,
                            cellType_key: Union[str, None] = None,
                            max: int = None, 
                            min: int = None,
                            step: int = None, 
                            threshold: int = 10,
                            permutations: int = 0, 
                            seed: int = 42, 
                            center_on_zero: bool = False, 
                            silence_zero_warnings: bool = True,
                            ) -> tuple[list[str], list[str], dict[str,pd.DataFrame]]:
        '''
        This function takes does all of the key analysis steps from the Data table, two conditions, & radii range object.

        Args:
            condition1, condition2 (string or None, default = None): if None, use the conditions inputted by self.set_conditions, 
                    otherwise these should be the labels of the two experimental conditions you intend to compare in the data. 

            min, max, step (integer or None): If one or both are None (default), will use the radii selected by self.set_fixed_r. 
                    Otherwise, if both are not None, then the min / max / step will be used as in the self.set_fixed_r 
                    method

            permutations (integer >= 0): whether to perform permutation correction (if > 0) or not (= 0), and if so how many permutations 
                    to perform to calculate the correction.

            seed (integer): random seed for performing all SpaceANOVA steps (permutations, bootstrapping, etc.)

            center_on_zero (boolean): whether to center the result of Ripley's g on 0 (True) or on 1 (False). Without permutation correction, 
                Ripley's g is naturally centered on 1, but can be adjusted to center on 0. In this case, I'm loosely using the 
                term "centered" to mean that the theoretical value of the statistic, such that values above the center indicate 
                greater between cell types than expected by chance and values below mean the cell types are less spatially 
                associated than expected from chance.
                This is the difference between the output of Ripley's K, which either:
                    if permutation correciton is NOT performed:
                        K = Kcalc (center = 1)
                            --or--

                        K = Kcalc - Ktheo (center = 0)

                    if permutation correction IS performed:
                        K = Kcalc - Kperm (center = 0) 
                                    --or--

                        K = Kcalc - Kperm + Ktheo (center = 1),

                where Ktheo = pi*(r**2) for each radii distance, and with Ripley's g later being calculated from this output.

            silence_zero_warnings (boolean): if True, silences a pair of particularly common division-by-zero warnings (recommended), if False
                    those warnings will be shown

        Returns:
            self._comparison_list:  a list of strings. It contains every pairwise comparison between cellTypes, in the format 
                    "cellType1___cellType2". These comparison correspond to the keys of the self._comparison_dictionary object. 
                                    
            self._comparison_dictionary: A dictionary of dictionaries with three pd.DataFrames inside each sub-dictionary. 
                    Format to access the dfs: self._comparison_dictionary["cellType1_cellType2"]["statistic"]
                    EXAMPLE: self._comparison_dictionary["astrocyte_neuron"]["K"] --> this will access the Ripley's K 
                    dataframe for the astrocyte-to-neuron spatial comparison. 
                    The dataframes contain columns for the calculated statistic (K, L, or g), the theoretical value, 
                    the radii value the statistic was determined at, and the condition/sample_id it was calculated for. These are 
                    the same data frames from the self._do_all_K_L_g() function.

        '''
        if condition1 is None:
            condition1 = self.condition1
        else:
            self.condition1 = condition1
        if condition2 is None:
            condition2 = self.condition2
        else:
            self.condition2 = condition2
        if cellType_key is not None:
            self.cellType_key = cellType_key
        if (max is not None) and (step is not None) and (min is not None):
            self.set_fixed_r(min = min, max = max, step = step)
        elif self.fixed_r is None:
            self.set_fixed_r()

        space_anova_table = self._retrieve_data_table()

        self.threshold = threshold
        self.seed = seed

        self._ingest_data(space_anova_table)
        self._return_comparison_lists()
        self._comparison_dictionary = {}
        if silence_zero_warnings is True:
            import warnings
            warnings.filterwarnings("ignore", message = "divide by zero encountered in divide") 
                                            ########## zero divisions are very common (strictly necessary?) in the vectorised calculation steps
                                            ## The program is meant to properly handle these, so I don't want the console spammed with warnings
            warnings.filterwarnings("ignore", message = "invalid value encountered in divide")

        for i in self._all_comparison_list:
            conditions = i.split("___")
            type1 = conditions[0]
            type2 = conditions[1]
            if (type1 != "dropped") and (type2 != "dropped"):
                all_g, all_K, all_L = self._do_all_K_L_g(type1 = type1, type2 = type2, permutations = permutations, 
                                                        perm_state = seed, center_on_zero = center_on_zero)
                self._comparison_dictionary[i] = {"K":all_K, "L":all_L, "g":all_g}
        if silence_zero_warnings is True:
            warnings.filterwarnings("default", message = "divide by zero encountered in divide")  ## undo prior warnings modifications
            warnings.filterwarnings("default", message = "invalid value encountered in divide")                    
        return self._comparison_list, self._all_comparison_list, self._comparison_dictionary
    
    def _return_comparison_lists(self):
        ''''''
        all_cell_types = []
        bad_cell_types = []           ## this will collect the cell types that are valid to make comparisons with (as in, are present in > 1 condition)
        if self.exp is not None:
            obs = self.exp.data.obs.copy()
            cellType_key = self.cellType_key
        else:
            obs = self.data_table.copy()
            cellType_key = "cellType"
        for i in obs[cellType_key].unique():
            all_cell_types.append(str(i))
            cell_type_copy = obs[obs[cellType_key] == i]
            compare_to_threshold = cell_type_copy.groupby(['condition','sample_id'], observed = True).count()[cellType_key].reset_index()
            for k in compare_to_threshold['condition'].unique():
                compare_to_threshold_copy = compare_to_threshold[compare_to_threshold['condition'] == k]
                if compare_to_threshold_copy[cellType_key].max() < self.threshold:
                    bad_cell_types.append(str(i))
                    print(f"The celltype {str(i)} is only present in one condition -- ANOVAs and F-statistics will not be available for that celltype!")
                    break   
        bad_cell_types.append('dropped')
        self.good_cell_types = [i for i in all_cell_types if i not in bad_cell_types]
        self._comparison_list = []
        all_types = np.array(self.good_cell_types)
        all_types = all_types[:,np.newaxis]
        tiled = np.tile(all_types,len(all_types))
        tiled_T = tiled.T
        for i,ii in zip(tiled.flatten(), tiled_T.flatten()):
            comparison = "".join ([str(i),"___",str(ii)])
            self._comparison_list.append(comparison)

        self._all_comparison_list = []
        all_types = np.array(all_cell_types)
        all_types = all_types[:,np.newaxis]
        tiled = np.tile(all_types,len(all_types))
        tiled_T = tiled.T
        for i,ii in zip(tiled.flatten(), tiled_T.flatten()):
            comparison = "".join ([str(i),"___",str(ii)])
            self._all_comparison_list.append(comparison)     ## plots of ripley's stats are still possible for the one condition
        return self._comparison_list, self._all_comparison_list
        
    def _do_all_K_L_g(self, 
                      type1, 
                      type2, 
                      permutations: int = 0, 
                      perm_state: int = None, 
                      center_on_zero: bool = False,
                      ) -> tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
        '''
        This may end being more of a helper function for do_spatial_analysis(), but it can remain in the class.
        It coordinates / performs the core statistical analysis: calculating Ripley's K, L, and g for a given cellType pair (type1 vs type2). 

        Args: 
            type1 / type2: the celltypes to compare
    
            >>> see self.do_spatial_analysis for details of other arguments.

        Returns:
            self._all_g / self._all_K / self._all_L: pandas dataframes with the calculated Ripley's g / K / L function at each radii for each 
                    imagID / Group

        '''
        if perm_state is None:
            perm_state = self.seed
        split_point_pattern = self._split_by_image
        group_img_dict = self._group_img_dict
        fixed_r = self.fixed_r
        if fixed_r is None:        
            print("You must provide a range object of the radii to check into this method's fixed_r argument, or first provide that object using the call the set_fixed_r() method!")
            return
            
        self._all_g = pd.DataFrame()
        self._all_K = pd.DataFrame()
        self._all_L = pd.DataFrame()
        for ii,i in zip(group_img_dict,range(0,len(split_point_pattern))):
            K_df, L_df, g_df = do_K_L_g(split_point_pattern[i], 
                                        type_column = 'cellType', 
                                        type1 = type1, 
                                        type2 = type2, 
                                        fixed_r = fixed_r,
                                        threshold = self.threshold,
                                        image_name = ii, 
                                        permutations = permutations, 
                                        perm_state = perm_state, 
                                        center_on_zero = center_on_zero) 
            if K_df['K'].sum() != 0: ### if sum() == 0, this means a failure of the algorithm / insufficient cells in the image:
                g_df["condition"] = group_img_dict[ii]
                g_df['image'] = i
                self._all_g = pd.concat([self._all_g, g_df], axis = 0)
                K_df["condition"] = group_img_dict[ii]
                K_df['image'] = i
                self._all_K = pd.concat([self._all_K, K_df], axis = 0)
                L_df["condition"] = group_img_dict[ii]
                L_df['image'] = i
                self._all_L = pd.concat([self._all_L, L_df], axis = 0)

        self.type1 = type1
        self.type2 = type2
        return self._all_g, self._all_K, self._all_L

    def _do_single_radius_ANOVA(self, 
                                distance_of_interest: int, 
                                comparison: str, 
                                stat: str = 'g',
                                ) -> np.ndarray[float]:
        '''
        At a given distance of interest (an integer that must be in the radii of the previously performed analysis), 
        perform an ANOVA test between the two conditions.

        Outputs a tuple with the format (f statistic, pvalue)

        '''
        comparison_dictionary = self._comparison_dictionary
        condition1 = self.condition1
        condition2 = self.condition2
            
        g_df = comparison_dictionary[comparison][stat]
        if len(g_df) == 0:
            print("This comparison has no data -- \n" 
                  "It might be that these two cells types are never present together in the same image above the threshold!"
                  "\n Exiting")
            return None, None
        only_at_dist = g_df[g_df['radii'] == distance_of_interest]
        if (condition1 is None) and (condition2 is None):
            condition_list = []
            for i in only_at_dist['condition'].unique():
                condition_list.append(only_at_dist[only_at_dist['condition'] == i][stat])
            stats = scipy.stats.f_oneway(*condition_list)
        else:
            stats = scipy.stats.f_oneway(only_at_dist[only_at_dist['condition'] == condition1][stat],
                                        only_at_dist[only_at_dist['condition'] == condition2][stat])
        return stats

    def do_all_radii_ANOVAs(self, 
                            comparison: str, 
                            stat: str = 'g',
                            ) -> tuple[list[float, list[float],np.ndarray[float]]]:
        '''
        This function performs the do_single_radii_anova() method at every available radii in the analysis, exporting the f statistic, p value, 
        and adjusted p value for every radii in a list (order = the ascending order of the radii). 
        
        This, I think, will only be used for plotting f_values, although *possibly* could be used for saving / exporting p_values for each 
        distance. 

        '''
        fixed_r = self.fixed_r    
        f_list = []
        p_list = []
        for i in fixed_r:
            if i == 0:
                f_stat = 0
                p_value = 0
            else:
                f_stat, p_value = self._do_single_radius_ANOVA(distance_of_interest = i, comparison = comparison, stat = stat)
            if f_stat is None:    ## this means the comparison has no data!
                return None, None, None
            f_list.append(float(f_stat))
            p_list.append(float(p_value))

        p_list = np.nan_to_num(np.array(p_list), nan = 1)

        p_list_adj = scipy.stats.false_discovery_control(p_list, method = 'bh')
        return f_list, p_list, p_list_adj

    def do_all_functional_ANOVAs(self, 
                                 stat: str = 'g', 
                                 seed: Union[int, None] = None,
                                 ) -> tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
        '''
        This implements a functional ANOVA comparison for every cellType vs. cellType pair.

        Args:
            stat (string -- 'g', 'L', 'K'): which Ripley's statistic to calculate

            seed (integer): the random seed for the ANOVA function, which uses sampling / bootstrapping. 

        Returns:
            three pandas dataframes -- these each form a matrix of the types vs. types (index = columns = all unique types in order), containing 
                    the adjusted p values, the anova statistics, and the unadjusted p values.
                    They can almost immediately be plotted as heatmaps of the p values (with a -log transformation first)

        '''
        self.stat_error = False
        if seed is None:
            seed = self.seed
        comparison_list = self._comparison_list
        comparison_dictionary = self._comparison_dictionary
        condition1 = self.condition1
        condition2 = self.condition2
        step = self.step        
        max = self.max
        min = self.min
            
        side_length = int(np.sqrt(len(comparison_list)))
        p_list = []
        stat_list = []
        new_comparison_list = []
        for i in comparison_list:
            all_g = comparison_dictionary[i][stat]
            if len(all_g) == 0:
                self.stat_error = True
                print(f"This comparison, {i}, has no data -- \n" 
                      "It might be that these two cells types are never present together in the same image above the threshold!"
                      "\n setting pvalue = 1, and statistic = 0")
                statistic, p_value = (0,1)
            else:
                statistic, p_value = do_functional_ANOVA(all_g, condition1, condition2, 
                                                        random_state = seed, min = min, 
                                                        max = max, step = step, stat = stat, comparison = i) 
                        # The underlying functional ANOVA implementation uses permutations, 
                        # so a random seed is necessary (running with different seeds will produce slightly 
                        # different output values).
            p_list.append(p_value)
            stat_list.append(statistic)
            new_comparison_list.append(i.split("___"))


        '''
        to_adjust_list = []
        unique_comparisons = []
        all_comparisons = []
        comparison_conversion_dict = {}
        for i,ii in zip(p_list, new_comparison_list):
            presort = "".join(copy.copy(ii))
            all_comparisons.append("".join(presort))
            ii.sort()
            comparison_conversion_dict["".join(presort)] = "".join(ii)
            if "".join(ii) not in unique_comparisons: 
                unique_comparisons.append("".join(ii))
                to_adjust_list.append(i)
            #else:
            #    to_adjust_list[] = (to_adjust_list[] + i) / 2     ## average p-values for symmetric comparisons?
        '''

        ## uncertain how to handle FDR, since comparison are symetric, but are close to symmetric  (do combined comparison in all_g above? average p_values?)
        p_adj_list = scipy.stats.false_discovery_control(np.nan_to_num(np.array(p_list), nan = 1.0) + 1e-25, method = 'bh')    ##  to_adjust_list
        
        '''
        map_dict = {}
        for i,ii in zip(unique_comparisons, p_adj_list):
            map_dict[i] = ii

        p_adj_array = np.array(p_list)
        for i,ii in enumerate(all_comparisons):
            p_adj_array[i] = map_dict[comparison_conversion_dict[ii]]
        p_adj_list = p_adj_array 
        ''' 

        begin = 0
        list_of_columns = []
        list_of_unadj_columns = []
        list_of_col_stat = []
        for i in range(side_length,len(comparison_list) + side_length, side_length):
            column = [sigfig.round(i,4, warn = False) for i in p_adj_list[begin:i]]
            list_of_columns.append(column)
            column1 = [sigfig.round(i,4, warn = False) for i in  p_list[begin:i]]
            list_of_unadj_columns.append(column1)
            column2 = [sigfig.round(i,4, warn = False) for i in  stat_list[begin:i]]
            list_of_col_stat.append(column2)
            begin = i
                
        numpy_array_p = np.array(list_of_columns).T
        numpy_array_stat = np.array(list_of_col_stat).T
        numpy_array_p_unadj = np.array(list_of_unadj_columns).T
        
        pd_columns = [i.split("___")[0] for i in comparison_list]
        pd_columns = pd.Series(pd_columns).unique()
    
        self.p = pd.DataFrame(numpy_array_p, columns = pd_columns)
        self.p.index = pd_columns
        self.stat = pd.DataFrame(numpy_array_stat, columns = pd_columns)
        self.stat.index = pd_columns
        self.unadj = pd.DataFrame(numpy_array_p_unadj, columns = pd_columns, index = pd_columns)
        self.unadj.index = pd_columns
        
        return self.p, self.unadj, self.stat

    def plot_spatial(self, 
                     stat_type: str, 
                     comparison: str = None, 
                     seed: Union[int, None] = None, 
                     f_list: Union[None, list[float]] = None, 
                     f_list_type: Union[None, str] = None, 
                     hline: Union[int, None] = None,
                     ) -> plt.figure:
        '''
        This plots K, L, or g (determined by stat_type) from a given dataframe (all_stat), colored by condition.

        Args:
            stat_type (string >>> 'K', 'L', or 'g'): indicates the column of the input dataframe that contains the statistic

            comparison (string, or None): determines the plot title. If None, no plot title. Title form == celltype1 vs. celltype2, derived by 
                    splitting this argument into two strings and an "_" character (the form of strings in self._comparison_list)

            seed (integer): The random seed for bootstrapping the uncertainty areas of the lines in the plot

            f_list (list of float, or None): If provided, this list of floats is used to draw an additional, adjacent line plot. Presumed to be 
                    a list of F-statistics (or similar stat) calculated at each radius. The do_all_radii_ANOVAs() method is the usual 
                    way to generate the F values for this kind of plot. 

            f_list_type (string, or None): Title of the f_list plot, if f_list is provided

            hline (integer or None): If not None, will draw a a horizontal line on the plot at the provided value (usually 0 or 1 depending 
                    on where Ripley's g is centered)

        Returns:
            A matplotlib figure, or None

        '''
        all_stat = self._comparison_dictionary[comparison][stat_type]
        if len(all_stat) == 0:
            print("This comparison has no data -- \n" 
                    "It might be that these two cells types are never present together in the same image above the threshold!"
                    "\n Skipping this plot")
            return None
        if seed is None:
            seed = self.seed
        fixed_r = self.fixed_r
        if (f_list is not None):
            figure, (ax, ax2) = plt.subplots(1,2)
            ax2.plot(list(fixed_r), f_list)
            ax2.set_title(f_list_type)
        else:
            figure = plt.figure()
            ax = plt.gca()
        sns.lineplot(all_stat, x = 'radii', y = stat_type, hue = "condition", palette = "viridis", ax = ax, seed = seed)   # style = "image",
        if comparison is not None:
            types = comparison.split("___")
            type1 = types[0]
            type2 = types[1]
            ax.set_title(f"{type1} vs. {type2}")
        if hline is not None:
            ax.hlines(hline, xmin = 0, xmax = fixed_r[-1])
        return figure
    
    def plot_all_spatial(self, 
                         stat: str = 'g', 
                         seed: Union[int, None] = None, 
                         write: bool = True, 
                         output_directory: Union[str, Path, None] = None, 
                         hlines: Union[None, int] = None,
                         ) -> list[plt.figure]:
        '''
        This function calls the plot_spatial() method for every pairwise cellType comparison in the dataset, without the F values being 
        plotted as well.

        Args:
            stat (string -- 'K', 'L', or 'g'): which Ripley's statistic to plot

            seed (integer): random seed for the bootstrapping of the confidence intervals around the lines in the plot

            write (boolean): If True will write plots to the disk, is False will only return the plots

            output_directory (path, str, or None): If None, will operate within the directory provided when setting up this class. Otherwise, 
                    will output plot as .png in the provided directory. Only relevant if write is True

            hlines (None or integer): place a horizontal line on the plots. Can be used to show the "center" of plot of Ripley's g (0, or 1 
                    depending on which center is used)

        Returns:
            list of matplotlib figures

        Input/Output:
            Output: If write is True, exports each figure to output_directory/Functional_plots/ as PNG files. 

        '''
        if seed is None:
            seed = self.seed
        comparison_list = self._comparison_list
        if output_directory is None:
            output_directory = self.output_dir + "/Functional_plots"
        output_directory = str(output_directory)
        if write is False:
            output_directory = None

        fig_list = []
        for i in comparison_list:
            figure = self.plot_spatial(stat, comparison = i, seed = seed, f_list = None, hline = hlines) 
            if figure is not None:
                if write is True:
                    figure.savefig(f"{output_directory}/{i}_{stat}.png", bbox_inches = "tight")
                plt.close()
                fig_list.append(figure)
        return fig_list

    def plot_spatial_with_stat(self, 
                               comparison: str, 
                               seed: Union[int, None] = None, 
                               stat: str = 'g', 
                               f_p_padj: str = 'f', 
                               hline: Union[None, int] = None,
                               ) -> plt.figure:
        '''
        This function makes the spatial plot for a given cell type comparison, with the corresponding F values plotted next to it 
        (accomplished by calling the self.do_all_radii_ANOVAs and self.plot_spatial methods, for the F values and to plot the graph, 
        respectively. See self.plot_spatial for details of args

        '''
        if seed is None:
            seed = self.seed

        if (comparison not in self._comparison_list):
            print(f"One of the celltype in this comparison -- {comparison} -- is only present in one condition! Will not plot f statistic!")
            f_list, p_list, p_list_adj = (None, None, None)
        else:    
            f_list, p_list, p_list_adj = self.do_all_radii_ANOVAs(comparison = comparison, stat = stat)

        if f_p_padj == 'f':
            figure = self.plot_spatial(stat, 
                                       comparison = comparison, 
                                       seed = seed, 
                                       f_list = f_list, 
                                       f_list_type = 'f values', 
                                       hline = hline)
            return figure
        
        elif f_p_padj == 'p':
            figure = self.plot_spatial(stat, 
                                       comparison = comparison, 
                                       seed = seed, 
                                       f_list = p_list, 
                                       f_list_type = 'p values', 
                                       hline = hline)
            return figure
        
        elif f_p_padj == 'padj':
            figure = self.plot_spatial(stat, 
                                       comparison = comparison, 
                                       seed = seed, 
                                       f_list = p_list_adj, 
                                       f_list_type = 'adjusted p values', 
                                       hline = hline)
            return figure

    def plot_all_spatial_with_stat(self, 
                           seed: Union[int, None] = None, 
                           stat: str = 'g', 
                           write: bool = True, 
                           output_directory: Union[None, str] = None, 
                           f_p_padj: str = 'f', 
                           hlines: Union[None, int] = None,
                           ) -> list[plt.figure]:
        '''
        This plots spatial graphs with F values for all cellType comparisons (by calling self.plot_spatial_with_f_list method iteratively). 
        Its only difference from the self.plot_all_spatial mthod is that this plots F values (or other statistic) next to the plot of the 
        Ripley's K/L/g

        Args:
            stat (string -- 'K', 'L', or 'g'): which Ripley's statistic to plot

            seed (integer): random seed for the bootstrapping of the confidence intervals around the lines in the plot

            write (boolean): If True will write plots to the disk, is False will only return the plots

            output_directory (path, str, or None): If None, will operate within the directory provided when setting up this class. Otherwise, 
                    will output plot as .png in the provided directory. Only relevant if write is True

            f_p_padj (string -- 'f', 'p', or 'padj'): Which single radius ANOVA statistic / value to plot

            hlines (None or integer):  place a horizontal line on the plots. Can be used to show the "center" of plot of Ripley's g (0, or
                    1 as needed)

        Returns:
            list of matplotlib figures

        Input/Output:
            Output: If write is True, exports each figure to output_directory/Functional_plots/ as PNG files. 

        '''
        if seed is None:
            seed = self.seed
        comparison_list = self._comparison_list
        if output_directory is None:
            output_directory = self.output_dir + "/Functional_plots"
        output_directory = str(output_directory)

        if write is False:
            output_directory = None
        elif not os.path.exists(output_directory):
            os.mkdir(output_directory)

        fig_list = []
        for comparison in comparison_list:
            figure = self.plot_spatial_with_stat(comparison, seed = seed, stat = stat, f_p_padj = f_p_padj, hline = hlines)
            if write is True:
                figure.savefig(f"{output_directory}/{comparison}_{stat}.png", bbox_inches = "tight")
            plt.close()
            fig_list.append(figure)

        return fig_list

    def plot_cell_maps(self, 
                       multi_or_single: str, 
                       cellType_key: Union[str, None] = None,
                       write: bool = True, 
                       output_directory: Union[None, str] = None, 
                       ) -> Union[so.Plot, list[so.Plot]]:
        ## previously named after imcRtools, as the when the program was running in R, I used 
        # imcRtools (https://github.com/BodenmillerGroup/imcRtools/blob/devel/DESCRIPTION) [also GPL3]
        # --> now the critical functionality of imcRtools that was desired (cell maps) has been ported into python with this function. 
        '''
        This creates cell maps for a given image, or for all of the unique images in the data table.
        
        Args:
            multi_or_single (str): "ALL" or the filename (not the sample_id !) of a single image to be run

            write (boolean): if True, will write the figure(s) as .png files to the output_directory, if False will only return the figure(s)

            output_directory (string or Path, or None): If None, will operate within the directory provided when setting up this class. Otherwise, 
                    will output plot as .png in the provided directory. Only relevant if write is True

            legend (boolean): whether to include a legend in the figure(s)

        Returns:
            a seaborn Plot (if multi_or_single != "ALL") or a list of seaborn Plots (if multi_or_single == "ALL")

        Input/Output:
            Output: If write is True, exports each figure to output_directory/cell_maps/ as PNG files. 

        '''
        if self.cellType_key is None and cellType_key is None:
            print('The cellType column (cellType_key parameter or self.CellType_key attribute) has not been set! Cancelling plot.')
            return
        elif cellType_key is not None:
            self.cellType_key = cellType_key
        space_anova = self._retrieve_data_table(for_cell_maps = True)

        if output_directory is None:
            output_directory = self.output_dir + "/cell_maps"
        output_directory = str(output_directory)

        if write is False:
            output_directory = None
        elif not os.path.exists(output_directory):
            os.mkdir(output_directory)
        
        area = np.array(self.areas)
        roi_areas = list(self.filenames.unique())
    
        # Loop to do all at once:
        if multi_or_single == "ALL":
            plot_list = []
            space_anova['sample_id'] = space_anova['sample_id'].astype('int')
            for i in space_anova['sample_id'].unique():
                id_filename = roi_areas[i]
                filename_without_extension = id_filename[:id_filename.rfind(".")]
                img = space_anova[space_anova['sample_id'] == i].copy()
                mask_areas = area[space_anova['sample_id'] == i]
                img.loc[:,'cell areas'] = mask_areas
                img.loc[:,'cellType'] = img['cellType'].astype('category')   ## test 'leiden' here --> or better, in the single run block below 
                mpl_figure, ax = plt.subplots()  ## 1 inch of figure per 100 micrometers
                handles, labels = sns.scatterplot(x = img['x'], y = img['y'], hue = img['cellType'], size = img['cell areas'], legend = True).get_legend_handles_labels()
                plt.close()
                mpl_figure, ax = plt.subplots(figsize = (img['x'].max() / 75, img['y'].max() / 75))
                mpl_figure.suptitle(filename_without_extension)
                sns.scatterplot(ax = ax, x = img['x'], y = img['y'], hue = img['cellType'], size = img['cell areas'], legend = False)
                ax.invert_yaxis()
                ax.set_aspect('equal', anchor = 'C')
                ratio = 0.1 # - np.log(img['x'].max() / img['y'].max()) / 8
                mpl_figure.legend(handles, labels, loc = "upper right", bbox_to_anchor = (1 + ratio, 0.88), fontsize = 'x-small')
                if write is True:
                    mpl_figure.savefig(output_directory + "/" +  filename_without_extension + ".png", bbox_inches = "tight") 
                plt.close()
                plot_list.append(mpl_figure)
            return plot_list

        else:   
            space_anova['file_name'] = list(self.filenames)
            filenames = list(space_anova['file_name'].astype('str'))
            
            if multi_or_single in list(space_anova['sample_id'].astype('str')):
                id = multi_or_single
            else:
                if multi_or_single not in filenames:    ## if the provided filename is not in the available filenames, see if it is a substring of one of them
                                                            ## (this is for allowing the filename without the extension to be provided)
                                                            ## useful in the GUI in case .ome.fcs is not the format available (?)
                    for i in filenames:
                        if i.find(multi_or_single) != -1:
                            multi_or_single = i
                            break
                id = space_anova[space_anova['file_name'].astype('str') == multi_or_single]["sample_id"].values[0]

            id_filename = roi_areas[int(id)]
            filename_without_extension = id_filename[:id_filename.rfind(".")]
            img = space_anova[space_anova['sample_id'] == id].copy()
            img.loc[:,'cellType'] = img['cellType'].astype('category')
            mask_areas = area[space_anova['sample_id'] == id] 
            img.loc[:,'cell areas'] = mask_areas
            mpl_figure, ax = plt.subplots()  ## 1 inch of figure per 100 micrometers
            handles, labels = sns.scatterplot(x = img['x'], y = img['y'], hue = img['cellType'], size = img['cell areas'], legend = True).get_legend_handles_labels()
            plt.close()
            mpl_figure, ax = plt.subplots(figsize = (img['x'].max() / 75, img['y'].max() / 75))
            mpl_figure.suptitle(filename_without_extension)
            sns.scatterplot(ax = ax, x = img['x'], y = img['y'], hue = img['cellType'], size = img['cell areas'], legend = False)
            ax.invert_yaxis()
            ax.set_aspect('equal', anchor = 'C')
            ratio = 0.1
            mpl_figure.legend(handles, labels, loc = "upper right", bbox_to_anchor = (1 + ratio, 0.88), fontsize = 'x-small')
            if write is True:
                mpl_figure.savefig(output_directory + "/" + filename_without_extension + ".png", bbox_inches = "tight")
            plt.close()
            return mpl_figure

def plot_spatial_stat_heatmap(p_table: Union[np.ndarray[float], pd.DataFrame], 
                              vmin: int = 0, 
                              vmax: int = 7,
                              ) -> plt.figure:
    '''
    Takes in a pandas dataframe of numbers and returns a seaborn heatmap of the negative log values
    '''
    p_table = p_table.astype('float')
    neg_log_p = - np.log(p_table)
    figure = plt.figure()
    figure.suptitle("Negative Log of p Values")
    ax = figure.gca()
    sns.heatmap(neg_log_p, cmap = "coolwarm", linewidths = 0.01, vmin = vmin, vmax = vmax, ax = ax, xticklabels = True)
    plt.close()
    return figure

def do_functional_ANOVA(all_stat: pd.DataFrame, 
                        condition1: str, 
                        condition2: str,
                        min: int = 0, 
                        max: int = 101, 
                        step: int = 1, 
                        stat: str = "g", 
                        comparison: str = "",
                        random_state: int = 42,
                        ) -> tuple[float, float]:
    '''
    This performs a functional ANOVA test between two conditions (args = condition1, condition2) from a provided the dataset (all_g). 

    The ANOVA function being used (from scikit-fda) utilizes sampling/bootstrapping, and is non-deterministic, so a seed is needed (default = 42). 
    There may be little reason to ever change the default seed.

    Args:
        all_stat (pandas dataframe): 
            should have K / L / g values over a consistent range of radii.

        condition1 & condition2 (None, or str): 
            if both are None, does multicomparison of all groups. Else, does a pairwise comparison
            of the only the two provided groups. condition1/2 must be values in the Group column of self.datatable 

        max, min, & step (int): 
            The ranges of the data are needed to help unravel the data in all_stat properly

        stat (str): 
            which stat (K / L / g) is being used.

        comparison (str): 
            not necessary, but useful for error messages identifying comparisons that encountered a problem, especially in the GUI.

        random_state (int): 
            random seed for reproducibility.

    Returns:
        stat:  The variance statistic of ANOVA, uncertain if / how to use it (it is not a statistic that informs what the p-value is directly,
                like the F, T, or H statistics do)

        p_val:  The calculated p value of the ANOVA
    '''  
    conditions = all_stat['condition'].unique()
    if len(conditions) == 1:  ### this means one or both cell types is only in one condition
        print(f"Error! Only one condition available for comparison: {comparison}! Setting state = 0 and pvalue = 1, \n"
              "but NOTE THAT THIS IS AN INVALID COMPARISON!")
        return (0, 1)
    condition_list = []
    if (condition1 is None) and (condition2 is None):
        for i in all_stat['condition'].unique():
            condition_list.append(all_stat[all_stat['condition'] == i][[stat,'radii']])
    else:
        for i in [condition1, condition2]:
            condition_list.append(all_stat[all_stat['condition'] == i][[stat,'radii']])
    for_fda_list = []
    for j in condition_list:
        last_level = 0
        output_df = pd.DataFrame()
        for i in range(0,len(j), int((max - min) / step)):    #### this unravels the list of K / L / g
            if i != 0:
                slicer = j[last_level:i][stat]
                slicer.index = range(min,max, step)
                last_level = i
                output_df = pd.concat([output_df, slicer], axis = 1)
        data = np.array(output_df.T)
        grid_points = np.array(range(min, max, step))
        for_fda_list.append(skfda.FDataGrid(data, grid_points))
    try:
        stat, p_val = oneway_anova(*for_fda_list, random_state = random_state)
    except Exception:
        print("error in obtaining pvalue: stat set = 0 , pvalue = 1 ") #   for following dataframe:")
        stat = 0
        p_val = 1
    return stat, p_val 


def do_K_L_g(pointpattern: pd.DataFrame, 
          type_column, 
          type1, 
          type2, 
          fixed_r: range, 
          threshold: int = 10,
          image_name: str = '', 
          permutations: int = 0, 
          perm_state: int = 42, 
          center_on_zero: bool = True,
          ) -> tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:       # *** deriv_spatstat (largely a direct translation, but some divergences)
    '''
    This function calculates K, L, and g for a given image and pair of cell types at a range of distances (fixed_r).
    
    This function is heavily based on spatstat package (R). Some notes are included here as why certain decisions were made:

    K -->  for notes about K & spatstat, see the _K_cross_homogeneous() function. 
    L --> https://github.com/spatstat/spatstat.core/blob/master/R/Kest.R, line 40 (in function Lest) >>> L <- eval.fv(sqrt(K/pi))
    g --> 

    Args:
        pointpattern (pandas dataframe): has columns ['x','y',type_column]. It should be for a single image (not a collection of images)

        type_column: the name of the pointpattern column containing the labels of the two types

        type1: one of the levels of the type_column used for the cross --> this is also the collection of objects used for edge correction 
                (the set of points FROM which radii are drawn)

        type2: one of the levels of the type_column used for the cross --> the set of point TO which radii are drawn
            NOTE: >>> type_column, type1, type2 are usually strings, and are recommended to be so, but can vary in type depending on the
                column label & dtype in the pandas dataframe

        fixed_r (range): indicates at what radii lengths to calculate the Kcross values

        permutations (int): representing the numer of permutations to correct K (and L / g downstream) by. Permutation correction is not
                    applied if == 0

        perm_state (int): the random seed used in shuffling the types for the permutations. Ignored if permutations == 0

    Returns:
        K_df, L_df, g_df: three dataframes with the calculated K / L / g values

    '''
    window = [pointpattern['x'].min(), pointpattern['x'].max(), pointpattern['y'].min(), pointpattern['y'].max()]
    result_array = np.zeros([len(fixed_r)])
    radii_array = np.zeros([len(fixed_r)])
    for i,ii in enumerate(fixed_r):
        radii_array[i] = ii

    result_array, theoretical_K = _K_cross_homogeneous(pointpattern,
                                            fixed_r = fixed_r, 
                                            window = window, 
                                            mark_type = type_column, 
                                            type1 = type1, 
                                            type2 = type2, 
                                            threshold = threshold,
                                            image_name = image_name)
    if (result_array.sum() == 0):
        '''This means that there are no cells / the number of cells is below the threshold '''
        K_df = pd.DataFrame(result_array, columns = ["K"])
        K_df['theoretical'] = theoretical_K
        K_df['radii'] = radii_array
        return K_df, np.zeros([len(fixed_r)]), np.zeros([len(fixed_r)])
    
    centerer = 1
    if permutations > 0 :
        avg_K = np.zeros(len(result_array))
        perm = pointpattern.copy()
        for i in range(0, permutations, 1):
            perm[type_column] = list(perm[type_column].sample(frac = 1.0, random_state = perm_state))
            new_K, _ = _K_cross_homogeneous(perm, 
                                fixed_r = fixed_r, 
                                window = window, 
                                mark_type = type_column, 
                                type1 = type1, 
                                type2 = type2, 
                                threshold = threshold,
                                image_name = image_name)
            avg_K = avg_K + new_K
        avg_K = avg_K / permutations
        if center_on_zero is True:
            perm_correction = 0 - avg_K 
            centerer = 0
        else:
            perm_correction = theoretical_K - avg_K 
        result_array = result_array + perm_correction 
        #result_array[result_array < 0] = 0       ## --> useful when center_on_zero is False (?)
        theoretical_K = avg_K
    else:
        if center_on_zero is True:
            result_array = result_array - theoretical_K
            centerer = 0
            
    K_df = pd.DataFrame(result_array, columns = ["K"])
    K_df['theoretical'] = theoretical_K
    K_df['radii'] = radii_array
    
    L_df = pd.DataFrame()
    signs = np.ones(result_array.shape)
    signs[result_array < 0] = signs[result_array < 0] * -1
    L_df["L"] = np.sqrt(np.abs(result_array) / np.pi) * signs
    L_df['theoretical'] = np.sqrt(theoretical_K / np.pi)
    L_df['radii'] = radii_array 

    ### calculate g, as well
    ### Code efectively translated from the pcf function of spastat using the method "c"   ( the method used in spaceANOVA):
    g_df = pd.DataFrame()
    z = K_df['K'] / (np.pi*(radii_array ** 2))
    z = np.nan_to_num(z, nan = centerer, posinf = centerer, neginf = centerer)
    cs = make_smoothing_spline(radii_array, z, lam = 50000)    
            ## helpful links: https://stackoverflow.com/questions/56667657/python-scipy-univariatespline-vs-r-smooth-spline                                                    ## 
    g = ((radii_array/2) * cs.derivative(nu = 1).__call__(fixed_r)) + z

    g_df['g'] = g
    for_theory_z = theoretical_K / (np.pi*(radii_array**2))
    for_theory_z = np.nan_to_num(for_theory_z, nan = 1, posinf = 1, neginf = 1)
    cs = make_smoothing_spline(radii_array, for_theory_z, lam = 50000)    
                ## helpful links: https://stackoverflow.com/questions/56667657/python-scipy-univariatespline-vs-r-smooth-spline                                                    ## 
    theory_g = ((radii_array/2) * cs.derivative(nu = 1).__call__(fixed_r)) + for_theory_z
    g_df['theoretical'] = theory_g + (centerer - 1)  # no change when center = 1, else -1 to the theoretical
    g_df['radii'] = radii_array
    
    return K_df, L_df, g_df

def _K_cross_homogeneous(df: pd.DataFrame, 
                         fixed_r: range, 
                         window: list[float], 
                         mark_type, 
                         type1: str, 
                         type2: str, 
                         threshold: int = 10,
                         image_name: str = '',
                         ) -> tuple[np.ndarray[float],np.ndarray[float]]:                       
                                                 # *** deriv_spatstat (largely a direct translation, but some divergences)
    '''
    This function is intended as a translation of the spatstat package Kest (homogeneous) function:
             https://github.com/spatstat/spatstat.core/blob/master/R/Kest.R

    It is only intended to only use Ripley's isotropic edge correction & consistent radii steps. It does not try to implement 
    the variance approximation.

    Instead of indentifying only close pairs (see: https://github.com/spatstat/spatstat.core/blob/master/R/Kest.R#L200), 
    this function identifies ALL pairs (perhaps slightly less efficient, shouldn't matter for accuracy). 
    ***Edge correction step & bulk of K calculation at line 290 in spatstat:
                https://github.com/spatstat/spatstat.core/blob/master/R/Kest.R#L290
    
    Args:
        df (pandas dataframe): where x and y columns are labeled accordingly and the col identified by {marktype} is the column used to 
            decide cell type pairs 

        marktype (str, numeric): a value that indicates which column in {df} to use for the two cell types. Usually a string. 

        window (list of numeric): a four-length list with the minimum / maximum dimensions of the window. 

        type1, type2 (strings, numeric). These determine which levels in the marktype column are used for the pairwise K estimation. 
                The spatial comparison is Type1 --> Type2. 

        fixed_r (range): the distances / radii being used in the calculation

    Returns:
        The calculated & theoretical K values as two numpy arrays. 

    '''
    window_area = (window[1] - window[0]) * (window[3] - window[2])
    corner_to_corner = [(window[1] - window[0]), (window[3] - window[2])]
    diameter = np.sqrt(np.square(corner_to_corner[0]) + np.square(corner_to_corner[1]))   
                    ### cacluate the euclidean distance from the 0,0 corner to the centerpoint --> radius of the bounding circle, I think
                    # Diameter / 2 in the original spatstat function: 
                    #       https://www.rdocumentation.org/packages/spatstat/versions/1.64-1/topics/diameter  
                    # ---> diameter = longest distance in window

    if (diameter/2 < fixed_r[-1]):
        new_max = [i for i in fixed_r if i < diameter/2][-1]  ## truncates the search area, while retaining the step distance
        truncated = True
    else:
        new_max = fixed_r[-1]
        truncated = False    
    
    x_and_y_and_type = df[['x','y',mark_type]]
    type1_objects = x_and_y_and_type[x_and_y_and_type[mark_type] == type1]
    t1_as_array = np.array([type1_objects['x'],type1_objects['y']]).T
    type2_objects = x_and_y_and_type[x_and_y_and_type[mark_type] == type2]
    t2_as_array = np.array([type2_objects['x'],type2_objects['y']]).T

    N_points_1 = len(type1_objects)
    N_points_2 = len(type2_objects) 

    radii_array = np.array([i for i in fixed_r])
    for i,ii in enumerate(fixed_r):
        if (truncated is True) and (ii > new_max):
            radii_array[i] = 0   
    K_theo = (np.pi*(radii_array**2))  ## This had been missing (only added 7-23-24) in my implementation.

    ## add trailling zeroes to truncated plots, to maintain consistent length:   ---> already effectivel accomplished in lines above
    if truncated is True:
        diff_length = fixed_r[-1] - new_max
        append_array = np.zeros(diff_length)
    #    K_theo = np.concatenate([K_theo, append_array])

    if (N_points_1 < threshold) or (N_points_2 < threshold):
        print(f'One or both of {mark_type}s {type1} or {type2} has less than {threshold} cells in the image {image_name}!')
        return np.zeros(len(K_theo)), K_theo
    
    lambda1 = N_points_1  ### technically divided by window 1 area, but that gets canceled out by later multiplication when K is calculated
    lambda2 = N_points_2 / window_area
    
    distances = cdist(t1_as_array, t2_as_array, "euclidean")
    
    ### Set points greater than the maximum to an infinite distance (so they will never register in the calculations). 
    distances[distances > new_max] = np.inf                      
    if type1 == type2:
        for i in range(0,distances.shape[0]):
            distances[i,i] = np.inf
    
    # edge correction
    for_weights = _spatstat_Edge_Ripley(t1_as_array, distances, window)
    if fixed_r[0] == 0:
        bins = int(new_max / fixed_r.step)   ## can't count from 0
    else:
        bins = int((new_max - fixed_r[0]) / fixed_r.step)  ## can count from first bin in this case 
    K_hist = np.histogram(distances, bins = bins, range = (fixed_r[0], new_max), weights = for_weights) 
    if fixed_r[0] == 0:
        fill = 0
    else:
        fill = np.cumsum(np.histogram(distances, bins = 1, range = (0, fixed_r[0]), weights = for_weights)[0])
    K = np.append(fill, np.cumsum(K_hist[0]) + fill)

    # take into account density of celltypes in the window
    K = K / (lambda1 * lambda2)
    if truncated is True:
        K = np.concatenate([K, append_array])
    return K, K_theo

def _spatstat_Edge_Ripley(X: pd.DataFrame, 
                          r: np.array, 
                          window: list[float],
                          ) -> np.ndarray[float]:         # *** deriv_spatstat (direct translation)
    '''
    This is intended to be a direct translation from R of the spatstat package: 
                https://github.com/spatstat/spatstat.core/blob/master/R/edgeRipley.R

    Args:
        X (pandas dataframe): has two columns, represent a set of points (rows) with X & Y values (columns). 

        r (numpy array): the distances between points (from the scipy cdist function)

        window list[float,float,float,float]: the max / min values of x,y in the window (aka, the four max / min of x,y in X)

    Returns:
        an array of weights to scale the histogram in the main _K_cross_homogeneous() function
    '''
    windowXmin = window[0]
    windowXmax = window[1]
    windowYmin = window[2]
    windowYmax = window[3]

    dLeft = X[:,0] - windowXmin
    dRight = windowXmax - X[:,0]
    dUp = X[:,1] - windowYmin    ### the top is usually the 0 in the ydimension for images --> X vs. Y shouldn't matter anyway (symmetric?)
    dDown = windowYmax - X[:,1]
    corner = (_spatstat_small(dLeft) == 0) + (_spatstat_small(dRight) == 0)  + (_spatstat_small(dDown) == 0) + (_spatstat_small(dUp) == 0) >= 2   ### points in the corner will have 0-values for exactly two of the dRight/Left/Up/Down paramters
    
    angleLeftUp = np.arctan2(dUp, dLeft)
    angleLeftDown = np.arctan2(dDown, dLeft)
    angleRightUp = np.arctan2(dUp, dRight)
    angleRightDown = np.arctan2(dDown, dRight)
    angleUpLeft = np.arctan2(dLeft, dUp)
    angleUpRight = np.arctan2(dRight, dUp)
    angleDownLeft = np.arctan2(dLeft, dDown)
    angleDownRight = np.arctan2(dRight, dDown)

    angleLeft = _spatstat_hang(dLeft, r)
    angleRight = _spatstat_hang(dRight, r)
    angleDown = _spatstat_hang(dDown, r)
    angleUp = _spatstat_hang(dUp, r)

    mini_left = np.fmin(angleLeft.T, angleLeftUp).T + np.fmin(angleLeft.T, angleLeftDown).T
    mini_right = np.fmin(angleRight.T, angleRightUp).T + np.fmin(angleRight.T, angleRightDown).T
    mini_down = np.fmin(angleDown.T, angleDownLeft).T + np.fmin(angleDown.T, angleDownRight).T
    mini_up = np.fmin(angleUp.T, angleUpLeft).T + np.fmin(angleUp.T, angleUpRight).T
    
    ## total exterior angle (? this is the note from spatstat itself --> I have not really followed the underlying math while copying the code)
    total = mini_left + mini_right + mini_down + mini_up

    if corner.sum() > 0:
        print('corners!')
        total[corner] = total[corner] + (np.pi / 2)

    weights = 1 / (1 - (total / (2 * np.pi)))
    weights = np.maximum(1, np.minimum(100, weights))   ## removes weights <1 and >100
    return weights

def _spatstat_hang(d: np.ndarray[float], 
                   r: np.ndarray[float],
                   ) -> np.ndarray[float]: # *** deriv_spatstat (direct translation)
    '''
    This function is similarly a direct translation from spatstat, it is a helper function to the _spatstat_Edge_Ripley() function above:
            see: https://github.com/spatstat/spatstat.core/blob/master/R/edgeRipley.R
            
    Args:
        d (numpy array): distances (from each point to the edge of the window)

        r (numpy array): a matrix of the calculated distances between pairs in the point pattern

    '''   
    final_matrix = np.zeros(r.shape)
    distance = np.full(r.T.shape, d).T
    hits = (r > distance)
    final_matrix[hits] = np.arccos(distance[hits] / r[hits])
    return final_matrix

def _spatstat_small(array: np.ndarray[float]) -> np.ndarray[bool]:  # *** deriv_spatstat (direct translation)
    '''This function checks if a float is == 0 (or close enough to 0)'''
    return abs(array) < np.finfo('float64').eps