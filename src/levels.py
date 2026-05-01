"""
Système de niveaux — 4 environnements + boss final.
Gère la progression entre les niveaux et les transitions.
"""

from direct.gui.OnscreenText import OnscreenText
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode, Vec4, ClockObject
import math

globalClock = ClockObject.getGlobalClock()

C_BRIGHT = Vec4(1.0, 0.7, 0.2, 1.0)
C_ORANGE = Vec4(0.9, 0.55, 0.15, 1.0)
C_DIM = Vec4(0.5, 0.3, 0.1, 0.5)

LEVELS = {
    1: {
        "name": "ASTEROID FIELD",
        "waves": 7,
        "intro_text": "Rebel squadron, engage enemy fighters!",
        "bg_color": (0.0,  0.0,  0.0),
        "description": "TIE Fighters, Interceptors, Bombers",
    },
    2: {
        "name": "LUNAR SURFACE",
        "waves": 7,
        "intro_text": "Stay low — Imperial ground forces ahead!",
        "bg_color": (0.04, 0.04, 0.05),
        "description": "Imperial Shuttles + Ground Turrets",
    },
    3: {
        "name": "DEATH STAR TRENCH",
        "waves": 7,
        "intro_text": "Stay on target... USE THE FORCE!",
        "bg_color": (0.01, 0.01, 0.015),
        "description": "Probe Droids + Attack Bombers + Turrets",
    },
    4: {
        "name": "NEBULA",
        "waves": 7,
        "intro_text": "Sensors jammed — fly by instinct!",
        "bg_color": (0.03, 0.01, 0.05),
        "description": "All enemies — maximum difficulty",
    },
}


class LevelManager:
    """Gère la progression entre les niveaux."""

    def __init__(self, game):
        self.game = game
        self.current_level = 1
        self.waves_completed_in_level = 0
        self.transitioning = False
        self.transition_timer = 0.0
        self.transition_phase = None  # "complete", "intro"
        self.all_levels_done = False

        # UI elements
        self.transition_bg = None
        self.transition_texts = []

    def get_level_config(self):
        return LEVELS.get(self.current_level, LEVELS[1])

    def get_waves_for_level(self):
        return self.get_level_config()["waves"]

    def get_level_name(self):
        config = self.get_level_config()
        return f"LEVEL {self.current_level}: {config['name']}"

    def get_wave_display(self):
        """Retourne 'Wave X/Y' relatif au niveau."""
        total = self.get_waves_for_level()
        current = min(self.waves_completed_in_level + 1, total)
        return f"WAVE {current}/{total}"

    def on_wave_complete(self):
        """Appelé quand une vague est terminée."""
        self.waves_completed_in_level += 1

        if self.waves_completed_in_level >= self.get_waves_for_level():
            if self.current_level >= len(LEVELS):
                self.all_levels_done = True
                return "boss"
            else:
                self._start_transition()
                return "transition"
        return "continue"

    def _start_transition(self):
        """Démarre la transition vers le niveau suivant."""
        self.transitioning = True
        self.transition_timer = 0.0
        self.transition_phase = "complete"
        self._show_level_complete()

    def update(self, dt):
        """Update la transition."""
        if not self.transitioning:
            return False

        self.transition_timer += dt

        if self.transition_phase == "complete":
            # Phase 1: "LEVEL COMPLETE" (2.5s)
            if self.transition_timer > 2.5:
                self._clear_transition()
                self.current_level += 1
                self.waves_completed_in_level = 0
                self.transition_phase = "intro"
                self.transition_timer = 0.0
                self._show_level_intro()

                # Change le bg color
                config = self.get_level_config()
                bg = config.get("bg_color", (0, 0, 0))
                self.game.setBackgroundColor(bg[0], bg[1], bg[2], 1)

        elif self.transition_phase == "intro":
            # Phase 2: intro du nouveau niveau (3s)
            if self.transition_timer > 3.0:
                self._clear_transition()
                self.transitioning = False
                self.transition_phase = None
                return True  # Transition terminée, reprendre le jeu

        return False

    def _show_level_complete(self):
        self._clear_transition()

        self.transition_bg = DirectFrame(
            frameColor=Vec4(0, 0, 0, 0.6),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=150,
        )

        config = self.get_level_config()
        t1 = OnscreenText(
            text=f"LEVEL {self.current_level} COMPLETE",
            pos=(0, 0.15), scale=0.07,
            fg=C_BRIGHT, align=TextNode.ACenter, sort=160,
            shadow=(0, 0, 0, 1),
        )
        t2 = OnscreenText(
            text=config["name"],
            pos=(0, 0.05), scale=0.04,
            fg=C_ORANGE, align=TextNode.ACenter, sort=160,
        )
        self.transition_texts = [t1, t2]

    def _show_level_intro(self):
        self._clear_transition()

        self.transition_bg = DirectFrame(
            frameColor=Vec4(0, 0, 0, 0.7),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=150,
        )

        config = self.get_level_config()
        t1 = OnscreenText(
            text=f"LEVEL {self.current_level}",
            pos=(0, 0.2), scale=0.08,
            fg=C_BRIGHT, align=TextNode.ACenter, sort=160,
            shadow=(0, 0, 0, 1),
        )
        t2 = OnscreenText(
            text=config["name"],
            pos=(0, 0.1), scale=0.05,
            fg=C_ORANGE, align=TextNode.ACenter, sort=160,
        )
        t3 = OnscreenText(
            text=config.get("intro_text", ""),
            pos=(0, -0.0), scale=0.03,
            fg=C_DIM, align=TextNode.ACenter, sort=160,
        )
        self.transition_texts = [t1, t2, t3]

    def _clear_transition(self):
        if self.transition_bg:
            self.transition_bg.destroy()
            self.transition_bg = None
        for t in self.transition_texts:
            t.destroy()
        self.transition_texts = []

    def reset(self):
        self._clear_transition()
        self.current_level = 1
        self.waves_completed_in_level = 0
        self.transitioning = False
        self.transition_timer = 0.0
        self.transition_phase = None
        self.all_levels_done = False
        self.game.setBackgroundColor(0, 0, 0, 1)
