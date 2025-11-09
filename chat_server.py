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
#
"""
apps.chat_server
~~~~~~~~~~~~~~~~~

Central server for peer discovery and tracking in hybrid chat system.
Implements RESTful APIs for peer registration and discovery.
Uses form data format for all communication.
"""

from daemon.weaprous import WeApRous
import json
import threading

# Global tracking list of active peers
active_peers = {}  # Structure: {"peer_id": {"ip": str, "port": int, "username": str}}
channels = {"general": {"peers": [], "owner": "system"}}  # Channel management

# Thread-safe locks
peers_lock = threading.Lock()
channels_lock = threading.Lock()



app = WeApRous()

# Unregister peer
@app.route('/unregister', methods=['POST'])
def unregister_peer(headers="", body=""):
    """Remove peer from active list."""
    try:
        data = json.loads(body)
        peer_id = data.get('peer_id')

        with peers_lock:
            if peer_id in active_peers:
                del active_peers[peer_id]
                print(f"[Server] Unregistered: {peer_id}")
                total = len(active_peers)
                return json.dumps({'status': 'success', 'total': total})
            else:
                return json.dumps({'status': 'error', 'message': 'Peer not found'})
    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)})

# Submit-info
@app.route('/submit-info', methods=['POST'])
def submit_info(headers="", body=""):
    """Peer registration."""
    try:
        data = json.loads(body)
        peer_id = data.get('peer_id')
        peer_info = {
            'ip': data.get('ip'),
            'port': int(data.get('port')),
            'username': data.get('username', 'Anonymous')
        }

        with peers_lock:
            active_peers[peer_id] = peer_info
            total = len(active_peers)

        print("[Server] Registered: {}".format(peer_id))
        return json.dumps({'status': 'success', 'total': total})
    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)})

# Get-list
@app.route('/get-list', methods=['GET'])
def get_list(headers="", body=""):
    """Get peer list."""
    with peers_lock:
        peers = [
            {'id': pid, 'ip': info['ip'], 'port': info['port'], 'username': info['username']}
            for pid, info in active_peers.items()
        ]
    return json.dumps({'status': 'success', 'peers': peers})

# List channels
@app.route('/channels', methods=['GET'])
def list_channels(headers="", body=""):
    """List channels."""
    with channels_lock:
        channel_list = [
            {'name': name, 'owner': data['owner'], 'members': len(data['peers'])}
            for name, data in channels.items()
        ]
    return json.dumps({'status': 'success', 'channels': channel_list})

# Connect peer
@app.route('/connect-peer', methods=['POST'])
def connect_peer(headers="", body=""):
    """Get peer connection info."""
    try:
        data = json.loads(body)
        peer_id = data.get('peer_id')

        with peers_lock:
            info = active_peers.get(peer_id)

        if info:
            return json.dumps({
                'status': 'success',
                'ip': info['ip'],
                'port': info['port'],
                'username': info['username']
            })
        return json.dumps({'status': 'error', 'message': 'Peer not found'})
    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)})

# Create new channel
@app.route('/channel/create', methods=['POST'])
def create_channel(headers="", body=""):
    """Create channel."""
    try:
        data = json.loads(body)
        channel = data.get('channel')
        peer_id = data.get('peer_id')

        with channels_lock:
            if channel in channels:
                return json.dumps({'status': 'error', 'message': 'Channel exists'})
            channels[channel] = {'peers': [peer_id], 'owner': peer_id}

        return json.dumps({'status': 'success'})
    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)})

# Join channel
@app.route('/channel/join', methods=['POST'])
def join_channel(headers="", body=""):
    """Join channel."""
    try:
        data = json.loads(body)
        channel = data.get('channel')
        peer_id = data.get('peer_id')

        with channels_lock:
            if channel not in channels:
                return json.dumps({'status': 'error', 'message': 'Channel not found'})
            if peer_id not in channels[channel]['peers']:
                channels[channel]['peers'].append(peer_id)

        return json.dumps({'status': 'success'})
    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)})

# See channel members
@app.route('/channel/members', methods=['POST'])
def channel_members(headers="", body=""):
    """Get channel members."""
    try:
        data = json.loads(body)
        channel = data.get('channel')

        with channels_lock:
            if channel not in channels:
                return json.dumps({'status': 'error'})
            members_ids = list(channels[channel]['peers'])  # copy to avoid race

        members = []
        with peers_lock:
            for pid in members_ids:
                if pid in active_peers:
                    members.append({'id': pid, 'username': active_peers[pid]['username']})

        return json.dumps({'status': 'success', 'members': members})
    except Exception as e:
        return json.dumps({'status': 'error', 'message': str(e)})


#Start WeAppRous
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog='ChatServer',
        description='Central server for hybrid chat system'
    )
    parser.add_argument('--server-ip', default='127.0.0.1')
    parser.add_argument('--server-port', type=int, default=8000)

    args = parser.parse_args()

    app.prepare_address(args.server_ip, args.server_port)
    print("=" * 50)
    print("Chat Tracker Server")
    print("Link: http://{}:{}".format(args.server_ip, args.server_port))
    print("=" * 50)
    app.run()