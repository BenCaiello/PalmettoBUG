import sys
import os

homedir = __file__.replace("\\","/")
homedir = homedir[:(homedir.rfind("/"))]
homedir = homedir[:(homedir.rfind("/"))]

### homedir = /path/to/project/palmettobug   -- as in, the folder name passed to sys.path.append is always 'palmettobug'
sys.path.append(homedir)

from palmettobug import fetch_CyTOF_example, fetch_IMC_example, Analysis
import tifffile as tf
import numpy as np
import tempfile as tmp

def test_CyTOF_fetch():
    with tmp.TemporaryDirectory() as dir:
        fetch_CyTOF_example(dir)
        new_dir = dir + "/Example_CyTOF"
        test_analysis = Analysis()
        test_analysis.load_data(new_dir + "/main", load_regionprops = False)
        assert(len(test_analysis.data) == 31162), "The fetched CyTOF is not the expected length"

def test_IMC_fetch():
    with tmp.TemporaryDirectory() as dir:
        fetch_IMC_example(dir)
        new_dir = dir + "/Example_IMC"
        assert(len(os.listdir(new_dir + "/raw")) == 3), "The fetched IMC does not have the expected number of MCD files in /raw!"
        assert("panel.csv" in os.listdir(new_dir)), "The fetched IMC did not get its panel file!"


if __name__ == "__main__":
    tests = [test_CyTOF_fetch, test_IMC_fetch]
    test_names = ["test_CyTOF_fetch", "test_IMC_fetch"]
    test_fail = []
    for i,ii in zip(tests, test_names):
        try:
            i()
            print(f"{ii} passed!")
        except AssertionError as e:
            print(f"{ii} failed with the following error: {e}")
            test_fail.append(ii)
    if len(test_fail) == 0:
        print("Passed all tests!")
    else:
        print(f"Failed the following tests: {str(', '.join(test_fail))}")
