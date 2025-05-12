# test_tier3_spectator_reconnect.py — Automated test for Tier 3 multiplayer + spectator + reconnect

import socket
import threading
import time

HOST = '127.0.0.1'
PORT = 12345

# --- Helpers ---
def send_and_print(sock, msg):
    print(f"[SEND] {msg}")
    sock.sendall(f"{msg}\n".encode())

def receive(sock):
    try:
        data = sock.recv(2048).decode()
        if data:
            print(f"[RECV]: {data.strip()}")
    except:
        print("[RECV]: [Socket closed]")

# --- Player thread ---
def simulate_player(name, moves, reconnect=False):
    def run():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))

        receive(sock)  # 'Enter your name:'
        send_and_print(sock, name)

        for move in moves:
            time.sleep(1)
            send_and_print(sock, move)
            receive(sock)

        if reconnect:
            print(f"[{name}] Disconnecting for simulated reconnect...")
            sock.close()
            time.sleep(10)
            simulate_player(name, ["SHOW", "FIRE A2"])
        else:
            time.sleep(1)
            send_and_print(sock, "QUIT")
            receive(sock)
            sock.close()
    threading.Thread(target=run).start()

# --- Spectator thread ---
def simulate_spectator(name):
    def run():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        receive(sock)
        send_and_print(sock, name)
        try:
            while True:
                receive(sock)
        except:
            pass
    threading.Thread(target=run).start()

# --- Run the simulation ---
def run_test():
    simulate_player("Rania", ["SHOW", "FIRE A1"], reconnect=True)
    simulate_player("Ornob", ["SHOW", "FIRE B1"])
    time.sleep(2)
    simulate_spectator("Zoya")
    simulate_spectator("Amir")

run_test()
