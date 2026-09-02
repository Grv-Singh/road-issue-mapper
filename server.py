import os
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.request
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
DATA_DIR = os.path.join(BASE_DIR, "data")
ISSUES_FILE = os.path.join(DATA_DIR, "issues.json")
TELEMETRY_FILE = os.path.join(DATA_DIR, "telemetry.json")

class RoadAuditHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/issues":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if os.path.exists(ISSUES_FILE):
                with open(ISSUES_FILE, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"[]")
            return

        elif path == "/api/telemetry":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if os.path.exists(TELEMETRY_FILE):
                with open(TELEMETRY_FILE, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b'{"status":"waiting"}')
            return

        elif path.startswith("/data/images/"):
            # Serve captured photos
            rel_file = path[len("/data/images/"):]
            img_path = os.path.join(DATA_DIR, "images", rel_file)
            if os.path.exists(img_path):
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.end_headers()
                with open(img_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404, "Image not found")
                return

        # Serve static web dashboard
        if path == "/" or path == "":
            target_path = os.path.join(WEB_DIR, "index.html")
        else:
            clean_path = path.lstrip("/")
            target_path = os.path.join(WEB_DIR, clean_path)

        if os.path.exists(target_path) and os.path.isfile(target_path):
            self.send_response(200)
            if target_path.endswith(".html"):
                self.send_header("Content-Type", "text/html; charset=utf-8")
            elif target_path.endswith(".js"):
                self.send_header("Content-Type", "application/javascript")
            elif target_path.endswith(".css"):
                self.send_header("Content-Type", "text/css")
            self.end_headers()
            with open(target_path, "rb") as f:
                self.wfile.write(f.read())
            return

        self.send_error(404, "File Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/trigger":
            # Manual capture trigger
            try:
                from collector import fetch_image, load_issues, save_issues, extract_gps, get_json
                now = time.time()
                ts_str = time.strftime("%Y%m%d_%H%M%S")
                img_name = f"manual_{ts_str}.jpg"
                img_path = os.path.join(DATA_DIR, "images", img_name)
                
                fetched = fetch_image(img_path)
                gps = extract_gps(get_json("gps.json"))
                
                entry = {
                    "id": f"manual_{int(now)}",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "type": "manual_flag",
                    "severity": "medium",
                    "magnitude": 0.0,
                    "z_accel": 0.0,
                    "gps": gps,
                    "image": f"/data/images/{img_name}" if fetched else None
                }
                issues = load_issues()
                issues.append(entry)
                save_issues(issues)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "entry": entry}).encode("utf-8"))
            except Exception as e:
                self.send_error(500, str(e))
            return
        self.send_error(404, "Not Found")

def run(port=8088):
    os.makedirs(WEB_DIR, exist_ok=True)
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, RoadAuditHandler)
    print(f"Road Audit Server listening on http://0.0.0.0:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
