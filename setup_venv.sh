#!/bin/bash

# Check for Python 3.11
if ! command -v python3.11 &> /dev/null; then
    echo "Python 3.11 is not installed. Please install Python 3.11 to continue."
    exit 1
fi

# Create virtual environment
echo "Creating virtual environment..."
python3.11 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Update pip
echo "Updating pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Install development tools
echo "Installing development tools..."
pip install pylint black pytest

echo "Setup complete! Virtual environment created and activated."
echo "To activate the environment use command: source venv/bin/activate"