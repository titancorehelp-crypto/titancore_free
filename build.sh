#!/bin/bash

# -----------------------------
# TITANCORE_FREE BUILD SCRIPT
# -----------------------------

# Exit on any error
set -e

echo "🚀 Starting TITANCORE_FREE build process..."

# -----------------------------
# Step 1: Clean previous builds
# -----------------------------
echo "🧹 Cleaning old build artifacts..."
rm -rf build target *.egg-info dist

# Create build directory
mkdir -p build

# -----------------------------
# Step 2: Build Rust core
# -----------------------------
if [ -f "Cargo.toml" ]; then
    echo "⚙️ Building Rust core..."
    cargo build --release
    echo "✅ Rust build finished"
fi

# -----------------------------
# Step 3: Build Python package
# -----------------------------
if [ -f "setup.py" ]; then
    echo "🐍 Building Python package..."
    python3 -m venv build/venv
    source build/venv/bin/activate
    pip install --upgrade pip setuptools wheel
    python setup.py sdist bdist_wheel
    deactivate
    echo "✅ Python package build finished"
fi

# -----------------------------
# Step 4: Build C++ core (optional)
# -----------------------------
if [ -f "Makefile" ]; then
    echo "💻 Building C++ components..."
    make clean
    make all
    echo "✅ C++ build finished"
fi

# -----------------------------
# Step 5: Summary
# -----------------------------
echo "🎉 TITANCORE_FREE build completed successfully!"
echo "Artifacts:"
[ -d "target/release" ] && echo " - Rust: target/release/"
[ -d "dist" ] && echo " - Python: dist/"
[ -d "build" ] && echo " - General build folder: build/"
