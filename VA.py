# add login function view
import tkinter as tk
from tkinter import messagebox
from tkinter.ttk import Combobox
import sqlite3
import re
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import pyttsx3
import speech_recognition as sr
import threading
import subprocess
from datetime import datetime

# Global Variables
current_user = None
window = None
current_state = "main"
current_user_email = None

# Initialize Argon2 Password Hasher
ph = PasswordHasher()

engine = pyttsx3.init()
voices = engine.getProperty('voices')
current_rate = engine.getProperty('rate')

# Connect to the SQLite database
conn = sqlite3.connect('user.db')
cursor = conn.cursor()


def speak(text):
    engine.say(text)
    engine.runAndWait()

def listen_and_respond(conversation_area):
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    
    def listen():
        conversation_area.insert(tk.END, "\nListening...\n")
        conversation_area.see(tk.END)
        window.update()
        
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source)
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                return recognizer.recognize_google(audio)
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                return None
            except Exception as e:
                print(f"Error: {e}")
                return None
    
    def process_command(command):
        if not command:
            return "I didn't catch that. Could you please repeat?"
        
        conversation_area.insert(tk.END, f"USER: {command}\n")
        conversation_area.see(tk.END)
        window.update()
        
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
            conversation_area.insert(tk.END, f"BOT: {response}\n")
            conversation_area.see(tk.END)
            speak(response)
            return False
        else:
            response = "I'm not sure how to help with that. Could you try asking something else?"
        
        conversation_area.insert(tk.END, f"BOT: {response}\n\n")
        conversation_area.see(tk.END)
        speak(response)
        return True
    
    def assistant_loop():
        while True:
            command = listen()
            if not process_command(command):
                break
    
    assistant_thread = threading.Thread(target=assistant_loop)
    assistant_thread.daemon = True
    assistant_thread.start()

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

        cursor.execute("SELECT * FROM signup WHERE email = ?", (email,))
        if cursor.fetchone():
            messagebox.showerror("Error", f"User with email '{email}' already exists.")
            return

        hashed_password = ph.hash(password)
        cursor.execute("INSERT INTO signup (name, last_name, email, password) VALUES (?, ?, ?, ?)", 
                      (name, last_name, email, hashed_password))
        conn.commit()
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
    cursor.execute("SELECT * FROM signup WHERE email = ?", (email,))
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
        
        cursor.execute("SELECT voice_speed FROM signup WHERE email=?", (email,))
        speed_setting = cursor.fetchone()
        if speed_setting:
            speed = speed_setting[0]
            engine.setProperty('rate', 200 if speed == "Fast" else 100 if speed == "Slow" else 150)
        
        logged_in()
    except VerifyMismatchError:
        messagebox.showerror("Error", "Invalid password")

def logged_in():
    global current_state
    current_state = "logged_in"
    clear_window()
    
    # Load voice settings
    cursor.execute("SELECT voice_speed FROM signup WHERE email=?", (current_user_email,))
    speed_setting = cursor.fetchone()
    if speed_setting:
        speed = speed_setting[0]
        engine.setProperty('rate', 200 if speed == "Fast" else 100 if speed == "Slow" else 150)
    
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

    tk.Button(window, text="LOG OUT", command=log_out).pack()
    tk.Button(window, text="History", command=history).pack()
    tk.Button(window, text="Settings", command=show_settings).pack()  # Changed to show_settings
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

        cursor.execute("SELECT voice_speed FROM signup WHERE email=?", (current_user_email,))
        saved_speed = cursor.fetchone()
        current_speed = saved_speed[0] if saved_speed else "Normal"

        tk.Label(window, text="Voice Speed:").pack()
        speed_combobox = Combobox(window, values=["Fast", "Normal", "Slow"], state="readonly")
        speed_combobox.pack()
        speed_combobox.set(current_speed)

        def save_voice_settings():
            new_speed = speed_combobox.get()
            
            cursor.execute("""
                UPDATE signup 
                SET voice_speed=? 
                WHERE email=?
            """, (new_speed, current_user_email))
            conn.commit()
            
            engine.setProperty('rate', 200 if new_speed == "Fast" else 100 if new_speed == "Slow" else 150)
            
            engine.say("Voice speed updated")
            engine.runAndWait()
            
            messagebox.showinfo("Saved", "Voice speed updated!")

        tk.Button(window, text="💾 Save Settings", command=save_voice_settings).pack(pady=10)
        tk.Button(window, text="🔙 Back to Assistant", command=logged_in).pack(pady=5)
    else:
        tk.Label(window, text="User not found.").pack()

def get_current_user_info():
    cursor.execute("SELECT name, password FROM signup WHERE email = ?", (current_user_email,))
    return cursor.fetchone()

def update_user_info(new_name):
    cursor.execute("UPDATE signup SET name = ? WHERE email = ?", (new_name, current_user_email))
    conn.commit()

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
    pass

def log_out():
    global current_user, current_user_email
    current_user = None
    current_user_email = None
    clear_window()
    setup_main_screen()

if __name__ == "__main__":
    window = tk.Tk()
    setup_main_screen()
    window.mainloop()