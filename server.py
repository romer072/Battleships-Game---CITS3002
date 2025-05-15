# Step-by-step scaffold for Tier 3: Supporting spectators, multiple players, reconnection, rematch, and match announcements

import socket
import threading
import time
import zlib
from battleship import Board
import os

def log_event(message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    with open("match_log.txt", "a") as f:
        f.write(f"[{timestamp}] {message}\n")

PACKET_TYPE_FIRE = 0x01
PACKET_TYPE_SHOW = 0x02
PACKET_TYPE_QUIT = 0x03
PACKET_TYPE_ERROR = 0xFF

def build_packet(seq, pkt_type, payload):
    data = payload.encode()
    length = len(data)
    header = bytes([seq, pkt_type, length]) + data
    crc = zlib.crc32(header) & 0xFFFFFFFF  # 4-byte checksum
    return header + crc.to_bytes(4, 'big')

def parse_packet(packet):
    if len(packet) < 7:  # Minimum packet with 0-length payload and 4-byte CRC
        raise ValueError("Packet too short")
    seq = packet[0]
    pkt_type = packet[1]
    length = packet[2]
    expected_length = 3 + length + 4
    if len(packet) < expected_length:
        raise ValueError("Incomplete packet data")
    payload = packet[3:3+length].decode()
    received_crc = int.from_bytes(packet[3+length:expected_length], 'big')
    calculated_crc = zlib.crc32(packet[:3+length]) & 0xFFFFFFFF
    if received_crc != calculated_crc:
        raise ValueError("Checksum mismatch")
    return seq, pkt_type, payload

HOST = '0.0.0.0'
PORT = 12345
INACTIVITY_TIMEOUT = 30
RECONNECT_TIMEOUT = 60  # seconds

disconnected_players = {}  # name -> (disconnect_time, board, opponent_index, was_current_turn, game)

class GameState:
    def __init__(self, players, spectators, player_names):
        self.players = players  # [conn1, conn2]
        self.boards = [Board(), Board()]
        self.current_turn = 0
        self.spectators = spectators  # List of extra client sockets
        self.names = player_names
        self.lock = threading.Lock()
        self.reconnected = [False, False]

    def switch_turn(self):
        with self.lock:
            self.current_turn = 1 - self.current_turn

    def get_opponent_index(self, i):
        return 1 - i

# Broadcast a message to all spectators
    
def coord_to_indices(coord):
    """
    Converts coordinate like 'B5' to (1, 4)
    """
    try:
        row_letter = coord[0].upper()
        col_number = coord[1:]
        row = ord(row_letter) - ord('A')
        col = int(col_number) - 1
        return row, col
    except:
        raise ValueError("Invalid coordinate format.")

def broadcast_to_spectators(message, spectators):
    dead = []
    for sock in spectators:
        try:
            sock.sendall(f"[SPECTATOR] {message}\n".encode())
        except:
            dead.append(sock)
    for s in dead:
        spectators.remove(s)

# Announce new match

def broadcast_match_start(p1, p2, spectators):
    message = f"New match starting: {p1} vs {p2}!"
    broadcast_to_spectators(message, spectators)
    log_event(f"New match: {p1} vs {p2}")
    for sock in spectators:
        try:
            sock.sendall("Match will begin shortly...\n".encode())
        except:
            pass
    time.sleep(2)  # Optional countdown buffer

# Accept client names (optional improvement)
def receive_name(conn):
    conn.sendall("Enter your name:\n".encode())
    try:
        name = conn.recv(1024).decode().strip()
        if not name:
            name = "Anonymous"
        log_event(f"{name} connected.")
        return name
    except:
        return "Anonymous"

# Handle spectator input

def handle_spectator(conn, name):
    try:
        conn.sendall("You are now a spectator. Enjoy the game!\n".encode())
        while True:
            msg = conn.recv(1024).decode().strip()
            if not msg:
                break
            conn.sendall("[ERROR] You are a spectator. You cannot play.\n".encode())
    except:
        pass
    conn.close()

# Handle each active player

def handle_player(player_index, game: GameState, names):
    conn = game.players[player_index]
    opponent_index = game.get_opponent_index(player_index)
    board = game.boards[opponent_index]

    conn.sendall("Game started! You will be firing at your opponent's board.\n".encode())
    log_event(f"{names[player_index]} is now Player {player_index+1}.")

    while True:
        try:
            conn.settimeout(INACTIVITY_TIMEOUT)
            raw = conn.recv(1024)
            try:
                seq, pkt_type, payload = parse_packet(raw)
            except ValueError as e:
                conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, str(e)))
                continue

            if pkt_type == PACKET_TYPE_QUIT:
                conn.sendall(build_packet(seq, PACKET_TYPE_QUIT, "You quit. Game over."))
                game.players[opponent_index].sendall(build_packet(seq, PACKET_TYPE_QUIT, "Opponent quit. You win!"))
                log_event(f"{names[player_index]} quit.")
                break

            if pkt_type == PACKET_TYPE_SHOW:
                view = game.boards[player_index].render_display_grid()
                conn.sendall(build_packet(seq, PACKET_TYPE_SHOW, view))
                continue

            if pkt_type != PACKET_TYPE_FIRE:
                conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, "Invalid command."))
                continue

            if game.current_turn != player_index:
                conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, "Not your turn."))
                continue

            coord = payload
            if len(coord) < 2 or coord[0].upper() not in "ABCDEFGHIJ":
                conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, "Invalid FIRE format. Use: FIRE A1-J10"))
                continue

            row, col = coord_to_indices(coord)
            status, sunk = board.fire_at(row, col)
            result_msg = f"{status.upper()} — Sunk {sunk}" if sunk else status.upper()
            conn.sendall(build_packet(seq, PACKET_TYPE_FIRE, f"RESULT {result_msg}"))
            game.players[opponent_index].sendall(build_packet(seq, PACKET_TYPE_FIRE, f"{names[player_index]} fired at {coord}: {result_msg}"))
            broadcast_to_spectators(f"{names[player_index]} fired at {coord}: {result_msg}", game.spectators)
            log_event(f"{names[player_index]} fired at {coord}: {result_msg}")

            if status == 'hit' and board.all_ships_sunk():
                conn.sendall("You win!\nDo you want a rematch? (YES/NO)\n".encode())
                game.players[opponent_index].sendall("You lose!\nDo you want a rematch? (YES/NO)\n".encode())
                broadcast_to_spectators(f"{names[player_index]} won the game!", game.spectators)
                log_event(f"{names[player_index]} won. {names[opponent_index]} lost.")

                try:
                    answer1 = game.players[player_index].recv(1024).decode().strip().upper()
                    answer2 = game.players[opponent_index].recv(1024).decode().strip().upper()

                    if answer1 == "YES" and answer2 == "YES":
                        conn.sendall("Rematch starting!\n".encode())
                        game.players[opponent_index].sendall("Rematch starting!\n".encode())
                        game.boards = [Board(), Board()]
                        game.current_turn = 0
                        broadcast_to_spectators(f"Rematch starting: {names[0]} vs {names[1]}!", game.spectators)
                        log_event(f"Rematch accepted by both players.")
                        continue
                    else:
                        conn.sendall("Game over.\n".encode())
                        game.players[opponent_index].sendall("Game over.\n".encode())
                        log_event("Game session ended without rematch.")
                except:
                    pass
                break
            else:
                game.switch_turn()

        except socket.timeout:
            conn.sendall("Inactivity timeout. You forfeit your turn.\n".encode())
            game.players[opponent_index].sendall("Opponent timed out. Your turn.\n".encode())
            broadcast_to_spectators(f"{names[player_index]} timed out. Turn skipped.", game.spectators)
            log_event(f"{names[player_index]} timed out.")
            game.switch_turn()
            continue

        except Exception as e:
            print(f"[ERROR] Player {player_index+1}: {e}")
            now = time.time()
            disconnected_players[names[player_index]] = (now, game.boards, opponent_index, game.current_turn == player_index, game)
            log_event(f"{names[player_index]} disconnected.")
            break

    conn.close()

# Accept and organize incoming clients
def lobby_listener():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()

    print(f"[SERVER] Listening on {HOST}:{PORT}")

    clients = []
    names = []

    while True:
        conn, addr = server_socket.accept()
        print(f"[CONNECT] {addr}")
        name = receive_name(conn)

        # Check for reconnection
        if name in disconnected_players:
            dc_time, saved_boards, opponent_index, was_current_turn, game = disconnected_players[name]
            if time.time() - dc_time <= RECONNECT_TIMEOUT:
                print(f"[RECONNECT] {name} reconnected.")
                log_event(f"{name} reconnected.")
                player_index = opponent_index ^ 1
                game.players[player_index] = conn
                game.boards = saved_boards
                game.reconnected[player_index] = True
                broadcast_to_spectators(f"{name} has rejoined the game. 👋", game.spectators)
                t = threading.Thread(target=handle_player, args=(player_index, game, game.names))
                t.start()
                del disconnected_players[name]
                continue
            else:
                print(f"[REJECT] {name} expired reconnect window.")
                del disconnected_players[name]

        clients.append(conn)
        names.append(name)

        if len(clients) >= 2:
            players = clients[:2]
            spectators = clients[2:]
            player_names = names[:2]

            game = GameState(players, spectators, player_names)
            broadcast_match_start(player_names[0], player_names[1], spectators)

            for idx in range(2):
                players[idx].sendall(f"You are Player {idx+1} ({player_names[idx]})\n".encode())

            # Start player threads
            t1 = threading.Thread(target=handle_player, args=(0, game, player_names))
            t2 = threading.Thread(target=handle_player, args=(1, game, player_names))
            t1.start()
            t2.start()

            # Start spectator threads
            for i, spec_conn in enumerate(spectators):
                t = threading.Thread(target=handle_spectator, args=(spec_conn, names[i+2]))
                t.start()

            t1.join()
            t2.join()

            # After game ends: remove those 2 from lists
            for p in players:
                if p in clients:
                    clients.remove(p)
            for n in player_names:
                if n in names:
                    names.remove(n)

if __name__ == '__main__':
    lobby_listener()
