from enum import Enum


class WorldType(Enum):
    MONDE_FORET = 0
    MONDE_JUNGLE = 1
    MONDE_VOLCAN = 2
    FIN_DE_PARTIE = 3


class DIFFICULTY(Enum):
    FACILE = 0
    NORMAL = 1
    DIFFICILE = 2
    OLD = 3
    TEST_DEBUG = 4


# les mondes augmente leur niveau de danger de 1 à chaque tableau
# un monde peut avoir un niveau de danger par défaut paramétré
# Chaque boss est associé à un type de monde, Chaque monde a un boss spécifique
# les niveaux de difficultée sont définis par une série de monde et le nombre de niveaux avant de rencontrer le boss
# une difficulté est dîtes infini si elle ne possède pas de monde de fin de partie, elle boucle donc sur la liste de monde
# quand une difficulté infini boucle, le niveau de danger par défaut de ses mondes augmente de 3
worlds_config = {
    DIFFICULTY.FACILE: [
        {"monde": WorldType.MONDE_FORET, "nb_level": 10},
        {"monde": WorldType.MONDE_JUNGLE, "nb_level": 10},
        {"monde": WorldType.FIN_DE_PARTIE, "nb_level": None},
    ],
    DIFFICULTY.NORMAL: [
        {"monde": WorldType.MONDE_FORET, "nb_level": 6},
        {"monde": WorldType.MONDE_JUNGLE, "nb_level": 7, "danger": 2},
        {"monde": WorldType.MONDE_VOLCAN, "nb_level": 7, "danger": 3},
        {"monde": WorldType.FIN_DE_PARTIE, "nb_level": None},
    ],
    DIFFICULTY.DIFFICILE: [
        {"monde": WorldType.MONDE_JUNGLE, "nb_level": 6, "danger": 2},
        {"monde": WorldType.MONDE_VOLCAN, "nb_level": 7, "danger": 4},
        {"monde": WorldType.MONDE_FORET, "nb_level": 7, "danger": 4},
    ],
    DIFFICULTY.OLD: [
        {"monde": WorldType.MONDE_JUNGLE, "nb_level": 7},
    ],
    DIFFICULTY.TEST_DEBUG: [
        {"monde": WorldType.MONDE_JUNGLE, "nb_level": 2},
        {"monde": WorldType.FIN_DE_PARTIE, "nb_level": None},
    ],
}
