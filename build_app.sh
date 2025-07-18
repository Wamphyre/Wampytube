#!/bin/bash

# WampyTube Native Launcher Build
# Creates a native C executable to completely eliminate Python menu

echo "WampyTube Native Launcher Build"
echo "==============================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if we have required tools
echo "Checking build tools..."
if ! command -v gcc >/dev/null 2>&1; then
    echo -e "${RED}Error: gcc not found. Install Xcode Command Line Tools:${NC}"
    echo "xcode-select --install"
    exit 1
fi
echo -e "${GREEN}✓ gcc found${NC}"

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

# Test Python dependencies
echo ""
echo "Testing Python dependencies..."
PYTHON_CMD=$(which python3)
echo "Using Python: $PYTHON_CMD"

if ! $PYTHON_CMD -c "import tkinter, pytubefix, requests, psutil" 2>/dev/null; then
    echo -e "${YELLOW}Missing dependencies. Installing...${NC}"
    pip3 install -r requirements.txt
    
    # Test again
    if ! $PYTHON_CMD -c "import tkinter, pytubefix, requests, psutil" 2>/dev/null; then
        echo -e "${RED}Failed to install dependencies!${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ All dependencies available${NC}"

# Create the native C launcher
echo ""
echo "Creating native C launcher..."
cat > wampytube_launcher.c << 'EOF'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <libgen.h>
#include <sys/stat.h>
#include <CoreFoundation/CoreFoundation.h>

// Function to get the bundle path
char* get_bundle_path() {
    CFBundleRef bundle = CFBundleGetMainBundle();
    if (!bundle) return NULL;
    
    CFURLRef bundleURL = CFBundleCopyBundleURL(bundle);
    CFURLRef resourcesURL = CFBundleCopyResourcesDirectoryURL(bundle);
    CFURLRef absoluteResourcesURL = CFURLCopyAbsoluteURL(resourcesURL);
    
    CFStringRef path = CFURLCopyFileSystemPath(absoluteResourcesURL, kCFURLPOSIXPathStyle);
    
    CFIndex length = CFStringGetLength(path);
    CFIndex maxSize = CFStringGetMaximumSizeForEncoding(length, kCFStringEncodingUTF8) + 1;
    char* buffer = malloc(maxSize);
    
    CFStringGetCString(path, buffer, maxSize, kCFStringEncodingUTF8);
    
    CFRelease(path);
    CFRelease(absoluteResourcesURL);
    CFRelease(resourcesURL);
    CFRelease(bundleURL);
    
    return buffer;
}

// Function to find Python with dependencies
char* find_python_with_deps() {
    char* candidates[] = {
        "/opt/homebrew/bin/python3",     // Apple Silicon Homebrew
        "/usr/local/bin/python3",         // Intel Homebrew
        "/usr/bin/python3",               // System Python
        "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/3.9/bin/python3",
        NULL
    };
    
    char test_cmd[1024];
    
    for (int i = 0; candidates[i] != NULL; i++) {
        // Check if file exists and is executable
        if (access(candidates[i], X_OK) == 0) {
            // Test if it has required modules
            snprintf(test_cmd, sizeof(test_cmd), 
                "%s -c \"import tkinter, pytubefix, requests, psutil\" 2>/dev/null", 
                candidates[i]);
            
            if (system(test_cmd) == 0) {
                char* result = malloc(strlen(candidates[i]) + 1);
                strcpy(result, candidates[i]);
                return result;
            }
        }
    }
    
    return NULL;
}

int main(int argc, char* argv[]) {
    // Get bundle resources path
    char* bundle_path = get_bundle_path();
    if (!bundle_path) {
        fprintf(stderr, "Error: Could not get bundle path\n");
        return 1;
    }
    
    // Construct paths
    char main_script[1024];
    char ffmpeg_path[1024];
    
    snprintf(main_script, sizeof(main_script), "%s/wampytube.py", bundle_path);
    snprintf(ffmpeg_path, sizeof(ffmpeg_path), "%s/ffmpeg", bundle_path);
    
    // Make ffmpeg executable
    chmod(ffmpeg_path, 0755);
    
    // Check if main script exists
    if (access(main_script, R_OK) != 0) {
        fprintf(stderr, "Error: wampytube.py not found at %s\n", main_script);
        free(bundle_path);
        return 1;
    }
    
    // Find Python with dependencies
    char* python_exe = find_python_with_deps();
    if (!python_exe) {
        // Show error dialog using osascript
        system("osascript -e 'display dialog \"Python 3 with required dependencies not found!\\n\\nPlease install:\\npip3 install pytubefix requests psutil\\n\\nOr download Python from python.org\" with title \"WampyTube Error\" buttons {\"OK\"} with icon stop'");
        free(bundle_path);
        return 1;
    }
    
    // Change to bundle directory
    if (chdir(bundle_path) != 0) {
        fprintf(stderr, "Error: Could not change to bundle directory\n");
        free(bundle_path);
        free(python_exe);
        return 1;
    }
    
    // Set up environment
    char new_path[2048];
    char* current_path = getenv("PATH");
    snprintf(new_path, sizeof(new_path), "%s:%s", bundle_path, current_path ? current_path : "");
    setenv("PATH", new_path, 1);
    
    // Execute Python script
    execl(python_exe, python_exe, main_script, (char*)NULL);
    
    // If we get here, exec failed
    fprintf(stderr, "Error: Failed to execute Python script\n");
    free(bundle_path);
    free(python_exe);
    return 1;
}
EOF

echo -e "${GREEN}✓ C launcher source created${NC}"

# Compile the native launcher
echo "Compiling native launcher..."
gcc -o wampytube_launcher wampytube_launcher.c -framework CoreFoundation

if [ ! -f "wampytube_launcher" ]; then
    echo -e "${RED}Error: Failed to compile native launcher${NC}"
    exit 1
fi

chmod +x wampytube_launcher
echo -e "${GREEN}✓ Native launcher compiled${NC}"

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

# Clean and create app bundle
echo ""
echo "Creating app bundle..."
rm -rf dist
mkdir -p dist/WampyTube.app/Contents/{MacOS,Resources}

# Copy the native launcher as the main executable
cp wampytube_launcher dist/WampyTube.app/Contents/MacOS/WampyTube
chmod +x dist/WampyTube.app/Contents/MacOS/WampyTube

# Copy resources
cp wampytube.py dist/WampyTube.app/Contents/Resources/
cp requirements.txt dist/WampyTube.app/Contents/Resources/
cp ffmpeg dist/WampyTube.app/Contents/Resources/
chmod +x dist/WampyTube.app/Contents/Resources/ffmpeg
cp icon.png dist/WampyTube.app/Contents/Resources/
[ -f "icon.icns" ] && cp icon.icns dist/WampyTube.app/Contents/Resources/

# Create Info.plist
cat > dist/WampyTube.app/Contents/Info.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>WampyTube</string>
    <key>CFBundleIdentifier</key>
    <string>com.wampytube.app</string>
    <key>CFBundleName</key>
    <string>WampyTube</string>
    <key>CFBundleDisplayName</key>
    <string>WampyTube</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright © 2024 WampyTube</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSMinimumSystemVersion</key>
    <string>10.14</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.video</string>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
EOF

# Add icon to Info.plist if available
if [ -f "icon.icns" ]; then
    echo "    <key>CFBundleIconFile</key>" >> dist/WampyTube.app/Contents/Info.plist
    echo "    <string>icon</string>" >> dist/WampyTube.app/Contents/Info.plist
    cp icon.icns dist/WampyTube.app/Contents/Resources/icon.icns
fi

# Close Info.plist
echo "</dict>" >> dist/WampyTube.app/Contents/Info.plist
echo "</plist>" >> dist/WampyTube.app/Contents/Info.plist

echo -e "${GREEN}✓ App bundle created${NC}"

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
rm -f wampytube_launcher.c wampytube_launcher

# Show results
APP_SIZE=$(du -sh "dist/WampyTube.app" | awk '{print $1}')
echo ""
echo -e "${BLUE}Native App Build Complete! 🎉${NC}"
echo "================================"
echo "App: dist/WampyTube.app"
echo "Size: $APP_SIZE"
echo ""
echo -e "${BLUE}Key Features:${NC}"
echo "• Native C executable (no Python in menu bar!)"
echo "• Hardware-accelerated video processing"
echo "• Menu will show 'WampyTube' instead of 'Python'"
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
    if pgrep -f "wampytube.py" >/dev/null; then
        echo -e "${GREEN}✓ WampyTube launched successfully!${NC}"
        echo "Check the menu bar - it should show 'WampyTube' NOT 'Python'!"
    else
        echo -e "${YELLOW}App may have launched. Check if the window appeared.${NC}"
    fi
fi

echo ""
echo -e "${GREEN}Build complete! Enjoy WampyTube without Python in the menu! 🎬${NC}"