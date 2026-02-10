from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from game import Game, Card, Suit, Rank  # Importing your provided game logic

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Global Storage ---
# In a production app, use Redis or a database. For now, in-memory dicts work.
games = {}       # Maps room_id -> Game instance
lobbies = {}     # Maps room_id -> List of player names (waiting to start)
player_sessions = {} # Maps request.sid -> {'room': room_id, 'name': player_name}

# --- Helper: Serialization ---
def serialize_card(card):
    if not card:
        return None
    return {'rank': card.rank.value, 'suit': card.suit.value, 'display': str(card)}

def get_game_state_for_player(game_instance, player_name):
    """
    Constructs a JSON-safe game state.
    CRITICAL: Hides opponents' hands to prevent cheating.
    """
    # 1. General Public Info (Visible to everyone)
    current_player_obj = next((p for p in game_instance.players if p.name == player_name), None)
    
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
        'players': []
    }

    # 2. Player Specific Info (Hide hands of others)
    for p in game_instance.players:
        p_data = {
            'name': p.name,
            'is_me': (p.name == player_name),
            'card_count': len(p.hand),
            'hand': [] # Default to empty/hidden
        }
        
        # Only populate 'hand' if this is the requesting player
        if p.name == player_name:
            p_data['hand'] = [serialize_card(c) for c in p.hand]
            
        state['players'].append(p_data)
        
    return state

def broadcast_game_state(room_id):
    """Sends the specific game state to EACH player individually."""
    if room_id not in games:
        return

    game = games[room_id]
    
    # We loop through all sockets in the room and send them their specific view
    # Note: Flask-SocketIO doesn't easily let us iterate room members to send unique msgs 
    # without an external store. A simpler pattern for this prototype is:
    # Emit a 'update_trigger' and have clients request their state, OR
    # Iterate our 'player_sessions' map to find who is in this room.
    
    for sid, info in player_sessions.items():
        if info['room'] == room_id:
            state = get_game_state_for_player(game, info['name'])
            socketio.emit('game_update', state, room=sid)

# --- SocketIO Events ---

@socketio.on('connect')
def on_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('join_game')
def on_join(data):
    """
    Data: {'room': 'room1', 'name': 'Alice'}
    """
    room = data['room']
    name = data['name']
    
    join_room(room)
    
    # Store session info
    player_sessions[request.sid] = {'room': room, 'name': name}
    
    # Add to lobby
    if room not in lobbies:
        lobbies[room] = []
    
    if name not in lobbies[room]:
        lobbies[room].append(name)
        
    # Notify room
    emit('lobby_update', {'players': lobbies[room]}, room=room)

@socketio.on('start_game')
def on_start(data):
    room = player_sessions[request.sid]['room']
    
    if room in games:
        return # Game already started
        
    player_names = lobbies.get(room, [])
    
    try:
        # Initialize Game from game.py logic
        # Constraints: 2-5 players
        new_game = Game(player_names) 
        games[room] = new_game
        broadcast_game_state(room)
        
    except ValueError as e:
        emit('error', {'message': str(e)})

@socketio.on('attack')
def on_attack(data):
    """
    Data: {'rank': 6, 'suit': '♥'}
    """
    sid = request.sid
    info = player_sessions.get(sid)
    game = games.get(info['room'])
    
    if not game: return
    
    try:
        # Reconstruct Card Object
        rank = Rank(data['rank'])
        suit = Suit(data['suit'])
        card = Card(rank, suit)
        
        # Find Player Object
        player = next(p for p in game.players if p.name == info['name'])
        
        # Execute Logic
        game.attack(card, player)
        
        broadcast_game_state(info['room'])
        
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('defend')
def on_defend(data):
    """
    Data: {'attack_rank': 6, 'attack_suit': '♥', 'defend_rank': 14, 'defend_suit': '♥'}
    """
    sid = request.sid
    info = player_sessions.get(sid)
    game = games.get(info['room'])
    
    if not game: return

    try:
        # Reconstruct Cards
        att_card = Card(Rank(data['attack_rank']), Suit(data['attack_suit']))
        def_card = Card(Rank(data['defend_rank']), Suit(data['defend_suit']))
        
        player = next(p for p in game.players if p.name == info['name'])
        
        # Execute Logic: Defender responds with higher card/trump [cite: 10]
        game.defend(att_card, def_card, player)
        
        # Check if turn ended (success) happens automatically in game.py logic? 
        # Actually, in game.py, 'end_turn' is not auto-called inside defend.
        # It's usually triggered when attackers stop attacking.
        
        broadcast_game_state(info['room'])
        
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('pass')
def on_pass_turn(data):
    """
    Maps to 'pass_attack' in game.py.
    This allows a defender to transfer the attack to the next player.
    Data: {'rank': 7, 'suit': '♥'}
    """
    sid = request.sid
    info = player_sessions.get(sid)
    game = games.get(info['room'])
    
    try:
        pass_card = Card(Rank(data['rank']), Suit(data['suit']))
        player = next(p for p in game.players if p.name == info['name'])
        
        game.pass_attack(pass_card, player)
        broadcast_game_state(info['room'])
        
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('skip')
def on_skip_turn(data):
    """
    Maps to 'skip_attack_turn' in game.py.
    This is used by an attacker to say "I am done attacking"[cite: 12].
    """
    sid = request.sid
    info = player_sessions.get(sid)
    game = games.get(info['room'])
    
    try:
        player = next(p for p in game.players if p.name == info['name'])
        
        # This function in game.py handles passing the attack token 
        # or ending the round if everyone skipped.
        game.skip_attack_turn(player)
        
        # Check for loser/game over
        loser_msg = game.check_loser()
        if loser_msg:
             emit('game_over', {'message': loser_msg}, room=info['room'])
        
        broadcast_game_state(info['room'])
        
    except Exception as e:
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    socketio.run(app, debug=True)