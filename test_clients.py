# test_tier2_validation_timeout.py — Tests Tier 2 input validation & timeout handling

import socket
import threading
import time

HOST = '127.0.0.1'
PORT = 12345

# Tier 2 command test sequences
# Player 1 will issue bad inputs and valid ones
# Player 2 will intentionally idle to trigger timeout
commands_p1 = [
    "HELLO",                # ❌ Invalid command
    "FIRE Z9",              # ❌ Invalid coordinate
    "FIRE A1",              # ✅ Valid move
    "FIRE A2",              # ❌ Not your turn (if turn-based enforced)
    "SHOW",                 # ✅ Board display
    "FIRE A10",             # Might be valid depending on ship layout
    "QUIT"                  # ✅ Graceful exit
]

# Player 2 does nothing to simulate timeout
commands_p2 = [
    "SHOW",                 # ✅ View board
    "WAIT",                 # ⏳ Deliberate wait
    "FIRE B2"               # Should be skipped due to timeout before reaching
]

def run_player(name, commands, delay=2):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        print(f"[{name}] Connected")

        def listen():
            try:
                while True:
                    data = sock.recv(4096).decode()
                    if not data:
                        break
                    for line in data.strip().split('\n'):
                        print(f"[{name} Received]: {line}")
            except:
                print(f"[{name}] Listener thread ended.")

        listener = threading.Thread(target=listen, daemon=True)
        listener.start()

        for cmd in commands:
            if cmd == "WAIT":
                print(f"[{name}] Intentionally waiting to trigger timeout...")
                time.sleep(35)  # Trigger server timeout (> 30s)
                continue
            time.sleep(delay)
            print(f"[{name}] Sending: {cmd}")
            sock.sendall((cmd + "\n").encode())

        time.sleep(10)
        sock.close()
    except Exception as e:
        print(f"[{name}] Error: {e}")

# Start both players
p1 = threading.Thread(target=run_player, args=("Player 1", commands_p1))
p2 = threading.Thread(target=run_player, args=("Player 2", commands_p2))

p1.start()
p2.start()

p1.join()
p2.join()

print("\n✅ [Tier 2 Validation/Timeout Test Complete]")
