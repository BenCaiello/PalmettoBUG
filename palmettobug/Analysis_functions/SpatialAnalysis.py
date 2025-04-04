'''
The SpatialNeighbors class draws heavily on Squidpy, mainly serving as a way of wrapping squidpy funcitons in a way that will help them
play nice with PalmettoBUG's existing data structures   (this file was added after many others, on 11-21-24).
SpatialEDT class performs the pixel-class driven euclidean distance transform calculation. 

SpatialAnalysis serves a unifying class FOR THE nonGUI API coordinating all the spatial functions/methods in PalmettoBUG 
IT IS NOT USED IN THE GUI AT PRESENT! Instead, the individual spatial classes are called by the GUI. These were made firstm
before the coordinating class, which is why there is a disconnect between the implementation in the GUI and outside it.

This file is licensed under the GPL3 license. No significant portion of the code here is known to be derived from another project 
(in the sense of needing to be separately / simultaneously licensed)
'''
import os
from typing import Union
from pathlib import Path
import tkinter as tk
import warnings

import tifffile as tf
import skimage
import scipy
import numpy as np
import pandas as pd
import scanpy as sc
import matplotlib.pyplot as plt
import seaborn as sns
import anndata as ann

#from .._vendor.flowsom import FlowSOM, plot_stars

## anticipate de-vendorization:
from flowsom import FlowSOM
from flowsom.pl import plot_stars

from ..Pixel_Classification.Classifiers import smooth_isolated_pixels
from ..Pixel_Classification.use_classifiers import merge_folder
from .SpatialANOVA import SpatialANOVA, plot_spatial_stat_heatmap

warnings.filterwarnings("ignore", message = "Importing read_text")   ## future warning in anndata that squidpy has not caught up to yet. Irritating to see everytime on startup
import squidpy as sq # noqa: E402

__all__ = ["SpatialAnalysis"]

class SpatialAnalysis:
    '''
    This class serves as a coordinating class for the three spatial analysis sub-classes. In the GUI, these subclasses are currently called directly (for historical reasons
    and because there is no real reason to update that). However, for use of PalmettoBUG in scripting, it is convenient to have a unified class where all the spatial methods
    can be accessed.

    The methods of this class are wrappers on methods of the 3 sublclasses. Because of this, it can be divided into a number of groupings:

        >>> data loading, cell maps, neighbors, neighborhoods, spaceANOVA, and edt    (in order)

    kEY Attributes:
        exp:
            This is the connected Analysis object, containing the anndata (exp.data) which holds most of the data used for calculations

        SpaceANOVA, neighbors, edt:
            These are subclasses that contain the actual methods used by this higher-level class. The methods of this class
            are all wrappers on methods contained in one of these sub-classes. 

    '''
    def __init__(self):
        '''
        '''
        self.edt = SpatialEDT()
        self.SpaceANOVA = SpatialANOVA()
        self.neighbors = SpatialNeighbors()

    def add_Analysis(self, Analysis):
        '''
        Connects the Spatial methods here to a palmettobug.Anlysis object. Edits to the Analysis object will affect the Spatial methods here
        '''
        self.exp = Analysis
        self.edt.add_Analysis(Analysis)
        self.SpaceANOVA.init_analysis(Analysis, output_directory = (self.exp.directory + "/Spatial_plots"))
        self.neighbors.add_Analysis(Analysis)

    def plot_cell_maps(self,
                       plot_type: str,
                       id: Union[str, int, None] = None, 
                       clustering: str = "merging") -> plt.figure:
        '''
        This plot cell maps either as "points" or as "masks".

        Args:
            plot_type (string): 
                either "points" or "masks". If "points" then the cells are represented at dots or various sizes on a white background. If "masks" then 
                the cells are represented as their mask shapes on a black background ("masks" uses a squidpy plotting function). 

            id (string, integer, or None): 
                If None, will make cell maps for every smpale_id / image in the dataset. If not None, will only make a plot for the specified image.
                id's should either be the sample_id (for which a string or integer form will work) or the file_name of the desired image.

            clustering (string): 
                the name of the column in self.exp.data.obs to use for coloring the cells. Usually one of the standard clustering column names 
                ("merging", "metaclustering", etc.)

        Returns:
            matplotlib.figure or None
        '''
        if plot_type == "masks":
            if id is None:
                self.neighbors.plot_all_cell_maps(clustering = clustering)
            else:
                id = str(id)
                sample_ids = list(self.exp.data.obs['sample_id'].astype('str'))
                if id in sample_ids:
                    plot, _ = self.neighbors.plot_cell_map(sample_id = id, clustering = clustering, save = True)
                    return plot
                elif id in list(self.exp.data.obs['file_name'].astype('str')):
                    plot, _ = self.neighbors.plot_cell_map(filename = id, clustering = clustering, save = True)
                    return plot
                else:
                    print(f"id = {id} was not in the data.obs sample_id or file_name columns!") 

        elif plot_type == "points":
            if id is None:
                self.SpaceANOVA.plot_cell_maps(multi_or_single = 'ALL', cellType_key = clustering)
            else:
                id = str(id)
                plot = self.SpaceANOVA.plot_cell_maps(multi_or_single = id, cellType_key = clustering)
                return plot

        else:
            print(f"plot_type must be either 'masks' or 'points', but instead {plot_type} was provided") 

    def do_neighbors(self, radius_or_neighbors: str, number: int):
        '''
        Creates the neighbor-graph between cells in the dataset (using their centroids). This step is necessary before performing any of the other neighbor-based methods.
        It uses the squidpy.gr.spatial_neighbors function to generate the neighborhood graph.

        Args:
            radius_or_neighbors (string):
                whether to create the neighbor graph using a fixed radius ("Radius") or to create the neighbor graph using 
                a fixed number of neartest neighbors ("Neighbor")

            number (integer): 
                either the length of the search radius in pixels, or the number of nearest neighbors per cell (depending on radius_or_neighbors parameter)
        '''
        self.neighbors.do_neighbors(radius_or_neighbors = radius_or_neighbors, number = number)

    def plot_neighbor_interactions(self, clustering: str = "merging", facet_by: str = "None", col_num: int = 1, filename: Union[str, None] = None):
        '''
        This method wraps squidpy's gr/pl.interaction_matrix functions. It plots a heatmap representing the number of interactions between
        cell types in the dataset. Note that this is an absolute number, and is effected by the abundance of celltypes (more abundant celltypes will 
        have more interactions). 

        Args:
            clustering (string): 
                the name of the column in self.exp.data.obs to use for grouping cells into cell types. Usually one of the standard clustering column names 
                ("merging", "metaclustering", etc.). Their should be >1 unique cluster, the heatmap's dimensions with only one cluster would be 1x1

            facet_by (string): 
                a name of a column in self.exp.data.obs or "None". If not "None", used to interaction matrices for subsets of the data, for example to compare
                interaction matrices between conditions. The first panel is always the interaction matrix for the entire dataset (not subsetted).

            col_num (integer): 
                If facetting, how many columns to have in the figure.

            filename (string or None): 
                if not None, will write the plot as /{filename}.png to the spatial save folder of the palmettobug analysis directory. 

        Returns:
            matplotlib.figure
        '''
        facet_by = str(facet_by)
        plot = self.neighbors.plot_interaction_matrix(clustering = clustering, facet_by = facet_by, col_num = col_num, filename = filename)
        return plot

    def plot_neighbor_enrichment(self, clustering = "merging", facet_by = "None", col_num = 1, seed = 42, n_perms = 1000, filename = None):
        '''
        This method wraps squidpy's gr/pl.neighborhood_enrichment functions. It plots a heatmap representing the enrichment of interactions over the 
        random expectation between cell types in the dataset. This is calculated by permutation test, and the values of the heatmap are z-scores
        between the interactions found in the permutation test and the empirical number of interactions.

        Args:
            clustering (string): 
                the name of the column in self.exp.data.obs to use for grouping cells into cell types. Usually one of the standard clustering column names 
                ("merging", "metaclustering", etc.). Their should be >1 unique cluster, the heatmap's dimensions with only one cluster would be 1x1

            facet_by (string): 
                a name of a column in self.exp.data.obs or "None". If not "None", used to interaction matrices for subsets of the data, for example to compare
                interaction matrices between conditions. The first panel is always the neighborhood enrichment for the entire dataset (not subsetted).

            col_num (integer): 
                If facetting, how many columns to have in the figure.

            seed (integer): 
                random seed for the permutation test

            n_perms (integer): 
                how many permutations to perform in the permutation test

            filename (string or None): 
                if not None, will write the plot as /{filename}.png to the spatial save folder of the palmettobug analysis directory. 

        Returns:
            matplotlib.figure 
        '''
        plot = self.neighbors.plot_neighborhood_enrichment(clustering = clustering, facet_by = facet_by, col_num = col_num, seed = seed, n_perms = n_perms, filename = filename)
        return plot

    def plot_neighbor_centrality(self, clustering: str = "merging", score: str = "closeness_centrality", filename: Union[str,None] = None):
        '''
        Wraps squidpy's gr/pl.centrality_scores functions. clustering corresponds to "cluster_key" in squidpy's API, and score corresponds to "score". 
        As with othe rfunciton sin PalmettoBUG, if filename is not None, then it will be used to write the plot to the disk as a png, otherwise only
        the plot itself will be returned (where is can be edited or saved manually). 
        '''
        plot = self.neighbors.plot_centrality(clustering = clustering, score = score, filename = filename)
        return plot

    def do_neighborhood_CNs(self, 
                            clustering: str = "merging", 
                            leiden_or_flowsom: str  = "FlowSOM", 
                            seed: int  = 42, 
                            resolution: float  = 1.0, 
                            min_dist: float  = 0.1, 
                            n_neighbors: int  = 15, 
                            **kwargs):
        '''
        This method uses a previously constructed neighbor graph and a cell clustering to identify the proportions of each cell type among the neighbors of 
        every cell, then runs an unsupervised clustering algorithm (FlowSOM or Leiden) to group the cells in "cellular neighborhoods" (CNs). This neighborhood 
        grouping is appended to self.exp.data.obs as a "CN" column, and can be used in all the same ways as any other annotation / clustering to generate plots, etc.
        Additionally, a figure is returned that is unique to the type of clustering performed -- if FlowSOM, a minimum spanning tree is returned while if Leiden then
        a UMAP is returned.

        Args:
            clustering (string): 
                the name of the column in self.exp.data.obs to use for grouping cells into cell types. Usually one of the standard clustering column names 
                ("merging", "metaclustering", etc.).

            leiden_or_flowsom (string): 
                "Leiden" or "FlowSOM" -- determines which of the unsupervised clsutering algorithms will be used to group the cells.

            seed (integer): 
                The random seed for the clustering algorithm

            resolution (float): 
                ONLY for Leiden clustering -- corresponds to the same parameter (resolution) in scanpy's tl.leiden function

            min_dist (float): 
                ONLY for Leiden clustering -- corresponds to the same parameter (min_dist) in scanpy's tl.umap function, which is 
                necessary for leiden clustering

            n_neighbors (integer): 
                ONLY for Ledien clustering -- corresponds to the same parameter in scanpy's pp.neighbors function, which is necessary 
                for leiden clustering

            **kwargs: 
                ONLY for FlowSOM -- these passed into the FlowSOM class (copied from saesys lab FlowSOM_Python repository). This allows key
                parameters like the number of trainig cycles (rlen), number of output clusters (n_clusters), and x/y dimensions (xdim and ydim)
                to be passed to the FlowSOM instance. 

        Returns:
            matplotlib.figure
        '''
        figure = self.neighbors.do_cellular_neighborhoods(clustering = clustering, 
                                  leiden_or_flowsom = leiden_or_flowsom, 
                                  seed = seed, 
                                  resolution = resolution, 
                                  min_dist = min_dist, 
                                  n_neighbors = n_neighbors, 
                                  **kwargs)
        return figure

    def plot_CN_graph(self, filename: Union[str, None] = None):
        ''' 
        UMAP or star-plot -- note that this figure is already returned by the method above
        '''
        plot = self.neighbors._plot_stars_CNs(filename = filename)
        return plot

    def plot_CN_heatmap(self, clustering: str = "merging", **kwargs):
        '''
        Plots a heatmap of the proportions of the cell types in each of the CN clusters
        '''
        plot = self.neighbors.plot_CN_heatmap(clustering_col = clustering, **kwargs)
        return plot

    def plot_CN_abundance(self, clustering, cols = 3):
        '''
        Plots a facetted barplot of the proportion of each cell type in each of the CN clusters
        '''
        plot = self.neighbors.plot_CN_abundance(clustering, cols = cols)
        return plot

    def do_SpaceANOVA_ripleys_stats(self,
                                    clustering: str,
                                    max: int = 100, 
                                    min: int = 10,
                                    step: int = 1, 
                                    condition1: Union[str, None] = None, 
                                    condition2: Union[str, None] = None,
                                    threshold: int = 10,
                                    permutations: int = 0, 
                                    seed: int = 42, 
                                    center_on_zero: bool = False, 
                                    silence_zero_warnings: bool = True):
        '''
        Calculates Ripley's spatial statistics for every celltype-celltype pair in clustering in every image. The necessary first step in the SpaceANOVA analysis
        pipeline.

        Args:
            clustering (string): 
                the name of the column in self.exp.data.obs to use for grouping cells into cell types. Usually one of the standard clustering column names 
                ("merging", "metaclustering", etc.).

            max / min / step (integers): 
                these are the integers that determine at which radii statistics will be calculated. An easy to see what those radii will be is

                    >>> list(range(min, max, step))

                The default looks at the range 10-100 with a step size of 1. The min is set to be > 0 because the first few radii should essentiall always have
                zero cell interactions in them. This is because we calculate using cell centroids, so even if two cells directly touch, the first few radii will 
                still not have an interaction. For example, if a perfectly circular cell has a diameter of 10, then only radii > 5 will even have a change of encountered 
                another cell since radii < 5 will only search space INSIDE the cell. And even once the earch radius is outside the cell, it does not count as an 
                interaction when it touches another cell -- it only is counted when it touches the centroid of the other cell. 
                Because of this, usually radii < 10 or so have almost no interaction and therefore very unusual behaviour, and might be best dropped from the calculations.
            
            condition1 / condition2 (string or None): 
                If both are None (default), then every condition in the dataset is used (and the fANOVAs are multi-comparison). Else if both
                condition1/2 are specificied, they should be unique values in the 'condition' columns of self.exp.data.obs, and the SpaceANOVA analysis will
                only look at those conditions, using pairwise comparisons / ANOVAs.

            threshold (integer): 
                default = 10. If at least of the celltypes in a given celltype-celltype pair has fewer cells than this threshold in a given image, 
                that image will be skipped & no Ripley statistics will be calculated from that image for that celltype-cetype pair. Note that is a given 
                celltype-celltype pair never passes this threshold for any of the images for a given condition, then it will be ignored for that condition. Further, 
                if only one condition (or no conditions) has images that pass the threshold, then an ANOVA for that celltype-celltype pair is impossible and will be 
                skipped. However, even then, the Ripley's statistics that were successfully calculated for that single condition can still be plotted.

            permutations (integer): 
                If greater than zero, than a permutation correction will be applied to the data. This is done by randomizing the celltype labels in an image
                and calculating the average Ripley's K for those randomizations. The average random K for the celltype is then substracted from the calculated Ripley's K 
                for that celltype in that image. This corrected K is than used to calculate Ripley's L / g as normal.
                Permutation correction can slow the calculation substantially, but is almost always recommended as it uses the actual strucutre of the cells in the 
                images to correct the values of the Ripley's statistics. This is a powerful and simple way to correct for holes / inhomogeneities in the tissue.

            seed (integer): 
                This is the random seed used for the SpaceANOVA methods. This includes the random permutations for the permutation correction, but
                also the seeds used plotting error regions and fANOVA. The seeds for plotting & fANOVA can be set separately when calling those functions
                but by default whatever you use here for the seed will be used for those steps as well. 

            center_on_zero (boolean): 
                ONLY with permutation correction (permutations > 0). This determines whether to 'center' Ripley's g on 0 or on 1.
                Ripley's g is unique among the Ripley's statistics in that it is particularly easy to interpret, as its theoretical value in a 
                random point pattern is equal to a straight line at 1, with values above 1 indicating more association between points that expected,
                and value less than 1 indicating less interactions that expected. However, the permutation correction shifts this centerpoint to 1 when 
                the permutation is substracted from the calculated K. Additionally, when this substract is done the shape of K / L will deviate strongly
                from the theoretical shape of those statistic's curves.
                So: 
                If this parameter is True, then this shift is allowed to occur, and g will need to be interpreted as centered on 0.

                    >>> Permutation correction is: K = K_data - K_permutation

                If this paramter is False, then after substracting the permutaiton K, the theoretical K { pi*(r^2) } is added back, which
                shifts the center of g to 1 without changing its shape. This change also restores the shape of the K / L statistics to better match  
                their more usual, monotonically increasing shape

                    >>> Permutation correction is: K = K_data + (K_theoretical - K_permutation)

            silence_zero_warnings (boolean):
                this method generates a large number of zero division errors, even in a normal run. By default these are silenced. 
        '''
        self.SpaceANOVA.do_spatial_analysis(
                            condition1 = condition1, 
                            condition2 = condition2,
                            cellType_key = clustering,
                            max = max, 
                            min = min,
                            step = step, 
                            threshold = threshold,
                            permutations = permutations, 
                            seed = seed, 
                            center_on_zero = center_on_zero, 
                            silence_zero_warnings = silence_zero_warnings,
                            )

    def plot_spaceANOVA_function(self, 
                                 stat: str, 
                                 comparison: str = None, 
                                 seed: Union[int, None] = None, 
                                 f_stat: Union[str, None] = None, 
                                 hline: Union[int, None] = None,
                                 output_directory: Union[str, None] = None):
        ''' 
        This function plots a selected Ripley's statistic for a celltype-celltype pair, and optionally also the signle-radii f-values from ANOVA tests
        conducted at each point along the Ripley stat graph.
        
        Args:
            stat (string): 
                either "K", "L", or "g". Determines which Ripley's statistic to plot

            comparison (string or None): 
                a string with the form {celltype1}___{celltype2}. The triple underscore in the middle is how this string is split
                into the two cell types of interest (don't have a triple underscore inside your cell type labels!). A full list of the available comparisons of 
                this form can also be easily accessed with the self.SpaceANOVA._all_comparison_list attribute

            seed (integer or None): 
                the random seed for the fANOVA function. If None, then the seed previously selected in self.do_SpaceANOVA_ripleys_stats will be used.

            f_stat (string or None): 
                if not None, should be "f" (typical), "padj", or "p". If not None, adds a panel to the final plot showing the results of
                (standard, not functional) ANOVA tests comparing conditions at every individual radii. This is useful for visualizing at what distance the 
                difference between conditions is most significant. 

            hline (int or None): 
                if not None, draws a horizontal line on the Ripley's statistics plot at the value (usually ONLY when plotting the 'g' statistic, and 
                set to 0 or 1, depending on where the graph is centered)

            output_directory (string or None): 
                If None, the plots are exported to the automatic / standard directory in the PalmettoBUG project. if not None, should the path to a folder where
                the plots can be exported. (ONLY used if comparison is None)
        
        '''
        if f_stat is None:
            if comparison is None:
                self.SpaceANOVA.plot_all_spatial(stat = stat, seed = seed, write = True, output_directory = output_directory, hlines = hline)
            else:
                plot = self.SpaceANOVA.plot_spatial(stat_type = stat, 
                                            comparison = comparison, 
                                            seed = seed, 
                                            f_list = f_stat, 
                                            hline = hline)
                plot.savefig(self.SpaceANOVA.output_dir + f"/Functional_plots/{comparison}_{stat}.png", bbox_inches = "tight")
                return plot
        else:
            if comparison is None:
                self.SpaceANOVA.plot_all_spatial_with_stat(seed = seed, 
                                                           stat = stat,
                                                           write = True, 
                                                           output_directory = output_directory, 
                                                           f_p_padj = f_stat, 
                                                           hlines = hline)
            else:
                plot = self.SpaceANOVA.plot_spatial_with_stat(comparison = comparison, 
                                                       seed = seed, 
                                                       stat = stat, 
                                                       f_p_padj = f_stat, 
                                                       hline = hline)
                plot.savefig(self.SpaceANOVA.output_dir + f"/Functional_plots/{comparison}_{stat}.png", bbox_inches = "tight")
                return plot 

    def run_SpaceANOVA_statistics(self, 
                                 stat: str = 'g', 
                                 seed: Union[int, None] = None):
        '''
        This runs the functional ANOVA on the available Ripley's statistics, returning 3 datatables for the (adjusted) p-value, and fANOVA stat
        '''
        self.padj, self.p, self.stat = self.SpaceANOVA.do_all_functional_ANOVAs(stat = stat, seed = seed)
        return self.padj, self.p, self.stat

    def plot_spaceANOVA_heatmap(self, stat: str, filename = None):      ## TODO: configure filename properly
        '''
        Plots a heatmap from one of the dataframes returned / created by self.run_SpaceANOVA_statistics. If plotting a (adjusted) p-value, as is typical, the 
        statistic is transformed by the negative log first so that high number indicate higher significance.

        stat = 'p', 'padj', or 'f'
        '''
        if stat == 'p':
            p_table = self.p
        elif stat == "padj":
            p_table = self.padj
        elif stat == 'f':
            p_table = self.stat
        figure = plot_spatial_stat_heatmap(p_table = p_table, 
                                  vmin = 0, 
                                  vmax = 7)
        
        if filename is not None:
            figure.savefig(self.SpaceANOVA.output_dir + "/" + filename + ".png", bbox_inches = "tight")
        
        return figure

    def do_edt(self, 
               pixel_classifier_folder: str, 
               masks_folder: str, 
               maps: str = "/classification_maps",
               smoothing: int = 10, 
               stat: str = 'mean', 
               normalized: bool = True, 
               background: bool = False,
               marker_class: Union[str, None] = 'spatial_edt', 
               auto_panel: bool = True,
               output_edt_folder: Union[None, str, Path] = None,
               save_path: Union[None, str, Path] = None):
        '''
        Calculates the euclidean distance between cell masks (provided in masks_folder) and matching pixel classifications (pixel_classifier_folder).
        This appends the calculated edt for each cell to self.exp.data, as a new 'channel' / 'antigen', where it can then be used for plotting & calculations.

        Args:
            pixel_classifier_folder (str): 
                the path to a PalmettoBUG-generated pixel classifier folder. This folder needs to contain a subfolder of .tiffs
                containing the pixel class predictions (see maps argument), and contain a biological_labels.csv indicating what the biological
                names of each class in the classifier are.
                When a pixel classifier with > 1 predicted pixel class is used, an edt statistic will be calculated separately for each and added to
                self.exp.data

            masks_folder (str): 
                the path to a folder containing a set of .tiff files of cell segmentation masks. These .tiffs should match those in 
                f'{pixel_classifier_folder}/{maps}'.

            maps (str): 
                should be either "/classification_maps" or "/merged_classification_maps". This determines which subfolder from pixel_classifier_folder
                that contains the .tiff files of the pixel classification maps to usea for calculating the distance from. The filenames of these .tiffs
                should match those in masks_folder

            smoothing (int): 
                If == 0, no smoothing is performed. Otherwise this indicates the size of isolated pixel class regions to smooth out before
                calculating distances. As in, if smoothing == 10 (default) regions of a pixel class smaller than 10 pixels will be dropped and "smoothed"
                into the surrounding pixel classes using mode-based fill-in (the mode of the remaining, closest neighbor pixels will be used to assign the replacement 
                value for dropped pixels). 
                Why smooth? When calculating the distance form a pixel class using the Euclidean Distance Transform (EDT), very small pixel regions can have an outsized
                impact on the final EDT map, so removing spurious / small regions can help clean up the final calculation.

            stat (str): 
                One of "mean", "median", or "minimum". This determines what statistic is read off of each segmentation region when calculating the edt value
                for each cell. The default, "mean", is the most common use, and represents the average distance from the pixel class across the whole cell's spatial
                footprint. "min" means that the calculated value for each cell with just be its minimum distance to the class of interest (its closest point).
                Of note, when "min" is the selected statistic, normalization cannot be performed (see f0ollowing argument). 

            normalized (bool): 
                Whether to normalize (True) or not (False). In this case, normalization means dividing each cell's determined edt value by the average of the 
                image that cell is in. As in, if "median" statistic is selected with normalized = True, each cell's edt value will be:

                    cell_stat = median(cell_edt) / median(image_edt)

                instead of the non-normalized value:

                    cell_stat = median(cell_edt)

                When "mean" is used as a statistic, then the normalization factor is the mean of the image's edt values. Normalization cannot be calculated this way
                with a statistic is "min", and so is ignored (there is no normalization for "min").

                Normalization is useful as it is a way to help correct for the abundance of the pixel class. As in, if one image is 70% within a pixel class (lets say
                the pixel class is for fibrotic regions) its edt distances will be much lower across the image than an image where only 30% of the image is the fibrotic class. 
                This would make all cells - regardless of cell type - in image 1 have much lower edt values than the cells in image 2, which would not be an inaccurate 
                conclusion (the cells in image 1 are genuinely closer to fibrotic regions), but introduces a confounding factor: have the cells moved towards the fibrosis, or 
                has the fibrotic regions expanded?
                Normalization helps address this, in part, as it takes into account the total quantity & positioning of the pixel class in each image when calculating
                the edt value for each cell.

            background (bool): 
                whether to include the 'background' class in the edt calculations (True) or not (False, default). Usually, the background class is ignored,
                because it is not biologically relevant, but in some situations there is effectively no background class / even the background is biologically meaningful.
                For example, if a classifier is trained to identify broad tissue regions in a sample (such as intestinal crypt lumen / epithelia / lamina propia in a 
                colon section), it might be the case that every part of the image falls into one of the pixel classes and there is no 'background'. 
                Because of how supervised classifier's are trained in PalmettoBUG, a background class is always created so this option is useful if that 'background'
                is actually a relevant grouping.

            marker_class (str or None): 
                what marker_class (self.exp.data.var['antigen']) to assign the edt columns when they are added to self.exp.data.X. By default,
                this is "spatial_edt", as it helps the subsequent plottting functions easily find the edt channels while ignoring the other marker_classes.
                However, setting this to "type" / "state" / "none" is also allowed, if you want to perform plots / calculations that combine both the spatial edt
                data and other channels. 

            auto_panel (bool): 
                Whether to automatically add the channels to self.exp.data (True, default), or only to return a panel dataframe (for manually editing
                marker_class, say if you want to assign different edt statistics from a single classifier to different marker_class-es). If False, you will 
                need to manually add the edt data to self.exp.data with self.edt.append_distance_transform(distances_panel = {your edited marker_class panel}).

            output_edt_folder (None, string, or Path): 
                Default is None (no edt map export). If not None, then should be the path where folders of .tiff files can be
                exported. Specifically, the folders used will be the f'{output_edt_folder}_{class_biological_label}' for each class in the classifier.
                The saved .tiff files will be the intermediate Euclidean distances transforms for that class, from which the stats for each cell mask were calculated.

            save_path (None, string, or Path): 
                Default is None (edt valuesa re not saved). If not None, then should be a file path where a csv file can be written.
                This csv will contain the information for all the edt's calculated for the provided pixel classifier / masks pairing. 
                Note that marker_class information will not be saved (that will need to be set again on re-load of the saved edt values)

        Returns:
            a pandas dataframe (panel) which can be used to see or set the marker_class information

            a pandas dataframe (self.edt.results) which contains the edt calculations for every cell and pixel class
        '''
        panel = self.edt.load_distance_transform(pixel_classifier_folder =  pixel_classifier_folder, masks_folder = masks_folder, maps = maps, 
               smoothing = smoothing, stat = stat, normalized = normalized, background = background, marker_class = marker_class, 
               auto_panel = auto_panel, output_edt_folder = output_edt_folder, save_path = save_path)
        return panel, self.edt.results

    def do_reload_edt(self, dataframe, marker_class):
        '''
        Loads a column of data into the anndata of the experiment (meant for saved edt information, but could be used for any type of channel)
        '''
        if not isinstance(dataframe, pd.DataFrame):
            dataframe = pd.read_csv(str(dataframe))
        self.edt.reload_edt(dataframe = dataframe, marker_class = marker_class)

    def plot_edt_heatmap(self, groupby_col, marker_class = "spatial_edt", filename = None):
        '''
        Plots a heatmap for spatial edt -- default marker_class is spatial_edt, and export folder (if filename is provided) is in /Spatial_plots
        '''
        if filename is not None:
            plot = self.edt.plot_edt_heatmap(groupby_col = groupby_col, 
                                         marker_class = marker_class, 
                                         filename = self.SpaceANOVA.output_dir + "/" + filename + ".png")
        else:
            plot = self.edt.plot_edt_heatmap(groupby_col = groupby_col, 
                                         marker_class = marker_class, 
                                         filename = None)
        return plot

    def plot_edt_boxplot(self, var_column, groupby_col = 'merging', facet_col = 'condition', col_num = 3, filename = ''):
        '''
        Plots a channel on a horizontal boxplot. Could be used for non-spatial_edt data, but export folder (if a filename is provided)
        is in /Spatial_plots.

        Args:
            var_column (str): 
                the channel to use for the plots. Usually a spatial edt channel (like 'distance to Vimentin'), but could be
                any of the channels in self.exp.data.var['antigen']

            groupby_col (str): 
                the column in self.exp.data.obs that will be used to gruop the box plot (one box per unique value in this column, per facet)

            facet_col (str): 
                the column in self.exp.data.obs that will be used to split the data into two boxplots. Usually (and by default) facetted on 
                the condition column, for comparison of treatment vs. control

            col_num (int): 
                the number of columns of facets before they begin to wrap. As in, with the default of col_num = 3, then the fourth facet
                will be on the second row of the facet grid.

            filename (str): 
                the name to the save a .png file of the plot unde rin /Spatial_plots. If not provided (default value), the plot will not be 
                written to the disk.

        Returns:
            matplotlib.figure (the boxplot)
        '''
        if filename != '':
            plot = self.edt.plot_horizontal_boxplot(var_column = var_column, 
                                                subset_col = groupby_col, 
                                                facet_col = facet_col, 
                                                col_num = col_num, 
                                                filename = self.SpaceANOVA.output_dir + "/" + filename + ".png")
        else:
            plot = self.edt.plot_horizontal_boxplot(var_column = var_column, 
                                                subset_col = groupby_col, 
                                                facet_col = facet_col, 
                                                col_num = col_num, 
                                                filename = '')
        return plot

    def run_edt_statistics(self, groupby_column, marker_class = "spatial_edt", statistic = "mean", test = "anova", filename = None):
        '''
        A wrapper on do_state_exprs from the Analysis class, but with the default marker_class of 'spatial_edt', and a output folder
        in /Spatial_plots
        '''
        if filename is not None:
            filename = self.SpaceANOVA.output_dir + "/" + filename + ".csv"
        df = self.edt.plot_edt_statistics(groupby_column = groupby_column, 
                                          marker_class = marker_class, 
                                          statistic = statistic, 
                                          test = test, 
                                          filename = filename)
        return df

class SpatialEDT:
    '''
    
    '''
    def __init__(self):
        pass

    def add_Analysis(self, Analysis_object):
        '''
        '''
        self.exp = Analysis_object

    def load_distance_transform(self, 
                                pixel_classifier_folder: Union[str, None], 
                                masks_folder: Union[str, None], 
                                maps: (str) = "/classification_maps",
                                smoothing: int = 10, 
                                stat: str = 'mean', 
                                normalized: bool = True, 
                                background: bool = False,
                                marker_class: Union[str, None] = 'spatial_edt', 
                                auto_panel: bool = True,
                                output_edt_folder: Union[None, str, Path] = None,
                                save_path: Union[None, str, Path] = None):
        '''
        Loads a distance transform statistic using a folder of masks (should match self.input_mask_folder, if available) and a folder of pixel classifications.
        The distance transform statistic is added for every cell in the dataset & can be treated like an additional antigen -- if marker_class == "type", then
        it can be used in clustering with the rest of the type markers, for example.
        '''
        distance_transforms = pd.DataFrame()   
        class_maps = pixel_classifier_folder + maps
        if marker_class is None:
            marker_class = "state"

        biological_labels = pd.read_csv(pixel_classifier_folder + "/biological_labels.csv")
        if maps == "/merged_classification_maps":
            if not os.path.exists(pixel_classifier_folder + "/merged_classification_maps"):
                merge_folder(pixel_classifier_folder + "/classification_maps",
                            pd.read_csv(pixel_classifier_folder + "/biological_labels.csv"),
                            pixel_classifier_folder + "/merged_classification_maps")
            zipper = zip(biological_labels['labels'].unique(), biological_labels['merging'].unique())
        elif maps == "/classification_maps":
            zipper = zip(biological_labels['labels'], biological_labels['class'])
        else:
            print("ERROR! maps must be either '/classification_maps' or '/merged_classification_maps' ! ")
            raise(ValueError)

        available_file_names = list(self.exp.data.obs['file_name'].unique())

        for i,ii in zipper:
            if ((i != "background") or (background is True)) and (ii != 0):
                if output_edt_folder is not None:
                    output_edt_folder = output_edt_folder + f"_{i}"
                distances = spatial_by_edt_folder(masks_folder, 
                                                  class_maps, 
                                                  available_file_names = available_file_names,
                                                  class_of_interest = ii, 
                                                  stat = stat, 
                                                  normalized = normalized, 
                                                  smoothing = smoothing,
                                                  output_edt_folder = output_edt_folder)
                distance_transforms[f'distance to {i}'] = distances[0]

        if save_path is not None:
            distance_transforms.to_csv(str(save_path), index = False)
        self.results = distance_transforms
        # print(self.results)
        # print(self.exp.data.obs)

        if len(distance_transforms) != len(self.exp.data.obs):
            if self.exp._in_gui: 
                tk.messagebox.showwarning("Warning!", message = "Distance edt data and currently loaded data do not match in length!"
                                           "\nAborting distances load. Did you use the same masks folder for distances calculations and for segmentation, \n"
                                           "Or have you edited that masks folder since starting this experiment (creating a mismatch in the number of \n"
                                           "masks in that folder and number cell events in the loaded analysis)?")
            else:
                print("Distance edt data and currently loaded data do not match in length!"
                      "\nAborting distances load. Did you use the same masks folder for distances calculations and for segmentation, \n"
                      "Or have you edited that masks folder since starting this experiment (creating a mismatch in the number of \n"
                      "masks in that folder and number cell events in the loaded analysis)?")
            return
        self.exp._distance_edt_data = distance_transforms
        if self.exp._in_gui: 
            self.exp.logger.info(f"Performed first step of adding distance transform edt data"
                            f"\n pixel_classifier = {pixel_classifier_folder}, masks = {masks_folder}, smoothing = {str(smoothing)}") 
            
        distances_panel = pd.DataFrame()
        distances_panel['fcs_colnames'] = distance_transforms.columns
        distances_panel['antigen'] = distance_transforms.columns
        distances_panel['marker_class'] = marker_class
        distances_panel.to_csv(self.exp.directory + '/distances_edt_panel.csv', index = False) 
        if auto_panel:
            self.append_distance_transform(distances_panel = distances_panel) ## specifying distances panel in this call overwrites any prior panel
        return distances_panel
    
    def append_distance_transform(self, distances_panel: Union[str, pd.DataFrame, None] = None):
        ''' 
        Adds a distance transform statistic loaded by load_distance_transform to self.data so that it can be accessed.
        '''
        if distances_panel is None:
            self.distances_panel = pd.read_csv(self.exp.directory + '/distances_edt_panel.csv')
        else:
            if isinstance(distances_panel, pd.DataFrame):
                self.distances_panel = distances_panel
            else:
                self.distances_panel = pd.read_csv(str(distances_panel))

        self.distances_panel.index = self.distances_panel['antigen']

        for i in self.exp.data.var['antigen']:         ## prevent duplicate columns by removing any prior columns/antigens that match any of the names of the new columns being added
            if i in self.exp._distance_edt_data.columns:
                slicer = self.exp.data.var['antigen'] != i
                self.exp.data = self.exp.data[:, slicer]
                self.exp.panel = self.exp.panel[slicer]

        self.exp.panel = pd.concat([self.exp.panel, self.distances_panel], axis = 0)

        if self.exp.unscaled_data is None:
            new_X  = np.concatenate((self.exp.data.X.copy(), np.array(self.exp._distance_edt_data)), axis = 1)
            self.exp.data = ann.AnnData(X = new_X, 
                                        var = self.exp.panel, 
                                        varm = self.exp.data.varm, 
                                        varp = self.exp.data.varp,
                                        obs = self.exp.data.obs, 
                                        obsm = self.exp.data.obsm, 
                                        obsp = self.exp.data.obsp, 
                                        uns = self.exp.data.uns)
        else:
            new_X  = np.concatenate((self.exp.unscaled_data.copy(), np.array(self.exp._distance_edt_data)), axis = 1)
            self.exp.unscaled_data = new_X.copy()
            self.exp.data = ann.AnnData(X = new_X, 
                                        var = self.exp.panel, 
                                        varm = self.exp.data.varm, 
                                        varp = self.exp.data.varp,
                                        obs = self.exp.data.obs, 
                                        obsm = self.exp.data.obsm, 
                                        obsp = self.exp.data.obsp, 
                                        uns = self.exp.data.uns)
            self.exp.do_scaling(scaling_algorithm = self.exp._scaling, upper_quantile = self.exp._quantile_choice)       

        if self.exp._in_gui: 
            self.exp.logger.info("Appended distance transform edt data") 

    def reload_edt(self, dataframe, marker_class):
        '''
        '''
        self.exp._distance_edt_data = dataframe
        distances_panel = pd.DataFrame()
        distances_panel['fcs_colnames'] = dataframe.columns
        distances_panel['antigen'] = dataframe.columns
        distances_panel['marker_class'] = marker_class

        if len(dataframe) != len(self.exp.data.obs):
            if self.exp._in_gui: 
                tk.messagebox.showwarning("Warning!", message = "Distance edt data and currently loaded data do not match in length!"
                                           "\nAborting distances load. Did you use the same masks folder for distances calculations and for segmentation, \n"
                                           "Or have you edited that masks folder since starting this experiment (creating a mismatch in the number of \n"
                                           "masks in that folder and number cel events in the loaded analysis)?")
            else:
                print("Distance edt data and currently loaded data do not match in length!"
                      "\nAborting distances load. Did you use the same masks folder for distances calculations and for segmentation, \n"
                      "Or have you edited that masks folder since starting this experiment (creating a mismatch in the number of \n"
                      "masks in that folder and number cell events in the loaded analysis)?")
            return
        self.append_distance_transform(distances_panel = distances_panel) ## specifying distances panel in this call overwrites any prior panel
        return distances_panel

    def plot_horizontal_boxplot(self,
                                var_column: str, 
                                subset_col: str = 'merging', 
                                facet_col: str = 'condition', 
                                col_num: int = 3, 
                                filename: str = ''):
        '''
        This function is for plotting the dstirubtion of values in a single column in an anndata object.
    
        Args:
            var_column (string): a unique value in anndata.var['antigen'] that denotes whivh column of anndata.X to use

            subset_col (string):  the name of a column in anndata.obs that will be used to subset the data into columns

            facet_col (string): the name of a column in anndata.obs that will be used to facet the plot into multiple panel (usually by experimental condition)

            col_num (integer): the number of columns of the plot panels

            filename (string): if not '', the FULL filepatth where the plot will be saved 
    
        Returns:
            maptlotlib.pyplot figure (the horizontal boxplot)
    
        I/O:
            Outputs: a file at the full filepath [filename], this is the saved version of the returned matplotlib.pyplot figure -- it is usually a .png file.
        '''
        anndata = self.exp.data.copy()
        df = anndata.obs
        df[var_column] = list(np.squeeze(anndata.X[:,anndata.var['antigen'] == var_column]))
        
        facet_num = len(df[facet_col].unique())
        if facet_num == col_num:
            col_num -= 1
    
        row_num = (facet_num // col_num) + 1 
        if (facet_num % col_num) == 0:
            row_num -= 1
        
        figure, axs = plt.subplots(row_num, col_num, sharey = True, sharex = True, figsize = (11,11))
        
        for ii,i in enumerate(df[facet_col].unique()):
            to_plot = df[df[facet_col] == i]
            to_plot.loc[:,subset_col] = to_plot[subset_col].astype('str')
            ax = axs.ravel()[ii]
            if subset_col != "None":
                sns.boxplot(to_plot, x = var_column, y = subset_col, orient = "h", ax = ax)
            else:
                sns.boxplot(to_plot, x = var_column, orient = "h", ax = ax)
            ax.set_title(i)
            
        ii += 1
        while (len(axs.ravel()) - ii) > 0:
            axs.ravel()[ii].set_axis_off()
            ii += 1
            
        if (filename != '') and (filename is not None):
            figure.savefig(filename, bbox_inches = 'tight')
        plt.close()
        return figure


    def plot_edt_heatmap(self, groupby_col, marker_class = "spatial_edt", filename = None):
        '''
        This is just a wrapper on pbug.Analysis.plot_medians_heatmap, where the default marker_class is "spatial_edt"
        '''
        figure = self.exp.plot_medians_heatmap(marker_class = marker_class, groupby = groupby_col)
        if filename is not None:
            figure.savefig(filename, bbox_inches = "tight")
        plt.close()
        return figure


    def plot_edt_statistics(self, groupby_column, marker_class = "spatial_edt", statistic = "mean", test = "anova", filename = None):
        '''
        This is just a wrapper on pbug.Analysis.do_state_exprs_ANOVAs, where the default marker_class is "spatial_edt"
        '''
        stat_df = self.exp.do_state_exprs_ANOVAs(groupby_column = groupby_column, 
                                                 marker_class = marker_class,
                                                 statistic = statistic,
                                                 test = test)
        if filename is not None:
            stat_df.to_csv(filename, index = False)
        return stat_df

def spatial_by_edt_folder(masks_folder: Union[str, Path], 
                          class_map_folder: Union[str, Path], 
                          available_file_names = None,
                          class_of_interest: int = 2, 
                          do_all_classes: int = 0, 
                          stat: str  = "mean", 
                          normalized: bool  = True, 
                          smoothing: int  = 0,
                          output_edt_folder: Union[None, str, Path] = None) -> list[list[float]]:
    '''
    from a folder of cell masks and amatching folder of pixel classifications, calculates a distance transform statistic for every cell in the data.
    This list of distance transform statistics can then be easily added to an anndata object containing read outs from the matching cells.

    Args:
        masks_folder (string or Path): the filepath to a folder containing the masks to be used in the calculation

        class_map_folder (string or Path): the filepath to a folder containing the pixel classifications to be used in the calculation

        class_of_interest (integer): (only if do_all_classes == 0) which class to calculate distance transform statistics for

        do_all_classes (integer): either 0 (when only the class_of_interest will be used) or a number indicating how many pixel classes to use from the 
                classifier (the first X classes will have distance transform stats calculated where X = do_all_classes)

        stat (integer): which statistic to calculate -- "mean" will calculate the mean euclidean distance transform value in each mask
                "median" will calculate the median value, and "min" the minimum. 

        normalized (boolean): whether to normalize the results of each mask. Only if stat != "min". As in, instead of reporting the raw
                average euclidean distance transform value within each mask, will report that value divided by the average of the image 
                that mask was in 

                        --> mean(edt_of_mask) / mean(edt_of_image) -- or median / median as the case may be

                this helps reduce the effect of some images containing substantially more of the pixel class

        smoothing (integer): a number indicating a threshold. Isolated regions of pixel class smaller than this number will be "smoothed" out (dropped to 
                zero, then their values replaced by the mode of the remaining, surrounding pixels). Effectively removes small regions in the pixel classification
                with the goal of removing spurious classifications. Particularly can be important for these distance transforms, as even a single isolated pixel in the 
                class of interest can create a large circular region of lower edt values.
                If no smoothing is desired, set this parameter == 0.

        output_edt_folder (None, string, or Path): If not None, then should be a file path to a folder where the edt maps can be exported. If None, edt maps are not exported.

    Returns:
        a list of lists of floats -- each sublist is the spatial transform for the full data for one of the pixel classes in the selected classifier
                if only one class is selected, then this will be a list containing a single sublist -- which will be as long as the data set (one float / distance
                statistic per cell)
    '''
    masks_folder = str(masks_folder)
    class_map_folder = str(class_map_folder)
    if output_edt_folder is not None:
        if not os.path.exists(output_edt_folder):
            os.mkdir(output_edt_folder)
    edt_list = []
    masks = [masks_folder + "/" + i for i in sorted(os.listdir(masks_folder))]
    class_maps = [class_map_folder + "/" + i for i in sorted(os.listdir(class_map_folder))]
    #print(available_file_names)
    if available_file_names is not None:
        masks = [i for i,ii in zip(masks, sorted(os.listdir(masks_folder))) if f"{ii[:ii.rfind('.')]}.fcs" in available_file_names]
        #print(masks)
        class_maps = [i for i,ii in zip(class_maps, sorted(os.listdir(class_map_folder))) if f"{ii[:ii.rfind('.')]}.fcs" in available_file_names]  
        masks.sort()
        class_maps.sort()     
        #print(class_maps)
        
    for iii, (i,ii) in enumerate(zip(masks, class_maps)):
        mask = tf.imread(i).astype('int')
        class_map = tf.imread(ii).astype('int')
        if output_edt_folder is not None:
            output_edt_path = output_edt_folder + f"/{i[i.rfind('/'):]}"
        else:
            output_edt_path = None
        if do_all_classes != 0:
            for i in range(0,do_all_classes,1):
                if iii == 0:
                    edt_list.append([])
                edt_list[iii] = edt_list[iii] + _spatial_by_edt(mask, class_map, 
                                                                class_of_interest = i, 
                                                                stat = stat, 
                                                                normalized = normalized, 
                                                                smoothing = smoothing, 
                                                                output_edt_path = output_edt_path)
        else:
            if iii == 0:
                edt_list.append([])
            edt_list[0] = edt_list[0] + _spatial_by_edt(mask, 
                                                        class_map, 
                                                        class_of_interest, 
                                                        stat = stat, 
                                                        normalized = normalized, 
                                                        smoothing = smoothing, 
                                                        output_edt_path = output_edt_path)
    return edt_list

def _spatial_by_edt(mask: np.ndarray[int], 
                    class_map: np.ndarray[int], 
                    class_of_interest: int, 
                    stat: str = 'mean', 
                    normalized: bool = True, 
                    smoothing: int = 0,
                    output_edt_path: Union[None, str, Path] = None):
    '''
    helper for spatial_by_edt_folder. From the provided numpy arrays representing the pixel classification & mask, calculates a distance transform statistic for each cell
    '''
    edt_list = []
    if smoothing > 0:
        max = np.max(class_map)
        #class_map[class_map == 0] = max + 1
        class_map = smooth_isolated_pixels(class_map, 
                                           class_num = max, 
                                           threshold = smoothing, 
                                           mode_mode = "dropped_image", 
                                           fill_in = False,
                                           warn = False)
        #class_map[class_map == max + 1] = 0
    class_map = (class_map != class_of_interest).astype('int') 
    edt_map = scipy.ndimage.distance_transform_edt(class_map)
    if output_edt_path is not None:
        output_edt_path = str(output_edt_path)
        tf.imwrite(output_edt_path, edt_map)
        
    if (stat == "mean") and (normalized is True):
        for j in skimage.measure.regionprops(mask, edt_map):
            edt_list.append(np.nan_to_num(j.intensity_mean / np.mean(edt_map), 0))
    elif (stat =="mean") and (normalized is False):
        for j in skimage.measure.regionprops(mask, edt_map):
            edt_list.append(j.intensity_mean)

    elif (stat == "median") and (normalized is False):
        for j in skimage.measure.regionprops(mask, edt_map):
            edt_list.append(np.median(j.image_intensity))
    elif (stat == "median") and (normalized is True):
        for j in skimage.measure.regionprops(mask, edt_map):
            edt_list.append(np.nan_to_num(np.median(j.image_intensity) / np.median(edt_map), 0))

    elif stat == "min":
        for j in skimage.measure.regionprops(mask, edt_map):
            edt_list.append(j.intensity_min)

    return edt_list


class SpatialNeighbors:        ## formerly SquipySpatial
    '''
    This class coordinates primarily squidpy-based neighborhood analysis options, such as neighborhood enrichment, cellular neighborhood groupings, etc.

    Key Attributes:
        self.exp (PalmettoBUG.Analysis): the analysis object containing the data 

        self.exp.data (anndata): the primary anndata object on which scanpy and squidpy operations are performed. It tends to get edited-in-place by many 
                of the methods, which can be useful when using an anndata object shared with an instance of pbug.Analysis(.data)

        self.save_dir, self.save_cell_maps_dir (string): paths to standard locations where plots are / can be saved

        self.masks_paths (list of strings): a list of full filepaths to the mask file that corespond to the data in self.data. For example, self.data.obs['file_name'] should 
                contain matching filenames (but not FULL file paths) to those in this list.

    '''
    def __init__(self):
        self.data = None

    def add_Analysis(self, Analysis):
        ''''''
        self.exp = Analysis
        masks_path = self.exp.input_mask_folder
        save_directory = (self.exp.directory + "/Spatial_plots") 
        self.save_dir = str(save_directory)
        if not os.path.exists(self.save_dir):
            os.mkdir(self.save_dir)
        self.save_cell_maps_dir = self.save_dir + "/cell_maps"
        if not os.path.exists(self.save_cell_maps_dir):
            os.mkdir(self.save_cell_maps_dir)
        self.masks_paths = [masks_path + "/" + i for i in os.listdir(str(masks_path))]

    def do_neighbors(self, radius_or_neighbors: str, number: int):
        '''
        Wrapper for squidpy.gr.spatial_neighbors --> preformed on self.exp.data using the provided radius and n_neighbors
        '''
        if radius_or_neighbors == "Radius":
            sq.gr.spatial_neighbors(self.exp.data, coord_type = "generic", library_key = "sample_id", radius = number)
        elif radius_or_neighbors == "Neighbors":
            sq.gr.spatial_neighbors(self.exp.data, coord_type = "generic", library_key = "sample_id", n_neighs = number)
        else:
            print(f"radius_or_neighbors must be either 'Radius' or 'Neighbors', but instead was {radius_or_neighbors}")

    def do_cellular_neighborhoods(self, 
                                  clustering: str = "merging", 
                                  leiden_or_flowsom: str  = "FlowSOM", 
                                  n_clusters = 20,
                                  seed: int  = 42, 
                                  resolution: float  = 1.0, 
                                  min_dist: float  = 0.1, 
                                  n_neighbors: int  = 15,
                                  flavor = "leidenalg", 
                                  plot_filename: Union[None, str] = None,
                                  **kwargs):
        '''
        Performs either FlowSOM-based or Leiden-based clustering of cells into cellular neighborhoods.

        Args:
            clustering (str): the cell metadata column (in self.exp.data.obs) used as input for the chosen clustering algorithm. As in, every cells' neighbors for each 
                    category in this metadata column is counted and a % is derived. This % neighboring cell types is tehn passed into the clustering
                    algorithm.

            leiden_or_flowsom (str): One of two strings -- "FlowSOM" or "Leiden" -- determines which algorith m is used to cluster the cells

            n_clusters (int): FLOWSOM only! -- the number of metaclustering to return at the end of the algorithm

            seed (int): random seed for reproducibility

            resolution (float): (leiden only) the resolution of the leiden clustering. High numbers tend to increase the number of cluster found
                    while lower numbers reduce the number of clusters found

            min_dist (float):  (leiden only) the minimum distance for the UMAP performed alongside the leiden clustering (I think this does not effect the leiden, but
                    does affect the UMAP secondary output.)

            n_neighbors (integer): (leiden only) this is used in scanpy.pp.neighbors() call of the %neighboring cell types data, which precedes leiden clustering

            **kwargs: (FlowSOM only) these keyword arguments are passed into the FlowSOM algorithm. arguments like rlen, etc. are commonly used.

        Returns:
            matplotlib.pyplot figure (UMAP for Leiden clustering, Minimum Spanning Tree / "starplot" for FlowSOM)

        Edits-in-place:
            self.exp.data: adds a 'CN' column in self.exp.data.obs, with the calculated cellular neighborhood groupings. 
        '''
        ### requires self.do_neighbors() first
        unique_clusters = self.exp.data.obs[clustering].unique()
        special_category = pd.CategoricalDtype(categories = unique_clusters, ordered = True)
        my_anndata = self.exp.data.copy()
        final_array = np.zeros([len(my_anndata), len(unique_clusters)])
        offset = 0
        for j in my_anndata.obs['sample_id'].unique():
            temp_anndata = my_anndata[my_anndata.obs['sample_id'] == j].copy()
            dense = temp_anndata.obsp['spatial_connectivities'].todense()
            for ii,i in enumerate(dense):
                cell_neighbor_types = pd.DataFrame(temp_anndata.obs.loc[np.array(i == 1).squeeze(), clustering].astype(special_category)).reset_index()
                percentages = np.array(cell_neighbor_types.groupby(clustering, observed = False).count() / len(cell_neighbor_types))
                final_array[ii + offset,:] = percentages.squeeze()
            offset += len(dense)
        final_array = np.nan_to_num(final_array, 0)
        var = pd.DataFrame()
        var['antigen'] = my_anndata.obs[clustering].unique()
        var.index = var['antigen']
        new_anndata = ann.AnnData(final_array, var = var)
        if leiden_or_flowsom.lower() == "flowsom":
            self.neighbors_flowsom = FlowSOM(new_anndata, seed = seed, n_clusters = n_clusters, **kwargs) 
                                    ## TODO: also need to unpack the new clustering into self.exp.data --> and from there into the main Analysis.data object (likely?)
            self.exp.data.obs['CN'] = list(self.neighbors_flowsom.get_cell_data().obs['metaclustering'])
            self.exp.data.obs['CN'] = self.exp.data.obs['CN'].astype('int') + 1
            figure = self._plot_stars_CNs()
            figure.subplots_adjust(top = 1, left = 0, bottom = 0)
            figure.suptitle("Cell Neighborhood FlowSOM Minimum Spanning Tree")
        

        elif leiden_or_flowsom.lower() == "leiden":
            rn_gen = np.random.default_rng(seed = seed)
            new_anndata.X = new_anndata.X + (rn_gen.random(new_anndata.X.shape) / 100)     ## Mind the eigengap
            sc.pp.neighbors(new_anndata, n_neighbors = n_neighbors, random_state = seed)
            sc.tl.umap(new_anndata, 
                        min_dist = min_dist, 
                        random_state = seed)
            sc.tl.leiden(new_anndata, 
                        resolution = resolution, 
                        random_state = seed,
                        flavor = flavor, 
                        n_iterations = 2)
            new_anndata.obs['leiden'] = new_anndata.obs['leiden'].astype('int') + 1
            new_anndata.obs['leiden'] = new_anndata.obs['leiden'].astype('category')
            self.exp.data.obs['CN'] = list(new_anndata.obs['leiden'])
            figure = plt.figure()
            ax = plt.gca()
            sc.pl.umap(new_anndata, color = "leiden", show = False, ax = ax)
            figure.suptitle("Leiden clustering of neighborhoods defined by % cell types")
            plt.close()
        if plot_filename is not None:
            figure.savefig(self.save_dir + "/" + plot_filename + ".png", bbox_inches = "tight") 
        return figure
        
    def plot_CN_heatmap(self, clustering_col: str = "merging", **kwargs):
        '''
        Plots a heatmap of the percent of {clustering_col} cells in each cellular neighborhood (CN). Useful for identifying what each CN is
        '''
        data = self.exp.data.copy()
        data.obs['CN'] = data.obs['CN'].astype('category')
        towards_percents = data.obs.groupby(['CN', clustering_col], observed = False).count().reset_index()
        cluster_df = pd.DataFrame()
        for ii,i in enumerate(towards_percents['CN'].unique()):
            subset = towards_percents[towards_percents['CN'] == i]
            if ii == 0:
                cluster_df[clustering_col] = subset[clustering_col]
            cluster_df[i] = list(subset['sample_id'] / subset['sample_id'].sum())

        cluster_df.index = cluster_df[clustering_col]

        def min_max(array):
            return (array - array.min()) / (array.max() - array.min())
        
        to_plot_df = cluster_df.drop(clustering_col, axis = 1).apply(min_max, axis = 1)
        to_plot_df = to_plot_df.T.reset_index()
        to_plot_df['CN cluster'] = to_plot_df['index']
        to_plot_df.index = to_plot_df['CN cluster']
        to_plot_df = to_plot_df.drop(['CN cluster', 'index'], axis = 1)
        figure = sns.clustermap(to_plot_df, xticklabels = 1, yticklabels = 1, **kwargs)
        figure.figure.suptitle('Scaled Percent of each celltype within each Cellular Neighborhood cluster')
        plt.close()
        return figure.figure

    def plot_CN_abundance(self, clustering_col, cols = 3):
        '''
        Plot the abundance of the celltypes (determined by clustering_col) in each cellular neighborhood
        '''
        data = self.exp.data.copy()
        data.obs['CN'] = data.obs['CN'].astype('category')
        towards_abundance = data.obs.groupby(['CN', clustering_col], observed = False).count().reset_index()
        facets = len(towards_abundance['CN'].unique())
        if int(facets) == int(cols):
            cols -= 1    ## automatically reshape if it is too small

        rows = (facets // cols) + 1            ## + 1 because the // operation rounds down
        if (rows == 1) and (cols > 2):
            cols -= 1  
            rows = (facets // cols) + 1  

        if int(facets % cols) == 0:
            rows = rows - 1   ## avoid a blank row at the end
        figX = cols * 2.35
        figY = rows * 1.9
        figure, axs = plt.subplots(rows, 
                                   cols, 
                                   sharex = True, 
                                   sharey = True, 
                                   figsize = (figX, figY))
        axs = axs.ravel()
        for i,ii in enumerate(towards_abundance['CN'].unique()):
            slice_df = towards_abundance[towards_abundance['CN'] == ii].copy()
            slice_df['% in neighborhood'] = slice_df['sample_id']
            sns.barplot(x = slice_df[clustering_col], 
                        y = (slice_df['% in neighborhood'] / slice_df['sample_id'].sum()) * 100, ### just need a column that consistently is in self.exp.data.obs
                        ax = axs[i])   
            axs[i].set_title(str(ii))
            axs[i].tick_params("x", labelrotation = 90)
        
        i += 1
        while len(axs) > i:
            axs[i].set_axis_off()
            i += 1

        figure.suptitle('Percentage of each celltype in the cellular Neighborhood clusterings')
            
        return figure

    def _plot_stars_CNs(self, filename: Union[str, None] = None):
        '''
        Plots the minimum spanning tree / star plot from the FlowSOM package
        '''
        figure = plot_stars(self.neighbors_flowsom, 
                         markers=None, 
                         background_values = self.neighbors_flowsom.get_cluster_data().obs['metaclustering'], 
                         title=None)
        figure.set_size_inches(18,18)
        sns.move_legend(figure.axes[0], loc = 'lower right')
        if filename is not None:
            figure.savefig(self.save_dir + "/" + filename, bbox_inches = "tight") 
        plt.close()
        return figure

    def plot_neighborhood_enrichment(self, clustering = "merging", facet_by = "condition", col_num = 1, seed = 42, n_perms = 1000, filename = None):
        '''
        Plots neighborhood enrichment scores for the chosen [clustering]. Can be facetted using [facet_by] to compare things like condition
        '''
        data = self.exp.data.copy()
        data.obs[clustering] = data.obs[clustering].astype('category')
        sq.gr.nhood_enrichment(data, cluster_key = clustering, show_progress_bar = False, seed = seed, n_perms = n_perms)
        if facet_by != "None":
            conditions = data.obs[facet_by].unique()
            condition_num = len(conditions)
            if condition_num < 2:
                facet_by = None
                figure = plt.figure()
                ax = plt.gca()
            else:
                if (condition_num + 1) % col_num > 0:
                    row_num = ((condition_num + 1) // col_num) + 1
                else:
                    row_num = (condition_num + 1) // col_num
                figure, axs = plt.subplots(row_num, col_num, sharey = True, figsize = (col_num * 6, row_num * 4))
                axs = axs.ravel()
                ax = axs[0]
        else:
            figure = plt.figure()
            ax = plt.gca()
        sq.pl.nhood_enrichment(data, cluster_key = clustering, cmap = 'coolwarm', ax = ax, fontsize = 10)

        if facet_by != "None":
            for ii,i in enumerate(conditions):
                ax = axs[ii + 1]
                condition_anndata = data[data.obs[facet_by] == i].copy()
                sq.gr.nhood_enrichment(condition_anndata, cluster_key = clustering, show_progress_bar = False, seed = seed, n_perms = n_perms)
                sq.pl.nhood_enrichment(condition_anndata, 
                                       cluster_key = clustering, 
                                       cmap = 'coolwarm', 
                                       ax = ax, 
                                       fontsize = 10, 
                                       title = f'{i} Neighborhood Enrichment')
            diff = len(axs) - (ii + 1)
            for j in range(0, diff + 1):
                axs[ii + j].set_axis_off()
                
        if filename is not None:
            figure.savefig(self.save_dir + "/" + filename, bbox_inches = "tight") 
        plt.close()
        return figure
    
    def plot_interaction_matrix(self, clustering: str = "merging", facet_by: str = "None", col_num: int = 1, filename: Union[str, None] = None):
        '''
        Plots the ineteraction matrix for the chosen [clustering]. Can be facetted using [facet_by] to compare things like condition.

        Neighborhood enrichment is typically better / more informative as that represents interactions beyond expectation, while the interaction matrix
        plotted by this function is just the total count of interactions (so abundant cell types are likely to have higher interaction numbers than the other
        cell types), and does not carry any statistical significance on its own.)
        '''
        data = self.exp.data.copy()
        data.obs[clustering] = data.obs[clustering].astype('category')
        sq.gr.interaction_matrix(data, cluster_key = clustering)
        if facet_by != "None":
            conditions = data.obs[facet_by].unique()
            condition_num = len(conditions)
            if condition_num < 2:
                facet_by = None
                figure = plt.figure()
                ax = plt.gca()
            else:
                if (condition_num + 1) % col_num > 0:
                    row_num = ((condition_num + 1) // col_num) + 1
                else:
                    row_num = (condition_num + 1) // col_num
                figure, axs = plt.subplots(row_num, col_num, sharey = True)
                axs = axs.ravel()
                ax = axs[0]
        else:
            figure = plt.figure()
            ax = plt.gca()
        sq.pl.interaction_matrix(data, cluster_key = clustering, cmap = 'coolwarm', ax = ax)

        if facet_by != "None":
            for ii,i in enumerate(conditions):
                ax = axs[ii + 1]
                condition_anndata = data[data.obs[facet_by] == i].copy()
                sq.gr.interaction_matrix(condition_anndata, cluster_key = clustering)
                sq.pl.interaction_matrix(condition_anndata, 
                                         cluster_key = clustering, 
                                         cmap = 'coolwarm', 
                                         ax = ax, 
                                         fontsize = 10, 
                                         title = f'{i} Interaction Matrix')
            diff = len(axs) - (ii + 1)
            for j in range(0, diff + 1):
                axs[ii + j].set_axis_off()
                
        if filename is not None:
            figure.savefig(self.save_dir + "/" + filename, bbox_inches = "tight") 
        plt.close()
        return figure
    
    def plot_centrality(self, clustering: str = "merging", score: str = "closeness_centrality", filename: Union[str,None] = None):
        '''
        score_options = ["closeness_centrality", "degree_centrality", "average_clustering"]

        See squipy's documentation on squidpy.gr.centrality_scores() for what these represent

        Because of how squipdy.pl.centrality() works, cannot be facetted.
        '''  
        data = self.exp.data.copy()
        data.obs[clustering] = data.obs[clustering].astype('category')
        sq.gr.centrality_scores(data, cluster_key = clustering, score = score, show_progress_bar = False)
        if filename is not None:
            sq.pl.centrality_scores(data, cluster_key = clustering, score = score, save = self.save_dir + "/" + filename)
        else:
            sq.pl.centrality_scores(data, cluster_key = clustering, score = score)
        figure = plt.gcf()
        plt.close()
        return figure
    
    def plot_cell_map(self, 
                      sample_id: Union[str,None] = None, 
                      filename: Union[str,None] = None, 
                      clustering: str = "merging", 
                      save: bool = False):
        '''
        Plots a single image (designated by either sample_id or filename) in the style of squidpy.pl.spatial_segment (masks shapes plotted, colored by [clustering])
        '''
        if (filename is None) and (sample_id is not None):
            filename = self.exp.data.obs[self.exp.data.obs['sample_id'] == sample_id]['file_name'].values[0]

        if self.exp.back_up_data is not None:
            data = self.exp.back_up_data.copy()
            up_to_date_data = self.exp.data.copy()
            data.obs[clustering] = 'dropped'
            data.obs.loc[up_to_date_data.obs.index, clustering] = up_to_date_data.obs[clustering]
        else:
            data = self.exp.data.copy()

        unique_clusters = data.obs[clustering].unique()
        special_category = pd.CategoricalDtype(categories = unique_clusters, ordered = True)
        subset_anndata = data[data.obs['file_name'] == filename].copy()
        subset_anndata.obs[clustering] = subset_anndata.obs[clustering].astype(special_category)
        filename = filename[:filename.rfind(".")]
        mask_path = [i for i in self.masks_paths if (i.find(filename) != - 1)]
        if len(mask_path) > 1:                 ## if a given filename is fully present within another filename in the folder (so .find() != -1 for >1 of the paths), 
                                                            # always take the filepath with theshortest match
            mask_array = np.array([len(i) for i in mask_path])
            mask_path = mask_path[np.argmin(mask_array)]
        else:
            mask_path = mask_path[0]
        mask = tf.imread(mask_path).astype('int')
        if not save:
            filename = None

        ## add the mask in a place where it can be recornized by squidpy. The "image" is initialized as a zero-matrix
                # so that the background of the cell is dark.
        dictionary_to_segmentation = {'images':{'segmentation':mask, 'hires':np.zeros([*mask.shape, 3])}}
        with_library_key  = {'filename' : dictionary_to_segmentation}
        subset_anndata.uns['spatial'] = with_library_key
        subset_anndata.obs['cell_id'] = subset_anndata.obs.reset_index().index + 1  # the masks themselves are not 0-indexed, so +1
        subset_anndata.obs['library'] = 'filename'
        subset_anndata.obs['library'] = subset_anndata.obs['library'].astype('category')

        figure = plt.figure()
        ax = plt.gca()
        sq.pl.spatial_segment(subset_anndata, seg_cell_id = 'cell_id', library_key = 'library', color = clustering, seg = True, ax = ax)
        if filename is not None:
            filename = filename + ".png"
            figure.savefig(self.save_cell_maps_dir + "/" + filename, bbox_inches = "tight")
        plt.close()
        return figure, filename
    
    def plot_all_cell_maps(self, clustering: str = "merging"):
        '''
        Plots all the cell maps possible in the dataset
        '''
        for i in self.exp.data.obs['sample_id'].unique():
            self.plot_cell_map(sample_id = i, clustering = clustering, save = True)