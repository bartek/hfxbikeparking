#!/bin/bash

set -e

# Take partial and merge it with existing data.geojson, creating a merged.geojson
# Once validated, can move into data.geojson
jq -s '{type: "FeatureCollection", features: (.[0].features + .[1].features)}' data.geojson partial.geojson > merged.geojson
