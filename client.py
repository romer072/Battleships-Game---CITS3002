#client.py

import socket       # For TCP/IP socket communication
import threading    # For handling incoming messages concurrently
import zlib         # For CRC32 checksum to verify data integrity
import sys          # For exiting on error or quit
import time         # For brief delays before closing
import re           # For coordinate input validation using regex

# === Packet Types ===
PACKET_TYPE_JOIN = 0x00    # Client joining the server
PACKET_TYPE_FIRE = 0x01    # Fire at a coordinate
PACKET_TYPE_SHOW = 0x02    # Request to display current board
PACKET_TYPE_QUIT = 0x03    # Client quitting the game
PACKET_TYPE_ERROR = 0xFF   # Server sent an error message
PACKET_TYPE_CHAT = 0x04    # Chat message between players
PACKET_TYPE_PLACE = 0x05   # Place a ship on the board

# === Packet Helpers ===

def build_packet(seq, pkt_type, payload):
    data = payload.encode()  # Convert string to bytes
    if len(data) > 255:      # Limit payload size to 255 bytes
        print(f"[CLIENT ERROR] Payload too long: {len(data)} bytes")
        raise ValueError("Payload too long for packet format")
    header = bytes([seq & 0xFF, pkt_type & 0xFF, len(data) & 0xFF]) + data
    crc = zlib.crc32(header) & 0xFFFFFFFF     # Compute CRC32 over header+payload
    packet = header + crc.to_bytes(4, 'big')  # Append CRC to form complete packet
    return packet

def parse_packet(data):
    try:
        if len(data) < 7:  # Minimum size for a valid packet
            return None, None, None
        seq, pkt_type, length = data[0], data[1], data[2]
        payload = data[3:3+length]
        if len(payload) < length:
            return None, None, None
        crc_bytes = data[3+length:7+length]  # Extract CRC from packet
        packet = data[:3+length]             # Extract packet without CRC
        received_crc = int.from_bytes(crc_bytes, 'big')
        calculated_crc = zlib.crc32(packet) & 0xFFFFFFFF
        if received_crc != calculated_crc:
            print(f"[CLIENT WARNING] CRC mismatch: received={received_crc}, calculated={calculated_crc}")
            return None, None, None
        payload_str = payload.decode(errors='replace')  # Decode payload safely
        return seq, pkt_type, payload_str
    except Exception as e:
        print(f"[CLIENT ERROR] Parsing packet: {e}")
        return None, None, None

def receive_messages(sock):
    buffer = b''            # Buffer for incomplete packet fragments
    board_buffer = ''       # Temporary buffer for multi-part board payloads
    awaiting_board = False  # State flag for board reconstruction

    while True:
        try:
            data = sock.recv(1024)  # Blocking receive from server
            if not data:
                print("[INFO] Connection closed by the server.")
                break
            buffer += data
            while len(buffer) >= 7:
                length = buffer[2]  # Payload length
                packet_size = 3 + length + 4  # Total size incl. header + CRC
                if len(buffer) < packet_size:
                    break
                packet_data = buffer[:packet_size]
                buffer = buffer[packet_size:]
                seq, pkt_type, payload = parse_packet(packet_data)
                if seq is None:
                    continue  # Skip invalid packets
                # Dispatch by packet type
                if pkt_type == PACKET_TYPE_CHAT:
                    print(f"\n[CHAT] {payload}")
                elif pkt_type == PACKET_TYPE_FIRE:
                    print(f"\n[FIRE] {payload}")
                elif pkt_type == PACKET_TYPE_SHOW:
                    # Multi-part board rendering
                    if payload.startswith("MORE\n"):
                        if not awaiting_board:
                            board_buffer = ''  # Start new multi-packet board
                            awaiting_board = True
                        board_buffer += payload[5:]  # Strip prefix
                    elif payload.startswith("LAST\n"):
                        if not awaiting_board:
                            board_buffer = ''
                        board_buffer += payload[5:]
                        print("\n[BOARD]")
                        print(board_buffer)
                        board_buffer = ''
                        awaiting_board = False
                    else:
                        # Legacy single-packet board
                        print("\n[BOARD]")
                        print(payload)
                        board_buffer = ''
                        awaiting_board = False
                elif pkt_type == PACKET_TYPE_ERROR:
                    print(f"\n[SERVER ERROR] {payload}")
                elif pkt_type == PACKET_TYPE_QUIT:
                    print(f"\n[QUIT] {payload}")
                    sock.close()
                    sys.exit(0)
                else:
                    print(f"\n[UNKNOWN PACKET] Type: {pkt_type}, Payload: {payload}")
        except Exception as e:
            print(f"[CLIENT ERROR] Receiving: {e}")
            break
    sock.close()
    sys.exit(1)

def is_valid_coordinate(coord):
    # Valid coordinates: A-J followed by 1-10 (e.g., A1, B10, j7)
    match = re.fullmatch(r"([A-Ja-j])([1-9]|10)", coord.strip())
    return bool(match)

def main():
    host = '127.0.0.1'   # Localhost for development
    port = 12345         # Server port to connect to
    seq_counter = 0      # Sequence number for packet tracking

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))  # Establish TCP connection
        print("Connected to server.")
        player_name = input("Enter your name: ").strip()
        if not player_name:
            player_name = "Anonymous"
        join_packet = build_packet(seq_counter, PACKET_TYPE_JOIN, player_name)
        sock.sendall(join_packet)  # Notify server of player name
        seq_counter = (seq_counter + 1) & 0xFF  # Wrap-around sequence number
    except Exception as e:
        print(f"[CLIENT ERROR] Could not connect to server: {e}")
        return

    receiver = threading.Thread(target=receive_messages, args=(sock,), daemon=True)
    receiver.start()  # Start listening to server messages in background

    print("\nCommands:")
    print("  show - Show your board")
    print("  place <coord> <H/V> <ship_name> - Place a ship (e.g. place A1 H Carrier)")
    print("  fire <coord> - Fire at coordinate (e.g. fire A1)")
    print("  chat <message> - Send chat message")
    print("  quit - Exit the game")

    while True:
        try:
            cmd = input("> ").strip()
            if not cmd:
                continue
            if cmd.lower() == 'quit':
                try:
                    packet = build_packet(seq_counter, PACKET_TYPE_QUIT, "")
                    sock.sendall(packet)
                    time.sleep(0.5)  # Allow time for quit packet to send
                except Exception as e:
                    print(f"[CLIENT ERROR] Failed to send quit: {e}")
                break
            elif cmd.lower() == 'show':
                try:
                    packet = build_packet(seq_counter, PACKET_TYPE_SHOW, "")
                    sock.sendall(packet)
                except Exception as e:
                    print(f"[CLIENT ERROR] Failed to send show: {e}")
            elif cmd.lower().startswith('place '):
                try:
                    packet = build_packet(seq_counter, PACKET_TYPE_PLACE, cmd[6:].strip())
                    sock.sendall(packet)
                except Exception as e:
                    print(f"[CLIENT ERROR] Failed to send place: {e}")
            elif cmd.lower().startswith('fire '):
                target = cmd[5:].strip()
                if not is_valid_coordinate(target):
                    print("[CLIENT ERROR] Invalid coordinate. Use A-J and 1-10, e.g. fire B7")
                    continue
                try:
                    packet = build_packet(seq_counter, PACKET_TYPE_FIRE, target.upper())
                    sock.sendall(packet)
                except Exception as e:
                    print(f"[CLIENT ERROR] Failed to send fire: {e}")
            elif cmd.lower().startswith('chat '):
                message = cmd[5:].strip()
                if not message:
                    print("[CLIENT ERROR] Chat message cannot be empty.")
                    continue
                try:
                    packet = build_packet(seq_counter, PACKET_TYPE_CHAT, message)
                    sock.sendall(packet)
                except Exception as e:
                    print(f"[CLIENT ERROR] Failed to send chat: {e}")
            else:
                print("[CLIENT ERROR] Unknown command. Try: show, place <coord> <H/V> <ship_name>, fire <coord>, chat <msg>, quit")
            seq_counter = (seq_counter + 1) & 0xFF
        except KeyboardInterrupt:
            print("\n[CLIENT INFO] Interrupted. Exiting.")
            try:
                packet = build_packet(seq_counter, PACKET_TYPE_QUIT, "")
                sock.sendall(packet)
                time.sleep(0.5)
            except Exception:
                pass
            break
        except Exception as e:
            print(f"[CLIENT ERROR] {e}")
            break
    sock.close()
    print("Disconnected.")

if __name__ == '__main__':
    main()  # Entry point for client execution