import os
import shutil

import numpy as np
import pandas as pd
import tifffile as tf
import anndata
import matplotlib
import customtkinter as ctk

import palmettobug
from palmettobug.Entrypoint.app_and_entry import App

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

### GUI App & entrypoint tests
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
    window.toggle_light_dark()
    window.slider_moved(1.0)
    window = window.change_theme('Sweetkind')
    window = window.change_theme('green') ### reset so local tests change less for git versioning (assets theme file)
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launchExampleDataWindow():     ## now also handles the loading of the example data
    global loader_window
    loader_window = app.entrypoint.launchExampleDataWindow()
    assert isinstance(loader_window, ctk.CTkToplevel)
    loader_window.entry.configure(textvariable = ctk.StringVar(value = fetch_dir))
    loader_window.load_IMC()
    shutil.move(proj_directory + "/panel.csv", fetch_dir + "/panel.csv")   ## test load without panel file
    app.entrypoint.img_entry_func(proj_directory) 
    ## restore example panel & reload
    shutil.move(fetch_dir + "/panel.csv", proj_directory + "/panel.csv")  
    app.entrypoint.img_entry_func(proj_directory, resolutions = [1.0,1.0]) 

### GUI Image Analysis tests
def test_call_raw_to_img_part_1_hpf():
    app.entrypoint.image_proc_widg.buttonframe.activate_region_measure()
    hpf_window = app.entrypoint.image_proc_widg.call_raw_to_img_part_1_hpf()
    hpf_window.read_values()
    images = [f"{proj_directory}/images/img/{i}" for i in sorted(os.listdir(proj_directory + "/images/img"))]
    assert(len(images) == 10), "Wrong number of images exported to images/img" 

def test_call_instanseg_segmentor():
    instanseg_window = app.entrypoint.image_proc_widg.call_instanseg_segmentor()
    instanseg_window.refresh1()
    instanseg_window.refresh2()
    instanseg_window.single_image.configure(variable = ctk.StringVar(value = os.listdir(proj_directory + "/images/img")[0]))
    w_window = instanseg_window.read_values()
    w_window.destroy()
    assert(len(os.listdir(proj_directory + "/masks/instanseg_masks"  )) == 1), "Wrong number of masks exported"
    instanseg_window.destroy()

def test_call_mask_expand():
    expander = app.entrypoint.image_proc_widg.call_mask_expand()
    expander.refresh3()
    expander.image_folder.configure(variable = ctk.StringVar(value = "example_deepcell_masks"))
    expander.output_folder.configure(textvariable = ctk.StringVar(value = "expanded_deepcell_masks"))
    expander.read_values()
    images = os.listdir(proj_directory + "/masks/expanded_deepcell_masks")
    assert(len(images) == 10), "All masks not expanded" 

def test_call_intersection_difference():
    intersect = app.entrypoint.image_proc_widg.call_intersection_difference()
    intersect.refresh1()
    intersect.refresh1()
    intersect.masks_folder1.configure(variable = ctk.StringVar(value = "example_deepcell_masks"))
    intersect.masks_folder2.configure(variable = ctk.StringVar(value = "expanded_deepcell_masks"))
    intersect.kind2.configure(variable = ctk.StringVar(value = "two-way"))
    intersect.read_values()
    assert(len(os.listdir(proj_directory + "/masks/example_deepcell_masks_expanded_deepcell_masks")) == 10), "Mask intersection function failed!"
    intersect.destroy()

def test_call_region_measurement():
    region_meas = app.entrypoint.image_proc_widg.call_region_measurement()
    region_meas.refresh1()
    region_meas.refresh2()
    region_meas.output_folder.configure(textvariable = ctk.StringVar(value = "test_analysis"))
    region_meas.masks_folder.configure(variable = ctk.StringVar(value = "example_deepcell_masks"))
    region_meas.accept_values.invoke()
    ## now without re_do selected
    region_meas = app.entrypoint.image_proc_widg.call_region_measurement()
    region_meas.re_do.deselect()
    region_meas.output_folder.configure(textvariable = ctk.StringVar(value = "test_analysis2"))
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
    #shutil.copyfile(Analysis_panel, proj_directory + "/Analyses/test_analysis/main/Analysis_panel.csv")
    #shutil.copyfile(metadata, proj_directory + "/Analyses/test_analysis/main/metadata.csv")
    analysis_loader = app.entrypoint.image_proc_widg.call_to_Analysis()
    analysis_loader.refresh10()
    analysis_loader.checkbox.select()
    analysis_loader.analysis_choice.configure(variable = ctk.StringVar(value = 'test_analysis'))
    analysis_loader.run()
    app.Tabs.tables.tablewidget.toggle_delete_column("disabled")
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
    window = loader_window.load_CyTOF()
    assert isinstance(window.table_launcher, ctk.CTkToplevel)
    window.table_launcher.destroy()
    loader_window.destroy()

def test_setup_for_FCS():
    palmettobug.setup_for_FCS(fetch_dir + "/Example_CyTOF")
    shutil.move(fetch_dir + "/Example_CyTOF/main/Analysis_panel.csv", fetch_dir + "/Example_CyTOF/Analysis_panel.csv")   ## test load without panel file
    shutil.move(fetch_dir + "/Example_CyTOF/main/metadata.csv", fetch_dir + "/Example_CyTOF/metadata.csv") 
    palmettobug.setup_for_FCS(fetch_dir + "/Example_CyTOF")
    assert True

def test_fake_bead_norm():
    fake_bead_norm_dir = fetch_dir + "/bead_norm_fakery"
    os.mkdir(fake_bead_norm_dir)
    beads_dir = fake_bead_norm_dir + "/beads"
    os.mkdir(beads_dir)
    no_beads_dir = fake_bead_norm_dir + "/no_beads"
    os.mkdir(no_beads_dir)
    real_FCS_files_dir = fetch_dir + "/Example_CyTOF/main/Analysis_fcs"
    real_FCS_files = [i for i in os.listdir(real_FCS_files_dir) if i.lower().find(".fcs") != -1]

    ### will use the example data .fcs files for the bead norm tests (HOWEVER! remember that the example is already normalized / non-bead cells so like many of these
    # tests, this is just confirms that the code can run, not that it produces accurate / useful results)
    for i,ii in enumerate(real_FCS_files):
        if i % 2 == 0:
            shutil.copyfile(f'{real_FCS_files_dir}/{ii}', f'{beads_dir}/{ii}')
        else:
            shutil.copyfile(f'{real_FCS_files_dir}/{ii}', f'{no_beads_dir}/{ii}')
    channel_norm_window = app.entrypoint.normalize_fcs_choice(directory = fake_bead_norm_dir)
    assert isinstance(channel_norm_window, ctk.CTkToplevel)
    for i in channel_norm_window.checkbox_beads_list[:5]:
        i.select()
    channel_norm_window.run_button.invoke()
    
    
### GUI Pixel classification tests (px class creation)
def test_unsupervised():
    loading_window = app.Tabs.px_classification.create.px_widg.launch_loading_window() 
    window = loading_window.unsupervised("unsupervised1", app.Tabs.px_classification.create.px_widg)
    window.refresh7()
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
    # app.Tabs.px_classification.create.px_widg.plot_pixel_heatmap()
    assert len(os.listdir(app.Tabs.px_classification.create.px_widg.unsupervised.output_dir)) == 1, "Wrong number of classification maps generated!"
    
def test_accept_classifier_name():   ## supervised window
    loading_window = app.Tabs.px_classification.create.px_widg.launch_loading_window() 
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
    global pixel_class_object
    pixel_class_object = app.Tabs.px_classification.create.px_widg.PxQuPy_class   
    assert pixel_class_object.details_dict["number_of_input_neurons"] == 1 * (len(window.features_list.checkbox_list) - 7) * 2, "Number of input neurons not the expected amount"


def test_training():
    training_dir = app.Tabs.px_classification.create.px_widg.classifier_dir + "/lumen_epithelia_laminapropria/training_labels"
    shutil.rmtree(training_dir)
    shutil.copytree(f"{homedir}/tests/training_labels", training_dir)
    app.Tabs.px_classification.create.px_widg.Napari_frame.choose_folder.configure(variable = ctk.StringVar(value = 'img'))
    app.Tabs.px_classification.create.px_widg.Napari_frame.training_button.invoke()
    assert True 

def test_events_create_px():   ## do at least after a classifier has been loaded to limit risk of errors
    app.Tabs.px_classification.create.px_widg.start_frame.refresh_exclusive_buttons()
    app.Tabs.px_classification.create.px_widg.start_frame.refresh_exclusive_buttons()
    app.Tabs.px_classification.create.px_widg.Napari_frame.refresh1()
    app.Tabs.px_classification.create.px_widg.Napari_frame.refresh2(image_folder = proj_directory + "images/img")
    app.Tabs.px_classification.create.px_widg.predictions_frame.refresh3()
    app.Tabs.px_classification.create.px_widg.predictions_frame.refresh4(image_folder = proj_directory + "images/img")
    app.Tabs.px_classification.create.px_widg.segment_frame.refresh5()

def test_prediction():
    app.Tabs.px_classification.create.px_widg.predictions_frame.update_one("img")
    app.Tabs.px_classification.create.px_widg.predictions_frame.folder.configure(variable = ctk.StringVar(value = 'img'))
    #app.Tabs.px_classification.create.px_widg.predictions_frame.predict_folder.invoke()
    app.Tabs.px_classification.create.px_widg.predictions_frame.all.select()
    app.Tabs.px_classification.create.px_widg.predictions_frame.predict_folder.invoke()

    images_dir = proj_directory + "/images/img"
    prediction_paths = ["".join([pixel_class_object.output_directory,"/",i]) for i in sorted(os.listdir(pixel_class_object.output_directory))]  
    image_paths = ["".join([images_dir,"/",i]) for i in sorted(os.listdir(images_dir))]  
    assert len(prediction_paths) == 10, "There are not 10 px class predictions (one for each image)!"
    assert (tf.imread(prediction_paths[0]).shape == tf.imread(image_paths[0]).shape[1:]), "The X/Y dimensions of the source images and output class maps should be the same!"
    assert (tf.imread(prediction_paths[1]).astype('int') != tf.imread(prediction_paths[1])).sum() == 0, "The pixel class maps shoul be integers!"
    assert tf.imread(prediction_paths[2]).max() <= 3, "There should be no pixels >3 (the number of prediction classes)"

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
    loading_window = app.Tabs.px_classification.create.px_widg.launch_loading_window()
    app.Tabs.px_classification.create.px_widg.save_classifier()
    loading_window.destroy()
    assert len(os.listdir(palmettobug.Pixel_Classification.Classifiers_GUI.PALMETTO_BUG_assets_classifier_folder)) == 1

def test_load_assets_classifier():
    loading_window = app.Tabs.px_classification.create.px_widg.launch_loading_window()
    loading_window.load_project.refresh6()
    load_from_assets = loading_window.launch_load_window(app.Tabs.px_classification.create.px_widg)
    load_from_assets.refresh8()
    assert isinstance(load_from_assets, ctk.CTkToplevel)
    load_from_assets.choice("lumen_epithelia_laminapropria")
    check_channels_window = load_from_assets.load_classifier(name = "lumen_epithelia_laminapropria2", classifier_load_name = "lumen_epithelia_laminapropria")
    assert isinstance(check_channels_window, ctk.CTkToplevel)
    reference_window = check_channels_window.channel_corrector.launch_reference()
    assert isinstance(reference_window, ctk.CTkToplevel)
    reference_window.destroy()
    check_channels_window.channel_corrector.save_changes()

def test_load_project_classifier():
    loading_window = app.Tabs.px_classification.create.px_widg.launch_loading_window() 
    loading_window.load("Unsupervised_unsupervised1")
    ### additionally check unsupervised details display
    window = app.Tabs.px_classification.create.px_widg.detail_display()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()
    loading_window = app.Tabs.px_classification.create.px_widg.launch_loading_window()
    loading_window.load("lumen_epithelia_laminapropria")
    assert True 

def test_segmentation():
    app.Tabs.px_classification.create.px_widg.segment_frame.input_folder.configure(variable = ctk.StringVar(value = "classification_maps"))
    app.Tabs.px_classification.create.px_widg.segment_frame.run_seg()
    assert len(os.listdir(proj_directory + "/masks/lumen_epithelia_laminapropria_direct_segmentation")) == 10, "Wrong number of images in sliced images folder!" 


### GUI Pixel classification tests (px class use)
def test_load_classifier():
    global px_use_widgets
    px_use_widgets = app.Tabs.px_classification.use_class.px_widg
    px_use_widgets.load_classifier("lumen_epithelia_laminapropria")
    assert True 

def test_events_use_px():   ## do at least after a classifier has been loaded to limit risk of errors
    px_use_widgets.load_and_display.refresh1()
    px_use_widgets.filter.refresh2()
    px_use_widgets.whole_class.refresh_panel_button()
    px_use_widgets.whole_class.refresh_launch_button()
    px_use_widgets.merge_class_masks.refresh3()
    px_use_widgets.merge_class_masks.refresh4()
    px_use_widgets.classify_cells.refresh5()  

def test_launch_classes_as_png():
    window = px_use_widgets.load_and_display.launch_classes_as_png()
    if_pixel_classifier = ["classification_maps", "merged_classification_maps"]
    options = [i for i in if_pixel_classifier if i in os.listdir(window.master.master.active_classifier_dir)]
    window.refresh_option2("pixel classification")
    window.convert_to_png("pixel classification", options[0])
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()
    output_dir = f"{window.master.master.active_classifier_dir}/{options[0]}_PNG_conversion"
    assert len(os.listdir(output_dir)) == 10, "Wrong number of PNGs exported!"

def test_launch_bio_labels():
    window = px_use_widgets.load_and_display.launch_bio_labels()
    window.accept_labels()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_filter():
    px_use_widgets.filter.filter_list.checkbox_list[0].select()
    px_use_widgets.filter.filter_images()
    assert len(os.listdir(proj_directory + "/images/img_filtered_on_")) == 10, "Wrong number of images in sliced images folder!"

def test_classify_masks_on_mode():
    name = "lumen_epithelia_laminapropria_expanded_deepcell_masks"
    run_folder = proj_directory + f"/classy_masks/{name}"
    output_folder = run_folder + f"/primary_masks"  
    px_use_widgets.classify_cells.mask_option_menu.configure(variable = ctk.StringVar(value = "expanded_deepcell_masks"))
    px_use_widgets.classify_cells.do_classy_masks()
    assert len(os.listdir(output_folder)) == 10, "Wrong number of classy masks exported!"
    assert len(pd.read_csv(run_folder + f"/{name}_cell_classes.csv")) == 36927, 'Wrong number of cells in classy mask .csv!'

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
    before_extend  = os.listdir(proj_directory + "/masks")
    px_use_widgets.merge_class_masks.mask_option_menu.configure(variable = ctk.StringVar(value = "expanded_deepcell_masks"))
    options = [i for i in sorted(os.listdir(px_use_widgets.merge_class_masks.master.main_directory + "/classy_masks")) if i.find(".") == -1]  
    px_use_widgets.merge_class_masks.classy_mask_option_menu.configure(variable = ctk.StringVar(value = options[0]))
    px_use_widgets.merge_class_masks.output_name.configure(textvariable = ctk.StringVar(value = "extended_masks"))
    px_use_widgets.merge_class_masks.select_table.checkbox_list[1].select()
    px_use_widgets.merge_class_masks.run_merging()
    after_extend = os.listdir(proj_directory + "/masks")
    output_directory_folder = [i for i in after_extend if i not in before_extend][0]
    assert len(os.listdir(proj_directory + "/masks/" + output_directory_folder)) == 10, "Wrong number of extended masks exported!"

def test_whole_class_analysis_1():
    px_use_widgets.whole_class.classifier_option_menu.configure(variable = ctk.StringVar(value = "classification_maps"))
    region_window = px_use_widgets.whole_class.create()
    app.update()
    region_window.refresh7()
    app.update()
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
    export_window.subset_or_whole = ctk.StringVar(value = "subset")
    export_window.groupby_or_plain = ctk.StringVar(value = "groupby")
    column = wca_window.analysis_exp_whole.data.obs.columns[0]
    value = list(wca_window.analysis_exp_whole.data.obs[column].unique())[0]
    export_window.subset_frame.columns_keep_or_no[0].select()
    export_window.subset_frame.column_values_list[0].insert("0.0", f'{value},')
    export_window.grouping.checkbox_list[2].select()
    export_window.file_name_entry.configure(textvariable = ctk.StringVar(value = "subset_grouped_data_table"))
    df = export_window.export_table()
    assert isinstance(df, pd.DataFrame), "data export did not return a pandas DataFrame"
    export_window.destroy()
    stats_window = wca_window.stats(wca_window)
    assert isinstance(stats_window, ctk.CTkToplevel)
    stats_window.destroy()
    wca_window.destroy()


### GUI Analysis tests
def test_launch_scaling():
    window = app.Tabs.py_exploratory.analysiswidg.launch_scaling()
    window.call_scaling()  
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

def test_launch_combat_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_combat_window()
    window.do_combat()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_scatterplot():
    window = app.Tabs.py_exploratory.analysiswidg.launch_scatterplot()
    window.refresh_scatter_antigen1()
    window.refresh_scatter_antigen2()
    window.refresh_scatter_hue()
    window.antigen1.configure(variable = ctk.StringVar(value = "Pan-Keratin"))
    window.antigen2.configure(variable = ctk.StringVar(value = "HistoneH3"))
    window.hue.configure(variable = ctk.StringVar(value = "None"))
    window.button_plot.invoke()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_Plot_Counts_per_ROI_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_Plot_Counts_per_ROI_window()
    window.refresh5()
    window.refresh6()
    window.pop_up.select()
    figure, display_window = window.plot_Counts_per_ROI()
    assert isinstance(display_window, ctk.CTkToplevel)
    display_window.move_legend_x(1)
    display_window.move_legend_y(1)
    display_window.change_aspect(0.5)
    display_window.change_aspect(0.0)
    display_window.change_aspect(-0.5)
    display_window.resize_widget(7)
    display_window.resize_text(7)
    display_window.destroy()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "Count plot did not return a matplotlib figure"
    window.destroy()

def test_launch_MDS_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_MDS_window()
    window.refresh8()
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
    window.refresh7()
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

def test_do_regions():
    my_analysis.do_regions(region_folder = proj_directory + "/masks/expanded_deepcell_masks")
    assert ('regions' in my_analysis.data.obs.columns), "Do regions did not generate a 'regions' column in obs!"

def test_spatial_leiden():
    my_analysis._do_spatial_leiden()
    assert ('spatial_leiden' in my_analysis.data.obs.columns), "Do spatial_leiden did not generate a 'spatial_leiden' column in obs!"

def test_launch_cluster_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_window()
    global fs
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
    window.refresh2z()
    window.refresh2zz()
    window.refresh3()

    figure = window.plot_UMAP(subsetting_column = 'antigens', color_column = "HistoneH3", filename = 'UMAP_antigens', kind = 'UMAP')
    assert isinstance(figure, matplotlib.figure.Figure), "UMAP facetted by antigen plot did not return a matplotlib figure"

    figure = window.plot_UMAP(subsetting_column = 'condition', color_column = "HistoneH3", filename = 'UMAP_condition', kind = 'UMAP')
    assert isinstance(figure, matplotlib.figure.Figure), "Facetted UMAP plot did not return a matplotlib figure"

    figure = window.plot_UMAP(subsetting_column = 'condition', color_column = "patient_id", filename = 'PCA_facet', kind = 'PCA')
    assert isinstance(figure, matplotlib.figure.Figure), "Facetted PCA plot did not return a matplotlib figure"

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
    window.refresh_cluster_heatmap_k()
    figure = window.plot_cluster_heatmap()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "Cluster medians Heatmap plot did not return a matplotlib figure"
    window.destroy()

def test_launch_distrib_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_distrib_window()
    figure = window.plot_clusterV(clustering_column = 'sample_id', 
                      type_of_graph = 'violin', 
                      type_of_comp = 'group vs. others', 
                      filename = "clusterV_distrib_etc", 
                      marker_class = "type")
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "ROI distributions (violin)plot did not return a matplotlib figure"
    window.destroy()

def test_launch_ClusterVGroup():
    window = app.Tabs.py_exploratory.analysiswidg.launch_ClusterVGroup()
    window.refresh_ClusterVgroup_clusters()
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
    window.refresh_cluster_exp_clusters()
    window.refresh11()
    window.switch_leiden() #switch back and forth from meta --> leiden --> meta 
    window.switch_leiden()
    window.clustering_option.configure(variable = ctk.StringVar(value = "metaclustering"))
    window.antigen.configure(variable = ctk.StringVar(value = "Pan-Keratin"))
    figure = window.run_py_plot_cluster_histograms()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "cluster histograms plot did not return a matplotlib figure"
    window.destroy()
    window = app.Tabs.py_exploratory.analysiswidg.launch_plot_cluster_expression_window()
    window.new.repopulate_table("merging1")
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_abundance_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_abundance_window()
    window.refresh_abund_k()
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
    window.refresh_cluster_stats_clusters()
    window.update_option_menu()
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
    window.new.refreshOption()
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
    window.refresher1()
    data_df = window.classy_mask(clustering = "metaclustering")
    assert isinstance(window, ctk.CTkToplevel)
    #assert len(data_df) == len(my_analysis.back_up_data)
    window.destroy()

def test_launch_abundance_ANOVAs_window():
    app.Tabs.py_exploratory.analysiswidg.hypothesis_widget.filter_N()
    window = app.Tabs.py_exploratory.analysiswidg.hypothesis_widget.launch_abundance_ANOVAs_window()
    window.refresh_abund_ANOVA_cluster()
    window.refresh12()
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
    window.GLM.configure(variable = ctk.StringVar(value = "GLM:Gaussian"))
    window.filename.configure(textvariable = ctk.StringVar(value = "Gaussian_GLM_table"))
    df, table_launch = window.run_ANOVAs()
    assert isinstance(table_launch, ctk.CTkToplevel)
    assert isinstance(df, pd.DataFrame), "count_GLM method (gaussian) did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.data.obs['merging'].unique()), "GLM statistics dataframe (gaussian) did not have the expected length"
    assert isinstance(window, ctk.CTkToplevel)
    table_launch.destroy()
    window.destroy()

def test_run_state_ANOVAs_window():
    window = app.Tabs.py_exploratory.analysiswidg.hypothesis_widget.launch_state_ANOVAs_window()
    window.refresh_state_ANOVA_clusters()
    window.marker_class.configure(variable = ctk.StringVar(value = "type"))
    df, table_launch = window.run_state_ANOVAs()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(table_launch, ctk.CTkToplevel)
    assert isinstance(df, pd.DataFrame), "state expression statistics did not return a pandas DataFrame"
    assert len(df) == (my_analysis.data.var['marker_class'] == "type").sum(), "state expression statistics dataframe did not have the expected length"
    table_launch.accept_and_return(None)
    window.stat.configure(variable = ctk.StringVar(value = "median"))
    window.filename.configure(textvariable = ctk.StringVar(value = 'state_exprs_ANOVA_table2'))
    df, table_launch = window.run_state_ANOVAs()
    assert isinstance(table_launch, ctk.CTkToplevel)
    assert isinstance(df, pd.DataFrame), "state expression statistics (median) did not return a pandas DataFrame"
    table_launch.table_list[0].delete_row(1)
    # table_launch.table_list[0].add_row(4)
    table_launch.destroy()
    window.destroy()

def test_plot_state_p_value_heatmap():
    figure =  my_analysis.plot_state_p_value_heatmap(ANOVA_kwargs = {'marker_class':"type"})
    assert isinstance(figure, matplotlib.figure.Figure), "plot_state_p_value_heatmap did not return a matplotlib figure"

def test_state_distribution_window():
    window = app.Tabs.py_exploratory.analysiswidg.hypothesis_widget.launch_state_distribution()
    window.refresher1()
    window.refresher2()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    figure = window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    assert isinstance(figure, matplotlib.figure.Figure), "plot_state_distributions did not return a matplotlib figure"
    window.destroy()

def test_launch_cluster_save_load():
    window = app.Tabs.py_exploratory.analysiswidg.launch_cluster_save_load()
    window.refresh_load_options()
    window.refresh_button()
    window.refresh1()
    window.refresh2()

    window.load_type.configure(variable = ctk.StringVar(value = "metaclustering"))
    window.saver_button.invoke()
    window.load_identifier.configure(variable = ctk.StringVar(value = os.listdir(app.Tabs.py_exploratory.analysiswidg.cat_exp.directory + "/clusterings")[0]))
    window.loader_button.invoke()
    assert isinstance(window, ctk.CTkToplevel)

    list_of_saved_classifiers = ["".join([window.classy_dir,"/",i,"/",f'{i}_cell_classes.csv']) for i in sorted(os.listdir(window.classy_dir)) if i.find(".") == -1]
    list_of_classifications = [i for i in list_of_saved_classifiers if os.path.exists(i)]
    list_of_classifications = [i[((i[:i.rfind("/")]).rfind("/") + 1):] for i in list_of_classifications] 
    window.load_identifier_from_px.configure(variable = ctk.StringVar(value = list_of_classifications[0]))
    window.load_from_px.invoke()
    assert 'classification' in my_analysis.data.obs.columns
    window.destroy()

def test_launch_drop_restore():           ## filtering
    window = app.Tabs.py_exploratory.analysiswidg.launch_drop_restore()
    window.refresh_list()
    window.switch_column('sample_id')
    window.drop.checkbox_list[0].select()
    window.button1.invoke()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_data_table_exportation_window():
    window = app.Tabs.py_exploratory.analysiswidg.launch_data_table_exportation_window()
    window.subset_frame.refresh_export_column_choice(window.subset_frame.to_list[0])
    window.subset_command()
    window.grouping_command()
    window.plain_command()
    window.whole_command()
    window.export_marker_class.select()
    df = window.export_table()
    window.export_marker_class.deselect()
    assert isinstance(df, pd.DataFrame), "data export did not return a pandas DataFrame"
    assert len(df) == (len(my_analysis.data.obs) + 1), "data export did not have the same length as the source data!"
    window.subset_or_whole = ctk.StringVar(value = "subset")
    window.groupby_or_plain = ctk.StringVar(value = "groupby")
    column = my_analysis.data.obs.columns[0]
    value = list(my_analysis.data.obs[column].unique())[0]
    window.subset_frame.columns_keep_or_no[0].select()
    window.subset_frame.column_values_list[0].insert("0.0", f'{value},')
    window.grouping.checkbox_list[1].select()
    window.grouping.checkbox_list[2].select()
    window.file_name_entry.configure(textvariable = ctk.StringVar(value = "subset_grouped_data_table"))
    df = window.export_table()
    window.grouping.stat_option.configure(variable = ctk.StringVar(value = "count"))
    df = window.export_table()
    window.grouping.stat_option.configure(variable = ctk.StringVar(value = "std"))
    df = window.export_table()
    window.grouping.stat_option.configure(variable = ctk.StringVar(value = "median"))
    df = window.export_table()
    window.grouping.stat_option.configure(variable = ctk.StringVar(value = "sum"))
    df = window.export_table()
    assert isinstance(df, pd.DataFrame), "data export did not return a pandas DataFrame"
    df = window.umap_pca_button.invoke()
    assert isinstance(df, pd.DataFrame), "DR export did not return a pandas DataFrame"
    assert len(df) == len(my_analysis.UMAP_embedding), "DR export did not have the same length as the source embedding!"
    window.umap_pca.configure(variable = ctk.StringVar(value = "pca"))
    window.umap_pca_filename.configure(textvariable = ctk.StringVar(value = "pca_export"))
    df = window.umap_pca_button.invoke()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_facetted_heatmap():
    path_to_svg = my_analysis._plot_facetted_heatmap("facetted_heatmap", "sample_id")
    assert path_to_svg.rfind(".svg") != -1
    assert os.path.exists(path_to_svg)

def test_launch_regionprop():
    window = app.Tabs.py_exploratory.analysiswidg.launch_regionprop()
    assert isinstance(window, ctk.CTkToplevel)
    window.accept_and_return(app.Tabs.py_exploratory.analysiswidg.cat_exp)

def test_directory_display():
    app.Tabs.py_exploratory.analysiswidg.directory_display.switch_deleter()
    app.Tabs.py_exploratory.analysiswidg.directory_display.switch_deleter()
    parent = app.Tabs.py_exploratory.analysiswidg.directory_display
    t_launch = app.Tabs.py_exploratory.analysiswidg.directory_display.button_list[0].file_click(parent, value = "Analysis_panel.csv")
    t_launch.destroy()
    app.Tabs.py_exploratory.analysiswidg.directory_display.button_list[0].invoke()

### GUI Spatial tests
def test_plot_cell_maps_window():
    window = app.Tabs.Spatial.widgets.plot_cell_maps_window()
    window.refresh_cell_maps_clustering()
    list_of_file_names = [(i[:i.rfind(".ome.fcs")]) for i in sorted(list(window.master.master_exp.data.obs['file_name'].unique()))]
    window.python_run_cell_maps(multi_or_single = list_of_file_names[0], clustering = 'metaclustering', masks = "masks")
    window.python_run_cell_maps(multi_or_single = list_of_file_names[1], clustering = 'metaclustering', masks = "points")
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_SpaceANOVA():
    window = app.Tabs.Spatial.widgets.widgets.launch()
    window.refresh_SpaceANOVA_clusters()
    window.refresh_comparisons()
    window.filter_N()
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
    t_launch = window.export_table(window.table_selection.get())
    assert isinstance(t_launch, ctk.CTkToplevel) 
    t_launch.destroy()
    assert isinstance(window, ctk.CTkToplevel) 
    window.destroy()

def test_SpaceANOVA_function_plots():
    window = app.Tabs.Spatial.widgets.widgets.launch_function_plot()
    window.refresh_fxn_plot_comparisons()
    window.plot_pairwise_comparison(comparison = "Run All", stat = 'g', plot_f_vals = True)
    #window.plot_pairwise_comparison(comparison = "Run All", stat = 'g', plot_f_vals = False)  ## set to only run 1 image each, instead of run all to check both + / - f_vals
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_do_neighbors():
    app.Tabs.Spatial.widgets.load_spatial()
    assert True

def test_sq_centrality():
    window = app.Tabs.Spatial.widgets.squidpy_spatial.launch_centrality_window()
    window.refresh_centrality_cluster()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_sq_inter_mat():
    window = app.Tabs.Spatial.widgets.squidpy_spatial.launch_interaction_matrix_window()
    window.refresh_interaction_mat_cluster()
    window.refresh_facet_options()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.facet.configure(variable = ctk.StringVar(value = "condition"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_sq_neigh_enrich():
    window = app.Tabs.Spatial.widgets.squidpy_spatial.launch_neigh_enrich_window()
    window.refresh_neighbor_clustering()
    window.refresh_facet_options()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.facet.configure(variable = ctk.StringVar(value = "condition"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_CN_window():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_CN_window()
    window.refresh_CN_cluster()
    window.celltype.configure(variable = ctk.StringVar(value = "merging"))
    window.run_cellular_neighborhoods()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_CN_UMAP_or_MST():
    window = app.Tabs.Spatial.widgets.CN_widgets.clustermap_window()
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)

def test_CN_save_load():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_save_load()
    window.refresh()
    window.save()
    saved_clusterings = [i for i in sorted(os.listdir(window.master.master.master_exp.clusterings_dir)) if (i.find("cellular_neighborhood") != -1)]
    window.path.configure(variable = ctk.StringVar(value = saved_clusterings[0]))
    window.reload()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_CN_annot():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_annotation()
    window.new.refreshOption()
    for ii,i in enumerate(window.new.table.widgetframe['1']):
        value = ii % 4   ## generate 4 fake clusters
        i.configure(textvariable = ctk.StringVar(value = f"c{str(value)}"))
    window.annotate(id = 'CN_merge')
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_annotation()
    window.new.repopulate_table()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_CN_heatmap():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_heatmap_window()
    window.refresh_CN_heatmap_cluster()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_CN_abundance():
    window = app.Tabs.Spatial.widgets.CN_widgets.launch_abundance_window()
    window.refresh_CN_abund_cluster()
    window.clustering.configure(variable = ctk.StringVar(value = "merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_launch_edt():
    window = app.Tabs.Spatial.widgets.test_edt.launch_load_window()
    window.pixel_class_entry.configure(textvariable = ctk.StringVar(value = proj_directory + "/Pixel_Classification/lumen_epithelia_laminapropria"))
    window.do_dist_transform()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_edt_reload_window():
    window = app.Tabs.Spatial.widgets.test_edt.launch_reload_window()
    window.refresh_edt_reload()
    options = [i for i in sorted(os.listdir(window.folder)) if i.lower().find(".csv") != -1]
    window.choice.configure(variable = ctk.StringVar(value = "lumen_epithelia_laminapropria.csv"))
    window.reload()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_edt_stats_window():
    window = app.Tabs.Spatial.widgets.test_edt.launch_stat_window()
    window.refresh_edt_options()
    window.groupby_column.configure(variable = ctk.StringVar(value = "merging"))
    window.do_stats()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_edt_distrib_window():
    window = app.Tabs.Spatial.widgets.test_edt.launch_distrib_window()
    window.refresh_edt_dist_cluster()
    window.refresh_edt_dist_var()
    window.var_column.configure(variable = ctk.StringVar(value = "HistoneH3"))
    window.subset_col.configure(variable = ctk.StringVar(value = "merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_edt_heatmap_window():
    window = app.Tabs.Spatial.widgets.test_edt.launch_heatmap_window()
    window.refresh_edt_heatmap_cluster()
    window.groupby_column.configure(variable = ctk.StringVar(value = "merging"))
    window.plot()
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_reload():    ### do after spatial, to repserve merging, etc.
    app.Tabs.py_exploratory.analysiswidg.reload_experiment()
    app.Tabs.py_exploratory.analysiswidg.launch_data_table_importation_window(directory = my_analysis.data_table_dir + "/data_table_1.csv")

def test_toggle_in_gui():
    palmettobug.ImageProcessing.ImageAnalysisClass.toggle_in_gui()   ## really here to reset --> not being in the gui after testing the App above
    assert not palmettobug.ImageProcessing.ImageAnalysisClass._in_gui 

def test_load_from_TIFFs():     ## now also handles the loading of the example data
    tiff_proj_dir = fetch_dir + "/tiff"
    os.mkdir(tiff_proj_dir)
    shutil.copytree(proj_directory + "/images/img", tiff_proj_dir + "/raw")
    image_proc = app.entrypoint.img_entry_func(tiff_proj_dir) 
    image_proc.raw_to_img(0.85)
    assert len(os.listdir(tiff_proj_dir + "/images/img")) == 10
    image_proc.directory_object.make_analysis_dirs("test_panel_and_meta_gen")
    image_proc.to_analysis(gui_switch = False)

def test_non_GUI_TableLaunch():
    path_to_df = proj_directory + "/panel.csv"
    panel_df = pd.read_csv(path_to_df)
    t_launch = palmettobug.Utils.sharedClasses.TableLaunch_nonGUI(panel_df, path_to_df, table_type = 'panel', labels_editable = False)
    assert isinstance(t_launch, ctk.CTk)
    t_launch.tablewidget.add_row(3)
    t_launch.tablewidget.toggle_delete_column("disabled")
    t_launch.tablewidget.toggle_delete_column("normal")
    t_launch.tablewidget._delete_row(1)
    table = t_launch.accept_and_return()
    assert isinstance(table, pd.DataFrame)

def test_text_window():
    window = palmettobug.sharedClasses.text_window(app, homedir + "/Assets/theme.txt")
    assert isinstance(window, ctk.CTkToplevel)
    window.destroy()

def test_salamification():
    salami = my_analysis.space_analysis.do_salamification()
    figure = my_analysis.space_analysis.plot_salami(condition = "SSA", radii = 25)
    assert isinstance(figure, matplotlib.figure.Figure)

def test_Spatial_Analysis():
    global spatial_analysis
    spatial_analysis = palmettobug.SpatialAnalysis()
    spatial_analysis.add_Analysis(my_analysis)
    spatial_analysis.add_Analysis(my_analysis)
    integer = spatial_analysis.estimate_SpaceANOVA_min_radii()
    assert isinstance(integer, int)

def test_smooth_folder():
    output_dir = proj_directory + "/Pixel_Classification/lumen_epithelia_laminapropria/smoothed_classification_maps"
    os.mkdir(output_dir)
    palmettobug.Pixel_Classification.Classifiers.smooth_folder(input_folder = proj_directory + "/Pixel_Classification/lumen_epithelia_laminapropria/classification_maps", 
                  output_folder = output_dir, 
                  class_num = 3, 
                  threshold = 3, 
                  search_radius = 1,
                  )
    assert len(os.listdir(output_dir)) == 10

def test_plot_class_centers():
    figure, df = palmettobug.plot_class_centers(fs)
    assert isinstance(df, pd.DataFrame)

def test_app_destroy():
    app.destroy()

