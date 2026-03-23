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
        self.node.setLightOff()

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
        """Charge le modèle TIE Fighter, plus gros, teinté rouge."""
        model_path = "assets/models/tie_fighter/scene.gltf"
        root = NodePath("tie_advanced")

        if os.path.exists(model_path):
            try:
                model = self.game.loader.loadModel(model_path)
                if model:
                    # Auto-scale à taille boss (3.5 = plus gros que les TIE normaux)
                    bounds = model.getTightBounds()
                    if bounds:
                        bmin, bmax = bounds
                        dims = bmax - bmin
                        max_dim = max(dims.getX(), dims.getY(), dims.getZ())
                        if max_dim > 0:
                            model.setScale(3.5 / max_dim)

                    model.reparentTo(root)
                    model.setH(0)
                    # Même rendu que les TIE normaux
                    model.setColorScale(Vec4(1.8, 1.8, 2.0, 1))
                    print("[Boss] TIE Advanced chargé depuis modèle")
                    return root
            except Exception as e:
                print(f"[Boss] Erreur modèle: {e}")

        # Fallback procédural simple
        from src.enemies import TIEFighter
        print("[Boss] Fallback procédural")
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
            self.node.setColorScale(4, 4, 4, 1)
            if self.flash_timer <= 0:
                self.node.setColorScale(1.8, 1.8, 2.0, 1)

        # --- Vol par waypoints ---
        self.pattern_timer += dt
        self.move_timer += dt
        prev_pos = Vec3(self.pos)

        # Définit les waypoints selon le pattern
        if not hasattr(self, 'waypoints') or len(self.waypoints) == 0:
            self._set_pattern(phase, player_pos)

        # Avance vers le waypoint courant
        if hasattr(self, 'waypoints') and self.wp_index < len(self.waypoints):
            target = self.waypoints[self.wp_index]
            to_target = target - self.pos
            dist = to_target.length()

            if dist < 3.0:
                # Waypoint atteint — suivant
                self.wp_index += 1
                if self.wp_index >= len(self.waypoints):
                    # Fin du pattern — en choisir un nouveau
                    self._set_pattern(phase, player_pos)
            else:
                # Avance vers le waypoint
                speed = 25 + phase * 8
                to_target.normalize()
                self.pos = self.pos + to_target * speed * dt

        self.node.setPos(self.pos)

        # --- Orientation naturelle ---
        move_dir = self.pos - prev_pos
        if move_dir.length() > 0.01:
            move_dir.normalize()
            h = math.degrees(math.atan2(-move_dir.getX(), move_dir.getY()))
            p = math.degrees(math.asin(max(-1, min(1, move_dir.getZ()))))
            r = move_dir.getX() * -50  # Banke dans les virages

            cur_h, cur_p, cur_r = self.node.getHpr()
            rl = min(1.0, 4.0 * dt)
            self.node.setHpr(
                cur_h + (h - cur_h) * rl,
                cur_p + (p - cur_p) * rl,
                cur_r + (r - cur_r) * rl,
            )

        # --- Tir (quand devant le joueur) ---
        if self.pos.getY() > player_pos.getY() + 10:
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

    def _set_pattern(self, phase, player_pos):
        """Choisit un nouveau pattern de vol avec waypoints."""
        self.wp_index = 0
        pattern = random.choice(["flyby_left", "flyby_right", "loop", "zigzag", "dive"])

        px = player_pos.getX()

        if pattern == "flyby_left":
            # Passe à gauche du joueur, fait demi-tour
            self.waypoints = [
                Point3(-10, 80, 6),
                Point3(-6, 50, 3),
                Point3(-3, 25, 0),    # Passe proche
                Point3(-8, 10, -2),   # Derrière
                Point3(-12, 30, 5),   # Remonte sur le côté
                Point3(-5, 70, 8),    # Revient devant
                Point3(0, 60, 4),
            ]
        elif pattern == "flyby_right":
            self.waypoints = [
                Point3(10, 80, 6),
                Point3(6, 50, 3),
                Point3(3, 25, 0),
                Point3(8, 10, -2),
                Point3(12, 30, 5),
                Point3(5, 70, 8),
                Point3(0, 60, 4),
            ]
        elif pattern == "loop":
            # Boucle verticale devant le joueur
            segs = 12
            self.waypoints = []
            for i in range(segs):
                a = i / segs * math.pi * 2
                x = math.sin(a) * 6 + random.uniform(-2, 2)
                y = 55 + math.cos(a) * 20
                z = 4 + math.sin(a * 2) * 5
                self.waypoints.append(Point3(x, y, z))
        elif pattern == "zigzag":
            # Zigzag rapide
            self.waypoints = [
                Point3(-8, 70, 5),
                Point3(8, 55, 3),
                Point3(-8, 45, 6),
                Point3(8, 35, 2),
                Point3(-5, 50, 4),
                Point3(0, 65, 5),
            ]
        elif pattern == "dive":
            # Piqué vers le joueur puis remontée
            self.waypoints = [
                Point3(px, 80, 10),
                Point3(px, 40, 2),      # Piqué
                Point3(px * 0.5, 25, -1),  # Très proche
                Point3(-px, 30, 3),     # Esquive
                Point3(-px * 0.5, 60, 8),
                Point3(0, 70, 5),
            ]

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
