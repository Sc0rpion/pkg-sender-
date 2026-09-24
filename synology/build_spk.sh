#!/bin/bash
set -e

# ==============================================================================
# PS5 PKG Sender - Synology SPK Package Builder
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"
BUILD_DIR="${SCRIPT_DIR}/build"
STAGE_DIR="${BUILD_DIR}/staging"
OUTPUT_SPK="${ROOT_DIR}/pkg-sender.spk"

echo "=== Building Synology SPK Package for PS5 PKG Sender ==="

# Clean build directory
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}" "${STAGE_DIR}/server" "${STAGE_DIR}/ui" "${STAGE_DIR}/scripts"

# Make scripts executable
chmod 755 "${SCRIPT_DIR}/scripts/"*

# 1. Copy server files to staging (clean of cache, logs and temporary DB)
echo "-> Copying server files..."
cp "${ROOT_DIR}/server/"*.py "${STAGE_DIR}/server/"
cp "${ROOT_DIR}/server/locales.json" "${STAGE_DIR}/server/"
mkdir -p "${STAGE_DIR}/server/icons"

# Initial default config
cat <<EOF > "${STAGE_DIR}/server/config.json"
{
    "pkg_folder": "/volume1/downloads",
    "server_port": 9898
}
EOF

# 2. Copy UI files
echo "-> Copying DSM UI integration..."
cp "${SCRIPT_DIR}/ui/config" "${STAGE_DIR}/ui/"
cp -r "${SCRIPT_DIR}/ui/images" "${STAGE_DIR}/ui/"

# 3. Copy service control script into package payload
cp "${SCRIPT_DIR}/scripts/start-stop-status" "${STAGE_DIR}/scripts/"
chmod 755 "${STAGE_DIR}/scripts/start-stop-status"

# 4. Create package.tgz
echo "-> Creating package.tgz payload..."
tar -czf "${BUILD_DIR}/package.tgz" -C "${STAGE_DIR}" server ui scripts

# 5. Pack final .spk file
echo "-> Packaging final SPK archive..."
cd "${SCRIPT_DIR}"
tar -cf "${OUTPUT_SPK}" \
    INFO \
    PACKAGE_ICON.PNG \
    PACKAGE_ICON_256.PNG \
    conf \
    WIZARD_UIFILES \
    scripts \
    -C "${BUILD_DIR}" package.tgz

# Also copy to dist if dist exists
if [ -d "${DIST_DIR}" ]; then
    cp "${OUTPUT_SPK}" "${DIST_DIR}/pkg-sender.spk"
fi

# Cleanup build directory
rm -rf "${BUILD_DIR}"

echo "=========================================================="
echo " [OK] Synology SPK package built successfully!"
echo " Location: ${OUTPUT_SPK}"
ls -lh "${OUTPUT_SPK}"
echo "=========================================================="
