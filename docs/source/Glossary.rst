Glossary
========

.. _Analysis:
Analysis
^^^^^^^^

   In PalmettoBUG an ‘analysis’ usually refers to the single-cell
   calculations and plots operating on :ref:`FCS`, which is to say all
   the functions associated with the 4\ :sup:`th` tab of the program.
   For imaging experiments, this occurs after measurements for each cell
   are read from the segmentation masks, and converted to FCS files.

.. _annotation:
Annotation
^^^^^^^^^^

   Or :ref:`merging`. The process of assigning biologically relevant labels to the output
   of an :ref:`unsupervised-algorithm` used to cluster cells or pixels. This typically also involves combining two
   or more groups of the clustering into a single label, hence the common alternative name "merging". 

Analysis_panel.csv
^^^^^^^^^^^^^^^^^^

   One of the key data tables required by PalmettoBUG (can be made
   inside the GUI). It is used for the *Analysis* portion of the
   program, and assigns a *marker_class* to each channel of the dataset
   (type, state, or none...) that affects how that channels is
   used for *clustering* and plotting functions of the analysis.
   This convention is derived from :ref:`CATALYST`

Batch Correction
^^^^^^^^^^^^^^^^

   Algorithm(s) that attempt to eliminate variability derived from
   confounding factors in a dataset, such as the variability between two
   different batches or technical replicates. In PalmettoBUG, batch
   correction is only provided by the ComBat algorithm through scanpy.

   Link: https://scanpy.readthedocs.io/en/stable/api/generated/scanpy.pp.combat.html

.. _CATALYST:
CATALYST
^^^^^^^^

   An R package whose functions and associated manuscript (https://f1000research.com/articles/6-748/v3) served as
   the inspiration and seed for much of the PalmettoBUG :ref:`Analysis`
   functions. 
   
   Link: https://github.com/HelenaLC/CATALYST/ 

Clustering
^^^^^^^^^^

   Clustering means assigning the cells of a dataset to groups — in
   PalmettoBUG, there are five main types of clustering:
   “metaclustering”, “leiden”, “merging”, “classification”, and “CN”.
   These are distinguished by how they are created / derived, but are
   also important to remember, as these five clustering types show up as
   options in the GUI, and only one of each can be actively loaded into
   an analysis at one time (as in, running a 2\ :sup:`nd` FlowSOM will
   overwrite the first metaclustering, etc.).

Metaclustering: 
'''''''''''''''

   A clustering derived by the FlowSOM unsupervised algorithm acting on
   the single-cell expression data. See :ref:`FlowSOM`

Leiden
''''''

   A clustering derived by the Leiden unsupervised algorithm acting on a
   UMAP of the single-cell expression data. See :ref:`Leiden-Algorithm`

.. _merging:
Merging
'''''''

   A manual :ref:`annotation` of an :ref:`unsupervised-algorithm` used for clustering 
   (:ref:`FlowSOM` / :ref:`Leiden-Algorithm`), assigning the numerical groups produced by those algorithms to
   biologically relevant groupings, often merging two or more of the
   numerical groups into one label.

Classification
''''''''''''''

   Any cell clustering derived from a pixel classifier. See :ref:`Pixel-Classification`

CN
'''

   Standing for “Cell Neighborhood” – a clustering that groups cell
   based on the % of each cell type among their spatial neighbors using
   a FlowSOM or Leiden to create unsupervised clusters that can then be
   annotated. CN clustering is only possible with imaging datasets.

.. _classification-maps:
Classification maps
^^^^^^^^^^^^^^^^^^^

   The predictive output of pixel classifiers. These are .tiff files
   with the same X / Y dimensions as the original image, but only 1
   ‘channel’ / layer. This channel contains the class predictions, which
   are unique integer values representing each unique class.

   When these numerical classes are annotated / merged (this is
   semi-automatic for supervised classifiers), a “merged classification map”
   is created, where ‘background’ pixels are set to 0, and the numerical
   values of the pixels are re-assigned based on the labels supplied by
   the user.

.. _denoising:
Denoising
^^^^^^^^^

   Or image restoration. These are methods & algorithms that seek to
   improve the signal-to-noise ratio in imaging channels. They tend to
   blur / smooth an image’s raw values.

Dimensionality Reduction
^^^^^^^^^^^^^^^^^^^^^^^^

   (DR) These are techniques for embedding high-dimensional data (in
   mass cytometry, this is from the high number of channels per image /
   FCS) into a lower-dimensional space, usually 2 dimensions for the
   sake of visualization on a scatter plot. These lower dimensional
   representations of the data can also be used for clustering by the
   Leiden algorithm, or to simplify other types of calculations. In
   PalmettoBUG, there are two main types of dimensionality reduction
   available: PCA and UMAP. The MDS plot is also an example of using
   dimensionality reduction, using a similar, but not identical method
   to PCA.

PCA
^^^

   Principal Component Analysis. This is a classic way of identifying
   the most important, linear, and orthogonal “components” of the
   dataset. PCA creates nearly as many components as there are
   dimensions in the dataset, but is also able to rank these components,
   allowing just the top two, most important components to be used for
   plotting.

.. _UMAP:
UMAP
^^^^

   Uniform Manifold Approximation and Projection. This creates a
   non-linear projection of the data into a lower dimensional space (2
   dimensions for plotting / leiden clustering in PalmettoBUG). It is
   similar to tSNE. In PalmettoBUG this is implemented through scanpy.

   Link: https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.umap.html

.. _fANOVA:
fANOVA
^^^^^^

   functional ANOVA test – a statistical test that compares two or more
   populations of functions, instead of 2+ populations of individual
   values. In the context of PalmettoBUG / SpaceANOVA, this means taking
   into account the spatial relationship of celltypes across an entire
   range of distances, instead of only testing one distance at a time.
    
.. _FCS:
FCS files
^^^^^^^^^

   Files of single-cell numerical data, where each row represents a
   cell, and each column represents a channel in the dataset, plus
   associated metadata. Commonly exported by flow cytometers and flow
   cytometry software.

   FCS files are one of the starting file types, and they can be used to
   initiate an :ref:`Analysis` in PalmettoBUG. They are also an
   intermediate in the PalmettoBUG pipeline, produced after taking
   region measurements of the cells in the images using segmentation
   masks.

.. _FlowSOM:
FlowSOM
^^^^^^^

   A Self-Organizing Map (SOM) algorithm, that takes an initial grid of
   points (determined by XY dimensions hyperparameter + a random seed)
   and fits that grid to the dataset. This is followed by consensus
   clustering of the grid points into a pre-set number of
   “metaclusters”. Cells are assigned to each *cluster* / *metacluster*.

   Link: https://github.com/saeyslab/FlowSOM_Python

.. _image-processing:
Image Processing
^^^^^^^^^^^^^^^^

   In PalmettoBUG / its documentation, this typically refers to the
   steps of the pipeline available in the second tab of the program,
   including the *isoSegDenoise* sub-program. This would include
   converting :ref:`MCD` / hot pixel filtering, :ref:`segmentation`,
   :ref:`denoising`, and :ref:`region-measurement`.

isoSegDenoise
^^^^^^^^^^^^^

   A pure-python associate package with PalmettoBUG, offering its own
   GUI for the :ref:`denoising` of images and the :ref:`segmentation` of cells. It
   expects the same directory structure, and the same file types, etc.
   as PalmettoBUG, and similarly its outputs are easily and
   automatically picked up by PalmettoBUG.

   It was separated from PalmettoBUG because some of its dependencies
   (specifically deepcell and possibly cellpose) have non-commercial
   restrictions affecting their segmentation models, which is
   incompatible with PalmettoBUG’s GPL-3 license.

   Link: https://github.com/BenCaiello/isoSegDenoise

.. _Leiden-Algorithm:
Leiden Algorithm
^^^^^^^^^^^^^^^^

   A method for grouping neighboring points in a network. In
   PalmettoBUG, it is used after a :ref:`UMAP` embedding of the cells, such
   that cells in similar locations of the UMAP projection will be
   clustered together. Unlike *FlowSOM*, it does not take a preset
   metaclustering number, and the final number of clusters it finds is
   variable. In PalmettoBUG, it is implemented
   through the leiden options in scanpy.

   Link: https://scanpy.readthedocs.io/en/stable/generated/scanpy.tl.leiden.html 

.. _masks:
Masks
^^^^^

   The output of :ref:`segmentation`. These are derived from the images of
   the dataset, having the same X / Y dimensions, but only 1 ‘channel’ /
   layer. This layer contains integer values for the pixels – each
   unique cell having a unique value – and zeros for pixels that lie
   outside any cell (background). When measurements are taken from the
   masks, all the pixels of a given integer value are treated as a
   single cell.

.. _MCD:
MCD Files
^^^^^^^^^

   A file format exported by Standard BioTools’ Hyperion imaging system.
   It is essentially a group of TIFF files (one for each ROI and
   panorama taken) associated with each other by metadata. Inside, there
   are ROIs (regions of interest – the images you actually care about
   which are converted by PalmettoBUG into TIFF files) and panoramas
   (brightfield images of the slides – these are usually only important
   for finding the tissue of interest during acquisition and not
   directly processed by PalmettoBUG).

   MCD files are one of the starting file types that can be used to
   initiate an imaging project in PalmettoBUG.

metadata.csv
^^^^^^^^^^^^

   One of the key data tables required by PalmettoBUG (can be made
   inside the GUI). It is used in the *analysis* portion of the
   PalmettoBUG pipeline to assign cells to different conditions or
   batches based on the ROI / FCS file those cells came from.

PalmettoBUG
^^^^^^^^^^^

   A pure-python software package offering a GUI for the analysis of
   high-dimensional imaging and single-cell data types, specifically
   MCD, TIFF, and FCS. Intended for mass cytometry data.

..

   Also, a dapper creature of the phylum *Arthropoda,* class *Insecta,*
   order *Blattodea*. Known in South Carolina for being a bit too large
   and flying at your face in inconvenient moments.

   Also, a recursive acronym for the program: (*P)ALMETTO (A)cronym
   (L)onger (M)ore (E)ven (T)han (T)he (O)riginal, (B)etter (U)ser
   (G)UI.*

panel.csv
^^^^^^^^^

   One of the key data table files needed by PalmettoBUG (can be made
   inside the GUI). This is concerned with :ref:`image-processing` steps, and
   specifies the name of the channels, what channels to keep from the
   initial :ref:`MCD` / :ref:`TIFF`, and what channels to use during
   :ref:`segmentation`.

.. _Pixel-Classification:
Pixel Classification
^^^^^^^^^^^^^^^^^^^^

   Assigning pixels to different groupings, analogous to clustering for
   cells. These can be used to classify cells, or to do a number of
   other transformations on the data, such as extending segmentation
   masks.

   In PalmettoBUG, this can also refer to the third tab of the program,
   and its two sub-tabs (creating and using a pixel classifier).

Project
^^^^^^^

   In PalmettoBUG, a ‘project’ typically refers to an imaging-based
   experiment that is processed all within in a single computer
   directory. As in, a replicate of a data analysis in PalmettoBUG whose :ref:`image-processing`,
   :ref:`segmentation`, :ref:`Analysis`, etc. occurred in an entirely separate folder from the original would
   be a separate “project”, despite only being a replicate.

.. _region-measurement:
Region Measurement
^^^^^^^^^^^^^^^^^^

   This is the step in the program where cell segmentation :ref:`masks` +
   images are converted into single-cell data that can be written as csv
   or *FCS* files. Specifically, pixels with all the same value in the
   masks are treated as ‘cells’, and their spatial / shape
   characteristics are written to ‘regionprops’ csv files, while the
   pixels’ intensities in each image channel are aggregated (usually by
   the mean or median) for each cell and written to ‘intensities’ csv
   files, which can then be easily converted to FCS files for
   :ref:`Analysis`.

.. _segmentation:
Segmentation
^^^^^^^^^^^^

   The process of identifying single cells in an image, in the end
   creating a :ref:`mask` that can be used for :ref:`region-measurement`. In
   PalmettoBUG, this can be done using pre-trained, generalist
   deep-learning networks from prior publications — Deepcell / Mesmer
   and Cellpose models — or by using a pixel classifier.

Spatial Analysis
^^^^^^^^^^^^^^^^

   In PalmettoBUG, this refers to the fifth and last tab of the program,
   as well as the functions that are available there. This includes cell
   neighborhoods, SpaceANOVA, spatial EDT, etc. This is tightly
   associated with, and dependent on, the :ref:`Analysis` portion of the
   program.

SpaceANOVA
^^^^^^^^^^

   An R package whose method (see https://pubs.acs.org/doi/10.1021/acs.jproteome.3c00462) was translated into
   Python for use inside PalmettoBUG. Briefly, it uses Ripley’s statistics + :ref:`fANOVA`` to test the spatial associations of
   clusterings / cell types in a dataset.

   Link: https://github.com/sealx017/SpaceANOVA

Spatial EDT
^^^^^^^^^^^

   This is technique in PalmettoBUG that uses a pixel classifier’s
   :ref:`classification-maps`` to generate Euclidean distance transforms of
   images for each pixel class, with the EDT values being the distance
   from that pixel classes. :ref:`region-measurement` can then be performed
   to find the distance values of cells from the pixel classes. In this
   way, the distance between cells and non-cellular structures can be
   probed.

Steinbock
^^^^^^^^^

   A python package from the Bodenmiller group that served as the
   inspiration & seed for much of image processing portion of the
   PalmettoBUG pipeline.

   Link: https://github.com/BodenmillerGroup/steinbock and https://www.nature.com/articles/s41596-023-00881-0

Supervised Algorithm
^^^^^^^^^^^^^^^^^^^^

   Any classification / clustering algorithm that requires a training
   set of labeled pixels / cells to learn the classes it will predict.
   This also means that its predictions can immediately be identified /
   correlated to biologically relevant labels. The only time PalmettoBUG uses a
   supervised algorithm is for a type of :ref:`Pixel-Classification`.

.. _unsupervised-algorithm:
Unsupervised Algorithm
^^^^^^^^^^^^^^^^^^^^^^

   Any *classification* / *clustering* algorithm that does not need a
   training set to learn before prediction, although they do take user
   input for hyperparameters. One consequence of this is that their
   output classes / clusters are numerical, not having any known
   biological meaning until :ref:`annotation` by the user. The most commonly
   used unsupervised algorithm in PalmettoBUG is :ref:`FlowSOM`, but :ref:`Leiden-Algorithm`
   clustering is also available for cells.

.. _TIFF:
TIFF files
^^^^^^^^^^

   An image format well-suited for raster images, like those from
   imaging mass cytometry. They consist of a grid of pixels with
   numerical values + associated metadata. The grid’s dimensionality is
   determined by the spatial, X/Y dimensions of the image as well as the
   number of channels. When read into python, they are easily
   represented by numpy arrays.

   TIFF files are one of the starting file types that can be used to
   initiate an imaging project in PalmettoBUG.

   .ome.tiff files are a subset of TIFF files, usually with more
   metadata and more consistently structure metadata, however their
   pixel values are read in the same way. PalmettoBUG always writes and
   processes with .ome.tiff files after the first step (conversion from
   the initial :ref:`MCD` or TIFF files).
