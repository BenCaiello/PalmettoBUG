'''
This module handles the back-end for pixel classifier creation, training, and prediction (as well as segmentation from a pixel classifier)

This also means that the functions/classes here are part of the public (non-GUI) API of PalmettoBUG.
Predominantly the SupervisedClassifier and the UnsupervisedClassifier classes handle the creation, etc. of pixel classifiers.

    >> SupervisedClassifier is a QuPath ANN_MLP pixel classifier mimic, & requires training from user-generating labels in Napari

    >> UnsupervisedClassifier is for an ark-analysis/Pixie-like unsupervised classifier based on FlowSOM clustering.


This code is inspired by, and some areas directly translated from, QuPath. 

Some of the functions of this file (marked with a triple asterisk::

     # ***QuPath translation [partial/complete]
    
used code translated from java --> python, from QuPath. QuPath is similarly licensed under GPL3.0

QuPath is copyright Copyright (C) 2018 - 2020 QuPath developers, The University of Edinburgh 

(some files in QuPath are Copyright (C) 2014 - 2016 The Queen's University of Belfast, Northern Ireland -- but these appear not to be the files partially translated here)

Source file from QuPath is mainly: qupath-core-processing/src/main/java/qupath/opencv/tools/MultiscaleFeatures.java. 
Additionally structure of the OpenCV classifier JSON was obtained by examining the exported json classifiers exported by QuPath. 

        > The structure of these JSONs, however, must be derived from the opencv formatting, which is what performs the ingestion / export of
        the json file.

        > This also means a level of compatibility between classifiers exported from QuPath and the classfiers used by PalmettoBUG 
        (and any project using ANN_MLP from opencv).

The directly translated functions identified are the functions that derive new features (Laplacian, hessians, gradient max, etc., etc.) from an image.

Other functions (such as train / predict functions) may have been helped by looking at QuPath code, but the key points that might be 
considered "translation" are either necessitated by the OpenCV API or diverge in terms of implementation / were implemented by my own 
code structure and not directly translated.
 
The final segmentation function wsa also heavily based on some of the documentation of scikit-image, enough that I list it in the
licenses_of_packages_derived_from.txt file in PalmettoBUG assets::

    Scikit-image: https://github.com/scikit-image/scikit-image, license: BSD-3
'''

import os
from typing import Union
from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd
import tifffile as tf
import cv2 as cv
import matplotlib.pyplot as plt
import napari
import anndata   
import scipy
import skimage
import seaborn as sns 

from flowsom import FlowSOM

pd.set_option('future.no_silent_downcasting', True)

__all__ = ["SupervisedClassifier", 
           "UnsupervisedClassifier", 
           "plot_pixel_heatmap", 
           "plot_class_centers", 
           "segment_class_map_folder"]

def _py_mean_quantile_norm(pd_groupby) -> np.ndarray[float]:    ##  median shouldn't be used used because the median often can be 0 for mass cytometry data (not a problem in 
                                                                    ## single-cell data because the mean intensity is taken of every cell first)
    ''' 
    This is a helper function for the mean / heatmap plotting function immediately below 
    '''
    pd_groupby = pd_groupby.copy()
    np_groupby = np.array(pd_groupby)
    np_groupby = np.mean(np_groupby, axis = 0)
    np_groupby = _quant(np_groupby)
    return np_groupby

def _quant(array: np.ndarray[float], 
          lower: float = 0.01, 
          upper:float = 0.99, 
          axis: int = None,
          ) -> np.ndarray[float]:
    '''
    This is a helper function for _py_mean_quantile_norm
    '''
    quantiles = np.quantile(array, (lower, upper), axis = axis) 
    array = (array - quantiles[0])  / (quantiles[1] - quantiles[0])
    array = np.nan_to_num(array)
    array[array > 1] = 1
    array[array < 0] = 0
    return array

class SupervisedClassifier:
    '''
    This class handles the supervised pixel classifier creation, training, and prediction.

    Key Attributes:
        classifier_path (str): 
            the full file path to the .json file containing the training opencv ANN_MLP classifier

        classifier_dir (str): 
            the path to the folder where the classifier will be setup (== {self._homedir}/Pixel_Classification/{self.classifier_name}/ )

        classifier_training_labels (str): 
            The path to the folder where the classifier training labels are (by default) expected to be written to / read from

        output_directory (str): 
            the path to the folder where the classifier predictions will be exported by default.

        classifier_name (str): 
            The name of the classifier, used for the folder name where the classifier is set up, and to help name the .json files containing
            the trained classifier & its details. Derived from the main, opencv2 .json file name & includes its .json file extension. 

        algorithm (cv2.ml.ANN_MLP): 
            the opencv2 ANN_MLP classifier instance

        details_dict (dictionary): 
            the dictionary containing details of the classifier not available inside the opencv2 .json file 
            This dictionary is saved to a .json file parallel to the opencv2 formatted .json, with "_details" appended to its filename
            Information in the this dictionary are things like the channels, sigmas, & features selected. 

    Formerly PxQuPy (Pixel QuPath Python) -- may likely will remain residuals of that naming in class-internal / GUI-internal namespace
    '''
    def __init__(self, homedir: Union[Path, str]):
        '''
        homedir (str) -- the path to the directory where the Pixel Classification folder and subfolder will be placed 
        (this is the main directory for PalmettoBUG)
        '''
        self._homedir = str(homedir)
        self._setup_directory()
        self.classifier_path = None
        self.algorithm = None
        self.details_dict  = {}
        self._image_name = ""
        
    def _setup_directory(self) -> None:
        '''
        helper for __init__, checks and sets up pixel classification folder that contains individual classifier subfolders
        '''
        if not os.path.exists(self._homedir):
            print("Error! Home Directory does not exist!")
            return
            
        self._px_dir = self._homedir + "/Pixel_Classification"
        if not os.path.exists(self._px_dir):
            os.mkdir(self._px_dir)

    def _setup_classifier_directory(self, 
                                    classifier_name: Union[str, None] = None, 
                                    classifier_path: Union[str, None] = None,
                                    ) -> None:       
        ''' 
        Sets up the classifier folder (subfolder of /Pixel_Classification) for an individual supervised classifier.

        If classifier_path is provided, then attempts to load the .josn at the provided classifier_path and derives the classifier name 
        from the path. When providing classifier_path, the loaded classifier can then be used (or this should be the case) immediately to
        predict. THIS TAKES PRECEDENCE over classifier_name.

        Alternatively, the classifier_name is provided and classifier_path is None --> This creates a new, empty classifier folder.

        In practice, may be more a helper method for the setup_classifier method
        '''
        if (classifier_path is None) and (classifier_name is None):
            print('please provide either classifier_path or classifier_name!')
            return
        if classifier_path is not None:
            self.classifier_path = str(classifier_path)
            classifier_name = self.classifier_path[:self.classifier_path.rfind(".json")]
            end = self.classifier_path.rfind("/")
            classifier_name = classifier_name[end:]
        self.classifier_name = classifier_name
        
        self.classifier_dir = self._px_dir + classifier_name
        self.output_directory = self.classifier_dir + "/classification_maps"
        if not os.path.exists(self.classifier_dir):
            os.mkdir(self.classifier_dir)
        if not os.path.exists(self.output_directory):
            os.mkdir(self.output_directory)

        self.classifier_training_labels = self._px_dir + classifier_name + "/training_labels"   
        if not os.path.exists(self.classifier_training_labels):
            os.mkdir(self.classifier_training_labels)

    def setup_classifier(self, 
                         classifier_name: str, 
                         number_of_classes: int, 
                         sigma_list: list[float], 
                         features_list: list[str], 
                         channel_dictionary: dict[str:int], 
                         classes_dictionary: dict[int:str] = {},
                         image_directory: str = "", 
                         categorical: bool = True, 
                         internal_architecture: list[int] = [], 
                         epsilon: float = 0.01, 
                         iterations: int = 1000,
                         ) -> tuple[cv.ml.ANN_MLP, dict]:
        '''
        This method takes in a variety of user inputs, and creates the initial pixel classifier directory and .json files, ready for training.

        Args:
            classifier_name (str):  
                the name of the classifier

            number_of_classes (int): 
                the number of classes being predicted by the classifier 

            sigma_list (list of numeric): 
                list of the numeric values of the sigmas to be used in the creation of features for the classifier. 
                    
                Example: [1.0, 2.0, 4.0]

            features_list (list of strings): 
                list of the features to be generated from the image and to be fed into the classifier. 
                Possible features = ["GAUSSIAN", "LAPLACIAN", "WEIGHTED_STD_DEV", "GRADIENT_MAGNITUDE", 
                "STRUCTURE_TENSOR_EIGENVALUE_MAX", "STRUCTURE_TENSOR_EIGENVALUE_MIN", "STRUCTURE_TENSOR_COHERENCE", 
                "HESSIAN_DETERMINANT", "HESSIAN_EIGENVALUE_MAX",  "HESSIAN_EIGENVALUE_MIN"]

            channel_dictionary (dict): 
                a dictionary with keys of the channels' common names (str) and values of the channels' location in the image (int). 

                    Example: {'channel_1_name':1, 'channel_10_name':10, 'channel_3_name':3, ...}

                Use this to specify the channels you want used, and to record in the classifier's .json file what antigen each 
                channel represents
            
            classes_dictionary (dict): 
                a dictionary with keys (int) that correspond to the integer labels in the label / prediction files. 
                As in, these are the label numbers used in napari for a given class. The dictionary values (str) correspond to the 
                description the user want for each class. 

                        Example == {1:"Astrocyte",2:"Neuron",3:"Background", ...}

                These are used to retrieve the biologically important information after the classification is complete. 
                It is not needed for the classification steps themselves. Currently has a default value of {}, but that may change 
                in the future to enforce a choice of labels on the part of the user.

            image_directory (str, optional): 
                The path to the folder containing the images you plan to train / predict pixel classes with.

                NOTE: this is optional / for the user's benefit & for reproducibility, as it is saved in the .json file for 
                retrieval of what images were used, but it is NOT ENFORCED. 
                As in, you can train / predict on totally different images (although that is likely a bad idea unless you are keeping thorough records!)

            categorical (bool): 
                if True, then the classifier is set to return only the category output. If False, then it will 
                return probabilities for each category instead of the final decision

            internal_architecture (list of integers or list[None]): 
                the sizes of any internal neuron layers you wish to add to the ANN_MLP.

            epsilon (float): 
                a learning rate parameter of the ANN_MLP training

            iterations (integer): 
                the number of iterations during ANN_MLP training. 
    
        Returns:
            cv.ml.ANN_MLP object: 
                an opencv ANN_MLP instance that is ready to train on data in the shape described by sigma/features/channels/classes information

            dictionary: 
                the information that is saved in classifier_X_details.json, holding the key details for properly deriving the image fetaures, etc. for training and prediction

        Inputs / Outputs: 
            Outputs: 
                saves the classifier as classifier_X.json that can be easily imported by an opencv ANN_MLP object
                (this save is done within the _initialize_classifier_dict_and_ANN_MLP() function)

                saves classifier_X_details.json with the following information: channel_dictionary, sigma list, features list.
                These details are saved separately, as they can mess with the simple import of the classifier into the opencv ANN_MLP
        '''
        ## Make algorithm and save classifier.json
        num_sigmas = len(sigma_list)
        num_features = len(features_list)
        num_channels = len(channel_dictionary)
        number_of_input_neurons = (num_sigmas*num_features*num_channels)
        algorithm1 = self._initialize_classifier_dict_and_ANN_MLP(number_of_input_neurons, 
                                                                 classifier_name = classifier_name, 
                                                                 number_of_classes = number_of_classes, 
                                                                 internal_architecture = internal_architecture,
                                                                 epsilon = epsilon, 
                                                                 iterations = iterations) 
        ## Now make the dictionary / .json containing the critical details of the classifier
        details_dict = {}
        details_dict['sigma_list'] = sigma_list
        details_dict['features_list'] = features_list
        details_dict['channel_dictionary'] = channel_dictionary
        details_dict['number_of_classes'] = number_of_classes
        details_dict['number_of_input_neurons'] = number_of_input_neurons
        details_dict['categorical'] = categorical
        details_dict["classes_dict"] = classes_dictionary
        details_dict["img_directory"] = image_directory
        with open(self._px_dir + "/" + classifier_name.replace(".json","") + "/" + classifier_name.replace(".json","_details.json"), 
                                'w', 
                                encoding="utf-8") as write_json:
            json.dump(details_dict, write_json, indent = 4)

        self.algorithm = algorithm1
        self.details_dict = details_dict
        self._write_biolables_csv()
        self.classifier_name = classifier_name
        return algorithm1, details_dict
    
    def _write_biolables_csv(self) -> None:
        '''
        This helper method writes the biolabel.csv file using the details dictionary.
        '''
        class_dict = self.details_dict["classes_dict"]
        seed_df = pd.DataFrame()
        seed_df['class'] = [i for i in class_dict]
        seed_df['labels'] = [class_dict[i] for i in class_dict]
        zip_dict = {}
        unique_names = list(seed_df['labels'].unique())
        if 'background' not in unique_names:
            unique_names = ['background'] + unique_names
        for i,ii in enumerate(unique_names):
            zip_dict[ii] = i + 1
        zip_dict['background'] = 0
        seed_df['merging'] = seed_df['labels'].replace(zip_dict)
        seed_df.to_csv(self._px_dir + "/" + self.classifier_name.replace(".json","") + "/biological_labels.csv")
        
    def _initialize_classifier_dict_and_ANN_MLP(self, 
                                                number_of_channels: int, 
                                                classifier_name: str = "classifier_test.json", 
                                                number_of_classes: int = 2, 
                                                internal_architecture: list[int] = [], 
                                                iterations: int = 1000, 
                                                epsilon: float = 0.01,
                                                ) -> cv.ml.ANN_MLP:
        ## Because of the need for different numbers of channels, this will need to be run at the start of every classification
        ## Will have to decide how to handle saving the classifier.json --> have an assets folder empty classifier until training, or 
        # initialize inside project every time (probaly the second)
        '''
        This helper method write the dictionary of the main .json file containing information like the classifier neuron weights. 
        See self.setup_classifier method for more details on arguments
        '''
        self.classifier_path = self._px_dir + "/" + classifier_name.replace(".json","") + "/" + classifier_name
        self.classifier_name = classifier_name
        
        ### I create an empty classifier dictionary assuming no intenral architecture -- that can be added after the fact
        training_dictionary = {}
        training_dictionary['train_method'] = 'RPROP'
        training_dictionary['dw0'] = 0.1
        training_dictionary['dw_plus'] = 1.2
        training_dictionary['dw_minus'] = 0.5
        training_dictionary['dw_min'] = 1.1920928955078125e-7
        training_dictionary['dw_max'] = 50.0
        training_dictionary['term_criteria'] = {'epsilon':epsilon, 'iterations':iterations}

        main_dictionary = {}
        main_dictionary['format'] = 3
        main_dictionary['layer_sizes'] = [number_of_channels, number_of_classes]   
        main_dictionary['activation_function'] = 'SIGMOID_SYM'
        main_dictionary['f_param1'] = 1.0
        main_dictionary['f_param2'] = 1.0
        main_dictionary['min_val'] = -0.95
        main_dictionary['max_val'] = 0.95
        main_dictionary['min_val1'] = - 0.98
        main_dictionary['max_val1'] = 0.98
        main_dictionary['training_params'] = training_dictionary
        output_scale_unit = [1.0,0.0]
        output_scale = []
        for i in range(0, number_of_classes):
            output_scale = output_scale  + output_scale_unit
        main_dictionary['input_scale'] = list(np.zeros(number_of_channels*2))
        main_dictionary['output_scale'] = output_scale
        main_dictionary['inv_output_scale'] = output_scale  ## keep an eye on the output scales with different numbers of classes
        main_dictionary['weights'] = [list(np.zeros((number_of_channels*number_of_classes) + number_of_classes))]  

        final_dictionary = {"opencv_ml_ann_mlp":main_dictionary}
        self._setup_classifier_directory(classifier_path = self.classifier_path)
        with open(self.classifier_path, 'w' , encoding="utf-8") as write_json:
            json.dump(final_dictionary, write_json, indent = 4)
        algorithm1 = cv.ml.ANN_MLP.create()
        algorithm1 = algorithm1.load(self.classifier_path)

        ### add hidden layers, if applicable
        if len(internal_architecture) > 0:
            layer_sizes = algorithm1.getLayerSizes()
            layer_in = list(layer_sizes[0])
            layer_out = list(layer_sizes[-1])
            new_layers  = np.array(layer_in + internal_architecture + layer_out)
            algorithm1.setLayerSizes(new_layers)
            algorithm1.save(self.classifier_path)   ## save and reload   (reloading is probably unnecessary)        
        return algorithm1

    def load_saved_classifier(self, classifier_json_path: Union[Path, str]) -> None:
        '''
        This is an alternate way to use this class -- instead creating a new classifier, load an old one.

        It loads a saved pixel classifier using its main classifier.json and classifier_details.json files 
        The classifier_json_path is the full path, including filename + file extension, to the classifier.json file. 
        The classifier_details.json is expected to be found in the SAME FOLDER with it. 
        '''
        classifier_json_path = str(classifier_json_path)
        self.classifier_path = classifier_json_path
        self.algorithm = cv.ml.ANN_MLP.create().load(self.classifier_path)
        open_json = open(classifier_json_path.replace(".json","_details.json"), 'r' , encoding="utf-8")
        loaded_json = open_json.read()
        loaded_json = json.loads(loaded_json)
        self.details_dict = loaded_json
        self.classifier_name = classifier_json_path[classifier_json_path.rfind("/")+1:]

    def launch_Napari_px(self, 
                         image_path: Union[Path, str], 
                         display_all_channels: bool = True,
                         ) -> None:
        '''
        This launches napari for generating training labels, receving a path (image_path) to the image file you want to make labels for
        '''
        image_path = str(image_path)
        image = tf.imread(image_path)
        self._image_name = image_path[image_path.rfind("/"):]
        if image.shape[0] > image.shape[2]:    ## the channel dimensions should be the first
            image = image.T

        if display_all_channels is True:
            viewer = napari.view_image(image, name = self._image_name, channel_axis = 0) 
        else:
            viewer = napari.view_image(image, name = self._image_name)     ### , channel_axis = 0   
                                                                          ## adding this argument this would cause Napari to display 
                                                                          # all channels at once

        labels_path = self.classifier_training_labels + "/" + self._image_name   
            ### check to see if the user has already made a labels layer for this images --> always reload an existing layer, if available
        if os.path.exists(labels_path):
            self._user_labels = viewer.add_labels(tf.imread(labels_path).astype('int'), name = "layer")
        else:
            self._user_labels = viewer.add_labels(np.zeros(list([image.shape[1], image.shape[2]])).astype('int'), name = "layer")
        napari.run()
         
    def write_from_Napari(self, output_folder: Union[str, None] = None) -> None:   
        ''' 
        This saves the training labels to the training labels folder. Will only run if labels have previously been made 
        & this method has not been run already (as this method clears the labels after saving them to the disk)
        '''
        if self._image_name is None:
            print('No training labels available to save!')
            return
        if output_folder is None:
            output_folder = self.classifier_training_labels
        new_labels = self._user_labels.data
        tf.imwrite(output_folder + "/" + self._image_name, new_labels.astype('int32'))  
                    ## labels have the same name as the original image
        print('Training labels written!')
        self._image_name = None

    def train_folder(self, image_folder: Union[Path, str], labels_dir: Union[str, Path, None] = None) -> cv.ml.ANN_MLP:
        '''
        This function trains the ANN_MLP classifier using the training labels in the classifier's directory & the corresponding images 
        in the provided image_folder.

        Note: the images in image_folder must have matching names with the training label files. It is fine if training labels does not 
        have every image in image_folder but it is not acceptable vice versa (training labels without a corresponding image in image_folder).

        Training parameters are previously determined when the classifier was set up with self.setup_classifier.

        Features are generated for each image one-by-one, and their pixels inside label layers are collected -- Then the training is performed 
        on those collected pixels together. 

        NOTE: If run on an already-trained classifier, then it is training with initial weights == the weights from the prior training (but 
        that probably does not make much of a difference)

        Args:
            image_folder (str / Pathlike): 
                The path to the folder where the .tiff files to predict pixel classes for reside. 

            labels_dir (str / Pathlike, None): 
                The path to the folder where the .tiff files containing the training label information reside. If None (default) will use self.classifier_training_labels. 
                There must be ONLY .tiff files in this folder & then names of the files in this folder MUST match with names of .tiff files in the image_folder. 

        Inputs / Outputs:
            Inputs: 
                reads .tiff files from image_folder / labels_dir (self.classifier_training_labels if labels_dir is None)

            Outputs: 
                writes self.details_dict to the {name}_details.json file
        '''
        image_folder = str(image_folder)
         ## initialize algorithm and retrieve details of classifier:
        classifier_details = self.details_dict
        if labels_dir is None:
            training_label_directory = self.classifier_training_labels
        else:
            training_label_directory = str(labels_dir)

        self.details_dict['img_directory'] = image_folder
        with open(self._px_dir + "/" + self.classifier_name.replace(".json","") + "/" + self.classifier_name.replace(".json","_details.json"), 
                                    'w', 
                                    encoding="utf-8") as write_json:
            json.dump(self.details_dict, write_json, indent = 4)

        algorithm1 = self.algorithm
        number_of_classes = [i for i in range(1,classifier_details['number_of_classes'] + 1,1)]

        counter = 0
        for i in sorted(os.listdir(training_label_directory)):
            label_layer = tf.imread(training_label_directory + "/" + i)
            if len(label_layer.shape) > 2:     ## this handles cases where a napari layer was generated with >1 dimension
                label_layer = np.apply_along_axis(np.sum, axis = 0, arr = label_layer) 
            image = tf.imread(image_folder + "/" + i).T
    
            ## generate input training data set:
            all_together = all_channels_features_together(image, classifier_details)
            training_data = all_together.reshape([(all_together.shape[0]*all_together.shape[1]),
                                                  all_together.shape[2]])    ## this assumes X/Y dimensions are the first two layers
    
            if label_layer.min() < 0:
                print("Should not have negative numbers in the pixel classifier training labels!")
                return
            
            output_training_data = np.zeros([label_layer.shape[0], label_layer.shape[1],len(number_of_classes)])
            non_zero_layer = label_layer != 0
            for ii,i in enumerate(number_of_classes):
                next_layer = (non_zero_layer).astype('int') * (-1)  ## all pixels with a class beside the class in question should = -1,  
                                                                    # while the class in question should have pixels = 1
                next_layer[(label_layer == i)] = 1
                output_training_data[:,:,ii] = next_layer
            output_training_data = output_training_data.reshape([(all_together.shape[0]*all_together.shape[1]), len(number_of_classes)])
        
            ## subset to only pixels that have a class:
            non_zeroes = (output_training_data != 0)
            output_training_data = output_training_data[non_zeroes[:,0],:]
            training_data = training_data[non_zeroes[:,0],:]

            if counter == 0:
                training_array = np.array(training_data)
                output_array = np.array(output_training_data)
                counter += 1 
            else:
                training_array = np.append(training_array, training_data, axis = 0)
                output_array = np.append(output_array, output_training_data, axis = 0) 
    
        ## create openCV compatible training set, train, and save training weights back to the classifier.json file, 
        # then return the trained algorithm
        training_set = cv.ml.TrainData.create(cv.Mat(training_array.astype('float32')), 
                                              responses = cv.Mat(output_array.astype('float32')), 
                                              layout = cv.ml.ROW_SAMPLE)
        algorithm1.train(training_set, flags = cv.ml.ANN_MLP_NO_OUTPUT_SCALE)
        algorithm1.save(self.classifier_path)  # these update the algorithm both in the disk file and in the PxQuPy class --> 
                                               # so each time training is run on an old classifier its weights should refine further
                                               ## If you don't wnat weights to change --- don't ever train again!
        self.algorithm = algorithm1
        return algorithm1

    def predict(self, 
                image: np.ndarray, 
                image_name: str,
                output_folder: Union[str, None] = None,
                ) -> np.ndarray[int]:
        '''
        This runs the provided QuPath classifier on an image (as a numpy array). Currently only limited QuPath classifiers are supported 
        (ANN_MLP only, not local normalization, etc.).
    
        Args:
            image (numpy array): 
                a numpy array representing the image to be analyzed

            image_name (str): 
                the file name of the image being analyzed, important for properly naming the output mask. Should include the file extension (usually .tiff). 

            output_folder (str, or default = None): 
                if not None, should be a valid directory (as a str) to write the pixel classification file into. If None, will instead write the file into 
                self.output_directory folder
    
        Returns:
            numpy array: 
                the pixel classification or probability predictions from the classifier. Dimensions match the spatial dimensions of the image.

        Inputs / Outputs:
            Outputs: 
                a pixel classification predict map exported as a .tiff file to self.output_directory/{image_name} or to output_folder/{image_name}, if output_folder is not None.
        '''
        # first get the name of the ANN_MLP classifier -- it'll be useful for naming things
        if output_folder is None:
            output_file_name = self.output_directory + "/" + image_name
        else:
            output_file_name = output_folder + "/" + image_name
        classifier_details = self.details_dict
        algorithm1 = self.algorithm
    
        # Create the data matrix with the correct features, sigmas, and channels for the classifier to make predictions with:
        all_together = all_channels_features_together(image, classifier_details)
        px_class = _predictClassifier(all_together, 
                                     algorithm1, 
                                     classifier_details['categorical'], 
                                     num_classes = classifier_details['number_of_classes'])   
        
        # finally, export the pixel classifications derived as .tiff files and return the px_class if it is desired
        tf.imwrite(output_file_name, px_class.T.astype('int32'), photometric = "minisblack")
        return px_class

    def predict_folder(self, 
                       img_folder: Union[Path, str],
                       output_folder: Union[str, None] = None,
                       ) -> None:
        '''
        This runs the provided PxQuPy classifier on the images in the provided directory, exporting images (calls self.predict for each image in the img_folder).

        Args:
            img_folder (str / Pathlike): 
                the path to a folder containing the images to generate pixel classifications from

            output_folder (str, or default = None): 
                if not None, should be a valid directory (as a str) to write the pixel classifications into. If None, will instead write the files into 
                the self.output_directory folder

        Inputs / Outputs:
            Outputs: 
                pixel classification predict maps exported as .tiff files to self.output_directory/ or to output_folder/, if output_folder is not None.
        '''
        if output_folder is None:
            output_folder = self.output_directory
        img_folder = str(img_folder)
        for image_name in sorted(os.listdir(img_folder)):
            image = tf.imread(img_folder + "/" + image_name).T
            self.predict(image, image_name, output_folder = output_folder)

######################### Functions that the class calls, but do not need to be inside the class itself ###########################
# derived from an earlier implementation of PxQuPy that took an exported classifier file from QuPath & sought to replicate QuPath output

def all_channels_features_together(image: np.ndarray[float], 
                                   classifier_details: dict,
                                   ) -> np.ndarray[float]:
    '''
    This function takes the image and the features, sigmas, and channel list + ordered channel_list and generates all the necessary feature 
    layers for all channels and at all desired sigmas for the classifier to ingest and make predictions.

    Args: (contained inside classifier_details dictionary)
        image (numpy array): 
            the numpy array derived from reading in the mult-channel .tif file of the original image

        channel_list_in_order (list): 
            a list of the channels to generate features from, in order desired. Needed to be made explicitly in cases 
            where a new panel / order of antibodies is being used compared to when the classifier was originally trained.

        features_list (list of strings): 
            a list of the features to be extracted from the designated channels / sigmas

        simga_list (list of numeics):   
            a list of the sigma-levels to be used for extracting features

    Returns:
        numpy array:  
            a 3D numpy array containing the all the features -- for each channel, sigma-level, and feature in the features_list -- 
            stacked in order that the pixel classifier ingests them. Has a shape matching the two spatial dimension of the image,
            plus a 3rd dimensions matching the number of features needed by the classifier.
                
                3rd Dimension size = len(sigma_list)*len(features_list)*len(channels_list_in_order)
    '''
    # Get the length of key features that determine the shape of downstream arrays and loops
    channel_number = len(classifier_details['channel_dictionary'])
    channel_list_in_order = list(classifier_details['channel_dictionary'].values())  
                                         ## this depends on the dictionaries' keys being entered by the user in order 
                                         # (so that the order of inputs matches between images with different channel setups)
    features_list = classifier_details['features_list']
    features_number = len(features_list)
    sigma_number = len(classifier_details['sigma_list']) 

    # Run the loops to generate the features for each channel at each sigma needed by the ANN_MLP classifier:
    all_together = np.zeros(((features_number*sigma_number*channel_number),image.shape[0],image.shape[1]))
    current_layer = 0
    for ii in classifier_details['sigma_list']:
        for kk in channel_list_in_order:
            image_temp = image[:,:,kk]            
            kernel0, kernel1, kernel2 = _getGaussianDerivs(ii) 
            # for each feature, a separate "if" statement on whether to calculate it:
            # the order of if statements matches QuPath classifier's, allowing a QuPath classifier to be used / allowing testing
            # vs. QuPath when initially developing this
            hessians_done = False
            struct_tense = False
            mixed_deriv = False
            if "GAUSSIAN" in features_list:
                gauss = cv.sepFilter2D(image_temp,ddepth = -1,kernelX = kernel0, kernelY = kernel0, borderType = 1)
                all_together[current_layer] = gauss
                current_layer += 1
            if "LAPLACIAN" in features_list:
                dxx, dyy, dxy = _getMixedDerivs(image_temp,kernel0, kernel1, kernel2) 
                mixed_deriv = True
                laplace = _getLaplacian(dxx, dyy)
                all_together[current_layer] = laplace
                current_layer += 1
            if "WEIGHTED_STD_DEV" in features_list:
                all_together[current_layer] = _getWeightedStdDev(image_temp, kernel0)
                current_layer += 1
            if "GRADIENT_MAGNITUDE" in features_list:
                all_together[current_layer] = _getGradMax(image_temp, kernel0, kernel1)
                current_layer += 1
            if "STRUCTURE_TENSOR_EIGENVALUE_MAX" in features_list:
                stMin, stMax, coherence = _getStructureTensor(image_temp,kernel0, co_bool = False)
                struct_tense = True
                all_together[current_layer] = stMax
                current_layer += 1
            if "STRUCTURE_TENSOR_EIGENVALUE_MIN" in features_list:
                if struct_tense is True:
                    all_together[current_layer] = stMin
                    current_layer += 1
                else:
                    stMin, stMax, coherence = _getStructureTensor(image_temp,kernel0, co_bool = False)
                    struct_tense = True
                    all_together[current_layer] = stMin
                    current_layer += 1
            if "STRUCTURE_TENSOR_COHERENCE" in features_list:
                stMin, stMax, coherence = _getStructureTensor(image_temp,kernel0, co_bool = True)
                struct_tense = True
                all_together[current_layer] = coherence                  
                current_layer += 1  
            if "HESSIAN_DETERMINANT" in features_list:
                if mixed_deriv is False:
                    dxx, dyy, dxy = _getMixedDerivs(image_temp,kernel0, kernel1, kernel2)
                    mixed_deriv = True
                hessian_min, hessian_max, hessian_determinant = _getHessian(dxx, dyy, dxy)
                hessians_done = True
                all_together[current_layer] = hessian_determinant
                current_layer += 1
            if "HESSIAN_EIGENVALUE_MAX" in features_list:
                if hessians_done is True:
                    all_together[current_layer] = hessian_max               
                    current_layer += 1
                else:
                    if mixed_deriv is False:
                        dxx, dyy, dxy = _getMixedDerivs(image_temp,kernel0, kernel1, kernel2)
                        mixed_deriv = True
                    hessian_min, hessian_max, hessian_determinant = _getHessian(dxx, dyy, dxy)
                    hessians_done = True
                    all_together[current_layer] = hessian_max             
                    current_layer += 1
            if "HESSIAN_EIGENVALUE_MIN" in features_list:
                if hessians_done is True:
                    all_together[current_layer] = hessian_min         
                    current_layer += 1
                else:
                    if mixed_deriv is False:
                        dxx, dyy, dxy = _getMixedDerivs(image_temp,kernel0, kernel1, kernel2)
                        mixed_deriv = True
                    hessian_min, hessian_max, hessian_determinant = _getHessian(dxx, dyy, dxy)
                    all_together[current_layer] = hessian_min               
                    current_layer += 1
    all_together = all_together.T
    return all_together

def _predictClassifier(all_together: np.ndarray[float],
                       algorithm1: cv.ml.ANN_MLP, 
                       categorical: bool, 
                       num_classes: Union[int, None] = None,
                       ) -> np.ndarray[int]:
    ''' 
    This function performs slightly different predictions on the data, dependent on the classifier type being used, and returns the 
    final predicted mask.

    Args:
        all_together (3-D numpy array): 
            the numpy array containing the all the features derived from the original image, stacked (shares 2 dimensions with image + 3rd stacked dimension)

        algorithm1 (cv.ml.statmodel.ANN_MLP instance): 
            this is the classifier itself

        categorical (boolean): 
            a boolean to determine whether the classifier is meant to produce categorical or probabilities as output. True = probability output, all other values 
            (False, or non-boolean) mean a categorical output. 

        num_classes (int): 
            is necessary for probability outputs, but not needed for categorical outputs

    Returns:
        numpy array: 
            2-D, the pixel classification or probability predictions from the classifier. Dimensions match the spatial dimensions of the image.
    '''
    px_class = np.zeros((all_together.shape[1],all_together.shape[0]))
    if categorical is False:
        px_class = np.zeros((all_together.shape[1],all_together.shape[0],num_classes))
    for i in range(0, all_together.shape[1]):
        row = all_together[:,i]
        px_probs = algorithm1.predict(row)[1]
        if categorical is False:
             px_class[i,:,:] = scipy.special.softmax(px_probs, axis = 1)      # presumes negative precedes positive in the QuPath classifier
        else:
            px_class[i] = np.argmax(px_probs, axis = 1) + 1 ## check proper axis!
    ## for now, and perhaps forever, only use the ANN_MLP classifier type (it seems like the best classifier anyway)
    return px_class

## Features generation functions:

def _getGaussianDerivs(sigma: float) -> tuple[np.ndarray[float],np.ndarray[float],np.ndarray[float]]:  # ***QuPath translation [complete]
    '''
    This is a simplified function that return all gaussian derivative kernel of order 0, 1, and 2 at once for a given sigma, 
    in a manner that matches QuPath's implementation of these kernels (specifically, matches kernel size).
    It is derived / translated from the two Java-language functions that implemented this in QuPath

    Args:
        sigma (numeric): 
            the numbers corresponding to the sigmas generated in the QuPath. This also increases the length of the kernel 
            The size of the kernel increases by the equation sigma*8 + 1 (rounded down to an integer). 
            The values available for this from Qupath are 0.5, 1.0, 2.0, 4.0, and 8.0

    Returns:
        numpy array: the gaussian kernal (zero-th derivative)

        numpy array: the first derivative of the gaussian kernel

        numpy array: the second derivative of the gaussian kernel
    '''
    length = int((sigma*8) + 1)
    n = int(length / 2)
    denom2 = 2 * (sigma**2)
    denom = sigma * np.sqrt(2 * np.pi)
    
    kernel0 = np.zeros((length,1))
    for i in range(-n, n+1):
        val = np.exp(-(i **2)/denom2)
        kernel0[(i + n)] = (val / denom)
        
    kernel1 = np.zeros((length,1))    
    denom = (sigma**3) * np.sqrt(2 * np.pi)
    for i in range(-n, n+1):
        val = - i * np.exp(-(i**2)/denom2)
        kernel1[(i + n)] = (val / denom)

    kernel2 = np.zeros((length,1))    
    denom = (sigma**5) * np.sqrt(2 * np.pi)
    for i in range(-n, n+1):
        val = - (sigma**2 - i**2) * np.exp(- (i**2)/denom2)
        kernel2[(i + n)] = (val / denom)
    
    return kernel0, kernel1, kernel2
    
def _getMixedDerivs(image: np.ndarray[float], 
                    kernel0: np.ndarray[float], 
                    kernel1: np.ndarray[float], 
                    kernel2: np.ndarray[float],
                    ) -> tuple[np.ndarray[float],np.ndarray[float],np.ndarray[float]]:            # ***QuPath translation [completely]
    ''' 
    Returns dxx, dyy, and dxy for a given image. Kernel0,1,2 are the gaussian derivative kernels of order 0,1,2. Retrieve kernels from the getGaussianDeriv() function
    '''
    dxy = cv.sepFilter2D(image,ddepth = -1,kernelX = kernel1, kernelY = kernel1, borderType = 1)
    dxx = cv.sepFilter2D(image,ddepth = -1,kernelX = kernel2, kernelY = kernel0, borderType = 1)
    dyy = cv.sepFilter2D(image,ddepth = -1,kernelX = kernel0, kernelY = kernel2, borderType = 1)
    return dxx, dyy, dxy

def _getHessian(dxx: np.ndarray[float], 
                dyy: np.ndarray[float], 
                dxy: np.ndarray[float],
                ) -> tuple[np.ndarray[float],np.ndarray[float],np.ndarray[float]]:                    # ***QuPath translation [completely]
    '''
    Performs calculation of the Hessian Min / Max Eigenvalues.   dxx / dyy are the second-order derivatives of the gaussian kernal applied in x / y, with 
    dxy being the first-order derivative kernel applied in BOTH x and y. Use getMixedDerivs() function to obtain dxx,dyy,dxy.
    '''
    hessian_min = np.zeros((dxy.shape))
    hessian_max = np.zeros((dxy.shape))
    eigenvalues, eigenvectors = np.linalg.eig((np.array(([dxx,dxy],[dxy,dyy])).T))
    hessian_determinant = (dxx*dyy) - (dxy**2)
    for i in range(0,dxy.shape[0]):
        for j in range(0,dxy.shape[1]):
            hessian_min[i,j] = eigenvalues[j,i].min()
            hessian_max[i,j] = eigenvalues[j,i].max()
    return hessian_min, hessian_max, hessian_determinant

def _getLaplacian(dxx: np.ndarray[float], 
                  dyy: np.ndarray[float],
                  ) -> np.ndarray[float]:                                             # ***QuPath translation [completely]
    '''
    Derives the Laplacian of Gaussian in the same way as QuPath: simply add dxx and dyy.   dxx and dyy are the second order derivatives of the guassian kernel 
    in the x and y directions. Use getMixedDerivs() function to get dxx, dyy (and dxy).
    '''
    Laplacian_of_Gaussian = dxx + dyy
    return Laplacian_of_Gaussian

def _getStructureTensor(image: np.ndarray[float], 
                        kernel0: np.ndarray[float], 
                        co_bool: bool = True,
                        ) -> tuple[np.ndarray[float], np.ndarray[float], Union[np.ndarray[float], int]]:    # ***QuPath translation [completely]
    '''
    This function calculates stucture tensor eigenvalues and coherence from an image. It uses the zero-eth gaussian derivative kernel (kernel0).
    Retrieve "kernel0" from the getGaussianDeriv() function
    
    co_bool = False means do not calculate the coherence. I have it here because the coherence calculation can tend to throw warnings. 
    (due to division, and the possibility of division by zero)
    '''
    ST_dx = cv.Sobel(image, -1, 1, 0)
    ST_dy = cv.Sobel(image, -1, 0, 1)
    ST_dxx = ST_dx**2
    ST_dyy = ST_dy**2
    ST_dxy = ST_dx*ST_dy
    ST_dxx = cv.sepFilter2D(ST_dxx, ddepth = -1, kernelX = kernel0, kernelY = kernel0, borderType = 1)
    ST_dyy = cv.sepFilter2D(ST_dyy, ddepth = -1, kernelX = kernel0, kernelY = kernel0, borderType = 1)				
    ST_dxy = cv.sepFilter2D(ST_dxy, ddepth = -1, kernelX = kernel0, kernelY = kernel0, borderType = 1)
    stMin, stMax, hessian_determinant = _getHessian(ST_dxx, ST_dyy, ST_dxy)
    if co_bool is True:              
        coherence = ((stMax - stMin) / (stMax + stMin)) **2
        coherence = np.nan_to_num(coherence)
    else:
        coherence = 0
    return stMin, stMax, coherence

def _getWeightedStdDev(image: np.ndarray[float], 
                       kernel0: np.ndarray[float],
                       ) -> np.ndarray[float]:                          # ***QuPath translation [complete]
    '''
    This function calculated the weighted standard deviation of an image.    Retrieve "kernel0" from the getGaussianDeriv() function
    '''
    for_weighted_st_dev = cv.sepFilter2D(image, ddepth = -1, kernelX = kernel0, kernelY = kernel0, borderType = 1)
    img_squared = np.square(image) 
    img_squared = cv.sepFilter2D(img_squared, ddepth = -1, kernelX = kernel0, kernelY = kernel0, borderType = 1)
    for_weighted_st_dev = img_squared - (for_weighted_st_dev**2)
    for_weighted_st_dev = np.sqrt(abs(for_weighted_st_dev))
    return for_weighted_st_dev

def _getGradMax(image: np.ndarray[float], 
                kernel0: np.ndarray[float], 
                kernel1: np.ndarray[float],
                ) -> np.ndarray[float]:                                  # ***QuPath translation [complete]
    '''
    This function calculates the gradient maximum of an image.        Retrieve "kernel0" and "kernel1" from the getGaussianDeriv() function
    '''
    grad_dxx = cv.sepFilter2D(image, ddepth = -1, kernelX = kernel1, kernelY = kernel0, borderType = 1)
    grad_dyy = cv.sepFilter2D(image, ddepth = -1, kernelX = kernel0, kernelY = kernel1, borderType = 1)				
    magnitude = cv.magnitude(grad_dxx, grad_dyy)
    return magnitude

class UnsupervisedClassifier():               
    '''
    This class coordinates the creation, training, and prediction from an unsupervised pixel classifier.

    Key Attributes:
        panel (pandas dataframe): 
            the same steinbock-style panel file / panel.csv from the main image processing steps. Critically, has columns with the channel
            names & a column 'keep' for whether that channel was carried over in the images of the dataset. 

        training_dictionary (dict): 
            contains infomration on the training of the classifier for reproducibility. Gets exported to the disk as a _details.json for future reference.

        flowsom_dictionary (dict): 
            contains information on the trained FlowSOM classifier used in the process of prediciton, including the 
            flowsom.FlowSOM instance itself. It is not saved to the disk as .json (I don't know for certain but I expect a flowsom.FlowSOM 
            object is not able to be written to the disk easily). 

        classifier_dir (str):
            The directory to the folder where the pixel classifier folder is to be setup

        output_dir (str): 
            The directory to the folder where the pixel classifier will output predictions by default. It is a sub-folder of classifier_dir. 
    
    The concept for this type of classifier was inspired from the Pixie / Ark-analysis::

            https://github.com/angelolab/ark-analysis?tab=MIT-1-ov-file

    Pixie is licensed under the MIT license
    
    However, this implementation is essentially fresh, although preserving the key steps 
            (0.999% channel normalization --> FlowSOM --> normalization within pixels) 

    but not the rest of the Pixie code.
    The only part that I'm aware of that borrows more directly from the original Pixie is how the 0.999% channel normalization numbers are 
    aggregated & averaged for all images, instead of done on an image-by-iamge basis, as I had originally done.

    This implementation also includes new capacities compared to Pixie, such as the ability to generate QuPath-like features (hessians, laplacians, etc.) as input 
    channels for the FlowSOM, although it is uncertain how useful these additional features are.
    '''
    def __init__(self, 
                 homedir: Union[str, Path], 
                 classifier_name: str, 
                 panel: Union[None, pd.DataFrame] = None, # only set here to None because the panel can be added later
                 classifier_dictionary: dict = {}):
        '''
        '''
        self._homedir = str(homedir)
        self.classifier_name = classifier_name
        self.panel = panel   ## needs to be inputted by user, or loaded from unsupervised classifier folder
        self.flowsom_dictionary = classifier_dictionary  ## derived in training, or loaded from unsupervised classifier folder -- loading not implmented yet
        self._setup_classifier_directory(classifier_name = classifier_name)
        
    def _setup_classifier_directory(self, classifier_name: Union[None, str] = None) -> None: 
        ''' Sets up individual classifier's folder '''  
        if not os.path.exists(self._homedir):
            print("Error! Home Directory does not exist!")
            return
        self._px_dir = self._homedir + "/Pixel_Classification"
        if not os.path.exists(self._px_dir):
            os.mkdir(self._px_dir)   

        self.classifier_dir = self._px_dir + "/" + classifier_name
        self.output_dir = self.classifier_dir + "/classification_maps"
        if not os.path.exists(self.classifier_dir):
            os.mkdir(self.classifier_dir)
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)

    def setup_and_train(self, 
                        img_directory: Union[Path, str], 
                        sigma: float = 1.0, 
                        size: int = 500000, 
                        seed: int = 1234, 
                        n_clusters: int = 20,
                        xdim: int = 15, 
                        ydim: int = 15, 
                        rlen: int = 50,
                        smoothing: int = 0,
                        suppress_zero_division_warnings = False,
                        quantile: float = 0.999,
                        ) -> tuple[dict, dict]:
        '''
        This function performs all the steps required to train an initialized unsupervised classifier.

        Args:
            img_directory (string or Path): 
                The path to a folder containing the .tiff images to train (and presumably predict) from

            sigma (float): 
                sets the extent of Gaussian blurring used to generate features for training 

            size (integer):  
                The number of pixels to sample from the iamges to form the training dataset

            seed (integer): 
                seed for the non-deterministic FlowSOM algorithm

            n_clusters (integer): 
                The number of metaclusters for the FlowSOM algorithm to return. 

            xdim / ydim (integer / integer):  
                The X / Y dimensions of the FlowSOM self-organizing map. xdim * ydim is how many initial 
                points are in the SOM (and so, how many clusters are predicted before merging down to n_clusters)

            rlen (integer): 
                The number of training iterations for the SOM

            additional_features (boolean): 
                whether there are additional features beyond only the gaussian blurred channels. If False, can run faster by skipping unneeded steps.

            smoothing (integer > 0): 
                Whether & how much to smooth the pixel classification made by the FlowSOM. If smoothing = 0, no 
                smoothing is applied. Otherwise, smoothing argument is used as the threshold for the smooth_isolated_pixels() 
                function which removes isolated pixel classifications from a pixel classification map. 
                Saved in the training dictionary, but not applied during training -- only applied later after prediction.

        Returns:
            dictionary: contains the trained flowSOM instance itself, useful for classification of  images

            dictionary:  contains the training parameters, useful for reproducibility / providing a record of how the classifier was trained. 

        Inputs / Outputs: 
            Outputs: 
                in the process of setting up the dictionaries, this method writes 2 .json files to the self.classifier_dir folder
        ''' 
        if suppress_zero_division_warnings:
            warnings.filterwarnings("ignore", message = "invalid value encountered in divide")
        img_directory = str(img_directory)
        panel = self.panel
        self.quantile = quantile

        ## Set up Panel file:
        channels_to_use = (panel['keep'] == 1)
        dropped_panel = panel[channels_to_use].reset_index().drop('index', axis = 1)
        additional_features_dict = make_feature_dict_from_panel(dropped_panel)
        panel_with_features = add_features_to_panel(dropped_panel, additional_features_dict)

        ## Get quantile averages & list of images:
        quantile_avg = get_quantile_averages(img_directory, channels_to_use, quantile = quantile)
        list_of_images = sorted(os.listdir(img_directory))

        counter = 0
        for image_name in list_of_images:
            image = _read_image(img_directory, image_name)
            pixels = blur_flatten_quantile_sample(image, 
                                                  channels_to_use, 
                                                  quantile_avg, 
                                                  dropped_panel, 
                                                  additional_features_dict = additional_features_dict,
                                                  sigma = sigma, 
                                                  seed = seed, 
                                                  sample_size = size, 
                                                  num_images = len(os.listdir(img_directory)))
            if counter == 0:
                pixels_together = np.array(pixels)
                counter += 1
            else:
                pixels_together = np.append(pixels_together, pixels, axis = 0)

        
        training_pixels = np.apply_along_axis(_min_max_normalize, axis = 1, arr = pixels_together)
        training_pixels = np.nan_to_num(training_pixels)

        
        panel_with_features_for_anndata = panel_with_features.copy()
        panel_with_features_for_anndata.index = panel_with_features_for_anndata['antigen']    
        my_anndata = anndata.AnnData(training_pixels, var = panel_with_features_for_anndata)
        fs = FlowSOM(my_anndata.copy(), 
                     n_clusters = n_clusters, 
                     cols_to_use = my_anndata.var.index, 
                     xdim = xdim,
                     ydim = ydim, 
                     rlen = rlen,  
                     seed = seed)
        panel_with_features.index = panel_with_features['antigen']

        flowsom_dictionary = {"quantile_avg": quantile_avg, 
                              "channels_to_use": channels_to_use, 
                              "panel": panel_with_features_for_anndata,
                              "fs": fs, 
                              "features_dict": additional_features_dict,
                              "sigma": sigma, 
                              "quantile": quantile,
                              "smoothing": smoothing, 
                              "number_of_classes": n_clusters}
        self.flowsom_dictionary = flowsom_dictionary

        ## make training dictionary for export to disk:
        ## it should likely contain all feasible (aka, serializable) info not already contained in the panel.csv --> at minimum needs 
        #       to allow for reproducibility!
        training_dictionary = {}
        training_dictionary['sigma'] = sigma
        training_dictionary['seed'] = seed
        training_dictionary['number_of_classes'] = n_clusters
        training_dictionary['Xdim'] = xdim
        training_dictionary['rlen'] = rlen
        training_dictionary['size'] = size
        training_dictionary['quantile'] = quantile
        training_dictionary['smoothing'] = smoothing
        training_dictionary['features_dictionary'] = additional_features_dict
        training_dictionary['img_directory'] = img_directory
        self.training_dictionary = training_dictionary
        if suppress_zero_division_warnings:
            warnings.filterwarnings("default", message = "invalid value encountered in divide") 
        return flowsom_dictionary, training_dictionary
    
    def predict(self, 
                image_name: str, 
                img_directory: Union[Path, str],
                flowsom_dictionary: dict,
                output_folder: Union[str, None] = None) -> None:
        '''
        Takes in an image directory + image name, and a training FlowSOM algorithm, and saves a prediction for that image in the pixel classifier's self.output_dir 
        or in output_folder (if provided / not None)
        '''
        img_directory = str(img_directory)
        if output_folder is None:
            output_directory = self.output_dir
        else:
            output_directory = output_folder
        image = _read_image(img_directory, image_name)
        classification = classify_one(image, flowsom_dictionary, quantile = self.quantile)
        tf.imwrite((output_directory + "/" + image_name), (classification.T.astype('int32')))

    def predict_folder(self, 
                       img_directory: Union[Path, str], 
                       flowsom_dictionary: dict,
                       output_folder: Union[str, None] = None) -> None:
        ''' 
        Applies self.predict to every image in a supplied folder 
        '''
        img_directory = str(img_directory)
        if output_folder is None:
            output_directory = self.output_dir
        else:
            output_directory = output_folder
        if not os.path.exists(output_directory):
            os.mkdir(output_directory)

        list_of_images = sorted(os.listdir(img_directory))
        for i in list_of_images:
            image = _read_image(img_directory, i)
            classification = classify_one(image, flowsom_dictionary, quantile = self.quantile)
            tf.imwrite((output_directory + "/" + i), (classification.T.astype('int32')))


def make_feature_dict_from_panel(panel: pd.DataFrame) -> dict:
    '''
    Takes in a panel file of the specified format and returns the additional feature dictionary.

    Format:
    columns: 'antigen' || 'keep' || 'GRAD_MAG' || 'HESSIAN_DET' || 'HESSIAN_MAX' || 'HESSIAN_MIN' || 'LAPLACIAN' || 'STRUCT_CO' || 'STRUCT_MAX' || 'STRUCT_MIN' || 'WGT_STDV'
    rows = 1 for each channel in the images.

    antigen --> the name of the channel (biological name usually)
    
    keep --> 0 or 1, 0 means do not use channel in classifier, 1 do use channel
    
    for each of the remaining columns (named after possible features), if a channels entry in that column = 1 (instead of 0) that means 
    generate that feature for that channel and use in the classifier.
    '''
    #possible_features_list = ['GRAD_MAG', 
    #                          'HESSIAN_DET', 
    #                          'HESSIAN_MAX', 
    #                          'HESSIAN_MIN', 
    #                          'LAPLACIAN', 
    #                          'STRUCT_CO', 
    #                          'STRUCT_MAX', 
    #                          'STRUCT_MIN', 
    #                          'WGT_STDV']
    additional_features_dict = {}
    panel_for_features = panel.copy().drop("keep", axis = 1)
    panel_for_features.index = panel_for_features['antigen']
    for i in panel_for_features.index:
        additional_features_dict[i] = ["GAUSSIAN"]
        slice = panel_for_features.loc[i]
        slice = slice[slice == 1]
        features_slice = list(slice.index)
        if len(features_slice) > 0:
            additional_features_dict[i] = ["GAUSSIAN"] + features_slice
    return additional_features_dict

def add_features_to_panel(panel: pd.DataFrame, 
                          additional_features_dict: dict,
                          ) -> pd.DataFrame:
    ''' 
    Allows editing of the panel from an existing panel by passing in an edited features dictionary 
    '''
    append_panel = pd.DataFrame()

    channel_feature_list = []
    
    for j in additional_features_dict: 
        features_list = list(set(additional_features_dict[j]))
        features_list.sort()   ## do the same sorting as in the adding function to ensure same order...
        if len(features_list) > 1:
            features_list = features_list[1:]     ## ignore GAUSSIAN 
            for k in features_list:
                channel_feature_list.append(f'''{j}_{k}''')
                
    append_panel.index = channel_feature_list
    append_panel['antigen'] = channel_feature_list
    if len(append_panel) > 0:
        new_panel = pd.concat([panel, append_panel], axis = 0)
    else:
        new_panel = panel.copy()
    return new_panel

def make_features(image_channel_slice: np.ndarray[float], 
                  feature_list: list[str], 
                  sigma: float = 1.0,
                  ) -> np.ndarray[float]:
    '''
    This function makes new features for a given single channel (passedin as a numpy array), as determined by the features_list
    
    Args:
        image_channel_slice (2D numpy array): 
            represents a single channle of a 2D dimensional image (dimensions = X / Y)

        feature_list (list of strings): 
            the names of the features to derive from the image & return in the final array. Order of the features (when sorted): 
            ['GRAD_MAG', 'HESSIAN_DET', 'HESSIAN_MAX', 'HESSIAN_MIN', 'LAPLACIAN', 'STRUCT_CO', 'STRUCT_MAX', 'STRUCT_MIN', 'WGT_STDV'] (insert in same order)

        sigma (float): 
            sigma value for the kernels used in feature generation

    Returns:
        3D numpy array: This is the stack of features derived from the image. Dimension lengths: 

                >> dim1 =  length feature_list, 
                >> dim2, dim3  = image_channel_slice dim1, dim2
    '''
    structure_tensor = False
    hessian = False
    counter = 0
    all_together = np.zeros([len(feature_list),image_channel_slice.shape[0],image_channel_slice.shape[1]])
    kernel0, kernel1, kernel2 = _getGaussianDerivs(sigma)
    dxx, dyy, dxy = _getMixedDerivs(image_channel_slice, kernel0, kernel1, kernel2)
    if "GRAD_MAG" in feature_list:
        all_together[counter] = _getGradMax(image_channel_slice, kernel0, kernel1)
        counter += 1
    if "HESSIAN_DET" in feature_list:
        hessian_min, hessian_max, hessian_determinant = _getHessian(dxx, dyy, dxy)
        hessian = True
        all_together[counter] = hessian_determinant
        counter += 1
    if "HESSIAN_MAX" in feature_list:
        if hessian is False:
            hessian_min, hessian_max, hessian_determinant = _getHessian(dxx, dyy, dxy)
            hessian = True
        all_together[counter] = hessian_max
        counter += 1
    if "HESSIAN_MIN" in feature_list:
        if hessian is False:
            hessian_min, hessian_max, hessian_determinant = _getHessian(dxx, dyy, dxy)
            hessian = True
        all_together[counter] = hessian_min
        counter += 1
    if "LAPLACIAN" in feature_list:
        all_together[counter] = _getLaplacian(dxx,dyy)
        counter += 1
    if 'STRUCT_CO' in feature_list:
        stMin, stMax, coherence = _getStructureTensor(image_channel_slice,kernel0,co_bool = True)
        structure_tensor = True
        all_together[counter] = coherence
        counter += 1
    if 'STRUCT_MAX' in feature_list:
        if structure_tensor is False:
            stMin, stMax, coherence = _getStructureTensor(image_channel_slice,kernel0,co_bool = False)
            structure_tensor = True
        all_together[counter] = stMax
        counter += 1
    if 'STRUCT_MIN' in feature_list:
        if structure_tensor is False:
            stMin, stMax, coherence = _getStructureTensor(image_channel_slice,kernel0,co_bool = False)
        all_together[counter] = stMin
        counter += 1
    if 'WGT_STDV' in feature_list:
        all_together[counter] = _getWeightedStdDev(image_channel_slice, kernel0)   
        ## no need to increment counter after the last feature.
    return all_together

def get_quantile_averages(img_directory: Union[Path, str], 
                          channels_to_use: list[int],
                          quantile: float = 0.999,
                          ) -> np.ndarray[float]:
    ''' 
    Finds the 99.9% quantiles for every channel_to_use of every image in the img_directory, and return the average across images 
    '''
    img_directory = str(img_directory)
    quantile_list = []
    for i in sorted(os.listdir(img_directory)):
        img = tf.imread("".join([img_directory, "/", i]))
        if  img.shape[0] > img.shape[1]:    ##### Presumes the channels have the fewest dimensions 
                                            # (as in, the ROI is not thinner in one dimensions than the number of channels)
            img = img.T
        img = img[channels_to_use,:,:]
        quantile_array = np.zeros([img.shape[0]])   ## should be an array of length = channels
        for j,jj in enumerate(img):     ### since we've removed the unwanted channels, lets collect the 0.999 quantile values)
             quantile_array[j] = np.quantile(jj[jj > 0], quantile)
        quantile_list.append(quantile_array)
        total = 0
        for i in quantile_list:
            total = i + total
        quantile_avg = total / (len(quantile_list))
    return quantile_avg

def add_additional_features(image: np.ndarray[float], 
                            dropped_panel: pd.DataFrame, 
                            additional_features_dict: dict = {}, 
                            sigma: float = 1.0,
                            quantile: float = 0.999,
                            ) -> tuple[np.ndarray[float], list[float]]:
    '''
    This function adds layers to an image (at the end, in order of channel) composed of a few potentially useful features:

    ['GRAD_MAG', 'HESSIAN_DET', 'HESSIAN_MAX', 'HESSIAN_MIN', 'LAPLACIAN', 'STRUCT_CO', 'STRUCT_MAX', 'STRUCT_MIN', 'WGT_STDV'] 

    Args:
        image (numpy array): 
            the multichannel image from which features are to be derived and then appended to. ONLY the channels to use 
            should remain in image! (channels to drop from the the classifier MUST have already been dropped)

        dropped_panel (pandas dataframe): 
            this is a dataframe with the critical components being a column called 'antigen' with the antigen-to-use name, and the standard index 
            (Ascending numbers, 0 --> len(df) - 1). It should have one row for each antigen to use, in order as they appear in the image argument.

            Easily derived by: 
            my_unsupervised_classifier.panel[my_unsupervised_classifier.panel['keep'] == 1].reset_index().drop('index', axis = 1)

        additional_features_dict (dictionary): 
            channel / feature pairs with the form --
            {  'channel_string_name':["feature_name_J_string", "feature_name_K_string", ...], 'GFAP':["HESSIAN_MIN","LAPLACIAN", ...], ... }

        Sigma (float): 
            the sigma value for the kernels used in feature generation.


    Returns:
        numpy array: represents the original image, following by additional layers, in order of channel, then feature
        (so first all the features of the first channel are added, then all the channels of the second features, etc.)

        list of floats: a list of 99.9% quantile values for every image channel/feature layer being used in the algorithm
    '''
    if len(additional_features_dict) == 0:  ## in the context of the GUI program / pipeline, a user may choose to use no additional features!
        return image, None
        
    quantile_list = []
    for j in additional_features_dict: 
        features_list = list(set(additional_features_dict[j]))
        features_list.sort()   ##sorted order = ['HESSIAN_DET', 'HESSIAN_MAX', 'HESSIAN_MIN', 'LAPLACIAN']
        j = dropped_panel[dropped_panel['antigen'] == j].index[0]
        
        channel_slice = image[j,:,:]    ## tehehe... imageJ
        if len(features_list) > 1:      ## ignore channels with only 'GAUSSIAN' (as in, all selected channels)
            features_list = features_list[1:]
            feature_set = make_features(channel_slice, features_list, sigma)
            for i in feature_set:
                feature_999 = np.quantile(i[i > 0], quantile)
                quantile_list.append(feature_999)
            image = np.append(image, feature_set, axis = 0)   ## note that that order in which the new features are added to the end of the image
    return image, quantile_list

def gaussian_blur_image(image: np.ndarray[float], 
                        sigma: float = 1.0,
                        ) -> np.ndarray[float]:
    ''' 
    This function blurs an image, gaussian-ly 
    '''
    kernel0, kernel1, kernel2 = _getGaussianDerivs(sigma)   
                ## this is a QuPATH style gaussian kernal, not a vanilla open-cv versian --> I think this tends to make the kernel larger, 
                # and also forces a fixed scaling between sigma and the kernel size (kernel length --> sigma*8 + 1)
    image = cv.sepFilter2D(image,ddepth = -1,kernelX = kernel0, kernelY = kernel0, borderType = 4)
    return image

def get_random_pixels(pixel_array: np.ndarray[float], 
                      size: int = 100000, 
                      seed: int = 1234,
                      ) -> np.ndarray[float]:
    ''' 
    This helper function return a random set of pixels from an image as a 1-D array
    '''
    gen = np.random.default_rng(seed = seed)
    slice = gen.choice(pixel_array, size = size, replace = False)
    return slice

def blur_flatten_quantile_sample(img: np.ndarray[float], 
                                 channels_to_use: np.ndarray[bool], 
                                 quantile_avg: np.ndarray[float], 
                                 dropped_panel: pd.DataFrame, 
                                 additional_features_dict: dict = {}, 
                                 sigma: float = 1.0, 
                                 seed: int = 8675309, 
                                 sample_size: int = 500000, 
                                 num_images: int = 1,
                                 quantile: float = 0.999,
                                 ) -> np.ndarray[int]:
    """
    This coordinates all the preparation steps for a single image.

    Args:
        img (numpy array): 
            the image to train or predict with

        channels_to_use (numpy array): 
            a boolean array for slicing image, only keeping the desired channels for training

        quantile_avg (nump array): 
            The 99.9% quantile values for each channel / feature generated from the image for training

        dropped_panel (pandas DataFrame): 
            this is a dataframe with rows = channels, and columns = features, with each entry being 0 / 1 to indicate whether to generate that feature for that channel.

        additional_features_dict (dictionary): 
            channel / feature pairs with the form --
            {  'channel_string_name':["feature_name_J_string", "feature_name_K_string", ...], 'GFAP':["HESSIAN_MIN","LAPLACIAN", ...], ... }

        sigma (float): 
            The feature blurring to use with generating the freatures for training

        seed (int): 
            The random seed of non-deterministic steps in the algorithm, for reproducibility

        sample_size (int): 
            The number of random to pixels to use during training

        list_img (integer): 
            the numer of images in the overall dataset, sample_size // num_images is how many pixels will be actually sampled from the image. Used for sampling from 
            multiple images at once. Default is 1, so by default number of pixels sampled from the image == sample_size.
    
    Returns:
        numpy array: the 1D array of random pixels, with all the channels / features per pixel divided by that feature / channel's 99.9% quantile value
    """
    ## first, drop unwanted channels
    img = img[channels_to_use,:,:]

    ## If there are additinal features to add, add them:
    if len(additional_features_dict) > 0:
        img, local_feature_quantile_list = add_additional_features(img, 
                                                                   dropped_panel, 
                                                                   additional_features_dict = additional_features_dict, 
                                                                   sigma = sigma, 
                                                                   quantile = quantile)

    ## now iterate through the image, blurring & flattening
    for i, ii in enumerate(img):
        if i <= len(additional_features_dict): 
            ii = gaussian_blur_image(ii, sigma)  
        image = ii.flatten()
        image = np.expand_dims(image, axis = 1)
        if i == 0:
            flat_image = np.array(image)
        else:
            flat_image = np.append(flat_image, image, axis = 1)
    pixel_array = np.array(flat_image)

    ## do the quantile divisions -- added features are divided by 1 to leave unchanged
    if quantile_avg.shape[0] != pixel_array.shape[1]:   ## this means additional features have been added
        new_quantiles_avg = np.append(quantile_avg, np.array(local_feature_quantile_list), axis = 0)
        pixel_array = (pixel_array / new_quantiles_avg) 
    else:
        pixel_array = (pixel_array / quantile_avg) 
    pixel_array = np.nan_to_num(pixel_array)
    # pixel_array[pixel_array > 1] = 1   ## set pixels brighter than threshold to 1

    ## sample, if doing training
    num_px_from_img = sample_size // num_images
    pixel_array = get_random_pixels(pixel_array, size = num_px_from_img, seed = seed)
    return pixel_array

def _min_max_normalize(array: np.ndarray[float], power: float = 0.0) -> np.ndarray[float]:
    '''
    min / max normalizes a numpy array
    '''
    #print(len(array))   ## a check that the proper axis is being normalized over
    minimum = array.min()
    maximum = array.max() 
    array = (array - minimum) / (maximum - minimum)
    if power != 0.0:
        array = array * np.power(maximum, power) #### test: see if the algorithm will be capable of identifying true negatives this way (currently, it is not capable of that)
                                ## this scaling is intended ensure that pixels that are dim for every channel don't have a channel set to equal level (aka, 1)
                                ## with pixels that have at lest one bright channel
    if ((maximum - minimum) == 0):
        if (maximum > 0):
            array = np.ones(array.shape)     ### if all channels are the same level within a pixel, then set them equal, either at one or at zero
        else:
            array = np.zeros(array.shape)
    return array

def _read_image(img_directory: Union[Path, str], 
                image_name: str,
                ) -> np.ndarray[float]:
    '''
    reads in an image, and transposes it if the first dimension is not shorter than the second 
    This is a quick and dirty check that *usually* should get the channel dimensions to be the first [0-th] dimension.
    It presumes the channels have the fewest dimensions (aka the ROI is not thinner in one spatial dimensions than the number of channels)
    '''
    img_directory = str(img_directory)
    img = tf.imread("".join([img_directory, "/", image_name]))
    if  img.shape[0] > img.shape[1]: 
        img = img.T
    return img

def classify_one(img: np.ndarray[float], 
                 flowsom_dictionary: dict,
                 quantile:float = 0.999,
                 suppress_zero_division_warnings: bool = True,
                 ) -> np.ndarray[int]:
    '''   
    Classify pixel from a trained FlowSOM algorithm.

    Args:
        img (numpy array): The image to have its pixels classified

        flowsom_dictionary (dictionary): 
            contains the trained flowsom instance and the training components of the flowsom
            key : value >>> "quantile_avg" : list of 99.9% quantile values (averaged across training images):

                "features_dict" : a dictionary indicating the channels to use and the features to make from each channel

                "sigma" : a float indicating the leve of gaussian smoothing to apply when generating features
                
                "smoothing" : whether to smooth the pixel classification output (remove isolated pixel classifications)

                "panel" : the pandas dataframe representing what channels / features to use

                "channel_to_use" : boolean numpy array for quick selection of desired channels

                "fs" : the trained FlowSOM instance

                "number_of_classes" : The number of outputted metaclusters from the FlowSOM

    Returns:
        numpy array: the pixel classification prediction for the image 
    '''
    if suppress_zero_division_warnings:
        warnings.filterwarnings("ignore", message = "invalid value encountered in divide")
    # unpack dictionary items
    quantile_avg = flowsom_dictionary["quantile_avg"]
    additional_features_dict = flowsom_dictionary["features_dict"]
    sigma = flowsom_dictionary["sigma"]
    smoothing = flowsom_dictionary["smoothing"]
    panel = flowsom_dictionary["panel"].drop('antigen', axis = 1).reset_index()

     ## first, drop unwanted channels
    img = img[flowsom_dictionary["channels_to_use"],:,:]

    ## If there are additinal features to add, add them:
    if len(additional_features_dict) > 0:
        img, quantile_list = add_additional_features(img, 
                                                     panel, 
                                                     additional_features_dict = additional_features_dict, 
                                                     sigma = sigma,
                                                     quantile = quantile)

    ## now iterate through the image, blurring & flattening
    for i, ii in enumerate(img):
        if i <= len(additional_features_dict):
            ii = gaussian_blur_image(ii, sigma)  
            img[i] = ii

    ## do the quantile divisions -- added features are divided by 1 to leave unchanged
    if quantile_avg.shape[0] != img.shape[0]:   ## this means additional features have been added
        new_quantiles_avg = np.append(quantile_avg, np.array(quantile_list), axis = 0)
        img = (img.T / new_quantiles_avg).T
    else:
        img = (img.T / quantile_avg).T
    
    img_flat = img.reshape([img.shape[0],(img.shape[1]*img.shape[2])])
    img_flat = np.apply_along_axis(_min_max_normalize, axis = 0, arr = img_flat)
    img = img_flat.reshape([img.shape[0],img.shape[1],img.shape[2]]).T
    counter = 0
    classification_array = np.zeros([img.shape[0],img.shape[1]])
    for i in img: 
        row_classification = flowsom_dictionary['fs'].model.predict(i)
        classification_array[counter] = row_classification + 1  
                                            ## The plus one above is reestablishing 1-indexing for the classes (0 is a special number for images)
                                            ## also, not doing this at this step messes up the smoothing f(x) in the next few lines
        counter += 1

    if smoothing != 0:
        classification_array = smooth_isolated_pixels(classification_array, 
                                                      flowsom_dictionary['number_of_classes'], 
                                                      threshold = smoothing, 
                                                      search_radius = 1, 
                                                      mode_mode = "original_image")
    if suppress_zero_division_warnings:
        warnings.filterwarnings("default", message = "invalid value encountered in divide")
    return classification_array

### Now, how to use px classification once done....:
def plot_class_centers(flowsom: FlowSOM, 
                       panel: pd.DataFrame,
                       **kwargs) -> tuple[plt.figure, pd.DataFrame]: 
    ''' 
    This plots the heatmap of the centroids of the metaclusters of a flowsom. It is useful to identifying what each 
    metaclustering represents biologically 
    '''
    fs = flowsom.get_cluster_data()
    cluster_data = np.nan_to_num((fs.X.T * np.array(fs.obs['percentages'])).T)
    cluster_data = pd.DataFrame(cluster_data)   ## This is the data on the values of the centroids of each individual cluster
    obs = pd.DataFrame(fs.obs)
    cluster_data["metaclustering"] = list(obs["metaclustering"])   
    cluster_centers = cluster_data.groupby("metaclustering").mean()
    cluster_centers.columns = panel.index
    percentile = [f''' ({np.round(obs.groupby("metaclustering").sum()["percentages"].iloc[i] * 100, 2)})%''' for i in range(0, len(obs.groupby("metaclustering").sum()))]
    cluster_centers.index = (obs.groupby("metaclustering").sum().index + 1).astype('string') + percentile
    try:
        plot = sns.clustermap(cluster_centers, cmap = "coolwarm", linewidths = 0.01, xticklabels = True, **kwargs)
    finally:
        plt.close()
    return plot, cluster_centers    ## in case you want the final dataframe

def plot_pixel_heatmap(pixel_folder, image_folder, channels, panel, silence_division_warnings = False):
    '''
    '''
    if silence_division_warnings is True:
        warnings.filterwarnings("ignore", message = "invalid value encountered in divide")
    slicer = np.array([i in channels for i in panel[panel['keep'] == 1]['name']])
    output_df = pd.DataFrame()
    pixel_files = sorted(os.listdir(pixel_folder))
    image_files = sorted(os.listdir(image_folder))
    to_use_files = [i for i in pixel_files if i in image_files]
    for i in to_use_files:
        pixel_map = tf.imread("".join([pixel_folder, "/", i]))
        temp_df_class = pixel_map.reshape(pixel_map.shape[0]*pixel_map.shape[1])
        image = tf.imread("".join([image_folder, "/", i]))
        ravel_image = image.reshape([image.shape[0], image.shape[1]*image.shape[2]])
        temp_df = pd.DataFrame(ravel_image[slicer].T, columns = channels)  
        temp_df['pixel_class'] = temp_df_class
        temp_df = temp_df[temp_df['pixel_class'] != 0]
        output_df = pd.concat([output_df, temp_df], axis = 0)
            
    main_df = pd.DataFrame()
    for ii,i in enumerate(output_df.groupby("pixel_class", observed = False).apply(_py_mean_quantile_norm, include_groups = False)):
        slice = pd.DataFrame(i, index = channels, columns = [ii + 1])
        main_df = pd.concat([main_df,slice], axis = 1)
    for_heatmap = main_df.T.copy()                             # output_df.groupby('pixel_class').median()
    #for_heatmap = (for_heatmap - for_heatmap.min()) / (for_heatmap.max() - for_heatmap.min())

    fractional_percentages = output_df.groupby('pixel_class').count() / len(output_df)
    percentages = 100 * fractional_percentages

    for_heatmap.index = [str(i) + f' ({str(np.round(j,2))}%)' for i,j in zip(for_heatmap.index, percentages.iloc[:,0])]
    try:
        plot = sns.clustermap(for_heatmap, cmap = "coolwarm", linewidths = 0.01, xticklabels = True)
    finally:
        plt.close()
    if silence_division_warnings is True:
        warnings.filterwarnings("default", message = "invalid value encountered in divide")
    return plot, for_heatmap  


def smooth_folder(input_folder: Union[Path, str], 
                  output_folder: Union[Path, str], 
                  class_num: int, 
                  threshold: int, 
                  search_radius: int,
                  ) -> None:
    '''
    Over an input_folder of pixel classification maps, iterates of the images, "smoothing" the classifications by removing 
    isolated & small regions of pixel classes

    Inputs / Outputs:
        Inputs: 
            read in .tiff files from input_folder (MUST have only tiff files and no subfolders in that directory)

        Outputs: 
            for each .tiff read-in exports a .tiff with the same name to output_folder (if input_folder == output_folder, then files in input_folder at overwritten)
    '''
    input_folder = str(input_folder)
    output_folder = str(output_folder)
    input_file_names = sorted(os.listdir(input_folder))
    for i in input_file_names:
        path_to_file = "".join([input_folder,"/",i])
        class_map = tf.imread(path_to_file)
        smoothed_img = smooth_isolated_pixels(class_map, 
                                              class_num = class_num, 
                                              threshold = threshold, 
                                              search_radius = search_radius)
        tf.imwrite(output_folder + "/" + i, smoothed_img.astype('int32'))


def smooth_isolated_pixels(unsupervised_class_map: np.ndarray[int], 
                           class_num: int, 
                           threshold: int = 3, 
                           search_radius: int = 1, 
                           mode_mode: str = "original_image",
                           fill_in: bool = True,
                           warn = True,
                           ) -> np.ndarray[int]:
    '''
    This function converts isolated pixels (pixels in a contiguous group smaller than the threshold size) to the mode of the neighboring 
    pixels in the search radius.

    Use case: unsupervised pixel classification currently produces a large number of isolated pixels -- lonely pixels of a class with no 
    neighbors of the same class -- which seems non-biological. The intention of this function is remove these small regions and blend them 
    into the surrounding pixels. In this sense, it is like hot-pixel filtering.

    Pipeline: This should be done immediately after pixel classification through a unsupervised FlowSOM classifier, although perhaps it could be used later(?)
                
    Args:
        unsupervised_class_map (numpy array, 2D): 
            the classification map generated by the pixel classifier

        class_num (int): 
            the number of pixel classes, defines the range of classes to iterate through, removing/smoothing isolated 
            pixels of each class in ascending order. Note how the class_num is the actual number, but the classes themselves are 1-indexed

        threshold (int): 
            groups of pixels smaller than this number are considered "isolated" and filtered out -- this is done by the 
            skimage.morphology.remove_small_objects() function, with threshold corresponding to the min_size parameter of that function. 

        search_radius (int): 
            this (+1) corresponds to the connectivity parameter in the skimage.morphology.remove_small_objects() function, 
            and also controls the size of the search radius for finding the mode of the surrounding pixels to smooth out isolated pixels. 
            Radius = 1 corresponds to a 3x3 square for the mode-search portion of the algorithm. If there are only 0's inside the search 
            radius, the function expands the serach radius by one and looks again    

        mode_mode (string): 
            one of "original_image", "dropped_image" -- whether to caculate the mode for filling holes from the original 
            image (this can unfortunately recreate isolated pixel regions, but likely better reflects the underlying situation) or 
            from the dropped image. Overall, both mode_modes create largely similar outputs.

        fill_in (bool):
            If True (default), then the removed pixels have their values filled in by the mode of the surrounding pixels
            Otherwise, the removed pixels are just left as 0's (this is more efficient for processes like EDT maps that don't
            care about the fill-in procedure). 

    Returns:
        (numpy array) the output, smoothed pixel classificaiton array
    '''
    ## First, convert all isolated pixels to zero:
    all_isolated_pixels_removed = np.zeros(unsupervised_class_map.shape)
    zero_number = unsupervised_class_map.max() + 10000
    unsupervised_class_map[unsupervised_class_map == 0] = zero_number    ## added to preserve blank patchs after merging
    for i in range(1, class_num + 1):
        single_class = (unsupervised_class_map == i)
        single_class_isolated_pixels_removed = skimage.morphology.remove_small_objects(single_class, 
                                                                                       min_size = threshold, 
                                                                                       connectivity = (search_radius + 1))
        all_isolated_pixels_removed  = all_isolated_pixels_removed + single_class_isolated_pixels_removed.astype('int')
    all_isolated_pixels_removed = (unsupervised_class_map * all_isolated_pixels_removed).astype('int')

    if not fill_in:
        return all_isolated_pixels_removed
    else:
        ## now use pixel-surroundings to fill in holes
        if mode_mode == "original_image":
            padded_array = np.pad(unsupervised_class_map, search_radius) 
        elif mode_mode == "dropped_image":
            padded_array = np.pad(all_isolated_pixels_removed, search_radius) 
        else:
            raise ValueError("mode_mode argument must either be 'original_image' or 'dropped_image'!")
        
        isolated_removed = np.copy(all_isolated_pixels_removed)
        for i,ii in enumerate(all_isolated_pixels_removed):
            for j,jj in enumerate(ii):
                if jj == 0:                                                                 
                    mode = _find_mode(padded_array, [i,j], search_radius, warn = warn)   
                                    ## do not have to take into account the padding in  [i,j] because of how the find_mode function slices
                    isolated_removed[i,j] = mode

        all_isolated_pixels_removed[all_isolated_pixels_removed == zero_number] = 0 ## added to preserve blank patchs after merging
        return isolated_removed

def _find_mode(padded_array: np.ndarray[int], 
               point: list[int], 
               search_radius: int,
               warn = True,
               ) -> int:
    ''' 
    Helper function for smooth_isolated_pixels(). Find the surrounding non-zero mode of the neighborhood of a point in an image.
    '''
    X = point[0]
    Y = point[1]
    right_X = X + 2*search_radius + 1   ### this slicing is why adjusting for padding is not needed: instead of slicing a square around the actual point
                                        ## it slices from the original (pre-padding) index -- which is one shifted search radius up & left
                                        ## it extends the slice two search radii + 1 from this shifted index -- recreating the square of
                                        ## radius 1*search radius around the original point
    lower_Y = Y + 2*search_radius + 1
    square = padded_array[X:right_X,Y:lower_Y]
    square_values = square[(square != 0)]   
    mode = scipy.stats.mode(square_values)[0]
    try:
        int(mode)     ## this is my awkward way of testing if mode == nan (for some reason using... if mode == np.nan: ...does not work)
    except ValueError:
        if warn:
            print(f"The point at {X},{Y} was surrounded by only zero-points -- expanding search radius!")   
                    ### should only be theoretically possible if mode_mode = "dropped_image" in smooth_isolated_pixels() 
        padded_array = np.pad(padded_array, 1)
        mode = _find_mode(padded_array, point, (search_radius + 1))
    return mode

def segment_class_map_folder(pixel_classifier_directory: Union[Path, str], 
                             output_folder: Union[Path, str], 
                             distance_between_centroids: int = 10, 
                             threshold: int = 5, 
                             to_segment_on: list[int] = [2], 
                             background: int = 1,
                             ) -> None:
    '''
    Takes pixel classification maps and uses edt + watershedding to segment into objects

    Args:
        pixel_classifier_directory (string or Path):  
            The path to the folder of pixel classification maps to derive segmentations from 

        output_folder (string or Path):  
            the path to a folder where the segmentation masks are to be written. 

        distance_between_centroids(integer):
            the minimum distance between centroids for the watershedding. Higher numbers remove the number of centroids and force them to be farther apart, 
            leading to fewer, larger cell segmentations, whereas lower numbers allow very close centroids, leading to smaller, more numerous segmentations. 

        threshold (integer): 
            objects smaller than this threshold (in pixels) will be removed before edt / watershedding. Objects this small could theoretically be segmented, if the 
            watershedding leads to this occurring. However, would have to happen inside a larger region being watershed from multiple points

        to_segment_on (list of integers): 
            The classes to segment on. They will be merged before running, and usually it is recommended that a dedicated supervised pixel classifier that only 
            finds the objects of interest be used (so usually only 1 class to segment on) 

        background (integer): 
            The background class, which is set to zero

    Returns:
        None 
        
    Inputs / Outputs:
        Inputs: 
            reads in all the files in pixel_classifier_directory as .tiff files (MUST NOT have other file types / subfolders)

        Outputs: 
            for each file read-in exports a .tiff file to output_folder
    '''
    pixel_classifier_directory = str(pixel_classifier_directory)
    output_folder = str(output_folder)
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    class_map_names = sorted(os.listdir(pixel_classifier_directory))
    class_maps_paths = ["".join([pixel_classifier_directory,"/",i]) for i in sorted(os.listdir(pixel_classifier_directory))]
    for i, ii in zip(class_map_names, class_maps_paths):
        map = tf.imread(ii)
        map[map == background] = 0
        all_isolated_pixels_removed = np.zeros(map.shape)
        for j in to_segment_on:
            single_class = (map == j)
            single_class_isolated_pixels_removed = skimage.morphology.remove_small_objects(single_class, min_size = threshold)
            all_isolated_pixels_removed  = all_isolated_pixels_removed + single_class_isolated_pixels_removed.astype('int')
        all_isolated_pixels_removed = (map * all_isolated_pixels_removed).astype('int')

        #watershed_map = scipy.ndimage.distance_transform_edt(all_isolated_pixels_removed)

        ## Following code block
        ## heavily based on: https://scikit-image.org/docs/stable/auto_examples/segmentation/plot_watershed.html tutorial / example
        peaks = scipy.ndimage.distance_transform_edt(all_isolated_pixels_removed)    
        peaks = skimage.feature.peak_local_max(peaks, min_distance = distance_between_centroids, labels = all_isolated_pixels_removed)
        markers = np.zeros(all_isolated_pixels_removed.shape)
        for k in tuple([tuple(k) for k in peaks]):
            markers[k] = 1
        markers = scipy.ndimage.label(markers)[0]
        segmentation = skimage.segmentation.watershed(all_isolated_pixels_removed, markers = markers, mask = all_isolated_pixels_removed)

        #segmentation = skimage.segmentation.watershed(-watershed_map, mask = all_isolated_pixels_removed)

        tf.imwrite("".join([output_folder,"/",i]), segmentation.astype('float'))