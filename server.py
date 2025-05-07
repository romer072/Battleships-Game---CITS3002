# """
# server.py

# Serves a single-player Battleship session to one connected client.
# Game logic is handled entirely on the server using battleship.py.
# Client sends FIRE commands, and receives game feedback.

# TODO: For Tier 1, item 1, you don't need to modify this file much. 
# The core issue is in how the client handles incoming messages.
# However, if you want to support multiple clients (i.e. progress through further Tiers), you'll need concurrency here too.
# """

# import socket
# from battleship import run_single_player_game_online

# HOST = '127.0.0.1'
# PORT = 5000

# def main():
#     print(f"[INFO] Server listening on {HOST}:{PORT}")
#     with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#         s.bind((HOST, PORT))
#         s.listen(2)
#         conn, addr = s.accept()
#         print(f"[INFO] Client connected from {addr}")
#         with conn:
#             rfile = conn.makefile('r')
#             wfile = conn.makefile('w')
#             run_single_player_game_online(rfile, wfile)
#         print("[INFO] Client disconnected.")

# # HINT: For multiple clients, you'd need to:
# # 1. Accept connections in a loop
# # 2. Handle each client in a separate thread
# # 3. Import threading and create a handle_client function

# if __name__ == "__main__":
#     main()




import socket
import threading
import sys
import time
from battleship import Board  # You must already have this defined


class GameState:
    def __init__(self, p1_sock, p2_sock):
        self.players = [p1_sock, p2_sock]
        self.boards = [Board(), Board()]
        self.current_turn = 0  # 0: player 1, 1: player 2
        self.lock = threading.Lock()

    def switch_turn(self):
        with self.lock:
            self.current_turn = 1 - self.current_turn

    def get_opponent_index(self, i):
        return 1 - i

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

# --- Step 1: Helper to validate coordinates ---
def is_valid_coord(coord):
    if len(coord) < 2:
        return False
    row = coord[0].upper()
    col = coord[1:]
    return row in "ABCDEFGHIJ" and col.isdigit() and 1 <= int(col) <= 10

# --- Step 2: Start and restart games ---
def start_game(game):
    for idx in range(MAX_PLAYERS):
        game.players[idx].sendall(f"You are Player {idx+1}\n".encode())
    time.sleep(1)

    threads = []
    for idx in range(MAX_PLAYERS):
        t = threading.Thread(target=handle_player, args=(idx, game))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()




# --- Step 3: Handle each player's session ---
def handle_player(player_index, game: GameState):
    conn = game.players[player_index]
    opponent_index = game.get_opponent_index(player_index)
    board = game.boards[opponent_index]

    conn.sendall("Game started! You will be firing at your opponent's board.\n".encode())

    while True:
        try:
            conn.settimeout(INACTIVITY_TIMEOUT)
            msg = conn.recv(1024).decode().strip()
            if not msg:
                raise ConnectionError("Empty message received")

            if msg.lower() == 'quit':
                conn.sendall("You quit. Game over.\n".encode())
                game.players[opponent_index].sendall("Opponent quit. You win!\n".encode())
                break

            if msg.upper() == 'SHOW':
                board_view = game.boards[player_index].render_display_grid()
                conn.sendall(board_view.encode())
                continue

            if not msg.startswith("FIRE"):
                conn.sendall("Invalid command. Use: FIRE <coord> or QUIT\n".encode())
                continue

            parts = msg.split()
            if len(parts) != 2 or not is_valid_coord(parts[1]):
                conn.sendall("Invalid FIRE format. Use: FIRE A1-J10\n".encode())
                continue

            if game.current_turn != player_index:
                conn.sendall("Not your turn.\n".encode())
                continue

            coord = parts[1]
            row, col = coord_to_indices(coord)
            status, sunk = board.fire_at(row, col)
            result_msg = f"{status.upper()} — Sunk {sunk}" if sunk else status.upper()

            conn.sendall(f"RESULT {result_msg}\n".encode())
            game.players[opponent_index].sendall(
                f"Opponent fired at {coord}: {result_msg}\n".encode())

            if status == 'hit' and board.all_ships_sunk():
                conn.sendall("You win!\n".encode())
                game.players[opponent_index].sendall("You lose!\n".encode())
                break
            else:
                game.switch_turn()

        except socket.timeout:
            conn.sendall("Inactivity timeout. You forfeit your turn.\n".encode())
            game.players[opponent_index].sendall("Opponent timed out. Your turn.\n".encode())
            game.switch_turn()
            continue

        except Exception as e:
            print(f"[ERROR] Player {player_index+1}: {e}")
            try:
                game.players[opponent_index].sendall("Opponent disconnected. You win!\n".encode())
            except:
                pass
            break

    conn.close()

# --- Step 4: Accept incoming players and handle games ---
def lobby_listener():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()

    print(f"[SERVER] Listening on {HOST}:{PORT}")

    waiting_players = []
    while True:
        conn, addr = server_socket.accept()
        print(f"[CONNECT] Player joined from {addr}")

        if len(waiting_players) >= MAX_PLAYERS:
            conn.sendall("Server full. Please try again later.\n".encode())
            conn.close()
            continue

        waiting_players.append(conn)

        if len(waiting_players) == MAX_PLAYERS:
            game = GameState(waiting_players)
            start_game(game)
            waiting_players.clear()

if __name__ == '__main__':
    lobby_listener()
