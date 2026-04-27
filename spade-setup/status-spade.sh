#!/bin/bash

# Check SPADE XMPP Server Status

CONTAINER_NAME="xmpp-server"

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "✅ SPADE XMPP Server is RUNNING"
    echo ""
    docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "📋 Recent logs:"
    docker logs --tail 10 $CONTAINER_NAME
else
    echo "❌ SPADE XMPP Server is NOT running"
    echo ""
    echo "💡 Start it with: ./start-spade.sh"
fi