# HomeMind AI Assistant - Makefile
# Convenient commands for development and deployment

.PHONY: help install dev prod build test clean logs health

# Default target
help:
	@echo "HomeMind AI Assistant - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  install     Install dependencies and setup environment"
	@echo "  dev         Run development server"
	@echo "  test        Run tests"
	@echo "  lint        Run linting"
	@echo ""
	@echo "Deployment:"
	@echo "  build       Build Docker image"
	@echo "  prod        Deploy to production"
	@echo "  health      Check application health"
	@echo "  logs        Show application logs"
	@echo "  clean       Clean Docker resources"
	@echo ""
	@echo "Utilities:"
	@echo "  format      Format code"
	@echo "  docs        Generate documentation"

# Install dependencies
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env file from template"; fi

# Development server
dev:
	@echo "Starting development server..."
	python src/main.py

# Production deployment
prod:
	@echo "Deploying to production..."
	./scripts/deploy.sh prod

# Build Docker image
build:
	@echo "Building Docker image..."
	docker build -t homemind-ai:latest .

# Run tests
test:
	@echo "Running tests..."
	pytest tests/ -v --cov=src

# Linting
lint:
	@echo "Running linting..."
	flake8 src/ --max-line-length=127
	mypy src/ --ignore-missing-imports

# Format code
format:
	@echo "Formatting code..."
	black src/
	isort src/

# Health check
health:
	@echo "Checking application health..."
	curl -f http://localhost:8080/health || (echo "Health check failed" && exit 1)

# Show logs
logs:
	docker-compose logs -f homemind-ai

# Clean Docker resources
clean:
	@echo "Cleaning Docker resources..."
	docker-compose down -v
	docker system prune -f

# Generate documentation
docs:
	@echo "Generating documentation..."
	@if command -v mkdocs >/dev/null 2>&1; then \
		mkdocs build; \
	else \
		echo "mkdocs not installed. Install with: pip install mkdocs"; \
	fi

# Setup development environment
setup-dev:
	@echo "Setting up development environment..."
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env file"; fi
	@echo "Development environment ready. Activate with: source venv/bin/activate"

# Quick start (install + dev)
quick-start: install dev

# Production quick start (build + prod)
quick-prod: build prod

# Watch for changes and restart
watch:
	@echo "Watching for changes..."
	@which watchfiles >/dev/null || (echo "Installing watchfiles..." && pip install watchfiles)
	watchfiles --patterns="*.py" --recursive --command="make dev" src/

# Backup data
backup:
	@echo "Backing up data..."
	mkdir -p backups
	tar -czf backups/homemind-backup-$(shell date +%Y%m%d-%H%M%S).tar.gz data/ config/

# Restore from backup
restore:
	@echo "Available backups:"
	@ls -la backups/
	@read -p "Enter backup filename: " backup; \
	if [ -f "backups/$$backup" ]; then \
		tar -xzf backups/$$backup; \
		echo "Backup restored"; \
	else \
		echo "Backup file not found"; \
	fi

# Update dependencies
update-deps:
	@echo "Updating dependencies..."
	pip install --upgrade pip
	pip install --upgrade -r requirements.txt

# Security scan
security:
	@echo "Running security scan..."
	@which trivy >/dev/null || (echo "Installing trivy..." && brew install trivy)
	trivy fs .

# Performance test
perf-test:
	@echo "Running performance tests..."
	@which hey >/dev/null || (echo "Installing hey..." && go install github.com/rakyll/hey@latest)
	hey -n 100 -c 10 http://localhost:8080/health
