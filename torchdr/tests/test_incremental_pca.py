"""Tests for incremental PCA."""

# Author: @sirluk
#
# License: BSD 3-Clause License

import pytest
import torch
from numpy.testing import assert_allclose
from sklearn import datasets
from sklearn.datasets import load_digits
from sklearn.decomposition import IncrementalPCA as SkIncrementalPCA
from sklearn.model_selection import train_test_split
from torch.testing import assert_close

from torchdr import IncrementalPCA

torch.manual_seed(1999)

iris = datasets.load_iris()


def test_incremental_pca():
    # Incremental PCA on dense arrays.
    n_components = 2
    X = torch.tensor(iris.data, dtype=torch.float32)
    batch_size = X.shape[0] // 3
    ipca = IncrementalPCA(n_components=n_components, batch_size=batch_size)
    ipca.fit(X)
    X_transformed = ipca.transform(X)

    # PCA
    U, S, Vh = torch.linalg.svd(X - torch.mean(X, dim=0))
    max_abs_rows = torch.argmax(torch.abs(Vh), dim=1)
    signs = torch.sign(Vh[range(Vh.shape[0]), max_abs_rows])
    Vh *= signs.view(-1, 1)
    explained_variance = S**2 / (X.size(0) - 1)
    explained_variance_ratio = explained_variance / explained_variance.sum()

    assert X_transformed.shape == (X.shape[0], 2)
    assert_close(
        ipca.explained_variance_ratio_.sum().item(),
        explained_variance_ratio[:n_components].sum().item(),
        rtol=1e-3,
        atol=1e-3,
    )


def test_incremental_pca_check_projection():
    # Test that the projection of data is correct.
    n, p = 100, 3
    X = torch.randn(n, p, dtype=torch.float64) * 0.1
    X[:10] += torch.tensor([3, 4, 5])
    Xt = 0.1 * torch.randn(1, p, dtype=torch.float64) + torch.tensor([3, 4, 5])

    # Get the reconstruction of the generated data X
    # Note that Xt has the same "components" as X, just separated
    # This is what we want to ensure is recreated correctly
    Yt = IncrementalPCA(n_components=2).fit(X).transform(Xt)

    # Normalize
    Yt /= torch.sqrt((Yt**2).sum())

    # Make sure that the first element of Yt is ~1, this means
    # the reconstruction worked as expected
    assert_close(torch.abs(Yt[0][0]).item(), 1.0, atol=1e-1, rtol=1e-1)


def test_incremental_pca_validation():
    # Test that n_components is <= n_features.
    X = torch.tensor([[0, 1, 0], [1, 0, 0]])
    n_samples, n_features = X.shape
    n_components = 4
    with pytest.raises((ValueError, AssertionError)):
        IncrementalPCA(n_components, batch_size=10).fit(X)

    # Tests that n_components is also <= n_samples.
    n_components = 3
    with pytest.raises((ValueError, AssertionError)):
        IncrementalPCA(n_components=n_components).partial_fit(X)


def test_n_componentsnone():
    # Ensures that n_components == None is handled correctly
    for n_samples, n_features in [(50, 10), (10, 50)]:
        X = torch.rand(n_samples, n_features)
        ipca = IncrementalPCA(n_components=None)

        # First partial_fit call, ipca.n_components is inferred from
        # min(X.shape)
        ipca.partial_fit(X)
        assert ipca.n_components == min(X.shape)


def test_incremental_pca_num_features_change():
    # Test that changing n_components will raise an error.
    n_samples = 100
    X = torch.randn(n_samples, 20)
    X2 = torch.randn(n_samples, 50)
    ipca = IncrementalPCA(n_components=None)
    ipca.fit(X)
    with pytest.raises(ValueError):
        ipca.partial_fit(X2)


def test_incremental_pca_batch_signs():
    # Test that components_ sign is stable over batch sizes.
    n_samples = 100
    n_features = 3
    X = torch.randn(n_samples, n_features)
    all_components = []
    batch_sizes = torch.arange(10, 20)
    for batch_size in batch_sizes:
        ipca = IncrementalPCA(n_components=None, batch_size=batch_size).fit(X)
        all_components.append(ipca.components_)

    for i, j in zip(all_components[:-1], all_components[1:]):
        assert_close(torch.sign(i), torch.sign(j), rtol=1e-6, atol=1e-6)


def test_incremental_pca_batch_values():
    # Test that components_ values are stable over batch sizes.
    n_samples = 100
    n_features = 3
    X = torch.randn(n_samples, n_features)
    all_components = []
    batch_sizes = torch.arange(20, 40, 3)
    for batch_size in batch_sizes:
        ipca = IncrementalPCA(n_components=None, batch_size=batch_size).fit(X)
        all_components.append(ipca.components_)

    for i, j in zip(all_components[:-1], all_components[1:]):
        assert_close(i, j, rtol=1e-1, atol=1e-1)


def test_incremental_pca_partial_fit():
    # Test that fit and partial_fit get equivalent results.
    n, p = 50, 3
    X = torch.randn(n, p)  # spherical data
    X[:, 1] *= 0.00001  # make middle component relatively small
    X += torch.tensor([5, 4, 3])  # make a large mean

    # same check that we can find the original data from the transformed
    # signal (since the data is almost of rank n_components)
    batch_size = 10
    ipca = IncrementalPCA(n_components=2, batch_size=batch_size).fit(X)
    pipca = IncrementalPCA(n_components=2, batch_size=batch_size)
    # Add one to make sure endpoint is included
    batch_itr = torch.arange(0, n + 1, batch_size)
    for i, j in zip(batch_itr[:-1], batch_itr[1:]):
        pipca.partial_fit(X[i:j, :])
    assert_close(ipca.components_, pipca.components_, rtol=1e-3, atol=1e-3)


def test_incremental_pca_lowrank():
    # Test that lowrank mode is equivalent to non-lowrank mode.
    n_components = 2
    X = torch.tensor(iris.data, dtype=torch.float32)
    batch_size = X.shape[0] // 3

    ipca = IncrementalPCA(n_components=n_components, batch_size=batch_size)
    ipca.fit(X)

    ipcalr = IncrementalPCA(
        n_components=n_components, batch_size=batch_size, lowrank=True
    )
    ipcalr.fit(X)

    assert_close(ipca.components_, ipcalr.components_, rtol=1e-7, atol=1e-7)


@pytest.mark.parametrize("n_components", [10, 20, None])
def test_incremental_pca_on_digits(n_components):
    """
    Test that our custom IncrementalPCA produces similar results to sklearn's
    IncrementalPCA on the digits dataset, both in partial_fit and fit/transform usage.
    """

    X, y = load_digits(return_X_y=True)
    X_train, X_test, _, _ = train_test_split(X, y, test_size=0.2, random_state=42)

    ipca = IncrementalPCA(
        n_components=n_components,
        batch_size=64,
    )
    sklearn_ipca = SkIncrementalPCA(
        n_components=n_components,
        batch_size=64,
    )

    ipca.fit(X_train)
    sklearn_ipca.fit(X_train)

    X_train_fit = ipca.transform(X_train)
    X_train_sklearn_fit = sklearn_ipca.transform(X_train)

    X_test_fit = ipca.transform(X_test)
    X_test_sklearn_fit = sklearn_ipca.transform(X_test)

    assert_allclose(X_train_sklearn_fit, X_train_fit, rtol=1e-5, atol=1e-5)
    assert_allclose(X_test_sklearn_fit, X_test_fit, rtol=1e-5, atol=1e-5)
