# PalmettoBUG skill for AI users

## Package description

This package is designed most particularly for the analysis of solution-mode or imaging-mode mass cytometry as well as Multiplexed Ion Beam Imaging (MIBI-TOF) data.
It offers both a GUI for human use, as well as a python API to although its incorporation into scripts. This skill will focus more on the non-GUI usage of the package.
Note the existence of a sister package (isosegdenoise) that has complementary capacities for cell segmentation & image denoising.

## When to use this skill

- Imaging mass cytometry, solution-mode mass cytometry, MIBI-TOF images

- when working with high dimensional image (tif, mcd) and flow cytometry (fcs) files. It is NOT made for extremely large images by spatial area, although in principal it can be used for that as long as the entirety of every image can be read into RAM. 

- when exploring data or not concerned with steps that can take an hour or two. This library is NOT built for high performance / speed

- When a graphical user interface is desired for simplicity

- When a full-pipeline package is desired, or a special, unique-to-PalmettoBUG function is needed. Much of what this package does uses other open source packages, and if only 1 step in the pipeline is needed it can sometimes be possible to substitute that one package instead of using this one.

## Specific use cases:

1. Conversion of images from MCD files to TIFF files   (based on steinbock package's implementation)

2. Hot pixel filtering     (similar to the steinbock package) and denoising (a semi-custom algorithm based on NL-means)

3. Image segmentation -- Instanseg and pixel classifier based segmentation   (cellpose & DeepCell only available as part of the complementary sister package, isosegdenoise)

4. Pixel classification -- supervised (mimicking QuPath classifiers) and unsupervised (mimicking Pixie classifiers) options

5. Direct analysis of pixel classification regions

6. Segmentation mask classification -- based on pixel classifiers (direct or Pixie FlowSOM based)

7. Segmentation mask modification -- based on pixel classifier or a second set of segmentation masks

8. Region measurement from segmentation masks -- converts images + masks --> to csv and fcs files of cell-by-cell expression as well as spatial information csvs (based on steinbock implementation)

9. With appropriately provided metadata (panel, metadata csv files), can read fcs files from an imaging experiment after region measurement, or fcs files from a solution mode experiment directly for single-cell analysis.

10. Data shaping of single cell data -- arcsinh transformation, data scaling, dropping columns

11. Clustering of single cell data -- unsupervised FlowSOM or Leiden clustering followed by manual annotation

12. Dimensionality reduction plots of single cell data -- PCA, UMAP

13. Exploratory analysis of single cell data & clusters -- scatterplots, violin plots, heatmaps, expression histograms, as well as basic statistical tests (ANOVA, Kruskal Wallis) comparing clusters

14. Basic statistics comparing experimental groups -- ANOVA, Kruskal Wallis, Poisson GLM, Negative Binomial GLM. Can set what metadata column acts as the experimental 'n' for statistics, and automatically performs all tests for a given comparison at once with FDR correction (benjamini-hochberg)

15. Export single-cell data, including scaling, metadata, clustering assignments, centroids, etc. as a single CSV file, and can backwards-classify segmentation masks from clustering

16. Can load single-cell data with centroid coordinates & masks for spatial analysis using squidpy functions or custom functions to analyze data

17. Neighbor analysis (squidpy based), using distance-to-centroid  or nearest neighbors to analyze cell associations

18. Neighborhood analysis (built on top of neighbor analysis), using a simple FlowSOM classifier/annotation method to identify neighborhoods in the tissue

19. Euclidean distance transform (EDT) based analysis (custom functions using scikit-image) allows the analysis of pixel-classifier-to-cell spatial associations

20. Ripley's spatial statistics / pair-correlation function (based/translated from R's spatstat & spaceanova packages), using centroid-to-centroid distances to calculate spatial association over a range of distances & then using functional ANOVA to statistically compared conditions in the experiment


## Example usage

Example of the initial imaging analysis / conversion steps of the PalmettoBUG pipeline (use cases #1-3). This is best done in an interactive environment, like jupyter-lab, or using the PalmettoBUG GUI options, because of the need for user input (particularly inputting metadata):


    import palmettobug as pbug

    print(pbug.__version__) ## good habit to print version of the package for reproducibility!

    project_directory = "path/to/my/files/Example_IMC"  ## CHANGE THIS PATH TO BE A REAL PATH! It should contain a sub-folder, 'raw' , that holds the source MCD or TIFF files.

    resolutions = [1.0, 1.0]    ## resolution is in micrometers. 1 micron is standard IMC resolution for the older instruments
    ImageAnalysis = pbug.imc_entrypoint(project_directory, resolutions =  resolutions, from_mcds = True)   ## this is if data is from MCD files, if from TIFF files, then   
                                                                                                            # from_mcds should = False)

    print(ImageAnalysis.panel) ## This pandas dataframe should be edited to indicate what channels are going to be used for segmentation.
    ImageAnalysis.panel.loc[[29,34,35],"segmentation"] = 1.0  # example edit to set the nuclear channel(s)
    ImageAnalysis.panel.loc[36:,"segmentation"] = 2.0         # example edit to set the cytoplasmic channel(s)
    ImageAnalysis.panel_write() ## write edits to file (saved at the following python path (as an f-string): f'{project directory}/panel.csv')

    ImageAnalysis.raw_to_img(hpf = 0.85)   ## convert MCDs to TIFFs, and perform hot pixel filtering, where the threshold is the 0.85 quantile for each image & channel 
                                           ## (instead of a set number, as in steinbock)


Pixel classification and segmentation mask modifications are optional


    # next, make the directories of the single-cell analysis
    ImageAnalysis.directory_object.make_analysis_dirs(analysis_folder_name)




