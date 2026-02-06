# PalmettoBUG
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/BenCaiello/PalmettoBUG/python-app.yml)
![Codecov](https://img.shields.io/codecov/c/github/BenCaiello/PalmettoBUG)
![Pepy Total Downloads](https://img.shields.io/pepy/dt/palmettobug)
![PyPI - Version](https://img.shields.io/pypi/v/palmettobug)
![Read the Docs](https://img.shields.io/readthedocs/PalmettoBUG)
![Static Badge](https://img.shields.io/badge/License-GPL3-blue)

Badges made in: https://shields.io/

## NOTE: PalmettoBUG is not yet published and is still intended to be reviewed & tested further, be sensible if you use it and keep an eye out for bugs / errors! 

Also please raise an issue if you do encounter a bug, so that it can be fixed!

## What is PalmettoBUG

![PaperFig](https://github.com/BenCaiello/PalmettoBUG/blob/main/docs/source/media/Welcome1.png)

PalmettoBUG is a pure-python GUI in customtinker (https://github.com/tomschimansky/customtkinter) that, along with its sister package isoSegDenoise, can preprocess, segment, and analyze solution mass cytometry and imaging mass cytometry data. 

PalmettoBUG is intended to accomplish a few things:

1. Be an easy starting point for scientists who do not necessarily have extensive background in computer science / coding but still want to be able to do basic data analysis & exploration of imaging mass cytometry data on their own. In particular, the GUI interface, extensive powerpoint documentation, easy installation, and integration of all the core necessary steps of IMC image analysis helps make analyzing data in PalmettoBUG much more approachable. _Note: while PalmettoBUG is capable of performing some common statistical tests (like ANOVA) for a number of comparisons, consulting an expert statistician and/or exporting the data from PalmettoBUG for more rigorous statistical analysis is still recommended!_

2. Be easily integrated into new or alternative workflows. Specfically, PalmettoBUG was designed so that most of its critical image / data intermediates as easily accessible by the user or automatically exported as common files types (.tiff for images/masks/pixel classification, .csv for statistics/data/metadata, and .png for graphs/plots in most cases). _Note that this is more of a easy integration with other tools through accesible and easy to work with **file** types, not as much integration within a single coding environment (PalmettoBUG is intentionally picky about its dependencies, and may or may not be installable with another package in the same python environment!)._

Powerpoint documenting many of the available options in PalmettoBUG (converted to a .gif):
![Gif of slides](https://github.com/BenCaiello/PalmettoBUG/blob/main/docs/slides/HowToUsePalmettoBUG.gif)

This powerpoint is available from within this github repo at _/docs/slides/How to Use PalmettoBUG.odp_ as an alternate form of documentation to the readthedocs website.

## Installation:

Its installation (in a clean, **Python 3.10** environment!) should be as simple as running:

    > pip install palmettobug

Then to launch PalmettoBUG, simply enter:

    > palmettobug

in the conda environment where the package was installed. 

### Strict Dependencies in Installation (!!)

As of the present moment, PalmettoBUG is primarily developed for an extremely restricted python environment setup! While the package could _technically_ be compatible with a somewhat looser set of dependencies, the sheer number of dependencies it requires makes it simpler for reliability and reproducibility's sake to have a very rigid set of dependencies and requirements. 

This strictness does mean that if you install another set of python packages with it (which is generally NOT recommmended - except for its sister-poackage, iSD, see the next heading) you may get a lot warning about incompatible package versions, even though PalmettoBUG might ultimately still launch and operate normally.

**If you want reliable installation of PalmettoBUG, ALWAYS install it in a FRESHLY made, Python 3.10 environment using the latest version of the software!** Trying to install older versions of PalmettoBUG or use other versions of Python are at best much more risky, and at worst impossible. Fortunately, if you are using an environment manager, like conda, setting up a fresh Python 3.10 environment if easy and only takes a few minutes.

## The isoSegDenoise (iSD) sister-package

You will also want to run either:

    > pip install isosegdenoise

or

    > pip install isosegdenoise[tensorflow]

This is because the overall workflow of PalmettoBUG depends on a semi-independent package "isoSegDenoise" / iSD (GitHub: https://github.com/BenCaiello/isoSegDenoise).
The packages are separated due to licensing reasons (certain algorithms in iSD are restricted to non-commercial use), but the two packages are still best installed together in one Python environment. When they are in the same environment, then PalmettoBUG can launch isoSegDenoise from inisde its GUI. If they are not in the same environment, then that button in PalmettoBUG with have no effect, although iseoSegDenoies can still be launched independently from PalmettoBUG and seemlessly perform segmentation/denoising steps within a PalmettoBUG project's directory even if they are not installed together. **If you install iSD in a separate environment from PalmettoBUG, also use a fresh python 3.10 environment!** 

More information about iSD, the [tensorflow] tag, etc. can be found at its repository & documentation pages (https://github.com/BenCaiello/isoSegDenoise and https://isosegdenoise.readthedocs.io/en/latest/).

**whether to use the [tensorflow] tag:**

The decision on whether to include the [tensorflow] tag is specfic to the Mesmer / DeepCell segmentation algorithm. Including [tensorflow] in the installation command will attempt to install the original, tensorflow based version of DeepCell (with same version number for DeepCell as used in the Steinbock pipeline). This version's output will more closely reflect previous DeepCell publications. 

Ommitting the tensorflow tag will cause iSD to use an ONNX/PyTorch version of the DeepCell neural network instead. This version simplifies some of the dependencies for PalmettoBUG/iSD, including making GPU support MUCH easier to configure. It also appears to generate masks that are visually similar to the tensorflow verison of DeepCell - but the masks are NOT identical to the tensorflow version, so if you need your DeepCell segmentation to exactly match the original neural network be sure to inlcude the tensorflow tag! 

## Instanseg option

Modifying the installation command to:

    > pip install palmettobug[instanseg]  

Will attempt to install instanseg with PalmettoBUG, allowing you to segment cells without needing isosegdenoise at all. Instanseg is a channel-invariant, fully open-source  deep-learning model for segmentation. As such, it can be a part of the main palmettobug package itself. 

While this command should work smoothly, it does introduce a bit of risk to the installation because the instanseg add-on is not as strict in its requirements as the main package.

## Documentation & Scripting use (using the package outside the GUI)

Documentation is hosted on readthedocs: https://palmettobug.readthedocs.io/en/latest/. 

Additionally, step-by-step documentation of what can be done in the GUI will be found in the **animated** slideshow files inside PalmettoBUG itself inside the docs/slides/ folder of this github repo, at _/docs/slides/How to Use PalmettoBUG.odp_

**non-GUI use of PalmettoBUG**
Additionally, PalmettoBUG exposes many of the key analysis functions it uses in a normal Python package API. While this is not envisioned to be the primary use case for this package, jupyter notebooks showing tutorials of how to do this are available on the readthedocs site, specifically: https://palmettobug.readthedocs.io/en/latest/notebooks/index.html. 
Using PalmettoBUB outside the GUI does make reproducibility easier as the code itself can be the documentation of the analysis performed.

## Packages that are used in or inspired parts of PalmettoBUG

The GUI is built mostly prominently on code from:

1. Steinbock (https://github.com/BodenmillerGroup/steinbock). This also applies to PalmettoBUG's sister-program, isoSegDenoise. Much of the code and workflow for image processing and segmentation original came from, or was modeled on, steinbock's design and code.

2. CATALYST (https://github.com/HelenaLC/CATALYST/). PalmettoBUG's single-cell analysis modules are largely python-translations / python mimics of CATALYST, with similar plots and similar workflows: FlowSOM clustering followed by cluster merging. PalmettoBUG also offers additional plot types, especially for comparing metaclusters in order to assist in their merging to biologically relevant labels

3. scverse packages, such as anndata (https://github.com/scverse/anndata), scanpy (https://github.com/scverse/scanpy), and squidpy (https://github.com/scverse/squidpy) are imported by PalmettoBUG and are critical to the single-cell / spatial analysis portions of the program. Notably, if PalmettoBUG is used in scripting form (outside the GUI), the most critical data in PalmettoBUG's single-cell/spatial analysis module is is stored as an anndata object (Analysis.data), which could improve inter-operability between PalmettoBUG and alternative analysis pipelines using scverse packages.

4. spaceanova (https://github.com/sealx017/SpaceANOVA/tree/main). PalmettoBUG offers a simple spatial data analysis module based on a python version of the spaceanova package, with functional ANOVAs used to compare the pairwise Ripley's g statistic of celltypes in the sample between treatment conditions. This is based a precise python translation of Ripley's K statistic with isotropic edge correction from R's spatstat package (https://github.com/spatstat/spatstat), which was used in the original spaceanova package.

5. Additionally, PalmettoBUG offers pixel classification with ideas and/or code drawn from QuPath https://github.com/qupath/qupath supervised pixel classifiers and from the Ark-Analysis https://github.com/angelolab/ark-analysis unsupervised pixel classifier, Pixie. Pixel classification can then be used to segment cells, expand cell masks into non-circular shapes, classify cells into lineages for analysis, crop images to only areas of interest, or to perform simplistic analyes of pixel classification regions as-a-whole.

**Vendored packages**

Some packages are (semi)-vendored in PalmettoBUG -- specifically, I copied only the essential code (not entire packages into new python files), with minimal changes from a number of packages. See palmettobug/_vendor files for more details and links to the original packages' GitHub repositories.

Packages that were "vendored": fcsparser, fcsy, pyometiff, qnorm, readimc, and steinbock

## LICENSE

This package is licensed under the GPL-3 license (See LICENSE.txt). However, much of the code in it is derived / copying from other software packages -- so the original licenses associated with that code also applies to those parts of the repository (see individual code files, or see Other_License_Details.txt in the repository or package's 
/Assets folder). 

Note:
On Linux and MacOS, the opencv package ships with an open source, but non-GPL-compatible library (OpenSSL v1.1.1). As far as I am aware, PalmettoBUG does not use, depend on, or in any way interact with this library. So I am uncertain of how this affects the program itself, although makes it likely that a full / dependency-included version of PalmettoBUG (on linux / Mac) is currently not legally redistributable. This exact situation (a non-redistributable program because of dependency license conflicts) is already described for the very packages causing a problem in opencv: https://github.com/FFmpeg/FFmpeg. 

## Citation

If you use this work in your data analysis, software package, or paper -- a citation of this repository or its associated preprint / paper (TBD ____________) would be appreciated. 

