import socket
import threading
import zlib
import sys
import time

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
        raise ValueError("Payload too long for packet format")
    header = bytes([seq & 0xFF, pkt_type & 0xFF, len(data) & 0xFF]) + data
    crc = zlib.crc32(header) & 0xFFFFFFFF
    packet = header + crc.to_bytes(4, 'big')
    print(f"[DEBUG] Sending packet: type={pkt_type}, seq={seq}, len={len(data)}, payload='{payload}'")
    return packet

def parse_packet(data):
    try:
        if len(data) < 7:  # Minimum packet size: 3 bytes header + 0 payload + 4 bytes CRC
            print(f"[DEBUG] Packet too small: {len(data)} bytes")
            return None, None, None
        
        seq, pkt_type, length = data[0], data[1], data[2]
        payload = data[3:3+length]
        
        if len(payload) < length:
            print(f"[DEBUG] Incomplete payload: got {len(payload)}, expected {length}")
            return None, None, None
            
        crc_bytes = data[3+length:7+length]
        packet = data[:3+length]
        received_crc = int.from_bytes(crc_bytes, 'big')
        calculated_crc = zlib.crc32(packet) & 0xFFFFFFFF
        
        if received_crc != calculated_crc:
            print(f"[WARNING] Checksum mismatch: received={received_crc}, calculated={calculated_crc}")
            return None, None, None
            
        payload_str = payload.decode()
        print(f"[DEBUG] Received packet: type={pkt_type}, seq={seq}, len={length}, payload='{payload_str}'")
        return seq, pkt_type, payload_str
    except Exception as e:
        print(f"[ERROR] Parsing packet: {e}")
        print(f"[DEBUG] Raw data: {data.hex()}")
        return None, None, None

def receive_messages(sock):
    buffer = b''
    seq_counter = 0
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                print("Connection closed by the server.")
                break
                
            print(f"[DEBUG] Received {len(data)} bytes from server")
            buffer += data
            
            # Try to process as many complete packets as possible
            while len(buffer) >= 7:  # Min packet size (3 byte header + 0 payload + 4 byte CRC)
                length = buffer[2]
                packet_size = 3 + length + 4  # header + payload + CRC
                
                if len(buffer) < packet_size:
                    print(f"[DEBUG] Need more data: have {len(buffer)}, need {packet_size}")
                    break  # Not enough data for a complete packet
                    
                packet_data = buffer[:packet_size]
                buffer = buffer[packet_size:]  # Remove processed packet
                
                seq, pkt_type, payload = parse_packet(packet_data)
                if seq is None:
                    continue  # Invalid packet
                
                # Handle different packet types
                if pkt_type == PACKET_TYPE_CHAT:
                    print(f"\n[CHAT] {payload}")
                elif pkt_type == PACKET_TYPE_FIRE:
                    print(f"\n[FIRE] {payload}")
                elif pkt_type == PACKET_TYPE_SHOW:
                    print("\n[BOARD]")
                    print(payload)
                elif pkt_type == PACKET_TYPE_ERROR:
                    print(f"\n[ERROR] {payload}")
                elif pkt_type == PACKET_TYPE_QUIT:
                    print(f"\n[QUIT] {payload}")
                    sock.close()
                    sys.exit(0)
                else:
                    print(f"\n[UNKNOWN] Type: {pkt_type}, Payload: {payload}")
                
        except ConnectionResetError:
            print("Connection lost.")
            break
        except Exception as e:
            print(f"Error receiving: {e}")
            break
    
    sock.close()
    sys.exit(1)

def main():
    host = '127.0.0.1'
    port = 12345
    seq_counter = 0

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect((host, port))
        print("Connected to server.")
        
        # Send JOIN packet with player name
        player_name = input("Enter your name: ")
        join_packet = build_packet(seq_counter, PACKET_TYPE_JOIN, player_name)
        sock.sendall(join_packet)
        seq_counter = (seq_counter + 1) & 0xFF
        
    except Exception as e:
        print(f"Could not connect to server: {e}")
        return

    # Start receiver thread
    receiver = threading.Thread(target=receive_messages, args=(sock,), daemon=True)
    receiver.start()

    # Help text
    print("\nCommands:")
    print("  show - Show your board")
    print("  fire A1 - Fire at coordinate A1")
    print("  chat <message> - Send chat message")
    print("  quit - Exit the game")

    # Main input loop
    while True:
        try:
            cmd = input("> ").strip()
            
            if not cmd:
                continue
                
            if cmd.lower() == 'quit':
                packet = build_packet(seq_counter, PACKET_TYPE_QUIT, "")
                sock.sendall(packet)
                # Wait briefly to allow the quit packet to be sent
                time.sleep(0.5)
                break
                
            elif cmd.lower() == 'show':
                packet = build_packet(seq_counter, PACKET_TYPE_SHOW, "")
                sock.sendall(packet)
                
            elif cmd.lower().startswith('fire '):
                target = cmd[5:].strip()
                if len(target) >= 2:  # Basic validation (e.g., "A1")
                    packet = build_packet(seq_counter, PACKET_TYPE_FIRE, target)
                    sock.sendall(packet)
                else:
                    print("Invalid coordinate. Use format like 'fire A1'")
                    
            elif cmd.lower().startswith('chat '):
                message = cmd[5:].strip()
                if message:
                    packet = build_packet(seq_counter, PACKET_TYPE_CHAT, message)
                    sock.sendall(packet)
                    
            else:
                print("Unknown command. Try: show, fire <coord>, chat <msg>, quit")
                
            seq_counter = (seq_counter + 1) & 0xFF
                
        except KeyboardInterrupt:
            print("\nInterrupted. Exiting.")
            packet = build_packet(seq_counter, PACKET_TYPE_QUIT, "")
            sock.sendall(packet)
            time.sleep(0.5)
            break
        except Exception as e:
            print(f"Error: {e}")
            break

    sock.close()
    print("Disconnected.")

if __name__ == '__main__':
    main() 