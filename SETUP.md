# Massi Website - Setup Guide

## Requirements

- Python 3.10+
- Node.js 18+
- MySQL server

## Backend Setup

```bash
cd server

# Install Python dependencies
pip install fastapi uvicorn sqlalchemy pymysql python-multipart google-auth aiomysql

# Make sure MySQL is running with database 'kiraa_db'
# Update credentials in server/functions.py and server/websocket/messages.py if needed

# Run main API server (port 8000)
uvicorn main:app --host 0.0.0.0 --port 8000

# In a separate terminal, run WebSocket server (port 8888)
cd websocket && uvicorn messages:app --host 0.0.0.0 --port 8888
```

## Frontend Setup

The frontend is pre-built in the `out/` folder. Serve it with any static server:

```bash
# Option 1: Using serve (npm)
npx serve out -l 3000

# Option 2: Using Python
python -m http.server 3000 -d out
```

Then open http://localhost:3000 in your browser.

## Development (if editing frontend)

```bash
# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build
```
