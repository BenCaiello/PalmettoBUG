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
    window = app.entrypoint.show_GPL()
    window.display_main()
    window.display_3rd()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_call_configGUI():
    window = app.entrypoint.call_configGUI()
    window.toggle_light_dark()
    window.slider_moved(1.0)
    window = window.change_theme('blue')
    window = window.change_theme('green') ### reset so local tests change less for git versioning (assets theme file)
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launchExampleDataWindow():
    window = app.entrypoint.launchExampleDataWindow()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_img_entry_func():
    number = app.entrypoint.img_entry_func(proj_directory)  ## successfully proceeding through function in tests
    assert True 


##>>## GUI Image Analysis tests
def test_call_raw_to_img_part_1_hpf():
    hpf_window = app.entrypoint.image_proc_widg.call_raw_to_img_part_1_hpf()
    hpf_window.read_values()
    images = [f"{proj_directory}/images/img/{i}" for i in sorted(os.listdir(proj_directory + "/images/img"))]
    assert(len(images) == 10), "Wrong number of images exported to images/img" 

def test_call_instanseg_segmentor():
    instanseg_window = app.entrypoint.image_proc_widg.call_instanseg_segmentor()
    instanseg_window.single_image.configure(variable = ctk.StringVar(value = os.listdir(proj_directory + "/images/img")[0]))
    w_window = instanseg_window.read_values()
    w_window.destroy()
    assert(len(os.listdir(proj_directory + "/masks/instanseg_masks"  )) == 1), "Wrong number of masks exported"
    instanseg_window.destroy()

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
    intersect.destroy()

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
    window = app.entrypoint.FCS_choice(fetch_dir + "/Example_CyTOF")
    window.table_launcher.destroy()

##>>## GUI Pixel classification tests (px class creation)
def test_toggle1a():
    palmettobug.Pixel_Classification.Classifiers_GUI.toggle_TESTING()
    assert (palmettobug.Pixel_Classification.Classifiers_GUI._TESTING is True)

def test_launch_loading_window():
    global loading_window
    loading_window = app.Tabs.px_classification.create.px_widg.launch_loading_window()   ## need access to loading window functions
    assert True 

def test_unsupervised():
    window = loading_window.unsupervised("unsupervised1", app.Tabs.px_classification.create.px_widg)
    window.training_number.configure(textvariable = ctk.StringVar(value = "25000"))
    window.image_choice.configure(variable = ctk.StringVar(value = 'img'))
    window.smoothing_choice.configure(variable = ctk.StringVar(value = '2'))
    channel_2_widgets = window.keep_table.widget_list_of_lists[1]
    channel_2_widgets[1].configure(variable = ctk.StringVar(value = 'Use Channel'))
    for i in channel_2_widgets[2:]:
        i.select() 
    warning_window = window.run_training()
    warning_window.destroy()
    ## Predict the first image to test single image prediction:
    app.Tabs.px_classification.create.px_widg.predictions_frame.one.select()
    app.Tabs.px_classification.create.px_widg.predictions_frame.folder.configure(variable = ctk.StringVar(value = 'img'))
    app.Tabs.px_classification.create.px_widg.predictions_frame.one_img.configure(variable = ctk.StringVar(value = os.listdir(app.Tabs.px_classification.create.px_widg.image_directory + "/img")[0]))
    app.Tabs.px_classification.create.px_widg.predictions_frame.predict_folder.invoke()
    assert True 

def test_accept_classifier_name():   ## supervised window
    window = loading_window.accept_classifier_name("lumen_epithelia_laminapropria", app.Tabs.px_classification.create.px_widg)
    advanced_window = window.advanced_options()
    advanced_window.retrieve_and_accept()
    window.sigma_list.checkbox_list[1].select()
    for ii,i in enumerate(window.features_list.checkbox_list):
        if (ii < 2) or (ii > 8):
            i.select()
    counter = 0
    for i,ii in enumerate(window.dictionary_maker.dataframe['name']):
        if (i == 6) or (i ==26):
            window.dictionary_maker.row_list[counter].configure(variable = ctk.StringVar(value = ii))
            counter += 1
    window.dictionary_maker.remove_last_row()
    window.class_dict_maker.row_list[1][1].configure(textvariable = ctk.StringVar(value = 'epithelia'))
    window.class_dict_maker.row_list[2][1].configure(textvariable = ctk.StringVar(value = 'laminapropria'))
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
    window = app.Tabs.px_classification.create.px_widg.detail_display()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_bio_label_launch():
    window = app.Tabs.px_classification.create.px_widg.bio_label_launch()
    window.save_labels_csv()
    window.plot_heatmap()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_save_classifier():
    app.Tabs.px_classification.create.px_widg.save_classifier()
    assert True 

def test_segmentation():
    app.Tabs.px_classification.create.px_widg.segment_frame.input_folder.configure(variable = ctk.StringVar(value = "classification_maps"))
    app.Tabs.px_classification.create.px_widg.segment_frame.run_seg()
    assert True 


##>>## GUI Pixel classification tests (px class use)
def test_toggle1b():
    palmettobug.Pixel_Classification.use_classifiers_GUI.toggle_TESTING()
    assert (palmettobug.Pixel_Classification.use_classifiers_GUI._TESTING is True)

def test_load_classifier():
    global px_use_widgets
    px_use_widgets = app.Tabs.px_classification.use_class.px_widg
    px_use_widgets.load_classifier("lumen_epithelia_laminapropria")
    assert True 

def test_launch_classes_as_png():
    window = px_use_widgets.load_and_display.launch_classes_as_png()
    window.option1.configure(variable = ctk.StringVar(value = "pixel classification"))
    if_pixel_classifier = ["classification_maps", "merged_classification_maps"]
    options = [i for i in if_pixel_classifier if i in os.listdir(window.master.master.active_classifier_dir)]
    window.option2.configure(variable = ctk.StringVar(value = options[0]))
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_bio_labels():
    window = px_use_widgets.load_and_display.launch_bio_labels()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_filter():
    px_use_widgets.filter.filter_list.checkbox_list[0].select()
    px_use_widgets.filter.filter_images()
    assert True

def test_classify_masks_on_mode():
    px_use_widgets.classify_cells.mask_option_menu.configure(variable = ctk.StringVar(value = "expanded_deepcell_masks"))
    px_use_widgets.classify_cells.do_classy_masks()
    assert True

def test_classify_masks_on_flowsom():
    px_use_widgets.classify_cells.classifier_option_menu.configure(variable = ctk.StringVar(value = "classification_maps"))
    px_use_widgets.classify_cells.mask_option_menu.configure(variable = ctk.StringVar(value = "example_deepcell_masks"))
    px_use_widgets.classify_cells.radioframe_do_secondary_flowsom.radio_SOM.invoke()
    global secondary_FlowSOM_window
    secondary_FlowSOM_window = px_use_widgets.classify_cells.do_classy_masks()
    assert isinstance(secondary_FlowSOM_window, ctk.CTkToplevel)

def test_secondary_FlowSOM_merge():
    secondary_FlowSOM_window.new_heatmap()
    list_of_classes = ['background','epithelia','laminapropria']
    for ii,i in enumerate(secondary_FlowSOM_window.secondary_labels.entry_list):
        value = ii % 3   ## cycle through available classes using a mod
        value = list_of_classes[value]
        i.configure(variable = ctk.StringVar(value = str(value)))
    secondary_FlowSOM_window.run_labeling()

def test_mask_extend():
    px_use_widgets.merge_class_masks.mask_option_menu.configure(variable = ctk.StringVar(value = "expanded_deepcell_masks"))
    options = [i for i in sorted(os.listdir(px_use_widgets.merge_class_masks.master.main_directory + "/classy_masks")) if i.find(".") == -1]  
    px_use_widgets.merge_class_masks.classy_mask_option_menu.configure(variable = ctk.StringVar(value = options[0]))
    px_use_widgets.merge_class_masks.output_name.configure(textvariable = ctk.StringVar(value = "extended_masks"))
    px_use_widgets.merge_class_masks.select_table.checkbox_list[1].select()
    px_use_widgets.merge_class_masks.run_merging()
    assert True

def test_whole_class_analysis_1():
    px_use_widgets.whole_class.classifier_option_menu.configure(variable = ctk.StringVar(value = "classification_maps"))
    region_window = px_use_widgets.whole_class.create()
    assert isinstance(region_window, ctk.CTkToplevel)
    region_window.read_values(px_use_widgets.whole_class.master.Experiment_object)

def test_wca_2():
    table_launcher = px_use_widgets.whole_class.add_panel()
    assert isinstance(table_launcher, ctk.CTkToplevel)
    table_launcher.accept_and_return(None)

def test_wca_3():
    wca_window = px_use_widgets.whole_class.launch_analysis()
    wca_window.plot_distribution_exprs(wca_window.class_to_barplot.get(),"Violin","crazy_filename_to_avoid_collisions")
    export_window = wca_window.launch_export_window()
    export_window.export_table()
    assert isinstance(export_window, ctk.CTkToplevel)
    export_window.destroy()
    stats_window = wca_window.stats(wca_window)
    assert isinstance(stats_window, ctk.CTkToplevel)
    stats_window.destroy()
    wca_window.destroy()


##>>## GUI Analysis tests
def test_toggle2():
    palmettobug.Analysis_widgets.Analysis_GUI.toggle_TESTING() ## prevents warning pop ups at many steps -- these block the testing suite and prevent errors from being properly debugged
    assert (palmettobug.Analysis_widgets.Analysis_GUI._TESTING is True)

def test_launch_drop_restore():           ## filtering
    window = app.Tabs.py_exploratory.analysiswidg.launch_drop_restore()  ##>>##
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_scaling():
    window = app.Tabs.py_exploratory.analysiswidg.launch_scaling()
    window.call_scaling()    ##>>##
    global my_analysis
    my_analysis = app.Tabs.py_exploratory.analysiswidg.cat_exp
    assert isinstance(my_analysis.data, anndata.AnnData)
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_scaling():
    scaling_options = ["%quantile", "min_max", "standard", "robust", "qnorm", "unscale"]
    my_analysis.do_scaling("unscale")
    original_X = my_analysis.data.X.copy()
    greater_than_zero = (original_X > 0)
    for i in scaling_options:
        my_analysis.do_scaling(scaling_algorithm = i)
        if i != "unscale":
            assert (my_analysis.data.X[greater_than_zero] != original_X[greater_than_zero]).sum().sum() > 0, "Scaling should change some of the data points > 0!"
        else:
            assert (my_analysis.data.X != original_X).sum().sum() == 0, "Unscaling did not restore the original data!"

def test_do_regions():
    my_analysis.do_regions(region_folder = proj_directory + "/masks/expanded_deepcell_masks")
    assert ('regions' in my_analysis.data.obs.columns), "Do regions did not generate a 'regions' column in obs!"

#def test_spatial_leiden():
#    my_analysis._do_spatial_leiden()
#    assert ('spatial_leiden' in my_analysis.data.obs.columns), "Do spatial_leiden did not generate a 'spatial_leiden' column in obs!"

def test_launch_combat_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_combat_window()
    window.do_combat()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_scatterplot():
    window = app.Tabs.py_exploratory.analysiswidg.launch_scatterplot()   ##>>##
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_Plot_Counts_per_ROI_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_Plot_Counts_per_ROI_window()
    figure = window.plot_Counts_per_ROI()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "Count plot did not return a matplotlib figure"
    window.destroy()

def test_launch_MDS_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_MDS_window()
    figure, df = window.plot_MDS()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "MDS plot did not return a matplotlib figure"
    assert isinstance(df, pd.DataFrame), "MDS plot did not return a pandas DataFrame"
    window.destroy()

def test_launch_NRS_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_NRS_window()
    figure = window.plot_NRS()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "NRS plot did not return a matplotlib figure"
    window.destroy()

def test_launch_Plot_histograms_per_ROI_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_Plot_histograms_per_ROI_window()
    figure = window.plot_ROI_histograms()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "ROI histogram plot did not return a matplotlib figure"
    window.destroy()

def test_launch_UMAP_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_UMAP_window()
    w_window = window.run_UMAP()
    window.run_UMAP(kind = 'PCA')
    w_window.destroy()
    assert isinstance(window, ctk.CTkToplevel)
    assert (my_analysis.PCA_embedding is not None), "do PCA did not create an anndata embedding"
    assert isinstance(my_analysis.PCA_embedding, anndata.AnnData), "do PCA did not create an anndata embedding"
    assert (my_analysis.UMAP_embedding is not None), "do UMAP did not create an anndata embedding"
    assert isinstance(my_analysis.UMAP_embedding, anndata.AnnData), "do UMAP did not create an anndata embedding"

def test_launch_cluster_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_window()
    w_window, fs = window.run_clustering()
    w_window.destroy()
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
    figure = window.plot_UMAP(subsetting_column = 'antigens', color_column = "HistoneH3", filename = 'UMAP_antigens', kind = 'UMAP')
    assert isinstance(figure, matplotlib.figure.Figure), "UMAP facetted by antigen plot did not return a matplotlib figure"

    figure = window.plot_UMAP(subsetting_column = 'condition', color_column = "HistoneH3", filename = 'UMAP_condition', kind = 'UMAP')
    assert isinstance(figure, matplotlib.figure.Figure), "Facetted UMAP plot did not return a matplotlib figure"

    figure = window.plot_UMAP(subsetting_column = 'Do not Facet', color_column = "HistoneH3", filename = 'UMAP_single', kind = 'UMAP')
    assert isinstance(figure, matplotlib.figure.Figure), "UMAP plot did not return a matplotlib figure"

    figure = window.plot_UMAP(subsetting_column = 'Do not Facet', color_column = "HistoneH3", filename = 'PCA_single', kind = 'PCA')
    assert isinstance(figure, matplotlib.figure.Figure), "PCA plot did not return a matplotlib figure"

    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_Exprs_Heatmap_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_Exprs_Heatmap_window()
    figure = window.plot_Heatmap()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "ROI medians Heatmap plot did not return a matplotlib figure"
    window.destroy()

def test_launch_cluster_heatmap_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_heatmap_window()
    #window.pop_up.select()
    figure = window.plot_cluster_heatmap()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "Cluster medians Heatmap plot did not return a matplotlib figure"
    window.destroy()

def test_launch_distrib_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_distrib_window()
    figure = window.plot_clusterV(clustering_column = 'sample_id', 
                      type_of_graph = 'violin', 
                      type_of_comp = 'Raw Group values (no substraction of rest of dataset)', 
                      filename = "clusterV_distrib_etc", 
                      marker_class = "type")
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "ROI distributions (violin)plot did not return a matplotlib figure"
    window.destroy()

def test_launch_ClusterVGroup():
    window = app.Tabs.py_exploratory.analysiswidg.launch_ClusterVGroup()
    figure = window.plot_clusterV(clustering_column = 'metaclustering', 
                      type_of_graph = 'bar', 
                      type_of_comp = 'Raw Cluster values (no substraction of rest of dataset)', 
                      filename = "clusterV_distrib_etc2", 
                      marker_class = "type")
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "cluster distributions (bar)plot did not return a matplotlib figure"
    window.destroy()

def test_launch_plot_cluster_expression_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_plot_cluster_expression_window()
    window.clustering_option.configure(variable = ctk.StringVar(value = "metaclustering"))
    window.antigen.configure(variable = ctk.StringVar(value = "Pan-Keratin"))
    figure = window.run_py_plot_cluster_histograms()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "cluster histograms plot did not return a matplotlib figure"
    window.destroy()

def test_launch_abundance_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_abundance_window()
    figure = window.plot_abundance(k = "metaclustering", by = "stacked barplot", filename = "Plot_12")
    assert isinstance(figure, matplotlib.figure.Figure), "abundance 1 plot did not return a matplotlib figure"
    figure = window.plot_abundance(k = "metaclustering", by = "cluster boxplot", filename = "Plot_112")
    assert isinstance(figure, matplotlib.figure.Figure), "abundance 2 (box)plot did not return a matplotlib figure"
    figure = window.plot_abundance(k = "metaclustering", by = "cluster stripplot", filename = "Plot_1112")
    assert isinstance(figure, matplotlib.figure.Figure), "abundance 2 (strip)plot did not return a matplotlib figure"
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_cluster_stats_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_stats_window()
    window.column_type.configure(variable = ctk.StringVar(value = "metaclustering"))
    window.button.invoke()
    output_dict, table_launch = window.launch_stat_table("1", True, "metaclustering")
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(output_dict, dict), "do_cluster_stats did not return a dictionary"
    assert len(output_dict) == len(my_analysis.data.obs['metaclustering'].unique()), "cluster statistics dictionary did not have expected length"
    assert len(output_dict[1]) == (my_analysis.data.var['marker_class'] == 'type').sum(), "cluster statistics dictionary sub-dataframe did not have expected length"
    assert isinstance(table_launch, ctk.CTkToplevel)
    table_launch.destroy()
    window.destroy()

def test_launch_cluster_merging():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_merging()
    for ii,i in enumerate(window.new.table.widgetframe['1']):
        value = ii % 4   ## generate 4 fake clusters
        i.configure(textvariable = ctk.StringVar(value = f"c{str(value)}"))
    window.new.button.invoke()
    assert isinstance(window, ctk.CTkToplevel)
    assert ('merging' in my_analysis.data.obs.columns), "do_merging did not add a merging!"
    assert len(my_analysis.data.obs['merging'].unique()) == 4, "do_merging did not add the expected number of merging categories!"
    window.destroy()

def test_launch_classy_masker():
    window = app.Tabs.py_exploratory.analysiswidg.launch_classy_masker()
    data_df = window.classy_mask(clustering = "metaclustering")
    assert isinstance(window, ctk.CTkToplevel)
    #assert len(data_df) == len(my_analysis.back_up_data)
    window.destroy()

def test_launch_abundance_ANOVAs_window():
    window = app.Tabs.py_exploratory.analysiswidg.hypothesis_widget.launch_abundance_ANOVAs_window()
    window.column.configure(variable = ctk.StringVar(value = "merging"))
    df, table_launch = window.run_ANOVAs()
    assert isinstance(table_launch, ctk.CTkToplevel)
    assert isinstance(df, pd.DataFrame), "count_GLM method did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.data.obs['merging'].unique()), "GLM statistics dataframe did not have the expected length"
    table_launch.destroy()
    window.GLM.configure(variable = ctk.StringVar(value = "ANOVA"))
    window.filename.configure(textvariable = ctk.StringVar(value = "ANOVA_NOVA_table"))
    df, table_launch = window.run_ANOVAs()
    assert isinstance(table_launch, ctk.CTkToplevel)
    assert isinstance(df, pd.DataFrame), "abundance ANOVA method did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.data.obs['merging'].unique()), "abundance ANOVA dataframe did not have the expected length"
    assert isinstance(window, ctk.CTkToplevel)
    table_launch.destroy()
    window.destroy()

def test_run_state_ANOVAs_window():
    window = app.Tabs.py_exploratory.analysiswidg.hypothesis_widget.launch_state_ANOVAs_window()
    window.marker_class.configure(variable = ctk.StringVar(value = "type"))
    df, table_launch = window.run_state_ANOVAs()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(table_launch, ctk.CTkToplevel)
    assert isinstance(df, pd.DataFrame), "state expression statistics did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.data.obs['merging'].unique()) * (my_analysis.data.var['marker_class'] == "type").sum(), "state expression statistics dataframe did not have the expected length"
    table_launch.destroy()
    window.destroy()

def test_plot_state_p_value_heatmap():
    figure =  my_analysis.plot_state_p_value_heatmap(ANOVA_kwargs = {'marker_class':"type"})
    assert isinstance(figure, matplotlib.figure.Figure), "plot_state_p_value_heatmap did not return a matplotlib figure"

def test_state_distribution_window():
    window = app.Tabs.py_exploratory.analysiswidg.hypothesis_widget.launch_state_distribution()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    figure = window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "plot_state_distributions did not return a matplotlib figure"
    window.destroy()

def test_launch_cluster_save_load():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_save_load()
    window.load_type.configure(variable = ctk.StringVar(value = "metaclustering"))
    window.saver_button.invoke()
    window.load_identifier.configure(variable = ctk.StringVar(value = os.listdir(app.Tabs.py_exploratory.analysiswidg.cat_exp.directory + "/clusterings")[0]))
    window.loader_button.invoke()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_data_table_exportation_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_data_table_exportation_window()
    window.subset_command()
    window.grouping_command()
    window.plain_command()
    window.whole_command()
    df = window.export_table()
    assert isinstance(df, pd.DataFrame), "data export did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.data.obs), "data export did not have the same length as the source data!"
    df = window.umap_pca_button.invoke()
    assert isinstance(df, pd.DataFrame), "DR export did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.UMAP_embedding), "DR export did not have the same length as the source embedding!"
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_regionprop():
    window = app.Tabs.py_exploratory.analysiswidg.launch_regionprop()
    #assert isinstance(window, ctk.CTkToplevel)


##>>## GUI Spatial tests
def test_toggle3():
    palmettobug.Analysis_widgets.Spatial_GUI.toggle_TESTING()
    assert (palmettobug.Analysis_widgets.Spatial_GUI._TESTING is True)

def test_plot_cell_maps_window():
    window = app.Tabs.Spatial.widgets.plot_cell_maps_window()
    list_of_file_names = [(i[:i.rfind(".ome.fcs")]) for i in sorted(list(window.master.master_exp.data.obs['file_name'].unique()))]
    window.python_run_cell_maps(multi_or_single = list_of_file_names[0], clustering = 'metaclustering', masks = "masks")
    window.python_run_cell_maps(multi_or_single = list_of_file_names[1], clustering = 'metaclustering', masks = "points")
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_SpaceANOVA():
    window = app.Tabs.Spatial.widgets.widgets.launch()
    window.load_and_run_spatial_analysis(min_radius = 10, 
                                         max_radii = 80, 
                                         step = 5, 
                                         condition_comparison = "All (multicomparison)", 
                                         celltype_key = 'merging', 
                                         permutations = 2, 
                                         seed = 42)
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_SpaceANOVA_stats_and_heatmap():
    window = app.Tabs.Spatial.widgets.widgets.launch_heat_plot()
    window.plot_heatmap("adjusted p values")
    assert isinstance(window, ctk.CTkToplevel) 
    window.destroy()

def test_SpaceANOVA_function_plots():
    window = app.Tabs.Spatial.widgets.widgets.launch_function_plot()
    window.plot_pairwise_comparison(comparison = "Run All", stat = 'g', plot_f_vals = True)
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_do_neighbors():
    app.Tabs.Spatial.widgets.squidpy_spatial.do_neighbors()
    assert True

def test_sq_centrality():
    window = app.Tabs.Spatial.widgets.squidpy_spatial.launch_centrality_window()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_sq_inter_mat():
    window = app.Tabs.Spatial.widgets.squidpy_spatial.launch_interaction_matrix_window()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.facet.configure(variable = ctk.StringVar(value = "condition"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_sq_neigh_enrich():
    window = app.Tabs.Spatial.widgets.squidpy_spatial.launch_neigh_enrich_window()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.facet.configure(variable = ctk.StringVar(value = "condition"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_CN_window():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_CN_window()
    window.celltype.configure(variable = ctk.StringVar(value = "merging"))
    window.run_cellular_neighborhoods()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_CN_save_load():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_save_load()
    window.save()
    saved_clusterings = [i for i in sorted(os.listdir(window.master.master.master_exp.clusterings_dir)) if (i.find("cellular_neighborhood") != -1)]
    window.path.configure(variable = ctk.StringVar(value = saved_clusterings[0]))
    window.reload()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_CN_annot():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_annotation()
    for ii,i in enumerate(window.new.table.widgetframe['1']):
        value = ii % 4   ## generate 4 fake clusters
        i.configure(textvariable = ctk.StringVar(value = f"c{str(value)}"))
    window.annotate(id = 'CN_merge')
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_CN_heatmap():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_heatmap_window()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_CN_abundance():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_abundance_window()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_CN_UMAP_or_MST():
    window = app.Tabs.Spatial.widgets.CN_widgets.clustermap_window()
    #window.plot()
    assert isinstance(window, ctk.CTkToplevel)

def test_launch_edt():
    window = app.Tabs.Spatial.widgets.test_edt.launch_load_window()
    window.pixel_class_entry.configure(textvariable = ctk.StringVar(value = proj_directory + "/Pixel_Classification/lumen_epithelia_laminapropria"))
    window.do_dist_transform()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_edt_reload_window():
    window = app.Tabs.Spatial.widgets.test_edt.launch_reload_window()
    options = [i for i in sorted(os.listdir(window.folder)) if i.lower().find(".csv") != -1]
    window.choice.configure(variable = ctk.StringVar(value = options[0]))
    #window.reload()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_edt_stats_window():
    window = app.Tabs.Spatial.widgets.test_edt.launch_stat_window()
    window.groupby_column.configure(variable = ctk.StringVar(value = "merging"))
    window.do_stats()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_edt_distrib_window():
    window = app.Tabs.Spatial.widgets.test_edt.launch_distrib_window()
    window.var_column.configure(variable = ctk.StringVar(value = "HistoneH3"))
    window.subset_col.configure(variable = ctk.StringVar(value = "merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_edt_heatmap_window():
    window = app.Tabs.Spatial.widgets.test_edt.launch_heatmap_window()
    window.groupby_column.configure(variable = ctk.StringVar(value = "merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_reload():    ### do after spatial, to repserve merging, etc.
    app.Tabs.py_exploratory.analysiswidg.reload_experiment()
    app.Tabs.py_exploratory.analysiswidg.launch_data_table_importation_window(directory = my_analysis.data_table_dir + "/data_table_1.csv")


def test_toggle_in_gui():
    palmettobug.ImageProcessing.ImageAnalysisClass.toggle_in_gui()   ## really here to reset --> not being in the gui after testing the App above

def non_GUI_TableLaunch():
    path_to_df = proj_directory + "/panel.csv"
    panel_df = pd.read_csv(path_to_df)
    t_launch = palmettobug.Utils.sharedClasses.TableLaunch_nonGUI(panel_df, path_to_df, table_type = 'panel')
    assert isinstance(t_launch, ctk.CTkToplevel)
    t_launch.tablewidget.add_row(3)
    t_launch.tablewidget.toggle_delete_column()
    table = t_launch.tablewidget.recover_input()
    assert isinstance(table, pd.DataFrame)

def test_salamification():
    salami = my_analysis.space_analysis.do_salamification()
    figure = my_analysis.space_analysis.plot_salami(condition = "SSA", radii = 25)
    assert isinstance(figure, matplotlib.figure.Figure)