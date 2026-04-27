#!/bin/bash

CONTAINER_NAME="xmpp-server"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/../agents.pid"

# Stop agent process
echo "🤖 Stopping agents..."
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "✅ Agent process (PID $PID) stopped"
    else
        echo "ℹ️  Agent process not running"
    fi
    rm -f "$PID_FILE"
else
    echo "ℹ️  No agents.pid found — agents may not be running"
fi

# Stop XMPP server
echo ""
echo "📡 Stopping XMPP server..."
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
    echo "✅ XMPP server stopped"
else
    echo "ℹ️  XMPP server is not running"
fi
