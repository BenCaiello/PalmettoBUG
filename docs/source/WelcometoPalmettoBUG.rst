Welcome to PalmettoBUG!
=======================

PalmettoBUG is a GUI interface for performing all the steps of analysis
for an (imaging) mass cytometry experiment. While explicitly intended
for IMC and solution-mode mass cytometry, it theoretically can work with
any imaging data that can represented in a .tiff file or any single-cell
data that can be represented as an .fcs file. However, note that it’s
design was very much directed at high-dimensional, but small/medium
scale experiments and not low-dimensional very large experiments. So its
performance will likely suffer with very large data / very large
individual ROIs.

PalmettoBUG Capabilities in Graphical Form
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

From the manuscript: ( BioRXiv link here )

|image1|

Installation:
~~~~~~~~~~~~~

To install, first setup a **Python 3.10** environment.

.. warning::

   A python 3.9 environment should be useable, but since most of the dependencies in pyproject.toml allow for some higher versions of the dependencies
   trying to directly install will run into errors. I know that at least anndata and mudata have a conflict that occurs in python 3.9 when installing
   automatically, because the latest anndata is compatible with python 3.9, but none of the mudata versions compatible with that verison of anndata
   allow python 3.10 *(so you would need to download an older version of anndata before installing PalmettoBUG, or something like that)*. And there
   may be other conflicts. If you can, stick with python 3.10!

I mainly used conda environments to develop and test PalmettoBUG.

Enter your environment and issue the command:

>>> pip install palmettobug

To install PalmettoBUG in your environment. All dependencies should be
automatically installed (via the pyproject.toml dependency manifest) by
pip.

.. admonition::Temporary Warning!

   Palmettobug is not (yet) on PyPI, so the command above is aspirational and not true! Until PalmettoBUG is on PyPI
   you will have to download both PalmettoBUG and isoSegDenoise programs (from GitHub repositories) and install them in the 
   same python 3.10 environment using pip's installation-from-a-folder-path capacity.

There are many dependencies for the program, and the example data for
PalmettoBUG is quite large so this installation will take some time, and
can use a good deal of disc space (> 1-2 Gb). If you run into errors you
believe are a result of dependency issues, you can look at the
environment files at the PalmettoBUG github repository to see the exact
version numbers of the packages in my development environment, or you
can open an issue at the same repository.

**A Note on the isoSegDenoise sister program**

One dependency to make particular note of is *isoSegDenoise* – a sister
program to PalmettoBUG that handles segmentation and denoising of images
(separated for licensing reasons, see below). If needed, it can be
separately installed by the command:

>>> pip install isoSegDenoise

Note that isoSegDenoise should be installed in the same python
environment as PalmettoBUG so that the PalmettoBUG GUI can directly and
smoothly launch it when needed.

Alternative Slideshow Documentation & Specific Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Inside the /docs/slides folder of the GitHub repository, you
will find two animated .odp files (open source format similar to .pptx files, 
open-able by PowerPoint or other slideshow software) which can serve an alternate 
documentation for the PalmettoBUG GUI. These can be particularly powerful because of their
animations that lay out how to use the various buttons of the GUI in **excruciating** detail.
These slideshows were created & edited in PowerPoint.

Also on the GitHub (in an /environments folder) will be a few text documents listing
all the dependencies that are installed with PalmettoBUG / isoSegDenoise, using “pip freeze” 
command to retrieve packages in installed in an environment I used in testing / development.

Example Data
~~~~~~~~~~~~~

The example data used in PalmettoBUG documentation / preprint / etc. can be retrieved using the fetch_CyTOF_example
and fetch_IMC_example functions, as well as in the GUI (which calls those two functions using a button). These work by
using the python requests library to download the data from Zenodo.
However, if an error occurs in one of these functions (which may be more likely for the IMC data because of its large size of ~700 MB), 
the example data can be downloaded directly from Zenodo instead: https://zenodo.org/records/14983582.  

GPU support
~~~~~~~~~~~

GPU support is only useful for the isosegdenoise sister program,
specifically for the DeepCell and Cellpose segmentation / denoising deep
neural network models. On a windows 10 system for a NVIDIA GPU (in
python 3.10), I was able to successfully install GPU support.
Specifically, presuming you have successfully installed the NVIDIA
driver for your GPU, you will need to:

   1). follow the recommended pip download on the PyTorch website:
   `Start Locally \|
   PyTorch <https://pytorch.org/get-started/locally/>`__ to get GPU
   support for Cellpose functions.

..

   2). Download the proper tensorflow & cuda packages for deepcell /
   mesmer (listed are what worked for me):

   >>> pip install tensorflow-gpu==2.8.4

   >>> conda install cudnn=8.9.2.26

   >>> conda install cudatoolkit=11.8.0

   >>> conda install zlib-wapi

However, your mileage using these steps may vary in practice – GPU
support was not thoroughly tested on a variety of computer systems or
setups!

Do note that to get GPU support really means getting it configured for
Cellpose (build on PyTorch) and DeepCell/Mesmer (Tensorflow) packages as
these are the only parts of the program that use a GPU. So you can also
consult these package’s for information about configuring GPU support.

Licensing information:
~~~~~~~~~~~~~~~~~~~~~~

PalmettoBUG is under the GPL-3 opensource license. Much of the code &
dependencies of PalmettoBUG came from GPL-2+ projects across a few
different programming languages, necessitating that PalmettoBUG itself
be under the same license. 

.. warning::

   The DeepCell / Mesmer segmentation model (and possibly some of the models from Cellpose) is licensed under a non-commercial / academic
   license! 

   This is not compatible with GPL-3, which is why the isoSegDenoise program was separated off as a technically independent program
   from the main PalmettoBUG package. 



Details of Documentation creation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The pages of this documentation was created in Microsoft Word (odt_docs) or in jupyterlab (notebooks).
The odt files were then translated into .rst files using the pandoc library. These .rst files were subsequently
edited into their final form (this mainly meant getting the proper relative links between pages and to images and fixing formatting).
Then, sphinx (using the automated readthedocs pipeline) was used to convert the .rst files 
into html. Other packages used in this process include: nbsphinx (for jupyter notebook files), sphinx-autoapi & the napoleon sphinx extension (for api docs),
and sphinx-rtd-theme.

The media / images (and odp files) in the /docs folder of the GitHub repository were created in 
Microsoft PowerPoint from screenshots (using Windows Snipping Tool) of the PalmettoBUG program & its output files, as well as screenshots of 
other programs (like Napari & Windows File Explorer) that are used while analysing the example data  
Additionally, (of course) PowerPoint objects such as arrows, shapes, etc. were used to compose and arrange the figures, before a 
final screenshot was taken to save the images as they are displayed here.
These screenshots are used under the assumption of fair use given the limited use of such screenshots and open-source / academic / non-commercial 
nature of the PalmettoBUG program and its documentation -- if this is inaccurate I am happy to remove any offending parts.
(such copyright concerns could only likely apply to icons in / screenshots of Windows File Explorer, which I may begin to edit anyway in order to reduce any such concerns)


.. |image1| image:: media/Welcome1.png
   :width: 6.49583in
   :height: 3.68681in

   
