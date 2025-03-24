## Warning! This package is still under development!

Final development plans:

    1). Documentation: 
        - re-run notebooks (update, check differences from original, be sure of consistency on fresh installation!)
        - Update images and descriptions with new features / missing features
            -- Premessa translation --> have a page for (would require fresh example data?)
            -- scatterplot option
            -- clustering --> classy mask, and classy mask / pixel class --> PNG options
            -- Added parameters to existing functions (is_torch, rlen, etc.)
        - update GPU section (if needing changes)
        - Edit images & screenshots to reduce / use open-source alternatives to windows explorer / excel
        - update text, incorporate proofreading edits

    2). Excessive warnings: address (if possible, or if genuine errors are occuring) or perhaps silence

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

Its installation (in a clean, **Python 3.10** environment!) should be as simple as running:

    > pip install palmettobug

Deepcell / Mesmer was originally implemented in tensorflow. I converted that model (using the tf2onnx package) into an Onnx model, so that it can be run in pytorch.
This onnx version of the model has not be extensively tested, and I know that it is not perfectly identical to the original mesmer model. The 
advantages of using the PyTorch model is that then tensorflow, keras, and associated packages are no longer needed (which saves a lot of download) and GPU support is
much easier to install for Pytorch alone (Cellpose already uses Pytorch). Right now, tensorflow is automatically installed (as the pytorch version may be too different from the original). To activate / test the PyTorch version of Mesmer, uninstall tensorflow from your environment -- palmettobug will switch to PyTorch if it can't find tensorflow.

Then to launch PalmettoBUG, simply enter:

    > palmettobug

in the conda environment where the package was installed. 

## isoSegDenoise

The overall workflow of PalmettoBUG depends on a semi-independent package: https://github.com/BenCaiello/isoSegDenoise 
This package was separated due to licensing reasons and both packages can theoretically be operated without the other, but it is automatically installed by pip as a dependency of PalmettoBUG so typically you don't need to pay too much attention to the division between the packages.


## Documentation

Step-by-step documentation of what can be done in the GUI will be found in the **animated** powerpoint file inside PalmettoBUG itself / this github repo, or at readthedocs: https://palmettobug.readthedocs.io/en/latest/. Tutorial notebooks for using this package outside the GUI can be found in this repository or at the readthedocs website.

## LICENSE

This package is licensed under the GPL-3 license. However, much of the code in it is derived / copying from other software packages -- so the original licenses associated with that code also applies to those parts of the repository. 

## Citation

If you use this work in your data analysis, software package, or paper -- a citation of this repository or its associated preprint / paper (TBD ____________) would be appreciated. 

