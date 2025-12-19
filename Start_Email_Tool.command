#!/bin/bash

echo "============================================"
echo "   Email Automation Tool - Starting..."
echo "============================================"
echo ""

# Navigate to the script's directory
cd "$(dirname "$0")/email_app"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo ""
    echo "Please install Python:"
    echo "1. Open Terminal"
    echo "2. Install Homebrew (if not installed):"
    echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo "3. Install Python:"
    echo "   brew install python3"
    echo "4. Run this script again"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Install dependencies if needed
if [ ! -f ".deps_installed" ]; then
    echo "Installing dependencies (first time only)..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        read -p "Press Enter to exit..."
        exit 1
    fi
    touch .deps_installed
    echo "Dependencies installed successfully!"
    echo ""
fi

echo "Starting the Email Tool..."
echo ""
echo "============================================"
echo "   The tool will open in your browser."
echo "   Keep this window open while using it."
echo "   Close this window when you're done."
echo "============================================"
echo ""

# Open browser after a short delay
sleep 2 && open "http://localhost:5000" &

# Start the Flask app
python3 app.py
