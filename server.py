import socket         # Networking for TCP connections
import threading      # To handle multiple players at once
import time           # Used for timeouts and delays
import zlib           # For CRC32 checksum to verify packet integrity
from battleship import Board                # Board logic (not shown here)
from ship_placement import ShipPlacement    # Manages player's ship placement

# === Server Configuration ===
HOST = '0.0.0.0'                # Listen on all network interfaces
PORT = 12345                   # Port the server listens on
INACTIVITY_TIMEOUT = 30      # Time in seconds before disconnecting idle clients
RECONNECT_TIMEOUT = 60        # Time window allowed for clients to reconnect

# === Packet Type Constants (matches with client) ===
PACKET_TYPE_JOIN = 0x00        # Initial handshake: joining the game
PACKET_TYPE_FIRE = 0x01        # Player fires at a coordinate
PACKET_TYPE_SHOW = 0x02        # Request for the current board
PACKET_TYPE_QUIT = 0x03        # Player quits
PACKET_TYPE_ERROR = 0xFF       # Error message
PACKET_TYPE_CHAT = 0x04        # Chat message
PACKET_TYPE_PLACE = 0x05       # Player is placing a ship

# === Helper: Build a binary packet to send over the wire ===
def build_packet(seq, pkt_type, payload):
    data = payload.encode()
    if len(data) > 255:  # Protocol only supports 1-byte length
        raise ValueError("Payload too long for packet format")
    # Packet = [seq, type, length] + payload + crc32
    header = bytes([seq & 0xFF, pkt_type & 0xFF, len(data) & 0xFF]) + data
    crc = zlib.crc32(header) & 0xFFFFFFFF
    return header + crc.to_bytes(4, 'big')

# === Helper: If board is too big for one packet, split it into chunks ===
def send_board_in_chunks(conn, seq, board_str):
    max_payload = 255 - 5  # Reserve 5 bytes for prefix (MORE\n/LAST\n)
    chunks = [board_str[i:i+max_payload] for i in range(0, len(board_str), max_payload)]
    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        prefix = 'LAST\n' if is_last else 'MORE\n'
        payload = prefix + chunk
        conn.sendall(build_packet(seq, PACKET_TYPE_SHOW, payload))

# === Helper: Read a full packet from a socket ===
def parse_packet(sock):
    try:
        header = sock.recv(3)  # First 3 bytes: [seq, type, length]
        if len(header) < 3:
            raise ValueError("Incomplete header")
        seq, pkt_type, length = header

        # Read the payload of specified length
        payload = b''
        while len(payload) < length:
            chunk = sock.recv(length - len(payload))
            if not chunk:
                raise ValueError("Incomplete payload")
            payload += chunk

        # Read CRC checksum
        crc_bytes = sock.recv(4)
        if len(crc_bytes) < 4:
            raise ValueError("Incomplete CRC")

        # Validate CRC
        packet = header + payload
        received_crc = int.from_bytes(crc_bytes, 'big')
        calculated_crc = zlib.crc32(packet) & 0xFFFFFFFF
        if received_crc != calculated_crc:
            raise ValueError("Checksum mismatch")

        return seq, pkt_type, payload.decode()
    except Exception as e:
        raise e

# === GameState: Keeps track of each match ===
class GameState:
    def __init__(self, players, spectators, names):
        self.players = players                      # [Player 1 socket, Player 2 socket]
        self.placements = [ShipPlacement(), ShipPlacement()]  # One placement object per player
        self.current_turn = 0                       # 0 or 1, determines whose turn it is
        self.names = names                          # List of player names
        self.spectators = spectators                # List of additional connected viewers (not used fully)
        self.lock = threading.Lock()                # Lock for turn switching
        self.placement_phase = True                 # Phase flag: before game starts
        self.placement_complete = [False, False]    # Whether both players have placed all ships

    def switch_turn(self):
        with self.lock:
            self.current_turn = 1 - self.current_turn  # Toggle turn between 0 and 1

    def get_opponent_index(self, i):
        return 1 - i  # Return other player

    def check_placement_complete(self):
        return all(self.placement_complete)  # Game can only begin when both have finished placing

    def start_game(self):
        self.placement_phase = False
        broadcast_to_all(self, "Game started! Fire away.")  # Notify both players

# === Broadcast a message to all connected sockets ===
def broadcast_to_all(game, msg):
    packet = build_packet(0, PACKET_TYPE_CHAT, msg)
    for conn in game.players + game.spectators:
        try:
            conn.sendall(packet)
        except:
            continue  # Ignore any sockets that are already disconnected

# === Reconnection logic support ===
reconnect_pool = {}  # Stores reconnecting players: {name: (placements, idx, game)}

# === Handle a single player's communication ===
def handle_player(player_idx, game):
    # If player_idx >= len(game.players), this is a spectator
    is_spectator = player_idx >= len(game.players)
    if is_spectator:
        conn = game.spectators[player_idx - len(game.players)]
        name = game.names[player_idx]
    else:
        conn = game.players[player_idx]
        opp_idx = game.get_opponent_index(player_idx)
        placement = game.placements[player_idx]
        name = game.names[player_idx]

    try:
        # Instructional welcome message for new players
        if not is_spectator:
            welcome_msg = (
                "Welcome to Battleship! Place your ships using the format: place <coord> <H/V> <ship_name>\n"
                "Available ships: Carrier(5), Battleship(4), Cruiser(3), Submarine(3), Destroyer(2)\n"
                "Example: place A1 H Carrier"
            )
            conn.sendall(build_packet(0, PACKET_TYPE_CHAT, welcome_msg))

        # Main command loop for a player
        while True:
            try:
                conn.settimeout(INACTIVITY_TIMEOUT)
                seq, pkt_type, payload = parse_packet(conn)

                # === Handle Quit Command ===
                if pkt_type == PACKET_TYPE_QUIT:
                    conn.sendall(build_packet(seq, PACKET_TYPE_QUIT, "You quit."))
                    if not is_spectator:
                        game.players[opp_idx].sendall(build_packet(seq, PACKET_TYPE_CHAT, f"{name} quit. You win!"))
                    break

                # === Show Board Request ===
                elif pkt_type == PACKET_TYPE_SHOW:
                    if not is_spectator:
                        view = placement.get_board().render_display_grid()
                        if len(view.encode()) > 255:
                            send_board_in_chunks(conn, seq, view)
                        else:
                            conn.sendall(build_packet(seq, PACKET_TYPE_SHOW, view))

                # === Place Ship ===
                elif pkt_type == PACKET_TYPE_PLACE:
                    if is_spectator:
                        conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, "Spectators cannot place ships."))
                        continue
                    if not game.placement_phase:
                        conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, "Placement phase is over."))
                        continue
                    try:
                        parts = payload.split()
                        if len(parts) != 3:
                            raise ValueError("Invalid format. Use: place <coord> <H/V> <ship_name>")
                        coord, orientation, ship_name = parts
                        success, message = placement.place_ship(coord, orientation, ship_name)
                        if success:
                            conn.sendall(build_packet(seq, PACKET_TYPE_CHAT, message))
                            if placement.is_complete():
                                game.placement_complete[player_idx] = True
                                conn.sendall(build_packet(seq, PACKET_TYPE_CHAT, "All ships placed! Waiting for opponent..."))
                                if game.check_placement_complete():
                                    game.start_game()
                        else:
                            conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, message))
                    except Exception as e:
                        conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, f"Invalid placement: {str(e)}"))

                # === Chat ===
                elif pkt_type == PACKET_TYPE_CHAT:
                    broadcast_to_all(game, f"[{name}]: {payload}")

                # === Fire at Opponent ===
                elif pkt_type == PACKET_TYPE_FIRE:
                    if is_spectator:
                        conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, "Spectators cannot fire."))
                        continue
                    if game.placement_phase:
                        conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, "Game hasn't started yet. Place your ships first."))
                        continue
                    try:
                        row = ord(payload[0].upper()) - ord('A')
                        col = int(payload[1:]) - 1
                        result, sunk = game.placements[opp_idx].get_board().fire_at(row, col)
                        msg = f"{result.upper()} — Sunk {sunk}" if sunk else result.upper()

                        # Notify both players and spectators of result
                        conn.sendall(build_packet(seq, PACKET_TYPE_FIRE, f"RESULT {msg}"))
                        game.players[opp_idx].sendall(build_packet(seq, PACKET_TYPE_FIRE, f"{name} fired at {payload}: {msg}"))
                        broadcast_to_all(game, f"{name} fired at {payload}: {msg}")

                        # Check for win condition
                        if result == 'hit' and game.placements[opp_idx].get_board().all_ships_sunk():
                            conn.sendall(build_packet(seq, PACKET_TYPE_CHAT, "You win!"))
                            game.players[opp_idx].sendall(build_packet(seq, PACKET_TYPE_CHAT, "You lose!"))
                            break
                        else:
                            game.switch_turn()
                    except:
                        conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, "Invalid FIRE format."))

                else:
                    conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, "Unknown command."))

            except socket.timeout:
                if not is_spectator:
                    conn.sendall(build_packet(0, PACKET_TYPE_ERROR, "Timeout. You forfeit your turn."))
                    game.players[opp_idx].sendall(build_packet(0, PACKET_TYPE_CHAT, f"{name} timed out."))
                    game.switch_turn()

            except Exception as e:
                if not is_spectator:
                    reconnect_pool[name] = (game.placements, opp_idx, game)
                break  # Leave handler, assume disconnect

    except Exception as outer:
        print(f"[ERROR] {name}: {outer}")

    conn.close()
    if is_spectator:
        game.spectators.remove(conn)
        game.names.remove(name)

# === Extract player name from JOIN packet ===
def receive_name(conn):
    try:
        seq, pkt_type, payload = parse_packet(conn)
        if pkt_type == PACKET_TYPE_JOIN:
            return payload.strip() or "Anonymous"
        else:
            conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, "Expected JOIN packet"))
            return "Anonymous"
    except:
        return "Anonymous"

# === Main Lobby Thread: Accept connections and pair up players ===
def lobby():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Prevent address already in use
    s.bind((HOST, PORT))
    s.listen()
    print(f"[SERVER] Listening on {HOST}:{PORT}")

    waiting = []  # Clients waiting to be paired
    names = []
    current_game = None  # Track the current game

    while True:
        conn, addr = s.accept()
        name = receive_name(conn)
        print(f"[CONNECT] {name} from {addr}")

        # Reconnect player if found in reconnect pool
        if name in reconnect_pool:
            placements, opponent_idx, old_game = reconnect_pool[name]
            old_game.players[opponent_idx ^ 1] = conn
            old_game.placements = placements
            del reconnect_pool[name]
            t = threading.Thread(target=handle_player, args=(opponent_idx ^ 1, old_game))
            t.start()
            continue

        # If there's an active game, add new connection as spectator
        if current_game is not None:
            current_game.spectators.append(conn)
            current_game.names.append(name)
            t = threading.Thread(target=handle_player, args=(len(current_game.players), current_game))
            t.start()
            continue

        waiting.append(conn)
        names.append(name)

        # When 2 players are ready, start a game
        if len(waiting) == 2:
            players = waiting[:2]
            player_names = names[:2]
            current_game = GameState(players, [], player_names)  # Initialize with empty spectators list

            # Let each player know who they are
            for i in range(2):
                players[i].sendall(build_packet(0, PACKET_TYPE_CHAT, f"You are Player {i+1} ({player_names[i]})"))

            threading.Thread(target=handle_player, args=(0, current_game)).start()
            threading.Thread(target=handle_player, args=(1, current_game)).start()

            # Clear paired players from the queue
            waiting.clear()
            names.clear()

# === Entry Point ===
if __name__ == '__main__':
    lobby()  # Start server and begin accepting clients