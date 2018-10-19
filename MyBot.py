#!/usr/bin/env python3
# Python 3.6

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import constants, commands
from hlt.positionals import Direction, Position
import random
import logging

game = hlt.Game()

# Declare global variables as shortands
me = None
game_map = None

# Pre computing before starting
game.ready("ShuzuiBot")

logging.info("Successfully created bot! My Player ID is {}.".format(game.my_id))
logging.info("The game is gonna last nb turns :  {}.".format(constants.MAX_TURNS))

""" <<<Utility functions>>> """

def is_reserved(cell):
    return cell.position in reserved_positions

def is_available(cell):
    return cell.is_empty #and not is_reserved(cell)

def is_interesting(cell):
    return cell.halite_amount > constants.MAX_HALITE * 5 / 100

def distance_to_base(ship):
    return game_map.calculate_distance(ship.position, me.shipyard.position)

def need_to_rush(ship):
    # Add arbitrary constant to distance considering that the ship may be blocked
    remaining_turns = constants.MAX_TURNS - game.turn_number
    return  distance_to_base(ship) + 5 >= remaining_turns

def navigate_to(ship, destination):
    if ship.halite_amount < game_map[ship.position].halite_amount:
        return commands.STAY_STILL

    if not need_to_rush(ship):
        return game_map.naive_navigate(ship, destination)
    else:
        distance = distance_to_base(ship)
        if distance == 0:
            # If ship is already on the shipyard
            return commands.STAY_STILL
        elif distance == 1:
            # If ship is next to shipyard, ignore collisions to drop halite on it
            return game_map.get_unsafe_moves(ship.position, me.shipyard.position)[0]
        else:
            # Return to base safely
            return game_map.naive_navigate(ship, me.shipyard.position)

def best_around(ship, i):
    # Create a list of position around the ship reachable in (i+1) turns, recursively
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


""" <<<Game Loop>>> """

while True:
    # Update game
    game.update_frame()
    me = game.me
    game_map = game.game_map

    # Queue for commands to be executed
    command_queue = []

    for ship in me.get_ships():
        logging.info("--> Control of ship id: {}".format(ship.id))

        if need_to_rush(ship) or ship.halite_amount > constants.MAX_HALITE * 95 / 100:
            logging.info(" --> Go drop halite, treshold 1 or RUSH time")
            destination = me.shipyard.position
            direction = navigate_to(ship, destination)
            command_queue.append(ship.move(direction))
        else:
            if is_interesting(game_map[ship.position]):
                logging.info("--> Collect")
                command_queue.append(ship.stay_still())
            else:
                if ship.halite_amount > constants.MAX_HALITE * 85 / 100:
                    logging.info("--> Go drop halite, treshold 2")
                    destination = me.shipyard.position
                    direction = navigate_to(ship, destination)
                    command_queue.append(ship.move(direction))
                else:
                    logging.info("--> Go to best cell in range")
                    destination = best_around(ship, 0)
                    direction = navigate_to(ship, destination)
                    command_queue.append(ship.move(direction))

    if game.turn_number <= 200 and me.halite_amount >= constants.SHIP_COST and not game_map[me.shipyard].is_occupied:
        command_queue.append(me.shipyard.spawn())

    game.end_turn(command_queue)
