#!/usr/bin/env bash 
set -ex

source .venv/bin/activate
dogsheeep-photos apple-photos photos.db
ALBUM="hfxbikeparking" python dogsheep/fetch.py > partial.geojson
./merge.sh
