'''
This module handles the widgets / front-end of the first hald of the third tab (pixel classification) of the program. This is the part
of the program where pixel classifiers can be created, trained, and used to predict pixel classifications for images.



This file is licensed under the GPL3 license. No significant portion of the code here is known to be derived from another project 
(in the sense of needing to be separately / simulataneously licensed)
'''

## directly copied from Classifiers_GUI.py and then edited

import os
from typing import Union
import shutil
import json
import tkinter as tk
from multiprocessing import Process

import customtkinter as ctk
import pandas as pd
import numpy as np
import tifffile as tf
import matplotlib.pyplot as plt 

from .alt_Classifiers import (SupervisedClassifier, 
                          UnsupervisedClassifier, 
                          plot_pixel_heatmap, 
                          segment_class_map_folder)

from .use_classifiers import merge_folder

from ..Utils.sharedClasses import (DirectoryDisplay, 
                                   CtkSingletonWindow, 
                                   Project_logger, 
                                   TableLaunch, 
                                   run_napari, 
                                   warning_window, 
                                   overwrite_approval, 
                                   display_image_button)

pd.set_option('future.no_silent_downcasting', True)

__all__ = []

PALMETTO_BUG_homedir = __file__.replace("\\","/")
PALMETTO_BUG_homedir = PALMETTO_BUG_homedir[:(PALMETTO_BUG_homedir.rfind("/"))]
## do it twice to get up to the top level directory:
PALMETTO_BUG_homedir = PALMETTO_BUG_homedir[:(PALMETTO_BUG_homedir.rfind("/"))]
PALMETTO_BUG_assets_classifier_folder = PALMETTO_BUG_homedir + '/Assets/Px_classifiers'


class Pixel_class_widgets(ctk.CTkFrame):

    def __init__(self, master):   
        super().__init__(master)
        self.master = master
        self.name = None

    def set_directory(self, dir_object: str) -> None:
        self.main_directory = dir_object.main
        self.classifier_dir = dir_object.px_classifiers_dir
        self.image_directory = dir_object.img_dir
        # self.supervised = SupervisedClassifier(directory)
        self.classifier_type = None   ## to be --> "supervised" or "unsupervised"

        global pixel_logger
        pixel_logger = Project_logger(dir_object.main).return_log()
        try:   ## clear old widgets, if there
            self.start_frame.destroy()    
            self.dir_display.destroy()
            self.Napari_frame.destroy()
            self.quick_display.destroy()
            self.predictions_frame.destroy()
            self.segment_frame.destroy()
        except Exception:
            pass

        self.name_holder = ctk.StringVar(value = self.name)
        self.start_frame = self.classifier_frame(self)
        self.start_frame.grid(column = 0, row = 0, padx = 3, pady = 3, rowspan = 2)

        self.dir_display = quick_option_dir_disp(self, self.image_directory)
        self.dir_display.grid(row = 6, column = 3, padx = 3, pady = 3)

        self.Napari_frame = self.Napari_Label_generation_frame(self)
        self.Napari_frame.grid(row = 0, column = 1, padx = 5, pady = 5, rowspan = 2)

        label_quick_display = ctk.CTkLabel(master = self, text = "Quick Display of Masks")
        label_quick_display.grid(row = 0, column = 3, padx = 5, pady = 5)

        self.quick_display = display_image_button(self, PALMETTO_BUG_homedir + "/Assets/Capture2.png")
        self.quick_display.grid(row = 1, rowspan = 5,  column = 3, padx = 3, pady = 3)

        self.dir_display.setup_with_dir(self.main_directory, delete_remove = True, png = self.quick_display)

        self.predictions_frame = self.prediction_frame(self)
        self.predictions_frame.grid(row = 3, column = 0, padx = 5, pady = 5)

        self.segment_frame = self.segmentation_frame(self)     
        self.segment_frame.grid(row = 3, column = 1, padx = 5, pady = 5)

    def detail_display(self) -> None:
        if self.name is None:
            tk.messagebox.showwarning("No Classifier Loaded!", message = "No Classifier Loaded!")
            return
        detail_display_window(self)

    def bio_label_launch(self) -> None:
        if self.name is None:
            tk.messagebox.showwarning("No Classifier Loaded!", message = "No Classifier Loaded!")
            return
        bio_label_launch_window(self)

    def save_classifier(self) -> None:
        '''
        '''
        if self.name is None:
            tk.messagebox.showwarning("No Classifier Available to Save!", message = "No Classifier Available to Save!")
            return
    
        ## this code is just a reverse of the load option:
        new_dir = PALMETTO_BUG_assets_classifier_folder + f"/{self.name}"
        if not os.path.exists(PALMETTO_BUG_assets_classifier_folder):
            os.mkdir(PALMETTO_BUG_assets_classifier_folder)
        assets_path = new_dir + f"/{self.name}_model.pkl"
        details_path = new_dir + f"/{self.name}_info.json"
        destination = self.classifier_dir + f"/{self.name}/"
        if not os.path.exists(new_dir):
            os.mkdir(new_dir)
        ## shutil copy over the classifier dictionaries to assets:
        shutil.copyfile((destination + f"{self.name}_model.pkl"), assets_path)
        shutil.copyfile((destination + f"{self.name}_info.json"), details_path)
        pixel_logger.info(f"Saved classifier {self.name} to PalmettoBUG assets")

    def training(self, image_folder: str) -> None:
        if image_folder == "":
            tk.messagebox.showwarning("Warning!", message = "You must select a folder of images in the training folder before training!"
                                                            "\nThis will be the same folder drop-down you use when launching in Napari"
                                                            "\nfor label generation.")
            return
        image_folder = f"{self.image_directory}/{image_folder}"
        images = [i for i in os.listdir(image_folder) if i.lower().find(".tif") != -1]
        if len(images) == 0:
            tk.messagebox.showwarning("Warning!", message = "The are no saved label images in the training folder of the classifier!")
            return
        self.supervised.train(image_folder = image_folder, from_save = True)    
        pixel_logger.info(f"Trained supervised classifier {self.name} on image folder = {image_folder}")
        warning_window("Training Finished!")

    def predict(self, prediction_type: str) -> None:
        if self.classifier_type == "supervised":
            if prediction_type == "one":
                success = self.predict_one_image_fx()
            elif prediction_type == "all":
                success = self.predict_folder()

        elif self.classifier_type == "unsupervised":
            if prediction_type == "one":
                success = self.run_one_unsupervised()
            elif prediction_type == "all":
                success = self.run_all_unsupervised()
        else:
            tk.messagebox.showwarning("No Classifier Available!", message = "No Classifier Available!")
            return
        if success:
            warning_window("Prediction Finished!")

    def predict_one_image_fx(self) -> None:
        image_folder_choice = self.predictions_frame.folder.get()
        if image_folder_choice == "":
            tk.messagebox.showwarning("No Image folder selected!", message = "Please select a folder to predict pixel classes from!")
            return False
        
        image_name = self.predictions_frame.one_img.get()
        if image_name == "":
            tk.messagebox.showwarning("No Image selected!", message = "Please select the image to predict pixel classes for!")
            return False
    
        image_folder_name = self.image_directory + "/" + image_folder_choice
        if not overwrite_approval(self.supervised.directory + "/classification_maps/" + image_name, file_or_folder = "file"):
            return False
        self.supervised.predict(image_folder_name, filenames = image_name)
        merge_folder(self.supervised.output_folder,
                     pd.read_csv(self.supervised.directory + "/biological_labels.csv"),
                    self.supervised.directory + "/merged_classification_maps")
        pixel_logger.info(f"Predicted classification map for following image: {image_folder_name + '/'  + image_name}")

    def predict_folder(self) -> None:
        image_folder_choice = self.predictions_frame.folder.get()
        if image_folder_choice == "":
            tk.messagebox.showwarning("No Image folder selected!", message = "Please select a folder to predict pixel classes from!")
            return False
        image_folder_name = self.image_directory + "/" + image_folder_choice
        if not overwrite_approval(self.supervised.directory + "/classification_maps", file_or_folder = "folder", custom_message = "Are you sure you want to potentially overwrite files in this folder"
                                  "and the associated /merged_classification_maps folder?"):
            return False
        self.supervised.predict(image_folder_name)
        merge_folder(self.supervised.output_folder, 
                     pd.read_csv(self.supervised.directory + "/biological_labels.csv"),
                    self.supervised.directory + "/merged_classification_maps")
        pixel_logger.info(f"Predicted classification map for following image folder: {image_folder_name}")

    def run_one_unsupervised(self) -> None:
        image_folder_choice = self.predictions_frame.folder.get()
        if image_folder_choice == "":
            tk.messagebox.showwarning("No Image folder selected!", message = "Please select a folder to predict pixel classes from!")
            return False
        
        image_name = self.predictions_frame.one_img.get()
        if image_name == "":
            tk.messagebox.showwarning("No Image selected!", message = "Please select the image to predict pixel classes for!")
            return False
        image_folder_name = self.image_directory + "/" + image_folder_choice
        if not overwrite_approval(self.unsupervised.directory + "/classification_maps/" + image_name, file_or_folder = "file"):
            return False
        self.unsupervised.predict(image_folder_name, filenames = image_name)
        merge_folder(self.unsupervised.output_folder, 
                    pd.read_csv(self.unsupervised.directory + "/biological_labels.csv"),
                    self.unsupervised.directory + "/merged_classification_maps")
        pixel_logger.info(f"Predicted classification map for following image: {image_folder_name + '/'  + image_name}")

    def run_all_unsupervised(self) -> None:
        image_folder_choice = self.predictions_frame.folder.get()
        if image_folder_choice == "":
            tk.messagebox.showwarning("No Image folder selected!", message = "Please select a folder to predict pixel classes from!")
            return False
        image_folder_name = self.image_directory + "/" + image_folder_choice
        if not overwrite_approval(self.unsupervised.directory + "/classification_maps/", file_or_folder = "folder"):
            return False
        self.unsupervised.predict(image_folder_name)
        merge_folder(self.unsupervised.output_folder, 
                    pd.read_csv(self.unsupervised.directory + "/biological_labels.csv"),
                    self.unsupervised.directory + "/merged_classification_maps")
        self.plot_pixel_heatmap(self.unsupervised.output_folder, image_folder_name, from_button = False)
        pixel_logger.info(f"Predicted classification map for following image folder: {image_folder_name}")

    def plot_pixel_heatmap(self, classifier_folder = None, image_folder = None, from_button = True):
        ''''''
        if classifier_folder is None:
            classifier_folder = self.classifier_dir + "/" + self.name + "/classification_maps"
        if self.name is None:
            tk.messagebox.showwarning("No Classifier Loaded!", message = "No Classifier Available to Plot Heatmap from!")
            return
        filepath = self.classifier_dir + "/" + self.name + "/cluster_heatmap.png"
        if from_button:
            if not overwrite_approval(filepath, file_or_folder = "file"):
                return
        
        panel = pd.read_csv(self.main_directory + "/panel.csv")
        open_json = open(self.classifier_dir + f"/{self.name}/{self.name}_info.json", 'r' , encoding="utf-8")
        loaded_json = open_json.read()
        loaded_json = json.loads(loaded_json) 
        open_json.close()
        channels = []
        for i in loaded_json['channels']:
            for j in loaded_json['channels'][i]:
                if j == "gaussian":
                    channels.append(f'{loaded_json["channel_names"][i]}')
        if image_folder is None:
            image_folder = loaded_json['image_folder']
        #print(channels, panel)
        plot, _ = plot_pixel_heatmap(classifier_folder, image_folder, channels = channels,
                                                    panel = panel, silence_division_warnings = True)
        plot.savefig(filepath)
        plt.close(fig = 'all')
        pixel_logger.info(f"Plotted heatmap from pixel class prediction for {self.name}")
        self.quick_display.save_and_display(filepath)
    
    def launch_loading_window(self) -> None:
        loading_window(self)

    class classifier_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            label = ctk.CTkLabel(master = self, text = "Name of the Currently Loaded Classifier:")
            label.grid(row = 0, column = 0, padx = 5, pady = 5, columnspan = 2)

            self.name_display = ctk.CTkEntry(master = self, textvariable = self.master.name_holder)
            self.name_display.grid(row = 1, column = 0, padx = 5, pady = 5, columnspan = 2)

            self.start = ctk.CTkButton(master = self, 
                                       text = "Create, Load, or Overwrite a Pixel Classifier", 
                                       command = self.master.launch_loading_window)
            self.start.grid(row = 2, column = 0, padx = 5, pady = 5, columnspan = 2)

            label2 = ctk.CTkLabel(master = self, text = "")
            label2.grid(row = 3, column = 0, padx = 5, pady = 5, columnspan = 2)

            self.display_classifier_details = ctk.CTkButton(master = self, 
                                                            text = "Display Classifier Details", 
                                                            command = self.master.detail_display)
            self.display_classifier_details.grid(row = 6, column = 0, padx = 5, pady = 5)

            self.make_class_biology_table = ctk.CTkButton(master = self, 
                                                          text = "Define Biological Class Labels", 
                                                          command = self.master.bio_label_launch)
            self.make_class_biology_table.grid(row = 6, column = 1, padx = 5, pady = 5)

            def refresh_exclusive_buttons(enter = ""):
                ''''''
                if self.save_current_classifier_to_assets.cget("state") == "disabled":
                    self.save_current_classifier_to_assets.configure(state = "normal")
                if self.pixel_heatmap.cget("state") == "disabled":
                    self.pixel_heatmap.configure(state = "normal")


            self.save_current_classifier_to_assets = ctk.CTkButton(master = self, 
                                                        text = "Save current classifier \n to PalmettoBUG Assets", 
                                                        command = self.master.save_classifier,
                                                        state = "disabled")
            self.save_current_classifier_to_assets.grid(row = 4, column = 0, columnspan = 2, padx = 5, pady = 5)
            self.save_current_classifier_to_assets.bind("<Enter>", refresh_exclusive_buttons)

            self.pixel_heatmap = ctk.CTkButton(master = self, 
                                                        text = "Make heatmap from \n previously completed predictions", 
                                                        command = self.master.plot_pixel_heatmap,
                                                        state = "disabled")
            self.pixel_heatmap.grid(row = 5, column = 0, columnspan = 2, padx = 5, pady = 5)
            self.pixel_heatmap.bind("<Enter>", refresh_exclusive_buttons)

    class Napari_Label_generation_frame(ctk.CTkFrame):

        def __init__(self, master):
            super().__init__(master)
            self.master = master
            self.labels_done = False

            self.image_directory = self.master.image_directory

            grand_label = ctk.CTkLabel(master = self, text = "Create Training Labels in Napari \n for Supervised Classifier:")
            grand_label.grid(row = 0, column = 0, padx = 5, pady = 5)

            label1 = ctk.CTkLabel(master = self, text = "Select an image Folder:")
            label1.grid(row = 1, column = 0, padx = 5, pady = 5)

            def refresh1():
                image_list = [i for i in sorted(os.listdir(self.image_directory)) if i.find(".") == -1]
                self.choose_folder.configure(values = image_list)

            self.choose_folder = ctk.CTkOptionMenu(self, values = [""], variable = ctk.StringVar(value = ""), command = self.update_folder)
            self.choose_folder.grid(row = 2, column = 0, padx = 5, pady = 5)
            self.choose_folder.bind("<Enter>", lambda enter: refresh1())

            label2 = ctk.CTkLabel(master = self, text = "Select an image to create labels for:")
            label2.grid(row = 3, column = 0, padx = 5, pady = 5)

            image_list = [""]

            self.choose_an_image = ctk.CTkOptionMenu(self, values = image_list, variable = ctk.StringVar(value = ""))
            self.choose_an_image.grid(row = 4, column = 0, padx = 5, pady = 5)

            button1 = ctk.CTkButton(master = self, 
                                    text = "Launch Selected Image in Napari", 
                                    command = lambda: self.launch_Napari(self.choose_an_image.get()))
            button1.grid(column = 1, row = 4, padx = 5, pady = 5)

            spacer = ctk.CTkLabel(master = self, text = "")
            spacer.grid(column = 0, row = 5, columnspan = 2, padx = 5, pady = 5)

            self.button2 = ctk.CTkButton(master = self, text = "Save Labels from Napari", command = self.accept_Napari_labeling, state = "disabled")
            self.button2.grid(column = 0, row = 6, padx = 5, pady = 5)

            self.button3 = ctk.CTkButton(master = self, text = "Discard last set of Napari Labels", command = self.discard_labels, state = "disabled")
            self.button3.grid(column = 1, row = 6, padx = 5, pady = 5)

            label2 = ctk.CTkLabel(master = self, 
                text = "A new Napari window cannot be launched unless \n the labels from the previous image have been saved or discarded")
            label2.grid(column = 0, row = 7, columnspan = 2, padx = 5, pady = 5)

            self.training_button = ctk.CTkButton(master = self, 
                                        text = "Train Classifier on Generated Labels", 
                                        command = lambda: self.master.training(image_folder = self.choose_folder.get()))
            self.training_button.grid(row = 8, column = 0, padx = 5, pady = 5)

            if self.master.name is None:
                self.disable_buttons()

        def update_folder(self, image_folder: str) -> None:
            def refresh2():
                try:       
                        ## try / except here because of the tendency of many errors to be generated by refreshers like these 
                        # before a classifier is loaded
                    image_list = [i for i in sorted(os.listdir(self.image_directory + "/" + image_folder)) if i.lower().find(".tif") != -1]
                    self.choose_an_image.configure(values = image_list)
                except Exception:
                    pass
            refresh2()
            self.choose_an_image.bind("<Enter>", lambda enter: refresh2())

        def activate_buttons(self) -> None:
            ##### Saving training labels should fail until an pixel classifier name is saved 
            #       --> block at least the save buttons until the user creates the classifier name
            self.labels_done = False
            if self.master.name is not None:
                for i in self.children:
                    child = self.children[i]
                    try:
                        child.configure(state = "normal")
                    except Exception:
                        pass
            self.button2.configure(state = "disabled")
            self.button3.configure(state = "disabled")

        def disable_buttons(self) -> None:
            for i in self.children:
                child = self.children[i]
                try:
                    child.configure(state = "disabled")
                except Exception:
                    pass

        #### These functions deal with the generation of Napari labels by the user:
        def launch_Napari(self, image_name: str, display_all_channels: bool = False) -> None:
            image_folder = self.choose_folder.get()
            if (image_name == "") or (image_folder == ""):
                tk.messagebox.showwarning("Napari Warning!", 
                    message = "You must select an image folder as well as an image in that folder to launch in Napari!")
                return
            image_path = self.image_directory + "/" + image_folder + "/" + image_name
            self.image_path_choice = image_path
            if self.labels_done is True:
                tk.messagebox.showwarning("Napari Warning!", 
                    message = "Labels have been generated and not exported! \n Napari will not launch unless you export or discard those labels!")
                return
            self.master.supervised.launch_Napari(image_path, display_all_channels = display_all_channels)
            self.labels_done = True
            self.button2.configure(state = "normal")
            self.button3.configure(state = "normal")

        def accept_Napari_labeling(self) -> None:
            if self.labels_done is False:
                tk.messagebox.showwarning("Napari Warning!", message = "No labels are available to save!")
                return
            if np.max(self.master.supervised._user_labels) == 0:
                tk.messagebox.showwarning("Napari Warning!",
                    message = "No labels to save! \n Did you accidently click save before drawing any labels in Napari? \n"
                              "If you have closed Napari, click the Discard button to allow another Napari window to be opened")
                return
            if not overwrite_approval(self.master.supervised.training_folder + "/" + self.master.supervised._image_name, file_or_folder = "file"):
                return
            self.master.supervised.write_from_Napari()
            pixel_logger.info(f"Updated labels for Training image: {self.image_path_choice}")
            self.labels_done = False
            self.button2.configure(state = "disabled")
            self.button3.configure(state = "disabled")

        def discard_labels(self) -> None:
            if self.labels_done is False:
                tk.messagebox.showwarning("Napari Warning!", message = "No labels are available to discard!")
                return
            self.master.supervised._user_labels = None   ## clears stored Napari layer
            self.labels_done = False
            self.button2.configure(state = "disabled")
            self.button3.configure(state = "disabled")

    class prediction_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master

            label = ctk.CTkLabel(master = self, text = "Applied a trained Pixel Classifier to make pixel class predictions")
            label.grid(row = 0, columnspan = 2, column = 0, padx = 4, pady = 4)

            self.type = ctk.StringVar(value = "")
            self.one = ctk.CTkRadioButton(master = self, text = "Do One Image", variable = self.type, value = "one")
            self.one.grid(row = 1, column = 0, padx = 4, pady = 4)
            self.all = ctk.CTkRadioButton(master = self, text = "Do Entire Folder", variable = self.type, value = "all")
            self.all.grid(row = 1, column = 1, padx = 4, pady = 4)
            self.all.select()

            self.predict_one_img = ctk.CTkLabel(master = self, text = "Choose Image Folder:")
            self.predict_one_img.grid(row = 2, column = 0, padx = 4, pady = 2)

            def refresh3():
                self.folder.configure(values = [i for i in sorted(os.listdir(self.master.image_directory)) if i.find(".") == -1])

            self.folder = ctk.CTkOptionMenu(master = self, 
                                            values = [i for i in sorted(os.listdir(self.master.image_directory)) if i.find(".") == -1], 
                                            variable = ctk.StringVar(value = ""), 
                                            command = self.update_one)
            self.folder.grid(row = 3, column = 0, padx = 4, pady = 2)
            self.folder.bind("<Enter>", lambda enter: refresh3())

            self.predict_one_img = ctk.CTkLabel(master = self, text = "Choose Single Test Image:")
            self.predict_one_img.grid(row = 4, column = 0, padx = 4, pady = 2)

            self.one_img = ctk.CTkOptionMenu(master = self, values = [""], variable = ctk.StringVar(value = "")) 
            self.one_img.grid(row = 5, column = 0, padx = 4, pady = 2)

            self.predict_folder = ctk.CTkButton(master = self, 
                                                text = "Create Pixel Class Predictions!", 
                                                command = lambda: self.master.predict(self.type.get()))
            self.predict_folder.grid(row = 6, column = 1, padx = 4, pady = 2)

        def update_one(self, image_folder: str) -> None:
            self.one_img.configure(values = [i for i in sorted(os.listdir(self.master.image_directory + "/" + image_folder)) if i.lower().find(".tif") != -1])
            def refresh4():
                try:       
                        ## try / except here because of the tendency of many errors to be generated by refreshers like these 
                        # before a classifier is loaded
                    self.one_img.configure(values = [i for i in sorted(os.listdir(self.master.image_directory + "/" + image_folder)) if i.lower().find(".tif") != -1])
                except Exception:
                    pass
            self.one_img.bind("<Enter>", lambda enter: refresh4())

    class segmentation_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master

            label = ctk.CTkLabel(master = self, 
                text = "Segment from Pixel Classification map: \n <<<only use with a single non-background class \n like nuclei or cells!>>>")
            label.grid(padx = 3, pady = 3, row = 0, column = 0)

            label1 = ctk.CTkLabel(master = self, text = "Choose pixel threshold for not segmenting \n objects too small to be cells")
            label1.grid(padx = 3, row = 1, column = 0, pady = 3)

            self.threshold = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "15"))
            self.threshold.grid(padx = 3, pady = 3, row = 1, column = 1)

            label1 = ctk.CTkLabel(master = self, 
                text = "Choose distance between centroids \n (higher numbers can help prevent excessive segmentation)")
            label1.grid(padx = 3, row = 2, column = 0, pady = 3)

            self.distance_between_centroids = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "10"))
            self.distance_between_centroids.grid(padx = 3, pady = 3, row = 2, column = 1)

            label2 = ctk.CTkLabel(master = self, text = "Choose input folder for class maps:")
            label2.grid(padx = 3, pady = 3, row = 3, column = 0)

            self.input_choices = ['classification_maps', 'merged_classification_maps']
            self.input_folder = ctk.CTkOptionMenu(master = self, values = self.input_choices, variable = ctk.StringVar(value = ""))
            self.input_folder.grid(padx = 3, pady = 3, row = 3, column = 1)

            button = ctk.CTkButton(master = self, text = "Run segmentation", command = self.run_seg)
            button.grid(padx = 3, pady = 3, row = 4, column = 1)

        def run_seg(self) -> None:
            if self.master.name is None:
                tk.messagebox.showwarning("No Classifier Loaded!", message = "No Classifier Loaded!")
                return
            if self.input_folder.get() == "":
                tk.messagebox.showwarning("No Class maps selected!", message = "Select a classification maps input folder before trying to run segmentation!")
                return
            threshold = self.threshold.get()
            distance_between_centroids = self.distance_between_centroids.get()
            try:
                threshold = int(threshold)
                distance_between_centroids = int(distance_between_centroids)
            except ValueError:
                tk.messagebox.showwarning("Warning!", 
                    message = "Threshold and distance between centroids must be integers, but one or both cannot be converted to an integer!")
                return
            
            input_folder = self.master.classifier_dir  + f"/{self.master.name}/" + self.input_folder.get()
            if len(input_folder) == 0:
                tk.messagebox.showwarning("Warning!", 
                    message = "No Classifier Maps! Have you both trained and predicted from this classifier?")
                return

            output_folder = self.master.main_directory  + f"/masks/{self.master.name}_direct_segmentation"
            if not overwrite_approval(output_folder, file_or_folder = "folder"):
                return
            
            if not os.path.exists(output_folder):
                os.mkdir(output_folder)
            segment_class_map_folder(input_folder, 
                                     output_folder, 
                                     threshold = threshold, 
                                     distance_between_centroids = distance_between_centroids, 
                                     background = 1)
            pixel_logger.info("Did Segmentation from pixel classifier: \n"
                              f"input folder = {input_folder}, \n" 
                              f"output_folder = {output_folder}, \n" 
                              f"threshold = {str(threshold)}, \n" 
                              f"distance_between_centroids = {str(distance_between_centroids)}")
            

class bio_label_launch_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.title("Associate class numbers with Biological Labels")
        try:
            self.current_class_labels = pd.read_csv(self.master.classifier_dir + f"/{self.master.name}/biological_labels.csv")
            open_json = open(self.master.classifier_dir + f"/{self.master.name}/{self.master.name}_info.json", 'r' , encoding="utf-8")
            loaded_json = open_json.read()
            loaded_json = json.loads(loaded_json) 
            open_json.close()
            if len(self.current_class_labels) != len(loaded_json['classes']):
                self.current_class_labels = None
        except FileNotFoundError:
            self.current_class_labels = None


        plot_heatmap = ctk.CTkButton(master = self, text = "Plot heatmap of channel expression from existing predictions", command = self.plot_heatmap)
        plot_heatmap.grid(padx = 3, pady = 10, column = 0, row = 0)

        self.channel_checkbox = ctk.CTkCheckBox(master = self, 
                                                text = "plot all channels in heatmap \n (default only plots channels used in classifier)", 
                                                onvalue = True, 
                                                offvalue = False)
        self.channel_checkbox.grid(padx = 3, pady = 10, column = 1, row = 0)

        if self.current_class_labels is None:
            self.number_list = [i for i in range(1, self.master.number_of_classes + 1)]
            self.entry_list = []
            for i in self.number_list:
                ctk.CTkLabel(master = self, text = str(i)).grid(column = 0, row = i, padx = 3, pady = 3)
                entry = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "Unassigned"))
                entry.grid(column = 1, row = i, padx = 3, pady = 3)
                self.entry_list.append(entry)
        else:
            self.number_list = list(self.current_class_labels['class'])
            self.entry_list = []
            for i,ii in zip(self.number_list, self.current_class_labels['labels']):
                ctk.CTkLabel(master = self, text = str(i)).grid(column = 0, row = i, padx = 3, pady = 3)
                entry = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = ii))
                entry.grid(column = 1, row = i, padx = 3, pady = 3)
                self.entry_list.append(entry)

        self.button = ctk.CTkButton(master = self, text = "Save Biological Labels", command = self.save_labels_csv)
        self.button.grid()
        self.after(200, self.focus)

    def save_labels_csv(self) -> None:
        ''''''
        labels = [i.get().strip() for i in self.entry_list]
        df = pd.DataFrame()
        df["class"] = self.number_list
        df["labels"] = labels
        unique_names = list(df["labels"].unique())
        if 'background' not in unique_names:
            unique_names = ['background'] + unique_names
        unique_dict = {ii:(i + 1) for i,ii in enumerate(unique_names)}
        unique_dict['background'] = 0
        df['merging'] = df['labels'].replace(unique_dict)
        df.to_csv(self.master.classifier_dir + f"/{self.master.name}/biological_labels.csv", index = False)
        
        if self.master.classifier_type == "supervised":
            merge_folder(self.master.supervised.directory + "/classification_maps", 
                        pd.read_csv(self.master.supervised.directory + "/biological_labels.csv"),
                        self.master.supervised.directory + "/merged_classification_maps")
        elif self.master.classifier_type == "unsupervised":
            self.master.unsupervised.set_class_names({i:ii for i,ii in zip(df["class"],df["labels"])})
            merge_folder(self.master.unsupervised.directory + "/classification_maps", 
                        pd.read_csv(self.master.unsupervised.directory + "/biological_labels.csv"),
                        self.master.unsupervised.directory + "/merged_classification_maps")
        pixel_logger.info(f"Saved Biological labels and merged: \n {str(df)}")
        self.destroy()

    def plot_heatmap(self):
        ''''''
        panel = pd.read_csv(self.master.main_directory + "/panel.csv")
        if self.master.classifier_type == "unsupervised":
            pixel_folder = self.master.unsupervised.output_dir
            details_dict = self.master.unsupervised.training_dictionary
            channels = [i for i in details_dict['channels']]
            filepath = self.master.unsupervised.directory + "/cluster_heatmap.png"
        else:
            pixel_folder = self.master.supervised.output_folder
            details_dict = self.master.supervised.model_info
            channels = [i for i in details_dict['channels']]
            filepath = self.master.supervised.directory + "/cluster_heatmap.png"
        if self.channel_checkbox.get() is True:
            channels = [i for i in panel[panel['keep'] == 1]['name']]
        
        if len(channels) == 1:
            tk.messagebox.showwarning("Warning!", 
                    message = "Cannot plot a heatmap with only 1 channel! Cancelling heatmap")
            return

        image_folder = details_dict['image_folder']       
        figure, _ = plot_pixel_heatmap(pixel_folder, image_folder, channels, panel, silence_division_warnings = True)
        figure.savefig(filepath)
        plt.close(fig = 'all')
        pixel_logger.info(f"Plotted heatmap for FlowSOM cluster centers of {self.master.name}")
        self.master.quick_display.save_and_display(filepath)

class loading_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__()
        self.master = master
        label = ctk.CTkLabel(master = self, 
            text = "To Overwrite a Prior Classifier -- enter the same name \n"
                    "then create the same type (supervised / unsupervised) as the classifier to be overwritten")
        label.grid(row = 0, column = 0, padx = 3, pady = 3)

        self.entry = self.new_classifier_frame(self, higher = master)
        self.entry.grid(row = 1, column = 0, padx = 3, pady = 3)
        self.entry.configure(fg_color = "gray50")

        load_label = ctk.CTkLabel(master = self, text = "Load Classifier from Local Project")
        load_label.grid(row = 2, column = 0, padx = 3, pady = 3)

        self.load_project = self.load_project_frame(self)
        self.load_project.grid(row = 3, column = 0, padx = 3, pady = 3, sticky = "nsew")

        self.load_or_save_frame = self.load_or_save(self, master)
        self.load_or_save_frame.grid(row = 4, column = 0, padx = 3, pady = 3, sticky = "nsew")
        self.load_or_save_frame.configure(fg_color = "gray50")

        self.deiconify()
        self.after(200, lambda: self.focus())

    def unsupervised(self, classifier_name: str, master) -> None:
        ''''''
        if not overwrite_approval(self.master.classifier_dir + "/Unsupervised_" + classifier_name, file_or_folder = "folder", custom_message = "Are you sure you want to overwrite the existing classifier?"):
            return
        unsupervised_window(master)
        pixel_logger.info(f"Initialized Classifier {self.master.name}")
        self.master.name = "Unsupervised_" + classifier_name
        self.master.name_holder.set(self.master.name)
        self.master.unsupervised = UnsupervisedClassifier(self.master.main_directory, self.master.name )
        self.master.classifier_type = "unsupervised" 
        self.master.name_holder.set(self.master.name)
        self.withdraw()

    def accept_classifier_name(self, classifier_name: str, master) -> None:
        ''''''
        if not overwrite_approval(self.master.classifier_dir + "/" + classifier_name, file_or_folder = "folder", custom_message = "Are you sure you want to overwrite the existing classifier?"):
            return
        self.master.name = classifier_name
        self.master.supervised = SupervisedClassifier(self.master.main_directory, classifier_name)
        supervised_window(master)
        self.master.name_holder.set(self.master.name)
        self.master.classifier_type = "supervised"
        self.master.Napari_frame.activate_buttons()
        pixel_logger.info(f"Initialized Classifier {self.master.name}")
        self.withdraw()

    def load(self, name: str) -> None:
        ''''''
        if name.rfind('Unsupervised') == -1:
            self.master.name = name
            self.master.name_holder.set(self.master.name)
            self.master.classifier_type = "supervised"
            self.master.Napari_frame.activate_buttons()

            details_path = self.master.classifier_dir + f"/{name}/{name}_info.json"
            open_json = open(details_path, 'r' , encoding="utf-8")
            loaded_json = open_json.read()
            loaded_json = json.loads(loaded_json) 
            open_json.close()
            self.master.supervised = SupervisedClassifier(self.master.main_directory, name)
            self.master.supervised.load_classifier()
            self.master.number_of_classes = len(loaded_json["classes"])

        else:
            self.master.name = name
            self.master.name_holder.set(self.master.name)
            self.master.classifier_type = "unsupervised"
            details_path = self.master.classifier_dir + f"/{name}/{name}_info.json"
            open_json = open(details_path, 'r' , encoding="utf-8")
            loaded_json = open_json.read()
            loaded_json = json.loads(loaded_json) 
            open_json.close()
            self.master.number_of_classes = loaded_json['metaclusters']
            self.master.unsupervised = UnsupervisedClassifier(self.master.main_directory, name)
            self.master.unsupervised.load_classifier()

        pixel_logger.info(f"Loaded Classifier {self.master.name} with details dictionary = \n {str(loaded_json)}")
        self.after(200, self.destroy())

    def launch_load_window(self, master) -> None:
        load_from_assets_window(master)
        self.after(200, self.withdraw())

    class new_classifier_frame(ctk.CTkFrame):
        def __init__(self, master, higher):
            super().__init__(master)
            label1 = ctk.CTkLabel(master = self, text = "Name a new Pixel Classifier:")
            label1.grid(row = 0, column = 1, padx = 5, pady = 5)

            label2 = ctk.CTkLabel(master = self, text = "Enter Classifier Name:")
            label2.grid(row = 1, column = 0, padx = 5, pady = 5)

            self.Name_entry = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "Classifier_1"))
            self.Name_entry.grid(row = 1, column = 1, padx = 5, pady = 5)

            self.unsupervised_button = ctk.CTkButton(master = self, 
                                                text = "Make an unsupervised Pixel Classifier", 
                                                command = lambda: self.master.unsupervised(self.Name_entry.get().strip(), master = higher))
            self.unsupervised_button.grid(row = 0, column = 2, padx = 5, pady = 5)

            self.name_entry_button = ctk.CTkButton(master = self, 
                                                text = "Make a supervised Pixel Classifier", 
                                                command = lambda: self.master.accept_classifier_name(self.Name_entry.get().strip(), 
                                                master = higher))
            self.name_entry_button.grid(row = 1, column = 2, padx = 5, pady = 5)

    class load_project_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            label = ctk.CTkLabel(master = self, text = "Selecting automatically loads \n (re-loaded unsupervised classifiers cannot predict):")
            label.grid(row = 0, column = 0, padx = 3, pady = 3)

            def refresh6():
                try:
                    local_projects = [i for i in sorted(os.listdir(self.master.master.classifier_dir)) if i.find(".") == -1] 
                    self.project_options.configure(values = local_projects)
                except Exception:
                    pass

            local_projects = [i for i in sorted(os.listdir(self.master.master.classifier_dir)) if i.find(".") == -1]
            self.project_options = ctk.CTkOptionMenu(master = self, 
                                                     values = local_projects, 
                                                     command = self.master.load, 
                                                     variable = ctk.StringVar(value = ""))
            self.project_options.grid(row = 0, column = 1, padx = 3, pady = 3)
            self.project_options.bind("<Enter>", lambda enter: refresh6())

    class load_or_save(ctk.CTkFrame):
        def __init__(self, master, higher):
            super().__init__(master)
            self.master = master
            self.configure(height = 200, width = 250)

            label = ctk.CTkLabel(self, text = "Load a Pixel Classifier \n From PalmettoBUG Assets:")
            label.grid(row = 0, column = 0 , columnspan = 2, padx = 3, pady = 3)

            Load_button = ctk.CTkButton(master = self, 
                                        text = "Load a Pixel Classifier", 
                                        command = lambda: self.master.launch_load_window(master = higher))
            Load_button.grid(row = 1, column = 0 , padx = 3, pady = 3)

class unsupervised_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__()
        self.master = master
        self.title("Select Options for Unsupervised FlowSOM-based Pixel Classifier")
        self.additional_features = False
        self.panel = pd.read_csv(self.master.main_directory + "/panel.csv").drop(["channel", "segmentation"], axis = 1)
        self.panel = self.panel[self.panel['keep'] == 1]

        label = ctk.CTkLabel(master = self, 
                             text = "Select what Channels to use: \n features   = gaussian | hessian | frangi | butterworth")
        label.grid(row = 0, column = 0, pady = 3, padx = 5)

        self.keep_table = self.keep_channel_table(self)
        self.keep_table.grid(row = 2 , column = 0, columnspan = 3, padx = 3, pady = 3)

        label = ctk.CTkLabel(master = self, text = "Choose Folder of Images to Train from:")
        label.grid(row = 3, column = 0 , padx = 3, pady = 3)

        def refresh7():
            self.img_choices = [i for i in os.listdir(self.master.image_directory) if i.find(".") == -1]
            self.image_choice.configure(values = self. img_choices)

        self.img_choices = [i for i in os.listdir(self.master.image_directory) if i.find(".") == -1]
        self.image_choice = ctk.CTkOptionMenu(master = self, values = self.img_choices, variable = ctk.StringVar(value= "")) 
        self.image_choice.grid(row = 4, column = 0, padx = 3, pady = 3)
        self.image_choice.bind("<Enter>", lambda enter:  refresh7())

        label2 = ctk.CTkLabel(master = self, text = "Choose Sigma levels:")
        label2.grid(row = 5, column = 0 , padx = 3, pady = 3)

        self.sigma_choice = self.Sigma_frame(self)
        self.sigma_choice.grid(row = 6, column = 0, padx = 3, pady = 3)

        label3 = ctk.CTkLabel(master = self, text = "Final Number of (meta)clusters to Classify on:")
        label3.grid(row = 7, column = 0 , padx = 3, pady = 3)

        self.metaclusters = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "20"))
        self.metaclusters.grid(row = 8, column = 0, padx = 3, pady = 3)

        label4 = ctk.CTkLabel(master = self, text = "Number of Pixels to Train on:")
        label4.grid(row = 9, column = 0, padx = 3, pady = 3)

        self.training_number = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "500000"))
        self.training_number.grid(row = 10, column = 0, padx = 3, pady = 3)

        label4 = ctk.CTkLabel(master = self, text = "Quantile (as a decimal < 1):")
        label4.grid(row = 11, column = 0, padx = 3, pady = 3)

        self.quantile  = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "0.999"))
        self.quantile.grid(row = 12, column = 0, padx = 3, pady = 3) 

        label4b = ctk.CTkLabel(master = self, text = "Number of Training Cycles:")
        label4b.grid(row = 3, column = 1, padx = 3, pady = 3)

        self.training_cycles = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "50"))
        self.training_cycles.grid(row = 4, column = 1, padx = 3, pady = 3)

        label5 = ctk.CTkLabel(master = self, text = "SOM X&Y Dimensions")
        label5.grid(row = 5, column = 1, padx = 3, pady = 3)

        self.XY_dim = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "15"))
        self.XY_dim.grid(row = 6, column = 1, padx = 3, pady = 3)

        label6 = ctk.CTkLabel(master = self, text = "Random Seed:")
        label6.grid(row = 7, column = 1, padx = 3, pady = 3)

        self.seed = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "42"))
        self.seed.grid(row = 8, column = 1, padx = 3, pady = 3)

        label7 = ctk.CTkLabel(master = self, 
            text = "Select Smoothing Threshold: \n groups of pixels smaller than threshold will be \n smoothed (select 0 for no smoothing)")
        label7.grid(row = 9, column = 1, padx = 3, pady = 3)

        self.smoothing_choice = ctk.CTkOptionMenu(master = self, values = ["0","1","2","3","4","5"], variable = ctk.StringVar(value = "0"))
        self.smoothing_choice.grid(row = 10, column = 1, padx = 3, pady = 3)

        button_train = ctk.CTkButton(master = self, text = "Run Training!", command = self.run_training)
        button_train.grid(row = 11, column = 1, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def run_training(self) -> None:
        ''''''
        img_directory = self.master.image_directory + "/" + self.image_choice.get()
        if self.image_choice.get() == "":
            tk.messagebox.showwarning("Warning!", 
                        message = "You must select a folder of images to train from!")
            self.focus()
            return
        try:
            quantile = float(self.quantile.get())
            training_cycles = int(self.training_cycles.get())
            size = int(self.training_number.get())
            seed = int(self.seed.get())
            n_clusters = int(self.metaclusters.get())
            XYdim = int(self.XY_dim.get())
        except ValueError:
            tk.messagebox.showwarning("Not Integer inputs!", 
                        message = "Number of Pixels & clusters, seed, training_cycles, quantile, and XY dimensions must all be integers!")
            self.focus()
            return
        
        if (quantile > 1) or (quantile < 0):
            tk.messagebox.showwarning("Improper inputs!", 
                        message = "Quantile parameter must be between 0 and 1")
            self.focus()
            return
        
        self.channel_panel = self.keep_table.retrieve()        
        self.channel_panel.to_csv(self.master.classifier_dir + f"/{self.master.name}/flowsom_panel.csv", index = False)
        self.channel_dictionary = {}
        self.channel_names = {}
        kept = self.channel_panel
        kept_channels = kept.index
        for i in kept_channels:
            features = ['gaussian','hessian','frangi','butterworth']
            applied_features = kept.loc[i,['gaussian','hessian','frangi','butterworth']]
            add_features = [q for q,qq in zip(features,applied_features) if int(qq) == 1]
            if len(add_features) != 0:
                self.channel_names[str(i)] = self.channel_panel.loc[i, 'antigen']
                self.channel_dictionary[str(i)] = [q for q,qq in zip(features,applied_features) if int(qq) == 1]

        if len(self.channel_dictionary) == 0:
            tk.messagebox.showwarning("No Channels selected", 
                        message = "You must select at least one channel to use!")
            self.focus()
            return

        self.master.image_source_dir = img_directory
        sigma = self.sigma_choice.retrieve()
        smoothing = int(self.smoothing_choice.get())

        df = pd.DataFrame()
        df["class"] = [i+1 for i in range(0, n_clusters)]
        df["labels"] = "Unassigned"
        df['merging'] = 1
        df.to_csv(self.master.classifier_dir + f"/{self.master.name}/biological_labels.csv", index = False)

        self.master.unsupervised.set_channel_names(self.channel_names)

        self.master.unsupervised.train(image_folder = img_directory,                
                                    sigmas = sigma, 
                                    channel_dictionary = self.channel_dictionary,  
                                    pixel_number = size, 
                                    seed = seed, 
                                    metaclusters = n_clusters, 
                                    XYdim = XYdim,  
                                    training_cycles = training_cycles, 
                                    smoothing = smoothing,
                                    # suppress_zero_division_warnings = True,
                                    quantile = quantile) 
        self.master.number_of_classes = n_clusters

        pixel_logger.info(f"Trained Unsupervised Classifier {self.master.name} with the following training dictionary: \n" 
                           f"{str(self.master.unsupervised.model_info)}")

        warning_window("Training Finished!")
        self.after(200, self.withdraw())

    class keep_channel_table(ctk.CTkScrollableFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            self.panel = master.panel
            self.configure(height = 400, width = 1000)
            features_list = ['gaussian',
                            'hessian',
                            'frangi',
                            'butterworth']
            self.widget_list_of_lists = []
            keeplist = []
            for i, ii in enumerate(self.panel['name']):
                label = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = ii))
                label.grid(row = i + 3, column = 0, pady = 5)
                label.configure(state = "disabled")

                keep = ctk.CTkOptionMenu(master = self, values = ["","Use Channel"], variable = ctk.StringVar(value = ""))
                #keep.grid(row = i + 3, column = 1, pady = 3, padx = 8)

                widget_list = [label, keep]
                keeplist.append(keep)
                for j, jj in enumerate(features_list):
                    feature = ctk.CTkCheckBox(master = self, text = "", onvalue = 1, offvalue = 0)
                    feature.grid(row = i + 3, column = j + 2, pady = 5)
                    feature.configure(width = 68, checkbox_width = 25)
                    widget_list.append(feature)

                self.widget_list_of_lists.append(widget_list)

        def retrieve(self) -> pd.DataFrame:
            index = ['antigen',
                     'keep', 
                     'gaussian',
                     'hessian',
                     'frangi',
                     'butterworth']
            self.dataframe = pd.DataFrame(index = index)
            for i,ii in enumerate(self.widget_list_of_lists):
                self.dataframe[i] = [k.get() for k in ii]
            self.dataframe = self.dataframe.transpose()
            self.dataframe['keep'] = self.dataframe['keep'].replace({"":0, "Use Channel":1}).astype('int')
            self.dataframe.index = [i for i in range(0,len(self.widget_list_of_lists))]
            if self.dataframe.drop(["keep","antigen"], axis = 1).sum().sum() != 0:
                self.master.additional_features = True
            else:
                self.master.additional_features = False
            return self.dataframe

    class Sigma_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            self.sigma_options_list = [0.5, 1.0, 5.0, 10.0]
            self.checkbox_list = []
            for i in self.sigma_options_list:
                checkbox = ctk.CTkCheckBox(master = self, text = i, onvalue = True, offvalue = False)
                if i != 0.5:
                    checkbox.select()
                checkbox.grid(padx = 5, pady = 5)
                self.checkbox_list.append(checkbox)

        def retrieve(self) -> list[float]:
            retrieve_list = []
            for i in self.checkbox_list:
                retrieve_list.append(i.get())
            dataframe = pd.DataFrame(self.sigma_options_list, columns = ["sigmas"])
            dataframe = dataframe[retrieve_list]
            return list(dataframe['sigmas'])

class supervised_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__()
        self.master = master
        self.title("Select Details for Supervised Pixel Classifier")
        self.additional_features = False
        self.panel = pd.read_csv(self.master.main_directory + "/panel.csv").drop(["channel", "segmentation"], axis = 1)
        self.panel = self.panel[self.panel['keep'] == 1]

        self.iterations = 1000   ## These are the advanced options
        self.learning_rate = 0.01
        self.internals = []

        label = ctk.CTkLabel(master = self, 
                             text = "Select what Channels to use: \n features   = gaussian | hessian | frangi | butterworth")
        label.grid(row = 0, column = 0, pady = 3, padx = 5)

        self.keep_table = self.keep_channel_table(self)
        self.keep_table.grid(row = 2 , column = 0, columnspan = 2, padx = 3, pady = 3)

        self.classes_selection = self.class_dict_maker_semi_auto(self)
        self.classes_selection.grid(row = 2 , column = 2, padx = 3, pady = 3)

        label = ctk.CTkLabel(master = self, text = "Choose Folder of Images to Train from:")
        label.grid(row = 3, column = 0 , padx = 3, pady = 3)

        def refresh7():
            self.img_choices = [i for i in os.listdir(self.master.image_directory) if i.find(".") == -1]
            self.image_choice.configure(values = self. img_choices)

        self.img_choices = [i for i in os.listdir(self.master.image_directory) if i.find(".") == -1]
        self.image_choice = ctk.CTkOptionMenu(master = self, values = self.img_choices, variable = ctk.StringVar(value= "")) 
        self.image_choice.grid(row = 4, column = 0, padx = 3, pady = 3)
        self.image_choice.bind("<Enter>", lambda enter:  refresh7())

        label2 = ctk.CTkLabel(master = self, text = "Choose Sigma levels:")
        label2.grid(row = 5, column = 0 , padx = 3, pady = 3)

        self.sigma_choice = self.Sigma_frame(self)
        self.sigma_choice.grid(row = 6, column = 0, padx = 3, pady = 3)

        label3 = ctk.CTkLabel(master = self, text = "Hidden Layers:")
        label3.grid(row = 7, column = 0 , padx = 3, pady = 3)

        self.hidden_layers = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "100"))
        self.hidden_layers.grid(row = 8, column = 0, padx = 3, pady = 3)

        label4 = ctk.CTkLabel(master = self, text = "Quantile (as a decimal < 1):")
        label4.grid(row = 11, column = 0, padx = 3, pady = 3)

        self.quantile  = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "0.999"))
        self.quantile.grid(row = 12, column = 0, padx = 3, pady = 3) 

        label6 = ctk.CTkLabel(master = self, text = "Learning Rate:")
        label6.grid(row = 7, column = 1, padx = 3, pady = 3)

        self.LR = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "0.001"))
        self.LR.grid(row = 8, column = 1, padx = 3, pady = 3)

        button_train = ctk.CTkButton(master = self, text = "Save Classifier Details", command = self.run_training)
        button_train.grid(row = 11, column = 1, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def run_training(self) -> None:
        ''''''
        img_directory = self.master.image_directory + "/" + self.image_choice.get()
        if self.image_choice.get() == "":
            tk.messagebox.showwarning("Warning!", 
                        message = "You must select a folder of images to train from!")
            self.focus()
            return
        try:
            quantile = float(self.quantile.get())
            learning_rate = float(self.LR.get())
            hidden_layers = self.hidden_layers.get()
            hidden_layers = hidden_layers.replace(" ","").split()
            hidden_layers = [int(i) for i in hidden_layers]
        except ValueError:
            tk.messagebox.showwarning("Improper inputs!", 
                        message = "Quantile & Learning Rate Parameters must be numerical & the hidden layers must be specified as a comma-separate sequence of integers!")
            self.focus()
            return
    
        if (quantile > 1) or (quantile < 0):
            tk.messagebox.showwarning("Improper inputs!", 
                        message = "Quantile parameter must be between 0 and 1")
            self.focus()
            return
        
        self.channel_panel = self.keep_table.retrieve()        
        self.channel_panel.to_csv(self.master.classifier_dir + f"/{self.master.name}/flowsom_panel.csv", index = False)
        self.channel_dictionary = {}
        self.channel_names = {}
        kept = self.channel_panel
        kept_channels = kept.index
        for i in kept_channels:
            features = ['gaussian','hessian','frangi','butterworth']
            applied_features = kept.loc[i,['gaussian','hessian','frangi','butterworth']]
            add_features = [q for q,qq in zip(features,applied_features) if int(qq) == 1]
            if len(add_features) != 0:
                self.channel_names[str(i)] = self.channel_panel.loc[i, 'antigen']
                self.channel_dictionary[str(i)] = [q for q,qq in zip(features,applied_features) if int(qq) == 1]

        if len(self.channel_dictionary) == 0:
            tk.messagebox.showwarning("No Channels selected", 
                        message = "You must select at least one channel to use!")
            self.focus()
            return

        self.master.image_source_dir = img_directory
        sigma = self.sigma_choice.retrieve()

        class_dictionary = self.classes_selection.make_dict()
        df = pd.DataFrame()
        df["class"] = [i for i in class_dictionary if class_dictionary[i] != ""]
        df["labels"] = [class_dictionary[i] for i in class_dictionary if class_dictionary[i] != ""]
        unique_names = df["labels"].unique()
        unique_dict = {ii:(i + 2) for i,ii in enumerate(unique_names)}
        unique_dict['background'] = 0
        df['merging'] = df['labels'].replace(unique_dict)
        df.to_csv(self.master.classifier_dir + f"/{self.master.name}/biological_labels.csv", index = False)

        self.master.supervised.set_target_classes(class_dictionary)

        self.master.supervised.set_channel_names(self.channel_names)

        self.master.supervised.write_classifier(image_folder = img_directory,                
                                    sigmas = sigma, 
                                    channel_dictionary = self.channel_dictionary,
                                    hidden_layers = hidden_layers,
                                    learning_rate = learning_rate,
                                    # quantile = quantile
                                    ) 
        self.master.number_of_classes = len(class_dictionary)

        pixel_logger.info(f"Initialized Supervised Classifier {self.master.name} with the following training dictionary: \n" 
                           f"{str(self.master.supervised.model_info)}")

        self.after(200, self.withdraw())

    class keep_channel_table(ctk.CTkScrollableFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            self.panel = master.panel
            self.configure(height = 400, width = 1000)
            features_list = ['gaussian',
                            'hessian',
                            'frangi',
                            'butterworth']
            self.widget_list_of_lists = []
            keeplist = []
            for i, ii in enumerate(self.panel['name']):
                label = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = ii))
                label.grid(row = i + 3, column = 0, pady = 5)
                label.configure(state = "disabled")

                keep = ctk.CTkOptionMenu(master = self, values = ["","Use Channel"], variable = ctk.StringVar(value = ""))
                #keep.grid(row = i + 3, column = 1, pady = 3, padx = 8)

                widget_list = [label, keep]
                keeplist.append(keep)
                for j, jj in enumerate(features_list):
                    feature = ctk.CTkCheckBox(master = self, text = "", onvalue = 1, offvalue = 0)
                    feature.grid(row = i + 3, column = j + 2, pady = 5)
                    feature.configure(width = 68, checkbox_width = 25)
                    widget_list.append(feature)

                self.widget_list_of_lists.append(widget_list)

        def retrieve(self) -> pd.DataFrame:
            index = ['antigen',
                     'keep', 
                     'gaussian',
                     'hessian',
                     'frangi',
                     'butterworth']
            self.dataframe = pd.DataFrame(index = index)
            for i,ii in enumerate(self.widget_list_of_lists):
                self.dataframe[i] = [k.get() for k in ii]
            self.dataframe = self.dataframe.transpose()
            self.dataframe['keep'] = self.dataframe['keep'].replace({"":0, "Use Channel":1}).astype('int')
            self.dataframe.index = [i for i in range(0,len(self.widget_list_of_lists))]
            if self.dataframe.drop(["keep","antigen"], axis = 1).sum().sum() != 0:
                self.master.additional_features = True
            else:
                self.master.additional_features = False
            return self.dataframe

    class Sigma_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            self.sigma_options_list = [0.5, 1.0, 5.0, 10.0]
            self.checkbox_list = []
            for i in self.sigma_options_list:
                checkbox = ctk.CTkCheckBox(master = self, text = i, onvalue = True, offvalue = False)
                if i != 0.5:
                    checkbox.select()
                checkbox.grid(padx = 5, pady = 5)
                self.checkbox_list.append(checkbox)

        def retrieve(self) -> list[float]:
            retrieve_list = []
            for i in self.checkbox_list:
                retrieve_list.append(i.get())
            dataframe = pd.DataFrame(self.sigma_options_list, columns = ["sigmas"])
            dataframe = dataframe[retrieve_list]
            return list(dataframe['sigmas'])

    class class_dict_maker_semi_auto(ctk.CTkScrollableFrame):
        ## This needs to be able to generate new rows at will
        def __init__(self, master, length_dict: int = 3):
            super().__init__(master)
            self.master = master
            self.configure(height = 300, width = 325)

            label_names = ctk.CTkLabel(master =self, text = "Label Each Class with \n a Biologically relevant label:")
            label_names.grid(column = 1, row = 0)

            button_add = ctk.CTkButton(master = self, text = "Add a row", command = self.add_row)
            button_add.grid(column = 2, row = 0)

            button_remove = ctk.CTkButton(master = self, text = "Remove final row", command = self.remove_last_row)
            button_remove.grid(column = 2, row = 1)

            self.row_list = []
            for i in range(0,length_dict):    ## start with three channels, users can add/remove rows as needed
                self.add_row(i)

        def add_row(self, row_num: Union[int, None] = None) -> None:
            text_var = ""
            disable = False
            if row_num == 0:
                text_var = "background"
                disable = True
            self.counter = len(self.row_list) + 1
            label = ctk.CTkLabel(master = self, text = self.counter)
            label.grid(column = 0, row = self.counter, pady = 3)
            entry1 = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = text_var))
            entry1.grid(column = 1, row = self.counter, pady = 3)
            if disable:
                entry1.configure(state = "disabled")
            self.row_list.append([label,entry1]) 

        def remove_last_row(self) -> None:
            for i in self.row_list[-1]:
                i.destroy()
            self.row_list = self.row_list[:-1]

        def make_dict(self) -> dict[int:str]:
            dictionary_out = {}
            for ii,i in enumerate(self.row_list):
                dictionary_out[ii + 1] = i[1].get().strip()    
                    ## {integer:"name"} --> likely use (and export) as a pandas dataframe / .csv instead of a dict
            return dictionary_out
        


class load_from_assets_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.title("Load a Pixel Classifier from Program Assets")

        label =  ctk.CTkLabel(master = self, text = "Select a Classifier to load:")
        label.grid(row = 0, column = 0, columnspan = 2, padx = 3, pady = 3)

        if not os.path.exists(PALMETTO_BUG_assets_classifier_folder):
            os.mkdir(PALMETTO_BUG_assets_classifier_folder)

        def refresh8():
            self.optionlist = sorted(os.listdir(PALMETTO_BUG_assets_classifier_folder))
            self.optionmenu.configure(values = self.optionlist)

        self.optionlist = sorted(os.listdir(PALMETTO_BUG_assets_classifier_folder))
        self.optionmenu = ctk.CTkOptionMenu(master = self, 
                                            values = self.optionlist, 
                                            variable = ctk.StringVar(value = ""), 
                                            command = self.choice)
        self.optionmenu.grid(row = 2, column = 0, padx = 3, pady = 3)
        self.optionmenu.bind("<Enter>", lambda enter: refresh8())

        label2 = ctk.CTkLabel(master = self, text = "Classifier_Name \n (local copy's name when loading from Assets):")
        label2.grid(row = 1, column = 3, padx = 3, pady = 3)

        self.name = ctk.StringVar()
        self.name_entry = ctk.CTkEntry(master = self, 
                                       textvariable=self.name)
        self.name_entry.configure(state = "normal")
        self.name_entry.grid(column = 3, row = 2, padx = 3, pady = 3)

        self.load_button = ctk.CTkButton(master = self, 
                                         text = "Load Classifier!", 
                                         command = lambda: self.load_classifier(self.name_entry.get().strip(), self.optionmenu.get()))
        self.load_button.grid()

        self.deiconify()
        self.after(200, lambda: self.focus())

    def choice(self, choice: str) -> None:
        self.name.set(choice)

    def load_classifier(self, name: str, classifier_load_name: str) -> None:
        ## classifier load name is only  needed when loading from assets (specifically when the project name != the assets name for the classifier)
        if not overwrite_approval(self.master.classifier_dir + "/" + name, file_or_folder = "folder", custom_message = "Are you sure you want to overwrite the existing classifier?"):
            return
        self.master.name = name
        self.master.name_holder.set(self.master.name)
        assets_path = PALMETTO_BUG_assets_classifier_folder + f"/{classifier_load_name}/{classifier_load_name}_model.pkl"
        details_path = PALMETTO_BUG_assets_classifier_folder + f"/{classifier_load_name}/{classifier_load_name}_info.json"
        destination = self.master.classifier_dir + f"/{name}/{name}"
        self.master.Napari_frame.activate_buttons()
        shutil.copyfile(assets_path, (destination + "_model.pkl"))
        shutil.copyfile(details_path, (destination + "_info.json"))
        
        open_json = open(details_path, 'r' , encoding="utf-8")
        loaded_json = open_json.read()
        loaded_json = json.loads(loaded_json) 
        open_json.close()

        if loaded_json['type'] == 'supervised':
            self.master.supervised = SupervisedClassifier(self.master.main_directory, name)
            self.master.classifier_type = "supervised"
        elif loaded_json['type'] == 'unsupervised':
            self.master.unsupervised = UnsupervisedClassifier(self.master.main_directory, name)
            self.master.classifier_type = "unsupervised"
        else:
            raise Exception("Classifier type in the .json file must be 'supervised' or 'unsupervised'")
        self.master.number_of_classes = len(loaded_json["classes"])

        pixel_logger.info(f"Classifier {name} loaded from assets and copied into this project")
        check_channels_window(self.master, loaded_json)
        self.after(200, self.withdraw())

class detail_display_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        if master.classifier_type == "supervised":
            self.setup_supervised()
        elif master.classifier_type == "unsupervised":
            self.setup_unsupervised()
        self.after(200, lambda: self.focus())

    def setup_supervised(self) -> None:
        self.classifier_json_dir = self.master.classifier_dir + f"/{self.master.name}/{self.master.name}_info.json"
        open_json = open(self.classifier_json_dir , 'r' , encoding="utf-8")
        loaded_json = open_json.read()
        self.dictionary = json.loads(loaded_json)
        open_json.close()

        self.channels = self.channel_frame(self)
        self.channels.grid(row = 0, column = 0 , pady = 3, padx = 3, sticky = "nsew")

        self.features = self.Feature_frame(self)
        self.features.grid(row = 1, column = 0 , pady = 3, padx = 3, sticky = "nsew")

        self.sigmas = self.sigma_frame(self)
        self.sigmas.grid(row = 1, column = 1 , pady = 3, padx = 3, sticky = "nsew")

        self.classes = self.classes_frame(self)
        self.classes.grid(row = 0, column = 1, pady = 3, padx = 3, sticky = "nsew")

        self.advanced = self.advanced_frame(self)
        self.advanced.grid(row = 2, column = 0 , pady = 3, padx = 3, sticky = "nsew")

    class channel_frame(ctk.CTkScrollableFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            classifier_json_dir = self.master.dictionary
            channel_label = ctk.CTkButton(master = self, text = "Channel Name : Channel Number")
            channel_label.grid(column = 0, row = 0, padx = 3, pady = 3, sticky = "nsew")
            channel_label.configure(fg_color= "green", hover_color = "green")

            channel_dictionary = classifier_json_dir["channels"]
            panel = pd.read_csv(self.master.master.main_directory + "/panel.csv")
            panel = panel[panel['keep'] == 1].reset_index()

            for ii,i in enumerate(channel_dictionary):
                label = ctk.CTkLabel(master = self, text = f"{i} : {panel.loc[int(i),'name']}")
                label.grid(column = 0, row = ii + 1, padx = 3, pady = 3, sticky = "nsew")

    class Feature_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            classifier_json_dir = self.master.dictionary
            features_label = ctk.CTkButton(master = self, text = "Channel Number : Channel Features")
            features_label.grid(column = 0, row = 0, padx = 3, pady = 3, sticky = "nsew")
            features_label.configure(fg_color= "green", hover_color = "green")

            channel_dictionary = classifier_json_dir["channels"]
            for ii,i in enumerate(channel_dictionary):
                label = ctk.CTkLabel(master = self, text = f"{i} : {str(channel_dictionary[i])}")
                label.grid(column = 0, row = ii + 1, padx = 3, pady = 3, sticky = "nsew")

    class sigma_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            classifier_json_dir = self.master.dictionary

            sigma_label = ctk.CTkButton(master = self, text = "Sigmas:")
            sigma_label.grid(column = 0, row = 0, padx = 3, pady = 3, sticky = "nsew")
            sigma_label.configure(fg_color = "green", hover_color = "green")

            sigma_list = classifier_json_dir["sigmas"]
            sigma_string = ", ".join([str(i) for i in sigma_list])
            label = ctk.CTkLabel(master = self, text = f"{sigma_string}")
            label.grid(column = 0, row = 1, padx = 3, pady = 3, sticky = "nsew")

    class classes_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            classifier_json_dir = self.master.dictionary

            channel_label = ctk.CTkButton(master = self, text = "Class Number : Class Label")
            channel_label.grid(column = 0, row = 0, padx = 3, pady = 3, sticky = "nsew")
            channel_label.configure(fg_color= "green", hover_color = "green")

            classes_dictionary = classifier_json_dir["classes"]
            for ii,i in enumerate(classes_dictionary):
                label = ctk.CTkLabel(master = self, text = f"{i} : {classes_dictionary[i]}")
                label.grid(column = 0, row = ii + 1, padx = 3, pady = 3, sticky = "nsew")

    class advanced_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master

            label0 = ctk.CTkButton(master = self, text = "Advanced feature settings:")
            label0.grid(column = 0, row = 0, padx = 3, pady = 3, sticky = "nsew")
            label0.configure(fg_color= "green", hover_color = "green")

            self.internals_dict = self.master.master.classifier_dir + f"/{self.master.master.name}/{self.master.master.name}_info.json"
            open_json = open(self.internals_dict , 'r' , encoding="utf-8")
            loaded_json = open_json.read()
            loaded_json = json.loads(loaded_json)
            open_json.close()
            epsilon = loaded_json['learning_rate']
            # iterations = loaded_json['']
            all_layers = loaded_json["hidden_layers"]

            label2 = ctk.CTkLabel(master = self, text = f"Epsilon = {epsilon}")
            label2.grid(column = 0, row = 2, padx = 3, pady = 3, sticky = "nsew")

            #label3 = ctk.CTkLabel(master = self, text = f"Iterations = {iterations}")
            #label3.grid(column = 0, row = 3, padx = 3, pady = 3, sticky = "nsew")

            label4 = ctk.CTkLabel(master = self, text = f"All Classifier Layers = {all_layers}")
            label4.grid(column = 0, row = 4, padx = 3, pady = 3, sticky = "nsew")

    def setup_unsupervised(self) -> None:
        self.classifier_panel_dir = self.master.classifier_dir + f"/{self.master.name}/flowsom_panel.csv"
        self.classifier_json_dir = self.master.classifier_dir + f"/{self.master.name}/{self.master.name}_info.json"
        self.channel_df = pd.read_csv(self.classifier_panel_dir)
        open_json = open(self.classifier_json_dir , 'r' , encoding="utf-8")
        loaded_json = open_json.read()
        self.dictionary = json.loads(loaded_json)
        open_json.close()

        channel_frame = self.unsup_channel_details_frame(self)
        channel_frame.grid(column = 0, row = 0, padx = 3, pady = 3, rowspan = 4)

        sigma_label = ctk.CTkLabel(master = self, text = f"Sigma = {self.dictionary['sigmas']}")
        sigma_label.grid(column = 0, row = 5, padx = 3, pady = 3)

        toplabel1 = ctk.CTkLabel(master = self, text = "Training Parameters:")
        toplabel1.grid(column = 1, row = 0, padx = 3, pady = 3)

        seed_label = ctk.CTkLabel(master = self, text = f"Seed = {self.dictionary['seed']}")
        seed_label.grid(column = 1, row = 1, padx = 3, pady = 3)

        n_clusters_label = ctk.CTkLabel(master = self, text = f"Number of clusters = {self.dictionary['metaclusters']}")
        n_clusters_label.grid(column = 1, row = 2, padx = 3, pady = 3)

        dims_label = ctk.CTkLabel(master = self, text = f"XYdimensions = {self.dictionary['XYdim']}")
        dims_label.grid(column = 1, row = 3, padx = 3, pady = 3)

        training_size = ctk.CTkLabel(master = self, text = f"Training set size = {self.dictionary['pixel_number']}")
        training_size.grid(column = 1, row = 4, padx = 3, pady = 3)

        source_directory = ctk.CTkLabel(master = self, text = f"Source Directory for Images = {self.dictionary['image_folder']}")
        source_directory.grid(column = 0, row = 6, padx = 3, pady = 3, columnspan = 2)

    class unsup_channel_details_frame(ctk.CTkScrollableFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            names = self.master.dictionary['channel_names']

            toplabel = ctk.CTkLabel(master = self, text = "Channels used in the Clustering:")
            toplabel.grid(padx = 5, pady = 5)
            for i in names:
                button = self.varButton(master = self, text = names[i], command_variable = i)
                button.grid(padx = 3, pady = 3)

            bottomlabel = ctk.CTkLabel(master = self, text = "Click above to display features \n generated per channel")
            bottomlabel.grid(padx = 5, pady = 5)

        class varButton(ctk.CTkButton):
            def __init__(self, master, text: str, command_variable: str):
                super().__init__(master, text = text)
                self.configure(command = lambda: self.show_features(command_variable))
                
            def show_features(self, variable) -> None:
                antigen_slice = self.master.master.dictionary['channels'][variable]
                features_window = ctk.CTkToplevel()
                toplabel = ctk.CTkLabel(master = features_window, text = "Features for this channel:")
                toplabel.grid(padx = 3, pady = 3)
                for i in antigen_slice:
                    label = ctk.CTkLabel(master = features_window, text = i)
                    label.grid(padx = 3, pady = 3)
                features_window.after(200, features_window.focus())


class check_channels_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master, seed_dictionary: dict):
        super().__init__(master)
        self.master = master

        label = ctk.CTkLabel(master= self, 
            text = "If the pixel classifier was trained on a different dataset, \n"
              "confirm that the channels in the classifier match the channels in your sample!")
        label.grid()

        self.channel_corrector = self.channel_dict_maker_entry(self, seed_dictionary)
        self.channel_corrector.grid()

        self.after(200, lambda: self.focus())     

    class channel_dict_maker_entry(ctk.CTkScrollableFrame):
        def __init__(self, master, dictionary: dict):
            super().__init__(master)
            self.dictionary = dictionary
            self.master = master
            self.configure(height = 300, width = 650)

            label_names = ctk.CTkLabel(master = self, text = "Channel Name")
            label_names.grid(column = 0, row = 0)

            label_integers = ctk.CTkLabel(master = self, text = "Channel Number")
            label_integers.grid(column = 1, row = 0)

            button_show_reference = ctk.CTkButton(master = self, 
                                                  text = "Show Channel Numbers in Current Project", 
                                                  command = self.launch_reference)
            button_show_reference.grid(column = 2, row = 2)

            button_save_changes = ctk.CTkButton(master = self, 
                                                text = "Save changed channel numbers \n and reload classifier with changes", 
                                                command = self.save_changes)
            button_save_changes.grid(column = 2, row = 3)

            self.row_list = []
            for i in dictionary["channel_names"]:
                self.add_row(i)

        def save_changes(self) -> None:
            channel_dict = {}
            for i in self.row_list:
                antigen = i[1].get()
                number = i[0].get()
                try:
                    number = int(number)
                except ValueError:
                    tk.messagebox.showwarning("Warning!",
                            message = f"{str(number)} can not be interpreted as an integer! Change and save again.")
                channel_dict[number] = antigen
            self.dictionary["channel_names"] = channel_dict
            grand_master = self.master.master
            with open(grand_master.classifier_dir + f"/{grand_master.name}/{grand_master.name}_info.json", 
                      'w', 
                      encoding="utf-8") as write_json: 
                json.dump(self.dictionary, write_json, indent = 4) 

            ## now reload the classifier
            if self.dictionary['type'] == 'supervised':
                grand_master.supervised.load_classifier()
            elif self.dictionary['type'] == 'unsupervised':
                grand_master.unsupervised.load_classifier()
            pixel_logger.info(f"Supervised Classifier {grand_master.name} channel dictionary: \n {str(self.dictionary)}")
            self.after(200, self.master.destroy())

        def add_row(self, dictionary_key: str) -> None:
            counter = len(self.row_list) + 1
            entry1 = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = dictionary_key))
            entry1.configure(state = "disabled")
            entry1.grid(column = 0, row = counter, pady = 3)
            if self.dictionary["image_folder"] != "":
                try:
                    image_list = [i for i in sorted(os.listdir(self.dictionary["image_folder"])) if i.lower().find(".tif") != -1]
                    example_img = tf.imread(self.dictionary["image_folder"] + "/" + image_list[0])
                    channel_num = len(example_img) - 1
                except FileNotFoundError:
                    entry2 = ctk.CTkEntry(master = self, 
                                          textvariable = ctk.StringVar(value = self.dictionary["channel_names"][dictionary_key]))  
                    entry2.grid(column = 1, row = counter, pady = 3) 
                entry2 = ctk.CTkOptionMenu(master = self,
                                           values = [str(i) for i in range(0,channel_num,1)], 
                                           variable = ctk.StringVar(value = self.dictionary["channel_names"][dictionary_key]))  
                entry2.grid(column = 1, row = counter, pady = 3) 
            else:
                entry2 = ctk.CTkEntry(master = self, 
                                      textvariable = ctk.StringVar(value = self.dictionary["channel_names"][dictionary_key])) 
                entry2.grid(column = 1, row = counter, pady = 3) 
            self.row_list.append([entry1, entry2])                             

        def make_dict(self) -> None:
            dictionary_out = {}
            for i in self.row_list:
                dictionary_out[i[0].get()] = i[1].get().strip()
            return dictionary_out
        
        def launch_reference(self) -> None:
            self.reference_window(self)
        
        class reference_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):

            def __init__(self, master):
                super().__init__(master)
                self.master = master
                label_exp_table = ctk.CTkLabel(master = self, text = "Layer number of the Channels Kept in the images:")
                label_exp_table.grid(row = 1, column = 0, padx = 5, pady = 5)  

                table = self.custom_table_widget(self)
                table.grid(row = 2, column = 0, padx = 5, pady = 5, rowspan = 5)

                self.after(200, lambda: self.focus())

            class custom_table_widget(ctk.CTkScrollableFrame):
                def __init__(self, master):
                    super().__init__(master)
                    self.master = master
                    self.configure(height = 300)

                    self.dataframe = pd.read_csv(self.master.master.master.master.main_directory + "/panel.csv")
                    self.dataframe = self.dataframe[self.dataframe['keep'] == 1].reset_index().drop(["channel", 
                                                                                                     "segmentation", 
                                                                                                     "keep", 
                                                                                                     "index"], axis = 1).reset_index()
                    counter = 0
                    for i,ii in zip(self.dataframe['index'], self.dataframe['name']):
                        label = ctk.CTkLabel(master = self, text = i)
                        label.grid(column = 0, row = counter)
                        label2 = ctk.CTkLabel(master = self, text = ii)
                        label2.grid(column = 1, row = counter)
                        counter += 1


class quick_option_dir_disp(DirectoryDisplay):
    def __init__ (self, master, image_dir: str, napari_backend = None):
        super().__init__(master, napari_backend)
        self.mode = "Napari"
        self.image_dir = image_dir

        self.switch_mode = ctk.CTkButton(master = self, text = "Toggle Quick Display / NAPARI", command = self.toggle_Napari_quick)
        self.switch_mode.grid(column = 0, row = 2)

    def toggle_Napari_quick(self) -> None:
        if self.mode == "Napari":
            self.mode = "quick"
            self.switch_mode.configure(text = "Toggle QUICK DISPLAY / Napari")

        elif self.mode == "quick":
            self.mode = "Napari"
            self.switch_mode.configure(text = "Toggle Quick Display / NAPARI")

    #### overwrite the varButton class to allow for the switch:
    ## note that only .tiff viewing abilities (and maybe .json?) are needed
    class varButton(ctk.CTkButton):
        '''
        a button that can return its own value to the parent object and change directories, etc.
        '''
        def __init__(self, master, 
                     textvariable: str, 
                     height: int, 
                     width: int, 
                     fg_color: str, 
                     hover_color: str, 
                     folder_file: str, 
                     parent):
            ''''''
            super().__init__(master = master, 
                             textvariable = textvariable,
                             height = height, 
                             width = width, 
                             fg_color = fg_color, 
                             hover_color = hover_color)
            self.textvar = textvariable
            self.type = folder_file
            self.parent = parent

        def configure_cmd(self) -> None:
            if self.type == "folder":
                self.configure(command = lambda: self.folder_click(self.parent, self.cget("textvariable").get()))     
            elif self.type == "file":
                self.configure(command = lambda: self.file_click(self.parent, self.cget("textvariable").get()))  
            elif self.type == "fdkjhgkjfdhgkdjghkdglskjlgkdlj":
                self.configure(command = lambda: self.folder_click(self.parent, "fdkjhgkjfdhgkdjghkdglskjlgkdlj"))  

        def file_click(self, parent, value: str) -> None:
            parent.out = value
            filepath = parent.currentdir + "/" + parent.out
            identifier = parent.out[(parent.out.rfind(".")):]
            if (identifier == ".tiff") and (self.parent.mode == "Napari"):
                input_img = tf.imread(filepath).T
                if input_img.dtype == "int":
                    masks = input_img
                    try:
                        filepath_folder = filepath[:filepath.rfind("/")]
                        classifier_folder = filepath_folder[:filepath_folder.rfind("/")]
                        details_dict = [i for i in sorted(os.listdir(classifier_folder)) if i.rfind("_details.jso") != -1]
                        open_json = open(classifier_folder + "/" + details_dict[0], 'r' , encoding="utf-8")
                        loaded_json = open_json.read()
                        loaded_json = json.loads(loaded_json) 
                        open_json.close()
                        img_directory = loaded_json['image_folder']
                        image = tf.imread(img_directory + "/" + value)
                    except Exception:
                        try:
                            image = tf.imread(self.parent.image_dir + "/img/" + value)
                        except FileNotFoundError:
                            image = np.zeros(masks.shape)
                    masks = masks.T
                    if masks.shape[0] != image.shape[1]:   ## this check only works if the image X dimensions != image Y dimensions (non-squares)
                        masks = masks.T
                    p = Process(target = run_napari, args = (image, masks))
                else:
                    p = Process(target = run_napari, args = (input_img.T, None))
                p.start()

            elif (identifier == ".tiff") and (self.parent.mode == "quick"):
                image = tf.imread(filepath).astype('int')
                plot = tf.imshow(image, cmap = "tab20", vmax = 20)
                plot[0].savefig(PALMETTO_BUG_homedir + "/Assets/temp_image.png")
                self.parent.master.quick_display.save_and_display(PALMETTO_BUG_homedir + "/Assets/temp_image.png")
                plt.close(fig = "all")

            elif identifier == ".png":
                if parent.png is not None:
                    parent.png.save_and_display(filepath)

            elif identifier == ".csv":
                dataframe = pd.read_csv(filepath)
                if len(dataframe) > 50:
                    dataframe_head = dataframe.head(25)
                    TableLaunch(1, 1, 
                                parent.currentdir, 
                                dataframe_head, 
                                f"First 25 entries of {parent.out}{identifier}", 
                                parent.experiment, 
                                logger = pixel_logger)
                else:
                    TableLaunch(1, 1, 
                                parent.currentdir, 
                                dataframe, 
                                (parent.out), 
                                parent.experiment, 
                                logger = pixel_logger)

        def folder_click(self, parent, value) -> None:
            parent.change_dir(value)