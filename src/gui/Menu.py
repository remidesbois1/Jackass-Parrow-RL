# src/gui/Menu.py

import pygame
import json
import pygame_gui
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CAT_COMIC_FONT_PATH = PROJECT_ROOT / "assets" / "fonts" / "Cat Comic.ttf"
DIMBO_FONT_PATH = PROJECT_ROOT / "assets" / "fonts" / "Dimbo Regular.ttf"
TOM_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "entity" / "tom.png"
PLAYERHD_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "player" / "playerHD.png"
SCORES_FILE_PATH = PROJECT_ROOT / "scores.json"
MENU_BG_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "background" / "menu.png"

class Menu:
    def __init__(self, game, ui_manager):
        self.game = game
        self.ui_manager = ui_manager
        self.menu_font = pygame.font.Font(str(CAT_COMIC_FONT_PATH), 80)
        self.lore_font = pygame.font.Font(str(DIMBO_FONT_PATH), 38)
        self.button_font = pygame.font.Font(str(CAT_COMIC_FONT_PATH), 50)
        self.leaderboard_font = pygame.font.Font(str(CAT_COMIC_FONT_PATH), 40)
        
        self.start_button = None
        self.boss_button = None
        self.lore_button = None
        self.leaderboard_button = None
        
        # Windows and their close buttons
        self.lore_window = None
        self.leaderboard_window = None
        self.lore_close_button = None
        self.leaderboard_close_button = None
        
        self.setup_start_menu()

    def handleMenu(self, event, game:"App"):
        if game.activeMenu in ("start", "leaderboard", "lore") and event.type == pygame.MOUSEBUTTONDOWN:
            if game.start_button_rect.collidepoint(event.pos) and not game.show_leaderboard:
                game.show_start_menu = False  # Démarre le jeu
                game.game_manager.start_game()
    def setup_start_menu(self):
        button_width = 220
        button_height = 80
        x_pos = self.game.weight // 2 - button_width // 2
        
        self.start_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((x_pos, self.game.height // 2), (button_width, button_height)),
                                                            text='Lancer',
                                                            manager=self.ui_manager,
                                                            object_id='@menu_button')

        self.boss_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((x_pos, self.game.height // 2 + 70), (button_width, button_height)),
                                                           text='Mode Boss',
                                                           manager=self.ui_manager,
                                                           object_id='@menu_button')

        self.lore_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((x_pos, self.game.height // 2 + 140), (button_width, button_height)),
                                                         text='Histoire',
                                                         manager=self.ui_manager,
                                                         object_id='@menu_button')
                                                         
        self.leaderboard_button = pygame_gui.elements.UIButton(relative_rect=pygame.Rect((x_pos, self.game.height // 2 + 210), (button_width, button_height)),
                                                                    text='Classement',
                                                                    manager=self.ui_manager,
                                                                    object_id='@menu_button')
    def handleMenu(self, event, game):
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.start_button:
                game.show_start_menu = False
                game.startGame()
                pygame.mixer.Sound(game.sounds.son_button).play()
                game.activeMenu = "game"
                self.hide_start_menu()
            elif event.ui_element == self.boss_button:
                game.show_start_menu = False
                game.game_manager.boss_mode = True
                pygame.mixer.Sound(game.sounds.son_button).play()
                game.game_manager.start_boss_mode()
                game.activeMenu = "game"
                self.hide_start_menu()
            elif event.ui_element == self.lore_button:
                pygame.mixer.Sound(game.sounds.son_button).play()
                self.show_lore_window()
            elif event.ui_element == self.leaderboard_button:
                pygame.mixer.Sound(game.sounds.son_button).play()
                self.show_leaderboard_window()
            elif self.lore_close_button and event.ui_element == self.lore_close_button:
                self.lore_window.kill()
                self.lore_window = None
                self.lore_close_button = None
            elif self.leaderboard_close_button and event.ui_element == self.leaderboard_close_button:
                self.leaderboard_window.kill()
                self.leaderboard_window = None
                self.leaderboard_close_button = None


        if event.type == pygame_gui.UI_WINDOW_CLOSE:
            if self.lore_window and event.ui_element == self.lore_window:
                self.lore_window.kill()
                self.lore_window = None
                self.lore_close_button = None
            if self.leaderboard_window and event.ui_element == self.leaderboard_window:
                self.leaderboard_window.kill()
                self.leaderboard_window = None
                self.leaderboard_close_button = None

    def show_start_screen(self):
        self.game.activeMenu = "start"
        self.start_button.show()
        self.boss_button.show()
        self.lore_button.show()
        self.leaderboard_button.show()


        # TOM
        tom_image = pygame.image.load(str(TOM_IMAGE_PATH)).convert_alpha()
        tom_image = pygame.transform.scale(tom_image, (
            tom_image.get_width() * self.game.height // 1.4 // tom_image.get_height(), self.game.height // 1.4))

        tom_rect = tom_image.get_rect(
            center=(tom_image.get_width() // 2 + 50, self.game.height // 2))
        self.game.gameSurface.blit(tom_image, tom_rect)

        # PERSO PRINCIPAL
        perso_image = pygame.image.load(str(PLAYERHD_IMAGE_PATH)).convert_alpha()
        perso_image = pygame.transform.scale(perso_image, (
            perso_image.get_width() * self.game.height // 1.4 // perso_image.get_height(), self.game.height // 1.4))

        perso_rect = perso_image.get_rect(
            center=(perso_image.get_width() // 0.45, self.game.height // 2))
        self.game.gameSurface.blit(perso_image, perso_rect)

        title_text = self.menu_font.render("Jackass-Parrow", True, (50, 50, 50))
        title_rect = title_text.get_rect(center=(self.game.width // 2 + 5, self.game.height // 3 + 5))
        self.game.gameSurface.blit(title_text, title_rect)
        title_text = self.menu_font.render("Jackass-Parrow", True, (255, 255, 255))
        title_rect = title_text.get_rect(center=(self.game.width // 2, self.game.height // 3))
        self.game.gameSurface.blit(title_text, title_rect)


        start_text = self.button_font.render("Lancer", True, (255, 255, 255))
        self.game.start_button_rect = start_text.get_rect()
        self.game.start_button_rect.width += 10 * 2
        self.game.start_button_rect.height += 10 * 2
        self.game.start_button_rect.center = (self.game.width // 2, self.game.height // 2)

    def hide_start_menu(self):
        self.start_button.hide()
        self.boss_button.hide()
        self.lore_button.hide()
        self.leaderboard_button.hide()

    def show_lore_window(self):
        if self.lore_window is None:
            lore_text = """
            Quand il était jeune, Jackass-Parrow n'était pas le pirate le plus agile du navire.
            C'est pour cela que ses parents lui ont greffé un canon scié sur l'arrière-train en guise de cadeau d'anniversaire.
            Malheureusement, celui-ci fut exclu de sa fratrie lorsqu'il tira accidentellement dans la tête de son père en voulant s'étirer.
            Jackass-Parrow passa donc le reste de son enfance dans une jungle, élevé par une tribu indigène.

            Aujourd'hui, menacé par Tom de l'Abbaye et ses chevaliers, Jackass-Parrow est prêt à tout pour défendre ceux qui l'ont recueilli.
            """
            window_rect = pygame.Rect((self.game.weight // 4, self.game.height // 6), (self.game.weight // 2, self.game.height // 1.5))

            button_width, button_height, padding = 180, 70, 20
            text_box_height = window_rect.height - button_height - padding * 2

            self.lore_window = pygame_gui.elements.UIWindow(
                rect=window_rect,
                manager=self.ui_manager,
                window_display_title='',
                object_id='@window',
                resizable=False,
                draggable=False
            )

            background_image_surface = pygame.image.load(str(MENU_BG_IMAGE_PATH)).convert_alpha()

            pygame_gui.elements.UIImage(
                relative_rect=pygame.Rect((0, 0), self.lore_window.get_container().get_size()),
                image_surface=background_image_surface,
                manager=self.ui_manager,
                container=self.lore_window
            )


            text_box = pygame_gui.elements.UITextBox(
                html_text=lore_text,
                relative_rect=pygame.Rect(padding, padding, window_rect.width - padding * 2, text_box_height),
                manager=self.ui_manager,
                container=self.lore_window,
                object_id='@text_box_in_window'
            )

            button_x = (window_rect.width - button_width) // 2
            button_y = text_box.get_relative_rect().bottom + padding

            self.lore_close_button = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect((button_x, button_y), (button_width, button_height)),
                text='Fermer',
                manager=self.ui_manager,
                container=self.lore_window,
                object_id='@menu_button'
            )


    def show_leaderboard_window(self):
        if self.leaderboard_window is None:
            try:
                with open(SCORES_FILE_PATH, "r") as f:
                    scores = json.load(f)
            except FileNotFoundError:
                scores = []

        boss_text = self.button_font.render("Mode Boss", True, (255, 255, 255))
        self.game.boss_button_rect = boss_text.get_rect()
        self.game.boss_button_rect.width += 10 * 2
        self.game.boss_button_rect.height += 10 * 2
        self.game.boss_button_rect.center = (self.game.width // 2, self.game.height // 1.22)

        pygame.draw.rect(self.game.gameSurface, boss_button_color, self.game.boss_button_rect, border_radius=10)
        boss_text_rect = boss_text.get_rect(center=self.game.boss_button_rect.center)
        self.game.gameSurface.blit(boss_text, boss_text_rect)

        # bouton lore
        lore_text = self.button_font.render("Histoire", True, (255, 255, 255))
        self.game.lore_button_rect = lore_text.get_rect(center=(self.game.width // 2, self.game.height // 1.4))
        pygame.draw.rect(self.game.gameSurface, (139, 69, 19), self.game.lore_button_rect,
                         border_radius=10)
        self.game.gameSurface.blit(lore_text, self.game.lore_button_rect)

        if self.game.show_lore:
            self.show_lore_menu()

            # bouton classement
        if self.game.show_leaderboard_button:
            leaderboard_text = self.button_font.render("Classement", True, (255, 255, 255))
            self.game.leaderboard_button_rect = leaderboard_text.get_rect(
                center=(self.game.width // 2, self.game.height // 1.6))
            pygame.draw.rect(self.game.gameSurface, (139, 69, 19), self.game.leaderboard_button_rect,
                             border_radius=10)
            self.game.gameSurface.blit(leaderboard_text, self.game.leaderboard_button_rect)

        if self.game.show_leaderboard:
            self.show_leaderboard_screen()



    def show_lore_menu(self):
        self.game.activeMenu = "lore"


        lore_surface = pygame.Surface((self.game.width // 1.3, self.game.height // 1.3), pygame.SRCALPHA)
        lore_surface.fill((0, 0, 0, 220))
        lore_rect = lore_surface.get_rect(center=(self.game.width // 2, self.game.height // 2))
        self.game.gameSurface.blit(lore_surface, lore_rect)

        title_text = self.menu_font.render("Histoire", True, (255, 255, 255))
        title_rect = title_text.get_rect(center=(self.game.width // 2, self.game.height // 5))
        self.game.gameSurface.blit(title_text, title_rect)

        lore_content = """
                Quand il était jeune, Jackass-Parrow n'était pas le pirate le plus agile du navire.
                C'est pour cela que ses parents lui ont greffé un canon scié sur l'arrière-train en guise de cadeau d'anniversaire.
                Malheureusement, celui-ci fut exclu de sa fratrie lorsqu'il tira accidentellement dans la tête de son père en voulant s'étirer.
                Jackass-Parrow passa donc le reste de son enfance dans une jungle, élevé par une tribu indigène.

                Aujourd'hui, menacé par Tom de l'Abbaye et ses chevaliers, Jackass-Parrow est prêt à tout pour défendre ceux qui l'ont recueilli.
                """

        line_height = 40
        x_pos = lore_rect.left + 50
        y_pos = lore_rect.top + 100
        max_width = lore_rect.width - 100

        wrapped_lines = self.wrap_text(lore_content, self.leaderboard_font, max_width)

        for line in wrapped_lines:
            text_surface = self.lore_font.render(line, True, (255, 255, 255))
            text_rect = text_surface.get_rect(topleft=(x_pos, y_pos))
            self.game.gameSurface.blit(text_surface, text_rect)
            y_pos += line_height

        close_text = self.button_font.render("Fermer", True, (255, 255, 255))
        self.game.close_lore_button_rect = close_text.get_rect(center=(self.game.width // 2, self.game.height // 1.2))
        pygame.draw.rect(self.game.gameSurface, (180, 69, 40), self.game.close_lore_button_rect,
                         border_radius=10)
        self.game.gameSurface.blit(close_text, self.game.close_lore_button_rect)

    def wrap_text(self, text, font, max_width):
        lines = []
        words = text.split()

        while words:
            line = ""
            while words and font.size(line + words[0])[0] <= max_width:
                line += (words.pop(0) + " ")
            lines.append(line)

        return lines


    def show_leaderboard_screen(self):
        self.game.activeMenu = "leaderboard"
        leaderboard_surface = pygame.Surface((self.game.width // 1.5, self.game.height // 1.5), pygame.SRCALPHA)
        leaderboard_surface.fill((139, 69, 19, 220))
        leaderboard_rect = leaderboard_surface.get_rect(center=(self.game.width // 2, self.game.height // 2))
        self.game.gameSurface.blit(leaderboard_surface, leaderboard_rect)

        title_text = self.menu_font.render("Classement", True, (255, 255, 255))
        title_rect = title_text.get_rect(center=(self.game.width // 2, self.game.height // 4))
        self.game.gameSurface.blit(title_text, title_rect)

        try:
            with open("scores.json", "r") as f:
                scores = json.load(f)
        except FileNotFoundError:
            scores = []

        scores.sort(key=lambda x: x["score"], reverse=True)

        # 10 meilleurs scores
        y_offset = self.game.height // 3
        for i, score in enumerate(scores[:10]):
            score_text = self.leaderboard_font.render(f"{i + 1}. {score['pseudo']} - {score['score']}", True,
                                                      (255, 255, 255))
            score_rect = score_text.get_rect(center=(self.game.width // 2, y_offset))
            self.game.gameSurface.blit(score_text, score_rect)
            y_offset += 40

        close_text = self.button_font.render("Fermer", True, (255, 255, 255))
        self.game.close_button_rect = close_text.get_rect(center=(self.game.width // 1.35, self.game.height // 4))
        pygame.draw.rect(self.game.gameSurface, (180, 69, 40), self.game.close_button_rect, border_radius=10)  # Couleur marron
        self.game.gameSurface.blit(close_text, self.game.close_button_rect)

    def show_end_screen(self):
        self.game.activeMenu = "end"
        frame_surface = pygame.Surface((self.game.width // 1.3, self.game.height // 1.3), pygame.SRCALPHA)
        frame_surface.fill((0, 0, 0, 164))
        frame_rect = frame_surface.get_rect(center=(self.game.width // 2, self.game.height // 2))
        self.game.gameSurface.blit(frame_surface, frame_rect)

        end_text = self.menu_font.render("Game Over", True, (255, 255, 255))
        end_text_rect = end_text.get_rect(center=(self.game.width // 2 + 5, self.game.height // 3 + 5))
        self.game.gameSurface.blit(end_text, end_text_rect)

        score_text = self.menu_font.render(f"Score : {self.game.game_manager.player.score}", True, (255, 255, 255))
        score_text_rect = score_text.get_rect(center=(self.game.width // 2 + 5, self.game.height // 2 + 5))
        self.game.gameSurface.blit(score_text, score_text_rect)

        # zone saisie pseudo
        pygame.draw.rect(self.game.gameSurface, self.game.input_box_color, self.game.input_box, 2)
        input_text = self.button_font.render(self.game.user_text, True, (255, 255, 255))
        input_text_rect = input_text.get_rect(
            topleft=(self.game.input_box.x + 5, self.game.input_box.y + 5))
        self.game.gameSurface.blit(input_text, input_text_rect)


        # bouton enregistrer
        save_text = self.button_font.render("Enregistrer", True, (255, 255, 255))
        self.game.save_button_rect = save_text.get_rect(center=(self.game.width // 2, self.game.height // 1.3))

        # changement de couleur
        mouse_pos = pygame.mouse.get_pos()
        save_button_color = (0, 150, 0)
        if self.game.save_button_rect.collidepoint(mouse_pos):
            save_button_color = (0, 200, 0)

        pygame.draw.rect(self.game.gameSurface, save_button_color, self.game.save_button_rect, border_radius=10)
        self.game.gameSurface.blit(save_text, self.game.save_button_rect)

    def show_boss_intro(self):
        self.game.activeMenu = "intro"
        intro_text = [
            "Le combat final approche",
            "Préparez-vous à combattre le grand...",
            "** TOM DE L'ABBAYE  **",
        ]

        font = pygame.font.Font(str(DIMBO_FONT_PATH), 52)
        text_color = (255, 255, 255)
        background_color = (0, 0, 0)
        padding = 60
        alpha = 150

        text_surfaces = []
        max_width = 0
        total_height = 0
        for line in intro_text:
            text_surface = font.render(line, True, text_color)
            text_surfaces.append(text_surface)
            max_width = max(max_width, text_surface.get_width())
            total_height += text_surface.get_height()

        background_width = max_width + 2 * padding
        background_height = total_height + 2 * padding
        background_surface = pygame.Surface((background_width, background_height),
                                            pygame.SRCALPHA)
        background_surface.fill((*background_color, alpha))

        screen_width = self.game.gameSurface.get_width()
        screen_height = self.game.gameSurface.get_height()
        background_x = (screen_width - background_width) // 2
        background_y = (screen_height - background_height) // 2

        y_offset = padding
        for text_surface in text_surfaces:
            text_x = (background_width - text_surface.get_width()) // 2
            background_surface.blit(text_surface, (text_x, y_offset))
            y_offset += text_surface.get_height()

        self.game.gameSurface.blit(background_surface, (background_x, background_y))

    def show_boss_win(self):
        victory_text = [
            "Victoire !",
            "Vous avez vaincu l'abominable",
            "",
            "Tom de L'Abbaye !!",
            "",
            "Merci d'avoir joué!"
        ]

        font = pygame.font.Font(str(DIMBO_FONT_PATH), 48)
        text_color = (255, 255, 255)
        background_color = (0, 0, 0)
        padding = 20
        alpha = 150

        text_surfaces = []
        max_width = 0
        total_height = 0
        for line in victory_text:
            text_surface = font.render(line, True, text_color)
            text_surfaces.append(text_surface)
            max_width = max(max_width, text_surface.get_width())
            total_height += text_surface.get_height()

        background_width = max_width + 2 * padding
        background_height = total_height + 2 * padding
        background_surface = pygame.Surface((background_width, background_height), pygame.SRCALPHA)
        background_surface.fill((*background_color, alpha))

        screen_width = self.game.gameSurface.get_width()
        screen_height = self.game.gameSurface.get_height()
        background_x = (screen_width - background_width) // 2
        background_y = (screen_height - background_height) // 2

        y_offset = padding
        for text_surface in text_surfaces:
            text_x = (background_width - text_surface.get_width()) // 2
            background_surface.blit(text_surface, (text_x, y_offset))
            y_offset += text_surface.get_height()

        self.game.gameSurface.blit(background_surface, (background_x, background_y))


    # pareil à réecrire
    def show_end_screen(self):
        self.game.activeMenu = "end"
        frame_surface = pygame.Surface((self.game.weight // 1.3, self.game.height // 1.3), pygame.SRCALPHA)
        frame_surface.fill((0, 0, 0, 164))
        frame_rect = frame_surface.get_rect(center=(self.game.weight // 2, self.game.height // 2))
        self.game.gameSurface.blit(frame_surface, frame_rect)

        end_text = self.menu_font.render("Game Over", True, (255, 255, 255))
        end_text_rect = end_text.get_rect(center=(self.game.weight // 2 + 5, self.game.height // 3 + 5))
        self.game.gameSurface.blit(end_text, end_text_rect)

        score_text = self.menu_font.render(f"Score : {self.game.player.score}", True, (255, 255, 255))
        score_text_rect = score_text.get_rect(center=(self.game.weight // 2 + 5, self.game.height // 2 + 5))
        self.game.gameSurface.blit(score_text, score_text_rect)

        # zone saisie pseudo
        pygame.draw.rect(self.game.gameSurface, self.game.input_box_color, self.game.input_box, 2)
        input_text = self.button_font.render(self.game.user_text, True, (255, 255, 255))
        input_text_rect = input_text.get_rect(
            topleft=(self.game.input_box.x + 5, self.game.input_box.y + 5))
        self.game.gameSurface.blit(input_text, input_text_rect)


        # bouton enregistrer
        save_text = self.button_font.render("Enregistrer", True, (255, 255, 255))
        self.game.save_button_rect = save_text.get_rect(center=(self.game.weight // 2, self.game.height // 1.3))

        # changement de couleur
        mouse_pos = pygame.mouse.get_pos()
        save_button_color = (0, 150, 0)
        if self.game.save_button_rect.collidepoint(mouse_pos):
            save_button_color = (0, 200, 0)

        pygame.draw.rect(self.game.gameSurface, save_button_color, self.game.save_button_rect, border_radius=10)
        self.game.gameSurface.blit(save_text, self.game.save_button_rect)