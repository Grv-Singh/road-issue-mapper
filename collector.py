import os
import time
import json
import math
import logging
import urllib.request
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMG_DIR = os.path.join(DATA_DIR, "images")
ISSUES_FILE = os.path.join(DATA_DIR, "issues.json")
TELEMETRY_FILE = os.path.join(DATA_DIR, "telemetry.json")

os.makedirs(IMG_DIR, exist_ok=True)

CAMERA_HOST = "http://10.63.105.80:8888"
BUMP_THRESHOLD = 3.5  # m/s^2 linear acceleration spike
COOLDOWN_SEC = 2.0     # minimum seconds between bump triggers
last_trigger_time = 0

def get_json(endpoint):
    url = f"{CAMERA_HOST}/{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "RoadAudit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=1.5) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception:
        return None

def fetch_image(save_path):
    url = f"{CAMERA_HOST}/shot.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": "RoadAudit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=3.0) as res:
            with open(save_path, "wb") as f:
                f.write(res.read())
        return True
    except Exception as e:
        logging.error(f"Failed to fetch frame: {e}")
        return False

def load_issues():
    if os.path.exists(ISSUES_FILE):
        try:
            with open(ISSUES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_issues(issues):
    with open(ISSUES_FILE, "w") as f:
        json.dump(issues, f, indent=2)

def extract_gps(gps_raw):
    # IP Webcam returns {"gps": {"latitude": ..., "longitude": ...}, "network": {...}}
    if not gps_raw:
        return None
    gps = gps_raw.get("gps", {})
    net = gps_raw.get("network", {})
    target = gps if gps and "latitude" in gps else net
    if target and "latitude" in target:
        return {
            "lat": target.get("latitude"),
            "lng": target.get("longitude"),
            "speed": target.get("speed", 0.0),
            "altitude": target.get("altitude", 0.0),
            "accuracy": target.get("accuracy", 0.0),
            "provider": "gps" if target == gps else "network"
        }
    return None

def run_collector():
    global last_trigger_time
    logging.info(f"Collector started targeting {CAMERA_HOST}")
    
    while True:
        try:
            # 1. Fetch Sensors & Telemetry
            sensors = get_json("sensors.json")
            gps_raw = get_json("gps.json")
            gps = extract_gps(gps_raw)
            
            lin_accel_data = None
            battery = None
            
            if sensors:
                if "lin_accel" in sensors and "data" in sensors["lin_accel"]:
                    arr = sensors["lin_accel"]["data"]
                    if arr:
                        lin_accel_data = arr[-1][1]  # [x, y, z]
                if "battery_level" in sensors and "data" in sensors["battery_level"]:
                    arr = sensors["battery_level"]["data"]
                    if arr:
                        battery = arr[-1][1][0]
            
            # 2. Write real-time telemetry state
            telem = {
                "timestamp": datetime.now().isoformat(),
                "battery": battery,
                "gps": gps,
                "lin_accel": lin_accel_data,
                "status": "online" if sensors else "offline"
            }
            with open(TELEMETRY_FILE, "w") as f:
                json.dump(telem, f)
            
            # 3. Detect Road Bump Shock
            if lin_accel_data:
                ax, ay, az = lin_accel_data
                # Magnitude of linear acceleration
                mag = math.sqrt(ax*ax + ay*ay + az*az)
                now = time.time()
                
                # Check spike
                if (mag >= BUMP_THRESHOLD or abs(az) >= BUMP_THRESHOLD) and (now - last_trigger_time > COOLDOWN_SEC):
                    last_trigger_time = now
                    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    img_name = f"bump_{ts_str}.jpg"
                    img_path = os.path.join(IMG_DIR, img_name)
                    
                    logging.info(f"⚠️ Bump / Pothole detected! Mag: {mag:.2f} m/s², Az: {az:.2f} m/s²")
                    fetched = fetch_image(img_path)
                    
                    issue_entry = {
                        "id": f"issue_{int(now)}",
                        "timestamp": datetime.now().isoformat(),
                        "type": "pothole_or_bump",
                        "severity": "high" if mag > 6.0 else "medium",
                        "magnitude": round(mag, 2),
                        "z_accel": round(az, 2),
                        "gps": gps,
                        "image": f"/data/images/{img_name}" if fetched else None,
                        "battery": battery
                    }
                    
                    issues = load_issues()
                    issues.append(issue_entry)
                    save_issues(issues)
                    logging.info(f"Recorded issue {issue_entry['id']}")
            
            time.sleep(0.15)  # ~6-7 polls per second for responsive bump detection
        except Exception as e:
            logging.error(f"Collector loop error: {e}")
            time.sleep(1.0)

if __name__ == "__main__":
    run_collector()
