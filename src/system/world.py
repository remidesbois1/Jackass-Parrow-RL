
from pathlib import Path
from enum import Enum
from random import randint
from src.system.GameConfig import WorldType

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BACKGROUND_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "background" / "fondGameJam.png"




class BossType(Enum):
    BALERINO = 1
    TOM = 2
    PAYA = 3

class World:
    def __init__(self, level_collection,monde_index: WorldType,nb_levels: int,danger_level=0):
        self.monde_index = monde_index
        self.level_collection = level_collection
        self.nb_levels = nb_levels
        self.current_level = 0
        self.danger_level = danger_level

    def get_next_level_id(self)-> int:
        #à changer
        if  self.monde_index == WorldType.MONDE_JUNGLE:
            idNiveau = randint(5, 10)
        elif self.monde_index == WorldType.MONDE_JUNGLE:
            idNiveau = randint(1, 5)
        self.current_level += 1
        self.danger_level += 1
        return idNiveau
        
    

