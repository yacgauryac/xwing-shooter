"""
Screenshake — Jitter caméra à décroissance quadratique.
Usage : screenshake.trigger(intensity, duration)  puis  screenshake.update(dt) chaque frame.
"""

import random
from panda3d.core import Vec3


class Screenshake:
    """Applique un jitter aléatoire X/Z à la caméra, décroissance quadratique."""

    def __init__(self, game):
        self.game      = game
        self.intensity = 0.0
        self.duration  = 0.0
        self.timer     = 0.0
        self._base_pos = None   # Position caméra capturée au déclenchement

    # ------------------------------------------------------------------

    def trigger(self, intensity: float, duration: float):
        """
        Lance un screenshake.
        Si un shake plus fort est déjà en cours il est ignoré.
        """
        if intensity >= self.intensity:
            self.intensity = intensity
            self.duration  = duration
            self.timer     = duration
            # Capture la position "au repos" de la caméra
            self._base_pos = Vec3(self.game.camera.getPos())

    def update(self, dt: float):
        """Appeler chaque frame avec le dt NON scalé (temps réel)."""
        if self.timer <= 0:
            # Restaure la position caméra et réinitialise
            if self._base_pos is not None:
                self.game.camera.setPos(self._base_pos)
                self._base_pos = None
            self.intensity = 0.0
            return

        self.timer -= dt
        if self.timer < 0:
            self.timer = 0.0

        # Décroissance quadratique : fort au début, s'estompe rapidement
        progress = self.timer / self.duration          # 1.0 → 0.0
        current  = self.intensity * (progress ** 2)

        x = random.uniform(-current, current)
        z = random.uniform(-current, current)

        if self._base_pos is not None:
            self.game.camera.setPos(
                self._base_pos.getX() + x,
                self._base_pos.getY(),
                self._base_pos.getZ() + z,
            )

    def reset(self):
        """Réinitialise le shake (ex : au restart d'une partie)."""
        if self._base_pos is not None and not self.game.camera.isEmpty():
            self.game.camera.setPos(self._base_pos)
        self.intensity = 0.0
        self.duration  = 0.0
        self.timer     = 0.0
        self._base_pos = None
