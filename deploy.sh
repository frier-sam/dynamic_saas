#!/bin/bash

# Dynamic SaaS Generator Deployment Script

# Exit on error
set -e

echo "=== Dynamic SaaS Generator Deployment ==="
echo "This script will help you set up and deploy the application."

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install it and try again."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists, create if it doesn't
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    
    # Generate a random secret key
    DJANGO_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(50))')
    
    # Update the secret key in the .env file
    sed -i "s/your-secret-key-here/$DJANGO_SECRET_KEY/" .env
    
    echo "Please edit the .env file to add your Azure OpenAI credentials."
    read -p "Press Enter to continue..."
fi

# Run database migrations
echo "Running database migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if needed
read -p "Do you want to create a superuser? (y/n): " create_superuser
if [ "$create_superuser" = "y" ]; then
    python manage.py createsuperuser
fi

# Ask about deployment
echo "Deployment options:"
echo "1. Development server (for testing)"
echo "2. Production deployment with Gunicorn"
read -p "Choose an option (1/2): " deployment_option

if [ "$deployment_option" = "1" ]; then
    echo "Starting development server..."
    python manage.py runserver
elif [ "$deployment_option" = "2" ]; then
    # Check if Gunicorn is installed
    if ! pip show gunicorn &> /dev/null; then
        echo "Installing Gunicorn..."
        pip install gunicorn
    fi
    
    echo "Starting Gunicorn server..."
    gunicorn dynamic_saas.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile - --error-logfile -
else
    echo "Invalid option. Exiting."
    exit 1
fi