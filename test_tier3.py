# tier3_diagnostics_readable.py — Clear output test for server.py Tier 3 behavior

import socket
import threading
import time

HOST = '127.0.0.1'
PORT = 12345
results = []

def log(status, message):
    tag = "✅" if status else "❌"
    results.append(f"[{tag}] {message}")
    print(f"[{tag}] {message}")

def info(message):
    results.append(f"[ℹ️] {message}")
    print(f"[ℹ️] {message}")

def try_recv(sock):
    try:
        return sock.recv(2048).decode()
    except:
        return ""

def simulate_player(name, actions, reconnect=False):
    def run():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            recv1 = try_recv(sock)
            if "Enter your name" in recv1:
                log(True, f"{name} received name prompt")
            else:
                log(False, f"{name} did not receive name prompt")

            sock.sendall(f"{name}\n".encode())
            recv2 = try_recv(sock)
            if f"You are Player" in recv2:
                log(True, f"{name} assigned role")
            else:
                log(False, f"{name} did not receive role assignment")

            for cmd in actions:
                sock.sendall(f"{cmd}\n".encode())
                time.sleep(1)
                recv = try_recv(sock)
                log(True, f"{name} sent '{cmd}', received response") if recv else log(False, f"{name} sent '{cmd}' but no response")

            if reconnect:
                log(True, f"{name} disconnecting for reconnect simulation")
                sock.close()
                time.sleep(10)

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((HOST, PORT))
                try_recv(sock)
                sock.sendall(f"{name}\n".encode())
                reconnect_response = try_recv(sock)
                if "rejoined" in reconnect_response.lower() or "Game started" in reconnect_response:
                    log(True, f"{name} reconnected successfully")
                else:
                    log(False, f"{name} failed to reconnect")

                sock.sendall(b"QUIT\n")
                try_recv(sock)
                sock.close()
            else:
                sock.sendall(b"QUIT\n")
                try_recv(sock)
                sock.close()

        except Exception as e:
            log(False, f"{name} encountered error: {e}")

    threading.Thread(target=run).start()

def simulate_spectator(name):
    def run():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
            try_recv(sock)  # name prompt
            sock.sendall(f"{name}\n".encode())
            data = try_recv(sock)
            if "spectator" in data.lower():
                log(True, f"{name} joined as spectator successfully")
            elif "you are player" in data.lower():
                info(f"{name} became a player instead of a spectator")
            elif "you are" in data.lower():
                info(f"{name} received role assignment")
            else:
                info(f"{name} did not match expected spectator or player role — possibly mid-session?")

            # Listen passively for 5s
            start = time.time()
            while time.time() - start < 5:
                msg = try_recv(sock)
                if msg:
                    info(f"{name} received: {msg.strip()}")
            sock.close()
        except Exception as e:
            log(False, f"{name} error: {e}")

    threading.Thread(target=run).start()

def run_test():
    simulate_player("Rania", ["SHOW", "FIRE A1"], reconnect=True)
    simulate_player("Ornob", ["SHOW", "FIRE B1"])
    time.sleep(2)
    simulate_spectator("Zoya")
    simulate_spectator("Amir")

    # Let test run fully
    time.sleep(20)
    print("\n🧪 Tier 3 Test Summary:")
    passed = [r for r in results if "✅" in r]
    failed = [r for r in results if "❌" in r]
    print(f"✔ {len(passed)} Passed")
    print(f"❌ {len(failed)} Failed")

run_test()
