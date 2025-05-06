import socket
import threading
import time

HOST = '127.0.0.1'
PORT = 12345

def simulate_player(player_number, fire_coords):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        print(f"[Player {player_number}] Connected")

        def listen():
            while True:
                try:
                    data = sock.recv(1024).decode()
                    if not data:
                        break
                    print(f"[Player {player_number} Received]: {data.strip()}")
                except:
                    break

        # Start listener thread
        threading.Thread(target=listen, daemon=True).start()

        # Let game start
        time.sleep(2)

        for coord in fire_coords:
            print(f"[Player {player_number}] Sending: FIRE {coord}")
            sock.sendall(f"FIRE {coord}\n".encode())
            time.sleep(3)  # Give the other player time to respond

        time.sleep(2)
        sock.sendall(b"QUIT\n")
        sock.close()
    except Exception as e:
        print(f"[Player {player_number}] Error: {e}")

def main():
    # Player 1 fires at A1, A2
    # Player 2 fires at B1, B2
    player1_coords = ["A1", "A2"]
    player2_coords = ["B1", "B2"]

    t1 = threading.Thread(target=simulate_player, args=(1, player1_coords))
    t2 = threading.Thread(target=simulate_player, args=(2, player2_coords))

    t1.start()
    t2.start()

    t1.join()
    t2.join()
    print("[Test] Both players completed.")

if __name__ == '__main__':
    main()
