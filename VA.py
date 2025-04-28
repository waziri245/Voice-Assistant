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

            log_conversation(current_user_email, "USER", command)
            
            response = ""
            command_lower = command.lower()
            
            if any(greeting in command_lower for greeting in ["hello", "hi", "hey"]):
                response = "Hello! How can I help you today?"
            elif "time" in command_lower:
                response = f"The current time is {datetime.now().strftime('%H:%M')}"
            elif "date" in command_lower:
                response = f"Today's date is {datetime.now().strftime('%B %d, %Y')}"
            elif "open" in command_lower:
                app = command_lower.replace("open", "").strip()
                response = f"Opening {app}"
                try:
                    if "chrome" in app or "browser" in app:
                        subprocess.Popen(["google-chrome"])
                    elif "terminal" in app:
                        subprocess.Popen(["gnome-terminal"])
                    elif "file" in app or "explorer" in app:
                        subprocess.Popen(["nautilus"])
                    else:
                        response = f"I'm not sure how to open {app}"
                except Exception as e:
                    response = f"Sorry, I couldn't open {app}. Error: {str(e)}"
            elif "search" in command_lower:
                query = command_lower.replace("search", "").strip()
                if query:
                    response = f"Searching the web for {query}"
                    try:
                        subprocess.Popen(["google-chrome", f"https://www.google.com/search?q={query}"])
                    except:
                        response = "I couldn't perform the search. Please try again."
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
    window.title("Voice Assistant")

    tk.Button(window, text="Continue without account", command=continue_without_account).pack()
    tk.Button(window, text="Sign In", command=sign_in).pack()
    tk.Button(window, text="Sign Up", command=sign_up).pack()
    tk.Button(window, text="About Me", command=about_me).pack()

def clear_window():
    global assistant_stop_event
    
    if 'assistant_stop_event' in globals() and assistant_stop_event:
        assistant_stop_event.set()
    
    for widget in window.winfo_children():
        widget.destroy()

def continue_without_account():
    clear_window()
    conversation_area = tk.Text(window, wrap=tk.WORD)
    conversation_area.pack(fill=tk.BOTH, expand=True)
    
    scrollbar = tk.Scrollbar(conversation_area)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    conversation_area.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=conversation_area.yview)
    
    wishMe()  # This calls speak() internally
    
    # Then after a delay, speak the welcome message
    window.after(1500, lambda: speak("Voice Assistant initialized."))
    welcome_msg = "Voice Assistant initialized.\n\n"
    conversation_area.insert(tk.END, welcome_msg)
    
    listen_and_respond(conversation_area)
    
    button_frame = tk.Frame(window)
    button_frame.pack(fill=tk.X)

    tk.Button(window, text="Sign Up", command=sign_up).pack(side=tk.RIGHT)
    tk.Button(window, text="Sign In", command=sign_in).pack(side=tk.RIGHT)
    tk.Button(window, text="Main Menu", command=setup_main_screen).pack()

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

    clear_window()
    tk.Label(window, text="Name:").pack()
    name_entry = tk.Entry(window)
    name_entry.pack()

    tk.Label(window, text="Last Name:").pack()
    last_entry = tk.Entry(window)
    last_entry.pack()

    tk.Label(window, text="Email:").pack()
    email_entry = tk.Entry(window)
    email_entry.pack()

    tk.Label(window, text="Password:").pack()
    password_entry = tk.Entry(window, show="*")
    password_entry.pack()

    tk.Label(window, text="Confirm Password:").pack()
    confirm_entry = tk.Entry(window, show="*")
    confirm_entry.pack()

    tk.Button(window, text="Create Account", command=create_account_if_valid).pack()
    tk.Button(window, text="Main Menu", command=setup_main_screen).pack()

def get_user_from_database(email):
    cursor = db_manager.execute("SELECT * FROM users WHERE email = ?", (email,))
    return cursor.fetchone()

def sign_in():
    clear_window()

    tk.Label(window, text="Email:").pack()
    email_entry = tk.Entry(window)
    email_entry.pack()

    tk.Label(window, text="Password:").pack()
    password_entry = tk.Entry(window, show="*")
    password_entry.pack()
    
    tk.Button(window, text="Login", command=lambda: login(email_entry.get(), password_entry.get())).pack()
    tk.Button(window, text="Sign Up", command=sign_up).pack()
    tk.Button(window, text="Main Menu", command=setup_main_screen).pack()

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
    global current_state, assistant_stop_event, current
    
    # Stop any existing assistant
    if assistant_stop_event:
        assistant_stop_event.set()
    
    # Create a new event for the new assistant
    assistant_stop_event = threading.Event()
    
    current_state = "logged_in"
    clear_window()
    
    user_name = f"{current_user[1]} {current_user[2]}"

    db_manager.execute("SELECT voice_speed FROM users WHERE email=?", (current_user_email,))
    speed_setting = db_manager.fetchone()
    if speed_setting:
        speed = speed_setting[0]
        engine.setProperty('rate', 200 if speed == "Fast" else 100 if speed == "Slow" else 150)
    
    conversation_area = tk.Text(window, wrap=tk.WORD)
    conversation_area.pack(fill=tk.BOTH, expand=True)
    
    scrollbar = tk.Scrollbar(conversation_area)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    conversation_area.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=conversation_area.yview)
    
    welcome_msg = f"Voice Assistant - Logged in as {user_name}\n\n"
    conversation_area.insert(tk.END, welcome_msg)
    
    wishMe()  # This calls speak() internally
    
    # Then after a delay, speak the welcome message
    window.after(1500, lambda: speak("Voice Assistant initialized."))
    
    
    if 'assistant_stop_event' in globals():
        assistant_stop_event.set()
    assistant_stop_event = listen_and_respond(conversation_area)
    
    button_frame = tk.Frame(window)
    button_frame.pack(fill=tk.X)

    tk.Button(window, text="LOG OUT", command=log_out).pack()
    tk.Button(window, text="History", command=show_history).pack()
    tk.Button(window, text="Settings", command=show_settings).pack()
    tk.Button(window, text="About Me", command=about_me).pack()

def show_settings():
    clear_window()
    
    user_info = get_current_user_info()
    if user_info:
        current_name, last_name, stored_hashed_password = user_info
        full_name = f"{current_name} {last_name}" if last_name else current_name

        # Display user info
        tk.Label(window, text="Current Name:").pack()
        name_label = tk.Label(window, text=full_name)
        name_label.pack()

        tk.Label(window, text="Email:").pack()
        email_label = tk.Label(window, text=current_user_email)
        email_label.pack()

        # Name change section
        def ask_for_password():
            password_window = tk.Toplevel(window)
            password_window.title("Verify Password")
            
            tk.Label(password_window, text="Enter your password:").pack()
            password_entry = tk.Entry(password_window, show='*')
            password_entry.pack()

            def verify_password():
                try:
                    if ph.verify(stored_hashed_password, password_entry.get()):
                        password_window.destroy()
                        change_name_window()
                    else:
                        messagebox.showerror("Error", "Incorrect password")
                except VerifyMismatchError:
                    messagebox.showerror("Error", "Incorrect password")

            tk.Button(password_window, text="Verify", command=verify_password).pack()

        def capitalize_name(name_str):
            """Capitalize first letter of each name part (including after hyphens)"""
            return ' '.join(
                word.capitalize() for part in name_str.split() 
                for word in part.split('-')
            ).replace('- ', '-')

        def change_name_window():
            change_window = tk.Toplevel(window)
            change_window.title("Change Name")
            
            tk.Label(change_window, text="New first name:").pack()
            new_name_entry = tk.Entry(change_window)
            new_name_entry.insert(0, current_name)
            new_name_entry.pack()

            tk.Label(change_window, text="New last name:").pack()
            new_last_entry = tk.Entry(change_window)
            new_last_entry.insert(0, last_name if last_name else "")
            new_last_entry.pack()

            def save_new_name():
                # Get and clean input
                new_name = new_name_entry.get().strip()
                new_last = new_last_entry.get().strip()
                
                if not new_name:  # At least first name is required
                    messagebox.showerror("Error", "First name cannot be empty")
                    return
                
                # Capitalize both names
                capitalized_name = capitalize_name(new_name)
                capitalized_last = capitalize_name(new_last) if new_last else ""
                
                try:
                    update_user_info(capitalized_name, capitalized_last)
                    name_label.config(text=f"{capitalized_name} {capitalized_last}" if capitalized_last else capitalized_name)
                    messagebox.showinfo("Success", "Name updated successfully!")
                    change_window.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update name: {str(e)}")

            tk.Button(change_window, text="Save", command=save_new_name).pack()

        tk.Button(window, text="✏️ Change Name", command=ask_for_password).pack(pady=10)

        # Voice speed settings
        tk.Label(window, text="\nVoice Speed Settings", font="Arial 12 bold").pack()

        db_manager.execute("SELECT voice_speed FROM users WHERE email=?", (current_user_email,))
        saved_speed = db_manager.fetchone()
        current_speed = saved_speed[0] if saved_speed else "Normal"

        tk.Label(window, text="Voice Speed:").pack()
        speed_combobox = Combobox(window, values=["Fast", "Normal", "Slow"], state="readonly")
        speed_combobox.pack()
        speed_combobox.set(current_speed)

        def save_voice_settings():
            new_speed = speed_combobox.get()
            
            db_manager.execute("""
                UPDATE users 
                SET voice_speed=? 
                WHERE email=?
            """, (new_speed, current_user_email))
            db_manager.commit()
            
            engine.setProperty('rate', 200 if new_speed == "Fast" else 100 if new_speed == "Slow" else 150)
            
            engine.say("Voice speed updated")
            engine.runAndWait()
            
            messagebox.showinfo("Saved", "Voice speed updated!")

        tk.Button(window, text="💾 Save Settings", command=save_voice_settings).pack(pady=10)
        tk.Button(window, text="🔙 Back to Assistant", command=logged_in).pack(pady=5)
    else:
        tk.Label(window, text="User not found.").pack()

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
    
    # Debug: Print current user email
    print(f"DEBUG: Current user email is: '{current_user_email}'")
    
    # Create a frame for the history display
    frame = tk.Frame(window)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Create text widget with scrollbar
    text_area = tk.Text(frame, wrap=tk.WORD)
    scrollbar = tk.Scrollbar(frame, command=text_area.yview)
    text_area.config(yscrollcommand=scrollbar.set)
    
    # Pack them properly
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    # Debug: Print the query we're about to execute
    query = "SELECT timestamp, speaker, message FROM conversations WHERE user_email = ? ORDER BY timestamp DESC"
    print(f"DEBUG: Executing query: {query} with email: '{current_user_email}'")
    
    # Fetch conversations from database
    cursor = db_manager.execute(query, (current_user_email,))
    conversations = cursor.fetchall()
    
    # Debug: Print the results we got
    print(f"DEBUG: Found {len(conversations)} conversations")
    for i, conv in enumerate(conversations):
        print(f"DEBUG: Conversation {i}: {conv}")
    
    if not conversations:
        text_area.insert(tk.END, "No conversation history found")
    else:
        text_area.insert(tk.END, "Conversation History:\n\n")
        for timestamp, speaker, message in conversations:
            text_area.insert(tk.END, f"{timestamp} - {speaker}: {message}\n\n")
    
    # Make text area read-only
    text_area.config(state=tk.DISABLED)
    
    # Add back button at bottom
    tk.Button(window, text="Back to Assistant", command=logged_in).pack()
    
    # Force update the display
    window.update()

def about_me():
    clear_window()
    tk.Label(window, text="About this Voice Assistant Project").pack()
    tk.Button(window, text="Back", command=back_to_previous).pack()

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
        setup_main_screen()
        
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