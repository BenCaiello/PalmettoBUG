'''
This module handles the widgets in the second tab of the program, which coordinate image processing (such as converison from /raw to /images/img)
None of the functions in this module should be exposed int eh public (non-GUI) API. 



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
                                   #warning_window, 
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
            if len(os.listdir(directory + "/images/img")) > 0:      ### if there are images in the image directory, 
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

            spacer1 = ctk.CTkLabel(self, text = "Denoising:")
            spacer1.grid(column = 1, row = 2)

            ## now these denoising and segmentation tasks are handled by a separate program 
            # (GPL reasons, although it does have the side benefit of multiprocessing for these often computationally intensive tasks):
            '''
            self.simple_denoise = ctk.CTkButton(self, text = "Simple Denoising")
            self.simple_denoise.grid(column = 1, row = 3)
            self.simple_denoise.configure(state = "disabled")

            self.cellposer = ctk.CTkButton(self, text = "Cellpose Denoiser")
            self.cellposer.grid(column = 1, row = 4, padx= 5, pady = 5)
            self.cellposer.configure(state = "disabled")

            label2 = ctk.CTkLabel(self, text = "Segmentation Options")
            label2.grid(row = 5, column = 1, padx = 5, pady = 5)

            self.DeepCell = ctk.CTkButton(self, text = "Run DeepCell")
            self.DeepCell.grid(column = 1, row = 6, padx= 5, pady = 5)
            self.DeepCell.configure(state = "disabled")

            self.cellpose_seg = ctk.CTkButton(self, text = "Run Cellpose")
            self.cellpose_seg.grid(column = 1, row = 7, padx= 5, pady = 5)
            self.cellpose_seg.configure(state = "disabled")

            self.expander = ctk.CTkButton(self, text = "Expand Masks")
            self.expander.grid(column = 1, row = 9, padx= 5, pady = 5)
            self.expander.configure(state = "disabled")
            '''
            self.seg_denoise_button = ctk.CTkButton(master = self, text = "Launch \n Segmentation \n & Denoising")
            self.seg_denoise_button.grid(column = 1, row = 3, rowspan = 6, padx = 5, pady = 5)
            self.seg_denoise_button.configure(state = "disabled")

            label3 = ctk.CTkLabel(self, text = "Measuring Segmented Objects & starting Analysis")
            label3.grid(row = 0, column = 2, padx = 5, pady = 5)

            self.Region_Measurements = ctk.CTkButton(self, text = "Do Region Measurements")
            self.Region_Measurements.grid(column = 2, row = 1, padx= 5, pady = 5)
            self.Region_Measurements.configure(state = "disabled")
            def activate_region_measure(enter = ""):
                try:
                    if (len(os.listdir(self.master.Experiment_object.directory_object.masks_dir)) > 0) and (self.Region_Measurements.cget("state") == "disabled"):
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
                if len(os.listdir(self.master.Experiment_object.directory_object.img_dir)) > 0: 
                    self.seg_denoise_button.configure(command = self.master.call_segmentation_denoise_program, state = "normal")
                    #self.DeepCell.configure(command = self.master.call_deepcell_mesmer_segmentor, state = "normal")
                    #self.cellpose_seg.configure(state = "normal", command = self.master.call_cellpose_seg)
                    #self.cellposer.configure(command = self.master.call_cellposer, state = "normal")
                    #self.simple_denoise.configure(command = self.master.call_simple_denoise, state = "normal")
                if len(os.listdir(self.master.Experiment_object.directory_object.masks_dir)) > 0:    
                    # self.expander.configure(state = "normal", command = self.master.call_mask_expand)
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
        if len(os.listdir(self.directory + "/images/img")) > 0:                         
            ### if there are images in the image directory, toggles off the keep column (creates errors if keep column is changed mid-experiment!)
            self.TableWidget.toggle_keep_column("normal")                        

    """
    def call_deepcell_mesmer_segmentor(self):
        '''
        Runs the deepcell segmentation. Also writes the 
        '''
        ## the panel write / setup block is too ensure the panel settings are saved while running, and also to avoid a bizarre bug where
        ## deep cell was using np.nan's as a third group for the channels (I have no idea why...). 
                            # Reading from a file solves that problem somehow
        self.call_write_panel()
        self.Experiment_object._panel_setup()
        DeepCell_window(self)
    """

    def call_segmentation_denoise_program(self):
        self.call_write_panel()
        self.Experiment_object._panel_setup()        
        from multiprocessing import Process
        p = Process(target = launch_denoise_seg_program, args = (self.directory, 
                                                                 self.Experiment_object.resolutions))
        p.start()  

    """
    def run_deepcell(self, 
                     image_list, 
                     re_do, 
                     image_folder = None, 
                     output_folder = None):   
        '''
        '''
        warning_window("Don't worry if this step takes a while to complete or the window appears to freeze!\n"
                    "This behavior during Deepcell / Mesmer segmentation is normal.")
        self.after(200, 
                   lambda: self.Experiment_object.deepcell_segmentation(image_list, 
                                                                        re_do = re_do, 
                                                                        image_folder = image_folder, 
                                                                        output_folder = output_folder))
        self.buttonframe.initialize_buttons()

    def call_cellposer(self):
        CellPoseDenoiseWindow(self) 

    def call_simple_denoise(self):
        SimpleDenoiseWindow(self)

    
    def call_cellpose_seg(self):
        ## the panel write / setup block is too ensure the panel settings are saved before running segmentation
        self.call_write_panel()
        self.Experiment_object._panel_setup()
        CellPoseSegmentationWindow(self) 
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
            self.image_folders = sorted(os.listdir(self.img_dir))
            self.image_folder.configure(values = self.image_folders)

        self.image_folder = ctk.CTkOptionMenu(self, values = ["img"], variable = ctk.StringVar(value = "img"))
        self.image_folder.grid(column = 1, row = 2, padx = 5, pady = 5)
        self.image_folder.bind("<Enter>", refresh1)

        label_8 = ctk.CTkLabel(self, text = "Select a masks folder that will define the regions being measured:")
        label_8.grid(column = 0, row = 3)

        self.masks_dir = self.master.Experiment_object.directory_object.masks_dir
        def refresh2(enter = ""):
            self.masks_folders = sorted(os.listdir(self.masks_dir))
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
            self.image_folders = sorted(os.listdir(self.masks_dir))
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