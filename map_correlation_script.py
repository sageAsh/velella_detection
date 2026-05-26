import os
import string
import requests
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image
from io import BytesIO
from datetime import datetime, timedelta
from dotenv import load_dotenv
import argparse
import tator
import ee #note- do not pip install ee that is a different package
    
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
    parser = argparse.ArgumentParser(description="Correlate Sentinel-2 satellite imagery with Tator drone imagery")
     
    #time you wanna find a sat image
    parser.add_argument("--time", type=str, required=True, 
                        help="Target date and time of the Satellite image in ISO 8601 format: YYYY-MM-DDTHH:MM:SS. It will find the closest image to this time")
    
    #drone image time threshold
    parser.add_argument("--threshold", type=int, default=30, 
                        help="+/- Threshold in minutes around the satellite pass to search for drone images (default = 30)")
    
    # coordinates
    parser.add_argument("--lat", type=float, default=36.780667, 
                        help="Center latitude of sat image (Default coordinate @ first main curve in Monterey Canyon)")
    
    parser.add_argument("--lon", type=float, default=-122.010139, 
                        help="Center longitude of sat image (Default coordinate @ first main curve in Monterey Canyon)")

    #output image specifications
    parser.add_argument("--zoom", type=float, default=0.15,
                        help="Half-width in degrees for the map extent (default: 0.15°)"
    )
    parser.add_argument("--sat-px", type=int, default=800,
                        help="Satellite thumbnail resolution in pixels (default: 800)"
    )
    parser.add_argument("--max-drone", type=int, default=5,
                        help="Maximum number of drone images to display (default: 5, sorted by closest to sat pass time)"
    )

    #output directory
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Directory to save output image (default: output_images/ next to the script)"
    )

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


# --------FIND CLOSEST DRONE IMAGE--------------
# get images from tator where date attribute is w/in drone start and end time
def get_drone_images(drone_start: datetime, drone_end: datetime):
    """
    Returns list of image objects that have non-null latitude and longitude
    """
    # tator attribute filters use ISO-8601 strings
    start_str = drone_start.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_str = drone_end.strftime('%Y-%m-%dT%H:%M:%SZ')

    print(f"  Querying Tator images between dates (inclusive): {start_str} to {end_str} ...")

    media_list = api.get_media_list(
        project=PROJECT_ID,
        attribute_gte=[f"date::{start_str}"],
        attribute_lte=[f"date::{end_str}"],
    )

    # only keep if they have valid GPS coordinates
    valid = []
    for m in media_list:
        attrs = m.attributes or {}
        lat = attrs.get('latitude')
        lon = attrs.get('longitude')
        date = attrs.get('date')
        if lat is not None and lon is not None and date is not None:
            valid.append(m)

    print(f"  Found {len(media_list)} images in time frame, {len(valid)} with GPS EXIF data.")
    return valid


def fetch_image_from_url(url: str) -> Image.Image:
    """Download an image from a URL and return a PIL Image."""
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return Image.open(BytesIO(resp.content)).convert("RGB")


# Download Helpers
def fetch_drone_thumbnail(media, max_size=(400, 300)) -> Image.Image | None:
    """Return a PIL thumbnail for a Tator media object, or None on failure."""
    try:
        media_files = media.get('media_files') or {}

        # Try the dedicated thumbnail first (relative path → prepend host)
        thumbs = media_files.get('thumbnail', [])
        if thumbs:
            path = thumbs[0]['path']
            url = path if path.startswith('http') else host.rstrip('/') + '/' + path.lstrip('/')
            try:
                img = fetch_image_from_url(url)
                img.thumbnail(max_size) 
                return img
            except Exception:
                pass  # fall through to full image

        # Fall back to the full image URL
        images = media_files.get('image', [])
        if images:
            url = images[0]['path']
            img = fetch_image_from_url(url)
            img.thumbnail(max_size)
            return img

    except Exception as e:
        print(f"    Warning: could not fetch thumbnail for {media.get('name', '?')}: {e}")
    return None

# COORDINATE → PIXEL mapping
def latlon_to_pixel(lat, lon, img_bounds, img_w, img_h):
    """
    Map a (lat, lon) to pixel (x, y) given the image bounding box.
    img_bounds = (west, south, east, north)  in degrees
    """
    west, south, east, north = img_bounds
    x = (lon - west)  / (east  - west)  * img_w
    y = (north - lat) / (north - south) * img_h   # y flipped (north=top)
    return x, y

# Visualization
LABEL_CHARS = list(string.ascii_uppercase)   # A, B, C, … 

def build_figure(sat_img: Image.Image, drone_items: list,
                 img_bounds: tuple, sat_datetime: datetime,
                 drone_start: datetime, drone_end: datetime,
                 output_path: str):
    """
    sat_img     – PIL image of the satellite base map
    drone_items – list of (media_object, pil_thumbnail_or_None)
    img_bounds  – (west, south, east, north)
    """
    n = len(drone_items)

    # ------------------------------------------------------------------
    # Layout: left = satellite map, right = drone thumbnails column
    # ------------------------------------------------------------------
    thumb_col_w = 2.5
    sat_w_in    = 6.0
    fig_h       = max(6.0, n * 2.0 + 1.0)

    fig = plt.figure(figsize=(sat_w_in + thumb_col_w + 0.5, fig_h))
    fig.patch.set_facecolor('#1a1a2e')

    gs = GridSpec(
        nrows=max(n, 1), ncols=2,
        figure=fig,
        left=0.02, right=0.98,
        top=0.93,  bottom=0.04,
        wspace=0.08, hspace=0.25,
        width_ratios=[sat_w_in, thumb_col_w]
    )

    ax_sat = fig.add_subplot(gs[:, 0])   # satellite spans all rows

    # -- Satellite image --
    sat_arr = np.array(sat_img)
    img_h_px, img_w_px = sat_arr.shape[:2]
    ax_sat.imshow(sat_arr, extent=[0, img_w_px, img_h_px, 0])
    ax_sat.set_xlim(0, img_w_px)
    ax_sat.set_ylim(img_h_px, 0)
    ax_sat.axis('off')
    ax_sat.set_facecolor('#0d0d1a')

    # Title
    fig.suptitle(
        f"Sentinel-2  ·  {sat_datetime.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"Drone window: {drone_start.strftime('%H:%M')} – {drone_end.strftime('%H:%M UTC')}",
        color='white', fontsize=11, fontweight='bold', y=0.975
    )

    # -- Plot pins on satellite image --
    west, south, east, north = img_bounds
    colors = plt.cm.tab20.colors   # distinct colors for pins

    legend_patches = []
    for i, (media, thumb) in enumerate(drone_items):
        label  = LABEL_CHARS[i % len(LABEL_CHARS)]
        color  = colors[i % len(colors)]
        attrs  = media.get('attributes') or {}
        m_lat  = float(attrs['latitude'])
        m_lon  = float(attrs['longitude'])

        px, py = latlon_to_pixel(m_lat, m_lon, img_bounds, img_w_px, img_h_px)

        # Pin: filled circle + letter
        circle = plt.Circle((px, py), radius=img_w_px * 0.018,
                             color=color, zorder=5, linewidth=1.5,
                             ec='white')
        ax_sat.add_patch(circle)
        ax_sat.text(px, py, label, color='white', fontsize=7,
                    fontweight='bold', ha='center', va='center', zorder=6)

        legend_patches.append(
            mpatches.Patch(color=color,
                           label=f"{label} · {media.get('name', '?')}  [{m_lat:.4f}, {m_lon:.4f}]")
        )

        # -- Drone thumbnail panel --
        ax_d = fig.add_subplot(gs[i, 1])
        ax_d.set_facecolor('#0d0d1a')
        ax_d.axis('off')

        if thumb is not None:
            ax_d.imshow(np.array(thumb))
        else:
            ax_d.text(0.5, 0.5, "No thumbnail", color='#888888',
                      ha='center', va='center', transform=ax_d.transAxes)

        # Badge (matching letter) in top-left corner
        ax_d.text(0.04, 0.93, label,
                  transform=ax_d.transAxes,
                  color='white', fontsize=12, fontweight='bold',
                  va='top', ha='left',
                  bbox=dict(boxstyle='round,pad=0.25', fc=color, ec='white', lw=1))

        # Caption
        date_str = str(attrs.get('date', ''))[:19]
        alt_str  = f"  alt: {float(attrs['altitude']):.0f} m" if attrs.get('altitude') else ''
        ax_d.set_title(f"{media.get('name', '?')}\n{date_str}{alt_str}",
                       color='#cccccc', fontsize=6.5, pad=3)

    # Legend below the satellite image
    if legend_patches:
        ax_sat.legend(
            handles=legend_patches,
            loc='lower left',
            fontsize=6.5,
            framealpha=0.6,
            facecolor='#111122',
            labelcolor='white',
            title='Drone images',
            title_fontsize=7,
            bbox_to_anchor=(0, 0),
            borderaxespad=0.5,
        )

    plt.savefig(output_path, dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Figure saved to {output_path}")



#-------------------MAIN-------------------------------------------------------
def main():
    args      = get_args()
    target_dt = datetime.fromisoformat(args.time)

    #FIND SAT IMAGE
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

    #FIND DRONE IMAGES
    window = timedelta(minutes=args.threshold)
    drone_start = actual_sat_dt - window
    drone_end = actual_sat_dt + window

    print(f"\nDrone image search window: {drone_start} to {drone_end}")

    drone_media = get_drone_images(drone_start, drone_end)

    if not drone_media:
        print("\nNo drone images with GPS found in this time frame, try widening drone image threshold. Exiting.")
        return
        
        # Sort by closest to actual satellite pass time, then cap
    def time_delta(m):
        date_str = m.get('attributes', {}).get('date', '')
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return abs((dt.replace(tzinfo=None) - actual_sat_dt).total_seconds())
        except Exception:
            return float('inf')

    drone_media.sort(key=time_delta)
    if len(drone_media) > args.max_drone:
        print(f"  Capping to {args.max_drone} closest images (of {len(drone_media)} found).")
        drone_media = drone_media[:args.max_drone]

    # 4. Download satellite base map thumbnail
    #    Define a tight bounding box around the requested center
    z = args.zoom
    west, south = args.lon - z, args.lat - z
    east, north = args.lon + z, args.lat + z
    img_bounds  = (west, south, east, north)

    region  = ee.Geometry.Rectangle([west, south, east, north])
    vis_params = {
        'bands': ['B4', 'B3', 'B2'],   # True color (R, G, B)
        'min': 0, 'max': 3000,
        'dimensions': args.sat_px,
        'region': region,
        'format': 'png',
    }
    sat_url = selected_sat.getThumbURL(vis_params)
    print(f"\nDownloading satellite thumbnail ...")
    sat_img = fetch_image_from_url(sat_url)
    print(f"  Satellite image size: {sat_img.size}")

    # 5. Download drone thumbnails
    print(f"\nFetching {len(drone_media)} drone thumbnails ...")
    drone_items = []
    for m in drone_media:
        thumb = fetch_drone_thumbnail(m)
        drone_items.append((m, thumb))

    # 6. Resolve output path
    if args.output_dir:
        out_dir = args.output_dir
    else:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output_images')
    os.makedirs(out_dir, exist_ok=True)
    filename = f"sat_drone_{actual_sat_dt.strftime('%Y%m%d_%H%M')}.png"
    output_path = os.path.join(out_dir, filename)

    # 7. Visualize
    print("\nRendering figure ...")
    build_figure(sat_img, drone_items, img_bounds, actual_sat_dt, drone_start, drone_end, output_path)


# TESTING COMMAND: (chose bc flight day on 2026/04/Seymour)
#python map_correlation_script.py --time 2026-04-17T19:00:00 --threshold 5760  #aka 4 days...
# NOTE - should maybe change the threshold to be optional so it just will just increase the threshold 
#        automatically by 1 day until it finds a drone image close enough. then instead it prints a warning message 
#        of how far (time wise) off the drone image time is from the sat image time. 

if __name__ == "__main__":
    main()
