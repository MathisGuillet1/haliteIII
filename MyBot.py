#!/usr/bin/env python3
# Python 3.6

# Import the Halite SDK, which will let you interact with the game.
import hlt
from hlt import constants, commands
from hlt.positionals import Direction, Position
import math
import random
import logging

game = hlt.Game()

# Declare global variables as shortands
me = None
game_map = None

# Initialize global variables for functions
first_ship_id = None
has_defended_spawn = None

# Pre computing before starting
game.ready("ShuzuiBot")

logging.info("Successfully created bot! My Player ID is {}.".format(game.my_id))
logging.info("The game is gonna last nb turns :  {}.".format(constants.MAX_TURNS))

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
    return cell.halite_amount > constants.MAX_HALITE * 5 / 100

def distance_to_base(ship):
    return game_map.calculate_distance(ship.position, me.shipyard.position)

def need_to_rush(ship):
    # Add arbitrary constant to distance considering that the ship may be blocked during cst turns
    remaining_turns = constants.MAX_TURNS - game.turn_number
    return  distance_to_base(ship) + 5 >= remaining_turns

def minimize_move_cost(ship, directions):
    # When there is multiple possibilities to reach destination at t turn, choose direction with lower cost
    lowest_cost = math.inf
    for direction in directions:
        target_pos = ship.position.directional_offset(direction)
        cost = game_map[target_pos].halite_amount
        if cost < lowest_cost:
            choice = direction
    return choice

def safe_navigate(ship, destination):
    return game_map.naive_navigate(ship, destination)

def unsafe_navigate(ship, destination):
    # This function return unsafe direction toward destination, chosing best lowest path cost
    direction =  minimize_move_cost(ship, game_map.get_unsafe_moves(ship.position, destination))
    target_pos = ship.position.directional_offset(direction)
    target_cell = game_map[target_pos]

    mark_safe(game_map[ship.position])
    target_cell.mark_unsafe(ship)

    return direction

def intending_navigate(ships):
    # Determine the move that each ship would do if collisions were ignored
    intentions = {}
    for ship in ships:
        intentions[ship.ip] = unsafe_navigate(ship, destination)


def navigate_to(ship, destination, steering_maker):
    if ship.halite_amount < game_map[ship.position].halite_amount * 10 / 100:
        # Make sure the ship has the ressources to move
        return commands.STAY_STILL

    if not need_to_rush(ship):
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
            return commands.STAY_STILL
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
    global game, me, game_map, command_queue, first_ship_id, has_defended_spawn

    # Update game
    game.update_frame()
    me = game.me
    game_map = game.game_map

    has_defended_spawn = False

    # Queue for commands to be executed
    command_queue = []

    # Update first ship id
    if first_ship_id == None and len(me.get_ships()) != 0:
        first_ship_id = me.get_ships()[0].id

    # Make decision for each ship one by one
    for ship in me.get_ships():
        logging.info("--> Control of ship id: {}".format(ship.id))

        # When playing with two players on a map, send a kamikaze to block enemy shipyard
        if ship.id == first_ship_id and len(game.players) == 2:
            enemy_player = None
            for key, player in game.players.items():
                if player.id != game.my_id:
                    enemy_player = player

            destination = enemy_player.shipyard.position
            direction = game_map.naive_navigate(ship, destination)
            command_queue.append(ship.move(direction))
            continue

        if need_to_rush(ship) or ship.halite_amount > constants.MAX_HALITE * 95 / 100:
            # When a ship is almost fully loaded or just have time to return shipyard, then return to shipyard
            logging.info(" --> Go drop halite, treshold 1 or RUSH time")
            destination = me.shipyard.position
            direction = navigate_to(ship, destination, steering_maker)
            command_queue.append(ship.move(direction))
        else:
            if is_interesting(game_map[ship.position]):
                # Keep collecting halite under the ship while the amount is interesting enough to collect
                logging.info("--> Collect")
                command_queue.append(ship.stay_still())
            else:
                if ship.halite_amount > constants.MAX_HALITE * 85 / 100:
                    # Lower bound of treshold to go back to a dropoff
                    logging.info("--> Go drop halite, treshold 2")
                    destination = me.shipyard.position
                    direction = navigate_to(ship, destination, steering_maker)
                    command_queue.append(ship.move(direction))
                else:
                    # Find the most interesting around the ship and move on it
                    logging.info("--> Go to best cell in range")
                    destination = best_around(ship, 0)
                    direction = navigate_to(ship, destination, steering_maker)
                    command_queue.append(ship.move(direction))


""" <<<Game Loop>>> """

while True:
    make_decisions(safe_navigate)

    # Keep creating ships while number of turns played is less than 200
    if game.turn_number <= 200 and me.halite_amount >= constants.SHIP_COST and not game_map[me.shipyard].is_occupied:
        command_queue.append(me.shipyard.spawn())

    game.end_turn(command_queue)
