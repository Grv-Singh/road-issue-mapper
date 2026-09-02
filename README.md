# 🛵 Road Defect & Pothole Audit Map

Automated real-time road defect mapping system powered by an onboard Pixel 6 IP camera and Debian audit daemon.

## 🌐 Public Live Map
View the live public road audit map:
**[https://grv-singh.github.io/road-issue-mapper/](https://grv-singh.github.io/road-issue-mapper/)**

## ⚡ How it works
1. **Phone Sensor Streaming:** IP Webcam Pro streams high-resolution road imagery along with GPS and linear accelerometer telemetry.
2. **Jolt / Pothole Detection:** The on-device collector detects acceleration shocks (> 3.5 m/s²), triggers instant road snapshots, and tags coordinates.
3. **Cloud Auto-Sync:** Flagged events are automatically committed and pushed to GitHub.
4. **GitHub Pages Dashboard:** Serves an interactive Leaflet.js defect map with photo popups.
