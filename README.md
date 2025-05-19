# BEER – Battleships: Engage in Explosive Rivalry

**BEER** (*Battleships: Engage in Explosive Rivalry*) is a two-player, turn-based Battleship game implemented in Python using TCP sockets and multithreading. Developed as part of the CITS3002 Computer Networks 2025 project, BEER showcases core networking principles through real-time game mechanics, custom communication protocols, and concurrent client-server architecture.

The game supports not only classic Battleship features like ship placement and firing, but also modern enhancements such as spectator mode, real-time chat, reconnection handling, and integrity-validated packet messaging using CRC-32.

---

## 🚀 Getting Started / Installation

BEER is implemented entirely in Python using the standard library. No external dependencies are required.

### Requirements
- Python 3.7 or higher

### Instructions

1. **Start the Server**  
   In Terminal 1:
   ```bash
   python3 server.py
   ```

2. **Start the First Client (Player 1)**  
   In Terminal 2:
   ```bash
   python3 client.py
   ```

3. **Start the Second Client (Player 2)**  
   In Terminal 3:
   ```bash
   python3 client.py
   ```

> The server automatically begins the game once two players connect. Additional clients join as spectators.

---

## 🕹️ How to Play

### 🌟 1. Ship Placement Phase
Use:
```bash
place <coordinate> <orientation> <ship_name>
```
Examples:
```bash
place B2 H Submarine
```
Available ships:
- Carrier (5)
- Battleship (4)
- Cruiser (3)
- Submarine (3)
- Destroyer (2)

### 🔥 2. Firing Phase
Use:
```bash
fire <coordinate>
```
Example:
```bash
fire E6
```
Server will respond with: `MISS`, `HIT`, or `HIT! You sank the <ShipName>!`

### 💬 3. Chat
Send a message to all players and spectators:
```bash
chat <message>
```
Example:
```bash
chat Good luck!
```

### 🚪 4. Quit
```bash
quit
```
Leaves the game and ends the session for that player.

---

## 🗂️ Code Structure

| File               | Description |
|--------------------|-------------|
| `server.py`        | Launches and manages the server, handles connections, game state, turns, and chat. |
| `client.py`        | Connects to the server, receives messages in a separate thread, and sends user commands. |
| `battleship.py`    | Core game logic: board class, firing, placement, sinking, rendering. Includes local game mode. |
| `ship_placement.py`| Validates and tracks ship placement for each player. |
| `README.md`        | Documentation and setup instructions. |
| `CITS3002_2025_Project.pdf` | Official project specification. |

---

## 🧱 Features by Tier

### ✅ Tier 1: Core Two-Player Game
- Threaded server/client for asynchronous messaging
- Turn-based firing logic
- CRC-validated custom packet protocol

### ✅ Tier 2: Input Validation & Stability
- Error handling for invalid input
- Idle timeout triggers forfeit
- Lobby support for new matches

### ✅ Tier 3: Spectators & Reconnection
- Spectators receive real-time updates
- Reconnect within timeout to resume game

### ✅ Tier 4: Protocol & Chat
- Custom packet format: `[SEQ][TYPE][LEN][PAYLOAD][CRC32]`
- Global in-game chat across players and spectators

---
