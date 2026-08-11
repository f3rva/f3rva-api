"""Dynamic Application Version Resolution via Git Tags and Package Metadata."""

from __future__ import annotations

import importlib.metadata
import subprocess


def get_version() -> str:
    """Resolve application version in order of precedence:

    1. Generated src/_version.py (written during CI/CD build from git tag)
    2. Package metadata via importlib.metadata
    3. Live git tag resolution via `git describe --tags` (during local development)
    4. Fallback baseline '0.1.0'
    """
    # 1. Check generated _version.py from setuptools_scm
    try:
        from src._version import __version__  # type: ignore

        return str(__version__)
    except ImportError:
        pass

    # 2. Check package metadata if installed via pip
    try:
        return importlib.metadata.version("f3rva-api")
    except importlib.metadata.PackageNotFoundError:
        pass

    # 3. Resolve live git tag during local development
    try:
        git_describe = subprocess.check_output(
            ["git", "describe", "--tags", "--always", "--dirty"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if git_describe:
            # Strip leading 'v' if present (e.g. 'v0.1.0' -> '0.1.0')
            return git_describe.lstrip("v")
    except Exception:
        pass

    # 4. Fallback baseline
    return "0.1.0"
