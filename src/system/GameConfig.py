
from enum import Enum


class WorldType(Enum):
    MONDE_FORET = 0
    MONDE_JUNGLE = 1
    MONDE_VOLCAN = 2
    FIN_DE_PARTIE = 3
    

class DIFICULTY(Enum):
    FACILE = 0
    NORMAL = 1
    DIFFICILE = 2
    OLD = 3
    TEST_DEBUG = 4

# Chaque boss est associé à un type de monde, Chaque monde a un boss spécifique
# les niveaux de difficultée sont définis par une série de monde et le nombre de niveaux avant de rencontrer le boss
# une difficulté est dîtes infini si elle ne possède pas de monde de fin de partie, elle boucle donc sur la liste de monde 

worlds_config = {
    DIFICULTY.FACILE: [
        {"monde": WorldType.MONDE_FORET, "nb_level": 10},
        {"monde": WorldType.MONDE_JUNGLE, "nb_level": 10},
        {"monde": WorldType.FIN_DE_PARTIE, "nb_level": None},
    ],
    DIFICULTY.NORMAL: [
        {"monde": WorldType.MONDE_FORET, "nb_level": 6},
        {"monde": WorldType.MONDE_JUNGLE, "nb_level": 7},
        {"monde": WorldType.MONDE_VOLCAN, "nb_level": 7},
        {"monde": WorldType.FIN_DE_PARTIE, "nb_level": None},
    ],
    DIFICULTY.DIFFICILE: [
        {"monde": WorldType.MONDE_JUNGLE, "nb_level": 6},
        {"monde": WorldType.MONDE_VOLCAN, "nb_level": 7},
        {"monde": WorldType.MONDE_FORET, "nb_level": 7},
    ],
    DIFICULTY.OLD: [
        {"monde": WorldType.MONDE_JUNGLE, "nb_level": 2},
    ],
    DIFICULTY.TEST_DEBUG: [
        {"monde": WorldType.MONDE_JUNGLE, "nb_level": 2},
        {"monde": WorldType.FIN_DE_PARTIE, "nb_level": None}
    ]
}
