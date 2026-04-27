#!/bin/bash

# SPADE XMPP Server Manager (Apple Silicon Compatible)
# Run this script whenever you need to work with SPADE

CONTAINER_NAME="xmpp-server"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/prosody.cfg.lua"

echo "🚀 Starting SPADE XMPP Server..."

# Function to check if container exists
container_exists() {
    docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

# Function to check if container is running
container_running() {
    docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"
}

# Stop and remove existing container if it exists
if container_exists; then
    echo "📦 Stopping existing container..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
fi

# Start the container
echo "🔧 Starting Prosody XMPP server..."
DOCKER_ARGS=(-d --name "$CONTAINER_NAME"
    --platform linux/amd64
    -p 5222:5222
    -p 5269:5269
    -p 5280:5280
    -e LOCAL=localhost
    -e DOMAIN=localhost
    -e ALLOW_REGISTRATION=true)

if [ -f "$CONFIG_FILE" ]; then
    DOCKER_ARGS+=(-v "$CONFIG_FILE:/etc/prosody/prosody.cfg.lua:ro")
fi

docker run "${DOCKER_ARGS[@]}" prosody/prosody:latest

# Wait for the server to start
echo "⏳ Waiting for server to initialize..."
sleep 3

# Fix TLS cert permissions so Prosody can read the private key
echo "🔑 Fixing TLS cert permissions..."
docker exec -u root $CONTAINER_NAME chown root:prosody /etc/prosody/certs/localhost.key 2>/dev/null || true
docker exec -u root $CONTAINER_NAME chmod 640 /etc/prosody/certs/localhost.key 2>/dev/null || true
docker exec $CONTAINER_NAME kill -HUP 1 2>/dev/null || true
sleep 1

# Check if it's running
if container_running; then
    echo ""
    echo "✅ SPADE XMPP Server is running!"
    echo ""
    echo "📊 Server Status:"
    docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "📝 Connection Details:"
    echo "   Host: localhost"
    echo "   Client Port: 5222"
    echo "   Server Port: 5269"
    echo "   HTTP Port: 5280"
    echo ""
    echo "🐍 Use in SPADE:"
    echo "   agent = Agent('username@localhost', 'password')"
    echo ""
    echo "💡 Tip: User accounts auto-register on first connect"
    echo ""
    echo "🔍 View logs: docker logs $CONTAINER_NAME"
    echo "🛑 Stop server: docker stop $CONTAINER_NAME"
    echo ""
    echo "⚠️  Note: This runs in-memory mode. Data won't persist after stopping."
    echo "   This is perfect for development - fresh start every time!"
else
    echo "❌ Failed to start server. Check logs with: docker logs $CONTAINER_NAME"
    exit 1
fi