#!/bin/bash

set -e

# Combine base.geojson with partial.geojson (from dogsheep/fetch.py) into data.geojson
jq -s '{type: "FeatureCollection", features: (.[0].features + .[1].features)}' base.geojson partial.geojson > data.geojson
