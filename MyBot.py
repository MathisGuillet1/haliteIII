#!/usr/bin/env python3
# Python 3.6

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import constants
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
    return cell.halite_amount > 20

def best_around(ship, i):
    # Create a list of position around the ship reachable in (i+1) turns, recursive
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
        if ship.halite_amount > constants.MAX_HALITE * 95 / 100:
            logging.info(" --> Ship is heavily loaded, return to shipyard order given")
            destination = me.shipyard.position
            direction = game_map.naive_navigate(ship, destination)
            command_queue.append(ship.move(direction))
        else:
            if is_interesting(game_map[ship.position]):
                logging.info("--> Ship is gonna collect because interesting amount halite")
                command_queue.append(ship.stay_still())
            else:
                if ship.halite_amount > constants.MAX_HALITE * 85 / 100:
                    logging.info("--> Ship return to base even if not that fully loaded")
                    destination = me.shipyard.position
                    direction = game_map.naive_navigate(ship, destination)
                    command_queue.append(ship.move(direction))
                else:
                    logging.info("--> Ship is exploring to the best cell!")
                    destination = best_around(ship, 0)
                    direction = game_map.naive_navigate(ship, destination)
                    command_queue.append(ship.move(direction))

    if game.turn_number <= 200 and me.halite_amount >= constants.SHIP_COST and not game_map[me.shipyard].is_occupied:
        command_queue.append(me.shipyard.spawn())

    game.end_turn(command_queue)
