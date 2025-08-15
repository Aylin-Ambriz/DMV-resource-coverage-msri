#!/usr/bin/env python3
"""
Test file with intentional security vulnerabilities for Claude analysis
"""

import os
import subprocess
import hashlib

# SQL Injection vulnerability
def get_user_data(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"  # Vulnerable to SQL injection
    return query

# Command injection vulnerability  
def process_file(filename):
    command = f"cat {filename}"  # Vulnerable to command injection
    result = subprocess.run(command, shell=True, capture_output=True)
    return result.stdout

# Weak cryptography
def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()  # MD5 is weak

# Hardcoded secrets
API_KEY = "sk-1234567890abcdef"  # Hardcoded API key
DATABASE_PASSWORD = "admin123"  # Hardcoded password

# Missing input validation
def calculate_discount(price, discount_percent):
    return price * (discount_percent / 100)  # No validation on inputs

# Path traversal vulnerability
def read_config_file(config_name):
    config_path = f"/app/config/{config_name}"  # Vulnerable to path traversal
    with open(config_path, 'r') as f:
        return f.read()

if __name__ == "__main__":
    print("This file contains security vulnerabilities for testing")