## Welcome to PalmettoBUG!


PalmettoBUG is a pure-python GUI in customtinker that, along with its sister package isoSegDenoise, can preprocess, segment, and analyze high-dimensional image or flow cytometry data,
especially mass cytometry / imaging mass cytometry data. The GUI is built mostly prominently on code from:

1. Steinbock (https://github.com/BodenmillerGroup/steinbock). PalmettoBUG has options for conversion of MCD files --> tiff files, hot pixel filtering, deepcell (Mesmer) segmentation, and mask expansion. PalmettoBUG also connects to cellpose (https://github.com/mouseland/cellpose) to offer denoising and cell segmentation options.

2. CATALYST (https://github.com/HelenaLC/CATALYST/). PalmettoBUG performs a python-translated version of CATALYST, with similar plot and a similar workflow: FlowSOM clustering followed by cluster merging. PalmettoBUG also offers additional plot types, especially for comparing metaclusters in order to assist in their merging to biologically relevant labels

3. spaceanova (https://github.com/sealx017/SpaceANOVA/tree/main). PalmettoBUG offers a simple spatial data analysis module based on a python version of the spaceanova package, with functional ANOVAs used to compare the pairwise Ripley's g statistic of celltypes in the sample between treatment conditions. This is based a precise python translation of Ripley's K statistic with isotropic edge correction from R's spatstat package (https://github.com/spatstat/spatstat), which was used in the original spaceanova package.

4. Additionally, PalmettoBUG offers pixel classification with ideas / code drawn from QuPath https://github.com/qupath/qupath supervised pixel classifiers and from the Ark-Analysis https://github.com/angelolab/ark-analysis unsupervised pixel classifier, Pixie. Pixel classification can then be used to segment cells, expand cell masks into non-circular shapes, classify cells into lineages for analysis, crop images to only areas of interest, or to perform simplistic analyes of pixel classification regions as-a-whole.

PalmettoBUG uses identical similar panel / metadata CSV files as Steinbock & CATALYST for the MCD/image processing and FCS analysis portions ofthe program

PalmettoBUG is intended to accomplish a few things:

1. Be an easy starting point for scientists who do not necessarily have extensive background in computer science / coding but still want to be able to do basic data analysis & exploration of imaging mass cytometry data on their own. In particular, the GUI interface, extensive powerpoint documentation, easy installation, and integration of all the usually necessary steps in high-dimensional biological image analysis helps make analyzing data in PalmettoBUG much more approachable. This is particularly the focus of why MUSC flow (& mass) cytometry shared resource wanted a package like this -- it could also users of our instruments to _begin_ their analyses and get a _preliminary_ idea of their data without needing a collaborating bioinformatician to analyze the data for them.  

2. Be easily integrated into new or alternative workflows. Specfically, PalmettoBUG was designed so that most of its critical image / data intermediates as easily accessible by the user or automatically exported as common files types (.tiff for images, .csv for statistics/data/metadata, and .png for graphs/plots in most cases). Similar to the Steinbock package on which much of PalmettoBUG was based, as steps are performed in the analysis, PalmettoBUG frequently auto-exports the output of those steps to folders on the users' hard drive. This means that PalmettoBUG could be easily used for only some of its functions -- say only using it to convert files to MCDs, then segment cells -- with its outputs being re-directed into a separate analysis pipeline. This promotes maximum flexibility with how PalmettoBUG could be used!

## Installation:

PalmettoBUG is still under development, however once published on pip, its installation (in a clean, **Python 3.10** environment!) should be as simple as running:

    > pip install palmettobug[tensorflow]

Deepcell / Mesmer was originally implemented in tensorflow. I converted that model (using the tf2onnx package) into an Onnx model, so that it can be run in pytorch.
This onnx version of the model has not be extensively tested, but from what I've seen is very similar -- BUT NOT IDENTICAL -- to the original mesmer model. The 
advantages of using the PyTorch model is that then tensorflow, keras, and associated packages are no longer needed (which saves a lot of downlaod) and GPU support is
much easier to install for Pytorch alone (Cellpose already uses Pytorch). To not install tensorflow, and use the PyTorch Mesmer model instead, use the installation command:

    > pip install palmettobug

Note that if you later install tensorflow, keras, etc. in this environment then palmettobug will use htat instead (if palmettobug finds tensorflow available for import, then it will prefer it to using PyTorch for Mesmer predictions).


Either of these commands also will install the sister package _isoSegDenoise_ in the same environment. That sister package is unique in that it is a fully independent, separate program for only the denoising / segmentation (separated to avoid licensing conflicts with GPL-3, as deepcell and cellpose models do or might have non-commercial-use clauses attached to them.). The two program should cooperate seamlessly, as the needed file structure and inputs/ouputs of isoSegDenoise precisely matches that of PalmettoBUG, and the two program share a good amount of code, giving them a similar appearance.

Then to launch PalmettoBUG, simply enter:

    > palmettobug

in the conda environment where the package was installed. 

## Documentation

Step-by-step documentation of what can be done in the GUI will be found in the **animated** powerpoint file inside PalmettoBUG itself / this github repo, or at readthedocs: __________________________________. Tutorial notebooks for using this package outside the GUI can be found in this repository or at the readthedocs website.

## Citation

If you use this work in your data analysis, software package, or paper -- a citation of this repository or its associated paper (TBD ____________) would be appreciated. 

