#!/usr/bin/env bash
# Render build script for Ente Naadu Django Backend
set -o errexit

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Applying database migrations..."
python manage.py migrate --no-input

echo "Build process completed successfully!"
