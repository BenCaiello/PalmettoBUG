.. palmettoBUG documentation master file, created by
   sphinx-quickstart on Wed Nov  6 12:39:27 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Alternate Entrypoints to PalmettoBUG Tutorials
==============================================

Besides the core imaging pipeline, there are alternate ways of starting a PalmettoBUG analysis, such as
directly from FCS files from solution-mode CyTOF or from a CSV file exported by PalmettoBUG (which allows
the easy transfer of a single-cell analysis from one copy of PalmetotBUG to another). Note that loading 
from a CSV does not allow spatial analysis (only single-cell analysis).

Additionally, there are some side-functionalities of PalmettoBUG that are illustrated here -- converting
the back-up text files exported by the Hyperion system into .tiffs, and performing bead-normalization on 
CyTOF FCS files. These tutorial notebooks do not use example data, depending on your own data to test.

The order of these notebooks is not important for their execution, except the AnalysisFromCSV does 
depend on an exported CSV file from the "AnalysisFromFCS" tutorial.


.. toctree::
   :maxdepth: 3
   :caption: Contents:

   TextFilesToTIFFs
   BeadNormalizer
   AnalysisFromFCS
   AnalysisFromCSV

