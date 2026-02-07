#!/bin/bash
cargo build --release
cp target/release/libtitancore_free.so .
echo "✅ Rust Free Core built!"
