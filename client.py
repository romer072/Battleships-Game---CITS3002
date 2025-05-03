"""
client.py

Connects to a Battleship server which runs the single-player game.
Simply pipes user input to the server, and prints all server responses.

TODO: Fix the message synchronization issue using concurrency (Tier 1, item 1).
"""

import socket
import threading

HOST = '127.0.0.1'
PORT = 5000

running = True #shared flag to control thread shutdown

# HINT: The current problem is that the client is reading from the socket,
# then waiting for user input, then reading again. This causes server
# messages to appear out of order.
#
# Consider using Python's threading module to separate the concerns:
# - One thread continuously reads from the socket and displays messages
# - The main thread handles user input and sends it to the server
#

#Continuously receive and display messages from the server.
def recieve_messages(rfile):
    global running
    try:
        while running:
            line = rfile.readline()
            if not line:
                print("[INFO] Server disconnected")
                running = False
                break

            line = line.strip()

            if line == "GRID":
                print("\n[Board]")
                while True:
                    board_line = rfile.readline()
                    if not board_line or board_line.strip() == "":
                        break
                    print(board_line.strip())
                
            else:
                print(line)

    except Exception as e:
        print(f"[ERROR] Receiver thread exception: {e}")
        running = False

def main():
    global running
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        rfile = s.makefile('r')
        wfile = s.makefile('w')
        
        # Start thread to receive messages
        receiver_thread = threading.Thread(target=receive_messages, args=(rfile,), daemon=True)
        receiver_thread.start()

        try:
            while running:
                # PROBLEM: This design forces the client to alternate between
                # reading a message and sending input, which doesn't work when
                # the server sends multiple messages in sequence
                
                user_input = input(">> ")
                if user_input.lower() in ['quit', 'exit']:
                    running = False
                    break
                wfile.write(user_input + '\n')
                wfile.flush()

        except KeyboardInterrupt:
            print("\n[INFO] Client exiting.")
        finally:
            running = False
            receiver_thread.join(timeout=1)

# HINT: A better approach would be something like:
#
# def receive_messages(rfile):
#     """Continuously receive and display messages from the server"""
#     while running:
#         line = rfile.readline()
#         if not line:
#             print("[INFO] Server disconnected.")
#             break
#         # Process and display the message
#
# def main():
#     # Set up connection
#     # Start a thread for receiving messages
#     # Main thread handles sending user input

if __name__ == "__main__":
    main()