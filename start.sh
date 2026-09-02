#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Kill any previous instances
pkill -f "collector.py" 2>/dev/null || true
pkill -f "server.py" 2>/dev/null || true

# Start Collector
python3 "$DIR/collector.py" > "$DIR/collector.log" 2>&1 &
COLLECTOR_PID=$!

# Start Web Server
python3 "$DIR/server.py" > "$DIR/server.log" 2>&1 &
SERVER_PID=$!

echo "Road Audit System Started!"
echo "Collector PID: $COLLECTOR_PID"
echo "Server PID: $SERVER_PID"
echo "Dashboard URL: http://localhost:8088 (or http://10.63.105.170:8088 on phone)"
