#!/bin/bash

# Function to handle cleanup on exit
cleanup() {
    echo "Stopping servers..."
    kill $BACKEND_PID
    kill $FRONTEND_PID
    exit
}

trap cleanup SIGINT

echo "Cleaning up ports..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null

echo "Starting Bridge Markets Trading Lab..."

# 1. Start Backend
echo "Checking Python environment..."
cd backend
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "Installing/Updating requirements..."
pip install -r requirements.txt --quiet

echo "Launching Python Backend (FastAPI)..."
python3 main.py &
BACKEND_PID=$!

# 2. Start Frontend
echo "Launching React Dashboard (Vite)..."
cd ../dashboard
# Ensure node_modules exist
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install --quiet
fi
npm run dev -- --port 3000 &
FRONTEND_PID=$!

echo "Lab is ready!"
echo "Dashboard: http://localhost:3000"
echo "Backend API: http://localhost:8000"

# Keep script running
wait
