#!/usr/bin/env bash
set -euo pipefail

# Build and package AWS Lambda zip for F3 RVA API (Python 3.13 / ARM64)
echo "📦 Building F3 RVA API Lambda deployment package..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

BUILD_DIR="${ROOT_DIR}/build"
PACKAGE_DIR="${BUILD_DIR}/package"
ZIP_FILE="${BUILD_DIR}/lambda.zip"

rm -rf "${BUILD_DIR}"
mkdir -p "${PACKAGE_DIR}"

echo "⬇️  Installing production dependencies for manylinux2014_aarch64 (ARM64)..."
pip install \
  --target "${PACKAGE_DIR}" \
  -r "${ROOT_DIR}/requirements.txt" \
  --platform manylinux2014_aarch64 \
  --only-binary=:all:

echo "📁 Copying application source code..."
cp -r "${ROOT_DIR}/src" "${PACKAGE_DIR}/"

echo "🗜️  Creating deployment zip: ${ZIP_FILE}..."
cd "${PACKAGE_DIR}"
zip -r -9 "${ZIP_FILE}" . -x "*.pyc" -x "__pycache__/*" -x "*.dist-info/*"

echo "✅ Lambda deployment bundle successfully built at: ${ZIP_FILE} ($(du -h "${ZIP_FILE}" | cut -f1))"
