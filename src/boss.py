"""
Boss — TIE Advanced (Darth Vader).
IA : Utility AI — évalue en continu 8 actions et choisit celle avec le meilleur score.
Mouvement : orbit (paramètres HP-dépendants) / charge / strafe / retraite.
"""

from panda3d.core import (
    Vec3, Vec4, NodePath,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
)
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode
from src.enemies import EnemyBolt
from src.boss_ai import BossUtilityAI
import random
import math
import os

# ── Constantes globales ──────────────────────────────────────────────────────

BOSS_TRIGGER_WAVE = 2

BOSS_HP           = 50
BOSS_HIT_RADIUS   = 3.0
BOSS_BOLT_SPEED   = 58.0   # Vitesse des bolts boss (légèrement plus rapide que TIE)

# ── Mouvement — orbite selon HP ───────────────────────────────────────────────
# Chaque entrée : radius_x, radius_z, speed (fréquence sinusoïdale), y_offset
ORBIT_HIGH   = dict(rx=9.0,  rz=4.0, spd=0.65, yo=35)   # HP > 65 %
ORBIT_MID    = dict(rx=7.0,  rz=3.2, spd=0.95, yo=32)   # HP 32-65 %
ORBIT_LOW    = dict(rx=5.5,  rz=2.5, spd=1.35, yo=28)   # HP < 32 % (erratique)

CHARGE_SPEED    = 38.0   # Vitesse de charge
CHARGE_DURATION = 0.85   # Durée de la phase charge (secondes)
STRAFE_RADIUS   = 13.0   # Amplitude du strafe latéral (unités)
RETREAT_Y       = 62.0   # Profondeur de retraite (Y monde)
LERP_NORMAL     = 2.5    # Lerp mouvement normal
LERP_CHARGE     = 8.0    # Lerp pendant la charge

# ── Tir ──────────────────────────────────────────────────────────────────────
AIMED_SPREAD_DEG   = 1.5    # Dispersion tir visé (degrés)
BURST_SHOTS        = 3      # Nombre de tirs dans une salve
BURST_INTERVAL     = 0.18   # Délai entre tirs de salve (s)
CONE_BOLT_COUNT    = 10     # Bolts du cône
CONE_SPREAD_DEG    = 52.0   # Angle total du cône
AOE_BOLT_COUNT     = 12     # Bolts de l'AOE circulaire
PREDICT_TIME       = 0.42   # Secondes de prédiction pour tir prédictif


class BossTIEAdvanced:
    """Boss principal — piloté par BossUtilityAI."""

    def __init__(self, game):
        self.game    = game
        self.active  = False
        self.hp      = BOSS_HP
        self.max_hp  = BOSS_HP
        self.alive   = True
        self.defeated = False
        self.hit_radius = BOSS_HIT_RADIUS

        # Mouvement
        self.pos             = Vec3(0, 80, 5)
        self.smoothed_target = Vec3(0, 80, 5)  # Buffer de lissage — absorbe les sauts
        self.move_timer      = 0.0

        # État charge
        self._charging       = False
        self._charge_elapsed = 0.0

        # Salve (burst)
        self._burst_queue   = []   # [(delay, target_pos), ...]
        self._burst_elapsed = 0.0

        # Visual
        self.node        = None
        self.flash_timer = 0.0

        # Destruction
        self.destruction_timer = 0.0

        # UI
        self.boss_name  = None
        self.phase_text = None

        # IA
        self.ai = BossUtilityAI()

    # ── Démarrage ────────────────────────────────────────────────────────────

    def start(self):
        self.active = True
        self.node   = self._make_tie_advanced()
        self.node.reparentTo(self.game.render)
        self.node.setPos(self.pos)

        self.boss_name = OnscreenText(
            text  = "DARTH VADER — TIE ADVANCED",
            pos   = (0, 0.72), scale=0.03,
            fg    = Vec4(1, 0.3, 0.1, 0.9), align=TextNode.ACenter,
            mayChange=True, sort=60, shadow=(0, 0, 0, 0.8),
        )
        self.phase_text = OnscreenText(
            text  = "PHASE I — CALIBRATION",
            pos   = (0, 0.66), scale=0.022,
            fg    = Vec4(1, 0.6, 0.2, 0.6), align=TextNode.ACenter,
            mayChange=True, sort=60,
        )

    # ── Modèle 3D ────────────────────────────────────────────────────────────

    def _make_tie_advanced(self):
        from src.enemies import BaseEnemy
        root = NodePath("tie_advanced")

        if "TIEFighter" in BaseEnemy._model_cache:
            model = BaseEnemy._model_cache["TIEFighter"].copyTo(root)
            scale = BaseEnemy._model_cache.get("TIEFighter_scale", 0.002)
            model.setScale(scale * 1.8)
            model.setH(0)
            model.setColorScale(Vec4(1.8, 1.8, 2.0, 1))
            return root

        model_path = "assets/models/tie_fighter/scene.gltf"
        if os.path.exists(model_path):
            try:
                model = self.game.loader.loadModel(model_path)
                if model:
                    bounds = model.getTightBounds()
                    if bounds:
                        bmin, bmax = bounds
                        dims = bmax - bmin
                        mx   = max(dims.getX(), dims.getY(), dims.getZ())
                        if mx > 0:
                            model.setScale(3.5 / mx)
                    model.reparentTo(root)
                    model.setH(0)
                    model.setColorScale(Vec4(1.8, 1.8, 2.0, 1))
                    return root
            except Exception as e:
                print(f"[Boss] Erreur modèle: {e}")

        cockpit = self._make_fallback()
        cockpit.reparentTo(root)
        root.setScale(2.0)
        return root

    def _make_fallback(self):
        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("boss", fmt, Geom.UHStatic)
        v     = GeomVertexWriter(vdata, "vertex")
        c     = GeomVertexWriter(vdata, "color")
        col   = Vec4(0.3, 0.2, 0.2, 1)
        s     = 1.0
        for px, py, pz in [(-s,-s,-s),(s,-s,-s),(s,s,-s),(-s,s,-s),
                            (-s,-s, s),(s,-s, s),(s,s, s),(-s,s, s)]:
            v.addData3(px, py, pz); c.addData4(col)
        tris = GeomTriangles(Geom.UHStatic)
        for face in [(0,1,2),(0,2,3),(4,6,5),(4,7,6),
                     (0,4,5),(0,5,1),(2,6,7),(2,7,3),
                     (0,3,7),(0,7,4),(1,5,6),(1,6,2)]:
            tris.addVertices(*face)
        geom = Geom(vdata); geom.addPrimitive(tris)
        n = GeomNode("fallback"); n.addGeom(geom)
        return NodePath(n)

    # ── Boucle principale ─────────────────────────────────────────────────────

    def update(self, dt, player_pos, enemy_bolts, player_hp=10):
        if not self.active or not self.alive:
            return

        # ── IA — met à jour perception + choisit action ──────────────────
        action = self.ai.update(
            dt, self.pos, self.hp, self.max_hp,
            player_pos, player_hp, 10, enemy_bolts,
        )

        # ── Mouvement ─────────────────────────────────────────────────────
        self.move_timer += dt
        raw_target, lerp_speed = self._compute_move_target(player_pos, dt)

        # 1er lissage : smoothed_target absorbe les sauts de move_intent
        sm = min(1.0, 1.8 * dt)
        self.smoothed_target = self.smoothed_target + (raw_target - self.smoothed_target) * sm

        # 2e lissage : boss suit la cible lissée
        lerp = min(1.0, lerp_speed * dt)
        self.pos = self.pos + (self.smoothed_target - self.pos) * lerp
        self.node.setPos(self.pos)

        # ── Orientation ──────────────────────────────────────────────────
        self._update_orientation(player_pos, raw_target, dt)

        # ── Flash hit ────────────────────────────────────────────────────
        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.node.getNumChildren() > 0:
                tint = Vec4(5, 5, 5, 1) if self.flash_timer > 0 else Vec4(1.8, 1.8, 2.0, 1)
                self.node.getChild(0).setColorScale(tint)

        # ── Exécution de l'action de tir ─────────────────────────────────
        if action and action.current_cooldown <= 0:
            self._execute_fire(action.name, player_pos, enemy_bolts)
            self.ai.trigger(action.name)

        # ── Traitement de la salve en cours ──────────────────────────────
        self._process_burst(dt, enemy_bolts)

        # ── HUD ──────────────────────────────────────────────────────────
        if self.phase_text:
            pct   = self.hp / self.max_hp
            label = self.ai.get_phase_label()
            self.phase_text.setText(f"{label} — {int(pct * 100)}%")

    # ── Mouvement ─────────────────────────────────────────────────────────────

    def _compute_move_target(self, player_pos, dt):
        """Retourne (target_pos, lerp_speed) selon l'intention de mouvement."""
        intent = self.ai.move_intent
        t      = self.move_timer
        hp_pct = self.hp / self.max_hp

        # ── Charge ───────────────────────────────────────────────────────
        if intent == "charge":
            if not self._charging:
                self._charging       = True
                self._charge_elapsed = 0.0
            self._charge_elapsed += dt
            if self._charge_elapsed >= CHARGE_DURATION:
                self._charging    = False
                self.ai.move_intent = "orbit"
            target = Vec3(player_pos.getX(), player_pos.getY() + 6, player_pos.getZ())
            return target, LERP_CHARGE

        # ── Strafe (esquive latérale) ─────────────────────────────────────
        if intent == "strafe":
            side   = math.sin(t * 2.2)
            target = Vec3(
                player_pos.getX() + side * STRAFE_RADIUS,
                player_pos.getY() + 22,
                player_pos.getZ() + math.cos(t * 1.4) * 2.5,
            )
            return target, LERP_NORMAL

        # ── Retraite ──────────────────────────────────────────────────────
        if intent == "retreat":
            target = Vec3(
                player_pos.getX() * 0.2,
                player_pos.getY() + RETREAT_Y,
                player_pos.getZ() * 0.2,
            )
            return target, LERP_NORMAL * 1.3

        # ── Orbite — paramètres interpolés en continu selon HP% ─────────────
        # Pas de seuils → pas de sauts. t_dmg : 0 = plein HP, 1 = mort.
        t_dmg = 1.0 - max(0.0, min(1.0, hp_pct))
        rx  = 9.0  - t_dmg * 3.5          # 9.0  → 5.5
        rz  = 4.0  - t_dmg * 1.5          # 4.0  → 2.5
        spd = 0.65 + t_dmg * 0.55         # 0.65 → 1.20
        yo  = 35.0 - t_dmg * 7.0          # 35   → 28

        # En rage (hp < ~30%) : légère variation lente de l'orbite, sans haute fréquence
        if hp_pct < 0.32:
            rx  += abs(math.sin(t * 0.25)) * 2.5
            rz  += abs(math.cos(t * 0.35)) * 1.2

        x = player_pos.getX() + math.sin(t * spd)        * rx
        y = player_pos.getY() + yo + math.sin(t * spd * 0.4) * 10
        z = player_pos.getZ() + math.cos(t * spd * 0.75) * rz
        return Vec3(x, y, z), LERP_NORMAL

    def _update_orientation(self, player_pos, raw_target, dt):
        """Oriente le boss vers le joueur avec un léger bank."""
        look_dir = player_pos - self.pos
        if look_dir.length() > 0:
            h = math.degrees(math.atan2(-look_dir.getX(), look_dir.getY()))
        else:
            h = 0

        # Roll clampé ±40° — évite les flips quand dx est grand
        dx   = raw_target.getX() - self.pos.getX()
        roll = max(-40.0, min(40.0, -dx * 6))

        cur_h, cur_p, cur_r = self.node.getHpr()
        cur_h = cur_h % 360
        if cur_h > 180: cur_h -= 360

        dh = h - cur_h
        if dh >  180: dh -= 360
        if dh < -180: dh += 360

        rl    = min(1.0, 2.2 * dt)
        new_h = cur_h + dh * rl
        new_p = max(-25.0, min(25.0, cur_p * (1 - rl)))  # Pitch clampé — jamais tête en bas
        self.node.setHpr(new_h, new_p, cur_r + (roll - cur_r) * rl)

    # ── Actions de tir ───────────────────────────────────────────────────────

    def _execute_fire(self, action_name, player_pos, enemy_bolts):
        """Dispatch vers la bonne action de tir."""

        if action_name == "aimed_fire":
            self._fire_aimed(player_pos, enemy_bolts, spread=AIMED_SPREAD_DEG)

        elif action_name == "burst_fire":
            target = Vec3(player_pos)
            for i in range(BURST_SHOTS):
                self._burst_queue.append((i * BURST_INTERVAL, target))
            self._burst_elapsed = 0.0

        elif action_name == "cone_shot":
            self._fire_cone(player_pos, enemy_bolts,
                            count=CONE_BOLT_COUNT, spread=CONE_SPREAD_DEG)

        elif action_name == "predictive_shot":
            vx, vz = self.ai.perception.player_vel
            predicted = Vec3(
                player_pos.getX() + vx * PREDICT_TIME,
                player_pos.getY(),
                player_pos.getZ() + vz * PREDICT_TIME,
            )
            self._fire_aimed(predicted, enemy_bolts, spread=0.8)

        elif action_name == "aoe_burst":
            self._fire_aoe(enemy_bolts, count=AOE_BOLT_COUNT)

        # charge / dodge / retreat → pas de tir direct

    def _fire_aimed(self, target_pos, enemy_bolts, spread=1.5):
        """Un bolt visant target_pos avec dispersion angulaire."""
        direction = target_pos - self.pos
        if direction.length() < 0.01:
            return
        direction.normalize()

        # Dispersion aléatoire en XZ
        rad = math.radians(random.uniform(-spread, spread))
        perp = Vec3(-direction.getY(), direction.getX(), 0)
        perp.normalize()
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        direction = Vec3(
            direction.getX() * cos_r + perp.getX() * sin_r,
            direction.getY() * cos_r + perp.getY() * sin_r,
            direction.getZ() + random.uniform(-0.08, 0.08),
        )
        direction.normalize()
        enemy_bolts.append(EnemyBolt(self.game.render, Vec3(self.pos), direction))

    def _fire_cone(self, player_pos, enemy_bolts, count=10, spread=52.0):
        """Éventail de bolts centré sur le joueur."""
        base = player_pos - self.pos
        if base.length() < 0.01:
            return
        base.normalize()
        perp = Vec3(-base.getY(), base.getX(), 0)
        if perp.length() > 0.01:
            perp.normalize()

        half = spread / 2.0
        for i in range(count):
            t   = i / max(count - 1, 1)
            deg = -half + t * spread
            rad = math.radians(deg)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            d = Vec3(
                base.getX() * cos_r + perp.getX() * sin_r,
                base.getY() * cos_r + perp.getY() * sin_r,
                base.getZ() + random.uniform(-0.15, 0.15),
            )
            d.normalize()
            enemy_bolts.append(EnemyBolt(self.game.render, Vec3(self.pos), d))

    def _fire_aoe(self, enemy_bolts, count=12):
        """Cercle complet de bolts dans le plan XY."""
        for i in range(count):
            angle = (i / count) * math.pi * 2
            d = Vec3(
                math.cos(angle),
                math.sin(angle),
                random.uniform(-0.2, 0.2),
            )
            d.normalize()
            enemy_bolts.append(EnemyBolt(self.game.render, Vec3(self.pos), d))

    def _process_burst(self, dt, enemy_bolts):
        """Traite la file de tirs de salve en cours."""
        if not self._burst_queue:
            return
        self._burst_elapsed += dt
        while self._burst_queue and self._burst_queue[0][0] <= self._burst_elapsed:
            _, target = self._burst_queue.pop(0)
            self._fire_aimed(target, enemy_bolts, spread=1.2)
        if not self._burst_queue:
            self._burst_elapsed = 0.0

    # ── Interface publique ───────────────────────────────────────────────────

    def hit(self, damage=1):
        if not self.alive:
            return False
        self.hp -= damage
        self.flash_timer = 0.15
        self.ai.register_hit()   # Monte la menace perçue
        if self.hp <= 0:
            self.alive    = False
            self.defeated = True
            return True
        return False

    def get_pos(self):
        return Vec3(self.pos) if self.alive else None

    def update_destruction(self, dt, explosion_manager):
        """Explosions en chaîne jusqu'à l'explosion finale."""
        self.destruction_timer += dt
        if self.destruction_timer < 2.5:
            if int(self.destruction_timer * 4) > int((self.destruction_timer - dt) * 4):
                offset = Vec3(
                    random.uniform(-2, 2),
                    random.uniform(-2, 2),
                    random.uniform(-1, 1),
                )
                explosion_manager.spawn(self.pos + offset, preset="small", score=0)
            return False
        explosion_manager.spawn(self.pos, preset="medium", score=0)
        return True

    def cleanup(self):
        if self.node and not self.node.isEmpty():
            self.node.removeNode()
        if self.boss_name:
            self.boss_name.destroy()
        if self.phase_text:
            self.phase_text.destroy()
        self.active = False
