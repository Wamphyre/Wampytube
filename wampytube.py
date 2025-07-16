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

# Global cache configuration for HTTP responses
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WampyTube")

# System resources configuration - Auto-detect cores/threads
SYSTEM_CORES = psutil.cpu_count(logical=False) or 4
SYSTEM_THREADS = psutil.cpu_count(logical=True) or 8
DOWNLOAD_THREADS = min(4, SYSTEM_THREADS // 2)
CPU_THREADS = SYSTEM_THREADS - 1  # Leave one thread for system operations

# Check for AMD GPU and VAAPI
def check_amd_gpu():
    """Check for AMD GPU and VAAPI support with detailed info"""
    try:
        # Check if we have the RX 6600 GPU
        result = subprocess.run(['lspci'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Get VAAPI capabilities
        vaapi_info = {'available': False, 'hevc_encoding': False, 'device': '/dev/dri/renderD128'}
        try:
            # Check VAAPI details
            vaapi_check = subprocess.run(['vainfo'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if vaapi_check.returncode == 0:
                vaapi_info['available'] = True
                
                # Look for HEVC encoding support
                if 'VAProfileHEVCMain' in vaapi_check.stdout and 'VAEntrypointEncSlice' in vaapi_check.stdout:
                    vaapi_info['hevc_encoding'] = True
                
                # Extract GPU model
                gpu_model = 'AMD GPU'
                model_match = re.search(r'for\s+(.+?)\s+\(', vaapi_check.stdout)
                if model_match:
                    gpu_model = model_match.group(1)
                
                # Try to find the correct render device
                dev_nodes = ['/dev/dri/renderD128', '/dev/dri/renderD129']
                for node in dev_nodes:
                    if os.path.exists(node):
                        vaapi_info['device'] = node
                        break
        except Exception as e:
            logger.warning(f"Error checking VAAPI details: {e}")
        
        # Determine AMD GPU presence
        if 'AMD' in result.stdout and ('RX 6600' in result.stdout or 'Radeon' in result.stdout or 'RDNA' in result.stdout):
            gpu_model = 'AMD Radeon'
            if 'RX 6600' in result.stdout:
                gpu_model = 'AMD RX 6600'
            
            return {
                'model': gpu_model,
                'vaapi': vaapi_info['available'],
                'hevc_encoding': vaapi_info['hevc_encoding'],
                'device': vaapi_info['device']
            }
        
        # No AMD GPU found
        return {'model': 'Unknown', 'vaapi': False, 'hevc_encoding': False, 'device': None}
    except Exception as e:
        logger.error(f"Error checking AMD GPU: {e}")
        return {'model': 'Unknown', 'vaapi': False, 'hevc_encoding': False, 'device': None}

# Get hardware acceleration information - AMD only
AMD_GPU = check_amd_gpu()
logger.info(f"Detected GPU: {AMD_GPU}")

# Check FFmpeg capabilities
def check_ffmpeg():
    """Check FFmpeg version and available encoders"""
    try:
        # Check FFmpeg version
        version_result = subprocess.run(['ffmpeg', '-version'], 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if version_result.returncode != 0:
            return {'available': False}
        
        # Extract version
        version_match = re.search(r'ffmpeg version ([^ ]+)', version_result.stdout)
        version = version_match.group(1) if version_match else "Unknown"
        
        # Check encoders
        encoders_result = subprocess.run(['ffmpeg', '-encoders'], 
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        encoders = {
            'hevc_vaapi': 'hevc_vaapi' in encoders_result.stdout,
            'h264_vaapi': 'h264_vaapi' in encoders_result.stdout,
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
    """Set the process priority to maximum for faster performance"""
    try:
        # Unix/Linux priority
        os.nice(-20)  # Requires root privileges to go below 0
    except Exception as e:
        logger.warning(f"Could not set process priority (might need sudo): {str(e)}")

def optimize_system_resources():
    """Optimize system resources for maximum processing speed in Linux"""
    try:
        # On Linux, we can set the process scheduling policy
        # This requires root privileges
        try:
            import ctypes
            libc = ctypes.CDLL('libc.so.6')
            
            # Try to set SCHED_FIFO policy
            # This requires root
            SCHED_FIFO = 1
            class sched_param(ctypes.Structure):
                _fields_ = [("sched_priority", ctypes.c_int)]
            
            param = sched_param(99)  # Max priority
            result = libc.sched_setscheduler(0, SCHED_FIFO, ctypes.byref(param))
            if result != 0:
                # If failed, try to increase nice value
                os.nice(-10)  # Try a modest priority boost
        except Exception as e:
            logger.debug(f"Could not set scheduler policy: {e}")
            
        # Try to set IO priority to Realtime
        try:
            subprocess.run(['ionice', '-c', '1', '-n', '0', '-p', str(os.getpid())], 
                          check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.debug(f"Could not set IO priority: {e}")
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
        
        # Process stdout for progress
        if process.stdout:
            for line in process.stdout:
                # Parse progress information
                if progress_callback:
                    if line.startswith('out_time_ms='):
                        try:
                            time_ms = int(line.split('=')[1])
                            if duration_seconds:
                                progress = min(100, (time_ms / 1000000) / duration_seconds * 100)
                                progress_callback(progress)
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
                            
                            # Calculate current FPS (every 3 seconds)
                            current_time = time.time()
                            if current_time - last_fps_time >= 3 and frame_count > 0:
                                elapsed = current_time - start_time
                                current_fps = frame_count / elapsed if elapsed > 0 else 0
                                fps_stats.append(current_fps)
                                avg_fps = sum(fps_stats) / len(fps_stats)
                                stats['avg_fps'] = avg_fps
                                
                                # Update progress with FPS info
                                if progress_callback and duration_seconds:
                                    progress = min(100, (frame_count / (duration_seconds * avg_fps)) * 100) if avg_fps > 0 else 0
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

def merge_audio_video_with_amd_hevc(video_path, audio_path, output_path, progress_callback=None):
    """Combine audio and video with AMD RX 6600 GPU acceleration using HEVC (H.265)"""
    if not AMD_GPU['vaapi'] or not AMD_GPU['hevc_encoding']:
        logger.warning("HEVC encoding via VAAPI not available, falling back to CPU")
        return False, {}
    
    try:
        # Get video details
        probe_cmd = [
            'ffprobe', 
            '-v', 'error', 
            '-select_streams', 'v:0', 
            '-show_entries', 'stream=width,height,r_frame_rate', 
            '-of', 'csv=p=0',
            video_path
        ]
        
        probe_result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if probe_result.returncode == 0:
            # Parse video information
            width, height, framerate = probe_result.stdout.strip().split(',')
            logger.info(f"Video details: {width}x{height} @ {framerate}")
            
            # Some VAAPI implementations have limitations at higher resolutions
            is_high_res = int(width) > 1920 or int(height) > 1080
            
            # Extract the actual frame rate value
            try:
                frame_rate_nums = framerate.split('/')
                actual_framerate = float(frame_rate_nums[0]) / float(frame_rate_nums[1])
                logger.info(f"Calculated frame rate: {actual_framerate:.2f} FPS")
            except (ValueError, ZeroDivisionError, IndexError):
                actual_framerate = 30
                logger.warning(f"Could not parse frame rate, using default: {actual_framerate} FPS")
        else:
            logger.warning("Could not get video details, using default parameters")
            is_high_res = False
            actual_framerate = 30
        
        # Build FFmpeg command for AMD GPU HEVC encoding via VAAPI
        command = [
            'ffmpeg',
            '-y',  # Overwrite output files without asking
            '-i', video_path,  # Video input
            '-i', audio_path,  # Audio input
            '-c:v', 'hevc_vaapi',  # HEVC via VAAPI
            '-vaapi_device', AMD_GPU['device'],  # VAAPI device
            '-vf', 'format=nv12,hwupload',  # Required format conversion
        ]
        
        # Add quality settings based on resolution
        if is_high_res:
            # Higher quality for high-res content
            quality_params = [
                '-qp', '24',          # QP value (lower = better quality)
                '-rc_mode', 'CQP',    # Constant Quality mode
                '-b:v', '6M',         # Higher bitrate for high-res
            ]
        else:
            # Standard quality for normal content
            quality_params = [
                '-qp', '26',          # QP value
                '-rc_mode', 'CQP',    # Constant Quality mode
                '-b:v', '4M',         # Bitrate
            ]
        
        command.extend(quality_params)
        
        # Add common parameters
        command.extend([
            '-c:a', 'aac',            # Audio codec
            '-b:a', '192k',           # Audio bitrate
            '-max_muxing_queue_size', '1024',  # Prevent muxing errors
            '-threads', str(CPU_THREADS),  # Use available CPU threads
            output_path
        ])
        
        # Run the command
        logger.info("Starting encoding with AMD RX 6600 HEVC via VAAPI...")
        success, stats = run_ffmpeg_command(command, progress_callback)
        
        if success:
            logger.info(f"Successfully processed with VAAPI HEVC. Average FPS: {stats.get('avg_fps', 0):.1f}")
            return True, stats
        else:
            logger.error("VAAPI HEVC encoding failed")
            return False, stats
            
    except Exception as e:
        logger.error(f"Error with AMD HEVC encoding: {str(e)}")
        return False, {}

def merge_audio_video_with_cpu(video_path, audio_path, output_path, progress_callback=None):
    """Fallback to CPU encoding with high quality HEVC"""
    try:
        # Build command for CPU-based HEVC encoding
        command = [
            'ffmpeg',
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
            'ffmpeg',
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
    """Main function to combine audio and video with AMD RX 6600 acceleration"""
    # Increase process priority
    set_process_priority()
    
    # Try AMD hardware acceleration with HEVC (H.265)
    if AMD_GPU['vaapi'] and AMD_GPU['hevc_encoding']:
        try:
            success, stats = merge_audio_video_with_amd_hevc(video_path, audio_path, output_path, progress_callback)
            if success:
                return True, stats
        except Exception as e:
            logger.error(f"AMD HEVC encoding failed: {str(e)}")
    
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
    else:
        root.after(0, lambda: progress_label.config(text=f"Encoding: {percentage:.1f}%"))

def download_in_thread(url, output_folder):
    """Handles the download in a separate thread"""
    try:
        # Optimize system resources
        optimize_system_resources()
        
        # Create the output directory if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)
        
        # Get the best streams
        video_stream, audio_stream, needs_merge = get_best_streams(url)
        if not video_stream:
            root.after(0, lambda: messagebox.showerror("Error", "No suitable stream found for this video."))
            return

        resolution = video_stream.resolution
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
            
            # Combine files with AMD RX 6600 acceleration
            acceleration = "AMD RX 6600 VAAPI" if AMD_GPU['vaapi'] and AMD_GPU['hevc_encoding'] else "CPU"
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
                gpu_model = AMD_GPU['model'] if (AMD_GPU['vaapi'] and AMD_GPU['hevc_encoding']) else "CPU"
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

def toggle_dark_mode():
    """Toggles between light and dark mode"""
    if toggle_dark_mode.is_dark_mode:
        # Switch to light mode
        root.config(bg="#f0f0f0")
        frame.config(bg="#f0f0f0")
        url_frame.config(bg="#f0f0f0")
        out_frame.config(bg="#f0f0f0")
        button_frame.config(bg="#f0f0f0")
        progress_frame.config(bg="#f0f0f0")
        for label in root.winfo_children():
            if isinstance(label, tk.Label):
                label.config(bg="#f0f0f0", fg="#000000")
        for frame_widget in frame.winfo_children():
            if isinstance(frame_widget, tk.Frame):
                frame_widget.config(bg="#f0f0f0")
                for label in frame_widget.winfo_children():
                    if isinstance(label, tk.Label):
                        label.config(bg="#f0f0f0", fg="#000000")
        
        # Reset button and progressbar colors
        amd_red = "#ED1C24"
        style.configure("TButton", background=amd_red, foreground="white")
        style.configure("TProgressbar", background=amd_red)
        
        dark_mode_button.config(text="Dark Mode")
        toggle_dark_mode.is_dark_mode = False
    else:
        # Switch to dark mode - AMD themed dark mode
        amd_dark = "#2D2D2D"
        amd_red = "#ED1C24"
        
        root.config(bg=amd_dark)
        frame.config(bg=amd_dark)
        url_frame.config(bg=amd_dark)
        out_frame.config(bg=amd_dark)
        button_frame.config(bg=amd_dark)
        progress_frame.config(bg=amd_dark)
        for label in root.winfo_children():
            if isinstance(label, tk.Label):
                label.config(bg=amd_dark, fg="#ffffff")
        for frame_widget in frame.winfo_children():
            if isinstance(frame_widget, tk.Frame):
                frame_widget.config(bg=amd_dark)
                for label in frame_widget.winfo_children():
                    if isinstance(label, tk.Label):
                        label.config(bg=amd_dark, fg="#ffffff")
        
        # Keep AMD red for buttons
        style.configure("TButton", background=amd_red, foreground="white")
        style.configure("TProgressbar", background=amd_red)
        
        dark_mode_button.config(text="Light Mode")
        toggle_dark_mode.is_dark_mode = True

# Initialize dark mode state
toggle_dark_mode.is_dark_mode = False

def create_gui():
    """Creates the program's graphical interface"""
    global root, url_entry, output_entry, download_button, progress_frame, progress_bar, progress_label
    global frame, url_frame, out_frame, button_frame, style, dark_mode_button
    
    # Create window
    root = tk.Tk()
    root.title("WampyTube: YouTube Downloader (3.0) - AMD RX 6600 HEVC Edition")
    
    # Center the window
    center_window(root, 550, 320)
    root.resizable(False, False)
    
    # Widget style - Use AMD red theme
    style = ttk.Style()
    style.theme_use('clam')  # Use a modern theme
    
    # AMD-inspired color scheme (red accents)
    amd_red = "#ED1C24"
    amd_dark = "#2D2D2D"
    
    style.configure("TButton", padding=6, relief="flat", background=amd_red, foreground="white")
    style.configure("TProgressbar", thickness=20, troughcolor="#f0f0f0", background=amd_red)
    
    # Main frame
    frame = tk.Frame(root, padx=15, pady=15)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # URL field
    url_frame = tk.Frame(frame)
    url_frame.pack(fill=tk.X, pady=5)
    
    tk.Label(url_frame, text="Video URL:", anchor="w").pack(side=tk.LEFT)
    url_entry = tk.Entry(url_frame, width=50)
    url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    
    # Paste button
    ttk.Button(url_frame, text="Paste", width=8, command=paste_from_clipboard).pack(side=tk.RIGHT)
    
    # Output folder field
    out_frame = tk.Frame(frame)
    out_frame.pack(fill=tk.X, pady=10)
    
    tk.Label(out_frame, text="Output folder:", anchor="w").pack(side=tk.LEFT)
    output_entry = tk.Entry(out_frame, width=40)
    output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    ttk.Button(out_frame, text="Select", width=10, command=select_output_folder).pack(side=tk.RIGHT)
    
    # Set default download directory
    default_download_dir = os.path.join(Path.home(), "Downloads")
    if os.path.exists(default_download_dir):
        output_entry.insert(0, default_download_dir)
    
    # Progress bar frame
    progress_frame = tk.Frame(root, padx=15)
    progress_bar = ttk.Progressbar(progress_frame, length=500, mode='determinate', style="TProgressbar")
    progress_bar.pack(fill=tk.X, pady=5)
    progress_label = tk.Label(progress_frame, text="", anchor="center")
    progress_label.pack(fill=tk.X)
    
    # Button frame
    button_frame = tk.Frame(frame)
    button_frame.pack(pady=15)
    
    # Download button
    download_button = ttk.Button(
        button_frame, 
        text="DOWNLOAD", 
        command=download_video, 
        width=20,
        style="TButton"
    )
    download_button.pack(side=tk.LEFT, padx=10)
    
    # Dark mode toggle button
    dark_mode_button = ttk.Button(
        button_frame,
        text="Dark Mode",
        command=toggle_dark_mode,
        width=15,
        style="TButton"
    )
    dark_mode_button.pack(side=tk.LEFT, padx=10)
    
    # Hardware acceleration info label
    gpu_model = AMD_GPU['model'] if AMD_GPU['vaapi'] else "AMD GPU not detected"
    hw_info_label = tk.Label(
        root, 
        text=f"{gpu_model} • HEVC (H.265) • {SYSTEM_CORES} Cores/{SYSTEM_THREADS} Threads",
        fg="#888888"
    )
    hw_info_label.pack(side=tk.BOTTOM, pady=2)
    
    # Version text
    version_label = tk.Label(root, text="WampyTube 3.0 - AMD RX 6600 HEVC Edition", fg="#888888")
    version_label.pack(side=tk.BOTTOM, pady=2)
    
    # Bind Enter key to download button
    root.bind('<Return>', lambda event: download_video())
    
    return root

if __name__ == "__main__":
    # Initialize the GUI
    root = create_gui()
    # Start the main loop
    root.mainloop()