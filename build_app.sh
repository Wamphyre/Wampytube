#!/bin/bash

# WampyTube PyInstaller Build
# Creates a 100% self-contained macOS app with embedded Python

echo "WampyTube Self-Contained App Build"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if we have required tools
echo "Checking build tools..."
PYTHON_CMD=$(which python3)
if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}Error: python3 not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ python3 found: $PYTHON_CMD${NC}"

# Check required files
echo "Checking files..."
for file in wampytube.py requirements.txt ffmpeg icon.png; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}Error: $file not found!${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ $file found${NC}"
done

# Make ffmpeg executable
chmod +x ffmpeg

# Install PyInstaller and dependencies
echo ""
echo "Installing PyInstaller and dependencies..."
pip3 install pyinstaller
pip3 install -r requirements.txt

# Test dependencies
if ! $PYTHON_CMD -c "import tkinter, pytubefix, requests, psutil, customtkinter, PyInstaller" 2>/dev/null; then
    echo -e "${RED}Failed to install dependencies!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ All dependencies installed${NC}"

# Create PyInstaller spec file for better control
echo ""
echo "Creating PyInstaller spec file..."
cat > wampytube.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Get current directory
current_dir = os.path.dirname(os.path.abspath(SPEC))

# Collect data files for customtkinter
customtkinter_datas = collect_data_files('customtkinter')

# Additional data files
added_files = [
    ('ffmpeg', '.'),
    ('icon.png', '.'),
]

# Hidden imports to ensure all modules are included
hiddenimports = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'customtkinter',
    'pytubefix',
    'requests',
    'psutil',
    'PIL',
    'PIL.Image',
    'concurrent.futures',
    'threading',
    'subprocess',
    'pathlib',
    'logging',
    'functools',
    're',
    'time',
    'os',
    'sys',
]

# Collect all customtkinter submodules
hiddenimports.extend(collect_submodules('customtkinter'))

a = Analysis(
    ['wampytube.py'],
    pathex=[current_dir],
    binaries=[],
    datas=customtkinter_datas + added_files,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WampyTube',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WampyTube',
)

app = BUNDLE(
    coll,
    name='WampyTube.app',
    icon='icon.png',
    bundle_identifier='com.wampytube.app',
    version='1.1.1',
    info_plist={
        'CFBundleName': 'WampyTube',
        'CFBundleDisplayName': 'WampyTube',
        'CFBundleVersion': '1.1.1',
        'CFBundleShortVersionString': '1.1.1',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.14',
        'LSApplicationCategoryType': 'public.app-category.video',
        'NSRequiresAquaSystemAppearance': False,
        'NSHumanReadableCopyright': 'Copyright © 2024 WampyTube',
    },
)
EOF

echo -e "${GREEN}✓ PyInstaller spec file created${NC}"

# Create icon if needed
if [ -f "icon.png" ] && [ ! -f "icon.icns" ]; then
    echo "Creating macOS icon..."
    mkdir -p icon.iconset
    
    # Create all required icon sizes
    for size in 16 32 128 256 512; do
        sips -z $size $size icon.png --out icon.iconset/icon_${size}x${size}.png >/dev/null 2>&1
        if [ $size -ne 512 ]; then
            sips -z $((size*2)) $((size*2)) icon.png --out icon.iconset/icon_${size}x${size}@2x.png >/dev/null 2>&1
        fi
    done
    sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png >/dev/null 2>&1
    
    iconutil -c icns icon.iconset >/dev/null 2>&1
    rm -rf icon.iconset
    echo -e "${GREEN}✓ Icon created${NC}"
fi

# Build with PyInstaller
echo ""
echo "Building self-contained app with PyInstaller..."
rm -rf dist build

# Run PyInstaller with the spec file
pyinstaller --clean --noconfirm wampytube.spec

if [ ! -d "dist/WampyTube.app" ]; then
    echo -e "${RED}Error: PyInstaller build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Self-contained app built successfully${NC}"

# PyInstaller already created the complete app bundle
# Just need to make ffmpeg executable and add any missing resources
echo "Finalizing app bundle..."

# Make sure ffmpeg is executable
if [ -f "dist/WampyTube.app/Contents/MacOS/ffmpeg" ]; then
    chmod +x "dist/WampyTube.app/Contents/MacOS/ffmpeg"
elif [ -f "dist/WampyTube.app/Contents/Resources/ffmpeg" ]; then
    chmod +x "dist/WampyTube.app/Contents/Resources/ffmpeg"
fi

# Copy icon if it exists and wasn't included
if [ -f "icon.icns" ] && [ ! -f "dist/WampyTube.app/Contents/Resources/icon.icns" ]; then
    cp icon.icns "dist/WampyTube.app/Contents/Resources/"
fi

echo -e "${GREEN}✓ App bundle finalized${NC}"

# Try to sign the app
echo "Signing app..."
if security find-identity -p codesigning 2>/dev/null | grep -q "Developer ID"; then
    # Sign with Developer ID if available
    IDENTITY=$(security find-identity -p codesigning | grep "Developer ID Application" | head -1 | awk '{print $2}')
    codesign --force --deep --sign "$IDENTITY" "dist/WampyTube.app"
    echo -e "${GREEN}✓ App signed with Developer ID${NC}"
else
    # Ad-hoc sign
    codesign --force --deep --sign - "dist/WampyTube.app" 2>/dev/null || {
        echo -e "${YELLOW}Note: Could not sign app (no developer certificate)${NC}"
    }
fi

# Remove quarantine
xattr -dr com.apple.quarantine "dist/WampyTube.app" 2>/dev/null || true

echo -e "${GREEN}✓ App preparation complete${NC}"

# Clean up
rm -f wampytube.spec
rm -rf build

# Show results
APP_SIZE=$(du -sh "dist/WampyTube.app" | awk '{print $1}')
echo ""
echo -e "${BLUE}Self-Contained App Build Complete! 🎉${NC}"
echo "====================================="
echo "App: dist/WampyTube.app"
echo "Size: $APP_SIZE"
echo ""
echo -e "${BLUE}Key Features:${NC}"
echo "• 100% self-contained (includes Python + all dependencies)"
echo "• No external dependencies required"
echo "• Hardware-accelerated video processing"
echo "• Native macOS app bundle"
echo "• Automatic dark/light mode support"
echo ""
echo -e "${BLUE}Installation:${NC}"
echo "1. Drag dist/WampyTube.app to /Applications"
echo "2. Double-click to run"
echo "3. If blocked: Right-click → Open (first time only)"

# Optional: Create DMG
echo ""
read -p "Create DMG for distribution? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Creating DMG..."
    
    # Create temporary DMG directory
    DMG_DIR=$(mktemp -d)
    mkdir -p "$DMG_DIR/.background"
    
    # Copy app
    cp -R "dist/WampyTube.app" "$DMG_DIR/"
    
    # Create symbolic link to Applications
    ln -s /Applications "$DMG_DIR/Applications"
    
    # Create DMG
    hdiutil create -volname "WampyTube" \
        -srcfolder "$DMG_DIR" \
        -ov -format UDZO \
        -fs HFS+ \
        "dist/WampyTube.dmg"
    
    # Clean up
    rm -rf "$DMG_DIR"
    
    if [ -f "dist/WampyTube.dmg" ]; then
        DMG_SIZE=$(du -sh "dist/WampyTube.dmg" | awk '{print $1}')
        echo -e "${GREEN}✓ DMG created successfully${NC}"
        echo "DMG: dist/WampyTube.dmg"
        echo "Size: $DMG_SIZE"
    fi
fi

# Test the app
echo ""
read -p "Test the native app now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Launching WampyTube..."
    
    # Remove quarantine again
    xattr -dr com.apple.quarantine "dist/WampyTube.app" 2>/dev/null || true
    
    # Open the app
    open "dist/WampyTube.app"
    
    sleep 3
    if pgrep -f "WampyTube" >/dev/null; then
        echo -e "${GREEN}✓ WampyTube launched successfully!${NC}"
        echo "The app is now running completely self-contained!"
    else
        echo -e "${YELLOW}App may have launched. Check if the window appeared.${NC}"
    fi
fi

echo ""
echo -e "${GREEN}Build complete! WampyTube is now 100% self-contained! 🎬${NC}"