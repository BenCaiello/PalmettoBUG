import sys
import os
import shutil

homedir = __file__.replace("\\","/")
homedir = homedir[:(homedir.rfind("/"))]
homedir = homedir[:(homedir.rfind("/"))]

### homedir = /path/to/project/palmettobug   -- as in, the folder name passed to sys.path.append is always 'palmettobug'
sys.path.append(homedir)

import tifffile as tf
import numpy as np
import pandas as pd
import anndata
import matplotlib

from palmettobug import Analysis, SpatialAnalysis

########### CRITICAL! -- depends on test_img_proc & test_analysis having been run first!
proj_directory = homedir + "/project_folder/Example_IMC"

my_analysis = Analysis()
my_analysis.load_data(proj_directory + "/Analyses/test_analysis/main")

my_analysis.filter_data(to_drop = "1") ### must match test_analysis!

my_spatial = SpatialAnalysis()


def test_load_clustering():
    my_analysis.load_clustering(path = my_analysis.clusterings_dir + "/merging.csv")
    assert "merging" in my_analysis.data.obs.columns, "Merging not added to analysis data.obs!"

def test_init_Spatial():
    my_spatial.add_Analysis(my_analysis)
    assert (my_spatial.exp is my_spatial.edt.exp) and (my_spatial.exp is my_spatial.SpaceANOVA.exp) and (my_spatial.exp is my_spatial.neighbors.exp) and (my_spatial.exp is my_analysis) 

def test_cell_maps():
    plot = my_spatial.plot_cell_maps(plot_type = "points", id = "5")
    assert isinstance(plot, matplotlib.figure.Figure), "Plot Cell maps for a single ROI (points) did not return a matplotlib figure"
    plot2 = my_spatial.plot_cell_maps(plot_type = "masks", id = "6")
    assert isinstance(plot2, matplotlib.figure.Figure), "Plot Cell maps for a single ROI (masks) did not return a matplotlib figure"
    my_spatial.plot_cell_maps(plot_type = "points")
    assert(len(os.listdir(my_spatial.SpaceANOVA.output_dir + "/cell_maps")) == 10), "Plot Cell maps for all ROIs (masks) did not write a plot for each ROI to the appropriate location"

def test_do_neighbors_and_plots():
    my_spatial.do_neighbors(radius_or_neighbors = "Neighbors", number = 20)
    plot = my_spatial.plot_neighbor_interactions()
    assert isinstance(plot, matplotlib.figure.Figure), "Plot Neighborhood Interactions did not return a matplotlib figure"
    plot2 = my_spatial.plot_neighbor_enrichment(facet_by = "condition")
    assert isinstance(plot2, matplotlib.figure.Figure), "Plot Neighborhood Enrichment (with facetting) did not return a matplotlib figure"

def test_neighbor_centrality_plots():
    plot = my_spatial.plot_neighbor_centrality()
    assert isinstance(plot, matplotlib.figure.Figure), "Plot Centrality (closeness) did not return a matplotlib figure"
    plot2 = my_spatial.plot_neighbor_centrality(score = "degree_centrality")
    assert isinstance(plot2, matplotlib.figure.Figure), "Plot Centrality (degree) did not return a matplotlib figure"
    plot3 = my_spatial.plot_neighbor_centrality(score = "average_clustering")
    assert isinstance(plot, matplotlib.figure.Figure), "Plot Centrality (average) did not return a matplotlib figure"

def test_do_neighborhood_CNs():
    plot = my_spatial.do_neighborhood_CNs()
    assert isinstance(plot, matplotlib.figure.Figure), "do Neighborhood Clustering (FlowSOM) did not return a matplotlib figure"
    assert 'CN' in my_analysis.data.obs.columns, "do Neighborhood Clustering (FlowSOM) did not add CN column to exp.data.obs"
    plot2 = my_spatial.plot_CN_graph()
    assert isinstance(plot2, matplotlib.figure.Figure), "plot CN graph did not return a matplotlib figure"

def test_plot_CN_heatmap():
    plot = my_spatial.plot_CN_heatmap()
    assert isinstance(plot, matplotlib.figure.Figure), "plot CN heatmap did not return a matplotlib figure"

def test_plot_CN_abundance():
    plot = my_spatial.plot_CN_abundance(clustering = 'merging')
    assert isinstance(plot, matplotlib.figure.Figure), "plot CN abundance did not return a matplotlib figure"

def test_do_SpaceANOVA_ripleys_stats():
    my_spatial.SpaceANOVA._comparison_dictionary = None
    my_spatial.do_SpaceANOVA_ripleys_stats(clustering = "merging")
    assert my_spatial.SpaceANOVA.data_table is not None, "spaceANOVA Ripley's statistics not calculated!"
    assert my_spatial.SpaceANOVA._comparison_dictionary is not None, "spaceANOVA Ripley's statistics not calculated!"

def test_plot_spaceANOVA_function():

    plot = my_spatial.plot_spaceANOVA_function(stat = 'g', comparison = my_spatial.SpaceANOVA._comparison_list[0])
    assert isinstance(plot, matplotlib.figure.Figure), "plot SpaceANOVA function (for one image) did not return a matplotlib figure"
    plot2 = my_spatial.plot_spaceANOVA_function(stat = 'K', comparison = my_spatial.SpaceANOVA._comparison_list[1], f_stat = 'f', hline = 1)
    assert isinstance(plot2, matplotlib.figure.Figure), "plot SpaceANOVA function (for one image + f_stat, hline) did not return a matplotlib figure"
    my_spatial.plot_spaceANOVA_function(stat = 'L')
    number_of_plots = len(my_spatial.SpaceANOVA.good_cell_types) * len(my_spatial.SpaceANOVA.good_cell_types)
    assert len(os.listdir(my_spatial.SpaceANOVA.output_dir + "/Functional_plots")) == (number_of_plots + 2), "plot SpaceANOVA function (for whole folder of image) did not export the expected files"

def test_run_SpaceANOVA_statistics():
    padj, p, stat = my_spatial.run_SpaceANOVA_statistics()
    assert (np.array(padj).shape == np.array(p).shape) and (np.array(padj).shape == np.array(stat).shape), "Dataframes returned are not square matrices!"
    assert (np.array(padj) >= np.array(p)).sum() == (np.array(padj).shape[0] * np.array(padj).shape[1]), "P adjusted values should be strictly greater than or equal to the underlying p values"

def test_plot_spaceANOVA_heatmap():
    plot = my_spatial.plot_spaceANOVA_heatmap(stat = "p")
    assert isinstance(plot, matplotlib.figure.Figure), "plot SpaceANOVA heatmap did not return a matplotlib figure"

def test_edt():
    my_analysis.filter_data(to_drop = "0")
    my_analysis.filter_data(to_drop = "8")
    my_analysis.filter_data(to_drop = "9")
    panel, results = my_spatial.do_edt(pixel_classifier_folder = proj_directory + "/Pixel_Classification/lumen_epithelia_laminapropria", 
                                        masks_folder = proj_directory + "/masks/fake", 
                                        maps = "/classification_maps",
                                        smoothing = 10, 
                                        stat = 'mean', 
                                        normalized = True, 
                                        background = False,
                                        marker_class = 'spatial_edt', 
                                        auto_panel = True,
                                        output_edt_folder = None,
                                        save_path = None)
    assert np.array(my_analysis.data.var['marker_class'] == "spatial_edt").sum() == 2, "Number of EDT classes is not the expected amount!"

def test_edt_heatmap():
    plot = my_spatial.plot_edt_heatmap(groupby_col = "merging")
    assert isinstance(plot, matplotlib.figure.Figure), "plot edt heatmap did not return a matplotlib figure"

def test_plot_edt_boxplot():
    second_edt = list(my_analysis.data.var[my_analysis.data.var['marker_class'] == "spatial_edt"]['antigen'])[1]
    # print(second_edt)
    plot = my_spatial.plot_edt_boxplot(second_edt)
    assert isinstance(plot, matplotlib.figure.Figure), "plot edt boxplot did not return a matplotlib figure"

def test_run_edt_statistics():
    df = my_spatial.run_edt_statistics(groupby_column = "merging")
    assert isinstance(df, pd.DataFrame), "edt statistics did not return a pandas dataframe"
    assert len(df) == ((np.array(my_analysis.data.var['marker_class'] == "spatial_edt").sum()) * len(my_analysis.data.obs['merging'].unique())), "edt_statistics did not retrun the expected number of comparison"



if __name__ == "__main__":
    try:
        test_load_clustering()
        print("Successfully loaded Spatial Analysis!")
    except Exception as e:
        print(f"Failed to load Spatial Analysis! Error: {e}")
    else:
        tests = [test_init_Spatial,
                test_cell_maps,
                test_do_neighbors_and_plots,
                test_neighbor_centrality_plots,
                test_do_neighborhood_CNs,
                test_plot_CN_heatmap,
                test_plot_CN_abundance,
                test_do_SpaceANOVA_ripleys_stats,
                test_plot_spaceANOVA_function,
                test_run_SpaceANOVA_statistics,
                test_plot_spaceANOVA_heatmap,
                test_edt,
                test_edt_heatmap,
                test_plot_edt_boxplot,
                test_run_edt_statistics]

        test_names = ["test_init_Spatial",
                     "test_cell_maps",
                     "test_do_neighbors_and_plots",
                     "test_neighbor_centrality_plots",
                     "test_do_neighborhood_CNs",
                     "test_plot_CN_heatmap",
                     "test_plot_CN_abundance",
                     "test_do_SpaceANOVA_ripleys_stats",
                     "test_plot_spaceANOVA_function",
                     "test_run_SpaceANOVA_statistics",
                     "test_plot_spaceANOVA_heatmap",
                     "test_edt",
                     "test_edt_heatmap",
                     "test_plot_edt_boxplot",
                     "test_run_edt_statistics"]

        test_fail = []
        for i,ii in zip(tests, test_names):
            try:
                test_name = f"test {ii}:"
                i()
                print(f"{test_name} passed")
            except AssertionError as e:
                print(f"{test_name} failed with assertion error: {e}")
                test_fail.append(ii)
            except Exception as e:
                print(f"{test_name} failed with an unexpected error: {e}")
                test_fail.append(ii)
        if len(test_fail) == 0:
            print("Passed all tests!")
        else:
            print(f"Failed the following tests: {str(', '.join(test_fail))}")
    