"""
Boss Utility AI — Cerveau du boss TIE Advanced.
Architecture : Perception → Utility AI (score par courbes) → Action.
Le boss évalue toutes ses actions en continu et choisit celle avec le meilleur score.
"""

import math


# ---------------------------------------------------------------------------
# Courbes utilitaires
# ---------------------------------------------------------------------------

def lerp_curve(points):
    """Courbe linéaire par morceaux définie par une liste de (x, y).
    Retourne une fonction evaluate(x) -> y, x clampé dans [points[0][0], points[-1][0]].
    """
    def evaluate(x):
        x = max(points[0][0], min(points[-1][0], x))
        for i in range(len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i + 1]
            if x <= x1:
                t = (x - x0) / (x1 - x0) if x1 != x0 else 1.0
                return y0 + (y1 - y0) * t
        return points[-1][1]
    return evaluate


FLAT  = lerp_curve([(0.0, 1.0), (1.0, 1.0)])   # Courbe neutre (×1 partout)
RAMP  = lerp_curve([(0.0, 0.3), (1.0, 1.0)])   # Monte progressivement
IRAMP = lerp_curve([(0.0, 1.0), (1.0, 0.3)])   # Descend progressivement


# ---------------------------------------------------------------------------
# BossPerception
# ---------------------------------------------------------------------------

class BossPerception:
    """Collecte et normalise toutes les données situationnelles pour l'IA."""

    MAX_DISTANCE   = 80.0   # Distance max de référence (normalisation 0-1)
    THREAT_DECAY   = 0.15   # Décroissance naturelle de la menace par seconde
    THREAT_ON_HIT  = 0.35   # Augmentation de la menace à chaque coup reçu

    def __init__(self):
        self.boss_hp_pct     = 1.0
        self.player_hp_pct   = 1.0
        self.distance        = 50.0
        self.norm_distance   = 0.5   # 0-1
        self.player_vel      = (0.0, 0.0)   # (vx, vz) unités/s
        self.player_moving   = False
        self.player_threat   = 0.0   # 0-1 : monte à chaque hit boss, décroît sinon
        self.bolt_count      = 0     # Bolts ennemis actifs à l'écran
        self._prev_player_pos = None

    # ------------------------------------------------------------------
    def update(self, dt, boss_pos, boss_hp, boss_max_hp,
               player_pos, player_hp, player_max_hp, enemy_bolts):
        self.boss_hp_pct   = max(0.0, boss_hp / boss_max_hp)
        self.player_hp_pct = max(0.0, player_hp / player_max_hp)

        # Distance
        delta = player_pos - boss_pos
        self.distance      = max(1.0, delta.length())
        self.norm_distance = min(1.0, self.distance / self.MAX_DISTANCE)

        # Vélocité joueur (dérivée de position)
        if self._prev_player_pos is not None:
            safe_dt = max(dt, 0.001)
            vx = (player_pos.getX() - self._prev_player_pos.getX()) / safe_dt
            vz = (player_pos.getZ() - self._prev_player_pos.getZ()) / safe_dt
            self.player_vel    = (vx, vz)
            self.player_moving = (vx**2 + vz**2) ** 0.5 > 1.5
        self._prev_player_pos = player_pos

        # Bolts actifs
        self.bolt_count = sum(1 for b in enemy_bolts if b.alive)

        # Menace décroît naturellement
        self.player_threat = max(0.0, self.player_threat - self.THREAT_DECAY * dt)

    def register_hit(self):
        """Appeler quand le boss reçoit un coup — monte la menace perçue."""
        self.player_threat = min(1.0, self.player_threat + self.THREAT_ON_HIT)


# ---------------------------------------------------------------------------
# BossAction
# ---------------------------------------------------------------------------

class BossAction:
    """
    Une action possible du boss avec ses courbes de scoring Utility AI.

    Paramètres de tuning :
    - base_priority : score de base (0-100)
    - cooldown      : temps minimum entre deux utilisations
    - dist_curve    : fonction(norm_dist 0-1) → multiplicateur
    - hp_curve      : fonction(boss_hp_pct 0-1) → multiplicateur
    - threat_curve  : fonction(player_threat 0-1) → multiplicateur
    - min/max_dist  : contraintes dures sur la distance monde (unités)
    - min/max_hp    : contraintes dures sur le HP% du boss
    - move_intent   : intention de mouvement liée ("orbit","charge","strafe","retreat")
    """

    def __init__(self, name, base_priority, cooldown,
                 dist_curve=None, hp_curve=None, threat_curve=None,
                 min_dist=0.0, max_dist=300.0,
                 min_hp=0.0,   max_hp=1.0,
                 move_intent="orbit"):
        self.name           = name
        self.base_priority  = base_priority
        self.cooldown       = cooldown
        self.dist_curve     = dist_curve   or FLAT
        self.hp_curve       = hp_curve     or FLAT
        self.threat_curve   = threat_curve or FLAT
        self.min_dist       = min_dist
        self.max_dist       = max_dist
        self.min_hp         = min_hp
        self.max_hp         = max_hp
        self.move_intent    = move_intent
        self.current_cooldown = 0.0

    def evaluate(self, perception):
        """Retourne le score de priorité dans la situation courante (0 = impossible)."""
        # Contraintes dures
        if perception.distance    < self.min_dist: return 0.0
        if perception.distance    > self.max_dist: return 0.0
        if perception.boss_hp_pct < self.min_hp:   return 0.0
        if perception.boss_hp_pct > self.max_hp:   return 0.0

        score  = self.base_priority
        score *= self.dist_curve(perception.norm_distance)
        score *= self.hp_curve(perception.boss_hp_pct)
        score *= self.threat_curve(perception.player_threat)

        # Pénalité forte si en cooldown (pas bloquant, mais très défavorisé)
        if self.current_cooldown > 0:
            score *= 0.05

        return max(0.0, score)


# ---------------------------------------------------------------------------
# BossUtilityAI
# ---------------------------------------------------------------------------

class BossUtilityAI:
    """
    Cerveau du boss : évalue toutes les actions disponibles et choisit
    celle avec le meilleur score toutes les EVAL_INTERVAL secondes.
    """

    EVAL_INTERVAL = 0.70   # Réévalue toutes les N secondes

    def __init__(self):
        self.perception     = BossPerception()
        self.actions        = self._build_actions()
        self.eval_timer     = 0.0
        self.current_action = None
        self.move_intent    = "orbit"

    # ------------------------------------------------------------------
    # Construction des actions (tuning centralisé)
    # ------------------------------------------------------------------

    def _build_actions(self):
        return [

            # ── Tir visé direct ─────────────────────────────────────────────
            # Action de base, toujours utile, score stable à toutes distances
            BossAction(
                name          = "aimed_fire",
                base_priority = 60,
                cooldown      = 0.9,
                dist_curve    = lerp_curve([(0,.4),(.2,1.0),(.55,1.0),(.8,.5),(1,.2)]),
                hp_curve      = FLAT,
                threat_curve  = FLAT,
            ),

            # ── Salve rapide (burst) ─────────────────────────────────────────
            # Plus efficace à distance moyenne, monte en priorité quand HP bas
            BossAction(
                name          = "burst_fire",
                base_priority = 48,           # Réduit — ne doit pas écraser aimed/predictive
                cooldown      = 2.8,
                dist_curve    = lerp_curve([(0,.2),(.2,.8),(.5,1.0),(.75,.6),(1,.15)]),
                hp_curve      = lerp_curve([(0,1.4),(.3,1.2),(.6,1.0),(1,.7)]),  # Max 1.4 au lieu de 2.2
                threat_curve  = lerp_curve([(0,.7),(.5,1.0),(1,1.4)]),
            ),

            # ── Tir en cône ─────────────────────────────────────────────────
            # Arrose la zone, optimal à longue distance, mode rage basse HP
            BossAction(
                name          = "cone_shot",
                base_priority = 56,           # Relevé pour plus de présence
                cooldown      = 3.0,
                dist_curve    = lerp_curve([(0,.05),(.25,.5),(.5,1.0),(1,.8)]),
                hp_curve      = lerp_curve([(0,1.6),(.4,1.1),(.7,1.0),(1,.5)]),
                threat_curve  = lerp_curve([(0,.5),(.5,1.0),(1,1.2)]),
                min_dist      = 12.0,         # Réduit — tire plus souvent
            ),

            # ── Tir prédictif ────────────────────────────────────────────────
            # Vise où le joueur sera — activé seulement si le joueur se déplace
            BossAction(
                name          = "predictive_shot",
                base_priority = 70,
                cooldown      = 1.2,          # Cooldown réduit — tire plus souvent
                dist_curve    = lerp_curve([(0,.3),(.25,1.0),(.6,1.0),(.9,.4),(1,.1)]),
                hp_curve      = FLAT,
                threat_curve  = lerp_curve([(0,.5),(.4,1.0),(1,1.5)]),
            ),

            # ── Charge ──────────────────────────────────────────────────────
            # Fonce sur le joueur — désactivée si trop proche ou HP critique
            BossAction(
                name          = "charge",
                base_priority = 28,          # Priorité basse — action rare
                cooldown      = 9.0,         # Cooldown long
                dist_curve    = lerp_curve([(0,0),(.45,.3),(.7,1.0),(1,.5)]),
                hp_curve      = lerp_curve([(0,.05),(.3,.4),(.55,1.0),(1,.8)]),
                threat_curve  = lerp_curve([(0,1.2),(.5,1.0),(1,.5)]),
                min_dist      = 35.0,        # Seulement de loin
                max_hp        = 0.55,        # Seulement en dessous de 55% HP
                move_intent   = "charge",
            ),

            # ── Esquive / Strafe ─────────────────────────────────────────────
            # Priorité maximale à courte distance ou HP très bas
            BossAction(
                name          = "dodge",
                base_priority = 48,
                cooldown      = 2.0,
                dist_curve    = lerp_curve([(0,2.2),(.18,1.8),(.35,.8),(.6,.2),(1,.05)]),
                hp_curve      = lerp_curve([(0,2.5),(.25,1.8),(.5,1.0),(1,.4)]),
                threat_curve  = lerp_curve([(0,.4),(.5,1.0),(1,2.0)]),
                max_dist      = 35.0,
                move_intent   = "strafe",
            ),

            # ── AOE Burst ───────────────────────────────────────────────────
            # Cercle de bolts — mode rage, HP < 35% seulement
            BossAction(
                name          = "aoe_burst",
                base_priority = 58,
                cooldown      = 5.5,
                dist_curve    = lerp_curve([(0,1.6),(.2,1.2),(.45,1.0),(.7,.5),(1,.1)]),
                hp_curve      = lerp_curve([(0,3.5),(.2,2.5),(.35,.3),(1,.05)]),
                threat_curve  = lerp_curve([(0,.5),(.5,1.0),(1,1.6)]),
                max_hp        = 0.38,
            ),

            # ── Retraite ────────────────────────────────────────────────────
            # Se repositionne loin — prioritaire si trop proche
            BossAction(
                name          = "retreat",
                base_priority = 38,
                cooldown      = 3.2,
                dist_curve    = lerp_curve([(0,2.5),(.12,1.5),(.25,.4),(.5,.05),(1,0)]),
                hp_curve      = lerp_curve([(0,2.0),(.35,1.2),(1,.5)]),
                threat_curve  = FLAT,
                max_dist      = 28.0,
                move_intent   = "retreat",
            ),
        ]

    # ------------------------------------------------------------------
    # Update principal
    # ------------------------------------------------------------------

    def update(self, dt, boss_pos, boss_hp, boss_max_hp,
               player_pos, player_hp, player_max_hp, enemy_bolts):
        """Met à jour la perception, les cooldowns et choisit l'action courante."""
        self.perception.update(
            dt, boss_pos, boss_hp, boss_max_hp,
            player_pos, player_hp, player_max_hp, enemy_bolts,
        )

        for action in self.actions:
            if action.current_cooldown > 0:
                action.current_cooldown -= dt

        self.eval_timer -= dt
        if self.eval_timer <= 0:
            self.eval_timer     = self.EVAL_INTERVAL
            self.current_action = self._choose_action()
            if self.current_action:
                self.move_intent = self.current_action.move_intent

        return self.current_action

    def _choose_action(self):
        """Évalue tous les scores, retourne l'action avec le meilleur."""
        p = self.perception
        best_score  = -1.0
        best_action = None

        for action in self.actions:
            # Le tir prédictif est inutile si le joueur ne bouge pas
            if action.name == "predictive_shot" and not p.player_moving:
                continue

            score = action.evaluate(p)
            if score > best_score:
                best_score  = score
                best_action = action

        return best_action

    def trigger(self, action_name):
        """Lance le cooldown d'une action après son exécution."""
        for action in self.actions:
            if action.name == action_name:
                action.current_cooldown = action.cooldown
                return

    def register_hit(self):
        """Notifie que le boss vient de recevoir un coup."""
        self.perception.register_hit()

    def get_phase_label(self):
        """Label cosmétique pour le HUD (pas de logique de jeu ici)."""
        hp = self.perception.boss_hp_pct
        if hp > 0.65:
            return "PHASE I — CALIBRATION"
        elif hp > 0.32:
            return "PHASE II — AGGRESSION"
        else:
            return "PHASE III — RAGE"
