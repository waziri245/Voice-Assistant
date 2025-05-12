import tkinter as tk
from tkinter import messagebox
from tkinter.ttk import Combobox
import sqlite3
import re
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import pyttsx3
import threading
import subprocess
from datetime import datetime
import time
import os
import sys
from contextlib import contextmanager
import webbrowser
import pytz
import holidays
import wikipedia
import requests
import ctypes
import platform
import time


class NullDevice:
    def write(self, s):
        pass
    def flush(self):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

# 1. Set ALSA environment variables to suppress warnings
os.environ['PYTHONWARNINGS'] = 'ignore'
os.environ['ALSA_DEBUG'] = '0'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['PULSE_SERVER'] = 'tcp:localhost'
os.environ['ALSA_CARD'] = '0'

# 2. Create a more robust stderr suppressor
@contextmanager
def suppress_stderr():
    """Completely suppress stderr output including ALSA"""
    with open(os.devnull, 'w') as devnull:
        old_stderr = os.dup(sys.stderr.fileno())
        try:
            os.dup2(devnull.fileno(), sys.stderr.fileno())
            yield
        finally:
            os.dup2(old_stderr, sys.stderr.fileno())

# 3. Import speech_recognition with suppression
with suppress_stderr():
    import speech_recognition as sr

# 4. Initialize pyttsx3 with suppression
with suppress_stderr():
    import pyttsx3
    engine = pyttsx3.init()

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.connection = None
        self.lock = threading.Lock()
        
    def connect(self):
        """Create a new database connection"""
        try:
            self.connection = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=30.0  # Increased timeout
            )
            self.connection.execute("PRAGMA foreign_keys = ON")
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False
            
    def ensure_connection(self):
        """Ensure we have a working connection"""
        try:
            if self.connection is None:
                return self.connect()
            # Test the connection
            self.connection.execute("SELECT 1")
            return True
        except:
            try:
                self.close()
                return self.connect()
            except:
                return False
                
    def get_cursor(self):
        """Get a new cursor from the current connection"""
        if not self.connection:
            if not self.connect():
                raise sqlite3.Error("No database connection")
        return self.connection.cursor()
            
    def execute(self, query, params=()):
        if not self.ensure_connection():
            raise sqlite3.Error("Could not establish database connection")
            
        with self.lock:
            try:
                cursor = self.get_cursor()
                cursor.execute(query, params)
                self.connection.commit()
                return cursor
            except sqlite3.IntegrityError:
                raise  # Re-raise unique constraint violations
            except sqlite3.Error as e:
                print(f"Database error: {e}")
                try:
                    self.connection.rollback()
                except:
                    pass
                # Reconnect and retry once for non-unique errors
                try:
                    self.close()
                    self.connect()
                    cursor = self.get_cursor()
                    cursor.execute(query, params)
                    self.connection.commit()
                    return cursor
                except Exception as e2:
                    print(f"Fatal database error: {e2}")
                    raise e2

    def fetchone(self):
        return self.get_cursor().fetchone()

    def fetchall(self):
        return self.get_cursor().fetchall()

    def commit(self):
        if self.connection:
            self.connection.commit()

    @property
    def lastrowid(self):
        if self.connection:
            return self.connection.cursor().lastrowid
        return None
        
    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None

def initialize_database():
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            if not db_manager.ensure_connection():
                raise sqlite3.Error("Could not establish database connection")
                
            # Create tables if they don't exist
            db_manager.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    last_name TEXT,
                    email TEXT UNIQUE,
                    password TEXT,
                    voice_speed TEXT DEFAULT 'Normal'
                )
            """)
            
            db_manager.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_email TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    speaker TEXT,
                    message TEXT,
                    FOREIGN KEY(user_email) REFERENCES users(email)
                )
            """)
            db_manager.commit()
            return True
            
        except sqlite3.Error as e:
            retry_count += 1
            print(f"Database initialization attempt {retry_count} failed: {e}")
            if retry_count >= max_retries:
                raise
            time.sleep(1)  # Wait before retrying

class DarkButton(tk.Button):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(
            bg=DARK_THEME['button_bg'],
            fg=DARK_THEME['fg'],
            activebackground=DARK_THEME['button_active'],
            activeforeground=DARK_THEME['fg'],
            relief=tk.FLAT,
            padx=10,
            pady=5,
            borderwidth=0,
            highlightthickness=0
        )
        self.bind("<Enter>", lambda e: self.config(bg=DARK_THEME['highlight']))
        self.bind("<Leave>", lambda e: self.config(bg=DARK_THEME['button_bg']))

class DarkEntry(tk.Entry):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(
            bg=DARK_THEME['entry_bg'],
            fg=DARK_THEME['entry_fg'],
            insertbackground=DARK_THEME['fg'],
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=1,
            highlightcolor=DARK_THEME['accent'],
            highlightbackground=DARK_THEME['bg']
        )

class DarkLabel(tk.Label):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(
            bg=DARK_THEME['bg'],
            fg=DARK_THEME['fg'],
            padx=5,
            pady=5
        )

class DarkText(tk.Text):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(
            bg=DARK_THEME['text_bg'],
            fg=DARK_THEME['text_fg'],
            insertbackground=DARK_THEME['fg'],
            relief=tk.FLAT,
            borderwidth=0,
            padx=10,
            pady=10,
            wrap=tk.WORD,
            highlightthickness=0
        )

class DarkScrollbar(tk.Scrollbar):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(
            bg=DARK_THEME['bg'],
            activebackground=DARK_THEME['highlight'],
            troughcolor=DARK_THEME['bg'],
            relief=tk.FLAT
        )

    
# Global Variables
current_user = None
window = None
current_state = "main"
current_user_email = None
assistant_stop_event = threading.Event()  # Add this near your other global variables
# Initialize Argon2 Password Hasher
ph = PasswordHasher()

engine = pyttsx3.init()
voices = engine.getProperty('voices')
current_rate = engine.getProperty('rate')

# Connect to the SQLite database
db_manager = DatabaseManager('user.db')

# Add this near the top of your code with other constants
DARK_THEME = {
    'bg': '#121212',  # Dark background
    'fg': '#e0e0e0',  # Light text
    'accent': '#bb86fc',  # Purple accent
    'secondary': '#03dac6',  # Teal secondary
    'highlight': '#3700b3',  # Dark purple highlight
    'entry_bg': '#1e1e1e',  # Dark entry fields
    'entry_fg': '#ffffff',  # White text in entries
    'button_bg': '#1f1f1f',  # Button background
    'button_active': '#3700b3',  # Button when pressed
    'text_bg': '#1e1e1e',  # Text widget background
    'text_fg': '#ffffff',  # Text widget foreground
    'scrollbar': '#424242'  # Scrollbar color
}

def configure_window():
    """Configure window with dark theme"""
    global window
    
    # Get screen dimensions
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    # Set window to screen dimensions (fullscreen)
    window.geometry(f"{screen_width}x{screen_height}+0+0")
    
    # Set dark theme attributes
    window.configure(bg=DARK_THEME['bg'])
    window.option_add('*background', DARK_THEME['bg'])
    window.option_add('*foreground', DARK_THEME['fg'])
    window.option_add('*Font', 'Arial 10')
    
    # Try to maximize (works on Windows/macOS)
    try:
        window.state('zoomed')
    except tk.TclError:
        try:
            # Linux fallback - try different methods
            window.attributes('-zoomed', True)
        except:
            pass
    
    # Ensure window decorations remain visible
    window.attributes('-fullscreen', False)

def speak(text):
    """Thread-safe text-to-speech"""
    def _speak():
        with suppress_stderr():
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"Speech error: {e}")
    
    window.after(0, _speak)

def get_working_microphone():
    """Find a working microphone with complete error suppression"""
    with suppress_stderr():
        recognizer = sr.Recognizer()
        try:
            if hasattr(get_working_microphone, 'mic'):
                get_working_microphone.mic = None
                
            mic = sr.Microphone()
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
            get_working_microphone.mic = mic
            return mic
        except:
            pass
        
        for i in range(5):
            try:
                mic = sr.Microphone(device_index=i)
                with mic as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                get_working_microphone.mic = mic
                return mic
            except:
                continue
    return None

def listen_and_respond(conversation_area):
    recognizer = sr.Recognizer()
    microphone = get_working_microphone()
    
    if microphone is None:
        messagebox.showerror("Microphone Error", "No working microphone found")
        return None

    stop_event = threading.Event()
    processing_lock = threading.Lock()

    def update_gui(text):
        if conversation_area.winfo_exists():
            conversation_area.insert(tk.END, text)
            conversation_area.see(tk.END)
            window.update()

    def show_listening():
        if conversation_area.winfo_exists():
            conversation_area.insert(tk.END, "Listening...\n")
            conversation_area.see(tk.END)
            window.update()

    def hide_listening():
        if conversation_area.winfo_exists():
            current_text = conversation_area.get("1.0", tk.END)
            if current_text.endswith("Listening...\n"):
                conversation_area.delete("end-2l", "end")
            window.update()

    def listen():
        with suppress_stderr():
            try:
                window.after(0, show_listening)
                with microphone as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                window.after(0, hide_listening)
                return recognizer.recognize_google(audio)
            except sr.WaitTimeoutError:
                window.after(0, hide_listening)
                return None
            except Exception as e:
                print(f"Recognition error: {e}")
                window.after(0, hide_listening)
                return None

    def process_command(command):
        if not command or not command.strip():
            return None
            
        with processing_lock:
            command = command.strip()
            print(f"Processing command: {command}")
            window.after(0, lambda: update_gui(f"USER: {command}\n"))
            log_conversation(current_user_email, "USER", command)
            
            response = ""
            command_lower = command.lower()
            
            if any(greeting in command_lower for greeting in ["hello", "hi"]):
                response = "Hello! How can I help you today?"
            elif "current local time" in command_lower:
                response = f"The current time is {datetime.now().strftime('%H:%M')}"
            elif "date" in command_lower:
                response = f"Today's date is {datetime.now().strftime('%B %d, %Y')}"
            elif "hey assistant" in command_lower or "bot" in command_lower or "can you hear me" in command_lower or "hey" in command_lower:
                response = f"I am in your service"
            elif any(word in command_lower for word in ['holiday', 'holidays']):
                response = show_holidays(command_lower, conversation_area)
            elif any(word in command.lower() for word in ['time in', 'time at', 'world time', 'time zones', 'what time is it in']):
                response = show_world_time(command, conversation_area)
                # Don't manually insert to conversation_area here - let show_world_time handle it
                return response
            elif "open" in command_lower:
                app = command_lower.replace("open", "").strip()
                response = f"Opening {app}"
                try:
                    if "chrome" in app or "browser" in app or "web" in app or "google" in app or "google chrome" in app:
                        subprocess.Popen(["google-chrome"])
                    elif "terminal" in app or "command line" in app:
                        subprocess.Popen(["gnome-terminal"])
                    elif "file" in app or "explorer" in app or "folder" in app:
                        subprocess.Popen(["nautilus"])
                    elif "code" in app or "editor" in app or "vs code" in app:
                        subprocess.Popen(["code"])
                    elif "spotify" in app or "music" in app:
                        subprocess.Popen(["spotify"])
                    elif "calculator" in app:
                        subprocess.Popen(["gnome-calculator"])
                    elif "settings" in app or "preferences" in app:
                        subprocess.Popen(["gnome-control-center"])
                    elif "email" in app or "mail" in app or "thunderbird" in app:
                        subprocess.Popen(["thunderbird"])
                    elif "calendar" in app:
                        subprocess.Popen(["gnome-calendar"])
                    elif "discord" in app:
                        subprocess.Popen(["discord"])
                    elif "zoom" in app or "meeting" in app:
                        subprocess.Popen(["zoom"])
                    elif "slack" in app:
                        subprocess.Popen(["slack"])
                    elif "libreoffice" in app or "writer" in app or "word" in app:
                        subprocess.Popen(["libreoffice", "--writer"])  # Fixed: Split args
                    elif "spreadsheet" in app or "excel" in app:
                        subprocess.Popen(["libreoffice", "--calc"])  # Fixed: Split args
                    elif "presentation" in app or "powerpoint" in app:
                        subprocess.Popen(["libreoffice", "--impress"])  # Fixed: Split args
                    elif "photos" in app or "gallery" in app:
                        subprocess.Popen(["shotwell"])
                    elif "camera" in app:
                        subprocess.Popen(["cheese"])
                    elif "vscode" in app or "visual studio code" in app:
                        subprocess.Popen(["code"])
                    elif "telegram" in app:
                        subprocess.Popen(["telegram-desktop"])
                    elif "whatsapp" in app:
                        subprocess.Popen(["whatsapp-desktop"])  # Changed to a more common name
                    elif "steam" in app or "games" in app:
                        subprocess.Popen(["steam"])
                    elif "youtube" in app or "you tube" in app:  # Fixed duplicate check
                        webbrowser.open("https://www.youtube.com")  # Better: Use default browser
                    elif "chatgpt" in app or "ai" in app:
                        webbrowser.open("https://chat.openai.com")  # Fixed URL
                    else:
                        response = f"I'm not sure how to open {app}"
                except FileNotFoundError:
                    response = f"Sorry, it seems {app} is not installed."
                except Exception as e:
                    response = f"Sorry, I couldn't open {app}. Error: {str(e)}"
            elif "search google" in command_lower or "search web" in command_lower or "search chrome" in command_lower or "search google chrome" in command_lower:
                query = command_lower.replace("search google", "")\
                        .replace("search web", "")\
                        .replace("search chrome", "")\
                        .replace("search google chrome", "")\
                        .strip()
                if query:
                    response = f"Searching the web for {query}"
                    try:
                        subprocess.Popen(["google-chrome", f"https://www.google.com/search?q={query}"])
                    except:
                        response = "I couldn't perform the search. Please try again."
            
            elif any(phrase in command_lower for phrase in ["wikipedia", "what is", "who is", "tell me about"]):
                # Extract query
                query = re.sub(
                    r'(search wikipedia for|wikipedia|what is|who is|tell me about)\s*', 
                    '', 
                    command_lower
                ).strip()
                
                # First show user message
                if conversation_area and conversation_area.winfo_exists():
                    conversation_area.insert(tk.END, f"USER: {command}\n")
                    conversation_area.see(tk.END)
                
                if query:
                    response = search_wikipedia(query, conversation_area, display_only=True)
                    # Then show bot response
                    if conversation_area and conversation_area.winfo_exists():
                        conversation_area.insert(tk.END, f"BOT: {response}\n\n")
                        conversation_area.see(tk.END)
                else:
                    response = "What would you like me to search on Wikipedia?"
                
                return response


            elif any(phrase in command_lower for phrase in [
                "what is the meaning of",
                "define",
                "what does mean",
                "explain the word"
            ]):
                response = explain_word(command, conversation_area)


            # System control commands
            elif "lock computer" in command_lower or "lock pc" in command_lower:
                response = lock_computer()
            elif "restart computer" in command_lower or "reboot computer" in command_lower:
                if "confirm" in command_lower:
                    response = restart_computer(confirm=False)
                else:
                    response = restart_computer()
            elif "shutdown computer" in command_lower or "turn off computer" in command_lower:
                if "confirm" in command_lower:
                    response = shutdown_computer(confirm=False)
                else:
                    response = shutdown_computer()
            


            elif "weather" in command_lower or "forecast" in command_lower:
                # Extract city name
                city = command_lower.replace("weather", "").replace("forecast", "").replace("in", "").strip()
                if city:
                    response = show_weather(city, conversation_area)
                else:
                    response = "Please specify a city (e.g., 'weather in London')"

            
            elif "news" in command_lower or "headlines" in command_lower:
                response = get_news_summaries(conversation_area)

            elif any(word in command_lower for word in ["convert", "change", "to"]):
                response = process_conversion_command(command, conversation_area)

            elif "exit" in command_lower or "quit" in command_lower or "stop" in command_lower:
                response = "Goodbye! Have a nice day."
                window.after(0, lambda: update_gui(f"BOT: {response}\n"))
                speak(response)
                return False
            else:
                response = "I'm not sure how to help with that. Could you try asking something else?"
            
            if response:
                log_conversation(current_user_email, "BOT", response)
            
            return response

    def assistant_loop():
        last_command = None
        while not stop_event.is_set():
            command = listen()
            if command is None or command == last_command:
                continue
                
            response = process_command(command)
            if response is False:
                stop_event.set()
                break
            if response is None:
                continue
                
            last_command = command
            
            window.after(0, lambda: update_gui(f"USER: {command}\n"))
            window.after(0, lambda: update_gui(f"BOT: {response}\n\n"))
            speak(response)

    assistant_thread = threading.Thread(target=assistant_loop)
    assistant_thread.daemon = True
    assistant_thread.start()
    
    return stop_event

def setup_main_screen():
    clear_window()
    global window, current_state
    current_state = "main"
    configure_window()

    window.title("Voice Assistant - Main Menu")

    # Main container frame
    main_frame = tk.Frame(window, bg=DARK_THEME['bg'])
    main_frame.pack(expand=True, fill=tk.BOTH, padx=50, pady=50)

    # Title label
    DarkLabel(main_frame, 
             text="VOICE ASSISTANT", 
             font=("Arial", 24, "bold")
             ).pack(pady=(0, 40))

    # Button frame
    button_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
    button_frame.pack()

    # Buttons with icons and consistent styling
    DarkButton(button_frame, 
              text="🚀 Continue Without Account", 
              command=continue_without_account,
              width=25
              ).pack(pady=10, fill=tk.X)

    DarkButton(button_frame, 
              text="🔑 Sign In", 
              command=sign_in,
              width=25
              ).pack(pady=10, fill=tk.X)

    DarkButton(button_frame, 
              text="📝 Sign Up", 
              command=sign_up,
              width=25
              ).pack(pady=10, fill=tk.X)

    DarkButton(button_frame, 
              text="ℹ️ About Me", 
              command=about_me,
              width=25
              ).pack(pady=10, fill=tk.X)

    # Footer
    footer_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
    footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)

    DarkLabel(footer_frame, 
             text="© 2025 Voice Assistant | Version 1.0",
             font=("Arial", 8)
             ).pack()

def clear_window():
    global assistant_stop_event
    
    if 'assistant_stop_event' in globals() and assistant_stop_event:
        assistant_stop_event.set()
    
    for widget in window.winfo_children():
        widget.destroy()

def continue_without_account():
    clear_window()
    configure_window()

    # Main frame
    main_frame = tk.Frame(window, bg=DARK_THEME['bg'])
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Header
    header_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
    header_frame.pack(fill=tk.X, pady=10)

    DarkLabel(header_frame, 
             text="GUEST MODE", 
             font=("Arial", 16, "bold")
             ).pack(side=tk.LEFT)

    # Conversation area
    conv_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
    conv_frame.pack(fill=tk.BOTH, expand=True)

    conversation_area = DarkText(conv_frame)
    scrollbar = DarkScrollbar(conv_frame, command=conversation_area.yview)
    
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    conversation_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    conversation_area.config(yscrollcommand=scrollbar.set)
    
    # Welcome message
    conversation_area.insert(tk.END, "Voice Assistant - Guest Mode\n\n")
    wishMe()
    window.after(1500, lambda: speak("Voice Assistant initialized in guest mode."))
    
    # Start listening
    global assistant_stop_event
    assistant_stop_event = listen_and_respond(conversation_area)
    
    # Control buttons
    button_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
    button_frame.pack(fill=tk.X, pady=10)

    DarkButton(button_frame, 
              text="🔙 Main Menu", 
              command=setup_main_screen
              ).pack(side=tk.LEFT, padx=5)

    DarkButton(button_frame, 
              text="📝 Sign Up", 
              command=sign_up
              ).pack(side=tk.LEFT, padx=5)

    DarkButton(button_frame, 
              text="🔑 Sign In", 
              command=sign_in
              ).pack(side=tk.LEFT, padx=5)
def sign_up():
    def create_account_if_valid():
        # Get and clean input values
        name = name_entry.get().strip()
        last_name = last_entry.get().strip()
        email = email_entry.get().strip()
        password = password_entry.get().strip()
        confirm_password = confirm_entry.get().strip()

        def is_valid_name(name_str):
            """Check if name contains only letters, spaces or hyphens"""
            return all(c.isalpha() or c in (' ', '-') for c in name_str)

        def capitalize_name(name_str):
            """Capitalize first letter of each name part (including after hyphens)"""
            return ' '.join(word.capitalize() for part in name_str.split() 
                          for word in part.split('-')).replace('- ', '-')

        # Validation checks
        if not all([name, last_name, email, password, confirm_password]):
            messagebox.showerror("Error", "Please fill in all fields")
            return
            
        if not (is_valid_name(name) and is_valid_name(last_name)):
            messagebox.showerror("Error", "Name and Last name should contain only letters, spaces or hyphens")
            return
            
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            messagebox.showerror("Error", "Please enter a valid email address")
            return
            
        if password != confirm_password:
            messagebox.showerror("Error", "Passwords do not match")
            return

        # Capitalize names before saving
        capitalized_name = capitalize_name(name)
        capitalized_last_name = capitalize_name(last_name)

        # Check if user exists
        try:
            # Check if user exists first
            cursor = db_manager.execute("SELECT * FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                messagebox.showerror("Error", f"User with email '{email}' already exists.")
                return

            # Create account
            hashed_password = ph.hash(password)
            db_manager.execute("""
                INSERT INTO users (name, last_name, email, password) 
                VALUES (?, ?, ?, ?)
                """, 
                (capitalized_name, capitalized_last_name, email, hashed_password))
            
            messagebox.showinfo("Success", "User account created successfully.")
            setup_main_screen()
            
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", f"User with email '{email}' already exists.")
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", "Failed to create account. Please try again.")
            print(f"Database error: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {str(e)}")

    try:
        clear_window()
        configure_window()

        # Create a frame for better layout control (matches sign-in style)
        signup_frame = tk.Frame(window, bg=DARK_THEME['bg'])
        signup_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Title
        DarkLabel(signup_frame, 
                 text="CREATE ACCOUNT", 
                 font=("Arial", 16, "bold")
                 ).grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Form fields
        fields = [
            ("Name:", "name_entry"),
            ("Last Name:", "last_entry"),
            ("Email:", "email_entry"),
            ("Password:", "password_entry"),
            ("Confirm Password:", "confirm_entry")
        ]

        entries = {}  # Dictionary to store all entry widgets
        for i, (label_text, entry_name) in enumerate(fields, start=1):
            DarkLabel(signup_frame, text=label_text).grid(row=i, column=0, sticky=tk.E, pady=5)
            entry = DarkEntry(signup_frame, width=30)
            entry.grid(row=i, column=1, pady=5, padx=10)
            entries[entry_name] = entry  # Store the entry widget in dictionary
            if "password" in entry_name:
                entry.config(show="•")

        # Store references to entry widgets
        global name_entry, last_entry, email_entry, password_entry, confirm_entry
        name_entry = entries["name_entry"]
        last_entry = entries["last_entry"]
        email_entry = entries["email_entry"]
        password_entry = entries["password_entry"]
        confirm_entry = entries["confirm_entry"]

        # Buttons
        button_frame = tk.Frame(signup_frame, bg=DARK_THEME['bg'])
        button_frame.grid(row=len(fields)+1, column=0, columnspan=2, pady=20)

        DarkButton(button_frame, 
                  text="Create Account", 
                  command=create_account_if_valid
                  ).pack(side=tk.LEFT, padx=10)

        DarkButton(button_frame, 
                  text="Main Menu", 
                  command=setup_main_screen
                  ).pack(side=tk.LEFT, padx=10)

    except Exception as e:
        print(f"Error initializing signup screen: {e}")
        messagebox.showerror("Error", "Failed to initialize signup form")
        setup_main_screen()

def get_user_from_database(email):
    cursor = db_manager.execute("SELECT * FROM users WHERE email = ?", (email,))
    return cursor.fetchone()

def sign_in():
    clear_window()
    configure_window()

    # Create a frame for better layout control
    login_frame = tk.Frame(window, bg=DARK_THEME['bg'])
    login_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    # Title
    DarkLabel(login_frame, 
             text="Voice Assistant Login", 
             font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=20)

    # Email
    DarkLabel(login_frame, text="Email:").grid(row=1, column=0, sticky=tk.E, pady=5)
    email_entry = DarkEntry(login_frame, width=30)
    email_entry.grid(row=1, column=1, pady=5, padx=10)

    # Password
    DarkLabel(login_frame, text="Password:").grid(row=2, column=0, sticky=tk.E, pady=5)
    password_entry = DarkEntry(login_frame, width=30, show="*")
    password_entry.grid(row=2, column=1, pady=5, padx=10)

    # Buttons
    button_frame = tk.Frame(login_frame, bg=DARK_THEME['bg'])
    button_frame.grid(row=3, column=0, columnspan=2, pady=20)

    DarkButton(button_frame, 
              text="Login", 
              command=lambda: login(email_entry.get(), password_entry.get())
              ).pack(side=tk.LEFT, padx=10)
    
    DarkButton(button_frame, 
              text="Sign Up", 
              command=sign_up
              ).pack(side=tk.LEFT, padx=10)
    
    DarkButton(button_frame, 
              text="Main Menu", 
              command=setup_main_screen
              ).pack(side=tk.LEFT, padx=10)

def login(email, password):
    if not email or not password:
        messagebox.showerror("Error", "Please enter both email and password")
        return
        
    user = get_user_from_database(email)
    if not user:
        messagebox.showerror("Error", "User not found")
        return
        
    try:
        ph.verify(user[4], password)
        global current_user, current_user_email
        current_user = user
        current_user_email = email
        
        db_manager.execute("SELECT voice_speed FROM users WHERE email=?", (email,))
        speed_setting = db_manager.fetchone()
        if speed_setting:
            speed = speed_setting[0]
            engine.setProperty('rate', 200 if speed == "Fast" else 100 if speed == "Slow" else 150)
       
        print(f"\n=== LOGIN SUCCESSFUL ===")
        print(f"User: {email}")
        logged_in()
    except VerifyMismatchError:
        messagebox.showerror("Error", "Invalid password")

def logged_in():
    global current_state, assistant_stop_event
    
    # Stop any existing assistant
    if assistant_stop_event:
        assistant_stop_event.set()
    
    # Create a new event for the new assistant
    assistant_stop_event = threading.Event()
    
    current_state = "logged_in"
    clear_window()
    configure_window()

    user_name = f"{current_user[1]} {current_user[2]}"

    # Main conversation frame
    main_frame = tk.Frame(window, bg=DARK_THEME['bg'])
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Header with user info
    header_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
    header_frame.pack(fill=tk.X, pady=10)
    
    DarkLabel(header_frame, 
             text=f"Voice Assistant - {user_name}", 
             font=("Arial", 14, "bold")
             ).pack(side=tk.LEFT)
    
    # Conversation area
    conv_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
    conv_frame.pack(fill=tk.BOTH, expand=True)
    
    conversation_area = DarkText(conv_frame)
    conversation_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    scrollbar = DarkScrollbar(conv_frame, command=conversation_area.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    conversation_area.config(yscrollcommand=scrollbar.set)
    
    # Welcome message
    welcome_msg = f"Voice Assistant initialized.\nLogged in as {user_name}\n\n"
    conversation_area.insert(tk.END, welcome_msg)
    
    # Control buttons
    button_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
    button_frame.pack(fill=tk.X, pady=10)
    
    DarkButton(button_frame, 
              text="LOG OUT", 
              command=log_out
              ).pack(side=tk.LEFT, padx=5)
    
    DarkButton(button_frame, 
              text="History", 
              command=show_history
              ).pack(side=tk.LEFT, padx=5)
    
    DarkButton(button_frame, 
              text="Settings", 
              command=show_settings
              ).pack(side=tk.LEFT, padx=5)
    
    DarkButton(button_frame, 
              text="About Me", 
              command=about_me
              ).pack(side=tk.LEFT, padx=5)
    
    wishMe()
    window.after(1500, lambda: speak("Voice Assistant initialized."))
    
    assistant_stop_event = listen_and_respond(conversation_area)

def show_settings():
    clear_window()
    configure_window()

    def ask_for_password(stored_hashed_password):
        password_window = tk.Toplevel(window)
        password_window.title("Verify Password")
        password_window.configure(bg=DARK_THEME['bg'])
        password_window.resizable(False, False)
        
        DarkLabel(password_window, text="Enter your password:").pack(pady=10)
        password_entry = DarkEntry(password_window, show='*')
        password_entry.pack(pady=5)

        def verify_password():
            try:
                if ph.verify(stored_hashed_password, password_entry.get()):
                    password_window.destroy()
                    change_name_window()
                else:
                    messagebox.showerror("Error", "Incorrect password")
            except VerifyMismatchError:
                messagebox.showerror("Error", "Incorrect password")

        button_frame = tk.Frame(password_window, bg=DARK_THEME['bg'])
        button_frame.pack(pady=10)
        
        DarkButton(button_frame, 
                  text="Verify", 
                  command=verify_password
                  ).pack(side=tk.LEFT, padx=5)
        
        DarkButton(button_frame, 
                  text="Cancel", 
                  command=password_window.destroy
                  ).pack(side=tk.LEFT, padx=5)

    def change_name_window():
        change_window = tk.Toplevel(window)
        change_window.title("Change Name")
        change_window.configure(bg=DARK_THEME['bg'])
        change_window.resizable(False, False)
        
        user_info = get_current_user_info()
        if not user_info:
            messagebox.showerror("Error", "User not found")
            change_window.destroy()
            return
            
        current_name, last_name, _ = user_info

        DarkLabel(change_window, text="New first name:").pack(pady=5)
        new_name_entry = DarkEntry(change_window)
        new_name_entry.insert(0, current_name)
        new_name_entry.pack(pady=5)

        DarkLabel(change_window, text="New last name:").pack(pady=5)
        new_last_entry = DarkEntry(change_window)
        new_last_entry.insert(0, last_name if last_name else "")
        new_last_entry.pack(pady=5)

        def save_new_name():
            new_name = new_name_entry.get().strip()
            new_last = new_last_entry.get().strip()
            
            if not new_name:
                messagebox.showerror("Error", "First name cannot be empty")
                return
                
            try:
                update_user_info(new_name, new_last)
                messagebox.showinfo("Success", "Name updated successfully!")
                change_window.destroy()
                show_settings()  # Refresh settings page
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update name: {str(e)}")

        button_frame = tk.Frame(change_window, bg=DARK_THEME['bg'])
        button_frame.pack(pady=10)
        
        DarkButton(button_frame, 
                  text="Save", 
                  command=save_new_name
                  ).pack(side=tk.LEFT, padx=5)
        
        DarkButton(button_frame, 
                  text="Cancel", 
                  command=change_window.destroy
                  ).pack(side=tk.LEFT, padx=5)

    # Main settings window content
    main_frame = tk.Frame(window, bg=DARK_THEME['bg'])
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Title
    DarkLabel(main_frame, 
             text="SETTINGS", 
             font=("Arial", 16, "bold")
             ).pack(pady=(0, 20))

    user_info = get_current_user_info()
    if user_info:
        current_name, last_name, stored_hashed_password = user_info
        full_name = f"{current_name} {last_name}" if last_name else current_name

        # User Profile Section
        profile_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
        profile_frame.pack(fill=tk.X, pady=10)

        DarkLabel(profile_frame, 
                 text="👤 User Profile", 
                 font=("Arial", 12, "bold")
                 ).pack(anchor=tk.W)

        info_frame = tk.Frame(profile_frame, bg=DARK_THEME['bg'])
        info_frame.pack(fill=tk.X, pady=10)

        DarkLabel(info_frame, text="Name:", width=10).grid(row=0, column=0, sticky=tk.W)
        DarkLabel(info_frame, text=full_name).grid(row=0, column=1, sticky=tk.W)

        DarkLabel(info_frame, text="Email:", width=10).grid(row=1, column=0, sticky=tk.W, pady=5)
        DarkLabel(info_frame, text=current_user_email).grid(row=1, column=1, sticky=tk.W)

        DarkButton(profile_frame, 
                  text="✏️ Change Name", 
                  command=lambda: ask_for_password(stored_hashed_password)
                  ).pack(pady=10)

        # Voice Settings Section
        voice_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
        voice_frame.pack(fill=tk.X, pady=20)

        DarkLabel(voice_frame, 
                 text="🔊 Voice Settings", 
                 font=("Arial", 12, "bold")
                 ).pack(anchor=tk.W)

        speed_frame = tk.Frame(voice_frame, bg=DARK_THEME['bg'])
        speed_frame.pack(fill=tk.X, pady=10)

        DarkLabel(speed_frame, text="Voice Speed:").pack(side=tk.LEFT)
        
        speed_combobox = Combobox(speed_frame, 
                                values=["Fast", "Normal", "Slow"], 
                                state="readonly")
        speed_combobox.pack(side=tk.LEFT, padx=10)
        
        # Set current speed
        db_manager.execute("SELECT voice_speed FROM users WHERE email=?", (current_user_email,))
        saved_speed = db_manager.fetchone()
        current_speed = saved_speed[0] if saved_speed else "Normal"
        speed_combobox.set(current_speed)
        
        def save_speed():
            new_speed = speed_combobox.get()
            db_manager.execute("""
                UPDATE users 
                SET voice_speed=? 
                WHERE email=?
            """, (new_speed, current_user_email))
            db_manager.commit()
            
            engine.setProperty('rate', 200 if new_speed == "Fast" else 100 if new_speed == "Slow" else 150)
            messagebox.showinfo("Saved", "Voice speed updated!")
        
        DarkButton(speed_frame, 
                  text="💾 Save", 
                  command=save_speed
                  ).pack(side=tk.LEFT, padx=10)

    # Back button
    DarkButton(main_frame, 
              text="🔙 Back to Assistant", 
              command=logged_in
              ).pack(pady=20)

def get_current_user_info():
    print(f"Looking up user with email: {current_user_email}")
    result = db_manager.execute("SELECT name, last_name, password FROM users WHERE email = ?", (current_user_email,))
    user_info = result.fetchone()
    print(f"Found user info: {user_info}")
    return user_info

def update_user_info(new_name, new_last_name):
    db_manager.execute("UPDATE users SET name = ?, last_name = ? WHERE email = ?", 
                      (new_name, new_last_name, current_user_email))
    db_manager.commit()

def log_conversation(email, speaker, message):
    try:
        db_manager.execute(
            "INSERT INTO conversations (user_email, speaker, message) VALUES (?, ?, ?)",
            (email, speaker, message.strip())
        )
        db_manager.commit()  # Ensure this is here
    except Exception as e:
        print(f"Failed to log conversation: {e}")

def show_history():
    clear_window()
    configure_window()

    # Main container
    history_frame = tk.Frame(window, bg=DARK_THEME['bg'])
    history_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Header
    header_frame = tk.Frame(history_frame, bg=DARK_THEME['bg'])
    header_frame.pack(fill=tk.X, pady=10)

    DarkLabel(header_frame, 
             text="CONVERSATION HISTORY", 
             font=("Arial", 16, "bold")
             ).pack(side=tk.LEFT)

    DarkButton(header_frame, 
              text="🔙 Back", 
              command=logged_in
              ).pack(side=tk.RIGHT)

    # Text area with scrollbar
    text_frame = tk.Frame(history_frame, bg=DARK_THEME['bg'])
    text_frame.pack(fill=tk.BOTH, expand=True)

    text_area = DarkText(text_frame)
    scrollbar = DarkScrollbar(text_frame, command=text_area.yview)
    text_area.config(yscrollcommand=scrollbar.set)

    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Fetch and display history
    cursor = db_manager.execute(
        "SELECT timestamp, speaker, message FROM conversations WHERE user_email = ? ORDER BY timestamp DESC", 
        (current_user_email,)
    )
    conversations = cursor.fetchall()

    if not conversations:
        text_area.insert(tk.END, "No conversation history found")
    else:
        text_area.insert(tk.END, "Your Conversation History:\n\n")
        for timestamp, speaker, message in conversations:
            # Color coding for speaker
            speaker_color = DARK_THEME['accent'] if speaker == "BOT" else DARK_THEME['secondary']
            text_area.insert(tk.END, f"{timestamp} - ", "timestamp")
            text_area.insert(tk.END, f"{speaker}: ", ("speaker", speaker.lower()))
            text_area.insert(tk.END, f"{message}\n\n")
            
        # Configure tags for styling
        text_area.tag_config("timestamp", foreground="#aaaaaa")
        text_area.tag_config("speaker", font=("Arial", 10, "bold"))
        text_area.tag_config("user", foreground=DARK_THEME['secondary'])
        text_area.tag_config("bot", foreground=DARK_THEME['accent'])

    text_area.config(state=tk.DISABLED)

def about_me():
    clear_window()
    configure_window()
    # Main frame with scrollbar
    main_frame = tk.Frame(window)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Create canvas and scrollbar
    canvas = tk.Canvas(main_frame)
    scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas)
    
    # Configure canvas scrolling
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")
        )
    )
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Pack canvas and scrollbar
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # Project description
    tk.Label(scrollable_frame, 
             text="About This Voice Assistant Project",
             font=("Arial", 16, "bold")).pack(pady=10)
    
    description = """This is an advanced Voice Assistant program developed with Python that combines:
    
• Natural language voice commands
• Secure user authentication
• Conversation history tracking
• Smart home/device control
• Information lookup (weather, time, conversions)
• Alarm and timer functionality
• System utilities (locking, shutdown)

The assistant features:
✓ Voice recognition
✓ Text-to-speech responses
✓ Cross-platform compatibility
✓ Database-backed user accounts
✓ Multi-threaded operation
"""
    tk.Label(scrollable_frame, 
             text=description,
             justify=tk.LEFT).pack(pady=10, padx=20)
    
    # Creator information
    tk.Label(scrollable_frame, 
             text="Creator Information",
             font=("Arial", 14, "bold")).pack(pady=(20,5))
    
    creator_info = """Developed by Atal Abdullah Waziri
Co-founder of Stellar Organization

This project represents my work in Python programming, SQL,
voice technology, and assistant development."""
    tk.Label(scrollable_frame, 
             text=creator_info,
             justify=tk.LEFT).pack(pady=5, padx=20)
    
    # Contact information
    tk.Label(scrollable_frame, 
             text="📫 Contact Information",
             font=("Arial", 14, "bold")).pack(pady=(20,5))
    
    # Email label
    email_frame = tk.Frame(scrollable_frame)
    email_frame.pack(anchor="w", padx=20)
    tk.Label(email_frame, text="Email: ").pack(side="left")
    email_link = tk.Label(email_frame, text="atalwaziri9@gmail.com", fg="blue", cursor="hand2")
    email_link.pack(side="left")
    email_link.bind("<Button-1>", lambda e: webbrowser.open("mailto:atalwaziri9@gmail.com"))
    
    # Instagram label
    insta_frame = tk.Frame(scrollable_frame)
    insta_frame.pack(anchor="w", padx=20)
    tk.Label(insta_frame, text="Instagram: ").pack(side="left")
    insta_link = tk.Label(insta_frame, text="https://www.instagram.com/atal_waziri/", fg="blue", cursor="hand2")
    insta_link.pack(side="left")
    insta_link.bind("<Button-1>", lambda e: webbrowser.open("https://www.instagram.com/atal_waziri/"))
    
    # Stellar Organization links
    tk.Label(scrollable_frame, 
             text="🌐 Stellar Organization Links",
             font=("Arial", 14, "bold")).pack(pady=(20,5))
    
    # Website
    website_frame = tk.Frame(scrollable_frame)
    website_frame.pack(anchor="w", padx=20)
    tk.Label(website_frame, text="Website: ").pack(side="left")
    website_link = tk.Label(website_frame, text="https://stellarorganization.mystrikingly.com/", fg="blue", cursor="hand2")
    website_link.pack(side="left")
    website_link.bind("<Button-1>", lambda e: webbrowser.open("https://stellarorganization.mystrikingly.com/"))
    
    # YouTube
    yt_frame = tk.Frame(scrollable_frame)
    yt_frame.pack(anchor="w", padx=20)
    tk.Label(yt_frame, text="YouTube: ").pack(side="left")
    yt_link = tk.Label(yt_frame, text="https://youtube.com/@Stellar_1Tech", fg="blue", cursor="hand2")
    yt_link.pack(side="left")
    yt_link.bind("<Button-1>", lambda e: webbrowser.open("https://youtube.com/@Stellar_1Tech"))
    
    # Instagram
    stellar_insta_frame = tk.Frame(scrollable_frame)
    stellar_insta_frame.pack(anchor="w", padx=20)
    tk.Label(stellar_insta_frame, text="Instagram: ").pack(side="left")
    stellar_insta_link = tk.Label(stellar_insta_frame, text="https://www.instagram.com/stellar_1training", fg="blue", cursor="hand2")
    stellar_insta_link.pack(side="left")
    stellar_insta_link.bind("<Button-1>", lambda e: webbrowser.open("https://www.instagram.com/stellar_1training"))
    
    # WhatsApp
    wa_frame = tk.Frame(scrollable_frame)
    wa_frame.pack(anchor="w", padx=20)
    tk.Label(wa_frame, text="WhatsApp Community: ").pack(side="left")
    wa_link = tk.Label(wa_frame, text="https://chat.whatsapp.com/H47fnJwZfeVG8ccISZbgqp", fg="blue", cursor="hand2")
    wa_link.pack(side="left")
    wa_link.bind("<Button-1>", lambda e: webbrowser.open("https://chat.whatsapp.com/H47fnJwZfeVG8ccISZbgqp"))
    
    # Blog link
    tk.Label(scrollable_frame, 
             text="✍️ Blog",
             font=("Arial", 14, "bold")).pack(pady=(20,5))
    
    blog_frame = tk.Frame(scrollable_frame)
    blog_frame.pack(anchor="w", padx=20)
    blog_link = tk.Label(blog_frame, text="https://atalcodeblog.wordpress.com", fg="blue", cursor="hand2")
    blog_link.pack(side="left")
    blog_link.bind("<Button-1>", lambda e: webbrowser.open("https://atalcodeblog.wordpress.com"))
    
    # Back button at bottom
    tk.Button(scrollable_frame, 
              text="🔙 Back", 
              command=back_to_previous,
              padx=20).pack(pady=20)

def back_to_previous():
    if current_state == "logged_in":
        logged_in()
    else:
        setup_main_screen()

def wishMe():
    hour = datetime.now().hour 
    if hour >= 0 and hour < 12:
        speak("Good Morning Sir !")

    elif hour >= 12 and hour < 18:
        speak("Good Afternoon Sir !")

    else:
        speak("Good Evening Sir !")

def convert_units(value, from_unit, to_unit):
    """Handle all supported unit conversions"""
    # Normalize units
    from_unit = from_unit.lower()
    to_unit = to_unit.lower()
    
    try:
        value = float(value)
    except ValueError:
        return "Invalid number"
    
    # Length conversions
    length_units = {
        'mm': 0.001,
        'cm': 0.01,
        'm': 1.0,
        'km': 1000.0,
        'in': 0.0254,
        'ft': 0.3048,
        'yd': 0.9144,
        'mi': 1609.34
    }
    
    # Weight conversions
    weight_units = {
        'mg': 0.001,
        'g': 1.0,
        'kg': 1000.0,
        'oz': 28.3495,
        'lb': 453.592,
        'ton': 907185
    }
    
    # Volume conversions
    volume_units = {
        'ml': 0.001,
        'l': 1.0,
        'gal': 3.78541,
        'qt': 0.946353,
        'pt': 0.473176,
        'cup': 0.24,
        'fl oz': 0.0295735
    }
    
    # Temperature conversions
    if from_unit in ['c', 'f'] and to_unit in ['c', 'f']:
        if from_unit == 'c' and to_unit == 'f':
            return value * 9/5 + 32
        elif from_unit == 'f' and to_unit == 'c':
            return (value - 32) * 5/9
        else:
            return value
    
    # Check which conversion type we're doing
    if from_unit in length_units and to_unit in length_units:
        # Convert to meters first, then to target unit
        meters = value * length_units[from_unit]
        return meters / length_units[to_unit]
    elif from_unit in weight_units and to_unit in weight_units:
        # Convert to grams first
        grams = value * weight_units[from_unit]
        return grams / weight_units[to_unit]
    elif from_unit in volume_units and to_unit in volume_units:
        # Convert to liters first
        liters = value * volume_units[from_unit]
        return liters / volume_units[to_unit]
    else:
        return "Unsupported unit conversion"

def process_conversion_command(command, conversation_area=None):
    """Handle unit conversion voice commands"""
    try:
        # Improved pattern to catch more variations
        pattern = r'(?:convert|change)\s+(\d+\.?\d*)\s+(\w+)\s+(?:to|in)\s+(\w+)'
        match = re.search(pattern, command.lower())
        
        if not match:
            return "Please specify units to convert from and to (e.g., 'convert 5 kilometers to meters')"
        
        value, from_unit, to_unit = match.groups()
        value = float(value)
        
        # Common unit aliases - expanded list
        unit_aliases = {
            # Length
            'kilometer': 'km', 'kilometers': 'km', 'km': 'km',
            'meter': 'm', 'meters': 'm', 'm': 'm',
            'centimeter': 'cm', 'centimeters': 'cm', 'cm': 'cm',
            'millimeter': 'mm', 'millimeters': 'mm', 'mm': 'mm',
            # Weight
            'kilogram': 'kg', 'kilograms': 'kg', 'kg': 'kg',
            'gram': 'g', 'grams': 'g', 'g': 'g',
            'milligram': 'mg', 'milligrams': 'mg', 'mg': 'mg',
            # Add more units as needed
        }
        
        from_unit = unit_aliases.get(from_unit, from_unit)
        to_unit = unit_aliases.get(to_unit, to_unit)
        
        result = convert_units(value, from_unit, to_unit)
        
        if isinstance(result, str):
            return result  # Error message
        
        response = f"{value} {from_unit} = {result:.2f} {to_unit}"
        
        if conversation_area:
            conversation_area.insert(tk.END, f"BOT: {response}\n\n")
            conversation_area.see(tk.END)
        
        return response
    
    except Exception as e:
        return f"Conversion failed: {str(e)}"
    
def get_news_summaries(conversation_area=None):
    """Fetch top 5 global news headlines with summaries"""
    try:
        API_KEY = "your_newsapi_key"  # Replace with your actual key
        url = f"https://newsapi.org/v2/top-headlines?country=us&pageSize=5&apiKey={API_KEY}"
        
        response = requests.get(url)
        data = response.json()
        
        if data['status'] != 'ok' or not data['articles']:
            return "Couldn't fetch news at the moment"
        
        news_items = []
        for article in data['articles'][:5]:  # Get top 5
            title = article['title']
            description = article['description'] or "No description available"
            source = article['source']['name']
            
            # Create 3-line summary
            summary = (
                f"📰 {title}\n"
                f"   - {description.split('.')[0]}\n"
                f"   - Source: {source}\n"
            )
            news_items.append(summary)
        
        # Format response
        response = "🌍 Top Global News Headlines:\n"
        full_report = response + "\n".join(news_items)
        
        # Update GUI
        if conversation_area:
            conversation_area.insert(tk.END, f"BOT: {response}\n")
            conversation_area.insert(tk.END, full_report + "\n\n")
            conversation_area.see(tk.END)
        
        return response  # Only speak the intro
    
    except Exception as e:
        print(f"News error: {e}")
        return "Failed to fetch news updates"
    
def get_weather(city_name):
    """Get current weather and forecast for a city"""
    try:
        # Use OpenWeatherMap API (free tier)
        API_KEY = "your_api_key"  # Get from https://openweathermap.org/
        base_url = "http://api.openweathermap.org/data/2.5/weather"
        forecast_url = "http://api.openweathermap.org/data/2.5/forecast"
        
        # Get current weather
        current_params = {
            'q': city_name,
            'units': 'metric',
            'appid': API_KEY
        }
        current_response = requests.get(base_url, params=current_params).json()
        
        # Get forecast
        forecast_params = {
            'q': city_name,
            'units': 'metric',
            'appid': API_KEY,
            'cnt': 5  # Next 5 time periods (about 24 hours)
        }
        forecast_response = requests.get(forecast_url, params=forecast_params).json()
        
        return {
            'current': current_response,
            'forecast': forecast_response
        }
    except Exception as e:
        print(f"Weather API error: {e}")
        return None

def show_weather(city_name, conversation_area=None):
    """Process weather command and display results"""
    try:
        weather_data = get_weather(city_name)
        if not weather_data:
            return f"Couldn't get weather data for {city_name}"
        
        current = weather_data['current']
        forecast = weather_data['forecast']
        
        # Current conditions to speak
        temp = current['main']['temp']
        condition = current['weather'][0]['description']
        date = datetime.fromtimestamp(current['dt']).strftime('%A, %B %d')
        
        spoken_response = f"Current weather in {city_name}: {date}, {temp}°C, {condition}"
        
        # Forecast to display in GUI
        forecast_text = f"\n🌦️ {city_name} Weather Forecast:\n"
        for entry in forecast['list']:
            time = datetime.fromtimestamp(entry['dt']).strftime('%a %H:%M')
            temp = entry['main']['temp']
            condition = entry['weather'][0]['description']
            forecast_text += f"• {time}: {temp}°C, {condition}\n"
        
        # Update GUI
        if conversation_area:
            conversation_area.insert(tk.END, f"BOT: {spoken_response}\n")
            conversation_area.insert(tk.END, forecast_text + "\n")
            conversation_area.see(tk.END)
        
        return spoken_response
    
    except Exception as e:
        return f"Error getting weather: {str(e)}"

# ===== SYSTEM CONTROL FUNCTIONS =====
def lock_computer():
    try:
        if platform.system() == "Windows":
            ctypes.windll.user32.LockWorkStation()
            return "Computer locked successfully"
        elif platform.system() == "Linux":
            # Try all common Linux locking methods with availability checks
            methods = [
                ("loginctl lock-session", ["loginctl"]),  # Systemd
                ("xdg-screensaver lock", ["xdg-screensaver"]),  # XDG standard
                ("gnome-screensaver-command -l", ["gnome-screensaver-command"]),  # GNOME
                ("i3lock", ["i3lock"]),  # i3 window manager
                ("dm-tool lock", ["dm-tool"]),  # LightDM (won't fail if not available)
                ("qdbus org.freedesktop.ScreenSaver /ScreenSaver Lock", ["qdbus"])  # KDE
            ]
            
            for cmd, deps in methods:
                try:
                    # Check if all dependencies exist
                    if all(subprocess.call(["which", dep], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0 for dep in deps):
                        subprocess.run(cmd.split(), check=True)
                        return "Computer locked successfully"
                except:
                    continue
            
            # Final fallback - try to detect desktop environment
            desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
            if "gnome" in desktop or "ubuntu" in desktop:
                os.system("dbus-send --type=method_call --dest=org.gnome.ScreenSaver /org/gnome/ScreenSaver org.gnome.ScreenSaver.Lock")
            elif "kde" in desktop:
                os.system("qdbus org.freedesktop.ScreenSaver /ScreenSaver Lock")
            else:
                os.system("i3lock")  # Try i3lock as last resort
            
            return "Computer locked successfully"
            
    except Exception as e:
        return f"Failed to lock computer: {str(e)}"

def restart_computer(confirm=True):
    if confirm:
        return "Please confirm you want to restart the computer"
    try:
        if platform.system() == "Windows":
            os.system("shutdown /r /t 1")
        elif platform.system() == "Linux":
            os.system("systemctl reboot")
        return "Restarting computer now..."
    except Exception as e:
        return f"Failed to restart: {str(e)}"

def shutdown_computer(confirm=True):
    if confirm:
        return "Please confirm you want to shutdown the computer"
    try:
        if platform.system() == "Windows":
            os.system("shutdown /s /t 1")
        elif platform.system() == "Linux":
            os.system("systemctl poweroff")
        return "Shutting down computer now..."
    except Exception as e:
        return f"Failed to shutdown: {str(e)}"



def simplify_word_meaning(word):
    """Get simple dictionary definition using DictionaryAPI"""
    try:
        response = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
        data = response.json()
        
        if isinstance(data, dict) and data.get("title") == "No Definitions Found":
            return f"Couldn't find a definition for '{word}'"
        
        # Extract the first entry
        entry = data[0]
        word = entry["word"]
        meanings = entry["meanings"]
        
        simplified = [f"📖 {word.capitalize()} means:"]
        
        # Limit to 3 meanings max
        for meaning in meanings[:3]:
            part_of_speech = meaning["partOfSpeech"]
            definitions = meaning["definitions"]
            
            simplified.append(f"• As a {part_of_speech}:")
            # Take first 2 definitions max
            for definition in definitions[:2]:
                simplified.append(f"  - {definition['definition']}")
                if "example" in definition:
                    simplified.append(f"    Example: '{definition['example']}'")
        
        return "\n".join(simplified)
    
    except Exception as e:
        return f"Sorry, I couldn't look up '{word}'. Try another word."

def explain_word(command, conversation_area=None):
    """Handle word explanation requests"""
    # Extract the word to look up
    triggers = [
        "what is the meaning of",
        "define",
        "what does mean",
        "explain the word"
    ]
    
    word = command.lower()
    for trigger in triggers:
        word = word.replace(trigger, "")
    word = word.strip()
    
    if not word:
        return "Please specify a word you'd like me to explain."
    
    explanation = simplify_word_meaning(word)
    
    # Update GUI if available
    if conversation_area and conversation_area.winfo_exists():
        conversation_area.insert(tk.END, f"USER: {command}\n")
        conversation_area.insert(tk.END, f"BOT: {explanation}\n\n")
        conversation_area.see(tk.END)
    
    return explanation


def search_wikipedia(query, conversation_area=None, display_only=False):
    """Search Wikipedia and return a summary"""
    try:
        wikipedia.set_lang("en")
        summary = wikipedia.summary(query, sentences=3)
        response = f"📚 Wikipedia summary for '{query}':\n\n{summary}"
        
        if not display_only and conversation_area and conversation_area.winfo_exists():
            conversation_area.insert(tk.END, f"BOT: {response}\n\n")
            conversation_area.see(tk.END)
        
        return response
    
    except wikipedia.exceptions.DisambiguationError:
        return "Multiple options found. Please be more specific."
    except wikipedia.exceptions.PageError:
        return "No Wikipedia page found. Try a different search."
    except Exception as e:
        return f"Search error: {str(e)}"

def get_holidays_by_month(month=None, year=2025):
    """Get global holidays for a specific month"""
    countries = ['US', 'GB', 'CA', 'AU', 'IN', 'JP', 'DE', 'FR', 'IT', 'BR', 'ZA', 'MX']
    holiday_dict = {}
    
    for country in countries:
        try:
            for date, name in holidays.CountryHoliday(country, years=year).items():
                if month is None or date.month == month:
                    if name not in holiday_dict:  # Avoid duplicates
                        holiday_dict[name] = date.strftime('%b %d')
        except:
            continue
    
    return holiday_dict

def show_holidays(command, conversation_area=None):
    """Handle all holiday-related commands"""
    month_map = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    # Determine if asking for specific month
    month_num = None
    for month_name, num in month_map.items():
        if month_name in command.lower():
            month_num = num
            month_display = month_name.capitalize()
            break
    
    holidays_data = get_holidays_by_month(month_num)
    
    if not holidays_data:
        response = "No holidays found for this period."
    else:
        if month_num:
            response = f"📅 Holidays in {month_display} 2025:\n\n"
        else:
            response = "🗓️ Upcoming Global Holidays:\n\n"
        
        for name, date in sorted(holidays_data.items(), key=lambda x: x[1]):
            response += f"• {date}: {name}\n"
    
    # Display in conversation area
    if conversation_area:
        conversation_area.insert(tk.END, "\n" + response + "\n")
        conversation_area.see(tk.END)
    
    return response


def get_world_time(location=None):
    """Get times for specific location or all major cities"""
    timezones = {
        # Americas
        'New York': 'America/New_York',
        'Los Angeles': 'America/Los_Angeles',
        'Toronto': 'America/Toronto',
        'Chicago': 'America/Chicago',
        # Europe
        'London': 'Europe/London',
        'Paris': 'Europe/Paris',
        'Berlin': 'Europe/Berlin',
        'Rome': 'Europe/Rome',
        # Asia
        'Tokyo': 'Asia/Tokyo',
        'Delhi': 'Asia/Kolkata',
        'Beijing': 'Asia/Shanghai',
        'Dubai': 'Asia/Dubai',
        # Australia
        'Sydney': 'Australia/Sydney',
        'Melbourne': 'Australia/Melbourne',
        # Add more as needed
    }
    
    # Handle country/region requests
    region_map = {
        'usa': ['New York', 'Los Angeles', 'Chicago'],
        'canada': ['Toronto'],
        'uk': ['London'],
        'europe': ['London', 'Paris', 'Berlin', 'Rome'],
        'asia': ['Tokyo', 'Delhi', 'Beijing', 'Dubai'],
        'australia': ['Sydney', 'Melbourne']
    }
    
    current_time = datetime.now()
    results = {}
    
    # Check if asking for specific region
    if location:
        location = location.lower()
        if location in region_map:
            cities = region_map[location]
            for city in cities:
                tz = timezones[city]
                city_time = current_time.astimezone(pytz.timezone(tz))
                results[city] = city_time.strftime('%I:%M %p (%Z)')
        elif location.title() in timezones:
            city = location.title()
            tz = timezones[city]
            city_time = current_time.astimezone(pytz.timezone(tz))
            results[city] = city_time.strftime('%I:%M %p (%Z)')
    
    # Default to all major cities if no specific location
    if not results and not location:
        for city, tz in timezones.items():
            city_time = current_time.astimezone(pytz.timezone(tz))
            results[city] = city_time.strftime('%I:%M %p (%Z)')
    
    return results

def show_world_time(command, conversation_area=None):
    """Handle all time-related commands"""
    try:
        # Extract location from command
        location = None
        time_keywords = ['time in', 'time at', 'time for', 'what time is it in']
        
        for keyword in time_keywords:
            if keyword in command.lower():
                location = command.lower().split(keyword)[-1].strip()
                break
        
        times = get_world_time(location)
        
        if not times:
            response = f"I couldn't find time information for {location}"
        else:
            if location:
                response = f"⏰ Current time in {location.title()}:\n\n"
            else:
                response = "⏰ Current World Times:\n\n"
            
            for city, time in times.items():
                response += f"• {city}: {time}\n"
        
        # Safely update conversation area if it exists
        if conversation_area and conversation_area.winfo_exists():
            conversation_area.insert(tk.END, f"BOT: {response}\n\n")
            conversation_area.see(tk.END)
        
        return response
    
    except Exception as e:
        print(f"Error in show_world_time: {e}")
        return "Sorry, I couldn't get the time information."

def log_out():
    global current_user, current_user_email, assistant_stop_event
    
    if 'assistant_stop_event' in globals() and assistant_stop_event:
        assistant_stop_event.set()
    
    current_user = None
    current_user_email = None
    clear_window()
    setup_main_screen()

if __name__ == "__main__":
    try:
        db_manager = DatabaseManager('user.db')
        if not initialize_database():
            messagebox.showerror("Error", "Could not initialize database")
            sys.exit(1)
            
        print("Database initialized successfully")
        
        # Create main window
        window = tk.Tk()
        configure_window()
        def delayed_start():
            setup_main_screen()
            window.attributes('-topmost', 1)  # Bring to front
            window.attributes('-topmost', 0)  # Allow other windows to top
            
        window.after(500, delayed_start)  # 500ms delay
        
        def on_closing():
            try:
                if 'assistant_stop_event' in globals() and assistant_stop_event:
                    assistant_stop_event.set()
                if 'db_manager' in globals():
                    db_manager.close()
                if 'engine' in globals():
                    engine.stop()
            except Exception as e:
                print(f"Close error: {e}")
            finally:
                window.destroy()
        
        def excepthook(type, value, traceback):
            print(f"Unhandled exception: {value}")
            try:
                if 'db_manager' in globals():
                    db_manager.close()
            except:
                pass
            sys.__excepthook__(type, value, traceback)
        
        sys.excepthook = excepthook
        
        window.mainloop()
        
    except Exception as e:
        print(f"Initialization failed: {e}")
        if 'db_manager' in locals():
            db_manager.close()
        sys.exit(1)