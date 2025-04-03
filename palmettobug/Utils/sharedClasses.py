'''
This module contains classes that can be used by multiple other modules in the program. Such as: logging classes, directory setup class, and 
table entry / display classes.
It does also contains the table widget/launch class for the public PalmettoBUG non-GUI API, as a separate class from the table widget/launch
classes used in the GUI itself.


While the PalmettoBUG project as a whole is licensed under GPL3 -- some of the code listed below is derivative of GPL comaptible licenses 
    
    (marked inside each class / function)

singletons package:
    
    https://github.com/jmaroeder/python-singletons/blob/master/src/singletons/singleton.py  (Copyright (c) 2019, James Roeder, MIT License)

Directory structures (but not code) derived from:
steinbock package: https://github.com/BodenmillerGroup/steinbock (MIT license), and the
CATALYST package (R): https://github.com/HelenaLC/CATALYST  (GPL>=2)

'''

import tkinter as tk
import os
from pathlib import Path
import logging
from typing import Union
import re
import threading
from multiprocessing import Process

import numpy as np
import pandas as pd
import tifffile as tf
import customtkinter as ctk
from PIL import Image
import napari

from .._vendor import fcsparser

__all__ = ["run_napari", "TableLaunch_nonGUI"]

homedir = __file__.replace("\\","/")
homedir = homedir[:(homedir.rfind("/"))]
## twice to get back to toplevel directory of the package
homedir = homedir[:(homedir.rfind("/"))]


def filename_checker(filename: str, GUI_object = None, regex: str = "[a-zA-Z0-9-_]") -> bool: 
    '''
    Checks if a filename is composed of allowable characters. Returns True (which aborts GUI process) if a character not in regex is in filename
    Otherwise returns False, which allows the GUI process to continue.

    Consider reversing the True / False return -- would make more intuitive sense (would require editing GUI code)
    '''
    if filename == "":  ## in the context of the GUI this means a user tried to save with an empty filename field
        tk.messagebox.showwarning("Warning!", message = "Filename field should not be empty!")
        if GUI_object is not None:
            GUI_object.focus()
        return True  
    for i in re.split(regex, filename):  
        if len(i) != 0:                ### this means a special character / a character not in the regex was in the filename
            tk.messagebox.showwarning("Warning!", message = "An unsupported special character was in your filename! \n" 
                           "Please only use letters, numbers, underscores, or dashes in your filename and try again.")
            if GUI_object is not None:
                GUI_object.focus()
            return True   
    return False  

def folder_checker(foldername: str, GUI_object = None, regex: str = "[a-zA-Z0-9-_]") -> bool:
    '''
    This function is like filename_checker() above, but for foldernames
    '''
    foldername = foldername.strip()
    if foldername == "":
        tk.messagebox.showwarning("Warning!", message = "You must specify a folder name!")
        if GUI_object is not None:
            GUI_object.focus()
        return True   
    for i in re.split(regex, foldername):    
        if len(i) != 0:                     
            tk.messagebox.showwarning("Warning!", message = "An unsupported special character was in your foldername! \n"
                            "Please only use letters, numbers, underscores, or dashes and try again.")
            if GUI_object is not None:
                GUI_object.focus()
            return True 
    return False 

def overwrite_approval(full_path: str, file_or_folder: str = "file", custom_message: str = None, GUI_object = None) -> bool:
    '''
    This function checks if a folder / file exists so that a user-warning & choice that be created before overwriting it.

    Args:
        full_path (string or Path): the file path of the folder / file you are about to write a new folder / file to. Will check if this 
            folder / file already exists, and if it does will prompt the user whether to proceed with overwriting or cancel.

        file_or_folder (string): either "file" or "folder". Customizes the tk.messagebox message.

        custom_message (string or None): if not None, will be used to customize the question asked of the user by the message box

        GUI_object (ctk.CTkToplevel, or None): tk message boxes defocus the current window (at least for customtkinter Toplevel windows) --
            supply the window in this argument to automatically re-focus on that window after the tk messagebox prompt. 

    Specify the GUI_object, if this is called inside a CTkToplevel window and you want that window to be focused after the tkinter
    message box pop-up. 
    '''
    full_path = str(full_path)
    if os.path.exists(full_path):
        file_or_folder = str(file_or_folder)
        has_files = True
        if file_or_folder == "folder":
            has_files = (len(os.listdir(full_path)) > 0)
        overwrite_message = str(custom_message)
        if custom_message is None:
            if file_or_folder == "file":
                overwrite_message = "Are you sure you want to overwrite the existing file?"
            if file_or_folder == "folder":
                overwrite_message = "Are you sure you want to potentially overwrite files in this folder?"
        if has_files:
            response = tk.messagebox.askyesno(title = "Overwrite Warning!", message = f"The {file_or_folder} path: \n\n {full_path} \n\n already exists! {overwrite_message}")
            if GUI_object is not None:
                GUI_object.focus()
            if response:
                return True
            else:
                return False
        else:
            return True
    else:
        return True   ### if the path does not exist, does not contain files (and is a folder), or if the user says "yes", proceed with the step

## These imports, etc. also from singleton package (Copyright (c) 2019, James Roeder, MIT License):
## edit 3-28-25 to shift noqa statements for ruff 
from collections import defaultdict # noqa: E402
from typing import Any, ClassVar, MutableMapping, Type, TypeVar # noqa: E402
T = TypeVar("T")

class CtkSingletonWindow(type):
    ############### This class edited from the singleton package: 
    #       https://github.com/jmaroeder/python-singletons/blob/master/src/singletons/singleton.py   
    # (originally the singleton.Singleton class)
    #### Edits needed because of the desire to focus a singleton window when it was "opened" again (accomplished with a ctk call in the 
    #       singleton class)
    ############### Singleton package copyright / license: Copyright (c) 2019, James Roeder, MIT License
    """
    Thread-safe singleton metaclass.

    Ensures that one instance is created.

    Note that if the process is forked before any instances have been accessed, then all processes
    will actually each have their own instances. You may be able to avoid this by instantiating the
    instance before forking.

    Usage::

        >>> class Foo(metaclass=Singleton):
        ...     pass
        >>> a = Foo()
        >>> b = Foo()
        >>> assert a is b

    """
    __instances: ClassVar[MutableMapping[Type, Any]] = {}
    __locks: ClassVar[MutableMapping[Type, threading.Lock]] = defaultdict(threading.Lock)

    def __call__(cls: Type[T], *args: Any, **kwargs: Any) -> T:  # noqa: D102
        if cls not in CtkSingletonWindow.__instances:
            with CtkSingletonWindow.__locks[cls]:
                if cls not in CtkSingletonWindow.__instances:  # pragma: no branch
                    # double checked locking pattern
                    CtkSingletonWindow.__instances[cls] = super().__call__(*args, **kwargs) 
                    CtkSingletonWindow.__instances[cls].geometry("+10+10")
                    return CtkSingletonWindow.__instances[cls]  
        else:
            try: 
                if CtkSingletonWindow.__instances[cls].state() == "withdrawn":
                    CtkSingletonWindow.__instances[cls].destroy()
                    CtkSingletonWindow.__instances[cls] = super().__call__(*args, **kwargs) 
                    CtkSingletonWindow.__instances[cls].geometry("+0+0")
                    CtkSingletonWindow.__instances[cls].after(200, CtkSingletonWindow.__instances[cls].focus())
                    return CtkSingletonWindow.__instances[cls] 

                else:
                    CtkSingletonWindow.__instances[cls].focus()   ## This focuses the window
                    ## This will throw an error if the window has been closed ("tkinter.TclError: bad window path name"), 
                    #       so if an error occurs in focusing --> just open a new window:
            
            except Exception:
                CtkSingletonWindow.__instances[cls] = super().__call__(*args, **kwargs) 
                CtkSingletonWindow.__instances[cls].geometry("+0+0")
                CtkSingletonWindow.__instances[cls].after(200, CtkSingletonWindow.__instances[cls].focus())
                return CtkSingletonWindow.__instances[cls] 

class LogSemiSingleton(type):
    ############### This class edited from the singleton package: 
    #      https://github.com/jmaroeder/python-singletons/blob/master/src/singletons/singleton.py   
    # (originally the singleton.Singleton class)
    #### Edits needed because of the desire to have the option to undo & produce another "singleton" (when [re]loading a new experiment). 
    # Hence, it is only a "semi"-singleton. This will make the project log initialized at the entry point carry over to all future project 
    # logs (until a new directory is provided to the project log, when a new singleton can be made)
    ############### Singleton package copyright / license: Copyright (c) 2019, James Roeder, MIT License
    """
    Thread-safe singleton metaclass.

    Ensures that one instance is created.

    Note that if the process is forked before any instances have been accessed, then all processes
    will actually each have their own instances. You may be able to avoid this by instantiating the
    instance before forking.

    Usage::

        >>> class Foo(metaclass=Singleton):
        ...     pass
        >>> a = Foo()
        >>> b = Foo()
        >>> assert a is b

    """
    __instances: ClassVar[MutableMapping[Type, Any]] = {}
    __locks: ClassVar[MutableMapping[Type, threading.Lock]] = defaultdict(threading.Lock)

    def __call__(cls: Type[T], proj_dir = None) -> T:  # noqa: D102
        #### Note: throws an error if proj_dir = None (default) when the Project logger is first called (does not throw an error 
        #       if proj_dir = None after the first call with a directory, as it loads the existing logger)
        if (cls not in LogSemiSingleton.__instances) and (proj_dir is not None):
            with LogSemiSingleton.__locks[cls]:
                if cls not in LogSemiSingleton.__instances:  # pragma: no branch
                    # double checked locking pattern
                    LogSemiSingleton.__instances[cls] = super().__call__(proj_dir) 
                    return LogSemiSingleton.__instances[cls]
        elif (LogSemiSingleton.__instances[cls].proj_dir == proj_dir) or (proj_dir is None):    ### if same directory or None is passed into the 
                                                                                # Project_log class -- just return the existing LogSemiSingleton
            return LogSemiSingleton.__instances[cls]
        elif proj_dir is not None:                                               # if a different directory -- initialize a new project logger 
                                                                                    # with the new directory, unless proj_dir is None
            LogSemiSingleton.__instances[cls] = super().__call__(proj_dir)
            return LogSemiSingleton.__instances[cls] 
        else:
            raise ValueError("no instance of Project Logger exists, and no directory was provided!")     
                                                                                                            
class Singleton(type):
    ############### This class copied (not edited) from the singleton package: 
    #       https://github.com/jmaroeder/python-singletons/blob/master/src/singletons/singleton.py   
    # (originally the singleton.Singleton class)
    #### Retained here separate from the singleton package simply because it reduces the number of imports required & because I've already 
    # copied from the package twice above this
    ###### Singleton package copyright / license: Copyright (c) 2019, James Roeder, MIT License
    """
    Thread-safe singleton metaclass.

    Ensures that one instance is created.

    Note that if the process is forked before any instances have been accessed, then all processes
    will actually each have their own instances. You may be able to avoid this by instantiating the
    instance before forking.

    Usage::

        >>> class Foo(metaclass=Singleton):
        ...     pass
        >>> a = Foo()
        >>> b = Foo()
        >>> assert a is b

    """

    __instances: ClassVar[MutableMapping[Type, Any]] = {}
    __locks: ClassVar[MutableMapping[Type, threading.Lock]] = defaultdict(threading.Lock)

    def __call__(cls: Type[T], *args: Any, **kwargs: Any) -> T:  # noqa: D102
        if cls not in Singleton.__instances:
            with Singleton.__locks[cls]:
                if cls not in Singleton.__instances:  # pragma: no branch
                    # double checked locking pattern
                    Singleton.__instances[cls] = super().__call__(*args, **kwargs) 
        return Singleton.__instances[cls] 

class Project_logger(metaclass = LogSemiSingleton):
    '''
    Because of its metaclass, this class will:
        --> Initialize a logger in the directory provided by the entrypoint that writes inside that directory
        --> If a Project logger already exists in the session, calling this function will not create a new logger unless the directory 
            provided is different
    '''
    def __init__(self, proj_dir = None):
        if proj_dir is not None:
            self.proj_dir = proj_dir
            self.log = logging.getLogger("Project_Log")
            for i in self.log.handlers:
                self.log.removeHandler(i)
            if not os.path.exists(f"{proj_dir}/Logs"):
                os.mkdir(f"{proj_dir}/Logs")
            log_a_log_handler = logging.FileHandler(f"{proj_dir}/Logs/Project.log")
            log_a_format = logging.Formatter("%(name)s: %(asctime)s: %(message)s")
            log_a_log_handler.setFormatter(log_a_format)
            self.log.setLevel(logging.INFO)
            self.log.addHandler(log_a_log_handler)

    def return_log(self) -> logging.Logger:
        return self.log

class Analysis_logger(metaclass = LogSemiSingleton):
    '''
    Because of its metaclass, this class will:
        --> Initialize a logger in the directory provided that writes inside that directory
        --> If a Analysis logger already exists in the session, calling this function will not create a new logger unless the directory 
            provided is different
    '''
    def __init__(self, proj_dir: Union[str, None] = None):
        if proj_dir is not None:
            self.proj_dir = proj_dir
            self.log = logging.getLogger("Analysis_Log")
            for i in self.log.handlers:
                self.log.removeHandler(i)
                i.close()    # helpful for fixing a logging problem I encountered (top answer / Martijn Pieters' answer): https://stackoverflow.com/questions/15435652/python-does-not-release-filehandles-to-logfile
            if not os.path.exists(f"{proj_dir}/Logs"):
                os.mkdir(f"{proj_dir}/Logs")
            log_a_log_handler = logging.FileHandler(f"{proj_dir}/Logs/Analysis.log")
            log_a_format = logging.Formatter("%(name)s: %(asctime)s: %(message)s") 
            log_a_log_handler.setFormatter(log_a_format)
            self.log.setLevel(logging.INFO)
            self.log.addHandler(log_a_log_handler)

    def return_log(self) -> logging.Logger:
        return self.log

def warning_window(warning_to_show: str, title: str = "Warning!") -> None:
    '''
    This just displays a warning window in the GUI, with text corresonding to the string passed into the function (the "warning_to_show").
    '''
    sub_window = ctk.CTkToplevel()
    sub_window.title(title)
    sub_label = ctk.CTkLabel(master = sub_window, text = warning_to_show)
    sub_label.grid(padx = 25, pady = 25)
    sub_window.after(200, lambda: sub_window.focus())
        
## The following class sets up & saves the directory structure of a steinbock-style experiment
## Originally written to setup the structure used by the steinbock package: 
#           https://github.com/BodenmillerGroup/steinbock (MIT license), 
# and the directory used by the CATALYST package (R):
#            https://github.com/HelenaLC/CATALYST  (GPL>=2)
## but this has been substantially changed and extended since then
## Still, some of the directory naming conventions or overall structure [with or without renaming] from the underlying packages 
# have been carried through
class DirSetup:
    def __init__(self, directory: str, kind: Union[None, str] = None):
        self.main = directory
        if kind == "Analysis":
            self.analysis_dir = self.main
            self.kind = "Analysis"
            self.Analyses_dir = directory[:directory.rfind("/")]
        else:
            self.kind = None
            self.raw_dir = directory + '/raw'
            self.img_dir = directory + '/images'
            self.masks_dir = directory + '/masks'
            self.classy_masks_dir = directory + '/classy_masks'
            self.px_classifiers_dir = directory + '/Pixel_Classification'
            self.Analyses_dir = directory + '/Analyses'
            self.logs = directory + '/Logs'

    def makedirs(self) -> None:
        if not os.path.exists(self.raw_dir):
            os.mkdir(self.raw_dir)
        if not os.path.exists(self.img_dir):
            os.mkdir(self.img_dir)
        if not os.path.exists(self.masks_dir):
            os.mkdir(self.masks_dir)
        if not os.path.exists(self.classy_masks_dir):
            os.mkdir(self.classy_masks_dir)
        if not os.path.exists(self.Analyses_dir):
            os.mkdir(self.Analyses_dir) 
        if not os.path.exists(self.logs):
            os.mkdir(self.logs)

    def make_analysis_dirs(self, analysis_name: str) -> None:
        # This new structure sequesters the intensities / regionprops & all analysis related folders 
        # (formerly labeled "CATALYST" folders / files) into a separate subfolder
        if self.kind is None:
            self.analysis_dir = self.Analyses_dir + f"/{analysis_name}"
        self.regionprops_dir = self.analysis_dir + '/regionprops'
        self.intensities_dir = self.analysis_dir + '/intensities'
        self.Analysis_internal_dir = self.analysis_dir + '/main'
        self.fcs_dir = self.Analysis_internal_dir + '/Analysis_fcs'
        self.saved_clusterings = self.Analysis_internal_dir + '/clusterings'

        if not os.path.exists(self.analysis_dir):
            os.mkdir(self.analysis_dir)
        if not os.path.exists(self.regionprops_dir):
            os.mkdir(self.regionprops_dir)
        if not os.path.exists(self.intensities_dir):
            os.mkdir(self.intensities_dir)
        if not os.path.exists(self.Analysis_internal_dir):
            os.mkdir(self.Analysis_internal_dir)
        if not os.path.exists(self.fcs_dir):
            os.mkdir(self.fcs_dir)
        if not os.path.exists(self.saved_clusterings):
            os.mkdir(self.saved_clusterings)

'''
from valkka.multiprocess import MessageProcess
class NapariProcessClass(MessageProcess):
    def __init__(self):
        super().__init__()


    def run_napari(self, image_name: np.ndarray[Union[int, float]], 
            channel_axis: Union[None, int] = None,
            ) -> None:
        #This function launches napari with the provided image & mask. The mask is shown as a layer over the image.
        image = tf.imread(image_name)
        if image.dtype != 'int':
            masks = None
        elif image.dtype == 'int':
            masks = image.copy()
            image = np.zeros(masks.shape)
        if channel_axis is not None:
            viewer, layer = napari.imshow(image, channel_axis = channel_axis)
        else:
            viewer, layer = napari.imshow(image)    
        if masks is not None:
            viewer.add_labels(masks, name = "layer")
        napari.run()
'''


def run_napari(image: np.ndarray[Union[int, float]], 
            masks: Union[None, np.ndarray[int]] = None, 
            channel_axis: Union[None, int] = None,
            ) -> None:
    '''
    This function launches napari with the provided image & mask. The mask is shown as a layer over the image.
    '''
    if channel_axis is not None:
        viewer, layer = napari.imshow(image, channel_axis = channel_axis)
    else:
        viewer, layer = napari.imshow(image)    
    if masks is not None:
        viewer.add_labels(masks, name = "layer")
    napari.run()

class display_image_button(ctk.CTkButton):
    def __init__(self, master, initial_image, PalmettoBUG_homedir: str = homedir, X = 550, Y = 550):
        super().__init__(master)
        self.master = master
        self.X = X
        self.Y = Y
        image = Image.open(initial_image)   ####  PalmettoBUG_homedir + "/Assets/Capture2.png"
        self.configure(text = "", image = ctk.CTkImage(image, size = (X,Y)), height = X, width = Y, fg_color = "white", hover = "white")

    def save_and_display(self, image: str) -> None:
        ##### This piece of code is currently repeated many times across each plotting function. Should probably be its own function...
        if isinstance(image, str):
            image = Image.open(image)
        sizeX = image.size[0]
        sizeY = image.size[1]
        ratio = image.size[0] / image.size[1]
        if sizeX > sizeY:
            sizeX = self.X
            sizeY = (self.Y / ratio)
        else:
            sizeX = (self.X*ratio)  
            sizeY = self.Y            
        image = ctk.CTkImage(image, size = (sizeX,sizeY))
        self.configure(image = image)

class DirectoryDisplay(ctk.CTkFrame):
    """
    This widget class is for displaying the directory structure of the project.
    """
    def __init__(self, master, deleter: bool = False, napari_multiprocess_backend = None):
        super().__init__(master)
        self.master = master
        self.napari_launch = napari_multiprocess_backend

        self.Placeholder = ctk.CTkLabel(master = self, text = "Directory Display")
        self.Placeholder.grid()
        self.deleter = deleter
        self.experiment = None
        self.png = None
        self.currentdir = None

    def setup_with_dir(self, directory: str, experiment = None, png = None, delete_remove: bool = False) -> None:
        '''This function allows the separation of the placement of the widget from the setup of the widget with a directory inside'''
        self.Placeholder.destroy()
        self.experiment = experiment
        self.configure(width = 450)
        self.png = png
        self.directories = DirSetup(directory)
        self.currentdir = directory
        self.option_menu = ctk.CTkButton(master = self, 
                                        text = self.currentdir)
        self.option_menu.grid(column = 0, row = 0, padx = 1, pady = 3)
        self.option_menu.configure(state = 'disabled', text_color_disabled = self.option_menu.cget("text_color"))
        self.button_list = []
        self.list_dir()
        if delete_remove is False:
            self.delete_button = ctk.CTkButton(master = self, text = "Enter Delete Mode", command  = self.switch_deleter)
            self.delete_button.grid(column = 0, row = 2, padx = 1, pady = 3)

    def switch_deleter(self) -> None:
        '''Switch in and out of a mode where clicking on a FILE will delete it --> 
        folder deletion is not allowed (will still just change directories)
        '''
        if self.deleter is False:
            self.deleter = True
            self.setup_with_dir(self.directories.main, self.experiment, self.png)   #### setup the widget again, but update deleter attribute
            self.delete_button = ctk.CTkButton(master = self, text = "Exit Delete Mode", command  = self.switch_deleter)
            self.delete_button.grid(column = 0, row = 2)
        elif self.deleter is True:
            self.deleter = False
            self.setup_with_dir(self.directories.main, self.experiment, self.png)   #### setup the widget again, but update deleter attribute
            self.delete_button = ctk.CTkButton(master = self, text = "Enter Delete Mode", command  = self.switch_deleter)
            self.delete_button.grid(column = 0, row = 2)

    class varButton(ctk.CTkButton):
        '''
        a button that can return its own value to the parent object and change directories, etc.
        '''
        def __init__(self, master, textvariable, height, width, fg_color, hover_color, folder_file, parent):
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
            elif self.type == "fdkjhgkjfdhgkdjghkdglskjlgkdlj":   ## intended to be a default that a user is unlikely to accidently use...
                                                                        # spaghetti code .... spaghetti code ...
                self.configure(command = lambda: self.folder_click(self.parent, "fdkjhgkjfdhgkdjghkdglskjlgkdlj"))  

        def file_click(self, parent, value: str) -> None:
            parent.out = value
            filepath = parent.currentdir + "/" + parent.out
            identifier = parent.out[(parent.out.rfind(".")):]
            file_name = parent.out[:(parent.out.rfind("."))]
            if self.parent.deleter is True:
                os.remove(filepath)
                self.destroy()
                try:
                    Project_logger().return_log().info(f"{filepath} deleted!")
                except Exception:
                    pass
            elif identifier == ".csv":
                if (parent.currentdir == parent.directories.main) & (file_name != "spatialtable"): ## TODO: fix to match current labeling
                    TableLaunch(1, 1, parent.currentdir, None, (parent.out), parent.experiment)
                else:
                    dataframe_head = pd.read_csv(filepath).head(25)
                    TableLaunch(1, 1, parent.currentdir, dataframe_head, f"First 25 entries of {file_name}{identifier}", parent.experiment)
            elif identifier == ".tiff":
                image = tf.imread(filepath)
                if image.dtype != 'int':
                    if parent.napari_launch is not None:
                        parent.napari_launch.run_napari(filepath)
                    else:
                        p = Process(target = run_napari, args = (image, None))
                        p.start()
                elif image.dtype == 'int':
                    if parent.napari_launch is not None:
                        parent.napari_launch.run_napari(filepath)
                    else:
                        p = Process(target = run_napari, args = (np.zeros(image.shape), image))
                        p.start()         
            # if ending in .fcs, convert to DataFrame and display (no metadata?)
            elif identifier == ".fcs":
                fcs_df_head = pd.DataFrame(fcsparser.parse(filepath)).head(25)
                TableLaunch(1, 1, parent.currentdir, fcs_df_head, f"First 25 entries of {file_name}{identifier}", parent.experiment)
            elif identifier == ".png":
                if parent.png is not None:
                    parent.png.update_image(filepath)
            elif identifier == ".txt":
                text_window(self, filepath)

        def folder_click(self, parent, value: str) -> None:
            parent.change_dir(value)

    def list_dir(self) -> None:
        container = ctk.CTkScrollableFrame(master = self)
        for i in self.button_list:
            i.destroy()
        self.button_list = []
        a = 1
        if self.currentdir != self.directories.main:
            button = self.varButton(master = container, 
                                    textvariable = ctk.StringVar(value = "Go up one folder"), 
                                    height = 20, 
                                    width = 350, 
                                    fg_color = "blue", 
                                    hover_color = "blue", 
                                    folder_file = "fdkjhgkjfdhgkdjghkdglskjlgkdlj", 
                                    parent = self)
            button.configure_cmd()
            button.grid(column = 0, row = 1, pady = 5, sticky = "ew")
            self.button_list.append(button)
            a = 2
        for i,ii in enumerate(os.scandir(self.currentdir)):
            if ii.is_dir() is True:
                button = self.varButton(master = container, 
                                        textvariable = ctk.StringVar(value = ii.name), 
                                        height = 20, 
                                        width = 350, 
                                        fg_color = "transparent", 
                                        hover_color= "blue", 
                                        folder_file = "folder", 
                                        parent = self)
                button.configure_cmd()
                button.grid(column = 0, row = i+a, pady = 5, sticky = "ew")
                self.button_list.append(button)
            else:
                button = self.varButton(master = container, 
                                        textvariable = ctk.StringVar(value = ii.name), 
                                        height = 20, 
                                        width = 350, 
                                        fg_color = "transparent", 
                                        hover_color= "blue", 
                                        folder_file = "file", 
                                        parent = self)
                button.configure_cmd()
                button.grid(column = 0, row = i+a, pady = 5, sticky = "ew")
                self.button_list.append(button)

        container.grid(column=0,row=1, padx = 3, pady = 1)
        container.configure(width = 350)
        
    def change_dir(self, new_dir: str, option_menu: bool = False) -> None:
        if new_dir == "fdkjhgkjfdhgkdjghkdglskjlgkdlj":
            to_dir = self.currentdir[:self.currentdir.rfind("/")]
        elif option_menu is True:
            to_dir = self.directories.main + f"/{new_dir}"
        else:
            to_dir = self.currentdir + f"/{new_dir}"
        self.currentdir = to_dir
        self.option_menu.configure(text = self.currentdir[self.currentdir.rfind("/")+1:])
        self.list_dir()

## This class launches TableWidget instances in a new window, and automatically updates / saves the .csv file when closed.
class TableLaunch(ctk.CTkToplevel, metaclass = CtkSingletonWindow):
    def __init__(self, width: int, 
                 height: int, 
                 directory: str, 
                 dataframe: pd.DataFrame,
                table_type: str, 
                experiment, 
                favor_table: bool = False, 
                logger: Union[None, logging.Logger] = None):
        ''' '''
        super().__init__()
        self.title('Table Examination')
        self.directory = directory
        self.logger = logger
        if logger is None:
            try:
                self.logger = Project_logger().return_log()
            except Exception:
                self.logger = None
        if table_type != "other":
            label1 = ctk.CTkLabel(self, text = f"Values of the {table_type} file")
        else:
            clip = directory.rfind('/')
            if clip == -1:
                clip = 0
            label1 = ctk.CTkLabel(self, text = f"Values of the {directory[clip:]} file")
        label1.grid(column = 0, row = 0, padx = 5, pady = 5, sticky = "ew")
        label1.configure(anchor = 'w')
        self.tablewidget = TableWidget(self)
        self.tablewidget.setup_data_table(directory, dataframe, table_type[:-4], favor_table = favor_table)
        self.tablewidget.setup_width_height(width, height, scale_width_height = True)

        self.tablewidget.grid(column = 0, row = 1, padx = 5, pady = 5)
        self.column = 1
        self.tablewidget.populate_table()
        self.table_list = [self.tablewidget]
        if (table_type != "other"):
            self.accept_button = ctk.CTkButton(master = self, 
                                    text = "Accept Choices and Return", 
                                    command = lambda: self.accept_and_return(experiment))
            self.accept_button.grid(column = 0, row = 2, pady = 15)

        if table_type.find("Regionprops_panel") != -1:
            self.leiden_check = ctk.CTkCheckBox(master = self, 
                    text = "Check to run Leiden Clustering \n from centroids (spatial neighborhoods)", 
                    onvalue = True, 
                    offvalue = False)
            self.leiden_check.grid(column = 1, row = 2, pady = 15)
        
        self.after(200, lambda: self.focus())

    def add_table(self, width: int, 
                  height: int, 
                  directory: str, 
                  dataframe: pd.DataFrame,
                  table_type: str, 
                  favor_table: bool = False) -> None:
        '''
        '''
        if table_type != "other":
            label1 = ctk.CTkLabel(self, text = f"Values of the {table_type} file")
        else:
            clip = directory.rfind('/')
            if clip == -1:
                clip = 0
            label1 = ctk.CTkLabel(self, text = f"Values of the {directory[clip:]} file")
        label1.grid(column = self.column, row = 0, padx = 5, pady = 5, sticky = "ew")
        label1.configure(anchor = 'w')
        self.tablewidget = TableWidget(self)
        self.tablewidget.setup_data_table(directory, dataframe, table_type, favor_table = favor_table)
        self.tablewidget.setup_width_height(width, height, scale_width_height = True)

        self.tablewidget.grid(column = self.column, row = 1, padx = 5, pady = 5)
        self.tablewidget.populate_table()
        self.table_list.append(self.tablewidget)
        self.column += 1

    def accept_and_return(self, experiment) -> None:
        for i in self.table_list:
            i.recover_input()
            if i.type == "panel":
                if experiment is not None:
                    experiment.panel = i.table_dataframe
                self.panel_write(i.table_dataframe)
            if i.type == "Analysis_panel":
                if experiment is not None:
                    experiment.Analysis_panel = i.table_dataframe
                self.Analysis_panel_write(i.table_dataframe)
            if i.type == "Regionprops_panel":
                self.regionprops_write(i.table_dataframe)
                experiment.append_regionprops()
            if i.type == "metadata":
                if experiment is not None:
                    experiment.metadata = i.table_dataframe
                self.metadata_write(i.table_dataframe)
        self.destroy()

    def panel_write(self, table: pd.DataFrame, alt_directory: Union[str, None] = None) -> None:
        if alt_directory is not None:
            directory = alt_directory
        else:
            directory = self.directory
        try:
            table.to_csv(directory + '/panel.csv', index = False)
        except Exception:
            warning_window("Could not write panel file! \n" 
                           "Do you have the .csv open right now in excel or another program?")
        else:
            if self.logger is not None:
                self.logger.info(f"Wrote panel file, with values: \n {str(table)}")

    def Analysis_panel_write(self, table: pd.DataFrame, alt_directory: Union[str, None] = None) -> None:
        if alt_directory is not None:
            directory = alt_directory
        else:
            directory = self.directory
        try:
            table.to_csv(directory + '/Analysis_panel.csv', index = False)

        except Exception:
            warning_window("Could not write Analysis_panel file! \n" 
                           "Do you have the .csv open right now in excel or another program?")
        else:            
            if self.logger is not None:
                self.logger.info(f"Wrote Analysis_panel file, with values: \n {str(table)}")

    def regionprops_write(self, table: pd.DataFrame, alt_directory: Union[str, None] = None) -> None:
        if alt_directory is not None:
            directory = alt_directory
        else:
            directory = self.directory
        try:
            table.to_csv(directory + '/Regionprops_panel.csv', index = False)
            
        except Exception:
            warning_window("Could not write regionprops panel file! \n" 
                           "Do you have the .csv open right now in excel or another program?")    
        else:
            if self.logger is not None:
                self.logger.info(f"Wrote regionprops panel file, with values: \n {str(table)}")

    def metadata_write(self, table: pd.DataFrame, alt_directory: Union[str, None] = None) -> None:
        if alt_directory is not None:
            directory = alt_directory
        else:
            directory = self.directory
        try:
            table.to_csv(directory + '/metadata.csv', index = False)
        except Exception:
            warning_window("Could not write metdata file! \n" 
                           "Do you have the .csv open right now in excel or another program?")   
        else:
            if self.logger is not None:
                self.logger.info(f"Wrote metadata file, with values: \n {str(table)}")

## This is a core class for representing, interacting, and editing .csv / panel / metadata files
class TableWidget(ctk.CTkScrollableFrame):
    '''
    '''
    def __init__(self, master):
        '''
        Initialize this class with six values (now split between the two setup functions beneath __init__):
        1. master -- the CTk window you want to embed the table in
        2. width -- the width of the table widget, scaled by the number of columns / rows in the dataframe
        3. height -- the height of the table widget, scaled by the number of columns / rows in the dataframe 
        4. directory -- the directory where the file is to be written (directory_class.main + "/" + table_type + ".csv")
        5. dataframe -- the pandas dataframe containing the values of the table
        6. table_type -- whether the table is the "panel", "Analysis_panel", or "metadata" file -- this class will treat each of those 
                        slightly differently
        '''
        super().__init__(master)
        self.widgetframe = pd.DataFrame()

    def setup_data_table(self, directory: str, dataframe: pd.DataFrame, table_type: str, favor_table: bool = False) -> None:
        ## decouple data loading from setup (to allow widgets to be displayed before directory is loaded in by user)
        self.type = table_type
        self.Analysis_internal_dir = directory
        if favor_table is False:
            try:
                self.directory = "".join([directory, "/", table_type, ".csv"])
                self.table_dataframe = pd.read_csv(directory + f'/{table_type}.csv', dtype = str)
                self.table_dataframe = self.table_dataframe.astype("str")
            except FileNotFoundError:
                self.table_dataframe = dataframe
                if dataframe is None:
                    tk.messagebox.showwarning("Warning!", 
                                message = f"No dataframe provided, and no existing {table_type} file is in the directory!")
                    return
                else:
                    self.table_dataframe = self.table_dataframe.astype("str")

        elif favor_table is True:
            if dataframe is None:
                try:
                    self.directory = "".join([directory, "/", table_type, ".csv"])
                    self.table_dataframe = pd.read_csv(directory + f'/{table_type}.csv', dtype = str)
                    self.table_dataframe = self.table_dataframe.astype("str")
                except FileNotFoundError:
                    tk.messagebox.showwarning("Warning!", 
                            message = f"No dataframe provided, and no existing {table_type} file is in the directory!")
                    return

            else:
                self.table_dataframe = dataframe
                self.table_dataframe = self.table_dataframe.astype("str")
    
    def setup_width_height(self, width: int, height: int, scale_width_height: bool = False) -> None:
        ### Decouple the widget placement from its size determination
        ### Also decoupled from loading the data so as to allow two differnet orders of construction:
        #       1.) place widget and manually set width / height (scale_width_height = False) without the table data pre-loaded into the widget
        #       2.) place the widget, load the data, then setup the width / height automatically, scaled by the number of columns&rows 
        #           (scale_width_height = True). Scaling will not work without the data loaded, the number of columns/rows is not known
        self.configure(width = width, height = height)
        if scale_width_height is True:     # In this case, a value for height / width should be ~1, and the overall size of the table 
                                            # will determined by the number of columns / rows multiplied by constants defined below & 
                                            # the height/width passed into the constructor:
            if height*(len(self.table_dataframe.index)*35) > 700:  ## cap out the height so the situation of a too long scrollable frame 
                                                                   # with a non-functional scroll bar does not occur (as frequently)
                self.configure(width = width*(len(self.table_dataframe.columns)*175), height = 700)
            else:
                self.configure(width = width*(len(self.table_dataframe.columns)*175), height = height*(len(self.table_dataframe.index)*35))


    def label_column(self, col_num: int, offset: int = 0, add_row_optionns: bool = False) -> None:
        '''
        Creates a column of plain labels inside the scrollable table, of the col_num specified (zero-indexed). 
        Offset shifts the column location to the right within the scrollable frame (offset of 1 needed for tables 
        that display the index as well).
        '''
        class varLabel(ctk.CTkLabel):
            def __init__(self, master, text, real_text):
                super().__init__(master, text = text)
                self.real_text = real_text

        column_list = []
        col1_title = ctk.CTkLabel(master = self, text = self.table_dataframe.columns[col_num])
        col1_title.grid(column = col_num + offset, row = 0, padx = 5, pady = 3)

        for i,ii in enumerate(self.table_dataframe.iloc[:,col_num]):
            if len(ii) > 25:
                col1_label = varLabel(master = self, text = ii[:15] + "..." + ii.strip(".fcs")[-6:], real_text = ii)   
                                # only display fewer characters to prevent overflow in widgets
            else:
                col1_label = varLabel(master = self, text = ii, real_text = ii) 
            col1_label.grid(column = col_num + offset, row = i + 1, padx = 5, pady = 3)
            col1_label.configure(width = 25)
            column_list.append(col1_label)
        self.widgetframe[str(col_num)] = column_list
        if add_row_optionns is True:
            self.add_row_button = ctk.CTkButton(self, text = 'Add a Row to this file', command = lambda: self.add_row((col_num + offset)))
            self.add_row_button.grid(column = col_num + offset, row = i + 2, padx = 5, pady = 3)

    def drop_down_column(self, col_num: int, values: list[str] = [], offset: int = 0, state: str = 'normal') -> None:
        '''
        Creates a column of drop menus inside the scrollable table, of the col_num specified (zero-indexed). 
        Values = a list of the values to be in the drop menu of the comboBoxes
        Offset shifts the column location to the right within the scrollable frame (offset of 1 needed for tables 
        that display the index as well).
        '''
        column_list = []
        if (self.type == "panel") and (col_num == 2):
            col1_title = ctk.CTkButton(master = self, 
                                       text = self.table_dataframe.columns[col_num], 
                                       command = lambda: self.toggle_keep_column(self.keep_state, warning = True))
            col1_title.grid(column = col_num + offset, row = 0, padx = 5, pady = 3)
        else:
            col1_title = ctk.CTkLabel(master = self, text = self.table_dataframe.columns[col_num])
            col1_title.grid(column = col_num + offset, row = 0, padx = 5, pady = 3)
        for i,ii in enumerate(self.table_dataframe.iloc[:,col_num]):
            variable = ctk.StringVar(value = str(ii))
            ## only want the segmentation colum to treated special:
            if (self.type == "panel") and (col_num == 3):
                if str(ii) == "1.0":
                    variable = ctk.StringVar(value = "Nuclei")
                elif str(ii) == "2.0":
                    variable = ctk.StringVar(value = "Cytoplasmic / Membrane")
            col_dropdown = ctk.CTkOptionMenu(master = self, variable = variable, values = values)
            col_dropdown.grid(column = col_num + offset, row = i + 1, padx = 5, pady = 3)
            col_dropdown.configure(state = state)
            column_list.append(col_dropdown)
        self.widgetframe[str(col_num)] = column_list

        self.select_all = ctk.CTkOptionMenu(master = self, 
                                    variable = ctk.StringVar(value = "Set All in Column"), 
                                    values = values, 
                                    command = lambda selection: self.selector(selection = selection, 
                                                                            column = self.widgetframe[str(col_num)]))
        self.select_all.grid(column = col_num + offset, row = i + 2, padx = 5, pady = 3)

    def selector(self, selection: str, column) -> None:
        for i in column:
            i.set(selection)

    def toggle_keep_column(self, state: str, warning: bool = False) -> None:
        col_num = 2
        if state == 'normal':
            for ii,i in enumerate(self.widgetframe.iloc[:,col_num]):
                i.configure(state = 'disabled')
            self.keep_state = 'disabled'
        else:
            for i in self.widgetframe.iloc[:,col_num]:
                i.configure(state = 'normal')
            self.keep_state = 'normal'
            if warning is True:
                warning_window("Caution! Editing the Keep column should NEVER be done after converting .mcd's --> .tiff's, \n" 
                               "unless you are intending on immediately repeating the mcd --> tiff conversion step after the edits!")

    def entry_column(self, col_num: int, offset: int = 0) -> None:
        '''
        Creates a column of plain labels inside the scrollable table, of the col_num specified (zero-indexed). 
        Values = a list of the vlaues to be in the drop menu of the comboboxes
        Offset shifts the column location to the right within the scrollable frame (offset of 1 needed for tables that
        display the index as well).
        '''
        column_list = []
        col1_title = ctk.CTkLabel(master = self, text = self.table_dataframe.columns[col_num])
        col1_title.grid(column = col_num + offset, row = 0, padx = 3, pady = 3)
        for i,ii in enumerate(self.table_dataframe.iloc[:,col_num]):
            variable = ctk.StringVar(value = str(ii))
            col_dropdown = ctk.CTkEntry(master = self, textvariable = variable)
            col_dropdown.grid(column = col_num + offset, row = i + 1, padx = 3, pady = 3)
            column_list.append(col_dropdown)
        self.widgetframe[str(col_num)] = column_list

    class delete_varButton(ctk.CTkButton):
            def __init__ (self, master, text, argument):
                super().__init__(master = master, text = text)
                self.master = master
                self.configure(command = lambda: self.master.delete_row(argument))

    def delete_column(self, col_num: int, offset: int = 0, state: str = "disabled") -> None:
        '''
        a rows of buttons, that -- if activated -- clicking on will delete the selected row from the file. 
        '''
        self.delete_state = state
        column_list = []
        col1_title = ctk.CTkButton(master = self, text = "Toggle Delete", command = lambda: self.toggle_delete_column(self.delete_state))
        col1_title.grid(column = col_num + offset, row = 0, padx = 3, pady = 3)
        for i,ii in enumerate(self.table_dataframe.index):
            col_dropdown = self.delete_varButton(master = self, text = "delete row", argument = i )
            col_dropdown.configure(state = state)
            col_dropdown.grid(column = col_num + offset, row = i + 1)
            column_list.append(col_dropdown)
        self.widgetframe[str(col_num)] = column_list

    def toggle_delete_column(self, state: str) -> None:
        col_num = self.widgetframe.columns[-1]
        if state == 'normal':
            for ii,i in enumerate(self.widgetframe.loc[:,col_num]):
                i.configure(state = 'disabled')
            self.delete_state = 'disabled'
        else:
            for i in self.widgetframe.loc[:,col_num]:
                i.configure(state = 'normal')
            self.delete_state = 'normal'
            
    def delete_row(self, row_number: int) -> None:
        '''
        '''
        for i in self.widgetframe.loc[row_number,:]:
            try:
                i.destroy()
            except Exception:
                pass
        self.widgetframe = self.widgetframe[self.widgetframe.index != row_number]

    def populate_table(self) -> None:
        '''  
        '''
        if self.type == "metadata":
            checks = True
            try:
                fcs_files  = sorted(os.listdir(self.Analysis_internal_dir + "/Analysis_fcs"))
            except FileNotFoundError:
                try:
                    fcs_files  = sorted(os.listdir(self.Analysis_internal_dir + "/main/Analysis_fcs"))
                except FileNotFoundError:
                    warning_window("Could not read fcs folder to perform checks of metadata file")
                    checks = False
                if checks is True:
                    if len(self.table_dataframe.index) > len(fcs_files):
                        warning_window("The loaded metadata file has more rows than fcs files in the folder! \n"
                                       "Will edit the metadata to only keep files that exist in the folder!")
                        truth_array = np.zeros(len(self.table_dataframe.index))
                        for i in fcs_files:
                            one_truth =  np.array(self.table_dataframe['file_name'] == i)
                            truth_array = truth_array + one_truth
                        truth_array = truth_array.astype('bool')
                        self.table_dataframe = self.table_dataframe[truth_array]

                    elif len(self.table_dataframe.index) < len(fcs_files):
                        warning_window("The loaded metadata file has fewer rows than the fcs files in the folder!"
                                       "If this is not intentional (such as with dropped files), be sure to add the missing rows!")
        try:
            for j in self.widgetframe.iloc[:,2]:
                del j
        except Exception:
            pass
        # for special table types, special widgets are made:
        if self.type == "panel":
            self.table_dataframe['keep'] = self.table_dataframe['keep'].astype('int')
            index_list = []
            for i,ii in enumerate(self.table_dataframe.index):
                index_label = ctk.CTkLabel(master = self, text = ii)
                index_label.grid(column = 0, row = i + 1)
                index_list.append(index_label)
            self.widgetframe['index'] = index_list
            self.label_column(0, offset = 1)
            self.entry_column(1, offset = 1)
            self.drop_down_column(2, values = ["0","1"], offset = 1, state = "disabled")
            self.drop_down_column(3,values = ["", "Nuclei", "Cytoplasmic / Membrane"], offset = 1)
            self.offset = 1
        elif (self.type == "Analysis_panel") or (self.type == "Regionprops_panel"):
            self.label_column(0, add_row_optionns = True)
            self.entry_column(1)
            self.drop_down_column(2, values = ["none", "type", "state"])
            self.delete_column(3)
            self.offset = 0
        elif self.type == "metadata":
            self.label_column(0, add_row_optionns = True)
            self.label_column(1)
            self.entry_column(2)
            self.entry_column(3)
            self.delete_column(4)
            self.offset = 0

        ## other wise, just show the values in the dataframe:
        else:
            for i,ii in enumerate(self.table_dataframe.index):
                index_label = ctk.CTkLabel(master = self, text = ii)
                index_label.grid(column = 0, row = i + 1)
            for i,ii in enumerate(self.table_dataframe.columns):
                self.label_column(i, offset = 1)
                self.offset = 1
        self.widgetframe = self.widgetframe.dropna(axis = 1)

    def add_row(self, column_of_button) -> None:
        row_list = []
        if len(self.widgetframe) == 0:
            row_number = 0
        else:
            row_number = self.widgetframe.index[-1]
        
        for i,ii in enumerate(self.widgetframe.columns):
            if i != (len(self.widgetframe.columns) - 1): 
                empty_entry = ctk.CTkEntry(self, textvariable = ctk.StringVar(value = ""))
                empty_entry.grid(column = i, row = row_number + 2, padx = 5, pady = 3)
                row_list.append(empty_entry)
            else:
                deleter = self.delete_varButton(master = self, text = "delete row", argument = row_number + 1)
                deleter.configure(state = self.delete_state)
                deleter.grid(column = i, row = row_number + 2, padx = 5, pady = 3)
                row_list.append(deleter)
        row_df = pd.DataFrame(row_list).T
        row_df.columns = self.widgetframe.columns
        row_df.index = [row_number + 1]
        self.widgetframe = pd.concat([self.widgetframe, row_df], axis = 0, ignore_index = False)
        self.add_row_button.grid(column = column_of_button, row = row_number + 3, padx = 5, pady = 3)

    def recover_input(self) -> None:
        '''
        This method recovers the user entered data from the GUI into the self.table_dataframe dataframe, and writes the recovered data to 
        a .csv file.
        '''          
        new_table_dataframe = pd.DataFrame()
        try:
            self.widgetframe = self.widgetframe.drop('index', axis = 1)
        except KeyError:
            pass
        for i,ii in zip(self.widgetframe.columns, self.table_dataframe.iloc[:,:(len(self.widgetframe.columns))]):
            column_of_interest = self.widgetframe[i]
            retrieval_list = []
            for i in column_of_interest:
                try:
                    out = i.get()
                except Exception:
                    out = i.real_text
                out = out.strip()
                retrieval_list.append(out)
            new_table_dataframe[ii] = retrieval_list
            if (self.type == "panel") and (ii == 3):
                new_table_dataframe[ii] = new_table_dataframe[ii].replace({"Nuclei":1,"Cytoplasmic / Membrane":2})
        self.table_dataframe = new_table_dataframe

class text_window(ctk.CTkToplevel):
    def __init__(self, master,  filepath: str):
        super().__init__(master)
        self.master = master
        self.title("Text Window")
        text_frame = ctk.CTkTextbox(master = self) 
        text_frame.configure(width = 800, height = 500, wrap = 'none')
        text_frame.grid()

        with open(filepath, encoding = "utf-8") as file:
            text_to_display = file.read()

        text_frame.insert(0.0, text_to_display)
        text_frame.configure(state = "disabled")
        self.after(200, lambda: self.focus())
 

class DirSetup_nonGUI:
    '''
    This class is a helper for organizing & creating the directories of both the image processing and the Analysis portions of PalmettoBUG.

    Initialize with a directory, if initializing for an Analysis only, then be sure to pass:  kind = "Analysis". 

    Its two main methods, self.makedirs() and self.make_analysis_dirs(analysis_name) create the directories in the style of the 
    PalmettoBUG GUI where files will be read / exported from. 
    '''
    def __init__(self, 
                directory: Union[Path, str], 
                kind: Union[None, str] = None,
                ) -> None:
        '''
        If kind = None, then pass in a directory for image processing / a whole project, if kind = "Analysis" then pass in the directory 
        for an Analysis only
        '''
        directory = str(directory)
        self.main = directory
        if kind == "Analysis":
            self.analysis_dir = self.main
            self.kind = "Analysis"
            self.Analyses_dir = directory[:directory.rfind("/")]
        else:
            self.kind = None
            self.raw_dir = directory + '/raw'
            self.img_dir = directory + '/images'
            self.masks_dir = directory + '/masks'
            self.classy_masks_dir = directory + '/classy_masks'
            self.px_classifiers_dir = directory + '/Pixel_classification'
            self.Analyses_dir = directory + '/Analyses'

    def makedirs(self) -> None:
        '''Create the directories for an image / entire project (the self.Analyses_dir is meant to contain Analysis subdirectories)'''
        if not os.path.exists(self.raw_dir):
            os.mkdir(self.raw_dir)
        if not os.path.exists(self.img_dir):
            os.mkdir(self.img_dir)
        if not os.path.exists(self.masks_dir):
            os.mkdir(self.masks_dir)
        if not os.path.exists(self.classy_masks_dir):
            os.mkdir(self.classy_masks_dir)
        if not os.path.exists(self.Analyses_dir):
            os.mkdir(self.Analyses_dir) 

    def make_analysis_dirs(self, analysis_name: str) -> None:
        '''Make the directories for an Analysis -- can be called alone, or inside the /Analyses folder of an imaging-based project'''
        if self.kind is None:
            self.analysis_dir = self.Analyses_dir + f"/{analysis_name}"

        self.regionprops_dir = self.analysis_dir + '/regionprops'
        self.intensities_dir = self.analysis_dir + '/intensities'
        self.Analysis_internal_dir = self.analysis_dir + '/main'
        self.fcs_dir = self.Analysis_internal_dir + '/Analysis_fcs'
        self.saved_clusterings = self.Analysis_internal_dir + '/clusterings'

        if not os.path.exists(self.analysis_dir):
            os.mkdir(self.analysis_dir)
        if not os.path.exists(self.regionprops_dir):
            os.mkdir(self.regionprops_dir)
        if not os.path.exists(self.intensities_dir):
            os.mkdir(self.intensities_dir)
        if not os.path.exists(self.Analysis_internal_dir):
            os.mkdir(self.Analysis_internal_dir)
        if not os.path.exists(self.fcs_dir):
            os.mkdir(self.fcs_dir)
        if not os.path.exists(self.saved_clusterings):
            os.mkdir(self.saved_clusterings)

class TableLaunch_nonGUI(ctk.CTk):
    '''
    This class launches a customtkinter GUI window, in order to display the contents of a table. 
    It can make setting up the panel/metadata/Analysis_panel files easier / faster, instead of manually setting values in python or 
    requiring the user to go to a second program (like excel) to enter values.
    '''
    def __init__(self, 
                dataframe: Union[str, Path, pd.DataFrame], 
                export_path: Union[str, Path],
                table_type: str = "other", 
                labels_editable: bool = True,  
                width: int = 1, 
                height: int = 1,
                ) -> None:
        '''
        Args:
            dataframe (Path, string, or pandas dataframe): 
                either the dataframe, or the path to a .csv file, which will be displayed in the window

            export_path (Path or string): 
                the path to where you want to write the dataframe when the "Accept and Return" Button is pressed & the window closes. Remeber to include the .csv file extension!

            table_type (str): 
                The type of the table being passed in. Helps determine the format of the display, one of ['panel','metadata','Analysis_panel','Regionprops_panel','other']. 
                'other' is the default, and will display all entries in the dataframe as either uneditable labels or as entry fields that 
                allow any kind of text editing depending on whether labels_editable is False or True. 

                The specific table types, like 'metadata', etc. expect a particular format for the dataframe. For example, selecting a 
                table_type of 'panel' means 4 data columns will be generated >> the first two are label/entry columns, the next column of 
                drop-down option widgets with 0 / 1 as the choices and the last column of data will be a drop down with options of 
                "Nuclei" and "Cytoplasmic / Membrane". This is to replicate the expectation of the panel file, but theoretically you could 
                use 'other' for all table types and simply use the entry fields to have full control of the final table. 
                Note that if you use 'other' instead of 'panel' in the example above, you should enter numbers for nuclei (1) and cytoplasmic (2) 
                segmentation channels, NOT the strings "Nuclei" or "Cytoplasmic / Membrane", as the table_type == "panel" also auto-converts
                between the human-friendly strings and the computer friendly integers (1 or 2). 

            labels_editable (bool): 
                whether fields are displayed as CTklabels (uneditable, if False) or CTkEntry (editable, if True) when those fields are otherwise specified by the table_type. 

            width / height (both ints): 
                determine the shape & size of the window/table when launched. This operates by an estimation of the needed table height/width to accommodate the widgets
                multiplied by height/width. (Default = 1 for both means the initial estimate is also the final shape)

        Input / Output:
            Input: 
                if dataframe is a file path, not a pandas dataframe, wil attempt to read a csv at that filepath
            Output: 
                when the accept button is pressed, will attempt to write the dataframe set up in the GUI to export_path as a csv file. 
        '''
        super().__init__()
        self.title('Table Examination')
        label1 = ctk.CTkLabel(self, text = f"Values of the {table_type} file")
        label1.grid(column = 0, row = 0, padx = 5, pady = 5, sticky = "ew")
        label1.configure(anchor = 'w')
        self.tablewidget = TableWidget_nonGUI(self)
        self.tablewidget.setup_data_table(dataframe, table_type = table_type, 
                                        export_directory = export_path, labels_editable = labels_editable, width = width, height = height)
        self.tablewidget.grid(column = 0, row = 1, padx = 5, pady = 5)
        self.column = 1
        self.tablewidget.populate_table()
        self.table_list = [self.tablewidget]

        self.accept_button = ctk.CTkButton(master = self, text = "Accept Choices and Return", command = lambda: self.accept_and_return())
        self.accept_button.grid(column = 0, row = 2, pady = 15)
        self.after(200, lambda: self.focus())

    def accept_and_return(self) -> None:
        for i in self.table_list:
            i.recover_input()
            i.table_dataframe.to_csv(i.export_dir, index = False)
        self.destroy()


## This is a core class for representing, interacting, and editing .csv / panel / metadata files, for the nonGUI / scripting API
class TableWidget_nonGUI(ctk.CTkScrollableFrame):
    ''' This class is for displaying and saving a dataframe  / csv file, subordinate to a TableLaunch instance '''
    def __init__(self, master):
        ''' '''
        super().__init__(master)
        self.widgetframe = pd.DataFrame()

    def setup_data_table(self, 
                        dataframe: Union[str, Path, pd.DataFrame], 
                        export_directory: Union[str, Path], 
                        table_type: str = "other", 
                        labels_editable: bool = True, 
                        height = 1,
                        width = 1,
                        ) -> None:
        ''' Sets up the table widget -- see the documentation for TableLaunch to see details '''
        if not isinstance(dataframe, pd.DataFrame):
            dataframe = pd.read_csv(str(dataframe))

        self.table_dataframe = dataframe
        self.type = table_type
        self.export_dir = export_directory
        self.editable = labels_editable
        
        self.table_dataframe = self.table_dataframe.astype("str")

        if height*(len(self.table_dataframe.index)*35) > 700:  
            ## cap out the height so the situation of a too long scrollable frame with a non-functional scroll bar does not occur (as frequently)
            self.configure(width = width*(len(self.table_dataframe.columns)*175), height = 700)
        else:
            self.configure(width = width*(len(self.table_dataframe.columns)*175), height = height*(len(self.table_dataframe.index)*35))
    
    def label_column(self, 
                    col_num: int, 
                    offset: int = 0,
                    ) -> None:
        '''
        Creates a column of plain labels inside the scrollable table, of the col_num specified (zero-indexed). 
        Offset shifts the column location to the right within the scrollable frame (offset of 1 needed for tables 
        that display the index as well).
        '''
        class varLabel(ctk.CTkLabel):
            def __init__(self, master, text, real_text):
                super().__init__(master, text = text)
                self.real_text = real_text
            def get(self):
                return self.real_text

        column_list = []
        col1_title = ctk.CTkLabel(master = self, text = self.table_dataframe.columns[col_num])
        col1_title.grid(column = col_num + offset, row = 0, padx = 5, pady = 3)

        for i,ii in enumerate(self.table_dataframe.iloc[:,col_num]):
            if len(ii) > 25:
                col1_label = varLabel(master = self, text = ii[:15] + "..." + ii.strip(".fcs")[-6:], real_text = ii)   
                        # only display fewer characters to prevent overflow within the widget
            else:
                col1_label = varLabel(master = self, text = ii, real_text = ii) 
            col1_label.grid(column = col_num + offset, row = i + 1, padx = 5, pady = 3)
            col1_label.configure(width = 25)
            column_list.append(col1_label)
        self.widgetframe[str(col_num)] = column_list

    def drop_down_column(self, 
                        col_num: int, 
                        values: list[str] = [], 
                        offset: int = 0, 
                        state: str = 'normal',
                        ) -> None:
        '''
        Creates a column of drop menus inside the scrollable table, of the col_num specified (zero-indexed). 
        Values = a list of the values to be in the drop menu of the comboboxes
        Offset shifts the column location to the right within the scrollable frame (offset of 1 needed for tables 
        that display the index as well).
        At the bottom, there will be a dropdown that allow you to select the value for the entire column at once
        '''
        column_list = []
        col1_title = ctk.CTkLabel(master = self, text = self.table_dataframe.columns[col_num])
        col1_title.grid(column = col_num + offset, row = 0, padx = 5, pady = 3)
        for i,ii in enumerate(self.table_dataframe.iloc[:,col_num]):
            variable = ctk.StringVar(value = str(ii))
            ## only want the segmentation colum to treated special:
            if (self.type == "panel") and (col_num == 3):
                if str(ii) == "1.0":
                    variable = ctk.StringVar(value = "Nuclei")
                elif str(ii) == "2.0":
                    variable = ctk.StringVar(value = "Cytoplasmic / Membrane")
            col_dropdown = ctk.CTkOptionMenu(master = self, variable = variable, values = values)
            col_dropdown.grid(column = col_num + offset, row = i + 1, padx = 5, pady = 3)
            col_dropdown.configure(state = state)
            column_list.append(col_dropdown)
        self.widgetframe[str(col_num)] = column_list
        self.select_all = ctk.CTkOptionMenu(master = self,
                                            variable = ctk.StringVar(value = "Set All in Column"),
                                            values = values, 
                                            command = lambda selection: self._selector(selection = selection, 
                                                                                    column = self.widgetframe[str(col_num)]))
        self.select_all.grid(column = col_num + offset, row = i + 2, padx = 5, pady = 3)

    def _selector(self, 
                selection, 
                column,
                ) -> None:
        '''helper to set all values in a dropdown column'''
        for i in column:
            i.set(selection)

    def entry_column(self, 
                    col_num: int, 
                    offset: int = 0,
                    ) -> None:
        '''
        Creates a column of entry field scrollable table, of the col_num specified (zero-indexed). This allows completely flexible 
        editing of the values in the entry field.
        Values = a list of the vlaues to be in the drop menu of the comboboxes
        Offset shifts the column location to the right within the scrollable frame (offset of 1 needed for tables that display 
        the index as well).
        '''
        column_list = []
        col1_title = ctk.CTkLabel(master = self, text = self.table_dataframe.columns[col_num])
        col1_title.grid(column = col_num + offset, row = 0, padx = 3, pady = 3)
        for i,ii in enumerate(self.table_dataframe.iloc[:,col_num]):
            variable = ctk.StringVar(value = str(ii))
            col_dropdown = ctk.CTkEntry(master = self, textvariable = variable)
            col_dropdown.grid(column = col_num + offset, row = i + 1, padx = 3, pady = 3)
            column_list.append(col_dropdown)
        self.widgetframe[str(col_num)] = column_list

    class delete_varButton(ctk.CTkButton):
        ''' Helper class for the delete column '''
        def __init__ (self, 
                    master, 
                    text, 
                    argument):
            super().__init__(master = master, text = text)
            self.master = master
            self.configure(command = lambda: self.master._delete_row(argument))

    def delete_column(self, 
                    col_num: int, 
                    offset: int = 0, 
                    state: str = "disabled", 
                    add_row_optionns: bool = True,
                    ) -> None:
        '''
        a row of buttons, that -- if activated by clicking the button in the column title position -- will delete allow the deletion 
        of selected rows from the file. 
        Additionally, at the bottom of the delete column, there will always be a button that allows the addition of a new row to the bottom
        of the file.
            >> This row will be composed of blank entry fields to allow any values to typed into them
        '''
        self.delete_state = state
        column_list = []
        col1_title = ctk.CTkButton(master = self, text = "Toggle Delete", command = lambda: self.toggle_delete_column(self.delete_state))
        col1_title.grid(column = col_num + offset, row = 0, padx = 3, pady = 3)
        for i,ii in enumerate(self.table_dataframe.index):
            col_dropdown = self.delete_varButton(master = self, text = "delete row", argument = i )
            col_dropdown.configure(state = state)
            col_dropdown.grid(column = col_num + offset, row = i + 1)
            column_list.append(col_dropdown)
        self.widgetframe[str(col_num)] = column_list
        if add_row_optionns is True:
            self.add_row_button = ctk.CTkButton(self, text = 'Add a Row to this file', command = lambda: self.add_row((col_num + offset)))
            self.add_row_button.grid(column = col_num + offset, row = i + 2, padx = 5, pady = 3)

    def toggle_delete_column(self, state: str) -> None:
        '''Toggles whether the buttons in the delete column are active'''
        col_num = self.widgetframe.columns[-1]
        if state == 'normal':
            for ii,i in enumerate(self.widgetframe.loc[:,col_num]):
                i.configure(state = 'disabled')
            self.delete_state = 'disabled'
        else:
            for i in self.widgetframe.loc[:,col_num]:
                i.configure(state = 'normal')
            self.delete_state = 'normal'
            
    def _delete_row(self, row_number: int) -> None:
        '''Deletes the row of the button that called this function'''
        for i in self.widgetframe.loc[row_number,:]:
            try:
                i.destroy()
            except Exception:
                pass
        self.widgetframe = self.widgetframe[self.widgetframe.index != row_number]

    def populate_table(self) -> None:
        '''Populates the widgets for display using the table_type and the values in the dataframe '''
        if self.editable is True:
            column_func = self.entry_column
        else:
            column_func = self.label_column

        # for auto-keep method (delete keep column and repopulate)
        try:
            for j in self.widgetframe.iloc[:,2]:
                del j
        except Exception:
            pass
        # for panel file only, I include the python 0-indexed channel numbers (useful for napari identification)
        if self.type == "panel":
            self.table_dataframe['keep'] = self.table_dataframe['keep'].astype('int')
            index_list = []
            for i,ii in enumerate(self.table_dataframe.index):
                index_label = ctk.CTkLabel(master = self, text = ii)
                index_label.grid(column = 0, row = i + 1)
                index_list.append(index_label)
            self.widgetframe['index'] = index_list
            column_func(0, offset = 1)
            self.entry_column(1, offset = 1)
            self.drop_down_column(2, values = ["0","1"], offset = 1, state = "normal")
            self.drop_down_column(3,values = ["", "Nuclei", "Cytoplasmic / Membrane"], offset = 1)
            self.delete_column(4, offset  = 1)
            self.offset = 1
        elif (self.type == "Analysis_panel") or (self.type == "Regionprops_panel"):
            column_func(0)
            self.entry_column(1)
            self.drop_down_column(2, values = ["none", "type", "state"])
            self.delete_column(3)
            self.offset = 0
        elif self.type == "metadata":
            column_func(0)
            column_func(1)
            self.entry_column(2)
            self.entry_column(3)
            self.delete_column(4)
            self.offset = 0

        ## otherwise, just show the values in the dataframe:
        else:
            for i,ii in enumerate(self.table_dataframe.index):
                index_label = ctk.CTkLabel(master = self, text = ii)
                index_label.grid(column = 0, row = i + 1)
            for i,ii in enumerate(self.table_dataframe.columns):
                column_func(i, offset = 1)
                self.offset = 1
            self.delete_column(i + self.offset + 1)

        self.widgetframe = self.widgetframe.dropna(axis = 1)

    def add_row(self, column_of_button: int) -> None:
        '''Adds a row of blank entry fields to the tablewidget, in case an additional row is needed'''
        row_list = []
        if len(self.widgetframe) == 0:
            row_number = 0
        else:
            row_number = self.widgetframe.index[-1]
        for i,ii in enumerate(self.widgetframe.columns):
            if i != (len(self.widgetframe.columns) - 1): 
                empty_entry = ctk.CTkEntry(self, textvariable = ctk.StringVar(value = ""))
                empty_entry.grid(column = i, row = row_number + 2, padx = 5, pady = 3)
                row_list.append(empty_entry)
            else:
                deleter = self.delete_varButton(master = self, text = "delete row", argument = row_number + 1)
                deleter.configure(state = self.delete_state)
                deleter.grid(column = i, row = row_number + 2, padx = 5, pady = 3)
                row_list.append(deleter)

        row_df = pd.DataFrame(row_list).T
        row_df.columns = self.widgetframe.columns
        row_df.index = [row_number + 1]
        self.widgetframe = pd.concat([self.widgetframe, row_df], axis = 0, ignore_index = False)
        self.add_row_button.grid(column = column_of_button, row = row_number + 3, padx = 5, pady = 3)

    def recover_input(self) -> None:
        '''
        This method recovers the user entered data from the GUI into the self.table_dataframe dataframe, and writes the recovered 
        data to a .csv file.
        '''          
        new_table_dataframe = pd.DataFrame()
        try:
            self.widgetframe = self.widgetframe.drop('index', axis = 1)
        except KeyError:
            pass
        for i,ii in zip(self.widgetframe.columns, self.table_dataframe.iloc[:,:(len(self.widgetframe.columns))]):
            column_of_interest = self.widgetframe[i]
            retrieval_list = []
            for i in column_of_interest:
                try:
                    out = i.get()
                except Exception:
                    out = i.real_text
                out = out.strip()
                if (self.type == "panel") and ((ii == 3) or (ii == "segmentation")):
                    if out == "Nuclei":
                        out = 1
                    elif out == "Cytoplasmic / Membrane":
                        out = 2
                retrieval_list.append(out)
            new_table_dataframe[ii] = retrieval_list
        self.table_dataframe = new_table_dataframe