from pathlib import Path
from enum import Enum
from random import randint
from src.system.GameConfig import WorldType
from src.system.GameConfig import DIFFICULTY
from src.system.GameConfig import worlds_config
from src.system.world import World


class WorldManager:
    def __init__(self, difficulty: DIFFICULTY,level_collection):
        self.__difficulty = difficulty
        self.__current_world_index = 0
        self.level_collection = level_collection
        self.danger_offset = 0
        self.last_level_id = -1

        self.set_current_world()

    def set_current_world(self):
        world_id = worlds_config[self.__difficulty][self.__current_world_index]['monde']
        nb_levels = worlds_config[self.__difficulty][self.__current_world_index]['nb_level']
        if 'danger' in worlds_config[self.__difficulty][self.__current_world_index].keys():
            danger_level = worlds_config[self.__difficulty][self.__current_world_index]['danger']
        else:
            danger_level = 0
        self.current_world : World = World(self.level_collection, world_id, nb_levels,danger_level+self.danger_offset)
        
    def get_current_world(self) -> World:
        return self.current_world
    
    def next_world(self):
        # Si le monde actuel est le dernier du tableau, on recommence sur le premier monde de la difficulté
        if self.__current_world_index + 1 >= len(worlds_config[self.__difficulty]):
            self.__current_world_index = 0
            self.danger_offset += 3
        else:
            self.__current_world_index += 1
        self.set_current_world()
    
    def get_next_level_id(self) -> int:
        self.last_level_id = self.current_world.get_next_level_id(self.last_level_id)
        return self.last_level_id