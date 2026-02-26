# Budallas Backend

This is the Python/Flask backend for the "Budallas" multiplayer card game. 
It serves as the central game server, managing game logic, enforcing rules, and handling real-time state synchronization between players using WebSockets (Socket.IO).

## Live Deployment
* **Backend API:** [https://budallas-backend.onrender.com]
* **Frontend Client:** [https://koljahribar.github.io/budallas-frontend/]

## Technical Architecture
* **Framework:** Flask (Python)
* **Real-time Protocol:** Flask-SocketIO (WebSockets)
* **Game Logic:** Custom Python classes (`Game`, `Player`, `Deck`, `Card`) that enforce Durak-style rules.
* **Concurrency:** Gunicorn with Gevent workers for handling multiple simultaneous WebSocket connections.

## API Documentation & Communication
The frontend communicates with the backend exclusively via **Socket.IO events**. There are no REST endpoints for gameplay.

### 1. Client -> Requests
The frontend emits these events to perform actions.

| Event Name | Parameters (JSON Payload) | Description |
| :--- | :--- | :--- |
| `join_game` | `{ "room": "room1", "name": "Alice", "userId": "uuid..." }` | Joins a player to a specific room. If the game is running and `userId` matches an existing player, it triggers a **reconnection**. |
| `start_game` | *None* | Signals the server to initialize the `Game` instance, shuffle the deck, and deal cards. |
| `attack` | `{ "rank": 11, "suit": "♥" }` | Attempts to play an attacking card. |
| `defend` | `{ "attack_rank": 6, "attack_suit": "♠", "defend_rank": 14, "defend_suit": "♠" }` | Attempts to beat a specific attacking card with a defending card. |
| `pass` | `{ "rank": 11, "suit": "♥" }` | The defender passes the attack to the next player (only allowed if they haven't defended yet). |
| `take` | *None* | The defender gives up and picks up all cards on the table. |
| `skip` | *None* | An attacker chooses to stop attacking (finishes their turn). |
| `restart_game`| *None* | Resets the game state in the current room, redeals cards, but keeps the same players. |

### 2. Server -> Responses
The server broadcasts these events to update the frontend.

* **`lobby_update`**: Sent when a player joins/leaves the waiting room.
    * **Payload:** `{ "players": ["Alice", "Bob"] }`
    * **Frontend Action:** Updates the list of names in the waiting lobby.

* **`game_update`**: The core state update. Sent after **every** valid move.
    * **Payload:** A comprehensive snapshot of the game board.
    * **Privacy Feature:** The `hand` array is **censored**. You only receive your own cards; opponents' hands are sent as empty arrays (preventing cheating).
    * **Structure:**
        ```json
        {
          "trump_suit": "♥",
          "trump_card": { "rank": 6, "suit": "♥", "display": "6♥" },
          "deck_count": 24,
          "table_attack": [ ...cards ],
          "table_defense": [ ...cards ],
          "attacker_name": "Alice",
          "defender_name": "Bob",
          "players": [
            { "name": "Alice", "is_me": true, "hand": [ ...my_cards... ] },
            { "name": "Bob", "is_me": false, "hand": [], "card_count": 6 }
          ]
        }
        ```
    * **Frontend Action:** Re-renders the entire game board (cards, names, status text).

* **`error`**: Sent when a move is invalid (e.g., attacking out of turn).
    * **Payload:** `{ "message": "It is not your turn." }`
    * **Frontend Action:** Displays an alert or toast notification to the user.

* **`game_over`**: Sent when a loser is determined.
    * **Payload:** `{ "message": "Game Over! The Budala is Bob." }`
    * **Frontend Action:** Shows the Game Over screen and a "Play Again" button.

---

## How to Use It
1. Open the **Frontend Client** link in your browser.
2. Enter your Name and a Room ID (e.g., "room1"). Share this Room ID with up to 5 friends.
3. Once in the waiting room, the "Start Game" button will appear when at least 2 players have joined.
4. Click Start, and the game will deal 6 cards to each player and reveal the Trump suit.
5. Follow the classic Durak-style rules to attack, defend, pass, or take cards until only one "Budala" remains!

## Setup & Running Locally

### Prerequisites
* Python 3.8+
* pip

### Installation
1.  **Clone the repository:**
    ```bash
    git clone <https://github.com/KoljaHribar/budallas.git>
    cd <budallas>
    ```

2.  **Create a Virtual Environment (Optional but recommended):**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Mac/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Running the Server
1.  **Start the Flask application:**
    ```bash
    python server.py
    ```
2.  The server will start at `http://localhost:5000`.
3.  **Note:** Ensure your frontend is pointing to `http://localhost:5000` when testing locally.

---

## Security & Authentication

### User Identification
* **UUIDs:** The backend relies on a client-generated UUID (`userId`) sent during the `join_game` event.
* **Persistence:** This `userId` is mapped to the player's session on the server. If a user refreshes the page, the server recognizes the UUID and reconnects them to their existing game seat rather than creating a new player.

### Key Management
* **Flask Secret Key:** The application uses a `SECRET_KEY` to sign session cookies and prevent tampering.
* **Environment Variables:** In production (Render), this key is stored as an environment variable (`os.environ.get('SECRET_KEY')`).
* **Card Visibility:** To prevent frontend hacking, the server filters the game state before sending it. Opponents' cards are stripped from the JSON payload, making it impossible to see other players' hands by inspecting network traffic.