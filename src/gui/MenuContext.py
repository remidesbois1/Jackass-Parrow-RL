class MenuContext:
    START_MENU = 'start'
    INGAME_MENU = 'game'
    END_MENU = 'end'
    INTRO_BOSS_MENU = 'intro_boss'
    OUTRO_BOSS_MENU = 'outro_boss'

    def __init__(self,default_menu:str=START_MENU):
        self.__active_menu = None
        self.set_active_menu(default_menu)

    def set_active_menu(self, menu:str):
        if menu not in (self.START_MENU, self.INGAME_MENU, self.END_MENU, self.INTRO_BOSS_MENU,self.OUTRO_BOSS_MENU):
            raise ValueError(f"Invalid menu: {menu}")
        self.__active_menu = menu

    def get_active_menu(self) -> str:
        return self.__active_menu