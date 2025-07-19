#!/usr/bin/env python3

import customtkinter as ctk
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
from tkinter import filedialog
from PIL import Image
import tkinter as tk

# Configure CustomTkinter
ctk.set_appearance_mode("dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WampyTube")
logger.handlers = []
logger.propagate = False

# System resources configuration
SYSTEM_CORES = psutil.cpu_count(logical=False) or 4
SYSTEM_THREADS = psutil.cpu_count(logical=True) or 8
DOWNLOAD_THREADS = min(4, SYSTEM_THREADS // 2)
CPU_THREADS = SYSTEM_THREADS - 1

# FFmpeg configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_PATH = os.path.join(SCRIPT_DIR, 'ffmpeg')

# Check if our local ffmpeg exists
if not os.path.exists(FFMPEG_PATH):
    FFMPEG_PATH = 'ffmpeg'
    logger.warning(f"Local ffmpeg not found in {SCRIPT_DIR}, using system ffmpeg")
else:
    logger.info(f"Using local ffmpeg from {SCRIPT_DIR}")

# Check for GPU and hardware acceleration on macOS
def check_macos_gpu():
    """Check for GPU and VideoToolbox support on macOS"""
    try:
        result = subprocess.run(['system_profiler', 'SPDisplaysDataType'], 
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        gpu_info = {'available': False, 'hevc_encoding': False, 'model': 'Unknown', 'videotoolbox': False}
        
        if result.returncode == 0:
            output = result.stdout
            
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
                gpu_info['hevc_encoding'] = True
        
        gpu_info['videotoolbox'] = True
        if gpu_info['available']:
            gpu_info['hevc_encoding'] = True
        
        return gpu_info
        
    except Exception as e:
        logger.error(f"Error checking macOS GPU: {e}")
        return {'model': 'Unknown', 'available': False, 'hevc_encoding': False, 'videotoolbox': False}

# Get hardware acceleration information
MACOS_GPU = check_macos_gpu()
logger.info(f"Detected GPU: {MACOS_GPU}")

# Check FFmpeg capabilities
def check_ffmpeg():
    """Check FFmpeg version and available encoders"""
    try:
        version_result = subprocess.run([FFMPEG_PATH, '-version'], 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if version_result.returncode != 0:
            return {'available': False}
        
        version_match = re.search(r'ffmpeg version ([^ ]+)', version_result.stdout)
        version = version_match.group(1) if version_match else "Unknown"
        
        return {
            'available': True,
            'version': version
        }
    except Exception as e:
        logger.error(f"Error checking FFmpeg: {e}")
        return {'available': False}

FFMPEG_INFO = check_ffmpeg()
logger.info(f"FFmpeg information: {FFMPEG_INFO}")

# Global variables for progress tracking
current_download = {
    'status': 'idle',
    'progress': 0,
    'message': '',
    'speed': '',
    'eta': ''
}

class WampyTubeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Set application name for macOS menu bar (must be done early)
        self.set_app_name()
        
        # Configure window
        self.title("WampyTube")
        self.geometry("800x800")  # Increased default height
        self.minsize(700, 700)    # Increased minimum height
        
        # Track if video info is shown to adjust window size
        self.video_info_shown = False
        
        # Set icon if available
        self.set_app_icon()
        
        # Create custom menu bar
        self.create_menu_bar()
        
        # Create widgets
        self.create_widgets()
        
        # Detect system theme
        self.detect_system_theme()
        
    def create_menu_bar(self):
        """Create custom menu bar with About dialog"""
        try:
            # Create menu bar
            menubar = tk.Menu(self)
            self.config(menu=menubar)
            
            # Create the main application menu (this will be the leftmost menu)
            # On macOS, this automatically becomes the app menu with the app name
            app_menu = tk.Menu(menubar, tearoff=0, name='apple')
            menubar.add_cascade(menu=app_menu)
            
            # Add About menu item to the main app menu
            app_menu.add_command(label="About WampyTube", command=self.show_about_dialog)
            app_menu.add_separator()
            app_menu.add_command(label="Quit WampyTube", command=self.quit_app, accelerator="Cmd+Q")
            
            # Set up macOS-specific menu commands
            try:
                self.createcommand('tkAboutDialog', self.show_about_dialog)
                self.createcommand('tk::mac::ShowPreferences', self.show_about_dialog)
            except:
                pass
            
            # Create File menu
            file_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="File", menu=file_menu)
            file_menu.add_command(label="Select Output Folder...", command=self.select_output_folder, accelerator="Cmd+O")
            file_menu.add_separator()
            file_menu.add_command(label="Clear Log", command=self.clear_log)
            
            # Create Edit menu
            edit_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Edit", menu=edit_menu)
            edit_menu.add_command(label="Paste URL", command=self.paste_from_clipboard, accelerator="Cmd+V")
            edit_menu.add_command(label="Clear URL", command=self.clear_url)
            
            # Bind keyboard shortcuts
            self.bind_all("<Command-q>", lambda e: self.quit_app())
            self.bind_all("<Command-o>", lambda e: self.select_output_folder())
            self.bind_all("<Command-v>", lambda e: self.paste_from_clipboard())
            
            logger.info("Custom menu bar created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create menu bar: {e}")
    
    def show_about_dialog(self):
        """Show About WampyTube dialog with custom icon"""
        try:
            # Create about window
            about_window = ctk.CTkToplevel(self)
            about_window.title("About WampyTube")
            about_window.geometry("450x520")
            about_window.resizable(False, False)
            
            # Center the window
            about_window.transient(self)
            about_window.grab_set()
            
            # Main container
            main_frame = ctk.CTkFrame(about_window, fg_color="transparent")
            main_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            # Icon section
            icon_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            icon_frame.pack(pady=(0, 10))
            
            # Load and display icon
            try:
                icon_path = os.path.join(SCRIPT_DIR, 'icon.png')
                if os.path.exists(icon_path):
                    # Load icon with PIL and resize
                    pil_image = Image.open(icon_path)
                    pil_image = pil_image.resize((80, 80), Image.Resampling.LANCZOS)
                    
                    # Convert to CTkImage
                    icon_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(80, 80))
                    
                    # Display icon
                    icon_label = ctk.CTkLabel(icon_frame, image=icon_image, text="")
                    icon_label.pack()
                else:
                    # Fallback text if no icon
                    icon_label = ctk.CTkLabel(icon_frame, text="🎬", font=ctk.CTkFont(size=40))
                    icon_label.pack()
            except Exception as e:
                logger.warning(f"Could not load icon for about dialog: {e}")
                # Fallback emoji
                icon_label = ctk.CTkLabel(icon_frame, text="🎬", font=ctk.CTkFont(size=40))
                icon_label.pack()
            
            # App name and version
            name_label = ctk.CTkLabel(main_frame, text="WampyTube", 
                                    font=ctk.CTkFont(size=22, weight="bold"))
            name_label.pack(pady=(0, 3))
            
            version_label = ctk.CTkLabel(main_frame, text="Version 1.1.1", 
                                       font=ctk.CTkFont(size=13))
            version_label.pack(pady=(0, 12))
            
            # Description
            desc_label = ctk.CTkLabel(main_frame, 
                                    text="Modern YouTube downloader with\nhardware acceleration for macOS", 
                                    font=ctk.CTkFont(size=12),
                                    justify="center")
            desc_label.pack(pady=(0, 12))
            
            # Features section
            features_frame = ctk.CTkFrame(main_frame)
            features_frame.pack(fill="x", pady=(0, 12))
            
            features_title = ctk.CTkLabel(features_frame, text="Key Features", 
                                        font=ctk.CTkFont(size=14, weight="bold"))
            features_title.pack(pady=(12, 8))
            
            features_text = """• 4K video downloads with HEVC encoding
• GPU acceleration (Apple Silicon, AMD, Intel)
• Real-time progress monitoring
• Native macOS interface"""
            
            features_label = ctk.CTkLabel(features_frame, text=features_text,
                                        font=ctk.CTkFont(size=11),
                                        justify="left",
                                        anchor="w")
            features_label.pack(fill="x", padx=15, pady=(0, 12))
            
            # System info section
            system_frame = ctk.CTkFrame(main_frame)
            system_frame.pack(fill="x", pady=(0, 15))
            
            system_title = ctk.CTkLabel(system_frame, text="System Info", 
                                      font=ctk.CTkFont(size=14, weight="bold"))
            system_title.pack(pady=(12, 8))
            
            # Truncate long GPU names
            gpu_name = MACOS_GPU['model']
            if len(gpu_name) > 25:
                gpu_name = gpu_name[:22] + "..."
            
            ffmpeg_version = FFMPEG_INFO.get('version', 'Not found')
            if len(ffmpeg_version) > 25:
                ffmpeg_version = ffmpeg_version[:22] + "..."
            
            system_text = f"""GPU: {gpu_name}
CPU: {SYSTEM_CORES} cores, {SYSTEM_THREADS} threads
FFmpeg: {ffmpeg_version}"""
            
            system_label = ctk.CTkLabel(system_frame, text=system_text,
                                      font=ctk.CTkFont(family="SF Mono", size=10),
                                      justify="left",
                                      anchor="w")
            system_label.pack(fill="x", padx=15, pady=(0, 12))
            
            # Copyright and close button
            copyright_label = ctk.CTkLabel(main_frame, text="© 2024 WampyTube", 
                                         font=ctk.CTkFont(size=11))
            copyright_label.pack(pady=(0, 12))
            
            # Close button
            close_button = ctk.CTkButton(main_frame, text="Close", width=80, height=32,
                                       command=about_window.destroy)
            close_button.pack()
            
            # Focus the about window
            about_window.focus()
            
        except Exception as e:
            logger.error(f"Failed to show about dialog: {e}")
    
    def quit_app(self):
        """Quit the application"""
        try:
            self.quit()
            self.destroy()
        except:
            pass
    
    def clear_log(self):
        """Clear the activity log"""
        try:
            self.log_text.delete("1.0", "end")
            self.log_message("Activity log cleared", "info")
        except Exception as e:
            logger.error(f"Failed to clear log: {e}")
    
    def clear_url(self):
        """Clear the URL entry field"""
        try:
            self.url_entry.delete(0, "end")
            # Hide video info frame if visible
            if self.video_info_shown:
                self.video_info_frame.pack_forget()
                self.video_info_shown = False
                self.after(100, self.adjust_window_size)  # Readjust window size
            # Clear selectors
            self.quality_selector.configure(values=[])
            self.audio_selector.configure(values=[])
            # Clear stored data
            self.available_streams = {}
            self.available_audio = {}
            self.current_video = None
        except Exception as e:
            logger.error(f"Failed to clear URL: {e}")
    
    def adjust_window_size(self):
        """Adjust window size based on content"""
        try:
            # Update the window to calculate new required size
            self.update_idletasks()
            
            # Get current window size
            current_width = self.winfo_width()
            current_height = self.winfo_height()
            
            # Calculate required height based on content
            if self.video_info_shown:
                # When video info is shown, we need more height
                target_height = max(850, current_height)
            else:
                # When video info is hidden, we can use original height
                target_height = 800
            
            # Only adjust if there's a significant difference
            if abs(current_height - target_height) > 30:
                self.geometry(f"{current_width}x{target_height}")
                
        except Exception as e:
            logger.error(f"Failed to adjust window size: {e}")
    
    def set_app_name(self):
        """Set application name for macOS menu bar"""
        try:
            # Method 1: Set process name using ctypes (most effective)
            try:
                import ctypes
                import ctypes.util
                
                # Load the Foundation framework
                foundation = ctypes.cdll.LoadLibrary(ctypes.util.find_library("Foundation"))
                
                # Get the current process
                objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
                
                # Set up function signatures
                objc.objc_getClass.restype = ctypes.c_void_p
                objc.objc_getClass.argtypes = [ctypes.c_char_p]
                objc.sel_registerName.restype = ctypes.c_void_p
                objc.sel_registerName.argtypes = [ctypes.c_char_p]
                objc.objc_msgSend.restype = ctypes.c_void_p
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                
                # Get NSProcessInfo class
                NSProcessInfo = objc.objc_getClass(b"NSProcessInfo")
                processInfo = objc.objc_msgSend(NSProcessInfo, objc.sel_registerName(b"processInfo"))
                
                # Set process name
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
                NSString = objc.objc_getClass(b"NSString")
                app_name = objc.objc_msgSend(NSString, objc.sel_registerName(b"stringWithUTF8String:"), b"WampyTube")
                objc.objc_msgSend(processInfo, objc.sel_registerName(b"setProcessName:"), app_name)
                
                logger.info("Application name set to 'WampyTube' using ctypes method")
                
            except Exception as e1:
                logger.warning(f"ctypes method failed: {e1}, trying PyObjC method")
                
                # Method 2: Try PyObjC if available
                try:
                    from Foundation import NSProcessInfo
                    NSProcessInfo.processInfo().setProcessName_("WampyTube")
                    logger.info("Application name set to 'WampyTube' using PyObjC method")
                    
                except ImportError:
                    logger.warning("PyObjC not available, trying subprocess method")
                    
                    # Method 3: Use subprocess to set process name
                    try:
                        subprocess.run(['exec', '-a', 'WampyTube'] + sys.argv, check=False)
                        logger.info("Attempted to set process name using subprocess")
                    except Exception as e3:
                        logger.warning(f"subprocess method failed: {e3}")
                        
                        # Method 4: Set sys.argv[0] as fallback
                        original_argv0 = sys.argv[0]
                        sys.argv[0] = "WampyTube"
                        logger.info("Set sys.argv[0] to 'WampyTube' as fallback")
                        
        except Exception as e:
            logger.error(f"Failed to set application name: {e}")
    
    def set_app_icon(self):
        """Set application icon for macOS dock"""
        try:
            icon_path = os.path.join(SCRIPT_DIR, 'icon.png')
            if os.path.exists(icon_path):
                # Create PhotoImage from PNG file
                photo = tk.PhotoImage(file=icon_path)
                
                # Set icon using wm_iconphoto (works with customtkinter)
                self.wm_iconphoto(True, photo)
                
                # Store reference to prevent garbage collection
                self._icon_photo = photo
                
                logger.info("Application icon set successfully")
            else:
                logger.warning(f"Icon file not found at {icon_path}")
                
        except Exception as e:
            logger.error(f"Failed to set application icon: {e}")
            # Try alternative method for macOS
            try:
                icon_path = os.path.join(SCRIPT_DIR, 'icon.png')
                if os.path.exists(icon_path):
                    # Direct tk call method
                    photo = tk.PhotoImage(file=icon_path)
                    self.tk.call('wm', 'iconphoto', self._w, photo)
                    self._icon_photo = photo
                    logger.info("Icon set using tk.call fallback method")
            except Exception as fallback_error:
                logger.error(f"Fallback icon method also failed: {fallback_error}")
    
    def detect_system_theme(self):
        """Detect if macOS is using dark mode"""
        try:
            result = subprocess.run(['defaults', 'read', '-g', 'AppleInterfaceStyle'], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                ctk.set_appearance_mode("dark")
            else:
                ctk.set_appearance_mode("light")
        except:
            ctk.set_appearance_mode("dark")
    
    def create_widgets(self):
        # Main container with padding
        main_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # URL Input Section
        url_frame = ctk.CTkFrame(main_container)
        url_frame.pack(fill="x", pady=(0, 15))
        
        url_label = ctk.CTkLabel(url_frame, text="YouTube URL", font=ctk.CTkFont(size=14, weight="bold"))
        url_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        url_input_frame = ctk.CTkFrame(url_frame, fg_color="transparent")
        url_input_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        self.url_entry = ctk.CTkEntry(url_input_frame, placeholder_text="https://youtube.com/watch?v=...", height=40)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        paste_button = ctk.CTkButton(url_input_frame, text="Paste", width=80, height=40, command=self.paste_from_clipboard)
        paste_button.pack(side="right")
        
        # Video Info Section (hidden initially)
        self.video_info_frame = ctk.CTkFrame(main_container)
        # Don't pack it initially
        
        self.video_title_label = ctk.CTkLabel(self.video_info_frame, text="", font=ctk.CTkFont(size=16, weight="bold"))
        self.video_title_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        info_details_frame = ctk.CTkFrame(self.video_info_frame, fg_color="transparent")
        info_details_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        self.video_duration_label = ctk.CTkLabel(info_details_frame, text="", font=ctk.CTkFont(size=13))
        self.video_duration_label.pack(side="left", padx=(0, 20))
        
        # Selection Options Section
        options_frame = ctk.CTkFrame(self.video_info_frame)
        options_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        # Main container for both selectors
        selectors_main_container = ctk.CTkFrame(options_frame, fg_color="transparent")
        selectors_main_container.pack(fill="x", padx=15, pady=15)
        
        # Video Quality Section (Left)
        quality_section = ctk.CTkFrame(selectors_main_container, fg_color="transparent")
        quality_section.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        quality_label = ctk.CTkLabel(quality_section, text="Video Quality:", font=ctk.CTkFont(size=13, weight="bold"))
        quality_label.pack(anchor="w", pady=(0, 5))
        
        self.quality_selector = ctk.CTkComboBox(quality_section, width=200, state="readonly")
        self.quality_selector.pack(fill="x")
        
        # Audio Language Section (Right)
        audio_section = ctk.CTkFrame(selectors_main_container, fg_color="transparent")
        audio_section.pack(side="left", fill="x", expand=True, padx=(10, 0))
        
        audio_label = ctk.CTkLabel(audio_section, text="Audio Language:", font=ctk.CTkFont(size=13, weight="bold"))
        audio_label.pack(anchor="w", pady=(0, 5))
        
        self.audio_selector = ctk.CTkComboBox(audio_section, width=200, state="readonly")
        self.audio_selector.pack(fill="x")
        
        # Store available streams for later use
        self.available_streams = {}
        self.available_audio = {}
        self.current_video = None
        
        # Output Folder Section
        folder_frame = ctk.CTkFrame(main_container)
        folder_frame.pack(fill="x", pady=(0, 15))
        
        folder_label = ctk.CTkLabel(folder_frame, text="Output Folder", font=ctk.CTkFont(size=14, weight="bold"))
        folder_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        folder_input_frame = ctk.CTkFrame(folder_frame, fg_color="transparent")
        folder_input_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        self.output_entry = ctk.CTkEntry(folder_input_frame, placeholder_text="/path/to/folder", height=40)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.output_entry.insert(0, os.path.expanduser("~/Downloads"))
        
        browse_button = ctk.CTkButton(folder_input_frame, text="Browse", width=80, height=40, command=self.select_output_folder)
        browse_button.pack(side="right")
        
        # Download Button and Progress Section
        progress_frame = ctk.CTkFrame(main_container)
        progress_frame.pack(fill="x", pady=(0, 15))
        
        button_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=15)
        
        self.download_button = ctk.CTkButton(button_frame, text="Download Video", height=45, 
                                           font=ctk.CTkFont(size=16, weight="bold"),
                                           command=self.download_video)
        self.download_button.pack(side="left")
        
        self.status_label = ctk.CTkLabel(button_frame, text="Ready to download", font=ctk.CTkFont(size=13))
        self.status_label.pack(side="right", padx=(20, 0))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(progress_frame, height=20)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 5))
        self.progress_bar.set(0)
        
        self.progress_label = ctk.CTkLabel(progress_frame, text="", font=ctk.CTkFont(size=12))
        self.progress_label.pack(padx=15, pady=(0, 15))
        
        # Activity Log Section
        log_frame = ctk.CTkFrame(main_container)
        log_frame.pack(fill="both", expand=True)
        
        log_label = ctk.CTkLabel(log_frame, text="Activity Log", font=ctk.CTkFont(size=14, weight="bold"))
        log_label.pack(anchor="w", padx=15, pady=(15, 5))
        
        # Create text widget for log
        log_container = ctk.CTkFrame(log_frame)
        log_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        self.log_text = ctk.CTkTextbox(log_container, font=ctk.CTkFont(family="SF Mono", size=12))
        self.log_text.pack(fill="both", expand=True)
        
        # Initial log messages
        self.log_message("WampyTube initialized successfully", "success")
        self.log_message(f"System: {MACOS_GPU['model']} • {SYSTEM_CORES} cores, {SYSTEM_THREADS} threads")
        self.log_message(f"FFmpeg: {FFMPEG_INFO.get('version', 'Not found')}")
    
    def log_message(self, message, level="info"):
        """Add message to activity log"""
        timestamp = time.strftime("%H:%M:%S")
        
        # Color coding based on level
        icon = {
            "info": "🔵",
            "success": "🟢",
            "warning": "🟡", 
            "error": "🔴"
        }.get(level, "⚪")
        
        formatted_message = f"[{timestamp}] {icon} {message}\n"
        
        # Add to text widget
        self.log_text.insert("end", formatted_message)
        self.log_text.see("end")
        
        # Also log to console
        logger.info(f"{icon} {message}")
    
    def paste_from_clipboard(self):
        """Paste clipboard content into URL field"""
        try:
            clipboard_text = self.clipboard_get()
            if clipboard_text:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, clipboard_text)
                # Auto-analyze if it's a YouTube URL
                if "youtube.com" in clipboard_text or "youtu.be" in clipboard_text:
                    self.analyze_url()
        except:
            pass
    
    def select_output_folder(self):
        """Open dialog to select output folder"""
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, folder_selected)
    
    def analyze_url(self):
        """Analyze YouTube URL and show video info"""
        url = self.url_entry.get().strip()
        if not url:
            return
        
        try:
            self.log_message("Analyzing video streams...")
            yt = YouTube(url, use_oauth=False, allow_oauth_cache=True)
            yt.check_availability()
            
            # Store current video for later use
            self.current_video = yt
            
            # Update video info display
            title_text = yt.title[:60] + "..." if len(yt.title) > 60 else yt.title
            self.video_title_label.configure(text=title_text)
            self.video_duration_label.configure(text=f"⏱️ {self.format_duration(yt.length)}")
            
            # Get all available streams
            self.populate_quality_options(yt)
            self.populate_audio_options(yt)
            
            # Show video info frame
            self.video_info_frame.pack(fill="x", pady=(0, 15), after=self.children['!ctkframe'].children['!ctkframe'])
            
            # Adjust window size if needed
            if not self.video_info_shown:
                self.video_info_shown = True
                self.after(100, self.adjust_window_size)  # Small delay to let the UI update
            
            self.log_message(f"Analyzed: {yt.title}", "success")
        except Exception as e:
            self.log_message(f"Failed to analyze URL: {str(e)}", "error")
    
    def populate_quality_options(self, yt):
        """Populate quality selector with available resolutions"""
        try:
            # Get all video streams (both progressive and adaptive)
            progressive_streams = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc()
            adaptive_streams = yt.streams.filter(adaptive=True, only_video=True, file_extension="mp4").order_by("resolution").desc()
            
            # Collect unique resolutions
            resolutions = set()
            stream_map = {}
            
            # Add progressive streams
            for stream in progressive_streams:
                if stream.resolution:
                    res_key = f"{stream.resolution} (Progressive)"
                    resolutions.add(res_key)
                    stream_map[res_key] = {'type': 'progressive', 'stream': stream}
            
            # Add adaptive streams (higher quality)
            for stream in adaptive_streams:
                if stream.resolution:
                    res_key = f"{stream.resolution} (Best Quality)"
                    resolutions.add(res_key)
                    stream_map[res_key] = {'type': 'adaptive', 'stream': stream}
            
            # Sort resolutions by quality (descending)
            sorted_resolutions = sorted(list(resolutions), key=lambda x: int(x.split('p')[0]), reverse=True)
            
            # Update selector
            self.quality_selector.configure(values=sorted_resolutions)
            if sorted_resolutions:
                self.quality_selector.set(sorted_resolutions[0])  # Select highest quality by default
            
            # Store stream mapping
            self.available_streams = stream_map
            
            self.log_message(f"Found {len(sorted_resolutions)} quality options")
            
        except Exception as e:
            self.log_message(f"Error getting quality options: {str(e)}", "error")
            self.quality_selector.configure(values=["Best Available"])
            self.quality_selector.set("Best Available")
    
    def populate_audio_options(self, yt):
        """Populate audio selector with available languages"""
        try:
            # Language code to name mapping
            language_names = {
                'en': 'English',
                'es': 'Spanish', 
                'es-ES': 'Spanish',
                'es-419': 'Spanish (Latin America)',
                'fr': 'French',
                'de': 'German',
                'it': 'Italian',
                'pt': 'Portuguese',
                'pt-BR': 'Portuguese (Brazil)',
                'ru': 'Russian',
                'ja': 'Japanese',
                'ko': 'Korean',
                'zh': 'Chinese',
                'zh-CN': 'Chinese (Simplified)',
                'zh-TW': 'Chinese (Traditional)',
                'ar': 'Arabic',
                'hi': 'Hindi',
                'tr': 'Turkish',
                'pl': 'Polish',
                'nl': 'Dutch',
                'sv': 'Swedish',
                'da': 'Danish',
                'no': 'Norwegian',
                'fi': 'Finnish'
            }
            
            audio_options = []
            audio_map = {}
            
            # Try to get language info from video metadata first
            try:
                # Access the video's raw data to get language information
                if hasattr(yt, 'vid_info') and yt.vid_info:
                    # Look for adaptive formats which might have language info
                    adaptive_formats = yt.vid_info.get('streamingData', {}).get('adaptiveFormats', [])
                    
                    for fmt in adaptive_formats:
                        if fmt.get('mimeType', '').startswith('audio/'):
                            lang_code = fmt.get('languageCode', '').lower()
                            quality = fmt.get('averageBitrate', 0)
                            quality_str = f"{quality//1000}kbps" if quality > 0 else "Unknown"
                            
                            if lang_code and lang_code in language_names:
                                lang_name = language_names[lang_code]
                                label = f"{lang_name} ({quality_str})"
                                
                                # Create a corresponding stream object
                                audio_streams = yt.streams.filter(only_audio=True, file_extension="mp4")
                                if audio_streams:
                                    # Match by quality or use best available
                                    matching_stream = None
                                    for stream in audio_streams:
                                        if stream.abr and quality_str in stream.abr:
                                            matching_stream = stream
                                            break
                                    
                                    if not matching_stream:
                                        matching_stream = audio_streams.order_by("abr").desc().first()
                                    
                                    if matching_stream and label not in [opt for opt in audio_options]:
                                        audio_options.append(label)
                                        audio_map[label] = matching_stream
            except Exception as e:
                self.log_message(f"Could not extract language info from metadata: {str(e)}", "warning")
            
            # If no languages found from metadata, fall back to stream analysis
            if not audio_options:
                audio_streams = yt.streams.filter(only_audio=True, file_extension="mp4").order_by("abr").desc()
                
                # Try to detect language from video title or description
                detected_lang = self.detect_video_language(yt)
                
                for i, stream in enumerate(audio_streams[:3]):  # Limit to top 3
                    quality = stream.abr or 'Unknown'
                    
                    if i == 0 and detected_lang:
                        # Use detected language for the first (best quality) stream
                        lang_name = language_names.get(detected_lang, detected_lang.upper())
                        label = f"{lang_name} ({quality})"
                    elif i == 0:
                        label = f"Default ({quality})"
                    else:
                        label = f"Alternative {i} ({quality})"
                    
                    audio_options.append(label)
                    audio_map[label] = stream
            
            # Update selector
            self.audio_selector.configure(values=audio_options)
            if audio_options:
                self.audio_selector.set(audio_options[0])  # Select best quality by default
            
            # Store audio mapping
            self.available_audio = audio_map
            
            self.log_message(f"Found {len(audio_options)} audio tracks")
            
        except Exception as e:
            self.log_message(f"Error getting audio options: {str(e)}", "error")
            self.audio_selector.configure(values=["Default Audio"])
            self.audio_selector.set("Default Audio")
    
    def detect_video_language(self, yt):
        """Try to detect video language from title, description, or channel"""
        try:
            # Simple language detection based on common patterns
            title = yt.title.lower() if yt.title else ""
            description = yt.description.lower() if yt.description else ""
            
            # Spanish indicators
            spanish_words = ['español', 'spanish', 'latino', 'castellano', 'méxico', 'argentina', 'colombia']
            if any(word in title or word in description for word in spanish_words):
                return 'es'
            
            # English is default for most content
            return 'en'
            
        except Exception:
            return 'en'  # Default to English
    
    def format_duration(self, seconds):
        """Format duration in seconds to readable string"""
        if not seconds:
            return "Unknown"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
    
    def update_progress(self, percentage, message=""):
        """Update progress bar and label"""
        self.progress_bar.set(percentage / 100)
        self.progress_label.configure(text=message)
        if percentage % 10 == 0:  # Log every 10%
            self.log_message(f"Progress: {percentage:.0f}% - {message}")
    
    def download_video(self):
        """Start video download in separate thread"""
        url = self.url_entry.get().strip()
        output_folder = self.output_entry.get().strip()
        
        if not url:
            self.log_message("Please enter a valid URL", "error")
            return
        if not output_folder:
            self.log_message("Please select an output folder", "error")
            return
        
        # Disable download button
        self.download_button.configure(state="disabled")
        self.status_label.configure(text="Downloading...")
        
        # Start download in thread
        thread = threading.Thread(target=self.download_in_thread, args=(url, output_folder))
        thread.daemon = True
        thread.start()
    
    def download_in_thread(self, url, output_folder):
        """Handle the download in a separate thread"""
        try:
            self.log_message("Starting download process...")
            
            # Create output directory if needed
            os.makedirs(output_folder, exist_ok=True)
            
            # Get YouTube object
            yt = YouTube(url, on_progress_callback=self.on_download_progress, use_oauth=False, allow_oauth_cache=True)
            yt.check_availability()
            
            # Get selected streams
            self.log_message("Preparing selected streams...")
            video_stream, audio_stream, needs_merge = self.get_selected_streams(yt)
            
            if not video_stream:
                raise Exception("No suitable stream found")
            
            resolution = video_stream.resolution
            self.log_message(f"Best quality found: {resolution}")
            
            if needs_merge:
                # Download video and audio separately
                self.after(0, lambda: self.status_label.configure(text=f"Downloading video ({resolution})..."))
                video_path = video_stream.download(output_folder, filename_prefix="video_")
                
                self.after(0, lambda: self.status_label.configure(text="Downloading audio..."))
                audio_path = audio_stream.download(output_folder, filename_prefix="audio_")
                
                # Merge with ffmpeg
                self.after(0, lambda: self.status_label.configure(text="Encoding with VideoToolbox..."))
                final_path = Path(video_path).parent / f"{Path(video_path).stem.replace('video_', '')}_HEVC.mp4"
                
                success = self.merge_audio_video(video_path, audio_path, str(final_path))
                
                if success:
                    # Clean up temp files
                    os.remove(video_path)
                    os.remove(audio_path)
                    self.log_message(f"Download complete! Saved to: {final_path.name}", "success")
                else:
                    raise Exception("Failed to merge audio and video")
            else:
                # Direct download
                final_path = video_stream.download(output_folder)
                self.log_message(f"Download complete! Saved to: {Path(final_path).name}", "success")
            
            # Update UI
            self.after(0, lambda: self.download_complete())
            
        except Exception as e:
            self.log_message(f"Download failed: {str(e)}", "error")
            self.after(0, lambda: self.download_failed())
    
    def get_selected_streams(self, yt):
        """Get streams based on user selection"""
        try:
            selected_quality = self.quality_selector.get()
            selected_audio = self.audio_selector.get()
            
            # Get video stream based on selection
            if selected_quality in self.available_streams:
                stream_info = self.available_streams[selected_quality]
                video_stream = stream_info['stream']
                needs_merge = stream_info['type'] == 'adaptive'
            else:
                # Fallback to best available
                video_stream = yt.streams.get_highest_resolution()
                needs_merge = False
            
            # Get audio stream based on selection
            audio_stream = None
            if needs_merge or selected_quality == "Best Available":
                if hasattr(self, 'available_audio') and selected_audio in self.available_audio:
                    audio_stream = self.available_audio[selected_audio]
                else:
                    # Fallback to best audio
                    audio_stream = yt.streams.filter(only_audio=True, file_extension="mp4")\
                                        .order_by("abr").desc().first()
                needs_merge = True
            
            return video_stream, audio_stream, needs_merge
            
        except Exception as e:
            self.log_message(f"Error getting selected streams, using defaults: {str(e)}", "warning")
            # Fallback to original logic
            return self.get_best_streams_fallback(yt)
    
    def get_best_streams_fallback(self, yt):
        """Fallback method for getting streams"""
        streams = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc()
        
        if not streams:
            return None, None, False
            
        best_progressive = streams.first()
        progressive_resolution = int(best_progressive.resolution[:-1]) if best_progressive else 0
        
        # If best progressive is less than 1080p, try adaptive
        if progressive_resolution < 1080:
            video_stream = yt.streams.filter(adaptive=True, file_extension="mp4", only_video=True)\
                                .order_by("resolution").desc().first()
            audio_stream = yt.streams.filter(only_audio=True, file_extension="mp4")\
                                .order_by("abr").desc().first()
            
            if video_stream and audio_stream:
                return video_stream, audio_stream, True
        
        return best_progressive, None, False
    
    def on_download_progress(self, stream, chunk, bytes_remaining):
        """Progress callback for download"""
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        percentage = (bytes_downloaded / total_size) * 100
        
        # Update progress in main thread
        self.after(0, lambda: self.update_progress(percentage, f"Downloading: {percentage:.1f}%"))
    
    def merge_audio_video(self, video_path, audio_path, output_path):
        """Merge audio and video using FFmpeg with VideoToolbox"""
        try:
            command = [
                FFMPEG_PATH,
                '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'hevc_videotoolbox',
                '-b:v', '6M',
                '-c:a', 'aac',
                '-b:a', '192k',
                output_path
            ]
            
            result = subprocess.run(command, capture_output=True, text=True)
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error merging: {str(e)}")
            return False
    
    def download_complete(self):
        """Reset UI after successful download"""
        self.download_button.configure(state="normal")
        self.status_label.configure(text="Download complete!")
        self.progress_bar.set(1.0)
        self.progress_label.configure(text="100% - Complete")
    
    def download_failed(self):
        """Reset UI after failed download"""
        self.download_button.configure(state="normal")
        self.status_label.configure(text="Download failed")
        self.progress_bar.set(0)
        self.progress_label.configure(text="")

def set_process_name():
    """Set process name before creating the app to change menu bar name"""
    try:
        # Check if running from native app bundle
        is_native_app = os.environ.get('WAMPYTUBE_APP') == '1'
        
        # Method 1: Set sys.argv[0] early
        sys.argv[0] = "WampyTube"
        
        # Method 2: macOS specific - set process name using Foundation (most effective)
        try:
            import objc
            from Foundation import NSProcessInfo, NSBundle
            
            # Set process name
            NSProcessInfo.processInfo().setProcessName_("WampyTube")
            
            # If running as native app, also set bundle info
            if is_native_app:
                bundle = NSBundle.mainBundle()
                if bundle:
                    info = bundle.infoDictionary()
                    if info:
                        info['CFBundleName'] = 'WampyTube'
                        info['CFBundleDisplayName'] = 'WampyTube'
            
            logger.info("Process name set using Foundation framework")
            
        except ImportError:
            # Foundation not available, try ctypes approach
            try:
                import ctypes
                import ctypes.util
                
                # Load Foundation framework
                foundation_lib = ctypes.util.find_library("Foundation")
                if foundation_lib:
                    objc_lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
                    
                    # Set up function signatures
                    objc_lib.objc_getClass.restype = ctypes.c_void_p
                    objc_lib.objc_getClass.argtypes = [ctypes.c_char_p]
                    objc_lib.sel_registerName.restype = ctypes.c_void_p
                    objc_lib.sel_registerName.argtypes = [ctypes.c_char_p]
                    objc_lib.objc_msgSend.restype = ctypes.c_void_p
                    objc_lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                    
                    # Get NSProcessInfo and set process name
                    NSProcessInfo = objc_lib.objc_getClass(b"NSProcessInfo")
                    processInfo = objc_lib.objc_msgSend(NSProcessInfo, objc_lib.sel_registerName(b"processInfo"))
                    
                    # Create NSString for "WampyTube"
                    objc_lib.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
                    NSString = objc_lib.objc_getClass(b"NSString")
                    app_name = objc_lib.objc_msgSend(NSString, objc_lib.sel_registerName(b"stringWithUTF8String:"), b"WampyTube")
                    objc_lib.objc_msgSend(processInfo, objc_lib.sel_registerName(b"setProcessName:"), app_name)
                    
                    logger.info("Process name set using ctypes Foundation framework")
            except Exception as e:
                logger.warning(f"Failed to set process name with ctypes: {e}")
        
    except Exception as e:
        logger.error(f"Failed to set process name: {e}")

if __name__ == "__main__":
    # Set process name before creating the app
    set_process_name()
    
    # Create and run the app
    app = WampyTubeApp()
    app.mainloop()