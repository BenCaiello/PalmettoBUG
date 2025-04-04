'''
This module contains the widgets used in the fifth and final tab of the GUI program, which coordinates Spatial Analysis / spaceANOVA.
Nothing in this file is used in the non-GUI API

Licensed under the GPL3

None of the code here is known to be derivative of any other projects' code 
(in the sense of needing separate attribution / copyright from the general attribution of the program).

This is generally true of the GUI portions of the program, as they form an original GUI framework that calls the analysis functions 
(which in contrast frequently derive or originate from another package) but do not contain any of the analysis functions themselves. 
'''

import os
from PIL import Image
import tkinter as tk
import customtkinter as ctk

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt                       

from ..Utils.sharedClasses import DirectoryDisplay, CtkSingletonWindow, filename_checker, TableLaunch, Analysis_logger, warning_window, overwrite_approval
from ..Analysis_functions.SpatialANOVA import SpatialANOVA, plot_spatial_stat_heatmap
from ..Analysis_functions.SpatialAnalysis import SpatialNeighbors, SpatialEDT
from .Analysis_GUI import Plot_window_display, MatPlotLib_Display, CLUSTER_NAMES_append_CN, MARKER_CLASSES_append_spatial_edt

homedir = __file__.replace("\\","/")
homedir = homedir[:(homedir.rfind("/"))]
## do it twice to get up to the top level directory:
homedir = homedir[:(homedir.rfind("/"))]  

__all__ = []

CLUSTER_NAMES = ["metaclustering", "merging", "classification", "leiden", "CN"] 
MARKER_CLASSES = ["type","state","none"]                                                        
COLNAMES = ['file_name', 'patient_id', 'sample_id', 'condition']

class Spatial_py(ctk.CTkFrame):
    '''  
    These widgets comprise the fifth tab of the program, which coordinate the spatial analysis steps.

    Sub-Widgets:
        self.display (class = MatPlotLib_Display): This frame contains the Image display widget for when plot are created / displayed
                Initially, has a Ms. PalmettoBUG in the display.

        self.directory_display (class = DirectoryDisplay): This frame contains the simple directory navigation widgets beneath self.display
        self.cellmaps_button (ctk.CTkButton): a single button that launches the plot_cell_maps_window. Below self.widgets

        self.widgets (class = self.spacewidgets): This contains the 3 buttons for launching windows which coordinate the steps of SpaceANOVA analysis. 
    '''
    def __init__(self, master):
        super().__init__(master)
        self.master_exp = None
        #self.master_exp.space_analysis = None

        self.squidpy_spatial = SquidpySpatialWidgets(self)
        self.squidpy_spatial.grid(column = 1, row = 1, sticky = "nsew")

        self.CN_widgets = cellularNeighborhoodsFrame(self)
        self.CN_widgets.grid(column = 1, row = 2, sticky = "nsew")

        self.display = MatPlotLib_Display(self, bug = 'Capture.jpg')
        self.display.grid(column = 0, row = 0, padx = 5, pady = 5, rowspan = 4)

        self.directory_display = DirectoryDisplay(self)
        self.directory_display.grid(column = 0, row = 4)

        self.load_frame = self.LoadFrame(self)
        self.load_frame.grid(column = 1, row = 0, sticky = "nsew")
        
        self.widgets = self.spacewidgets(master = self, data = False)
        self.widgets.grid(column = 1, row = 3, sticky = "nsew")  # sticky = "nsew"

        self.test_edt = dist_transform_frame(self)
        self.test_edt.grid(column = 1, row = 4, padx = 5, pady = 5, sticky = "nsew")

        self.cellmaps_button = ctk.CTkButton(master = self, text = "Make Spatial Cell plots")
        self.cellmaps_button.grid(column = 2, row = 3, padx = 5, pady = 5)
        self.cellmaps_button.configure(command = self.plot_cell_maps_window, state = "disabled")

    def setup_dir_disp(self, directory: str) -> None:
        '''
        This initializes the widgets in this frame (as well as the directory display in the master frame). 
        Without this, the dropdown will not populate with values
        '''
        self.directory_display.setup_with_dir(directory, self, png = self.display) 
        #self.clustering_dir = directory + "/clusterings"
        global space_logger
        space_logger = Analysis_logger(directory).return_log()

    def add_Analysis(self, Analysis):
        self.master_exp = Analysis
        self.master_exp.space_analysis = SpatialANOVA()
        self.squidpy_spatial.add_AnalysisObject(Analysis)
        self.CN_widgets.add_Analysis(Analysis, self.squidpy_spatial.spatial)
        self.test_edt.edt_object.add_Analysis(Analysis)
        if not Analysis._spatial:
            self.cellmaps_button.configure(state = "disabled")
            self.load_frame.load_button.configure(state = "disabled")
            self.test_edt.disable()
            self.widgets.disable_buttons()
            self.widgets.run_button.configure(state = "disabled")
        else:
            self.widgets.configure_commands()
            self.test_edt.button_load.configure(state = "normal") 
            self.test_edt.disable()
            self.widgets.disable_buttons()
            self.widgets.run_button.configure(state = "normal")
            self.cellmaps_button.configure(state = "normal")
            self.load_frame.load_button.configure(state = "normal")

    class LoadFrame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master

            label_load = ctk.CTkLabel(master = self, text = "Select Loading Parameters:")
            label_load.grid(column = 1, row = 0, padx = 5, pady = 5, columnspan = 2)

            labelU = ctk.CTkLabel(master = self, text = "Make neighbor graph on radius or number of neighbors:")
            labelU.grid(column = 1, row = 2, padx = 5, pady = 5)

            self.radius = ctk.CTkOptionMenu(master = self, values= ['Radius', 'Neighbors'], variable = ctk.StringVar(value = "Radius"))
            self.radius.grid(column = 2, row = 2, padx = 5, pady = 5)

            labelV = ctk.CTkLabel(master = self, text = "Enter Radius or Number of Neighbors (must be a positive integer):")
            labelV.grid(column = 1, row = 3, padx = 5, pady = 5)

            self.n_neigh = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "10"))
            self.n_neigh.grid(column = 2, row = 3, padx = 5, pady = 5)

            self.load_button = ctk.CTkButton(master = self, text = "Create Spatial Neighbor grid", command = self.master.load_spatial)
            self.load_button.grid(column = 1, row = 4, padx = 5, pady = 5)

    def load_spatial(self):    #### TODO: move this frame to be above the neighbor-dependent frames (distinguish from frames with functions that do not need this step)
        ''''''
        self.squidpy_spatial.do_neighbors()
        self.CN_widgets.targeted_enable()

    def launch_edt(self) -> None:
        dist_transform_window(self)

    def plot_cell_maps_window(self) -> None:
        '''Launches the window for generating plots of the cells in X/Y space, colored by cell type and sized by cell area'''
        plot_cell_maps_window(self)

    class spacewidgets(ctk.CTkFrame):  
        '''
        This Frame contains the buttons that launch windows for performing Spatial Analysis.

        1. self.run_button --> window that runs the calculations of Ripley's statistics & accepts user input for the parameters 
                of those calculations

        2. plot_fx_button --> window for plotting Ripley's Statistics +/- F statistics (from single radii ANOVAs at each radii distance)

        3. self.plot_button --> window for calculating statistics from functional ANOVA of Ripley's g (these are calculated automatically as
                the window is opening), and then exporting stat tables / plotting heatmaps of each pairwise fANOVA comparison.

        '''  
        def __init__(self, master, data = True):
            super().__init__(master)
            self.master = master
            self.configure(fg_color = 'grey')

            label = ctk.CTkLabel(master = self, text = "SpaceANOVA analysis:")
            label.grid(column = 0, row = 0, padx = 5, pady = 5)

            self.run_button = ctk.CTkButton(master = self, text = "Run SpaceANOVA analysis")
            self.run_button.grid(column = 0, row = 1, padx = 5, pady = 5)
            self.run_button.configure(state = "disabled")

            self.plot_fx_button = ctk.CTkButton(master = self, text = "Plot SpaceANOVA Ripley functions")
            self.plot_fx_button.grid(column = 0, row = 2, padx = 5, pady = 5)
            self.plot_fx_button.configure(state = "disabled")

            stat_label = ctk.CTkLabel(master = self, text = "Select Ripley's Statistic \n for fANOVA:")
            stat_label.grid(column = 1, row = 0, padx = 5, pady = 5, rowspan = 2)

            self.stat = ctk.CTkOptionMenu(master = self, variable = ctk.StringVar(value = "g"), values = ['g', 'K', 'L'], state = "disabled")
            self.stat.grid(column = 2, row = 1, padx = 5, pady = 5)

            self.plot_button = ctk.CTkButton(master = self, text = "SpaceANOVA Statistics")
            self.plot_button.grid(column = 2, row = 2, padx = 5, pady = 5)
            self.plot_button.configure(state = "disabled")

            if data is True:
                self.configure_commands()

        def configure_commands(self) -> None:
            if not self.master.master_exp._spatial:
                self.run_button.configure(state = "disable")
            else:
                self.run_button.configure(state = "normal")
            self.run_button.configure(command = self.launch)
            self.plot_button.configure(command = lambda: self.launch_heat_plot(stat = self.stat.get()))
            self.plot_fx_button.configure(command = self.launch_function_plot)

        def disable_buttons(self) -> None:
            ''' purpose: to re-disable buttons when Analysis is reloaded '''
            self.plot_button.configure(state = "disabled")
            self.stat.configure(state = "disabled")
            self.plot_fx_button.configure(state = "disabled")
            
        def launch(self) -> None:
            self.launch_window(self)

        def launch_heat_plot(self, stat = 'g') -> None:
            self.launch_heat_plot_window(self, stat = stat)

        def launch_function_plot(self) -> None:
            self.launch_function_plot_window(self)

        class launch_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
            '''
            This window coordinates the calculation of Ripley's spatial statistics (K/L/g), with fields for parameters:
                - condition comparison --> The comparison of conditions to make, whether All/multicomparison or pairwise.
                                            Pairwise comparisons are of the form "condition1_vs_condition2"
                                            "_vs_" should not be inside condition1 / 2, as that will create errors.
                - permutations --> whether (>0) are how many permutations to use for permutations correction. 
                                    Permutation correction is highly recommended as it accounts for common irregularities
                                    in the distribution of cells, such as holes or gaps in the tissue. 
                - max Radii and Radii step --> These define distances (always starting at 0) where Ripley's statistics
                                                will be calculated.
            
            '''
            def __init__(self, master):
                super().__init__(master)
                self.master = master
                self.title("Run Analysis")
                label = ctk.CTkLabel(self, text = "Options:")
                label.grid(column = 0,row = 0, padx = 5, pady = 5)

                label1A = ctk.CTkLabel(self, text = "Cell clustering:")
                label1A.grid(column = 0, row = 1)

                options = [i for i in CLUSTER_NAMES if i in self.master.master.master_exp.data.obs.columns]

                self.celltype = ctk.CTkOptionMenu(master = self, values = options, variable = ctk.StringVar(value = ""))
                self.celltype.grid(column = 0, row = 2, padx = 5, pady = 5)

                def refresh_SpaceANOVA_clusters(enter = ""):
                    options = [i for i in CLUSTER_NAMES if i in self.master.master.master_exp.data.obs.columns]
                    self.celltype.configure(values = options)

                self.celltype.bind("<Enter>", refresh_SpaceANOVA_clusters)

                label_1 = ctk.CTkLabel(self, text = "Conditions to Compare:")
                label_1.grid(column = 0, row = 3)

                condition_list = self.master.master.master_exp.data.obs['condition'].unique()

                def comparisons_return():
                    comparison_list = ["All (multicomparison)"]
                    already_used_list = []
                    for i in condition_list:
                        for j in condition_list:
                            if (i != j) and (j not in already_used_list):
                                comparison_list.append(f'{i}_vs_{j}')
                        already_used_list.append(i)
                    return comparison_list

                comparison_list = comparisons_return()

                self.C1 = ctk.CTkOptionMenu(self, values = comparison_list, variable = ctk.StringVar(value = comparison_list[0]))
                self.C1.grid(column = 0, row = 4, padx = 5, pady = 5)

                def refresh_comparisons(enter = ""):
                    comparison_list = comparisons_return()
                    self.C1.configure(values = comparison_list)

                self.C1.bind("<Enter>", refresh_comparisons)

                label_seed = ctk.CTkLabel(self, text = "Select threshold of cell count per ROI \n for excluding comparisons:") 
                label_seed.grid(column = 1, row = 6)

                self.threshold = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "5"))
                self.threshold.grid(column = 1, row = 7, padx = 5, pady = 5)

                label_permutation = ctk.CTkLabel(self, 
                            text = "Number of Permutations \n for permutation correction: \n (0 means no permutation correction)") 
                label_permutation.grid(column = 1, row = 2)

                self.nPerm = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "0"))
                self.nPerm.grid(column= 1, row = 3, padx = 5, pady = 5)

                label_seed = ctk.CTkLabel(self, text = "Select Random seed for \n all SpaceANOVA steps \n (permutations, bootstrapping, etc.):") 
                label_seed.grid(column = 1, row = 4)

                self.seed = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "42"))
                self.seed.grid(column = 1, row = 5, padx = 5, pady = 5)

                self.radFrame = self.Radii_Frame(self)
                self.radFrame.grid(column = 0, row = 8, padx = 5, pady = 5)

                button_run_uni = ctk.CTkButton(self,
                                                text = "Run Spatial Analysis!", 
                                                command = lambda: self.load_and_run_spatial_analysis(min_radius = self.radFrame.minR.get(),
                                                                                                     max_radii = self.radFrame.maxR.get(),
                                                                                                     step = self.radFrame.Radii_step.get(),
                                                                                                     condition_comparison = self.C1.get(),
                                                                                                     seed = self.seed.get()
                                                                                                     ))
                button_run_uni.grid(column = 0, row = 9, padx = 5, pady = 5)
                self.after(200, lambda: self.focus())
                    
            class Radii_Frame(ctk.CTkFrame):
                '''This frame is for the radius metrics required by the fixed_r parameter.
                
                The radii considered are from 0 --> maxR, with the step parameter determining the stepsize 
                at each point between 0 & maxR
                '''
                def __init__ (self, master):
                    super().__init__(master)
                    self.master = master

                    label_1 = ctk.CTkLabel(self, text = "Minimum Radius:")
                    label_1.grid(column = 0, row = 0, padx = 5)
                    self.minR = ctk.CTkEntry(master = self,  textvariable = ctk.StringVar(value = "0"))
                    self.minR.grid(column = 0, row = 1)
                    self.minR.configure(width = 65)

                    label_2 = ctk.CTkLabel(self, text = "Maximum Radius:")
                    label_2.grid(column = 1, row = 0, padx = 5)
                    self.maxR = ctk.CTkEntry(master = self,  textvariable = ctk.StringVar(value = "100"))
                    self.maxR.grid(column = 1, row = 1)
                    self.maxR.configure(width = 65)

                    label_3 = ctk.CTkLabel(self, text = "Radius Step:")
                    label_3.grid(column = 2, row = 0, padx = 5)
                    self.Radii_step = ctk.CTkEntry(master = self,  textvariable = ctk.StringVar(value = "1"))
                    self.Radii_step.grid(column = 2, row = 1)
                    self.Radii_step.configure(width = 65)

            def load_and_run_spatial_analysis(self, min_radius: int, max_radii: int, step: int, condition_comparison: str, seed: int = 42) -> None:
                ''' If not All (multicomparison), this function splits condition_comparison by the string "_vs_" into the two conditions, and
                then loads these conditions & the other provided parameters into the do_spatial_analysis method of the spatial class.
                '''
                import warnings
                warnings.filterwarnings("ignore", message = "divide by zero encountered in divide") #########
                                                        # zero divisions are very common (strictly necessary?) in the vectorised calculation steps
                                                        # The program should properly handle these, so I don't want the console spammed with warnings
                warnings.filterwarnings("ignore", message = "invalid value encountered in divide") 
                permutations = self.nPerm.get()
                celltype_key = self.celltype.get()
                if celltype_key == "":
                    tk.messagebox.showwarning("Warning!", message = 'You must select a clustering!')
                    self.focus()
                    return
                try:
                    permutations = int(permutations)
                    min_rad = int(min_radius)
                    max_radii = int(max_radii)
                    step = int(step)
                    seed = int(seed)
                    threshold = int(self.threshold.get())
                except ValueError:
                    tk.messagebox.showwarning("Warning!", 
                        message = "Radius Parameters, nPerm, and seed must be integers / numerical, but at least one was not!")
                    return
                if (min_rad > max_radii) or ((max_radii - min_rad) % step != 0):
                    tk.messagebox.showwarning("Warning!", 
                       message = "Radius Parameter error: minimum radius must be < maximum, and the interval (max - min) must be evenly divible by the radius step!")
                    return
                
                if condition_comparison == "All (multicomparison)":
                    condition1 = None
                    condition2 = None
                else:
                    condition1, condition2 = condition_comparison.split("_vs_")

                grand_master = self.master.master    ## to lessen the horrifyingly long master.master.... vairables names

                grand_master.master_exp.space_analysis.init_analysis(grand_master.master_exp, 
                                                    output_directory = grand_master.master_exp.directory + "/Spatial_plots", 
                                                    cellType_key = celltype_key)

                grand_master.master_exp.space_analysis.set_fixed_r(min = min_rad, max = max_radii, step = step)
                grand_master.master_exp.space_analysis.set_conditions(condition1 = condition1, condition2 = condition2)
                
                (grand_master.comparison_list, 
                 grand_master._all_comparison_list, 
                 grand_master.comparison_dictionary) = grand_master.master_exp.space_analysis.do_spatial_analysis(permutations = permutations, 
                                                                                                                  seed = seed, 
                                                                                                                  center_on_zero = False,
                                                                                                                  threshold = threshold)
                self.master.plot_button.configure(state = "normal")
                self.master.plot_fx_button.configure(state = "normal")
                self.master.stat.configure(state = "normal")
                grand_master.directory_display.list_dir()
                warnings.filterwarnings("default", message = "divide by zero encountered in divide")  ## undo prior warnings modifications
                warnings.filterwarnings("default", message = "invalid value encountered in divide") 

                space_logger.info(f"""Spatial Analysis Run: 
                                  clusterin = {str(celltype_key)},
                                  max_radii = {str(max_radii)}, min_radii = {str(min_rad)} step = {str(step)},
                                  threshold = {str(threshold)},
                                  conditions = {str([condition1, condition2])},
                                  permutations = {str(permutations)},
                                  random_seed = {str(seed)}""")
                
                warning_window("Spatial Analysis finished")
                
                self.withdraw()

        class launch_heat_plot_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
            '''
            When this window is created, functional ANOVAs are run on Ripley's g for each celltype-to-celltype spatial copmarison.
            This window can then export p-values or adjusted p-values from these ANOVAs, or plot heatmaps from these.

            The window does not close automatically when plots / tables are generated / exported. This is to minimize the need for 
            re-running the statistics everytime the window is opened.
            '''
            def __init__(self, master, stat = 'g'):
                super().__init__()
                self.master = master
                self.p_table, self.p_unadj, self.f_table = self.master.master.master_exp.space_analysis.do_all_functional_ANOVAs(stat = stat)
                if self.master.master.master_exp.space_analysis.stat_error is True:
                    warning_window("At least one of the comparisons in the data encountered an error. It's p-value will be set to 1. \n"
                                   "See the terminal for printed messages detailing which comparison failed")

                label = ctk.CTkLabel(self, text = "Statistics Plot Options:")
                label.grid(column = 0,row = 0, padx = 5, pady = 5)

                label_2 = ctk.CTkLabel(self, 
                            text = "Filename (some details automatically added: \n heatmap --> _heatmap.png, table -> _table.csv):")
                label_2.grid(column = 0, row = 2)

                self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value = f"Spatial_p_value_{stat}"))
                self.filename.grid(column = 1, row = 2, padx = 5, pady = 5)

                label_3 = ctk.CTkLabel(self, text = "Select Table")
                label_3.grid(column = 0, row = 3)

                self.table_selection = ctk.CTkOptionMenu(self, 
                                            variable = ctk.StringVar(value = "adjusted p values"), 
                                            values = ['adjusted p values','unadjusted p values'])
                self.table_selection.grid(column= 1, row= 3, padx = 5, pady = 5)

                button_run_uni = ctk.CTkButton(self,
                                                    text = "Plot Heatmap from Table", 
                                                    command = lambda: self.plot_heatmap(self.table_selection.get()))
                button_run_uni.grid(column = 1, row = 5, padx = 5, pady = 5)

                self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
                self.pop_up.grid(column = 1, row = 6, padx = 3, pady = 3)

                tablebutton = ctk.CTkButton(self,
                                            text = "Export Table", 
                                            command = lambda: self.export_table(self.table_selection.get()))
                tablebutton.grid(column = 0, row = 5, padx = 5, pady = 5)

                self.after(200, lambda: self.focus())

            def plot_heatmap(self, table_type: str) -> None:
                if table_type == "adjusted p values":
                    data_table = self.p_table
                elif table_type == "unadjusted p values":
                    data_table = self.p_unadj
                
                filename = self.filename.get().strip()
                if filename_checker(filename, self):
                    return
                output_directory = f'{self.master.master.master_exp.directory}/Spatial_plots/{filename}.png'
                
                figure = plot_spatial_stat_heatmap(data_table)
                figure.savefig(output_directory, bbox_inches = "tight")
                self.master.master.save_and_display(filename = filename, sizeX = 550, sizeY = 550, parent_folder = "/Spatial_plots")
                self.master.master.directory_display.list_dir()

                space_logger.info(f"Plotted {table_type} heatmap, with the filename = {filename}.png")

                if self.pop_up.get() is True:
                    Plot_window_display(figure)

            def export_table(self, table_type: str) -> None:
                filename = self.filename.get().strip()
                if filename_checker(filename, self):
                    return
                output_directory = f'{self.master.master.master_exp.directory}/Spatial_plots/{filename}.csv'
                if table_type == "adjusted p values":
                    data_table = self.p_table
                elif table_type == "unadjusted p values":
                    data_table = self.p_unadj

                data_table.to_csv(output_directory, index = False)
                space_logger.info(f"Exported spatial statistics table {table_type}, with filename = {filename}.csv")
                TableLaunch(dataframe = data_table, 
                            directory = filename, 
                            width = 1, 
                            height = 1, 
                            table_type = "other", 
                            experiment = None, 
                            favor_table = True, 
                            logger = space_logger)

        class launch_function_plot_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
            '''This window allows the generation & exporting of plots of Ripley's statistics +/- F-values

            The F-values are derived by standard (not functional) ANOVA tests at each radii distance for the chosen Ripley's statistic. 
            These F-values are not corrected for multi-comparison, and are not intended to be used as evidence of significant changes,
            (the determination of statistical significance is meant to be determined by the functional ANOVA across the entire set of radii)
            but if the fANOVAs indicate a statistically significant difference between the conditions, then the F-values in these plots
            can indicate at which distance(s) this significant difference is most likely to be occurring, by looking at the peak F-value(s). 
            '''
            def __init__(self, master):
                super().__init__()
                self.master = master

                label = ctk.CTkLabel(self, text = "Function Plot Options:")
                label.grid(column = 0,row = 0, padx = 5, pady = 5)

                label_1 = ctk.CTkLabel(self, text = "Choose Cell type Comparison (or do all at once):")
                label_1.grid(column = 0, row = 1)

                self.comparison = ctk.CTkOptionMenu(self, 
                                        values = ["Run All"] + self.master.master._all_comparison_list, 
                                        variable = ctk.StringVar(value = "Run All"))  
                self.comparison.grid(column= 1, row= 1, padx = 5, pady = 5)

                def refresh_fxn_plot_comparisons(enter = ""):
                    self.comparison.configure(values = ["Run All"] + self.master.master._all_comparison_list)

                self.comparison.bind("<Enter>", refresh_fxn_plot_comparisons)

                label_2 = ctk.CTkLabel(self, text = "Choose Ripley's Statistic to plot:")                                     
                label_2.grid(column = 0, row = 2)

                self.stat = ctk.CTkOptionMenu(self, values = ["K","L","g"], variable = ctk.StringVar(value = "g"))  
                self.stat.grid(column = 1, row = 2, padx = 5, pady = 5)

                self.plot_f_vals = ctk.CTkCheckBox(master = self, text = "check to plot f values as well" , onvalue = True, offvalue = False)
                self.plot_f_vals.grid(column = 0, row = 3, padx = 5, pady = 5)
                self.plot_f_vals.select()

                button_run_clustering = ctk.CTkButton(self,
                                                    text = "Plot!", 
                                                    command = lambda: self.plot_pairwise_comparison(self.comparison.get(),
                                                                                                    self.stat.get(),
                                                                                                    self.plot_f_vals.get()))
                button_run_clustering.grid(column = 0, row = 5, padx = 5, pady = 5)

                self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
                self.pop_up.grid(column = 0, row = 6, padx = 3, pady = 3)

                self.after(200, lambda: self.focus())

            def plot_pairwise_comparison(self, comparison: str, stat: str, plot_f_vals: str) -> None:
                output_dir = self.master.master.master_exp.space_analysis.output_dir
                if comparison != "Run All":
                    if not overwrite_approval(f"{output_dir}/Functional_plots/{comparison}_{stat}",
                                   file_or_folder = "file", 
                                   GUI_object = self):
                        return
                else:
                    if not overwrite_approval(f"{output_dir}/Functional_plots/",
                                   file_or_folder = "folder", 
                                   GUI_object = self):
                        return
                if not os.path.exists("".join([output_dir, "/Functional_plots"])):
                    os.mkdir("".join([output_dir, "/Functional_plots"]))

                def log_update():
                    space_logger.info(f"""Plotted pairwise function plot(s) with the following settings:
                                    comparison = {comparison}, stat = {stat}""")
                    self.master.master.directory_display.list_dir()

                if (plot_f_vals is False) and (comparison != "Run All"):
                    fx = self.master.master.master_exp.space_analysis.plot_spatial
                    figure = fx(comparison = comparison, 
                                stat_type = stat, 
                                seed = 42)
                    if figure is not None:
                        figure.savefig(f"{output_dir}/Functional_plots/{comparison}_{stat}.png",
                                 bbox_inches = "tight")
                        plt.close()
                        self.master.master.save_and_display(filename = f"{comparison}_{stat}", parent_folder = "/Spatial_plots/Functional_plots")
                        log_update()
                        if self.pop_up.get() is True:
                            Plot_window_display(figure)
                            self.withdraw()
                    else:
                        warning_window("Figure failed to generate! This is usually because the two cell types chosen are never"
                                       "present in the same images. Check terminal error messages")
                        plt.close()

                elif (plot_f_vals is False) and (comparison == "Run All"):
                    self.master.master.master_exp.space_analysis.plot_all_spatial(stat = stat, seed = 42, write = True)
                    log_update()
                    self.destroy()
                    
                elif (plot_f_vals is True) and (comparison != "Run All"):
                    figure = self.master.master.master_exp.space_analysis.plot_spatial_with_stat(comparison = comparison,
                                                                                                  seed = 42,
                                                                                                    stat = stat)
                    if figure is not None:
                        figure.savefig(f"{output_dir}/Functional_plots/{comparison}_{stat}.png", bbox_inches = "tight")
                        plt.close()
                        self.master.master.save_and_display(filename = f"{comparison}_{stat}", parent_folder = "/Spatial_plots/Functional_plots")
                        log_update()

                        if self.pop_up.get() is True:
                            Plot_window_display(figure)
                            self.withdraw()
                    else:
                        warning_window("Figure failed to generate! This is usually because the two cell types chosen are never "
                                       "present in the same images. Check terminal error messages")
                        plt.close()

                elif (plot_f_vals is True) and (comparison == "Run All"):
                    self.master.master.master_exp.space_analysis.plot_all_spatial_with_stat(seed = 42, stat = stat, write = True)
                    log_update()
                    self.destroy()

    def save_and_display(self, filename: str, sizeX: int = 550, sizeY: int = 550, parent_folder: str = "gg_export") -> None:
        ##### This piece of code is currently repeated many times across each plotting function. Should probably be its own function...
        try:
            path = self.master.master.py_exploratory.analysiswidg.cat_exp.directory + f"/{parent_folder}/{filename}.png"
            image = Image.open(path)
        except FileNotFoundError:
            path = f"{parent_folder}/{filename}.png"
            image = Image.open(path)
        except OSError:
            path = f"{parent_folder}/{filename}.png"
            image = Image.open(path)
        image = ctk.CTkImage(image, size = (sizeX,sizeY))
        self.display.update_image(image)

class plot_cell_maps_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    For plotting "cell maps" (scatter plots of cells in the X / Y coordinates of the original image, with cells
    colored by celltype & pointsize determined by cell area)
    '''
    def __init__(self, master):
        super().__init__(master)
        self.title("Make Spatial Plots")
        self.master = master   ### connects this to the Analysis GUI with a simpler self.master relationship
        self.id_val = None
        self.directory = self.master.master_exp.directory
        if self.directory is None:
            tk.messagebox.showwarning("Warning!", message = 'Load an experiment before trying to create cell maps!')
            return 
        
        self.label_1 = ctk.CTkLabel(self, text = "Cells as Masks or as Points:")
        self.label_1.grid(column = 1, row = 2, padx = 5, pady = 5)

        self.masks_or_points = ctk.CTkOptionMenu(self, values = ["masks","points"], variable = ctk.StringVar(value = "masks"))
        self.masks_or_points.grid(column = 1, row = 3, padx = 5, pady = 5)

        label_cluster = ctk.CTkLabel(self, text = "Color cells by which clustering:")
        label_cluster.grid(column = 1, row = 4, padx = 5, pady = 5)

        options = [i for i in CLUSTER_NAMES if i in self.master.master_exp.data.obs.columns]

        self.clustering = ctk.CTkOptionMenu(master = self, values = options, variable = ctk.StringVar(value = ""))
        self.clustering.grid(column = 1, row = 5, padx = 5, pady = 5)

        def refresh_cell_maps_clustering(enter = ""):
            options = [i for i in CLUSTER_NAMES if i in self.master.master_exp.data.obs.columns]
            self.clustering.configure(values = options)

        self.clustering.bind("<Enter>", refresh_cell_maps_clustering)
        
        self.label_2 = ctk.CTkLabel(self, text = "Choose one test image:")
        self.label_2.grid(column = 1, row = 6, padx = 5, pady = 5)

        image_list = [(i[:i.rfind(".ome.fcs")]) for i in sorted(os.listdir(self.directory + "/Analysis_fcs"))]

        self.choose_an_image = ctk.CTkOptionMenu(self, values = image_list, variable = ctk.StringVar(value = ""))
        self.choose_an_image.grid(column = 1, row = 7, padx = 5, pady = 5)

        self.python_button = ctk.CTkButton(master = self, text = "Plot one cell map", 
                                           command = lambda: self.python_run_cell_maps(self.choose_an_image.get(), 
                                                                                       masks = self.masks_or_points.get(),
                                                                                       clustering = self.clustering.get())) 
        self.python_button.grid(column = 1, row = 8, padx = 5, pady = 5)

        self.all_button = ctk.CTkButton(master = self, text = "Plot All cell maps", command = lambda: self.python_run_cell_maps("RUN ALL",  
                                                                                                                                masks = self.masks_or_points.get(),
                                                                                                                                clustering = self.clustering.get())) 
        self.all_button.grid(column = 1, row = 9, padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        #self.pop_up.grid(column = 1, row = 10, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def python_run_cell_maps(self, multi_or_single: str, clustering: str = 'merging', masks: str = "masks") -> None:
        '''
        multi_or_single (str) -- "RUN ALL" or the filename to be run
        '''
        if clustering == "":
            tk.messagebox.showwarning("Warning!", message = 'You must select a clustering to color the cell maps!')
            self.focus()
            return
        if multi_or_single == "":
            tk.messagebox.showwarning("Warning!", message = "You must specify an image if you are not going to do all at once!")
            self.focus()
            return
        
        if multi_or_single == "RUN ALL":
            if not overwrite_approval(f"{self.master.master_exp.directory}/Spatial_plots/cell_maps", file_or_folder = "folder", GUI_object = self):
                return
        else:   
            if not overwrite_approval(f"{self.master.master_exp.directory}/Spatial_plots/cell_maps/{multi_or_single}.ome", file_or_folder = "file", GUI_object = self):
                return
        
        if masks == "masks":
            if multi_or_single != "RUN ALL":
                figure = self.master.squidpy_spatial.plot_cell_map(filename = (multi_or_single + ".ome.fcs"), clustering = clustering)
                self.master.save_and_display(filename = (multi_or_single + ".ome"), parent_folder = "/Spatial_plots/cell_maps")
                if self.pop_up.get() is True:
                    Plot_window_display(figure)                

            else:
                self.master.squidpy_spatial.plot_all_cell_maps(clustering = clustering)
                warning_window("All Cell maps plotted & exported")
            
        else: 
            self.master.master_exp.space_analysis.init_analysis(self.master.master_exp, 
                                                               output_directory = self.master.master_exp.directory + "/Spatial_plots", 
                                                               cellType_key = clustering)
            if multi_or_single != "RUN ALL":
                figure = self.master.master_exp.space_analysis.plot_cell_maps(multi_or_single)
                self.master.save_and_display(filename = (multi_or_single + ".ome"), parent_folder = "/Spatial_plots/cell_maps")

                if self.pop_up.get() is True:
                    Plot_window_display(figure)                
            else:
                self.master.master_exp.space_analysis.plot_cell_maps(multi_or_single = "ALL")
                warning_window("All Cell maps plotted & exported")

        space_logger.info(f"""Plotted cell maps: {multi_or_single}, masks = {masks}, clustering = {clustering}""")  
        self.withdraw()

class SquidpySpatialWidgets(ctk.CTkFrame):
    '''
    '''
    def __init__(self, master, widgets = True):
        super().__init__(master)
        self.master = master
        self.spatial = None
        self.AnalysisObject = None 

        ##place widgets:
        if widgets:    ## this allows easy inheritance from the split off cellularNeighborhoodsFrame class --> consider changing ? (spaghetti code...spaghetti code...)
            labelT = ctk.CTkLabel(master = self, text = "Neighborhood analysis Plots:")
            labelT.grid(row = 0, column = 0, padx = 5, pady = 5)

            interact_matrix = ctk.CTkButton(master = self, text = "Plot Interaction Matrix", command = self.launch_interaction_matrix_window)
            interact_matrix.grid(row = 1, column = 0, padx = 5, pady = 5)

            n_enrich_button = ctk.CTkButton(master = self, text = "Plot Neighborhood Enrichment", command = self.launch_neigh_enrich_window)
            n_enrich_button.grid(row = 2, column = 0, padx = 5, pady = 5)

            centrality_button = ctk.CTkButton(master = self, text = "Plot Centrality", command = self.launch_centrality_window)
            centrality_button.grid(row = 1, column = 1, padx = 5, pady = 5)

            self.disable()

    def add_AnalysisObject(self, object):
        self.AnalysisObject = object
        if object._spatial:
            self.spatial = SpatialNeighbors()
            self.spatial.add_Analysis(self.AnalysisObject)
        self.disable()

    def enable(self):
        ''''''
        for i in self.children:
            child = self.children[i]
            try:
                child.configure(state = "normal")
            except Exception:
                pass

    def disable(self):
        ''''''
        for i in self.children:
            child = self.children[i]
            try:
                child.configure(state = "disabled")
            except Exception:
                pass

    def launch_CN_window(self):
        CellularNeighborhoodWindow(self)

    def launch_interaction_matrix_window(self):
        InteractionMatrixWindow(self)

    def launch_neigh_enrich_window(self):
        NeigborhoodEnrichmentWindow(self)

    def launch_centrality_window(self):
        CentralityWindow(self)

    def do_neighbors(self):
        ''''''
        radius = self.master.load_frame.radius.get()
        n_neighbors = int(self.master.load_frame.n_neigh.get())
        self.spatial.do_neighbors(radius_or_neighbors = radius, number = n_neighbors)
        self.enable()
            
    def plot_neighborhood_enrichment(self, clustering = "merging", facet_by = "None", seed = 42, n_perms = 1000, filename = None):
        ''''''
        figure = self.spatial.plot_neighborhood_enrichment(clustering = clustering, facet_by = facet_by, seed = seed, n_perms = n_perms, filename = filename)
        self.master.save_and_display(filename = filename, parent_folder = self.spatial.save_dir)
        return figure

    def plot_interaction_matrix(self, clustering = "merging", facet_by = "None", filename = None):
        ''''''
        figure = self.spatial.plot_interaction_matrix(clustering = clustering, facet_by = facet_by, filename = filename)
        self.master.save_and_display(filename = filename, parent_folder = self.spatial.save_dir)
        return figure

    def plot_centrality(self, clustering = "merging", score = "closeness_centrality", filename = None):
        ''''''
        figure = self.spatial.plot_centrality(clustering = clustering, score = score, filename = filename)
        self.master.save_and_display(filename = filename, parent_folder = self.spatial.save_dir)
        return figure

    def plot_cell_map(self, filename, clustering = "merging"):
        ''''''
        figure, filename = self.spatial.plot_cell_map(filename = filename, clustering = clustering, save = True)
        self.master.save_and_display(filename = filename[:filename.rfind(".")], parent_folder = self.spatial.save_cell_maps_dir)
        return figure

    def plot_all_cell_maps(self, clustering = "merging"):
        ''''''
        self.spatial.plot_all_cell_maps(clustering = clustering)
        

class NeigborhoodEnrichmentWindow(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    '''
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        label_cluster = ctk.CTkLabel(self, text = "Choose Cell clustering to calculate Neigborhood Enrichments for:")
        label_cluster.grid(padx = 5, pady = 5)

        options = [i for i in CLUSTER_NAMES if i in self.master.spatial.exp.data.obs.columns]

        self.clustering = ctk.CTkOptionMenu(master = self, values = options, variable = ctk.StringVar(value = ""))
        self.clustering.grid(padx = 5, pady = 5)

        def refresh_neighbor_clustering(enter = ""):
            options = [i for i in CLUSTER_NAMES if i in self.master.spatial.exp.data.obs.columns]
            self.clustering.configure(values = options)

        self.clustering.bind("<Enter>", refresh_neighbor_clustering)

        labelXX = ctk.CTkLabel(master = self, text = "Facet statistics / plots by:")
        labelXX.grid(padx = 5, pady = 5)

        self.facet = ctk.CTkOptionMenu(master = self, values = [], variable = ctk.StringVar(value = "None"))
        self.facet.grid(padx = 5, pady = 5)

        def refresh_facet_options(enter = ""):
            try:
                facet_options = [i for i in self.master.spatial.exp.data.obs.columns if i in COLNAMES]
                self.facet.configure(values = ["None"] + list(facet_options))
            except Exception:
                self.facet.configure(values = [])

        self.facet.bind("<Enter>", refresh_facet_options)

        label_nperm = ctk.CTkLabel(master = self, text = "Number of Permutations to perform:")
        label_nperm.grid(padx = 5, pady = 5)

        self.n_perms = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "1000"))
        self.n_perms.grid(padx = 5, pady = 5)

        label_seed = ctk.CTkLabel(master = self, text = "Random seed for permutation steps:")
        label_seed.grid(padx = 5, pady = 5)

        self.seed = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "42"))
        self.seed.grid(padx = 5, pady = 5)

        labelXX = ctk.CTkLabel(master = self, text = "Choose Filename:")
        labelXX.grid(padx = 5, pady = 5)

        self.filename = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "Neighborhood_enrichment"))
        self.filename.grid(padx = 5, pady = 5)

        self.plot_group = ctk.CTkButton(master = self, text = "Plot!", command = self.plot)
        self.plot_group.grid(padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(padx = 3, pady = 3)

        self.after(200, self.focus())

    def plot(self):
        ''''''
        clustering = self.clustering.get()
        if clustering == "":
            tk.messagebox.showwarning(title = "Warning!",
                message = "You must select a clustering!")
            self.focus()
            return
        facet = self.facet.get()
        seed = self.seed.get()
        n_perms = self.n_perms.get()
        try:
            seed = int(seed)
            n_perms = int(n_perms)
        except Exception:
            tk.messagebox.showwarning("Warning!", message = 'Random seed and number of permutations must be integers! Cancelling plot')
            return 
        self.master.spatial.exp.data.obs[clustering] = self.master.spatial.exp.data.obs[clustering].astype('category')
        filename = self.filename.get()
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.spatial.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        figure = self.master.plot_neighborhood_enrichment(clustering = clustering, 
                                                          facet_by = facet, 
                                                          filename = filename, 
                                                          seed = seed, 
                                                          n_perms = n_perms)

        space_logger.info(f"""Neighborhood Enrichment plot made:
                clustering = {clustering}
                facet_by = {facet}
                number_permutation = {str(n_perms)}
                seed = {str(seed)}
                filename = {filename} """)

        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

class CentralityWindow(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    '''
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        label_cluster = ctk.CTkLabel(self, text = "Choose Cell clustering to calculate Centrality for:")
        label_cluster.grid(padx = 5, pady = 5)

        options = [i for i in CLUSTER_NAMES if i in self.master.spatial.exp.data.obs.columns]

        self.clustering = ctk.CTkOptionMenu(master = self, values = options, variable = ctk.StringVar(value = ""))
        self.clustering.grid(padx = 5, pady = 5)

        def refresh_centrality_cluster(enter = ""):
            options = [i for i in CLUSTER_NAMES if i in self.master.spatial.exp.data.obs.columns]
            self.clustering.configure(values = options)

        self.clustering.bind("<Enter>", refresh_centrality_cluster)

        label_cluster = ctk.CTkLabel(self, text = "Choose type of Centrality to plot:")
        label_cluster.grid(padx = 5, pady = 5)

        self.centrality = ctk.CTkOptionMenu(master = self, 
                                            values = ["degree_centrality","closeness_centrality", "average_clustering"], 
                                            variable = ctk.StringVar(value = "degree_centrality"))
        self.centrality.grid(padx = 5, pady = 5)

        labelXX = ctk.CTkLabel(master = self, text = "Choose Filename:")
        labelXX.grid(padx = 5, pady = 5)

        self.filename = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "Centrality"))
        self.filename.grid(padx = 5, pady = 5)

        self.plot_group = ctk.CTkButton(master = self, text = "Plot!", command = self.plot)
        self.plot_group.grid(padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(padx = 3, pady = 3)

        self.after(200, self.focus())

    def plot(self):
        ''''''
        clustering = self.clustering.get()
        if clustering == "":
            tk.messagebox.showwarning(title = "Warning!",
                message = "You must select a clustering!")
            self.focus()
            return
        self.master.spatial.exp.data.obs[clustering] = self.master.spatial.exp.data.obs[clustering].astype('category')
        filename = self.filename.get()
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.spatial.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        
        centrality = self.centrality.get()
        figure = self.master.plot_centrality(clustering = clustering, score = centrality, filename = filename)

        space_logger.info(f"""Centrality Plot made:
                clustering = {clustering}
                score = {centrality}
                filename = {filename} """)

        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()
        
class InteractionMatrixWindow(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    '''
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        label_cluster = ctk.CTkLabel(self, text = "Choose Cell clustering to calculate Interactions for:")
        label_cluster.grid(padx = 5, pady = 5)

        options = [i for i in CLUSTER_NAMES if i in self.master.spatial.exp.data.obs.columns]

        self.clustering = ctk.CTkOptionMenu(master = self, values = options, variable = ctk.StringVar(value = ""))
        self.clustering.grid(padx = 5, pady = 5)

        def refresh_interaction_mat_cluster(enter = ""):
            options = [i for i in CLUSTER_NAMES if i in self.master.spatial.exp.data.obs.columns]
            self.clustering.configure(values = options)

        self.clustering.bind("<Enter>", refresh_interaction_mat_cluster)

        labelXX = ctk.CTkLabel(master = self, text = "Facet statistics / plots by:")
        labelXX.grid(padx = 5, pady = 5)

        self.facet = ctk.CTkOptionMenu(master = self, values = [], variable = ctk.StringVar(value = "None"))
        self.facet.grid(padx = 5, pady = 5)
        def refresh_facet_options(enter = ""):
            try:
                facet_options = [i for i in self.master.spatial.exp.data.obs.columns if i in COLNAMES]
                self.facet.configure(values = ["None"] + list(facet_options))
            except Exception:
                self.facet.configure(values = [])
        self.facet.bind("<Enter>", refresh_facet_options)

        labelXX = ctk.CTkLabel(master = self, text = "Choose Filename:")
        labelXX.grid(padx = 5, pady = 5)

        self.filename = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "Interaction_Matrix"))
        self.filename.grid(padx = 5, pady = 5)

        self.plot_group = ctk.CTkButton(master = self, text = "Plot!", command = self.plot)
        self.plot_group.grid(padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(padx = 3, pady = 3)

        self.after(200, self.focus())

    def plot(self):
        ''''''
        clustering = self.clustering.get()
        if clustering == "":
            tk.messagebox.showwarning(title = "Warning!",
                message = "You must select a clustering!")
            self.focus()
            return
        facet = self.facet.get()
        self.master.spatial.exp.data.obs[clustering] = self.master.spatial.exp.data.obs[clustering].astype('category')
        filename = self.filename.get()
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.spatial.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        
        figure = self.master.plot_interaction_matrix(clustering = clustering, facet_by = facet, filename = filename)
        space_logger.info(f"""Interaction Matrix plotted:
                clustering = {clustering}
                facet_by = {facet}
                filename = {filename} """)

        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

class cellularNeighborhoodsFrame(SquidpySpatialWidgets):
    '''
    '''
    def __init__(self, master):
        super().__init__(master, widgets = False)
        self.master = master
        self.spatial = None
        self.AnalysisObject = None 
        self.clustering = ""
        self.figure = None

        labelZZ = ctk.CTkLabel(master = self, text = "Do a Cellular Neighborhood (CN) clustering by Leiden or FlowSOM")
        labelZZ.grid(row = 0, column = 0, padx = 5, pady = 5, columnspan = 2)

        self.save_load = ctk.CTkButton(master = self, 
                                                  text = "Save or Load a CN annotation", 
                                                  command = self.launch_save_load)
        self.save_load.grid(row = 1, column = 1, padx = 5, pady = 5)

        self.CN_button = ctk.CTkButton(master = self, text = "Launch CN window", command = self.launch_CN_window)
        self.CN_button.grid(row = 1, column = 0, padx = 5, pady = 5)

        self.Plot_clustering_algorithm = ctk.CTkButton(master = self, text = "Plot UMAP (Leiden) or MST (FlowSOM)", command = self.clustermap_window)
        self.Plot_clustering_algorithm.grid(padx = 5, pady = 5)

        Plot_heatmap = ctk.CTkButton(master = self, 
                                     text = "Plot Heatmap of celltype \n mixture in each neighborhood", 
                                     command = self.launch_heatmap_window)
        Plot_heatmap.grid(padx = 5, pady = 5)

        Plot_abundance = ctk.CTkButton(master = self, 
                                     text = "Plot Abundance of celltype \n mixture in each neighborhood", 
                                     command = self.launch_abundance_window)
        Plot_abundance.grid(padx = 5, pady = 5)

        merging = ctk.CTkButton(master = self, 
                                text = "Launch CN annotation / merging window", 
                                command = self.launch_annotation)
        merging.grid(padx = 5, pady = 5)
        
        self.disable()

    def add_Analysis(self, Analysis, squidpy_spatial):
        self.AnalysisObject = Analysis 
        self.spatial = squidpy_spatial
        self.disable()

    def targeted_enable(self):
        ''''''
        if self.AnalysisObject._spatial:
            self.CN_button.configure(state = "normal")
            self.save_load.configure(state = "normal")

    def clustermap_window(self):
        if self.CN_type is None:
            return
        CNUMAPMSTwindow(self)      

    def launch_abundance_window(self):
        CNabundanceWindow(self)

    def launch_heatmap_window(self):
        CNheatmapWindow(self)

    def launch_annotation(self):
        CNannotationWindow(self)

    def launch_save_load(self):
        CNwindowSaveLoad(self)

class CNUMAPMSTwindow(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    '''
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        self.after(200, self.focus())     

        self.title("Plot MST (FlowSOM) or UMAP (Leiden) from Cellular Neighborhood clustering:")

        labelXX = ctk.CTkLabel(master = self, text = "Choose Filename:")
        labelXX.grid(padx = 5, pady = 5)

        if self.master.CN_type == "flowsom":
            filename = "CN_stars"
        elif self.master.CN_type == "leiden":
            filename = "CN_umap"

        self.filename = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = filename))
        self.filename.grid(padx = 5, pady = 5)

        self.plot_group = ctk.CTkButton(master = self, text = "Plot!", command = self.plot)
        self.plot_group.grid(padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot(self):
        figure = self.master.figure
        filename = self.filename.get()
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.spatial.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        
        if self.master.CN_type == "flowsom":
            figure.savefig(self.master.spatial.save_dir + f"/{filename}.png", bbox_inches = "tight")
            self.master.master.save_and_display(f"/{filename}", parent_folder = self.master.spatial.save_dir)
            space_logger.info("""Cell neighborhood flowsom star plot generated""")

        elif self.master.CN_type == "leiden":
            figure.savefig(self.master.spatial.save_dir + f"/{filename}.png", bbox_inches = "tight")
            self.master.master.save_and_display(f"/{filename}", parent_folder = self.master.spatial.save_dir)
            space_logger.info("""Cell neighborhood leiden UMAP plot generated""")

        if self.pop_up.get() is True:
            Plot_window_display(figure)
        self.withdraw()

class CNabundanceWindow(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    '''
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        self.after(200, self.focus())     

        self.title("CN abundance plot Window")

        labelXX = ctk.CTkLabel(master = self, text = "% of cell types in each Neihgborhood from which cell clustering to plot: \n" 
                                                    "(Default is the same clustering used in calculating the neighborhoods)")
        labelXX.grid(padx = 5, pady = 5)

        options = [i for i in ["merging", "metaclustering", "leiden", "classification"] if i in self.master.spatial.exp.data.obs.columns]

        self.clustering = ctk.CTkOptionMenu(master = self, 
                                       values = options, 
                                       variable = ctk.StringVar(value = self.master.clustering))
        self.clustering.grid(padx = 5, pady = 5)

        def refresh_CN_abund_cluster(enter = ""):
            options = [i for i in ["merging", "metaclustering", "leiden", "classification"] if i in self.master.spatial.exp.data.obs.columns]
            self.clustering.configure(values = options)

        self.clustering.bind("<Enter>", refresh_CN_abund_cluster)

        labelXX = ctk.CTkLabel(master = self, text = "Choose Filename:")
        labelXX.grid(padx = 5, pady = 5)

        self.filename = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "CN_abundance_plot"))
        self.filename.grid(padx = 5, pady = 5)

        self.plot_group = ctk.CTkButton(master = self, text = "Plot!", command = self.plot)
        self.plot_group.grid(padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot(self):
        filename = self.filename.get()
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.spatial.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        figure = self.master.spatial.plot_CN_abundance(clustering_col = self.clustering.get())
        figure.savefig(self.master.spatial.save_dir + f"/{filename}.png", bbox_inches = "tight")
        self.master.master.save_and_display(f"/{filename}", parent_folder = self.master.spatial.save_dir)

        space_logger.info("""Cell neighborhood abundance plot generated""")

        if self.pop_up.get() is True:
            Plot_window_display(figure)

        self.withdraw()

class CNheatmapWindow(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    '''
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        self.after(200, self.focus())     

        self.title("CN heatmap Window")

        labelXX = ctk.CTkLabel(master = self, text = "% of cell types in each Neihgborhood from which cell clustering to plot: \n" 
                                                    "(Default is the same clustering used in calculating the neighborhoods)")
        labelXX.grid(padx = 5, pady = 5)

        options = [i for i in ["merging", "metaclustering", "leiden", "classification"] if i in self.master.spatial.exp.data.obs.columns]

        self.clustering = ctk.CTkOptionMenu(master = self, 
                                       values = options, 
                                       variable = ctk.StringVar(value = self.master.clustering))
        self.clustering.grid(padx = 5, pady = 5)

        def refresh_CN_heatmap_cluster(enter = ""):
            options = [i for i in ["merging", "metaclustering", "leiden", "classification"] if i in self.master.spatial.exp.data.obs.columns]
            self.clustering.configure(values = options)

        self.clustering.bind("<Enter>", refresh_CN_heatmap_cluster)

        labelXX = ctk.CTkLabel(master = self, text = "Choose Filename:")
        labelXX.grid(padx = 5, pady = 5)

        self.filename = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "CN_heatmap"))
        self.filename.grid(padx = 5, pady = 5)

        self.plot_group = ctk.CTkButton(master = self, text = "Plot!", command = self.plot)
        self.plot_group.grid(padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot(self):
        filename = self.filename.get()
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.spatial.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        figure = self.master.spatial.plot_CN_heatmap(self.clustering.get(), cmap = 'coolwarm')
        figure.savefig(self.master.spatial.save_dir + f"/{filename}.png", bbox_inches = "tight")
        self.master.master.save_and_display(f"/{filename}", parent_folder = self.master.spatial.save_dir)
        space_logger.info("""Cell neighborhood heatmap generated""")
        if self.pop_up.get() is True:
            Plot_window_display(figure)

        self.withdraw()

class CNannotationWindow(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    '''
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        self.title("Cluster Merging Window")
        self.master = master
        self.directory = self.master.AnalysisObject.directory
        self.id_out = None
        self.number = len(self.master.AnalysisObject.data.obs['CN'].unique())

        self.new = self.new_merge_frame(self)
        self.new.grid(column = 0, row = 0, rowspan = 4, padx = 5, pady = 5)

        self.after(200, lambda: self.focus())

    def annotate(self, id):
        id = id.lstrip().rstrip() #### removes any leading and trailing spaces
        if " " in id:
            id = id.replace(" ","_")  #### now replaces any remaining spaces (with would break the underlying R code) with underscores
            warning_window(f"Blank spaces inside your merging name have been replaced with underscores: the merging name will now be saved as {id}")

        merging_file_path = self.directory + "/mergings/" + id + ".csv"
        if filename_checker(id, self):
            return
        if not overwrite_approval(merging_file_path, file_or_folder = "file", GUI_object = self):
            return

        self.new.table.add_id(id)
        self.new.table.recover_input()
        self.new.table.special_to_csv()
        self.master.AnalysisObject.do_cluster_merging(file_path = merging_file_path,
                                                      groupby_column = "CN",
                                                      output_column = "CN")
        
        space_logger.info(f"""Cell neighborhood merging/annotation save to {merging_file_path}""")
        self.destroy()


    class new_merge_frame(ctk.CTkFrame):
        def __init__(self,master):
            super().__init__(master)
            self.master = master

            self.label_2 = ctk.CTkLabel(self, text = "Name new Merging:")
            self.label_2.grid(column = 3, row = 0)

            self.id_new = ctk.CTkEntry(self, textvariable = ctk.StringVar(value  = "merging_CNs_1"))
            self.id_new.grid(column = 3, row = 1)

            self.label3 = ctk.CTkLabel(self, text = "Load a previously made \n Merging Table:")
            self.label3.grid(column = 4, row = 0)

            def refreshOption(enter = ""):
                made_mergings = ["blank"] + [i for i in sorted(os.listdir(self.master.directory + "/mergings/")) if i.find("CN") != -1] 
                self.reload_merge.configure(values = made_mergings)

            self.reload_merge = ctk.CTkOptionMenu(self, 
                                    values = ["blank"], 
                                    command = lambda choice: self.table.repopulate_table(self.master.directory + "/mergings/" + choice))
            self.reload_merge.grid(column = 4, row = 1)
            self.reload_merge.bind("<Enter>", refreshOption)
            
            self.table = TableWidget_merging(self,
                                             width = 1, 
                                             directory = self.master.directory + "/mergings", 
                                             input_column = self.master.master.AnalysisObject.data.obs['CN'])
            self.table.grid(column = 3, row = 2, columnspan = 4, padx = 5, pady = 5)

            self.button = ctk.CTkButton(master = self, 
                                        text = "Accept Table Entry & Run Cluster Merging", 
                                        command = lambda: self.master.annotate(self.id_new.get().strip()))
            self.button.grid(column = 3, row = 7, padx = 5, pady = 5)

class TableWidget_merging(ctk.CTkScrollableFrame):
    '''
    This class is a modified and streamlined form of the old table widget used in the Image processing portion of the pipeline
    Goals: have it be a bit more streamlined, general purpose (or maybe not....), and less hard-coded
    '''
    def __init__(self, master, width, directory, input_column):
        '''
        id is the name the user gave it
        '''
        super().__init__(master)
        self.id = None
        self.input_column = input_column
        self.directory = directory
        self.to_add = ""
        self.table_dataframe = pd.DataFrame()
        self.table_dataframe['original_cluster'] = list(input_column.sort_values().unique())
        self.table_dataframe['new_cluster'] = "unknown"
        self.configure(width = width*(len(self.table_dataframe.columns)*200), height = 650)
        self.widgetframe = pd.DataFrame()
        self.populate_table()

    def repopulate_table(self, new_dataframe_path: str) -> None:
        for i in self.widgetframe.iloc[:,0]:
            i.destroy()
        for i in self.widgetframe.iloc[:,1]:
            i.destroy()
        if new_dataframe_path[new_dataframe_path.rfind("/")+1:] == "blank":
            self.table_dataframe['original_cluster'] = [i for i in range(1, self.maxK + 1)]
            self.table_dataframe['new_cluster'] = "unknown"
        else:
            self.table_dataframe = pd.read_csv(new_dataframe_path)
        self.widgetframe = pd.DataFrame()
        self.populate_table()        

    def add_id(self, id: str) -> None:
        self.id = id
        self.to_add = f'/{id}.csv'

    def populate_table(self) -> None:
        self.add_entry_column(0, disable = True)
        self.add_entry_column(1)

    def recover_input(self) -> None:
        '''
        This method recovers the user entered data from the GUI into the self.table_dataframe dataframe,
        and writes the recovered data to a .csv file.
        '''
        out_list = []
        for i in self.widgetframe.iloc[:,0]:
            out = i.get().strip()
            out_list.append(int(out))
        self.table_dataframe.iloc[:,0] = out_list
        out_list2 = []
        for i in self.widgetframe.iloc[:,1]:
            out = i.get().strip()
            out_list2.append(out)
        self.table_dataframe.iloc[:,1] = out_list2

    def special_to_csv(self, dataframe = None):
        if dataframe is None:
            dataframe = self.table_dataframe
        dataframe.to_csv(self.directory + self.to_add, index = False)
        #Analysis_widget_logger.info(f"Wrote merging file, with name '{self.id}', with the values: \n {str(dataframe)}")

    def add_entry_column(master, col_num: int, offset: int = 0, disable: bool = False) -> None:
            '''
            Creates a column of plain labels inside the scrollable table, of the col_num specified (zero-indexed). 
            Values = a list of the values to be in the drop menu of the comboboxes
            Offset shifts the column location to the right within the scrollable frame (offset of 1 needed for tables that 
                                                                                        display the index as well).
            '''
            column_list = []
            col1_title = ctk.CTkLabel(master = master, text = master.table_dataframe.columns[col_num])
            col1_title.grid(column = col_num + offset, row = 0, padx = 5, pady = 3)
            for i,ii in enumerate(master.table_dataframe.iloc[:,col_num]):
                variable = ctk.StringVar(value = str(ii))
                col_dropdown = ctk.CTkEntry(master = master, textvariable = variable)
                if disable is True:
                    col_dropdown.configure(state = "disabled")
                col_dropdown.grid(column = col_num + offset, row = i + 1, padx = 5, pady = 3)
                column_list.append(col_dropdown)
            master.widgetframe[str(col_num)] = column_list


class CNwindowSaveLoad(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    '''
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        labelA = ctk.CTkLabel(master = self, text = "Save / Load Cellular Neighborhoods designations")
        labelA.grid(row = 0, column = 1, padx = 3, pady = 3, columnspan = 2)

        labelC = ctk.CTkLabel(master = self, text = "Set identifier for file save:")
        labelC.grid(row = 2, column = 0, padx = 3, pady = 3)

        self.identifier = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "1"))
        self.identifier.grid(row = 2, column = 1, padx = 3, pady = 3)

        run_button = ctk.CTkButton(master = self, text = "Save CN clustering", command = self.save)
        run_button.grid(row = 3, column = 0, padx = 3, pady = 3, columnspan = 2)

        spacer = ctk.CTkLabel(master = self, text = "")
        spacer.grid(row = 2, column = 4, padx = 3, pady = 3)

        labelD = ctk.CTkLabel(master = self, text = "Select CN clustering to load:")
        labelD.grid(row = 2, column = 3, padx = 3, pady = 3)

        def refresh(enter = ""):
            saved_clusterings =  [i for i in sorted(os.listdir(self.master.master.master_exp.clusterings_dir)) if (i.find("cellular_neighborhood") != -1)]
            self.path.configure(values = saved_clusterings)

        self.path = ctk.CTkOptionMenu(master = self, values = [""], variable = ctk.StringVar(value = ""))
        self.path.grid(row = 2, column = 4, padx = 3, pady = 3)
        self.path.bind("<Enter>", refresh)

        load_button = ctk.CTkButton(master = self, text = "Load CN clustering", command = self.reload)
        load_button.grid(row = 3, column = 3, padx = 3, pady = 3, columnspan = 2)

        self.after(200, self.focus())

    def save(self):
        identifier = self.identifier.get()
        if filename_checker(identifier, self):   ##TODO: check if warning is proper
            return
        if not overwrite_approval(f"{self.master.master.master_exp.clusterings_dir}/CN_cellular_neighborhood_{identifier}.csv", file_or_folder = "file", GUI_object = self):
            return
        self.master.master.master_exp.export_clustering("CN", identifier = f"_cellular_neighborhood_{identifier}") ## use 'cellular_neighborhood' in path name to control behaviour
                                                                                                                        ## when loading from Analysis tab (?)
        space_logger.info(f"""Saved current cell neighborhoods with the following filename: CN_cellular_neighborhood_{identifier}.csv""")

    def reload(self, load_into_experiment = True):
        if self.path.get() == "":
            tk.messagebox.showwarning(title = "Warning!",
                                      message = "Please select a CN save to reload!")
            self.focus()
            return
        path = self.master.master.master_exp.clusterings_dir + "/" + self.path.get()
        self.master.master.master_exp.load_clustering(path)
        self.master.figure = None
        self.master.enable()
        self.master.Plot_clustering_algorithm.configure(state = "disabled")
        if load_into_experiment:
            self.master.AnalysisObject.data.obs['CN'] = list(self.master.spatial.exp.data.obs['CN'])
            CLUSTER_NAMES_append_CN()

        self.master.clustering = ""

        ## TODO: test!
        try: ## either space_analysis or data_table attributes may not exist
            if np.sum(np.array(self.master.master.master_exp.data_table['cellType'] == 'CN')) > 0:
                self.master.master.widgets.disable_buttons() 
        except Exception:
            pass

        space_logger.info(f"""Loaded cell neighborhoods from the following filepath: {path}""")

        self.withdraw()

class CellularNeighborhoodWindow(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    '''
    '''
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        labelA = ctk.CTkLabel(master = self, text = "Create Cellular Neighborhoods (CNs) with FlowSOM or Leiden")
        labelA.grid(row = 0, column = 1, padx = 3, pady = 3, columnspan = 2)

        labelAA = ctk.CTkLabel(master = self, text = "Cell clustering to calculate neighborhoods from:")
        labelAA.grid(row = 1, column = 1, padx = 3, pady = 3, columnspan = 2)

        options = [i for i in ["merging", "metaclustering", "leiden", "classification"] if i in self.master.spatial.exp.data.obs.columns]

        self.celltype = ctk.CTkOptionMenu(master = self, values = options, variable = ctk.StringVar(value = ""))
        self.celltype.grid(column = 1, row = 2, padx = 5, pady = 5, columnspan = 2)

        def refresh_CN_cluster(enter = ""):
            options = [i for i in ["merging", "metaclustering", "leiden", "classification"] if i in self.master.spatial.exp.data.obs.columns]
            self.celltype.configure(values = options)

        self.celltype.bind("<Enter>", refresh_CN_cluster)

        labelC = ctk.CTkLabel(master = self, text = "UMAP+Leiden or FlowSOM:")
        labelC.grid(row = 3, column = 1, padx = 3, pady = 3, columnspan = 2)

        self.type = ctk.CTkOptionMenu(master = self, values = ["FlowSOM", "Leiden"], variable = ctk.StringVar(value = "FlowSOM"))
        self.type.grid(row = 4, column = 1, padx = 3, pady = 3, columnspan = 2)

        labelG = ctk.CTkLabel(master = self, text = "Seed = ")
        labelG.grid(row = 5, column = 1, padx = 3, pady = 3)

        self.seed = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "42"))
        self.seed.grid(row = 5, column = 2, padx = 3, pady = 3)

        spacer = ctk.CTkLabel(master = self, text = "")
        spacer.grid(row = 6)

        labelD = ctk.CTkLabel(master = self, text = "(FlowSOM) number of metaclusters = ")
        labelD.grid(row = 7, column = 0, padx = 3, pady = 3)

        self.CN_num = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "20"))
        self.CN_num.grid(row = 7, column = 1, padx = 3, pady = 3)

        labelE = ctk.CTkLabel(master = self, text = "(FlowSOM) XY dims = ")
        labelE.grid(row = 8, column = 0, padx = 3, pady = 3)

        self.FlowSOM_XY = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "10"))
        self.FlowSOM_XY.grid(row = 8, column = 1, padx = 3, pady = 3)

        labelF = ctk.CTkLabel(master = self, text = "(FlowSOM) training iterations =")
        labelF.grid(row = 9, column = 0, padx = 3, pady = 3)

        self.rlen = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "100"))
        self.rlen.grid(row = 9, column = 1, padx = 3, pady = 3)


        labelH = ctk.CTkLabel(master = self, text = "(Leiden) UMAP minimum distance = ")
        labelH.grid(row = 7, column = 2, padx = 3, pady = 3)

        self.min_dist = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "0.1"))
        self.min_dist.grid(row = 7, column = 3, padx = 3, pady = 3)

        labelI = ctk.CTkLabel(master = self, text = "(Leiden) resolution = ")
        labelI.grid(row = 8, column = 2, padx = 3, pady = 3)

        self.resolution = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "1"))
        self.resolution.grid(row = 8, column = 3, padx = 3, pady = 3)

        run_button = ctk.CTkButton(master = self, text = "Run Cellular Neighborhood clustering!", command = self.run_cellular_neighborhoods)
        run_button.grid(row = 10, column = 1, padx = 3, pady = 3, columnspan = 2)

        self.load_into_experiment = ctk.CTkCheckBox(master = self, text = "Load into main Analysis?", onvalue = True, offvalue = False)
        #self.load_into_experiment.grid(row = 11, column = 1, padx = 3, pady = 3, columnspan = 2)
        self.load_into_experiment.select()

        self.after(1000, self.focus())

    def run_cellular_neighborhoods(self):
            ''''''
            celltype = self.celltype.get()
            if celltype == "":
                tk.messagebox.showwarning(title = "Warning!",
                    message = "You must select a clustering!")
                self.focus()
                return
            seed = int(self.seed.get())
            load_into_experiment = self.load_into_experiment.get()
            if self.type.get() == "FlowSOM":
                self.master.CN_type = "flowsom"
                CN_num = int(self.CN_num.get())
                rlen = int(self.rlen.get())
                FlowSOM_XY = int(self.FlowSOM_XY.get())
                figure = self.master.spatial.do_cellular_neighborhoods(clustering = celltype, 
                                                              leiden_or_flowsom = "FlowSOM",
                                                              n_clusters = CN_num, 
                                                              rlen = rlen, 
                                                              seed = seed, 
                                                              xdim = FlowSOM_XY, 
                                                              ydim = FlowSOM_XY)
                space_logger.info(f"""Ran Cell Neighborhood clustering with: 
                    celltype  = {celltype}
                    seed = {str(seed)}
                    type = FlowSOM
                    n_clusters = {str(CN_num)}
                    xydim = {str(FlowSOM_XY)}
                    rlen = {str(len)}""")
                
            elif self.type.get() == "Leiden":
                self.master.CN_type = "leiden"
                resolution = float(self.resolution.get())
                min_dist = float(self.min_dist.get())
                figure = self.master.spatial.do_cellular_neighborhoods(clustering = celltype, 
                                                          seed = seed, 
                                                          resolution = resolution,
                                                          min_dist = min_dist,
                                                          leiden_or_flowsom = "Leiden")
                space_logger.info(f"""Ran Cell Neighborhood clustering with: 
                    celltype  = {celltype}
                    seed = {str(seed)}
                    type = Leiden
                    resolution = {str(resolution)}
                    mind_dist = {str(min_dist)}""")


            if load_into_experiment:
                self.master.AnalysisObject.data.obs['CN'] = list(self.master.spatial.exp.data.obs['CN'])
                CLUSTER_NAMES_append_CN()

            self.master.clustering = celltype
            self.master.figure = figure
            ## TODO: test!
            try: ## either space_analysis or data_table attributes may not exist
                if np.sum(np.array(self.master.master.master_exp.data_table['cellType'] == 'CN')) > 0:
                    self.master.master.widgets.disable_buttons() 
            except Exception:
                pass
            self.master.enable()
            self.withdraw()

class dist_transform_frame(ctk.CTkFrame):
    ''''''
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.edt_object = SpatialEDT()
        self.edt_object.add_Analysis(self.master.master_exp)

        label = ctk.CTkLabel(master = self, text = "Use a Pixel Classifier to calculate" 
                                                   "\n Distance from cells to all pixel classes"
                                                   "\n of the classifier (except background):")
        label.grid(row = 0, column = 0, pady = 3, padx = 3)

        self.button_load = ctk.CTkButton(master = self, text = "Calculate Distance Transform", command = self.launch_load_window)
        self.button_load.grid(row = 1, column = 0, pady = 3, padx = 3)

        label = ctk.CTkLabel(master = self, text = "Plotting functions (only for marker_class = spatial_edt)"
                                                    "\n if you selected a different marker_class while loading"
                                                    "\n then go the previous tab (Analysis) to access this data")
        label.grid(row = 2, column = 0, pady = 3, padx = 3)

        button_heatmap = ctk.CTkButton(master = self, 
                                       text = "Plot Heatmap of every loaded distance transform", 
                                       command = self.launch_heatmap_window)
        button_heatmap.grid(row = 3, column = 0, pady = 3, padx = 3)

        button_dist = ctk.CTkButton(master = self, 
                                    text = "Plot Distributions of a distance transform", 
                                    command = self.launch_distrib_window)
        button_dist.grid(row = 4, column = 0, pady = 3, padx = 3)

        button_stats= ctk.CTkButton(master = self, 
                                    text = "Do basic Statistics using distance transform data", 
                                    command = self.launch_stat_window)
        button_stats.grid(row = 5, column = 0, pady = 3, padx = 3)

        self.reload = ctk.CTkButton(master = self, 
                                    text = "Reload a previously done edt", 
                                    command = self.launch_reload_window)
        self.reload.grid(row = 1, column = 1, pady = 3, padx = 3)

        self.disable()

    def enable(self):
        ''''''
        for i in self.children:
            child = self.children[i]
            try:
                child.configure(state = "normal")
            except Exception:
                pass

    def disable(self):
        ''''''
        for i in self.children:
            child = self.children[i]
            try:
                child.configure(state = "disabled")
            except Exception:
                pass
        try: 
            if self.master.master_exp._spatial:
                self.button_load.configure(state = 'normal')
                self.reload.configure(state = 'normal')
        except AttributeError:   ## if self.master.master_exp._spatial does not exist
            pass

    def re_load_analysis_object(self):
        self.edt_object = SpatialEDT()
        self.edt_object.add_Analysis(self.master.master_exp)
        try:
            if not self.master.master_exp._spatial:
                self.disable()
        except AttributeError:   ## if self.master.master_exp._spatial does not exist
            pass

    def launch_load_window(self):
        dist_transform_window(self.master)

    def launch_reload_window(self):
        edt_reload_window(self.master)

    def launch_heatmap_window(self):
        if np.array(self.edt_object.exp.data.var['marker_class'] == "spatial_edt").sum() == 1:
            tk.messagebox.showwarning("Warning!", 
                                      message = 'There must at least be 2 EDTs loaded as marker_class == "spatial_edt" for a heatmap to be plotted!')
            return
        edt_heatmap_window(self)

    def launch_distrib_window(self):
        edt_dist_window(self)

    def launch_stat_window(self):
        edt_stat_window(self)

class edt_heatmap_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        self.experiment = self.master.edt_object.exp

        label = ctk.CTkLabel(master = self, text = 'Plot Distributions of Distance Transforms:')
        label.grid(column = 0, row = 0, padx = 3, pady = 3, columnspan = 2)

        label1 = ctk.CTkLabel(master = self, text = 'Select metadata to Group with:')
        label1.grid(column = 0, row = 1, padx = 3, pady = 3)

        options = [i for i in CLUSTER_NAMES if i in self.master.edt_object.exp.data.obs.columns]

        self.groupby_column = ctk.CTkOptionMenu(master = self, values = options, variable = ctk.StringVar(value = ""))
        self.groupby_column.grid(column = 1, row = 1, padx = 3, pady = 3)

        def refresh_edt_heatmap_cluster(enter = ""):
            options = [i for i in CLUSTER_NAMES if i in self.master.edt_object.exp.data.obs.columns]
            self.groupby_column.configure(values = options)

        self.groupby_column.bind("<Enter>", refresh_edt_heatmap_cluster)

        label2 = ctk.CTkLabel(master = self, text = "Select Filename:")
        label2.grid(column = 0, row = 2, padx = 3, pady = 3)

        self.filename = ctk.CTkEntry(master = self, textvariable= ctk.StringVar(value = "dist_transform_heatmap"))
        self.filename.grid(column = 1, row = 2, padx = 3, pady = 3)

        plot_button = ctk.CTkButton(master = self, text = "Plot!", command = self.plot)
        plot_button.grid(column = 0, row = 3, padx = 3, pady = 3, columnspan = 2)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(padx = 3, pady = 3)

        self.after(200, self.focus())

    def plot(self):
        groupby_col = self.groupby_column.get()
        filename = self.filename.get()
        if filename_checker(filename, self):
            return
        if not overwrite_approval(self.experiment.directory + f"/Spatial_plots/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        figure = self.master.edt_object.plot_edt_heatmap(groupby_col, marker_class = "spatial_edt")
        figure.savefig(self.experiment.directory + f"/Spatial_plots/{filename}.png", bbox_inches = "tight")
        self.master.master.save_and_display(f"/{filename}", parent_folder = self.experiment.directory + "/Spatial_plots")

        space_logger.info(f"""Plotted distance transform horizontal boxplot: 
                        groupby_col  = {groupby_col}
                        filename = {filename}""")

        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

class edt_dist_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        self.experiment = self.master.edt_object.exp

        label = ctk.CTkLabel(master = self, text = 'Plot Distributions of Distance Transforms:')
        label.grid(column = 0, row = 0, padx = 3, pady = 3, columnspan = 2)

        label1 = ctk.CTkLabel(master = self, text = 'Select distance transform to plot:')
        label1.grid(column = 0, row = 1, padx = 3, pady = 3)

        options = list(self.experiment.data.var['antigen'].iloc[np.array(self.experiment.data.var['marker_class'] == "spatial_edt")])

        self.var_column = ctk.CTkOptionMenu(master = self, 
                                                values = options, 
                                                variable = ctk.StringVar(value = ""))
        self.var_column.grid(column = 1, row = 1, padx = 3, pady = 3)

        def refresh_edt_dist_var(enter = ""):
            options = list(self.experiment.data.var['antigen'].iloc[np.array(self.experiment.data.var['marker_class'] == "spatial_edt")])
            self.var_column.configure(values = options)

        self.var_column.bind("<Enter>", refresh_edt_dist_var)

        label1a = ctk.CTkLabel(master = self, text = 'Select clustering:')
        label1a.grid(column = 0, row = 2, padx = 3, pady = 3)

        options = [i for i in CLUSTER_NAMES if i in self.master.edt_object.exp.data.obs.columns]

        self.subset_col = ctk.CTkOptionMenu(master = self, values = ["None"] + options, variable = ctk.StringVar(value = ""))
        self.subset_col.grid(column = 1, row = 2, padx = 3, pady = 3)

        def refresh_edt_dist_cluster(enter = ""):
            options = [i for i in CLUSTER_NAMES if i in self.master.edt_object.exp.data.obs.columns]
            self.subset_col.configure(values = options)

        self.subset_col.bind("<Enter>", refresh_edt_dist_cluster)

        label1b = ctk.CTkLabel(master = self, text = 'Select  metadata to facet on:')
        label1b.grid(column = 0, row = 3, padx = 3, pady = 3)

        self.facet_col = ctk.CTkOptionMenu(master = self, 
                                           values = ["condition","patient_id"], 
                                           variable = ctk.StringVar(value = "condition"))
        self.facet_col.grid(column = 1, row = 3, padx = 3, pady = 3)

        label2 = ctk.CTkLabel(master = self, text = "Select Filename:")
        label2.grid(column = 0, row = 4, padx = 3, pady = 3)

        self.filename = ctk.CTkEntry(master = self, textvariable= ctk.StringVar(value = "distance_transform_distribution"))
        self.filename.grid(column = 1, row = 4, padx = 3, pady = 3)

        plot_button = ctk.CTkButton(master = self, text = "Plot!", command = self.plot)
        plot_button.grid(column = 0, row = 5, padx = 3, pady = 3)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(padx = 3, pady = 3)

        self.after(200, self.focus())

    def plot(self):
        var_column = self.var_column.get()
        filename = self.filename.get()
        if filename_checker(filename, self):
            return
        if not overwrite_approval(self.experiment.directory + f"/Spatial_plots/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        subset_col = self.subset_col.get()
        if subset_col == "None":
            subset_col = None
        facet_col = self.facet_col.get()

        figure = self.master.edt_object.plot_horizontal_boxplot(var_column = var_column, subset_col = subset_col, facet_col = facet_col)
        space_logger.info(f"""Plotted distance transform horizontal boxplot: 
                        var_column  = {var_column}
                        subset_col = {subset_col}
                        facet_col = {facet_col}
                        filename = {filename}""")
        
        figure.savefig(self.experiment.directory + f"/Spatial_plots/{filename}.png", bbox_inches = "tight")
        self.master.master.save_and_display(f"/{filename}", parent_folder = self.experiment.directory + "/Spatial_plots")

        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()


class edt_stat_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        label = ctk.CTkLabel(master = self, text = 'Plot Distributions of Distance Transforms:')
        label.grid(column = 0, row = 0, padx = 3, pady = 3, columnspan = 2)

        label1 = ctk.CTkLabel(master = self, text = 'Select clustering:')
        label1.grid(column = 0, row = 1, padx = 3, pady = 3)

        options = [i for i in CLUSTER_NAMES if i in self.master.edt_object.exp.data.obs.columns]

        self.groupby_column = ctk.CTkOptionMenu(master = self, 
                                                values = options, 
                                                variable = ctk.StringVar(value = ""))
        self.groupby_column.grid(column = 1, row = 1, padx = 3, pady = 3)

        def refresh_edt_options(enter = ""):
            options = [i for i in CLUSTER_NAMES if i in self.master.edt_object.exp.data.obs.columns]
            self.groupby_column.configure(values = options)

        self.groupby_column.bind("<Enter>", refresh_edt_options)

        label2 = ctk.CTkLabel(master = self, text = 'Select statistic:')
        label2.grid(column = 0, row = 2, padx = 3, pady = 3)

        self.stat = ctk.CTkOptionMenu(master = self, 
                                                values = ['mean','median'], 
                                                variable = ctk.StringVar(value = "mean"))
        self.stat.grid(column = 1, row = 2, padx = 3, pady = 3)

        label3 = ctk.CTkLabel(master = self, text = 'Select test:')
        label3.grid(column = 0, row = 3, padx = 3, pady = 3)

        self.test = ctk.CTkOptionMenu(master = self, 
                                                values = ['ANOVA','Kruskal'], 
                                                variable = ctk.StringVar(value = "ANOVA"))
        self.test.grid(column = 1, row = 3, padx = 3, pady = 3)

        label4 = ctk.CTkLabel(master = self, text = "Select Filename:")
        label4.grid(column = 0, row = 4, padx = 3, pady = 3)

        self.filename = ctk.CTkEntry(master = self, textvariable= ctk.StringVar(value = "distance_transform_stats"))
        self.filename.grid(column = 1, row = 4, padx = 3, pady = 3)

        plot_button = ctk.CTkButton(master = self, text = "Do Stats!", command = self.do_stats)
        plot_button.grid(column = 0, row = 5, padx = 3, pady = 3)

        self.after(200, self.focus())

    def do_stats(self):
        filename = self.filename.get()
        if filename_checker(filename, self):
            return
        if not overwrite_approval(self.master.edt_object.exp.directory + f"/Spatial_plots/{filename}.csv", file_or_folder = "file", GUI_object = self):
            return
        groupby_column = self.groupby_column.get()
        stat = self.stat.get()
        test = self.test.get().lower()
        output = self.master.edt_object.plot_edt_statistics(groupby_column = groupby_column, 
                                                     marker_class = 'spatial_edt',
                                                     statistic = stat,
                                                     test = test,
                                                     filename = self.master.edt_object.exp.directory + f"/Spatial_plots/{filename}.csv")
        space_logger.info(f"""Ran statistics on distance transform: 
                        groupby_column  = {groupby_column}
                        stat = {stat}
                        test = {test}""")
        
        TableLaunch(dataframe = output, 
                    directory = "",
                    width = 1, 
                    height = 1, 
                    table_type = "other",
                    experiment = None, 
                    favor_table = True, 
                    logger = space_logger)


class dist_transform_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        self.title("Append Distance Transform Data from pixel classifier")

        label = ctk.CTkLabel(master = self, 
            text  = "Enter Pixel classifier filepath:")
        label.grid(row = 0, column = 0, padx = 5, pady = 5, columnspan = 2)

        self.pixel_class_entry = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = ""))
        self.pixel_class_entry.grid(row = 1, column = 0, padx = 5, pady = 5)

        pixel_class_selection = ctk.CTkButton(master = self, text = "find in file explorer", command = self.launch_px_finder)
        pixel_class_selection.grid(row = 1, column = 1, padx = 5, pady = 5)

        label_merge = ctk.CTkLabel(master = self, 
            text  = "Select classifier output folder \n (subfolder within the classifier):")
        label_merge.grid(row = 2, column = 0, padx = 5, pady = 5)

        self.merge = ctk.CTkOptionMenu(master = self, values = ["clasification_maps", "merged_classification_maps"], variable = ctk.StringVar(value = "classification_maps"))
        self.merge.grid(row = 2, column = 1, padx = 5, pady = 5)

        label = ctk.CTkLabel(master = self, 
            text  = "Select distance transforms' marker_class:")
        label.grid(row = 3, column = 0, padx = 5, pady = 5)

        self.marker_class = ctk.CTkOptionMenu(master = self, values = ["spatial_edt"] + MARKER_CLASSES, variable = ctk.StringVar(value = "spatial_edt"))
        self.marker_class.grid(row = 3, column = 1, padx = 5, pady = 5)

        label = ctk.CTkLabel(master = self, 
            text  = "---> Select 'spatial_edt' if you intend on making plots with this data in this tab (The Spatial tab),"
                    "\n\t Otherwise, if you intend on using this parameter in the main Analysis tab, "
                    "\n\t (say in FlowSOM clustering, or in combination with antigens) then select 'type' or 'state'")
        label.grid(row = 4, column = 0, padx = 5, pady = 5, columnspan = 2)


        label = ctk.CTkLabel(master = self, 
            text  = "Choose Smoothing of pixel classifier (must be an integer -- 0 for no smoothing):")
        label.grid(row = 5, column = 0, padx = 5, pady = 5)

        self.smoothing = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "10"))
        self.smoothing.grid(row = 5, column = 1, padx = 5, pady = 5)

        label2 = ctk.CTkLabel(master = self, 
            text  = "Distance statistic:")
        label2.grid(row = 6, column = 0, padx = 5, pady = 5)

        self.stat = ctk.CTkOptionMenu(master = self, values = ["mean", "median", "min"], variable = ctk.StringVar(value = "mean"))
        self.stat.grid(row = 6, column = 1, padx = 5, pady = 5)

        self.normalize = ctk.CTkCheckBox(master = self, text = "Normalize distance by average of each image? \n (ignored if statistic is min)", onvalue = True, offvalue = False)
        self.normalize.grid(row = 7, column = 1, padx = 5, pady = 5)

        button = ctk.CTkButton(master = self, text = "Add distance transform data", command = self.do_dist_transform)
        button.grid(row = 8, column = 0 , padx = 5, pady= 5)

        self.checkbox = ctk.CTkCheckBox(master = self, text = "Check to export the EDT maps \n to /Spatial_plots/edt_maps", onvalue = True, offvalue = False)
        self.checkbox.grid()

        self.after(200, self.focus()) 

    def launch_px_finder(self):
        choice = tk.filedialog.askdirectory()   
        self.pixel_class_entry.configure(textvariable = ctk.StringVar(value = choice))
        self.after(200, self.focus())

    def do_dist_transform(self) -> None:
        auto_panel = True
        stat = self.stat.get()
        maps = f"/{self.merge.get()}"
        pixel_class_folder = str(self.pixel_class_entry.get())
        if pixel_class_folder == "":
            tk.messagebox.showwarning("Warning!", 
                                      message = 'Please select a pixel classifier folder!')
            self.focus()
            return
        mask_folder = str(self.master.master_exp.input_mask_folder)
        smoothing = int(self.smoothing.get())
        marker_class = self.marker_class.get()
        if self.checkbox.get():
            load_distance_transform = self.master.master_exp.directory + "/Spatial_plots/edt_maps"
            if not os.path.exists(self.master.master_exp.directory + "/Spatial_plots"):
                os.mkdir(self.master.master_exp.directory + "/Spatial_plots")
            if not os.path.exists(load_distance_transform):
                os.mkdir(load_distance_transform)
            load_distance_transform = load_distance_transform + f"/{pixel_class_folder[pixel_class_folder.rfind('/') + 1:]}"
        else:
            load_distance_transform = None
        save_folder = self.master.master_exp.directory[:self.master.master_exp.directory.rfind("/")] + "/spatial_edts"
        if not os.path.exists(save_folder):
            os.mkdir(save_folder)
        save_path = save_folder + f"/{pixel_class_folder[pixel_class_folder.rfind('/') + 1:]}.csv"
        if not overwrite_approval(save_path, file_or_folder = "file", GUI_object = self):
            return
        # distances_panel = 
        self.master.test_edt.edt_object.load_distance_transform(pixel_class_folder, 
                                                                mask_folder,
                                                                maps = maps, 
                                                                smoothing = smoothing, 
                                                                marker_class = marker_class, 
                                                                auto_panel = auto_panel,
                                                                stat = stat,
                                                                background = True,
                                                                normalized = self.normalize.get(),
                                                                output_edt_folder = load_distance_transform,
                                                                save_path = save_path)
        space_logger.info(f"""Loaded distance transform: 
                        pixel classifier = {pixel_class_folder}
                        smoothing = {str(smoothing)}
                        marker_class = {marker_class}
                        stat = {stat}
                        normalize = {str(self.normalize.get())}""")
        self.master.test_edt.enable()
        if marker_class == "spatial_edt":
            MARKER_CLASSES_append_spatial_edt()
        self.withdraw()


class edt_reload_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        self.folder = self.master.master_exp.directory[:self.master.master_exp.directory.rfind("/")] + "/spatial_edts"
        if not os.path.exists(self.folder):
            os.mkdir(self.folder)

        label = ctk.CTkLabel(master = self, text = 'Reload a previously performed distance transform:')
        label.grid(column = 0, row = 0, padx = 3, pady = 3, columnspan = 2)

        label1 = ctk.CTkLabel(master = self, text = 'Select File:')
        label1.grid(column = 0, row = 1, padx = 3, pady = 3)

        self.choice = ctk.CTkOptionMenu(master = self, 
                                                values = sorted(os.listdir(self.folder)),
                                                variable = ctk.StringVar(value = ""))
        self.choice.grid(column = 1, row = 1, padx = 3, pady = 3)

        def refresh_edt_reload(enter = ""):
            self.choice.configure(values = sorted(os.listdir(self.folder)))

        self.choice.bind("<Enter>", refresh_edt_reload)

        label2 = ctk.CTkLabel(master = self, text = 'Select marker_class for all distance transforms in this file:')
        label2.grid(column = 0, row = 2, padx = 3, pady = 3)

        self.marker_class = ctk.CTkOptionMenu(master = self, 
                                                values = ['spatial_edt', 'type', 'state', 'none'], 
                                                variable = ctk.StringVar(value = "spatial_edt"))
        self.marker_class.grid(column = 1, row = 2, padx = 3, pady = 3)

        plot_button = ctk.CTkButton(master = self, text = "Reload", command = self.reload)
        plot_button.grid(column = 0, row = 4, padx = 3, pady = 3)

        self.after(200, self.focus())

    def reload(self):


        if self.choice.get() == "":
            tk.messagebox.showwarning("Warning!", 
                                      message = 'Please select an EDT to load!')
            self.focus()
            return
        self.path = f"{self.folder}/{self.choice.get()}"
        marker_class = self.marker_class.get()
        distance_transform = pd.read_csv(self.path)
        self.master.test_edt.edt_object.reload_edt(distance_transform, marker_class)

        self.master.test_edt.enable()
        if marker_class == "spatial_edt":
            MARKER_CLASSES_append_spatial_edt()

        self.destroy()
