# add login function view
import tkinter as tk
from tkinter import messagebox
from tkinter.ttk import Combobox
import sqlite3
import re
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import pyttsx3

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

def setup_main_screen():
    clear_window()
    global window
    global current_state
    current_state = "main"
    window.title("Voice Assistant")

    tk.Button(window, text="Continue without account", command=continue_without_account).pack()
    tk.Button(window, text="Sign In", command=sign_in).pack()
    tk.Button(window, text="Sign Up", command=sign_up).pack()
    tk.Button(window, text="About Me", command=about_me).pack()

def main_screen():
    clear_window()
    tk.Button(window, text="Continue without account", command=continue_without_account).pack()
    tk.Button(window, text="Sign In", command=sign_in).pack()
    tk.Button(window, text="Sign Up", command=sign_up).pack()
    tk.Button(window, text="About Me", command=about_me).pack()

def main_assist():
    clear_window()
    setup_main_screen()

def continue_without_account():
    clear_window()
    conversation_area = tk.Text(window)
    conversation_area.pack()

    tk.Button(window, text="Sign Up", command=sign_up).pack(side=tk.RIGHT)
    tk.Button(window, text="Sign In", command=sign_in).pack(side=tk.RIGHT)
    tk.Button(window, text="Main Menu", command=main_assist).pack()

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

        if not is_valid_email(email):
            messagebox.showerror("Error", "Please enter a valid email address")
            return

        if password != confirm_password:
            messagebox.showerror("Error", "Passwords do not match")
            return

        create_account(name, last_name, email, password)

        clear_window()

        tk.Button(window, text="Continue without account", command=continue_without_account).pack()
        tk.Button(window, text="Sign In", command=sign_in).pack()
        tk.Button(window, text="Sign Up", command=sign_up).pack()
        tk.Button(window, text="About Me", command=about_me).pack()

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
    tk.Button(window, text="Main Menu", command=lambda: main_assist()).pack()

def sign_up_assist():
    clear_window()
    sign_up()

def is_valid_email(email):
    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(email_regex, email)

def create_account(name, last_name, email, password):
    cursor.execute("SELECT * FROM signup WHERE email = ?", (email,))
    existing_email = cursor.fetchone()

    if existing_email:
        messagebox.showerror("Error", f"User  with email '{email}' already exists.")
        return

    # Hash the password using Argon2
    hashed_password = ph.hash(password)

    # Store only the hashed password
    cursor.execute("INSERT INTO signup (name, last_name, email, password) VALUES (?, ?, ?, ?)", 
                   (name, last_name, email, hashed_password))
    conn.commit()
    messagebox.showinfo("Success", "User  account created successfully.")

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
    tk.Button(window, text="SIGN Up", command=lambda: sign_up_assist()).pack()
    tk.Button(window, text="Main Menu", command=lambda: main_assist()).pack()

def login(email, password):
    user = get_user_from_database(email)

    if user:
        stored_password = user[4]  # Get the stored hashed password

        # Verify the password
        try:
            ph.verify(stored_password, password)
            messagebox.showinfo("Success", "Login successful!")
            global current_user
            current_user = user
            global current_user_email
            current_user_email = email
            logged_in()
        except VerifyMismatchError:
            messagebox.showerror("Error", "Incorrect email or password.")
    else:
        messagebox.showerror("Error", "User  not found.")

def logged_in():
    global current_state
    current_state = "logged_in"
    clear_window()
    conversation_area = tk.Text(window)
    conversation_area.pack()

    tk.Button(window, text="LOG OUT", command=log_out).pack()
    tk.Button(window, text="History", command=history).pack()
    tk.Button(window, text="Settings", command=settings).pack()
    tk.Button(window, text="About Me", command=aboutme_assist).pack()

def about_me():
    clear_window()
    tk.Label(window, text="About this Voice Assistant Project").pack()
    tk.Button(window, text="Back", command=back_to_previous).pack()

def aboutme_assist():
    clear_window()
    about_me()

def back_to_previous():
    if current_state == "logged_in":
        logged_in()  # Return to logged-in page
    else:
        main_screen()  # Return to main menu

def history():
    pass


def update_user_info(new_name):
    # Update the user's name in the database
    cursor.execute("UPDATE signup SET name = ? WHERE email = ?", (new_name, current_user_email))
    conn.commit()

def get_current_user_info():
    cursor.execute("SELECT name, password FROM signup WHERE email = ?", (current_user_email,))
    return cursor.fetchone()  # Returns (name, password)

def settings():
    clear_window()
    
    user_info = get_current_user_info()
    
    if user_info:
        current_name, stored_hashed_password = user_info  # Unpack the name and hashed password

        # Display current name
        tk.Label(window, text="Current Name:").pack()
        name_label = tk.Label(window, text=current_name)
        name_label.pack()

        tk.Label(window, text="EMAIL").pack()
        name_label = tk.Label(window, text=current_user_email)
        name_label.pack()
        
 # Initialize the TTS engine
        
        gender_combobox=Combobox(window,values=["Male","Female"],font="arial 14", state="r",width=10)
        gender_combobox.place(x=550,y=200)
        gender_combobox.set("Male")

        speed_combobox=Combobox(window,values=["Fast","Normal","Slow"],font="arial 14", state="r",width=10)
        speed_combobox.place(x=730,y=200)
        speed_combobox.set("Normal")


        def ask_for_password():
            # Create a new window to ask for the password
            password_window = tk.Toplevel(window)
            password_window.title("Verify Password")

            tk.Label(password_window, text="Enter your password:").pack()
            password_entry = tk.Entry(password_window, show='*')
            password_entry.pack()

            def verify_password():
                entered_password = password_entry.get()
                try:
                    # Verify the entered password against the stored hashed password
                    if ph.verify(stored_hashed_password, entered_password):
                        password_window.destroy()  # Close the password window
                        change_name_window()  # Open the change name window
                    else:
                        messagebox.showerror("Error", "Incorrect password. Please try again.")
                except VerifyMismatchError:
                    messagebox.showerror("Error", "Incorrect password. Please try again.")

            tk.Button(password_window, text="Verify", command=verify_password).pack()

        def change_name_window():
            # Create a new window to change the name
            change_window = tk.Toplevel(window)
            change_window.title("Change Name")

            tk.Label(change_window, text="Enter new name:").pack()
            new_name_entry = tk.Entry(change_window)
            new_name_entry.pack()

            accept_var = tk.BooleanVar()
            tk.Checkbutton(change_window, text="I accept to change my name", variable=accept_var).pack()

            def save_new_name():
                new_name = new_name_entry.get()
                if accept_var.get() and new_name:
                    update_user_info(new_name)  # Update the database
                    name_label.config(text=new_name)  # Update the displayed name
                    messagebox.showinfo("Success", "Your name has been updated.")
                    change_window.destroy()  # Close the change name window
                else:
                    messagebox.showerror("Error", "Please accept the change and enter a new name.")

            tk.Button(change_window, text="Change Name", command=save_new_name).pack()

        tk.Button(window, text="Change Name", command=ask_for_password).pack()  # Button to change name
    else:
        tk.Label(window, text="User  not found.").pack()

def clear_window():
    for widget in window.winfo_children():
        widget.destroy()

def log_out():
    global current_user
    current_user = None
    clear_window()
    main_screen()

if __name__ == "__main__":
    window = tk.Tk()
    setup_main_screen()  # Call this once to set up the main screen
    window.mainloop()  # Start the Tkinter event loop