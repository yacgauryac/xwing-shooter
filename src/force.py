"""
Use the Force — Capacité spéciale.
Bullet time + auto-aim parfait + surchauffe désactivée.
"""

from panda3d.core import Vec4
import math

# Recharge par type de kill
FORCE_PER_KILL = {
    "TIEFighter": 8,
    "TIEInterceptor": 10,
    "TIEBomber": 12,
}
FORCE_TORPEDO_BONUS = 5
FORCE_MAX = 100.0

# Durée et timing
FORCE_DURATION = 6.0
TIME_SCALE_TARGET = 0.3      # 30% vitesse monde
EASE_IN_TIME = 0.3            # Transition vers bullet time
EASE_OUT_TIME = 0.5           # Retour à la normale


class ForceAbility:
    """Gère la jauge de Force et le mode bullet time."""

    def __init__(self):
        self.gauge = 0.0
        self.active = False
        self.timer = 0.0
        self.time_scale = 1.0
        self.was_full = False  # Pour le flash "USE THE FORCE" une seule fois

    def add_kill(self, enemy_class_name, torpedo_kill=False):
        """Ajoute de la Force basé sur le type d'ennemi tué."""
        if self.active:
            return
        gain = FORCE_PER_KILL.get(enemy_class_name, 8)
        if torpedo_kill:
            gain += FORCE_TORPEDO_BONUS
        self.gauge = min(FORCE_MAX, self.gauge + gain)

    def is_ready(self):
        return self.gauge >= FORCE_MAX and not self.active

    def activate(self):
        """Active le mode Force (mouse2/mouse3 selon binding)."""
        if self.gauge < FORCE_MAX or self.active:
            return False
        self.active = True
        self.timer = FORCE_DURATION
        return True

    def update(self, dt):
        """Update le timer et le time_scale."""
        if not self.active:
            # Pas actif — time_scale = 1.0
            self.time_scale = 1.0
            return

        self.timer -= dt

        # Jauge se vide progressivement
        self.gauge = max(0, (self.timer / FORCE_DURATION) * FORCE_MAX)

        # Time scale avec ease-in/ease-out
        time_in_force = FORCE_DURATION - self.timer

        if time_in_force < EASE_IN_TIME:
            # Ease-in : 1.0 → TIME_SCALE_TARGET
            t = time_in_force / EASE_IN_TIME
            t = t * t  # Ease quadratique
            self.time_scale = 1.0 + (TIME_SCALE_TARGET - 1.0) * t
        elif self.timer < EASE_OUT_TIME:
            # Ease-out : TIME_SCALE_TARGET → 1.0
            t = 1.0 - (self.timer / EASE_OUT_TIME)
            t = t * t
            self.time_scale = TIME_SCALE_TARGET + (1.0 - TIME_SCALE_TARGET) * t
        else:
            self.time_scale = TIME_SCALE_TARGET

        # Fin
        if self.timer <= 0:
            self.active = False
            self.timer = 0
            self.time_scale = 1.0
            self.gauge = 0
            self.was_full = False

    def get_time_scale(self):
        return self.time_scale

    def get_gauge_pct(self):
        return self.gauge / FORCE_MAX

    def reset(self):
        self.gauge = 0.0
        self.active = False
        self.timer = 0.0
        self.time_scale = 1.0
        self.was_full = False
