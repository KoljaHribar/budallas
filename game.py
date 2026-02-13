import random # used for shuffling the deck
from enum import Enum # used for comparing ranks (with constants)
from typing import List, Optional, Tuple # used for type hints (code clarity)

"""
Enum -> prevents Suit.HEARTS = "Banana", suits and ranks fixed as they are
"""
class Suit(Enum):
    HEARTS = '♥'
    DIAMONDS = '♦'
    CLUBS = '♣'
    SPADES = '♠'

class Rank(Enum):
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

class Card:
    def __init__(self, rank: Rank, suit: Suit):
        self.rank = rank
        self.suit = suit

    def __repr__(self):
        # Maps strict enum values to display strings (e.g., 11 -> J)
        rank_str = {11: 'J', 12: 'Q', 13: 'K', 14: 'A'}.get(self.rank.value, str(self.rank.value)) # dict.get(val to find in dict, val if not found)
        return f"{rank_str}{self.suit.value}"

    def __eq__(self, other):
        # Allows us to compare two card objects using '=='
        return self.rank == other.rank and self.suit == other.suit

class Deck:
    def __init__(self):
        self.cards: List[Card] = []
        self.trump_card: Optional[Card] = None # var to remember which card is the "Trump"
        self._initialize_deck()

    def _initialize_deck(self):
        # Helper method to create the standard 36-card Budallas deck.
        for suit in Suit:
            for rank in Rank:
                self.cards.append(Card(rank, suit))
        random.shuffle(self.cards) # shuffles the deck

    def setup_trump(self):
        # A card is placed face up under the deck indicating trump
        if self.cards:
            self.trump_card = self.cards[0] # card at the bottom (index 0), last to be picked up

    def draw(self, count: int) -> List[Card]:
        """
        Removes cards from the top of the deck and returns them to a player.
        count: How many cards the player needs.
        """
        drawn = []
        for _ in range(count):
            if not self.cards: # if deck empty, stop draw
                break
            drawn.append(self.cards.pop())  # adds card to drawn list
        return drawn

    def is_empty(self):
        return len(self.cards) == 0

class Player:
    def __init__(self, name: str):
        self.name = name
        self.hand: List[Card] = [] # player's hand

    def take_cards(self, cards: List[Card]):
        self.hand.extend(cards) # add the card to hand
        self.hand.sort(key=lambda c: c.rank.value) # look at every cards' ranks and sort them

    def has_card(self, card: Card):
        return card in self.hand # uses __eq__ to see if player holds a specific card (so player doesn't play card if he doesn't have it)

    def remove_card(self, card: Card):
        self.hand.remove(card) # Removes a card from the player's hand (when playing it)

class Game:
    def __init__(self, player_names: List[str]):
        if len(player_names) < 2:
            raise ValueError("Game requires at least 2 players.") # min 2 players
            
        if len(player_names) > 5:
            raise ValueError("Game supports a maximum of 5 players.") # max 5 players
        
        self.deck = Deck() # creates and shuffles 36 cards
        self.deck.setup_trump() # indicate the trump suit
        self.trump_suit = self.deck.trump_card.suit # store suit to check later quicker
        
        self.players = [Player(name) for name in player_names]
        self.discard_pile: List[Card] = [] # Cards removed from play
        self.table_attack: List[Card] = [] # Cards currently attacking
        self.table_defense: List[Card] = [] # Cards currently defending (paired)
        
        # Track Whose Turn It Is
        self.attacker_idx = 0  # main attacker
        self.defender_idx = (self.attacker_idx + 1) % len(self.players) # player on left is the defender (% is for player[len] to attack player[0])
        
        self.active_attacker_idx = self.attacker_idx # initial attacker is active (you have to attack as a primary attacker)

        self.skipped_count = 0

        # Each player is dealt 6 cards
        for p in self.players:
            p.take_cards(self.deck.draw(6))

    @property # to always check the attack limit
    def current_attack_limit(self):
        # Limits: 5 if dis deck empty, 6 if not, but n if player has n cards in hand
        defender = self.players[self.defender_idx]
        base_limit = 6 if len(self.discard_pile) > 0 else 5
        
        # Each defense adds 2 cards (attack + defense) to table_defense
        defended_pairs_count = len(self.table_defense) // 2
        
        return min(base_limit - defended_pairs_count, len(defender.hand))

    def attack(self, card: Card, player: Player):
        self.skipped_count = 0
        # The primary attacker starts. If they pass, it goes to the left.
        if player != self.players[self.active_attacker_idx]:
             raise ValueError(f"It is not {player.name}'s turn to attack.")

        if player == self.players[self.defender_idx]:
            raise ValueError("The defender cannot attack.") # skips defender when asking for attackers

        if not player.has_card(card):
            raise ValueError("Player does not have this card.") # prevent illegal moves
        
        # To attack again there must be a card of the same value on table.
        if self.table_attack or self.table_defense:
            valid_ranks = {c.rank for c in self.table_attack + self.table_defense}
            if card.rank not in valid_ranks:
                raise ValueError("Card rank must match cards already on table.") # if card isn't on table, can't attack with it

        if len(self.table_attack) >= self.current_attack_limit:
            raise ValueError("Attack limit reached.") # can't attack if limit reached

        player.remove_card(card)
        self.table_attack.append(card)
        print(f"{player.name} attacks with {card}")

    def defend(self, attack_card: Card, defense_card: Card, player: Player):
        self.skipped_count = 0
        if player != self.players[self.defender_idx]:
            raise ValueError(f"{player.name} is not the defender!") # only defender defends
        
        if not player.has_card(defense_card):
            raise ValueError("Defender does not have this card.") # prevents illegal moves
        
        if attack_card not in self.table_attack:
            raise ValueError("That card is not currently attacking.") # if card isn't on table, can't defend it

        # check if attack or defend card is trump
        is_trump_defense = defense_card.suit == self.trump_suit
        is_trump_attack = attack_card.suit == self.trump_suit

        winning = False
        if attack_card.suit == defense_card.suit: # if cards same suit
            if defense_card.rank.value > attack_card.rank.value: # if defense higher
                winning = True
        elif is_trump_defense and not is_trump_attack: # if defense trump and attack isn't
            winning = True
            
        if not winning:
            raise ValueError("Defense card does not beat the attack card.") # can't beat attack with lower defense

        player.remove_card(defense_card)
        self.table_attack.remove(attack_card) # remove attack card from active attack
        self.table_defense.extend([attack_card, defense_card]) # put both cards in defended state (others can still put same card in attack)
        print(f"{player.name} defends {attack_card} with {defense_card}")

    def skip_attack_turn(self, player: Player):
        if player != self.players[self.active_attacker_idx]:
             raise ValueError(f"It is not {player.name}'s turn to skip.")

        # Primary Attacker cannot skip if table is empty (must play first card)
        is_primary = (self.active_attacker_idx == self.attacker_idx)
        is_table_empty = (len(self.table_attack) == 0 and len(self.table_defense) == 0)
        if is_primary and is_table_empty:
            raise ValueError("Primary attacker cannot skip. You must play at least one card.")

        print(f"{player.name} passes their attack turn.")
        
        # --- NEW LOGIC START ---
        self.skipped_count += 1
        
        # Calculate how many "attackers" exist (Total players - 1 defender)
        # (We count active players only, but for simplicity, total players - 1 is usually safe 
        # unless someone ran out of cards mid-round. Let's rely on active players count).
        active_attacker_count = len([p for p in self.players if p != self.players[self.defender_idx] and len(p.hand) > 0])
        
        # If everyone has skipped consecutively
        if self.skipped_count >= active_attacker_count:
            print("All attackers have passed. Round ending...")
            if len(self.table_attack) == 0:
                self.end_turn(success=True)
            else:
                print(f"Attackers done. {self.players[self.defender_idx].name} must defend or take.")
            
            # Reset for next phase
            self.active_attacker_idx = self.attacker_idx
            self.skipped_count = 0
            return
        # --- NEW LOGIC END ---

        # Otherwise, pass priority to the next eligible attacker
        start_idx = self.active_attacker_idx
        current_search_idx = (start_idx + 1) % len(self.players)
        found_new_attacker = False

        while current_search_idx != start_idx:
            p_obj = self.players[current_search_idx]
            is_defender = (current_search_idx == self.defender_idx)
            has_cards = (len(p_obj.hand) > 0)
            
            if not is_defender and has_cards:
                self.active_attacker_idx = current_search_idx
                found_new_attacker = True
                break
            current_search_idx = (current_search_idx + 1) % len(self.players)

        # If we couldn't find anyone else (rare edge case where skipped_count logic didn't catch it), end turn
        if not found_new_attacker:
             self.end_turn(success=True)
             return
        
        print(f"Now it is {self.players[self.active_attacker_idx].name}'s turn to attack.")

    def pass_attack(self, pass_card: Card, player: Player):
        self.skipped_count = 0
        if player != self.players[self.defender_idx]:
             raise ValueError("Only the defender can pass the attack.") # only defender can pass
        
        if self.table_defense:
            raise ValueError("Cannot pass after starting defense.") # can't pass if cards already defended
            
        if not player.has_card(pass_card):
             raise ValueError("Do not have that card.") # can't pass card if the user doesn't have it

        if not all(c.rank == pass_card.rank for c in self.table_attack):
             raise ValueError("Can only pass with card matching current attack rank.") # can't pass card of different rank

        # check if next defender can take it
        next_defender_idx = self._find_next_active_player(self.defender_idx)
        next_defender = self.players[next_defender_idx]
        total_attack_count = len(self.table_attack) + 1 # Current attack cards + the card being used to pass
        
        if len(next_defender.hand) < total_attack_count:
            raise ValueError("Cannot pass: Next player has too few cards.") # can't pass if next defender lacks cards

        player.remove_card(pass_card)
        self.table_attack.append(pass_card)
        
        print(f"{player.name} passes with {pass_card}")
        # rotating manually
        self.attacker_idx = self.defender_idx 
        self.defender_idx = next_defender_idx
        self.active_attacker_idx = self.attacker_idx

    def _find_next_active_player(self, start_idx: int) -> int:
        # Finds the index of the next player who still has cards in their hand.
        n = len(self.players)
        current_idx = (start_idx + 1) % n
        
        while len(self.players[current_idx].hand) == 0 and current_idx != start_idx:
            current_idx = (current_idx + 1) % n # Loop until we find someone with cards OR we circle back to start
            
        return current_idx

    def end_turn(self, success: bool):
        defender = self.players[self.defender_idx] # set defender
        
        if success:
            print("Defense Successful. Round End.")
            self.discard_pile.extend(self.table_attack + self.table_defense) # put defense and attack in discard
            self.table_attack = [] # reset
            self.table_defense = []# reset
            
            self._refill_hands() # refill hands
            
            self.attacker_idx = self.defender_idx # defender becomes attacker
            self.defender_idx = self._find_next_active_player(self.attacker_idx) # the one on their left is now defender

            self.active_attacker_idx = self.attacker_idx
            
        else:
            print("Defense Failed. Defender picks up.")
            all_table_cards = self.table_attack + self.table_defense
            defender.take_cards(all_table_cards) # defender picks up all cards on table
            self.table_attack = [] # reset
            self.table_defense = [] # reset
            
            self._refill_hands() # refill hands
            
            # Defender loses turn to attack
            self.attacker_idx = self._find_next_active_player(self.defender_idx) # player to left of defender becomes new attacker
            self.defender_idx = self._find_next_active_player(self.attacker_idx) # player to left of them becomes new defender

            self.active_attacker_idx = self.attacker_idx

    def _refill_hands(self):
        # Order is Defender, then Attacker, then others
        play_order = []
        
        # 1. Defender
        play_order.append(self.players[self.defender_idx])
        
        # 2. Attacker
        play_order.append(self.players[self.attacker_idx])
        
        # 3. Rest of players
        n = len(self.players)
        for i in range(1, n):
            # Calculate index starting from attacker
            p_idx = (self.attacker_idx + i) % n
            p = self.players[p_idx]
            if p not in play_order:
                play_order.append(p) # add every player in their correct position in the order

        for p in play_order:
            needed = 6 - len(p.hand)
            if needed > 0 and not self.deck.is_empty():
                p.take_cards(self.deck.draw(needed)) # refill hand only if needed and if possible

    def action_take(self, player: Player):
        # Allows the defender to give up and take all cards on the table.
        # Security Check: Only the defender can take
        if player != self.players[self.defender_idx]:
             raise ValueError(f"Only the defender ({self.players[self.defender_idx].name}) can decide to take cards.")

        # Validation: Can't take if there are no cards to take
        if not self.table_attack:
            raise ValueError("There are no cards on the table to take.")

        # Trigger the 'Loss' condition
        print(f"{player.name} decides to take the cards.")
        self.end_turn(success=False)

    def check_loser(self, last_defender: Optional[Player] = None):
        # Game ends when deck empty and 1 player left.
        if not self.deck.is_empty():
            return None # no endgame with a present deck
            
        active_players = [p for p in self.players if len(p.hand) > 0] # keep track of players with cards
        
        if len(active_players) == 1:
            return f"Game Over! The Budala is {active_players[0].name}" # last one standing is the "budala"
        
        if len(active_players) == 0:
            # Use the person passed in, OR fallback to current defender if not provided
            loser = last_defender if last_defender else self.players[self.defender_idx]
            return f"Game Over! The Budala is {loser.name} (Defended last)"
        return None # If there are multiple people with cards, the game keeps going