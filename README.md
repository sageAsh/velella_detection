# velella_detection
This repository contains the work I am doing for MBARI. more to come...

## Get started
Create a file in /tokens called .env and put your Tator API token in there. There is an example file called .env_example you can find /tokens/.env_example. You can find the API token and host API Token and under the server name in Tator REST API respectively.

Create a Google Earth Engine service account key by following this guide [here](https://developers.google.com/earth-engine/guides/service_account#:~:text=Creating%20a%20service%20account%20involves,the%20Earth%20Engine%20API%20enabled.). Rename the json file to **.ee_key.json**.

1) You must enable Earth Engine for the project. You can do this by going to the Google Cloud home page, click on API & Services, click "+ Enable API & Services", search "Earth Engine", click it, and click the Enable button. 
2) You also must make sure the service account is registered for noncommercial use. You can click this [link](code.earthengine.google.com/register), click the first button for manage registration, and then fill out accordingly for scientific usage. I didn't want to set up a billing account so I chose the Community Tier which is "Intended for undergraduate students and other low computation users. 150 EECU-hour limit. A billing account is not required for this tier.*" 

 
## Drone/Satellite Image map correlation
1. **map_correlation_script.py** is a script that will return the given satalite image with correlated drone images location pins. 


### Planning
INPUT:
1. a date and time to find the closest satellite image from https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED#colab-python to base the image on
2) a threshold that determines how faraway in time the drone image is allowed to be when searching. for example if the threshold is 30 minutes the drone image exif data has to be either 30 min before the sat image was taken or after, but it could also be 12 hour difference so this will be specified with a flag

SCRIPT OUTLINE:
It will use the Tator API token to query drone data. It will pull the exif data date and time, use the threshold input value to search for only drone images that fall within that time range. Once it has a list of those drone images relevant by date and time, it will look at the EXIF data to find the geolocation. It will then label with a small pin/dot and letter, where on the map that specific drone image was taken. 

OUTPUT: 
All the drone images will be displayed to the right of the satellite image with the same letter on it as is on the correlated location pin on the sat image.