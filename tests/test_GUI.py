import os
import shutil

import numpy as np
import pandas as pd
import anndata
import matplotlib
import customtkinter as ctk

import palmettobug
from palmettobug.Entrypoint.app_and_entry import App, fetch_IMC_example, fetch_CyTOF_example

homedir = __file__.replace("\\","/")
homedir = homedir[:(homedir.rfind("/"))]
homedir = homedir[:(homedir.rfind("/"))]
fetch_dir = homedir + "/project_folder"
if not os.path.exists(fetch_dir):
    os.mkdir(fetch_dir)
proj_directory = fetch_dir + "/Example_IMC"

np.random.default_rng(42)

def test_print_licenses():
    palmettobug.print_license()
    palmettobug.print_3rd_party_license_info()
    assert True

def test_fetch_IMC():
    fetch_IMC_example(fetch_dir)

def test_fetch_CyTOF():
    fetch_CyTOF_example(fetch_dir)

##########################################################################################################################################################
# Right now, only trying to test majority of GUI elements and not the backend analysis functions. In the future, could consider superseding the existing #
# test suite with tests launched from this GUI testing script -- allowing more thorough testing through every nook and cranny of the GUI widgets         #
##########################################################################################################################################################

##>>## GUI App & entrypoint tests
def test_setup_app():
    global app
    app = App(None)
    assert True   ## non-failure is enough for me right now, as it implies successful setting up of the widgets of the GUI

def test_GPL_window():
    app.entrypoint.show_GPL()
    assert True 

def test_call_configGUI():
    app.entrypoint.call_configGUI()
    assert True 

def test_launchExampleDataWindow():
    app.entrypoint.launchExampleDataWindow()
    assert True

def test_img_entry_func():
    number = app.entrypoint.img_entry_func(proj_directory)  ## successfully proceeding through function in tests
    assert True 


##>>## GUI Image Analysis tests
def test_call_raw_to_img_part_1_hpf():
    hpf_window = app.entrypoint.image_proc_widg.call_raw_to_img_part_1_hpf()
    hpf_window.read_values()
    images = [f"{proj_directory}/images/img/{i}" for i in sorted(os.listdir(proj_directory + "/images/img"))]
    assert(len(images) == 10), "Wrong number of images exported to images/img" 

'''
def test_call_instanseg_segmentor():
    instanseg_window = app.entrypoint.image_proc_widg.call_instanseg_segmentor()
    instanseg_window.single_image.configure(variable = ctk.StringVar(value = os.listdir(proj_directory + "/images/img")[0]))
    instanseg_window.read_values()
    assert(len(os.listdir(proj_directory + "/masks/instanseg_masks"  )) == 1), "Wrong number of masks exported"
'''

def test_call_mask_expand():
    expander = app.entrypoint.image_proc_widg.call_mask_expand()
    expander.image_folder.configure(variable = ctk.StringVar(value = "example_deepcell_masks"))
    expander.output_folder.configure(textvariable = ctk.StringVar(value = "expanded_deepcell_masks"))
    expander.read_values()
    images = os.listdir(proj_directory + "/masks/expanded_deepcell_masks")
    assert(len(images) == 10), "All masks not expanded" 

def test_call_intersection_difference():
    intersect = app.entrypoint.image_proc_widg.call_intersection_difference()
    intersect.masks_folder1.configure(variable = ctk.StringVar(value = "example_deepcell_masks"))
    intersect.masks_folder2.configure(variable = ctk.StringVar(value = "expanded_deepcell_masks"))
    intersect.read_values()
    print(os.listdir(proj_directory + "/masks"))
    assert(len(os.listdir(proj_directory + "/masks/example_deepcell_masks_expanded_deepcell_masks")) == 10), "Mask intersection function failed!"

def test_call_region_measurement():
    region_meas = app.entrypoint.image_proc_widg.call_region_measurement()
    region_meas.output_folder.configure(textvariable = ctk.StringVar(value = "test_analysis"))
    region_meas.masks_folder.configure(variable = ctk.StringVar(value = "example_deepcell_masks"))
    region_meas.accept_values.invoke()
    analysis_dir = app.entrypoint.image_proc_widg.Experiment_object.directory_object.Analyses_dir + "/test_analysis"
    intensities_dir = analysis_dir + "/intensities"
    assert(len(os.listdir(analysis_dir + "/regionprops")) == 10), "Wrong number of regionprops csv exported (expecting 10 to match the number of images)"
    assert(len(pd.read_csv(intensities_dir + "/CRC_1_ROI_001.ome.csv") == 2177)), "Unexpected number of cells in image 1" 

def test_call_to_Analysis():
    ## pre load metadata / analysis panel into analysis directory so that Analysis loads properly
    Analysis_panel = proj_directory + "/Analyses/Analysis_panel.csv"
    metadata = proj_directory + "/Analyses/metadata.csv"
    shutil.copyfile(Analysis_panel, proj_directory + "/Analyses/test_analysis/main/Analysis_panel.csv")
    shutil.copyfile(metadata, proj_directory + "/Analyses/test_analysis/main/metadata.csv")
    analysis_loader = app.entrypoint.image_proc_widg.call_to_Analysis()
    analysis_loader.analysis_choice.configure(variable = ctk.StringVar(value = 'test_analysis'))
    analysis_loader.run()
    app.Tabs.tables.accept_button.invoke()
    metadata = app.Tabs.py_exploratory.analysiswidg.cat_exp.metadata
    panel = app.Tabs.py_exploratory.analysiswidg.cat_exp.panel
    interal_dir = app.entrypoint.image_proc_widg.Experiment_object.directory_object.Analysis_internal_dir
    assert(os.listdir(interal_dir + "/Analysis_fcs")[0].rfind(".fcs") != -1), "FCS files not in /main/Analysis_fcs!"
    assert(len(metadata) == 10), "Automatically generated Metadata file's length does not match the number of FCS files in the experiment!"
    assert("marker_class" in panel.columns), "Automatically generated Analysis_panel file should have a 'marker_class' column"
    assert("Analysis_panel.csv" in os.listdir(interal_dir)), "Analysis_panel.csv not written to the proper place!"
    assert("metadata.csv" in os.listdir(interal_dir)), "metadata.csv not written to the proper place!"
    assert("condition" in list(pd.read_csv(interal_dir + "/metadata.csv").columns)), "Automatically generated metadata.csv file must have a 'condition' column!"

def test_FCS_choice():   ### have occur after to not disrupt tablelaunch windows (as is, does not close itself and blocks future instnaces as a singleton)
    app.entrypoint.FCS_choice(fetch_dir + "/Example_CyTOF")
    assert True 

##>>## GUI Pixel classification tests (px class creation)
def test_launch_loading_window():
    global loading_window
    loading_window = app.Tabs.px_classification.create.px_widg.launch_loading_window()   ## need access to loading window functions
    assert True 

def test_unsupervised():
    window = loading_window.unsupervised("unsupervised1", app.Tabs.px_classification.create.px_widg)
    window.image_choice.configure(variable = ctk.StringVar(value = 'img'))
    channel_2_widgets = window.keep_table.widget_list_of_lists[1]
    channel_2_widgets[1].configure(variable = ctk.StringVar(value = 'Use Channel'))
    for i in channel_2_widgets[2:]:
        i.select() 
    window.run_training()
    ## Predict the first image to test single image prediction:
    app.Tabs.px_classification.create.px_widg.predictions_frame.one.select()
    app.Tabs.px_classification.create.px_widg.predictions_frame.folder.configure(variable = ctk.StringVar(value = 'img'))
    app.Tabs.px_classification.create.px_widg.predictions_frame.one_img.configure(variable = ctk.StringVar(value = os.listdir(app.Tabs.px_classification.create.px_widg.image_directory + "/img")[0]))
    app.Tabs.px_classification.create.px_widg.predictions_frame.predict_folder.invoke()
    assert True 

def test_accept_classifier_name():   ## supervised window
    window = loading_window.accept_classifier_name("lumen_epithelia_laminapropria", app.Tabs.px_classification.create.px_widg)
    window.advanced_options()
    window.sigma_list.checkbox_list[1].select()
    for i in window.features_list.checkbox_list:
        i.select()
    counter = 0
    for i,ii in enumerate(window.dictionary_maker.dataframe['name']):
        if (i == 6) or (i ==26):
            window.dictionary_maker.row_list[counter].configure(variable = ctk.StringVar(value = ii))
            counter += 1
    window.dictionary_maker.remove_last_row()
    window.class_dict_maker.row_list[1][1].configure(textvariable = ctk.StringVar(value = 'epithelia'))
    window.class_dict_maker.row_list[1][1].configure(textvariable = ctk.StringVar(value = 'laminapropria'))
    window.set_up_classifier_details()
    assert True 

def test_training():
    training_dir = app.Tabs.px_classification.create.px_widg.classifier_dir + "/lumen_epithelia_laminapropria/training_labels"
    shutil.rmtree(training_dir)
    shutil.copytree(f"{homedir}/tests/training_labels", training_dir)
    app.Tabs.px_classification.create.px_widg.Napari_frame.choose_folder.configure(variable = ctk.StringVar(value = 'img'))
    app.Tabs.px_classification.create.px_widg.Napari_frame.training_button.invoke()
    assert True 

def test_prediction():
    app.Tabs.px_classification.create.px_widg.predictions_frame.all.select()
    app.Tabs.px_classification.create.px_widg.predictions_frame.folder.configure(variable = ctk.StringVar(value = 'img'))
    app.Tabs.px_classification.create.px_widg.predictions_frame.predict_folder.invoke()
    assert True 

def test_detail_display():
    app.Tabs.px_classification.create.px_widg.detail_display()
    assert True 

def test_bio_label_launch():
    app.Tabs.px_classification.create.px_widg.bio_label_launch()
    assert True 

def test_save_classifier():
    app.Tabs.px_classification.create.px_widg.save_classifier()
    assert True 


##>>## GUI Pixel classification tests (px class use)
def test_load_classifier():
    app.Tabs.px_classification.use_class.px_widg.load_classifier("lumen_epithelia_laminapropria")
    assert True 

def test_launch_classes_as_png():
    window = app.Tabs.px_classification.use_class.px_widg.load_and_display.launch_classes_as_png()
    window.option1.configure(variable = ctk.StringVar(value = "pixel classification"))
    if_pixel_classifier = ["classification_maps", "merged_classification_maps"]
    options = [i for i in if_pixel_classifier if i in os.listdir(window.master.master.active_classifier_dir)]
    window.option2.configure(variable = ctk.StringVar(value = options[0]))
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_classes_as_png():
    window = app.Tabs.px_classification.use_class.px_widg.load_and_display.launch_bio_labels()
    window.accept_labels()
    assert isinstance(window, ctk.CTkToplevel)


## windows to add: RegionMeasurement, Secondary_FlowSOM_Analysis_window, whole_class_analysis_window, stats_window


##>>## GUI Analysis tests
palmettobug.Analysis_widgets.Analysis_GUI.toggle_TESTING() ## prevents warning pop ups at many steps -- these block the testing suite and prevent errors from being properly debugged

def test_launch_drop_restore():           ## filtering
    window = app.Tabs.py_exploratory.analysiswidg.launch_drop_restore()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_scaling():
    window = app.Tabs.py_exploratory.analysiswidg.launch_scaling()
    window.call_scaling()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_combat_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_combat_window()
    window.do_combat()
    assert isinstance(window, ctk.CTkToplevel)

def test_do_regions():
    global my_analysis
    my_analysis = app.Tabs.py_exploratory.analysiswidg.cat_exp
    assert isinstance(my_analysis.data, anndata.AnnData)
    #my_analysis.do_regions(region_folder = proj_directory + "/masks/test_seg")
    #assert ('regions' in my_analysis.data.obs.columns), "Do regions did not generate a 'regions' column in obs!"

def test_launch_scatterplot():
    window = app.Tabs.py_exploratory.analysiswidg.launch_scatterplot()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_Plot_Counts_per_ROI_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_Plot_Counts_per_ROI_window()
    window.plot_Counts_per_ROI()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_MDS_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_MDS_window()
    window.plot_MDS()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_NRS_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_NRS_window()
    window.plot_NRS()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_Plot_histograms_per_ROI_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_Plot_histograms_per_ROI_window()
    window.plot_ROI_histograms()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_UMAP_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_UMAP_window()
    window.run_UMAP()
    window.run_UMAP(kind = 'PCA')
    assert isinstance(window, ctk.CTkToplevel)
    assert (my_analysis.PCA_embedding is not None), "do PCA did not create an anndata embedding"
    assert isinstance(my_analysis.PCA_embedding, anndata.AnnData), "do PCA did not create an anndata embedding"
    assert (my_analysis.UMAP_embedding is not None), "do UMAP did not create an anndata embedding"
    assert isinstance(my_analysis.UMAP_embedding, anndata.AnnData), "do UMAP did not create an anndata embedding"

def test_launch_cluster_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_window()
    window.run_clustering()
    try:
        metaclustering = my_analysis.data.obs['metaclustering']
    except Exception:
        metaclustering = None
    assert metaclustering is not None, "do_flowsom did not create a metaclustering column"
    assert len(metaclustering.unique()) == 20, "do_flowsom did not create the expected number of values in the metaclustering column"
    assert '1' in metaclustering, "do_flowsom did not create the expected values in metaclustering column"
    assert '20' in metaclustering,  "do_flowsom did not create the expected values in metaclustering column"

def test_launch_leiden():
    window =  app.Tabs.py_exploratory.analysiswidg.launch_leiden()
    window.do_leiden()
    assert isinstance(window, ctk.CTkToplevel)
    try:
        leiden = my_analysis.data.obs['leiden']
    except Exception:
        leiden = None
    assert leiden is not None,  "do_leiden did not create a leiden column"
    number_of_leiden =  len(leiden.unique())
    assert '1' in leiden, "do_leiden did not create the expected values in leiden column"
    assert str(number_of_leiden) in leiden, "do_ledien did not create the expected values in leiden column"

def test_launch_plot_UMAP_window():     ### this window handles UMAP, PCA, and facetted varieties of both
    window = app.Tabs.py_exploratory.analysiswidg.launch_plot_UMAP_window()
    window.plot_UMAP(subsetting_column = 'antigens', color_column = "HistoneH3", filename = 'UMAP_antigens', kind = 'UMAP')
    window.plot_UMAP(subsetting_column = 'condition', color_column = "HistoneH3", filename = 'UMAP_condition', kind = 'UMAP')
    window.plot_UMAP(subsetting_column = 'Do not Facet', color_column = "HistoneH3", filename = 'UMAP_single', kind = 'UMAP')
    window.plot_UMAP(subsetting_column = 'Do not Facet', color_column = "HistoneH3", filename = 'PCA_single', kind = 'PCA')
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_Exprs_Heatmap_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_Exprs_Heatmap_window()
    window.plot_Heatmap()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_cluster_heatmap_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_heatmap_window()
    #window.pop_up.select()
    window.plot_cluster_heatmap()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_distrib_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_distrib_window()
    window.plot_clusterV(clustering_column = 'sample_id', 
                      type_of_graph = 'violin', 
                      type_of_comp = 'Raw Group values (no substraction of rest of dataset)', 
                      filename = "clusterV_distrib_etc", 
                      marker_class = "type")
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_ClusterVGroup():
    window = app.Tabs.py_exploratory.analysiswidg.launch_ClusterVGroup()
    window.plot_clusterV(clustering_column = 'metaclustering', 
                      type_of_graph = 'violin', 
                      type_of_comp = 'Raw Cluster values (no substraction of rest of dataset)', 
                      filename = "clusterV_distrib_etc2", 
                      marker_class = "type")
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_plot_cluster_expression_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_plot_cluster_expression_window()
    window.clustering_option.configure(variable = ctk.StringVar(value = "metaclustering"))
    window.antigen.configure(variable = ctk.StringVar(value = "HistoneH3"))
    window.run_py_plot_cluster_histograms()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_abundance_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_abundance_window()
    window.plot_abundance(k = "metaclustering", by = "stacked barplot", filename = "Plot_12")
    window.plot_abundance(k = "metaclustering", by = "cluster boxplot", filename = "Plot_112")
    window.plot_abundance(k = "metaclustering", by = "cluster stripplot", filename = "Plot_1112")
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_cluster_stats_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_stats_window()
    window.column_type.configure(variable = ctk.StringVar(value = "metaclustering"))
    window.button.invoke()
    window.launch_stat_table("1", True, "metaclustering")
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_cluster_merging():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_merging()
    for ii,i in enumerate(window.new.table.widgetframe['1']):
        value = ii % 4   ## generate 4 fake clusters
        i.configure(textvariable = ctk.StringVar(value = f"c{str(value)}"))
    window.new.button.invoke()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_classy_masker():
    window = app.Tabs.py_exploratory.analysiswidg.launch_classy_masker()
    window.classy_mask(clustering = "metaclustering")
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_regionprop():
    window = app.Tabs.py_exploratory.analysiswidg.launch_regionprop()
    #assert isinstance(window, ctk.CTkToplevel)

def test_launch_cluster_save_load():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_save_load()
    window.load_type.configure(variable = ctk.StringVar(value = "metaclustering"))
    window.saver_button.invoke()
    print(app.Tabs.py_exploratory.analysiswidg.cat_exp.directory  + "/clusterings")
    print(os.listdir(app.Tabs.py_exploratory.analysiswidg.cat_exp.directory + "/clusterings"))
    window.load_identifier.configure(variable = ctk.StringVar(value = os.listdir(app.Tabs.py_exploratory.analysiswidg.cat_exp.directory + "/clusterings")[0]))
    window.loader_button.invoke()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_data_table_exportation_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_data_table_exportation_window()
    window.subset_command()
    window.grouping_command()
    window.plain_command()
    window.whole_command()
    window.button1.invoke()
    window.umap_pca_button.invoke()
    assert isinstance(window, ctk.CTkToplevel)

##>>## GUI Spatial tests
palmettobug.Analysis_widgets.Spatial_GUI.toggle_TESTING()

def test_plot_cell_maps_window():
    window = app.Tabs.Spatial.widgets.plot_cell_maps_window()
    list_of_file_names = [(i[:i.rfind(".ome.fcs")]) for i in sorted(list(window.master.master_exp.data.obs['file_name'].unique()))]
    window.python_run_cell_maps(multi_or_single = list_of_file_names[0], clustering = 'metaclustering', masks = "masks")
    window.python_run_cell_maps(multi_or_single = list_of_file_names[1], clustering = 'metaclustering', masks = "points")
    assert isinstance(window, ctk.CTkToplevel)

def test_SpaceANOVA():
    window = app.Tabs.Spatial.widgets.widgets.launch()
    window.load_and_run_spatial_analysis(min_radius = 10, 
                                         max_radii = 100, 
                                         step = 5, 
                                         condition_comparison = "All (multicomparison)", 
                                         celltype_key = 'merging', 
                                         permutations = 2, 
                                         seed = 42)
    assert isinstance(window, ctk.CTkToplevel)

def test_SpaceANOVA_stats_and_heatmap():
    window = app.Tabs.Spatial.widgets.widgets.launch_heat_plot()
    assert isinstance(window, ctk.CTkToplevel) 

def test_SpaceANOVA_function_plots():
    window = app.Tabs.Spatial.widgets.widgets.launch_function_plot()
    assert isinstance(window, ctk.CTkToplevel)

def test_do_neighbors():
    app.Tabs.Spatial.widgets.squidpy_spatial.do_neighbors()
    assert True

def test_sq_centrality():
    window = app.Tabs.Spatial.widgets.squidpy_spatial.launch_centrality_window()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)

def test_sq_inter_mat():
    window = app.Tabs.Spatial.widgets.squidpy_spatial.launch_interaction_matrix_window()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.facet.configure(variable = ctk.StringVar(value = "condition"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)

def test_sq_neigh_enrich():
    window = app.Tabs.Spatial.widgets.squidpy_spatial.launch_neigh_enrich_window()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.facet.configure(variable = ctk.StringVar(value = "condition"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)

def test_CN_window():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_CN_window()
    window.celltype.configure(variable = ctk.StringVar(value = "merging"))
    window.run_cellular_neighborhoods()
    assert isinstance(window, ctk.CTkToplevel)

def test_CN_save_load():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_save_load()
    window.save()
    saved_clusterings = [i for i in sorted(os.listdir(window.master.master.master_exp.clusterings_dir)) if (i.find("cellular_neighborhood") != -1)]
    window.path.configure(variable = ctk.StringVar(value = saved_clusterings[0]))
    window.reload()
    assert isinstance(window, ctk.CTkToplevel)

def test_CN_annot():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_annotation()
    for ii,i in enumerate(window.new.table.widgetframe['1']):
        value = ii % 4   ## generate 4 fake clusters
        i.configure(textvariable = ctk.StringVar(value = f"c{str(value)}"))
    window.annotate(id = 'CN_merge')
    assert isinstance(window, ctk.CTkToplevel)

def test_CN_heatmap():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_heatmap_window()
    print(window.master.clustering)
    #window.clustering.configure(variable = ctk.StringVar("merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)

def test_CN_abundance():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_abundance_window()
    window.clustering.configure(variable = ctk.StringVar("merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)

def test_CN_UMAP_or_MST():
    window = app.Tabs.Spatial.widgets.CN_widgets.clustermap_window()
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_edt():
    window = app.Tabs.Spatial.widgets.test_edt.launch_load_window()
    window.pixel_class_entry.configure(textvariable = ctk.StringVar(value = proj_directory + "/Pixel_Classification/lumen_epithelia_laminapropria"))
    window.do_dist_transform()
    assert isinstance(window, ctk.CTkToplevel)

def test_edt_reload_window():
    window = app.Tabs.Spatial.widgets.test_edt.launch_reload_window()
    options = [i for i in sorted(os.listdir(window.folder)) if i.lower().find(".csv") != -1]
    window.choice.configure(variable = ctk.StringVar(value = options[0]))
    #window.reload()
    assert isinstance(window, ctk.CTkToplevel)

def test_edt_stats_window():
    window = app.Tabs.Spatial.widgets.test_edt.launch_stat_window()
    window.groupby_column.configure(variable = ctk.StringVar(value = "merging"))
    window.do_stats()
    assert isinstance(window, ctk.CTkToplevel)

def test_edt_distrib_window():
    window = app.Tabs.Spatial.widgets.test_edt.launch_distrib_window()
    window.var_column.configure(variable = ctk.StringVar(value = "HistoneH3"))
    window.subset_col.configure(variable = ctk.StringVar(value = "merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)

def test_edt_heatmap_window():
    window = app.Tabs.Spatial.widgets.test_edt.launch_heatmap_window()
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)

def test_toggle_in_gui():
    palmettobug.ImageProcessing.ImageAnalysisClass.toggle_in_gui()   ## really here to reset --> not being in the gui after testing the App above
