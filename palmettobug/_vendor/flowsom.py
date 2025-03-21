'''
This module is copied code from the saesys lab flowsom package::
 
    https://github.com/saeyslab/FlowSOM_Python

Date of copying not recalled precisely -- This note made 12/11/24 (likely copied ~6 months earlier, except star plot code, which was copied much later [maybe a month prior])

It is only used by parts of PalmettoBUG that use FlowSOm clustering (unsupervised pixel classifiers, and the main Analysis modules).


Goal / Why this file exists & is not simply treated like a standard import: 

    1. Conflicting dependenices: the repo from the saesys lab had conflicting dependencies -- so for the sake of smooth downloading of PalmettoBUG, 
    I separated out only the portion of FLOWSOM repo that I actually needed

    2. This also has the side benefit of reducing the amount of code & number of libraries needed to download PalmettoBUG, which is always good. 
    Additionally, the saesys lab repo has not been published as a pip package yet -- so this has some benefit in terms of 
    ease-of-use / simple one-command installation. Once the repo from the saesys lab is published on pip, I could consider re-visiting it
    to see if I can resolve the dependency conflicts to use it directly

One disadvantage of this current set up is that I have not yet copied the code for minimum spanning tree plots from the original repo to here,
so they are not yet available in PalmettoBUG. 


Being part of PalmettoBUG, this file is licensed under GPL3. This is also copied code (also originally licensed under GPL3)
So effectively this is licensed in the same way as the rest of the program, except -- the original authors of this code retain the copyright 
to this (this is not my original work / copyrighted by me, except any modifications deemed significant enough)

minimal edits were applied to allow the code to continue to work in one document (to further the goal of "unhooking" this package from the original dependencies / repo)
this would mean:

        1. combining the code from various scripts into one

        2. removing redundant imports (many scripts have the same imports, which is unecessary to keep them all)

        3. See the comments above the starplots code (likely the same minimal edits, but didn't precisely record edits at the time)

        4. (2-6-25): removed assert statements (replaced with if / print / raise). This silences security warnings from certain tools.

        5. added __all__= [] (for the sake of autoapi docs -- I don't really want to include any of the vendor files)  

        6. See section lower down for edits to the MST plotting function  
'''
from __future__ import annotations

__all__ = []

import copy
import re
import inspect

import anndata as ad 
import igraph as ig 
import numpy as np
from numba import jit
import pandas as pd

import bisect
from itertools import combinations
from sklearn.cluster import AgglomerativeClustering

import readfcs
from loguru import logger 
from mudata import MuData  
from scipy.sparse import issparse
from scipy.spatial.distance import cdist, pdist, squareform
from scipy.stats import median_abs_deviation
from sklearn.base import check_is_fitted as check_is_fitted2
from sklearn.base import  BaseEstimator, ClusterMixin
from sklearn.utils.validation import check_is_fitted

import matplotlib.colors
import matplotlib.pyplot as plt
from matplotlib import collections as mc
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Wedge
#from scipy.spatial.distance import pdist

__all__ = []

@jit(nopython=True, parallel=False)
def eucl(p1, p2):
    distance = 0.0
    for j in range(len(p1)):
        diff = p1[j] - p2[j]
        distance += diff * diff
    return np.sqrt(distance)


@jit(nopython=True, parallel=True)
def manh(p1, p2):
    return np.sum(np.abs(p1 - p2))


@jit(nopython=True)
def chebyshev(p1, p2, px, n, ncodes):
    distance = 0.0
    for j in range(px):
        diff = abs(p1[j * n] - p2[j * ncodes])
        if diff > distance:
            distance = diff
    return distance


@jit(nopython=True, parallel=True)
def cosine(p1, p2, px, n, ncodes):
    nom = 0.0
    denom1 = 0.0
    denom2 = 0.0
    for j in range(px):
        nom += p1[j * n] * p2[j * ncodes]
        denom1 += p1[j * n] * p1[j * n]
        denom2 += p2[j * ncodes] * p2[j * ncodes]

    return (-nom / (np.sqrt(denom1) * np.sqrt(denom2))) + 1


@jit(nopython=True, parallel=True)
def SOM(data, codes, nhbrdist, alphas, radii, ncodes, rlen, distf=eucl, seed=None):
    if seed is not None:
        np.random.seed(seed)
    xdists = np.zeros(ncodes)
    n = data.shape[0]
    px = data.shape[1]
    niter = rlen * n
    threshold = radii[0]
    thresholdStep = (radii[0] - radii[1]) / niter
    change = 1.0

    for k in range(niter):
        if k % n == 0:
            if change < 1:
                k = niter
            change = 0.0

        i = np.random.randint(n)

        nearest = 0
        for cd in range(ncodes):
            xdists[cd] = distf(data[i, :], codes[cd, :])
            if xdists[cd] < xdists[nearest]:
                nearest = cd

        if threshold < 1.0:
            threshold = 0.5
        alpha = alphas[0] - (alphas[0] - alphas[1]) * k / niter

        for cd in range(ncodes):
            if nhbrdist[cd, nearest] > threshold:
                continue

            for j in range(px):
                tmp = data[i, j] - codes[cd, j]
                change += abs(tmp)
                codes[cd, j] += tmp * alpha

        threshold -= thresholdStep
    return codes


@jit(nopython=True, parallel=True)
def map_data_to_codes(data, codes, distf=eucl):
    counter = -1
    n_codes = codes.shape[0]
    nd = data.shape[0]
    nn_codes = np.zeros(nd)
    nn_dists = np.zeros(nd)
    for i in range(nd):
        minid = -1
        mindist = np.inf
        for cd in range(n_codes):
            tmp = distf(data[i, :], codes[cd, :])
            if tmp < mindist:
                mindist = tmp
                minid = cd
        counter += 1
        nn_codes[counter] = minid
        nn_dists[counter] = mindist
    return nn_codes, nn_dists

class BaseClusterEstimator(BaseEstimator, ClusterMixin):
    """Base class for all cluster estimators in FlowSOM."""

    def __init__(self):
        super().__init__()
        self._is_fitted = False

    def __sklearn_is_fitted__(self):
        """Check fitted status and return a Boolean value."""
        return hasattr(self, "_is_fitted") and self._is_fitted
    
class BaseFlowSOMEstimator(BaseEstimator):
    """Base class for all FlowSOM estimators in FlowSOM."""

    def __init__(
        self,
        cluster_model: type[BaseClusterEstimator],
        metacluster_model: type[BaseClusterEstimator],
        **kwargs,
    ):
        """Initialize the FlowSOMEstimator object."""
        super().__init__()
        cluster_args = list(inspect.signature(cluster_model).parameters)
        cluster_dict = {k: kwargs.pop(k) for k in dict(kwargs) if k in cluster_args}
        self.cluster_model = cluster_model(**cluster_dict)
        metacluster_args = list(inspect.signature(metacluster_model).parameters)
        metacluster_dict = {k: kwargs.pop(k) for k in dict(kwargs) if k in metacluster_args}
        self.metacluster_model = metacluster_model(**metacluster_dict)

    @property
    def codes(self):
        """Return the codes, shaped: (n_clusters, n_features)."""
        check_is_fitted(self, "_is_fitted")
        return self.cluster_model.codes

    @property
    def distances(self):
        """Return the distances."""
        check_is_fitted(self, "_is_fitted")
        return self.cluster_model.distances

    @property
    def cluster_labels(self):
        """Return the cluster labels."""
        check_is_fitted(self, "_is_fitted")
        return self.cluster_labels_

    @property
    def metacluster_labels(self):
        """Return the metacluster labels."""
        check_is_fitted(self, "_is_fitted")
        return self.labels_

    def fit(self, X, y=None):
        """Fit the model."""
        self.cluster_model.fit(X)
        y_codes = self.metacluster_model.fit_predict(self.cluster_model.codes)
        self._y_codes = y_codes
        self._is_fitted = True
        return self

    def fit_predict(self, X):
        """Fit the model and predict the clusters."""
        # overcluster
        y_clusters = self.cluster_model.fit_predict(X)
        self.cluster_labels_ = y_clusters
        # metacluster the overclustered data
        X_codes = self.cluster_model.codes
        y_codes = self.metacluster_model.fit_predict(X_codes)
        # assign the metacluster labels to the original data via the overcluster labels
        y = y_codes[y_clusters]
        self._y_codes = y_codes
        self.labels_ = y
        self._is_fitted = True
        return y

    def predict(self, X):
        """Predict the clusters."""
        check_is_fitted(self, "_is_fitted")
        y_clusters = self.cluster_model.predict(X)
        self.cluster_labels_ = y_clusters
        # skip the metaclustering step
        # assign the metacluster labels to the original data via the overcluster labels
        y = self._y_codes[y_clusters]
        self.labels_ = y
        return y

    def subset(self, indices):
        """Subset the model."""
        self.labels_ = self.labels_[indices]
        self.cluster_labels_ = self.cluster_labels_[indices]
        self.cluster_model.distances = self.cluster_model.distances[indices]
        return self

    def set_n_clusters(self, n_clusters):
        """Set the number of clusters."""
        self.metacluster_model.n_clusters = n_clusters
        return self

###############################################   (concensusCluster class only)
# Copyright Žiga Sajovic, XLAB 2019           #
# Distributed under the MIT License           #
#                                             #
# github.com/ZigaSajovic/Consensus_Clustering #
#                                             #
###############################################

class ConsensusCluster(BaseClusterEstimator):
    """
    Implementation of Consensus clustering.

    This follows the paper
    https://link.springer.com/content/pdf/10.1023%2FA%3A1023949509487.pdf
    https://github.com/ZigaSajovic/Consensus_Clustering/blob/master/consensusClustering.py
      * cluster -> clustering class
      * NOTE: the class is to be instantiated with parameter `n_clusters`,
        and possess a `fit_predict` method, which is invoked on data.
      * L -> smallest number of clusters to try
      * K -> biggest number of clusters to try
      * H -> number of resamplings for each cluster number
      * resample_proportion -> percentage to sample.
    """

    def __init__(
        self, n_clusters, K=None, H=100, resample_proportion=0.9, linkage="average", cluster=AgglomerativeClustering
    ):
        super().__init__()
        if (not 0 <= resample_proportion <= 1): # , "proportion has to be between 0 and 1"
            raise Exception
        self.n_clusters = n_clusters
        self.K = K if K else n_clusters
        self.H = H
        self.resample_proportion = resample_proportion
        self.cluster = cluster
        self.linkage = linkage

    def _internal_resample(self, data, proportion):
        """Resamples the data.

        Args:
          * data -> (examples,attributes) format
          * proportion -> percentage to sample.
        """
        resampled_indices = np.random.choice(range(data.shape[0]), size=int(data.shape[0] * proportion), replace=False)
        return resampled_indices, data[resampled_indices, :]

    def fit(self, data):
        """
        Fits a consensus matrix for each number of clusters.

        Args:
          * data -> (examples,attributes) format
        """
        Mk = np.zeros((data.shape[0], data.shape[0]))
        Is = np.zeros((data.shape[0],) * 2)
        for _ in range(self.H):
            resampled_indices, resample_data = self._internal_resample(data, self.resample_proportion)
            Mh = self.cluster(n_clusters=self.K, linkage=self.linkage).fit_predict(resample_data)
            index_mapping = np.array((Mh, resampled_indices)).T
            index_mapping = index_mapping[index_mapping[:, 0].argsort()]
            sorted_ = index_mapping[:, 0]
            id_clusts = index_mapping[:, 1]
            for i in range(self.K):
                ia = bisect.bisect_left(sorted_, i)
                ib = bisect.bisect_right(sorted_, i)
                is_ = id_clusts[ia:ib]
                ids_ = np.array(list(combinations(is_, 2))).T
                if ids_.size != 0:
                    Mk[ids_[0], ids_[1]] += 1
            ids_2 = np.array(list(combinations(resampled_indices, 2))).T
            Is[ids_2[0], ids_2[1]] += 1
        Mk /= Is + 1e-8
        Mk += Mk.T
        Mk[range(data.shape[0]), range(data.shape[0])] = 1
        self.Mk = Mk
        self._is_fitted = True
        return self

    def fit_predict(self, data):
        """Predicts on the consensus matrix, for best found cluster number."""
        return self.cluster(n_clusters=self.n_clusters, linkage=self.linkage).fit_predict(data)



class SOMEstimator(BaseClusterEstimator):
    """Estimate a Self-Organizing Map (SOM) clustering model."""

    def __init__(
        self,
        xdim=10,
        ydim=10,
        rlen=10,
        mst=1,
        alpha=(0.05, 0.01),
        init=False,
        initf=None,
        map=True,
        codes=None,
        importance=None,
        seed=None,
    ):
        super().__init__()
        self.xdim = xdim
        self.ydim = ydim
        self.rlen = rlen
        self.mst = mst
        self.alpha = alpha
        self.init = init
        self.initf = initf
        self.map = map
        self.codes = codes
        self.importance = importance
        self.seed = seed

    def fit(
        self,
        X,
        y=None,
    ):
        """Perform SOM clustering.

        :param inp:  An array of the columns to use for clustering
        :type inp: np.array
        :param xdim: x dimension of SOM
        :type xdim: int
        :param ydim: y dimension of SOM
        :type ydim: int
        :param rlen: Number of times to loop over the training data for each MST
        :type rlen: int
        :param importance: Array with numeric values. Parameters will be scaled
        according to importance
        :type importance: np.array
        """
        codes = self.codes
        xdim = self.xdim
        ydim = self.ydim
        importance = self.importance
        init = self.init
        mst = self.mst
        alpha = self.alpha

        if codes is not None:
            if not ((codes.shape[1] == X.shape[1]) and (codes.shape[0] == xdim * ydim)):     ## removed assert
                print("If codes is not NULL, it should have the same number of columns as the data and the number of rows should correspond with xdim*ydim")
                raise Exception    ## removed assert

        if importance is not None:
            X = np.stack([X[:, i] * importance[i] for i in range(len(importance))], axis=1)

        # Initialize the grid
        grid = [(x, y) for x in range(xdim) for y in range(ydim)]
        n_codes = len(grid)

        if self.seed is not None:
            np.random.seed(self.seed)

        if codes is None:
            if init:
                codes = self.initf(X, xdim, ydim)
            else:
                codes = X[np.random.choice(X.shape[0], n_codes, replace=False), :]

        # Initialize the neighbourhood
        nhbrdist = squareform(pdist(grid, metric="chebyshev"))

        # Initialize the radius
        radius = (np.quantile(nhbrdist, 0.67), 0)
        if mst == 1:
            radius = [radius]
            alpha = [alpha]
        else:
            radius = np.linspace(radius[0], radius[1], num=mst + 1)
            radius = [tuple(radius[i : i + 2]) for i in range(mst)]
            alpha = np.linspace(alpha[0], alpha[1], num=mst + 1)
            alpha = [tuple(alpha[i : i + 2]) for i in range(mst)]

        # Compute the SOM
        for i in range(mst):
            codes = SOM(
                X,
                codes,
                nhbrdist,
                alphas=alpha[i],
                radii=radius[i],
                ncodes=n_codes,
                rlen=self.rlen,
                seed=self.seed,
            )
            if mst != 1:
                nhbrdist: list[list[int]] = _dist_mst(codes)

        clusters, dists = map_data_to_codes(data=X, codes=codes)
        self.codes, self.labels_, self.distances = codes.copy(), clusters, dists
        self._is_fitted = True
        return self

    def predict(self, X, y=None):
        """Predict labels using the model."""
        check_is_fitted(self)
        self.distances = cdist(X, self.codes, metric="euclidean")
        clusters, dists = map_data_to_codes(X, self.codes)
        self.labels_ = clusters.astype(int)
        self.distances = dists
        return self.labels_

    def fit_predict(self, X, y=None):
        """Fit the model and predict labels."""
        self.fit(X)
        return self.predict(X)


def _dist_mst(codes):
    adjacency = cdist(
        codes,
        codes,
        metric="euclidean",
    )
    full_graph = ig.Graph.Weighted_Adjacency(adjacency, mode="undirected", loops=False)
    MST_graph = ig.Graph.spanning_tree(full_graph, weights=full_graph.es["weight"])
    codes = [
        [len(x) - 1 for x in MST_graph.get_shortest_paths(v=i, to=MST_graph.vs.indices, weights=None)]
        for i in MST_graph.vs.indices
    ]
    return codes


class FlowSOMEstimator(BaseFlowSOMEstimator):
    """A class that implements the FlowSOM model."""

    def __init__(
        self,
        cluster_model=SOMEstimator,
        metacluster_model=ConsensusCluster,
        **kwargs,
    ):
        """Initialize the FlowSOMEstimator object."""
        super().__init__(
            cluster_model=cluster_model,
            metacluster_model=metacluster_model,
            **kwargs,
        )




def get_channels(obj, markers: np.ndarray, exact=True):
    """Gets the channels of the provided markers based on a FlowSOM object or an FCS file.

    :param obj: A FlowSOM object or a FCS AnnData object
    :type obj: FlowSOM / AnnData
    :param markers: An array of markers
    :param exact: If True, a strict search is performed. If False, regexps can be used.
    :type exact: boolean
    """
    if not (obj.__class__.__name__ == "FlowSOM") or (isinstance(obj, ad.AnnData)):
        print("Please provide an FCS file or a FlowSOM object")
        raise Exception           ## removed assert
    if obj.__class__.__name__ == "FlowSOM":
        object_markers = np.asarray(
            [re.sub(" <.*", "", pretty_colname) for pretty_colname in obj.mudata["cell_data"].var["pretty_colnames"]]
        )
        object_channels = np.asarray(
            [
                re.sub(r".*<(.*)>.*", r"\1", pretty_colname)
                for pretty_colname in obj.mudata["cell_data"].var["pretty_colnames"]
            ]
        )
    else:
        object_markers = np.asarray(obj.uns["meta"]["channels"]["$PnS"])
        object_channels = np.asarray(obj.uns["meta"]["channels"]["$PnN"])

    channelnames = {}
    for marker in markers:
        if isinstance(marker, int):
            i_channel = [marker]
        else:
            if exact:
                marker = r"^" + marker + r"$"
            i_channel = np.asarray([i for i, m in enumerate(object_markers) if re.search(marker, m) is not None])
        if len(i_channel) != 0:
            for i in i_channel:
                channelnames[object_channels[i]] = object_markers[i]
        else:
            i_channel = np.asarray([i for i, c in enumerate(object_channels) if re.search(marker, c) is not None])
            if len(i_channel) != 0:
                for i in i_channel:
                    channelnames[object_channels[i]] = object_channels[i]
            else:
                raise Exception(f"Marker {marker} could not be found!")
    return channelnames

def get_markers(obj, channels, exact=True):
    """Gets the markers of the provided channels based on a FlowSOM object or an FCS file.

    :param obj: A FlowSOM object or a FCS AnnData object
    :type obj: FlowSOM / AnnData
    :param channels: An array of channels
    :type channels: np.array
    :param exact: If True, a strict search is performed. If False, regexps can be used.
    :type exact: boolean
    """
    if not (obj.__class__.__name__ == "FlowSOM") or (isinstance(obj, ad.AnnData)):
        print("Please provide an FCS file or a FlowSOM object")
        raise Exception        ## removed assert
    if obj.__class__.__name__ == "FlowSOM":
        object_markers = np.asarray(
            [re.sub(" <.*", "", pretty_colname) for pretty_colname in obj.mudata["cell_data"].var["pretty_colnames"]]
        )
        object_channels = np.asarray(
            [
                re.sub(r".*<(.*)>.*", r"\1", pretty_colname)
                for pretty_colname in obj.mudata["cell_data"].var["pretty_colnames"]
            ]
        )
    else:
        object_markers = np.asarray(obj.uns["meta"]["channels"]["$PnS"])
        object_channels = np.asarray(obj.uns["meta"]["channels"]["$PnN"])

    markernames = {}
    for channel in channels:
        if isinstance(channel, int):
            i_marker = [channel]
        else:
            if exact:
                channel = r"^" + channel + r"$"
            i_marker = np.asarray([i for i, c in enumerate(object_channels) if re.search(channel, c) is not None])
        if len(i_marker) != 0:
            for i in i_marker:
                if len(object_markers[i]) == 0:
                    markernames[object_channels[i]] = object_channels[i]
                else:
                    markernames[object_markers[i]] = object_channels[i]
        else:
            i_marker = np.asarray([i for i, m in enumerate(object_markers) if re.search(channel, m) is not None])
            if len(i_marker) != 0:
                for i in i_marker:
                    markernames[object_markers[i]] = object_markers[i]
            else:
                raise Exception(f"Channel {channel} could not be found!")
    return markernames

def read_FCS(filepath):
    """Reads in an FCS file.

    :param filepath: An array containing a full path to the FCS file
    :type filepath: str
    """
    try:
        f = readfcs.read(filepath, reindex=True)
        f.var.n = f.var.n.astype(int)
        f.var = f.var.sort_values(by="n")
        f.uns["meta"]["channels"].index = f.uns["meta"]["channels"].index.astype(int)
        f.uns["meta"]["channels"] = f.uns["meta"]["channels"].sort_index()
    except ValueError:
        f = readfcs.read(filepath, reindex=False)
        markers = {
            str(re.sub("S$", "", re.sub("^P", "", string))): f.uns["meta"][string]
            for string in f.uns["meta"].keys()
            if re.match("^P[0-9]+S$", string)
        }
        fluo_channels = list(markers.keys())
        non_fluo_channels = {
            i: f.uns["meta"]["channels"]["$PnN"][i] for i in f.uns["meta"]["channels"].index if i not in fluo_channels
        }
        index_markers = dict(markers, **non_fluo_channels)
        f.var.rename(index=index_markers, inplace=True)
        f.uns["meta"]["channels"]["$PnS"] = [index_markers[key] for key in f.uns["meta"]["channels"].index]
    return f

def read_csv(filepath, spillover=None, **kwargs):
    """Reads in a CSV file."""
    ff = ad.read_csv(filepath, **kwargs)
    ff.var = pd.DataFrame(
        {"n": range(ff.shape[1]), "channel": ff.var_names, "marker": ff.var_names}, index=ff.var.index
    )
    if spillover is not None:
        ff.uns["meta"]["SPILL"] = pd.read_csv(spillover)
    return ff

class FlowSOM:
    """A class that contains all the FlowSOM data using MuData objects."""

    def __init__(
        self,
        inp,
        n_clusters: int,
        cols_to_use: np.ndarray | None = None,
        model: type[BaseFlowSOMEstimator] = FlowSOMEstimator,
        xdim: int = 10,
        ydim: int = 10,
        rlen: int = 10,
        mst: int = 1,
        alpha: tuple[float, float] = (0.05, 0.01),
        seed: int | None = None,
        mad_allowed=4,
        **kwargs,
    ):
        """Initialize the FlowSOM AnnData object.

        :param inp: An AnnData or filepath to an FCS file
        :param n_clusters: The number of clusters
        :param xdim: The x dimension of the SOM
        :param ydim: The y dimension of the SOM
        :param rlen: Number of times to loop over the training data for each MST
        :param mst: Number of times to loop over the training data for each MST
        :param alpha: The learning rate
        :param seed: The random seed to use
        :param cols_to_use: The columns to use for clustering
        :param mad_allowed: Number of median absolute deviations allowed
        :param model: The model to use
        :param kwargs: Additional keyword arguments. See documentation of the cluster_model and metacluster_model for more information.
        :type kwargs: dict
        """
        self.cols_to_use = cols_to_use
        self.mad_allowed = mad_allowed
        # cluster model params
        self.xdim = xdim
        self.ydim = ydim
        self.rlen = rlen
        self.mst = mst
        self.alpha = alpha
        self.seed = seed
        # metacluster model params
        self.n_clusters = n_clusters

        self.model = model(
            xdim=xdim,
            ydim=ydim,
            rlen=rlen,
            mst=mst,
            alpha=alpha,
            seed=seed,
            n_clusters=n_clusters,
            **kwargs,
        )
        self.mudata = MuData(
            {
                "cell_data": ad.AnnData(),
                "cluster_data": ad.AnnData(),
            }
        )
        logger.debug("Reading input.")
        self.read_input(inp)
        logger.debug("Fitting model: clustering and metaclustering.")
        self.run_model()
        logger.debug("Updating derived values.")
        self._update_derived_values()

    @property
    def cluster_labels(self):
        """Get the cluster labels."""
        if "cell_data" in self.mudata.mod.keys():
            if "clustering" in self.mudata["cell_data"].obs_keys():
                return self.mudata["cell_data"].obs["clustering"]
        return None

    @cluster_labels.setter
    def cluster_labels(self, value):
        """Set the cluster labels."""
        if "cell_data" in self.mudata.mod.keys():
            self.mudata["cell_data"].obs["clustering"] = value
        else:
            raise ValueError("No cell data found in the MuData object.")

    @property
    def metacluster_labels(self):
        """Get the metacluster labels."""
        if "cell_data" in self.mudata.mod.keys():
            if "clustering" in self.mudata["cell_data"].obs_keys():
                return self.mudata["cell_data"].obs["metaclustering"]
        return None

    @metacluster_labels.setter
    def metacluster_labels(self, value):
        """Set the metacluster labels."""
        if "cell_data" in self.mudata.mod.keys():
            self.mudata["cell_data"].obs["metaclustering"] = value
        else:
            raise ValueError("No cell data found in the MuData object.")

    def read_input(
        self,
        inp=None,
        cols_to_use=None,
    ):
        """Converts input to a FlowSOM AnnData object.

        :param inp: A file path to an FCS file or a AnnData FCS file to cluster
        :type inp: str / ad.AnnData
        """
        if cols_to_use is not None:
            self.cols_to_use = cols_to_use
        if isinstance(inp, str):
            if inp.endswith(".csv"):
                adata = read_csv(inp)
            elif inp.endswith(".fcs"):
                adata = read_FCS(inp)
        elif isinstance(inp, ad.AnnData):
            adata = inp
        else:
            adata = ad.AnnData(inp)
        self.mudata.mod["cell_data"] = adata
        self.clean_anndata()
        if self.cols_to_use is not None:
            self.cols_to_use = list(get_channels(self, self.cols_to_use).keys())
        if self.cols_to_use is None:
            self.cols_to_use = self.mudata["cell_data"].var_names.values

    def clean_anndata(self):
        """Cleans marker and channel names."""
        adata = self.get_cell_data()
        if issparse(adata.X):
            # sparse matrices are not supported
            adata.X = adata.X.todense()
        if "channel" not in adata.var.keys():
            adata.var["channel"] = np.asarray(adata.var_names)
        channels = np.asarray(adata.var["channel"])
        if "marker" not in adata.var.keys():
            adata.var["marker"] = np.asarray(adata.var_names)
        markers = np.asarray(adata.var["marker"])
        isnan_markers = [str(marker) == "nan" or len(marker) == 0 for marker in markers]
        markers[isnan_markers] = channels[isnan_markers]
        pretty_colnames = [markers[i] + " <" + channels[i] + ">" for i in range(len(markers))]
        adata.var["pretty_colnames"] = np.asarray(pretty_colnames, dtype=str)
        adata.var_names = np.asarray(channels)
        adata.var["markers"] = np.asarray(markers)
        adata.var["channels"] = np.asarray(channels)
        self.mudata.mod["cell_data"] = adata
        return self.mudata

    def run_model(self):
        """Run the model on the input data."""
        X = self.mudata["cell_data"][:, self.cols_to_use].X
        self.model.fit_predict(X)

    def _update_derived_values(self):
        """Update the derived values such as median values and CV values."""
        self.mudata["cell_data"].obs["clustering"] = self.model.cluster_labels
        self.mudata["cell_data"].obs["distance_to_bmu"] = self.model.distances
        self.mudata["cell_data"].uns["n_nodes"] = self.xdim * self.ydim
        self.mudata["cell_data"].var["cols_used"] = np.array(
            col in self.cols_to_use for col in self.mudata["cell_data"].var_names
        )
        self.mudata["cell_data"].uns["n_metaclusters"] = self.n_clusters
        self.mudata["cell_data"].obs["metaclustering"] = self.model.metacluster_labels
        # get dataframe of intensities and cluster labels on cell level
        df = self.mudata["cell_data"].to_df()  # [self.adata.X[:, 0].argsort()]
        df = pd.concat([self.mudata["cell_data"].obs["clustering"], df], axis=1)
        n_nodes = self.mudata["cell_data"].uns["n_nodes"]

        # get median values per cluster on cell level
        cluster_median_values = df.groupby("clustering").median()
        # make sure cluster_median_values is of length n_nodes
        # some clusters might be empty when fitting on new data
        missing_clusters = set(range(n_nodes)) - set(cluster_median_values.index)
        if len(missing_clusters) > 0:
            cluster_median_values = cluster_median_values.reindex(
                list(cluster_median_values.index) + list(missing_clusters)
            )
        cluster_median_values.sort_index(inplace=True)
        # create values for cluster_data
        cluster_mudata = ad.AnnData(cluster_median_values.values)
        cluster_mudata.var_names = self.mudata["cell_data"].var_names
        # standard deviation of cells per cluster
        sd_values = []
        # coefficient of variation of cells per cluster
        cv_values = []
        # median absolute deviation of cells per cluster
        mad_values = []
        # percentages of cells of cells per cluster
        pctgs = {}
        for cl in range(n_nodes):
            cluster_data = df[df["clustering"] == cl]
            # if cluster is empty, set values to nan for all markers
            if cluster_data.shape[0] == 0:
                cluster_mudata.X[cl, :] = np.nan
                cv_values.append([np.nan] * cluster_data.shape[1])
                sd_values.append([np.nan] * cluster_data.shape[1])
                mad_values.append([np.nan] * cluster_data.shape[1])
                pctgs[cl] = 0
                continue
            means = np.nanmean(cluster_data, axis=0)
            means[means == 0] = np.nan
            cv_values.append(np.divide(np.nanstd(cluster_data, axis=0), means))
            sd_values.append(np.nanstd(cluster_data, axis=0))
            mad_values.append(median_abs_deviation(cluster_data, axis=0, nan_policy="omit"))
            pctgs[cl] = cluster_data.shape[0]

        cluster_mudata.obsm["cv_values"] = np.vstack(cv_values)
        cluster_mudata.obsm["sd_values"] = np.vstack(sd_values)
        cluster_mudata.obsm["mad_values"] = np.vstack(mad_values)
        pctgs = np.divide(list(pctgs.values()), np.sum(list(pctgs.values())))
        cluster_mudata.obs["percentages"] = pctgs
        cluster_mudata.obs["metaclustering"] = self.model._y_codes
        cluster_mudata.uns["xdim"] = self.xdim
        cluster_mudata.uns["ydim"] = self.ydim
        cluster_mudata.obsm["codes"] = self.model.codes
        cluster_mudata.obsm["grid"] = np.array([(x, y) for x in range(self.xdim) for y in range(self.ydim)])
        cluster_mudata.uns["outliers"] = self.test_outliers(mad_allowed=self.mad_allowed).reset_index()
        # update metacluster values

        self.mudata.mod["cluster_data"] = cluster_mudata
        df = self.mudata["cell_data"].X[self.mudata["cell_data"].X[:, 0].argsort()]
        df = np.c_[self.mudata["cell_data"].obs["metaclustering"], df]
        metacluster_median_values: pd.DataFrame = pd.DataFrame(df).groupby(0).median()
        self.mudata["cluster_data"].uns["metacluster_MFIs"] = metacluster_median_values
        self.build_MST()

    def build_MST(self):
        """Make a minimum spanning tree."""
        check_is_fitted2(self.model)
        adjacency = cdist(
            self.model.codes,
            self.model.codes,
            metric="euclidean",
        )
        full_graph = ig.Graph.Weighted_Adjacency(adjacency, mode="undirected", loops=False)
        MST_graph = ig.Graph.spanning_tree(full_graph, weights=full_graph.es["weight"])
        MST_graph.es["weight"] /= np.mean(MST_graph.es["weight"])
        layout = MST_graph.layout_kamada_kawai(
            seed=MST_graph.layout_grid(), maxiter=50 * MST_graph.vcount(), kkconst=max([MST_graph.vcount(), 1])
        ).coords
        self.mudata["cluster_data"].obsm["layout"] = np.array(layout)
        self.mudata["cluster_data"].uns["graph"] = MST_graph
        return self

    def _dist_mst(self, codes):
        adjacency = cdist(
            codes,
            codes,
            metric="euclidean",
        )
        full_graph = ig.Graph.Weighted_Adjacency(adjacency, mode="undirected", loops=False)
        MST_graph = ig.Graph.spanning_tree(full_graph, weights=full_graph.es["weight"])
        codes = [
            [len(x) - 1 for x in MST_graph.get_shortest_paths(v=i, to=MST_graph.vs.indices, weights=None)]
            for i in MST_graph.vs.indices
        ]
        return codes

    def metacluster(self, n_clusters=None):
        """Perform a (consensus) hierarchical clustering.

        :param n_clusters: The number of metaclusters
        :type n_clusters: int
        """
        if n_clusters is None:
            n_clusters = self.n_clusters
            self.model.set_n_clusters(n_clusters)
        self.model.metacluster_model.fit_predict(self.model.codes)
        return self

    def test_outliers(self, mad_allowed: int = 4, fsom_reference=None, plot_file=None, channels=None):
        """Test if any cells are too far from their cluster centers.

        :param mad_allowed: Number of median absolute deviations allowed. Default = 4.
        :type mad_allowed: int
        :param fsom_reference: FlowSOM object to use as reference. If NULL (default), the original fsom object is used.
        :type fsom_reference: FlowSOM
        :param plot_file:
        :type plot_file:
        :param channels:If channels are given, the number of outliers in the original space for those channels will be calculated and added to the final results table.
        :type channels: np.array
        """
        if fsom_reference is None:
            fsom_reference = self
        cell_cl = fsom_reference.mudata["cell_data"].obs["clustering"]
        distance_to_bmu = fsom_reference.mudata["cell_data"].obs["distance_to_bmu"]
        distances_median = [
            np.median(distance_to_bmu[cell_cl == cl + 1]) if len(distance_to_bmu[cell_cl == cl + 1]) > 0 else 0
            for cl in range(fsom_reference.mudata["cell_data"].uns["n_nodes"])
        ]

        distances_mad = [
            median_abs_deviation(distance_to_bmu[cell_cl == cl + 1])
            if len(distance_to_bmu[cell_cl == cl + 1]) > 0
            else 0
            for cl in range(fsom_reference.mudata["cell_data"].uns["n_nodes"])
        ]
        thresholds = np.add(distances_median, np.multiply(mad_allowed, distances_mad))

        max_distances_new = [
            np.max(
                self.mudata["cell_data"].obs["distance_to_bmu"][self.mudata["cell_data"].obs["clustering"] == cl + 1]
            )
            if len(
                self.mudata["cell_data"].obs["distance_to_bmu"][self.mudata["cell_data"].obs["clustering"] == cl + 1]
            )
            > 0
            else 0
            for cl in range(self.mudata["cell_data"].uns["n_nodes"])
        ]
        distances = [
            self.mudata["cell_data"].obs["distance_to_bmu"][self.mudata["cell_data"].obs["clustering"] == cl + 1]
            for cl in range(self.mudata["cell_data"].uns["n_nodes"])
        ]
        outliers = [sum(distances[i] > thresholds[i]) for i in range(len(distances))]

        result = pd.DataFrame(
            {
                "median_dist": distances_median,
                "median_absolute_deviation": distances_mad,
                "threshold": thresholds,
                "number_of_outliers": outliers,
                "maximum_outlier_distance": max_distances_new,
            }
        )

        if channels is not None:
            outliers_dict = {}
            codes = fsom_reference.mudata["cluster_data"]().obsm["codes"]
            data = fsom_reference.mudata["cell_data"].X
            channels = list(get_channels(fsom_reference, channels).keys())
            for channel in channels:
                channel_i = np.where(fsom_reference.mudata["cell_data"].var_names == channel)[0][0]
                distances_median_channel = [
                    np.median(np.abs(np.subtract(data[cell_cl == cl + 1, channel_i], codes[cl, channel_i])))
                    if len(data[cell_cl == cl + 1, channel_i]) > 0
                    else 0
                    for cl in range(fsom_reference.mudata["cell_data"].uns["n_nodes"])
                ]
                distances_mad_channel = [
                    median_abs_deviation(np.abs(np.subtract(data[cell_cl == cl + 1, channel_i], codes[cl, channel_i])))
                    if len(data[cell_cl == cl + 1, channel_i]) > 0
                    else 0
                    for cl in range(fsom_reference.mudata["cell_data"].uns["n_nodes"])
                ]
                thresholds_channel = np.add(distances_median_channel, np.multiply(mad_allowed, distances_mad_channel))

                distances_channel = [
                    np.abs(
                        np.subtract(
                            self.mudata["cell_data"].X[self.mudata["cell_data"].obs["clustering"] == cl + 1, channel_i],
                            fsom_reference.mudata["cell_data"].uns["n_nodes"][cl, channel_i],
                        )
                    )
                    for cl in range(self.mudata["cell_data"].uns["n_nodes"])
                ]
                outliers_channel = [
                    sum(distances_channel[i] > thresholds_channel[i]) for i in range(len(distances_channel))
                ]
                outliers_dict[list(get_markers(self, [channel]).keys())[0]] = outliers_channel
            result_channels = pd.DataFrame(outliers_dict)
            result = result.join(result_channels)
        return result

    def new_data(self, inp, mad_allowed=4):
        """Map new data to a FlowSOM grid.

        :param inp: An anndata or filepath to an FCS file
        :type inp: ad.AnnData / str
        :param mad_allowed: A warning is generated if the distance of the new
        data points to their closest cluster center is too big. This is computed
        based on the typical distance of the points from the original dataset
        assigned to that cluster, the threshold being set to median +
        madAllowed * MAD. Default is 4.
        :type mad_allowed: int
        """
        fsom_new = copy.deepcopy(self)
        fsom_new.read_input(inp)
        fsom_new.mad_allowed = mad_allowed
        X = fsom_new.get_cell_data()[:, self.cols_to_use].X
        fsom_new.model.predict(X)
        fsom_new._update_derived_values()
        return fsom_new

    def subset(self, ids):
        """Take a subset from a FlowSOM object.

        :param ids: An array of ids to subset
        :type ids: np.array
        """
        fsom_subset = copy.deepcopy(self)
        fsom_subset.mudata.mod["cell_data"] = fsom_subset.mudata["cell_data"][ids, :].copy()
        fsom_subset.model.subset(ids)
        fsom_subset._update_derived_values()
        return fsom_subset

    def get_cell_data(self):
        """Get the cell data."""
        return self.mudata["cell_data"]

    def get_cluster_data(self):
        """Get the cluster data."""
        return self.mudata["cluster_data"]


def flowsom_clustering(inp: ad.AnnData, cols_to_use=None, n_clusters=10, xdim=10, ydim=10, **kwargs):
    """Perform FlowSOM clustering on an anndata object and returns the anndata object.

    The FlowSOM clusters and metaclusters are added as variable.

    :param inp: An anndata or filepath to an FCS file
    :type inp: ad.AnnData / str
    """
    fsom = FlowSOM(inp.copy(), cols_to_use=cols_to_use, n_clusters=n_clusters, xdim=xdim, ydim=ydim, **kwargs)
    inp.obs["FlowSOM_clusters"] = fsom.mudata["cell_data"].obs["clustering"]
    inp.obs["FlowSOM_metaclusters"] = fsom.mudata["cell_data"].obs["metaclustering"]
    d = kwargs
    d["cols_to_use"] = cols_to_use
    d["n_clusters"] = n_clusters
    d["xdim"] = xdim
    d["ydim"] = ydim
    inp.uns["FlowSOM"] = d
    return inp

################################################ Added 11-21-24 --> the code (also copied from the FlowSOM package) for plotting star plots
## Uncertain of specific edits to the original code, but any edits that were applied were to allow this code to function independently of the rest of the
## FlowSOM package. 
## Certainly modifications occurred in the process of compiling the various portions of the original package needed for this function into this one script

##>>## 3-21-25 modification: moved imports to the top, removed redundant import

def FlowSOM_colors():
    """Colormap of default FlowSOM colors."""
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "FlowSOM_colors",
        ["#00007F", "#0000E1", "#007FFF", "#00E1E1", "#7FFF7F", "#E1E100", "#FF7F00", "#E10000", "#7F0000"],
    )
    return cmap

def gg_color_hue():
    """Colormap of default ggplot colors."""
    cmap = matplotlib.colors.ListedColormap(
        ["#F8766D", "#D89000", "#A3A500", "#39B600", "#00BF7D", "#00BFC4", "#00B0F6", "#9590FF", "#E76BF3", "#FF62BC"]
    )
    return cmap

def add_legend(
    fig, ax, data, title, cmap, location="best", orientation="horizontal", bbox_to_anchor=None, categorical=True
):
    if categorical:
        unique_data = sorted(np.unique(data))
        colors = cmap(np.linspace(0, 1, len(unique_data)))
        legend_elements = [
            Line2D([0], [0], marker="o", color="w", label=unique_data[i], markerfacecolor=colors[i], markersize=5)
            for i in range(len(unique_data))
        ]
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        legend = plt.legend(
            handles=legend_elements,
            loc=location,
            frameon=False,
            title=title,
            bbox_to_anchor=bbox_to_anchor,  # (1, 0.5),
            fontsize=5,
            title_fontsize=6,
        )
        plt.gca().add_artist(legend)
    else:
        norm = matplotlib.colors.Normalize(vmin=min(data), vmax=max(data))
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array(data)
        fig.colorbar(sm, ax=ax, orientation=orientation, shrink=0.4, label=title)
    return ax, fig


def plot_FlowSOM(
    fsom,
    view: str = "MST",
    background_values: np.array | None = None,
    background_cmap=gg_color_hue(),
    background_size=1.5,
    equal_background_size=False,
    node_sizes: np.array | None = None,
    max_node_size: int = 1,
    ref_node_size: int | None = None,
    equal_node_size: bool = False,
):
    """Plots the base layer of a FlowSOM result.

    :param fsom: A FlowSOM object
    :type fsom: A object from the class FlowSOM
    :param view: The view you want to plot, can be either "grid" for
    a grid view or "MST" for a minimum spanning tree view
    :type view: str
    :param background_values: The background values to be plotted
    :type background_values: np.array
    :param background_cmap: A colormap for the background colors
    :type background_cmap: Colormap
    :param background_size: The size of the background nodes relative to the nodes
    :type background_size: float
    :param equal_background_size: If True the background nodes will be equally sized
    :type equal_background_size: boolean
    :param node_sizes: An array with the node sizes. Will be scaled between 0
    and max_node_size and transformed with a sqrt. Default is the percentages
    :type node_sizes: np.array
    :param max_node_size: The maximum node size
    :type max_node_size: float
    :param ref_node_size: Reference for node size against which the node sizes
    will be scaled. Default is the maximum of the node sizes
    :type ref_node_size: float
    :param equal_node_size: If True the all the nodes will be equally sized to
    max_node_size
    :type equal_node_size: boolean
    :param title: Title for the plot
    :type title: str
    """
    # Initialization
    nNodes = fsom.get_cell_data().uns["n_nodes"]
    isEmpty = fsom.get_cluster_data().obs["percentages"] == 0

    # Warnings
    if node_sizes is not None:
        if not (nNodes == len(node_sizes)):
            print('Length of "node_sizes" should be equal to number of clusters in FlowSOM object')
            raise Exception  ## removed assert

    if background_values is not None:
        if not (background_values.shape[0] == fsom.mudata["cell_data"].uns["n_nodes"]):
            print("Length of background_values should be equal to number of clusters in FlowSOM object")
            raise Exception  ## removed assert

    # Node sizes
    node_sizes = parse_node_sizes(
        fsom,
        view=view,
        node_sizes=node_sizes,
        max_node_size=max_node_size,
        ref_node_size=ref_node_size,
        equal_node_size=equal_node_size,
    )
    node_sizes[isEmpty] = min([0.05, node_sizes.max()])

    # Layout
    layout = fsom.get_cluster_data().obsm["layout"] if view == "MST" else fsom.get_cluster_data().obsm["grid"]

    # Start plot
    fig, ax = plt.subplots()

    # Add background
    if background_values is not None:
        if equal_background_size:
            background_size = np.repeat(np.max(node_sizes) * background_size, len(background_values))
        else:
            background_size = (
                parse_node_sizes(
                    fsom,
                    view=view,
                    node_sizes=None,
                    max_node_size=max_node_size,
                    ref_node_size=ref_node_size,
                    equal_node_size=False,
                )
                * background_size
            )
        background = add_nodes(layout, background_size)
        b = mc.PatchCollection(background, cmap=background_cmap)
        if background_values.dtype == np.float64 or background_values.dtype == np.int64:
            b.set_array(background_values)
        else:
            b.set_array(pd.get_dummies(background_values).values.argmax(1))
        b.set_alpha(0.5)
        b.set_zorder(1)
        ax.add_collection(b)
        ax, fig = add_legend(
            fig=fig,
            ax=ax,
            data=background_values,
            title="Background",
            cmap=background_cmap,
            location="lower left",
            bbox_to_anchor=(1.04, 0),
        )

    # Add MST
    if view == "MST":
        e = add_MST(fsom)
        MST = mc.LineCollection(e)
        MST.set_edgecolor("black")
        MST.set_linewidth(0.2)
        MST.set_zorder(0)
        ax.add_collection(MST)

    # Add nodes
    nodes = add_nodes(layout, node_sizes)
    n = mc.PatchCollection(nodes)
    n.set_facecolor(["#C7C7C7" if tf else "#FFFFFF" for tf in isEmpty])  # "white")
    n.set_edgecolor("black")
    n.set_linewidth(0.1)
    n.set_zorder(2)
    ax.add_collection(n)

    return fig, ax, layout, node_sizes


def plot_star_legend(fig, ax, markers, coords=(0, 0), cmap=FlowSOM_colors(), max_star_height=1, star_height=1):
    """Function makes the legend of the FlowSOM star plot.

    :param markers:
    :type markers:
    :param cmap:
    :type cmap:
    :param star_height:
    :type star_height:
    """
    n_markers = len(markers)
    if isinstance(star_height, int) | isinstance(star_height, float):
        star_height = np.repeat(star_height, len(markers)).tolist()
    else:
        if not (len(star_height) == n_markers):
            print("Make sure star_height is an array with the same length as markers")
            raise Exception  # removed assert
    star_height = np.divide(star_height, max(star_height)) * max_star_height
    x = 2 * np.pi / (n_markers * 2)
    y = 2 * np.pi / n_markers
    circular_coords = np.linspace(start=x, stop=x + (n_markers - 1) * y, num=n_markers)
    segments = np.column_stack(
        (
            markers,
            [np.cos(x) * max_star_height for x in circular_coords],
            [np.sin(x) * max_star_height for x in circular_coords],
            [1.1 if i >= 0 else -1.1 for i in np.cos(circular_coords)],
            np.repeat(None, len(markers)),
            range(len(markers)),
        )
    )
    n_left_right = segments[:, 1] >= 0
    n_left_right = pd.crosstab(n_left_right, columns="x")
    if n_left_right.shape[0] != 1:
        by = 1 if len(markers) <= 8 else 0.65
        left = np.linspace(start=0, stop=(n_left_right.x.iloc[0] - 1) * by, num=n_left_right.x.iloc[0])
        right = np.multiply(
            -1, np.linspace(start=0, stop=(n_left_right.x.iloc[1] - 1) * by, num=n_left_right.x.iloc[1])
        )
        segments_left = segments[segments[:, 1] < 0, :]
        segments_left = segments_left[segments_left[:, 2].argsort()]
        segments_right = segments[segments[:, 1] >= 0]
        segments_right = segments_right[segments_right[:, 2].argsort()[::-1]]
        segments = np.concatenate((segments_right, segments_left))
        segments[segments[:, 1] < 0, 4] = left - sum(left) / len(left)
        segments[segments[:, 1] >= 0, 4] = right - sum(right) / len(right)
        segments = segments[segments[:, 5].argsort()]
        segments = np.delete(segments, 5, axis=1)
    else:
        segments[:, 4] = -1
        segments[:, 1] = segments[:, 1] * -1
        segments[:, 3] = segments[:, 3] * -1
    horizontal_lines = np.column_stack(
        (
            segments[:, 0],
            segments[:, 3],
            segments[:, 4],
            np.add(segments[:, 3], [0.5 if i >= 0 else -0.5 for i in segments[:, 3]]),
            segments[:, 4],
        )
    )
    segments = np.concatenate((segments, horizontal_lines))
    x = np.add(horizontal_lines[:, 3], [0.3 if i >= 0 else -0.3 for i in horizontal_lines[:, 3]])
    y = np.asarray(horizontal_lines[:, 4])
    x_coord = coords[0] - min(x) + 0.2 * len(max(markers, key=len))
    dfLabels = np.column_stack((x + x_coord, y + coords[1], ["left" if i >= 0 else "right" for i in x]))
    lines = []
    for row in segments:
        lines += [[(row[1] + x_coord, row[2] + coords[1]), (row[3] + x_coord, row[4] + coords[1])]]
    e = mc.LineCollection(lines, cmap=cmap, capstyle="round", joinstyle="round")
    e.set_array(range(n_markers))
    e.set_linewidth(1)
    e.set_zorder(0)
    ax.add_collection(e)
    ax = add_text(ax, dfLabels, markers, ha=dfLabels[:, 2], text_size=5)
    l = mc.PatchCollection(add_wedges(np.array((x_coord, coords[1])), star_height), cmap=cmap)
    l.set_array(range(n_markers))
    l.set_edgecolor("black")
    l.set_linewidth(0.1)
    ax.add_collection(l)
    ax.axis("equal")

    return fig, ax


def scale_star_heights(median_values, node_sizes):
    if isinstance(node_sizes, pd.Series):
        node_sizes = node_sizes.to_numpy()
    max_all_nodes = median_values[~np.isnan(median_values)].max()
    min_all_nodes = median_values[~np.isnan(median_values)].min()
    scaled_row = [
        np.divide(np.multiply(np.subtract(row, min_all_nodes), node_sizes[i]), max_all_nodes - min_all_nodes)
        for i, row in enumerate(median_values)
    ]
    return np.vstack(scaled_row)


def parse_node_sizes(fsom, view="MST", node_sizes=None, max_node_size=1, ref_node_size=None, equal_node_size=False):
    node_sizes = fsom.get_cluster_data().obs["percentages"] if node_sizes is None else node_sizes
    ref_node_size = max(node_sizes) if ref_node_size is None else ref_node_size
    layout = fsom.get_cluster_data().obsm["layout"] if view == "MST" else fsom.get_cluster_data().obsm["grid"]
    auto_node_size = auto_max_node_size(layout, 1 if view == "MST" else -0.3)  # overlap
    max_node_size = auto_node_size * max_node_size

    if equal_node_size:
        node_sizes = np.repeat(max_node_size, len(node_sizes))
    n_nodes = len(node_sizes)
    if len(np.unique(node_sizes)) == 1:
        return np.repeat(max_node_size, n_nodes)
    scaled_node_size = np.sqrt(np.multiply((np.divide(node_sizes, ref_node_size)), np.square(max_node_size)))
    return scaled_node_size


def auto_max_node_size(layout, overlap):
    overlap = 1 + overlap
    min_distance = min(pdist(layout))
    return min_distance / 2 * overlap


def add_text(ax, layout, text, text_size=25, text_color="black", ha=None, va=None):
    if isinstance(text, pd.Series):
        text = text.to_numpy()
    if va is None:
        va = ["center"]
    if ha is None:
        ha = ["right"]
    if len(ha) == 1:
        ha = np.repeat(ha, len(text))
    if len(va) == 1:
        va = np.repeat(va, len(text))
    for i, row in enumerate(layout):
        ax.text(row[0], row[1], text[i], size=text_size, ha=ha[i], va=va[i], c=text_color, clip_on=False)
    return ax


def add_MST(fsom):
    edges = parse_edges(fsom)
    lines = [[(row[0], row[1]), (row[2], row[3])] for row in edges]
    return lines


def parse_edges(fsom):
    edge_list = fsom.get_cluster_data().uns["graph"].get_edgelist()
    coords = fsom.get_cluster_data().obsm["layout"]
    segment_plot = [
        (coords[nodeID[0], 0], coords[nodeID[0], 1], coords[nodeID[1], 0], coords[nodeID[1], 1]) for nodeID in edge_list
    ]
    return np.asarray(segment_plot, dtype=np.float32)


def add_nodes(layout, heights):
    if isinstance(heights, pd.Series):
        heights = heights.to_numpy()
    patches = [Circle((row[0], row[1]), heights[i]) for i, row in enumerate(layout)]
    return patches


def add_stars(layout, heights):
    if isinstance(heights, pd.Series):
        heights = heights.to_numpy()
    patches = np.hstack([add_wedges((row[0], row[1]), heights[i, :]) for i, row in enumerate(layout)])
    return patches


def add_wedges(coord, heights, angles=None):
    if isinstance(heights, pd.Series):
        heights = heights.to_numpy()
    if angles is None:
        part = 360 / len(heights)
        angles = np.arange(0, 360.01, part)
    stars = [Wedge(coord, heights[i], angles[i], angles[i + 1], edgecolor="black") for i in range(len(angles) - 1)]
    return stars

def plot_stars(fsom, markers=None, cmap=FlowSOM_colors(), title=None, **kwargs):
    """Plot star charts.

    :param fsom: A FlowSOM object
    :type fsom: FlowSOM
    :param markers: Markers, channels or indices to plot
    :type markers: np.array
    :param cmap: A colormap to use
    :type cmap:
    :param title: Title of the plot
    :type title: str
    """
    if markers is None:
        markers_bool = fsom.get_cell_data().var["cols_used"]
        markers = fsom.get_cell_data().var_names[markers_bool]
    if not isinstance(markers, np.ndarray):
        markers = np.asarray(markers)
    pretty_markers = fsom.get_cell_data()[:, markers].var["pretty_colnames"]
    fig, ax, layout, scaled_node_size = plot_FlowSOM(fsom, **kwargs)
    max_x, max_y = np.max(layout, axis=0)
    fig, ax = plot_star_legend(
        fig,
        ax,
        pretty_markers,
        coords=(max_x, max_y),
        cmap=cmap,
        max_star_height=max(scaled_node_size) * 3,
        star_height=1,
    )
    data = fsom.get_cluster_data()[:, markers].X
    heights = scale_star_heights(data, scaled_node_size)
    s = mc.PatchCollection(add_stars(layout, heights), cmap=cmap)
    s.set_array(range(data.shape[1]))
    s.set_edgecolor("black")
    s.set_linewidth(0.1)
    s.set_zorder(3)
    ax.add_collection(s)
    ax.axis("equal")
    plt.axis("off")
    if title is not None:
        plt.title(title)
    return fig