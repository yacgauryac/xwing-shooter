"""
Menu principal — Écran titre avec starfield animé.
"""

from direct.gui.OnscreenText import OnscreenText
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode, Vec4, TransparencyAttrib, ClockObject
import math

globalClock = ClockObject.getGlobalClock()


C_BRIGHT = Vec4(1.0, 0.7, 0.2, 1.0)
C_ORANGE = Vec4(0.9, 0.55, 0.15, 1.0)
C_DIM = Vec4(0.5, 0.3, 0.1, 0.6)
C_SELECTED = Vec4(1.0, 0.8, 0.3, 1.0)


class MainMenu:
    """Menu principal du jeu."""

    ENTRIES_MAIN = [
        ("SOLO", "solo"),
        ("COOP LAN", "coop"),
        ("LEADERBOARD", "leaderboard"),
        ("OPTIONS", "options"),
        ("QUITTER", "quit"),
    ]

    ENTRIES_OPTIONS = [
        ("VOLUME SFX  +", "sfx_up"),
        ("VOLUME SFX  -", "sfx_down"),
        ("PLEIN ECRAN", "fullscreen"),
        ("RETOUR", "back"),
    ]

    def __init__(self, game):
        self.game = game
        self.active = False
        self.selected = 0
        self.current_menu = "main"
        self.elements = []
        self.timer = 0.0

        # Titre
        self.title = None
        self.subtitle = None
        self.bg = None
        self.entry_texts = []

    def show(self):
        """Affiche le menu principal."""
        self.hide()
        self.active = True
        self.selected = 0
        self.current_menu = "main"

        # Fond sombre
        self.bg = DirectFrame(
            frameColor=Vec4(0, 0, 0, 0.85),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=200,
        )

        # Titre
        self.title = OnscreenText(
            text="X-WING SHOOTER",
            pos=(0, 0.6), scale=0.12,
            fg=C_BRIGHT, align=TextNode.ACenter, sort=210,
            shadow=(0, 0, 0, 1),
        )
        self.subtitle = OnscreenText(
            text="A long time ago in a galaxy far, far away...",
            pos=(0, 0.48), scale=0.03,
            fg=C_DIM, align=TextNode.ACenter, sort=210,
        )

        self._build_entries(self.ENTRIES_MAIN)

        # Contrôles
        self.controls_text = OnscreenText(
            text="Z/S: navigate  |  ENTER: select  |  ESC: back",
            pos=(0, -0.85), scale=0.022,
            fg=Vec4(0.5, 0.3, 0.1, 0.4), align=TextNode.ACenter, sort=210,
        )

        # Bindings
        self.game.accept("arrow_up", self._nav_up)
        self.game.accept("arrow_down", self._nav_down)
        self.game.accept("z-repeat", self._nav_up)
        self.game.accept("s-repeat", self._nav_down)
        self.game.accept("z", self._nav_up)
        self.game.accept("s", self._nav_down)
        self.game.accept("enter", self._select)
        self.game.accept("space", self._select)
        self.game.accept("escape", self._back)

        # Task pour l'animation
        self.game.taskMgr.add(self._update_menu, "menu_update")

    def _build_entries(self, entries):
        """Construit les textes du menu."""
        for t in self.entry_texts:
            t.destroy()
        self.entry_texts = []

        start_y = 0.2
        spacing = 0.1

        for i, (label, _) in enumerate(entries):
            t = OnscreenText(
                text=label,
                pos=(0, start_y - i * spacing),
                scale=0.045,
                fg=C_ORANGE, align=TextNode.ACenter,
                mayChange=True, sort=210,
                shadow=(0, 0, 0, 0.6),
            )
            self.entry_texts.append(t)

        self._update_selection()

    def _update_selection(self):
        """Met à jour la surbrillance."""
        entries = self._get_entries()
        for i, t in enumerate(self.entry_texts):
            if i == self.selected:
                t.setFg(C_SELECTED)
                t.setScale(0.05)
            else:
                t.setFg(C_ORANGE)
                t.setScale(0.045)

    def _get_entries(self):
        if self.current_menu == "options":
            return self.ENTRIES_OPTIONS
        return self.ENTRIES_MAIN

    def _nav_up(self):
        if not self.active:
            return
        entries = self._get_entries()
        self.selected = (self.selected - 1) % len(entries)
        self._update_selection()

    def _nav_down(self):
        if not self.active:
            return
        entries = self._get_entries()
        self.selected = (self.selected + 1) % len(entries)
        self._update_selection()

    def _select(self):
        if not self.active:
            return
        entries = self._get_entries()
        _, action = entries[self.selected]

        if action == "solo":
            self.hide()
            self.game.start_game()
        elif action == "coop":
            # Coming soon
            if self.subtitle:
                self.subtitle.setText("COOP LAN — COMING SOON")
                self.subtitle.setFg(Vec4(1, 0.5, 0.1, 0.8))
        elif action == "leaderboard":
            self._show_leaderboard()
        elif action == "options":
            self.current_menu = "options"
            self.selected = 0
            self._build_entries(self.ENTRIES_OPTIONS)
        elif action == "quit":
            self.game.userExit()
        elif action == "sfx_up":
            if hasattr(self.game, 'sounds'):
                self.game.sounds.sfx_volume = min(1.0, self.game.sounds.sfx_volume + 0.1)
                self._show_volume()
        elif action == "sfx_down":
            if hasattr(self.game, 'sounds'):
                self.game.sounds.sfx_volume = max(0.0, self.game.sounds.sfx_volume - 0.1)
                self._show_volume()
        elif action == "fullscreen":
            self.game.toggle_fullscreen()
        elif action == "back":
            self.current_menu = "main"
            self.selected = 0
            self._build_entries(self.ENTRIES_MAIN)

    def _back(self):
        if not self.active:
            return
        if self.current_menu != "main":
            self.current_menu = "main"
            self.selected = 0
            self._build_entries(self.ENTRIES_MAIN)
        else:
            self.game.userExit()

    def _show_volume(self):
        vol = int(self.game.sounds.sfx_volume * 100)
        if self.subtitle:
            self.subtitle.setText(f"SFX VOLUME: {vol}%")
            self.subtitle.setFg(C_ORANGE)

    def _show_leaderboard(self):
        """Affiche le leaderboard depuis le menu."""
        if hasattr(self.game, 'leaderboard'):
            entries = self.game.leaderboard.entries
            # Efface les entrées du menu
            for t in self.entry_texts:
                t.destroy()
            self.entry_texts = []

            # Titre
            t = OnscreenText(
                text="TOP PILOTS", pos=(0, 0.3), scale=0.05,
                fg=C_BRIGHT, align=TextNode.ACenter, sort=210,
                shadow=(0, 0, 0, 0.8),
            )
            self.entry_texts.append(t)

            # Header
            t = OnscreenText(
                text="  #   NAME   SCORE    WAVE  KILLS   DATE",
                pos=(0, 0.22), scale=0.022,
                fg=C_DIM, align=TextNode.ACenter, sort=210,
            )
            self.entry_texts.append(t)

            for i, entry in enumerate(entries[:10]):
                rank = i + 1
                name = entry.get("name", "???")
                score = entry.get("score", 0)
                wave = entry.get("wave", 0)
                kills = entry.get("kills", 0)
                date = entry.get("date", "")
                line = f" {rank:>2}.   {name}   {score:>6}     {wave:>2}     {kills:>3}   {date}"
                t = OnscreenText(
                    text=line, pos=(0, 0.14 - i * 0.06), scale=0.025,
                    fg=C_ORANGE, align=TextNode.ACenter, sort=210,
                )
                self.entry_texts.append(t)

            t = OnscreenText(
                text="PRESS ESC TO GO BACK",
                pos=(0, -0.5), scale=0.025,
                fg=C_DIM, align=TextNode.ACenter, sort=210,
            )
            self.entry_texts.append(t)

            self.current_menu = "leaderboard"

    def _update_menu(self, task):
        """Animation du menu."""
        if not self.active:
            return task.done
        self.timer += globalClock.getDt()

        # Pulse du titre
        if self.title:
            pulse = 0.95 + 0.05 * math.sin(self.timer * 2.0)
            self.title.setScale(0.12 * pulse)

        return task.cont

    def hide(self):
        """Cache le menu et nettoie."""
        self.active = False

        # Remove task
        self.game.taskMgr.remove("menu_update")

        # Unbind menu keys
        for key in ["arrow_up", "arrow_down", "z-repeat", "s-repeat",
                     "z", "s", "enter", "space", "escape"]:
            self.game.ignore(key)

        # Destroy elements
        if self.bg:
            self.bg.destroy()
            self.bg = None
        if self.title:
            self.title.destroy()
            self.title = None
        if self.subtitle:
            self.subtitle.destroy()
            self.subtitle = None
        if hasattr(self, 'controls_text') and self.controls_text:
            self.controls_text.destroy()
            self.controls_text = None
        for t in self.entry_texts:
            t.destroy()
        self.entry_texts = []
