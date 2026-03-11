
online_users = set()
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime , timezone
import sqlite3
import os
import re 
from cryptography.fernet import Fernet
from dotenv import load_dotenv
load_dotenv()


FERNET_SECRET_KEY = os.getenv('FERNET_SECRET_KEY')
if not FERNET_SECRET_KEY:
    raise ValueError("FERNET_SECRET_KEY not found in .env")

fernet = Fernet(FERNET_SECRET_KEY.encode())

user_sid_map = {}  
sid_user_map = {}  

app = Flask(__name__)
app.secret_key = 'secretkey'
socketio = SocketIO(app)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'txt', 'zip', 'mp4', 'webm', 'ogg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    os.makedirs("chat_app", exist_ok=True)
    conn = sqlite3.connect('chat_app/database.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password TEXT NOT NULL,
            approved INTEGER DEFAULT 0
        )
    ''')

    # Chat messages table
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            room TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('chat_app/database.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username=?', (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            if user[4] == 0:  # Check if 'approved' column is 0
                return redirect(url_for('login', error='not_approved'))
            session['username'] = username
            return redirect(url_for('chat', success='login'))

        return redirect(url_for('login', error='invalid'))

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Check if passwords match
        if password != confirm_password:
            return redirect(url_for('signup', error='mismatch', username=username, email=email))

        # Username: only alphabets
        if not re.match(r'^[A-Za-z]+$', username):
            return redirect(url_for('signup', error='invalid_username', email=email))

        # Password: at least 6 chars, 1 uppercase, 1 lowercase, 1 special char
        if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*[^A-Za-z0-9]).{6,}$', password):
            return redirect(url_for('signup', error='weak_password', username=username, email=email))

        hashed_password = generate_password_hash(password)

        try:
            conn = sqlite3.connect('chat_app/database.db')
            c = conn.cursor()
            c.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                      (username, email, hashed_password))
            conn.commit()
            conn.close()
            return redirect(url_for('login', success='1'))
        except:
            return redirect(url_for('signup', error='exists', username=username, email=email))

    return render_template('signup.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']

        conn = sqlite3.connect('chat_app/database.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username=? AND email=?', (username, email))
        user = c.fetchone()
        conn.close()

        if user:
            session['reset_username'] = username
            return redirect(url_for('reset_password'))
        else:
            return redirect(url_for('forgot_password', error='not_found'))

    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        password = request.form['password']
        confirm = request.form['confirm_password']

        if password != confirm:
            return redirect(url_for('reset_password', error='mismatch'))

        if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*[^A-Za-z0-9]).{6,}$', password):
            return redirect(url_for('reset_password', error='weak'))

        hashed = generate_password_hash(password)
        conn = sqlite3.connect('chat_app/database.db')
        c = conn.cursor()
        c.execute('UPDATE users SET password=? WHERE username=?', (hashed, session['reset_username']))
        conn.commit()
        conn.close()
        session.pop('reset_username', None)
        return redirect(url_for('login', success='reset'))

    return render_template('reset_password.html')

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == 'admin':
            conn = sqlite3.connect('chat_app/database.db')
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE username=?', (username,))
            admin = c.fetchone()
            conn.close()

            if admin and check_password_hash(admin[3], password):
                session['username'] = 'admin'
                session['is_admin'] = True
                return redirect(url_for('admin_panel'))

        return redirect(url_for('admin_login', error='invalid'))

    return render_template('admin_login.html')


@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('chat_app/database.db')
    c = conn.cursor()

    # Handle approval
    if request.method == 'POST':
        if 'approve_user_id' in request.form:
            user_id = request.form['approve_user_id']
            c.execute('UPDATE users SET approved = 1 WHERE id = ?', (user_id,))
            conn.commit()
        elif 'delete_user_id' in request.form:
            user_id = request.form['delete_user_id']
            c.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()

    # Get all users (for full list)
    c.execute('SELECT id, username, email, approved FROM users')
    users = c.fetchall()
    conn.close()

    return render_template('admin.html', users=users)



@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', username=session['username'])

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files or 'username' not in session:
        return 'No file or user', 400

    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        file_data = file.read()
        encrypted_data = fernet.encrypt(file_data)

        with open(filepath, 'wb') as f:
            f.write(encrypted_data)

        return jsonify({
            'filename': filename,
            'url': f"/view-file/{filename}"  
        })

    return 'Invalid file', 400

@app.route('/view-file/<filename>')
def view_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(filepath):
        return "File not found", 404

    with open(filepath, 'rb') as f:
        encrypted_data = f.read()

    try:
        decrypted_data = fernet.decrypt(encrypted_data)
    except:
        return "Decryption failed", 403

    mime = 'application/octet-stream'
    ext = filename.rsplit('.', 1)[-1].lower()
    if ext in ['jpg', 'jpeg']:
        mime = 'image/jpeg'
    elif ext == 'png':
        mime = 'image/png'
    elif ext == 'gif':
        mime = 'image/gif'
    elif ext == 'pdf':
        mime = 'application/pdf'
    elif ext == 'txt':
        mime = 'text/plain'
    elif ext == 'mp4':
         mime = 'video/mp4'
    elif ext == 'webm':
        mime = 'video/webm'
    elif ext == 'ogg':
        mime = 'video/ogg'


    return decrypted_data, 200, {'Content-Type': mime}



@socketio.on('message')
def handle_message(data):
    conn = sqlite3.connect('chat_app/database.db')
    c = conn.cursor()
    encrypted_msg = fernet.encrypt(data['message'].encode()).decode()
    c.execute('INSERT INTO messages (username, room, message) VALUES (?, ?, ?)', 
          (data['username'], data['room'], encrypted_msg))

    conn.commit()
    conn.close()
    data['timestamp'] = datetime.now(timezone.utc).isoformat()
    emit('message', data, room=data['room'])

@socketio.on('join')
def handle_join(data):
    username = data['username']
    room = data['room']

    old_sid = sid_user_map.get(username)
    if old_sid:
        user_sid_map.pop(old_sid, None)

    user_sid_map[request.sid] = username
    sid_user_map[username] = request.sid

    join_room(room)
    online_users.add(username)
    emit('status', {'msg': f"{username} has joined the room."}, room=room)
    emit('onlineUsers', list(online_users), broadcast=True)

@socketio.on('typing')
def handle_typing(data):
    emit('typing', data, room=data['room'], include_self=False)

@socketio.on('leave')
def handle_leave(data):
    leave_room(data['room'])
    online_users.discard(data['username'])  # 👈 Remove user from online set
    emit('status', {'msg': f"{data['username']} has left the room."}, room=data['room'])
    emit('onlineUsers', list(online_users), broadcast=True)  # 👈 Send updated list to all

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    username = user_sid_map.get(sid)

    if username:
        online_users.discard(username)
        user_sid_map.pop(sid, None)
        sid_user_map.pop(username, None)

        emit('status', {'msg': f"{username} has left the chat."}, broadcast=True)
        emit('onlineUsers', list(online_users), broadcast=True)

@socketio.on('load_history')
def load_history(data):
    room = data['room']
    conn = sqlite3.connect('chat_app/database.db')
    c = conn.cursor()
    c.execute('SELECT username, message, timestamp FROM messages WHERE room = ? ORDER BY timestamp ASC', (room,))
    rows = c.fetchall()
    conn.close()

    for username, encrypted_message, timestamp in rows:
        try:
            message = fernet.decrypt(encrypted_message.encode()).decode()
        except Exception as e:
            message = "[Decryption failed]"

        try:
            iso_timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
        except:
            iso_timestamp = timestamp  # fallback if already ISO

        emit('message', {
            'username': username,
            'message': message,
            'timestamp': iso_timestamp
        }, to=request.sid)



@socketio.on('private_chat_invite')
def handle_private_chat_invite(data):
    to_user = data['to']
    to_sid = sid_user_map.get(to_user)
    if to_sid:
        emit('chat_invite', {
            'from': data['from'],
            'room': data['room']
        }, room=to_sid)


if __name__ == '__main__':
    init_db()
    socketio.run(app, host='127.0.0.1',port=3000, debug=True)
