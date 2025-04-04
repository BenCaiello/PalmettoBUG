'''
This module contains the GUI widgets for the fourth tab of the program, which coordinates the CATALYST-style analysis of the single-cell data 
derived from IMC / solution-mode CyTOF.
None of the functions / classes in this file should be available in the public (non-GUI) API of PalmettoBUG.

This file is licensed under the GPL3 license. No significant portion of the code here is believed to be derived from another project 

    (in the sense of needing to be separately / simultaneously licensed)

any code that IS copied/derived from an existing project, of course, remains under the original copyright / license as well -- 
although here it is licensed as GPL-3 inside the PalmettoBUG.

The structure / labeling IS heavily based on the API / outputs of the CATALYST R package and the saesys lab FLOWSOM_Python package -- 
however the code that is directly derived from those is not copied here, but called from the ..Analysis_functions.Analysis_functions module. 

Both CATALYST and the FLOWSOM_Python package are similarly licensed under GPL3 or GPL>=2:

CATALYST: https://github.com/HelenaLC/CATALYST/tree/main 
FLOWSOM_Python: https://github.com/saeyslab/FlowSOM_Python
'''

import os
from typing import Union
import tkinter as tk
import customtkinter as ctk

from PIL import Image
import pandas as pd
import numpy as np
import seaborn as sns
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from .._vendor import sigfig
from ..Analysis_functions.Analysis import Analysis
from ..Utils.sharedClasses import DirectoryDisplay, CtkSingletonWindow, Analysis_logger, TableLaunch, filename_checker, overwrite_approval, warning_window

__all__ = []

homedir = __file__.replace("\\","/")
homedir = homedir[:(homedir.rfind("/"))]
## do it twice to get up to the top level directory:
homedir = homedir[:(homedir.rfind("/"))]                         ############## Needed for accessing asset folder for image display

CLUSTER_NAMES = ["metaclustering", "merging", "classification", "leiden"]
MARKER_CLASSES = ["type","state","none"]
COLNAMES = ['patient_id', 'sample_id', 'condition']

def CLUSTER_NAMES_append_CN():
    global CLUSTER_NAMES
    if "CN" not in CLUSTER_NAMES:
        CLUSTER_NAMES = CLUSTER_NAMES + ["CN"]

def MARKER_CLASSES_append_spatial_edt():
    global MARKER_CLASSES
    if "spatial_edt" not in MARKER_CLASSES:
        MARKER_CLASSES = MARKER_CLASSES + ["spatial_edt"]
                                                           

class Analysis_py_widgets(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.cat_exp = Analysis(in_gui = True)
        
        self.display2 = MatPlotLib_Display(self)
        self.display2.grid(column = 0, row = 0, padx = 5, pady = 5, rowspan = 2)

        self.directory_display = DirectoryDisplay(self)
        self.directory_display.grid(column = 0, row = 2, rowspan = 4)

        self.analysis_bank = self.analysis_function_buttons(self)
        self.analysis_bank.grid(column = 1, row = 0, sticky = "nsew")

        self.plot_bank = self.plotting_function_buttons(self)
        self.plot_bank.grid(column = 2, row = 0, sticky = "nsew")

        self.hypothesis_widget = Hypothesis_widget(self)
        self.hypothesis_widget.grid(column = 1, row  = 1, columnspan = 2, sticky = "nsew")
        self.hypothesis_widget.configure(fg_color = "gray56")

        self.data_export_buton = ctk.CTkButton(master = self, 
                                               text = 'Export Data Table', 
                                               command = self.launch_data_table_exportation_window)
        self.data_export_buton.grid(column = 1 , row = 2, padx = 5, pady = 5)
        self.data_export_buton.configure(state = 'disabled')

        self.data_import_buton = ctk.CTkButton(master = self, 
                                               text = 'Import from a Data Table', 
                                               command = self.launch_data_table_importation_window)
        self.data_import_buton.grid(column = 1, row = 3, padx = 5, pady = 5)

        self.region = ctk.CTkButton(master = self, text = 'Load Regionprop data', command = self.launch_regionprop)
        self.region.grid(column = 2, row = 2, padx = 5, pady = 5)
        self.region.configure(state = 'disabled')

        self.scatter = ctk.CTkButton(master = self, text = 'Scatterplot', command = self.launch_scatterplot)
        self.scatter.grid(column = 2, row = 3, padx = 5, pady = 5)
        self.scatter.configure(state = 'disabled')

        self.classy_masker = ctk.CTkButton(master = self, text = 'Clustering to classy masks', command = self.launch_classy_masker)
        self.classy_masker.grid(column = 2, row = 4, padx = 5, pady = 5)
        self.classy_masker.configure(state = 'disabled')


    def initialize_experiment_and_buttons(self, directory: str) -> None: 
        ### This function is to separate the initialization of the widgets and their placement from the initialization 
        #       of the Analysis_experiment & the commands (since these require the directory & data first)
        self.directory = directory
        global Analysis_widget_logger
        Analysis_widget_logger = Analysis_logger(directory).return_log() 
        self.cat_exp.load_data(self.directory)  
        self.data_export_buton.configure(state = 'normal')
        self.scatter.configure(state = 'normal')
        self.classy_masker.configure(state = 'normal')
        regionprops_directory = self.cat_exp.directory[:-4] + "/regionprops/"
        try:
            roi_areas = os.listdir(regionprops_directory)   ## TODO: Fix this -- it is not working.
            if len(roi_areas) > 0:
                self.region.configure(state = 'normal')
                regions = True
            else:
                print('no files in the regionprops directory -- spatial analysis for this data will be unavailable')
                regions = False
        except Exception:
            print("No regionprops directory -- spatial analysis for this data will not be available.")
            regions = False

        self.analysis_bank.initialize_buttons()
        self.plot_bank.initialize_buttons()
        self.hypothesis_widget.initialize_buttons()

        if regions:
            self.master.master.Spatial.widgets.add_Analysis(self.cat_exp)      ## this method in spatial also handles the proper activation of widgets in the spatial frame
        else:
            self.master.master.Spatial.widgets.add_Analysis(self.cat_exp)

    def setup_dir_disp(self, directory: str) -> None:
        self.directory_display.setup_with_dir(directory, self, png = self.display2)

    def launch_scatterplot(self):
        scatterplot_window(self)

    def launch_classy_masker(self):
        classy_masker_window(self)

    def launch_leiden(self):
        do_leiden_window(self)

    def launch_UMAP_window(self) -> None:
        UMAP_window(self)

    def launch_ClusterVGroup(self) -> None:
        ClusterVGroup(self)

    def launch_distrib_window(self) -> None:
        PrelimDistribPlotWindow(self)

    def launch_plot_UMAP_window(self) -> None:
        Plot_UMAP_window(self)

    def launch_cluster_window(self) -> None:
        Cluster_Window(self)

    def launch_Exprs_Heatmap_window(self) -> None:
        Plot_ExprsHeatMap_window(self)

    def launch_Plot_Counts_per_ROI_window(self) -> None:
        Plot_Counts_per_ROI_window(self)

    def launch_Plot_histograms_per_ROI_window(self) -> None:
        Plot_histograms_per_ROI_window(self)

    def launch_MDS_window(self) -> None:
        Plot_MDS_window(self)

    def launch_NRS_window(self) -> None:
        Plot_NRS_window(self)

    def launch_abundance_window(self) -> None:
        plot_cluster_abundances_window(self)

    def launch_cluster_heatmap_window(self) -> None:
        plot_cluster_heatmap_window(self)

    def launch_plot_cluster_expression_window(self) -> None:
        plot_cluster_expression_window(self)
    
    def launch_cluster_stats_window(self) -> None:
        cluster_statistics_window(self)

    def launch_regionprop(self) -> None:
        region_props_panel = self.cat_exp.regionprops_data
        if region_props_panel is not None:
            TableLaunch(1, 1, 
                        self.cat_exp.directory, 
                        dataframe = region_props_panel, 
                        table_type = "Regionprops_panel.csv", 
                        experiment = self.cat_exp, 
                        logger = Analysis_widget_logger)
        
    def launch_cluster_merging(self) -> None:
        if ("metaclustering" not in self.cat_exp.data.obs.columns) and ("leiden" not in self.cat_exp.data.obs.columns):
            tk.messagebox.showwarning("Warning!", message = "No metaclustering / leiden available for merging! Load or run a clustering first!")
            return
        cluster_merging_window(self)

    def launch_drop_restore(self) -> None:
        image_drop_restore_window(self)

    def launch_scaling(self) -> None:
        Scaling_window(self)
    
    def launch_cluster_save_load(self) -> None:
        Cluster_save_load_window(self)

    def launch_data_table_exportation_window(self) -> None:
        data_table_exportation_window(self, self.cat_exp.data)
    
    def launch_data_table_importation_window(self) -> None:    ### This could be pushed back to the app&entry 
                                                                # as a separate entrance method (?)
        directory = tk.filedialog.askopenfilename()
        if directory == "":
            return
        directory  = directory.replace("\\" , "/")
        Analysis_directory = directory[:directory.rfind("/")] + f"/Analysis_loaded_from_{directory[directory.rfind('/') + 1 : -4]}"
        if not os.path.exists(Analysis_directory):
            os.mkdir(Analysis_directory)
        self.cat_exp = Analysis(in_gui = True)
        self.cat_exp.load_data(Analysis_directory, csv = directory)

        self.directory = Analysis_directory
        log_dir = directory[:(directory.rfind("/"))]
        global Analysis_widget_logger
        Analysis_widget_logger = Analysis_logger(log_dir).return_log() 
        Analysis_widget_logger.info(f"Loaded from CSV: {directory}")

        self.data_export_buton.configure(state = 'normal')
        self.scatter.configure(state = 'normal')
        self.classy_masker.configure(state = 'normal')
        self.analysis_bank.initialize_buttons()
        self.plot_bank.initialize_buttons()
        self.hypothesis_widget.initialize_buttons()
        self.setup_dir_disp(Analysis_directory)
        self.master.master.Spatial.widgets.add_Analysis(self.cat_exp)
    
    def launch_combat_window(self) -> None:
        combat_window(self)

    def reload_experiment(self) -> None:
        self.cat_exp = Analysis(in_gui = True)
        self.cat_exp.load_data(self.directory)
        Analysis_widget_logger.info("Reloaded Experiment!")
        with open(self.directory + '/Analysis_panel.csv') as file:
            Analysis_widget_logger.info(f"Loaded Analysis_panel file, with values: \n {file.read()}")
        with open(self.directory + '/metadata.csv') as file:
            Analysis_widget_logger.info(f"Loaded metadata file, with values: \n {file.read()}")

        ## re-disable buttons that depend on clustering, etc.
        #self.plot_bank.cluster_vs_group.configure(state = 'disabled')
        self.plot_bank.umap_plot.configure(state = 'disabled')

        #### re-disable Spatial widgets:\
        self.master.master.Spatial.widgets.add_Analysis(self.cat_exp)        
        
    def save_and_display(self, filename: str, 
                         sizeX: int = 550, 
                         sizeY: int = 550, 
                         parent_folder: Union[str, None] = None) -> None:
        ''''''
        if parent_folder is None:
            parent_folder = self.cat_exp.save_dir
            to_read = f"{parent_folder}/{filename}.png"
        else:
            to_read = self.directory + f"/{parent_folder}/{filename}.png"
        image = Image.open(to_read)
        image = ctk.CTkImage(image, size = (sizeX,sizeY))
        self.display2.update_image(image)
        self.directory_display.list_dir()

    class analysis_function_buttons(ctk.CTkFrame):
        def __init__ (self, master):
            super().__init__(master)
            self.master = master

            label = ctk.CTkLabel(self, text = "Analysis Functions:")
            label.grid(column = 0, row = 0)

            self.reload = ctk.CTkButton(master = self, text = "Reload Analysis, Panel, and Metadata Files")
            self.reload.grid(column = 0, row = 1, padx = 5, pady = 5)
            self.reload.configure(state = "disabled")

            self.scaling = ctk.CTkButton(master = self, text = "Scale Antigen Data (Highly Recommended!)")
            self.scaling.grid(column = 0, row = 2, padx = 5, pady = 5)
            self.scaling.configure(state = "disabled")

            self.drop_restore = ctk.CTkButton(master = self, text = "Filter cells from analysis")
            self.drop_restore.grid(column = 0, row = 3, padx = 5, pady = 5)
            self.drop_restore.configure(state = "disabled")

            self.combat_button = ctk.CTkButton(master = self, text = "Do comBat Batch Correction")
            self.combat_button.grid(column = 0, row = 4, padx = 5, pady = 5)
            self.combat_button.configure(state = "disabled")

            label2 = ctk.CTkLabel(self, text = "Dimensionality Reduction:")
            label2.grid(column = 0, row = 5)

            self.umap_block = ctk.CTkButton(master = self, text = "Run Dimensionality Reduction (UMAP)")
            self.umap_block.grid(column = 0, row = 6, padx = 5, pady = 10)
            self.umap_block.configure(state = "disabled")

            cluster_anno = ctk.CTkLabel(self, text = "Clustering / Annotation functions:")
            cluster_anno.grid(column = 0, row = 7)

            self.cluster_block = ctk.CTkButton(master = self, text = "Do FlowSOM clustering")
            self.cluster_block.grid(column = 0, row = 8, padx = 5, pady = 5)
            self.cluster_block.configure(state = "disabled")

            self.test_leiden = ctk.CTkButton(master = self, text = 'Do Leiden Clustering') 
            self.test_leiden.grid(column = 0, row = 9, padx = 5, pady = 5)
            self.test_leiden.configure(state = "disabled")

            self.cluster_merging = ctk.CTkButton(master = self, text = "Do a cluster Merging")
            self.cluster_merging.grid(column = 0, row = 10, padx = 5, pady = 5)
            self.cluster_merging.configure(state = "disabled")
            
            self.load_save_clustering = ctk.CTkButton(master = self, text = "Save or Load Clustering or Merging")
            self.load_save_clustering.grid(column = 0, row = 11, padx = 5, pady = 5)
            self.load_save_clustering.configure(state = "disabled")

        def initialize_buttons(self) -> None:
            self.reload.configure(state = "normal", command = self.master.reload_experiment)
            self.drop_restore.configure(state = "normal", command = self.master.launch_drop_restore)
            self.scaling.configure(state = "normal", command = self.master.launch_scaling)
            self.load_save_clustering.configure(state = "normal", command = self.master.launch_cluster_save_load)
            self.cluster_block.configure(state = "normal", command  = self.master.launch_cluster_window)
            self.test_leiden.configure(state = "normal", command  = self.master.launch_leiden)
            self.umap_block.configure(state = "normal", command = self.master.launch_UMAP_window)
            self.cluster_merging.configure(state = "normal", command = self.master.launch_cluster_merging)
            self.combat_button.configure(state = "normal", command = self.master.launch_combat_window)

    class plotting_function_buttons(ctk.CTkFrame):
        def __init__ (self, master):
            super().__init__(master)
            self.master = master

            ############# These buttons should be open from the start (don't NECESSARILY require clustering before use)
            label = ctk.CTkLabel(master = self, text = "Plots that don't necessarily need clustering")
            label.grid(column = 0, row = 0, padx = 5, pady = 10, sticky = "ew")

            self.countplot = ctk.CTkButton(master = self, text = "Plot Counts per ROI")
            self.countplot.grid(column = 0, row = 1, padx = 5, pady = 5)
            self.countplot.configure(state = "disabled")

            self.histogram_button = ctk.CTkButton(master = self, text = "Plot KDE Histograms per ROI")
            self.histogram_button.grid(column = 1, row = 1, padx = 5, pady = 5)
            self.histogram_button.configure(state = "disabled")

            self.MDS_button = ctk.CTkButton(master = self, text = "Make MDS plot")
            self.MDS_button.grid(column = 0, row = 2, padx = 5, pady = 5)
            self.MDS_button.configure(state = "disabled")

            self.distrib_plots = ctk.CTkButton(master = self, text = "Plot Group Expression Distributions")
            self.distrib_plots.grid(column = 1, row = 2, padx = 5, pady = 5)
            self.distrib_plots.configure(state = "disabled")

            self.ExprsHeatmapbutton = ctk.CTkButton(master = self, text = "Plot Expression Heatmap")
            self.ExprsHeatmapbutton.grid(column = 1, row = 3, padx = 5, pady = 5)
            self.ExprsHeatmapbutton.configure(state = "disabled")

            self.NRS_button = ctk.CTkButton(master = self, text = "Make NRS plot")
            self.NRS_button.grid(column = 0, row = 3, padx = 5, pady = 5)
            self.NRS_button.configure(state = "disabled")

            ################ These buttons should be closed before dimensionality reduction (UMAP / PCA) 
            label2 = ctk.CTkLabel(master = self, text = "This requires dimensionality reduction first:")
            label2.grid(column = 0, row = 4, padx = 5, pady = 10, sticky = "ew")

            self.umap_plot = ctk.CTkButton(master = self, text = "Plot Dimensionality Reduction (UMAP)")
            self.umap_plot.grid(column = 0, row = 5, padx = 5, pady = 5)
            self.umap_plot.configure(state = "disabled")

            ############## These buttons should be disabled before clustering
            label1 = ctk.CTkLabel(master = self, text = "These Plots require clustering to be performed first:")
            label1.grid(column = 0, row = 6, padx = 5, pady = 10, sticky = "ew")

            self.cluster_vs_group = ctk.CTkButton(master = self, text = "Plot Cluster Expression Distributions")
            self.cluster_vs_group.grid(column = 0, row = 7, padx = 5, pady = 5)
            self.cluster_vs_group.configure(state = "disabled")

            self.cluster_heatmap = ctk.CTkButton(master = self, text = "Cluster Heatmap")
            self.cluster_heatmap.grid(column = 0, row = 8, padx = 5, pady = 5)
            self.cluster_heatmap.configure(state = "disabled")

            self.cluster_exp = ctk.CTkButton(master = self, text = "Cluster Expression KDE Histograms")
            self.cluster_exp.grid(column = 1, row = 7, padx = 5, pady = 5)
            self.cluster_exp.configure(state = "disabled")

            self.cluster_statistics = ctk.CTkButton(master = self, text = "Cluster Statistics (to assist in merging)")
            self.cluster_statistics.grid(column = 1, row = 8, padx = 5, pady = 5)
            self.cluster_statistics.configure(state = "disabled") 

            label3 = ctk.CTkLabel(master = self, text = "Clustering first is required. \n Merging is also recommended:")
            label3.grid(column = 1, row = 9, padx = 5, pady = 10, sticky = "ew")

            self.abundance_button = ctk.CTkButton(master = self, text = "Make abundance plot")
            self.abundance_button.grid(column = 1, row = 10, padx = 5, pady = 5)
            self.abundance_button.configure(state = "disabled")

        def initialize_buttons(self) -> None:
            ### goal: decouple widget placement & initialization from data loading & button activation
            self.countplot.configure(state = "normal", command = self.master.launch_Plot_Counts_per_ROI_window)
            self.histogram_button.configure(state = "normal", command = self.master.launch_Plot_histograms_per_ROI_window)
            self.MDS_button.configure(state = "normal", command = self.master.launch_MDS_window)
            self.ExprsHeatmapbutton.configure(state = "normal", command = self.master.launch_Exprs_Heatmap_window)
            self.NRS_button.configure(state = "normal", command = self.master.launch_NRS_window)
            self.distrib_plots.configure(state = "normal", command = self.master.launch_distrib_window)
            self.cluster_vs_group.configure(state = "normal", command = self.master.launch_ClusterVGroup)
            self.cluster_heatmap.configure(state = "normal", command = self.master.launch_cluster_heatmap_window)
            self.cluster_statistics.configure(state = "normal", command = self.master.launch_cluster_stats_window)
            self.cluster_exp.configure(state = "normal", command = self.master.launch_plot_cluster_expression_window)
            self.umap_plot.configure(command = self.master.launch_plot_UMAP_window)     ## leave disabled (activated with DR)
            self.abundance_button.configure(state = "normal", command = self.master.launch_abundance_window)

class PrelimDistribPlotWindow(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("Plot Cluster vs. Group Expression")
        self.master = master
        self.clustering_done = False

        label_1 = ctk.CTkLabel(self, text = "Choose Cell Grouping:")
        label_1.grid(column = 0, row = 0, padx = 3, pady = 3)

        option_list = COLNAMES   
        self.clustering = ctk.CTkOptionMenu(master = self, variable = ctk.StringVar(value = "sample_id"), values = option_list)
        self.clustering.grid(column = 1, row = 0, padx = 3, pady = 3)

        label_1 = ctk.CTkLabel(self, text = "Choose Marker Class:")
        label_1.grid(column = 0, row = 1, padx = 3, pady = 3)

        option_list = ['All'] + MARKER_CLASSES
        self.marker_class = ctk.CTkOptionMenu(master = self, variable = ctk.StringVar(value = "type"), values = option_list)
        self.marker_class.grid(column = 1, row = 1, padx = 3, pady = 3)
        
        label_1 = ctk.CTkLabel(self, text = "Choose Type of graph:")
        label_1.grid(column = 0, row = 2, padx = 3, pady = 3)

        option_list = ['bar','violin']
        self.option_menu = ctk.CTkOptionMenu(master = self, variable = ctk.StringVar(value = "violin"), values = option_list)
        self.option_menu.grid(column = 1, row = 2, padx = 3, pady = 3)

        label_1 = ctk.CTkLabel(self, text = "Choose Type of comparison:")
        label_1.grid(column = 0, row = 3, padx = 3, pady = 3)

        option_list2 = ['group vs. others','Raw Group values (no substraction of rest of dataset)']
        self.type_of_comp = ctk.CTkOptionMenu(master = self, 
                variable = ctk.StringVar(value = "Raw Group values (no substraction of rest of dataset)"), 
                values = option_list2)
        self.type_of_comp.grid(column = 1, row = 3, padx = 3, pady = 3)

        label_1 = ctk.CTkLabel(self, text = "Choose Filename:")
        label_1.grid(column = 0, row = 4, padx = 3, pady = 3)

        self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value = "Group_raw_dist"))
        self.filename.grid(column = 1, row = 4, padx = 3, pady = 3)

        button_run = ctk.CTkButton(self,
                                text = "Plot", 
                                command = lambda: self.plot_clusterV(self.clustering.get(), 
                                                                        self.option_menu.get(), 
                                                                        self.type_of_comp.get(), 
                                                                        self.filename.get().strip(), 
                                                                        marker_class = self.marker_class.get()))
        button_run.grid(column = 1, row = 5, padx = 3, pady = 3)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(column = 1, row = 6, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot_clusterV(self, clustering_column: str, 
                      type_of_graph, 
                      type_of_comp: str, 
                      filename: str, 
                      marker_class: str = "type") -> None:
        ''''''
        if filename_checker(filename, self):
            return
        available_columns = [i for i in (CLUSTER_NAMES + COLNAMES) if i in list(self.master.cat_exp.data.obs.columns)]
        if clustering_column == "":
            tk.messagebox.showwarning(title = "Warning!",
                message = "You must select a clustering!")
            self.focus()
            return
        elif clustering_column not in available_columns:
            tk.messagebox.showwarning(title = "Warning!",
                message = f"Clustering =  {clustering_column}  is not available in the dataset! \n Of {str(COLNAMES)}" +
                    f"\n These are currently available: {str(available_columns)}")
            self.focus()
            return
        if not overwrite_approval(f"{self.master.cat_exp.save_dir}/{type_of_graph}{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        if filename is not None:  
            select_dict = {"Raw Group values (no substraction of rest of dataset)": "raw", "group vs. others": "vs"}
            type_of_comp = select_dict[type_of_comp]
            figure = self.master.cat_exp.plot_cluster_distributions(filename = filename, 
                                                                    groupby_column = clustering_column, 
                                                                    plot_type = type_of_graph, 
                                                                    comp_type = type_of_comp,
                                                                    marker_class = marker_class)
            self.master.save_and_display(filename = f"{type_of_graph}{filename}",sizeX = 550, sizeY = 550)

            Analysis_widget_logger.info(f"""Plotted cluster vs group plot with settings: 
                                        groupby_column column = {clustering_column},
                                        plot_type = {str(type_of_graph)}
                                        comp_type = {type_of_comp},
                                        marker_class = {marker_class}, 
                                        filename = {type_of_graph}{filename}.png""")
            
            if self.pop_up.get() is True:
                Plot_window_display(figure)
                self.withdraw()
            else:
                self.destroy()


class Cluster_save_load_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__ (self, master):
        super().__init__(master)
        self.title("Save or Load a FlowSOM Clustering")
        self.master = master

        label = ctk.CTkLabel(self, 
            text = """Save or Load a FlowSOM metaclustering, a manual merging of a FlowSOM metaclustering, or a pixel classification: 
            \n Only attempt loading a clustering / merging if the experiment is identical to what it was in the last clustering
            \n Only attempt loading a pixel classification if the classy masks \n and the masks used to generate the data for the analysis have the same origin""")
        label.grid(column = 0, columnspan = 4, row = 0, padx = 5, pady = 5)

        spacing_button = ctk.CTkButton(master = self, text = "")
        spacing_button.configure(height = 5, width = 1350, fg_color = "blue", hover_color = "blue", state = "disabled")
        spacing_button.grid(column = 0, columnspan = 8, row = 1, padx = 5, pady = 5, sticky = "ew")

        label_1 = ctk.CTkLabel(self, text = "Name of Column to save:")
        label_1.grid(column = 0, row = 2)

        list_of_columns = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns]

        self.load_type = ctk.CTkOptionMenu(master = self, values = list_of_columns, variable = ctk.StringVar(value = ""))
        self.load_type.grid(column= 0, row = 3, padx = 5, pady = 5)

        def refresh_load_options(enter = ""):
            list_of_columns = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns]
            self.load_type.configure(values = list_of_columns)

        self.load_type.bind("<Enter>", refresh_load_options)

        label_1 = ctk.CTkLabel(self, 
            text = "Save Identifier / filename \n" +
             "(Metaclustering / Merging / Classification \n will be automatically added, as appropriate, to the identifier):")
        label_1.grid(column = 0, row = 4)

        self.save_identifier = ctk.CTkEntry(self, textvariable = ctk.StringVar(value = "Seed_1234"))
        self.save_identifier.grid(column= 0, row = 5, padx = 5, pady = 5)

        button_run_clustering = ctk.CTkButton(self,
                                            text = "Save metaclustering / merging / classification to this Analysis", 
                                            command = lambda: self.save_clustering(self.load_type.get(), 
                                                                                   self.save_identifier.get().strip()))
        button_run_clustering.grid(column = 0, row = 6, padx = 5, pady = 5)

        divider_button = ctk.CTkButton(master = self, text = "")
        divider_button.configure(height = 350, width = 5, fg_color = "blue", hover_color = "blue", state = "disabled")
        divider_button.grid(column = 1, rowspan = 6, row = 2, padx = 5, sticky = "ns")

        divider_button = ctk.CTkButton(master = self, text = "")
        divider_button.configure(height = 350, width = 5, fg_color = "blue", hover_color = "blue", state = "disabled")
        divider_button.grid(column = 3, rowspan = 6, row = 2, padx = 5, sticky = "ns")

        ## If there is no clustering in the current experiment, block the button
        def refresh_button(enter = ""):
            obs_col = (self.master.cat_exp.data.obs.columns)
            if ("metaclustering" not in obs_col) and ("merging" not in obs_col) and ("classification" not in obs_col) and ("leiden" not in obs_col) and (button_run_clustering.cget('state') == "normal"):
                button_run_clustering.configure(state = "disabled")
            else:
                button_run_clustering.configure(state = "normal")
        button_run_clustering.bind("<Enter>", refresh_button)
        refresh_button()

        label_2 = ctk.CTkLabel(self, 
            text = "Name of saved clustering to load: \n (these are all the metaclustering / merging / classification \n" +
                "that you have previously saved in this analysis)")
        label_2.grid(column = 2, row = 2)
        
        def refresh1(enter = ""):
            list_of_saved_clusterings = sorted(os.listdir(self.master.cat_exp.directory + "/clusterings"))
            self.load_identifier.configure(values = list_of_saved_clusterings)

        self.load_identifier = ctk.CTkOptionMenu(master = self, values = [""], variable = ctk.StringVar(value = ""))
        self.load_identifier.grid(column = 2, row = 3, padx = 5, pady = 5)
        self.load_identifier.bind("<Enter>", refresh1)

        button_run_clustering = ctk.CTkButton(self,
                                            text = "Load a metaclustering / merging / classification \n from those saved to this Analysis", 
                                            command = lambda: self.load_clustering(self.load_identifier.get()))
        button_run_clustering.grid(column = 2, row = 4, padx = 5, pady = 5)

        label_2 = ctk.CTkLabel(self,
            text = """Or choose a Pixel Classifier's classification output: 
            \n\n This is the initial loading from the classy masks folder of the project 
            \n Once loaded to inside this analysis AND SAVED, you can load it in the same way as a merging/metaclustering""")
        label_2.grid(column = 4, row = 2)
        master_dir = self.master.directory[:self.master.directory.rfind("/Analyses")]
        self.classy_dir = master_dir + "/classy_masks"

        def refresh2(enter = ""):
            try:
                list_of_saved_classifiers = sorted(os.listdir(self.classy_dir))
                all_classifications = []
                for i in list_of_saved_classifiers:
                    list_of_classifications = ["".join([self.classy_dir,"/",i,"/",f'{i}_cell_classes.csv']),
                                               "".join([self.classy_dir,"/",i,"/",'secondary_cell_classification.csv'])]
                    list_of_classifications = [i for i in list_of_classifications if os.path.exists(i)]
                    list_of_classifications = [i[((i[:i.rfind("/")]).rfind("/") + 1):] for i in list_of_classifications]  
                                                                                    ## grab the first folder and the file name for display
                    all_classifications = all_classifications + list_of_classifications

                self.load_identifier_from_px.configure(values = all_classifications)
            except Exception:
                pass

        self.load_identifier_from_px = ctk.CTkOptionMenu(master = self, values = [""], variable = ctk.StringVar(value = ""))
        self.load_identifier_from_px.grid(column = 4, row = 3, padx = 5, pady = 5)
        self.load_identifier_from_px.bind("<Enter>", refresh2)

        load_from_px = ctk.CTkButton(self,
                                    text = "Load Classification from px classifier", 
                                    command = lambda: self.load_class_from_px_classifier(self.load_identifier_from_px.get()))
        load_from_px.grid(column = 4, row = 4, padx = 5, pady = 5)

        self.after(200, lambda: self.focus())

    def save_clustering(self, save_type: str, identifier: str) -> None:
        if save_type not in list(self.master.cat_exp.data.obs.columns):
            tk.messagebox.showwarning(title = "Warning!", 
                message = f"Cell grouping ({save_type}) column not currently in data! \n Create or Load this before trying to save")
            self.focus()
            return
        if not overwrite_approval(f"{self.master.cat_exp.clusterings_dir}/{save_type}{identifier}.csv", file_or_folder = "file", GUI_object = self):
            return
        self.master.cat_exp.export_clustering(save_type, identifier)
        Analysis_widget_logger.info(f"Saved Clustering: {save_type + identifier}!")

    def load_clustering(self, identifier: str) -> None:
        if (identifier == ""):
            tk.messagebox.showwarning(title = "Warning!", 
                message = "No clustering selected to load!")
            self.focus()
            return
        identifier2 = f"{self.master.cat_exp.directory}/clusterings/{identifier}"
        self.master.cat_exp.load_clustering(path = identifier2)
        self.master.plot_bank.cluster_vs_group.configure(state = "normal")
        Analysis_widget_logger.info(f"LoadedClustering: {identifier}!")

        ## TODO: test this! -- purpose is to re-disable SpaceANOVA buttons if spaceANOVA column has been overwritten
        try: ## either space_analysis or data_table attributes may not exist
            load_types = ["metaclustering", "leiden", "merging", "classification", "CN"]
            load_types2 = np.array([identifier.find(i) for i in load_types])
            load_types2[load_types2 == -1] = 100000000
            load_type = load_types[np.argmin(load_types2)]
            if self.master.cat_exp.space_analysis.cellType_key == load_type:
                self.master.master.master.Spatial.widgets.widgets.disable_buttons() 
        except Exception:
            pass
        self.withdraw()

    def load_class_from_px_classifier(self, identifier: str) -> None:
        if (identifier == ""):
            tk.messagebox.showwarning(title = "Warning!", 
                message = "No cell classification selected to load!")
            self.focus()
            return   
        self.master.cat_exp.load_classification(cell_classifications = (self.classy_dir + "/" + identifier))

        ## TODO: test!-- purpose is to re-disable SpaceANOVA buttons if spaceANOVA column has been overwritten
        try: ## either space_analysis or data_table attributes may not exist
            if self.master.cat_exp.space_analysis.cellType_key == 'classification':
                self.master.master.master.Spatial.widgets.widgets.disable_buttons() 
        except Exception:
            pass

        Analysis_widget_logger.info(f"Loaded Pixel Classification: {identifier}!")
        self.withdraw()


class Cluster_Window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("Clustering Options")
        self.master = master
        self.clustering_done = False
        ###### A bank of buttons:
        label = ctk.CTkLabel(self, text = "FlowSOM clustering options:")
        label.grid(column = 0,row = 0, padx = 5, pady =5)

        label1 = ctk.CTkLabel(master = self, text = "Marker Class:")
        label1.grid(column = 0, row = 1, padx = 3, pady = 3)

        self.marker_class = ctk.CTkOptionMenu(master = self, values = ["All"] + MARKER_CLASSES, variable = ctk.StringVar(value = "type"))
        self.marker_class.grid(column = 1, row = 1, padx = 3, pady = 3)

        label_2 = ctk.CTkLabel(self, text = "XY dimensions:")
        label_2.grid(column = 0, row = 2)

        self.cluster_dimX = ctk.CTkEntry(self, textvariable = ctk.StringVar(value = "10"))
        self.cluster_dimX.grid(column= 1, row= 2, padx = 5, pady =5)

        label_3 = ctk.CTkLabel(self, text = "Merge to K meta-clusters:")
        label_3.grid(column = 0, row = 3)

        self.k = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="20"))
        self.k.grid(column = 1, row = 3, padx = 5, pady = 5)

        label_4 = ctk.CTkLabel(self, text = "Number of Training Iterations:")
        label_4.grid(column = 0, row = 4)

        self.rlen_entry = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="50"))  
                        # Including & increasing the default of this parameter is wise:
                        #  https://www.frontiersin.org/journals/immunology/articles/10.3389/fimmu.2024.1414400/full 
        self.rlen_entry.grid(column = 1, row = 4, padx = 5, pady = 5)

        label_5 = ctk.CTkLabel(self, text = "Random Seed:")
        label_5.grid(column = 0, row = 5)

        self.seed_entry = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="1234"))
        self.seed_entry.grid(column = 1, row = 5, padx = 5, pady = 5)

        button_run_clustering = ctk.CTkButton(self,
                                            text = "Run FlowSOM clustering", 
                                            command = lambda: self.run_clustering(self.cluster_dimX.get(), 
                                                                                    self.k.get(), 
                                                                                    self.rlen_entry.get(),
                                                                                    self.seed_entry.get(),
                                                                                    self.plot_stars.get()))
        button_run_clustering.grid(column = 0, row = 6, padx = 5, pady = 5)

        self.plot_stars = ctk.CTkCheckBox(master = self, onvalue = True, offvalue = False, text = "Plot MST")
        self.plot_stars.grid(column = 1, row = 7, padx = 5, pady = 5)
        
        self.after(200, lambda: self.focus())

    def run_clustering(self, xdim: int = 10, maxK: int = 20, rlen: int = 50, seed: int = 1234, plot_stars = True) -> None:
        marker_class = self.marker_class.get()
        try:
            xdim = int(xdim)
            maxK = int(maxK)
            rlen = int(rlen)
            seed = int(seed)
        except ValueError:
            tk.messagebox.showwarning("Warning!", 
                message = "The parameters of FlowSOM clustering must be integers, but one of the inputs cannot be converted to an integer!")
            self.focus()
            return
        returned = self.master.cat_exp.do_flowsom(marker_class = marker_class, XY_dim = xdim, n_clusters = maxK, rlen = rlen, seed = seed)
        if returned is not None:
            Analysis_widget_logger.info(f"""Performed FlowSOM / Consensus clustering with the following parameters:
                                                XYdim = {xdim}, 
                                                maxK = {maxK}, 
                                                rlen = {rlen},
                                                seed = {seed}""")
            self.master.maxK = maxK

            self.master.plot_bank.cluster_vs_group.configure(state = "normal")

            ## TODO: test this! -- purpose is to re-disable buttons is spaceANOVA column has been overwritten
            try: ## either space_analysis or data_table attributes may not exist
                if self.master.cat_exp.space_analysis.cellType_key == 'metaclustering':
                    self.master.master.master.Spatial.widgets.widgets.disable_buttons() 
            except Exception:
                pass
            if plot_stars:
                filename = "FlowSOM_MST"
                self.master.cat_exp._plot_stars_CNs(returned, filename = filename + ".png")
                self.master.save_and_display(filename = filename,sizeX = 550, sizeY = 550)
            warning_window("FlowSOM complete!")
            self.withdraw()
        else:
            warning_window("There are no channels of this marker_class!")

class UMAP_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("DR Options")
        self.master = master

        label = ctk.CTkLabel(self, text = "Dimensionality Reduction options:")
        label.grid(column = 0, row = 0, padx = 5, pady = 5)

        label_1 = ctk.CTkLabel(self, text = "Kind of DR:")
        label_1.grid(column = 0, row = 1)

        self.UMAP_or_PCA = ctk.CTkOptionMenu(master = self, values = ["UMAP","PCA"], variable = ctk.StringVar(value = "UMAP"))      
        self.UMAP_or_PCA.grid(column= 1, row= 1, padx = 5, pady =5)

        label_2 = ctk.CTkLabel(self, text = "Max number of cells per sample_id:")
        label_2.grid(column = 0, row = 2)

        self.num_cells = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="1000"))
        self.num_cells.grid(column = 1, row = 2, padx = 5, pady = 5)

        label_3 = ctk.CTkLabel(self, text = "Markers to Use:")
        label_3.grid(column = 0, row = 3)

        self.features = ctk.CTkOptionMenu(master = self, values = MARKER_CLASSES + ["All"], variable = ctk.StringVar(value = "type"))
        self.features.grid(column = 1, row = 3, padx = 5, pady = 5)

        label_4 = ctk.CTkLabel(self, text = "Random Seed:")
        label_4.grid(column = 0, row = 4)

        self.seed_entry = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="1234"))
        self.seed_entry.grid(column = 1, row = 4, padx = 5, pady = 5)

        button_run = ctk.CTkButton(self, text = "Run DR", command = lambda: self.run_UMAP(kind = self.UMAP_or_PCA.get(), 
                                                                                            cells = self.num_cells.get(), 
                                                                                            features = self.features.get(),
                                                                                            n_neighbors = self.n_neigh.get(),
                                                                                            min_dist = self.min_dist.get(), 
                                                                                            seed = self.seed_entry.get()))
        button_run.grid(column = 1, row = 5, padx = 5, pady = 5)

        label_UMAP = ctk.CTkLabel(self, text = "UMAP-only parameters")
        label_UMAP.grid(column = 2, row = 0, padx = 5, pady = 5)

        label_UMAP1 = ctk.CTkLabel(self, text = "Number of Neighbors")
        label_UMAP1.grid(column = 2, row = 1, padx = 5, pady = 5)

        self.n_neigh = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="15"))
        self.n_neigh.grid(column = 3, row = 1, padx = 5, pady = 5)

        label_UMAP2 = ctk.CTkLabel(self, text = "Minimum distance")
        label_UMAP2.grid(column = 2, row = 2, padx = 5, pady = 5)

        self.min_dist = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="0.1"))
        self.min_dist.grid(column = 3, row = 2, padx = 5, pady = 5)

        self.after(200, lambda: self.focus())

    def run_UMAP(self, kind: str = "UMAP", 
                 cells: int = 1e3, 
                 features: str = "type", 
                 n_neighbors: int = 15,
                 min_dist: float = 0.1,
                 seed: int = 1234) -> None:
        try:
            cells = int(cells)
            seed = int(seed)
            if kind == "UMAP":
                n_neighbors = int(n_neighbors)
                min_dist = float(min_dist)
        except ValueError:
            tk.messagebox.showwarning("Warning!", 
                message = "At least one numerical / integer parameter (max cells / seed -- and n_neighbors / min_dist if for UMAP)"
                          "\n was set to a non-numerical value! Dimensionality Reduction cancelled.")
            self.focus()
            return
        
        if kind == "UMAP":
            self.master.cat_exp.do_UMAP(marker_class = features, 
                                        cell_number = cells, 
                                        n_neighbors = n_neighbors, 
                                        min_dist = min_dist, 
                                        seed = seed)
        elif kind == "PCA":
            self.master.cat_exp.do_PCA(marker_class = features, cell_number = cells, seed = seed)
        self.master.plot_bank.umap_plot.configure(state = "normal")
        Analysis_widget_logger.info(f"""Ran Dimensionality Reduction with the following parameters: 
                                                DR = {kind}, 
                                                cell_number = {cells}, 
                                                marker_class = {features}, 
                                                seed = {seed}""")
        if kind == "UMAP":  #### UMAP takes a long time, so a pop up is reasonable (PCA is usually fast)
            warning_window("UMAP run complete!")
        self.withdraw()

class Plot_UMAP_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.title("DR Plotting Options")
        label = ctk.CTkLabel(self, text = "Dimensionality Reduction plotting options:")
        label.grid(column = 0,row = 0, padx = 5, pady = 5)

        label_0 = ctk.CTkLabel(self, text = "Kind of Dimensionality Reduction:")
        label_0.grid(column = 0, row = 1) 

        def refresh2z(enter = ""):
            option_list = [i for i, ii in zip(["UMAP","PCA"],
                                              [self.master.cat_exp.UMAP_embedding, self.master.cat_exp.PCA_embedding]) if ii is not None]
            self.UMAP_or_PCA.configure(values = option_list)

        self.UMAP_or_PCA = ctk.CTkOptionMenu(master = self, values = [""], variable = ctk.StringVar(value = ""))
        self.UMAP_or_PCA.grid(column= 1, row= 1, padx = 5, pady = 5)
        self.UMAP_or_PCA.bind("<Enter>", refresh2z)  

        label_1 = ctk.CTkLabel(self, text = "Facet By __ Column of data:")
        label_1.grid(column = 0, row = 2) 

        def refresh3(enter = ""):
            allowed_columns_list = CLUSTER_NAMES
            if self.UMAP_or_PCA.get() == 'UMAP':
                option_list = [i for i in self.master.cat_exp.UMAP_embedding.obs.columns if i in allowed_columns_list] + COLNAMES
            elif self.UMAP_or_PCA.get() == 'PCA':
                option_list = [i for i in self.master.cat_exp.PCA_embedding.obs.columns if i in allowed_columns_list] + COLNAMES
            else:
                option_list = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns] + COLNAMES
            option_list = ["Do not Facet"] + option_list   
            self.sub_column.configure(values = option_list)

        self.sub_column = ctk.CTkOptionMenu(master = self, values = ["Do not Facet"], variable = ctk.StringVar(value = "Do not Facet"))
        self.sub_column.grid(column= 1, row= 2, padx = 5, pady = 5)
        self.sub_column.bind("<Enter>", refresh3)

        label_2 = ctk.CTkLabel(self, text = "Color Plot by:")
        label_2.grid(column = 0, row = 3)

        def refresh2zz(enter = ""):
            if self.UMAP_or_PCA.get() == "UMAP":
                option_list = ( [i for i in CLUSTER_NAMES if i in self.master.cat_exp.UMAP_embedding.obs.columns] + COLNAMES
                                + list(self.master.cat_exp.UMAP_embedding.var['antigen']) )
            elif self.UMAP_or_PCA.get() == "PCA":
                option_list = ( [i for i in CLUSTER_NAMES if i in self.master.cat_exp.PCA_embedding.obs.columns] + COLNAMES
                                + list(self.master.cat_exp.PCA_embedding.var['antigen']) )
            else:
                option_list = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns] + COLNAMES
            self.cluster_marker.configure(values = option_list) 

        self.cluster_marker = ctk.CTkOptionMenu(master = self, values = [""], variable = ctk.StringVar(value = ""))
        self.cluster_marker.grid(column = 1, row = 3, pady = 5, padx = 5)
        self.cluster_marker.bind("<Enter>", refresh2zz) 

        label_3 = ctk.CTkLabel(self, text = "Filename:")
        label_3.grid(column = 0, row = 4)

        self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value = "DimReduct_1"))
        self.filename.grid(column = 1, row = 4, padx = 5, pady = 5)

        button_plot = ctk.CTkButton(self, text = "Generate Plot", command = lambda: self.plot_UMAP(subsetting_column = self.sub_column.get(), 
                                                                                                color_column = self.cluster_marker.get(),
                                                                                                filename = self.filename.get().strip(),
                                                                                                kind = self.UMAP_or_PCA.get()))
        button_plot.grid(column = 0, row = 5, padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(column = 0, row = 6, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot_UMAP(self, subsetting_column: str, color_column: str, filename: str, kind: str = 'umap') -> None:
        if filename_checker(filename, self):
            return
        if "" in [subsetting_column, color_column]:
            tk.messagebox.showwarning("Warning!", 
                message = "A parameter for UMAP plots was left blank!")
            self.focus()
            return
        if not overwrite_approval(f"{self.master.cat_exp.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        if subsetting_column != "Do not Facet":
            if kind == 'UMAP':
                figure = self.master.cat_exp.plot_facetted_DR(filename = filename, 
                                                            color_by = color_column, 
                                                            subsetting_column = subsetting_column, 
                                                            kind = kind)
            elif kind == 'PCA':
                figure = self.master.cat_exp.plot_facetted_DR(filename = filename, 
                                                            color_by = color_column, 
                                                            subsetting_column = subsetting_column, 
                                                            kind = kind)
        else:
            self.plot_single(kind = kind, color_by = color_column, filename = filename)
        self.master.save_and_display(filename = filename,sizeX = 550, sizeY = 550)
        Analysis_widget_logger.info(f"""Plotted Facetted UMAP with: 
                                                kind = {kind},
                                                subsetting_column = {subsetting_column}, 
                                                color_by = {color_column}, 
                                                filename = {filename}.png""")
        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

    def plot_single(self, kind: str, color_by: str, filename: str) -> None:
        if kind == "UMAP":
            figure = self.master.cat_exp.plot_UMAP(filename = filename, color_by = color_by)
        elif kind == "PCA":
            figure = self.master.cat_exp.plot_PCA(filename = filename, color_by = color_by)
        self.master.save_and_display(filename = filename,sizeX = 550, sizeY = 550)
        Analysis_widget_logger.info(f"Plotted Dimensionality reduction with: DR = {kind}, color_by = {color_by}, filename = {filename}.png")
        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

class Plot_ExprsHeatMap_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("Expression Heatmap Options")
        self.master = master
        label = ctk.CTkLabel(self, text = "Expression Heatmap Options:")
        label.grid(column = 0,row = 0, padx = 5, pady = 5)

        label_1 = ctk.CTkLabel(self, text = "Markers to use (type / state):")
        label_1.grid(column = 0, row = 1)

        self.type_state = ctk.CTkOptionMenu(master = self, 
                                            values = MARKER_CLASSES + ["All"], 
                                            variable = ctk.StringVar(value = "type"))
        self.type_state.grid(column= 1, row= 1, padx = 5, pady = 5)

        label_4 = ctk.CTkLabel(self, text = "Filename:")
        label_4.grid(column = 0, row = 4)

        self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value = "Expression_Heatmap"))
        self.filename.grid(column = 1, row = 4, padx = 5, pady = 5)

        button_plot = ctk.CTkButton(self, text = "Plot", command = lambda: self.plot_Heatmap(features = self.type_state.get(), 
                                                                                                filename = self.filename.get().strip()))
        button_plot.grid(column = 0, row = 5, padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(column = 0, row = 6, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot_Heatmap(self, features: str = "type", filename: str = "Plot_4") -> None:
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.cat_exp.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        figure = self.master.cat_exp.plot_medians_heatmap(marker_class = features, groupby = "sample_id", filename = filename)
        Analysis_widget_logger.info(f"Plotted Expression Heatmap: marker_class = {features}, groupby = 'sample_id', filename = {filename}.png")
        self.master.save_and_display(filename = filename,sizeX = 550, sizeY = 550)
        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

class Plot_Counts_per_ROI_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("Count Plot Options")
        self.master = master
        label = ctk.CTkLabel(self, text = "Counts per ROI plot Options:")
        label.grid(column = 0,row = 0, padx = 5, pady = 5)

        label_1 = ctk.CTkLabel(self, text = "Group ROIs by:")
        label_1.grid(column = 0, row = 1)

        def refresh5(enter = ""):
            colData_list = COLNAMES
            self.group.configure(values = colData_list)
        
        colData_list = COLNAMES
        self.group = ctk.CTkOptionMenu(master = self, values = colData_list, variable = ctk.StringVar(value = "sample_id"))
        self.group.grid(column= 1, row= 1, padx = 5, pady = 5)
        self.group.bind("<Enter>", refresh5)

        label_2 = ctk.CTkLabel(self, text = "color ROIs by:")
        label_2.grid(column = 0, row = 2)

        def refresh6(enter = ""):
            colData_list_null = colData_list + ["NULL"]
            self.color.configure(values = colData_list_null)

        self.color = ctk.CTkOptionMenu(master = self, values = colData_list + ["NULL"], variable = ctk.StringVar(value = "condition"))
        self.color.grid(column = 1, row = 2, padx = 5, pady = 5)
        self.color.bind("<Enter>", refresh6)

        label_3 = ctk.CTkLabel(self, text = "Filename:")
        label_3.grid(column = 0, row = 3)

        self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="Counts_per_ROI"))
        self.filename.grid(column = 1, row = 3, padx = 5, pady = 5)

        button_plot = ctk.CTkButton(self, text = "Plot", command = lambda: self.plot_Counts_per_ROI(group_by= self.group.get(), 
                                                                                                color_by = self.color.get(),
                                                                                                filename = self.filename.get().strip()))
        button_plot.grid(column = 0, row = 4, padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(column = 0, row = 5, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot_Counts_per_ROI(self, group_by: str = "sample_id", color_by: str = "condition", filename: str = "Plot_1") -> None:
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.cat_exp.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        figure = self.master.cat_exp.plot_cell_counts(group_by = group_by, color_by = color_by, filename = filename)
        Analysis_widget_logger.info(f"Plotted Counts per ROI with: group_by = {group_by}, color_by = {color_by}, filename = {filename}.png")
        self.master.save_and_display(filename = filename,sizeX = 550, sizeY = 550)
        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
           self.destroy()

class Plot_histograms_per_ROI_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("KDE Histograms for ROI options")
        self.master = master
        label = ctk.CTkLabel(self, text = "KDE Histograms per marker, per ROI options:")
        label.grid(column = 0,row = 0, padx = 5, pady = 5)

        label_1 = ctk.CTkLabel(self, text = "Color KDE traces by:")
        label_1.grid(column = 0, row = 1)

        def refresh7(enter = ""):
            colData_list = COLNAMES
            self.color.configure(values = colData_list)

        colData_list = COLNAMES

        self.color =  ctk.CTkOptionMenu(master = self, values = colData_list, variable = ctk.StringVar(value = "condition"))
        self.color.grid(column= 1, row= 1, padx = 5, pady = 5)
        self.color.bind("<Enter>", refresh7)

        label_2 = ctk.CTkLabel(self, text = "Filename:")
        label_2.grid(column = 0, row = 2)

        self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="KDE_Histograms_per_ROI"))
        self.filename.grid(column = 1, row = 2, padx = 5, pady = 5)

        button_plot = ctk.CTkButton(self, text = "Plot", command = lambda: self.plot_ROI_histograms(color_by= self.color.get(), 
                                                                                                filename = self.filename.get().strip()))
        button_plot.grid(column = 0, row = 3, padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(column = 0, row = 4, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot_ROI_histograms(self, color_by: str = "condition", filename: str = "Plot_2") -> None:
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.cat_exp.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        figure = self.master.cat_exp.plot_ROI_histograms(color_by = color_by, filename = filename)
        Analysis_widget_logger.info(f"Plotted KDE Histograms per ROI with: color_by = {color_by}, filename = {filename}.png")
        self.master.save_and_display(filename = filename,sizeX = 550, sizeY = 550)

        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

class Plot_MDS_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("MDS plot Options")
        self.master = master
        label = ctk.CTkLabel(self, text = "MDS plot Options:")
        label.grid(column = 0,row = 0, padx = 5, pady = 5)

        label_1 = ctk.CTkLabel(self, text = "Markers to plot (type / state):")
        label_1.grid(column = 0, row = 1)

        self.group = ctk.CTkOptionMenu(master = self, values = MARKER_CLASSES + ["All"], variable = ctk.StringVar(value = "type"))
        self.group.grid(column= 1, row= 1, padx = 5, pady = 5)

        label_2 = ctk.CTkLabel(self, text = "Color by:")
        label_2.grid(column = 0, row = 2)

        def refresh8(enter = ""):
            colData_list = COLNAMES
            self.color.configure(values = colData_list)
        colData_list = COLNAMES

        self.color = ctk.CTkOptionMenu(master = self, values = colData_list, variable = ctk.StringVar(value = "condition"))
        self.color.grid(column = 1, row = 2, padx = 5, pady = 5)
        self.color.bind("<Enter>", refresh8)

        label_3 = ctk.CTkLabel(self, text = "Filename:")
        label_3.grid(column = 0, row = 3)

        self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="MDS_plot"))
        self.filename.grid(column = 1, row = 3, padx = 5, pady = 5)

        button_plot = ctk.CTkButton(self, text = "Plot", command = lambda: self.plot_MDS(features = self.group.get(), 
                                                                                                color_by = self.color.get(),
                                                                                                filename = self.filename.get().strip()))
        button_plot.grid(column = 0, row = 5, padx = 5, pady = 5)


        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(column = 0, row = 6, padx = 3, pady = 3)

        self.print_stat = ctk.CTkCheckBox(master = self, text = "Export MDS values to /Data_tables?", onvalue = True, offvalue = False)
        self.print_stat.grid(column = 1, row = 6, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot_MDS(self, features: str = "type", color_by: str = "condition", filename: str = "Plot_3") -> None:
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.cat_exp.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        figure, df = self.master.cat_exp.plot_MDS(marker_class = features, 
                                                  color_by = color_by, 
                                                  filename = filename, 
                                                  print_stat = self.print_stat.get())
        Analysis_widget_logger.info(f"Plotted MDS with: marker_class = {features}, color_by = {color_by}, filename = {filename}.png")
        self.master.save_and_display(filename = filename, sizeX = 550, sizeY = 550)

        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

class ClusterVGroup(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("Plot Cluster vs. Group Expression")
        self.master = master
        self.clustering_done = False

        label_1 = ctk.CTkLabel(self, text = "Choose Clustering / Merging:")
        label_1.grid(column = 0, row = 0, padx = 3, pady = 3)

        option_list = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns] # + COLNAMES   
        self.clustering = ctk.CTkOptionMenu(master = self, variable = ctk.StringVar(value = ""), values = option_list)
        self.clustering.grid(column = 1, row = 0, padx = 3, pady = 3)

        def refresh_ClusterVgroup_clusters(enter = ""):
            option_list = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns] # + COLNAMES   
            self.clustering.configure(values = option_list)

        self.clustering.bind("<Enter>", refresh_ClusterVgroup_clusters)

        label_1 = ctk.CTkLabel(self, text = "Choose Marker Class:")
        label_1.grid(column = 0, row = 1, padx = 3, pady = 3)

        option_list = ['All'] + MARKER_CLASSES
        self.marker_class = ctk.CTkOptionMenu(master = self, variable = ctk.StringVar(value = "type"), values = option_list)
        self.marker_class.grid(column = 1, row = 1, padx = 3, pady = 3)
        
        label_1 = ctk.CTkLabel(self, text = "Choose Type of graph:")
        label_1.grid(column = 0, row = 2, padx = 3, pady = 3)

        option_list = ['heatmap','bar','violin']
        self.option_menu = ctk.CTkOptionMenu(master = self, variable = ctk.StringVar(value = "violin"), values = option_list)
        self.option_menu.grid(column = 1, row = 2, padx = 3, pady = 3)

        label_1 = ctk.CTkLabel(self, text = "Choose Type of comparison:")
        label_1.grid(column = 0, row = 3, padx = 3, pady = 3)

        option_list2 = ['cluster vs. other clusters','Raw Cluster values (no substraction of rest of dataset)']
        self.type_of_comp = ctk.CTkOptionMenu(master = self, 
                variable = ctk.StringVar(value = "Raw Cluster values (no substraction of rest of dataset)"), 
                values = option_list2)
        self.type_of_comp.grid(column = 1, row = 3, padx = 3, pady = 3)

        label_1 = ctk.CTkLabel(self, text = "Choose Filename:")
        label_1.grid(column = 0, row = 4, padx = 3, pady = 3)

        self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value = "cluster_raw_dist"))
        self.filename.grid(column = 1, row = 4, padx = 3, pady = 3)

        button_run = ctk.CTkButton(self,
                                text = "Plot", 
                                command = lambda: self.plot_clusterV(self.clustering.get(), 
                                                                        self.option_menu.get(), 
                                                                        self.type_of_comp.get(), 
                                                                        self.filename.get().strip(), 
                                                                        marker_class = self.marker_class.get()))
        button_run.grid(column = 1, row = 5, padx = 3, pady = 3)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(column = 1, row = 6, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot_clusterV(self, clustering_column: str, 
                      type_of_graph, 
                      type_of_comp: str, 
                      filename: str, 
                      marker_class: str = "type") -> None:
        ''''''
        if filename_checker(filename, self):
            return
        available_columns = [i for i in (CLUSTER_NAMES + COLNAMES) if i in list(self.master.cat_exp.data.obs.columns)]
        if clustering_column == "":
            tk.messagebox.showwarning(title = "Warning!",
                message = "You must select a clustering!")
            self.focus()
            return
        elif clustering_column not in available_columns:
            tk.messagebox.showwarning(title = "Warning!",
                message = f"Clustering column =  {clustering_column}  is not in the dataset! \n Of {str(COLNAMES)}" +
                    f"\n These are currently available: {str(available_columns)}")
            self.focus()
            return
        if not overwrite_approval(f"{self.master.cat_exp.save_dir}/{type_of_graph}{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        if filename is not None:  
            select_dict = {"Raw Cluster values (no substraction of rest of dataset)": "raw", "cluster vs. other clusters": "vs"}
            type_of_comp = select_dict[type_of_comp]
            figure = self.master.cat_exp.plot_cluster_distributions(filename = filename, 
                                                                    groupby_column = clustering_column, 
                                                                    plot_type = type_of_graph, 
                                                                    comp_type = type_of_comp,
                                                                    marker_class = marker_class)
            self.master.save_and_display(filename = f"{type_of_graph}{filename}",sizeX = 550, sizeY = 550)

            Analysis_widget_logger.info(f"""Plotted cluster vs group plot with settings: 
                                        groupby_column column = {clustering_column},
                                        plot_type = {str(type_of_graph)}
                                        comp_type = {type_of_comp},
                                        marker_class = {marker_class}, 
                                        filename = {type_of_graph}{filename}.png""")
            
            if self.pop_up.get() is True:
                Plot_window_display(figure)
                self.withdraw()
            else:
                self.destroy()

class Plot_NRS_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("NRS Plot Options")
        self.master = master
        label = ctk.CTkLabel(self, text = "NRS plot Options:")
        label.grid(column = 0,row = 0, padx = 5, pady = 5)

        label_1 = ctk.CTkLabel(self, text = "Markers to use (type / state):")
        label_1.grid(column = 0, row = 1)

        self.group = ctk.CTkOptionMenu(master = self, values = MARKER_CLASSES + ["All"], variable = ctk.StringVar(value = "type"))
        self.group.grid(column= 1, row= 1, padx = 5, pady = 5)

        label_3 = ctk.CTkLabel(self, text = "Filename:")
        label_3.grid(column = 0, row = 3)

        self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="NRS_plot"))
        self.filename.grid(column = 1, row = 3, padx = 5, pady = 5)

        button_plot = ctk.CTkButton(self, text = "Plot", command = lambda: self.plot_NRS(features = self.group.get(), 
                                                                                                filename = self.filename.get().strip()))
        button_plot.grid(column = 1, row = 4, padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(column = 0, row = 5, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot_NRS(self, features: str = "type", filename: str = "Plot_5") -> None:
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.cat_exp.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        figure = self.master.cat_exp.plot_NRS(marker_class = features, filename = filename)
        Analysis_widget_logger.info(f"Plotted NRS with: marker_class = {features}, filename = {filename}.png")
        self.master.save_and_display(filename = filename,sizeX = 550, sizeY = 550)
        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

class plot_cluster_abundances_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("Cluster Abundance Plot Options")
        self.master = master
        label = ctk.CTkLabel(self, text = "Cluster Abundance plot options:")
        label.grid(column = 0,row = 0, padx = 5, pady = 5)

        label_1 = ctk.CTkLabel(self, text = "Clustering to Plot:")
        label_1.grid(column = 0, row = 1)

        self.k = ctk.CTkOptionMenu(master = self, values = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns], variable = ctk.StringVar())
        self.k.grid(column = 1, row = 1, pady = 5, padx = 5)

        def refresh_abund_k(enter = ""):
            self.k.configure(values = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns])
        
        self.k.bind("<Enter>", refresh_abund_k)

        label_2 = ctk.CTkLabel(self, text = "Type of Plot:")
        label_2.grid(column = 0, row = 2)

        self.by = ctk.CTkOptionMenu(master = self, 
                                    values = ["stacked barplot","cluster boxplot","cluster stripplot"], 
                                    variable = ctk.StringVar(value = "stacked barplot"))
        self.by.grid(column = 1, row = 2, padx = 5, pady = 5)

        label_2b = ctk.CTkLabel(self, text = "Color by (when grouping by cluster_stripplot only):")
        label_2b.grid(column = 0, row = 3)

        self.color = ctk.CTkOptionMenu(master = self, 
                                       values = COLNAMES, 
                                       variable = ctk.StringVar(value = "condition"))
        self.color.grid(column = 1, row = 3, padx = 5, pady = 5)

        label_3 = ctk.CTkLabel(self, text = "Filename:")
        label_3.grid(column = 0, row = 4)

        self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="Abundance_plot"))
        self.filename.grid(column = 1, row = 4, padx = 5, pady = 5)

        button_plot = ctk.CTkButton(self, text = "Plot", command = lambda: self.plot_abundance(k = self.k.get(), 
                                                                                                by = self.by.get(),
                                                                                                filename = self.filename.get().strip(),
                                                                                                ))
        button_plot.grid(column = 0, row = 5, padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(column = 0, row = 6, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot_abundance(self, k: str = "merging1", by: str = "sample_id", filename: str = "Plot_12") -> None:
        '''
        '''
        if filename_checker(filename, self):
            return
        available_columns = [i for i in CLUSTER_NAMES if i in list(self.master.cat_exp.data.obs.columns)]
        if k == "":
            tk.messagebox.showwarning(title = "Warning!", 
                                    message = "You must select a clustering!")
            self.focus()
            return
        elif k not in available_columns:
            tk.messagebox.showwarning(title = "Warning!", 
                                    message = f"Clustering =  {k}  is not available in the dataset! \n Of {str(COLNAMES)} \n" +
                                    "These are currently available: {str(available_columns)}")
            self.focus()
            return
        if not overwrite_approval(f"{self.master.cat_exp.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        if by == "stacked barplot":
            figure = self.master.cat_exp.plot_cluster_abundance_1(filename = filename, groupby_column = k)
            Analysis_widget_logger.info(f"Plotted Cluster Abundance with: groupby_column = {k}, type = 'stacked_barplot', filename = {filename}.png")
            self.master.save_and_display(filename = filename,sizeX = 550, sizeY = 550)

            if self.pop_up.get() is True:
                Plot_window_display(figure)
                self.withdraw()
            else:
                self.destroy()
        else:
            plot_type = by[by.rfind(" ") + 1:]
            if plot_type =="boxplot":
                figure = self.master.cat_exp.plot_cluster_abundance_2(filename = filename, 
                                                                      groupby_column = k, 
                                                                      plot_type = plot_type, 
                                                                      hue = self.color.get())
            else:
                figure = self.master.cat_exp.plot_cluster_abundance_2(filename = filename, 
                                                                      groupby_column = k, 
                                                                      plot_type = plot_type, 
                                                                      hue = self.color.get())
            Analysis_widget_logger.info(f"""Plotted Cluster Abundance with: 
                                                    groupby_column = {k}, 
                                                    plot_type = {plot_type}, 
                                                    filename = {filename}.png""")
            self.master.save_and_display(filename = filename,sizeX = 550, sizeY = 550)

            if self.pop_up.get() is True:
                Plot_window_display(figure)
                self.withdraw()
            else:
                self.destroy()

class plot_cluster_heatmap_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("Cluster Heatmap Options")
        self.master = master
        label = ctk.CTkLabel(self, text = "Cluster Heatmap options:")
        label.grid(column = 0,row = 0, padx = 5, pady = 5)

        label_1 = ctk.CTkLabel(self, text = "Markers to use:")
        label_1.grid(column = 0, row = 2)

        self.features = ctk.CTkOptionMenu(master = self, values = MARKER_CLASSES + ["All"], variable = ctk.StringVar(value = "type"))
        self.features.grid(column= 1, row = 2, padx = 5, pady = 5)

        label_2 = ctk.CTkLabel(self, text = "Clustering to use:")
        label_2.grid(column = 0, row = 1)

        option_list =  [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns]
        self.k = ctk.CTkOptionMenu(master = self, values = option_list, variable = ctk.StringVar())
        self.k.grid(column = 1, row = 1, pady = 5, padx = 5)

        def refresh_cluster_heatmap_k(eenter = ""):
            option_list =  [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns]
            self.k.configure(values = option_list)

        self.k.bind("<Enter>", refresh_cluster_heatmap_k)

        label_7 = ctk.CTkLabel(self, text = "Filename:")
        label_7.grid(column = 0, row = 7)

        self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="Cluster_Heatmap"))
        self.filename.grid(column = 1, row = 7, padx = 5, pady = 5)

        self.facet = ctk.CTkCheckBox(master = self, text = "Make Facetted Heatmap \n (does not auto-display)?", onvalue = True, offvalue = False)
        #self.facet.grid(column = 0, row = 8, padx = 5, pady = 5)

        # label_facet = ctk.CTkLabel(self, text = "If facetting, choose the column:")
        #label_facet.grid(column = 0, row = 9)

        self.subsetting_column = ctk.CTkOptionMenu(self, 
                                                   values = COLNAMES, 
                                                   variable = ctk.StringVar(value ="sample_id"))
        #self.subsetting_column.grid(column = 1, row = 9, padx = 5, pady = 5)

        button_plot = ctk.CTkButton(self, text = "Plot", command = lambda: self.plot_cluster_heatmap(features = self.features.get(), 
                                                                                                k = self.k.get(),
                                                                                                filename = self.filename.get().strip()))
        button_plot.grid(column = 0, row = 10, padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(column = 0, row = 11, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot_cluster_heatmap(self, features: str = "type", k: str = "metaclustering", filename: str = "Plot_6") -> None:
        if filename_checker(filename, self):
            return
        available_columns = [i for i in CLUSTER_NAMES if i in list(self.master.cat_exp.data.obs.columns)]
        if k == "":
            tk.messagebox.showwarning(title = "Warning!", 
                                    message = "You must select a clustering!")
            self.focus()
            return
        elif k not in available_columns:
            tk.messagebox.showwarning(title = "Warning!", 
                                    message = f"Clustering =  {k}  is not available in the dataset! \n Of {str(CLUSTER_NAMES)} \n"
                                    "These are currently available: {str(available_columns)}")
            self.focus()
            return
        if not overwrite_approval(f"{self.master.cat_exp.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        if self.facet.get() is True:
            self.master.cat_exp.plot_facetted_heatmap(filename = filename, 
                                                      subsetting_column = self.subsetting_column.get(), 
                                                      groupby_column = k, 
                                                      marker_class = features)
            Analysis_widget_logger.info(f"""Plotted facetted cluster heatmap with: 
                                                    marker_class = {features}, 
                                                    groupby_column = {k}, 
                                                    facetting_column = {self.subsetting_column.get()}, 
                                                    filename = {filename}.png""")
        else:
            figure = self.master.cat_exp.plot_medians_heatmap(filename = filename, groupby = k, marker_class = features)
            Analysis_widget_logger.info(f"Plotted cluster heatmap with: marker_class = {features}, groupby = {k}, filename = {filename}.png")  
            self.master.save_and_display(filename = filename, sizeX = 550, sizeY = 550)
        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

class plot_cluster_expression_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("KDE Histograms by Clustering")

        label = ctk.CTkLabel(master = self, text = "Plot KDE Histograms of the Clusters' Expression of one Antigen:")
        label.grid(padx = 3, pady = 3)

        label1 = ctk.CTkLabel(master = self, text = "Choose clustering:")
        label1.grid(padx = 3, pady = 3)

        clustering_options = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns]
        self.clustering_option = ctk.CTkOptionMenu(master = self, values = clustering_options, variable = ctk.StringVar())
        self.clustering_option.grid(padx = 3, pady = 3)

        def refresh_cluster_exp_clusters(enter = ""):
            clustering_options = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns]
            self.clustering_option.configure(values = clustering_options)

        self.clustering_option.bind("<Enter>", refresh_cluster_exp_clusters)

        label2 = ctk.CTkLabel(master = self, text = "Choose Antigen to plot expression of:")
        label2.grid(padx = 3, pady = 3)

        def refresh11(enter = ""):
            antigen_options = list(self.master.cat_exp.data.var.index)
            self.antigen.configure(values = antigen_options)

        antigen_options = list(self.master.cat_exp.data.var.index)
        self.antigen = ctk.CTkOptionMenu(master = self, values = antigen_options, variable = ctk.StringVar())
        self.antigen.grid(padx = 3, pady = 3)
        self.antigen.bind("<Enter>", refresh11)

        label3 = ctk.CTkLabel(master = self, text = "Choose Filename:")
        label3.grid(padx = 3, pady = 3)

        self.filename = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "Cx_Ay_Histogram"))
        self.filename.grid(padx = 3, pady = 3)

        button = ctk.CTkButton(master = self, text = "Make Plot", command = self.run_py_plot_cluster_histograms)
        button.grid(padx = 3, pady = 3)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid()

        self.after(200, self.focus())

    def run_py_plot_cluster_histograms(self) -> None:
        filename = self.filename.get().strip()
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.cat_exp.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        figure = self.master.cat_exp.plot_cluster_histograms(filename = filename, 
                                                             groupby_column = self.clustering_option.get(), 
                                                             antigen = self.antigen.get())
        Analysis_widget_logger.info(f"Plotted KDE / histogram Expression in Cluster {self.clustering_option.get()} of {self.antigen.get()}, filename = {filename}")

        self.master.save_and_display(filename = filename, sizeX = 550, sizeY = 550)
        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

class cluster_merging_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("Cluster Merging Window")
        self.master = master
        self.directory = self.master.directory
        self.clustering = None
        self.id_out = None
        try:
            self.number = len(self.master.cat_exp.data.obs['metaclustering'].unique())
            self.leiden_or_meta = "metaclustering"
        except KeyError:
            self.number = len(self.master.cat_exp.data.obs['leiden'].unique())
            self.leiden_or_meta = "leiden"
        self.new = self.new_merge_frame(self)
        self.new.grid(column = 0, row = 0, rowspan = 4, padx = 5, pady = 5)

        label = ctk.CTkLabel(master = self, text = "Merge either FlowSOM metaclustering or Leiden clustering:")
        label.grid(column = 2, row = 1)

        metaclustering_or_leiden = ctk.CTkOptionMenu(master = self, 
                                                    values = ["metaclustering", "leiden"], 
                                                    variable = ctk.StringVar(value = self.leiden_or_meta), command = lambda choice: self.switch_leiden(choice))
        metaclustering_or_leiden.grid(column = 2, row = 2)

        self.after(200, lambda: self.focus())

    def switch_leiden(self, leiden_or_meta):
        ''''''
        if self.leiden_or_meta != leiden_or_meta:
            self.leiden_or_meta = leiden_or_meta
            self.number = len(self.master.cat_exp.data.obs[leiden_or_meta].unique())
            self.new.destroy()
            self.new = self.new_merge_frame(self)
            self.new.grid(column = 0, row = 0, rowspan = 4, padx = 5, pady = 5)

    def load_merging(self, id: str) -> None:
        merging_file_path = self.master.directory + "/mergings/" + id + ".csv"
        
        self.master.cat_exp.do_cluster_merging(file_path = merging_file_path)
        Analysis_widget_logger.info(f"Loaded Cluster Merging with: name = {id}")

        self.destroy()

    def do_cluster_merging(self, id: str, meta_or_leiden: str = "metaclustering") -> None:
        # reassign the values from the old widgets to new self.variables
        id = id.lstrip().rstrip() #### removes any leading and trailing spaces
        if filename_checker(id, self):
            return
        merging_file_path = self.master.directory + "/mergings/" + id + ".csv"
        if not overwrite_approval(merging_file_path, file_or_folder = "file", GUI_object = self):
            return
        if " " in id:
            id = id.replace(" ","_")  #### now replaces any remaining spaces (with would break the underlying R code) with underscores
            warning_window(f"Blank spaces inside your merging name have been replaced with underscores: the merging name will now be saved as {id}")

        self.new.table.add_id(id)
        self.new.table.recover_input()
        self.new.table.special_to_csv()
        self.master.cat_exp.do_cluster_merging(file_path = merging_file_path, groupby_column = meta_or_leiden)

        ## TODO: test this! -- purpose is to re-disable buttons is spaceANOVA column has been overwritten
        try: ## either space_analysis or data_table attributes may not exist
            if self.master.cat_exp.space_analysis.cellType_key == 'merging':
                self.master.master.master.Spatial.widgets.widgets.disable_buttons() 
        except Exception:
            pass

        Analysis_widget_logger.info(f"Ran Cluster Merging with: name = {id}")
        self.destroy()

    class new_merge_frame(ctk.CTkFrame):
        def __init__(self,master):
            super().__init__(master)
            self.master = master

            self.label_2 = ctk.CTkLabel(self, text = "Name new Merging:")
            self.label_2.grid(column = 3, row = 0)

            self.id_new = ctk.CTkEntry(self, textvariable = ctk.StringVar(value  = "merging1"))
            self.id_new.grid(column = 3, row = 1)

            self.label3 = ctk.CTkLabel(self, text = "Load a previously made \n Merging Table:")
            self.label3.grid(column = 4, row = 0)

            def refreshOption(enter = ""):
                made_mergings = ["blank"] + [i for i in sorted(os.listdir(self.master.master.directory + "/mergings/"))] 
                self.reload_merge.configure(values = made_mergings)

            self.reload_merge = ctk.CTkOptionMenu(self, 
                                    values = ["blank"], 
                                    command = lambda choice: self.repopulate_table(choice))
            self.reload_merge.grid(column = 4, row = 1)
            self.reload_merge.bind("<Enter>", refreshOption)
            
            self.table = TableWidget_merging(self,width = 1, directory = self.master.directory + "/mergings", maxK = self.master.number)
            self.table.grid(column = 3, row = 2, columnspan = 4, padx = 5, pady = 5)

            self.button = ctk.CTkButton(master = self, 
                                        text = "Accept Table Entry & Run Cluster Merging", 
                                        command = lambda: self.master.do_cluster_merging(self.id_new.get().strip(), self.master.leiden_or_meta))
            self.button.grid(column = 3, row = 7, padx = 5, pady = 5)

        def repopulate_table(self, choice):
            self.table.repopulate_table(self.master.master.directory + "/mergings/" + choice)
            self.id_new.configure(textvariable = ctk.StringVar(value = choice[:choice.rfind(".csv")]))    

class TableWidget_merging(ctk.CTkScrollableFrame):
    '''
    This class is a modified and streamlined form of the old table widget used in the Image processing portion of the pipeline
    Goals: have it be a bit more streamlined, general purpose (or maybe not....), and less hard-coded
    '''
    def __init__(self, master, width, directory, maxK):
        '''
        id is the name the user gave it
        '''
        super().__init__(master)
        self.id = None
        self.maxK = maxK
        self.directory = directory
        self.to_add = ""
        self.table_dataframe = pd.DataFrame()
        self.table_dataframe['original_cluster'] = [i for i in range(1, maxK + 1)]
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
        Analysis_widget_logger.info(f"Wrote merging file, with name '{self.id}', with the values: \n {str(dataframe)}")

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

class Hypothesis_widget(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.model_list = []
        self.FDR_list = []
        
        self.Grand_Label = ctk.CTkLabel(master = self, text = "Hypothesis Testing Functions")
        self.Grand_Label.grid(column = 0, row = 0, columnspan = 2, padx = 5, pady = 5)
        self.Grand_Label.configure(width = 300)

        self.make_model = ctk.CTkButton(master = self, text = "Run Cluster Abundance ANOVAs")
        self.make_model.grid(row = 1, column = 0, columnspan = 2, padx = 5, pady = 5)
        self.make_model.configure(state = "disabled")

        self.DA_button = ctk.CTkButton(master = self, text = "Run State Expression ANOVAs")
        self.DA_button.grid(column = 0, columnspan = 2, row = 3, padx = 5, pady = 5)
        self.DA_button.configure(state = "disabled")

    def initialize_buttons(self) -> None:
        ### goal: decouple widget placement & initialization from data loading & button activation
        self.make_model.configure(state = "normal", command = self.launch_abundance_ANOVAs_window)
        self.DA_button.configure(state = "normal", command = self.launch_state_ANOVAs_window)

    def launch_abundance_ANOVAs_window(self) -> None:
        run_abundance_ANOVAs_window(self.master)

    def launch_state_ANOVAs_window(self) -> None:
        run_state_ANOVAs_window(self.master)

class run_abundance_ANOVAs_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):

    def __init__(self, master):
        super().__init__(master)
        self.master = master

        label = ctk.CTkLabel(master = self, text = "Choose clustering column:")
        label.grid(padx = 3, pady = 3, row = 0, column = 0)

        self.options = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns]
        self.column = ctk.CTkOptionMenu(master = self, values = self.options, variable = ctk.StringVar())
        self.column.grid(padx = 3, pady = 3, row = 1, column = 0)

        def refresh_abund_ANOVA_cluster(enter = ""):
            self.options = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns]
            self.column.configure(values = self.options)

        self.column.bind("<Enter>", refresh_abund_ANOVA_cluster)

        label1 = ctk.CTkLabel(master = self, text = "Choose comparison:")
        label1.grid(padx = 3, pady = 3, row = 2, column = 0)

        self.condition_pairs = []
        self.conditions = list(self.master.cat_exp.data.obs['condition'].astype('str').unique())
        for i in self.conditions:
            for j in self.conditions:
                if i != j:
                    self.condition_pairs.append(f"{i} %vs.% {j}")   ## want the spacer to be unique enough that it is very unlikely to accidently 
                                                                            ## exist in a users' choice of condition name

        def refresh12(enter = ""):
            self.condition_pairs = []
            self.conditions = list(self.master.cat_exp.data.obs['condition'].astype('str').unique())
            for i in self.conditions:
                for j in self.conditions:
                    if i != j:
                        self.condition_pairs.append(f"{i} %vs.% {j}")   ## want the spacer to be unique enough that it is very unlikely to accidently 
                                                                         ## exist in a users' choice of condition name
            self.options1 = ["multicomparison"] + self.condition_pairs
            self.condition1.configure(values = self.options1)

        self.options1 = [""]
        self.condition1 = ctk.CTkOptionMenu(master = self, values = self.options1, variable = ctk.StringVar(value = "multicomparison"))
        self.condition1.grid(padx = 3, pady = 3, row = 3, column = 0)
        self.condition1.bind("<Enter>", refresh12)

        label10 = ctk.CTkLabel(master = self, text = "Choose Filename of exported table:")
        label10.grid(padx = 3, pady = 3, row = 6, column = 0)

        self.filename = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = 'abundance_ANOVA_table'))
        self.filename.grid(padx = 3, pady = 3, row = 7, column = 0)

        button = ctk.CTkButton(master = self, text = "Run cluster abundance ANOVAs", command = self.run_ANOVAs)
        button.grid(padx = 3, pady = 3, row = 8, column = 0)

        col2_label = ctk.CTkLabel(master = self, text = "Select GLM model or ANOVA:")
        col2_label.grid(padx = 3, pady = 3, row = 2, column = 1)

        self.GLMs = ["ANOVA", "GLM:Poisson", "GLM:NegativeBinomial", "GLM:Gaussian"]          #     ,"GLM:Gaussian","GLM:Binomial"    
        self.GLM = ctk.CTkOptionMenu(master = self, values = self.GLMs, variable = ctk.StringVar(value = "GLM:Poisson"))
        self.GLM.grid(padx = 3, pady = 3, row = 3, column = 1)

        self.after(200, self.focus())

    def run_ANOVAs(self) -> None:
        filename = self.filename.get().strip()
        if filename_checker(filename, self):
            return
        available_columns = [i for i in CLUSTER_NAMES if i in list(self.master.cat_exp.data.obs.columns)]
        column = self.column.get()
        if column == "":
            tk.messagebox.showwarning(title = "Warning!", 
                                    message = "You must choose a clustering!")
            self.focus()
            return
        elif self.column.get() not in available_columns:
            tk.messagebox.showwarning(title = "Warning!", 
                                    message = f"Clustering =  {column}  is not available in the dataset! \n Of {str(CLUSTER_NAMES)} \n"
                                    "These are currently available: {str(available_columns)}")
            self.focus()
            return
        if not overwrite_approval(self.master.cat_exp.directory + f"/Data_tables/{filename}.csv", file_or_folder = "file", GUI_object = self):
            return

        if self.GLM.get() == "ANOVA":
            family_type = "N/A"
            if self.condition1.get()  == "multicomparison":
                conditions = self.conditions
            else:
                conditions = self.condition1.get().split(" %vs.% ")
            output_df = self.master.cat_exp.do_abundance_ANOVAs(groupby_column = column, 
                                                                conditions = conditions)
            output_df.to_csv(self.master.cat_exp.data_table_dir + f"/{filename}.csv", index_label = column)
        else:
            family_type = self.GLM.get()[self.GLM.get().find(":")+1:]
            if self.condition1.get()  == "multicomparison":
                conditions = self.conditions
            else:
                conditions = self.condition1.get().split(" %vs.% ")
            self.master.cat_exp.do_count_GLM(variable = "condition", groupby_column = column, 
                                          conditions = conditions, 
                                          family = family_type, filename = filename)
        Analysis_widget_logger.info(f"""Ran Abundance statistical test: 
                                    conditions = {str(conditions)},
                                    groupby_column = {column},
                                    test_type = {family_type},
                                    filename = {filename}.csv""")  

        dataframe = pd.read_csv(self.master.cat_exp.directory + f"/Data_tables/{filename}.csv")
        TableLaunch(dataframe = dataframe.head(50), 
                    directory = filename, 
                    width = 1, 
                    height = 1, 
                    table_type = "First 50 entries of the cluster abundance statistics table", 
                    experiment = None, 
                    favor_table = True, 
                    logger = Analysis_widget_logger)
        
class run_state_ANOVAs_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):

    def __init__(self, master):
        super().__init__(master)
        self.master = master

        label = ctk.CTkLabel(master = self, text = "Choose clustering column:")
        label.grid(padx = 3, pady = 3)

        self.options = ["whole dataset"] + [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns]
        self.clustering_column = ctk.CTkOptionMenu(master = self, values = self.options, variable = ctk.StringVar(value = "whole dataset"))
        self.clustering_column.grid(padx = 3, pady = 3)

        def refresh_state_ANOVA_clusters(enter = ""):
            self.options = ["whole dataset"] + [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns]
            self.clustering_column.configure(values = self.options)

        self.clustering_column.bind("<Enter>", refresh_state_ANOVA_clusters)

        label2 = ctk.CTkLabel(master = self, text = "Choose marker class to analyze:")
        label2.grid(padx = 3, pady = 3)

        self.options2 = MARKER_CLASSES + ["All"]
        self.marker_class = ctk.CTkOptionMenu(master = self, values = self.options2, variable = ctk.StringVar(value = "state"))
        self.marker_class.grid(padx = 3, pady = 3)

        label3 = ctk.CTkLabel(master = self, text = "Choose statistic:")
        label3.grid(padx = 3, pady = 3)

        self.options3 = ["mean","median"]
        self.stat = ctk.CTkOptionMenu(master = self, values = self.options3, variable = ctk.StringVar(value = "mean"))
        self.stat.grid(padx = 3, pady = 3)

        label4 = ctk.CTkLabel(master = self, text = "Choose statistical test:")
        label4.grid(padx = 3, pady = 3)

        self.options4 = ["anova","kruskal"]
        self.test = ctk.CTkOptionMenu(master = self, values = self.options4, variable = ctk.StringVar(value = "anova"))
        self.test.grid(padx = 3, pady = 3)

        label10 = ctk.CTkLabel(master = self, text = "Choose Filename of exported table:")
        label10.grid(padx = 3, pady = 3)

        self.filename = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = 'state_exprs_ANOVA_table'))
        self.filename.grid(padx = 3, pady = 3)

        button = ctk.CTkButton(master = self, text = "Run state markers expression ANOVAs", command = self.run_state_ANOVAs)
        button.grid(padx = 3, pady = 3)

        self.after(200, self.focus())

    def run_state_ANOVAs(self) -> None:
        filename = self.filename.get().strip()
        if filename_checker(filename, self):
            return
        
        available_columns = [i for i in CLUSTER_NAMES if i in list(self.master.cat_exp.data.obs.columns)] + ["whole dataset"]
        clustering = self.clustering_column.get()
        if clustering not in available_columns:
            tk.messagebox.showwarning(title = "Warning!", 
                                message = "You must select a clustering!")
            self.focus()
            return
        elif clustering not in available_columns:
            tk.messagebox.showwarning(title = "Warning!", 
                                message = f"Clustering =  {clustering}  is not available in the dataset! \n" +
                                f"Of {str(CLUSTER_NAMES + ['whole dataset'])} \n These are currently available: {str(available_columns)}")
            self.focus()
            return
        
        if not overwrite_approval(self.master.cat_exp.directory + f"/Data_tables/{filename}.csv", file_or_folder = "file", GUI_object = self):
            return
        
        success = self.master.cat_exp.do_state_exprs_ANOVAs(filename = filename, marker_class = self.marker_class.get(), 
                                                    groupby_column = clustering, # ind_var_column = 'condition', 
                                                    statistic = self.stat.get(), 
                                                    test = self.test.get())
        if success is None:
            warning_window("There are no channels of this marker_class!")
            return
        
        Analysis_widget_logger.info(f"""Ran marker Expression ANOVA tests: 
                                    marker class = {self.marker_class.get()}
                                    clustering column = {clustering},
                                    aggregateion_statistic = {self.stat.get()},
                                    anova_or_kruskal = {self.test.get()},
                                    filename = {filename}.csv""")
        dataframe = pd.read_csv(self.master.cat_exp.directory + f"/Data_tables/{filename}.csv")
        TableLaunch(dataframe = dataframe.head(50), 
                    directory = filename, 
                    width = 1, 
                    height = 1, 
                    table_type = "First 50 entries of the state expression statistics table",
                    experiment = None, 
                    favor_table = True, 
                    logger = Analysis_widget_logger)

class cluster_statistics_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):

    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.title("Create & View Cluster Marker Expression Statistics")

        label = ctk.CTkLabel(master = self, text = "Cluster Statistics Heatmap:")
        label.grid(column = 0, row = 0, pady = 5)

        label2 = ctk.CTkLabel(master = self, text = "Choose Clustering / Merging to run ANOVA on:")
        label2.grid(column = 0, row = 1, pady = 5, padx = 5)

        option_list = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns] 
        self.column_type = ctk.CTkOptionMenu(master = self, 
                                             values = option_list, 
                                             variable = ctk.StringVar(), 
                                             command = self.update_option_menu) 
        self.column_type.grid(column = 1, row = 1, pady = 5, padx = 5)

        def refresh_cluster_stats_clusters(enter = ""):
            option_list = [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns] 
            self.column_type.configure(values = option_list)

        self.column_type.bind("<Enter>", refresh_cluster_stats_clusters)

        label4 = ctk.CTkLabel(master = self, text = "Heatmap Filename:")
        label4.grid(column = 0, row = 4, pady = 5, padx = 5)

        self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value = "Statistic_Heatmap"))
        self.filename.grid(column = 1, row = 4, padx = 5, pady = 5)

        self.button = ctk.CTkButton(master = self, 
                                    text = "Plot Heatmap", 
                                    command = lambda: self.run_stat(filename = self.filename.get().strip(),
                                                                    obs_column = self.column_type.get()))
        self.button.grid(column = 1, row = 5, padx = 5, pady = 5)

        label_col3 = ctk.CTkLabel(master = self, text = "Select individual cluster to open stat table for:")
        label_col3.grid(column = 3, row = 1, padx = 5, pady = 5)

        self.cluster_to_table = ctk.CTkOptionMenu(master = self, values = [""], variable = ctk.StringVar(value = "")) 
        self.cluster_to_table.grid(column = 3, row = 2, pady = 5, padx = 5)
        self.cluster_to_table.bind("<Enter>", lambda enter: self.update_option_menu())

        self.output = ctk.CTkCheckBox(master = self, text = "Check to export stat table to disk", onvalue = True, offvalue = False)
        self.output.grid(column = 3, row = 4, padx = 5, pady = 5)

        self.button2 = ctk.CTkButton(master = self, text = "Open Table for selected cluster", command = lambda: self.launch_stat_table())
        self.button2.grid(column = 3, row = 5, padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(column = 1, row = 6, padx = 3, pady = 3)

        self.after(200, lambda: self.focus()) 

    def run_stat(self, filename: str, obs_column: str) -> None:
        '''
        '''
        if filename_checker(filename, self):
            return
        if not overwrite_approval(self.master.cat_exp.save_dir + f"/Neg_log_{filename}.csv", file_or_folder = "file", GUI_object = self):
            return
        self.master.cat_exp.do_cluster_stats(groupby_column = obs_column)
        figure = self.master.cat_exp.plot_cluster_stats(filename = filename)
        
        self.master.save_and_display(filename = "Neg_log_" + filename,sizeX = 550, sizeY = 550)
        Analysis_widget_logger.info(f"""Plotted heatmap of cluster comparison statistics:
                                    cell clustering = {obs_column},
                                    filename = Neg_log_{filename}.png""")
        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

    def update_option_menu(self, choice: Union[None, str] = None) -> None:
        '''
        '''
        if choice is None:
            choice = self.column_type.get()
            warning = False
        else:
            warning = True
        try:
            option_list = list(self.master.cat_exp.data.obs[choice].unique())
        except KeyError:
            if warning is True:   ## only warn if someone has selected a non-existant column -- 
                                    # not everytime someone mouses over the cluster_to_table optionmenu
                tk.messagebox.showwarning("Warning!", message = f"{choice} not available!")
                self.focus()
                return
            return
        else:
            option_list.sort()
            option_list = [str(i) for i in option_list]
        self.cluster_to_table.configure(values = option_list)

    def launch_stat_table(self) -> None:
        '''
        '''
        output_bool = self.output.get()
        cluster = self.cluster_to_table.get()
        obs_column = self.column_type.get()

        df_out_dict = self.master.cat_exp.do_cluster_stats(groupby_column = obs_column)
        try:
            dataframe = df_out_dict[int(cluster)]
        except ValueError:
            dataframe = df_out_dict[cluster]
        
        if output_bool is True:
            output_path = f'{self.master.cat_exp.directory}/Data_tables/cluster_stat_tables/{str(self.cluster_to_table.get())}.csv' 
            output_folder = f'{self.master.cat_exp.directory}/Data_tables/cluster_stat_tables/'
            if not os.path.exists(output_folder):
                os.mkdir(output_folder)
            dataframe.to_csv(output_path, index = False)

        Analysis_widget_logger.info(f"""Generated cluster comparison statistic table for cluster: {cluster}
                                    cell clustering = {obs_column},
                                    exported = {output_bool}""")
        
        TableLaunch(dataframe = dataframe, 
                    directory = cluster, 
                    width = 1, 
                    height = 1, 
                    table_type = "other", 
                    experiment = None, 
                    favor_table = True, 
                    logger = Analysis_widget_logger)

class Scaling_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        label1 = ctk.CTkLabel(master = self, text = "Choose to Scale / Unscale data \n (99.9% or min_max are more standard):")
        label1.grid(column = 0, row = 0, pady = 5, padx = 5)

        label2 =  ctk.CTkLabel(master = self, text = f"Current scaling = \n {self.master.cat_exp._scaling}")
        label2.grid(column = 1, row = 0, pady = 5, padx = 5)

        label3 =  ctk.CTkLabel(master = self, text = "Select upper quantile: \n used for % quantile scaling")
        label3.grid(column = 1, row = 1, pady = 5, padx = 5, columnspan = 2)

        self.upper_quant = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "99.9"))
        self.upper_quant.grid(column = 1, row = 2, pady = 5, padx = 5, columnspan = 2)

        values_list = ["min_max", "%quantile", "standard", "robust", "qnorm", "unscale"]
        self.choice_menu = ctk.CTkOptionMenu(master = self, variable = ctk.StringVar(value = "%quantile"), values = values_list)
        self.choice_menu.grid(column = 0, row = 1, pady = 5, padx = 5)

        self.button1 = ctk.CTkButton(master = self, text = "Perform Scaling", command = self.call_scaling)
        self.button1.grid(column = 0, row = 4, padx = 5, pady = 5)

        self.after(200, lambda: self.focus()) 

    def call_scaling(self) -> None:
        scaling_choice = self.choice_menu.get()
        upper_quant = self.upper_quant.get()
        upper_quant_log = "n/a"
        if scaling_choice == "%quantile":
            try:
                upper_quant = float(upper_quant)
                upper_quant_log = str(upper_quant)
            except ValueError:
                tk.messagebox.showwarning("Warning!", message = "Upper quantile must be a number for %quantile scaling!")
                self.focus()
                return
        self.master.cat_exp.do_scaling(scaling_choice, upper_quantile = upper_quant)
        Analysis_widget_logger.info(f"Scaling set to {self.choice_menu.get()}, quantile% = {upper_quant_log}") 
        self.destroy()

class image_drop_restore_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.column = None
        self.label = None
        self.drop = None
        self.col1 = None
        self.col2 = None
        self.title("Filter cells from the analysis \n (Temporary: restore to original state by reloading experiment)")
        label1 = ctk.CTkLabel(master = self, text = "Choose a metadata column to Filter your analysis on:")
        label1.grid(column = 0, row = 0, pady = 5, padx = 5)

        values_list = COLNAMES + CLUSTER_NAMES

        def refresh_list():
            values = [i for i in values_list if i in self.master.cat_exp.data.obs.columns]
            self.choice_menu.configure(values = values)


        self.choice_menu = ctk.CTkOptionMenu(master = self, variable = ctk.StringVar(value = "Select column to filter dataset on"),
                                             values = [""], 
                                             command = lambda choice: self.switch_column(choice))
        self.choice_menu.bind("<Enter>", lambda event: refresh_list())
        
        self.choice_menu.grid(column = 0, row = 1, pady = 5, padx = 5)

        self.button1 = ctk.CTkButton(master = self, text = "Drop Samples", command = self.call_drop)
        self.button1.grid(column = 0, row = 4, padx = 5, pady = 5)
        self.button1.configure(state = "disabled")
        self.after(200, lambda: self.focus()) 

    def switch_column(self, column: str) -> None:
        if self.label is not None:
            self.label.destroy()
        if self.drop is not None:
            self.drop.destroy()

        self.column = column
        if column == "sample_id":
            self.col1 = "File_name"
            self.col2 = "Sample id"
        else:
            self.col1 = None
            self.col2 = column

        self.label = self.label_frame(self)
        self.label.grid(row = 2, column = 0, padx = 5)
        
        self.drop = self.drop_frame(self)
        self.drop.grid(row = 3, column = 0, padx = 5)

        self.button1.configure(state = "normal")

    class label_frame(ctk.CTkFrame):
        def __init__(self, master):
            super().__init__(master)
            if self.master.col1 is not None:
                label1 = ctk.CTkLabel(master = self, text = self.master.col1)
                label1.grid(column = 0, row = 0, pady = 5, padx = 5)

            label2 = ctk.CTkLabel(master = self, text = self.master.col2)
            label2.grid(column = 1, row = 0, pady = 5, padx = 5)

            label3 = ctk.CTkLabel(master = self, text = "Check to Filter \n from experiment:")
            label3.grid(column = 2, row = 0, pady = 5, padx = 5)

    class drop_frame(ctk.CTkScrollableFrame):
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            self.configure(width = 300)            
            self.panel = self.master.master.cat_exp.data.obs.copy() 
            self.metadata = pd.read_csv(self.master.master.directory + '/metadata.csv')
            try:
                filter_column = list(self.panel[self.master.column].astype('int').sort_values().unique())
            except ValueError:
                filter_column = list(self.panel[self.master.column].astype('str').sort_values().unique())

            if self.master.col1 is not None:
                file_names = list(self.metadata["file_name"])
            else:
                file_names = filter_column
            counter = 0
            self.checkbox_list = []
            for i,ii in zip(file_names, filter_column):
                if self.master.col1 is not None:
                    length = len(i)
                    if length > 20:
                        label = ctk.CTkLabel(master = self, text = i[:15] + "..." + i.strip(".fcs")[-8:], width = 150)
                        label.grid(column = 0, row = counter, pady = 5, padx = 5)
                    else:
                        label = ctk.CTkLabel(master = self, text = i, width = 150)
                        label.grid(column = 0, row = counter, pady = 5, padx = 5)
                label2 = ctk.CTkLabel(master = self, text = ii)
                label2.grid(column = 1, row = counter, pady = 5, padx = 5)
                checkbox = ctk.CTkCheckBox(master = self, text = "", onvalue = ii, offvalue = False)
                checkbox.grid(column = 2, row = counter, pady = 5, padx = 5)
                self.checkbox_list.append(checkbox)
                counter += 1

        def retrieve(self) -> list[Union[bool,str,int]]:
            checkbox_output = [i.get() for i in self.checkbox_list if i.get() is not False]
            return checkbox_output
         
    def call_drop(self) -> None:
        filter_sample_ids = self.drop.retrieve()
        if filter_sample_ids == []:
            return
        for i in filter_sample_ids:
            self.master.cat_exp.filter_data(i, column = self.column)
        Analysis_widget_logger.info("Dropped from loaded analysis (will be restored at reload): \n" +
                                    f"column = {self.column}, \n" +
                                    f"to_drop = {str(filter_sample_ids)}")
        
        ## TODO: test this! -- purpose is to re-disable buttons in spaceANOVA, as the data for that has been changed
        self.master.master.master.Spatial.widgets.widgets.disable_buttons() 

        self.destroy()

class data_table_exportation_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master, data_table, umap = True):
        super().__init__(master)
        self.master = master
        try:
            data_table.obs = data_table.obs.drop('distance_to_bmu')
        except KeyError:
            pass
        self.data_table = data_table

        self.title("Export Data Tables!")
        label1 = ctk.CTkLabel(master = self, text = "Export Data Tables:")
        label1.grid(column = 0, row = 0, pady = 5, padx = 5)

        self.subset_or_whole = ctk.StringVar(value = "whole")
        radio_A_1 = ctk.CTkRadioButton(master = self, 
                                       text = "Whole Dataframe", 
                                       variable = self.subset_or_whole, 
                                       value = 'whole', 
                                       command = self.whole_command)
        radio_A_1.grid(column = 0, row = 1, pady = 5, padx = 5)

        radio_A_2 = ctk.CTkRadioButton(master = self, 
                                       text = "Subset Dataframe", 
                                       variable = self.subset_or_whole, 
                                       value = 'subset', 
                                       command = self.subset_command)
        radio_A_2.grid(column = 1, row = 1, pady = 5, padx = 5)

        self.subset_frame = self.subset_frame_class(self, data_table)
        self.subset_frame.grid(column = 0, columnspan = 5, row = 2, rowspan = 4, pady = 5, padx = 5)

        self.groupby_or_plain = ctk.StringVar(value = "plain")
        radio_B_1 = ctk.CTkRadioButton(master = self, 
                                       text = "No grouping", 
                                       variable = self.groupby_or_plain, 
                                       value = 'plain', 
                                       command = self.plain_command)
        radio_B_1.grid(column = 0, row = 6, pady = 5, padx = 5)

        radio_B_2 = ctk.CTkRadioButton(master = self, 
                                       text = "Export Grouping", 
                                       variable = self.groupby_or_plain, 
                                       value = 'groupby', 
                                       command = self.grouping_command)
        radio_B_2.grid(column = 1, row = 6, pady = 5, padx = 5)

        self.grouping = self.grouping_frame(self, data_table)
        self.grouping.grid(column = 0, columnspan = 4, row = 7, pady = 5, padx = 5)

        label = ctk.CTkLabel(master = self, 
            text = "select filename (if grouped, the grouping statistic \n will be automatically appended to start:)")
        label.grid(column = 1, row = 8, pady = 5, padx = 5)

        self.export_marker_class = ctk.CTkCheckBox(master = self, 
                                    text = "Check to export markerclass \n (type/state/etc.) information \n as the final row of the data table",
                                    onvalue = True, 
                                    offvalue = False)
        self.export_marker_class.grid(column = 0, row = 9, pady = 5, padx = 5)

        self.file_name_entry = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "data_table_1"))
        self.file_name_entry.grid(column = 1, row = 9, pady = 5, padx = 5)

        self.button1 = ctk.CTkButton(master = self, text = "Export Table", command = self.export_table)
        self.button1.grid(column = 1, row = 10, padx = 5, pady = 5)

        if umap is True:
            label_umap = ctk.CTkLabel(master = self, text = "Export Dimensionality Reduction Embedding:")
            label_umap.grid(column = 6, row = 1, pady = 5, padx = 5)

            self.umap_pca = ctk.CTkOptionMenu(master = self, values = ["umap","pca"], variable = ctk.StringVar(value = "umap"))
            self.umap_pca.grid(column = 6, row = 2, pady = 5, padx = 5)

            self.umap_pca_filename = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "file_umap_embedding"))
            self.umap_pca_filename.grid(column = 6, row = 3, pady = 5, padx = 5)

            self.umap_pca_button = ctk.CTkButton(master = self, text = "Export Umap / PCA embedding", 
                                                command = lambda: self.do_umap_pca(self.umap_pca.get(), self.umap_pca_filename.get()))
            self.umap_pca_button.grid(column = 6, row = 4, padx = 5, pady = 5)

        self.whole_command()
        self.plain_command()
        self.after(200, lambda: self.focus()) 

    def whole_command(self) -> None:
        self.export_marker_class.configure(state = "normal")
        for i in self.subset_frame.children:
            child = self.subset_frame.children[i]
            try:
                child.configure(state = "disabled")
            except Exception:
                pass

    def subset_command(self) -> None:
        self.export_marker_class.deselect()
        self.export_marker_class.configure(state = "disabled")
        for i in self.subset_frame.children:
            child = self.subset_frame.children[i]
            try:
                child.configure(state = "normal")
            except Exception:
                pass

    def plain_command(self) -> None:
        self.export_marker_class.configure(state = "normal")
        for i in self.grouping.children:
            child = self.grouping.children[i]
            try:
                child.configure(state = "disabled")
            except Exception:
                pass

    def grouping_command(self) -> None:
        self.export_marker_class.deselect()
        self.export_marker_class.configure(state = "disabled")
        for i in self.grouping.children:
            child = self.grouping.children[i]
            try:
                child.configure(state = "normal")
            except Exception:
                pass

    def do_umap_pca(self, kind: str, filename: str) -> None:
        filename = self.umap_pca_filename.get().strip()
        if filename_checker(filename, self):
            return
        if not overwrite_approval(self.master.cat_exp.data_table_dir + f"/{filename}.csv", file_or_folder = "file", GUI_object = self):
            return
        self.master.cat_exp.export_DR(kind = kind, filename = filename)
        Analysis_widget_logger.info(f"DR table exported: kind = {kind}, filename = {filename}") 

    def export_table(self) -> None:
        filename = self.file_name_entry.get().strip()
        if filename_checker(filename, self):
            return
        
        subset_or_whole = self.subset_or_whole.get()
        if subset_or_whole == "subset":
            columns_to_subset_on, column_values_list = self.subset_frame.recover()
            if len(columns_to_subset_on) == 0:
                columns_to_subset_on = None
            if len(column_values_list) == 0:
                columns_to_subset_on = None
        else:
            columns_to_subset_on = None
            column_values_list = None

        if self.groupby_or_plain.get() == "groupby":
            grouping_list, stat = self.grouping.recover()
            filename = f'{stat}_{filename}' 
            if len(grouping_list) == 0:
                grouping_list = None 
        else:
            grouping_list = None
            stat = None

        if not overwrite_approval(self.master.cat_exp.data_table_dir + f"/{filename}.csv", file_or_folder = "file", GUI_object = self):
            return

        self.master.cat_exp.export_data(filename = filename, 
            subset_columns = columns_to_subset_on, 
            subset_types = column_values_list, 
            groupby_columns = grouping_list, 
            statistic = stat,
            include_marker_class_row = self.export_marker_class.get())
        try:
            Analysis_widget_logger.info(f"Exported data from analysis with the following settings: \n"
                                        f"filename = {filename}, \n"
                                        f"subset_columns = {str(columns_to_subset_on)}, \n" 
                                        f"subset_types = {str(column_values_list)}, \n"
                                        f"groupby_columns = {str(grouping_list)}, \n"
                                        f"aggregation_statistic = {str(stat)} \n"
                                        f"include_marker_class_row = {self.export_marker_class.get()}") 
        except Exception:
            print(f"Logging failed (expected for whole-class analysis) -- Exported data from analysis with the following settings: \n"
                    f"filename = {filename}, \n"
                    f"subset_columns = {str(columns_to_subset_on)},  \n"
                    f"subset_types = {str(column_values_list)},  \n"
                    f"groupby_columns = {str(grouping_list)},  \n"
                    f"aggregation_statistic = {str(stat)} \n"
                    f"include_marker_class_row = {self.export_marker_class.get()}") 

    class grouping_frame(ctk.CTkFrame):
        def __init__(self, master, data_table):
            super().__init__(master)
            self.data_table = data_table

            grand_label = ctk.CTkLabel(master = self, text = "Select Columns to group data by:")
            grand_label.grid(row = 0 , column = 0, padx = 3, pady = 3)

            self.checkbox_list = []
            allowed_columns_list = CLUSTER_NAMES + COLNAMES
            to_list = [i for i in data_table.obs.columns if i in allowed_columns_list]
            self.to_list = np.array(to_list)
            for ii,i in enumerate(to_list):
                checkbox = ctk.CTkCheckBox(master = self, text = f'{i}', onvalue = True, offvalue = False)
                checkbox.grid(row =  1, column = ii + 1, padx = 2, pady = 2)
                self.checkbox_list.append(checkbox)

            label = ctk.CTkLabel(master = self, text = "Select group statistic:")
            label.grid(row = 2, column = 0, padx = 3, pady = 3)

            self.stat_option = ctk.CTkOptionMenu(master = self, 
                                                 values = ["count","mean","median","std","sum"], 
                                                 variable = ctk.StringVar(value = "mean"))
            self.stat_option.grid(column = 0, row = 3, pady = 5, padx = 5)

        def recover(self) -> tuple[list[bool], str]:
            stat = self.stat_option.get()
            grouping_list_slicer = np.array([i.get() for i in self.checkbox_list])
            grouping_list = list(self.to_list[grouping_list_slicer])
            return grouping_list, stat

    class subset_frame_class(ctk.CTkFrame):
        def __init__(self, master, data_table):
            super().__init__(master)
            self.data_table = data_table

            grand_label = ctk.CTkLabel(master = self, 
                        text = "Select Columns & column values to subset data on. \n Rows WITHOUT the selected column values will be dropped:")
            grand_label.grid(row = 0 , column = 0, columnspan = 3, padx = 3, pady = 6)

            sub_label1 = ctk.CTkLabel(master = self, text = "Selecting a column means it \n will be used for subsetting:")
            sub_label1.grid(row = 1, column = 0, padx = 3, pady = 3)

            sub_label2 = ctk.CTkLabel(master = self, text = "Column values to keep can be selected --")
            sub_label2.grid(row = 1, column = 1, pady = 3)

            sub_label3 = ctk.CTkLabel(master = self, text = "or they can be manually entered, separated by commas:")
            sub_label3.grid(row = 1, column = 2, pady = 3)

            self.column_values_list = []
            self.columns_keep_or_no = []

            allowed_columns_list = CLUSTER_NAMES + COLNAMES
            to_list = [i for i in data_table.obs.columns if i in allowed_columns_list]

            for ii,i in enumerate(data_table.obs.columns):
                if i in to_list:
                    leader_checkbox = ctk.CTkCheckBox(master = self, text = f'column: {i}', onvalue = True, offvalue = False)
                    leader_checkbox.grid(row = ii + 2, column = 0, padx = 2, pady = 2)
                    self.columns_keep_or_no.append(leader_checkbox)

                    column = data_table.obs[i].astype('str')
                    self.column_choice = self.special_optionmenu(master = self, values = column.unique(), row_number = ii)
                    self.column_choice.grid(row = ii + 2, column = 1, padx = 2, pady = 2)

                    def refresh_export_column_choice(enter = ""):
                        column = data_table.obs[i].astype('str')
                        if list(column.unique()) == []:
                            self.column_choice.configure(values = "")
                            return
                        self.column_choice.configure(values = list(column.unique()))

                    self.column_choice.bind("<Enter>", refresh_export_column_choice)

                    text_box_of_choices = ctk.CTkTextbox(master = self, activate_scrollbars = True, wrap = 'none')
                    text_box_of_choices.grid(row = ii + 2, column = 2, padx = 2, pady = 2)
                    text_box_of_choices.configure(width = 160, height  = 40)
                    self.column_values_list.append(text_box_of_choices)
                else:
                    leader_checkbox = ctk.CTkCheckBox(master = self, text = f'column: {i}', onvalue = True, offvalue = False)
                    self.columns_keep_or_no.append(leader_checkbox)
                    text_box_of_choices = ctk.CTkTextbox(master = self, activate_scrollbars = True, wrap = 'none')
                    self.column_values_list.append(text_box_of_choices)

        def recover(self) -> tuple[list[str], list[str]]:
            subsetter_silcer = np.array([i.get() for i in self.columns_keep_or_no])
            columns_to_subset_on = list(self.data_table.obs.columns[subsetter_silcer])

            column_values = [i.get('0.0', 'end').replace('\n','').rstrip(",").split(",") for i in self.column_values_list]
            column_values_list = []
            for ii,i in zip(list(subsetter_silcer),column_values):
                if ii:
                    column_values_list.append(i)

            return columns_to_subset_on, column_values_list

        class special_optionmenu(ctk.CTkOptionMenu):
            def __init__(self, master, values: str, row_number: int): 
                self.master = master
                super().__init__(master, variable = ctk.StringVar(value = ''), values = values, command = self.select_value)
                self.row_number = row_number

            def select_value(self, value: str) -> None:
                text_box_of_choices = self.master.column_values_list[self.row_number]
                current_list = text_box_of_choices.get('0.0','end').rstrip(",").split(",")
                if value not in current_list:
                    text_box_of_choices.insert("0.0", f'{value},')

class combat_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        self.title("Combat Batch Correction")

        label = ctk.CTkLabel(master = self, 
            text  = "ComBat Batch Correction. Choose batch column of the data: \n"
                    "adding covariate information currently not supported -- \n"
                    "lacking covariates can create bias or errors with unbalanced numbers of samples in each group")
        label.grid(row = 0, column = 0, padx = 5, pady = 5)

        self.batch_column = ctk.CTkOptionMenu(master = self, 
                                            values = COLNAMES, 
                                            variable = ctk.StringVar(value = "patient_id"))
        self.batch_column.grid(row = 1, column = 1, padx = 5, pady = 5)

        button = ctk.CTkButton(master = self, text = "Run Batch Correction", command = self.do_combat)
        button.grid(row = 2, column = 0 , padx = 5, pady= 5)

        self.after(200, self.focus())       

    def do_combat(self) -> None:
        batch_column = self.batch_column.get()
        self.master.cat_exp.do_COMBAT(batch_column)
        Analysis_widget_logger.info(f"""Ran ComBat batch correction. Batch column in metadata file = {str(batch_column)}""") 
        self.destroy()

class do_leiden_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    ''''''
    def __init__(self, master):
        super().__init__(master)
        self.master

        master_label = ctk.CTkLabel(master = self, text = "Choose Leiden Clustering parameters \n (Also runs UMAP on ALL cells, which can be plotted like any other UMAP embedding):")
        master_label.grid(column = 0, columnspan = 2, row = 1, padx = 3, pady = 3)

        label1 = ctk.CTkLabel(master = self, text = "Marker Class:")
        label1.grid(column = 0, row = 2, padx = 3, pady = 3)

        self.marker_class = ctk.CTkOptionMenu(master = self, values = ["All"] + MARKER_CLASSES, variable = ctk.StringVar(value = "type"))
        self.marker_class.grid(column = 1, row = 2, padx = 3, pady = 3)

        label2 = ctk.CTkLabel(master = self, text = "UMAP Minimum Distance:")
        label2.grid(column = 0, row = 3, padx = 3, pady = 3)

        self.minimum_distance = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "0.1"))
        self.minimum_distance.grid(column = 1, row = 3, padx = 3, pady = 3)

        label3 = ctk.CTkLabel(master = self, text = "UMAP number of neighbors:")
        label3.grid(column = 0, row = 4, padx = 3, pady = 3)

        self.n_neighbors = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "15"))
        self.n_neighbors.grid(column = 1, row = 4, padx = 3, pady = 3)

        label4 = ctk.CTkLabel(master = self, text = "Leiden Resolution:")
        label4.grid(column = 0, row = 5, padx = 3, pady = 3)

        self.resolution = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "1"))
        self.resolution.grid(column = 1, row = 5, padx = 3, pady = 3)

        label5 = ctk.CTkLabel(master = self, text = "Random Seed:")
        label5.grid(column = 0, row = 6, padx = 3, pady = 3)

        self.seed = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "42"))
        self.seed.grid(column = 1, row = 6, padx = 3, pady = 3)

        execute_button = ctk.CTkButton(master = self, text = "Run Leiden", command = self.do_leiden)
        execute_button.grid(column = 1, row = 7, padx = 3, pady = 3)

    def do_leiden(self):
        seed = self.seed.get()
        marker_class = self.marker_class.get()
        resolution = self.resolution.get()
        minimum_distance = self.minimum_distance.get()
        n_neighbors = self.n_neighbors.get()
        try:
            seed = int(seed)
            n_neighbors = int(n_neighbors)
            resolution = float(resolution)
            minimum_distance = float(minimum_distance)
        except ValueError:
            tk.messagebox.showwarning("Warning!", message = "Seed, resolution, neighbors, and minimum distance must be numeric! Exiting without performing Leiden")
            self.focus()
            return
        success = self.master.cat_exp.do_leiden_clustering(marker_class = marker_class, 
                                                 resolution = resolution, 
                                                 min_dist = minimum_distance,
                                                 n_neighbors = n_neighbors, 
                                                 seed = seed,
                                                 try_from_umap_embedding = False)
        if success:
            self.master.plot_bank.umap_plot.configure(state = 'normal')

            ## TODO: test!
            try: ## either space_analysis or data_table attributes may not exist
                if self.master.cat_exp.space_analysis.cellType_key == 'leiden':
                    self.master.master.master.Spatial.widgets.widgets.disable_buttons() 
            except Exception:
                pass
            self.withdraw()     
        else:
            warning_window("There are no channels of the selected marker_class!")   
        
class Plot_window_display(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, figure):
        super().__init__()
        self.title("Plot Title")
        self.figure = figure
        self.text_size = 10
        try:
            figure.legends[-1]
            self.has_legend = True
        except AttributeError:
            try:
                figure.axes.legends[-1]
                self.has_legend = True
            except Exception:
                self.has_legend = False
        except IndexError:
            try:
                figure.axes.legends[-1]
                self.has_legend = True
            except Exception:
                self.has_legend = False

        self.leg_x = 0.85
        self.leg_y = 0.85
        self.size = 850

        self.display_widg = MatPlotLib_Display(master = self, height = 850, width = 850)
        self.display_widg.configure(height = 850, width = 850)
        self.display_widg.update_figure(figure)
        self.display_widg.grid(row = 0, column = 0, padx = 3, rowspan = 10)

        legend_slider_label = ctk.CTkLabel(master = self, text = "Adjust Legend location (X,Y) using sliders: \n (not available for heatmaps)")
        legend_slider_label.grid(row = 1, column = 1, padx = 3, columnspan = 2)

        if self.has_legend is True:
            legend_x_slider = ctk.CTkSlider(self, from_ = -0.75, to = 1.25, number_of_steps = 30, command = self.move_legend_x)
            legend_x_slider.grid(row = 2, column = 2, padx = 3)
            legend_x_slider.set(0.85)

            self.X_var = ctk.StringVar(value = f'Legend X: {sigfig.round(legend_x_slider.get(), 2, warn = False)}')
            labelx = ctk.CTkLabel(master = self, textvariable = self.X_var)
            labelx.grid(row = 2, column = 1, padx = 3)

            legend_y_slider = ctk.CTkSlider(self, from_ = -0.75, to = 1.25, number_of_steps = 30, command = self.move_legend_y)
            legend_y_slider.grid(row = 3, column = 2, padx = 3)
            legend_y_slider.set(0.85)

            self.Y_var = ctk.StringVar(value = f'Legend Y: {sigfig.round(legend_y_slider.get(), 2, warn = False)}')
            labely = ctk.CTkLabel(master = self, textvariable = self.Y_var)
            labely.grid(row = 3, column = 1, padx = 3)
            
        else:
            labelx = ctk.CTkLabel(master = self, text = "No Legend detected in Figure")
            labelx.grid(row = 3, column = 1, padx = 3)

        self.text_sizer = ctk.CTkOptionMenu(master = self, 
                                            values = ["4","5","6","7","8","9","10","11","12","13","14","15"], 
                                            variable = ctk.StringVar(value = "Text Font Size"), 
                                            command = lambda choice: self.resize_text(choice))
        self.text_sizer.grid(row = 4, column = 2, padx = 3)

        aspect_slider_label = ctk.CTkLabel(master = self, text = "Adjust Figure Aspect Ratio and Size:")
        aspect_slider_label.grid(row = 1, column = 4, padx = 3, columnspan = 2)

        aspect_slider = ctk.CTkSlider(self, from_ = -0.95, to = 0.95, number_of_steps = 38, command = self.change_aspect)
        aspect_slider.grid(row = 2, column = 5, padx = 3)

        self.aspect_var = ctk.StringVar(value = "Aspect Ratio: 1.0")
        labelx = ctk.CTkLabel(master = self, textvariable = self.aspect_var)
        labelx.grid(row = 2, column = 4, padx = 3)

        size_slider = ctk.CTkSlider(self, from_ = 500, to = 1000, number_of_steps = 50, command = self.resize_widget)
        size_slider.grid(row = 3, column = 5, padx = 3)
        size_slider.set(1000)

        self.size_var = ctk.StringVar(value = f"Size: {sigfig.round(size_slider.get(), 2, warn = False)}")

        labelx = ctk.CTkLabel(master = self, textvariable = self.size_var)
        labelx.grid(row = 3, column = 4, padx = 3)

        self.after(200, self.focus())

    def move_legend_x(self, legend_x: float) -> None:
        self.leg_x = legend_x
        self.X_var.set( f'Legend X: {sigfig.round(legend_x, 3, warn = False)}')
        
        try:
            self.display_widg.figure.legends[-1]._remove_method = self.display_widg.figure.legends.remove
            sns.move_legend(self.display_widg.figure, 
                            loc = "center right", 
                            bbox_to_anchor = (self.leg_x, self.leg_y), 
                            fontsize = self.text_size)
        except Exception:
            sns.move_legend(self.display_widg.figure.axes[-1], 
                            loc = "center right", 
                            bbox_to_anchor = (self.leg_x, self.leg_y), 
                            fontsize = self.text_size)
        self.display_widg.canvas.draw()

    def move_legend_y(self, legend_y: float) -> None:
        self.leg_y = legend_y
        self.Y_var.set(f'Legend Y: {sigfig.round(legend_y, 2, warn = False)}')
        try:
            self.display_widg.figure.legends[-1]._remove_method = self.display_widg.figure.legends.remove
            sns.move_legend(self.display_widg.figure, 
                            loc = "center right", 
                            bbox_to_anchor = (self.leg_x, self.leg_y), 
                            fontsize = self.text_size)
        except Exception:
            sns.move_legend(self.display_widg.figure.axes[-1], 
                            loc = "center right", 
                            bbox_to_anchor = (self.leg_x, self.leg_y), 
                            fontsize = self.text_size)
        self.display_widg.canvas.draw()

    def change_aspect(self, aspect: float) -> None:
        if aspect == 0:   ## this means a ratio of 1.0
            self.display_widg.figure.set_figwidth(self.size / 100)
            self.display_widg.figure.set_figheight(self.size / 100)
            self.display_widg.canvas.draw()
            self.display_widg.widget.configure(width = self.size, height = self.size)
            self.aspect_var.set("Aspect Ratio: 1.0")
        elif aspect > 0: 
            aspect = 1 - aspect
            self.display_widg.figure.set_figwidth(self.size / 100)
            self.display_widg.figure.set_figheight((self.size * aspect) / 100)
            self.display_widg.canvas.draw()
            self.display_widg.widget.configure(width = self.size, height = self.size*aspect)
            self.aspect_var.set(f"Aspect Ratio: {sigfig.round((1/aspect), 2, warn = False)}")
        else:
            aspect = 1 + aspect
            self.display_widg.figure.set_figwidth((self.size * aspect) / 100)
            self.display_widg.figure.set_figheight(self.size / 100)
            self.display_widg.canvas.draw()
            self.display_widg.widget.configure(width = self.size*aspect, height = self.size)
            self.aspect_var.set(f"Aspect Ratio: {sigfig.round(aspect, 2, warn = False)}")

    def resize_widget(self, size: float) -> None:
        self.size_var.set(f"Size: {sigfig.round(size, 3, warn = False)}")
        self.display_widg.widget.configure(width = int(size), height = int(size))
        self.size = int(size)

    def resize_text(self, text_size: float) -> None:
        if self.display_widg.figure is None:
            return
        text_size = float(text_size)
        self.text_size = text_size
        for i in self.display_widg.figure.axes:
            i.set_title(i.get_title(), y = 1.03, size = text_size)
            i.set_ylabel(i.get_ylabel(), size = text_size)
            i.set_xlabel(i.get_xlabel(), size = text_size)
            i.tick_params(labelsize = text_size)
        try:
            self.display_widg.figure.legends[-1]._remove_method = self.display_widg.figure.legends.remove
            sns.move_legend(self.display_widg.figure, 
                            loc = "center right", 
                            bbox_to_anchor =  [self.leg_x, self.leg_y], 
                            fontsize = text_size)
        except Exception:
            try:
                sns.move_legend(self.display_widg.figure.axes[-1], 
                                loc = "center right", 
                                bbox_to_anchor = [self.leg_x, self.leg_y], 
                                fontsize = text_size)
            except Exception:
                print("could not change legend fontsize")
        self.display_widg.canvas.draw()

class MatPlotLib_Display(ctk.CTkFrame):
    def __init__(self, master, height = 550, width = 550, bug = 'Capture.png'):
        super().__init__(master)
        self.master = master
        self.height = height
        self.width = width

        self.background = ctk.CTkButton(master = self, text = "")    ## this widget prevents the frame from resizing as the figure is resized
        image = Image.open(homedir + "/Assets/Capture_blank.png")   
        self.background.configure(image = ctk.CTkImage(image, size = (self.width + 50, self.height + 50)), 
                                  height = height, 
                                  width = width, 
                                  fg_color = "white", 
                                  hover = "white")
        self.background.grid(row = 0, column= 0, columnspan = 2)


        self.widget = ctk.CTkButton(master = self, text = "")
        image = Image.open(homedir + f"/Assets/{bug}") 
        self.widget.configure(image = ctk.CTkImage(image, size = (self.height, self.width)), 
                              height = height, 
                              width = width, 
                              fg_color = "white", 
                              hover = "white")
        self.widget.grid(row = 0, column= 0, columnspan = 2)

        self.toolbar = ctk.CTkLabel(master = self, text = "placeholder so the .destroy() method doesn't throw an error the first time")
        
    def update_figure(self, figure) -> None:
        '''
        '''
        self.widget.destroy()
        self.toolbar.destroy()

        self.figure = figure

        self.canvas = FigureCanvasTkAgg(self.figure, master = self)
        self.canvas.draw()
        self.widget = self.canvas.get_tk_widget()
        self.widget.grid(row = 0, column = 0)
        self.widget.configure(height = self.height, width = self.width)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self, pack_toolbar = False)
        self.toolbar.grid(row = 1, column = 0)

    def update_image(self, image: Union[str, ctk.CTkImage]) -> None:
        '''
        '''
        self.figure = None
        self.widget.destroy()
        self.toolbar.destroy()
        if isinstance(image, str):
            image = Image.open(image)
            image = ctk.CTkImage(image, size = (self.width + 50, self.height + 50))

        self.widget = ctk.CTkButton(master = self, text = "")
        self.widget.configure(image = image, height = self.height + 50, width = self.width + 50, fg_color = "white", hover = "white")
        self.widget.grid(row = 0, column = 0)

        self.toolbar = ctk.CTkLabel(master = self, text = "placeholder so the .destroy() method doesn't throw an error")


class scatterplot_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, master):
        super().__init__(master)
        self.title("Scatterplot Options")
        self.master = master
        label = ctk.CTkLabel(self, text = "Scatterplot options:")
        label.grid(column = 0,row = 0, padx = 5, pady = 5)

        label_1 = ctk.CTkLabel(self, text = "Antigen X:")
        label_1.grid(column = 0, row = 2)

        self.antigen1 = ctk.CTkOptionMenu(master = self, values = list(self.master.cat_exp.data.var['antigen'].unique()))
        self.antigen1.grid(column= 1, row = 2, padx = 5, pady = 5)

        def refresh_scatter_antigen1(enter = ""):
            self.antigen1.configure(values = list(self.master.cat_exp.data.var['antigen'].unique()))

        self.antigen1.bind("<Enter>", refresh_scatter_antigen1)

        label_2 = ctk.CTkLabel(self, text = "Antigen Y:")
        label_2.grid(column = 0, row = 3)

        self.antigen2 = ctk.CTkOptionMenu(master = self, values = list(self.master.cat_exp.data.var['antigen'].unique()))
        self.antigen2.grid(column= 1, row = 3, padx = 5, pady = 5)

        def refresh_scatter_antigen2(enter = ""):
            self.antigen2.configure(values = list(self.master.cat_exp.data.var['antigen'].unique()))

        self.antigen2.bind("<Enter>", refresh_scatter_antigen2)

        label_3 = ctk.CTkLabel(self, text = "Color points by:")
        label_3.grid(column = 0, row = 4)

        color_list = ["None", "Density", ] + COLNAMES
        color_list_obs = [i for i in CLUSTER_NAMES if i in list(self.master.cat_exp.data.obs.columns.unique())]
        color_list_antigens = list(self.master.cat_exp.data.var['antigen'].unique())
        color_list = color_list + color_list_obs + color_list_antigens

        self.hue = ctk.CTkOptionMenu(master = self, values = color_list)
        self.hue.grid(column= 1, row = 4, padx = 5, pady = 5)

        def refresh_scatter_hue(enter = ""):
            color_list = ["None", "Density", ] + COLNAMES
            color_list_obs = [i for i in CLUSTER_NAMES if i in list(self.master.cat_exp.data.obs.columns.unique())]
            color_list_antigens = list(self.master.cat_exp.data.var['antigen'].unique())
            color_list = color_list + color_list_obs + color_list_antigens
            self.hue.configure(values = color_list)

        self.hue.bind("<Enter>", refresh_scatter_hue)

        label_4 = ctk.CTkLabel(self, text = "Point Size: \n (automatically determined if not a number)")
        label_4.grid(column = 0, row = 5)

        self.size = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "auto"))
        self.size.grid(column= 1, row = 5, padx = 5, pady = 5)

        label_5 = ctk.CTkLabel(self, text = "Transparency (alpha):")
        label_5.grid(column = 0, row = 6)

        self.alpha = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "0.5"))
        self.alpha.grid(column= 1, row = 6, padx = 5, pady = 5)

        label_7 = ctk.CTkLabel(self, text = "Filename:")
        label_7.grid(column = 0, row = 7)

        self.filename = ctk.CTkEntry(self, textvariable = ctk.StringVar(value ="scatter"))
        self.filename.grid(column = 1, row = 7, padx = 5, pady = 5)

        button_plot = ctk.CTkButton(self, text = "Plot", command = lambda: self.plot_scatter(antigen1 = self.antigen1.get(), 
                                                                                             antigen2 = self.antigen2.get(),
                                                                                             hue = self.hue.get(),
                                                                                             size = self.size.get(),
                                                                                             alpha = self.alpha.get(),
                                                                                             filename = self.filename.get().strip()))
        button_plot.grid(column = 0, row = 10, padx = 5, pady = 5)

        self.pop_up = ctk.CTkCheckBox(master = self, text = "Make detailed Plot Editing Pop-up?", onvalue = True, offvalue = False)
        self.pop_up.grid(column = 0, row = 11, padx = 3, pady = 3)

        self.after(200, lambda: self.focus())

    def plot_scatter(self, 
                    antigen1: str, 
                    antigen2: str, 
                    hue = None, 
                    size: str = "1", 
                    alpha: str = "0.5", 
                    filename: str = "Scatter_plot") -> None:
        '''  '''
        try:
            alpha = float(alpha)
        except Exception:
            tk.messagebox.showwarning("Warning!", 
                message = "Alpha must be numerical! Cancelling plot!")
            self.focus()
            return
        try:
            size = float(size)
        except Exception:
            size = None
        if filename_checker(filename, self):
            return
        if not overwrite_approval(f"{self.master.cat_exp.save_dir}/{filename}.png", file_or_folder = "file", GUI_object = self):
            return
        if hue == "None":
            hue = None
        figure = self.master.cat_exp.plot_scatter(antigen1, 
                                                 antigen2, 
                                                 hue = hue, 
                                                 size = size, 
                                                 alpha = alpha, 
                                                 filename = filename)
        self.master.save_and_display(filename = filename, sizeX = 550, sizeY = 550)
        if self.pop_up.get() is True:
            Plot_window_display(figure)
            self.withdraw()
        else:
            self.destroy()

class classy_masker_window(ctk.CTkToplevel, metaclass = CtkSingletonWindow):

    def __init__(self, master):
        super().__init__(master)
        self.title("Classy masks from clustering")
        self.master = master
        label = ctk.CTkLabel(self, text = "Classy masks from clustering:")
        label.grid(column = 0,row = 0, padx = 5, pady = 5)

        label_1 = ctk.CTkLabel(self, text = "Clustering")
        label_1.grid(column = 0, row = 2)

        self.clustering = ctk.CTkOptionMenu(master = self, 
                                            values = [""] + [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns])
        self.clustering.grid(column= 1, row = 2, padx = 5, pady = 5)

        def refresher1(enter = ""):
            self.clustering.configure(values = [""] + [i for i in CLUSTER_NAMES if i in self.master.cat_exp.data.obs.columns])
        self.clustering.bind("<Enter>", refresher1)

        label_5 = ctk.CTkLabel(self, text = "Identifier:")
        label_5.grid(column = 0, row = 3)

        self.identifier = ctk.CTkEntry(master = self, textvariable = ctk.StringVar(value = "1"))
        self.identifier.grid(column= 1, row = 3, padx = 5, pady = 5)

        button_plot = ctk.CTkButton(self, text = "Create", command = lambda: self.classy_mask(clustering = self.clustering.get(),
                                                                                            identifier = self.identifier.get()))
        button_plot.grid(column = 0, row = 4, padx = 5, pady = 5)
        self.after(200, lambda: self.focus())

    def classy_mask(self, clustering = "merging", identifier = "") -> None:
        '''  '''
        self.master.cat_exp.export_clustering_classy_masks(clustering = clustering, identifier = identifier)
        self.destroy()