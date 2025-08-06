from pathlib import Path
from enum import Enum
from random import randint
from src.system.GameConfig import WorldType
from src.system.GameConfig import DIFICULTY
from src.system.GameConfig import worlds_config
from src.system.world import World


class WorldManager:
    def __init__(self, difficulty: DIFICULTY,level_collection):
        self.__difficulty = difficulty
        self.__current_world_index = 0
        self.level_collection = level_collection

        world_id = worlds_config[self.__difficulty][self.__current_world_index]['monde']
        nb_levels = worlds_config[self.__difficulty][self.__current_world_index]['nb_level']
        self.current_world : World = World(self.level_collection, world_id, nb_levels)

    def set_current_world(self):
        world_id = worlds_config[self.__difficulty][self.__current_world_index]['monde']
        nb_levels = worlds_config[self.__difficulty][self.__current_world_index]['nb_level']
        self.curent_world = World(self.level_collection, world_id, nb_levels)
    
    def get_current_world(self) -> World:
        return self.curent_world
    
    def next_world(self):
        self.__current_world_index += 1
        self.set_current_world()