#!/usr/bin/env python3
# Python 3.6

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import constants, commands
from hlt.positionals import Direction, Position
import math, logging, time, numpy as np

game = hlt.Game()

# Global varaibles
interesting_treshold = 5 / 100

game.ready("shuzuiBot")
logging.info("Successfully created bot! My Player ID is {}.".format(game.my_id))

def mark_safe(cell):
    cell.ship = None

def mark_reserved(cell):
    cell.reserved = True

def has_fuel(ship):
    return ship.halite_amount >= game_map[ship.position].halite_amount * 10 / 100

def fleet_size():
    return len(me.get_ships())

def is_reserved(cell):
    if hasattr(cell, 'reserved'):
        return cell.reserved
    else:
        return False

def has_defended_dropoff(position):
    cell = game_map[position]
    if hasattr(cell, 'defended'):
        return cell.defended
    else:
        cell.defended = True
        return False

def is_dropoff_attacked(position):
    cell = game_map[position]
    return cell.is_occupied and not me.has_ship(cell.ship.id)

def is_interesting(cell):
    return cell.halite_amount > constants.MAX_HALITE * interesting_treshold

def distance_to_dropoff(ship):
    return game_map.calculate_distance(ship.position, closest_dropoff(ship))

def grid_distance_to_dropoff(ship):
    return grid_distance(ship.position, closest_dropoff(ship))

def need_to_rush(ship):
    # Add arbitrary constant to distance considering that the ship may be blocked during X turns
    remaining_turns = constants.MAX_TURNS - game.turn_number
    return  distance_to_dropoff(ship) + 7 >= remaining_turns

def grid_distance(position_A, position_B):
    # compute distance with 8 connectivity between two positions
    dx = abs(position_B.x - position_A.x)
    dy = abs(position_B.y - position_A.y)

    # toric map
    dx = min(dx, game_map.width - dx)
    dy = min(dy, game_map.height - dy)

    minimum = min(dx, dy)
    maximum = max(dx, dy)

    diagonal_steps = minimum
    straight_steps = maximum - minimum

    return int(math.sqrt(2) * diagonal_steps + straight_steps)

def closest_dropoff(ship):
    dropoffs = me.get_dropoffs()
    positions = [drop.position for drop in dropoffs]
    positions.append(me.shipyard.position)

    best_dropoff = None
    min_distance = math.inf
    for position in positions:
        distance = game_map.calculate_distance(ship.position, position)
        if distance < min_distance:
            min_distance = distance
            best_dropoff = position

    return best_dropoff

def get_unsafe_positions(ship, destination):
    directions = game_map.get_unsafe_moves(ship.position, destination)
    positions = []

    for direction in directions:
        position = ship.position.directional_offset(direction)
        positions.append(position)

    return positions

def order_by_distance(ships):
    # Ships sorted by descending order with distance to a dropoff
    ships_distances = {}
    for ship in ships:
        ships_distances[ship.id] = distance_to_dropoff(ship)

    ordered_ships = []
    for key in sorted(ships_distances, key=ships_distances.get, reverse=True):
        ordered_ships.append(key)

    return ordered_ships

def create_scanned_map(range=5):
    scanned = np.zeros((game_map.width, game_map.height))

    for i in range(game_map.width):
        for j in range(game_map.height):
            scanned[i][j] = compute_interest(i, j, range)

def best_around(ship, i=1):
    # Reset recursion when no cell greater than intresting treshold found
    global interesting_treshold
    if(i > game_map.width):
        interesting_treshold -= 1 / 100
        return best_around(ship)

    # Create a list of positions around the ship reachable in (i+1) turns, recursively
    x = ship.position.x
    y = ship.position.y
    surrounding = []
    for k in range(-i, i+1):
        for s in range(-i, i+1):
            # Keep only edges since it is recursive
            if (abs(k) + abs(s)) == i:
                position = Position(x+k, y+s)
                normalized = game_map.normalize(position)
                surrounding.append(normalized)

    best_position = None
    best_score = -1
    for position in surrounding:
        cell = game_map[position]
        if cell.is_empty and not is_reserved(cell) and is_interesting(cell) and cell.halite_amount > best_score:
            best_score = cell.halite_amount
            best_position = position

    if best_position is None:
        return best_around(ship, i+1)
    else:
        return best_position

def find_destination(ship):
    if need_to_rush(ship) or ship.halite_amount > constants.MAX_HALITE * 95 / 100:
        # When a ship is almost fully loaded or just have time to return a dropoff, then return to dropoff
        destination = closest_dropoff(ship)
    elif is_interesting(game_map[ship.position]):
        # Keep collecting halite under the ship while the amount is interesting enough to collect
        destination = ship.position
    elif ship.halite_amount > constants.MAX_HALITE * 85 / 100:
        # Lower bound of treshold to go back to a dropoff
        destination = closest_dropoff(ship)
    else:
        # Find the most interesting around the ship and move on it
        destination = best_around(ship)

    return destination

def safe_direction_to(ship, destination):
    # When there is multiple possibilities to reach destination, choose direction with lower cost
    lowest_cost = math.inf
    # The default choice is None, if the ship can't move without collisions
    choice = None
    directions = game_map.get_unsafe_moves(ship.position, destination)

    for direction in directions:
        target_pos = ship.position.directional_offset(direction)
        target_cell = game_map[target_pos]
        cost = game_map[target_pos].halite_amount
        if cost < lowest_cost:
            if not target_cell.is_occupied:
                 choice = direction

    return choice

def navigate_to(ship, destination):
    if destination == ship.position or not has_fuel(ship):
        return Direction.Still

    if need_to_rush(ship):
        distance = distance_to_dropoff(ship)
        if distance == 0:
            return Direction.Still
        elif distance == 1:
            # Ignore collisions over dropoffs cells
            return game_map.get_unsafe_moves(ship.position, closest_dropoff(ship))[0]
        else:
            # Return to dropoff safely
            return safe_direction_to(ship, closest_dropoff(ship))

    dropoff_pos = closest_dropoff(ship)
    dropoff_dist = game_map.calculate_distance(ship.position, dropoff_pos)
    if dropoff_dist == 1 and is_dropoff_attacked(dropoff_pos) and not has_defended_dropoff(dropoff_pos):
        # If an enemy is on a dropoff, use one ship to collide with it on dropoff position
        # When spawn is blocked by an enemy, use only one ship to make the way, others wait
        return game_map.get_unsafe_moves(ship.position, dropoff_pos)[0]

    return safe_direction_to(ship, destination)

def find_crossing_ship(ship_A, destination_A, ships_play_order):
    position_A = ship_A.position
    moves_A = get_unsafe_positions(ship_A, destination_A)

    for ship_id in ships_play_order:
        ship_B = me.get_ship(ship_id)

        if not has_fuel(ship_B) or ship_id == ship_A.id:
            continue

        position_B = ship_B.position
        destination_B = find_destination(ship_B)
        moves_B = get_unsafe_positions(ship_B, destination_B)

        if position_A in moves_B and position_B in moves_A:
            return ship_B

    return None

def make_decisions():
    ships = me.get_ships()
    # Queue for commands to be executed
    command_queue = []
    # Determine in which order, making decision for each ship
    ships_play_order = order_by_distance(ships)

    # Remove from ships_play_order when a ship can move
    ship_moving = True
    while ships_play_order and ship_moving:
        ship_moving = False

        for ship_id in ships_play_order:
            ship = me.get_ship(ship_id)
            destination = find_destination(ship)

            """ CONSTRUCTION """

            if me.halite_amount > constants.DROPOFF_COST and not game_map[ship.position].has_structure and \
                grid_distance_to_dropoff(ship) > 15 and fleet_size() > 15 and game.turn_number < 350:

                command_queue.append(ship.make_dropoff())
                me.halite_amount -= constants.DROPOFF_COST
                # free cell
                ship_moving = True
                ships_play_order.remove(ship_id)
                break

            """ CONSTRUCTION """

            # Determine the best command to reach destination
            direction = navigate_to(ship, destination)
            if direction:
                command_queue.append(ship.move(direction))
                ships_play_order.remove(ship_id)
                ship_moving = True

                # Update map cells info, if ship is moving
                if direction != Direction.Still:
                    mark_safe(game_map[ship.position])
                    target_pos = ship.position.directional_offset(direction)
                    target_cell = game_map[target_pos]
                    target_cell.mark_unsafe(ship)
                    mark_reserved(destination)
                break

    # Try to cross on remaining ships
    while ships_play_order:
        ship = me.get_ship(ships_play_order[0])
        destination = find_destination(ship)
        crossing_ship = find_crossing_ship(ship, destination, ships_play_order)
        if crossing_ship:
            direction_ship = game_map.get_unsafe_moves(ship.position, crossing_ship.position)[0]
            direction_ship_crossing = game_map.get_unsafe_moves(crossing_ship.position, ship.position)[0]
            command_queue.append(ship.move(direction_ship))
            command_queue.append(crossing_ship.move(direction_ship_crossing))

            ships_play_order.remove(ship.id)
            ships_play_order.remove(crossing_ship.id)
            ship_moving = True

            # Special update for cells, when crossing
            game_map[ship.position].mark_unsafe(crossing_ship)
            game_map[crossing_ship.position].mark_unsafe(ship)

            destination_crossing = find_destination(crossing_ship)
            mark_reserved(destination_crossing)
            mark_reserved(destination)
            break
        else:
            ships_play_order.remove(ship.id)

    return command_queue

""" <<<Game Loop>>> """
while True:
    # Shortands for functions
    global me, game_map

    start_time = time.time()
    game.update_frame()
    me = game.me
    game_map = game.game_map

    command_queue = make_decisions()

    # Keep creating ships while number of turns played is less than 200
    if game.turn_number <= (constants.MAX_TURNS / 2) and me.halite_amount >= constants.SHIP_COST and not game_map[me.shipyard].is_occupied:
        command_queue.append(me.shipyard.spawn())

    logging.info("Time elapsed to make a decision this turn: {}".format(time.time() - start_time))

    game.end_turn(command_queue)
