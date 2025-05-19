#!/usr/bin/env python3
"""
A debugging wrapper for server.py with added logging
"""

import socket
import threading
import time
import zlib
import sys
import traceback
from battleship import Board

# === Constants ===
HOST = '0.0.0.0'
PORT = 12345
INACTIVITY_TIMEOUT = 300  # Increased for debugging
RECONNECT_TIMEOUT = 60

# === Packet Types ===
PACKET_TYPE_JOIN = 0x00
PACKET_TYPE_FIRE = 0x01
PACKET_TYPE_SHOW = 0x02
PACKET_TYPE_QUIT = 0x03
PACKET_TYPE_ERROR = 0xFF
PACKET_TYPE_CHAT = 0x04

# === Packet Helpers ===
def build_packet(seq, pkt_type, payload):
    data = payload.encode()
    if len(data) > 255:
        print(f"[ERROR] Payload too long: {len(data)} bytes")
        raise ValueError("Payload too long for packet format")
    header = bytes([seq & 0xFF, pkt_type & 0xFF, len(data) & 0xFF]) + data
    crc = zlib.crc32(header) & 0xFFFFFFFF
    packet = header + crc.to_bytes(4, 'big')
    print(f"[DEBUG] Sending packet: type={pkt_type}, seq={seq}, len={len(data)}, payload={payload[:50]}...")
    return packet

# Helper to send a board in multiple packets if needed
def send_board_in_chunks(conn, seq, board_str):
    max_payload = 255 - 5  # Reserve 5 bytes for 'MORE\n' or 'LAST\n'
    chunks = [board_str[i:i+max_payload] for i in range(0, len(board_str), max_payload)]
    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        prefix = 'LAST\n' if is_last else 'MORE\n'
        payload = prefix + chunk
        conn.sendall(build_packet(seq, PACKET_TYPE_SHOW, payload))
        print(f"[DEBUG] Sent board chunk {i+1}/{len(chunks)} (is_last={is_last})")

def parse_packet(sock):
    try:
        header = sock.recv(3)
        if len(header) < 3:
            print(f"[ERROR] Incomplete header: {len(header)} bytes received")
            raise ValueError("Incomplete header")
            
        seq, pkt_type, length = header
        print(f"[DEBUG] Received header: seq={seq}, type={pkt_type}, length={length}")
        
        payload = b''
        while len(payload) < length:
            chunk = sock.recv(length - len(payload))
            if not chunk:
                print(f"[ERROR] Incomplete payload: expected {length}, got {len(payload)}")
                raise ValueError("Incomplete payload")
            payload += chunk
            
        crc_bytes = sock.recv(4)
        if len(crc_bytes) < 4:
            print(f"[ERROR] Incomplete CRC: {len(crc_bytes)} bytes received")
            raise ValueError("Incomplete CRC")
            
        packet = header + payload
        received_crc = int.from_bytes(crc_bytes, 'big')
        calculated_crc = zlib.crc32(packet) & 0xFFFFFFFF
        
        if received_crc != calculated_crc:
            print(f"[ERROR] Checksum mismatch: received={received_crc}, calculated={calculated_crc}")
            raise ValueError("Checksum mismatch")
            
        payload_str = payload.decode()
        print(f"[DEBUG] Successfully parsed packet: type={pkt_type}, seq={seq}, payload={payload_str}")
        return seq, pkt_type, payload_str
    except Exception as e:
        print(f"[ERROR] Exception in parse_packet: {e}")
        traceback.print_exc()
        raise e

# === Game State ===
class GameState:
    def __init__(self, players, spectators, names):
        self.players = players
        self.boards = [Board(), Board()]
        for i in range(2):
            self.boards[i].place_ships_randomly()
            print(f"[DEBUG] Placed ships for player {i+1} ({names[i]})")
        self.current_turn = 0
        self.names = names
        self.spectators = spectators
        self.lock = threading.Lock()
        print(f"[INFO] Game initialized with players: {names}")

    def switch_turn(self):
        with self.lock:
            self.current_turn = 1 - self.current_turn
            print(f"[INFO] Switched turn to player {self.current_turn+1} ({self.names[self.current_turn]})")

    def get_opponent_index(self, i):
        return 1 - i

# === Broadcasts ===
def broadcast_to_all(game, msg):
    packet = build_packet(0, PACKET_TYPE_CHAT, msg)
    print(f"[INFO] Broadcasting: {msg}")
    for i, conn in enumerate(game.players + game.spectators):
        try:
            recipient = f"player {i+1}" if i < len(game.players) else f"spectator {i+1-len(game.players)}"
            print(f"[DEBUG] Sending broadcast to {recipient}")
            conn.sendall(packet)
        except Exception as e:
            print(f"[ERROR] Failed to send broadcast to recipient {i}: {e}")
            continue

# === Connection Handling ===
reconnect_pool = {}

def handle_player(player_idx, game):
    conn = game.players[player_idx]
    opp_idx = game.get_opponent_index(player_idx)
    board = game.boards[opp_idx]
    name = game.names[player_idx]

    print(f"[INFO] Starting handler for player {player_idx+1} ({name})")
    
    try:
        welcome_msg = f"Game started! You are playing against {game.names[opp_idx]}. Fire away."
        conn.sendall(build_packet(0, PACKET_TYPE_CHAT, welcome_msg))
        
        while True:
            try:
                print(f"[DEBUG] Waiting for packet from player {player_idx+1} ({name})")
                conn.settimeout(INACTIVITY_TIMEOUT)
                seq, pkt_type, payload = parse_packet(conn)
                print(f"[INFO] Received packet from {name}: type={pkt_type}, payload={payload}")

                if pkt_type == PACKET_TYPE_QUIT:
                    print(f"[INFO] Player {player_idx+1} ({name}) quit")
                    conn.sendall(build_packet(seq, PACKET_TYPE_QUIT, "You quit."))
                    game.players[opp_idx].sendall(build_packet(seq, PACKET_TYPE_CHAT, f"{name} quit. You win!"))
                    break

                elif pkt_type == PACKET_TYPE_SHOW:
                    print(f"[INFO] Player {player_idx+1} ({name}) requested board")
                    view = game.boards[player_idx].render_display_grid()
                    # Use chunked sending if needed
                    if len(view.encode()) > 255:
                        send_board_in_chunks(conn, seq, view)
                    else:
                        conn.sendall(build_packet(seq, PACKET_TYPE_SHOW, view))

                elif pkt_type == PACKET_TYPE_CHAT:
                    print(f"[INFO] Chat from player {player_idx+1} ({name}): {payload}")
                    broadcast_to_all(game, f"[{name}]: {payload}")

                elif pkt_type == PACKET_TYPE_FIRE:
                    print(f"[INFO] Fire command from player {player_idx+1} ({name}): {payload}")
                    
                    if game.current_turn != player_idx:
                        print(f"[INFO] Not {name}'s turn (current turn: {game.names[game.current_turn]})")
                        conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, "Not your turn."))
                        continue
                        
                    try:
                        row = ord(payload[0].upper()) - ord('A')
                        col = int(payload[1:]) - 1
                        print(f"[DEBUG] Parsed coordinates: row={row}, col={col}")
                        result, sunk = board.fire_at(row, col)
                        print(f"[DEBUG] Fire result: {result}, sunk={sunk}")
                        
                        msg = f"{result.upper()} — Sunk {sunk}" if sunk else result.upper()
                        conn.sendall(build_packet(seq, PACKET_TYPE_FIRE, f"RESULT {msg}"))
                        game.players[opp_idx].sendall(build_packet(seq, PACKET_TYPE_FIRE, f"{name} fired at {payload}: {msg}"))
                        broadcast_to_all(game, f"{name} fired at {payload}: {msg}")
                        
                        if result == 'hit' and board.all_ships_sunk():
                            print(f"[INFO] Player {player_idx+1} ({name}) won!")
                            conn.sendall(build_packet(seq, PACKET_TYPE_CHAT, "You win!"))
                            game.players[opp_idx].sendall(build_packet(seq, PACKET_TYPE_CHAT, "You lose!"))
                            break
                        else:
                            game.switch_turn()
                    except Exception as e:
                        print(f"[ERROR] Error processing fire command: {e}")
                        traceback.print_exc()
                        conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, f"Invalid FIRE format: {e}"))

                else:
                    print(f"[WARNING] Unknown packet type {pkt_type} from {name}")
                    conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, f"Unknown command (type {pkt_type})."))

            except socket.timeout:
                print(f"[INFO] Timeout from player {player_idx+1} ({name})")
                conn.sendall(build_packet(0, PACKET_TYPE_ERROR, "Timeout. You forfeit your turn."))
                game.players[opp_idx].sendall(build_packet(0, PACKET_TYPE_CHAT, f"{name} timed out."))
                game.switch_turn()

            except Exception as e:
                print(f"[ERROR] Exception in player handler for {name}: {e}")
                traceback.print_exc()
                reconnect_pool[name] = (game.boards, opp_idx, game)
                print(f"[INFO] Added {name} to reconnect pool")
                break

    except Exception as outer:
        print(f"[ERROR] Outer exception for {name}: {outer}")
        traceback.print_exc()

    print(f"[INFO] Player {player_idx+1} ({name}) handler ending, closing connection")
    conn.close()

def receive_name(conn):
    try:
        print("[DEBUG] Waiting for JOIN packet")
        seq, pkt_type, payload = parse_packet(conn)
        if pkt_type == PACKET_TYPE_JOIN:
            name = payload.strip() or "Anonymous"
            print(f"[INFO] Received name '{name}'")
            return name
        else:
            print(f"[WARNING] Expected JOIN packet, got type {pkt_type}")
            conn.sendall(build_packet(seq, PACKET_TYPE_ERROR, "Expected JOIN packet"))
            return "Anonymous"
    except Exception as e:
        print(f"[ERROR] Error receiving name: {e}")
        traceback.print_exc()
        return "Anonymous"

def lobby():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(5)
    print(f"[SERVER] Listening on {HOST}:{PORT}")

    waiting = []
    names = []

    while True:
        print("[SERVER] Waiting for connection...")
        conn, addr = s.accept()
        print(f"[SERVER] New connection from {addr}")
        
        name = receive_name(conn)
        print(f"[CONNECT] {name} from {addr}")

        if name in reconnect_pool:
            print(f"[INFO] {name} is reconnecting")
            boards, opponent_idx, old_game = reconnect_pool[name]
            old_game.players[opponent_idx ^ 1] = conn
            old_game.boards = boards
            del reconnect_pool[name]
            t = threading.Thread(target=handle_player, args=(opponent_idx ^ 1, old_game))
            t.start()
            continue

        waiting.append(conn)
        names.append(name)
        print(f"[INFO] Added {name} to waiting list. Current waiting: {len(waiting)}")

        if len(waiting) >= 2:
            print(f"[INFO] Starting game with {names[:2]}")
            players = waiting[:2]
            spectators = waiting[2:]
            player_names = names[:2]
            game = GameState(players, spectators, player_names)

            for i in range(2):
                players[i].sendall(build_packet(0, PACKET_TYPE_CHAT, f"You are Player {i+1} ({player_names[i]})"))
            threading.Thread(target=handle_player, args=(0, game)).start()
            threading.Thread(target=handle_player, args=(1, game)).start()

            waiting = waiting[2:]
            names = names[2:]
            print(f"[INFO] Game started. Remaining in waiting: {len(waiting)}")

if __name__ == '__main__':
    try:
        lobby()
    except Exception as e:
        print(f"[FATAL] Unhandled exception in main thread: {e}")
        traceback.print_exc()
        sys.exit(1) 