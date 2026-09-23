#!/usr/bin/env bash
# Start FastAPI backend and Vite frontend together
trap 'kill 0' EXIT

echo "Starting FastAPI evaluation backend on http://127.0.0.1:8000..."
.venv/bin/python -m src.api.server &

echo "Starting Vite React frontend on http://127.0.0.1:5173..."
npm --prefix frontend run dev &

wait
