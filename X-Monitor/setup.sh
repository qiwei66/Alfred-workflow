#!/bin/bash
# X Monitor Setup Script
# This script sets up the X Monitor for automatic background checking

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.alfred.x-monitor.plist"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"

echo "X Monitor Setup"
echo "==============="
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    echo "Please install Python 3 and try again."
    exit 1
fi

echo "Python 3 found: $(python3 --version)"
echo ""

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCHD_DIR"

# Update the plist with the correct path
PLIST_CONTENT=$(cat "$SCRIPT_DIR/$PLIST_NAME")
PLIST_CONTENT="${PLIST_CONTENT//\$HOME/$HOME}"
PLIST_CONTENT="${PLIST_CONTENT//x-monitor\/x_monitor.py/$SCRIPT_DIR\/x_monitor.py}"

# Write the updated plist
echo "$PLIST_CONTENT" > "$LAUNCHD_DIR/$PLIST_NAME"

echo "LaunchAgent plist installed to: $LAUNCHD_DIR/$PLIST_NAME"

# Unload existing agent if running
if launchctl list | grep -q "com.alfred.x-monitor"; then
    echo "Stopping existing X Monitor service..."
    launchctl unload "$LAUNCHD_DIR/$PLIST_NAME" 2>/dev/null || true
fi

# Load the new agent
echo "Starting X Monitor service..."
launchctl load "$LAUNCHD_DIR/$PLIST_NAME"

echo ""
echo "Setup complete!"
echo ""
echo "X Monitor is now running in the background and will check for new tweets every 5 minutes."
echo ""
echo "Usage:"
echo "  Add account:    python3 $SCRIPT_DIR/x_monitor.py --add @username"
echo "  Remove account: python3 $SCRIPT_DIR/x_monitor.py --remove @username"
echo "  List accounts:  python3 $SCRIPT_DIR/x_monitor.py --list"
echo "  Manual check:   python3 $SCRIPT_DIR/x_monitor.py"
echo ""
echo "To stop the background service:"
echo "  launchctl unload $LAUNCHD_DIR/$PLIST_NAME"
echo ""
echo "To view logs:"
echo "  tail -f /tmp/x-monitor.log"
echo ""
