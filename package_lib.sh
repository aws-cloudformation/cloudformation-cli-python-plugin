#!/bin/sh

OUT=$(pwd)
cd src/
python3 setup.py sdist
cp dist/*.tar.gz "$OUT"
rm -r dist/
