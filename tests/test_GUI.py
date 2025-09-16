import os

import palmettobug
from palmettobug.Entrypoint.app_and_entry import App, fetch_IMC_example, fetch_CyTOF_example

homedir = __file__.replace("\\","/")
homedir = homedir[:(homedir.rfind("/"))]
homedir = homedir[:(homedir.rfind("/"))]
fetch_dir = homedir + "/project_folder"
if not os.path.exists(fetch_dir):
    os.mkdir(fetch_dir)
proj_directory = fetch_dir + "/Example_IMC"

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

def test_FCS_choice():
    app.entrypoint.FCS_choice(fetch_dir + "/Example_CyTOF")
    assert True  


##>>## GUI Image Analysis tests
def test_call_raw_to_img_part_1_hpf():
    hpf_window = app.entrypoint.image_proc_widg.call_raw_to_img_part_1_hpf()
    hpf_window.read_values()
    images = [f"{proj_directory}/images/img/{i}" for i in sorted(os.listdir(proj_directory + "/images/img"))]
    assert(len(images) == 10), "Wrong number of images exported to images/img" 

def test_call_instanseg_segmentor():
    instanseg_window = app.entrypoint.image_proc_widg.call_instanseg_segmentor()
    instanseg_window.single_image.configure(values = os.listdir(proj_directory + "/images/img")[0])
    instanseg_window.read_values()
    assert(len(os.listdir(proj_directory + "/masks/instanseg_masks"  )) == 1), "Wrong number of masks exported"

def test_call_mask_expand():
    expander = app.entrypoint.image_proc_widg.call_mask_expand()
    expander.image_folder.configure(values = "example_deepcell_masks")
    expander.output_folder.configure(textvariable = ctk.StringVar(value = "expanded_deepcell_masks"))
    expander.read_values()
    images = os.listdir(proj_directory + "/masks/expanded_deepcell_masks")
    assert(len(images) == 10), "All masks not expanded" 

def test_call_intersection_difference():
    intersect = app.entrypoint.image_proc_widg.call_intersection_difference()
    masks1 = proj_directory + "/masks/example_deepcell_masks"
    masks2 = proj_directory + "/masks/expanded_deepcell_masks"
    intersect.masks_folder1.configure(variable = ctk.StringVar(value = "example_deepcell_masks"))
    intersect.masks_folder2.configure(variable = ctk.StringVar(value = "expanded_deepcell_masks"))
    intersect.read_values()
    assert(len(os.listdir(proj_directory + "/masks/example_deepcell_masks_expanded_deepcell_masks"  )) == 10), "Mask intersection function failed!"

def test_call_region_measurement():
    region_meas = app.entrypoint.image_proc_widg.call_region_measurement()
    region_meas.output_folder.configure(textvariable = ctk.StringVar(value = "test_analysis"))
    region_meas.masks_folder.configure(variable = ctk.StringVar(value = "example_deepcell_masks"))
    region_meas.read_values(app.entrypoint.image_proc_widg.Experiment_object)
    analysis_dir = app.entrypoint.image_proc_widg.Experiment_object.directory_object.Analyses_dir + "/test_analysis"
    intensities_dir = analysis_dir + "/intensities"
    assert(len(os.listdir(analysis_dir + "/regionprops")) == 10), "Wrong number of regionprops csv exported (expecting 10 to match the number of images)"
    assert(len(pd.read_csv(intensities_dir + "/CRC_1_ROI_001.ome.csv") == 2177)), "Unexpected number of cells in image 1" 

def test_call_to_Analysis():
    analysis_loader = app.entrypoint.image_proc_widg.call_to_Analysis()
    analysis_loader.analysis_choice.configure(value = 'test_analysis')
    metadata = app.Tabs.py_exploratory.analysiswidg.cat_exp.metadata
    panel = app.Tabs.py_exploratory.analysiswidg.cat_exp.panel
    interal_dir = app.entrypoint.image_proc_widg.Experiment_object.directory_object.Analysis_internal_dir
    assert(os.listdir(interal_dir + "/Analysis_fcs")[0].rfind(".fcs") != -1), "FCS files not in /main/Analysis_fcs!"
    assert(len(metadata) == 10), "Automatically generated Metadata file's length does not match the number of FCS files in the experiment!"
    assert("marker_class" in panel_file.columns), "Automatically generated Analysis_panel file should have a 'marker_class' column"
    assert("Analysis_panel.csv" in os.listdir(interal_dir)), "Analysis_panel.csv not written to the proper place!"
    assert("metadata.csv" in os.listdir(interal_dir)), "metadata.csv not written to the proper place!"
    assert("condition" in list(pd.read_csv(interal_dir + "/metadata.csv").columns)), "Automatically generated metadata.csv file must have a 'condition' column!"


'''
##>>## GUI Pixel classification tests (px class creation)
def test_launch_loading_window():
    global loading_window
    loading_window = app.Tabs.px_classification.create.px_widg.launch_loading_window()   ## need access to loading window functions
    assert True 

def test_unsupervised():
    loading_window.unsupervised("unsupervised1")
    assert True 

def test_accept_classifier_name():   ## supervised window
    loading_window.accept_classifier_name("supervised1")
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

def test_load_classifier():
    app.Tabs.px_classification.use_class.px_widg.load_classifier("lumen_epithelia_laminapropria")
    assert True 
'''



##>>## GUI Analysis tests



############################################ Some test require that an Analysis is loaded, these are currently commented out ############################

#def test_launch_scatterplot():
#    app.Tabs.py_exploratory.analysiswidg.launch_scatterplot()

#def test_launch_classy_masker():
#    app.Tabs.py_exploratory.analysiswidg.launch_classy_masker()

def test_launch_leiden():
    app.Tabs.py_exploratory.analysiswidg.launch_leiden()

def test_launch_UMAP_window():
    app.Tabs.py_exploratory.analysiswidg.launch_UMAP_window()

#def test_launch_ClusterVGroup():
#    app.Tabs.py_exploratory.analysiswidg.launch_ClusterVGroup()

def test_launch_distrib_window():
    app.Tabs.py_exploratory.analysiswidg.launch_distrib_window()

def test_launch_plot_UMAP_window():
    app.Tabs.py_exploratory.analysiswidg.launch_plot_UMAP_window()

def test_launch_cluster_window():
    app.Tabs.py_exploratory.analysiswidg.launch_cluster_window()

def test_launch_Exprs_Heatmap_window():
    app.Tabs.py_exploratory.analysiswidg.launch_Exprs_Heatmap_window()

def test_launch_Plot_Counts_per_ROI_window():
    app.Tabs.py_exploratory.analysiswidg.launch_Plot_Counts_per_ROI_window()

def test_launch_Plot_histograms_per_ROI_window():
    app.Tabs.py_exploratory.analysiswidg.launch_Plot_histograms_per_ROI_window()

def test_launch_MDS_window():
    app.Tabs.py_exploratory.analysiswidg.launch_MDS_window()

def test_launch_NRS_window():
    app.Tabs.py_exploratory.analysiswidg.launch_NRS_window()

#def test_launch_abundance_window():
#    app.Tabs.py_exploratory.analysiswidg.launch_abundance_window()

#def test_launch_cluster_heatmap_window():
#    app.Tabs.py_exploratory.analysiswidg.launch_cluster_heatmap_window()

#def test_launch_plot_cluster_expression_window():
#    app.Tabs.py_exploratory.analysiswidg.launch_plot_cluster_expression_window()

#def test_launch_cluster_stats_window():
#    app.Tabs.py_exploratory.analysiswidg.launch_cluster_stats_window()

#def test_launch_regionprop():
#    app.Tabs.py_exploratory.analysiswidg.launch_regionprop()

#def test_launch_cluster_merging():
#    app.Tabs.py_exploratory.analysiswidg.launch_cluster_merging()

def test_launch_drop_restore():
    app.Tabs.py_exploratory.analysiswidg.launch_drop_restore()

def test_launch_scaling():
    app.Tabs.py_exploratory.analysiswidg.launch_scaling()

#def test_launch_cluster_save_load():
#    app.Tabs.py_exploratory.analysiswidg.launch_cluster_save_load()

#def test_launch_data_table_exportation_window():
#    app.Tabs.py_exploratory.analysiswidg.launch_data_table_exportation_window(app.Tabs.py_exploratory.analysiswidg.cat_exp.data)


def test_launch_combat_window():
    app.Tabs.py_exploratory.analysiswidg.launch_combat_window()




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

