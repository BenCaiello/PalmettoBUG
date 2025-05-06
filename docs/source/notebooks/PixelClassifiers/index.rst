.. palmettoBUG documentation master file, created by
   sphinx-quickstart on Wed Nov  6 12:39:27 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Pixel Classification Notebooks
==============================

These three tutorial notebooks are dedicated to pixel classifiers & their uses. The Supervised and Unsupervised notebooks
each show how their titular classifier type can be made. After showing how to make a classifier, these notebooks then also
illustrate some of hte possible uses of that pixel classifier. 

The Whole Class Analysis notebook then shows the special use case of pixel classifiers where each pixel class is treated like 
a segmentation mask in order to take measurements from each class as-a-whole, and do comparisons of the classes. This notebooks uses
the classifier outputs created by the Supervised Classifier -- so that notebook must be done first before doing whole-class analysis.

Some of the predictions and outputs of supervised classifier is always used in the Core Imaging Pipeline notebooks, so if you
are interested in seeing the particular uses illustrated in the core pipeline (such as using a pixel classifier to cluster cells
during a single-cell analysis), then you will need to do the Supervised Classifier notebook first.

.. note::
   All the notebooks in this folder depend on the Core Imaging Analysis --> Image Processing notebook to have been executed first! 
   The project directory used by the pixel classifiers here is the same as the project directory set up in the Image Processing 
   tutorial, so without that having been created & populated with image data, the pixel classifier notebooks will run run.

.. toctree::
   :maxdepth: 1
   :caption: Contents:

   SupervisedClassifier
   UnsupervisedClassifier
   WholeClassAnalysis
