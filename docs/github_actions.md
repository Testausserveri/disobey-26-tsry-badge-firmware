# GitHub Actions CI/CD Setup

This document describes the GitHub Actions workflow for building and releasing the Disobey Badge 2025 firmware.

## Workflow

### Build & Release (`.github/workflows/build.yml`)

This single unified workflow handles both regular builds and releases.

**Triggers:**
- Every push to `main` branch → **Build only**
- Every pull request to `main` branch → **Build only**
- Push of tags starting with `v` (e.g., `v1.0.0`) → **Build + Release**

**What it does (all builds):**
- Checks out code with submodules
- Installs system dependencies and Python packages
- Caches ESP-IDF, mpy-cross, and build artifacts for faster builds
- Builds the normal firmware
- Uploads firmware artifacts (retained for 30 days)

**Additional steps for tagged builds:**
- Uploads firmware to S3-compatible storage (uocloud.com)
- Updates ota.json with version info (URL, SHA256, size)

**Caching Strategy:**
- ESP-IDF installation (~1GB) - Speeds up builds significantly
- mpy-cross compiled binary - Only rebuilds when source changes
- Build artifacts - Incremental builds when possible

**First build:** ~15-20 minutes  
**Subsequent builds:** ~5-10 minutes (with cache)
**Release:** ~10-15 minutes

## Configuration

### Required Repository Secrets

Set these in GitHub repository settings → Secrets and variables → Actions:

#### S3 Storage Secrets (for firmware upload)

- `S3_ACCESS_KEY_ID` - Your S3 access key ID
- `S3_SECRET_ACCESS_KEY` - Your S3 secret access key

#### Repository Variables

- `S3_ENDPOINT` - S3 endpoint URL (e.g., `https://s3.uocloud.com`)
- `S3_BUCKET` - S3 bucket name (e.g., `disobey-firmware`)

**Note:** If S3 variables are not configured, the release workflow will skip S3 upload but still create a GitHub Release.

### Permissions

The workflows use `GITHUB_TOKEN` which is automatically provided. The release workflow requires `contents: write` permission to:
- Push commits and tags
- Create releases

This is already configured in the workflow file.

## Usage

### Automatic Builds

Builds run automatically on every push to `main`:

1. Push your changes: `git push origin main`
2. Go to Actions tab in GitHub
3. Watch the build progress
4. Download artifacts from the workflow run

### Creating a Release

The release process is simple and automatic:

**Step 1: Bump version and create tag locally**
```bash
# Create a patch release (e.g., v0.0.1 → v0.0.2)
make release

# Or for different bump types:
make release BUMP_TYPE=minor  # v0.1.0 → v0.2.0
make release BUMP_TYPE=major  # v1.0.0 → v2.0.0
```

This will:
- ✅ Bump version in `frozen_fs/VERSION`
- ✅ Commit the change
- ✅ Create a local git tag (e.g., `v0.0.2-abc1234`)
- ✅ Build firmware locally (optional verification)

**Step 2: Push the tag to GitHub**
```bash
git push origin main --tags
```

**Step 3: Watch GitHub Actions**

Once the tag is pushed, GitHub Actions automatically:
- ✅ Builds firmware at that tagged commit
- ✅ Uploads to S3 storage (if configured)
- ✅ Updates ota.json with version metadata

**That's it!** The entire release process is automated after you push the tag.

Firmware artifacts are stored in S3 and can be downloaded from there or accessed via the OTA system.

**Alternative: Manual tag creation**

You can also create tags manually without using `make release`:
```bash
# Create a tag directly
git tag v1.0.0
git push origin v1.0.0
```

This will trigger the release workflow, but the version in `frozen_fs/VERSION` won't be automatically updated.

### Firmware Files in Release

Each release includes three firmware files:

1. **firmware_normal.bin** - Main firmware for flashing
   - Use this for initial badge programming
   - Contains bootloader, partitions, and application
   
2. **full_firmware.bin** - Complete firmware image
   - Alternative format for some flash tools
   
3. **ota_firmware.bin** - OTA update file
   - MicroPython application only (no bootloader)
   - Use for over-the-air updates

### S3 Storage Structure

Firmware is uploaded to S3 with the following structure:

```
s3://your-bucket/
  ota.json                      # Version manifest for OTA updates
  firmware/
    v0.0.2-abc1234/            # Version-specific
      full_firmware.bin
      ota_firmware.bin
    latest/                     # Always points to latest
      full_firmware.bin
      ota_firmware.bin
```

#### ota.json Format

The `ota.json` file at the bucket root tracks all released versions:

```json
{
  "latest": "v0.0.2-abc1234",
  "versions": {
    "v0.0.2-abc1234": {
      "url": "https://s3.uocloud.com/bucket/firmware/v0.0.2-abc1234/ota_firmware.bin",
      "sha256": "abc123...",
      "size": 1234567
    },
    "v0.0.1-def5678": {
      "url": "https://s3.uocloud.com/bucket/firmware/v0.0.1-def5678/ota_firmware.bin",
      "sha256": "def456...",
      "size": 1234000
    }
  }
}
```

This allows badges to:
- Check current latest version
- Download firmware with verified SHA256 checksum
- Display firmware size before downloading
- Implement OTA updates pointing to the `latest` field

## Troubleshooting

### Build fails with "Submodule not initialized"

The workflows use `submodules: recursive` which should handle this automatically. If it fails:
- Check that `.gitmodules` is correctly configured
- Ensure submodules are accessible (not private repos requiring auth)

### Build fails with ESP-IDF errors

The cache might be corrupted:
1. Go to Actions → Caches
2. Delete the `esp-idf-*` cache
3. Re-run the workflow (will take longer but rebuild cache)

### Release fails to push tags

Check that the workflow has `contents: write` permission:
- Settings → Actions → General → Workflow permissions
- Select "Read and write permissions"

### S3 upload fails

Verify your secrets are correctly set:
```bash
# Test S3 access locally
aws s3 ls s3://your-bucket/ --endpoint-url https://s3.uocloud.com
```

If successful locally but fails in GitHub Actions:
- Check secret names match exactly
- Ensure variables are set as "Variables" not "Secrets"
- Verify endpoint URL format

### Build is slow (>15 minutes with cache)

This is expected for the first build. Subsequent builds should be faster:
- Check that caches are being hit (look for "Cache restored" in logs)
- mpy-cross and ESP-IDF caches are the biggest time savers
- Full clean builds will always be slow

## Comparison to GitLab CI

### Advantages
✅ Better caching (GitHub Actions cache is faster)  
✅ Native GitHub integration  
✅ Free for public repos  
✅ Better UI and logs  
✅ Workflow visualization
✅ **Single unified workflow** for build and release

### Differences
- GitLab: Uses separate jobs for build and release
- GitHub: Single workflow with conditional release steps
- GitLab: Artifact links in release  
- GitHub: Binary files attached to release
- GitLab: Manual workflow trigger for release
- GitHub: Automatic release on tag push

## Local Testing

You can test the build process locally using the same commands:

```bash
# Test version bump
make bump_version

# Test full release (without pushing)
make release

# Undo test release
git tag -d v0.0.2-abc1234
git reset --hard HEAD~1
```

See [docs/release_process.md](../docs/release_process.md) for detailed local testing guide.

## Monitoring

### Build Status Badge

Add this to your README.md to show build status:

```markdown
![Build Status](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/build.yml/badge.svg)
```

### Email Notifications

GitHub Actions automatically sends email notifications on:
- Workflow failures
- First workflow success after a failure

Configure in: Settings → Notifications → Actions

## Future Improvements

Potential enhancements:
- [ ] Add firmware size checks
- [ ] Run tests before building
- [ ] Build minimal firmware variant in parallel
- [ ] Matrix builds for multiple configurations
- [ ] Automated changelog generation
- [ ] Firmware signing for OTA security
- [ ] Deploy to staging environment for testing

## Support

For issues with the workflows:
1. Check the Actions tab for detailed logs
2. Review troubleshooting section above
3. See [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) for general issues
4. Open an issue with workflow run URL
