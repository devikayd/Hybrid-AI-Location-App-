#!/bin/bash

# Script to create a zip file containing only backend and frontend directories
# Excludes: node_modules, __pycache__, venv, dist, .env files, database files, etc.

PROJECT_NAME="hybridWebApp"
ZIP_NAME="${PROJECT_NAME}_backend_frontend.zip"
TEMP_DIR=$(mktemp -d)

echo "Creating zip file: ${ZIP_NAME}"
echo "Temporary directory: ${TEMP_DIR}"

# Copy backend directory (excluding unnecessary files)
echo "Copying backend directory..."
rsync -av \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='*.pyd' \
  --exclude='.Python' \
  --exclude='venv/' \
  --exclude='v/' \
  --exclude='env/' \
  --exclude='backend/backend/' \
  --exclude='.env' \
  --exclude='.env.local' \
  --exclude='*.db' \
  --exclude='*.sqlite' \
  --exclude='*.sqlite3' \
  --exclude='.DS_Store' \
  --exclude='.vscode/' \
  --exclude='.idea/' \
  --exclude='*.log' \
  --exclude='test-results/' \
  --exclude='coverage/' \
  backend/ "${TEMP_DIR}/backend/"

# Copy frontend directory (excluding unnecessary files)
echo "Copying frontend directory..."
rsync -av \
  --exclude='node_modules/' \
  --exclude='dist/' \
  --exclude='dist-ssr/' \
  --exclude='.env' \
  --exclude='.env.local' \
  --exclude='.DS_Store' \
  --exclude='.vscode/' \
  --exclude='.idea/' \
  --exclude='*.log' \
  --exclude='.cache/' \
  --exclude='coverage/' \
  --exclude='test-results/' \
  frontend/ "${TEMP_DIR}/frontend/"

# Create zip file
echo "Creating zip archive..."
cd "${TEMP_DIR}"
zip -r "${OLDPWD}/${ZIP_NAME}" backend/ frontend/
cd "${OLDPWD}"

# Clean up temporary directory
rm -rf "${TEMP_DIR}"

echo "✅ Zip file created successfully: ${ZIP_NAME}"
echo "📦 Size: $(du -h ${ZIP_NAME} | cut -f1)"

