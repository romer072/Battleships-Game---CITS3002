from battleship import Board, SHIPS  # Import the game board class and list of ship definitions

class ShipPlacement:
    def __init__(self):
        self.board = Board()              # New board instance to track ship placements
        self.placed_ships = set()         # Track which ships have been placed (by name)

    def place_ship(self, coord, orientation, ship_name):
        """
        Attempt to place a ship on the board.
        
        Parameters:
        - coord: string (e.g., "A1") — starting coordinate for the ship
        - orientation: string ("H" or "V") — horizontal or vertical
        - ship_name: string (e.g., "Carrier") — the name of the ship to place

        Returns:
        - (success: bool, message: str)
        """

        try:
            # Look up the size of the ship using a case-insensitive match
            ship_size = next((size for name, size in SHIPS if name.lower() == ship_name.lower()), None)
            if ship_size is None:
                return False, f"Unknown ship: {ship_name}"  # Ship not in list

            # Prevent duplicate placement of the same ship
            if ship_name in self.placed_ships:
                return False, f"{ship_name} already placed"

            # Convert coordinate string to board indices
            row = ord(coord[0].upper()) - ord('A')  # A-J → 0–9
            col = int(coord[1:]) - 1                # 1–10 → 0–9

            # Orientation: 0 = horizontal, 1 = vertical
            orientation = 0 if orientation.upper() == 'H' else 1

            # Validate and place the ship
            if self.board.can_place_ship(row, col, ship_size, orientation):
                occupied = self.board.do_place_ship(row, col, ship_size, orientation)  # Returns occupied positions
                self.board.placed_ships.append({      # Track the ship with name and positions
                    'name': ship_name,
                    'positions': occupied
                })
                self.placed_ships.add(ship_name)      # Mark this ship as placed
                return True, f"Placed {ship_name} at {coord}"
            else:
                return False, "Cannot place ship there. Try another position."  # Overlap or out-of-bounds

        except Exception as e:
            # General failure (e.g., invalid coord format)
            return False, f"Invalid placement: {str(e)}"

    def is_complete(self):
        """
        Check if the player has placed all ships.
        Returns:
        - bool: True if all ships are placed, False otherwise
        """
        return len(self.placed_ships) == len(SHIPS)

    def get_board(self):
        """
        Returns:
        - Board: the board object (used for rendering or firing)
        """
        return self.board

    def get_available_ships(self):
        """
        Get list of ships that are still unplaced.

        Returns:
        - List[str]: names of unplaced ships
        """
        return [name for name, _ in SHIPS if name not in self.placed_ships]