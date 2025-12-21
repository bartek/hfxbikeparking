from collections import namedtuple
import ast
import json
import os
import sqlite3



# This script queries the Apple Photos database and returns a GeoJSON
# FeatureCollection.
#
# First, obtain the photos.db
# > dogsheep-photos apple-photos photos.db
# Then, set the ALBUM environment variable and run the script
# > ALBUM="hfxbikeparking" python dogsheep/fetch.py > hfxbikeparking.geojson
album_name = os.environ.get("ALBUM")

RowData = namedtuple('RowData', [
    'sha256',
    'uuid',
    'burst_uuid',
    'filename',
    'original_filename',
    'description',
    'date',
    'date_modified',
    'title',
    'keywords',
    'albums',
    'persons',
    'path',
    'ismissing',
    'hasadjustments',
    'external_edit',
    'favorite',
    'hidden',
    'latitude',
    'longitude',
    'path_edited',
    'shared',
    'isphoto',
    'ismovie',
    'uti',
    'burst',
    'live_photo',
    'path_live_photo',
    'iscloudasset',
    'incloud',
    'portrait',
    'screenshot',
    'slow_mo',
    'time_lapse',
    'hdr',
    'selfie',
    'panorama',
    'has_raw',
    'uti_raw',
    'path_raw',
    'place_street',
    'place_sub_locality',
    'place_city',
    'place_sub_administrative_area',
    'place_state_province',
    'place_postal_code',
    'place_country',
    'place_iso_country_code',
])

valid_types = [
    'Ring',
    'Corral',
    'U Ring',
    'Ring Corral',
    'Wave Corral',
    'Wheel Slot Corral',
    'Triangle Corral',
    'Hanging Corral',
    'Ornamental',
    'Locker',
]

def query_database(db_file):
    assert album_name is not None, "ALBUM environment variable must be set."

    with sqlite3.connect(db_file) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM apple_photos WHERE albums = ?"
        cursor.execute(query, (json.dumps([album_name]),))

        features = []

        for row in cursor.fetchall():
            f = create_feature(RowData(*row))
            if f:
                features.append(f)

        feature_collection = {
            "type": "FeatureCollection",
            "features": features
        }

        geojson_blob = json.dumps(feature_collection, indent=2)
        print(geojson_blob)

def create_feature(row: RowData): 
    keywords = ast.literal_eval(row.keywords)

    # Photos without a type: are likely untagged and should be resolved.
    hasType = False
    for kw in keywords:
        if kw.startswith("type:"):
            hasType = True
            break
    assert hasType, f"Photo on {row.date} does not have a type: keyword."

    # Files are assumed to be exported to jpeg for the purposes of delivery and
    # otherwise the original name is retained.
    filename = row.original_filename.rsplit(".")[0] + ".jpeg"

    properties = { 
        "description": row.description or "",
        "filename": filename,
        "date": row.date,
    }

    # Currently tagging size and type
    for kw in keywords:
        if kw.startswith("size"):
            properties["Size"] = int(kw.split(":")[1])
        if kw.startswith("type"):
            p = kw.split(":")[1]
            properties["Type"] = p.title()
            assert p.title() in valid_types, f"Photo on {row.date} has invalid type: {p}"


    # Map the various keywords to the appropriate properties.
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [row.longitude, row.latitude]
        },
        "properties": properties,
    }

if __name__ == "__main__":
    database_file = "photos.db"
    query_database(database_file)
