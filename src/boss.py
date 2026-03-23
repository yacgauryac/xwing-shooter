"""
Boss — TIE Advanced (Darth Vader).
Dogfight : vole devant le joueur, fait des passes, tire, esquive.
"""

from panda3d.core import (
    Vec3, Vec4, Point3, NodePath,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode, TransparencyAttrib
)
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode
from src.enemies import EnemyBolt
import random
import math
import os

BOSS_TRIGGER_WAVE = 2

# Stats
BOSS_HP = 50
BOSS_FIRE_RATE = 0.8
BOSS_BOLT_SPEED = 55.0
BOSS_HIT_RADIUS = 3.0

# Phases
PHASE_1_HP = 50  # Plein HP — vol tranquille, tir espacé
PHASE_2_HP = 30  # Plus agressif
PHASE_3_HP = 15  # Furieux, tir rapide, esquives


class BossTIEAdvanced:
    """Boss TIE Advanced — dogfight."""

    def __init__(self, game):
        self.game = game
        self.active = False
        self.hp = BOSS_HP
        self.max_hp = BOSS_HP
        self.alive = True
        self.defeated = False
        self.hit_radius = BOSS_HIT_RADIUS

        # Mouvement
        self.pos = Vec3(0, 80, 5)
        self.target_pos = Vec3(0, 60, 3)
        self.move_timer = 0.0
        self.move_speed = 15.0
        self.pattern = "strafe"  # strafe, dive, charge, retreat
        self.pattern_timer = 0.0

        # Combat
        self.fire_timer = 2.0  # Délai avant premier tir
        self.fire_rate = BOSS_FIRE_RATE

        # Visual
        self.node = None
        self.flash_timer = 0.0

        # Destruction
        self.destruction_timer = 0.0

        # UI
        self.hp_bar_bg = None
        self.hp_bar = None
        self.boss_name = None
        self.phase_text = None

    def start(self):
        self.active = True
        self.node = self._make_tie_advanced()
        self.node.reparentTo(self.game.render)
        self.node.setPos(self.pos)

        # Waypoints flight
        self.waypoints = []
        self.wp_index = 0

        # UI — barre de vie en haut
        self.boss_name = OnscreenText(
            text="DARTH VADER — TIE ADVANCED",
            pos=(0, 0.72), scale=0.03,
            fg=Vec4(1, 0.3, 0.1, 0.9), align=TextNode.ACenter,
            mayChange=True, sort=60, shadow=(0, 0, 0, 0.8),
        )
        self.phase_text = OnscreenText(
            text="PHASE 1",
            pos=(0, 0.66), scale=0.022,
            fg=Vec4(1, 0.6, 0.2, 0.6), align=TextNode.ACenter,
            mayChange=True, sort=60,
        )

    def _make_tie_advanced(self):
        """Charge le modèle TIE Fighter — réutilise le cache si dispo."""
        from src.enemies import BaseEnemy

        root = NodePath("tie_advanced")

        # Essaye le cache des ennemis d'abord
        if "TIEFighter" in BaseEnemy._model_cache:
            model = BaseEnemy._model_cache["TIEFighter"].copyTo(root)
            scale = BaseEnemy._model_cache.get("TIEFighter_scale", 0.002)
            model.setScale(scale * 1.8)  # 80% plus gros
            model.setH(0)
            model.setColorScale(Vec4(1.8, 1.8, 2.0, 1))
            print("[Boss] TIE Advanced depuis cache")
            return root

        # Sinon charge le modèle
        model_path = "assets/models/tie_fighter/scene.gltf"
        if os.path.exists(model_path):
            try:
                model = self.game.loader.loadModel(model_path)
                if model:
                    bounds = model.getTightBounds()
                    if bounds:
                        bmin, bmax = bounds
                        dims = bmax - bmin
                        max_dim = max(dims.getX(), dims.getY(), dims.getZ())
                        if max_dim > 0:
                            model.setScale(3.5 / max_dim)
                    model.reparentTo(root)
                    model.setH(0)
                    model.setColorScale(Vec4(1.8, 1.8, 2.0, 1))
                    print("[Boss] TIE Advanced depuis fichier")
                    return root
            except Exception as e:
                print(f"[Boss] Erreur modèle: {e}")

        # Fallback
        cockpit = self._make_fallback()
        cockpit.reparentTo(root)
        root.setScale(2.0)
        return root

    def _make_fallback(self):
        """Fallback si pas de modèle."""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("boss", fmt, Geom.UHStatic)
        v = GeomVertexWriter(vdata, "vertex")
        c = GeomVertexWriter(vdata, "color")

        col = Vec4(0.3, 0.2, 0.2, 1)
        s = 1.0
        v.addData3(-s, -s, -s); c.addData4(col)
        v.addData3(s, -s, -s); c.addData4(col)
        v.addData3(s, s, -s); c.addData4(col)
        v.addData3(-s, s, -s); c.addData4(col)
        v.addData3(-s, -s, s); c.addData4(col)
        v.addData3(s, -s, s); c.addData4(col)
        v.addData3(s, s, s); c.addData4(col)
        v.addData3(-s, s, s); c.addData4(col)

        tris = GeomTriangles(Geom.UHStatic)
        for face in [(0,1,2),(0,2,3),(4,6,5),(4,7,6),
                     (0,4,5),(0,5,1),(2,6,7),(2,7,3),
                     (0,3,7),(0,7,4),(1,5,6),(1,6,2)]:
            tris.addVertices(*face)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        n = GeomNode("fallback")
        n.addGeom(geom)
        return NodePath(n)

    def get_phase(self):
        if self.hp > PHASE_2_HP:
            return 1
        elif self.hp > PHASE_3_HP:
            return 2
        return 3

    def update(self, dt, player_pos, enemy_bolts):
        if not self.active or not self.alive:
            return

        phase = self.get_phase()

        # Flash quand touché
        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.node.getNumChildren() > 0:
                self.node.getChild(0).setColorScale(Vec4(5, 5, 5, 1))
            if self.flash_timer <= 0:
                if self.node.getNumChildren() > 0:
                    self.node.getChild(0).setColorScale(Vec4(1.8, 1.8, 2.0, 1))

        self.move_timer += dt

        # Mouvement fluide — figure en 8 devant le joueur
        speed_mult = 1.0 + (phase - 1) * 0.3
        t = self.move_timer * speed_mult

        x = math.sin(t * 0.8) * 8
        y = 55 + math.sin(t * 0.4) * 12
        z = 3 + math.cos(t * 0.6) * 3

        target = Vec3(x, y, z)
        lerp = min(1.0, 2.5 * dt)
        self.pos = self.pos + (target - self.pos) * lerp
        self.node.setPos(self.pos)

        # Orientation — face au joueur avec léger bank
        dx = target.getX() - self.pos.getX()
        roll = -dx * 15

        look_dir = player_pos - self.pos
        if look_dir.length() > 0:
            h = math.degrees(math.atan2(-look_dir.getX(), look_dir.getY()))
        else:
            h = 0

        cur_h, cur_p, cur_r = self.node.getHpr()

        # Normalise les angles pour éviter les tours
        cur_h = cur_h % 360
        if cur_h > 180:
            cur_h -= 360

        dh = h - cur_h
        if dh > 180:
            dh -= 360
        elif dh < -180:
            dh += 360

        rl = min(1.0, 2.0 * dt)  # Plus lent = plus smooth
        new_h = cur_h + dh * rl
        self.node.setHpr(
            new_h,
            cur_p * (1 - rl),  # Pitch vers 0
            cur_r + (roll - cur_r) * rl,
        )

        # Tir
        fire_rate = 1.2 if phase == 1 else 0.7 if phase == 2 else 0.4
        self.fire_timer -= dt
        if self.fire_timer <= 0:
            self.fire_timer = fire_rate
            self._fire(player_pos, enemy_bolts)
            if phase >= 2:
                self._fire(player_pos, enemy_bolts, offset=Vec3(0.8, 0, 0))
            if phase >= 3:
                self._fire(player_pos, enemy_bolts, offset=Vec3(-0.8, 0, 0))

        # UI
        pct = self.hp / self.max_hp
        if self.phase_text:
            self.phase_text.setText(f"PHASE {phase} — {int(pct * 100)}%")

    def _fire(self, player_pos, enemy_bolts, offset=None):
        pos = Vec3(self.pos)
        if offset:
            pos = pos + offset
        direction = player_pos - pos
        direction.setX(direction.getX() + random.uniform(-1.5, 1.5))
        direction.setZ(direction.getZ() + random.uniform(-1.0, 1.0))
        direction.normalize()
        bolt = EnemyBolt(self.game.render, pos, direction)
        enemy_bolts.append(bolt)

    def hit(self, damage=1):
        if not self.alive:
            return False
        self.hp -= damage
        self.flash_timer = 0.15
        if self.hp <= 0:
            self.alive = False
            self.defeated = True
            return True
        return False

    def get_pos(self):
        if self.alive:
            return Vec3(self.pos)
        return None

    def update_destruction(self, dt, explosion_manager):
        """Explosions en chaîne."""
        self.destruction_timer += dt

        if self.destruction_timer < 2.5:
            if int(self.destruction_timer * 4) > int((self.destruction_timer - dt) * 4):
                offset = Vec3(
                    random.uniform(-2, 2),
                    random.uniform(-2, 2),
                    random.uniform(-1, 1),
                )
                explosion_manager.spawn(self.pos + offset, score=0)
            return False
        else:
            # Explosion finale
            explosion_manager.spawn(self.pos, score=5000)
            return True

    def cleanup(self):
        if self.node and not self.node.isEmpty():
            self.node.removeNode()
        if self.boss_name:
            self.boss_name.destroy()
        if self.phase_text:
            self.phase_text.destroy()
        self.active = False
