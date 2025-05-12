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
import tempfile as tmp
import matplotlib

from palmettobug import (fetch_IMC_example, 
                        ImageAnalysis,
                        merge_folder,
                        slice_folder,
                        mode_classify_folder,
                        secondary_flowsom,
                        classify_from_secondary_flowsom,
                        extend_masks_folder,
                        plot_classes,
                        WholeClassAnalysis)

from palmettobug.Pixel_Classification.alt_Classifiers import (SupervisedClassifier, UnsupervisedClassifier, segment_class_map_folder, plot_pixel_heatmap)

fetch_dir = homedir + "/px_class_test/"
if not os.path.exists(fetch_dir):
    os.mkdir(fetch_dir)
proj_directory = fetch_dir + "Example_IMC"

np.random.default_rng(42)

def test_fetch_IMC():
    fetch_IMC_example(fetch_dir)

def test_raw_to_img():
    global image_proc
    image_proc = ImageAnalysis(proj_directory, from_mcds = True)
    image_proc.directory_object.makedirs()
    image_proc.raw_to_img(0.85)
    images = [f"{proj_directory}/images/img/{i}" for i in sorted(os.listdir(proj_directory + "/images/img"))]
    assert(len(images) == 10), "Wrong number of images exported to images/img"               ## all the images are transferred
    shutil.rmtree(proj_directory + "/raw") ## don't need raw anymore

def test_load_SupPx():
    global my_classifier_name
    my_classifier_name = "lumen_epithelia_laminapropria"
    global images_dir
    images_dir = proj_directory + "/images/img"
    global pixel_class_object
    classes = ["background", "epithelia", "lamina_propria"] 
    classes_dictionary = {1:"background",2:"epithelia",3:"lamina_propria"} 
    pixel_class_object = SupervisedClassifier(proj_directory, my_classifier_name, classes_dictionary)
    panel = pd.read_csv(f"{proj_directory}/panel.csv")
    panel = panel[panel['keep'] == 1].reset_index()
    channel_dictionary = {}  
    for i,ii in zip(panel.index, panel['name']):
        if (i == 6) or (i == 26):
            channel_dictionary[str(i)] = ['gaussian','hessian','frangi','butterworth']

    sigma_list = [1.0, 5.0, 10.0]  
    
    shutil.rmtree(pixel_class_object.training_folder)
    shutil.copytree(f"{homedir}/tests/training_labels", pixel_class_object.training_folder)
    _ = pixel_class_object.train(image_folder = images_dir, channel_dictionary = channel_dictionary, sigmas = sigma_list)
    assert pixel_class_object.model_info["channels"] == channel_dictionary, "Channel dictionary should remain the same in training"   ## key test is not really the assert, 
                                                                                                                                      ## but the lack of an error while running
                                                                                                                                      ## the training & the ability to predict 
                                                                                                                                      ## afterwards

def test_train_predict_supervised_classifier():
    pixel_class_object.predict(images_dir, output_folder = None, filenames = None)
    prediction_paths = ["".join([pixel_class_object.output_folder,"/",i]) for i in sorted(os.listdir(pixel_class_object.output_folder))]  
    image_paths = ["".join([images_dir, "/", i]) for i in sorted(os.listdir(images_dir))]  
    assert len(prediction_paths) == 10, "There are not 10 px class predictions (one for each image)!"
    assert (tf.imread(prediction_paths[0]).shape == tf.imread(image_paths[0]).shape[1:]), "The X/Y dimensions of the source images and output class maps should be the same!"
    assert (tf.imread(prediction_paths[1]).astype('int') != tf.imread(prediction_paths[1])).sum() == 0, "The pixel class maps shoul be integers!"
    assert tf.imread(prediction_paths[2]).max() <= 3, "There should be no pixels >3 (the number of prediction classes)"

def test_unsupervised_classifier():
    global unsup
    unsup = UnsupervisedClassifier(proj_directory, name = "test_unsup")
    global panel
    panel = pd.read_csv(proj_directory + "/panel.csv")
    panel = panel[panel['keep'] == 1].reset_index().drop('index', axis = 1).reset_index()
    panel.index = panel['name']
    target_channels = ['aSMA', 'Vimentin', 'Pan-Keratin', 'E-cadherin', 'Vitrionectin', 'Collagen-1', 'Beta-Catenin']
    channel_dictionary = {}
    for i in target_channels:
        channel_number = panel.loc[i, 'index']
        features = ['gaussian']
        if i == 'Collagen-1':
            features = features + ['hessian', 'frangi', 'butterworth']
        channel_dictionary[str(channel_number)] = features
    global img_directory
    img_directory = proj_directory + "/images/img"  
    unsup.train(image_folder = img_directory, 
                channel_dictionary = channel_dictionary,
                sigmas = [1.0, 5.0, 10.0], 
                pixel_number = 50000, 
                quantile = 0.999,
                seed = 8675309, 
                metaclusters = 20, 
                training_cycles = 50,
                XYdim = 10, 
                smoothing = 2)
    unsup.predict(image_folder = img_directory)
    assert len(os.listdir(unsup.output_folder)) == 10, "Wrong number of classification maps generated!"

def test_pixel_class_heatmap():
    clustergrid, df = plot_pixel_heatmap(pixel_folder = unsup.output_folder, 
                                          image_folder = img_directory, 
                                          channels = list(panel[panel['keep'] == 1]['name']), 
                                          panel = panel)
    assert isinstance(clustergrid.figure, matplotlib.figure.Figure), "Pixel Heatmap did not return a matplotlib figure"

def test_direct_seg():
    segment_class_map_folder(pixel_classifier_directory = unsup.output_folder, 
                                  output_folder = proj_directory + "/masks/test_seg", 
                                  distance_between_centroids = 15,
                                  threshold = 5, 
                                  to_segment_on = [1,2,3,4,5], 
                                  background = 10)
    assert len(os.listdir(proj_directory + "/masks/test_seg")) == 10, "Wrong number of images in sliced images folder!" 

def test_slice_by_class():
    slice_folder(class_to_keep = 2,
                    class_map_folder = unsup.output_folder, 
                    image_folder = img_directory, 
                    output_folder = proj_directory + "/images/sliced_by_epithelia",
                    padding = 0, zero_out = False) 
    assert len(os.listdir(proj_directory + "/images/sliced_by_epithelia")) == 10, "Wrong number of images in sliced images folder!"

def test_merging_px_classes():
    global merging_table
    merging_table = pd.DataFrame()
    merging_table['class'] = [i for i in range(0,20,1)]
    merging_table['merging'] = [(i % 4) + 1 for i in range(0,20,1)]   ## four fake test classes -- [1,2,3,4]
    merging_table['labels'] = merging_table['merging'].replace({1:"test_1", 2:"test_2", 3:"test_3", 4:"test_4"})
    global merging_dir
    merging_dir = proj_directory + "/Pixel_Classification/test_unsup/merged_classification_maps"
    merge_folder(folder_to_merge = unsup.output_folder, 
                 merging_table = merging_table, 
                 output_folder = merging_dir)
    assert len(os.listdir(merging_dir)) == 10, "Wrong number of merged class maps generated!"

def test_classy_mask_mode():
    name = "test_classy_mode_masks"
    run_folder = proj_directory + f"/classy_masks/{name}"
    global output_folder
    output_folder = run_folder + f"/{name}"   

    if not os.path.exists(run_folder):
        os.mkdir(run_folder)
    mask_classifications = mode_classify_folder(proj_directory + "/masks/example_deepcell_masks", 
                                                merging_dir, 
                                                output_folder, 
                                                merging_table = None) 
    mask_classifications.to_csv(run_folder + f"/{name}.csv", index = False)   
    assert len(os.listdir(output_folder)) == 10, "Wrong number of classy masks exported!"
    assert len(pd.read_csv(run_folder + f"/{name}.csv")) == 36927, 'Wrong number of cells in classy mask .csv!'

def test_classy_mask_flowsom():
    mask_folder = proj_directory + "/masks/example_deepcell_masks"

    name = "Test_2ndary_FlowwSOM"
    run_folder = proj_directory + f"/classy_masks/{name}"
    classy_fs_output_folder = run_folder + f"/{name}"
    if not os.path.exists(run_folder):
        os.mkdir(run_folder) 
    
    fs, _ = secondary_flowsom(mask_folder = proj_directory + "/masks/example_deepcell_masks", 
                               classifier_map_folder = unsup.output_folder, 
                               number_of_classes = 20, 
                               XY_dim = 10, 
                               n_clusters = 15, 
                               seed = 42)

    cell_classifications = classify_from_secondary_flowsom(mask_folder, classy_fs_output_folder, flowsom_data = fs)
    cell_classifications.to_csv(run_folder + f"/{name}_cell_classes.csv", index = False)
    assert len(os.listdir(classy_fs_output_folder)) == 10, "Wrong number of classy masks exported!"
    assert len(pd.read_csv(run_folder + f"/{name}_cell_classes.csv")) == 36927, 'Wrong number of cells in classy mask .csv!'

def test_extend_masks():
    output_directory_folder = proj_directory + "/masks/extended_masks"
    extend_masks_folder(merging_dir, proj_directory + "/masks/example_deepcell_masks", 
                        output_folder, output_directory_folder,
                        merge_list = [1,2], 
                        connectivity = 2)
    assert len(os.listdir(output_directory_folder)) == 10, "Wrong number of extended masks exported!"

def test_maps_to_PNGs():
    output_dir = proj_directory + "/Pixel_Classification/test_unsup/class_maps_to_PNGs"
    plot_classes(class_map_folder = unsup.output_folder, output_folder = output_dir)
    assert len(os.listdir(output_dir)) == 10, "Wrong number of PNGs exported!"

def test_whole_class_analysis_load():
    whole_class_directory = proj_directory + "/Pixel_Classification/test_unsup/whole_class_analysis"
    os.mkdir(whole_class_directory)

    metadata = pd.read_csv(proj_directory +  "/Analyses/metadata.csv")
    panel = pd.read_csv(proj_directory +  "/Analyses/Analysis_panel.csv")

    image_proc.make_segmentation_measurements(proj_directory + "/images/img", 
                                            proj_directory + "/Pixel_Classification/test_unsup/merged_classification_maps", 
                                            output_intensities_folder = whole_class_directory + "/intensities", 
                                            output_regions_folder  = whole_class_directory + "/regionprops", 
                                            statistic = 'mean',
                                            re_do = True)
    global wca
    wca = WholeClassAnalysis(directory = whole_class_directory, classifier_df = merging_table, metadata = metadata, 
                             Analysis_panel = panel)
    fig = wca.plot_percent_areas()
    assert isinstance(fig, matplotlib.figure.Figure), "Whole Class Analysis percent areas did not return a matplotlib figure"

def test_wca_dist():
    facet_grid = wca.plot_distribution_exprs(unique_class = 'test_2', plot_type = 'Violin')
    assert isinstance(facet_grid.figure, matplotlib.figure.Figure), "Whole Class Analysis distribution plot did not return a matplotlib figure"

def test_wca_stat():
    df = wca.whole_marker_exprs_ANOVA(marker_class = 'type', groupby_column = 'class', variable = 'condition', statistic = 'ANOVA', area = True)
    assert isinstance(df, pd.DataFrame), "Whole Class Stats did not return a pandas dataframe!"

def test_wca_heatmap():
    facet_grid = wca.plot_heatmap("p_adj")
    assert isinstance(facet_grid.figure, matplotlib.figure.Figure), "Whole Class Analysis statistics heatmap plot did not return a matplotlib figure"

def test_wca_export():
    df = wca.export_data(filename = None, 
                        subset_columns = None, 
                        subset_types = None, 
                        groupby_columns = None, 
                        statistic= 'mean',
                        include_marker_class_row = False)
    assert isinstance(df, pd.DataFrame), "Whole class export funciton did not return a pandas dataframe!"
                    