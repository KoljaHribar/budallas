// Make sure this matches your Render URL
const socket = io("https://budallas-backend.onrender.com", { 
    transports: ["websocket"],
    cors: { origin: "*" }
});

let gameState = null;
let myName = "";
let myRoom = "";

// --- NEW: User ID Logic ---
// 1. Try to get ID from local storage
let myUserId = localStorage.getItem("budallas_userId");

// 2. Generate ID if it doesn't exist yet
if (!myUserId) {
    myUserId = crypto.randomUUID(); 
    localStorage.setItem("budallas_userId", myUserId);
}
// --------------------------

let selectedHandCard = null;
let selectedTableCard = null;

const screens = {
    login: document.getElementById('login-overlay'),
    lobby: document.getElementById('lobby-screen'),
    game: document.getElementById('game-interface')
};

const ui = {
    nameInput: document.getElementById('username'),
    roomInput: document.getElementById('room'),
    btnJoin: document.getElementById('btn-join'),
    
    lobbyRoomName: document.getElementById('lobby-room-name'),
    lobbyList: document.getElementById('lobby-player-list'),
    lobbyStatus: document.getElementById('lobby-status-text'),
    btnStart: document.getElementById('btn-start-game'),

    hand: document.getElementById('my-hand'),
    table: document.getElementById('battlefield'),
    opponents: document.getElementById('opponents-container'),
    status: document.getElementById('status-message'),
    
    // Header Elements
    trumpContainer: document.getElementById('trump-card-container'),
    deckCount: document.getElementById('deck-count'),
    statAttacker: document.getElementById('stat-attacker'),
    statDefender: document.getElementById('stat-defender')
};

// --- LOGIN ---
ui.btnJoin.addEventListener('click', () => {
    const name = ui.nameInput.value.trim();
    // Force lowercase here:
    const room = ui.roomInput.value.trim().toLowerCase(); 
    
    if (!name || !room) return alert("Please enter both Name and Room ID");
    
    myName = name;
    myRoom = room;
    
    screens.login.classList.add('hidden');
    screens.lobby.classList.remove('hidden');
    ui.lobbyRoomName.innerText = `Room: ${myRoom}`;

    // --- UPDATED EMIT: Sending userId now ---
    socket.emit('join_game', { 
        room: room, 
        name: name, 
        userId: myUserId 
    });
});

// --- LOBBY ---
socket.on('lobby_update', (data) => {
    const players = data.players || [];
    ui.lobbyList.innerHTML = '';
    players.forEach(pName => {
        const li = document.createElement('li');
        li.innerText = pName === myName ? `${pName} (You)` : pName;
        ui.lobbyList.appendChild(li);
    });

    if (players.length >= 2) {
        ui.btnStart.classList.remove('hidden');
        ui.lobbyStatus.innerText = "Ready to begin.";
    } else {
        ui.btnStart.classList.add('hidden');
        ui.lobbyStatus.innerText = "Waiting for more players...";
    }
});

ui.btnStart.addEventListener('click', () => {
    socket.emit('start_game', {});
});

// --- GAME LOGIC ---
socket.on('game_update', (state) => {
    gameState = state;
    if (!screens.lobby.classList.contains('hidden')) {
        screens.lobby.classList.add('hidden');
        screens.game.classList.remove('hidden');
    }
    renderGame();
});

socket.on('game_over', (data) => {
    alert(data.message);
});

socket.on('error', (data) => {
    console.error(data);
    alert("Error: " + data.message);
});

function renderGame() {
    if (!gameState) return;

    // 1. HEADER INFO
    // Render Trump Card
    ui.trumpContainer.innerHTML = '';
    if (gameState.trump_card) {
        // Create a visual card for the trump
        const tCard = createCardElement(gameState.trump_card);
        ui.trumpContainer.appendChild(tCard);
    }

    ui.deckCount.innerText = gameState.deck_count;

    // Render Status Names
    ui.statAttacker.innerText = gameState.active_attacker_name || '-';
    ui.statDefender.innerText = gameState.defender_name || '-';

    // Status Pill (Center Table)
    let statusText = "";
    if (gameState.active_attacker_name === myName) statusText = "Your Turn to ATTACK";
    else if (gameState.defender_name === myName) statusText = "DEFEND YOURSELF";
    else statusText = `${gameState.active_attacker_name} is attacking...`;
    
    ui.status.innerText = statusText;
    ui.status.classList.remove('hidden');

    renderOpponents();
    renderTable();
    renderHand();
}

function renderOpponents() {
    ui.opponents.innerHTML = '';
    gameState.players.forEach(p => {
        if (p.is_me) return;
        
        const el = document.createElement('div');
        el.className = `opponent-card ${gameState.active_attacker_name === p.name || gameState.defender_name === p.name ? 'active' : ''}`;
        el.innerHTML = `
            <div class="opponent-avatar">${p.name.charAt(0).toUpperCase()}</div>
            <div style="font-size:0.8rem; color:white; margin-top:5px; font-weight:600; text-shadow:0 1px 2px black;">${p.name}</div>
            <div style="font-size:0.7rem; color:#cbd5e1; text-shadow:0 1px 2px black;">${p.card_count} cards</div>
        `;
        ui.opponents.appendChild(el);
    });
}

function renderTable() {
    ui.table.innerHTML = '';
    const defCards = gameState.table_defense || [];
    const attCards = gameState.table_attack || [];

    for (let i = 0; i < defCards.length; i += 2) {
        const attackC = defCards[i];
        const defendC = defCards[i+1];
        const group = document.createElement('div');
        group.className = 'card-group pair';
        group.appendChild(createCardElement(attackC));
        group.appendChild(createCardElement(defendC));
        ui.table.appendChild(group);
    }

    attCards.forEach(card => {
        const group = document.createElement('div');
        group.className = 'card-group';
        const cardEl = createCardElement(card);
        
        if (selectedTableCard && isSameCard(card, selectedTableCard)) {
            cardEl.classList.add('selected-target');
        }

        cardEl.onclick = () => {
            if (gameState.defender_name !== myName) return;
            selectedTableCard = (selectedTableCard && isSameCard(card, selectedTableCard)) ? null : card;
            renderTable();
        };

        group.appendChild(cardEl);
        ui.table.appendChild(group);
    });
}

function renderHand() {
    const me = gameState.players.find(p => p.is_me);
    ui.hand.innerHTML = '';
    if (!me || !me.hand) return;

    me.hand.forEach(card => {
        const el = createCardElement(card);
        if (selectedHandCard && isSameCard(card, selectedHandCard)) {
            el.classList.add('selected-hand');
        }
        el.onclick = () => {
            selectedHandCard = (selectedHandCard && isSameCard(card, selectedHandCard)) ? null : card;
            renderHand();
        };
        ui.hand.appendChild(el);
    });
}

function createCardElement(cardData) {
    const div = document.createElement('div');
    const isRed = ['♥', '♦'].includes(cardData.suit);
    div.className = `card ${isRed ? 'red' : 'black'}`;
    
    const suitChar = cardData.suit;
    // Safety check for display string
    const displayStr = cardData.display || ""; 
    const rankStr = displayStr.replace(suitChar, '');

    div.innerHTML = `
        <div class="card-top">${rankStr} <small>${suitChar}</small></div>
        <div class="card-center" style="font-size:2rem">${suitChar}</div>
        <div class="card-bottom" style="transform:rotate(180deg)">${rankStr} <small>${suitChar}</small></div>
    `;
    return div;
}

function isSameCard(c1, c2) {
    return c1.rank === c2.rank && c1.suit === c2.suit;
}

window.attemptAction = (action) => {
    if (action === 'skip') { socket.emit('skip', {}); resetSelection(); return; }
    if (action === 'take') { socket.emit('take', {}); resetSelection(); return; }

    if (['attack', 'pass'].includes(action)) {
        if (!selectedHandCard) return alert("Select a card from your hand first!");
        socket.emit(action, { rank: selectedHandCard.rank, suit: selectedHandCard.suit });
        resetSelection();
    }
    
    if (action === 'defend') {
        if (!selectedHandCard) return alert("Select a card from your hand.");
        if (!selectedTableCard) return alert("Select the attack card on the table.");
        socket.emit('defend', {
            attack_rank: selectedTableCard.rank,
            attack_suit: selectedTableCard.suit,
            defend_rank: selectedHandCard.rank,
            defend_suit: selectedHandCard.suit
        });
        resetSelection();
    }
};

function resetSelection() {
    selectedHandCard = null;
    selectedTableCard = null;
    renderGame();
}