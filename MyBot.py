#!/usr/bin/env python3
# Python 3.6

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import constants, commands
from hlt.positionals import Direction, Position
import math, random, logging, copy

game = hlt.Game()

# Global varaibles
interesting_treshold = 5 / 100

game.ready("ShuzuiBot")

logging.info("Successfully created bot! My Player ID is {}.".format(game.my_id))

""" <<<Utility functions>>> """
def mark_safe(cell):
    cell.ship = None

def is_shipyard_attacked():
    cell = game_map[me.shipyard.position]
    return cell.is_occupied and not me.has_ship(cell.ship.id)

def is_interesting(cell):
    return cell.halite_amount > constants.MAX_HALITE * interesting_treshold

def distance_to_base(ship):
    return game_map.calculate_distance(ship.position, me.shipyard.position)

def need_to_rush(ship):
    # Add arbitrary constant to distance considering that the ship may be blocked during cst turns
    remaining_turns = constants.MAX_TURNS - game.turn_number
    return  distance_to_base(ship) + 5 >= remaining_turns

def find_unblocked_ship(ships_intentions):
    # Create deep copies og game instance to keep safe original game object and reuse it later
    me = copy.deepcopy(game.me)
    game_map = copy.deepcopy(game.game_map)

    # Find a ship that can move and lock position desired by the ship
    for ship_id, direction in ships_intentions.items():
        ship = me.get_ship(ship_id)
        target_pos = ship.position.directional_offset(direction)
        target_cell = game_map[target_pos]

        if not target_cell.is_occupied:
            # Update map info
            mark_safe(game_map[ship.position])
            target_cell.mark_unsafe(ship)
            return ship

    return None

def determine_play_order(ships_intentions):
    ships_play_order = []

    # If no move intetions where determined before, return default order of ships
    if not ships_intentions:
        ships_play_order = list(map(lambda ship: ship.id, me.get_ships()))
        return ships_play_order

    for ship_id, direction in ships_intentions.items():
        if direction == Direction.Still:
            ships_play_order.append(ship_id)

    # Rmove ships which has been place in order queue
    for ship_id in ships_play_order:
        ships_intentions.pop(ship_id)

    can_move = True
    while can_move:
        ship = find_unblocked_ship(ships_intentions)
        if ship != None:
            ships_play_order.append(ship.id)
            ships_intentions.pop(ship.id)
        else:
            can_move = False

    # Handle remaining ships that can't move
    for ship_id in ships_intentions:
        ships_play_order.append(ship_id)

    return ships_play_order

def minimize_cost_unsafe(ship, directions):
    # When there is multiple possibilities to reach destination at t turn, choose direction with lower cost
    lowest_cost = math.inf
    for direction in directions:
        target_pos = ship.position.directional_offset(direction)
        target_cell = game_map[target_pos]
        cost = game_map[target_pos].halite_amount
        if cost < lowest_cost:
            choice = direction
    return choice

def minimize_cost_safe(ship, directions):
    # When there is multiple possibilities to reach destination at t turn, choose direction with lower cost
    lowest_cost = math.inf
    choice = None
    for direction in directions:
        target_pos = ship.position.directional_offset(direction)
        target_cell = game_map[target_pos]
        cost = game_map[target_pos].halite_amount
        if cost < lowest_cost:
            global crossing_ships
            if not target_cell.is_occupied:
                 choice = direction
            elif ship.id in crossing_ships:
                choice = direction
    if not choice:
        return Direction.Still
    else:
        return choice

def safe_navigate(ship, destination):
    direction =  minimize_cost_safe(ship, game_map.get_unsafe_moves(ship.position, destination))
    mark_safe(game_map[ship.position])
    target_pos = ship.position.directional_offset(direction)
    target_cell = game_map[target_pos]
    target_cell.mark_unsafe(ship)
    return direction

def unsafe_navigate(ship, destination):
    # This function return unsafe direction toward destination, chosing best lowest path cost
    direction =  minimize_cost_unsafe(ship, game_map.get_unsafe_moves(ship.position, destination))
    return direction

def navigate_to(ship, destination, steering_maker):
    if not need_to_rush(ship):
        if ship.halite_amount < game_map[ship.position].halite_amount * 10 / 100:
            # Make sure the ship has the ressources to move
            return Direction.Still

        distance = distance_to_base(ship)
        global has_defended_spawn
        if distance == 1 and is_shipyard_attacked() and not has_defended_spawn:
            # If an enemy is on the shipyard, use one ship to collide with it on shipyard position
            # When spawn is blocked by an enemy, use only collide only one ship on it, let others wait
            has_defended_spawn = True
            return game_map.get_unsafe_moves(ship.position, me.shipyard.position)[0]

        else:
            return steering_maker(ship, destination)
    else:
        distance = distance_to_base(ship)
        if distance == 0:
            # If ship is already on the shipyard
            return Direction.Still
        elif distance == 1:
            # If ship is next to shipyard, ignore collisions to drop halite on it
            return game_map.get_unsafe_moves(ship.position, me.shipyard.position)[0]
        else:
            # Return to base safely
            return steering_maker(ship, me.shipyard.position)

def order_by_distance(ships):
    ships_distances = {}
    for ship in ships:
        ships_distances[ship.id] = distance_to_base(ship)

    ordered_ships= []
    for key in sorted(ships_distances, key=ships_distances.get):
        ordered_ships.append(key)

    return ordered_ships

def find_crossing_ships(ships, ships_intentions):
    # Find ships that are crossing by pairs
    intentions = copy.deepcopy(ships_intentions)
    crossing_ships = []
    ordered_ships = order_by_distance(ships)
    for ship_id in ordered_ships:
        if ship_id in crossing_ships:
            continue
        # Determine where is going this ship A
        ship_A = me.get_ship(ship_id)
        direction_A = intentions[ship_A.id]
        destination_A = ship_A.position.directional_offset(direction_A)
        intentions.pop(ship_A.id)
        # Try to find a ship to pair with
        for key in intentions:
            ship_B = me.get_ship(key)
            direction_B = intentions[ship_B.id]
            destination_B = ship_B.position.directional_offset(direction_B)
            # The ship B to pair is where the ship is going, then check if ship B is going on ship A position
            if ship_B.position == destination_A and ship_A.position == destination_B:
                # A crossing is happening, update list of crossing, and remaining
                crossing_ships.append(ship_A.id)
                crossing_ships.append(ship_B.id)
                intentions.pop(ship_B.id)
                logging.info("Ship {} at position {} will cross with ship {} at position {}".format(ship_A.id, ship_A.position, ship_B.id, ship_B.position))
                break


    return crossing_ships

def best_around(ship, i):
    # Reset recursion when no cell greater than intresting treshold found
    global interesting_treshold
    if(i > game_map.width / 2):
        interesting_treshold -= 1 / 100
        return best_around(ship, 0)

    # Create a list of positions around the ship reachable in (i+1) turns, recursively
    # Ignore cell under the ship since this function is called only when moving is required
    if i == 0:
        surrounding = ship.position.get_surrounding_cardinals()
    else:
        x = ship.position.x
        y = ship.position.y
        surrounding = []
        for k in range(-i, i+1):
            for s in range(-i, i+1):
                # Keep only edges since it is recursive
                if k == -i or k == i or s == -i or s == i:
                    position = Position(x+k, y+s)
                    normalized = game_map.normalize(position)
                    surrounding.append(normalized)

    best_position = None
    best_score = -1
    for position in surrounding:
        cell = game_map[position]
        if cell.is_empty and is_interesting(cell) and cell.halite_amount > best_score:
            best_score = cell.halite_amount
            best_position = position

    if best_position is None:
        return best_around(ship, i+1)
    else:
        return best_position

def make_decisions(steering_maker, ships_intentions):
    # Varaible to know if a ship has to collide on spawn with enemy
    global has_defended_spawn
    has_defended_spawn = False
    # Queue for commands to be executed
    command_queue = []
    # Determine in which order, making decision for each ship, thanks to a list indicating how to iterate
    ships_play_order = determine_play_order(ships_intentions)

    # Dictionnary of ships with ship id as key, make decision for each ship
    ships = me._ships
    for ship_id in ships_play_order:
        ship = ships[ship_id]
        logging.info("--> Control of ship id: {}".format(ship.id))

        """ Entering in the main decision tree, making a choice independently of game state """

        if need_to_rush(ship) or ship.halite_amount > constants.MAX_HALITE * 95 / 100:
            # When a ship is almost fully loaded or just have time to return shipyard, then return to shipyard
            logging.info(" --> Go drop halite, treshold 1 or RUSH time")
            destination = me.shipyard.position
            direction = navigate_to(ship, destination, steering_maker)
            ships_intentions[ship.id] = direction
            command_queue.append(ship.move(direction))
            continue

        if is_interesting(game_map[ship.position]):
            # Keep collecting halite under the ship while the amount is interesting enough to collect
            logging.info("--> Collect")
            ships_intentions[ship.id] = Direction.Still
            command_queue.append(ship.stay_still())
            continue

        if ship.halite_amount > constants.MAX_HALITE * 85 / 100:
            # Lower bound of treshold to go back to a dropoff
            logging.info("--> Go drop halite, treshold 2")
            destination = me.shipyard.position
            direction = navigate_to(ship, destination, steering_maker)
            ships_intentions[ship.id] = direction
            command_queue.append(ship.move(direction))
            continue
        else:
            # Find the most interesting around the ship and move on it
            logging.info("--> Go to best cell in range")
            destination = best_around(ship, 0)
            direction = navigate_to(ship, destination, steering_maker)
            ships_intentions[ship.id] = direction
            command_queue.append(ship.move(direction))

    return (ships_intentions, command_queue)


""" <<<Game Loop>>> """
while True:
    # Shortands for functions
    global me, game_map

    game.update_frame()
    me = game.me
    game_map = game.game_map

    """ Let's first determine what ships would like to do (where they would like to move) """
    ships_intentions = make_decisions(unsafe_navigate, {})[0]

    global crossing_ships
    crossing_ships = find_crossing_ships(me.get_ships(), ships_intentions)

    """ In a second time, we know how ships want to move, and we can determine a play order
    that allow a maximum of ships to move instead of iterating randomly through ships """
    command_queue = make_decisions(safe_navigate, ships_intentions)[1]

    # Keep creating ships while number of turns played is less than 200
    if game.turn_number <= 200 and me.halite_amount >= constants.SHIP_COST and not game_map[me.shipyard].is_occupied:
        command_queue.append(me.shipyard.spawn())

    game.end_turn(command_queue)
