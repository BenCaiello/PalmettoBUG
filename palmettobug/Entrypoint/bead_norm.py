'''
This module contains the functions that handles bead normalization of CyTOF solution mode data. One function ( CyTOF_bead_normalize() )
is available in the public (non-GUI) API of PalmettoBUG, so the others are really more private / helper functions for that.


While the PalmettoBUG project as a whole is licensed under the GPL3 license, including this file, portions of this file
are derived / translated from Premessa / Cytof-Normalization packages::

    https://github.com/nolanlab/bead-normalization   &   https://github.com/ParkerICI/premessa

Which were also GPL3 licensed. 

In particular, the mathematical operations / algorithm itself was directly translated from Premessa (which is written in R) into Python,
including the finding of rolling medians, slopes, and then interpolating to normalize. 
'''
import re
import os
from typing import Union
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from .._vendor.fcsy import DataFrame
from .._vendor import fcsparser

__all__ = ["CyTOF_bead_normalize"]
                 
def _identify_metal_columns(dataframe: pd.DataFrame) -> list[str]:
    '''
    This function attempts to identify the metal channels of a CyTOF fcs using the characteristic 'Di', and return their names as a list.
    '''
    metal_regex = re.compile( r".+Di")       ## r"[A-Z][a-z][0-9]{2,3}Di"
    column_list = []
    for i in dataframe.columns:
        if metal_regex.match(i) is not None:
            column_list.append(i)
    return column_list

def _median_500_window_df(dataframe: pd.DataFrame, 
                          columns_to_run_on: list, 
                          window: int = 501,
                          ) -> pd.DataFrame:            ## made as a translation of Premessa
    '''
    This is a function that performs rolling median calculations on all the columns of a dataframe specified by columns_to_run_on
    '''
    dataframe = dataframe.copy()
    print(dataframe.columns)
    for i in columns_to_run_on:
        dataframe[i] = dataframe[i].rolling(window, min_periods = int((window / 2) - 1), center = True, closed = 'neither').median()            
                                                                                                                         # min_periods = 99,
    return dataframe

def _find_slope(original_data: pd.DataFrame, 
                smoothed_data: pd.DataFrame, 
                columns_to_run_on: list,
                ) -> pd.DataFrame:                     ## made as a translation of Premessa (https://github.com/ParkerICI/premessa)
    '''
    This function finds the slope at each point between smoothed data and the median of the original data, in a way meant to mimic Premessa
    '''
    original_data = original_data.copy().loc[:,columns_to_run_on]
    baseline = original_data.median(axis = 0)
    smoothed_data = smoothed_data.copy().loc[:,columns_to_run_on]
    slope = (baseline*smoothed_data).sum(axis = 1) / (smoothed_data**2).sum(axis = 1)
    return slope

def normalize_pipeline_one_fcs(bead_fcs: pd.DataFrame, 
                               to_normalize_fcs: pd.DataFrame, 
                               bead_channels: list, 
                               channels_to_normalize: list,
                               ) -> tuple[pd.DataFrame, pd.DataFrame]:                          ## made as a translation of Premessa
    '''
    This function performs the Premessa-style (it was translated into python from Premessa, which is written in R) normalization of CyTOF data 
    on a single bead / non-bead fcs pair. 

    Args:
        bead_fcs (pd.DataFrame): a pandas dataframe, usually read from an fcs (in testing, using fcsy), of only the beads

        to_normalize_fcs (pd.DataFrame): a pandas dataframe, usually read from an fcs (in testing, using fcsy), of the events to be normalized.
                Usually the non-beads, live, singlet events (from being already gated in a program like FlowJo)

        bead_channels (list): a list of the columns (i.e., metal channel / antigen) in the beads that will be used to calculate the slopes 
                for normalization

        channels_to_normalize (list): a list of the columns (i.e., metal channel / antigen) that will be normalized for analysis. 
                If None is passed in, will automatically try to detect all metal channels by looking for the 
                following regex: 

                        r".+Di"

                It is best to explicitly define the channels to normalize. 

    Returns:
        (pd.DataFrame, pd.DataFrame): the first output is the to_normalize_fcs dataframe, normalized on channels_to_normalize. 
        the second output is the bead_fcs dataframe, normalized on bead_channels
    '''
    median_smoothed_beads = _median_500_window_df(bead_fcs, bead_channels).sort_values('Time')
    slopes = _find_slope(bead_fcs, median_smoothed_beads.loc[:,bead_channels], bead_channels)
    norm_events = np.interp(to_normalize_fcs['Time'], median_smoothed_beads['Time'], slopes)
    norm_beads = np.interp(bead_fcs['Time'], median_smoothed_beads['Time'], slopes)
    my_normed_events = pd.DataFrame((np.array(to_normalize_fcs.loc[:, channels_to_normalize]).T * norm_events).T, 
                                    columns = channels_to_normalize)
    my_normed_events['Time'] = to_normalize_fcs['Time']
    my_normed_beads = pd.DataFrame((np.array(bead_fcs.loc[:, bead_channels]).T * norm_beads).T, columns = bead_channels)
    my_normed_beads['Time'] = bead_fcs['Time']
    return my_normed_events, my_normed_beads

def CyTOF_bead_normalize(bead_fcs_folder: str, 
                         to_normalize_fcs_folder: str, 
                         output_folder: str, 
                         bead_channels: list, 
                         channels_to_normalize: Union[list, None] = None, 
                         include_figures: bool = True,
                         ) -> None:
    '''
    This function performs the Premessa-style CyTOF normalization of the function above (normalize_pipeline_one_fcs) on all the FCS files 
    in a pair of beads / non-beads folders.

    Args:
        bead_fcs_folder (str | Pathlike): 
            file path to a directory containg fcs files of only beads

        to_normalize_fcs_folder (str | Pathlike): 
            file path to a directory containg fcs files that you want to be normalized. Usually 
            the non-beads, live, singlets (already gated in a program like FlowJo)

        output_folder (str | Pathlike): 
            file path to a directory where you want the normalized fcs' and figures will be written. Will 
            attempt to create the directory if it does not exist 

        bead_channels (list): 
            a list of the columns (i.e., metal channel / antigen) in the beads that will be used to calculate the slopes for normalization

        channels_to_normalize (list | None): 
            a list of the columns (i.e., metal channel / antigen) that will be normalized for analysis. 
            If None is passed in, will automatically try to detect all metal channels by looking for the 
            following regex: 

                    r".+Di"

            It is best to explicitly define the channels to normalize. 

        include_figures (bool): 
            whether to export figures of the normalization (True) or not (False)

    Returns:
        None

    Inputs/Outputs:
        Inputs: 
            reads in two folders, specified by bead_fcs_folder & to_normalize_fcs_folder, containing data from a CyTOF experiment
            with only beads remaining in bead_fcs_folder (non-beads gated out)) and with the events to nomalize in to_normalize_fcs_folder. 
            Normally, the to_normalize_fcs_folder .fcs files would be gated to exclude beads / dead cells, which would be more computationally
            efficient, but technically that isn't necessary as long as those are gated out afterwards. 
            Each folder should contain .fcs files and ONLY .fcs files.
            
            NOTE: It is assumed that the order of the files in each folder match (as in, the first file in os.listdir(bead_fcs_folder) are 
            the matching beads from the first file in os.listdir(to_normalize_fcs_folder))

        Outputs: 
            Outputs normalized beads .fcs files to output_folder/normalized_beads folder and normalized non-beads .fcs files to
            output_folder/normalized folder. The files in the output folders should match the same filenames as the two input folders.
            Additionally, if include_figures is True -- will export plots of the normalization to the output_folder/normalization_figures
            folder (as PNG files).  
    '''
    ## str conversion for pathlike compatibility:
    bead_fcs_folder = str(bead_fcs_folder)
    to_normalize_fcs_folder = str(to_normalize_fcs_folder)
    output_folder = str(output_folder)

    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    output_beads = output_folder + "/normalized_beads"
    output_no_beads = output_folder + "/normalized"
    if not os.path.exists(output_beads):
        os.mkdir(output_beads)
    if not os.path.exists(output_no_beads):
        os.mkdir(output_no_beads)
    if include_figures is True:
        output_figures = output_folder + "/normalization_figures"
        if not os.path.exists(output_figures):
            os.mkdir(output_figures)
    beads_fcsS = ["".join([bead_fcs_folder,"/",i]) for i in sorted(os.listdir(bead_fcs_folder))]
    to_normalize_fcsS = ["".join([to_normalize_fcs_folder,"/",i]) for i in sorted(os.listdir(to_normalize_fcs_folder))]
    for i,ii in zip(beads_fcsS, to_normalize_fcsS):
        _, prenorms_df = fcsparser.parse(ii, channel_naming = "$PnS")
        prenorms_df = DataFrame(prenorms_df.sort_values('Time'))
        no_bead_label = ii[ii.rfind("/") + 1:]
        _, beads_df = fcsparser.parse(i, channel_naming = "$PnS")
        beads_df = DataFrame(beads_df.sort_values('Time'))
        bead_label = i[i.rfind("/") + 1:]
        if channels_to_normalize is None:
            channels_to_normalize = _identify_metal_columns(prenorms_df)
        my_normed_events, my_normed_beads = normalize_pipeline_one_fcs(bead_fcs = beads_df, 
                                                            to_normalize_fcs = prenorms_df, 
                                                            bead_channels = bead_channels, 
                                                            channels_to_normalize = channels_to_normalize)
        DataFrame(my_normed_events).to_fcs(output_no_beads + "/" + no_bead_label)
        DataFrame(my_normed_beads).to_fcs(output_beads + "/" + bead_label)
        if include_figures is True:
            fig = plt.figure()
            axs = plt.gca()
            axs.plot(_median_500_window_df(beads_df, bead_channels).sort_values('Time')['Time'], 
                    _median_500_window_df(beads_df, bead_channels).sort_values('Time').loc[:,bead_channels], label =  bead_channels)
            axs.legend()
            fig.suptitle("Pre-normalization Beads")
            fig.savefig(output_figures + f"/pre_beads_{bead_label[:bead_label.rfind('.')]}")
            plt.close()
            fig = plt.figure()
            axs = plt.gca()
            axs.plot(_median_500_window_df(my_normed_beads, bead_channels).sort_values('Time')['Time'], 
                    _median_500_window_df(my_normed_beads, bead_channels).sort_values('Time').loc[:,bead_channels], label =  bead_channels)
            axs.legend()
            fig.suptitle("Normalized Beads")
            fig.savefig(output_figures + f"/normalized_beads_{bead_label[:bead_label.rfind('.')]}")
            plt.close()
            
            fig = plt.figure()
            axs = plt.gca()
            axs.plot(_median_500_window_df(prenorms_df, channels_to_normalize).sort_values('Time')['Time'],
                    _median_500_window_df(prenorms_df, channels_to_normalize).sort_values('Time').loc[:,channels_to_normalize], 
                    label =  channels_to_normalize)
            fig.suptitle("Pre-normalization non-Beads")
            fig.savefig(output_figures + f"/pre_norm_{no_bead_label[:no_bead_label.rfind('.')]}")
            plt.close()

            fig = plt.figure()
            axs = plt.gca()
            axs.plot(_median_500_window_df(my_normed_events, channels_to_normalize).sort_values('Time')['Time'], 
                    _median_500_window_df(my_normed_events, channels_to_normalize).sort_values('Time').loc[:,channels_to_normalize],
                    label =  channels_to_normalize)
            fig.suptitle("Normalized non-Beads")
            fig.savefig(output_figures + f"/normalized_{no_bead_label[:no_bead_label.rfind('.')]}")
            plt.close()
    return


# example call:

#CyTOF_bead_normalize(directory + "/beads", 
#                           directory + "/no_beads", 
#                           directory + "/normalization",
#                           bead_channels,
#                           channels_to_normalize = channels_to_normalize,
#                           include_figures = True)