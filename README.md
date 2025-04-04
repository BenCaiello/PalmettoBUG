# PalmettoBUG
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/BenCaiello/PalmettoBUG/python-app.yml)
![Pepy Total Downloads](https://img.shields.io/pepy/dt/palmettobug)
![PyPI - Version](https://img.shields.io/pypi/v/palmettobug)
![Static Badge](https://img.shields.io/badge/License-GPL3-blue)


## Warning! This package is still under development!

Final development plans:

    1). Documentation: 
        - Update images and descriptions with new features & data
            -- single-cell analysis doc images -- CyTOF example data or IMC example data (then update)
            -- Premessa / bead-normalization translation --> have a page for this (would require fresh example data?)
            -- update to remove / reduce screenshots of prop-licensed software (probably fair use, but won't hurt to do)
        - update text of docs & slides 1x more / incorporate proofreader edits
        - Notebooks: add examples of missing functions (scatterplot, clustering-->classy masks, pxclass-->PNGs)
        - Look at API documentation -- it is almost certianly a mess right now

    2). Code:
        - Test more python versions (3.11, 3.12, etc.), create new env / pip freeze files for the updated dependency & python version lists 


## What is PalmettoBUG

PalmettoBUG is a pure-python GUI in customtinker that, along with its sister package isoSegDenoise, can preprocess, segment, and analyze high-dimensional image or flow cytometry data, especially mass cytometry / imaging mass cytometry data. 

PalmettoBUG is intended to accomplish a few things:

1. Be an easy starting point for scientists who do not necessarily have extensive background in computer science / coding but still want to be able to do basic data analysis & exploration of imaging mass cytometry data on their own. In particular, the GUI interface, extensive powerpoint documentation, easy installation, and integration of all the usually necessary steps in high-dimensional biological image analysis helps make analyzing data in PalmettoBUG much more approachable. This is particularly the focus of why MUSC flow (& mass) cytometry shared resource wanted a package like this -- it could also users of our instruments to _begin_ their analyses and get a _preliminary_ idea of their data without needing a collaborating bioinformatician to analyze the data for them.  

2. Be easily integrated into new or alternative workflows. Specfically, PalmettoBUG was designed so that most of its critical image / data intermediates as easily accessible by the user or automatically exported as common files types (.tiff for images, .csv for statistics/data/metadata, and .png for graphs/plots in most cases). Similar to the Steinbock package on which much of PalmettoBUG was based, as steps are performed in the analysis, PalmettoBUG frequently auto-exports the output of those steps to folders on the users' hard drive. This means that PalmettoBUG could be easily used for only some of its functions -- say only using it to convert files to MCDs, then segment cells -- with its outputs being re-directed into a separate analysis pipeline. This promotes maximum flexibility with how PalmettoBUG could be used!

## Packages that are used in or inspired parts of PalmettoBUG

The GUI is built mostly prominently on code from:

1. Steinbock (https://github.com/BodenmillerGroup/steinbock). PalmettoBUG has options for conversion of MCD files --> tiff files, hot pixel filtering, deepcell (Mesmer) segmentation, and mask expansion. PalmettoBUG also connects to cellpose (https://github.com/mouseland/cellpose) to offer denoising and cell segmentation options.

2. CATALYST (https://github.com/HelenaLC/CATALYST/). PalmettoBUG uses a python-translation / python mimic of CATALYST, with similar plot and a similar workflow: FlowSOM clustering followed by cluster merging. PalmettoBUG also offers additional plot types, especially for comparing metaclusters in order to assist in their merging to biologically relevant labels

3. spaceanova (https://github.com/sealx017/SpaceANOVA/tree/main). PalmettoBUG offers a simple spatial data analysis module based on a python version of the spaceanova package, with functional ANOVAs used to compare the pairwise Ripley's g statistic of celltypes in the sample between treatment conditions. This is based a precise python translation of Ripley's K statistic with isotropic edge correction from R's spatstat package (https://github.com/spatstat/spatstat), which was used in the original spaceanova package.

4. Additionally, PalmettoBUG offers pixel classification with ideas and/or code drawn from QuPath https://github.com/qupath/qupath supervised pixel classifiers and from the Ark-Analysis https://github.com/angelolab/ark-analysis unsupervised pixel classifier, Pixie. Pixel classification can then be used to segment cells, expand cell masks into non-circular shapes, classify cells into lineages for analysis, crop images to only areas of interest, or to perform simplistic analyes of pixel classification regions as-a-whole.

**Vendored packages**

Some packages are (semi)-vendored in PalmettoBUG -- specifically, I copied only the essential code (not entire packages into new python files), with minimal changes from a number of packages. See palmettobug/_vendor files for more details and links to the original packages' GitHub repositories.

Packages that were vendored: fcsparser, fcsy, pyometiff, qnorm, readimc, sigfig, and steinbock

## Installation:

Its installation (in a clean, **Python 3.10** environment!) should be as simple as running:

    > pip install palmettobug

Then to launch PalmettoBUG, simply enter:

    > palmettobug

in the conda environment where the package was installed. 

## isoSegDenoise

You will also want to run either:

    > pip install isosegdenoise

or

    > pip install isosegdenoise[tensorflow]

This is because the overall workflow of PalmettoBUG depends on a semi-independent package "isoSegDenoise" (GitHub: https://github.com/BenCaiello/isoSegDenoise).
This package was separated due to licensing reasons and both packages can theoretically be operated independent of each other, however the segmentation and denoising steps shown in the documentation are not possible without isoSegDenoise.

The decision on whether to include the [tensorflow] tag is because the popular Deepcell / Mesmer algorithm was originally implemented using tensorflow, so if you want an exact replication of the original Mesmer neural net model you should use the [tensorflow] tag. This will install the needd packges to run the model using tensorflow -- and when those packages are available, isoSegDenoise will use them by default. However, doing this does have a few practical downsides: 1). more, large dependencies are needed for installation (tensorflow, keras, etc.), 2). it makes it harder to configure GPU support and 3). the obsolete versions of tensorflow / keras that are needed to run the model generate large numbers of security warnings / have a large number of security vulnerablilities.

Without the [tensorflow] tag, the tensorflow / keras packages will not be installed and isosegdenoise with use an ONNX model version of Mesmer (generated using tf2onnx package) inside PyTorch (using onnx2torch). This makes GPU support easier and reduces the dependencies required by the program. However, the model is not 100% identical to the original tensorflow model! Its output does look very similar by eye -- but I have not (yet) benchmarked its accuracy vs. the original model.

## Documentation

Step-by-step documentation of what can be done in the GUI will be found in the **animated** powerpoint file inside PalmettoBUG itself / this github repo, or at readthedocs: https://palmettobug.readthedocs.io/en/latest/. Tutorial notebooks for using this package outside the GUI can be found in this repository or at the readthedocs website.

## LICENSE

This package is licensed under the GPL-3 license. However, much of the code in it is derived / copying from other software packages -- so the original licenses associated with that code also applies to those parts of the repository. 

## Citation

If you use this work in your data analysis, software package, or paper -- a citation of this repository or its associated preprint / paper (TBD ____________) would be appreciated. 

