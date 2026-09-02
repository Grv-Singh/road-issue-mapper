import os
import time
import json
import math
import logging
import urllib.request
from datetime import datetime
import cv2
import numpy as np

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
BUMP_THRESHOLD = 3.5          # m/s^2 linear acceleration spike
BUMP_COOLDOWN = 2.0           # Cooldown between bump triggers (seconds)
VISION_SCAN_INTERVAL = 3.0    # Scan frame with OpenCV every 3 seconds
PERIODIC_SURVEY_SEC = 20.0    # Periodic street capture interval

last_bump_time = 0
last_vision_scan_time = 0
last_survey_time = 0

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
            data = res.read()
            with open(save_path, "wb") as f:
                f.write(data)
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

def detect_visual_anomalies(img_path):
    """
    OpenCV road surface analyzer:
    Detects foreign contrast objects, rubble, bricks, garbage clusters on road lane ROI.
    """
    img = cv2.imread(img_path)
    if img is None:
        return False, None, 0.0

    h, w = img.shape[:2]
    # Lower 50% road center ROI
    roi = img[int(h * 0.45):int(h * 0.95), int(w * 0.15):int(w * 0.85)]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Road median color deviation
    median_val = np.median(blur)
    diff = cv2.absdiff(blur, int(median_val))
    _, thresh = cv2.threshold(diff, 48, 255, cv2.THRESH_BINARY)

    # Find distinct contours on the road surface
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter blobs: size between 400 and 25000 pixels (rubble, plastic piles, stones)
    hazard_blobs = [c for c in contours if 400 < cv2.contourArea(c) < 25000]
    
    if len(hazard_blobs) >= 2 or any(cv2.contourArea(c) > 2500 for c in hazard_blobs):
        return True, "Garbage / Rubble Cluster", min(0.92, 0.6 + len(hazard_blobs) * 0.08)

    return False, None, 0.0

def sync_github():
    os.system("nohup bash /home/droid/workspace/projects/road-issue-mapper/sync_github.sh >/dev/null 2>&1 &")

def record_defect(issue_type, severity, description, mag, z_accel, gps, img_name, battery):
    entry = {
        "id": f"defect_{int(time.time())}",
        "timestamp": datetime.now().isoformat(),
        "type": issue_type,
        "description": description,
        "severity": severity,
        "magnitude": round(mag, 2),
        "z_accel": round(z_accel, 2),
        "gps": gps,
        "image": f"data/images/{img_name}",
        "battery": battery
    }
    issues = load_issues()
    issues.append(entry)
    save_issues(issues)
    logging.info(f"Recorded [{issue_type}]: {description} at GPS {gps.get('lat') if gps else 'N/A'}")
    sync_github()

def run_collector():
    global last_bump_time, last_vision_scan_time, last_survey_time
    logging.info(f"Visual + Shock Road Audit Daemon active on {CAMERA_HOST}")

    while True:
        try:
            now = time.time()
            sensors = get_json("sensors.json")
            gps_raw = get_json("gps.json")
            gps = extract_gps(gps_raw)

            lin_accel_data = None
            battery = None

            if sensors:
                if "lin_accel" in sensors and "data" in sensors["lin_accel"]:
                    arr = sensors["lin_accel"]["data"]
                    if arr:
                        lin_accel_data = arr[-1][1]
                if "battery_level" in sensors and "data" in sensors["battery_level"]:
                    arr = sensors["battery_level"]["data"]
                    if arr:
                        battery = arr[-1][1][0]

            # Telemetry state
            telem = {
                "timestamp": datetime.now().isoformat(),
                "battery": battery,
                "gps": gps,
                "lin_accel": lin_accel_data,
                "status": "online" if sensors else "offline"
            }
            with open(TELEMETRY_FILE, "w") as f:
                json.dump(telem, f)

            # --- 1. ACCELEROMETER BUMP / POTHOLE SHOCK DETECTION ---
            if lin_accel_data:
                ax, ay, az = lin_accel_data
                mag = math.sqrt(ax*ax + ay*ay + az*az)

                if (mag >= BUMP_THRESHOLD or abs(az) >= BUMP_THRESHOLD) and (now - last_bump_time > BUMP_COOLDOWN):
                    last_bump_time = now
                    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    img_name = f"bump_{ts_str}.jpg"
                    img_path = os.path.join(IMG_DIR, img_name)

                    if fetch_image(img_path):
                        sev = "high" if mag > 6.0 else "medium"
                        record_defect(
                            issue_type="pothole_shock",
                            severity=sev,
                            description=f"Pothole Jolt: {mag:.1f} m/s² shock",
                            mag=mag,
                            z_accel=az,
                            gps=gps,
                            img_name=img_name,
                            battery=battery
                        )

            # --- 2. OPENCV VISUAL SCAN (Garbage, Rubble, Stones) ---
            if now - last_vision_scan_time > VISION_SCAN_INTERVAL:
                last_vision_scan_time = now
                temp_img = os.path.join(IMG_DIR, "current_scan.jpg")
                if fetch_image(temp_img):
                    is_anomaly, desc, conf = detect_visual_anomalies(temp_img)
                    if is_anomaly:
                        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        img_name = f"hazard_{ts_str}.jpg"
                        perm_path = os.path.join(IMG_DIR, img_name)
                        os.rename(temp_img, perm_path)

                        record_defect(
                            issue_type="garbage_or_debris",
                            severity="medium",
                            description=f"Road Anomaly: {desc} (conf: {conf:.2f})",
                            mag=0.0,
                            z_accel=0.0,
                            gps=gps,
                            img_name=img_name,
                            battery=battery
                        )

            # --- 3. PERIODIC ROUTE SURVEY (Continuous Street Mapping) ---
            if now - last_survey_time > PERIODIC_SURVEY_SEC:
                last_survey_time = now
                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                img_name = f"survey_{ts_str}.jpg"
                img_path = os.path.join(IMG_DIR, img_name)
                if fetch_image(img_path):
                    record_defect(
                        issue_type="route_audit",
                        severity="low",
                        description="Street Survey Breadcrumb",
                        mag=0.0,
                        z_accel=0.0,
                        gps=gps,
                        img_name=img_name,
                        battery=battery
                    )

            time.sleep(0.15)
        except Exception as e:
            logging.error(f"Collector loop error: {e}")
            time.sleep(1.0)

if __name__ == "__main__":
    run_collector()
