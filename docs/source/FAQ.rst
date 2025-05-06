FAQ / Common Errors
===================

For now this section will be short / just be my best guesses for common problems.

    *1). I made a panel file already outside of PalmettoBUG -- do I have to create it inside PalmettoBUG again?*

        -- You can use a panel (or analysis_panel / metadata) file that was created outside PalmettoBUG! They just need to match the formatting expected by PalmettoBUG.
        This includes a few factors: 1). these files should be .csv files (comma separated -- no alternate delimiters!) 2). They must have the same column names
        and follow the same conventions of PalmettoBUG versions of these files. 3). They must be placed in the same location in a PalmettoBUG project directory
        so that the program can find them at the appropriate steps (overwriting any files PalmettoBUG auto-generated).

        -- One easy way to ensure your panel files match the PalmettoBUG format is to get to the point of a generating a panel (etc.) file in the GUI and proceed
        without editing the table in the PalmettoBUG pop-up. You can then check the csv that was saved in the project directory, and use that empty panel file as a template 
        to ensure that you match the formatting needed by PalmettoBUG in your self-generated file.

    *2). What is 'nan' in the segmentation column of my panel file?*

        -- 'nan' in this column is a result of that column being blank (i.e., not marked to be used for segmentation), and being assigned the value of 
        *Not A Number*, because the columns that are used for segmentation have the values 1 (for nuclei) or 2 (for cytoplasm / membrane). If you see
        'nan' in columns that you do not intend to use for segmentation, you can ignore this - it should not cause any problems.

    *3). I see I made a plot, but was it saved? Why does it look so weird in the display?*
            
        -- If you see a plot displayed in PalmettoBUG, this means it **has been saved** to your project directory as a .png file. 

        -- The display window in PalmettoBUG does not care about aspect ratio, and is not particularly high resolution - so a lot of your 
        plot will look weird when displayed inside the program! While the display inside PalmettoBUg is convenient for a quick glance at the plots you are making,
        if you want a detailed look at a plot it is effectively **always better** to open plots in your system's native image display software!
