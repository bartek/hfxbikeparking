from collections import namedtuple
import ast
import json
import os
import sqlite3

# This script queries the Apple Photos database and returns a GeoJSON blob
# which can be uploaded to Felt (or appropriate source)
#
# First, obtain the photos.db
# dogsheep-photos apple-photos photos.db
# Then, adjust the query in line within this script (this can/should be improved in the future)
# When run, a GeoJSON feature collection will be returned. Pipe this to a file and upload.

# The album name (which is what will house the photos we want to process) is
# fetched from the environment
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
def query_database(db_file):
    try:
        # Connect to the database
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Perform the query
        query = """SELECT * FROM apple_photos WHERE albums = '["{}"]'""".format(album_name)
        cursor.execute(query)

        features = []

        rows = cursor.fetchall()
        for row in rows:
            f = create_feature(RowData(*row))
            if f is not None:
                features.append(f)

        feature_collection = {
            "type": "FeatureCollection",
            "features": features
        }

        geojson_blob = json.dumps(feature_collection, indent=2)
        print(geojson_blob)


    except sqlite3.Error as e:
        print("Error while querying the database:", e)
    finally:
        # Close the connection
        if conn:
            conn.close()

def create_feature(row: RowData): 
    keywords = ast.literal_eval(row.keywords)

    # Only concerned with photos which are tagged for bike parking. These are
    # any with a type: prefix on a keyword
    x = True
    for kw in keywords:
        if kw.startswith("type:"):
            x = False
    if x:
        return None

    # Files are assumed to be exported to jpeg for the purposes of delivery and
    # otherwise the original name is retained.
    filename = row.original_filename.split(".")[0] + ".jpeg"

    properties = { 
        "description": row.description if not None else "",
        "filename": filename,
        "date": row.date,
    }

    for kw in keywords:
        if kw.startswith("size"):
            properties["Size"] = int(kw.split(":")[1])
        if kw.startswith("type"):
            p = kw.split(":")[1]
            properties["Type"] = p.title()


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
