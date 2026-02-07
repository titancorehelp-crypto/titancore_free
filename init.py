# -*- coding: utf-8 -*-
"""
TITANCORE_FREE Python API
-------------------------
Provides high-performance access to Rust/C++ cores.
"""

import os
import sys

# ---------------------------------
# Add local library paths
# ---------------------------------
_here = os.path.dirname(__file__)
_lib_path = os.path.join(_here, "lib")  # যদি C++/Rust shared libs থাকে
if _lib_path not in sys.path:
    sys.path.append(_lib_path)

# ---------------------------------
# Import Rust bindings (if compiled with PyO3/maturin)
# ---------------------------------
try:
    import sovereign  # Assuming Rust core compiled to a Python module named 'sovereign'
except ImportError:
    print("⚠️ Warning: Rust core module 'sovereign' not found. Make sure build.sh has run.")

# ---------------------------------
# Import Python helpers
# ---------------------------------
# from .utils import *  # Uncomment if you have Python helpers

# ---------------------------------
# Version info
# ---------------------------------
__version__ = "0.1.0"
__author__ = "Rahul Sarkar"
__license__ = "MIT"

# ---------------------------------
# Expose main API
# ---------------------------------
def info():
    return {
        "project": "TITANCORE_FREE",
        "version": __version__,
        "author": __author__,
    }

# Example function calling Rust core
def run_rust_example(*args, **kwargs):
    try:
        return sovereign.run(*args, **kwargs)
    except NameError:
        raise RuntimeError("Rust core not loaded. Build the project first using ./build.sh")
