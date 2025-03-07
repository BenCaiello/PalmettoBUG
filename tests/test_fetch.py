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
        test_analysis = Analysis()
        test_analysis.load_data(dir + "/main", load_regionprops = False)
        assert(len(test_analysis.data) == 31162), "The fetched CyTOF is not the expected length"

def test_IMC_fetch():
    with tmp.TemporaryDirectory() as dir:
        fetch_IMC_example(dir)
        assert(len(os.listdir(dir + "/raw")) == 10), "The fetched IMC does not have the expected number of image files in /raw!"
        assert("panel.csv" in os.listdir(dir)), "The fetched IMC did not get its panel file!"


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
