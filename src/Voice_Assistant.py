# === Built-in Imports ===
from contextlib import contextmanager
from datetime import datetime
from tkinter import messagebox
from tkinter.ttk import Combobox
import ctypes
from datetime import datetime
import os
import platform
import re
import sqlite3
import subprocess 
import sys
import threading
import time
import tkinter as tk
import webbrowser

# === Third-party Imports ===
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import holidays
import pyttsx3
import pytz
import requests
import wikipedia


# Set ALSA environment variables to suppress warnings (LINUX)
os.environ['PYTHONWARNINGS'] = 'ignore'
os.environ['ALSA_DEBUG'] = '0'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['PULSE_SERVER'] = 'tcp:localhost'
os.environ['ALSA_CARD'] = '0'

# Create a more robust stderr suppressor
@contextmanager

# Function: suppress_stderr(), [ALSA errors]
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


# === Classes ===

# === Class Definition: NullDevice: ===
class NullDevice:
    def write(self, s):
        pass
    def flush(self):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# === Class Definition: DatabaseManager: ===
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


# === Class Definition: DarkButton ===
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


# === Class Definition: DarkEntry ===
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


# === Class Definition: DarkLabel ===
class DarkLabel(tk.Label):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(
            bg=DARK_THEME['bg'],
            fg=DARK_THEME['fg'],
            padx=5,
            pady=5
        )


# === Class Definition: DarkText ===
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


# === Class Definition: DarkScrollbar ===
class DarkScrollbar(tk.Scrollbar):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(
            bg=DARK_THEME['bg'],
            activebackground=DARK_THEME['highlight'],
            troughcolor=DARK_THEME['bg'],
            relief=tk.FLAT
        )

# === Global Variables ===
current_user = None
window = None
current_state = "main"
current_user_email = None
assistant_stop_event = threading.Event()
ph = PasswordHasher()
engine = pyttsx3.init()
voices = engine.getProperty('voices')
current_rate = engine.getProperty('rate')
db_manager = DatabaseManager('user.db')
DARK_THEME = {
    'bg': '#121212',  # Dark background
    'fg': '#e0e0e0',  # Light text
    'accent': '#bb86fc',  # Purple accent
    'secondary': '#03dac6',  # Teal secondary (changed to turquoise)
    'highlight': '#3700b3',  # Dark purple highlight
    'entry_bg': '#1e1e1e',  # Dark entry fields
    'entry_fg': '#ffffff',  # White text in entries
    'button_bg': '#1f1f1f',  # Button background
    'button_active': '#3700b3',  # Button when pressed
    'text_bg': '#1e1e1e',  # Text widget background
    'text_fg': '#ffffff',  # Text widget foreground
    'scrollbar': '#424242',  # Scrollbar color
    'user_text': '#40E0D0',  # Turquoise for user messages
    'bot_text': '#E0E0E0'    # Light gray for bot messages
}

# === GUI Functions ===

    # Function: configure_window()
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
    
    # Handle Linux scaling
    if platform.system() == "Linux":
        try:
            window.tk.call("tk", "scaling", 2.0)
        except tk.TclError:
            pass
    
    # Try to maximize (works on Windows/macOS)
    try:
        window.state('zoomed')
    except tk.TclError:
        pass
    
    # Ensure window decorations remain visible
    window.attributes('-fullscreen', False)


    # Function: setup_main_screen() (Main screen)
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
             font=("Arial", 30, "bold")
             ).pack(pady=(100, 40))

    # Button frame with CENTERING
    button_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
    button_frame.pack(expand=True, pady=20)  # Added expand and pady

    # Button code
    DarkButton(button_frame, 
              text="🚀 Continue Without Account", 
              command=continue_without_account,
              width=28  # Slightly increased from 25
              ).pack(pady=10, fill=tk.X)

    DarkButton(button_frame, 
              text="🔑 Sign In", 
              command=sign_in,
              width=28  # Slightly increased
              ).pack(pady=10, fill=tk.X)

    DarkButton(button_frame, 
              text="📝 Sign Up", 
              command=sign_up,
              width=28  # Slightly increased
              ).pack(pady=10, fill=tk.X)

    DarkButton(button_frame, 
              text="ℹ️ About Me", 
              command=about_me,
              width=28  # Slightly increased
              ).pack(pady=10, fill=tk.X)

    # Footer 
    footer_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
    footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)

    DarkLabel(footer_frame, 
             text="© 2025 Voice Assistant | Version 1.0",
             font=("Arial", 8)
             ).pack()


    # Function: continue_without_account() (Guest mode)
def continue_without_account():
    try:
        clear_window()
        configure_window()

        # Main frame
        main_frame = tk.Frame(window, bg=DARK_THEME['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Conversation area with scrollbar
        conv_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
        conv_frame.pack(fill=tk.BOTH, expand=True)

        conversation_area = tk.Text(
            conv_frame,
            bg=DARK_THEME['text_bg'],
            fg=DARK_THEME['text_fg'],
            insertbackground=DARK_THEME['fg'],
            wrap=tk.WORD,
            font=('Arial', 10)
        )
        scrollbar = tk.Scrollbar(conv_frame, command=conversation_area.yview)
        conversation_area.config(yscrollcommand=scrollbar.set)
        
        # Configure tags for coloring
        conversation_area.tag_config('user', foreground=DARK_THEME['user_text'])  # Turquoise
        conversation_area.tag_config('bot', foreground=DARK_THEME['bot_text'])    # Light gray
        conversation_area.tag_config('system', foreground=DARK_THEME['accent'])   # Purple accent
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        conversation_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Welcome message
        conversation_area.insert(tk.END, "Voice Assistant - Guest Mode\n\n", 'system')
        
        # Initialize speech engine safely
        try:
            wishMe()
            window.after(1500, lambda: speak("Voice Assistant initialized"))
        except Exception as e:
            print(f"Speech initialization error: {e}")
            conversation_area.insert(tk.END, "Speech functions unavailable\n", 'system')

        # Start listening thread safely
        global assistant_stop_event
        try:
            assistant_stop_event = listen_and_respond(conversation_area)
        except Exception as e:
            print(f"Listener error: {e}")
            conversation_area.insert(tk.END, "Could not start voice listener\n", 'system')

        # Control buttons
        button_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
        button_frame.pack(fill=tk.X, pady=10)

        # Left-aligned Main Menu
        DarkButton(button_frame, 
                text="Main Menu",
                command=setup_main_screen
                ).pack(side=tk.LEFT, padx=5)

        # Centered Sign Up/Sign In container
        center_buttons = tk.Frame(button_frame, bg=DARK_THEME['bg'])
        center_buttons.pack(side=tk.LEFT, expand=True)

        DarkButton(center_buttons, 
                text="Sign Up", 
                command=sign_up
                ).pack(side=tk.LEFT, padx=20)

        DarkButton(center_buttons, 
                text="Sign In", 
                command=sign_in
                ).pack(side=tk.LEFT, padx=20)

    except Exception as e:
        print(f"Fatal error in guest mode: {e}")
        messagebox.showerror("Error", "Failed to initialize guest mode")
        setup_main_screen()


    # Function: sign_up() (Sign up form)
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

        # Create a frame for better layout control
        signup_frame = tk.Frame(window, bg=DARK_THEME['bg'])
        signup_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Title
        DarkLabel(signup_frame, 
                 text="CREATE ACCOUNT", 
                 font=("Arial", 20, "bold")
                 ).grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # Form fields
        fields = [
            ("Name:", "name_entry"),
            ("Last Name:", "last_entry"),
            ("Email:", "email_entry"),
            ("Password:", "password_entry"),
            ("Confirm Password:", "confirm_entry")
        ]

        entries = {}
        for i, (label_text, entry_name) in enumerate(fields, start=1):
            DarkLabel(signup_frame, text=label_text).grid(row=i, column=0, sticky=tk.E, pady=5)
            
            # Create entry frame to hold both entry and toggle button
            entry_frame = tk.Frame(signup_frame, bg=DARK_THEME['bg'])
            entry_frame.grid(row=i, column=1, pady=5, sticky='ew')
            
            entry = DarkEntry(entry_frame, width=25)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            entries[entry_name] = entry
            
            if entry_name in ["password_entry", "confirm_entry"]:
                entry.config(show="•")  # Set to show bullets by default
                toggle_btn = create_password_toggle(entry_frame, entry)
                toggle_btn.pack(side=tk.LEFT)

        # Store references to entry widgets
        global name_entry, last_entry, email_entry, password_entry, confirm_entry
        name_entry = entries["name_entry"]
        last_entry = entries["last_entry"]
        email_entry = entries["email_entry"]
        password_entry = entries["password_entry"]
        confirm_entry = entries["confirm_entry"]

        # Buttons
        button_frame = tk.Frame(signup_frame, bg=DARK_THEME['bg'])
        button_frame.grid(row=len(fields)+1, column=0, columnspan=3, pady=20)

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


    # Function: sign_in() (Sign in form)
def sign_in():
    clear_window()
    configure_window()

    # Create a frame for better layout control
    login_frame = tk.Frame(window, bg=DARK_THEME['bg'])
    login_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    # Title
    DarkLabel(login_frame, 
             text="Voice Assistant Login", 
             font=("Arial", 20, "bold")).grid(row=0, column=0, columnspan=2, pady=20)

    # Email
    DarkLabel(login_frame, text="Email:").grid(row=1, column=0, sticky=tk.E, pady=5)
    email_entry = DarkEntry(login_frame, width=30)
    email_entry.grid(row=1, column=1, pady=5, padx=10)

    # Password
    DarkLabel(login_frame, text="Password:").grid(row=2, column=0, sticky=tk.E, pady=5)
    
    # Password entry with toggle
    password_frame = tk.Frame(login_frame, bg=DARK_THEME['bg'])
    password_frame.grid(row=2, column=1, pady=5, sticky='ew')
    
    password_entry = DarkEntry(password_frame, width=25, show="•")
    password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    toggle_btn = create_password_toggle(password_frame, password_entry)
    toggle_btn.pack(side=tk.LEFT)

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


    # Function: login()
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
       
        print(f"\n=== LOGIN SUCCESSFUL ===")      # Debug prints
        print(f"User: {email}")
        logged_in()
    except VerifyMismatchError:
        messagebox.showerror("Error", "Invalid password")


    # Function: logged_in() (Logged in user page)
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
    
    # Configure tags for coloring
    conversation_area.tag_config('user', foreground=DARK_THEME['user_text'])  # Turquoise
    conversation_area.tag_config('bot', foreground=DARK_THEME['bot_text'])    # Light gray
    conversation_area.tag_config('system', foreground=DARK_THEME['accent'])  # Purple accent
    
    conversation_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    scrollbar = DarkScrollbar(conv_frame, command=conversation_area.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    conversation_area.config(yscrollcommand=scrollbar.set)
    
    # Welcome message
    welcome_msg = f"Voice Assistant initialized.\n\n"
    conversation_area.insert(tk.END, welcome_msg, 'system')
    
    # Control buttons
    button_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
    button_frame.pack(fill=tk.X, pady=10, side=tk.BOTTOM)

    # Left-aligned Log Out
    DarkButton(button_frame, 
            text="LOG OUT", 
            command=log_out
            ).pack(side=tk.LEFT, padx=5)

    # Center-aligned History and Settings
    center_buttons = tk.Frame(button_frame, bg=DARK_THEME['bg'])
    center_buttons.pack(side=tk.LEFT, expand=True)

    DarkButton(center_buttons, 
            text="History", 
            command=show_history
            ).pack(side=tk.LEFT, padx=20)

    DarkButton(center_buttons, 
            text="Settings", 
            command=show_settings
            ).pack(side=tk.LEFT, padx=20)

    # Right-aligned About Me
    DarkButton(button_frame, 
            text="About Me", 
            command=about_me
            ).pack(side=tk.RIGHT, padx=5)
    
    wishMe()
    window.after(1500, lambda: speak("Voice Assistant initialized."))
    
    assistant_stop_event = listen_and_respond(conversation_area)


    # Function: show_settings() (Settings for the logged in user)
def show_settings():
    clear_window()
    configure_window()

    def ask_for_password(stored_hashed_password):
        password_window = tk.Toplevel(window)
        password_window.title("Verify Password")
        password_window.configure(bg=DARK_THEME['bg'])
        password_window.resizable(False, False)
        
        DarkLabel(password_window, text="Enter your password:").pack(pady=10)
        
        # Password entry with toggle
        password_frame = tk.Frame(password_window, bg=DARK_THEME['bg'])
        password_frame.pack(pady=5)
        
        password_entry = DarkEntry(password_frame, show='•', width=28)
        password_entry.pack(side=tk.LEFT)
        
        toggle_btn = create_password_toggle(password_frame, password_entry)
        toggle_btn.pack(side=tk.LEFT, padx=(5,0))

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

    # Centered Title
    DarkLabel(main_frame, 
             text="SETTINGS", 
             font=("Arial", 16, "bold")
             ).pack(pady=(0, 20), anchor='center')

    user_info = get_current_user_info()
    if user_info:
        current_name, last_name, stored_hashed_password = user_info
        full_name = f"{current_name} {last_name}" if last_name else current_name

        # User Profile Section - Centered
        profile_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
        profile_frame.pack(fill=tk.X, pady=10)

        DarkLabel(profile_frame, 
                 text="👤 User Profile", 
                 font=("Arial", 12, "bold")
                 ).pack(anchor='center', pady=5)

        # Centered Info Grid
        info_frame = tk.Frame(profile_frame, bg=DARK_THEME['bg'])
        info_frame.pack(anchor='center', pady=10)

        DarkLabel(info_frame, text="Name:").grid(row=0, column=0, padx=5, sticky='e')
        DarkLabel(info_frame, text=full_name).grid(row=0, column=1, padx=5, sticky='w')

        DarkLabel(info_frame, text="Email:").grid(row=1, column=0, padx=5, pady=5, sticky='e')
        DarkLabel(info_frame, text=current_user_email).grid(row=1, column=1, padx=5, sticky='w')

        # Centered Change Name Button
        DarkButton(profile_frame, 
                  text="✏️ Change Name", 
                  command=lambda: ask_for_password(stored_hashed_password)
                  ).pack(pady=10, anchor='center')

        # Spacer between sections
        tk.Frame(main_frame, height=20, bg=DARK_THEME['bg']).pack()

        # Voice Settings Section - Centered
        voice_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
        voice_frame.pack(fill=tk.X, pady=10)

        DarkLabel(voice_frame, 
                 text="🔊 Voice Settings", 
                 font=("Arial", 12, "bold")
                 ).pack(anchor='center', pady=5)

        # Centered Speed Controls
        speed_frame = tk.Frame(voice_frame, bg=DARK_THEME['bg'])
        speed_frame.pack(anchor='center', pady=10)

        DarkLabel(speed_frame, text="Voice Speed:").pack(side=tk.LEFT, padx=5)
        
        speed_combobox = Combobox(speed_frame, 
                                values=["Fast", "Normal", "Slow"], 
                                state="readonly")
        speed_combobox.pack(side=tk.LEFT, padx=5)
        
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
                  ).pack(side=tk.LEFT, padx=5)

    # Centered Back Button
    DarkButton(main_frame, 
              text="🔙 Back to Assistant", 
              command=logged_in
              ).pack(pady=100, anchor='center')


    # Function: show_history() (Conversation history for logged in users)
def show_history():
    # Clear window safely
    try:
        if window.winfo_exists():
            for widget in window.winfo_children():
                widget.destroy()
    except:
        pass
    
    # Create basic UI first
    main_frame = tk.Frame(window, bg=DARK_THEME['bg'])
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    loading_label = DarkLabel(main_frame, 
                            text="Loading History...", 
                            font=("Arial", 14))
    loading_label.pack(pady=50)
    
    # Force UI update before any database ops
    window.update_idletasks()
    
    def safe_history_load():
        try:
            # 1. Ensure database connection
            if not db_manager.ensure_connection():
                raise sqlite3.Error("Connection failed")
            
            # 2. Execute query with retries
            for attempt in range(3):
                try:
                    cursor = db_manager.execute(
                        "SELECT timestamp, speaker, message FROM conversations WHERE user_email = ? ORDER BY timestamp DESC",
                        (current_user_email,)
                    )
                    conversations = cursor.fetchall()
                    break
                except sqlite3.ProgrammingError:
                    if attempt == 2: raise
                    time.sleep(0.1)
            
            # 3. Build UI in main thread
            window.after(0, lambda: build_history_ui(conversations))
            
        except Exception as e:
            window.after(0, lambda: show_error(str(e)))
    
    def build_history_ui(conversations):
        # Clear loading
        for widget in main_frame.winfo_children():
            widget.destroy()
        
        # Create main container
        container = tk.Frame(main_frame, bg=DARK_THEME['bg'])
        container.pack(fill=tk.BOTH, expand=True)
        
        # History display area
        text_area = DarkText(container)
        scrollbar = DarkScrollbar(container, command=text_area.yview)
        text_area.config(yscrollcommand=scrollbar.set)
        
        text_area.tag_config("timestamp", foreground="#aaaaaa")
        text_area.tag_config("user", foreground=DARK_THEME['user_text'])
        text_area.tag_config("bot", foreground=DARK_THEME['accent'])
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        if conversations:
            text_area.insert(tk.END, "Conversation History:\n\n", "bot")
            for ts, speaker, msg in conversations:
                text_area.insert(tk.END, f"{ts} - ", "timestamp")
                text_area.insert(tk.END, f"{speaker}: ", "user" if speaker == "USER" else "bot")
                text_area.insert(tk.END, f"{msg}\n\n")
        else:
            text_area.insert(tk.END, "No history found", "bot")
        
        text_area.config(state=tk.DISABLED)
        
        # Bottom frame for back button
        bottom_frame = tk.Frame(main_frame, bg=DARK_THEME['bg'])
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        # Centered back button
        DarkButton(bottom_frame, 
                 text="Back", 
                 command=logged_in,
                 width=20).pack(anchor='center')
    
    def show_error(msg):
        for widget in main_frame.winfo_children():
            widget.destroy()
        
        DarkLabel(main_frame, text=f"Error: {msg}", fg="red").pack(pady=10)
        DarkButton(main_frame, text="Retry", command=show_history).pack(pady=5)
        DarkButton(main_frame, text="Back", command=logged_in).pack(pady=5)
    
    # Start database thread
    threading.Thread(target=safe_history_load, daemon=True).start()


    # Function: about_me() (About me page)
def about_me():
    clear_window()
    configure_window()
    
    # Main frame with scrollbar
    main_frame = tk.Frame(window, bg=DARK_THEME['bg'])
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Create canvas and scrollbar
    canvas = tk.Canvas(main_frame, bg=DARK_THEME['bg'], highlightthickness=0)
    scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg=DARK_THEME['bg'])
    
    # Configure canvas scrolling
    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set, bg=DARK_THEME['bg'])
    
    # Pack canvas and scrollbar
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # Style constants
    TITLE_COLOR = "#40E0D0"  # Turquoise
    HEADER_FONT = ("Arial", 22, "bold")
    SECTION_FONT = ("Arial", 16, "bold")
    BODY_FONT = ("Arial", 12)
    LINK_FONT = ("Arial", 12, "underline")
    ICON_FONT = ("Arial", 16)
    PADX = 30
    SECTION_SPACING = 20

    # Main Title Frame
    title_frame = tk.Frame(scrollable_frame, bg=DARK_THEME['bg'])
    title_frame.pack(fill='x', pady=(20, SECTION_SPACING))
    DarkLabel(title_frame, 
            text="About This Voice Assistant Project",
            font=HEADER_FONT,
            fg=TITLE_COLOR).pack(expand=True)

    # Content Container
    content_frame = tk.Frame(scrollable_frame, bg=DARK_THEME['bg'])
    content_frame.pack(fill='x', padx=PADX)

    # Project Description
    description_text = """An advanced voice assistant platform featuring:
    
• Natural Language Processing for voice commands
• Secure user authentication system
• Conversation history tracking
• Real-time information retrieval (weather, time, conversions)
• System utilities integration

Key Features:
✓ Voice recognition
✓ Text-to-speech responses
✓ Cross-platform compatibility
✓ Database-backed user accounts
✓ Multi-threaded operation for smooth performance"""
    
    DarkLabel(content_frame, 
            text=description_text,
            font=BODY_FONT,
            justify=tk.LEFT).pack(fill='x', pady=10)

    # Separator
    tk.Frame(content_frame, height=2, bg=DARK_THEME['fg']).pack(fill='x', pady=SECTION_SPACING)

    # Developer Section
    dev_frame = tk.Frame(content_frame, bg=DARK_THEME['bg'])
    dev_frame.pack(fill='x', pady=10)
    
    DarkLabel(dev_frame, 
            text="Developer Information",
            font=SECTION_FONT,
            fg=TITLE_COLOR).pack(anchor='w')
    
    creator_info = """Developed by: Atal Abdullah Waziri
Position: Co-founder & Lead Developer at Stellar Organization

Technical Aspects:
- Python Development
- SQL Database Design
- Voice Interface Engineering
- GUI Design
"""
    
    DarkLabel(dev_frame, 
            text=creator_info,
            font=BODY_FONT,
            justify=tk.LEFT).pack(fill='x', pady=10)

    # Contact Information
    contact_frame = tk.Frame(content_frame, bg=DARK_THEME['bg'])
    contact_frame.pack(fill='x', pady=10)
    
    DarkLabel(contact_frame, 
            text="📨 Contact Information",
            font=SECTION_FONT,
            fg=TITLE_COLOR).pack(anchor='w')

    def create_contact_row(parent, icon, label, url):
        row_frame = tk.Frame(parent, bg=DARK_THEME['bg'])
        row_frame.pack(fill='x', pady=3)
        DarkLabel(row_frame, text=icon, font=ICON_FONT).pack(side=tk.LEFT, padx=(0, 10))
        DarkLabel(row_frame, text=label, font=BODY_FONT).pack(side=tk.LEFT)
        link_label = DarkLabel(row_frame, text=url, font=LINK_FONT, cursor="hand2")
        link_label.pack(side=tk.LEFT, padx=(10, 0))
        link_label.bind("<Button-1>", lambda e: webbrowser.open(url))
        return row_frame

    # Personal Contacts
    personal_contacts = [
        ("📧", "Email:", "mailto:atalwaziri9@gmail.com"),
        ("📱", "Instagram:", "https://www.instagram.com/atal_waziri/")
    ]

    contact_grid = tk.Frame(contact_frame, bg=DARK_THEME['bg'])
    contact_grid.pack(fill='x', pady=5)
    for contact in personal_contacts:
        create_contact_row(contact_grid, *contact)

    # Organization Section
    org_frame = tk.Frame(content_frame, bg=DARK_THEME['bg'])
    org_frame.pack(fill='x', pady=10)
    
    DarkLabel(org_frame, 
            text="🌟 Stellar Organization",
            font=SECTION_FONT,
            fg=TITLE_COLOR).pack(anchor='w')

    org_info = """A technology training and development organization focused on:
- Teaching programming
- Math and English language tutoring
- Book recommendations
- Exam tips"""
    
    DarkLabel(org_frame, 
            text=org_info,
            font=BODY_FONT,
            justify=tk.LEFT).pack(fill='x', pady=10)

    # Organization Links
    org_links = [
        ("🌐", "Website:", "https://stellarorganization.mystrikingly.com/"),
        ("▶️", "YouTube:", "https://youtube.com/@Stellar_1Tech"),
        ("💬", "WhatsApp:", "https://chat.whatsapp.com/H47fnJwZfeVG8ccISZbgqp"),
        ("📱", "Instagram:", "https://www.instagram.com/stellar_1training"),
        ("✍️", "Blog:", "https://atalcodeblog.wordpress.com")
    ]

    org_link_frame = tk.Frame(org_frame, bg=DARK_THEME['bg'])
    org_link_frame.pack(fill='x', pady=5)
    for link in org_links:
        create_contact_row(org_link_frame, *link)

    # Centered Back Button
    bottom_frame = tk.Frame(window, bg=DARK_THEME['bg'])
    bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)

    DarkButton(
        bottom_frame,
        text="◀ Back to Main Menu",
        command=back_to_previous,
        width=25,
        font=("Arial", 14)
    ).pack(anchor='center')


    # Function: back_to_previous() (Helper function)
def back_to_previous():
    if current_state == "logged_in":
        logged_in()
    else:
        setup_main_screen()


# === Database Functions ===

    # Function: initialize_database()
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
            time.sleep(1)


    # Function: get_user_from_database()
def get_user_from_database(email):
    cursor = db_manager.execute("SELECT * FROM users WHERE email = ?", (email,))
    return cursor.fetchone()


    # Function: get_current_user_info()
def get_current_user_info():
    print(f"Looking up user with email: {current_user_email}")
    result = db_manager.execute("SELECT name, last_name, password FROM users WHERE email = ?", (current_user_email,))
    user_info = result.fetchone()
    print(f"Found user info: {user_info}")
    return user_info


    # Function: update_user_info()
def update_user_info(new_name, new_last_name):
    db_manager.execute("UPDATE users SET name = ?, last_name = ? WHERE email = ?", 
                      (new_name, new_last_name, current_user_email))
    db_manager.commit()


    # Function: log_conversation()
def log_conversation(email, speaker, message):
    try:
        db_manager.execute(
            "INSERT INTO conversations (user_email, speaker, message) VALUES (?, ?, ?)",
            (email, speaker, message.strip())
        )
        db_manager.commit()  
    except Exception as e:
        print(f"Failed to log conversation: {e}")



    # Function: speak()
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


    # Function: get_working_microphone()
def get_working_microphone():
    """Cross-platform microphone detection"""
    with suppress_stderr():
        recognizer = sr.Recognizer()
        try:
            mic_list = sr.Microphone.list_microphone_names()
            
            # Windows/Linux/macOS compatible device detection
            preferred_keywords = [
                'microphone',
                'input',
                'default',
                'built-in',
                'webcam',  # For built-in webcam mics
                'speakers',  # Sometimes mics are listed with speakers
                'audio',
                'recording'
            ]
            
            for index, name in enumerate(mic_list):
                if any(kw in name.lower() for kw in preferred_keywords):
                    with sr.Microphone(device_index=index) as source:
                        recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        return sr.Microphone(device_index=index)
            
            # Fallback to default microphone
            return sr.Microphone()
            
        except Exception as e:
            print(f"Microphone detection error: {e}")
            return sr.Microphone()


    # Function: listen_and_respond()
def listen_and_respond(conversation_area):
    recognizer = sr.Recognizer()
    microphone = get_working_microphone()
    
    if microphone is None:
        messagebox.showerror("Microphone Error", "No working microphone found")
        return None

    stop_event = threading.Event()
    processing_lock = threading.Lock()

    def update_gui(text, speaker):
        if conversation_area.winfo_exists():
            tag = 'user' if speaker == "USER" else 'bot'
            conversation_area.insert(tk.END, f"{speaker}: {text}\n", tag)
            conversation_area.see(tk.END)
            window.update()

    def show_listening():
        if conversation_area.winfo_exists():
            conversation_area.insert(tk.END, "Listening...\n", 'system')
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
            window.after(0, lambda: update_gui(command, "USER"))
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
                return response
            elif "open" in command_lower:
                app = command_lower.replace("open", "").strip()
                response = f"Opening {app}"
                try:
                    success = open_application(app)
                    if not success:
                        response = f"Couldn't find {app} on this system"
                except Exception as e:
                    response = f"Error opening {app}: {str(e)}"
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
                query = re.sub(
                    r'(search wikipedia for|wikipedia|what is|who is|tell me about)\s*', 
                    '', 
                    command_lower
                ).strip()
                
                if query:
                    response = search_wikipedia(query, conversation_area, display_only=True)
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
                window.after(0, lambda: update_gui(response, "BOT"))
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
            
            if response:
                window.after(0, lambda: update_gui(response, "BOT"))
                speak(response)

    assistant_thread = threading.Thread(target=assistant_loop)
    assistant_thread.daemon = True
    assistant_thread.start()
    
    return stop_event


    # Function: wishMe() (Greetings)
def wishMe():
    hour = datetime.now().hour 
    if hour >= 0 and hour < 12:
        speak("Good Morning Sir !")

    elif hour >= 12 and hour < 18:
        speak("Good Afternoon Sir !")

    else:
        speak("Good Evening Sir !")

# === Capability Functions ===

    # Function: convert_units()
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


    # Function: process_conversion_command()
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


    # Function: get_news_summaries()
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


    # Function: get_weather()
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


    # Function: show_weather()
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


    # Function: simplify_word_meaning()
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


    # Function: explain_word()
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


    # Function: search_wikipedia()
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


    # Function: get_holidays_by_month()
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


    # Function: show_holidays()
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


    # Function: get_world_time()
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



    # Function: show_world_time()
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

# === Utility Functions ===

    # Function: open_application()
def open_application(app_name):
    """Cross-platform application opener with fallbacks"""
    try:
        system_os = platform.system()
        app_name = app_name.lower()
        
        # Map applications to OS-specific commands
        app_commands = {
            'terminal': {
                'Windows': ['cmd.exe'],
                'Linux': ['gnome-terminal', 'x-terminal-emulator', 'konsole', 'xfce4-terminal'],
                'Darwin': ['open', '-a', 'Terminal']
            },
            'file manager': {
                'Windows': ['explorer.exe'],
                'Linux': ['nautilus', 'dolphin', 'thunar'],
                'Darwin': ['open', '-a', 'Finder']
            },
            'browser': {
                'Windows': ['start', 'chrome'],
                'Linux': ['google-chrome', 'firefox'],
                'Darwin': ['open', '-a', 'Google Chrome']
            },
            'calculator': {
                'Windows': ['calc.exe'],
                'Linux': ['gnome-calculator', 'kcalc'],
                'Darwin': ['open', '-a', 'Calculator']
            },
            'text editor': {
                'Windows': ['notepad.exe'],
                'Linux': ['gedit', 'kate', 'mousepad'],
                'Darwin': ['open', '-a', 'TextEdit']
            },
            'spotify': {
                'Windows': ['spotify'],
                'Linux': ['spotify'],
                'Darwin': ['open', '-a', 'Spotify']
            }
        }

        # Determine application type
        app_type = None
        if 'terminal' in app_name:
            app_type = 'terminal'
        elif any(x in app_name for x in ['file', 'explorer']):
            app_type = 'file manager'
        elif any(x in app_name for x in ['chrome', 'browser', 'firefox']):
            app_type = 'browser'
        elif 'calculator' in app_name:
            app_type = 'calculator'
        elif 'editor' in app_name:
            app_type = 'text editor'
        elif 'spotify' in app_name:
            app_type = 'spotify'

        if app_type and app_type in app_commands:
            commands = app_commands[app_type].get(system_os, [])
            for cmd in commands:
                try:
                    subprocess.Popen(cmd)
                    return True
                except FileNotFoundError:
                    continue

        # Fallback to generic open
        if system_os == "Windows":
            os.startfile(app_name)
        elif system_os == "Darwin":
            subprocess.run(["open", app_name])
        else:
            subprocess.run(["xdg-open", app_name])
            
        return True
        
    except Exception as e:
        print(f"Error opening application: {e}")
        return False


    # Function: lock_computer()
def lock_computer():
    """Cross-platform computer locking"""
    try:
        system_os = platform.system()
        if system_os == "Windows":
            if hasattr(ctypes, 'windll'):
                ctypes.windll.user32.LockWorkStation()
                return "Computer locked successfully"
            return "Locking not supported on this Windows configuration"
            
        elif system_os == "Linux":
            try:
                # Try generic Linux command first
                subprocess.run(["xdg-screensaver", "lock"], check=True)
                return "Computer locked successfully"
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to loginctl
                subprocess.run(["loginctl", "lock-session"], check=True)
                return "Computer locked successfully"
            
        elif system_os == "Darwin":
            subprocess.run(["pmset", "displaysleepnow"], check=True)
            return "Computer locked successfully"
            
        return "Locking not supported on this OS"
        
    except Exception as e:
        return f"Failed to lock computer: {str(e)}"


    # Function: shutdown_computer()
def shutdown_computer(confirm=True):
    """Cross-platform system shutdown"""
    if confirm:
        return "Please confirm you want to shutdown the computer"
        
    try:
        system_os = platform.system()
        if system_os == "Windows":
            subprocess.run(["shutdown", "/s", "/t", "1"])
        elif system_os == "Linux":
            if subprocess.run(["which", "systemctl"], capture_output=True).returncode == 0:
                subprocess.run(["systemctl", "poweroff"])
            else:
                subprocess.run(["shutdown", "-h", "now"])
        elif system_os == "Darwin":
            subprocess.run(["osascript", "-e", 'tell app "System Events" to shut down'])
        return "Shutting down computer now..."
        
    except Exception as e:
        return f"Failed to shutdown: {str(e)}"


    # Function: restart_computer()
def restart_computer(confirm=True):
    """Cross-platform system restart"""
    if confirm:
        return "Please confirm you want to restart the computer"
        
    try:
        system_os = platform.system()
        if system_os == "Windows":
            subprocess.run(["shutdown", "/r", "/t", "1"])
        elif system_os == "Linux":
            # Try different init systems
            if subprocess.run(["which", "systemctl"], capture_output=True).returncode == 0:
                subprocess.run(["systemctl", "reboot"])
            else:
                subprocess.run(["shutdown", "-r", "now"])
        elif system_os == "Darwin":
            subprocess.run(["osascript", "-e", 'tell app "System Events" to restart'])
        return "Restarting computer now..."
        
    except Exception as e:
        return f"Failed to restart: {str(e)}"

# === Other Functions ===

    # Function: clear_window()
def clear_window():
    global assistant_stop_event
    
    if 'assistant_stop_event' in globals() and assistant_stop_event:
        assistant_stop_event.set()
    
    for widget in window.winfo_children():
        widget.destroy()


    # Function: log_out()
def log_out():
    global current_user, current_user_email, assistant_stop_event
    
    if 'assistant_stop_event' in globals() and assistant_stop_event:
        assistant_stop_event.set()
    
    current_user = None
    current_user_email = None
    clear_window()
    setup_main_screen()


    # Function: create_password_toggle()
def create_password_toggle(parent, entry_widget):
    """Create a show/hide password toggle button with text fallback"""
    def toggle_password():
        if entry_widget.cget('show') == '':
            entry_widget.config(show='•')
            toggle_btn.config(text='Show')
        else:
            entry_widget.config(show='')
            toggle_btn.config(text='Hide')
    
    # Create button with text fallback
    toggle_btn = tk.Button(
        parent,
        text='Show',
        command=toggle_password,
        font=("Arial", 8),
        bg=DARK_THEME['entry_bg'],
        fg=DARK_THEME['fg'],
        activebackground=DARK_THEME['entry_bg'],
        activeforeground=DARK_THEME['fg'],
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=0,
        padx=2,
        pady=2
    )
    return toggle_btn

# === Main Guard ===
if platform.system() == "Linux":
    try:
        import distro
    except ImportError:
        pass

if __name__ == "__main__":
    try:
        db_manager = DatabaseManager('user.db')
        if not initialize_database():
            messagebox.showerror("Error", "Could not initialize database")
            sys.exit(1)
            
        print("Database initialized successfully")
        
        # Create main window
        window = tk.Tk()

        if platform.system() == "Linux":
            try:
                # Fix potential display issues
                os.environ['DISPLAY'] = ':0'
                os.environ['XAUTHORITY'] = '/home/$USER/.Xauthority'
            except:
                pass

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