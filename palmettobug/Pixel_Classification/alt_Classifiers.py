'''
This is an alternative backend for pixel classification steps, intended to use skimage filters / sklearn MLPs instead of opencv ANN_MLP & quapth filters

Why? 
-- qupath filters are complex to explain and rarely used. Why do we need three Hessian options, when we can have just one?
-- some of what sci-kit image can do, the current qupath filters cannot, like true vessel-ness filters (sato/frangi, etc.) or spectral-based filters (butterworth, etc.).
-- Can simplify licensing (although that is already mostly set-up for QuPath) and could remove the potential opencv-with-OpenSSL-lib issue entirely. 
-- The code itself maybe easier to read

Downsides:
-- I expect skimage to run slower than opencv. However, the code itself maybe more efficient in design -- first because I'll be using skimage-optimized filters instead
     of hand-made mimics of QuPath filters, and second because re-writing the code may let me write more efficiently this time around.
-- Switching to this would end compatibility with QuPath classifiers
-- I will also have to write & test a bunch of new code in the first place....
'''
## License / derivation info (commented out to avoid inclusion in API docs)
# like all files in PalmettoBUG, all code is under the GPL-3 license.

## copied from original Classifiers.py file (only self-written functions / no derivation from qupath or opencv in them):
            # plot_pixel_heatmap, smoothing functions (all three), _py_mean_quantile_norm, and _quant & supervised classifier's napari launch / save methods
            # segment_class_map_folder   (heavily based on some of the documentation of scikit-image, enough that I list it in the Other_License_Details.txt file:
                                    # Scikit-image: https://github.com/scikit-image/scikit-image, Copyright: 2009-2022 the scikit-image team, license: BSD-3))

import os
from typing import Union
from pathlib import Path
import json
import warnings

import tifffile as tf
import joblib
import numpy as np 
import pandas as pd 
import skimage as ski 
import scipy
import sklearn
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.neural_network import MLPClassifier as MLP
from flowsom import FlowSOM

import napari

__all__ = []


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

def GaussianFilter(image, sigma):  ## standard gaussian -- only function capable of operating on multi-channels at once
    '''Note: this also scales the image to be between -1 and 1'''
    return ski.filters.gaussian(image, sigma = sigma)

def HessianFilter(image):          ## edge detection
    return ski.filters.hessian(image)

def FrangiFilter(image):
    return ski.filters.frangi(image)

def ButterWorthFilter(image, ratio, high_pass = True):
    return ski.filters.butterworth(image, cutoff_frequency_ratio = ratio, high_pass = high_pass)

def calculate_features(image, channels = {}, feature_list = ['gaussian'], sigmas = [1.0, 5.0, 10.0]):
    ''''''
    length = 0
    if channels == {}:
        for i,ii in enumerate(image):
            i = str(i)
            channels[i] = feature_list
    for i in channels:
        feat = channels[i]
        length += len(feat)
        if 'gaussian' in feat:
            length += len(sigmas) - 1
        if 'butterworth' in feat:
            length += (len(sigmas)*2) - 1
    final_array = np.zeros([length] + list(image[0].shape))
    count = 0
    for i in channels:
        img_slice = image[int(i)]
        features = channels[i]
        if len(features) != 0:
            if 'gaussian' in features:
                for j in sigmas:
                    final_array[count] = GaussianFilter(img_slice, sigma = j)
                    count += 1
            if ('hessian' in features):
                final_array[count] = HessianFilter(img_slice)
                count += 1
            if ('frangi' in features):
                final_array[count] = FrangiFilter(img_slice)
                count += 1
            if ('butterworth' in features):
                for i in sigmas:
                    final_array[count] = ButterWorthFilter(img_slice, ratio = i / 100, high_pass = True)
                    count += 1
                    final_array[count] = ButterWorthFilter(img_slice, ratio = i / 100, high_pass = False)
                    count += 1
    if length != count:
        raise Exception(f'Length ({str(length)}) of expected number of features did not equal count ({str(count)}) of channel features actually derived')
    return final_array, channels

class SupervisedClassifier:
    def __init__(self, directory, name):
        ''''''
        if not os.path.exists(f'{directory}/Pixel_Classification'):
            os.mkdir(f'{directory}/Pixel_Classification')
        self.name = name
        directory = f'{directory}/Pixel_Classification/{name}'
        self.directory = directory
        if not os.path.exists(directory):
            os.mkdir(directory)
        self.output_folder = f"{directory}/classification_maps"
        if not os.path.exists(self.output_folder):
            os.mkdir(self.output_folder)
        self.merged_folder = f"{directory}/merged_classification_maps"
        if not os.path.exists(self.merged_folder):
            os.mkdir(self.merged_folder)
        self.training_folder = f"{directory}/training_labels"
        if not os.path.exists(self.training_folder):
            os.mkdir(self.training_folder)
        self.model = None
        self.model_path = f"{directory}/{name}_model.pkl"
        self.model_info = {}
        self.model_info_path = f"{directory}/{name}_info.json"
        self.classes = {}
        self.channel_names = {}
        self._channels = {}
        self._image_name = None
        self._user_labels = None

    def set_channel_names(self, channel_names_dict):
        ''' This is intended for setting a dictionary corresponding {channel integer numbers : channel antigen names}'''
        self.channel_names = channel_names_dict

    def set_target_classes(self, classes_dict):
        '''for setting a dictionary corrseponding to the names of the target classes { class# : class name }'''
        self.classes = classes_dict

    def write_classifier(self, image_folder, 
                           channel_dictionary = {},
                           sigmas = [1.0, 5.0, 10.0],
                           quantile = 0.999,
                           hidden_layers = [100],
                           learning_rate = 0.001):
        '''Point of this method is to set up the .json that will store the information relevant to the classifier'''
        write_dictionary = {}
        write_dictionary['type'] = 'supervised'
        write_dictionary['image_folder'] = image_folder
        write_dictionary['channels'] = channel_dictionary
        write_dictionary['channel_names'] = self.channel_names
        write_dictionary['classes'] = self.classes
        write_dictionary['sigmas'] = sigmas
        write_dictionary['quantile'] = quantile
        write_dictionary['hidden_layers'] = hidden_layers
        write_dictionary['learning_rate'] = learning_rate
        self.model_info = write_dictionary
        if len(self.classes) > 0:
            class_list = []
            class_no_list = []
            for i in self.classes:
                class_no_list.append(i)
                class_list.append(self.classes[i])
            df = pd.DataFrame()
            df['class'] = class_no_list
            df['labels']  = class_list
            unique_names = list(df["labels"].unique())
            if 'background' not in unique_names:
                unique_names = ['background'] + unique_names
            unique_dict = {ii:(i + 1) for i,ii in enumerate(unique_names)}
            unique_dict['background'] = 0
            df['merging'] = df['labels'].replace(unique_dict)
            df.to_csv(self.directory + "/biological_labels.csv", index = False)
        with open(self.model_info_path, "w") as write_file:
            json.dump(write_dictionary, write_file)
        if self.model is not None:
            joblib.dump(self.model, self.model_path)

    def load_classifier(self):
        ''''''
        with open(self.model_info_path, "r") as read_file:
            self.model_info = json.load(read_file)
        try:
            self.model = joblib.load(self.model_path)
        except sklearn.exceptions.InconsistentVersionWarning:
            print("Version of Scikit-Learn is different than when the pixel classifier model was originally trained! Model not loaded.")

    def launch_Napari(self, 
                         image_path: Union[Path, str], 
                         display_all_channels: bool = False,
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

        labels_path = self.training_folder + "/" + self._image_name   
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

        Args:
            output_folder (str, Path, or None): What folder to write the training labels to (must exist). If None, will use the default location
            for a Pixel Classifier, same as used in the GUI. 
        '''
        if self._image_name is None:
            print('No training labels available to save!')
            return
        if output_folder is None:
            output_folder = self.training_folder
        output_folder = str(output_folder)
        new_labels = self._user_labels.data
        tf.imwrite(output_folder + "/" + self._image_name, new_labels.astype('int32'))  
                    ## labels have the same name as the original image
        print('Training labels written!')
        self._image_name = None
        

    def train(self, image_folder, 
                    training_folder = None, 
                    channel_dictionary = {}, 
                    feature_list = ['gaussian'],         ## only used if channel_dictionary == {}
                    sigmas = [1.0, 5.0, 10.0],
                    quantile = 0.999,
                    hidden_layers = [100],
                    learning_rate = 0.001,
                    from_save = False,
                    auto_predict = False):
        ''''''
        if training_folder is None:
            training_folder = self.training_folder
        if from_save:
            image_folder = self.model_info['image_folder'] = image_folder
            channel_dictionary = self.model_info['channels']
            sigmas = self.model_info['sigmas']
            quantile = self.model_info['quantile'] 
            hidden_layers = self.model_info['hidden_layers'] 
            learning_rate = self.model_info['learning_rate'] 
            #try:                         #### if training from save -- try to reload existing model or always re-train (as in the current implementation)?
            #    self.model = joblib.load(self.model_path)
            #except Exception:
            #    pass
        training_images = [i for i in sorted(os.listdir(training_folder)) if i.lower().rfind('.tif') != -1]
        all_images = [i for i in sorted(os.listdir(image_folder)) if i.lower().rfind('.tif') != -1]
        images = [i for i in training_images if i in all_images]
        if len(images) == 0:
            print('No images to train on!')
            return
        all_pixels = None
        all_labels = None
        for i in images:
            img = tf.imread(f'{image_folder}/{i}').astype('float32')
            trn_img = tf.imread(f'{training_folder}/{i}').astype('int32')
            image_features, self._channels = calculate_features(img, channels = channel_dictionary, feature_list = ['gaussian'], sigmas = sigmas)
            image_features = self.scaled_features(image_features, quantile)
            image_features = np.reshape(image_features, (image_features.shape[0], img.shape[1], img.shape[2]))
            if all_pixels is None:
                all_pixels = np.zeros([image_features.shape[0],1])
                all_labels = np.zeros([1])
            all_pixels = np.concatenate((all_pixels, image_features[:,trn_img > 0]), axis = 1)
            all_labels = np.concatenate((all_labels, trn_img[trn_img > 0]), axis = 0)
        all_pixels = all_pixels[:, 1:]
        all_labels = all_labels[1:]
        self.model = MLP(hidden_layer_sizes = hidden_layers, learning_rate_init = learning_rate, early_stopping = True)
        self.model.fit(all_pixels.T, all_labels)  
        self.write_classifier(image_folder, self._channels, quantile = quantile)
        if auto_predict:
            self.predict(image_folder, output_folder = self.output_folder, filenames = None)

    def predict(self, image_folder, output_folder = None, filenames = None):
        ''''''
        if output_folder is None:
            output_folder = self.output_folder
        channel_dictionary = self.model_info['channels']
        sigmas = self.model_info['sigmas']
        quantile = self.model_info['quantile']

        def predict_image(filename):
             img = tf.imread(f'{image_folder}/{filename}').astype('float32')
             image_features, _ = calculate_features(img, channels = channel_dictionary, sigmas = sigmas)
             image_features = self.scaled_features(image_features, quantile)
             prediction = self.model.predict(image_features.T)
             prediction = np.reshape(prediction, [img.shape[1], img.shape[2]])
             tf.imwrite(f'{output_folder}/{filename}', prediction.astype('int32'))
             
        if filenames is None:
            images = [i for i in sorted(os.listdir(image_folder)) if i.lower().rfind(".tif") != -1]
            for filename in images:
                predict_image(filename)
        elif isinstance(filenames, list):
            for filename in filenames:
                predict_image(filename)
        elif isinstance(filenames, str):
            predict_image(filename)
        else:
            raise(ValueError, "Filenames parameter must be a str, list, or None")

    def scaled_features(self, array, quantile):
        '''Quantile scales within channels, then min-max channels across channels'''
        new_shape = (array.shape[0], array.shape[1]*array.shape[2])    ## reshape to remove X,Y dimensions but preserve channels
        array = np.reshape(array, new_shape)
        ## Here I do a more simplistic quantile scaling -- I only scale by the sampled pixels
        array = (array - array.min(axis = 0)) / (np.quantile(array, quantile, axis = 0) - array.min(axis = 0))
        array[np.isnan(array)] = 0
        array[array > 1] = 1
        return array
        
class UnsupervisedClassifier:
    def __init__(self, directory, name):
        ''''''
        if not os.path.exists(f'{directory}/Pixel_Classification'):
            os.mkdir(f'{directory}/Pixel_Classification')
        self.name = name
        directory = f'{directory}/Pixel_Classification/{name}'
        self.directory = directory
        if not os.path.exists(directory):
            os.mkdir(directory)
        self.output_folder = f"{directory}/classification_maps"
        if not os.path.exists(self.output_folder):
            os.mkdir(self.output_folder)
        self.merged_folder = f"{directory}/merged_classification_maps"
        if not os.path.exists(self.merged_folder):
            os.mkdir(self.merged_folder)
        self.model = None
        self.model_path = f"{directory}/{name}_model.pkl"
        self.model_info = {}
        self.model_info_path = f"{directory}/{name}_info.json"
        self.classes = {}
        self.channel_names = {}
        self._channels = {}

    def set_class_names(self, class_names_dict):
        ''' This is intended for setting a dictionary corresponding {channel integer numbers : channel antigen names}'''
        self.classes = class_names_dict

    def set_channel_names(self, channel_names_dict):
        ''' This is intended for setting a dictionary corresponding {channel integer numbers : channel antigen names}'''
        self.channel_names = channel_names_dict

    def write_classifier(self, image_folder, 
                         channel_dictionary = {}, 
                         sigmas = [1.0, 5.0, 10.0],
                         pixel_number = 250000, 
                         quantile = 0.999,
                         XYdim = 10,
                         metaclusters = 15,
                         training_cycles = 50,
                         smoothing = 0,
                         seed = 42):
        '''Point of this method is to set up the .json that will store the information relevant to the classifier'''
        write_dictionary = {}
        write_dictionary['type'] = 'unsupervised'
        write_dictionary['image_folder'] = image_folder
        write_dictionary['channels'] = channel_dictionary
        write_dictionary['channel_names'] = self.channel_names
        write_dictionary['classes'] = self.classes
        write_dictionary['sigmas'] = sigmas
        write_dictionary['pixel_number'] = pixel_number
        write_dictionary['quantile'] = quantile
        write_dictionary['XYdim'] = XYdim
        write_dictionary['metaclusters'] = metaclusters
        write_dictionary['training_cycles'] = training_cycles
        write_dictionary['smoothing'] = smoothing
        write_dictionary['seed'] = seed
        if len(self.classes) > 0:
            class_list = []
            class_no_list = []
            for i in self.classes:
                class_no_list.append(i)
                class_list.append(self.classes[i])
            df = pd.DataFrame()
            df['class'] = class_no_list
            df['labels']  = class_list
            unique_names = list(df["labels"].unique())
            if 'background' not in unique_names:
                unique_names = ['background'] + unique_names
            unique_dict = {ii:(i + 1) for i,ii in enumerate(unique_names)}
            unique_dict['background'] = 0
            df['merging'] = df['labels'].replace(unique_dict)
            df.to_csv(self.directory + "/biological_labels.csv", index = False)
        self.model_info = write_dictionary
        with open(self.model_info_path, "w") as write_file:
            json.dump(write_dictionary, write_file)

        joblib.dump(self.model, self.model_path)

    def load_classifier(self):
        ''''''
        with open(self.model_info_path, "r") as read_file:
            self.model_info = json.load(read_file)
        try:
            self.model = joblib.load(self.model_path)
        except sklearn.exceptions.InconsistentVersionWarning:
            print("Version of Scikit-Learn is different than when the pixel classifier model was originally trained! Model not loaded.")

    def train(self, image_folder, 
                    pixel_number = 250000, 
                    quantile = 0.999,
                    channel_dictionary = {}, 
                    feature_list = ['gaussian'],         ## only used if channel_dictionary == {}, all channels will be used with the listed feature filters
                    sigmas = [1.0, 5.0, 10.0],
                    XYdim = 10,
                    metaclusters = 15,
                    training_cycles = 50,
                    smoothing = 0,
                    seed = 42,
                    from_save = False,
                    auto_predict = False):
        ''''''
        if from_save:
            image_folder = self.model_info['image_folder']
            channel_dictionary = self.model_info['channels']
            sigmas = self.model_info['sigmas']
            pixel_number = self.model_info['pixel_number']
            quantile = self.model_info['quantile']
            XYdim = self.model_info['XYdim']
            metaclusters = self.model_info['metaclusters']
            training_cycles = self.model_info['training_cycles']
            seed = self.model_info['seed']
        gen = np.random.default_rng(seed)
        images = [i for i in sorted(os.listdir(image_folder)) if i.lower().rfind('.tif') != -1]
        if len(images) == 0:
            print('No images to train on!')
            return
        all_pixels = None
        pixels_per_image = pixel_number // len(images)
        for i in images:
            img = tf.imread(f'{image_folder}/{i}').astype('float32')
            image_features, self._channels = calculate_features(img, channels = channel_dictionary, feature_list = feature_list, sigmas = sigmas)
            ## Here I do a simplified scaling on a per-image basis (instead of the wholedataset at once)
            image_features = self.scaled_features(image_features, quantile)
            sample = gen.choice(image_features, pixels_per_image, replace = False, axis = 1, shuffle = False)
            if all_pixels is None:
                all_pixels = np.zeros([sample.shape[0],1])
            all_pixels = np.concatenate((all_pixels, sample), axis = 1)
        all_pixels = all_pixels[:,1:]
        self.model = FlowSOM(all_pixels.T, n_clusters = metaclusters, xdim = XYdim, ydim = XYdim, rlen = training_cycles, seed = seed).model
        if (self.classes is None) or (len(self.classes) != metaclusters):
            self.classes = {i+1:'unassigned' for i in range(0,metaclusters)}
        if not from_save:  ## no need to rewrite if from saved model
            self.write_classifier(image_folder, self._channels, sigmas = sigmas, pixel_number = pixel_number, 
                         quantile = quantile,
                         XYdim = XYdim,
                         metaclusters = metaclusters,
                         training_cycles = training_cycles,
                         smoothing = smoothing,
                         seed = seed)
        if auto_predict:
            self.predict(image_folder, output_folder = self.output_folder, filenames = None)

    def predict(self, image_folder, output_folder = None, filenames = None):
        ''''''
        if output_folder is None:
            output_folder = self.output_folder
        channel_dictionary = self.model_info['channels']
        smoothing = self.model_info['smoothing']
        metaclusters = self.model_info['metaclusters']
        quantile = self.model_info['quantile']
        sigmas = self.model_info['sigmas']
         
        def predict_image(filename):
             img = tf.imread(f'{image_folder}/{filename}').astype('float32')
             image_features, _ = calculate_features(img, channels = channel_dictionary, sigmas = sigmas)
             shape_image_features = self.scaled_features(image_features, quantile)
             prediction = self.model.predict(shape_image_features.T).T + 1
             prediction = np.reshape(prediction, [image_features.shape[1], image_features.shape[2]])
             if smoothing > 0:
                  prediction = smooth_isolated_pixels(prediction, metaclusters, smoothing)
             tf.imwrite(f'{output_folder}/{filename}', prediction.astype('int32'))
             
        if filenames is None:
            images = [i for i in sorted(os.listdir(image_folder)) if i.lower().rfind(".tif") != -1]
            for filename in images:
                predict_image(filename)
        elif isinstance(filenames, list):
            for filename in filenames:
                predict_image(filename)
        elif isinstance(filenames, str):
            predict_image(filename)
        else:
            raise(ValueError, "Filenames parameter must be a str, list, or None")

    def scaled_features(self, array, quantile):
        '''Quantile scales within channels, then min-max channels across channels'''
        new_shape = (array.shape[0], array.shape[1]*array.shape[2])    ## reshape to remove X,Y dimensions but preserve channels
        array = np.reshape(array, new_shape)
        ## Here I do a more simplistic quantile scaling -- I only scale by the sampled pixels
        array = (array - array.min(axis = 0)) / (np.quantile(array, quantile, axis = 0) - array.min(axis = 0))
        array[np.isnan(array)] = 0
        array[array > 1] = 1
        return array

def plot_pixel_heatmap(pixel_folder: Union[str, Path],
                       image_folder: Union[str, Path], 
                       channels: list[str], 
                       panel: pd.DataFrame, 
                       silence_division_warnings = False) -> tuple[plt.figure, pd.DataFrame]:
    '''
    This plots a heatmap derived from the actual data of the pixel class regions predicted by a classifier (unlike plot_class_centers, which uses the training centroids).
    Specifically, it shows the mean of 1%-99% quantile scaled data for each channel in each pixel class.

    Args:
        pixel_folder (str, Path):
            The folder of predictions from a pixel classifier

        image_folder (str, Path):
            The folder of images that the channels intensities will be read from to construct the heatmap. Only files present in BOTH pixel_folder & image_folder
            will be used.

        channels (iterable of strings):
            The names of the antigens to use in the panel. Will be matched against the antigens in panel, and then used to slice the images to only the channels of interest.
            These antigen names are also what will be displayed on the heatmap axes.

        panel (pd.DataFrame):
            The panel file (panel.csv) of the PalmettoBUG project in question. Specifically, panel['keep'] == 0 channels are removed, and then the antigen names in channels
            are matched against the antigen names in panel['name'] to slice the images to only the channels of interest. 

        silence_division_warnings (bool):
            One of the steps of this function involves a lot of division where zero-division / related errors can occur. 
            Will silence these warnings if this parameter == True

    Returns:
        a matplotlib figure and a pandas dataframe containing the values displayed in the plot

    '''
    pixel_folder = str(pixel_folder)
    image_folder = str(image_folder)
    if silence_division_warnings is True:
        warnings.filterwarnings("ignore", message = "invalid value encountered in divide")
    slicer = np.array([i in channels for i in panel[panel['keep'] == 1]['name']])
    output_df = pd.DataFrame()
    pixel_files = [i for i in sorted(os.listdir(pixel_folder)) if i.lower().find(".tif") != -1]
    image_files = [i for i in sorted(os.listdir(image_folder)) if i.lower().find(".tif") != -1]
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
    input_file_names = [i for i in sorted(os.listdir(input_folder)) if i.lower().find(".tif") != -1]
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
        single_class_isolated_pixels_removed = ski.morphology.remove_small_objects(single_class, 
                                                                                       min_size = threshold, 
                                                                                       connectivity = (search_radius + 1))
        all_isolated_pixels_removed  = all_isolated_pixels_removed + single_class_isolated_pixels_removed.astype('int')
    all_isolated_pixels_removed = (unsupervised_class_map * all_isolated_pixels_removed).astype('int')

    if not fill_in:
        all_isolated_pixels_removed[all_isolated_pixels_removed == zero_number] = 0 ## added to preserve blank patchs after merging
        return all_isolated_pixels_removed
    else:
        ## now use pixel-surroundings to fill in holes
        if mode_mode == "original_image":
            padded_array = np.pad(unsupervised_class_map, search_radius) 
        elif mode_mode == "dropped_image":
            padded_array = np.pad(all_isolated_pixels_removed, search_radius) 
        else:
            raise ValueError("mode_mode argument must either be 'original_image' or 'dropped_image'!")
        
        for i,ii in enumerate(all_isolated_pixels_removed):
            for j,jj in enumerate(ii):
                if jj == 0:                                                                 
                    mode = _find_mode(padded_array, [i,j], search_radius, warn = warn)   
                                    ## do not have to take into account the padding in  [i,j] because of how the find_mode function slices
                    all_isolated_pixels_removed[i,j] = mode

        all_isolated_pixels_removed[all_isolated_pixels_removed == zero_number] = 0 ## added to preserve blank patchs after merging
        return all_isolated_pixels_removed

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
            The background class, which wil be set to zero

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
    class_map_names = [i for i in sorted(os.listdir(pixel_classifier_directory)) if i.lower().find(".tif") != -1]
    class_maps_paths = ["".join([pixel_classifier_directory,"/",i]) for i in sorted(os.listdir(pixel_classifier_directory)) if i.lower().find(".tif") != -1]
    for i, ii in zip(class_map_names, class_maps_paths):
        map = tf.imread(ii)
        map[map == background] = 0
        all_isolated_pixels_removed = np.zeros(map.shape)
        for j in to_segment_on:
            single_class = (map == j)
            single_class_isolated_pixels_removed = ski.morphology.remove_small_objects(single_class, min_size = threshold)
            all_isolated_pixels_removed  = all_isolated_pixels_removed + single_class_isolated_pixels_removed.astype('int')
        all_isolated_pixels_removed = (map * all_isolated_pixels_removed).astype('int')

        #watershed_map = scipy.ndimage.distance_transform_edt(all_isolated_pixels_removed)

        ## Following code block
        ## heavily based on: https://scikit-image.org/docs/stable/auto_examples/segmentation/plot_watershed.html tutorial / example
        peaks = scipy.ndimage.distance_transform_edt(all_isolated_pixels_removed)    
        peaks = ski.feature.peak_local_max(peaks, min_distance = distance_between_centroids, labels = all_isolated_pixels_removed)
        markers = np.zeros(all_isolated_pixels_removed.shape)
        for k in tuple([tuple(k) for k in peaks]):
            markers[k] = 1
        markers = scipy.ndimage.label(markers)[0]
        segmentation = ski.segmentation.watershed(all_isolated_pixels_removed, markers = markers, mask = all_isolated_pixels_removed)

        #segmentation = ski.segmentation.watershed(-watershed_map, mask = all_isolated_pixels_removed)

        tf.imwrite("".join([output_folder,"/",i]), segmentation.astype('float'))
