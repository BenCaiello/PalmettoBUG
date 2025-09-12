import sys
import os
import shutil

homedir = __file__.replace("\\","/")
homedir = homedir[:(homedir.rfind("/"))]
homedir = homedir[:(homedir.rfind("/"))]

### homedir = /path/to/project/palmettobug   -- as in, the folder name passed to sys.path.append is always 'palmettobug'
#sys.path.append(homedir)

import tifffile as tf
import numpy as np
import pandas as pd
import anndata
import matplotlib

from palmettobug import fetch_IMC_example, ImageAnalysis, mask_expand
from palmettobug import Analysis, SpatialAnalysis

fetch_dir = homedir + "/project_folder"
if not os.path.exists(fetch_dir):
    os.mkdir(fetch_dir)
proj_directory = fetch_dir + "/Example_IMC"
np.random.default_rng(42)

#def test_fetch_IMC():
#    fetch_IMC_example(fetch_dir)

def test_raw_to_img():
    global image_proc
    image_proc = ImageAnalysis(proj_directory, from_mcds = True)
    image_proc.directory_object.makedirs()
    image_proc.raw_to_img(0.85)
    images = [f"{proj_directory}/images/img/{i}" for i in sorted(os.listdir(proj_directory + "/images/img"))]
    assert(len(images) == 10), "Wrong number of images exported to images/img"               ## all the images are transferred
    shutil.rmtree(proj_directory + "/raw") ## don't need raw anymore

def test_expand_masks():
    mask_expand(2, proj_directory + "/masks/example_deepcell_masks", proj_directory + "/masks/expanded_deepcell_masks")
    images = [f"{proj_directory}/masks/expanded_deepcell_masks/{i}" for i in sorted(os.listdir(proj_directory + "/masks/expanded_deepcell_masks"))]
    assert(len(images) == 10), "All masks not expanded" 
     
def test_instanseg():
    image_proc.instanseg_segmentation(single_image = os.listdir(proj_directory + "/images/img")[0])
    assert(len(os.listdir(proj_directory + "/masks/instanseg_masks"  )) == 1), "Wrong number of masks exported"

def test_mask_intersection_difference():
    masks1 = proj_directory + "/masks/example_deepcell_masks"
    masks2 = proj_directory + "/masks/expanded_deepcell_masks"
    image_proc.mask_intersection_difference(masks1, masks2)
    assert(len(os.listdir(proj_directory + "/masks/example_deepcell_masks_expanded_deepcell_masks"  )) == 10), "Mask intersection function failed!"

def test_regionprops_write():
    image_proc.directory_object.make_analysis_dirs("test_analysis")
    input_img_folder = proj_directory + "/images/img"
    input_mask_folder = proj_directory + "/masks/example_deepcell_masks"    # "/masks/instanseg_masks" 
    image_proc.make_segmentation_measurements(input_img_folder = input_img_folder, input_mask_folder = input_mask_folder)
    analysis_dir = image_proc.directory_object.Analyses_dir + "/test_analysis"
    intensities_dir = analysis_dir + "/intensities"
    assert(len(os.listdir(analysis_dir + "/regionprops")) == 10), "Wrong number of regionprops csv exported (expecting 10 to match the number of images)"
    assert(len(pd.read_csv(intensities_dir + "/CRC_1_ROI_001.ome.csv") == 2177)), "Unexpected number of cells in image 1"

def test_setup_analysis():
    panel_file, metadata, Analysis_panel_dir, metadata_dir = image_proc.to_analysis()
    panel_file.to_csv(Analysis_panel_dir)
    metadata.to_csv(metadata_dir)
    assert(os.listdir(image_proc.directory_object.Analysis_internal_dir + "/Analysis_fcs")[0].rfind(".fcs") != -1), "FCS files not in /main/Analysis_fcs!"
    assert(len(metadata) == 10), "Automatically generated Metadata file's length does not match the number of FCS files in the experiment!"
    assert("marker_class" in panel_file.columns), "Automatically generated Analysis_panel file should have a 'marker_class' column"
    assert("Analysis_panel.csv" in os.listdir(image_proc.directory_object.Analysis_internal_dir)), "Analysis_panel.csv not written to the proper place!"
    assert("metadata.csv" in os.listdir(image_proc.directory_object.Analysis_internal_dir)), "metadata.csv not written to the proper place!"
    assert("condition" in list(pd.read_csv(image_proc.directory_object.Analysis_internal_dir + "/metadata.csv").columns)), "Automatically generated metadata.csv file must have a 'condition' column!"

########### CRITICAL! -- depends on test_img_proc having been run first!
def test_setup_directories():
    global Analysis_panel
    Analysis_panel = proj_directory + "/Analyses/Analysis_panel.csv"
    global metadata
    metadata = proj_directory + "/Analyses/metadata.csv"
    shutil.copyfile(Analysis_panel, proj_directory + "/Analyses/test_analysis/main/Analysis_panel.csv")
    shutil.copyfile(metadata, proj_directory + "/Analyses/test_analysis/main/metadata.csv")

def test_load():
    global my_analysis
    my_analysis = Analysis()
    my_analysis.load_data(proj_directory + "/Analyses/test_analysis/main")
    #print(len(my_analysis.data.obs))
    assert isinstance(my_analysis.data, anndata.AnnData)

def test_filtering():
    starting_length = len(my_analysis.data.obs)
    length_sample_1 = len(my_analysis.data.obs[my_analysis.data.obs['sample_id'] == '1'])
    my_analysis.filter_data(to_drop = "1")
    assert (starting_length - length_sample_1) == len(my_analysis.data.obs), "Filtered data not the expected length!"

def test_scaling():
    scaling_options = ["%quantile", "min_max", "standard", "robust", "qnorm", "unscale"]
    original_X = my_analysis.data.X.copy()
    greater_than_zero = (original_X > 0)
    for i in scaling_options:
        my_analysis.do_scaling(scaling_algorithm = i)
        if i != "unscale":
            assert (my_analysis.data.X[greater_than_zero] != original_X[greater_than_zero]).sum().sum() > 0, "Scaling should change some of the data points > 0!"
        else:
            assert (my_analysis.data.X != original_X).sum().sum() == 0, "Unscaling did not restore the original data!"

def test_do_regions():
    my_analysis.do_regions(region_folder = proj_directory + "/masks/test_seg")
    assert ('regions' in my_analysis.data.obs.columns), "Do regions did not generate a 'regions' column in obs!"

#def test_spatial_leiden():
#    my_analysis._do_spatial_leiden()
#    assert ('spatial_leiden' in my_analysis.data.obs.columns), "Do spatial_leiden did not generate a 'spatial_leiden' column in obs!"

def test_comBat():
    original_X = my_analysis.data.X.copy()
    greater_than_zero = (original_X > 0)
    my_analysis.do_COMBAT(batch_column = "patient_id")
    assert (my_analysis.data.X[greater_than_zero] == original_X[greater_than_zero]).sum().sum() < (len(original_X[greater_than_zero]) / 10) , "ComBat did not change all the data points > 0!"

def test_countplot():
    figure = my_analysis.plot_cell_counts()
    assert isinstance(figure, matplotlib.figure.Figure), "Count plot did not return a matplotlib figure"

def test_MDS():
    figure, df = my_analysis.plot_MDS()
    assert isinstance(figure, matplotlib.figure.Figure), "MDS plot did not return a matplotlib figure"
    assert isinstance(df, pd.DataFrame), "MDS plot did not return a pandas DataFrame"
    
def test_NRS():
    figure = my_analysis.plot_NRS()
    assert isinstance(figure, matplotlib.figure.Figure), "NRS plot did not return a matplotlib figure"

def test_ROI_histograms():
    figure = my_analysis.plot_ROI_histograms()
    assert isinstance(figure, matplotlib.figure.Figure), "ROI histogram plot did not return a matplotlib figure"

def test_do_UMAP():
    my_analysis.do_UMAP()
    assert (my_analysis.UMAP_embedding is not None), "do UMAP did not create an anndata embedding"
    assert isinstance(my_analysis.UMAP_embedding, anndata.AnnData), "do UMAP did not create an anndata embedding"

def test_do_PCA():
    my_analysis.do_PCA()
    assert (my_analysis.PCA_embedding is not None), "do PCA did not create an anndata embedding"
    assert isinstance(my_analysis.PCA_embedding, anndata.AnnData), "do PCA did not create an anndata embedding"

def test_do_flowsom():
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

def test_do_leiden_clustering():
    fs = my_analysis.do_leiden_clustering()
    try:
        leiden = my_analysis.data.obs['leiden']
    except Exception:
        leiden = None
    assert leiden is not None,  "do_leiden did not create a leiden column"
    number_of_leiden =  len(leiden.unique())
    assert '1' in leiden, "do_leiden did not create the expected values in leiden column"
    assert str(number_of_leiden) in leiden, "do_ledien did not create the expected values in leiden column"

def test_plot_UMAP():
    figure = my_analysis.plot_UMAP(color_by = "HistoneH3")
    assert isinstance(figure, matplotlib.figure.Figure), "UMAP plot did not return a matplotlib figure"

def test_plot_PCA():
    figure = my_analysis.plot_PCA()
    assert isinstance(figure, matplotlib.figure.Figure), "PCA plot did not return a matplotlib figure"

def test_facetted_DR():
    figure = my_analysis.plot_facetted_DR(color_by = "metaclustering", subsetting_column = "sample_id")
    assert isinstance(figure, matplotlib.figure.Figure), "Facetted DR plot did not return a matplotlib figure"

def test_facetted_by_antigen_DR():
    figure = my_analysis.plot_facetted_DR_by_antigen(marker_class = ["type","state"], kind = "UMAP")
    assert isinstance(figure, matplotlib.figure.Figure), "Antigen Facetted DR plot did not return a matplotlib figure"

def test_medians_heatmap():
    figure = my_analysis.plot_medians_heatmap()
    assert isinstance(figure, matplotlib.figure.Figure), "medians Heatmap plot did not return a matplotlib figure"

def test_cluster_dist():
    figure = my_analysis.plot_cluster_distributions()
    assert isinstance(figure, matplotlib.figure.Figure), "cluster distributions plot did not return a matplotlib figure"

def test_cluster_histograms():
    figure = my_analysis.plot_cluster_histograms(antigen = "Pan-Keratin")
    assert isinstance(figure, matplotlib.figure.Figure), "cluster histograms plot did not return a matplotlib figure"

def test_abundance_1():
    figure = my_analysis.plot_cluster_abundance_1()
    assert isinstance(figure, matplotlib.figure.Figure), "abundance 1 plot did not return a matplotlib figure"

def test_abundance_2():
    figure = my_analysis.plot_cluster_abundance_2()
    assert isinstance(figure, matplotlib.figure.Figure), "abundance 2 plot did not return a matplotlib figure"

def test_do_cluster_stats():
    output_dict = my_analysis.do_cluster_stats()
    assert isinstance(output_dict, dict), "do_cluster_stats did not return a dictionary"
    assert len(output_dict) == len(my_analysis.data.obs['metaclustering'].unique()), "cluster statistics dictionary did not have expected length"
    assert len(output_dict[1]) == (my_analysis.data.var['marker_class'] == 'type').sum(), "cluster statistics dictionary sub-dataframe did not have expected length"

def test_plot_cluster_stats():
    figure = my_analysis.plot_cluster_stats()
    assert isinstance(figure, matplotlib.figure.Figure), "cluster statistics plot did not return a matplotlib figure"

def test_do_cluster_merging():
    fake_merging = pd.DataFrame()
    fake_merging['original_cluster'] = list(my_analysis.data.obs['metaclustering'].unique())
    annotation_list = ["a","a","a","a","a","b","b","b","b","b","c","c","c","c","c","a","b","b","c","c",]
    fake_merging['new_cluster'] = annotation_list[:len(fake_merging)]
    fake_merging.to_csv(proj_directory + "/temp.csv")
    my_analysis.do_cluster_merging(file_path = proj_directory + "/temp.csv")
    assert ('merging' in my_analysis.data.obs.columns), "do_merging did not add a merging!"
    assert len(my_analysis.data.obs['merging'].unique()) == 3, "do_merging did not add the expected number of merging categories!"

def test_export_clustering():
    df, path = my_analysis.export_clustering(groupby_column = "merging")
    assert len(os.listdir(my_analysis.clusterings_dir)) == 1, "Clustering save did not export!"

def test_do_abundance_ANOVAs():
    df = my_analysis.do_abundance_ANOVAs()    ## need to do merging before!
    assert isinstance(df, pd.DataFrame), "abundance ANOVA method did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.data.obs['merging'].unique()), "abundance ANOVA dataframe did not have the expected length"

def test_do_count_GLM():
    for i in ["Gaussian","Poisson"]:
        df = my_analysis.do_count_GLM(list(my_analysis.data.obs['condition'].unique()), family = i)
    assert isinstance(df, pd.DataFrame), "count_GLM method did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.data.obs['merging'].unique()), "GLM statistics dataframe did not have the expected length"

def test_plot_state_distributions():
    figure = my_analysis.plot_state_distributions(marker_class = 'type')
    assert isinstance(figure, matplotlib.figure.Figure), "plot_state_distributions did not return a matplotlib figure"

def test_do_state_exprs_ANOVAs():
    df = my_analysis.do_state_exprs_ANOVAs(marker_class = "type")
    assert isinstance(df, pd.DataFrame), "state expression statistics did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.data.obs['merging'].unique()) * (my_analysis.data.var['marker_class'] == "type").sum(), "state expression statistics dataframe did not have the expected length"

def test_plot_state_p_value_heatmap():
    figure =  my_analysis.plot_state_p_value_heatmap(ANOVA_kwargs = {'marker_class':"type"})
    assert isinstance(figure, matplotlib.figure.Figure), "plot_state_p_value_heatmap did not return a matplotlib figure"

def test_export_data():
    df = my_analysis.export_data()
    df.to_csv(proj_directory + "/temp.csv")
    df2 = pd.read_csv(proj_directory + "/temp.csv")
    assert isinstance(df, pd.DataFrame), "data export did not return a pandas DataFrame"
    assert len(df2) == len(my_analysis.data.obs), "data export did not have the same length as the source data!"

def test_export_DR():
    df = my_analysis.export_DR()
    assert isinstance(df, pd.DataFrame), "DR export did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.UMAP_embedding), "DR export did not have the same length as the source embedding!"

#def test_scatterplot():
#    figure = my_analysis.plot_scatter(antigen1 = "CD3", antigen2 = "CD4")
#    assert isinstance(figure, matplotlib.figure.Figure), "scatterplot did not make a matplotlib figure"

def test_to_classy_masks():
    data_df = my_analysis.export_clustering_classy_masks(clustering = "merging")
    assert len(data_df) == len(my_analysis.back_up_data)

def test_load_clustering():
    my_analysis.load_clustering(path = my_analysis.clusterings_dir + "/merging.csv")
    assert "merging" in my_analysis.data.obs.columns, "Merging not added to analysis data.obs!"

def test_init_Spatial():
    global my_spatial
    my_spatial = SpatialAnalysis()
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
    # print(os.listdir('/home/runner/work/PalmettoBUG/PalmettoBUG/project_folder/Example_IMC/Pixel_Classification/lumen_epithelia_laminapropria'))
    panel, results = my_spatial.do_edt(pixel_classifier_folder = proj_directory + "/Pixel_Classification/lumen_epithelia_laminapropria", 
                                        masks_folder = proj_directory + "/masks/example_deepcell_masks", 
                                        maps = "/classification_maps",
                                        smoothing = 10, 
                                        stat = 'mean', 
                                        normalized = True, 
                                        background = False,   ## because background is False, expect only 2 classes!
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


