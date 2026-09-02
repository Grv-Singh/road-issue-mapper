#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

git add index.html style.css app.js data/issues.json data/images/*.jpg README.md 2>/dev/null
git commit -m "Auto-sync road defects [$(date '+%Y-%m-%d %H:%M:%S')]" >/dev/null 2>&1
git push -u origin main >/dev/null 2>&1
