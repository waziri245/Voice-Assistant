# Voice Assistant with GUI

A cross-platform, voice-controlled desktop assistant built using Python. This assistant provides a graphical user interface (GUI) and a wide array of functionalities including system control, web information retrieval, and user-specific features backed by an SQLite database.

---

## Features

* 🎙️ **Voice Recognition** with real-time response
* 💬 **Text-to-Speech Output** (TTS)
* 🧑‍💼 **User Authentication System** (Sign up / Sign in)
* 🗃️ **User-specific conversation history**
* ⚙️ **Settings page** with user details
* 🧠 **Multi-function intelligent assistant**, including:

  * Unit conversion
  * Wikipedia search
  * News summarization
  * Weather information
  * Word explanations and simplifications
  * World time zones
  * Holiday lookups
* 🖥️ **System control** commands (open apps, lock, shutdown, restart)
* 🌐 **Web integration** (opens links, searches online)
* 🎨 **Dark-themed GUI** built with `tkinter`
* 🛡️ **Secure password hashing** with `argon2`
* 🧠 **Multithreading** for non-blocking GUI and voice interaction

---

## Setup & Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-username/voice-assistant.git
   cd voice-assistant
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**

   ```bash
   python Voice_Assistant.py
   ```

---

## Functionalities the Assistant Can Perform

### 🔧 System Controls

* `open calculator`
* `open browser`
* `open terminal`
* `open file manager`
* `lock computer`
* `shutdown computer`
* `restart computer`

### 🌐 Web and Knowledge

* `search wikipedia for <topic>`
* `explain <word>`
* `simplify <word>`
* `what's the weather in <city>`
* `get news summaries`
* `world time in <city>`
* `holidays in <month>`

### 📐 Unit Conversion

* Convert between:

  * Length: mm, cm, m, km, in, ft, yd, mi
  * Weight: mg, g, kg, oz, lb
  * Volume: ml, l, gal, qt, pt, cup, fl oz
  * Temperature: C, F

### 👥 User Management

* Sign up / Sign in securely
* Continue as guest
* View and update user settings
* View history of previous interactions

---

## File Structure

```
voice-assistant/
├── VA.py               # Main application file
├── README.md           # Project overview and usage
├── user.db             # SQLite database for user info and history
├── requirements.txt    # List of Python dependencies
```

---

## Technologies Used

* **Python 3**
* **tkinter** - GUI
* **speech\_recognition** - Voice input
* **pyttsx3** - Text-to-speech
* **wikipedia**, **requests** - Web data
* **sqlite3** - Local data storage
* **argon2-cffi** - Secure password hashing
* **holidays**, **pytz** - Global time & calendar support

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Author

Developed with passion by Atal abdullah Waziri, co-founder of Stellar organization.

---

## Screenshots

*Add some GUI screenshots here showing the interface in action.*
