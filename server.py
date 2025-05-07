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


def setup_server(host='0.0.0.0', port=12345):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(2)
    print(f"[SERVER] Listening on {host}:{port}")
    return server


def wait_for_players(server):
    players = []
    while len(players) < 2:
        conn, addr = server.accept()
        print(f"[CONNECT] Player {len(players)+1} joined from {addr}")
        conn.sendall(f"You are Player {len(players)+1}\n".encode())
        players.append(conn)
    return players

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


def handle_player(player_index, game: GameState):
    conn = game.players[player_index]
    opponent_index = game.get_opponent_index(player_index)
    board = game.boards[opponent_index]

    conn.sendall("Game started! You will be firing at your opponent's board.\n".encode())

    while True:
        try:
            msg = conn.recv(1024).decode().strip()
            if not msg:
                print(f"[DISCONNECT] Player {player_index+1} disconnected.")
                break

            if msg.lower() == 'quit':
                conn.sendall("You quit. Game over.\n".encode())
                game.players[opponent_index].sendall("Opponent quit. You win!\n".encode())
                break

            if game.current_turn != player_index:
                conn.sendall("Not your turn.\n".encode())
                continue

            if msg.upper() == "SHOW":
                board_view = game.boards[player_index].render_display_grid()
                conn.sendall(board_view.encode())
                continue

            if msg.startswith("FIRE"):
                parts = msg.split()
                if len(parts) != 2:
                    conn.sendall("Usage: FIRE <coord>\n".encode())
                    continue

                coord = parts[1]
                try:
                    row, col = coord_to_indices(coord)
                    status, sunk = board.fire_at(row, col)
                except Exception:
                    conn.sendall(f"Invalid coordinate: {coord}\n".encode())
                    continue

                # Format result message
                if sunk:
                    result_msg = f"{status.upper()} — Sunk {sunk}"
                else:
                    result_msg = status.upper()

                # Send result to player
                conn.sendall(f"RESULT {result_msg}\n".encode())
                # Notify opponent
                game.players[opponent_index].sendall(
                    f"Opponent fired at {coord}: {result_msg}\n".encode()
                )

                # ✅ ONLY declare win if it was a hit AND all ships are sunk
                if status == 'hit' and board.all_ships_sunk():
                    conn.sendall("You win!\n".encode())
                    game.players[opponent_index].sendall("You lose!\n".encode())
                    break
                else:
                    game.switch_turn()

            else:
                conn.sendall("Invalid command. Use: FIRE <coord> or QUIT\n".encode())

        except Exception as e:
            print(f"[ERROR] With Player {player_index+1}: {e}")
            break

    conn.close()


def main():
    server = setup_server()
    players = wait_for_players(server)
    game = GameState(players[0], players[1])

    threads = []
    for i in range(2):
        t = threading.Thread(target=handle_player, args=(i, game))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("[SERVER] Game over. Server shutting down.")
    server.close()


if __name__ == '__main__':
    main()
