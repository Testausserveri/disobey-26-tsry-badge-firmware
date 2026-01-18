#!/bin/bash
set -e

# Script to update OTA.json with new firmware version
# Usage: ./update_ota_json.sh <version> <firmware_path> <s3_bucket> <s3_endpoint>

VERSION="$1"
FIRMWARE_PATH="$2"
S3_BUCKET="$3"
S3_ENDPOINT="$4"

if [ -z "$VERSION" ] || [ -z "$FIRMWARE_PATH" ] || [ -z "$S3_BUCKET" ] || [ -z "$S3_ENDPOINT" ]; then
    echo "Usage: $0 <version> <firmware_path> <s3_bucket> <s3_endpoint>"
    exit 1
fi

if [ ! -f "$FIRMWARE_PATH" ]; then
    echo "Error: Firmware file not found at $FIRMWARE_PATH"
    exit 1
fi

echo "=== Updating OTA.json ==="
echo "Version: $VERSION"
echo "Firmware: $FIRMWARE_PATH"

# Calculate SHA256 and size of the firmware
FIRMWARE_SHA256=$(sha256sum "$FIRMWARE_PATH" | awk '{print $1}')
FIRMWARE_SIZE=$(stat -c%s "$FIRMWARE_PATH" 2>/dev/null || stat -f%z "$FIRMWARE_PATH")

echo "SHA256: $FIRMWARE_SHA256"
echo "Size: $FIRMWARE_SIZE bytes"

# Construct the firmware URL
FIRMWARE_URL="${S3_ENDPOINT}/${S3_BUCKET}/firmware/${VERSION}/ota_firmware.bin"

# Download existing OTA.json or create new one
OTA_JSON="ota.json"
echo "Downloading existing OTA.json..."
if aws s3 cp "s3://${S3_BUCKET}/OTA.json" "$OTA_JSON" --endpoint-url "$S3_ENDPOINT" 2>/dev/null; then
    echo "✓ Downloaded existing OTA.json"
else
    echo "⚠ OTA.json not found, creating new one"
    cat > "$OTA_JSON" <<EOF
{
  "latest": "",
  "versions": {}
}
EOF
fi

# Update the JSON using Python
python3 << PYTHON_SCRIPT
import json
import sys

try:
    with open('$OTA_JSON', 'r') as f:
        data = json.load(f)
except:
    data = {"latest": "", "versions": {}}

# Ensure structure exists
if "versions" not in data:
    data["versions"] = {}

# Add/update the new version
data["versions"]["$VERSION"] = {
    "url": "$FIRMWARE_URL",
    "sha256": "$FIRMWARE_SHA256",
    "size": $FIRMWARE_SIZE
}

# Update latest
data["latest"] = "$VERSION"

# Write back with nice formatting
with open('$OTA_JSON', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')  # Add trailing newline

print(f"✓ Updated OTA.json with version $VERSION")
PYTHON_SCRIPT

echo ""
echo "Updated OTA.json contents:"
cat "$OTA_JSON"
echo ""

# Upload updated OTA.json back to S3
echo "Uploading OTA.json to S3..."
aws s3 cp "$OTA_JSON" "s3://${S3_BUCKET}/OTA.json" --endpoint-url "$S3_ENDPOINT"

echo "✅ OTA.json updated successfully!"
