#!/bin/bash
set -e

echo "🚀 Starting deployment build..."

# Update pip and install/upgrade dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Verify SSL certificates are installed
echo "🔒 Verifying SSL certificates..."
python -c "import certifi; print(f'SSL certificates found at: {certifi.where()}')"

# Run database migrations
echo "🗄️  Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Run security checks
echo "🔐 Running security checks..."
python manage.py check --deploy

echo "✅ Build completed successfully!"