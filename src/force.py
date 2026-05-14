"""
Use the Force — Capacité spéciale.
Bullet time + auto-aim parfait + surchauffe désactivée.

Nouveau comportement : hold mouse2 pour utiliser, drain continu.
Activable dès qu'il y a de la jauge (plus besoin d'attendre 100%).
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
FORCE_DRAIN_RATE = 18.0      # Unités/seconde consommées en usage (100 / ~5.5s max)
TIME_SCALE_TARGET = 0.3      # 30% vitesse monde
EASE_IN_TIME  = 0.25         # Transition vers bullet time
EASE_OUT_TIME = 0.4          # Retour à la normale


class ForceAbility:
    """Gère la jauge de Force et le mode bullet time (hold-to-use)."""

    def __init__(self):
        self.gauge = 0.0
        self.active = False          # True = joueur maintient appuyé ET jauge > 0
        self.held   = False          # True = touche physiquement enfoncée
        self.time_scale = 1.0
        self._ease_timer = 0.0       # Temps depuis activation/désactivation
        self._easing_in  = False
        self._easing_out = False

    def add_kill(self, enemy_class_name, torpedo_kill=False):
        """Ajoute de la Force basé sur le type d'ennemi tué."""
        gain = FORCE_PER_KILL.get(enemy_class_name, 8)
        if torpedo_kill:
            gain += FORCE_TORPEDO_BONUS
        self.gauge = min(FORCE_MAX, self.gauge + gain)

    def is_ready(self):
        """Jauge suffisante pour activer (seuil minimal 5%)."""
        return self.gauge >= FORCE_MAX * 0.05

    def activate(self):
        """Active la Force si jauge suffisante."""
        if not self.is_ready():
            return False
        self.active      = True
        self.held        = True
        self._easing_in  = True
        self._easing_out = False
        self._ease_timer = 0.0
        return True

    def deactivate(self):
        """Désactive la Force."""
        if self.active:
            self.active      = False
            self._easing_in  = False
            self._easing_out = True
            self._ease_timer = 0.0
        self.held = False

    def set_held(self, held):
        """Compatibilité — redirige vers activate/deactivate."""
        if held:
            self.activate()
        else:
            self.deactivate()

    def update(self, dt):
        """Update drain, recharge et time_scale."""

        # Drain pendant l'utilisation
        if self.active:
            self.gauge = max(0.0, self.gauge - FORCE_DRAIN_RATE * dt)
            if self.gauge <= 0.0:
                # Jauge vide — désactive même si touche tenue
                self.active      = False
                self._easing_out = True
                self._easing_in  = False
                self._ease_timer = 0.0

        # Ease-in / ease-out du time_scale
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
        self.held        = False
        self.time_scale  = 1.0
        self._ease_timer = 0.0
        self._easing_in  = False
        self._easing_out = False
