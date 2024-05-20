# -*- coding: utf-8 -*-
"""
Common (simple) affinity matrices
"""

# Author: Hugues Van Assel <vanasselhugues@gmail.com>
#
# License: BSD 3-Clause License

from abc import ABC, abstractmethod

from torchdr.utils import pairwise_distances, normalize_matrix, to_torch


class Affinity(ABC):
    """
    Base class for affinity matrices.
    """

    def __init__(self, metric="euclidean", device="cuda", keops=True, verbose=True):
        self.log_ = {}
        self.metric = metric
        self.device = device
        self.keops = keops
        self.verbose = verbose

    @abstractmethod
    def fit(self, X):
        self.data_ = to_torch(X, device=self.device, verbose=self.verbose)
        return self

    def _ground_cost_matrix(self, X):
        return pairwise_distances(X, metric=self.metric, keops=self.keops)

    def fit_transform(self, X):
        """
        Computes the affinity matrix from input data X.
        """
        self.fit(X)
        assert hasattr(
            self, "affinity_matrix_"
        ), "[TorchDR] Affinity (Error) : affinity_matrix_ should be computed "
        "in fit method."
        return self.affinity_matrix_  # type: ignore


class ScalarProductAffinity(Affinity):
    def __init__(self, device="cuda", keops=True, verbose=True, centering=False):
        super().__init__(metric="angular", device=device, keops=keops, verbose=verbose)
        self.centering = centering

    def fit(self, X):
        super().fit(X)
        if self.centering:
            self.data_ = self.data_ - self.data_.mean(0)
        self.affinity_matrix_ = -self._ground_cost_matrix(self.data_)


class LogAffinity(Affinity):
    """Computes an affinity matrix from an affinity matrix in log space."""

    def __init__(self, metric="euclidean", device="cuda", keops=True, verbose=True):
        super().__init__(metric=metric, device=device, keops=keops, verbose=verbose)

    def fit_transform(self, X, log=False):
        self.fit(X)
        assert hasattr(
            self, "log_affinity_matrix_"
        ), "[TorchDR] Affinity (Error) : log_affinity_matrix_ should be computed "
        "in  fit method of a LogAffinity."

        if log:  # return the log of the affinity matrix
            return self.log_affinity_matrix_  # type: ignore
        else:
            if not hasattr(self, "affinity_matrix_"):
                self.affinity_matrix_ = self.log_affinity_matrix_.exp()  # type: ignore
            return self.affinity_matrix_


class GibbsAffinity(LogAffinity):
    def __init__(
        self,
        sigma=1.0,
        dim_normalization=(0, 1),
        metric="euclidean",
        device=None,
        keops=True,
        verbose=True,
    ):
        super().__init__(metric=metric, device=device, keops=keops, verbose=verbose)
        self.sigma = sigma
        self.dim_normalization = dim_normalization

    def fit(self, X):
        super().fit(X)
        C = self._ground_cost_matrix(self.data_)
        log_P = -C / self.sigma
        self.log_affinity_matrix_ = normalize_matrix(
            log_P, dim=self.dim_normalization, log=True
        )


class StudentAffinity(LogAffinity):
    def __init__(
        self,
        degrees_of_freedom=1,
        dim_normalization=(0, 1),
        metric="euclidean",
        device=None,
        keops=True,
        verbose=True,
    ):
        super().__init__(metric=metric, device=device, keops=keops, verbose=verbose)
        self.dim_normalization = dim_normalization
        self.degrees_of_freedom = degrees_of_freedom

    def fit(self, X):
        super().fit(X)
        C = self._ground_cost_matrix(self.data_)
        C /= self.degrees_of_freedom
        C += 1.0
        log_P = -0.5 * (self.degrees_of_freedom + 1) * C.log()
        self.log_affinity_matrix_ = normalize_matrix(
            log_P, dim=self.dim_normalization, log=True
        )
