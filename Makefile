# Hybrid AI Location App - Development Makefile

.PHONY: help install dev test build clean

# Default target
help:
	@echo "Hybrid AI Location App - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  install     - Install all dependencies (frontend + backend)"
	@echo "  dev         - Start development environment (frontend + backend)"
	@echo "  dev-frontend - Start frontend development server"
	@echo "  dev-backend  - Start backend development server"
	@echo ""
	@echo "Testing:"
	@echo "  test        - Run all tests"
	@echo "  test-frontend - Run frontend tests"
	@echo "  test-backend  - Run backend tests"
	@echo "  test-e2e    - Run end-to-end tests"
	@echo ""
	@echo "Build:"
	@echo "  build       - Build both frontend and backend"
	@echo "  clean       - Clean build artifacts and dependencies"
	@echo ""
	@echo "Utilities:"
	@echo "  lint        - Run linting for both frontend and backend"
	@echo "  format      - Format code for both frontend and backend"
	@echo "  setup       - Initial project setup"

# Installation
install: install-backend install-frontend

install-backend:
	@echo "Installing backend dependencies..."
	cd backend && python -m venv venv
	cd backend && source venv/bin/activate && pip install -r requirements.txt
	cd backend && source venv/bin/activate && pip install -r requirements-dev.txt

install-frontend:
	@echo "Installing frontend dependencies..."
	cd frontend && pnpm install

# Development
dev:
	@echo "Starting development environment..."
	@echo "Make sure Redis is running locally on port 6379"
	@echo "Frontend: http://localhost:5173"
	@echo "Backend: http://localhost:8000"
	@echo ""
	@echo "Run 'make dev-frontend' and 'make dev-backend' in separate terminals"

dev-frontend:
	@echo "Starting frontend development server..."
	cd frontend && pnpm dev

dev-backend:
	@echo "Starting backend development server..."
	cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Testing
test: test-backend test-frontend

test-backend:
	@echo "Running backend tests..."
	cd backend && source venv/bin/activate && pytest -v --cov=app

test-frontend:
	@echo "Running frontend tests..."
	cd frontend && pnpm test:ci

test-e2e:
	@echo "Running end-to-end tests..."
	cd frontend && pnpm test:e2e

# Build
build: build-frontend build-backend

build-frontend:
	@echo "Building frontend..."
	cd frontend && pnpm build

build-backend:
	@echo "Building backend..."
	cd backend && source venv/bin/activate && python -m build

# Cleanup
clean:
	@echo "Cleaning up..."
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	rm -rf backend/venv
	rm -rf backend/__pycache__
	rm -rf backend/.pytest_cache
	rm -rf backend/coverage.xml

# Code Quality
lint: lint-backend lint-frontend

lint-backend:
	@echo "Linting backend..."
	cd backend && source venv/bin/activate && flake8 app/
	cd backend && source venv/bin/activate && mypy app/

lint-frontend:
	@echo "Linting frontend..."
	cd frontend && pnpm lint

format: format-backend format-frontend

format-backend:
	@echo "Formatting backend..."
	cd backend && source venv/bin/activate && black app/
	cd backend && source venv/bin/activate && isort app/

format-frontend:
	@echo "Formatting frontend..."
	cd frontend && pnpm format

# Setup
setup: install
	@echo "Setting up environment..."
	cp env.example .env
	@echo "Please edit .env file with your API keys and configuration"
	@echo "Setup complete! Run 'make dev' to start development"







