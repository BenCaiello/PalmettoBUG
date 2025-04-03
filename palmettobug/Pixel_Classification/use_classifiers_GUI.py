'''
This module handles the second-half of the third tab of the program (pixel classification). This is the portion of the GUI concerned
with using the outputs of pixel classifiers, such as slicing images to only be regions containing pixel classes of interest, classifying
cells by a pixel classifier, doing secondary flowsom, whole-class analysis, etc.



This file is licensed under the GPL3 license. No significant portion of the code here is known to be derived from another project 
(in the sense of needing to be separately / simultaneously licensed)                                                 
'''

import os
from pathlib import Path
from typing import Union
import json
import tkinter as tk
import customtkinter as ctk

import pandas as pd
import numpy as np
import tifffile as tf

from ..ImageProcessing.ImageAnalysisClass import TableLaunchAnalysis
from ..Analysis_functions.WholeClassAnalysis import WholeClassAnalysis
from ..Analysis_widgets.Analysis_GUI import MatPlotLib_Display, data_table_exportation_window
from .Classifiers_GUI import quick_option_dir_disp
from .Classifiers import plot_pixel_heatmap
from .use_classifiers import (plot_classes,
                              extend_masks_folder, 
                              slice_folder, 
                              secondary_flowsom, 
                              classify_from_secondary_flowsom, 
                              mode_classify_folder, 
                              merge_classes, 
                              merge_folder,
                              toggle_in_gui)
from ..Utils.sharedClasses import (CtkSingletonWindow, 
                                   Project_logger, 
                                   TableWidget, 
                                   run_napari, 
                                   folder_checker,
                                   overwrite_approval, 
                                   display_image_button,
                                   warning_window)

pd.set_option('future.no_silent_downcasting', True)

__all__ = []

PALMETTO_BUG_homedir = __file__.replace("\\","/")
PALMETTO_BUG_homedir = PALMETTO_BUG_homedir[:(PALMETTO_BUG_homedir.rfind("/"))]
## do it twice to get up to the top level directory:
PALMETTO_BUG_homedir = PALMETTO_BUG_homedir[:(PALMETTO_BUG_homedir.rfind("/"))] 

class Pixel_usage_widgets(ctk.CTkFrame):

    def __init__(self, master):    
        super().__init__(master)
        toggle_in_gui()
        self.master = master
        self.classifier_type = None

    def add_experiment(self, experiment):
        self.Experiment_object = experiment

    def set_directory(self, dir_object: str, partial: bool = False) -> None:
        if partial is False:
            self.dir_object = dir_object
            self.main_directory = dir_object.main
            self.classifier_dir = dir_object.px_classifiers_dir
            self.image_directory = dir_object.img_dir

            global pixel_logger
            pixel_logger = Project_logger(dir_object.main).return_log()

        try:   ## clear old widgets, if they exist
            if partial is False:
                self.load_and_display.destroy()    
            self.whole_class.destroy()
            self.filter.destroy()
            self.classify_cells.destroy()
            self.merge_class_masks.destroy()
        except Exception:
            pass

        if partial is False:
            self.load_and_display = self.load_and_display_frame(self)
            self.load_and_display.grid(row = 0, column = 0, rowspan = 5)

        self.whole_class = self.whole_class_frame(self)
        self.whole_class.grid(row = 0, column = 2, sticky = "nsew")

        self.filter = self.filter_frame(self)
        self.filter.grid(row = 0, column = 1, sticky = "nsew")

        self.classify_cells = self.classify_cells_frame(self)
        self.classify_cells.grid(row = 1, column = 1, sticky = "nsew")

        self.merge_class_masks = self.merge_class_masks_frame(self)
        self.merge_class_masks.grid(row = 1, column = 2, sticky = "nsew")

    def load_classifier(self, option: str) -> None:
        self.name = option
        self.active_classifier_dir = self.classifier_dir + "/" + option
        if option.find("Unsupervised") == -1:
            self.classifier_type = "supervised"
        else:
            self.classifier_type = "unsupervised"

        self.set_directory(self.dir_object, partial = True)

        self.filter.filter_list.initialize_with_classifier()
        self.merge_class_masks.loaded_classifier(self.classifier_type)
        self.classify_cells.loaded_classifier()
        self.classify_cells.merge_frame.initialize_with_classifier()
        self.whole_class.load_classifier_activate_buttons()
        pixel_logger.info(f"Loaded Classifier: {self.name}, for post-prediction use")
        self.load_and_display.change_labels_button.configure(command = self.load_and_display.launch_bio_labels)

    class load_and_display_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master

            self.label = ctk.CTkLabel(master = self, text = "Load a Classifier's masks to Use:")
            self.label.grid(padx = 3, pady = 3, column = 0, row = 0, sticky = "ew", columnspan = 2)

            def refresh1():
                self.classifier_option_menu.configure(values = sorted(os.listdir(self.master.classifier_dir)))

            classifier_options = sorted((self.master.classifier_dir))
            self.classifier_option_menu = ctk.CTkOptionMenu(master = self, 
                                                            values = classifier_options, 
                                                            variable = ctk.StringVar(value = ""), 
                                                            command = self.master.load_classifier)
            self.classifier_option_menu.grid(padx = 3, pady = 3, column = 0, row = 1, columnspan = 2)
            self.classifier_option_menu.bind("<Enter>", lambda enter: refresh1())

            self.quick_display = display_image_button(self, PALMETTO_BUG_homedir + "/Assets/Capture2.png")
            self.quick_display.grid(row = 2, column = 0, padx = 3, pady = 3,  columnspan = 2) 

            self.dir_disp = quick_option_dir_disp(self, self.master.image_directory)
            self.dir_disp.grid(padx = 3, pady = 3, column = 0, row = 3, rowspan = 2)
            self.dir_disp.setup_with_dir(self.master.main_directory, delete_remove = True, png = self.quick_display)

            self.change_labels_button = ctk.CTkButton(master = self, text = "View / Edit \n Class number : biological label \n assignments")
            self.change_labels_button.grid(padx = 3, pady = 3, column = 1, row = 3, columnspan = 2)

            self.plot_classes = ctk.CTkButton(master = self, text = "Plot Classes as PNG files", command = self.launch_classes_as_png)
            self.plot_classes.grid(padx = 3, pady = 3, column = 1, row = 4, columnspan = 2)

        def launch_classes_as_png(self):
            ''''''
            classes_as_png_window(self)
        
        def launch_bio_labels(self) -> None:
            if self.master.classifier_type is None:
                tk.messagebox.showwarning("No Classifier Loaded!", message = "No Classifier Loaded!")
                return
            bio_labels_window(self.master)

        def refresh1(self) -> None:
            self.classifier_option_menu.configure(values = sorted(os.listdir(self.master.classifier_dir)))

    class filter_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master

            grand_label = ctk.CTkButton(master = self, text = "Filter Images on a Class or set of classes:", hover = False, corner_radius = 0)
            grand_label.grid(padx = 1, pady = 3, column = 0, row = 0, sticky = "nsew", columnspan = 2)

            label = ctk.CTkLabel(master = self, 
                        text = "Images wil be cropped to the minimal rectangles containing \n"
                            "all pixels of the specified class(es) \n\n Note that filtered images will need new masks and classifer maps \n"
                            "(the old masks, etc. will not work)")
            label.grid(padx = 3, pady = 3, column = 0, row = 1, columnspan = 2)

            filter_list_label = ctk.CTkLabel(master = self, text = "Select Class numbers to filter on:")
            filter_list_label.grid(padx = 3, pady = 3, column = 0, row = 2)

            self.filter_list = self.filter_list_frame(self)
            self.filter_list.grid(row = 3, column = 0, padx = 3, pady = 3, rowspan = 5)

            label2 = ctk.CTkLabel(master = self, text = "Name of image folder to filter from:")
            label2.grid(padx = 3, pady = 3, column = 1, row = 2)

            def refresh2():
                self.select_image_folder.configure(values = sorted(os.listdir(self.master.image_directory)) )
            image_folder_options = sorted(os.listdir(self.master.image_directory)) 
            self.select_image_folder = ctk.CTkOptionMenu(master = self, 
                                                         variable = ctk.StringVar(value = "img"), 
                                                         values = image_folder_options) 
            self.select_image_folder.grid(column = 1, row = 3, padx = 3, pady = 3)
            self.select_image_folder.bind("<Enter>", lambda enter: refresh2())

            label2 = ctk.CTkLabel(master = self, text = "Name of output folder:")
            label2.grid(padx = 3, pady = 3, column = 1, row = 4)

            self.name_output = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "img_filtered_on_"))   
            self.name_output.grid(column = 1, row = 5, padx = 3, pady = 3)

            self.zero_checkbox = ctk.CTkCheckBox(master = self, 
                                                 text = "check to zero-out \n all non-class pixels", 
                                                 onvalue = True, 
                                                 offvalue = False)
            self.zero_checkbox.grid(column = 1, row = 6, padx = 3, pady = 3)

            label3 = ctk.CTkLabel(master = self, text = "Enter Padding to add to \n edges of filtered images (integers):")
            label3.grid(column = 1, row = 7, padx = 3, pady = 3)

            self.padding = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "5"))
            self.padding.grid(column = 1, row = 8, padx = 3, pady = 3)

            self.execute_button = ctk.CTkButton(master = self, text = "Run Filtering!", command = self.filter_images)
            self.execute_button.grid(column = 1, row = 9, padx = 3, pady = 3)

        def filter_images(self) -> None:
            if folder_checker(self.name_output.get()):
                return
            if self.master.classifier_type is None:
                tk.messagebox.showwarning("No Classifier Loaded!", message = "No Classifier Loaded!")
                return
            output_folder = self.master.image_directory + "/" + self.name_output.get().strip()
            
            zero_out = self.zero_checkbox.get()
            zero_helper = ""
            if zero_out is True:
                zero_helper = ", with all pixels not in selected classes set to zero in all channels."
            padding = int(self.padding.get())
            class_to_keep = self.filter_list.retrieve()
            if len(class_to_keep) == 0:
                tk.messagebox.showwarning("Warning!", message = "You must select at least one class to filter images on!")
                return
            if not overwrite_approval(output_folder, file_or_folder = "folder"):
                return
            class_map_folder = self.master.active_classifier_dir + "/classification_maps"
            image_folder = self.master.image_directory + "/" + self.select_image_folder.get()  
            

            slice_folder(class_to_keep, 
                                      class_map_folder, 
                                      image_folder, 
                                      output_folder, 
                                      padding = padding, 
                                      zero_out = zero_out)

            pixel_logger.info(f"""Using classifier {self.master.name}, filtered / cropped images in image folder = {image_folder}, 
                              on classes = {str(class_to_keep)}, exporting to = {output_folder}, padding = {str(padding)} {zero_helper}""")

        class filter_list_frame(ctk.CTkScrollableFrame):
            ### Will need to be initialized after the classifier has been chosen
            def __init__(self, master):
                super().__init__(master)
                self.master = master

            def initialize_with_classifier(self) -> None:
                try:
                    self.biological_class_labels = pd.read_csv(self.master.master.active_classifier_dir + "/biological_labels.csv")
                    self.from_labels = True
                except Exception:
                    try:
                        open_json = open(self.master.master.active_classifier_dir + f"/{self.master.master.name}_details.json", 
                                         'r', 
                                         encoding="utf-8")
                        loaded_json = open_json.read()
                        self.dictionary = json.loads(loaded_json)
                        open_json.close()
                        self.list_of_labels = [i for i in range(1,self.dictionary["number_of_classes"]+1)]
                        self.from_labels = False
                    except Exception:
                        tk.messagebox.showwarning("Warning!", 
                            message = "Classifier is corrupted (_details.json missing)! \n"
                                "Both the biological_labels.csv and _details.json is missing from this classifier. Please recreate classifier \n"
                                "or load a different classifier.")
                        return
                    
                if self.from_labels is True:
                    self.checkbox_list = []
                    for i in self.biological_class_labels["labels"].unique():
                        checkbox = ctk.CTkCheckBox(master = self, text = i, onvalue = i, offvalue = -1)
                        checkbox.grid(padx = 3, pady = 3)
                        self.checkbox_list.append(checkbox)

                else:
                    self.checkbox_list = []
                    for i in self.list_of_labels:
                        checkbox = ctk.CTkCheckBox(master = self, text = str(i), onvalue = i, offvalue = -1)
                        checkbox.grid(padx = 3, pady = 3)
                        self.checkbox_list.append(checkbox)

            def retrieve(self) -> list[str]:
                if self.from_labels is True:
                    labels_to_use = [i.get() for i in self.checkbox_list if i.get() != -1]
                    total_bool_array = np.zeros(len(self.biological_class_labels['labels']))
                    for i in labels_to_use:
                        boolean_array = (self.biological_class_labels['labels'] == i)
                        total_bool_array = (total_bool_array  + boolean_array).astype('bool')
                        
                    classes_to_use = list(self.biological_class_labels['class'][total_bool_array])
                else:
                    classes_to_use = [i.get() for i in self.checkbox_list if i.get() != -1]

                return classes_to_use

    class whole_class_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master

            label = ctk.CTkButton(master = self, text = "Analysis at the Class level:", hover = False, corner_radius = 0)
            label.grid(pady = 3, column = 0, row = 0, sticky = "nsew", padx = 1, columnspan = 2)

            selection_label = ctk.CTkLabel(master = self, text = "Select Classifier Masks to use for Class-level Analysis:")
            selection_label.grid(padx = 3, pady = 3, column = 0, row = 1)

            self.classifier_option_menu = ctk.CTkOptionMenu(master = self, 
                                                values = ["classification_maps","merged_classification_maps"], 
                                                variable = ctk.StringVar())
            self.classifier_option_menu.grid(padx = 3, pady = 3, column = 0, row = 3)

            self.create_button = ctk.CTkButton(master = self, text = "Create Measurements!", command = self.create)
            self.create_button.grid(padx = 3, pady = 3, column = 0, row = 4)
            self.create_button.configure(state = "disabled")

            self.add_panel_button = ctk.CTkButton(master = self, text = "Add Panel / Metadata!", command = self.add_panel)
            self.add_panel_button.grid(padx = 3, pady = 3, column = 0, row = 5)

            def refresh_panel_button(enter = ""):
                try:
                    if (not os.path.exists(str(self.master.active_classifier_dir) + "/Whole_class_analysis")) and (self.add_panel_button.cget('state') == "normal"):
                        self.add_panel_button.configure(state = "disabled")
                    elif self.add_panel_button.cget("state") == "disabled":
                        self.add_panel_button.configure(state = "normal")
                except AttributeError:
                    self.add_panel_button.configure(state = "disabled")

            self.add_panel_button.bind("<Enter>", refresh_panel_button)
            refresh_panel_button()


            self.launch = ctk.CTkButton(master = self, text = "Launch Analysis!", command = self.launch_analysis)
            self.launch.grid(padx = 3, pady = 3, column = 0, row = 6)

            def refresh_launch_button(enter = ""):
                try:
                    if (not os.path.exists(str(self.master.active_classifier_dir) + "/Whole_class_analysis/Analysis_panel.csv")) and \
                       (not os.path.exists(str(self.master.active_classifier_dir) + "/Whole_class_analysis/metadata.csv")) and \
                        (self.launch.cget('state') == "normal"):
                        
                        self.launch.configure(state = "disabled")
                    elif self.launch.cget('state') == "disabled":
                        self.launch.configure(state = "normal")
                except AttributeError:
                    self.launch.configure(state = "disabled")


            self.launch.bind("<Enter>", refresh_launch_button)
            refresh_launch_button()

        def load_classifier_activate_buttons(self):
            ''''''
            self.create_button.configure(state = "normal")

        def create(self) -> None:
            if self.master.classifier_type is None:
                tk.messagebox.showwarning("No Classifier Loaded!", message = "No Classifier Loaded!")
                return
            if self.classifier_option_menu.get() == "":
                tk.messagebox.showwarning("Error", message = "Select what kind of classification map is being used!")
                return
            if not overwrite_approval(self.master.active_classifier_dir + "/Whole_class_analysis", file_or_folder = "folder", custom_message = "This step"
                                      "will overwrite previously calculated intensity/regionprop \n files for the whole-class analysis of this classifier, if image filenames match -- "
                                      "\nDo you wish to proceed?"):
                return
            
            '''
            if ((self.classifier_option_menu.get() == "merged_classification_maps") 
                    and (not os.path.exists(self.master.active_classifier_dir + "/merged_classification_maps"))):
                merge_folder(self.master.active_classifier_dir + "/classification_maps", 
                             pd.read_csv(self.master.active_classifier_dir + "/biological_labels.csv"))
            '''

            RegionMeasurement(self.master, 
                              self.master.Experiment_object, 
                              input_masks_dir = (self.master.active_classifier_dir + "/" + self.classifier_option_menu.get()))

        def launch_analysis(self) -> None:  
            whole_class_analysis_window(self)
            pixel_logger.info("""Entered Whole class analysis""") 

        def add_panel(self) -> None:
            try:                ## first read from classifier directory
                panel_file = pd.read_csv(self.master.active_classifier_dir + "/Whole_class_analysis/Analysis_panel.csv")
            except FileNotFoundError:
                path_to_proj = Path(self.master.main_directory)  ## change to the appropriate path
                analysis_panel_files = path_to_proj.rglob("*Analysis_panel.csv")  
                        ## because recursive rglob looks at the highest folder levels first, 
                        # it will find any saved in the Analyses folder
                try:
                    to_use = next(analysis_panel_files)
                    panel_file = pd.read_csv(to_use)
                except Exception:
                    panel_file = None

            try: 
                        ## first read from classifier directory if it already exists 
                        # (aka, panel file has already been loaded for this whole class analysis)
                metadata = pd.read_csv(self.master.active_classifier_dir + "/Whole_class_analysis/metadata.csv")
            except FileNotFoundError:
                path_to_proj = Path(self.master.main_directory)  ## change to the appropriate path
                analysis_panel_files = path_to_proj.rglob("*metadata.csv")
                try:
                    to_use = next(analysis_panel_files)
                    metadata = pd.read_csv(to_use)
                except Exception:
                    metadata = None

            if panel_file is None:
                ## make initial panel file:
                fcs_files  = sorted(os.listdir(self.master.active_classifier_dir + "/Whole_class_analysis/intensities"))
                dataframe1 = pd.read_csv(self.master.active_classifier_dir + "/Whole_class_analysis/intensities/" + fcs_files[0])
                try:
                    dataframe1 = dataframe1.drop('Object', axis = 1)
                except KeyError:
                    pass
                self.Analysis_panel = pd.DataFrame()
                self.Analysis_panel['fcs_colnames'] = dataframe1.columns
                self.Analysis_panel['antigen'] = dataframe1.columns
                self.Analysis_panel['marker_class'] = "none"
                try:
                    self.Analysis_panel = self.Analysis_panel.drop("Object", axis = 0) 
                except KeyError:
                    pass
                panel_file = self.Analysis_panel

                ## make metadata file:
                file_list = sorted(os.listdir(self.master.active_classifier_dir + "/Whole_class_analysis/intensities"))
                metadata = pd.DataFrame()
                metadata['file_name']  = file_list
                metadata['sample_id'] = metadata.reset_index()['index']
                metadata['patient_id'] = 'batch'      # manually set later
                metadata['condition'] = 'treatment_VS_control'       # manually set later

            ## now, launch the tables:
            table_launcher = TableLaunchAnalysis(1, 1,  
                                self.master.active_classifier_dir + "/Whole_class_analysis",
                                panel_file, table_type = "Analysis_panel.csv", 
                                experiment = None, 
                                tab = None, 
                                favor_table = True, 
                                logger = pixel_logger, 
                                alt_dir = self.master.main_directory + "/Analyses")
            table_launcher.add_table(1, 1, 
                                     self.master.active_classifier_dir + "/Whole_class_analysis", 
                                     metadata, "metadata", 
                                     favor_table = True)

    class merge_class_masks_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            grand_label = ctk.CTkButton(master = self, 
                                        text = "Extend Cell Masks with Classifier to generate larger masks:", 
                                        hover = False, 
                                        corner_radius = 0)
            grand_label.grid(row = 0, column = 0, pady = 3, columnspan = 2, sticky = "nsew", padx = 1)

            label = ctk.CTkLabel(master = self, text = "Select Masks folder:")
            label.grid(row = 1, column = 0, padx = 3, pady = 3)

            def refresh3():
                masks_options = sorted(os.listdir(self.master.main_directory + "/masks"))
                self.mask_option_menu.configure(values = masks_options)

            masks_options = sorted(os.listdir(self.master.main_directory + "/masks"))
            self.mask_option_menu = ctk.CTkOptionMenu(master = self, values = masks_options, variable = ctk.StringVar(value = ""))
            self.mask_option_menu.grid(padx = 3, pady = 3, column = 1, row = 1)
            self.mask_option_menu.bind("<Enter>", lambda enter: refresh3())

            ## default to only using the merged maps (since merging REQUIRES classy masks, and classy masks do the merging simultaneously 
            # --> just use the merging labels for everything

            label3 = ctk.CTkLabel(master = self, text = "Select Classy Masks folder:")
            label3.grid(row = 3, column = 0, padx = 3, pady = 3)

            def refresh4():
                classy_masks_options = [i for i in sorted(os.listdir(self.master.main_directory + "/classy_masks")) if i[-4:] != '.csv']  
                self.classy_mask_option_menu.configure(values = classy_masks_options)

            classy_masks_options = [i for i in sorted(os.listdir(self.master.main_directory + "/classy_masks")) if i[-4:] != '.csv']                                                                                         
            self.classy_mask_option_menu = ctk.CTkOptionMenu(master = self, values = classy_masks_options, variable = ctk.StringVar(value = ""))
            self.classy_mask_option_menu.grid(padx = 3, pady = 3, column = 1, row = 3)
            self.classy_mask_option_menu.bind("<Enter>", lambda enter: refresh4())

            label3 = ctk.CTkLabel(master = self, 
                            text = "Choose Output folder name \n (will be generated in the masks folder \n as a derived mask):")
            label3.grid(row = 5, column = 0, padx = 3, pady = 3)

            self.output_name = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = ""))
            self.output_name.grid(row = 5, column = 1, padx = 3, pady = 3)

            label5 = ctk.CTkLabel(master = self, text = "Set connectivity:")
            label5.grid(row = 6, column = 0, padx = 3, pady = 3)

            self.connectivity = ctk.CTkOptionMenu(master = self, values = ["1","2"], variable = ctk.StringVar(value = "2"))
            self.connectivity.grid(padx = 3, pady = 3, column = 1, row = 6)

            self.do_merging_button = ctk.CTkButton(master = self, text = "Do Merging!", command = self.run_merging)
            self.do_merging_button.grid(padx = 3, pady = 3, column = 1, row = 8) 

            selection_label = ctk.CTkLabel(master = self, text = "Select classes in the classification \n map to merge with masks:")
            selection_label.grid(padx = 3, pady = 3, column = 0, row = 7) 

            self.select_table = self.ignore_frame(self)
            self.select_table.grid(padx = 3, pady = 3, column = 0, row = 8) 

        def loaded_classifier(self, classifier_type) -> None:
            self.classifier_type = classifier_type
            self.select_table.init_with_classifier()

        def run_merging(self) -> None:
            if self.master.classifier_type is None:
                tk.messagebox.showwarning("No Classifier Loaded!", message = "No Classifier Loaded!")
                return
            if self.mask_option_menu.get() == "":
                tk.messagebox.showwarning("Warning!", message = "You must select a mask folder!")
                return
            if self.classy_mask_option_menu.get() == "":
                tk.messagebox.showwarning("Warning!", message = "You must select a classy mask folder!")
                return
            if folder_checker(self.output_name.get()):
                return
            merge_list = self.select_table.retrieve()
            if len(merge_list) == 0:
                tk.messagebox.showwarning("Warning!", message = "You must select at least one class to extend on!")
                return

            connectivity = int(self.connectivity.get())

            output_directory_folder = self.master.main_directory + "/masks/" + self.output_name.get().strip()
            if not overwrite_approval(output_directory_folder, file_or_folder = "folder"):
                return
            
            masks_folder = self.master.main_directory + "/masks/" + self.mask_option_menu.get()    
            classification_folder = self.master.active_classifier_dir + "/merged_classification_maps"
            classy_mask_folder = self.master.main_directory + "/classy_masks/" + self.classy_mask_option_menu.get()

            classy_mask_secondary_folder = classy_mask_folder + "/secondary_masks"
            classy_mask_folder = classy_mask_folder + "/primary_masks"
            try:
                os.listdir(classy_mask_secondary_folder)       ## if secondary mask folder exists, use that
                classy_mask_folder = classy_mask_secondary_folder
            except FileNotFoundError:
                pass


            extend_masks_folder(classification_folder, 
                                            masks_folder, 
                                            classy_mask_folder, 
                                            output_directory_folder, 
                                            connectivity = connectivity,
                                            merge_list = merge_list) 
            
            pixel_logger.info("Merged Masks & Pixel classifier: \n"
                              f"masks_folder = {masks_folder}, \n"
                              f"classy_masks_folder = {classy_mask_folder}, \n"
                              f"classification_maps folder = {classification_folder}, \n"
                              f"output_masks folder = {output_directory_folder}, \n"
                              f"connectivity = {str(connectivity)}, \n"
                              f"merge_list (boolean indicates which classes, in order, were merged) = {str(merge_list)}")
            
        class ignore_frame(ctk.CTkScrollableFrame): 
            def __init__(self, master):
                super().__init__(master)
                self.master = master
                self.configure(height = 50)

            def init_with_classifier(self) -> None:
                bio_path = self.master.master.active_classifier_dir + "/biological_labels.csv"
                try:
                    self.table = pd.read_csv(bio_path)
                except FileNotFoundError:
                    tk.messagebox.showwarning("Warning!", message = "The biological labels for the classifier or classy masks are missing! \n"
                                              "DO NOT attempt a mask merging until this is fixed & the classifier reloaded!")
                    return

                self.checkbox_list = []
                length_list = []
                for i,ii in zip(self.table['merging'], self.table['labels']):
                    label_text = f'{ii}:{i}'
                    length_list.append(len(label_text))
                    label = ctk.CTkLabel(master = self, text = str(label_text), width = 45)
                    label.grid(column = 0, row = i + 1)
                    checkbox = ctk.CTkCheckBox(master = self, text = '', onvalue = True, offvalue = False, width = 35)
                    checkbox.grid(column = 1, row = i + 1)
                    self.checkbox_list.append(checkbox)

                max_width = np.max(np.array(length_list))
                self.configure(width = (max_width*10) + 10, height = 50)

            def retrieve(self) -> list[int]:
                return list(self.table['merging'].copy()[np.array([i.get() for i in self.checkbox_list]).astype('bool')])

    class classify_cells_frame(ctk.CTkFrame):
        '''
        Classy Mask Generation!        
        '''
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            self.classifier_type = self.master.classifier_type

            grand_label = ctk.CTkButton(master = self, text = "Make classy cell masks!", hover = False, corner_radius = 0)
            grand_label.grid(pady = 3, column = 0, row = 0, columnspan = 2, sticky = "nsew", padx = 1)

            label = ctk.CTkLabel(master = self, text = "Choose Masks folder to classify:")
            label.grid(padx = 3, pady = 3, column = 0, row = 1)

            def refresh5():
                masks_options = sorted(os.listdir(self.master.main_directory + "/masks"))
                self.mask_option_menu.configure(values = masks_options)

            masks_options = sorted(os.listdir(self.master.main_directory + "/masks"))
            self.mask_option_menu = ctk.CTkOptionMenu(master = self, values = masks_options, variable = ctk.StringVar(value = ""))
            self.mask_option_menu.grid(padx = 3, pady = 3, column = 1, row = 1)
            self.mask_option_menu.bind("<Enter>", lambda enter: refresh5())

            label2 = ctk.CTkLabel(master = self, text = "Select Classifier's ouput to use \n (only for FlowSOM method):")
            label2.grid(row = 2, column = 0, padx = 3, pady = 3)              

            classifier_options = ["classification_maps","merged_classification_maps"]   ## only want folder names
            self.classifier_option_menu = ctk.CTkOptionMenu(master = self, values = classifier_options, variable = ctk.StringVar(value = "classification_maps"))
            self.classifier_option_menu.grid(padx = 3, pady = 3, column = 1, row = 2)

            self.merge_frame = self.biological_labels(self)

            self.flowsom_training = self.flowsom_training_frame(self)
            self.flowsom_training.grid(row = 5, column = 1, padx = 3, pady = 3)

            self.radioframe_do_secondary_flowsom = self.radio_option_frame(self)
            self.radioframe_do_secondary_flowsom.grid(row = 4, column = 1, padx = 3, pady = 3)

            self.accept_button = ctk.CTkButton(master = self, text = "Do Mask Classification!", command = self.do_classy_masks)
            self.accept_button.grid(row = 6, column = 1, padx = 3, pady = 3)

        def loaded_classifier(self) -> None:
            try:
                open_json = open(self.master.active_classifier_dir + f"/{self.master.name}_details.json", 'r' , encoding="utf-8")
                loaded_json = open_json.read()
                self.dictionary = json.loads(loaded_json)
                open_json.close()
            except FileNotFoundError:
                warning_window("Warning! could not load .json file with the details of this classifier! \n" 
                                "Have you manually renamed the classifier or the .json file?")

        class biological_labels:
            '''
            '''
            ### Will need to be initialized after the classifier has been chosen
            def __init__(self, master):
                self.master = master

            def initialize_with_classifier(self) -> None:
                try:
                    self.biological_class_labels = pd.read_csv(self.master.master.active_classifier_dir + "/biological_labels.csv")
                except FileNotFoundError:
                    self.biological_class_labels = pd.DataFrame()
                    self.master.classifier_option_menu.set("classification_maps")
                    self.master.classifier_option_menu.configure(state = "disabled")
                    self.master.radioframe_do_secondary_flowsom.radio_SOM.invoke()
                    self.master.radioframe_do_secondary_flowsom.radio_SOM.configure(state = "disabled")

                    number_of_classes = self.master.dictionary["number_of_classes"]
                    self.biological_class_labels['labels'] = [i + 1 for i in range(0, number_of_classes)]
                    self.biological_class_labels['class'] = self.biological_class_labels['labels']
                    self.biological_class_labels['merging'] = self.biological_class_labels['labels']

            def retrieve(self) -> pd.DataFrame:
                return self.biological_class_labels
            
        class radio_option_frame(ctk.CTkFrame):
            def __init__(self, master):
                super().__init__(master)
                self.master = master
                grand_label = ctk.CTkLabel(master = self, text = "Do cell classification by Mode \n or by secondary FlowSOM:")
                grand_label.grid(row = 0, column = 0, columnspan = 2, padx = 3, pady = 3)

                self.radio_variable = ctk.StringVar(value = "Mode")
                self.radio_mode = ctk.CTkRadioButton(master = self, 
                                                     text = "Mode", 
                                                     variable = self.radio_variable, 
                                                     value = "Mode", 
                                                     command = self.master.flowsom_training.self_destroy)
                self.radio_mode.grid(row = 1, column = 0, padx = 3, pady = 3)

                self.radio_SOM = ctk.CTkRadioButton(master = self, 
                                                    text = "flowSOM", 
                                                    variable = self.radio_variable, 
                                                    value = "SOM", 
                                                    command = self.master.flowsom_training.initialize)
                self.radio_SOM.grid(row = 1, column = 1, padx = 3, pady = 3)

        class flowsom_training_frame(ctk.CTkFrame):
            def __init__(self, master):
                super().__init__(master)
                self.master = master
                self.widget_list = None

            def initialize(self) -> None:
                self.grand_label = ctk.CTkLabel(master = self, text = "FlowSOM options:")
                self.grand_label.grid(row = 0, column = 0)

                self.label1 = ctk.CTkLabel(master = self, text = "Number of Metaclusters:")
                self.label1.grid(row = 1, column = 0)

                self.n_clusters_entry = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "10"), width = 35)
                self.n_clusters_entry.grid(row = 1, column = 1)

                self.label2 = ctk.CTkLabel(master = self, text = "XY dims:")
                self.label2.grid(row = 2, column = 0)

                self.XY_entry = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "5"), width = 35)
                self.XY_entry.grid(row = 2, column = 1)

                self.label3 = ctk.CTkLabel(master = self, text = "Training Iterations:")
                self.label3.grid(row = 3, column = 0)

                self.rlen = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "50"), width = 35)
                self.rlen.grid(row = 3, column = 1)

                self.label4 = ctk.CTkLabel(master = self, text = "Random seed:")
                self.label4.grid(row = 4, column = 0)

                self.seed_entry = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "42"), width = 35)
                self.seed_entry.grid(row = 4, column = 1)
                self.widget_list = [self.grand_label, self.label1, self.n_clusters_entry, self.label2, self.XY_entry, self.label3, self.rlen, self.label4, self.seed_entry]

            def self_destroy(self) -> None:
                [i.destroy() for i in self.widget_list]
                
        def do_classy_masks(self) -> None:
            if self.master.classifier_type is None:
                tk.messagebox.showwarning("Warning!", message = "No Classifier Loaded!")
                return
            masks_folder = self.mask_option_menu.get()
            if masks_folder == "":
                tk.messagebox.showwarning("Warning!", message = "You must select a masks folder!")
                return 
            
            mode_or_SOM = self.radioframe_do_secondary_flowsom.radio_variable.get()
            if mode_or_SOM == "Mode":
                classifier_masks_folder = self.master.active_classifier_dir + "/classification_maps"
            else:
                classifier_masks_folder = self.master.active_classifier_dir + f"/{self.classifier_option_menu.get()}"

            masks_folder = self.master.main_directory + "/masks/" + masks_folder

            ## tests:
            classifier_files = sorted(os.listdir(classifier_masks_folder))
            masks_files = sorted(os.listdir(masks_folder))
            if len(classifier_files) == len(masks_files):
                not_shared_names = [i for i,ii in zip(classifier_files,masks_files) if i != ii]
                if len(not_shared_names) > 0:
                    tk.messagebox.showwarning("Warning", 
                        message = "The names of the files in the classifier maps folder and the masks folder do not match!")
                    return
            else:
                tk.messagebox.showwarning("Warning", 
                    message = "The number of masks and the number of pixel classification maps do not match! \n" 
                            "Did you only do part of the classifier prediction, or only segmented some of your images?")
                return
            
            output_folder = f'''{self.master.main_directory}/classy_masks/{self.master.name}_{self.mask_option_menu.get()}'''
            if not overwrite_approval(output_folder, file_or_folder = "folder"):
                return

            metadata = self.merge_frame.retrieve()
            if self.classifier_option_menu.get() == "merged_classification_maps":
                number_of_classes = len(metadata['merging'].unique())
            else:
                number_of_classes = len(metadata)

            metadata.to_csv(self.master.active_classifier_dir + "/biological_labels.csv" , index = False)  
            bio_dict = {}
            for i,ii in zip(metadata['merging'].astype('str'), metadata['labels']):
                bio_dict[i] = ii
            bio_dict['1'] = 'unassigned'
            
            if not os.path.exists(output_folder):
                os.mkdir(output_folder)
            output_folder = output_folder + "/primary_masks"

            self.classy_mask_name = f'{self.master.name}_{self.mask_option_menu.get()}'

            if mode_or_SOM == "Mode":
                cell_classes_df = mode_classify_folder(masks_folder, 
                                                            classifier_masks_folder, 
                                                            output_folder, 
                                                            merging_table = metadata)
                cell_classes_df['labels'] = cell_classes_df['classification'].astype('str').replace(bio_dict)
                cell_classes_df.to_csv(f'{self.master.main_directory}/classy_masks/{self.classy_mask_name}/{self.classy_mask_name}_cell_classes.csv', 
                                       index = False)
                pixel_logger.info("Made Classy Masks, using the simple Mode based classification, with the following parameters: \n"
                                  f"masks folder = {masks_folder}, \n"
                                  f"classification maps folder = {classifier_masks_folder}, \n"
                                  f"output folder = {output_folder}, \n"
                                  f"merging_table = {str(metadata)}")
            else:
                try:
                    number_of_classes = int(number_of_classes)
                    XY_dim = int(self.flowsom_training.XY_entry.get())
                    n_clusters = int(self.flowsom_training.n_clusters_entry.get())
                    seed =  int(self.flowsom_training.seed_entry.get())
                    rlen = int(self.flowsom_training.rlen.get())
                except ValueError:
                    tk.messagebox.showwarning("XY dimensions, number of clusters, training iterations, and random seed must all be integers, \n" 
                                              "but one of the provided values was not an integer!")
                    return
                
                if not os.path.exists(self.master.active_classifier_dir + "/merged_classification_maps"):
                    os.mkdir(self.master.active_classifier_dir + "/merged_classification_maps")
                
                for i in sorted(os.listdir(classifier_masks_folder)):
                    merged_class = merge_classes(tf.imread(classifier_masks_folder + "/" + i), metadata)
                    tf.imwrite(self.master.active_classifier_dir + "/merged_classification_maps/" + i, 
                               merged_class.astype('int'))
                to_use_classifier_masks_folder = self.master.active_classifier_dir + "/" + self.classifier_option_menu.get()

                fs, anndata_df = secondary_flowsom(masks_folder, 
                                                to_use_classifier_masks_folder, 
                                                number_of_classes = number_of_classes,
                                                XY_dim = XY_dim, 
                                                rlen = rlen, 
                                                n_clusters = n_clusters, 
                                                seed = seed) 
                
                cell_classes_df = classify_from_secondary_flowsom(masks_folder, output_folder, fs)
                cell_classes_df['labels'] = 'unknown (SOM first step)'
                cell_classes_df.to_csv(f'{self.master.main_directory}/classy_masks/{self.classy_mask_name}/{self.classy_mask_name}_cell_classes.csv',
                                       index = False)

                self.output_path = f'{self.master.main_directory}/classy_masks/{self.classy_mask_name}/{self.classy_mask_name}_heatmap.png'
                panel = self.master.Experiment_object.panel
                plot, _ = plot_pixel_heatmap(output_folder, 
                                            self.dictionary["img_directory"],
                                            list(panel[panel['keep'] == 1]['name']), 
                                            panel = panel)
                plot.figure.suptitle(self.classy_mask_name)
                plot.figure.savefig(self.output_path)
                pixel_logger.info("MadeClassy Masks, using the 2ndary FlowSOM based classification, with the following parameters: \n"
                                  f"masks folder = {masks_folder}, \n"
                                  f"classification maps folder = {classifier_masks_folder}, \n"
                                  f"output foldre = {output_folder}, \n"
                                  f"merging_table = {str(metadata)}, \n"
                                  f"XY_dim = {str(XY_dim)}, \n"
                                  f"n_clusters = {str(n_clusters)}, \n"
                                  f"seed = {str(seed)}")
                self.output_folder = output_folder
                Secondary_FlowSOM_Analysis_window(self, heatmap_path = self.output_path, fs = fs)

class RegionMeasurement(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    This object is copied from the ImageAnalysisWidgets file (with edits)
    '''
    def __init__(self, master, experiment, input_masks_dir: str): 
        #### Set up the buttons / options / entry fields in the window      
        super().__init__(master)
        self.master = master
        self.input_masks_dir = input_masks_dir
        self.title('Region Measurement Options: Whole class measurements')
        label1 = ctk.CTkLabel(master = self, text = "Choose the intensity measurement option (within each mask region):")
        label1.grid(column = 0, row = 0, padx = 10, pady = 10)
        self.intensity_options = ctk.CTkOptionMenu(master = self, values = ["mean","median","sum","min","max","std","var"])
        self.intensity_options.grid(column = 1, row = 0, padx = 10, pady = 10)

        self.re_do = ctk.CTkCheckBox(master= self, 
                                     text = "Leave Check to redo previously calculated measurements. \n"
                                       "Un-check to only do measurements if they do not alreayd exist for a given image.", 
                                     onvalue = True, offvalue = False)
        self.re_do.select()

        label_8 = ctk.CTkLabel(self, text = "Select an image folder from which measurements will be taken:")
        label_8.grid(column = 0, row = 2)

        def refresh7():
            self.image_folders = sorted(os.listdir(self.master.Experiment_object.directory_object.img_dir))
            self.image_folder.configure(values = self.image_folders)

        self.image_folders = sorted(os.listdir(self.master.Experiment_object.directory_object.img_dir))
        self.image_folder = ctk.CTkOptionMenu(self, values = self.image_folders, variable = ctk.StringVar(value = "img"))
        self.image_folder.grid(column = 1, row = 2, padx = 5, pady = 5)
        self.image_folder.bind("<Enter>", lambda enter: refresh7())

        accept_values = ctk.CTkButton(master = self, text = "Accept choices and proceed", command = lambda: self.read_values(experiment))
        accept_values.grid(padx = 10, pady = 10)

        self.after(200, lambda: self.focus())
        
    def read_values(self, experiment_class) -> None:
        ### Read in the values and return it to the experiment
        experiment_class.int_opt = self.intensity_options.get() 

        output_dir = self.master.active_classifier_dir + "/Whole_class_analysis" 
        
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)

        experiment_class.make_segmentation_measurements(re_do = self.re_do.get(), 
                                        input_img_folder = (self.master.Experiment_object.directory_object.img_dir + "/" + self.image_folder.get()),
                                        input_mask_folder = (self.input_masks_dir),
                                        output_intensities_folder = output_dir + "/intensities",
                                        output_regions_folder = output_dir + "/regionprops")  
        
        pixel_logger.info(f"Did Region Measurements for whole class analysis into the directory = {output_dir} \n"
                          f"with the following settings: aggregation stat = {experiment_class.int_opt}")  
        self.destroy()

class Secondary_FlowSOM_Analysis_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    '''
    def __init__(self, master, heatmap_path: str, fs): 
        super().__init__(master)
        self.master = master
        self.fs = fs
        self.n_clusters = int(self.master.flowsom_training.n_clusters_entry.get())
        self.active_classifier_dir = self.master.output_folder
        self.image_folder = self.master.dictionary['img_directory']
        self.heatmap_path = heatmap_path

        self.disp = display_image_button(self, PALMETTO_BUG_homedir + "/Assets/Capture2.png")
        self.disp.save_and_display(image = heatmap_path)         ## TODO: simplify by moving path into line above (then test)
        self.disp.grid(column = 0, row = 0, rowspan = 5, padx = 3, pady = 3)

        label_napari = ctk.CTkLabel(master = self, text = "Select a mask to view in Napari")
        label_napari.grid(row = 0, column = 1, padx = 3, pady = 3)

        napari_options = ctk.CTkOptionMenu(master = self, 
                                           values = sorted(os.listdir(self.image_folder)), 
                                           variable = ctk.StringVar(value = ""), 
                                           command = self.napari_launch)
        napari_options.grid(row = 1, column = 1, padx = 3, pady = 3)

        heatmap_label = ctk.CTkLabel(master = self, text = "Run a new heatmap with selected markers (instead of all markers)")
        heatmap_label.grid(row = 3, column = 1, padx = 3, pady = 3)

        self.heatmap_array = ctk.CTkScrollableFrame(master = self)
        self.heatmap_array.grid(row = 4, column = 1, padx = 3, pady = 3)

        self.checkbox_list = []
        for i in self.master.master.Experiment_object.panel['name'][self.master.master.Experiment_object.panel['keep'] == 1]:
            checkbox = ctk.CTkCheckBox(master = self.heatmap_array, text = i, onvalue = True, offvalue = False)
            checkbox.select()
            checkbox.grid(padx = 3, pady = 1)
            self.checkbox_list.append(checkbox)

        redo_heatmap = ctk.CTkButton(master = self, text = "Plot Heatmap", command = self.new_heatmap)
        redo_heatmap.grid(row = 5, column = 1, padx = 3, pady = 3)

        label4 = ctk.CTkLabel(master = self, text = "The Biological labels for the 2ndary FlowSOM:")
        label4.grid(row = 0, rowspan = 3, column = 3, padx = 3, pady = 3)

        self.primary_labels = self.primary_bio_labels(self)
        self.primary_labels.initialize_with_classifier(state = 'disabled')

        self.secondary_labels = self.primary_bio_labels(self)
        self.secondary_labels.grid(row = 3, column = 3, padx = 3, pady = 3)
        self.secondary_labels.initialize_with_classifier(blank_number = self.n_clusters, 
                                                         blank_options = self.primary_labels.biological_class_labels)

        self.primary_labels.destroy()

        self.radio_f = self.radio_button_frame(self)
        self.radio_f.grid(column = 3, row = 4, padx = 3, pady = 3)

        button = ctk.CTkButton(master = self, text = "Label the Secondary FlowSOM", command = self.run_labeling)
        button.grid(column = 3, row = 5, padx = 3, pady = 3)

        self.after(200, self.focus())

    class radio_button_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master

            self.radio_out = ctk.StringVar(value = "default")

            self.radio_default = ctk.CTkRadioButton(master = self, 
                                                    variable = self.radio_out, 
                                                    value = "default", 
                                                    text = "2ndary labels limited \n by classifer labels", 
                                                    command = lambda: self.master.toggle_secondary_labels(self.radio_out.get()))
            self.radio_default.grid(padx = 3, pady = 3, row = 0, column = 0)

            self.radio_custom = ctk.CTkRadioButton(master = self, 
                                                   variable = self.radio_out, value = "custom",
                                                   text = "custom 2ndary labels. \n DO NOT USE with mask merging!", 
                                                   command = lambda: self.master.toggle_secondary_labels(self.radio_out.get()))
            self.radio_custom.grid(padx = 3, pady = 3, row = 0, column = 1)

    def toggle_secondary_labels(self, choice: str) -> None:
        if choice == "custom":
            current_state = self.secondary_labels.retrieve()
            self.secondary_labels.destroy()
            self.secondary_labels = self.primary_bio_labels(self)
            self.secondary_labels.grid(row = 3, column = 3, padx = 3, pady = 3)
            self.secondary_labels.initialize_with_classifier(blank_number = self.n_clusters, 
                                                             blank_options = current_state, 
                                                             still_do_entries = True)
        else:
            self.secondary_labels.destroy()
            self.secondary_labels = self.primary_bio_labels(self)
            self.secondary_labels.grid(row = 3, column = 3, padx = 3, pady = 3)
            self.secondary_labels.initialize_with_classifier(blank_number = self.n_clusters, 
                                                             blank_options = self.primary_labels.biological_class_labels)

    def napari_launch(self, image_choice: str) -> None:
        ''''''
        mask_path = self.master.output_folder + "/" + image_choice
        mask = tf.imread(mask_path).astype('int')
        image_path = self.image_folder  + "/" + image_choice
        image = tf.imread(image_path)
        if mask.shape[0] != image.shape[1]:
            mask = mask.T
        import multiprocessing
        p = multiprocessing.Process(target = run_napari, args = (image, mask))
        p.start()

    def new_heatmap(self) -> None:
        type_array = np.array([i.get() for i in self.checkbox_list])
        if type_array.sum() < 2:
            tk.messagebox.showwarning("Warning", 
                        message = "You must have at least two channels selected to create a new heatmap!")
            self.focus()
            return
        panel = self.master.master.Experiment_object.panel
        plot, _ = plot_pixel_heatmap(self.master.output_folder, 
                                    self.master.dictionary["img_directory"],
                                    list(panel[panel['keep'] == 1].loc[type_array,'name']), 
                                    panel = panel)
        plot.figure.suptitle(self.master.classy_mask_name)
        plot.figure.savefig(self.master.output_path)
        pixel_logger.info(f"""Changed heatmap for 2ndary FlowSOM by channels-to-use array: {str(type_array)}""")
        self.disp.save_and_display(image = self.heatmap_path)
        
    def run_labeling(self) -> None:
        '''
        Needs to:
            -- save merging table
            -- save a parallel folder of merged classy masks (which takes precedence over the originals later on with merging)
            -- save a merged form of the csv with the per-cell classifications
        '''
        one_folder_up = self.master.output_folder[:self.master.output_folder.rfind("/")]
        classifier_name = one_folder_up[(one_folder_up.rfind("/") + 1):]

        merging_table = self.secondary_labels.retrieve()
        if (merging_table == "").sum().sum() > 0:
            choice = tk.messagebox.askyesno("One of labeling fields was left blank! Are you sure you want to continue?")
            self.focus()
            if not choice:
                return
        merging_table.to_csv(one_folder_up + "/secondary_merging.csv", index = False)

        read_in = pd.read_csv(one_folder_up + "/" + classifier_name + "_cell_classes.csv")
        replace_dict = {}
        for i,ii in zip(merging_table['class'].astype('str'), merging_table['merging'].astype('str')):
            replace_dict[i] = ii

        replace_dict_labels = {}
        for i,ii in zip(merging_table['class'].astype('str'), merging_table['labels'].astype('str')):
            replace_dict_labels[i] = ii
        merged_classifications_per_cell = pd.DataFrame()
        merged_classifications_per_cell["classification"] = read_in["classification"].astype('str').replace(replace_dict)
        merged_classifications_per_cell["labels"] = read_in["classification"].astype('str').replace(replace_dict_labels)
        merged_classifications_per_cell.to_csv(one_folder_up + "/secondary_cell_classification.csv", index = False)

        image_path_list = ["".join([self.master.output_folder,"/",i])  for i in sorted(os.listdir(self.master.output_folder))]
        write_path_list = ["".join([one_folder_up,"/secondary_masks/",i])  for i in sorted(os.listdir(self.master.output_folder))]
        if not os.path.exists(one_folder_up + "/secondary_masks/"):
            os.mkdir(one_folder_up + "/secondary_masks/")

        for i,ii in zip(image_path_list, write_path_list):
            mask = tf.imread(i).astype('int')
            new_mask = merge_classes(mask, merging_table)
            tf.imwrite(ii, new_mask)

        pixel_logger.info("Merged Secondary FlowSOM output into biological labels & secondary masks: \n"
                          f"{str(merged_classifications_per_cell)}")
        self.destroy()

    class primary_bio_labels(ctk.CTkScrollableFrame):
            '''
            this frame is intended to contain all the class #, their biological labels, & the putative merging labels
            '''
            ### Will need to be initialized after the classifier has been chosen
            def __init__(self, master):
                super().__init__(master)
                self.master = master

            def initialize_with_classifier(self, 
                                           blank_number: int = 0, 
                                           blank_options: pd.DataFrame = None, 
                                           state: str = 'normal', 
                                           still_do_entries: bool = False) -> None:
                if blank_number == 0:
                    try:
                        self.biological_class_labels = pd.read_csv(self.master.master.master.active_classifier_dir + "/biological_labels.csv")
                    except FileNotFoundError:
                        tk.messagebox.showwarning("Warning!", 
                            message = "The biological_labels.csv is missing from this classifier! \n"
                                      "Please create Biological Labels for the classes before classifying cell masks")
                        return
                    else:
                        self.biological_class_labels['labels'] = self.biological_class_labels['labels'].astype('str')
                        self.from_labels = True
                else:
                    self.from_labels = False
                    
                if self.from_labels is True:
                    unique_names = self.biological_class_labels["labels"].unique()
                    unique_dict = {str(ii):(i + 1) for i,ii in enumerate(unique_names)}
                    unique_dict['background'] = 0
                    self.labels = [i for i in self.biological_class_labels["labels"].values]
                    self.entry_list = []
                    counter = 0
                    for i in self.labels:
                        i = i
                        label = ctk.CTkLabel(master = self, text = f"{str(counter+1)}:{i}")
                        label.grid(padx = 3, pady = 3, row = counter, column = 0)
                        entry = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = f"{unique_dict[i]}"))
                        entry.grid(padx = 3, pady = 3, row = counter, column = 1)
                        entry.configure(state = state)
                        self.entry_list.append(entry)
                        counter += 1
                else:
                    self.labels = range(1, blank_number + 1)
                    self.entry_list = []
                    counter = 0
                    for i in self.labels:
                        i = str(i)
                        label = ctk.CTkLabel(master = self, text = f"{str(counter+1)}:{i}")
                        label.grid(padx = 3, pady = 3, row = counter, column = 0)
                        if blank_options is not None:
                            if still_do_entries:
                                self.blank_options = None
                                try:
                                    value = blank_options['labels'].values[int(i) - 1]
                                except ValueError:
                                    value = ""
                                entry = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = value))
                                entry.grid(padx = 3, pady = 3, row = counter, column = 1)
                            else:
                                self.blank_options = {}
                                for k,kk in zip(blank_options['labels'], blank_options['merging']):
                                    self.blank_options[k] = kk
                                self.blank_options[""] = ""
                                entry = ctk.CTkOptionMenu(master = self, 
                                                          variable = ctk.StringVar(value = ""), 
                                                          values = blank_options['labels'].unique())
                                entry.grid(padx = 3, pady = 3, row = counter, column = 1)                   
                        else:
                            self.blank_options = None
                            entry = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = ""))
                            entry.grid(padx = 3, pady = 3, row = counter, column = 1)
                        entry.configure(state = 'normal')
                        self.entry_list.append(entry)
                        counter += 1

            def retrieve(self) -> pd.DataFrame:
                metadata = pd.DataFrame()
                if self.blank_options is not None:
                    classes_numbers = [self.blank_options[i.get().strip()] for i in self.entry_list]
                    metadata['labels'] = [i.get() for i in self.entry_list]
                    metadata['merging'] = classes_numbers
                else:
                    classes_numbers = [i.get().strip() for i in self.entry_list]
                    metadata['labels'] = classes_numbers
                    merging_dict = {}
                    for i,ii in enumerate(metadata['labels'].unique()):
                        merging_dict[ii] = i + 1
                    merging_dict['background'] = 0
                    metadata['merging'] = metadata['labels'].replace(merging_dict)
                metadata['class'] = np.array(metadata.index) + 1
                return metadata
        
class bio_labels_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master, blank_load: Union[int, None] = None):
        '''
        blank_load (int) or None -- when None, the existing class labels are loaded in. When blank load is a number, 
                then a new, blank class labels are made with length = blank_load
        '''
        super().__init__(master)
        self.master = master 
        self.title("View and/or Edit Biological labels for each class")

        grand_label = ctk.CTkLabel(master = self, text = "Current Biological Labels for each class")
        grand_label.grid(row = 0, column = 0, padx = 3, pady = 3, columnspan = 2)

        column1 = ctk.CTkLabel(master = self, text = "Classification Number:")
        column1.grid(row = 1, column = 0, padx = 3, pady = 3)

        column2 = ctk.CTkLabel(master = self, text = "Biological Label:")
        column2.grid(row = 1, column = 1, padx = 3, pady = 3)

        if blank_load is None:
            try:
                self.biological_class_labels = pd.read_csv(self.master.active_classifier_dir + "/biological_labels.csv")
                self.from_labels = True
                column3 = ctk.CTkLabel(master = self, 
                                       text = "Biological Merging's new number: \n (0 and 1 are a special numbers reserved for the background class)")
                column3.grid(row = 1, column = 2, padx = 3, pady = 3)
            except Exception:
                try:   
                    open_json = open(self.master.active_classifier_dir + f"/{self.master.name}_details.json", 'r' , encoding="utf-8")
                    loaded_json = open_json.read()
                    self.dictionary = json.loads(loaded_json)
                    open_json.close()
                    self.list_of_labels = [i for i in range(1,self.dictionary["number_of_classes"]+1)]
                    self.from_labels = False
                except Exception:
                    tk.messagebox.showwarning("Warning!",
                        message = "The biological_labels.csv and _details.json (if unsupervised) is missing from this classifier!")
                    return
        else:
            self.biological_class_labels = pd.DataFrame()
            self.biological_class_labels['class'] = [i for i in range(1,blank_load + 1)]
            self.biological_class_labels['labels'] = ""
            self.from_labels = False
 
        if self.from_labels is True:
            self.entry_numbers_list = []
            self.entry_labels_list = []
            self.entry_merging_list = []
            counter = 2
            for i,ii,iii in zip(self.biological_class_labels["class"], 
                                self.biological_class_labels["labels"], 
                                self.biological_class_labels['merging']):
                
                entry_numbers = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = str(i)))
                entry_numbers.grid(row = counter, column = 0, padx = 3, pady = 3)
                self.entry_numbers_list.append(entry_numbers)
                entry_labels = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = str(ii)))
                entry_labels.grid(row = counter, column = 1, padx = 3, pady = 3)
                self.entry_labels_list.append(entry_labels)
                entry_merging = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = str(iii)))
                entry_merging.grid(row = counter, column = 2, padx = 3, pady = 3)
                self.entry_merging_list.append(entry_merging)
                counter += 1
        else:
            self.entry_numbers_list = []
            self.entry_labels_list = []
            self.entry_merging_list = []
            counter = 2
            for i in self.list_of_labels:
                entry_numbers = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = str(i)))
                entry_numbers.grid(row = counter, column = 0, padx = 3, pady = 3)
                self.entry_numbers_list.append(entry_numbers)
                entry_labels = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = ""))
                entry_labels.grid(row = counter, column = 1, padx = 3, pady = 3)
                self.entry_labels_list.append(entry_labels)
                counter += 1

        self.accept_button = ctk.CTkButton(master = self, text = "Accept Labels Above", command = self.accept_labels)
        self.accept_button.grid(padx = 3, pady = 3, columnspan = 2)
        self.after(200, self.focus())

    def accept_labels(self) -> None:
        '''
        '''
        class_numbers = [i.get() for i in self.entry_numbers_list]
        class_labels = [i.get().strip() for i in self.entry_labels_list]
        df = pd.DataFrame()
        df['class'] = class_numbers
        df["labels"] = class_labels
        if self.entry_merging_list == []:
            unique_names = df["labels"].unique()
            unique_dict = {ii:(i + 1) for i,ii in enumerate(unique_names)}
            unique_dict['background'] = 0
            df['merging'] = df['labels'].replace(unique_dict)
        else:
            class_merge = [i.get() for i in self.entry_merging_list]
            df['merging'] = class_merge
        df.to_csv(self.master.active_classifier_dir + "/biological_labels.csv", index = False)


        if self.master.classifier_type == "supervised":
            merge_folder(self.master.active_classifier_dir + "/classification_maps", 
                        pd.read_csv(self.master.active_classifier_dir + "/biological_labels.csv"),
                        self.master.PxQuPy_class.active_classifier_dir + "/merged_classification_maps")
        elif self.master.classifier_type == "unsupervised":
            merge_folder(self.master.active_classifier_dir + "/classification_maps", 
                        pd.read_csv(self.master.active_classifier_dir + "/biological_labels.csv"),
                        self.master.active_classifier_dir + "/merged_classification_maps")
        pixel_logger.info(f"Saved Biological labels and merged: \n {str(df)}")

        self.master.classify_cells.merge_frame.initialize_with_classifier()
        self.destroy()

class whole_class_analysis_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.directory = self.master.master.active_classifier_dir + "/Whole_class_analysis"

        self.display1 = MatPlotLib_Display(self, height = 700, width = 400)
        self.display1.grid(row = 1, column = 1, padx = 30, pady = 3, rowspan = 3, columnspan = 4)
        self.display2 = MatPlotLib_Display(self, height = 400, width = 400)
        self.display2.grid(row = 1, column = 6, padx = 3, pady = 3)

        directory = self.directory
        biological_csv = pd.read_csv(self.master.master.active_classifier_dir + "/biological_labels.csv")
        metadata = pd.read_csv(self.master.master.active_classifier_dir + "/Whole_class_analysis/metadata.csv")
        Analysis_panel = pd.read_csv(self.master.master.active_classifier_dir + "/Whole_class_analysis/Analysis_panel.csv")

        self.analysis_exp_whole = WholeClassAnalysis(directory, biological_csv, metadata, Analysis_panel)

        classes = self.analysis_exp_whole.class_labels['labels'].astype('str').unique()

        if len(classes) > 1:
            show_class = classes[1]
        else:
            show_class = classes[0]

        self.analysis_exp_whole.plot_distribution_exprs(unique_class = show_class, 
                                                        plot_type = "Bar", 
                                                        filename = f"{show_class}_Bar")
        self.display1.update_image(self.analysis_exp_whole.save_dir + f"/{show_class}_Bar.png")

        self.class_to_barplot = ctk.CTkOptionMenu(master = self, 
                                                  variable = ctk.StringVar(value = show_class),
                                                  values = classes, 
                                                  command = lambda choice: self.plot_distribution_exprs(unique_class = choice, 
                                                                                            plot_type = self.plot_type_choice.get(),
                                                                                            filename = f'{self.plot_type_choice.get()}_{choice}'))
        self.class_to_barplot.grid(row = 4, column = 1, padx = 3, pady = 3)

        self.plot_type_choice = ctk.CTkOptionMenu(master = self, 
                                                  variable = ctk.StringVar(value = "Bar"),
                                                  values = ["Violin","Bar"], 
                                                  command = lambda choice: self.plot_distribution_exprs(unique_class = self.class_to_barplot.get(), 
                                                                                            plot_type = choice,
                                                                                            filename = f'{choice}_{self.class_to_barplot.get()}'))
        self.plot_type_choice.grid(row = 4, column = 2, padx = 3, pady = 3)

        self.analysis_exp_whole.plot_percent_areas(filename = "PercentAreasBoxplot")
        self.display2.update_image(self.analysis_exp_whole.save_dir + "/PercentAreasBoxplot.png")

        self.data_export_button = ctk.CTkButton(master = self, text = "Export Data", command = self.launch_export_window)
        self.data_export_button.grid(row = 2, column = 6, padx = 3, pady = 3)

        self.stat_p_f_button = ctk.CTkButton(master = self, text = "Do basic Stats", command = lambda: self.stats(self))   
        self.stat_p_f_button.grid(row = 4, column = 6, padx = 3, pady = 3)

        self.statistic = ctk.CTkOptionMenu(master = self, values = ["ANOVA", "Kruskal"], variable = ctk.StringVar(value = "ANOVA"))  
        self.statistic.grid(row = 5, column = 6, padx = 3, pady = 3)

    def plot_distribution_exprs(self, unique_class, plot_type, filename) -> None:
        self.analysis_exp_whole.plot_distribution_exprs(unique_class = unique_class, 
                                    plot_type = plot_type,
                                    filename = filename)
        self.display1.update_image(self.analysis_exp_whole.save_dir + "/" + filename + ".png")

    def launch_export_window(self):
        self.cat_exp = self.analysis_exp_whole
        data_table_exportation_window(self, self.analysis_exp_whole.data, umap = False)  

    def stats(self, master) -> None:
        self.stats_window(master, statistic = self.statistic.get())

    class stats_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
        def __init__(self, master, statistic: str) -> None:
            super().__init__()
            self.display3 = MatPlotLib_Display(self, height = 400, width = 400)
            self.display3.grid(row = 1, column = 1, padx = 3, pady = 3)

            if statistic == "ANOVA":
                test_statistic = "F statistic"
            elif statistic == "Kruskal":
                test_statistic = "H statistic"
            self.test_stat = test_statistic
    
            self.change_stat_heatmap = ctk.CTkOptionMenu(master = self, 
                                                         variable = ctk.StringVar(value = "Stat on Heatmap"), 
                                                         values = [test_statistic,"p_adj","p_value"],
                                                         command = lambda choice: self.plot_heatmap(to_plot = choice))
            self.change_stat_heatmap.grid(row = 2, column = 1, padx = 3, pady = 3)

            self.master = master
            self.cluster_expression_ANOVA_df = self.master.analysis_exp_whole.whole_marker_exprs_ANOVA(marker_class = "All", 
                                                                                                       groupby_column = 'class', 
                                                                                                       statistic = statistic)
            self.cluster_expression_ANOVA_df.to_csv(self.master.analysis_exp_whole.directory + "/Data_tables/p_f_stat_table.csv")
            self.plot_heatmap(test_statistic)

            
            self.p_table = TableWidget(self)
            self.p_table.setup_data_table(directory = self.master.analysis_exp_whole.directory + "/Data_tables/p_f_stat_table.csv", 
                                        dataframe = self.cluster_expression_ANOVA_df, 
                                        table_type = 'other', 
                                        favor_table = True)
            self.p_table.setup_width_height(0.5, 0.8, scale_width_height = True)
            self.p_table.populate_table()
            self.p_table.grid(row = 1, column = 2, padx = 3, pady = 3)

            self.after(1000, self.focus())
        
        def plot_heatmap(self, to_plot):
            self.master.analysis_exp_whole.plot_heatmap(to_plot, filename = f"Heatmap of {to_plot}")
            self.display3.update_image(self.master.analysis_exp_whole.save_dir + f"/Heatmap of {to_plot}.png")


class classes_as_png_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    ''''''
    def __init__(self, master) -> None:
        super().__init__(master)

        label1 = ctk.CTkLabel(master = self, text = "Write classifications as png files / plots")
        label1.grid(padx = 3, pady = 3)

        label2 = ctk.CTkLabel(master = self, text = "Convert Pixel Classification (currently loaded classifier only) \n or"
                                                    " classy masks (any) to .png's:")
        label2.grid(padx = 3, pady = 3)
        
        self.option1 = ctk.CTkOptionMenu(master = self, values = ["pixel classification", "classy masks"])
        self.option1.grid(padx = 3, pady = 3)

        label3 = ctk.CTkLabel(master = self, text = "Select folder to convert")
        label3.grid(padx = 3, pady = 3)

        if_pixel_classifier = ["classification_maps", "merged_classification_maps"]

        self.option2 = ctk.CTkOptionMenu(master = self, values = [""])
        self.option2.grid(padx = 3, pady = 3)

        def refresh_option2(choice):
            if choice == "pixel classification":
                self.option2.configure(values = [i for i in if_pixel_classifier if i in os.listdir(self.master.master.active_classifier_dir)])
            elif choice == "classy masks":
                self.option2.configure(values = sorted(os.listdir(f"{self.master.master.main_directory}/classy_masks")))

        self.option1.configure(command = refresh_option2)

        ## output folder will be automatically parallel to the selected folder (just append "_PNG_conversion" or something like that)
        button = ctk.CTkButton(master = self, text = "Plot / Convert!", command = lambda: self.convert_to_png(self.option1.get(),
                                                                                                            self.option2.get()))
        button.grid(padx = 3, pady = 3)

        self.after(200, self.focus())

    def convert_to_png(self, map_type = "pixel classification", choice = "classification_maps"):
        ''''''
        ## Step 1: use map_type & choice to identify folder to convert
        if map_type == "pixel classification":
            path_to_folder = f"{self.master.master.active_classifier_dir}/{choice}"
        elif map_type == "classy masks":
            path_to_classy_mask = f"{self.master.master.main_directory}/classy_masks/{choice}"
            if "merged_classification_maps" in os.listdir(path_to_classy_mask):
                path_to_folder = f"{path_to_classy_mask}/merged_classification_maps"
            else:
                path_to_folder = f"{path_to_classy_mask}/{choice}"

        path_to_ouput = path_to_folder + "_PNG_conversion"
        if not os.path.exists(path_to_ouput):
            os.mkdir(path_to_ouput)

        ## Step 2: convert folder & write png's to a parallel folder to the original (with _PNG appended to the name or somesuch)
        plot_classes(path_to_folder, path_to_ouput)
        self.destroy()