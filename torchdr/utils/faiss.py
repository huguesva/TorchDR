"""Robust handling of faiss as optional dependency."""

# Author: Hugues Van Assel <vanasselhugues@gmail.com>
#
# License: BSD 3-Clause License

try:
    import faiss

except Exception:
    faiss = False
