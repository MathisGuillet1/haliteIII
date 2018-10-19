#!/usr/bin/env python3
# Python 3.6

# Import the Halite SDK, which will let you interact with the game.
import hlt

# This library contains constant values.
from hlt import constants

# This library contains direction metadata to better interface with the game.
from hlt.positionals import Direction, Position

# This library allows you to generate random numbers.
import random

# Logging allows you to save messages for yourself. This is required because the regular STDOUT
#   (print statements) are reserved for the engine-bot communication.
import logging

""" <<<Game Begin>>> """

# This game object contains the initial game state.
game = hlt.Game()
# At this point "game" variable is populated with initial map data.
# This is a good place to do computationally expensive start-up pre-processing.
# As soon as you call "ready" function below, the 2 second per turn timer will start.
game.ready("MyPythonBot")

# Now that your bot is initialized, save a message to yourself in the log file with some important information.
#   Here, you log here your id, which you can always fetch from the game object by using my_id.
logging.info("Successfully created bot! My Player ID is {}.".format(game.my_id))
logging.info("The game is gonna last nb turns :  {}.".format(constants.MAX_TURNS))


""" <<<Game Loop>>> """

while True:
    # This loop handles each turn of the game. The game object changes every turn, and you refresh that state by
    #   running update_frame().
    game.update_frame()
    # You extract player metadata and the updated map metadata here for convenience.
    me = game.me
    game_map = game.game_map

    # Global loop variables
    reserved_positions = []

    # Utility functions
    def is_reserved(cell):
        return cell.position in reserved_positions

    def is_available(cell):
        return cell.is_empty and not is_reserved(cell)

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
            if is_available(cell) and cell.halite_amount > 15 and cell.halite_amount > best_score:
                best_score = cell.halite_amount
                best_position = position

        if best_position is None:
            return best_around(ship, i+1)
        else:
            return best_position


    # A command queue holds all the commands you will run this turn. You build this list up and submit it at the
    #   end of the turn.
    command_queue = []

    for ship in me.get_ships():
        logging.info("--> Control of ship id: {}".format(ship.id))
        if ship.halite_amount > constants.MAX_HALITE * 95 / 100:
            logging.info(" --> Ship is heavily loaded, return to shipyard order given")
            destination = me.shipyard.position
            direction = game_map.naive_navigate(ship, destination)
            command_queue.append(ship.move(direction))
        else:
            if game_map[ship.position].halite_amount > 15:
                logging.info("--> Ship is gonna collect because interesting amount halite")
                command_queue.append(ship.stay_still())
            else:
                if ship.halite_amount > constants.MAX_HALITE * 70 / 100:
                    logging.info("--> Ship return to base even if not that fully loaded")
                    destination = me.shipyard.position
                    direction = game_map.naive_navigate(ship, destination)
                    command_queue.append(ship.move(direction))
                else:
                    logging.info("--> Ship is exploring to the best cell!")
                    destination = best_around(ship, 0)
                    direction = game_map.naive_navigate(ship, destination)
                    command_queue.append(ship.move(direction))
                    # reserved_pos.append(go_to)

    if game.turn_number <= 200 and me.halite_amount >= constants.SHIP_COST and not game_map[me.shipyard].is_occupied:
        command_queue.append(me.shipyard.spawn())

    # Send your moves back to the game environment, ending this turn.
    game.end_turn(command_queue)
