# Budallas Backend

This is the Python/Flask backend for the "Budallas" multiplayer card game. 
It manages the state of the game, turn logic, and real-time communication using WebSockets.

## Live Deployment
* **Backend:** https://budallas-backend.onrender.com
* **Frontend:** https://koljahribar.github.io/budallas-frontend/

## Endpoints & Communication
The frontend communicates with this backend via **Socket.IO events** (WebSockets).

### Key Events
* **`connect`**: Establishes the WebSocket connection.
* **`join_game`**:
    * **Sends:** `{ room: "room1", name: "Kolja", userId: "uuid..." }`
    * **Returns:** Joins the user to a specific socket room. Emits `lobby_update` to all users in that room.
* **`start_game`**:
    * **Action:** Initializes the `Game` class, shuffles the deck, and deals cards.
    * **Returns:** Emits `game_update` with the initial board state.
* **`attack` / `defend`**:
    * **Sends:** Card data (Rank/Suit).
    * **Action:** Validates the move against Durak rules.
    * **Returns:** Broadcasts the new game state to all players in the room.

## 🔒 Security
* **Secrets:** The Flask `SECRET_KEY` is configured via environment variables in production (Render) to prevent session tampering.