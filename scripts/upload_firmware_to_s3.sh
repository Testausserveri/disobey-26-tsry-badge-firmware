#!/bin/bash
set -e

# Script to upload firmware binaries to S3
# Usage: ./upload_firmware_to_s3.sh <version> <full_firmware_path> <ota_firmware_path> <s3_bucket> <s3_endpoint>

VERSION="$1"
FULL_FW="$2"
OTA_FW="$3"
S3_BUCKET="$4"
S3_ENDPOINT="$5"

if [ -z "$VERSION" ] || [ -z "$FULL_FW" ] || [ -z "$OTA_FW" ] || [ -z "$S3_BUCKET" ] || [ -z "$S3_ENDPOINT" ]; then
    echo "Usage: $0 <version> <full_firmware_path> <ota_firmware_path> <s3_bucket> <s3_endpoint>"
    exit 1
fi

if [ ! -f "$FULL_FW" ]; then
    echo "Error: Full firmware file not found at $FULL_FW"
    exit 1
fi

if [ ! -f "$OTA_FW" ]; then
    echo "Error: OTA firmware file not found at $OTA_FW"
    exit 1
fi

echo "=== Uploading Firmware to S3 ==="
echo "Version: $VERSION"
echo "Bucket: $S3_BUCKET"
echo "Endpoint: $S3_ENDPOINT"
echo "Full firmware: $FULL_FW"
echo "OTA firmware: $OTA_FW"

# Extract hostname from endpoint URL
S3_HOST=$(echo "${S3_ENDPOINT}" | sed 's|https://||' | sed 's|http://||')

# Check if s3cmd is available
if ! command -v s3cmd &> /dev/null; then
    echo "Installing s3cmd..."
    pip install s3cmd
fi

echo ""
echo "📦 Uploading firmware to S3..."

# Upload versioned firmware
echo "Uploading full_firmware.bin to firmware/${VERSION}/"
s3cmd --access_key="${S3_ACCESS_KEY_ID}" \
    --secret_key="${S3_SECRET_ACCESS_KEY}" \
    --host="${S3_HOST}" \
    --host-bucket='%(bucket)s.'"${S3_HOST}" \
    put "$FULL_FW" \
    s3://${S3_BUCKET}/firmware/${VERSION}/full_firmware.bin

echo "Uploading ota_firmware.bin to firmware/${VERSION}/"
s3cmd --access_key="${S3_ACCESS_KEY_ID}" \
    --secret_key="${S3_SECRET_ACCESS_KEY}" \
    --host="${S3_HOST}" \
    --host-bucket='%(bucket)s.'"${S3_HOST}" \
    put "$OTA_FW" \
    s3://${S3_BUCKET}/firmware/${VERSION}/ota_firmware.bin

# Upload as "latest" for easy access
echo "Uploading full_firmware.bin to firmware/latest/"
s3cmd --access_key="${S3_ACCESS_KEY_ID}" \
    --secret_key="${S3_SECRET_ACCESS_KEY}" \
    --host="${S3_HOST}" \
    --host-bucket='%(bucket)s.'"${S3_HOST}" \
    put "$FULL_FW" \
    s3://${S3_BUCKET}/firmware/latest/full_firmware.bin

echo "Uploading ota_firmware.bin to firmware/latest/"
s3cmd --access_key="${S3_ACCESS_KEY_ID}" \
    --secret_key="${S3_SECRET_ACCESS_KEY}" \
    --host="${S3_HOST}" \
    --host-bucket='%(bucket)s.'"${S3_HOST}" \
    put "$OTA_FW" \
    s3://${S3_BUCKET}/firmware/latest/ota_firmware.bin

echo ""
echo "✅ Uploaded to S3:"
echo "  - ${S3_ENDPOINT}/${S3_BUCKET}/firmware/${VERSION}/"
echo "  - ${S3_ENDPOINT}/${S3_BUCKET}/firmware/latest/"
