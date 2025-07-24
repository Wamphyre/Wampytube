# WampyTube - YouTube Video Downloader

A modern, macOS-optimized YouTube video downloader with hardware acceleration support and a beautiful native interface. **Now 100% self-contained with no external dependencies required!**

![WampyTube Icon](icon.png)

## Features

- **🎯 100% Self-Contained**: No Python or external dependencies required - everything is bundled!
- **High-Quality Downloads**: Automatically downloads videos in the highest available quality (up to 4K)
- **Hardware Acceleration**: Uses macOS VideoToolbox for blazing-fast HEVC (H.265) encoding
- **GPU Support**: Automatically detects and utilizes AMD, Intel, or Apple Silicon GPUs
- **Modern CustomTkinter GUI**: Completely rebuilt interface using CustomTkinter for a native look
- **Native macOS App**: True native application with custom icon and menu bar integration
- **Custom Menu Bar**: Professional "WampyTube" menu instead of generic "Python" menu
- **About Dialog**: Custom About dialog with app icon and system information
- **Dark/Light Mode**: Automatic theme detection and beautiful modern interface
- **Smart Processing**: Downloads video and audio streams separately for optimal quality
- **Real-time Progress**: Live encoding progress with FPS monitoring
- **Efficient**: Multi-threaded downloads and processing for maximum performance

## Requirements

- **For Users**: macOS 10.14 or later (that's it!)
- **For Developers**: Python 3.8+ and build tools (see Building section)

## Installation

### 🚀 For Users (Recommended)

**Simply download and run - no setup required!**

1. Download the latest release from the [Releases](https://github.com/Wamphyre/Wampytube/releases) page
2. Drag `WampyTube.app` to your Applications folder
3. Double-click to run (first time: right-click → Open if blocked by Gatekeeper)

**That's it!** The app is completely self-contained with Python and all dependencies bundled inside.

### 🛠️ For Developers (Build from Source)

1. Clone the repository:
```bash
git clone https://github.com/Wamphyre/Wampytube.git
cd Wampytube
```

2. Build the self-contained app:
```bash
chmod +x build_app.sh
./build_app.sh
```

The script will:
- Install PyInstaller and all dependencies automatically
- Create a 100% self-contained app bundle with embedded Python
- Generate a proper macOS app with native integration
- Optionally create a DMG for distribution

3. Find your app in the `dist/` folder:
```bash
open dist/WampyTube.app
```

### 🔧 Development Mode (Optional)

For development only:
```bash
pip3 install -r requirements.txt
python3 wampytube.py
```

## Usage

1. **Copy a YouTube URL** to your clipboard
2. **Launch WampyTube**
3. **Click "Paste"** to insert the URL
4. **Select output folder** (defaults to Downloads)
5. **Click "Download Video"**

The app will:
- Analyze available video streams
- Download the highest quality video and audio
- Merge them using hardware acceleration
- Save as an optimized HEVC (H.265) MP4 file

## Technical Details

### Hardware Acceleration

WampyTube automatically detects your system's GPU and uses:
- **VideoToolbox** for hardware-accelerated HEVC encoding on macOS
- **Intelligent fallback** to CPU encoding if GPU acceleration fails
- **Optimized settings** based on video resolution

### Performance

- **Multi-threaded downloads**: Parallel video and audio stream downloads
- **Hardware encoding**: Up to 10x faster than CPU encoding
- **Progress monitoring**: Real-time FPS and progress updates
- **Resource optimization**: Automatic CPU thread allocation

### Supported GPUs

- Apple Silicon (M1, M2, M3)
- AMD Radeon GPUs
- Intel integrated graphics

## Building the Self-Contained App

The `build_app.sh` script uses **PyInstaller** to create a completely self-contained macOS application:

### Key Features of the Build Process

1. **🐍 Embedded Python**: Includes Python interpreter inside the app bundle
2. **📦 All Dependencies Bundled**: PyTubeFix, CustomTkinter, and all libraries included
3. **⚡ FFmpeg Included**: Video processing binary embedded in the app
4. **🎨 Native Integration**: Proper macOS app bundle with icon and Info.plist
5. **🔐 Code Signing**: Automatic signing for Gatekeeper compatibility
6. **💿 DMG Creation**: Optional disk image for easy distribution

### Build Requirements (Developers Only)

- Python 3.8 or higher
- pip3 (Python package manager)
- macOS development tools

### Build Process

```bash
# Clone and enter directory
git clone https://github.com/Wamphyre/Wampytube.git
cd Wampytube

# Make script executable and run
chmod +x build_app.sh
./build_app.sh

# The script automatically:
# 1. Installs PyInstaller and all dependencies
# 2. Creates optimized PyInstaller spec file
# 3. Builds self-contained app with embedded Python
# 4. Includes FFmpeg and all resources
# 5. Signs the app bundle
# 6. Optionally creates DMG for distribution
```

### What Makes It Self-Contained

- **No Python Required**: Python interpreter is embedded in the app
- **No pip install**: All Python packages are bundled
- **No FFmpeg Install**: Video processing binary is included
- **No External Dependencies**: Everything needed is inside the .app bundle
- **Portable**: Can run on any macOS 10.14+ system without setup

## File Structure

```
wampytube/
├── wampytube.py       # Main application
├── ffmpeg            # FFmpeg binary
├── icon.png          # Application icon
├── requirements.txt  # Python dependencies
├── build_app.sh     # App build script
├── README.md        # This file
└── dist/            # Build output (created by build script)
    ├── WampyTube.app/   # macOS application
    └── WampyTube.dmg    # Distribution image (optional)
```

## Dependencies

### For Users
**None!** The app is completely self-contained.

### For Developers (Build Dependencies)
- **pyinstaller**: Creates self-contained executable with embedded Python
- **customtkinter**: Modern and customizable GUI framework
- **pytubefix**: YouTube video downloader library
- **psutil**: System resource monitoring
- **requests**: HTTP library
- **PIL (Pillow)**: Image processing for icons and UI elements

## Troubleshooting

### App won't open (Gatekeeper)
- **First time**: Right-click the app and select "Open"
- Or remove quarantine: `xattr -cr /Applications/WampyTube.app`
- The app is self-contained, so no other setup is needed

### "Python dependencies missing" (Development only)
- **For users**: This shouldn't happen with the self-contained app
- **For developers**: Run `pip3 install -r requirements.txt`
- **Building**: The build script installs everything automatically

### Download fails
- Check your internet connection
- Verify the YouTube URL is valid
- Some videos may have geographic restrictions

### Slow encoding
- Hardware acceleration requires a compatible GPU
- CPU fallback is slower but works on all systems
- Higher resolution videos take longer to process

## Advanced Features

### Custom FFmpeg Options

The app uses optimized FFmpeg settings:
- **VideoToolbox HEVC**: `-c:v hevc_videotoolbox -b:v 6M`
- **CPU HEVC**: `-c:v libx265 -preset medium -crf 26`
- **Audio**: `-c:a aac -b:a 192k`

### Debug Mode

View detailed logs in the Activity Log section of the app.

## License

This project is licensed under the BSD 3-Clause License - see the [LICENSE](LICENSE) file for details.

## Changelog

### v1.2.0 (Current)
- **🎯 100% Self-Contained App**: Complete migration to PyInstaller for embedded Python
- **📦 No Dependencies Required**: Users no longer need Python or pip installations
- **⚡ Optimized Build Process**: Automated PyInstaller workflow with UPX compression
- **🔐 Enhanced Security**: Proper code signing and Gatekeeper compatibility
- **📱 Improved Portability**: Single .app file runs on any macOS 10.14+ system
- **🛠️ Developer Experience**: Simplified build process with automatic dependency management

### v1.1.1
- **Quality Selection**: Added dropdown selector for available video resolutions
- **Audio Language Selection**: Added selector for different audio tracks and languages
- **Enhanced Video Analysis**: Better detection of available streams and audio languages
- **Improved Layout**: Compact side-by-side design for quality and audio selectors
- **Better Window Sizing**: Automatic window adjustment when video info is displayed

### v1.1.0
- **Complete GUI Rebuild**: Entire interface reconstructed using CustomTkinter for modern aesthetics
- **Native App Identity**: Complete removal of "Python" branding from menu bar and dock
- **Custom Menu Bar**: Professional "WampyTube" menu with About, File, and Edit options
- **Custom About Dialog**: Personalized About dialog featuring the app icon and system info
- **Enhanced Icon Integration**: Proper icon display in dock, menu bar, and About dialog
- **Modern UI Framework**: Migrated from tkinter to CustomTkinter for better macOS integration
- **Keyboard Shortcuts**: Added Cmd+Q (Quit), Cmd+O (Open Folder), Cmd+V (Paste URL)
- **Improved User Experience**: More polished and professional native macOS integration

### v1.0.0
- Initial release
- Hardware-accelerated video encoding
- macOS app bundle with custom launcher
- Automatic dark/light mode support
- Multi-threaded downloading