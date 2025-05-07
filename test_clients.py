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
                    for line in data.strip().split('\n'):
                        print(f"[Player {player_number} Received]: {line}")
                except:
                    break

        # Start background listener
        threading.Thread(target=listen, daemon=True).start()

        # Let server finish welcome message
        time.sleep(2)

        for coord in fire_coords:
            msg = f"FIRE {coord}"
            print(f"[Player {player_number}] Sending: {msg}")
            sock.sendall((msg + "\n").encode())
            time.sleep(3)  # Respect turn cycle

        # Send QUIT if still in game
        time.sleep(2)
        sock.sendall(b"QUIT\n")
        print(f"[Player {player_number}] Sent: QUIT")
        sock.close()

    except Exception as e:
        print(f"[Player {player_number}] Error: {e}")

def main():
    # Different test coordinates now!
    player1_coords = ["C3", "C4", "D4"]   # Pretend aiming for vertical ship
    player2_coords = ["F5", "G5", "H5"]   # Pretend aiming for horizontal ship

    # Give server a moment to get ready
    time.sleep(1)

    t1 = threading.Thread(target=simulate_player, args=(1, player1_coords))
    t2 = threading.Thread(target=simulate_player, args=(2, player2_coords))

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    print("\n✅ [Test Complete] All new moves have been executed.\n")

if __name__ == '__main__':
    main()
