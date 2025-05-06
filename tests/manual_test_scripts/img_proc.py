import sys
import os
import shutil

homedir = __file__.replace("\\","/")
homedir = homedir[:(homedir.rfind("/"))]
homedir = homedir[:(homedir.rfind("/"))]

### homedir = /path/to/project/palmettobug   -- as in, the folder name passed to sys.path.append is always 'palmettobug'
sys.path.append(homedir)

import tifffile as tf
import numpy as np
import pandas as pd
# import pytest

from palmettobug import fetch_IMC_example, ImageAnalysis

fetch_dir = homedir + "/project_folder"
os.mkdir(fetch_dir)
proj_directory = fetch_dir + "/Example_IMC"

np.random.default_rng(42)

#fetch_IMC_example(proj_directory)
#img_processing = ImageAnalysis(proj_directory, from_mcds = False)
    
def fetch_IMC():
    fetch_IMC_example(fetch_dir)

def test_raw_to_img():
    img_processing = ImageAnalysis(proj_directory, from_mcds = True)
    img_processing.directory_object.makedirs()
    img_processing.raw_to_img(0.85)
    images = [f"{proj_directory}/images/img/{i}" for i in os.listdir(proj_directory + "/images/img")]
    assert(len(images) == 10), "Wrong number of images exported to images/img"               ## all the images are transferred
    shutil.rmtree(proj_directory + "/raw") ## don't need raw anymore
    return img_processing

def make_fake_masks():   ########### bundle real masks with data, as well (?)
    os.mkdir(proj_directory + "/masks/fake")
    for i in os.listdir(proj_directory + "/images/img"):
        image = tf.imread(proj_directory + "/images/img/" + i)
        fake_mask_array = np.random.rand(image.shape[1], image.shape[2])*1500     ## Goal: create roughly 2000 "masks" per images (unlike real masks, these will be discontinuous)
        fake_mask_array[fake_mask_array < 1] = 0
        fake_mask_array = fake_mask_array.astype('int32')
        tf.imwrite(proj_directory + "/masks/fake/" + i, fake_mask_array)

def test_regionprops_write(image_proc):
    image_proc.directory_object.make_analysis_dirs("test_analysis")
    input_img_folder = proj_directory + "/images/img"
    input_mask_folder = proj_directory + "/masks/fake"
    image_proc.make_segmentation_measurements(input_img_folder = input_img_folder, input_mask_folder = input_mask_folder)
    analysis_dir = image_proc.directory_object.Analyses_dir + "/test_analysis"
    intensities_dir = analysis_dir + "/intensities"
    assert(len(os.listdir(analysis_dir + "/regionprops")) == 10), "Wrong number of regionprops csv exported (expecting 10 to match the number of images)"
    assert(len(pd.read_csv(intensities_dir + "/" + os.listdir(intensities_dir)[0])) > 1400), "Randomnly generated masks should be roughly ~1500, but too low"
    assert(len(pd.read_csv(intensities_dir + "/" + os.listdir(intensities_dir)[0])) < 1600), "Randomnly generated masks should be roughly ~1500, ubt too high"

def test_setup_analysis(image_proc):
    panel_file, metadata, Analysis_panel_dir, metadata_dir = image_proc.to_analysis()
    panel_file.to_csv(Analysis_panel_dir)
    metadata.to_csv(metadata_dir)
    assert(os.listdir(image_proc.directory_object.Analysis_internal_dir + "/Analysis_fcs")[0].rfind(".fcs") != -1), "FCS files not in /main/Analysis_fcs!"
    assert(len(metadata) == 10), "Automatically generated Metadata file's length does not match the number of FCS files in the experiment!"
    assert("marker_class" in panel_file.columns), "Automatically generated Analysis_panel file should have a 'marker_class' column"
    assert("Analysis_panel.csv" in os.listdir(image_proc.directory_object.Analysis_internal_dir)), "Analysis_panel.csv not written to the proper place!"
    assert("metadata.csv" in os.listdir(image_proc.directory_object.Analysis_internal_dir)), "metadata.csv not written to the proper place!"
    assert("condition" in list(pd.read_csv(image_proc.directory_object.Analysis_internal_dir + "/metadata.csv").columns)), "Automatically generated metadata.csv file must have a 'condition' column!"

if __name__ == "__main__":
    failed_tests = []
    fetch_IMC()
    try:
        image_proc = test_raw_to_img()
    except AssertionError as e:
        print(f"Raw to Img failed with the following error: {e}")
        failed_tests.append("Raw to Img")
    make_fake_masks()
    try:
        test_regionprops_write(image_proc)
    except AssertionError as e:
        print(f"Regionproperty read failed with the following error: {e}")
        failed_tests.append("Regionproperty read")
    try:
        test_setup_analysis(image_proc)
    except AssertionError as e:
        print(f"to analysis / panel & metadata file generation failed with the following error: {e}")
        failed_tests.append("to analysis / panel & metadata file generation")

    if len(failed_tests) == 0:
        print("Passed all tests!")
    else:
        print(f"Failed the following tests: {str(', '.join(failed_tests))}")
