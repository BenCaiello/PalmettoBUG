'''
This module handles the widgets in the second tab of the program, which coordinate image processing (such as conversion from /raw to /images/img)
None of the functions in this module should be exposed in the public (non-GUI) API. 

This file is licensed under the GPL3 license. No significant portion of the code here is known to be derived from another project 
(in the sense of needing to be separately / simulataneously licensed)        
'''

import os
import tkinter as tk

import customtkinter as ctk

from ..Utils.sharedClasses import (CtkSingletonWindow, 
                                   DirectoryDisplay, 
                                   TableWidget, 
                                   Project_logger, 
                                   Analysis_logger, 
                                   warning_window, 
                                   folder_checker,
                                   overwrite_approval)
from .ImageAnalysisClass import mask_expand, launch_denoise_seg_program, toggle_in_gui

__all__ = []

class ImageProcessingWidgets(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)

        toggle = toggle_in_gui()
        if not toggle:    ## this horrible little construct ensures _in_gui is True even if reinitialized
            toggle_in_gui()

        self.master = master
        label1 = ctk.CTkLabel(master = self, text = "Steinbock-style Panel File:")
        label1.grid(column = 0, row = 0)

        self.TableWidget = TableWidget(self) 
        self.TableWidget.setup_width_height(600, 700) 
        self.TableWidget.grid(column = 0, row = 1, rowspan = 4)

        label2 = ctk.CTkLabel(master = self, text = "Directory navigator")
        label2.grid(column = 1, row = 2)

        self.dir_disp = DirectoryDisplay(self) 
        self.dir_disp.grid(column = 1, row = 3)

        label3 = ctk.CTkLabel(master = self, text = "Processing Functions")
        label3.grid(column = 1, row = 0)
        
        self.buttonframe = self.ButtonFrame(self)
        self.buttonframe.grid(column = 1, row = 1)

    def add_Experiment(self, Experiment_object, from_mcds = True):
        self.Experiment_object = Experiment_object
        self.Experiment_object.TableWidget = self.TableWidget
        self.from_mcds = from_mcds

    def initialize_buttons(self, directory):
        ## decoupler for widget setup and data setup
        self.directory = directory
        self.ImageAnalysisPortionLogger = Project_logger(directory).return_log()
        self.dir_disp.setup_with_dir(directory, self.Experiment_object)
        self.TableWidget.setup_data_table(directory, self.Experiment_object.panel, "panel")
        self.TableWidget.populate_table()
        self.call_write_panel()
        self.Experiment_object._panel_setup()
        self.buttonframe.initialize_buttons()
        self.TableWidget.toggle_keep_column("disabled") 
        try:           ### The try block is likely unneeded, 
                            #  but was meant to catch an error in case the /img folder had not been created yet
            image_files = [i for i in os.listdir(directory + "/images/img") if i.lower().find("tif") != -1]
            if len(image_files) > 0:      ### if there are images in the image directory, 
                                                                # toggles off the keep column (creates errors if keep column is
                                                                #                                changed mid-experiment!)
                self.TableWidget.toggle_keep_column("normal") 
        except FileNotFoundError:
            pass
        
    class ButtonFrame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            label1 = ctk.CTkLabel(self, text = "Image conversion (MCD --> tiff) \n and Hot Pixel Filtering:")
            label1.grid(row = 0, column = 1, padx = 5, pady = 5)

            self.MCD_ome = ctk.CTkButton(self, text = "From Raw (MCD / tiff) to .ome.tiff")
            self.MCD_ome.grid(column = 1, row = 1, padx= 5, pady = 5)
            self.MCD_ome.configure(state = "disabled")

            spacer1 = ctk.CTkLabel(self, text = "Segmentation & Denoising:")
            spacer1.grid(column = 1, row = 2)

            ## now these denoising and segmentation tasks are handled by a separate program 
            # (GPL reasons, although it does have the side benefit of multiprocessing for these often computationally intensive tasks):
            '''
            self.simple_denoise = ctk.CTkButton(self, text = "Simple Denoising")
            self.simple_denoise.grid(column = 1, row = 3)
            self.simple_denoise.configure(state = "disabled")
            '''
            
            self.Instanseg = ctk.CTkButton(self, text = "Run InstanSeg")
            self.intersection = ctk.CTkButton(self, text = "Mask Transform by Intersection/Difference")
            self.expander = ctk.CTkButton(self, text = "Expand Masks")
            self.Instanseg.grid(column = 1, row = 4, padx= 5, pady = 5)
            self.intersection.grid(column = 1, row = 5, padx= 5, pady = 5)
            self.expander.grid(column = 1, row = 6, padx= 5, pady = 5)
            try:
                from instanseg import InstanSeg  # noqa: F401
                self.master.instanseg_available = True
            except Exception:
                self.master.instanseg_available = False
            self.Instanseg.configure(state = "disabled")
            self.expander.configure(state = "disabled")

            self.seg_denoise_button = ctk.CTkButton(master = self, text = "Launch separate \n Segmentation \n & Denoising program")
            self.seg_denoise_button.grid(column = 1, row = 3, padx = 5, pady = 5)
            self.seg_denoise_button.configure(state = "disabled")

            label3 = ctk.CTkLabel(self, text = "Measuring Segmented Objects & starting Analysis")
            label3.grid(row = 0, column = 2, padx = 5, pady = 5)

            self.Region_Measurements = ctk.CTkButton(self, text = "Do Region Measurements")
            self.Region_Measurements.grid(column = 2, row = 1, padx= 5, pady = 5)
            self.Region_Measurements.configure(state = "disabled")
            def activate_region_measure(enter = ""):
                try:
                    masks_dir_list = [i for i in os.listdir(self.master.Experiment_object.directory_object.masks_dir) if i.find(".") == -1]  ## only want to list directories
                    if (len(masks_dir_list) > 0) and (self.Region_Measurements.cget("state") == "disabled"):
                        self.Region_Measurements.configure(state = "normal", command = self.master.call_region_measurement)
                except Exception:
                    pass
            self.Region_Measurements.bind("<Enter>", activate_region_measure)

            self.Convert_towards_analysis = ctk.CTkButton(self, text = "Load an existing Analysis")
            self.Convert_towards_analysis.grid(column = 2, row = 4, padx= 5, pady = 5)
            self.Convert_towards_analysis.configure(state = "disabled")

        def initialize_buttons(self):
            ###This function allow the set up of the commands to coordinated by only activating buttons that 
            ## have there necessary inputs already in the appropriate folders (images / masks)
            try:
                self.MCD_ome.configure(state = "normal", command = self.master.call_raw_to_img_part_1_hpf)
                image_dir_list = [i for i in os.listdir(self.master.Experiment_object.directory_object.img_dir) if i.find(".") == -1] ## only want to list directories
                if len(image_dir_list) > 0: 
                    self.seg_denoise_button.configure(command = self.master.call_segmentation_denoise_program, state = "normal")
                    self.Instanseg.configure(command = self.master.call_instanseg_segmentor, state = "normal")
                    self.intersection.configure(command = self.master.call_intersection_difference, state = "normal")
                    #self.simple_denoise.configure(command = self.master.call_simple_denoise, state = "normal")
                masks_dir_list = [i for i in os.listdir(self.master.Experiment_object.directory_object.masks_dir) if i.find(".") == -1]
                if len(masks_dir_list) > 0:    
                    self.expander.configure(state = "normal", command = self.master.call_mask_expand)
                    self.Region_Measurements.configure(state = "normal", command = self.master.call_region_measurement)

                self.Convert_towards_analysis.configure(state = "normal", command = self.master.call_to_Analysis)

            except Exception:
                tk.messagebox.showwarning("Warning!", message = "Error: Could not initialize commands!")

    def call_raw_to_img_part_1_hpf(self):
        '''
        '''
        ## the panel write / setup block is too ensure the panel settings are saved while running
        self.call_write_panel()
        self.Experiment_object._panel_setup()
        HPF_readin(self)

    def call_raw_to_img_part_2_run(self, hpf):
        if not overwrite_approval(self.directory + "images/img", file_or_folder = "folder"):
            return
        self.Experiment_object.raw_to_img(hpf = hpf)
        self.buttonframe.initialize_buttons()
        image_list = [i for i in os.listdir(self.directory + "/images/img") if i.lower().find(".tif") != -1]
        if len(image_list) > 0:                         
            ### if there are images in the image directory, toggles off the keep column (creates errors if keep column is changed mid-experiment!)
            self.TableWidget.toggle_keep_column("normal")                        

    def call_instanseg_segmentor(self):
        '''
        Runs the instanseg segmentation. Also writes the panel file
        '''
        if not self.instanseg_available:
            tk.messagebox.showwarning("Warning!", message = "Instanseg is not installed! To fix this warning, \ninstall instanseg-torch package using pip")
            return
        ## the panel write / setup block is too ensure the panel settings are saved while running
        self.call_write_panel()
        self.Experiment_object._panel_setup()
        Instanseg_window(self)

    def call_intersection_difference(self):
        '''
        Runs the intersection / difference mask transform. Also writes the panel file
        '''
        self.call_write_panel()
        self.Experiment_object._panel_setup()
        intersection_difference_window(self)

    def call_segmentation_denoise_program(self):
        self.call_write_panel()
        self.Experiment_object._panel_setup()        
        from multiprocessing import Process
        p = Process(target = launch_denoise_seg_program, args = (self.directory, 
                                                                 self.Experiment_object.resolutions))
        p.start()  

    """
    def call_simple_denoise(self):
        SimpleDenoiseWindow(self)
    """ 

    def call_mask_expand(self):
        Expander_window(self)      

    def call_mask_expand_part_2(self, 
                                  distance, 
                                  image_source, 
                                  output_directory = None):
        ## First, copy the unexpanded data to a subdirectory --> allows restoration of original segmentation:
        mask_expand(distance, image_source, output_directory = output_directory) 

    def call_region_measurement(self):
        # This opens a new window to choosing your region measurement options
        RegionMeasurement(self, self.Experiment_object) 

    def call_to_Analysis(self):
        go_to_Analysis_window(self)

    def to_analysis(self, 
                    analysis_folder, 
                    metadata_from_save = False):
        ''''''
        self.Experiment_object.directory_object.make_analysis_dirs(analysis_folder)
        Analysis_logger(self.Experiment_object.directory_object.Analysis_internal_dir).return_log().info(f"Start log of experiment from the directory {self.Experiment_object.directory_object.Analysis_internal_dir}/Logs after loading .fcs for direct analysis")
        self.Experiment_object.to_analysis(self.master.master.py_exploratory, 
                                           metadata_from_save = metadata_from_save)
        self.master.master.set('Analysis')

    def call_write_panel(self):
        # writes panel file after recovering data from TableWidget
        self.Experiment_object.TableWidget.recover_input()
        self.Experiment_object.panel = self.Experiment_object.TableWidget.table_dataframe
        self.Experiment_object.panel_write()


class Instanseg_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    ''''''
    def __init__(self, master): 
        #### Set up the buttons / options / entry fields in the window      
        super().__init__(master)
        self.master = master
        self.title('InstanSeg Segmentation')
        label1 = ctk.CTkLabel(master = self, text = "Choose segmentation target:")
        label1.grid(column = 0, row = 0, padx = 10, pady = 10)
        self.seg_options = ctk.CTkOptionMenu(master = self, values = ["nuclei","cells"], variable = ctk.StringVar(value = "cells"))
        self.seg_options.grid(column = 1, row = 0, padx = 5, pady = 5)

        label2 = ctk.CTkLabel(master = self, text = "Choose model (only 1 available at the moment):")
        label2.grid(column = 0, row = 1, padx = 10, pady = 10)
        self.model = ctk.CTkOptionMenu(master = self, values = ["fluorescence_nuclei_and_cells"], variable = ctk.StringVar(value = "fluorescence_nuclei_and_cells"))
        self.model.grid(column = 1, row = 1, padx = 5, pady = 5)

        label3 = ctk.CTkLabel(master = self, text = "Threshold (higher numbers excludes more cells):")
        label3.grid(column = 0, row = 2, padx = 10, pady = 10)
        self.threshold = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "0.0"))
        self.threshold.grid(column = 1, row = 2, padx = 5, pady = 5)

        label_8 = ctk.CTkLabel(self, text = "Select an image folder to segment:")
        label_8.grid(column = 0, row = 3, padx = 5, pady = 5)

        self.img_dir = self.master.Experiment_object.directory_object.img_dir
        def refresh1(enter = ""):
            self.image_folders = [i for i in sorted(os.listdir(self.img_dir)) if i.find(".") == -1]
            self.image_folder.configure(values = self.image_folders)

        self.image_folder = ctk.CTkOptionMenu(self, values = ["img"], variable = ctk.StringVar(value = "img"))
        self.image_folder.grid(column = 1, row = 3, padx = 5, pady = 5)
        self.image_folder.bind("<Enter>", refresh1)

        def refresh2(enter = ""):
            self.filenames = [i for i in sorted(os.listdir(self.image_folder.get())) if i.find(".tif") != -1]
            self.single_image.configure(values = [""] + self.filenames)

        self.single_image = ctk.CTkOptionMenu(self, values = [""], variable = ctk.StringVar(value = ""))
        self.single_image.grid(column = 1, row = 3, padx = 5, pady = 5)
        self.single_image.bind("<Enter>", refresh2)

        self.re_do = ctk.CTkCheckBox(master = self, 
                    text = "Check to redo previous segmentations." 
                            "\n Un-check to only do if they do not alreayd exist for a given image.", 
                    onvalue = True, offvalue = False)
        self.re_do.grid(column = 0, row = 5, padx = 5, pady = 5)

        accept_values = ctk.CTkButton(master = self, text = "Accept choices and proceed", command = self.read_values)
        accept_values.grid(padx = 10, pady = 10)

    def read_values(self):
        ''''''
        threshold = self.threshold.get()
        try:
            threshold = float(threshold)
        except Exception:
            tk.messagebox.showwarning("Warning!", message = "Error: Threshold must be numerical!")
            return
        re_do = self.re_do.get()
        input_folder = self.image_folder.get()
        target = self.seg_options.get()
        model = self.model.get()
        single_image = self.single_image.get()
        if single_image == "":
            single_image = None
        
        warning_window("Don't worry if this step takes a while to complete or the window appears to freeze!\n"
                    "This behavior during Instanseg segmentation is normal.")
        self.master.Experiment_object.instanseg_segmentation(re_do = re_do, 
                                                             input_img_folder = f"{self.master.Experiment_object.directory_object.img_dir}/{input_folder}",
                                                             single_image = single_image,
                                                             mean_threshold = threshold,
                                                             target = target,
                                                             model = model)
        self.master.ImageAnalysisPortionLogger.info(f"Performed Instanseg segmentation with re_do = {str(re_do)},"
                                                            f"input_img_folder = {input_folder}, single_image = {str(single_image)},"
                                                            f"mean_threshold = {str(threshold)}, target = {str(target)},"
                                                            f"model = {model}")
        self.master.buttonframe.initialize_buttons()


class intersection_difference_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    ''''''
    def __init__(self, master): 
        super().__init__(master)
        self.master = master
        self.title('Mask transformation by Intersection / Difference')

        label1 = ctk.CTkLabel(master = self, text = "Choose First folder of Masks \n (or pixel classifier merged output):")
        label1.grid(column = 0, row = 0, padx = 10, pady = 10)
        def refresh1(enter = ""):
            created_mask_classifiers = [i for i in sorted(os.listdir(self.master.Experiment_object.directory_object.masks_dir)) if i.find(".") == -1]
            created_px_classifiers = [i for i in sorted(os.listdir(self.master.Experiment_object.directory_object.px_classifiers_dir)) if i.find(".") == -1]
            self.folders1 = created_mask_classifiers + created_px_classifiers
            self.masks_folder1.configure(values = self.folders1)
            self.masks_folder2.configure(values = self.folders1)

        self.masks_folder1 = ctk.CTkOptionMenu(master = self, 
                                            values = [""], 
                                            variable = ctk.StringVar(value = ""))
        self.masks_folder1.grid(column = 1, row = 0, padx = 5, pady = 5)
        self.masks_folder1.bind("<Enter>", refresh1)

        label2 = ctk.CTkLabel(master = self, text = "Choose Second folder of Masks  \n (or pixel classifier merged output):")
        label2.grid(column = 0, row = 1, padx = 10, pady = 10)
        self.masks_folder2 = ctk.CTkOptionMenu(master = self, 
                                            values = os.listdir(self.master.Experiment_object.directory_object.masks_dir), 
                                            variable = ctk.StringVar(value = ""))
        self.masks_folder2.grid(column = 1, row = 1, padx = 5, pady = 5)
        self.masks_folder2.bind("<Enter>", refresh1)

        label3 = ctk.CTkLabel(master = self, text = "Pixel Threshold (integer > 1):")
        label3.grid(column = 0, row = 2, padx = 10, pady = 10)
        self.pixel_threshold = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "1"))
        self.pixel_threshold.grid(column = 1, row = 2, padx = 5, pady = 5)

        label4 = ctk.CTkLabel(master = self, text = "Object Threshold (integer > 1):")
        label4.grid(column = 0, row = 3, padx = 10, pady = 10)
        self.object_threshold = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "1"))
        self.object_threshold.grid(column = 1, row = 3, padx = 5, pady = 5)

        label5 = ctk.CTkLabel(master = self, text = "Intersection or Difference:")
        label5.grid(column = 0, row = 4, padx = 10, pady = 10)
        self.kind1 = ctk.CTkOptionMenu(self, values = ["intersection","difference"], variable = ctk.StringVar(value = "intersection"))
        self.kind1.grid(column = 1, row = 4, padx = 5, pady = 5)

        label6 = ctk.CTkLabel(master = self, text = "One way or Two way:")
        label6.grid(column = 0, row = 5, padx = 10, pady = 10)
        self.kind2 = ctk.CTkOptionMenu(self, values = ["one-way","two-way"], variable = ctk.StringVar(value = "one-way"))
        self.kind2.grid(column = 1, row = 5, padx = 5, pady = 5)

        accept_values = ctk.CTkButton(master = self, text = "Transform!", command = self.read_values)
        accept_values.grid(padx = 10, pady = 10)

    def read_values(self):
        ''''''
        object_threshold = self.object_threshold.get()
        pixel_threshold = self.pixel_threshold.get()
        try:
            object_threshold = float(object_threshold)
            pixel_threshold = float(pixel_threshold)
        except Exception:
            tk.messagebox.showwarning("Warning!", message = "Error: both pixel and object thresholds must be numerical!")
            return

        masks_folder1 = self.masks_folder1.get()
        masks_folder2 = self.masks_folder2.get()
        output_folder = f'{masks_folder1}_{masks_folder2}'
        def check_masks_or_px(path):
            if path in os.listdir(self.master.Experiment_object.directory_object.px_classifiers_dir):
                if "merged_classification_maps" in os.listdir(self.master.Experiment_object.directory_object.px_classifiers_dir + "/" + path):
                    return self.master.Experiment_object.directory_object.px_classifiers_dir +"/" + path + "/merged_classification_maps"     
                    ## only used merged pixel class maps, so that background is 0 and outside the masks (otherwise every pixel will be 'inside' a mask)
                else:
                    return None
            else:
                return self.master.Experiment_object.directory_object.masks_dir + "/" + path
        masks_folder1 = check_masks_or_px(masks_folder1)
        masks_folder2 = check_masks_or_px(masks_folder2)
        if (masks_folder1 is None) or (masks_folder2 is None):
            tk.messagebox.showwarning("Warning!", 
                     message = "One of the pixel classifiers provided does not have a merged folder. \nOnly merged pixel classification maps can be used by this function! Cancelling")
            return

        kind1 = self.kind1.get()
        kind2 = self.kind2.get()
        if kind2 == "one-way":
            kind = f'{kind1}1'
        else:
            kind = f'{kind1}2'
        self.master.Experiment_object.mask_intersection_difference(masks_folder1 = masks_folder1, 
                                                                    masks_folder2 = masks_folder2, 
                                                                    kind = kind, 
                                                                    object_threshold = object_threshold, 
                                                                    pixel_threshold = pixel_threshold, 
                                                                    re_order = True,    #leave re-order & output folder as defaults for now
                                                                    output_folder = output_folder)
        self.master.ImageAnalysisPortionLogger.info(f"Performed Mask Intersection Transform with:"
                                                            f"masks_folder1 = {masks_folder1}, masks_folder2 = {str(masks_folder2)},"
                                                            f"kind = {str(kind)}, object_threshold = {str(object_threshold)},"
                                                            f"pixel_threshold = {pixel_threshold}, output_folder = {output_folder}")
        self.master.buttonframe.initialize_buttons()


class RegionMeasurement(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    This object is the launched window for taking in the user selections of the region measurements.
    '''
    def __init__(self, master, experiment): 
        #### Set up the buttons / options / entry fields in the window      
        super().__init__(master)
        self.master = master
        self.title('Region Measurement Options')
        label1 = ctk.CTkLabel(master = self, text = "Choose the intensity measurement option:")
        label1.grid(column = 0, row = 0, padx = 10, pady = 10)
        self.intensity_options = ctk.CTkOptionMenu(master = self, values = ["mean","median","std"])
        self.intensity_options.grid(column = 1, row = 0, padx = 10, pady = 10)

        self.re_do = ctk.CTkCheckBox(master= self, 
                    text = "Leave checked to redo previously calculated measurements." 
                            "\n Un-check to only do measurements if they do not alreayd exist for a given image.", 
                    onvalue = True, offvalue = False)
        self.re_do.grid(padx = 10, pady = 10)
        self.re_do.select()

        label_8 = ctk.CTkLabel(self, text = "Select an image folder from which measurements will be taken:")
        label_8.grid(column = 0, row = 2)

        self.img_dir = self.master.Experiment_object.directory_object.img_dir
        def refresh1(enter = ""):
            self.image_folders = [i for i in sorted(os.listdir(self.img_dir)) if i.find(".") == -1]
            self.image_folder.configure(values = self.image_folders)

        self.image_folder = ctk.CTkOptionMenu(self, values = ["img"], variable = ctk.StringVar(value = "img"))
        self.image_folder.grid(column = 1, row = 2, padx = 5, pady = 5)
        self.image_folder.bind("<Enter>", refresh1)

        label_8 = ctk.CTkLabel(self, text = "Select a masks folder that will define the regions being measured:")
        label_8.grid(column = 0, row = 3)

        self.masks_dir = self.master.Experiment_object.directory_object.masks_dir
        def refresh2(enter = ""):
            self.masks_folders = [i for i in sorted(os.listdir(self.masks_dir)) if i.find(".") == -1]
            self.masks_folder.configure(values = self.masks_folders)

        self.masks_folder = ctk.CTkOptionMenu(self, values = [""], variable = ctk.StringVar(value = ""))
        self.masks_folder.grid(column = 1, row = 3, padx = 5, pady = 5)
        self.masks_folder.bind("<Enter>", refresh2)

        label_9 = ctk.CTkLabel(self, text = "Name an Analysis folder where the csv / fcs files will be saved ready for analysis:")   
        label_9.grid(column = 0, row = 4)

        self.output_folder = ctk.CTkEntry(self, textvariable = ctk.StringVar(value = "Analysis_1"))
        self.output_folder.grid(column = 1, row = 4, padx = 5, pady = 5)

        accept_values = ctk.CTkButton(master = self, text = "Accept choices and proceed", command = lambda: self.read_values(experiment))
        accept_values.grid(padx = 10, pady = 10)

        self.advanced_region = ctk.CTkCheckBox(master= self, 
                                     text = "Do advanced regionprops measurements? \n (Will take much longer)", 
                                     onvalue = True, offvalue = False)
        # self.advanced_region.grid(column = 1, row = 5, padx = 5, pady = 5)  ## TODO: fix branch point calculation error (in NAVis?) and reactivate

        self.after(200, lambda: self.focus())
        
    def read_values(self, experiment_class):
        output_folder = self.output_folder.get()
        if folder_checker(output_folder):
            return
        if not overwrite_approval(experiment_class.directory_object.Analyses_dir + "/" + output_folder,
                                   file_or_folder = "folder",
                                   custom_message = "Are you sure you want to potentially overwrite intensity / regionprop files in this analysis?"):
            return
        ### Read in the values and return it to the experiment
        experiment_class.directory_object.make_analysis_dirs(output_folder.strip())

        experiment_class.make_segmentation_measurements(re_do = self.re_do.get(), 
                    input_img_folder = (self.img_dir + "/" + self.image_folder.get()),
                    input_mask_folder = (self.masks_dir + "/" + self.masks_folder.get()),
                    advanced_regionprops = False, # self.advanced_region.get(),     ## TODO: fix branch point calculation error (in NAVis?) and reactivate
                    statistic = self.intensity_options.get(),
                    )
        try:   ## this try/except is my crude means of ensuring this doesn't throw an error when called from the use_classifier_GUI buttons
                ## for whole-class analysis. Consider a better solution...
            self.master.buttonframe.initialize_buttons()
            self.master.dir_disp.list_dir()
        except Exception:
            pass
        Analysis_logger(experiment_class.directory_object.analysis_dir + "/main").return_log().info(f"""Region Measurements made with the following 
                            image folder = {(self.img_dir + "/" + self.image_folder.get())},
                            Masks folder = {(self.masks_dir + "/" + self.masks_folder.get())},
                            Intensity aggregation method = {self.intensity_options.get()}""")
        self.destroy()

class up_down_class(ctk.CTkFrame):
    def __init__(self, master, column = 1, row = 0):
        super().__init__(master)
        self.master = master
        self.column = column
        self.row = row

        upvalue = ctk.CTkButton(master = self, text = "^", command = lambda: self.upvalue(master))
        upvalue.configure(width = 15, height = 10)
        upvalue.grid(column = 0, row = 0)

        downvalue = ctk.CTkButton(master = self, text = "˅", command = lambda: self.downvalue(master))
        downvalue.configure(width = 15, height = 10)
        downvalue.grid(column = 0, row = 1)

    def upvalue(self, master):
        current_val = int(master.value.get())
        current_val += 1
        master.values_list.append(str(current_val))
        master.values_list = list(set(master.values_list))
        master.values_list.sort()
        master.value.configure(values = master.values_list)
        master.value.set(current_val)

    def downvalue(self, master):
        current_val = int(master.value.get())
        current_val = current_val - 1
        if current_val < 0:
            current_val = 0
        master.values_list.append(str(current_val))
        master.values_list = list(set(master.values_list))
        master.values_list.sort()
        master.value.configure(values = master.values_list)
        master.value.set(current_val)

class HPF_readin(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    '''
    def __init__(self, master): 
        #### Set up the buttons / options / entry fields in the window      
        super().__init__(master)
        self.title('HPF')
        label1 = ctk.CTkLabel(master = self, text = "Choose HPF threshold -- use an integer to directly set threshold value \n"
                                                    "(steinbock pipeline default is 50), or use a decimal > 0 and < 1 to calculate \n"
                                                    "the hpf separately for every image & channel with decimal used as the quantile \n"
                                                    "value to threshold at. Hot pixel filtering will not be performed if hpf == 0.")
        label1.grid(column = 0, row = 0, padx = 10, pady = 10)
        #self.values_list = ["0","50"]
        #self.values_list = list(set(self.values_list))
        self.value = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "0.85"))
        self.value.grid(column = 1, row = 0, padx = 10, pady = 10)

        #up_down = up_down_class(self)
        #up_down.grid(column = 2, row = 0)

        accept_button = ctk.CTkButton(master = self, text = "Accept & proceed", command = lambda: self.read_values())
        accept_button.grid(column = 0, row = 2, padx = 10, pady = 10)

        self.after(200, lambda: self.focus())
        
    def read_values(self):
        ### Read in the values and return it to the experiment
        try:
            hpf = float(self.value.get())
            if hpf > 1:
                hpf = int(hpf)
            if hpf < 0:
                raise ValueError
        except ValueError:
            tk.messagebox.showwarning("Warning!", message = "hpf must be numerical and great than 0!")
            return
        self.master.call_raw_to_img_part_2_run(hpf = hpf)
        self.master.dir_disp.list_dir()
        self.master.ImageAnalysisPortionLogger.info(f"Converted MCD files to OME.TIFFs using a hot pixel threshold of {self.value.get()}")
        self.destroy()

class Expander_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    '''
    def __init__(self, master): 
        #### Set up the buttons / options / entry fields in the window      
        super().__init__(master)
        self.master = master
        self.title('Mask Pixel Expansion')
        label1 = ctk.CTkLabel(master = self, text = "Choose The number of pixels to expand your masks by:")
        label1.grid(column = 0, row = 0, padx = 10, pady = 10)
        self.values_list = ["5"]
        self.values_list = list(set(self.values_list))
        self.value = ctk.CTkOptionMenu(master = self, 
                                       values = self.values_list, 
                                       variable = ctk.StringVar(value = "5"))
        self.value.grid(column = 1, row = 0, padx = 10, pady = 10)

        up_down = up_down_class(self)
        up_down.grid(column = 2, row = 0)
            
        label_8 = ctk.CTkLabel(self, text = "Select folder of masks to be expanded:")
        label_8.grid(column = 0, row = 1)


        self.masks_dir = self.master.Experiment_object.directory_object.masks_dir
        def refresh3(enter = ""):
            self.image_folders = [i for i in sorted(os.listdir(self.masks_dir)) if i.find(".") == -1]
            self.image_folder.configure(values = self.image_folders)

        self.image_folder = ctk.CTkOptionMenu(self, values = [""], variable = ctk.StringVar(value = ""))
        self.image_folder.grid(column = 1, row = 1, padx = 5, pady = 5)
        self.image_folder.bind("<Enter>", refresh3)

        label_9 = ctk.CTkLabel(self, text = "Name folder where the expanded masks will be save to:")
        label_9.grid(column = 0, row = 2)

        self.output_folder = ctk.CTkEntry(self, textvariable = ctk.StringVar(value = "Expanded_masks"))
        self.output_folder.grid(column = 1, row = 2, padx = 5, pady = 5)

        accept_button = ctk.CTkButton(master = self, text = "Accept & proceed", command = lambda: self.read_values())
        accept_button.grid(column = 0, row = 3, padx = 10, pady = 10)

        self.after(200, lambda: self.focus())
        
    def read_values(self):
        ### Read in the values and return it to the experiment
        self.master.call_mask_expand_part_2(int(self.value.get()), 
            image_source = self.masks_dir + "/" + self.image_folder.get(), 
            output_directory = self.masks_dir + "/" + self.output_folder.get().strip())
        self.master.ImageAnalysisPortionLogger.info(f"Expanded masks by {self.value.get()} pixels")
        self.master.dir_disp.list_dir()
        self.destroy()


class go_to_Analysis_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__()
        self.title("Select an Analysis folder to do analysis in")
        self.master = master

        label = ctk.CTkLabel(self, text = "Select an Analysis Folder:")
        label.grid(column = 0, row = 1)

        self.checkbox = ctk.CTkCheckBox(self, text = "Load metadata / panel file \n from save:", onvalue = True, offvalue = False)
        self.checkbox.grid(column = 0, row = 2)

        analyses_dir = self.master.Experiment_object.directory_object.Analyses_dir

        def refresh10(enter = ""):
            self.analysis_options = [i for i in sorted(os.listdir(analyses_dir)) if i.find(".csv") == -1]
            self.analysis_choice.configure(values = self.analysis_options)

        self.analysis_choice = ctk.CTkOptionMenu(self, values = [""], variable = ctk.StringVar(value = ""))
        self.analysis_choice.grid(column = 1, row = 1, padx = 5, pady = 5)
        self.analysis_choice.bind("<Enter>", refresh10)

        button = ctk.CTkButton(self, text = "Go to Analysis!", command = self.run)
        button.grid(column = 1, row = 2, padx = 5, pady = 5)
        self.after(200, lambda: self.focus())

    def run(self):
        choice = self.analysis_choice.get()
        if choice == "":
            return
        metadata_from_save = self.checkbox.get()
        self.master.to_analysis(choice, metadata_from_save = metadata_from_save)
        Analysis_logger(self.master.Experiment_object.directory_object.Analyses_dir + 
                        f"/{self.analysis_choice.get()}/main").return_log().info("Loading Analysis from Image Processing modeule")
        self.after(200, lambda: self.destroy())