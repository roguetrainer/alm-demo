#!/bin/bash

# 1. Create a virtual environment named 'venv' if it doesn't exist

alias python3='/usr/local/bin/python3'

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# 2. Activate the virtual environment
# Note: This activation is only valid for the duration of this script execution
# inside the subshell.
source venv/bin/activate

# 3. Install dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
else
    echo "Error: requirements.txt not found."
    exit 1
fi

echo "------------------------------------------------"
echo "Setup complete!"
echo "To run the simulation, activate the environment:"
echo "    source venv/bin/activate"
echo "    python alm_simulation.py"
echo "------------------------------------------------"