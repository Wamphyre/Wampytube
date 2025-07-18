import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pytubefix import YouTube
import requests
import threading
import os
import subprocess
import re
from pathlib import Path
import logging
import concurrent.futures
import time
from functools import lru_cache
import psutil
import sys

# Global cache configuration for HTTP responses
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WampyTube")
# Remove all existing handlers to avoid duplication
logger.handlers = []
logger.propagate = False

# System resources configuration - Auto-detect cores/threads
SYSTEM_CORES = psutil.cpu_count(logical=False) or 4
SYSTEM_THREADS = psutil.cpu_count(logical=True) or 8
DOWNLOAD_THREADS = min(4, SYSTEM_THREADS // 2)
CPU_THREADS = SYSTEM_THREADS - 1  # Leave one thread for system operations

# FFmpeg configuration - Use ffmpeg from the same directory as the script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_PATH = os.path.join(SCRIPT_DIR, 'ffmpeg')

# Check if our local ffmpeg exists
if not os.path.exists(FFMPEG_PATH):
    # Fallback to system ffmpeg if local not found
    FFMPEG_PATH = 'ffmpeg'
    logger.warning(f"Local ffmpeg not found in {SCRIPT_DIR}, using system ffmpeg")
else:
    logger.info(f"Using local ffmpeg from {SCRIPT_DIR}")

# Check for GPU and hardware acceleration on macOS
def check_macos_gpu():
    """Check for GPU and VideoToolbox support on macOS"""
    try:
        # Check system profiler for GPU information
        result = subprocess.run(['system_profiler', 'SPDisplaysDataType'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        gpu_info = {'available': False, 'hevc_encoding': False, 'model': 'Unknown', 'videotoolbox': False}
        
        if result.returncode == 0:
            output = result.stdout
            
            # Look for GPU models
            if 'AMD' in output or 'Radeon' in output:
                if 'RX 6600' in output:
                    gpu_info['model'] = 'AMD RX 6600'
                elif 'Radeon' in output:
                    gpu_info['model'] = 'AMD Radeon'
                else:
                    gpu_info['model'] = 'AMD GPU'
                gpu_info['available'] = True
            elif 'Intel' in output:
                gpu_info['model'] = 'Intel GPU'
                gpu_info['available'] = True
            elif 'Apple' in output or 'M1' in output or 'M2' in output or 'M3' in output:
                if 'M1' in output:
                    gpu_info['model'] = 'Apple M1'
                elif 'M2' in output:
                    gpu_info['model'] = 'Apple M2'
                elif 'M3' in output:
                    gpu_info['model'] = 'Apple M3'
                else:
                    gpu_info['model'] = 'Apple Silicon'
                gpu_info['available'] = True
                gpu_info['hevc_encoding'] = True  # Apple Silicon has excellent HEVC support
        
        # Check if VideoToolbox is available (should be on all modern macOS)
        try:
            # VideoToolbox is available on macOS 10.8+, so we assume it's available
            gpu_info['videotoolbox'] = True
            if gpu_info['available']:
                gpu_info['hevc_encoding'] = True
        except Exception as e:
            logger.warning(f"Error checking VideoToolbox: {e}")
        
        return gpu_info
        
    except Exception as e:
        logger.error(f"Error checking macOS GPU: {e}")
        return {'model': 'Unknown', 'available': False, 'hevc_encoding': False, 'videotoolbox': False}

# Get hardware acceleration information for macOS
MACOS_GPU = check_macos_gpu()
logger.info(f"Detected GPU: {MACOS_GPU}")

# Check FFmpeg capabilities
def check_ffmpeg():
    """Check FFmpeg version and available encoders"""
    try:
        # Check FFmpeg version
        version_result = subprocess.run([FFMPEG_PATH, '-version'], 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if version_result.returncode != 0:
            return {'available': False}
        
        # Extract version
        version_match = re.search(r'ffmpeg version ([^ ]+)', version_result.stdout)
        version = version_match.group(1) if version_match else "Unknown"
        
        # Check encoders
        encoders_result = subprocess.run([FFMPEG_PATH, '-encoders'], 
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        encoders = {
            'hevc_videotoolbox': 'hevc_videotoolbox' in encoders_result.stdout,
            'h264_videotoolbox': 'h264_videotoolbox' in encoders_result.stdout,
            'libx265': 'libx265' in encoders_result.stdout,
            'libx264': 'libx264' in encoders_result.stdout,
        }
        
        return {
            'available': True,
            'version': version,
            'encoders': encoders
        }
    except Exception as e:
        logger.error(f"Error checking FFmpeg: {e}")
        return {'available': False}

# Check FFmpeg capabilities
FFMPEG_INFO = check_ffmpeg()
logger.info(f"FFmpeg information: {FFMPEG_INFO}")

# Ensure FFmpeg is available
if not FFMPEG_INFO.get('available', False):
    logger.error("FFmpeg is not installed or not in PATH. Please install FFmpeg.")
    messagebox = __import__('tkinter.messagebox').messagebox
    messagebox.showerror("Error", "FFmpeg is not installed. Please install FFmpeg.")
    exit(1)

def on_progress(stream, chunk, bytes_remaining):
    """Callback to update the progress bar during download"""
    size = stream.filesize
    bytes_downloaded = size - bytes_remaining
    percentage = (bytes_downloaded / size) * 100
    # Using throttling to reduce excessive UI updates
    current_time = time.time()
    if not hasattr(on_progress, "last_update") or current_time - on_progress.last_update > 0.1:
        root.after(0, update_progress_bar, percentage)
        on_progress.last_update = current_time

def update_progress_bar(percentage):
    """Updates the progress bar in the interface"""
    progress_bar['value'] = percentage
    progress_label.config(text=f"Downloading: {percentage:.1f}%")
    # Only log every 10% to avoid spam
    if int(percentage) % 10 == 0:
        log_message(f"Download progress: {percentage:.1f}%")

@lru_cache(maxsize=64)
def get_youtube_object(url):
    """Gets and caches the YouTube object to avoid repeated requests"""
    yt = YouTube(url, on_progress_callback=on_progress, use_oauth=False, allow_oauth_cache=True)
    yt.check_availability()
    return yt

def get_best_streams(url):
    """Gets the best available streams for the video"""
    try:
        yt = get_youtube_object(url)
        
        # Try to get the best available quality in progressive format
        streams = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc()
        
        if not streams:
            logger.info("No progressive streams found")
            return None, None, False
            
        best_progressive = streams.first()
        progressive_resolution = int(best_progressive.resolution[:-1]) if best_progressive else 0
        
        # If the best progressive resolution is less than 1080p, look for adaptive streams
        if progressive_resolution < 1080:
            video_stream = yt.streams.filter(adaptive=True, file_extension="mp4", only_video=True)\
                                .order_by("resolution").desc().first()
            audio_stream = yt.streams.filter(only_audio=True, file_extension="mp4")\
                                .order_by("abr").desc().first()
            
            if video_stream and audio_stream:
                return video_stream, audio_stream, True
        
        return best_progressive, None, False
    except Exception as e:
        logger.error(f"Error getting streams: {str(e)}")
        raise

def set_process_priority():
    """Set the process priority to maximum for faster performance on macOS"""
    try:
        # macOS priority adjustment - only if running as root
        if os.geteuid() == 0:
            os.nice(-10)
        else:
            # For normal users, use a smaller value
            os.nice(-5)
    except Exception as e:
        # This is expected for normal users, don't log as warning
        logger.debug(f"Process priority adjustment skipped: {str(e)}")

def optimize_system_resources():
    """Optimize system resources for maximum processing speed on macOS"""
    try:
        # On macOS, we have more limited options for process optimization
        try:
            # Try to increase nice value (more conservative on macOS)
            os.nice(-5)  # Modest priority boost for macOS
        except Exception as e:
            logger.debug(f"Could not set process priority: {e}")
            
        # macOS doesn't have ionice, but we can try to optimize other aspects
        try:
            # Set environment variables for better performance
            os.environ['MALLOC_ARENA_MAX'] = '4'  # Limit memory arenas
        except Exception as e:
            logger.debug(f"Could not set performance environment: {e}")
    except Exception as e:
        logger.warning(f"Could not optimize system resources: {str(e)}")

def run_ffmpeg_command(command, progress_callback=None):
    """
    Run an FFmpeg command with frame rate information and progress monitoring.
    
    Args:
        command (list): FFmpeg command as a list of arguments
        progress_callback (callable): Optional callback for progress updates
        
    Returns:
        bool: True if successful, False otherwise
        dict: Information like average frame rate
    """
    stats = {'avg_fps': 0, 'total_frames': 0, 'duration': 0}
    
    try:
        # Add global progress reporting
        if progress_callback:
            command.extend(['-progress', 'pipe:1'])
            
        # Print command for debugging
        logger.debug(f"FFmpeg command: {' '.join(command)}")
            
        # Launch FFmpeg process
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        
        # Variables for progress tracking
        start_time = time.time()
        duration_seconds = None
        frame_count = 0
        fps_stats = []
        last_fps_time = start_time
        last_progress_update = start_time
        
        # Process stdout for progress
        if process.stdout:
            for line in process.stdout:
                # Parse progress information
                if progress_callback:
                    if line.startswith('out_time_ms='):
                        try:
                            time_ms = int(line.split('=')[1])
                            current_time = time.time()
                            # Update progress every 0.5 seconds
                            if current_time - last_progress_update >= 0.5:
                                if duration_seconds:
                                    progress = min(100, (time_ms / 1000000) / duration_seconds * 100)
                                    progress_callback(progress)
                                    last_progress_update = current_time
                        except (ValueError, ZeroDivisionError):
                            pass
                    elif line.startswith('duration='):
                        try:
                            duration_str = line.split('=')[1].strip()
                            h, m, s = map(float, duration_str.split(':'))
                            duration_seconds = h * 3600 + m * 60 + s
                            stats['duration'] = duration_seconds
                        except (ValueError, IndexError):
                            pass
                    elif line.startswith('frame='):
                        try:
                            frame_count = int(line.split('=')[1])
                            stats['total_frames'] = frame_count
                            
                            # Calculate current FPS
                            current_time = time.time()
                            elapsed = current_time - start_time
                            if elapsed > 0:
                                current_fps = frame_count / elapsed
                                fps_stats.append(current_fps)
                                if len(fps_stats) > 10:  # Keep only last 10 FPS measurements
                                    fps_stats.pop(0)
                                avg_fps = sum(fps_stats) / len(fps_stats)
                                stats['avg_fps'] = avg_fps
                                
                                # Update progress with FPS info every 0.5 seconds
                                if current_time - last_fps_time >= 0.5:
                                    if progress_callback and duration_seconds and avg_fps > 0:
                                        # Estimate progress based on frames
                                        estimated_total_frames = duration_seconds * 30  # Assume 30 fps average
                                        progress = min(100, (frame_count / estimated_total_frames) * 100)
                                        progress_callback(progress, f"Encoding at {avg_fps:.1f} FPS")
                                    last_fps_time = current_time
                        except (ValueError, ZeroDivisionError):
                            pass
        
        # Wait for process to complete
        process.wait()
        
        # Calculate final stats
        if frame_count > 0:
            elapsed = time.time() - start_time
            if elapsed > 0:
                stats['avg_fps'] = frame_count / elapsed
        
        # Check if successful
        if process.returncode != 0:
            stderr_output = process.stderr.read() if process.stderr else "No error output"
            logger.error(f"FFmpeg failed with return code {process.returncode}")
            logger.error(stderr_output)
            return False, stats
        
        return True, stats
    except Exception as e:
        logger.error(f"Error running FFmpeg: {str(e)}")
        return False, stats

def merge_audio_video_with_videotoolbox(video_path, audio_path, output_path, progress_callback=None):
    """Combine audio and video with macOS VideoToolbox hardware acceleration using HEVC (H.265)"""
    if not MACOS_GPU['videotoolbox'] or not MACOS_GPU['hevc_encoding']:
        logger.warning("HEVC encoding via VideoToolbox not available, falling back to CPU")
        return False, {}
    
    try:
        # Build FFmpeg command for macOS VideoToolbox HEVC encoding
        command = [
            FFMPEG_PATH,
            '-y',  # Overwrite output files without asking
            '-i', video_path,  # Video input
            '-i', audio_path,  # Audio input
            '-c:v', 'hevc_videotoolbox',  # HEVC via VideoToolbox
            '-b:v', '6M',         # Bitrate (VideoToolbox doesn't support -q:v)
            '-c:a', 'aac',            # Audio codec
            '-b:a', '192k',           # Audio bitrate
            '-max_muxing_queue_size', '1024',  # Prevent muxing errors
            '-threads', str(CPU_THREADS),  # Use available CPU threads
            output_path
        ]
        
        # Run the command
        logger.info("Starting encoding with macOS VideoToolbox HEVC...")
        success, stats = run_ffmpeg_command(command, progress_callback)
        
        if success:
            logger.info(f"Successfully processed with VideoToolbox HEVC. Average FPS: {stats.get('avg_fps', 0):.1f}")
            return True, stats
        else:
            logger.error("VideoToolbox HEVC encoding failed")
            return False, stats
            
    except Exception as e:
        logger.error(f"Error with VideoToolbox HEVC encoding: {str(e)}")
        return False, {}

def merge_audio_video_with_cpu(video_path, audio_path, output_path, progress_callback=None):
    """Fallback to CPU encoding with high quality HEVC"""
    try:
        # Build command for CPU-based HEVC encoding
        command = [
            FFMPEG_PATH,
            '-y',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'libx265',  # CPU-based HEVC
            '-preset', 'medium',  # Balance between speed and quality
            '-x265-params', 'log-level=error',  # Reduce log spam
            '-crf', '26',  # Constant Rate Factor (quality) - lower is better
            '-c:a', 'aac',
            '-b:a', '192k',
            '-movflags', '+faststart',  # Optimize for streaming
            '-threads', str(CPU_THREADS),
            output_path
        ]
        
        logger.info("Starting CPU HEVC encoding...")
        success, stats = run_ffmpeg_command(command, progress_callback)
        
        if success:
            logger.info(f"Successfully processed with CPU HEVC. Average FPS: {stats.get('avg_fps', 0):.1f}")
            return True, stats
        
        # If HEVC failed, try H.264
        logger.info("CPU HEVC encoding failed, trying H.264...")
        command = [
            FFMPEG_PATH,
            '-y',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'libx264',  # CPU-based H.264
            '-preset', 'medium',
            '-crf', '18',  # H.264 needs a lower CRF for similar quality
            '-profile:v', 'high',
            '-level', '5.1',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-movflags', '+faststart',
            '-threads', str(CPU_THREADS),
            output_path
        ]
        
        logger.info("Starting CPU H.264 encoding...")
        success, stats = run_ffmpeg_command(command, progress_callback)
        
        if success:
            logger.info(f"Successfully processed with CPU H.264. Average FPS: {stats.get('avg_fps', 0):.1f}")
            return True, stats
        
        logger.error("All encoding methods failed")
        return False, {}
        
    except Exception as e:
        logger.error(f"Error in CPU encoding: {str(e)}")
        return False, {}

def merge_audio_video(video_path, audio_path, output_path, progress_callback=None):
    """Main function to combine audio and video with macOS hardware acceleration"""
    # Increase process priority
    set_process_priority()
    
    # Try macOS VideoToolbox hardware acceleration with HEVC (H.265)
    if MACOS_GPU['videotoolbox'] and MACOS_GPU['hevc_encoding']:
        try:
            success, stats = merge_audio_video_with_videotoolbox(video_path, audio_path, output_path, progress_callback)
            if success:
                return True, stats
        except Exception as e:
            logger.error(f"VideoToolbox HEVC encoding failed: {str(e)}")
    
    # If hardware encoding failed or not available, try CPU encoding
    logger.info("Using CPU encoding fallback...")
    return merge_audio_video_with_cpu(video_path, audio_path, output_path, progress_callback)

def download_stream(stream, output_folder, prefix=""):
    """Downloads a specific stream with optimized buffer sizes"""
    try:
        # Configure large buffer size for faster downloads
        if hasattr(stream, '_monostate'):
            if hasattr(stream._monostate, 'requests_session'):
                stream._monostate.requests_session.chunk_size = 4 * 1024 * 1024  # 4MB chunks
        
        return stream.download(output_folder, filename_prefix=prefix)
    except Exception as e:
        logger.error(f"Error downloading stream: {str(e)}")
        raise

def update_encode_progress(percentage, status_text=None):
    """Updates the progress bar for encoding progress"""
    root.after(0, lambda: progress_bar.config(value=percentage))
    if status_text:
        root.after(0, lambda: progress_label.config(text=status_text))
        root.after(0, lambda: log_message(status_text))
    else:
        text = f"Encoding: {percentage:.1f}%"
        root.after(0, lambda: progress_label.config(text=text))
        if percentage % 10 == 0:  # Log every 10%
            root.after(0, lambda: log_message(f"Encoding progress: {percentage:.1f}%"))

def download_in_thread(url, output_folder):
    """Handles the download in a separate thread"""
    try:
        # Log start of download
        root.after(0, lambda: log_message("Starting download process..."))
        
        # Optimize system resources
        optimize_system_resources()
        
        # Create the output directory if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)
        root.after(0, lambda: log_message(f"Output directory: {output_folder}"))
        
        # Get the best streams
        root.after(0, lambda: log_message("Analyzing video streams..."))
        video_stream, audio_stream, needs_merge = get_best_streams(url)
        if not video_stream:
            root.after(0, lambda: log_message("ERROR: No suitable stream found", "ERROR"))
            root.after(0, lambda: messagebox.showerror("Error", "No suitable stream found for this video."))
            return

        resolution = video_stream.resolution
        root.after(0, lambda: log_message(f"Best quality found: {resolution}"))
        root.after(0, lambda: progress_label.config(text=f"Starting download in {resolution}..."))
        
        if needs_merge:
            # Use executor to download audio and video in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=DOWNLOAD_THREADS) as executor:
                # Start video download
                root.after(0, lambda: progress_label.config(text=f"Downloading video in {resolution}..."))
                video_future = executor.submit(download_stream, video_stream, output_folder, "video_")
                
                # Start audio download (after updating the UI)
                time.sleep(0.5)  # Small pause to avoid conflicts in the progress bar
                root.after(0, lambda: progress_label.config(text="Downloading audio..."))
                root.after(0, lambda: progress_bar.config(value=0))
                audio_future = executor.submit(download_stream, audio_stream, output_folder, "audio_")
                
                # Wait for both downloads to finish
                video_path = video_future.result()
                audio_path = audio_future.result()
            
            # Combine files with macOS hardware acceleration
            acceleration = f"{MACOS_GPU['model']} VideoToolbox" if MACOS_GPU['videotoolbox'] and MACOS_GPU['hevc_encoding'] else "CPU"
            root.after(0, lambda: progress_label.config(text=f"Combining with {acceleration} HEVC acceleration..."))
            
            # Create a more specific filename with HEVC notation
            final_path = Path(video_path).parent / f"{Path(video_path).stem.replace('video_', '')}_HEVC.mp4"
            
            # Perform encoding
            success, stats = merge_audio_video(video_path, audio_path, str(final_path), update_encode_progress)
            
            if success:
                # Remove temporary files in the background
                def cleanup_temp_files():
                    try:
                        os.remove(video_path)
                        os.remove(audio_path)
                    except Exception as e:
                        logger.error(f"Error removing temporary files: {str(e)}")
                
                threading.Thread(target=cleanup_temp_files, daemon=True).start()
                
                # Show success message with HEVC info and performance stats
                codec_info = "HEVC (H.265)"
                gpu_model = MACOS_GPU['model'] if (MACOS_GPU['videotoolbox'] and MACOS_GPU['hevc_encoding']) else "CPU"
                fps_info = f"{stats.get('avg_fps', 0):.1f} FPS" if stats.get('avg_fps', 0) > 0 else "Unknown FPS"
                
                success_msg = (f"Video successfully downloaded and processed with high quality\n"
                              f"Resolution: {resolution}\n"
                              f"Codec: {codec_info}\n"
                              f"Acceleration: {gpu_model}\n"
                              f"Encoding Speed: {fps_info}\n"
                              f"Saved to: {final_path}")
                root.after(0, lambda: messagebox.showinfo("Success", success_msg))
            else:
                root.after(0, lambda: messagebox.showerror("Error", 
                    "Error combining audio and video."))
                return
        else:
            # Direct download if it's a progressive stream
            video_path = download_stream(video_stream, output_folder)
            final_path = video_path

            root.after(0, lambda: messagebox.showinfo("Success", 
                f"Video successfully downloaded in {resolution}\nSaved to: {final_path}"))
        
    except Exception as e:
        logger.error(f"Error in download: {str(e)}")
        root.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {str(e)}"))
    finally:
        root.after(0, cleanup_after_download)

def cleanup_after_download():
    """Cleans up the interface after a download"""
    download_button.config(state=tk.NORMAL)
    progress_frame.pack_forget()
    progress_bar['value'] = 0
    progress_label.config(text="")

def download_video():
    """Starts the download process"""
    url = url_entry.get().strip()
    output_folder = output_entry.get().strip()
    
    if not url:
        messagebox.showerror("Error", "Please enter a valid URL.")
        return
    if not output_folder:
        messagebox.showerror("Error", "Please select an output folder.")
        return
    
    # Validate URL (basic check)
    if not url.startswith(("http://", "https://")) or "youtube.com" not in url and "youtu.be" not in url:
        messagebox.showerror("Error", "The URL doesn't seem to be a valid YouTube address.")
        return
    
    # Reset and show the progress bar
    progress_bar['value'] = 0
    progress_label.config(text="Preparing download...")
    progress_frame.pack(fill=tk.X, padx=10, pady=5)
    
    # Disable the button during download
    download_button.config(state=tk.DISABLED)
    
    # Start the download in a separate thread
    download_thread = threading.Thread(target=download_in_thread, args=(url, output_folder))
    download_thread.daemon = True
    download_thread.start()

def select_output_folder():
    """Opens a dialog to select the output folder"""
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        output_entry.delete(0, tk.END)
        output_entry.insert(0, folder_selected)

def center_window(window, width, height):
    """Centers the window on the screen"""
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")

def paste_from_clipboard():
    """Pastes clipboard content into the URL field"""
    try:
        clipboard_text = root.clipboard_get()
        if clipboard_text:
            url_entry.delete(0, tk.END)
            url_entry.insert(0, clipboard_text)
    except:
        pass

# macOS Color Scheme
MACOS_COLORS = {
    'light': {
        'bg': '#FFFFFF',
        'secondary_bg': '#F5F5F7',
        'card_bg': '#FFFFFF',
        'text': '#1D1D1F',
        'secondary_text': '#86868B',
        'accent': '#007AFF',
        'success': '#30D158',
        'warning': '#FF9F0A',
        'error': '#FF3B30',
        'border': '#D2D2D7',
        'input_bg': '#F2F2F7',
        'shadow': '#00000010'
    },
    'dark': {
        'bg': '#1C1C1E',
        'secondary_bg': '#2C2C2E',
        'card_bg': '#2C2C2E',
        'text': '#FFFFFF',
        'secondary_text': '#8E8E93',
        'accent': '#0A84FF',
        'success': '#32D74B',
        'warning': '#FF9F0A',
        'error': '#FF453A',
        'border': '#38383A',
        'input_bg': '#1C1C1E',
        'shadow': '#00000030'
    }
}

# Global theme state
current_theme = 'light'

def detect_system_theme():
    """Detect if macOS is using dark mode"""
    try:
        # Use macOS command to check dark mode
        result = subprocess.run(['defaults', 'read', '-g', 'AppleInterfaceStyle'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return 'dark' if result.returncode == 0 else 'light'
    except:
        return 'light'

def get_color(key):
    """Get color from current theme"""
    return MACOS_COLORS[current_theme][key]

# Custom logging handler for GUI
class GUILogHandler(logging.Handler):
    def __init__(self, log_widget):
        super().__init__()
        self.log_widget = log_widget
        
    def emit(self, record):
        try:
            msg = self.format(record)
            timestamp = time.strftime("%H:%M:%S", time.localtime(record.created))
            
            # Color coding based on level
            if record.levelno >= logging.ERROR:
                icon = "🔴"
                color = "#FF453A"
            elif record.levelno >= logging.WARNING:
                icon = "🟡"
                color = "#FF9F0A"
            elif record.levelno >= logging.INFO:
                icon = "🔵"
                color = "#0A84FF"
            else:
                icon = "⚪"
                color = "#8E8E93"
            
            formatted_msg = f"[{timestamp}] {icon} {msg}\n"
            
            # Update GUI in main thread
            if hasattr(self.log_widget, 'after'):
                self.log_widget.after(0, self._update_log, formatted_msg, color)
        except Exception:
            pass
    
    def _update_log(self, message, color="#8E8E93"):
        try:
            self.log_widget.config(state=tk.NORMAL)
            self.log_widget.insert(tk.END, message)
            self.log_widget.see(tk.END)
            self.log_widget.config(state=tk.DISABLED)
        except Exception:
            pass

def log_message(message, level="INFO"):
    """Add message to log with timestamp and color coding"""
    timestamp = time.strftime("%H:%M:%S")
    
    # Color coding based on level
    if level == "ERROR":
        icon = "🔴"
    elif level == "WARNING":
        icon = "🟡"
    elif level == "SUCCESS":
        icon = "🟢"
    elif level == "INFO":
        icon = "🔵"
    else:
        icon = "⚪"
    
    formatted_message = f"[{timestamp}] {icon} {message}\n"
    
    try:
        if 'log_text' in globals() and log_text:
            log_text.config(state=tk.NORMAL)
            log_text.insert(tk.END, formatted_message)
            log_text.see(tk.END)
            log_text.config(state=tk.DISABLED)
    except:
        pass

def toggle_theme():
    """Toggle between light and dark theme"""
    global current_theme
    current_theme = 'dark' if current_theme == 'light' else 'light'
    apply_theme()

def apply_theme():
    """Apply current theme to all widgets"""
    try:
        # Main window
        root.config(bg=get_color('bg'))
        
        # Main container
        main_container.config(bg=get_color('bg'))
        
        # Input section
        input_section.config(bg=get_color('card_bg'), highlightbackground=get_color('border'))
        url_label.config(bg=get_color('card_bg'), fg=get_color('text'))
        folder_label.config(bg=get_color('card_bg'), fg=get_color('text'))
        url_frame.config(bg=get_color('card_bg'))
        folder_frame.config(bg=get_color('card_bg'))
        url_entry.config(bg=get_color('input_bg'), fg=get_color('text'), 
                        insertbackground=get_color('text'), highlightbackground=get_color('accent'))
        output_entry.config(bg=get_color('input_bg'), fg=get_color('text'), 
                           insertbackground=get_color('text'), highlightbackground=get_color('accent'))
        
        # Progress section
        progress_section.config(bg=get_color('card_bg'), highlightbackground=get_color('border'))
        progress_title.config(bg=get_color('card_bg'), fg=get_color('text'))
        progress_label.config(bg=get_color('card_bg'), fg=get_color('secondary_text'))
        
        # Log section
        log_section.config(bg=get_color('card_bg'), highlightbackground=get_color('border'))
        log_title.config(bg=get_color('card_bg'), fg=get_color('text'))
        log_frame.config(bg=get_color('card_bg'))
        log_text.config(bg=get_color('input_bg'), fg=get_color('text'), 
                       insertbackground=get_color('text'))
        
        # Update button styles
        style.configure("Accent.TButton", 
                       background=get_color('accent'),
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       relief='flat')
        
        style.map("Accent.TButton",
                  background=[('active', get_color('accent')),
                             ('pressed', get_color('accent'))],
                  foreground=[('active', 'white'),
                             ('pressed', 'white')])
        
        style.configure("Secondary.TButton",
                       background=get_color('secondary_bg'),
                       foreground=get_color('text'),
                       borderwidth=1,
                       focuscolor='none',
                       relief='flat')
        
        style.map("Secondary.TButton",
                  background=[('active', get_color('border')),
                             ('pressed', get_color('secondary_bg'))],
                  foreground=[('active', get_color('text')),
                             ('pressed', get_color('text'))])
        
        style.configure("TProgressbar",
                       background=get_color('accent'),
                       troughcolor=get_color('secondary_bg'),
                       borderwidth=0,
                       lightcolor=get_color('accent'),
                       darkcolor=get_color('accent'))
    except:
        pass

def create_gui():
    """Creates the modern macOS-style GUI"""
    global root, url_entry, output_entry, download_button, progress_bar, progress_label
    global main_container, input_section, url_label, folder_label, progress_section, progress_title
    global log_section, log_title, log_text, log_frame, style
    global url_frame, folder_frame, progress_frame, current_theme
    
    # Detect system theme
    current_theme = detect_system_theme()
    
    # Create main window
    root = tk.Tk()
    root.title("WampyTube - YouTube Downloader")
    root.geometry("800x700")
    center_window(root, 800, 700)
    root.resizable(True, True)
    root.minsize(700, 600)
    
    # Set window icon if available
    try:
        icon_path = os.path.join(SCRIPT_DIR, 'icon.png')
        if os.path.exists(icon_path):
            # For macOS, we need to use iconphoto
            icon = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, icon)
    except Exception as e:
        logger.debug(f"Could not set icon: {e}")
    
    # Configure ttk styles
    style = ttk.Style()
    style.theme_use('clam')
    
    # Configure initial styles before creating widgets
    style.configure("Accent.TButton", 
                   background=get_color('accent'),
                   foreground='white',
                   borderwidth=0,
                   focuscolor='none',
                   relief='flat')
    
    style.map("Accent.TButton",
              background=[('active', get_color('accent')),
                         ('pressed', get_color('accent'))],
              foreground=[('active', 'white'),
                         ('pressed', 'white')])
    
    style.configure("Secondary.TButton",
                   background=get_color('secondary_bg'),
                   foreground=get_color('text'),
                   borderwidth=1,
                   focuscolor='none',
                   relief='flat')
    
    style.map("Secondary.TButton",
              background=[('active', get_color('border')),
                         ('pressed', get_color('secondary_bg'))],
              foreground=[('active', get_color('text')),
                         ('pressed', get_color('text'))])
    
    style.configure("TProgressbar",
                   background=get_color('accent'),
                   troughcolor=get_color('secondary_bg'),
                   borderwidth=0,
                   lightcolor=get_color('accent'),
                   darkcolor=get_color('accent'))
    
    # Main container with padding
    main_container = tk.Frame(root, bg=get_color('bg'))
    main_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)
    
    # Input section
    input_section = tk.Frame(
        main_container,
        bg=get_color('card_bg'),
        relief=tk.SOLID,
        bd=1,
        highlightbackground=get_color('border'),
        highlightthickness=1
    )
    input_section.pack(fill=tk.X, pady=(0, 20))
    
    # URL input
    url_label = tk.Label(
        input_section,
        text="YouTube URL",
        font=("SF Pro Text", 14, "bold"),
        bg=get_color('card_bg'),
        fg=get_color('text')
    )
    url_label.pack(anchor=tk.W, padx=20, pady=(20, 5))
    
    url_frame = tk.Frame(input_section, bg=get_color('card_bg'))
    url_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
    
    url_entry = tk.Entry(
        url_frame,
        font=("SF Pro Text", 13),
        bg=get_color('input_bg'),
        fg=get_color('text'),
        insertbackground=get_color('text'),
        relief=tk.FLAT,
        bd=8
    )
    url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    paste_button = ttk.Button(
        url_frame,
        text="Paste",
        command=paste_from_clipboard,
        style="Secondary.TButton",
        width=8
    )
    paste_button.pack(side=tk.RIGHT, padx=(10, 0))
    
    # Output folder
    folder_label = tk.Label(
        input_section,
        text="Output Folder",
        font=("SF Pro Text", 14, "bold"),
        bg=get_color('card_bg'),
        fg=get_color('text')
    )
    folder_label.pack(anchor=tk.W, padx=20, pady=(0, 5))
    
    folder_frame = tk.Frame(input_section, bg=get_color('card_bg'))
    folder_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
    
    output_entry = tk.Entry(
        folder_frame,
        font=("SF Pro Text", 13),
        bg=get_color('input_bg'),
        fg=get_color('text'),
        insertbackground=get_color('text'),
        relief=tk.FLAT,
        bd=8
    )
    output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    browse_button = ttk.Button(
        folder_frame,
        text="Browse",
        command=select_output_folder,
        style="Secondary.TButton",
        width=8
    )
    browse_button.pack(side=tk.RIGHT, padx=(10, 0))
    
    # Download button
    download_button = ttk.Button(
        input_section,
        text="Download Video",
        command=download_video,
        style="Accent.TButton"
    )
    download_button.pack(pady=(0, 20))
    
    # Progress section
    progress_section = tk.Frame(
        main_container,
        bg=get_color('card_bg'),
        relief=tk.SOLID,
        bd=1,
        highlightbackground=get_color('border'),
        highlightthickness=1
    )
    progress_section.pack(fill=tk.X, pady=(0, 20))
    
    progress_title = tk.Label(
        progress_section,
        text="Progress",
        font=("SF Pro Text", 14, "bold"),
        bg=get_color('card_bg'),
        fg=get_color('text')
    )
    progress_title.pack(anchor=tk.W, padx=20, pady=(15, 5))
    
    progress_frame = tk.Frame(progress_section, bg=get_color('card_bg'))
    progress_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
    
    progress_bar = ttk.Progressbar(
        progress_frame,
        mode='determinate'
    )
    progress_bar.pack(fill=tk.X, pady=(0, 8))
    
    progress_label = tk.Label(
        progress_frame,
        text="Ready to download",
        font=("SF Pro Text", 12),
        bg=get_color('card_bg'),
        fg=get_color('secondary_text')
    )
    progress_label.pack(anchor=tk.W)
    
    # Log section
    log_section = tk.Frame(
        main_container,
        bg=get_color('card_bg'),
        relief=tk.SOLID,
        bd=1,
        highlightbackground=get_color('border'),
        highlightthickness=1
    )
    log_section.pack(fill=tk.BOTH, expand=True)
    
    log_title = tk.Label(
        log_section,
        text="Activity Log",
        font=("SF Pro Text", 14, "bold"),
        bg=get_color('card_bg'),
        fg=get_color('text')
    )
    log_title.pack(anchor=tk.W, padx=20, pady=(15, 5))
    
    log_frame = tk.Frame(log_section, bg=get_color('card_bg'))
    log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
    
    # Log text with scrollbar
    log_text = tk.Text(
        log_frame,
        font=("SF Mono", 11),
        bg=get_color('input_bg'),
        fg=get_color('text'),
        insertbackground=get_color('text'),
        relief=tk.FLAT,
        bd=8,
        state=tk.DISABLED,
        wrap=tk.WORD
    )
    
    scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
    log_text.configure(yscrollcommand=scrollbar.set)
    
    log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Apply initial theme
    apply_theme()
    
    # Set up logging without duplication
    # Clear any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add only the GUI handler
    gui_handler = GUILogHandler(log_text)
    gui_handler.setFormatter(logging.Formatter('%(message)s'))
    gui_handler.setLevel(logging.INFO)
    logger.addHandler(gui_handler)
    logger.setLevel(logging.INFO)
    
    # Initial log message - only log once
    cpu_info = f"{SYSTEM_CORES} cores, {SYSTEM_THREADS} threads"
    gpu_info = MACOS_GPU['model'] if MACOS_GPU['available'] else "No GPU detected"
    ffmpeg_info = f"FFmpeg {FFMPEG_INFO.get('version', 'Unknown')}" if FFMPEG_INFO.get('available') else "FFmpeg not found"
    
    log_message("WampyTube initialized successfully")
    log_message(f"System: {gpu_info} • {cpu_info}")
    log_message(f"FFmpeg: {ffmpeg_info}")
    
    # Bind Enter key to download button
    root.bind('<Return>', lambda event: download_video())
    
    # Set default output folder to Downloads
    downloads_folder = os.path.expanduser("~/Downloads")
    output_entry.insert(0, downloads_folder)
    
    return root

if __name__ == "__main__":
    # Initialize the GUI
    root = create_gui()
    # Start the main loop
    root.mainloop()