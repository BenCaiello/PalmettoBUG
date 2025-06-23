# PalmettoBUG
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/BenCaiello/PalmettoBUG/python-app.yml)
![Codecov](https://img.shields.io/codecov/c/github/BenCaiello/PalmettoBUG)
![Pepy Total Downloads](https://img.shields.io/pepy/dt/palmettobug)
![PyPI - Version](https://img.shields.io/pypi/v/palmettobug)
![Read the Docs](https://img.shields.io/readthedocs/PalmettoBUG)
![Static Badge](https://img.shields.io/badge/License-GPL3-blue)

Badges made in: https://shields.io/

## What is PalmettoBUG

![PaperFig](https://github.com/BenCaiello/PalmettoBUG/blob/main/docs/source/media/Welcome1.png)

PalmettoBUG is a pure-python GUI in customtinker (https://github.com/tomschimansky/customtkinter) that, along with its sister package isoSegDenoise, can preprocess, segment, and analyze high-dimensional image or flow cytometry data, especially mass cytometry / imaging mass cytometry data. 

PalmettoBUG is intended to accomplish a few things:

1. Be an easy starting point for scientists who do not necessarily have extensive background in computer science / coding but still want to be able to do basic data analysis & exploration of imaging mass cytometry data on their own. In particular, the GUI interface, extensive powerpoint documentation, easy installation, and integration of all the usually necessary steps in high-dimensional biological image analysis helps make analyzing data in PalmettoBUG much more approachable. This is particularly the focus of why the MUSC Flow (& mass) Cytometry Shared Resource wanted a package like this -- it could allow users of our instruments to _begin_ their analyses and get a _preliminary_ idea of their data without needing a collaborating bioinformatician to analyze the data for them.  

2. Be easily integrated into new or alternative workflows. Specfically, PalmettoBUG was designed so that most of its critical image / data intermediates as easily accessible by the user or automatically exported as common files types (.tiff for images, .csv for statistics/data/metadata, and .png for graphs/plots in most cases). Similar to the Steinbock package on which much of PalmettoBUG was based, as steps are performed in the analysis, PalmettoBUG frequently auto-exports the output of those steps to folders on the users' hard drive. This means that PalmettoBUG could be easily used for only some of its functions -- say only using it to convert files to MCDs, then segment cells -- with its outputs being re-directed into a separate analysis pipeline. This promotes maximum flexibility with how PalmettoBUG could be used!

Example of a piece of the GUI (specifically some of the buttons in the main window & the pop-up window for calculating UMAPs), and some of the plots that can be made with the program:

![Example](https://github.com/BenCaiello/PalmettoBUG/blob/main/docs/source/media/SingleCellAnalysis/SCAnalysis9.png)

## Installation:

Its installation (in a clean, **Python 3.10 or 3.11** environment!) should be as simple as running:

    > pip install palmettobug

Then to launch PalmettoBUG, simply enter:

    > palmettobug

in the conda environment where the package was installed. 

### Strict Installation Options: Strictly defined dependencies & using Python 3.9 

As the scientific python package ecosystem updates, the current dependencies defined for PalmettoBUG (and isoSegDenoise) in the pyproject.toml files may break. Additionaly, you may be interested in using the programs on Python 3.9 -- however, the dependency requirements in the mian branch DO NOT work for python 3.9. 

Therefore, I offer two versions of the program for strictly defining the version number of every dependency in the program -- version 0.1.2.dev39 (python 3.9) or 0.1.2.dev310 (Python 3.10). As in:

    > pip install palmettobug==0.1.2.dev39

## The isoSegDenoise sister-package

You will also want to run either:

    > pip install isosegdenoise

or

    > pip install isosegdenoise[tensorflow]

This is because the overall workflow of PalmettoBUG depends on a semi-independent package "isoSegDenoise" / iSD (GitHub: https://github.com/BenCaiello/isoSegDenoise).
This package was separated due to licensing reasons and both packages can theoretically be operated independent of each other, however the segmentation and denoising steps shown in the documentation are not possible without isoSegDenoise. These packages are best installed together in one Python environment, as then PalmettoBUG can launch isoSegDenoise from inisde its GUI using command-line call / subprocess, however this is not strictly necessary either, as iSD can be launched on its own.

The decision on whether to include the [tensorflow] tag is because the popular Deepcell / Mesmer algorithm was originally implemented using tensorflow, so if you want an exact replication of the original Mesmer neural net model you should use the [tensorflow] tag. This will install the needd packges to run the model using tensorflow -- and when those packages are available, isoSegDenoise will use them by default. However, doing this does have a few practical downsides: 1). more, large dependencies are needed for installation (tensorflow, keras, etc.), 2). it makes it harder to configure GPU support and 3). the obsolete versions of tensorflow / keras that are needed to run the model generate large numbers of security warnings / have a large number of security vulnerablilities.

Without the [tensorflow] tag, the tensorflow / keras packages will not be installed and isosegdenoise with use an ONNX model version of Mesmer (generated using tf2onnx package) inside PyTorch (using onnx2torch). This makes GPU support easier and reduces the dependencies required by the program. However, the model is not 100% identical to the original tensorflow model! Its output does look very similar by eye -- but I have not (yet) benchmarked its accuracy vs. the original model in a thorough enough manner. More
information about iSD, and the tensorflow vs. Torch models, can be found at its repository & documentation pages.

## Instanseg option (*new feature / only in the development branch!*)

Modifying the installation command to:

    > pip install palmettobug[instanseg]  

(or really, since the development branch has not been uploaded to PyPI yet, you have to download the development branch of the repo and then run >>> pip install .[instaseg] in the directory where you saved the repo)

Will install instanseg with PalmettoBUG, allowing you to segment cells without needing isosegdenoise at all. Instanseg is a channel-invariant, fully open-source segmentation
deep-learning model. As such, it can be a part of the mian palmettobug package itself, and behaves somewhat differently than cellpose / deepcell (Mesmer) segmentation. Unlike those other two models, when selecting segmentation channels for Instanseg it does not matter the compartment label (nuclei / cytoplasm) you apply to the channels in the panel.csv -- both nuclei channels and cytoplasmic channels are treated equally. However, ONLY channels with some segmentation labels will be passed to Instanseg during segmentation -- so you do need select segmentation channels in the panel file still! 

In a future version of the program, this may become a 

## Documentation & Scripting use (using the package outside the GUI)

Documentation is hosted on readthedocs: https://palmettobug.readthedocs.io/en/latest/. 

Additionally, step-by-step documentation of what can be done in the GUI will be found in the **animated** slideshow files inside PalmettoBUG itself inside the docs/slides/ folder of this github repo.

Gif of the /docs/slides/How to Use PalmettoBUG.odp file:

![Gif of slides](https://github.com/BenCaiello/PalmettoBUG/blob/main/docs/slides/HowToUsePalmettoBUG.gif)

**non-GUI use of PalmettoBUG**
Additionally, PalmettoBUG exposes many of the key analysis functions it uses in a normal Python package API. While this is not envisioned to be the primary use case for this package, jupyter notebooks showing tutorials of how to do this are available on the readthedocs site, specifically: https://palmettobug.readthedocs.io/en/latest/notebooks/index.html. 
Using PalmettoBUB outside the GUI does have the advantage of making exactly reproducing the analysis of a user substantially more straightforward, as the data analysis method can then be conveyed directly through the code itself, instead of being trying to decipher the log file made by the GUI (or using a description of the steps performed).

## Packages that are used in or inspired parts of PalmettoBUG

The GUI is built mostly prominently on code from:

1. Steinbock (https://github.com/BodenmillerGroup/steinbock). This also applies to PalmettoBUG's sister-program, isoSegDenoise. Much of the code and workflow for image processing and segmentation original came from, or was modeled on, steinbock's design and code.

2. CATALYST (https://github.com/HelenaLC/CATALYST/). PalmettoBUG's single-cell analysis modules are largely python-translations / python mimics of CATALYST, with similar plots and similar workflows: FlowSOM clustering followed by cluster merging. PalmettoBUG also offers additional plot types, especially for comparing metaclusters in order to assist in their merging to biologically relevant labels

3. scverse packages, such as anndata (https://github.com/scverse/anndata), scanpy (https://github.com/scverse/scanpy), and squidpy (https://github.com/scverse/squidpy) are imported by PalmettoBUG and are critical to the single-cell / spatial analysis portions of the program. Notably, if PalmettoBUG is used in scripting form (outside the GUI), the most critical data in PalmettoBUG's single-cell/spatial analysis module is is stored as an anndata object (Analysis.data), which could improve inter-operability between PalmettoBUG and alternative analysis pipelines using scverse packages.

4. spaceanova (https://github.com/sealx017/SpaceANOVA/tree/main). PalmettoBUG offers a simple spatial data analysis module based on a python version of the spaceanova package, with functional ANOVAs used to compare the pairwise Ripley's g statistic of celltypes in the sample between treatment conditions. This is based a precise python translation of Ripley's K statistic with isotropic edge correction from R's spatstat package (https://github.com/spatstat/spatstat), which was used in the original spaceanova package.

5. Additionally, PalmettoBUG offers pixel classification with ideas and/or code drawn from QuPath https://github.com/qupath/qupath supervised pixel classifiers and from the Ark-Analysis https://github.com/angelolab/ark-analysis unsupervised pixel classifier, Pixie. Pixel classification can then be used to segment cells, expand cell masks into non-circular shapes, classify cells into lineages for analysis, crop images to only areas of interest, or to perform simplistic analyes of pixel classification regions as-a-whole.

**Vendored packages**

Some packages are (semi)-vendored in PalmettoBUG -- specifically, I copied only the essential code (not entire packages into new python files), with minimal changes from a number of packages. See palmettobug/_vendor files for more details and links to the original packages' GitHub repositories.

Packages that were "vendored": fcsparser, fcsy, pyometiff, qnorm, readimc, sigfig, and steinbock

## LICENSE

This package is licensed under the GPL-3 license (See LICENSE.txt). However, much of the code in it is derived / copying from other software packages -- so the original licenses associated with that code also applies to those parts of the repository (see individual code files, or see Other_License_Details.txt in the repository or package's 
/Assets folder). 

Note:
On Linux and MacOS, the opencv package ships with an open source, but non-GPL-compatible library (OpenSSL v1.1.1). As far as I am aware, PalmettoBUG does not use, depend on, or in any way interact with this library (and it is NOT shipped in Windows version of opencv, which kind of proves those points). So I am uncertain of how this affects the program itself, although makes it likely that a full / dependency-included version of PalmettoBUG (on linux / Mac) is currently not legally redistributable. This exact situation (a non-redistributable program because of dependency license conflicts) is already described for the very packages causing a problem in opencv: https://github.com/FFmpeg/FFmpeg. Hopefully the pending release of opencv 5.0 will also resolve this detail, as well, by providing a version of opencv without problematic libraries. 

## Citation

If you use this work in your data analysis, software package, or paper -- a citation of this repository or its associated preprint / paper (TBD ____________) would be appreciated. 

