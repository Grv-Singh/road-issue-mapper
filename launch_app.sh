#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Start Server if not already running
if ! pgrep -f "$DIR/server.py" > /dev/null; then
    python3 "$DIR/server.py" > "$DIR/server.log" 2>&1 &
    sleep 0.5
fi

# Start Collector daemon if not already running
if ! pgrep -f "$DIR/collector.py" > /dev/null; then
    python3 "$DIR/collector.py" > "$DIR/collector.log" 2>&1 &
    sleep 0.5
fi

# Open Chromium Dashboard App window
chromium --app=http://localhost:8088 > /dev/null 2>&1 &
