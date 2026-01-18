# GitHub Actions Setup Checklist

Follow these steps to enable CI/CD for the Disobey Badge 2025 firmware.

## ✅ Step 1: Files Created (DONE)

- [x] `.github/workflows/build.yml` - Unified build & release workflow
- [x] `scripts/bump_version.sh` - Version bumping script
- [x] Updated `Makefile` with release targets
- [x] Documentation created

## 📋 Step 2: Configure GitHub Repository

### 2.1 Enable GitHub Actions

1. Go to your repository on GitHub
2. Click **Settings** → **Actions** → **General**
3. Under "Actions permissions", select:
   - ✅ **Allow all actions and reusable workflows**
4. Under "Workflow permissions", select:
   - ✅ **Read and write permissions**
   - ✅ **Allow GitHub Actions to create and approve pull requests**
5. Click **Save**

### 2.2 Configure S3 Storage (for firmware uploads)

#### Add Secrets

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add the following secrets:

| Secret Name | Value | Example |
|-------------|-------|---------|
| `S3_ACCESS_KEY_ID` | Your S3 access key | `AKIAIOSFODNN7EXAMPLE` |
| `S3_SECRET_ACCESS_KEY` | Your S3 secret key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |

#### Add Variables

1. Click on **Variables** tab
2. Click **New repository variable**
3. Add the following variables:

| Variable Name | Value | Example |
|---------------|-------|---------|
| `S3_ENDPOINT` | Your S3 endpoint URL | `https://s3.uocloud.com` |
| `S3_BUCKET` | Your S3 bucket name | `disobey-firmware` |

**Note:** If you skip S3 configuration, releases will still work but firmware won't be uploaded to S3 (only to GitHub Releases).

## 🚀 Step 3: Push Workflows to GitHub

```bash
# Add the new files
git add .github/ scripts/ docs/ Makefile

# Commit
git commit -m "Add GitHub Actions CI/CD

- Unified build & release workflow
- Automatic release on tag push
- S3 upload for firmware distribution
- Comprehensive caching for faster builds"

# Push to GitHub
git push origin main
```

## 🧪 Step 4: Test the Build Workflow

The build workflow should start automatically after pushing. Monitor it:

1. Go to **Actions** tab on GitHub
2. You should see "Build Firmware" workflow running
3. Click on it to see the progress
4. First build will take ~15-20 minutes (setting up caches)
5. Subsequent builds will be ~5-10 minutes

## 🎯 Step 5: Test Release Workflow

Once the build workflow succeeds, test the release:

```bash
# Step 1: Create a release locally
make release

# Step 2: Push the tag to GitHub
git push origin main --tags
```

Once the tag is pushed to GitHub, the workflow automatically:
- ✅ Detects it's a tagged build
- ✅ Builds firmware at that tag
- ✅ Uploads to S3 (if configured)
- ✅ Updates OTA.json

**Monitor the release:**
1. Go to **Actions** tab
2. You'll see "Build Firmware" workflow running
3. In the logs, look for "This is a release: v0.0.2-xxxxx"
4. Watch the S3 upload and OTA.json update steps
5. Verify firmware in S3 bucket

## 📊 Step 6: Monitor and Verify

### Check Build Status

- Builds should appear in Actions tab for every push
- Green checkmark = success
- Red X = failure (click for logs)

### Check Releases

1. Go to **Releases** section (right sidebar)
2. You should see your release with:
   - Version tag (e.g., `v0.0.2-abc1234`)
   - Three firmware files attached
   - Release notes

### Check S3 Storage

If S3 is configured, verify uploads:

```bash
aws s3 ls s3://your-bucket/firmware/ --endpoint-url https://s3.uocloud.com
```

You should see:
```
firmware/v0.0.2-abc1234/
firmware/latest/
```

## 🔧 Troubleshooting

### "Workflow not found"

- Make sure `.github/workflows/` directory exists
- Ensure YAML files are in the correct location
- Check file permissions (should be readable)

### "Permission denied" errors

- Go to Settings → Actions → General
- Change Workflow permissions to "Read and write"

### Build fails immediately

- Check that submodules are accessible
- Ensure `.gitmodules` is correct
- Try running `git submodule update --init --recursive` locally

### S3 upload fails but release succeeds

- This is expected if S3 is not configured
- The workflow will skip S3 upload gracefully
- Firmware is still available in GitHub Release

## 📚 Next Steps

Once everything is working:

1. ✅ Add build status badge to README:
   ```markdown
   ![Build](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/build.yml/badge.svg)
   ```

2. ✅ Update README with release instructions

3. ✅ Configure OTA updates to use S3 URLs

4. ✅ Set up notifications for failed builds

## 📖 Documentation

- [Release Process](release_process.md) - How to create releases
- [GitHub Actions Guide](github_actions.md) - Detailed workflow documentation
- [Troubleshooting](../TROUBLESHOOTING.md) - General troubleshooting

## 🎉 Success Criteria

You're all set when:

- ✅ Build workflow runs on every push
- ✅ Build completes in <20 min (first time) or <10 min (cached)
- ✅ Tagged commits trigger release build
- ✅ S3 storage contains firmware (if configured)
- ✅ OTA.json is updated with each release
- ✅ Tags are created and pushed automatically

---

**Status:** Setup complete! Ready to push to GitHub.
