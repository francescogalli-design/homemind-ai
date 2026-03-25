#!/bin/bash

# HomeMind AI Assistant - Deployment Script
# This script handles deployment to various environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_status "Docker and Docker Compose are installed"
}

# Check if required files exist
check_files() {
    if [ ! -f ".env" ]; then
        print_warning ".env file not found. Creating from template..."
        cp .env.example .env
        print_warning "Please edit .env file with your configuration before continuing."
        exit 1
    fi
    
    if [ ! -f "docker-compose.yml" ]; then
        print_error "docker-compose.yml not found"
        exit 1
    fi
    
    print_status "Required files found"
}

# Build Docker image
build_image() {
    print_status "Building Docker image..."
    docker build -t homemind-ai:latest .
    print_status "Docker image built successfully"
}

# Deploy using Docker Compose
deploy_compose() {
    print_status "Deploying with Docker Compose..."
    
    # Stop existing containers
    docker-compose down 2>/dev/null || true
    
    # Pull latest images
    docker-compose pull
    
    # Start services
    docker-compose up -d
    
    print_status "Services deployed successfully"
    print_status "Application is available at: http://localhost:8080"
}

# Deploy to production
deploy_production() {
    print_status "Deploying to production..."
    
    # Set production environment variables
    export HOMEMIND_ENV=production
    export LOG_LEVEL=WARNING
    
    # Deploy with production settings
    deploy_compose
    
    print_status "Production deployment completed"
}

# Deploy to development
deploy_development() {
    print_status "Deploying to development..."
    
    # Set development environment variables
    export HOMEMIND_ENV=development
    export LOG_LEVEL=DEBUG
    
    # Deploy with development settings
    deploy_compose
    
    print_status "Development deployment completed"
}

# Health check
health_check() {
    print_status "Performing health check..."
    
    # Wait for services to start
    sleep 10
    
    # Check if application is responding
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        print_status "Health check passed - Application is responding"
    else
        print_error "Health check failed - Application is not responding"
        exit 1
    fi
}

# Show logs
show_logs() {
    print_status "Showing application logs..."
    docker-compose logs -f homemind-ai
}

# Cleanup
cleanup() {
    print_status "Cleaning up..."
    docker-compose down -v
    docker system prune -f
    print_status "Cleanup completed"
}

# Show usage
show_usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  dev         Deploy to development environment"
    echo "  prod        Deploy to production environment"
    echo "  build       Build Docker image only"
    echo "  health      Perform health check"
    echo "  logs        Show application logs"
    echo "  cleanup     Cleanup Docker resources"
    echo "  help        Show this help message"
}

# Main script
main() {
    case "${1:-help}" in
        "dev")
            check_docker
            check_files
            deploy_development
            health_check
            ;;
        "prod")
            check_docker
            check_files
            deploy_production
            health_check
            ;;
        "build")
            check_docker
            build_image
            ;;
        "health")
            health_check
            ;;
        "logs")
            show_logs
            ;;
        "cleanup")
            cleanup
            ;;
        "help"|*)
            show_usage
            ;;
    esac
}

# Run main function with all arguments
main "$@"
