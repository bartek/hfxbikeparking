#!/usr/bin/env bash 
set -ex

if [[ -z "$FELT_COOKIE_VALUE" ]]; then
    echo "FELT_COOKIE_VALUE must be set";
    exit 1
fi

if [[ -z "$FELT_MAP_ID" ]]; then
    echo "FELT_MAP_ID must be set";
    exit 1
fi

reset () {
    git reset --mixed --quiet
}

download_and_verify() {
    # Felt does not have an API or any token system, so copy the cookie value from
    # my desktop machine for now. Flaky, but works.
    curl --cookie "_felt_server_web_google_oauth_remember_me=${FELT_COOKIE_VALUE}" https://felt.com/map/export/${FELT_MAP_ID} -o export.geojson

    # Verify the file is somewhat sensible by checking jq output
    count=$(jq '.features | length' export.geojson)
    if [[ -z $count || "$count" -eq "0" ]]; then
        echo "Export does not seem to contain GeoJSON Features"
        exit 1
    fi

    # Looks OK, overwrite file in working tree
    mv export.geojson data.geojson
}


diff_and_sync() {
    files=$(git diff --name-only)

    for file in $files; do
        case $file in
            "data.geojson")
              commit_and_push
              ;;
        esac
    done
}

commit_and_push() {
    git add data.geojson

    # git config user.* is assumed set by host machine (or GitHub Action)
    git commit -m "Sync"
    git push --quiet origin main
}

reset
download_and_verify
diff_and_sync
