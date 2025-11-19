#!/bin/bash

echo "🚀 Starting Crowd Anomaly Detection System..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Ensure Docker daemon is running (Docker Desktop on macOS)
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker daemon is not running. Please start Docker Desktop and try again."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Copy environment files if they don't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from example..."
    cp .env.example .env
fi

if [ ! -f frontend/.env ]; then
    echo "📝 Creating frontend/.env file from example..."
    cp frontend/.env.example frontend/.env
fi

# Build and start containers
echo "🔨 Building Docker containers..."
docker-compose -f docker-compose.yml build

echo "🎬 Starting services..."
docker-compose -f docker-compose.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
if [ "$(docker-compose -f docker-compose.yml ps -q backend)" ]; then
    echo "✅ Backend is running on http://localhost:8000"
    echo "📚 API Documentation: http://localhost:8000/docs"
else
    echo "❌ Backend failed to start"
fi

if [ "$(docker-compose -f docker-compose.yml ps -q frontend)" ]; then
    echo "✅ Frontend is running on http://localhost:3000"
else
    echo "❌ Frontend failed to start"
fi

echo ""
echo "🎉 System is ready!"
echo "📊 Access Dashboard: http://localhost:3000"
echo "🔧 Access API: http://localhost:8000"
echo ""
echo "To view logs: docker-compose -f docker-compose.yml logs -f"
echo "To stop: docker-compose -f docker-compose.yml down"
