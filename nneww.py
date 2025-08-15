#!/usr/bin/env python3
"""
Vulnerable web application with multiple security issues for Claude analysis
"""

import os
import pickle
import sqlite3
import subprocess
import tempfile
from flask import Flask, request, render_template_string, redirect, session
import hashlib
import jwt
import requests

app = Flask(__name__)
app.secret_key = "hardcoded_secret_key_123"  # Hardcoded secret

# Global variables with sensitive data
DATABASE_PASSWORD = "admin123"
API_KEYS = {
    "stripe": "sk_live_1234567890abcdef",
    "aws": "AKIAIOSFODNN7EXAMPLE"
}

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    # SQL Injection vulnerability
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    result = cursor.execute(query).fetchone()
    
    if result:
        # Weak session management
        session['user_id'] = username  # Should be random token
        return "Login successful"
    return "Login failed"

@app.route('/search')
def search():
    query = request.args.get('q', '')
    
    # XSS vulnerability - no output encoding
    template = f"<h1>Search Results for: {query}</h1>"
    return render_template_string(template)

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    
    # Path traversal vulnerability
    filename = request.form.get('filename', file.filename)
    filepath = os.path.join('/uploads', filename)
    
    # No file type validation
    file.save(filepath)
    
    # Deserialization vulnerability
    if filename.endswith('.pkl'):
        with open(filepath, 'rb') as f:
            data = pickle.load(f)  # Dangerous deserialization
    
    return f"File uploaded to {filepath}"

@app.route('/admin/execute')
def admin_execute():
    # Command injection vulnerability
    command = request.args.get('cmd', 'ls')
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return f"<pre>{result.stdout}</pre>"

@app.route('/user/<user_id>')
def get_user(user_id):
    # IDOR vulnerability - no authorization check
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Another SQL injection
    query = f"SELECT * FROM users WHERE id = {user_id}"
    user = cursor.execute(query).fetchone()
    
    return f"User data: {user}"

@app.route('/download')
def download_file():
    # Local file inclusion vulnerability
    filename = request.args.get('file')
    file_path = f"/var/www/files/{filename}"
    
    # No path validation
    with open(file_path, 'r') as f:
        content = f.read()
    
    return content

def hash_password(password):
    # Weak hashing algorithm
    return hashlib.md5(password.encode()).hexdigest()

def generate_token(user_id):
    # Weak JWT implementation
    payload = {'user_id': user_id}
    return jwt.encode(payload, "weak_secret", algorithm="HS256")

@app.route('/api/data')
def api_data():
    # Missing authentication
    # Missing rate limiting
    # Information disclosure
    return {
        "database_host": "prod-db-server.internal",
        "api_keys": API_KEYS,
        "debug_info": os.environ
    }

@app.route('/redirect')
def redirect_user():
    # Open redirect vulnerability
    url = request.args.get('url')
    return redirect(url)  # No URL validation

def make_request(url):
    # SSRF vulnerability
    response = requests.get(url)  # No URL validation
    return response.content

@app.route('/backup')
def create_backup():
    # Race condition vulnerability
    backup_file = f"/tmp/backup_{os.getpid()}.sql"
    
    # Temporary file with predictable name
    with open(backup_file, 'w') as f:
        f.write("SENSITIVE_DATA")
    
    return f"Backup created: {backup_file}"

# Insecure cookie settings
@app.after_request
def after_request(response):
    response.set_cookie('session_id', 'value', secure=False, httponly=False)
    return response

if __name__ == '__main__':
    # Debug mode in production
    app.run(debug=True, host='0.0.0.0', port=5000)
