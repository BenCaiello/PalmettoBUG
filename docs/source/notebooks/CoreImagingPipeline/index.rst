.. palmettoBUG documentation master file, created by
   sphinx-quickstart on Wed Nov  6 12:39:27 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Core Imaging Pipeline Tutorials
===============================

These notebooks should be done in order. The first notebook, Image Processing, is also necessary before doing any of the Pixel Classification tutorials! In particular, the Image Processing notebook creates and sets up 
the project directory we'll be using for most of these tutorial notebooks.

If you want to see the details of the Image segmentation / denoising, see the documentation for the isoSegDensoise sister-package:
https://isosegdenoise.readthedocs.io/en/latest/notebooks/index.html

Directly performing segmentation is not necessary in these notebooks, because the example data is bundled with masks for the images (these masks were generated using DeepCell). 

These go through the most important parts of the PalmettoBUG pipeline except pixel classification, and go in the most depth about each step. 

.. toctree::
   :maxdepth: 1
   :caption: Contents:

   ImageProcessing
   SingleCellAnalysis
   SpatialAnalysis

