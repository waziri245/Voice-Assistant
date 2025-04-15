# add login function view
import tkinter as tk
from tkinter import messagebox
import sqlite3
import re
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Global Variables
current_user = None
window = None

# Initialize Argon2 Password Hasher
ph = PasswordHasher()

# Connect to the SQLite database
conn = sqlite3.connect('user.db')
cursor = conn.cursor()

def get_user_from_database(email):
    cursor.execute("SELECT * FROM signup WHERE email = ?", (email,))
    return cursor.fetchone()

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

def login(email, password):
    user = get_user_from_database(email)

    if user:
        stored_password = user[4]  # Get the stored hashed password

        # Verify the password
        try:
            ph.verify(stored_password, password)
            messagebox.showinfo("Success", "Login successful!")
        except VerifyMismatchError:
            messagebox.showerror("Error", "Incorrect email or password.")
    else:
        messagebox.showerror("Error", "User  not found.")

def sign_in():
    clear_window()

    tk.Label(window, text="Email:").pack()
    email_entry = tk.Entry(window)
    email_entry.pack()

    tk.Label(window, text="Password:").pack()
    password_entry = tk.Entry(window, show="*")
    password_entry.pack()

    tk.Button(window, text="Login", command=lambda: login(email_entry.get(), password_entry.get())).pack()

def is_valid_email(email):
    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(email_regex, email)

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

def clear_window():
    for widget in window.winfo_children():
        widget.destroy()

def setup_main_screen():
    global window
    window = tk.Tk()
    window.title("Voice Assistant")

    tk.Button(window, text="Continue without account", command=continue_without_account).pack()
    tk.Button(window, text="Sign In", command=sign_in).pack()
    tk.Button(window, text="Sign Up", command=sign_up).pack()
    tk.Button(window, text="About Me", command=about_me).pack()

    window.mainloop()

def continue_without_account():
    clear_window()
    conversation_area = tk.Text(window)
    conversation_area.pack()

    tk.Button(window, text="Sign Up", command=sign_up).pack(side=tk.RIGHT)
    tk.Button(window, text="Sign In", command=sign_in).pack(side=tk.RIGHT)

def about_me():
    clear_window()
    tk.Label(window, text="About this Voice Assistant Project").pack()
    tk.Button(window, text="Back", command=setup_main_screen).pack()

if __name__ == "__main__":
    setup_main_screen()