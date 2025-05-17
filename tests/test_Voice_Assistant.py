"""
Voice Assistant Comprehensive Test Suite
This file contains unit tests for all major components of the Voice Assistant application.
"""

import unittest
from unittest.mock import patch, MagicMock
import sqlite3
import tkinter as tk
from src.Voice_Assistant import DatabaseManager, DarkButton, convert_units, get_current_user_info, ph
from argon2.exceptions import VerifyMismatchError


# ======================================================================================
# Database Manager Tests
# ======================================================================================
class TestDatabaseManager(unittest.TestCase):
    """Tests for database operations including user creation and conversation logging"""
    
    def setUp(self):
        """Initialize an in-memory database with test schema"""
        self.db = DatabaseManager(':memory:')
        self.db.connect()
        # Create users table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                last_name TEXT,
                email TEXT UNIQUE,
                password TEXT,
                voice_speed TEXT DEFAULT 'Normal'
            )
        """)
        # Create conversations table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                speaker TEXT,
                message TEXT
            )
        """)
        self.db.commit()

    def test_user_creation(self):
        """Verify user creation with valid data"""
        # Insert test user
        self.db.execute(
            "INSERT INTO users (name, last_name, email, password) VALUES (?, ?, ?, ?)",
            ("John", "Doe", "john@test.com", "hash")
        )
        # Retrieve and verify
        user = self.db.execute("SELECT * FROM users WHERE email = ?", ("john@test.com",)).fetchone()
        self.assertEqual(user[1], "John")  # Verify name
        self.assertEqual(user[3], "john@test.com")  # Verify email

    def test_conversation_logging(self):
        """Test conversation history storage functionality"""
        # Insert test conversation
        self.db.execute(
            "INSERT INTO conversations (user_email, speaker, message) VALUES (?, ?, ?)",
            ("john@test.com", "USER", "Test message")
        )
        # Verify insertion
        conv = self.db.execute("SELECT * FROM conversations").fetchone()
        self.assertEqual(conv[3], "USER")  # Verify speaker
        self.assertEqual(conv[4], "Test message")  # Verify message content

    def tearDown(self):
        """Clean up database connection after each test"""
        self.db.close()

# ======================================================================================
# Authentication Tests
# ======================================================================================
class TestAuthentication(unittest.TestCase):
    """Tests for user authentication system including password hashing"""
    
    @classmethod
    def setUpClass(cls):
        """Create test user with hashed password"""
        cls.db = DatabaseManager(':memory:')
        cls.db.connect()
        cls.db.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                last_name TEXT,
                email TEXT UNIQUE,
                password TEXT
            )
        """)
        # Create test user with Argon2 hashed password
        hashed = ph.hash("testpass123")
        cls.db.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            ("Test User", "test@user.com", hashed)
        )
        cls.db.commit()

    def test_valid_login(self):
        """Test successful authentication with correct credentials"""
        user = self.db.execute("SELECT * FROM users WHERE email = ?", ("test@user.com",)).fetchone()
        self.assertTrue(ph.verify(user[4], "testpass123"))  # Verify password hash

    def test_invalid_login(self):
        """Test failed authentication with incorrect password"""
        user = self.db.execute("SELECT * FROM users WHERE email = ?", ("test@user.com",)).fetchone()
        with self.assertRaises(VerifyMismatchError):
            ph.verify(user[4], "wrongpassword")  # Expect password mismatch

    @classmethod
    def tearDownClass(cls):
        """Clean up database after all tests"""
        cls.db.close()

# ======================================================================================
# Utility Function Tests
# ======================================================================================
class TestUtilityFunctions(unittest.TestCase):
    """Tests for core utility functions including unit conversions and time handling"""
    
    def test_unit_conversion(self):
        """Verify accurate unit conversions between different measurement systems"""
        # Metric length conversion
        self.assertAlmostEqual(convert_units(1, 'km', 'm'), 1000)
        # Temperature conversions
        self.assertAlmostEqual(convert_units(0, 'c', 'f'), 32)  # Celsius to Fahrenheit
        self.assertAlmostEqual(convert_units(32, 'f', 'c'), 0)   # Fahrenheit to Celsius
        
    def test_world_time(self):
        """Test world time lookup functionality"""
        from src.Voice_Assistant import get_world_time
        times = get_world_time('London')
        self.assertIn('London', times)  # Verify location exists in results
        # Verify time format HH:MM AM/PM
        self.assertRegex(times['London'], r'\d{2}:\d{2} [AP]M')

# ======================================================================================
# GUI Component Tests
# ======================================================================================
class TestGUIComponents(unittest.TestCase):
    """Tests for custom GUI components and theme consistency"""
    
    def setUp(self):
        """Initialize GUI environment without displaying windows"""
        self.root = tk.Tk()
        self.root.withdraw()  # Prevent window from appearing
        from src.Voice_Assistant import DARK_THEME
        self.theme = DARK_THEME

    def test_dark_button_creation(self):
        """Verify proper creation of themed buttons"""
        button = DarkButton(self.root, text="Test")
        self.assertEqual(button['text'], "Test")
        self.assertEqual(button.cget('bg'), self.theme['button_bg'])
        self.assertEqual(button.cget('fg'), self.theme['fg'])

    def tearDown(self):
        self.root.destroy()

# ======================================================================================
# User Function Tests
# ======================================================================================
class TestUserFunctions(unittest.TestCase):
    """Tests for user profile management functions"""
    
    def setUp(self):
        """Create test user with full profile data"""
        self.db = DatabaseManager(':memory:')
        self.db.connect()
        self.db.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                last_name TEXT,
                email TEXT,
                password TEXT,
                voice_speed TEXT DEFAULT 'Normal'
            )
        """)
        # Insert complete user profile
        self.db.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
            (1, "Alice", "Smith", "alice@test.com", "hash", "Normal")
        )
        self.db.commit()

# ======================================================================================
# Error Handling Tests
# ======================================================================================
class TestErrorHandling(unittest.TestCase):
    """Tests for proper error handling in edge cases"""
    
    def test_invalid_unit_conversion(self):
        """Test handling of unsupported unit conversions"""
        result = convert_units(1, 'invalid', 'units')
        self.assertEqual(result, "Unsupported unit conversion")

    @patch('src.Voice_Assistant.requests.get')
    def test_failed_weather_api(self, mock_get):
        """Test graceful handling of API failures"""
        mock_get.side_effect = Exception("API Error")
        from src.Voice_Assistant import get_weather
        result = get_weather("InvalidCity")
        self.assertIsNone(result)  # Verify None return on failure

# ======================================================================================
# Test Execution Configuration
# ======================================================================================
if __name__ == '__main__':
    """Main test execution with verbose output and fail-fast mode"""
    unittest.main(failfast=True, verbosity=2)