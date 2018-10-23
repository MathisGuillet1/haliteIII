#!/usr/bin/env python3
# Python 3.6

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import constants, commands
from hlt.positionals import Direction, Position
import math, random, logging, copy

game = hlt.Game()

# Declare global variables as shortands for functions
me = None
game_map = None

# Initialize global variables for functions
has_defended_spawn = None
ships_play_order = None
ships_intentions = None

game.ready("ShuzuiBot")

logging.info("Successfully created bot! My Player ID is {}.".format(game.my_id))

""" <<<Utility functions>>> """

def is_reserved(cell):
    return cell.position in reserved_positions

def is_available(cell):
    return cell.is_empty #and not is_reserved(cell)

def mark_safe(cell):
    cell.ship = None

def is_shipyard_attacked():
    cell = game_map[me.shipyard.position]
    return cell.is_occupied and not me.has_ship(cell.ship.id)

def is_interesting(cell):
    return cell.halite_amount > constants.MAX_HALITE * 1 / 100

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
    global ships_play_order
    ships_play_order = []

    # If no move intetions where determined before, return default order of ships
    if not ships_intentions:
        ships_play_order = list(map(lambda ship: ship.id, me.get_ships()))
        return

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
        if cost < lowest_cost and not target_cell.is_occupied:
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

def best_around(ship, i):
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
                position = Position(x+k, y+s)
                normalized = game_map.normalize(position)
                surrounding.append(normalized)

    best_position = None
    best_score = -1
    for position in surrounding:
        cell = game_map[position]
        if is_available(cell) and is_interesting(cell) and cell.halite_amount > best_score:
            best_score = cell.halite_amount
            best_position = position

    if best_position is None:
        return best_around(ship, i+1)
    else:
        return best_position

def make_decisions(steering_maker):
    global command_queue, first_ship_id, has_defended_spawn, ships_intentions

    has_defended_spawn = False
    # Queue for commands to be executed
    command_queue = []
    # Determine in which order, making decision for each ship, thanks to a list indicating how to iterate
    determine_play_order(ships_intentions)
    # Commands itentions of Ships
    ships_intentions = {}
    # Dictionnary of ships with ship id as key
    ships = me._ships

    # Make decision for each ship one by one
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
        else:
            if is_interesting(game_map[ship.position]):
                # Keep collecting halite under the ship while the amount is interesting enough to collect
                logging.info("--> Collect")
                ships_intentions[ship.id] = Direction.Still
                command_queue.append(ship.stay_still())
            else:
                if ship.halite_amount > constants.MAX_HALITE * 85 / 100:
                    # Lower bound of treshold to go back to a dropoff
                    logging.info("--> Go drop halite, treshold 2")
                    destination = me.shipyard.position
                    direction = navigate_to(ship, destination, steering_maker)
                    ships_intentions[ship.id] = direction
                    command_queue.append(ship.move(direction))
                else:
                    # Find the most interesting around the ship and move on it
                    logging.info("--> Go to best cell in range")
                    destination = best_around(ship, 0)
                    direction = navigate_to(ship, destination, steering_maker)
                    ships_intentions[ship.id] = direction
                    command_queue.append(ship.move(direction))


""" <<<Game Loop>>> """

while True:
    game.update_frame()
    me = game.me
    game_map = game.game_map

    # Commands itentions of Ships
    ships_intentions = {}

    # Let's first determine what ships would like to do (where they would like to move)
    make_decisions(unsafe_navigate)

    # Between the two steps of the decision process, most of global variables are reset

    # In a second time, we know how ships want to move, and we can determine a play order
    # that allow a maximum of ships to move instead of iterating randomly through ships
    make_decisions(safe_navigate)

    # Keep creating ships while number of turns played is less than 200
    if game.turn_number <= 200 and me.halite_amount >= constants.SHIP_COST and not game_map[me.shipyard].is_occupied:
        command_queue.append(me.shipyard.spawn())

    game.end_turn(command_queue)
