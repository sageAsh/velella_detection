import os
from dotenv import load_dotenv
import tator
import ee
from datetime import datetime, timedelta
import argparse
    
'''
INPUT: 
    - date and time of a satelite image
    - time threshold for drone image (**decide units later)

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


#----------------------------------HELPER FUNCTIONS---------------------------------------------------------
# get CLI args--------------
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




#-------------------MAIN-------------------------------------------------------
def main():
    args      = get_args()
    target_dt = datetime.fromisoformat(args.time)
    print(target_dt)

if __name__ == "__main__":
    main()
