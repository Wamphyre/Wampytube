# WampyTube - YouTube Video Downloader

A modern, macOS-optimized YouTube video downloader with hardware acceleration support and a beautiful native interface.

![WampyTube Icon](icon.png)

## Features

- **High-Quality Downloads**: Automatically downloads videos in the highest available quality (up to 4K)
- **Hardware Acceleration**: Uses macOS VideoToolbox for blazing-fast HEVC (H.265) encoding
- **GPU Support**: Automatically detects and utilizes AMD, Intel, or Apple Silicon GPUs
- **Modern Interface**: Clean, native macOS design with automatic dark/light mode support
- **Smart Processing**: Downloads video and audio streams separately for optimal quality
- **Real-time Progress**: Live encoding progress with FPS monitoring
- **Efficient**: Multi-threaded downloads and processing for maximum performance
- **Native App**: Runs as a true macOS application without showing "Python" in the menu bar

## Requirements

- macOS 10.14 or later
- Python 3.8 or higher
- FFmpeg (included in the repository)

## Installation

### Option 1: Download Pre-built App

Download the latest release from the [Releases](https://github.com/yourusername/wampytube/releases) page and drag WampyTube.app to your Applications folder.

### Option 2: Build from Source

1. Clone the repository:
```bash
git clone https://github.com/yourusername/wampytube.git
cd wampytube
```

2. Install Python dependencies:
```bash
pip3 install -r requirements.txt
```

3. Build the native macOS app:
```bash
chmod +x build_app.sh
./build_app.sh
```

The script will:
- Check all dependencies
- Create a native C launcher (no Python in menu!)
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

The `build_app.sh` script creates a true native macOS application:

1. **Native C Launcher**: Eliminates "Python" from the menu bar
2. **Smart Python Detection**: Finds Python in multiple locations
3. **Automatic Icon Generation**: Converts PNG to macOS ICNS format
4. **Code Signing**: Signs the app for Gatekeeper (if certificates available)
5. **DMG Creation**: Optional disk image for easy distribution

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
# 2. Create native C launcher
# 3. Generate app bundle
# 4. Optionally create DMG
# 5. Test the app
```

## File Structure

```
wampytube/
├── wampytube.py       # Main application
├── ffmpeg            # FFmpeg binary
├── icon.png          # Application icon
├── requirements.txt  # Python dependencies
├── build_app.sh     # Native app build script
├── README.md        # This file
└── dist/            # Build output (created by build script)
    ├── WampyTube.app/   # macOS application
    └── WampyTube.dmg    # Distribution image (optional)
```

## Dependencies

- **pytubefix**: YouTube video downloader library
- **tkinter**: GUI framework (included with Python)
- **psutil**: System resource monitoring
- **requests**: HTTP library

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
- Or install manually: `pip3 install pytubefix requests psutil`

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

## Acknowledgments

- FFmpeg for video processing
- pytubefix for YouTube integration
- The macOS developer community

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

## Changelog

### v1.0.0
- Initial release
- Hardware-accelerated video encoding
- Native macOS app with C launcher
- Automatic dark/light mode support
- Multi-threaded downloading