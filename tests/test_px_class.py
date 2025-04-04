import sys
import os

homedir = __file__.replace("\\","/")
homedir = homedir[:(homedir.rfind("/"))]
homedir = homedir[:(homedir.rfind("/"))]

### homedir = /path/to/project/palmettobug   -- as in, the folder name passed to sys.path.append is always 'palmettobug'
sys.path.append(homedir)

from palmettobug import fetch_IMC_example
import tifffile as tf
import numpy as np
import tempfile as tmp

proj_directory = homedir + "/px_class_test/"
os.mkdir(proj_directory)

def test_fetch_IMC():
    fetch_IMC_example(fetch_dir)

def test_raw_to_img():
    global image_proc
    image_proc = ImageAnalysis(proj_directory, from_mcds = True)
    image_proc.directory_object.makedirs()
    image_proc.raw_to_img(0.85)
    images = [f"{proj_directory}/images/img/{i}" for i in os.listdir(proj_directory + "/images/img")]
    assert(len(images) == 10), "Wrong number of images exported to images/img"               ## all the images are transferred
    shutil.rmtree(proj_directory + "/raw") ## don't need raw anymore

def test_unsupervised_classifier():
    pass 

def test_direct_seg():
    pass 

def test_slice_by_class():
    pass 

def test_whole_class_analysis():
    pass 

def test_classy_mask_mode():
    pass 

def test_classy_mask_flowsom():
    pass

def test_extend_masks():
    pass

def test_maps_to_PNGs():
    pass