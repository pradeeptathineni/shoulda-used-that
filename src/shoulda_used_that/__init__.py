"""ShouldaUsedThat public package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("shoulda-used-that")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.2.0"

__all__ = ["__version__"]
