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

from palmettobug import SupervisedClassifier, UnsupervisedClassifier, plot_pixel_heatmap, segment_class_map_folder

########### CRITICAL! -- depends on test_img_proc having been run first!
proj_directory = homedir + "/project_folder/Example_IMC"
images_dir = proj_directory + "/images/img"

my_classifier_name = "lumen_epithelia_laminapropria.json"

def test_load_SupPx():
    pixel_class_object = SupervisedClassifier(proj_directory)
    classes = ["background", "epithelia", "lamina_propria"] 
    classes_dictionary = {1:"background",2:"epithelia",3:"lamina_propria"} 
    panel = pd.read_csv(f"{proj_directory}/panel.csv")
    panel = panel[panel['keep'] == 1].reset_index()
    channel_dictionary = {}  
    for i,ii in zip(panel.index, panel['name']):
        if (i == 6) or (i == 26):
            channel_dictionary[ii] = i 

    sigma_list = [1.0, 2.0]  
    possible_features =  ["GAUSSIAN", "LAPLACIAN", "WEIGHTED_STD_DEV", "GRADIENT_MAGNITUDE", "STRUCTURE_TENSOR_EIGENVALUE_MAX", 
                        "STRUCTURE_TENSOR_EIGENVALUE_MIN", "STRUCTURE_TENSOR_COHERENCE", "HESSIAN_DETERMINANT", 
                        "HESSIAN_EIGENVALUE_MAX",  "HESSIAN_EIGENVALUE_MIN"]
    internal_architecture = [256,128] 
    _ = pixel_class_object.setup_classifier(classifier_name = my_classifier_name, number_of_classes = 3, 
                            sigma_list = sigma_list, features_list = possible_features, 
                            channel_dictionary = channel_dictionary, image_directory = images_dir, classes_dictionary = classes_dictionary,  
                            categorical = True, internal_architecture = internal_architecture, epsilon = 0.01, iterations = 1000)
    assert pixel_class_object.details_dict["number_of_input_neurons"] == len(sigma_list) * len(possible_features) * len(channel_dictionary), "Number of input neurons not the expected amount"
    return pixel_class_object

def test_train_predict_supervised_classifier(pixel_class_object):
    shutil.rmtree(pixel_class_object.classifier_training_labels)
    shutil.copytree(f"{homedir}/notebooks/PixelClassifiers/training_labels", pixel_class_object.classifier_training_labels)
    _ = pixel_class_object.train_folder(images_dir)
    pixel_class_object.predict_folder(images_dir)
    prediction_paths = ["".join([pixel_class_object.output_directory,"/",i]) for i in os.listdir(pixel_class_object.output_directory)]  
    image_paths = ["".join([images_dir,"/",i]) for i in os.listdir(images_dir)]  
    assert len(prediction_paths) == 10, "There are not 10 px class predictions (one for each image)!"
    assert (tf.imread(prediction_paths[0]).shape == tf.imread(image_paths[0]).shape[1:]), "The X/Y dimensions of the source images and output class maps should be the same!"
    assert (tf.imread(prediction_paths[1]).astype('int') != tf.imread(prediction_paths[1])).sum() == 0, "The pixel class maps shoul be integers!"
    assert tf.imread(prediction_paths[2]).max() <= 3, "There should be no pixels >3 (the number of prediction classes)"

if __name__ == "__main__":
    try:
        sup_class = test_load_SupPx()
        print(f"Load Supervised Classifier Succeeded")
    except Exception as e:
        print(f"px class load failed: {e}")
    else:
        tests = [test_train_predict_supervised_classifier]

        test_names = ["test_train_predict_supervised_classifier"]

        test_fail = []
        for i,ii in zip(tests, test_names):
            try:
                i(sup_class)
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