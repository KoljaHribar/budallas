from flask import Flask, request # core components for a web server
from flask_socketio import SocketIO, emit, join_room, leave_room # handling real-time communication
from game import Game, Card, Suit, Rank # game rules and logic
import os # interacting with operating system
import time # to monitor pleyr activity

app = Flask(__name__) # creates app instance
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_local_secret') # Setting up a secure key, either Render or default
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False) # wraps flask app with Websocket capabilities

# Function to confirm the server is alive
@app.route('/')
def index():
    return "Budallas Backend is Running!"

# Storage
games = {}          # stores running game object (games['Room 1'] = <Game Object>)
users = {}          # stores unique user_id, so you can come back to the game after a refresh, or lost connection
socket_map = {}     # stores the current connection to the permanent user (changes after every refresh)
room_activity = {}  # tracks the last time someone did something in a room

# Helper function to reset the 10-minute timer
def mark_active(room_id):
    room_activity[room_id] = time.time()

# Background check that monitors activity
def inactive_room_cleanup():
    while True:
        socketio.sleep(60) # Check every 60 seconds
        
        try: # Try block prevents the thread from crashing permanently
            now = time.time()
            
            # Find rooms inactive for more than 600 seconds (10 minutes)
            inactive_rooms = [room for room, last_active in list(room_activity.items()) if now - last_active > 600]
            
            for room in inactive_rooms:
                print(f"Cleaning up inactive room: {room}")
                # Alert any players still connected
                socketio.emit('error', {'message': 'Room closed due to inactivity. Please refresh the page.'}, room=room)
                
                # Wipe the room from main memory
                if room in games: del games[room]
                del room_activity[room]
                
                # Prevent Memory Leak -> Delete users attached to this dead room
                users_to_delete = [uid for uid, u_data in users.items() if u_data['room'] == room]
                for uid in users_to_delete:
                    del users[uid]
                    
        except Exception as e:
            print(f"Error in cleanup thread: {e}")

# Start the cleanup thread immediately
socketio.start_background_task(inactive_room_cleanup)

def get_active_players_in_room(room_id):
    """Dynamically calculates exactly who is currently connected to a room"""
    active_names = []
    for sid, uid in list(socket_map.items()):
        if uid in users and users[uid]['room'] == room_id:
            name = users[uid]['name']
            if name not in active_names:
                active_names.append(name)
    return active_names

# Converts cards into JSON
def serialize_card(card):
    if not card: return None
    return {'rank': card.rank.value, 'suit': card.suit.value, 'display': str(card)}

def get_game_state_for_player(game_instance, player_name):
    """Constructs a JSON-safe game state and hides opponents' hands to prevent cheating"""

    # Check if this specific player has won (spectator)
    is_spectator = (player_name in game_instance.winners)

    state = {
        'trump_suit': game_instance.trump_suit.value,
        'trump_card': serialize_card(game_instance.deck.trump_card),
        'deck_count': len(game_instance.deck.cards),
        'discard_pile_count': len(game_instance.discard_pile),
        'table_attack': [serialize_card(c) for c in game_instance.table_attack],
        'table_defense': [serialize_card(c) for c in game_instance.table_defense],
        'attacker_name': game_instance.players[game_instance.attacker_idx].name,
        'defender_name': game_instance.players[game_instance.defender_idx].name,
        'active_attacker_name': game_instance.players[game_instance.active_attacker_idx].name,
        'is_spectator': is_spectator,
        'winners': game_instance.winners,
        'players': []
    }

    # Adding player specific data to the state
    for p in game_instance.players:
        p_data = {
            'name': p.name,
            'is_me': (p.name == player_name),
            'card_count': len(p.hand),
            'hand': [] 
        }
        # Show cards if it's player's hand or if it's spectator's
        if p.name == player_name or is_spectator: 
            p_data['hand'] = [serialize_card(c) for c in p.hand]

        state['players'].append(p_data)
        
    return state

def broadcast_game_state(room_id):
    """Sends the specific game state to each player individually"""
    if room_id not in games: return

    game = games[room_id]
    
    # Iterate through all active sockets (connected devices)
    for sid, user_id in list(socket_map.items()):
        user = users.get(user_id)
        if user and user['room'] == room_id: # right room, right person
            state = get_game_state_for_player(game, user['name'])
            socketio.emit('game_update', state, room=sid) # sends the state to only the user based on his own sid (connection identifier)

def get_user_from_sid(sid):
    """Helper to look up user data from socket ID"""
    user_id = socket_map.get(sid)
    if not user_id: return None
    return users.get(user_id)

# SocketIO Events

@socketio.on('connect')
def on_connect():
    print(f"Client connected: {request.sid}") # logs that device touched the server

@socketio.on('disconnect')
def on_disconnect():
    user_id = socket_map.get(request.sid)
    if user_id:
        name = users[user_id]['name']
        room = users[user_id]['room']
        print(f"User disconnected: {name} (ID: {user_id})")
        
        del socket_map[request.sid]
        
        # Update lobby instantly when someone closes their tab
        active_players = get_active_players_in_room(room)
        socketio.emit('lobby_update', {'players': active_players}, room=room)

@socketio.on('join_game')
def on_join(data):
    # Use .get() to prevent server crashes if a player has an old cached browser!
    room = data.get('room')
    name = data.get('name')
    user_id = data.get('userId', request.sid) # Falls back to session ID if missing

    if not room or not name:
        return

    mark_active(room)
    
    join_room(room)
    
    # Register/Update User Session
    users[user_id] = {'room': room, 'name': name}
    socket_map[request.sid] = user_id 
    
    print(f"User {name} joined/reconnected to {room}")

    # Check for RECONNECT (Game already running)
    if room in games:
        game = games[room]
        # Check if this player is actually in the game
        if any(p.name == name for p in game.players):
            print(f"-> Reconnection detected for {name}")
            # Send them the game state immediately
            state = get_game_state_for_player(game, name)
            emit('game_update', state)
            return
        else:
             emit('error', {'message': "Game already started, and you are not in it!"}) 
             return

    # Broadcast dynamic lobby list instead of manually appending
    active_players = get_active_players_in_room(room)
    emit('lobby_update', {'players': active_players}, room=room)

@socketio.on('start_game')
def on_start(data):
    user = get_user_from_sid(request.sid)
    if not user: return
    
    room = user['room']
    mark_active(room)
    if room in games: return 
        
    # Just call our helper! No more manual filtering.
    valid_players = get_active_players_in_room(room)

    if len(valid_players) < 2:
        emit('error', {'message': "Need at least 2 ACTIVE players to start!"})
        return

    # creates new game object and saves it to games[]
    try:
        new_game = Game(valid_players) 
        games[room] = new_game
        broadcast_game_state(room)
    except ValueError as e:
        emit('error', {'message': str(e)})

@socketio.on('leave_game')
def on_leave(data):
    user = get_user_from_sid(request.sid)
    if not user: return
    
    room = user['room']
    name = user['name']
        
    # If a game is running, end it because someone abandoned
    if room in games:
        emit('error', {'message': f"Game over! {name} abandoned the match."}, room=room)
        emit('game_over', {'message': f"{name} fled the battlefield!"}, room=room)
        del games[room] # Reset the room
        
    # Clean up server memory for this user
    leave_room(room)
    uid = socket_map.get(request.sid)
    if uid in users:
        del users[uid]
    if request.sid in socket_map:
        del socket_map[request.sid]
    
    print(f"{name} left room {room}")
    
    # Update lobby instantly for anyone left behind using the dynamic list
    active_players = get_active_players_in_room(room)
    emit('lobby_update', {'players': active_players}, room=room)

# Game Actions

@socketio.on('attack')
def on_attack(data):
    user = get_user_from_sid(request.sid)
    if not user: return # identity check

    game = games.get(user['room'])
    if not game: return # game check

    mark_active(user['room'])
    
    try:
        # convert JSON from frontend into Card object
        rank = Rank(data['rank'])
        suit = Suit(data['suit'])
        card = Card(rank, suit)
        player = next(p for p in game.players if p.name == user['name'])
        
        game.attack(card, player) # calls the attack
        broadcast_game_state(user['room']) # shows the attack to everyone
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('defend')
def on_defend(data):
    user = get_user_from_sid(request.sid)
    if not user: return # identity check

    game = games.get(user['room'])
    if not game: return # game check

    mark_active(user['room'])

    try:
        # convert JSON from frontend into Card object
        att_card = Card(Rank(data['attack_rank']), Suit(data['attack_suit']))
        def_card = Card(Rank(data['defend_rank']), Suit(data['defend_suit']))
        player = next(p for p in game.players if p.name == user['name'])
        
        game.defend(att_card, def_card, player) # calls the defense
        broadcast_game_state(user['room']) # shows the defense to everyone
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('pass')
def on_pass_turn(data):
    user = get_user_from_sid(request.sid)
    if not user: return # identity check

    game = games.get(user['room'])
    if not game: return # game check

    mark_active(user['room'])
    
    try:
        # convert JSON from frontend into Card object
        pass_card = Card(Rank(data['rank']), Suit(data['suit']))
        player = next(p for p in game.players if p.name == user['name'])
        
        game.pass_attack(pass_card, player) # calls the pass
        broadcast_game_state(user['room']) # shows the pass to everyone
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('skip')
def on_skip_turn(data):
    user = get_user_from_sid(request.sid)
    if not user: return # identity check

    game = games.get(user['room'])
    if not game: return # game check

    mark_active(user['room'])
    
    try:
        # convert JSON from frontend into game state in python
        player = next(p for p in game.players if p.name == user['name'])
        game.skip_attack_turn(player) # call the skip
        
        # Update everyone's screen first (so they see the final move)
        broadcast_game_state(user['room'])
        
        # Check for game over
        loser_msg = game.check_loser()
        if loser_msg:
             emit('game_over', {'message': loser_msg}, room=user['room'])
             # Delete the game so the room resets to "Lobby Mode"
             del games[user['room']]
        
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('take')
def on_take(data):
    user = get_user_from_sid(request.sid)
    if not user: return # identity check

    game = games.get(user['room'])
    if not game: return # game check

    mark_active(user['room'])
    
    try:
        # convert JSON from frontend into game state in python
        player = next(p for p in game.players if p.name == user['name'])
        game.action_take(player) # call the take
        
        # Update screen first
        broadcast_game_state(user['room'])
        
        # Check for game over
        loser_msg = game.check_loser()
        if loser_msg:
             emit('game_over', {'message': loser_msg}, room=user['room'])
             # Delete the game so the room resets
             del games[user['room']]
             
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('restart_game')
def on_restart(data):
    """
    Resets the game state for the room but keeps the same players.
    """
    user = get_user_from_sid(request.sid)
    if not user: return # identity check
    
    room = user['room']
    if room not in games: return # game check

    mark_active(user['room'])

    # Get the list of current player names from the existing game
    current_game = games[room]
    player_names = [p.name for p in current_game.players]
    
    try:
        # Create a fresh Game instance
        new_game = Game(player_names)
        games[room] = new_game
        
        # Notify everyone (clears the board, resets hands)
        print(f"Game in {room} restarted by {user['name']}")
        broadcast_game_state(room)
        
        # Send a system message so they know why it reset
        emit('error', {'message': f"Game restarted by {user['name']}!"}, room=room)
        
    except ValueError as e:
        emit('error', {'message': str(e)})

@socketio.on('send_chat')
def on_chat(data):
    room = data['room']
    mark_active(room)
    # Broadcast to everyone in the room
    emit('receive_chat', data, room=room)

if __name__ == '__main__':
    socketio.run(app, debug=True)