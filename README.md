# BISMILLAH

# BEER: Battleships - Engage in Explosive Rivalry

CITS3002 — Computer Networks  
University of Western Australia  
**Due:** 19 May 2025, 11:59 PM  
**Weight:** 30%  
**Group Project (max 2 members)**

## 😾 Project Overview

This project implements a **networked, turn-based Battleship game** called **BEER**. The goal is to create a multiplayer client-server application where players can engage in real-time battles, while the server handles connections, state synchronization, and gameplay logic.

---

## 🧹 Project Structure

```
.
├── battleship.py       # Core gameplay logic (shared)
├── server.py           # Server to manage multiple clients and game state
├── client.py           # Client interface for players
├── README.md           # This file
└── requirements.txt    # Optional - for Python dependencies if used
```

---

## 🎯 Implementation Tiers

### ✅ Tier 1: Basic 2-Player Game with Concurrency

- [Y] Fix concurrency issues in client (separate send/receive threads)
- [Y] Enable 2-player turn-based gameplay
- [Y] Game ends when one fleet is destroyed
- [Y] Basic client-server message exchange
- [Y] Assumes stable connections (no disconnection handling)

### ⚙️ Tier 2: Improved Game UX and Robustness

- [ ] Validate invalid inputs (e.g., bad coordinates, out-of-turn)
- [ ] Support multiple games after the first ends
- [ ] Inactivity timeout (e.g., 30 seconds)
- [ ] Handle mid-game disconnections gracefully
- [ ] Handle idle clients or multiple connections (waiting lobby)

### 🌐 Tier 3: Scalability and Spectator Support

- [ ] Accept multiple clients
- [ ] Support spectator mode (real-time updates only)
- [ ] Allow reconnections within 60s with game state recovery
- [ ] Transition from game to game (automatic player selection)

### 🔐 Tier 4: Advanced Networking Features (2+ required)

- [ ] T4.1 Custom low-level protocol with checksum
- [ ] T4.2 Instant Messaging (IM) system
- [ ] T4.3 Encryption layer (e.g., AES)
- [ ] T4.4 Security flaw analysis & mitigation

---

## 📦 How to Run

### Server

```bash
python server.py
```

### Client (in separate terminals)

```bash
python client.py
```

- Follow prompts to place ships and take turns.
- Optionally modify `battleship.py` for local testing.

---

## 🥪 Demo & Testing

- Local 2-player testing with threads
- Test disconnection/reconnection with timeout simulation
- Simulate spectators by launching >2 clients
- Check server stability under rapid messages or dropped clients

---

## 📄 Deliverables

- ✅ `BEER_report.pdf` – project explanation and design justifications
- ✅ `BEER_code.zip` – all required code files
- ✅ `BEER_demo.mp4` or [Demo Video Link](https://your-link-here.com)

**Filename format:** `StudentID1_StudentID2_BEER.zip/pdf`

---

## 📚 Authors

- **Name 1 (Student ID)**  
- **Name 2 (Student ID)**

---

## 📘 Notes

- Python 3.8+ recommended
- Multithreading used for I/O concurrency
- Custom protocol details in `report.pdf`
