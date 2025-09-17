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

## needed when only testing GUI (otherwise can depend on px classifier script)
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
    assert True 

def test_accept_classifier_name():   ## supervised window
    window = loading_window.accept_classifier_name("lumen_epithelia_laminapropria", app.Tabs.px_classification.create.px_widg)
    window.advanced_options()
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
def test_launch_classes_as_png():
    app.Tabs.px_classification.use_class.px_widg.load_and_display.launch_classes_as_png()
    assert True 

#def test_load_classifier():
#    app.Tabs.px_classification.use_class.px_widg.load_classifier("lumen_epithelia_laminapropria")
#    assert True 


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
    #print(len(my_analysis.data.obs))
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
                      type_of_comp = 'Raw Group values (no substraction of rest of dataset)', 
                      filename = "clusterV_distrib_etc", 
                      marker_class = "type")
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_plot_cluster_expression_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_plot_cluster_expression_window()
    self.clustering_option.configure(variable = ctk.StringVar(value = "metaclustering"))
    self.antigen.configure(variable = ctk.StringVar(value = "HistoneH3"))
    window.run_py_plot_cluster_histograms()
    assert isinstance(window, ctk.CTkToplevel)



def test_launch_abundance_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_abundance_window()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_cluster_stats_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_stats_window()
    assert isinstance(window, ctk.CTkToplevel)

#def test_launch_cluster_merging():
#    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_merging()
#    assert isinstance(window, ctk.CTkToplevel)

def test_launch_classy_masker():
    window = app.Tabs.py_exploratory.analysiswidg.launch_classy_masker()
    window.classy_mask(clustering = "metaclustering")
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_regionprop():
    window = app.Tabs.py_exploratory.analysiswidg.launch_regionprop()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_cluster_save_load():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_save_load()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_data_table_exportation_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_data_table_exportation_window()
    assert isinstance(window, ctk.CTkToplevel)



##>>## GUI Spatial tests
def test_launch_edt():
    app.Tabs.Spatial.widgets.launch_edt()
    assert True 

#def test_plot_cell_maps_window():
#    app.Tabs.Spatial.widgets.plot_cell_maps_window()
 #   assert True 

# spatial windows to test:    launch_heat_plot_window, launch_function_plot_window, launch_window, NeigborhoodEnrichmentWindow, CentralityWindow, InteractionMatrixWindow
                # CNUMAPMSTwindow, CNabundanceWindow, CNheatmapWindow, CNannotationWindow, CNwindowSaveLoad, CellularNeighborhoodWindow, edt_heatmap_window
                # edt_dist_window, edt_stat_window, edt_reload_window

def test_toggle_in_gui():
    palmettobug.ImageProcessing.ImageAnalysisClass.toggle_in_gui()   ## really here to reset --> not being in the gui after testing the App above
