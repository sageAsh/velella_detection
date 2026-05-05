import os
from dotenv import load_dotenv
import tator
import ee    #note- do not pip install ee that is a different package
from datetime import datetime, timedelta
import argparse
    
'''
INPUT: 
    - date and time of a satelite image (ex: 2026-04-17T19:00:00)
    - time threshold for drone image in minutes (ex: 720)
    - coordinates lat (default at 36.780667)
    - coordinates lon (default at 122.010139)



OUTPUT: 
    - a new sat image annotated with the location of the drone images as well as the drone 
    images themselves displayed on the side of sat image
'''

# load tokens from .env file into environment
load_dotenv()

#grab token
host = os.getenv("HOST")
tator_token = os.getenv("TATOR_TOKEN")
earth_id = os.getenv("EE_PROJECT_ID")
earth_path = os.getenv("EE_PATH")

PROJECT_ID = 4

#tator checks
if not tator_token or not host:
    print("Error: no tator token or host found in .env, please make sure there is a .env file, you can reference .env_example")
else:
    api = tator.get_api(host=host, token=tator_token)
    print("Connected to Tator")

#GEE checks
if earth_path and os.path.exists(earth_path):
    # service account key
    credentials = ee.ServiceAccountCredentials(earth_id, earth_path)
    ee.Initialize(credentials=credentials, project=earth_id)
    print("Earth Engine Initialized via Service Account")
else:
    print("Earth Engine not initialized, check Google Cloud")
    #try to authenticate without seervice account key?
    # ee.Authenticate()
    # ee.Initialize(project=earth_id)


#----------------------------------FUNCTIONS---------------------------------------------------------
# --------GET CLI ARGS--------------
def get_args():
    parser = argparse.ArgumentParser(description="Map Drone imagery over Sentinel-2 Satellite data")
     
    #time you wanna find a sat image
    parser.add_argument("--time", type=str, required=True, 
                        help="Target date and time of the Satellite image in ISO format (YYYY-MM-DDTHH:MM:SS). It will find the closest image to this time")
    
    #drone image time threshold
    parser.add_argument("--threshold", type=int, default=30, 
                        help="+/- Threshold in minutes around the satellite pass to search for drone images (default = 30)")
    
    # coordinates
    parser.add_argument("--lat", type=float, default=36.780667, help="Center latitude of sat image (Default coordinate @ first main curve in Monterey Canyon)")
    parser.add_argument("--lon", type=float, default=-122.010139, help="Center longitude of sat image (Default coordinate @ first main curve in Monterey Canyon)")

    return parser.parse_args()

# --------FIND CLOSEST SAT IMAGE--------------
# find closest sat image with in 30 days to actually find an iimage w low cloud cover
def get_closest_sentinel_image(target_dt, lat, lon):
    target_ms   = target_dt.timestamp() * 1000
    start_date  = (target_dt - timedelta(days=30)).strftime('%Y-%m-%d')
    end_date    = (target_dt + timedelta(days=30)).strftime('%Y-%m-%d')
 
    poi = ee.Geometry.Point([lon, lat])
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(poi)
        .filterDate(start_date, end_date)
        # Pre-filter to get less cloudy granules.
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) #you can see thru with 20-30% cloud cover
    )
 
    #check if there are even any images w/in 30 days of time specified (like if its a particularily cloudy month)
    count = collection.size().getInfo()
    if count == 0:
        raise RuntimeError(
            f"No Sentinel-2 images found near ({lat}, {lon}) within ±30 days of "
            f"{target_dt.date()} with <20% cloud cover."
        )

    def add_time_diff(img):
        diff = ee.Number(img.get('system:time_start')).subtract(target_ms).abs()
        return img.set('time_diff', diff)

    return collection.map(add_time_diff).sort('time_diff').first()



#-------------------MAIN-------------------------------------------------------
def main():
    args      = get_args()
    target_dt = datetime.fromisoformat(args.time)

    print(f"\nSearching for Sentinel-2 image near {args.time} ...")
    selected_sat = get_closest_sentinel_image(target_dt, args.lat, args.lon)

    sat_info = selected_sat.getInfo()
    if sat_info is None:
        raise RuntimeError(
            "Earth Engine returned None, the collection might be empty.\n"
            "Try a different --time or a wider area."
        )

    actual_sat_ms = sat_info['properties']['system:time_start']
    actual_sat_dt = datetime.fromtimestamp(actual_sat_ms / 1000.0)

    print(f"Found: {sat_info['id']}")
    print(f"Satellite pass time: {actual_sat_dt}")



# TESTING COMMAND: (chose bc flight day on 2026/04/Seymour)
#python map_correlation_script.py --time 2026-04-17T19:00:00 --threshold 720  #aka 12 hrs...

if __name__ == "__main__":
    main()
