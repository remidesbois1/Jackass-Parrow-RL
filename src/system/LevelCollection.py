from src.block.BlockGroup import BlockGroup
from src.block.Block import Block
from src.system.GameConfig import WorldType


class LevelCollection:
    # si il y a  5 élements alors le block est spawnable
    # les tuple à 2 éléments sont le point de spawn

    LEVEL1 = [
        (12, 14),
        (0, 5, 6, 2, True),
        (18, 5, 6, 2, True),
        (9, 9, 6, 2, True),
        (2, 13, 5, 3, True),
        (17, 13, 5, 3, True),
    ]
    LEVEL2 = [
        (12, 14),
        (5, 2, 3, 2),
        (11, 2, 3, 4),
        (17, 2, 3, 2),
        (5, 12, 3, 1, True),
        (11, 10, 3, 3, True),
        (17, 8, 3, 1, True),
    ]
    LEVEL3 = [
        (2, 14),
        # platform
        (6, 13, 6, 1, True),
        (1, 9, 4, 1, True),
        (5, 5, 4, 1, True),
        (12, 5, 5, 1, True),
        # autre
        (20, 9, 4, 1, True),
        (18, 13, 6, 1, True),
    ]
    LEVEL4 = [
        (15, 14),
        (-1, 4, 3, 2),
        (2, 4, 2, 7),
        (-1, -3, 3, 19),
        (2, 11, 3, 5),
        (4, 9, 1, 2),
        (5, 9, 2, 7),
        (7, 14, 3, 2),
        (17, 4, 4, 2, True),
        (17, 9, 4, 2, True),
        (17, 14, 4, 2, True),
    ]
    LEVEL5 = [
        (0, 10),
        (-1, 12, 4, 4),
        (3, 14, 2, 2),
        # (6, 13, 11, 3),
        (6, 8, 10, 2),
        (9, 6, 5, 3),
        (10, 3, 3, 3),
        (20, 3, 4, 2, True),
        (20, 8, 4, 2, True),
        (20, 14, 4, 2, True),
    ]
    LEVEL1HARD = [
        (12, 14),
        (0, 5, 6, 1, True),
        (18, 6, 6, 1, True),
        (10, 4, 5, 1, True),
        (9, 9, 6, 2, True),
        (3, 13, 4, 3, True),
        (17, 13, 4, 3, True),
        (0, 11, 3, 5, True),
        (21, 11, 3, 5, True),
    ]
    LEVEL2HARD = [
        (12, 14),
        (5, 1, 3, 3),
        (11, 1, 3, 5),
        (17, 1, 3, 3),
        (5, 12, 3, 1, True),
        (11, 10, 3, 3, True),
        (0, 10, 3, 6, True),
        (17, 8, 3, 1, True),
        (0, 6, 3, 1, True),
        (20, 14, 3, 1, True),
    ]
    LEVEL3HARD = [
        (2, 14),
        # platform
        (5, 4, 4, 1, True),
        (12, 5, 5, 1, True),
        (0, 9, 3, 1, True),
        (20, 8, 4, 1, True),
        (6, 13, 6, 1, True),
        (18, 12, 6, 1, True),
    ]
    LEVEL4HARD = [
        (15, 14),
        (-1, -3, 3, 19),
        (-1, 4, 3, 2),
        (2, 6, 2, 7, True),
        (4, 10, 3, 1, True),
        (2, 11, 3, 5),
        (7, 14, 3, 2, True),
        (17, 4, 4, 2, True),
        (17, 9, 4, 2, True),
        (17, 14, 4, 2, True),
    ]
    LEVEL5HARD = [
        (0, 10),
        (10, 4, 3, 3, True),
        (9, 7, 5, 3),
        (6, 8, 3, 2, True),
        (-1, 12, 4, 4),
        (3, 14, 2, 2, True),
        (21, 3, 4, 2, True),
        (21, 8, 4, 2, True),
        (21, 14, 4, 2, True),
    ]
    # équivalent des 5 niveaux en hard

    # des niveaux à perdre le sens

    LEVELS = [
        LEVEL1,
        LEVEL2,
        LEVEL3,
        LEVEL4,
        LEVEL5,
        LEVEL1HARD,
        LEVEL2HARD,
        LEVEL3HARD,
        LEVEL4HARD,
        LEVEL5HARD,
    ]

    def __init__(self, blockGroup: BlockGroup):
        self.blocks = blockGroup
        self.playerSpawn = (0, 0)

    def build_tableau(self, lstBloc: list):
        # sol
        self.blocks.add(Block(-1, 16, 26, 1))
        # mur
        self.blocks.add(Block(-2, -8, 1, 28))
        self.blocks.add(Block(25, -8, 1, 28))

        # bloc contenus dans le paramètre lstBloc
        for bloc in lstBloc:
            if len(bloc) == 2:
                self.playerSpawn = (bloc[0] * 50, bloc[1] * 50)
            else:
                if len(bloc) <= 4:
                    spawn = False
                else:
                    spawn = bloc[4]
                if len(bloc) <= 5:
                    transparent = False
                else:
                    transparent = bloc[5]
                self.blocks.add(
                    Block(
                        x=bloc[0],
                        y=bloc[1],
                        width=bloc[2],
                        height=bloc[3],
                        spawnable=spawn,
                        transparent=transparent,
                    )
                )

    def load_boss(self, world_index: WorldType):
        if world_index == WorldType.MONDE_JUNGLE:
            lstBloc = [
                (1, 1),
                (-1, 3, 2, 1, False),
                (-1, 7, 4, 1, False),
                (-1, 11, 6, 1, False),
                (-1, 15, 8, 1, False),
                (17, 14, 6, 2, False),
                (17, 0, 6, 3),
                (17, 3, 1, 11, False, True),
            ]
        else:
            raise NotImplementedError(
                f"Aucun boss ne correspond au monde {WorldType(world_index).name}"
            )
        self.build_tableau(lstBloc)

    def load(self, levelId):
        lstBloc = self.LEVELS[levelId - 1]
        self.build_tableau(lstBloc)
