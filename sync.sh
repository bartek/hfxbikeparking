#!/usr/bin/env bash
set -ex

cd "$(dirname "$0")"

(cd photos && source .venv/bin/activate && python sync_images.py)

source .venv/bin/activate
dogsheep-photos apple-photos photos.db
ALBUM="hfxbikeparking" python dogsheep/fetch.py > partial.geojson
./merge.sh

git add data.geojson
git commit -m "Sync"
git push
