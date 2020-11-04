#!/usr/bin/env bash

if [[ "$TRAVIS_TAG" =~ plugin ]]; then
    echo .
elif [[ "$TRAVIS_TAG" =~ lib ]]; then
    echo src
fi
