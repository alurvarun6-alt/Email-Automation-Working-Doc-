#!/bin/bash

echo ""
echo "============================================"
echo "   Email Automation Tool"
echo "============================================"
echo ""

# Navigate to the script's directory
cd "$(dirname "$0")/email_app"

# Check if system Python is available
if ! command -v /usr/bin/python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo ""
    echo "Please install Python from: https://www.python.org/downloads/"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Install dependencies if needed
if [ ! -f ".deps_installed" ]; then
    echo "Installing dependencies (first time only, please wait)..."
    echo ""
    /usr/bin/python3 -m pip install -r requirements.txt --quiet
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        read -p "Press Enter to exit..."
        exit 1
    fi
    touch .deps_installed
    echo "Dependencies installed!"
    echo ""
fi

echo "Starting the Email Tool..."
echo ""
echo "============================================"
echo "   Opening browser to: http://localhost:5001"
echo "   Keep this window open while using it."
echo "   Close this window when you're done."
echo "============================================"
echo ""

# Open browser after a short delay
(sleep 2 && open "http://localhost:5001") &

# Start the Flask app using system Python
/usr/bin/python3 app.py
