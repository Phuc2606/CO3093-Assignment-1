#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course

"""
chat_peer
~~~~~~~~~~~~~~~~~

P2P chat peer using WeApRous framework with form data.
Each peer runs as a web application with HTML UI.
"""

import socket
import threading
import argparse
import json
import time
from daemon.weaprous import WeApRous

# Peer configuration
peer_config = {
    'username': 'Anonymous',
    'peer_id': None,
    'peer_port': 5000,
    'server_ip': '127.0.0.1',
    'server_port': 8000,
    'connected_peers': {},
    'messages': [],
    'channels': {},
    'peer_list': [],
    'handshakes': {}  # Track handshake status: peer_id -> {'status': 'pending'|'accepted', 'timestamp': time}
}

app = WeApRous()

# P2P Socket Server
p2p_server_socket = None
p2p_running = False

# Add message notification queue
message_update_flag = {'updated': False, 'timestamp': time.time()}
message_lock = threading.Lock()

# Add tracking for peers and channels
peer_update_flag = {'updated': False, 'timestamp': time.time(), 'last_count': 0}
channel_update_flag = {'updated': False, 'timestamp': time.time(), 'last_count': 0}
update_lock = threading.Lock()

def send_http_to_server(method, path, data=None):
    """Send HTTP request with JSON to central server."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((peer_config['server_ip'], peer_config['server_port']))
        
        body = json.dumps(data) if data else ""
        request = "{} {} HTTP/1.1\r\n".format(method, path)
        request += "Host: {}:{}\r\n".format(
            peer_config['server_ip'], peer_config['server_port'])
        request += "Content-Type: application/json\r\n"
        request += "Content-Length: {}\r\n".format(len(body))
        request += "\r\n{}".format(body)
        
        sock.sendall(request.encode())
        response = sock.recv(4096).decode()
        sock.close()
        
        if '\r\n\r\n' in response:
            body_part = response.split('\r\n\r\n', 1)[1]
            return json.loads(body_part) if body_part else {}
        return {}
    except Exception as e:
        print("[Peer] HTTP request error: {}".format(e))
        return {}

def send_p2p_message(peer_ip, peer_port, message_data):
    """Send P2P message with JSON."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((peer_ip, peer_port))
        
        body = json.dumps(message_data)
        request = "POST /p2p/message HTTP/1.1\r\n"
        request += "Host: {}:{}\r\n".format(peer_ip, peer_port)
        request += "Content-Type: application/json\r\n"
        request += "Content-Length: {}\r\n".format(len(body))
        request += "\r\n{}".format(body)
        
        sock.sendall(request.encode())
        sock.recv(1024)
        sock.close()
        return True
    except Exception as e:
        print("[Peer] P2P send error: {}".format(e))
        return False

def handle_p2p_connection(conn, addr):
    """Handle incoming P2P connection."""
    try:
        request = conn.recv(2048).decode()
        if '\r\n\r\n' in request:
            # Parse request line to get path
            lines = request.split('\r\n')
            request_line = lines[0]
            parts = request_line.split(' ')
            path = parts[1] if len(parts) > 1 else ''
            
            body = request.split('\r\n\r\n', 1)[1]
            data = json.loads(body)
            
            # Handle handshake request
            if path == '/p2p/handshake':
                from_peer = data.get('from')
                username = data.get('username', 'Unknown')
                
                print("[Peer] Handshake request from {} ({})".format(username, from_peer))
                
                # Accept handshake
                peer_config['handshakes'][from_peer] = {
                    'status': 'accepted',
                    'timestamp': time.time(),
                    'username': username
                }
                
                response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{}"
                conn.sendall(response.format(json.dumps({
                    'status': 'accepted',
                    'peer_id': peer_config['peer_id'],
                    'username': peer_config['username']
                })).encode())
                return
            
            # Handle regular message
            from_peer = data.get('from', 'unknown')
            msg_type = data.get('type', 'direct')
            
            # Check handshake only for direct and broadcast messages, not for channel
            if msg_type in ['direct', 'broadcast']:
                if from_peer not in peer_config['handshakes'] or peer_config['handshakes'][from_peer]['status'] != 'accepted':
                    response = "HTTP/1.1 403 Forbidden\r\nContent-Type: application/json\r\n\r\n{}"
                    conn.sendall(response.format(json.dumps({
                        'status': 'error',
                        'message': 'Handshake required'
                    })).encode())
                    return
            
            # Store message
            with message_lock:
                peer_config['messages'].append({
                    'from': data.get('from', 'unknown'),
                    'to': 'me',
                    'content': data.get('message', ''),
                    'type': msg_type,
                    'channel': data.get('channel', '')
                })
                
                # Set update flag for notification
                message_update_flag['updated'] = True
                message_update_flag['timestamp'] = time.time()
            
            print("[Peer] New message from {}: {}".format(
                data.get('from'), data.get('message')))
            
            response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{}"
            conn.sendall(response.format(json.dumps({'status': 'ok'})).encode())
    except Exception as e:
        print("[Peer] P2P error: {}".format(e))
    finally:
        conn.close()

def start_p2p_listener():
    """Start P2P listener on separate thread."""
    global p2p_server_socket, p2p_running
    
    try:
        p2p_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        p2p_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        p2p_port = peer_config['peer_port'] + 1000
        p2p_server_socket.bind(('0.0.0.0', p2p_port))
        p2p_server_socket.listen(10)
        p2p_running = True
        
        print("[Peer] P2P listener started on port {}".format(p2p_port))
        
        while p2p_running:
            try:
                conn, addr = p2p_server_socket.accept()
                thread = threading.Thread(
                    target=handle_p2p_connection,
                    args=(conn, addr)
                )
                thread.daemon = True
                thread.start()
            except Exception as e:
                if p2p_running:
                    print("[Peer] Accept error: {}".format(e))
    except Exception as e:
        print("[Peer] P2P listener error: {}".format(e))
    finally:
        if p2p_server_socket:
            p2p_server_socket.close()

# ==================== WeApRous Routes ====================

@app.route('/api/peers', methods=['GET'])
def get_peers(headers="guest", body="anonymous"):
    """Get list of peers from central server."""
    result = send_http_to_server('GET', '/get-list')
    return json.dumps(result if result else {'status': 'error'})

@app.route('/api/messages', methods=['GET'])
def get_messages(headers="guest", body="anonymous"):
    """Get messages."""
    with message_lock:
        return json.dumps({
            'status': 'success',
            'messages': peer_config['messages'],
            'timestamp': message_update_flag['timestamp']
        })

@app.route('/api/messages/poll', methods=['GET'])
def poll_messages(headers="guest", body="anonymous"):
    """Long-polling endpoint for real-time updates."""
    # Wait for new messages (max 30 seconds)
    timeout = 30
    start_time = time.time()
    last_check = message_update_flag['timestamp']
    
    while (time.time() - start_time) < timeout:
        with message_lock:
            if message_update_flag['updated'] and message_update_flag['timestamp'] > last_check:
                # New message arrived
                message_update_flag['updated'] = False
                return json.dumps({
                    'status': 'success',
                    'has_update': True,
                    'messages': peer_config['messages'],
                    'timestamp': message_update_flag['timestamp']
                })
        
        # Sleep briefly before checking again
        time.sleep(0.5)
    
    # Timeout - no new messages
    return json.dumps({
        'status': 'success',
        'has_update': False,
        'timestamp': time.time()
    })

@app.route('/api/peers/poll', methods=['GET'])
def poll_peers(headers="guest", body="anonymous"):
    """Long-polling endpoint for peer updates."""
    timeout = 30
    start_time = time.time()
    last_check = peer_update_flag['timestamp']
    
    while (time.time() - start_time) < timeout:
        # Check server for peer updates
        result = send_http_to_server('GET', '/get-list')
        if result.get('status') == 'success':
            peer_count = len(result.get('peers', []))
            
            with update_lock:
                if peer_count != peer_update_flag['last_count']:
                    peer_update_flag['last_count'] = peer_count
                    peer_update_flag['updated'] = True
                    peer_update_flag['timestamp'] = time.time()
                    
                    return json.dumps({
                        'status': 'success',
                        'has_update': True,
                        'timestamp': peer_update_flag['timestamp']
                    })
        
        time.sleep(1)
    
    return json.dumps({
        'status': 'success',
        'has_update': False,
        'timestamp': time.time()
    })

@app.route('/api/channels/poll', methods=['GET'])
def poll_channels(headers="guest", body="anonymous"):
    """Long-polling endpoint for channel updates."""
    timeout = 30
    start_time = time.time()
    last_check = channel_update_flag['timestamp']
    
    while (time.time() - start_time) < timeout:
        # Check server for channel updates
        result = send_http_to_server('GET', '/channels')
        if result.get('status') == 'success':
            channel_count = len(result.get('channels', []))
            
            with update_lock:
                if channel_count != channel_update_flag['last_count']:
                    channel_update_flag['last_count'] = channel_count
                    channel_update_flag['updated'] = True
                    channel_update_flag['timestamp'] = time.time()
                    
                    return json.dumps({
                        'status': 'success',
                        'has_update': True,
                        'timestamp': channel_update_flag['timestamp']
                    })
        
        time.sleep(1)
    
    
    return json.dumps({
        'status': 'success',
        'has_update': False,
        'timestamp': time.time()
    })

@app.route('/api/handshake', methods=['POST'])
def handshake_peer(headers="guest", body="anonymous"):
    """Initiate handshake with another peer."""
    try:
        data = json.loads(body) if body != "anonymous" else {}
        to_peer_id = data.get('peer_id')
        
        if not to_peer_id:
            return json.dumps({'status': 'error', 'message': 'Missing peer_id'})
        
        # Get peer info from server
        peer_info = send_http_to_server('POST', '/connect-peer', {'peer_id': to_peer_id})
        
        if peer_info.get('status') == 'success':
            ip = peer_info['ip']
            port = int(peer_info['port'])
            
            # Send handshake request
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((ip, port + 1000))
                
                handshake_data = {
                    'from': peer_config['peer_id'],
                    'username': peer_config['username']
                }
                body_str = json.dumps(handshake_data)
                request = "POST /p2p/handshake HTTP/1.1\r\n"
                request += "Host: {}:{}\r\n".format(ip, port + 1000)
                request += "Content-Type: application/json\r\n"
                request += "Content-Length: {}\r\n".format(len(body_str))
                request += "\r\n{}".format(body_str)
                
                sock.sendall(request.encode())
                response = sock.recv(1024).decode()
                sock.close()
                
                if '\r\n\r\n' in response:
                    body_part = response.split('\r\n\r\n', 1)[1]
                    result = json.loads(body_part) if body_part else {}
                    
                    if result.get('status') == 'accepted':
                        # Store handshake
                        peer_config['handshakes'][to_peer_id] = {
                            'status': 'accepted',
                            'timestamp': time.time(),
                            'username': result.get('username', 'Unknown')
                        }
                        
                        return json.dumps({
                            'status': 'success',
                            'message': 'Handshake accepted',
                            'peer_username': result.get('username')
                        })
                
                return json.dumps({'status': 'error', 'message': 'Handshake rejected'})
            except Exception as e:
                return json.dumps({'status': 'error', 'message': 'Connection failed: {}'.format(str(e))})
        
        return json.dumps({'status': 'error', 'message': 'Peer not found'})
    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)})

@app.route('/api/handshakes', methods=['GET'])
def get_handshakes(headers="guest", body="anonymous"):
    """Get list of handshaked peers."""
    return json.dumps({
        'status': 'success',
        'handshakes': peer_config['handshakes']
    })

@app.route('/api/send', methods=['POST'])
def send_direct(headers="guest", body="anonymous"):
    """Send direct P2P message."""
    try:
        data = json.loads(body) if body != "anonymous" else {}
        to_peer_id = data.get('to')
        message = data.get('message')
        
        if not to_peer_id or not message:
            return json.dumps({'status': 'error', 'message': 'Missing fields'})
        
        # Check handshake status
        if to_peer_id not in peer_config['handshakes'] or peer_config['handshakes'][to_peer_id]['status'] != 'accepted':
            return json.dumps({'status': 'error', 'message': 'Handshake required. Please handshake first.'})
        
        peer_info = send_http_to_server('POST', '/connect-peer', {'peer_id': to_peer_id})
        
        if peer_info.get('status') == 'success':
            ip = peer_info['ip']
            port = int(peer_info['port'])
            
            msg_data = {
                'from': peer_config['peer_id'],
                'message': message,
                'type': 'direct'
            }
            
            if send_p2p_message(ip, port + 1000, msg_data):
                with message_lock:
                    peer_config['messages'].append({
                        'from': 'You',
                        'to': to_peer_id,
                        'content': message,
                        'type': 'direct',
                        'channel': ''
                    })
                    message_update_flag['updated'] = True
                    message_update_flag['timestamp'] = time.time()
                
                return json.dumps({'status': 'success'})
        
        return json.dumps({'status': 'error', 'message': 'Failed to send'})
    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)})

@app.route('/api/broadcast', methods=['POST'])
def broadcast(headers="guest", body="anonymous"):
    """Broadcast message to all peers."""
    try:
        data = json.loads(body) if body != "anonymous" else {}
        message = data.get('message')
        
        if not message:
            return json.dumps({'status': 'error', 'message': 'Missing message'})
        
        peers_data = send_http_to_server('GET', '/get-list')
        if peers_data.get('status') == 'success':
            msg_data = {
                'from': peer_config['peer_id'],
                'message': message,
                'type': 'broadcast'
            }
            
            sent = 0
            failed = []
            for peer in peers_data.get('peers', []):
                if peer['id'] != peer_config['peer_id']:
                    # Check handshake for broadcast
                    if peer['id'] not in peer_config['handshakes'] or peer_config['handshakes'][peer['id']]['status'] != 'accepted':
                        failed.append(peer['id'])
                        continue
                    
                    if send_p2p_message(peer['ip'], int(peer['port']) + 1000, msg_data):
                        sent += 1
            
            with message_lock:
                peer_config['messages'].append({
                    'from': 'You',
                    'to': '',
                    'content': message,
                    'type': 'broadcast',
                    'channel': ''
                })
                message_update_flag['updated'] = True
                message_update_flag['timestamp'] = time.time()
            
            msg = 'Sent to {} peers'.format(sent)
            if failed:
                msg += ' ({} peers require handshake first)'.format(len(failed))
            
            return json.dumps({'status': 'success', 'message': msg})
        
        return json.dumps({'status': 'error'})
    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)})

@app.route('/api/channel/create', methods=['POST'])
def create_channel(headers="guest", body="anonymous"):
    """Create new channel."""
    data = json.loads(body) if body != "anonymous" else {}
    result = send_http_to_server('POST', '/channel/create', {
        'channel': data.get('channel'),
        'peer_id': peer_config['peer_id']
    })
    return json.dumps(result)

@app.route('/api/channel/join', methods=['POST'])
def join_channel(headers="guest", body="anonymous"):
    """Join channel."""
    data = json.loads(body) if body != "anonymous" else {}
    result = send_http_to_server('POST', '/channel/join', {
        'channel': data.get('channel'),
        'peer_id': peer_config['peer_id']
    })
    return json.dumps(result)

@app.route('/api/channel/send', methods=['POST'])
def send_to_channel(headers="guest", body="anonymous"):
    """Send message to channel."""
    try:
        data = json.loads(body) if body != "anonymous" else {}
        channel = data.get('channel')
        message = data.get('message')
        
        if not channel or not message:
            return json.dumps({'status': 'error'})
        
        members = send_http_to_server('POST', '/channel/members', {'channel': channel})
        
        if members.get('status') == 'success':
            msg_data = {
                'from': peer_config['peer_id'],
                'message': message,
                'type': 'channel',
                'channel': channel
            }
            
            sent = 0
            for member in members.get('members', []):
                if member['id'] != peer_config['peer_id']:
                    peer_info = send_http_to_server('POST', '/connect-peer', {'peer_id': member['id']})
                    if peer_info.get('status') == 'success':
                        # No handshake check for channel messages
                        if send_p2p_message(peer_info['ip'], int(peer_info['port']) + 1000, msg_data):
                            sent += 1
            
            with message_lock:
                peer_config['messages'].append({
                    'from': 'You',
                    'to': '',
                    'content': message,
                    'type': 'channel',
                    'channel': channel
                })
                message_update_flag['updated'] = True
                message_update_flag['timestamp'] = time.time()
            
            return json.dumps({'status': 'success', 'message': 'Sent to {} members'.format(sent)})
        
        return json.dumps({'status': 'error'})
    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)})

@app.route('/api/channels', methods=['GET'])
def get_channels(headers="guest", body="anonymous"):
    """Get channels."""
    result = send_http_to_server('GET', '/channels')
    return json.dumps(result)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='P2P Chat Peer')
    parser.add_argument('--username', required=True)
    parser.add_argument('--peer-port', type=int, required=True)
    parser.add_argument('--server-ip', default='127.0.0.1')
    parser.add_argument('--server-port', type=int, default=8000)
    
    args = parser.parse_args()
    
    peer_config['username'] = args.username
    peer_config['peer_port'] = args.peer_port
    peer_config['server_ip'] = args.server_ip
    peer_config['server_port'] = args.server_port
    
    # Start P2P listener thread
    p2p_thread = threading.Thread(target=start_p2p_listener)
    p2p_thread.daemon = True
    p2p_thread.start()
    
    # Register with central server
    peer_config['peer_id'] = 'peer_{}'.format(args.peer_port)
    reg_data = {
        'peer_id': peer_config['peer_id'],
        'username': args.username,
        'ip': '127.0.0.1',
        'port': args.peer_port
    }
    
    result = send_http_to_server('POST', '/submit-info', reg_data)
    if result and result.get('status') == 'success':
        print("[Peer] Registered as {}".format(peer_config['peer_id']))
    else:
        print("[Peer] Registration failed!")
    
    # Start WeApRous web server
    app.prepare_address('127.0.0.1', args.peer_port)
    print("=" * 60)
    print("[Peer] {} - Web UI: http://127.0.0.1:{}".format(
        args.username, args.peer_port))
    print("[Peer] P2P Port: {}".format(args.peer_port + 1000))
    print("=" * 60)
    app.run()