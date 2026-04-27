import os
from dotenv import load_dotenv
import tator
    
'''
INPUT: 
    - satelite image
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
earth_id = os.getenv("EARTH_ENGINE_API")

if not tator_token or not host:
    print("Error: no tator token or host found in .env, please make sure there is a .env file and reference .env_example")
else:
    api = tator.get_api(host=host, token=tator_token)
    print("Connected to Tator")
