# velella_detection
This repository contains the work I am doing for MBARI. more to come...

## Get started
Create a file called .env and put your Tator API token in there. There is an example file called .env_example.

 
## Drone/Satellite Image map correlation
1. **map_correlation_script.py** is a script that will return the given satalite image with correlated drone images location pins. 


### Planning
INPUT:
1. a satellite image from https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED#colab-python
2) a threshold that determines how faraway in time the drone image is allowed to be when searching. for example if the threshold is 30 minutes the drone image exif data has to be either 30 min before the sat image was taken or after, but it could also be 12 hour difference so this will be specified with a flag

SCRIPT OUTLINE:
It will use the Tator API token to query thru data. It will pull the exif data date and time, use the threshold input value to search for only drone images that fall within that time range. Once it has a list of those drone images relevant by date and time, it will look at the EXIF data to find the geolocation. It will then label with a small pin/dot and letter, where on the map that specific drone image was taken. 

OUTPUT: 
All the drone images will be displayed to the right of the satellite image with the same letter on it as is on the correlated location pin on the sat image.