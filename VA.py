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

# 2. Create a more robust stderr suppressor
@contextmanager
def suppress_stderr():
    """Completely suppress stderr output"""
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
        self.connection = sqlite3.connect(self.db_path)
        return self.connection
        
    def get_cursor(self):
        if not self.connection:
            self.connect()
        return self.connection.cursor()
        
    def execute(self, query, params=()):
        with self.lock:
            try:
                cursor = self.get_cursor()
                cursor.execute(query, params)
                self.connection.commit()
                return cursor
            except sqlite3.Error as e:
                print(f"Database error: {e}")
                raise

    # Add these methods to your DatabaseManager class:
    def fetchone(self):
        return self.get_cursor().fetchone()

    def fetchall(self):
        return self.get_cursor().fetchall()

    def commit(self):
        self.connection.commit()

    @property
    def lastrowid(self):
        return self.get_cursor().lastrowid
        
    def close(self):
        if self.connection:
            self.connection.close()


def initialize_database():
    try:
        # Create tables if they don't exist
        db_manager.execute("""
            CREATE TABLE IF NOT EXISTS signup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                last_name TEXT,
                email TEXT UNIQUE,
                password TEXT,
                voice_speed TEXT DEFAULT 'Normal'
            )
        """)
        
        db_manager.execute("""
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                start_time DATETIME,
                end_time DATETIME,
                FOREIGN KEY(user_email) REFERENCES signup(email)
            )
        """)
        
        db_manager.execute("""
            CREATE TABLE IF NOT EXISTS conversation_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                timestamp DATETIME,
                speaker TEXT,
                message TEXT,
                FOREIGN KEY(session_id) REFERENCES conversation_sessions(session_id)
            )
        """)
        db_manager.commit()
    except Exception as e:
        print(f"Error initializing database: {e}")

# Global Variables
current_user = None
window = None
current_state = "main"
current_user_email = None
current_session_id = None  # Add with your other global variables

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
    
    # Run in main thread
    window.after(0, _speak)

def get_working_microphone():
    """Find a working microphone with complete error suppression"""
    with suppress_stderr():
        recognizer = sr.Recognizer()
        try:
            # Try default microphone first
            mic = sr.Microphone()
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
            return mic
        except:
            pass
        
        # Try specific device indexes
        for i in range(5):
            try:
                mic = sr.Microphone(device_index=i)
                with mic as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
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

    def update_gui(text):
        """Safely update the GUI from main thread"""
        if conversation_area.winfo_exists():
            conversation_area.insert(tk.END, text)
            conversation_area.see(tk.END)
            window.update()

    def show_listening():
        """Show listening indicator"""
        if conversation_area.winfo_exists():
            conversation_area.insert(tk.END, "Listening...\n")
            conversation_area.see(tk.END)
            window.update()

    def hide_listening():
        """Remove listening indicator"""
        if conversation_area.winfo_exists():
            # Remove the last line if it says "Listening..."
            current_text = conversation_area.get("1.0", tk.END)
            if current_text.endswith("Listening...\n"):
                conversation_area.delete("end-2l", "end")
            window.update()

    def listen():
        """Listen for user input"""
        with suppress_stderr():
            try:
                window.after(0, show_listening)
                with microphone as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                window.after(0, hide_listening)
                return recognizer.recognize_google(audio)
            except:
                window.after(0, hide_listening)
                return None

    def process_command(command):
        if not command or not command.strip():
            return "I didn't catch that. Could you please repeat?"
    
        command = command.strip()
        print(f"Processing command: {command}")

        # Log user command
        if current_session_id:
            log_conversation(current_session_id, "USER", command)
        
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
        
        # Update GUI and speak only once
        window.after(0, lambda: update_gui(f"USER: {command}\nBOT: {response}\n\n"))
        speak(response)

        if current_session_id and response and response.strip():
            log_conversation(current_session_id, "BOT", response.strip())
        
        return True

    def assistant_loop():
        while not stop_event.is_set():
            command = listen()
            if command and "exit" in command.lower():
                break
            if not process_command(command):
                break
        window.after(0, lambda: hide_listening())

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
    
    # Stop any running assistant thread
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
    
    welcome_msg = "Voice Assistant initialized. Say 'hello' to start or 'exit' to quit.\n\n"
    conversation_area.insert(tk.END, welcome_msg)
    speak("Voice Assistant initialized. Say hello to start or exit to quit.")
    
    listen_and_respond(conversation_area)
    
    button_frame = tk.Frame(window)
    button_frame.pack(fill=tk.X)

    tk.Button(window, text="Sign Up", command=sign_up).pack(side=tk.RIGHT)
    tk.Button(window, text="Sign In", command=sign_in).pack(side=tk.RIGHT)
    tk.Button(window, text="Main Menu", command=setup_main_screen).pack()

def sign_up():
    def create_account_if_valid():
        name = name_entry.get()
        last_name = last_entry.get()
        email = email_entry.get()
        password = password_entry.get()
        confirm_password = confirm_entry.get()

        if not all([name, last_name, email, password, confirm_password]):
            messagebox.showerror("Error", "Please fill in all fields")
            return
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            messagebox.showerror("Error", "Please enter a valid email address")
            return
        if password != confirm_password:
            messagebox.showerror("Error", "Passwords do not match")
            return

        db_manager.execute("SELECT * FROM signup WHERE email = ?", (email,))
        if db_manager.fetchone():
            messagebox.showerror("Error", f"User with email '{email}' already exists.")
            return

        hashed_password = ph.hash(password)
        db_manager.execute("INSERT INTO signup (name, last_name, email, password) VALUES (?, ?, ?, ?)", 
                      (name, last_name, email, hashed_password))
        db_manager.commit()
        messagebox.showinfo("Success", "User account created successfully.")
        setup_main_screen()

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
    cursor = db_manager.execute("SELECT * FROM signup WHERE email = ?", (email,))
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
        
        db_manager.execute("SELECT voice_speed FROM signup WHERE email=?", (email,))
        speed_setting = db_manager.fetchone()
        if speed_setting:
            speed = speed_setting[0]
            engine.setProperty('rate', 200 if speed == "Fast" else 100 if speed == "Slow" else 150)
        
        logged_in()
    except VerifyMismatchError:
        messagebox.showerror("Error", "Invalid password")

def logged_in():
    global current_state, current_session_id, assistant_stop_event
    
    if current_session_id:
        end_conversation_session(current_session_id)
    
    current_state = "logged_in"
    clear_window()
    
    # Start new session
    current_session_id = start_conversation_session(current_user_email)

    # Load voice settings
    db_manager.execute("SELECT voice_speed FROM signup WHERE email=?", (current_user_email,))
    speed_setting = db_manager.fetchone()
    if speed_setting:
        speed = speed_setting[0]
        engine.setProperty('rate', 200 if speed == "Fast" else 100 if speed == "Slow" else 150)
    
    # Create conversation area
    conversation_area = tk.Text(window, wrap=tk.WORD)
    conversation_area.pack(fill=tk.BOTH, expand=True)
    
    scrollbar = tk.Scrollbar(conversation_area)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    conversation_area.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=conversation_area.yview)
    
    # Welcome message
    welcome_msg = "Voice Assistant initialized. Say 'hello' to start or 'exit' to quit.\n\n"
    conversation_area.insert(tk.END, welcome_msg)
    speak("Voice Assistant initialized. Say hello to start or exit to quit.")
    
    # Start assistant (ONCE)
    assistant_stop_event = listen_and_respond(conversation_area)
    
    # Add control buttons
    button_frame = tk.Frame(window)
    button_frame.pack(fill=tk.X)

    tk.Button(window, text="LOG OUT", command=log_out).pack()
    tk.Button(window, text="History", command=history).pack()
    tk.Button(window, text="Settings", command=show_settings).pack()
    tk.Button(window, text="About Me", command=about_me).pack()


def show_settings():
    clear_window()
    
    user_info = get_current_user_info()
    if user_info:
        current_name, stored_hashed_password = user_info

        # Display user info
        tk.Label(window, text="Current Name:").pack()
        name_label = tk.Label(window, text=current_name)
        name_label.pack()

        tk.Label(window, text="Email:").pack()
        email_label = tk.Label(window, text=current_user_email)
        email_label.pack()

        # Name change section (keep this if you want)
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

        def change_name_window():
            change_window = tk.Toplevel(window)
            change_window.title("Change Name")
            
            tk.Label(change_window, text="New name:").pack()
            new_name_entry = tk.Entry(change_window)
            new_name_entry.pack()

            def save_new_name():
                new_name = new_name_entry.get()
                if new_name:
                    update_user_info(new_name)
                    name_label.config(text=new_name)
                    messagebox.showinfo("Success", "Name updated!")
                    change_window.destroy()

            tk.Button(change_window, text="Save", command=save_new_name).pack()

        tk.Button(window, text="✏️ Change Name", command=ask_for_password).pack(pady=10)

        # Voice speed settings
        tk.Label(window, text="\nVoice Speed Settings", font="Arial 12 bold").pack()

        db_manager.execute("SELECT voice_speed FROM signup WHERE email=?", (current_user_email,))
        saved_speed = db_manager.fetchone()
        current_speed = saved_speed[0] if saved_speed else "Normal"

        tk.Label(window, text="Voice Speed:").pack()
        speed_combobox = Combobox(window, values=["Fast", "Normal", "Slow"], state="readonly")
        speed_combobox.pack()
        speed_combobox.set(current_speed)

        def save_voice_settings():
            new_speed = speed_combobox.get()
            
            db_manager.execute("""
                UPDATE signup 
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
    db_manager.execute("SELECT name, password FROM signup WHERE email = ?", (current_user_email,))
    return db_manager.fetchone()

def update_user_info(new_name):
    db_manager.execute("UPDATE signup SET name = ? WHERE email = ?", (new_name, current_user_email))
    db_manager.commit()

# Add these near your other database functions
def start_conversation_session(email):
    db_manager.execute("INSERT INTO conversation_sessions (user_email, start_time) VALUES (?, datetime('now'))", (email,))
    db_manager.commit()
    return db_manager.lastrowid

def end_conversation_session(session_id):
    if not session_id:
        return
        
    try:
        with db_manager.lock:
            print(f"Ending session {session_id}")  # Debug
            db_manager.execute(
                "UPDATE conversation_sessions SET end_time = datetime('now') WHERE session_id = ?", 
                (session_id,)
            )
            db_manager.commit()
    except Exception as e:
        print(f"Failed to end session {session_id}: {e}")
        # Emergency save
        try:
            db_manager.execute(
                "UPDATE conversation_sessions SET end_time = datetime('now') WHERE session_id = ?", 
                (session_id,)
            )
            db_manager.commit()
        except:
            pass

def log_conversation(session_id, speaker, message):
    if not message or not message.strip():
        return
        
    try:
        with db_manager.lock:
            # Print debug info (remove after testing)
            print(f"Attempting to log: Session {session_id}, {speaker}: {message[:50]}...")
            
            cursor = db_manager.execute(
                "INSERT INTO conversation_logs (session_id, timestamp, speaker, message) VALUES (?, datetime('now'), ?, ?)",
                (session_id, speaker, message.strip())
            )
            db_manager.commit()
            print("Log successful!")  # Debug
    except Exception as e:
        print(f"CRITICAL LOG FAILURE: {str(e)}")
        # Try one more time
        try:
            db_manager.execute(
                "INSERT INTO conversation_logs (session_id, timestamp, speaker, message) VALUES (?, datetime('now'), ?, ?)",
                (session_id, speaker, message.strip())
            )
            db_manager.commit()
        except:
            pass

def get_user_conversation_sessions(email):
    db_manager.execute("""
        SELECT session_id, start_time, end_time 
        FROM conversation_sessions 
        WHERE user_email = ?
        ORDER BY start_time DESC
    """, (email,))
    return db_manager.fetchall()

def get_conversation_logs(session_id):
    db_manager.execute("""
        SELECT timestamp, speaker, message 
        FROM conversation_logs 
        WHERE session_id = ?
        ORDER BY timestamp
    """, (session_id,))
    return db_manager.fetchall()

def about_me():
    clear_window()
    tk.Label(window, text="About this Voice Assistant Project").pack()
    tk.Button(window, text="Back", command=back_to_previous).pack()

def back_to_previous():
    if current_state == "logged_in":
        logged_in()
    else:
        setup_main_screen()

def history():
    clear_window()
    global current_state
    current_state = "history"
    
    sessions = get_user_conversation_sessions(current_user_email)
    
    if not sessions:
        tk.Label(window, text="No conversation history found").pack()
        tk.Button(window, text="Back", command=logged_in).pack()
        return
    
    tk.Label(window, text="Your Conversation History", font=("Arial", 14)).pack(pady=10)
    
    for session in sessions:
        session_id, start_time, end_time = session
        btn_text = f"Session from {start_time} to {end_time if end_time else 'now'}"
        
        def show_session(session_id=session_id):
            view_conversation(session_id)
            
        tk.Button(window, text=btn_text, command=show_session).pack(fill=tk.X, padx=20, pady=5)
    
    tk.Button(window, text="Back to Assistant", command=logged_in).pack(pady=10)

def view_conversation(session_id):
    clear_window()
    logs = get_conversation_logs(session_id)
    
    tk.Label(window, text="Conversation Details", font=("Arial", 14)).pack(pady=10)
    
    text_area = tk.Text(window, wrap=tk.WORD)
    scrollbar = tk.Scrollbar(window, command=text_area.yview)
    text_area.configure(yscrollcommand=scrollbar.set)
    
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    text_area.pack(fill=tk.BOTH, expand=True)
    
    for log in logs:
        timestamp, speaker, message = log
        text_area.insert(tk.END, f"{timestamp} - {speaker}: {message}\n\n")
    
    text_area.config(state=tk.DISABLED)
    tk.Button(window, text="Back to History", command=history).pack(pady=10)

def log_out():
    global current_user, current_user_email, current_session_id, assistant_stop_event
    
    # Stop assistant thread
    if 'assistant_stop_event' in globals() and assistant_stop_event:
        assistant_stop_event.set()
    
    # End current session
    if current_session_id:
        end_conversation_session(current_session_id)
        current_session_id = None
    
    current_user = None
    current_user_email = None
    clear_window()
    setup_main_screen()

if __name__ == "__main__":
    # Verify database structure
    db_manager = DatabaseManager('user.db')
    try:
        initialize_database()
        # Test database connection
        db_manager.execute("SELECT name FROM sqlite_master WHERE type='table'")
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        # Try recreating database
        try:
            os.remove('user.db')
            db_manager = DatabaseManager('user.db')
            initialize_database()
            print("Recreated database successfully")
        except:
            print("Fatal database error")
            exit(1)
    
    # Rest of your main code...
    
    window = tk.Tk()
    setup_main_screen()
    
    def on_closing():
        if current_user_email and current_session_id:
            db_manager.execute(
                "UPDATE conversation_sessions SET end_time = datetime('now') WHERE session_id = ?",
                (current_session_id,)
            )
        db_manager.close()
        window.destroy()
    
    window.protocol("WM_DELETE_WINDOW", on_closing)
    window.mainloop()