"""
Use the Force — Capacité spéciale.
Bullet time + auto-aim parfait + surchauffe désactivée.

Comportement : clic molette = activation 2s fixes, puis arrêt automatique.
"""

import math

# Recharge par type de kill
FORCE_PER_KILL = {
    "TIEFighter": 8,
    "TIEInterceptor": 10,
    "TIEBomber": 12,
}
FORCE_TORPEDO_BONUS = 5
FORCE_MAX = 100.0

# Drain et timing
USE_DURATION      = 2.0       # Durée fixe d'une utilisation (secondes)
FORCE_DRAIN_RATE  = 18.0      # Unités/seconde consommées (garde la jauge comme ressource)
TIME_SCALE_TARGET = 0.3       # 30% vitesse monde
EASE_IN_TIME  = 0.25          # Transition vers bullet time
EASE_OUT_TIME = 0.4           # Retour à la normale


class ForceAbility:
    """Gère la jauge de Force et le mode bullet time (use-for-duration)."""

    def __init__(self):
        self.gauge = 0.0
        self.active = False
        self.time_scale = 1.0
        self._ease_timer = 0.0
        self._easing_in  = False
        self._easing_out = False
        self._use_timer  = 0.0      # Décompte de la durée fixe

    def add_kill(self, enemy_class_name, torpedo_kill=False):
        gain = FORCE_PER_KILL.get(enemy_class_name, 8)
        if torpedo_kill:
            gain += FORCE_TORPEDO_BONUS
        self.gauge = min(FORCE_MAX, self.gauge + gain)

    def add_pickup(self, amount=15.0):
        self.gauge = min(FORCE_MAX, self.gauge + amount)

    def is_ready(self):
        return self.gauge >= FORCE_MAX * 0.05

    def use(self):
        """Active la Force pour USE_DURATION secondes. Réutilisable : reset le timer."""
        if not self.is_ready():
            return False
        self._use_timer = USE_DURATION
        if not self.active:
            self.active      = True
            self._easing_in  = True
            self._easing_out = False
            self._ease_timer = 0.0
        return True

    def deactivate(self):
        if self.active:
            self.active      = False
            self._use_timer  = 0.0
            self._easing_in  = False
            self._easing_out = True
            self._ease_timer = 0.0

    def update(self, dt):
        if self.active:
            self._use_timer -= dt
            self.gauge = max(0.0, self.gauge - FORCE_DRAIN_RATE * dt)

            if self._use_timer <= 0 or self.gauge <= 0:
                self.active      = False
                self._use_timer  = 0.0
                self._easing_in  = False
                self._easing_out = True
                self._ease_timer = 0.0

        if self._easing_in:
            self._ease_timer += dt
            t = min(1.0, self._ease_timer / EASE_IN_TIME)
            t = t * t
            self.time_scale = 1.0 + (TIME_SCALE_TARGET - 1.0) * t
            if t >= 1.0:
                self._easing_in = False
                self.time_scale = TIME_SCALE_TARGET

        elif self._easing_out:
            self._ease_timer += dt
            t = min(1.0, self._ease_timer / EASE_OUT_TIME)
            t = t * t
            self.time_scale = TIME_SCALE_TARGET + (1.0 - TIME_SCALE_TARGET) * t
            if t >= 1.0:
                self._easing_out = False
                self.time_scale = 1.0

        elif not self.active:
            self.time_scale = 1.0

    def get_time_scale(self):
        return self.time_scale

    def get_gauge_pct(self):
        return self.gauge / FORCE_MAX

    def reset(self):
        self.gauge       = 0.0
        self.active      = False
        self.time_scale  = 1.0
        self._ease_timer = 0.0
        self._easing_in  = False
        self._easing_out = False
        self._use_timer  = 0.0
