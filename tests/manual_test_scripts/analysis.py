import sys
import os
import shutil
import warnings

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

from palmettobug import Analysis

########### CRITICAL! -- depends on test_img_proc having been run first!
proj_directory = homedir + "/project_folder/Example_IMC"
Analysis_panel = proj_directory + "/Analyses/Analysis_panel.csv"
metadata = proj_directory + "/Analyses/metadata.csv"
shutil.copyfile(Analysis_panel, proj_directory + "/Analyses/test_analysis/main/Analysis_panel.csv")
shutil.copyfile(metadata, proj_directory + "/Analyses/test_analysis/main/metadata.csv")

def test_load():
    my_analysis = Analysis()
    my_analysis.load_data(proj_directory + "/Analyses/test_analysis/main")
    #print(len(my_analysis.data.obs))
    assert isinstance(my_analysis.data, anndata.AnnData)
    return my_analysis

def test_filtering(my_analysis):
    starting_length = len(my_analysis.data.obs)
    length_sample_1 = len(my_analysis.data.obs[my_analysis.data.obs['sample_id'] == '1'])
    my_analysis.filter_data(to_drop = "1")
    assert (starting_length - length_sample_1) == len(my_analysis.data.obs), "Filtered data not the expected length!"

def test_scaling(my_analysis):
    scaling_options = ["%quantile", "min_max", "standard", "robust", "qnorm", "unscale"]
    original_X = my_analysis.data.X.copy()
    greater_than_zero = (original_X > 0)
    for i in scaling_options:
        my_analysis.do_scaling(scaling_algorithm = i)
        if i != "unscale":
            assert (my_analysis.data.X[greater_than_zero] == original_X[greater_than_zero]).sum().sum() < 1, "Scaling did not change all the data points > 0!"
        else:
            assert (my_analysis.data.X != original_X).sum().sum() == 0, "Unscaling did not restore the original data!"

def test_comBat(my_analysis):
    original_X = my_analysis.data.X.copy()
    greater_than_zero = (original_X > 0)
    my_analysis.do_COMBAT(batch_column = "patient_id")
    #print((my_analysis.data.X[greater_than_zero] == original_X[greater_than_zero]).sum().sum())
    assert (my_analysis.data.X[greater_than_zero] == original_X[greater_than_zero]).sum().sum() < (len(original_X[greater_than_zero]) / 10) , "ComBat did not change all the data points > 0!"

def test_countplot(my_analysis):
    figure = my_analysis.plot_cell_counts()
    assert isinstance(figure, matplotlib.figure.Figure), "Count plot did not return a matplotlib figure"

def test_MDS(my_analysis):
    figure, df = my_analysis.plot_MDS()
    assert isinstance(figure, matplotlib.figure.Figure), "MDS plot did not return a matplotlib figure"
    assert isinstance(df, pd.DataFrame), "MDS plot did not return a pandas DataFrame"
    
def test_NRS(my_analysis):
    figure = my_analysis.plot_NRS()
    assert isinstance(figure, matplotlib.figure.Figure), "NRS plot did not return a matplotlib figure"

def test_ROI_histograms(my_analysis):
    figure = my_analysis.plot_ROI_histograms()
    assert isinstance(figure, matplotlib.figure.Figure), "ROI histogram plot did not return a matplotlib figure"

def test_do_UMAP(my_analysis):
    my_analysis.do_UMAP()
    assert (my_analysis.UMAP_embedding is not None), "do UMAP did not create an anndata embedding"
    assert isinstance(my_analysis.UMAP_embedding, anndata.AnnData), "do UMAP did not create an anndata embedding"

def test_do_PCA(my_analysis):
    my_analysis.do_PCA()
    assert (my_analysis.PCA_embedding is not None), "do PCA did not create an anndata embedding"
    assert isinstance(my_analysis.PCA_embedding, anndata.AnnData), "do PCA did not create an anndata embedding"

def test_do_flowsom(my_analysis):
    fs = my_analysis.do_flowsom()
    figure = my_analysis._plot_stars_CNs(fs)
    try:
        metaclustering = my_analysis.data.obs['metaclustering']
    except Exception:
        metaclustering = None
    assert metaclustering is not None, "do_flowsom did not create a metaclustering column"
    assert len(metaclustering.unique()) == 20, "do_flowsom did not create the expected number of values in the metaclustering column"
    assert '1' in metaclustering, "do_flowsom did not create the expected values in metaclustering column"
    assert '20' in metaclustering,  "do_flowsom did not create the expected values in metaclustering column"
    assert isinstance(figure, matplotlib.figure.Figure), "FlowSOM MST plot did not return a matplotlib figure"

def test_do_leiden_clustering(my_analysis):
    fs = my_analysis.do_leiden_clustering()
    try:
        leiden = my_analysis.data.obs['leiden']
    except Exception:
        leiden = None
    assert leiden is not None,  "do_leiden did not create a leiden column"
    number_of_leiden =  len(leiden.unique())
    assert '1' in leiden, "do_leiden did not create the expected values in leiden column"
    assert str(number_of_leiden) in leiden, "do_ledien did not create the expected values in leiden column"

def test_plot_UMAP(my_analysis):
    figure = my_analysis.plot_UMAP()
    assert isinstance(figure, matplotlib.figure.Figure), "UMAP plot did not return a matplotlib figure"

def test_plot_PCA(my_analysis):
    figure = my_analysis.plot_PCA()
    assert isinstance(figure, matplotlib.figure.Figure), "PCA plot did not return a matplotlib figure"

def test_facetted_DR(my_analysis):
    figure = my_analysis.plot_facetted_DR(color_by = "metaclustering", subsetting_column = "sample_id")
    assert isinstance(figure, matplotlib.figure.Figure), "Facetted DR plot did not return a matplotlib figure"

def test_medians_heatmap(my_analysis):
    figure = my_analysis.plot_medians_heatmap()
    assert isinstance(figure, matplotlib.figure.Figure), "medians Heatmap plot did not return a matplotlib figure"

def test_cluster_dist(my_analysis):
    figure = my_analysis.plot_cluster_distributions()
    assert isinstance(figure, matplotlib.figure.Figure), "cluster distributions plot did not return a matplotlib figure"

def test_cluster_histograms(my_analysis):
    figure = my_analysis.plot_cluster_histograms(antigen = "CCL2")
    assert isinstance(figure, matplotlib.figure.Figure), "cluster histograms plot did not return a matplotlib figure"

def test_abundance_1(my_analysis):
    figure = my_analysis.plot_cluster_abundance_1()
    assert isinstance(figure, matplotlib.figure.Figure), "abundance 1 plot did not return a matplotlib figure"

def test_abundance_2(my_analysis):
    figure = my_analysis.plot_cluster_abundance_2()
    assert isinstance(figure, matplotlib.figure.Figure), "abundance 2 plot did not return a matplotlib figure"

def test_do_cluster_stats(my_analysis):
    output_dict = my_analysis.do_cluster_stats()
    assert isinstance(output_dict, dict), "do_cluster_stats did not return a dictionary"
    assert len(output_dict) == len(my_analysis.data.obs['metaclustering'].unique()), "cluster statistics dictionary did not have expected length"
    assert len(output_dict[1]) == (my_analysis.data.var['marker_class'] == 'type').sum(), "cluster statistics dictionary sub-dataframe did not have expected length"

def test_plot_cluster_stats(my_analysis):
    figure = my_analysis.plot_cluster_stats()
    assert isinstance(figure, matplotlib.figure.Figure), "cluster statistics plot did not return a matplotlib figure"

def test_do_cluster_merging(my_analysis):
    fake_merging = pd.DataFrame()
    fake_merging['original_cluster'] = list(my_analysis.data.obs['metaclustering'].unique())
    annotation_list = ["a","a","a","a","a","b","b","b","b","b","c","c","c","c","c","a","b","b","c","c",]
    fake_merging['new_cluster'] = annotation_list[:len(fake_merging)]
    fake_merging.to_csv(proj_directory + "/temp.csv")
    my_analysis.do_cluster_merging(file_path = proj_directory + "/temp.csv")
    assert ('merging' in my_analysis.data.obs.columns), "do_merging did not add a merging!"
    assert len(my_analysis.data.obs['merging'].unique()) == 3, "do_merging did not add the expected number of merging categories!"

def test_export_clustering(my_analysis):
    df, path = my_analysis.export_clustering(groupby_column = "merging")
    assert len(os.listdir(my_analysis.clusterings_dir)) == 1, "Clustering save did not export!"

def test_do_abundance_ANOVAs(my_analysis):
    df = my_analysis.do_abundance_ANOVAs()    ## need to do merging before!
    assert isinstance(df, pd.DataFrame), "abundance ANOVA method did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.data.obs['merging'].unique()), "abundance ANOVA dataframe did not have the expected length"

def test_do_count_GLM(my_analysis):
    df = my_analysis.do_count_GLM(list(my_analysis.data.obs['condition'].unique()))
    assert isinstance(df, pd.DataFrame), "count_GLM method did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.data.obs['merging'].unique()), "GLM statistics dataframe did not have the expected length"

def test_do_state_exprs_ANOVAs(my_analysis):
    df = my_analysis.do_state_exprs_ANOVAs(marker_class = "type")
    assert isinstance(df, pd.DataFrame), "state expression statistics did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.data.obs['merging'].unique()) * (my_analysis.data.var['marker_class'] == "type").sum(), "state expression statistics dataframe did not have the expected length"

def test_export_data(my_analysis):
    df = my_analysis.export_data()
    df.to_csv(proj_directory + "/temp.csv")
    df2 = pd.read_csv(proj_directory + "/temp.csv")
    assert isinstance(df, pd.DataFrame), "data export did not return a pandas DataFrame"
    assert len(df2) == len(my_analysis.data.obs), "data export did not have the same length as the source data!"

def test_export_DR(my_analysis):
    df = my_analysis.export_DR()
    assert isinstance(df, pd.DataFrame), "DR export did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.UMAP_embedding), "DR export did not have the same length as the source embedding!"

def test_to_classy_masks(my_analysis):
    data_df = my_analysis.export_clustering_classy_masks()
    assert len(data_df) == len(my_analysis.back_up_data)

def test_scatterplot(my_analysis):
    figure = my_analysis.plot_scatter(antigen1 = "CD3", antigen2 = "CD4")
    assert isinstance(figure, matplotlib.figure.Figure), "scatterplot did not make a matplotlib figure"

##############################################################

if __name__ == "__main__":
    try:
        my_analysis = test_load()
        print("Successfully loaded Analysis!")
    except Exception as e:
        print(f"Failed to load Analysis! Error: {e}")
    else:
        tests = [test_filtering,
                test_scaling,
                test_comBat,
                test_countplot, 
                test_MDS, 
                test_NRS, 
                test_ROI_histograms,
                test_do_UMAP,
                test_do_PCA,
                test_do_flowsom,
                test_do_leiden_clustering,
                test_plot_UMAP,
                test_plot_PCA,
                test_facetted_DR,
                test_medians_heatmap,
                test_cluster_dist,
                test_cluster_histograms,
                test_abundance_1,
                test_abundance_2,
                test_do_cluster_stats,
                test_plot_cluster_stats,
                test_do_cluster_merging,
                test_do_abundance_ANOVAs,
                test_export_clustering,
                test_do_count_GLM,
                test_do_state_exprs_ANOVAs,
                test_export_data,
                test_export_DR,
                test_to_classy_masks]

        test_names = ["test_filtering",
                    "test_scaling",
                    "test_comBat",
                    "test_countplot", 
                    "test_MDS", 
                    "test_NRS", 
                    "test_ROI_histograms",
                    "test_do_UMAP",
                    "test_do_PCA",
                    "test_do_flowsom",
                    "test_do_leiden_clustering",
                    "test_plot_UMAP",
                    "test_plot_PCA",
                    "test_facetted_DR",
                    "test_medians_heatmap",
                    "test_cluster_dist",
                    "test_cluster_histograms",
                    "test_abundance_1",
                    "test_abundance_2",
                    "test_do_cluster_stats",
                    "test_plot_cluster_stats",
                    "test_do_cluster_merging",
                    "test_do_abundance_ANOVAs",
                    "test_export_clustering",
                    "test_do_count_GLM",
                    "test_do_state_exprs_ANOVAs",
                    "test_export_data",
                    "test_export_DR",
                    "test_to_classy_masks"]

        test_fail = []
        for i,ii in zip(tests, test_names):
            #print(f"Shape of data in analysis = {my_analysis.data.X.shape}")
            try:
                i(my_analysis)
                print(f"test {ii} passed")
            except AssertionError as e:
                print(e)
                test_fail.append(ii)
            except Exception as e:
                print(f"{ii} failed with an unexpected error: {e}")
                test_fail.append(ii)
        if len(test_fail) == 0:
            print("Passed all tests!")
        else:
            print(f"Failed the following tests: {str(', '.join(test_fail))}")
