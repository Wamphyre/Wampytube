# WampyTube - YouTube Video Downloader

A modern, macOS-optimized YouTube video downloader with hardware acceleration support and a beautiful native interface.

![WampyTube Icon](icon.png)

## Features

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

- macOS 10.14 or later
- Python 3.8 or higher
- FFmpeg (included in the repository)

## Installation

### Option 1: Download Pre-built App

Download the latest release from the [Releases](https://github.com/Wamphyre/Wampytube/releases) page and drag WampyTube.app to your Applications folder.

### Option 2: Build from Source

1. Clone the repository:
```bash
git clone https://github.com/Wamphyre/Wampytube.git
cd Wampytube
```

2. Install Python dependencies:
```bash
pip3 install -r requirements.txt
```

3. Build the macOS app:
```bash
chmod +x build_app.sh
./build_app.sh
```

The script will:
- Check all dependencies
- Create a native launcher
- Generate a proper macOS app bundle
- Optionally create a DMG for distribution

4. Find your app in the `dist/` folder:
```bash
open dist/WampyTube.app
```

### Option 3: Run Directly (Development)

```bash
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

## Building the App

The `build_app.sh` script creates a macOS application bundle:

1. **Native Launcher**: Custom shell script launcher that replaces Python branding
2. **Smart Python Detection**: Finds Python in multiple locations
3. **Automatic Icon Generation**: Converts PNG to macOS ICNS format
4. **Menu Bar Integration**: Ensures "WampyTube" appears instead of "Python"
5. **Code Signing**: Signs the app for Gatekeeper (if certificates available)
6. **DMG Creation**: Optional disk image for easy distribution

### Build Requirements

- Xcode Command Line Tools (`xcode-select --install`)
- Python 3 with tkinter support
- Required Python packages (installed automatically)

### Build Process

```bash
# Make script executable
chmod +x build_app.sh

# Run build
./build_app.sh

# The script will:
# 1. Check all dependencies
# 2. Create native shell launcher (eliminates Python branding)
# 3. Generate app bundle with proper icon integration
# 4. Configure Info.plist for native app behavior
# 5. Optionally create DMG for distribution
# 6. Test the app
```

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

- **customtkinter**: Modern and customizable GUI framework (NEW in v1.1.0)
- **pytubefix**: YouTube video downloader library
- **psutil**: System resource monitoring
- **requests**: HTTP library
- **PIL (Pillow)**: Image processing for icons and UI elements

## Troubleshooting

### FFmpeg not found
- The build script includes ffmpeg in the app bundle
- For development, ensure `ffmpeg` is in the same directory as `wampytube.py`
- Make it executable: `chmod +x ffmpeg`

### App won't open (Gatekeeper)
- Right-click the app and select "Open"
- Or remove quarantine: `xattr -cr /Applications/WampyTube.app`

### Python dependencies missing
- The app will attempt to install them automatically
- Or install manually: `pip3 install pytubefix requests psutil customtkinter`
- **Note**: CustomTkinter is required for the modern GUI (new in v1.1.0)

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

This project is licensed under the MIT License - see the LICENSE file for details.

## Changelog

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