Tutorial Notebooks
=========================

Tutorials for using PalmettoBUG outside of the GUI (in jupyter notebooks). 

The notebooks are in three folders: 

	1). Core Imaging Pipeline -- 
		4 notebooks about the key steps to an Imaging project: Image Processing (2 notebooks), Single-Cell analysis, and 
		Spatial Analysis.  

	2). Core Pixel Classifiers -- 
		3 notebooks on making supervised / unsupervised classifiers and how to use them.

	3). Alternate Entrypoints -- 
		4 notebooks covering loading an analysis directly from FCS files, or from a saved CSV file as well as side-functions 
		of PalmettoBUG, like converting backup .txt files to .tiffs, and normalizing solution-mode data using beads. 

There is, additionally, a notebook in this folder (LaunchMainGUIs) that shows how to launch the PalmetotBUG GUIs in a notebook instead of
from the command-line.

.. note::
	 You will need to edit a cell at the top of most of the tutorial notebooks to reflect the path to your computer's files.
	This path should be the same for every notebook, and it is best to follow the order of the notebooks, as some depend on the outputs 
	of a prior notebook, which are written to subfolders at the path you specify. An exception to the usual order are the tutorials for 
	pixel classifiers, as at least one of the prior notebooks depends on pixel classifier outputs for a few optional steps. 
	In the first cell of each notebook, information should be provided about what prior steps / notebooks it depends on, so you can 
	follow that information if you attempt to do the notebooks out-of-order.

.. important::
	If you want to exactly reproduce the results of the notebooks shown in this documentation, you should install PalmettoBUG in a special way:

		1). BEFORE installing PamettoBUG, run:

				>>> pip install -r /environments/windows_local_pip_freeze3.10.txt         

		To install all the same versions of packages as the environment used to run these notebooks.	
		(Note that "/environments/windows_local_pip_freeze3.10.txt" in the command above indicates the file location inside the PalmettoBUG repository -- 
		the directory & command will presumably be different on your computer!)

		2). Install PalmettoBUG normally -- since all the requirements of the program are met, it *should* not alter
		the versions of packages at all. You could also instead install PalmettoBUG and force pip to not configure dependencies

	These steps should ensure that the environment is as similar as possible (excluding a docker container). In particular, methods like FlowSOM and UMAP
	(which use random seeds) might be sensitive to otherwise "meaningless" changes in the versions of the dependencies.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   CoreImagingPipeline/index.rst
   PixelClassifiers/index.rst
   EntrypointAlternatives/index.rst

   LaunchMainGUIs.ipynb

