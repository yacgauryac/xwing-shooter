"""
HUD — Score, vague, vie, game over.
"""

from direct.gui.OnscreenText import OnscreenText
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode, Vec4


class HUD:
    """Affiche les infos de jeu à l'écran."""

    def __init__(self, game):
        self.game = game

        # Score
        self.score_text = OnscreenText(
            text="Score: 0",
            pos=(-1.3, 0.9),
            scale=0.06,
            fg=Vec4(0.2, 1.0, 0.2, 1),
            align=TextNode.ALeft,
            mayChange=True,
        )

        # Vague
        self.wave_text = OnscreenText(
            text="Vague 1",
            pos=(0, 0.9),
            scale=0.06,
            fg=Vec4(1.0, 1.0, 0.2, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )

        # Ennemis
        self.enemy_text = OnscreenText(
            text="Ennemis: 0",
            pos=(1.3, 0.9),
            scale=0.06,
            fg=Vec4(1.0, 0.4, 0.4, 1),
            align=TextNode.ARight,
            mayChange=True,
        )

        # Vie (texte)
        self.health_text = OnscreenText(
            text="Blindage: 100%",
            pos=(-1.3, -0.85),
            scale=0.05,
            fg=Vec4(0.3, 0.8, 1.0, 1),
            align=TextNode.ALeft,
            mayChange=True,
        )

        # Barre de vie (fond)
        self.health_bar_bg = DirectFrame(
            frameColor=Vec4(0.2, 0.2, 0.2, 0.8),
            frameSize=(-0.3, 0.3, -0.012, 0.012),
            pos=(-1.0, 0, -0.88),
        )

        # Barre de vie (remplissage)
        self.health_bar = DirectFrame(
            frameColor=Vec4(0.2, 0.8, 1.0, 0.9),
            frameSize=(-0.3, 0.3, -0.01, 0.01),
            pos=(-1.0, 0, -0.88),
        )

        # Contrôles
        self.controls_text = OnscreenText(
            text="ZQSD: bouger | Espace/Clic: tirer | M: son | Echap: quitter",
            pos=(0, -0.95),
            scale=0.035,
            fg=Vec4(0.5, 0.5, 0.5, 0.6),
            align=TextNode.ACenter,
            mayChange=False,
        )

        # Annonce de vague
        self.wave_announce = OnscreenText(
            text="",
            pos=(0, 0.3),
            scale=0.12,
            fg=Vec4(1.0, 0.8, 0.0, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )
        self.announce_timer = 0.0

        # Flash de dégât (écran rouge)
        self.damage_flash = DirectFrame(
            frameColor=Vec4(1, 0, 0, 0),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0),
            sortOrder=100,
        )
        self.flash_timer = 0.0

        # Game Over
        self.game_over_text = OnscreenText(
            text="",
            pos=(0, 0.1),
            scale=0.15,
            fg=Vec4(1.0, 0.2, 0.2, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )
        self.game_over_sub = OnscreenText(
            text="",
            pos=(0, -0.1),
            scale=0.06,
            fg=Vec4(0.8, 0.8, 0.8, 1),
            align=TextNode.ACenter,
            mayChange=True,
        )

    def update(self, dt, score, wave, enemy_count, health, max_health):
        """Met à jour l'affichage."""
        self.score_text.setText(f"Score: {score}")
        self.wave_text.setText(f"Vague {wave}")
        self.enemy_text.setText(f"Ennemis: {enemy_count}")

        # Vie
        health_pct = max(0, health / max_health)
        self.health_text.setText(f"Blindage: {int(health_pct * 100)}%")

        # Couleur de la barre selon la vie
        if health_pct > 0.5:
            bar_color = Vec4(0.2, 0.8, 1.0, 0.9)
        elif health_pct > 0.25:
            bar_color = Vec4(1.0, 0.8, 0.0, 0.9)
        else:
            bar_color = Vec4(1.0, 0.2, 0.2, 0.9)

        self.health_bar["frameColor"] = bar_color
        self.health_bar["frameSize"] = (-0.3, -0.3 + 0.6 * health_pct, -0.01, 0.01)

        # Annonce de vague
        if self.announce_timer > 0:
            self.announce_timer -= dt
            if self.announce_timer <= 0:
                self.wave_announce.setText("")

        # Flash de dégât
        if self.flash_timer > 0:
            self.flash_timer -= dt
            alpha = max(0, self.flash_timer / 0.3) * 0.3
            self.damage_flash["frameColor"] = Vec4(1, 0, 0, alpha)
            if self.flash_timer <= 0:
                self.damage_flash["frameColor"] = Vec4(1, 0, 0, 0)

    def announce_wave(self, wave_num):
        self.wave_announce.setText(f"--- VAGUE {wave_num} ---")
        self.announce_timer = 2.5

    def show_damage_flash(self):
        """Flash rouge quand le joueur est touché."""
        self.flash_timer = 0.3

    def show_game_over(self, score):
        """Affiche l'écran de game over."""
        self.game_over_text.setText("GAME OVER")
        self.game_over_sub.setText(f"Score final: {score}\n\nAppuie sur R pour recommencer")
