from src.system import level_data
from src.block.BlockGroup import BlockGroup
from src.block.Block import Block
from src.system.GameConfig import WorldType


class LevelCollection:
    # si il y a  5 élements alors le block est spawnable
    # les tuple à 2 éléments sont le point de spawn

    LEVEL1 = level_data.LEVEL1
    LEVEL2 = level_data.LEVEL2
    LEVEL3 = level_data.LEVEL3
    LEVEL4 = level_data.LEVEL4
    LEVEL5 = level_data.LEVEL5
    LEVEL1HARD = level_data.LEVEL1HARD
    LEVEL2HARD = level_data.LEVEL2HARD
    LEVEL3HARD = level_data.LEVEL3HARD
    LEVEL4HARD = level_data.LEVEL4HARD
    LEVEL5HARD = level_data.LEVEL5HARD
    LEVELS = level_data.LEVELS

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
            lstBloc = level_data.BOSS_JUNGLE
        else:
            raise NotImplementedError(
                f"Aucun boss ne correspond au monde {WorldType(world_index).name}"
            )
        self.build_tableau(lstBloc)

    def load(self, levelId):
        lstBloc = self.LEVELS[levelId - 1]
        self.build_tableau(lstBloc)
