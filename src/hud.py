"""
HUD — Affichage tête haute (score, vague, ennemis restants).
"""

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode, Vec4


class HUD:
    """Affiche les infos de jeu à l'écran."""

    def __init__(self, game):
        self.game = game

        # Score (haut gauche)
        self.score_text = OnscreenText(
            text="Score: 0",
            pos=(-1.3, 0.9),
            scale=0.06,
            fg=Vec4(0.2, 1.0, 0.2, 1),
            align=TextNode.ALeft,
            font=None,
            mayChange=True,
        )

        # Vague (haut centre)
        self.wave_text = OnscreenText(
            text="Vague 1",
            pos=(0, 0.9),
            scale=0.06,
            fg=Vec4(1.0, 1.0, 0.2, 1),
            align=TextNode.ACenter,
            font=None,
            mayChange=True,
        )

        # Ennemis restants (haut droit)
        self.enemy_text = OnscreenText(
            text="Ennemis: 0",
            pos=(1.3, 0.9),
            scale=0.06,
            fg=Vec4(1.0, 0.4, 0.4, 1),
            align=TextNode.ARight,
            font=None,
            mayChange=True,
        )

        # Contrôles (bas gauche, discret)
        self.controls_text = OnscreenText(
            text="ZQSD: bouger | Espace/Clic: tirer | Echap: quitter",
            pos=(-1.3, -0.95),
            scale=0.04,
            fg=Vec4(0.5, 0.5, 0.5, 0.7),
            align=TextNode.ALeft,
            font=None,
            mayChange=False,
        )

        # Annonce de vague (temporaire, gros texte)
        self.wave_announce = OnscreenText(
            text="",
            pos=(0, 0.3),
            scale=0.12,
            fg=Vec4(1.0, 0.8, 0.0, 1),
            align=TextNode.ACenter,
            font=None,
            mayChange=True,
        )
        self.announce_timer = 0.0

    def update(self, dt, score, wave, enemy_count):
        """Met à jour l'affichage."""
        self.score_text.setText(f"Score: {score}")
        self.wave_text.setText(f"Vague {wave}")
        self.enemy_text.setText(f"Ennemis: {enemy_count}")

        if self.announce_timer > 0:
            self.announce_timer -= dt
            if self.announce_timer <= 0:
                self.wave_announce.setText("")

    def announce_wave(self, wave_num):
        """Affiche une annonce de nouvelle vague."""
        self.wave_announce.setText(f"--- VAGUE {wave_num} ---")
        self.announce_timer = 2.5
