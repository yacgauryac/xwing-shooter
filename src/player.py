"""
Player — Le X-Wing du joueur.
Charge un modèle .glb si disponible, sinon utilise le modèle procédural.

Contrôles :
- ZQSD ou Flèches : déplacer le vaisseau
- Souris / Espace : tirer (géré par lasers.py)
"""

import os
from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath, WindowProperties
)
import math


class Player:
    """Gère le vaisseau du joueur et ses contrôles."""

    BOUNDS_X = 8.0
    BOUNDS_Z = 5.0
    MOVE_SPEED = 12.0
    LERP_SPEED = 12.0
    MAX_ROLL = 35.0
    MAX_PITCH = 15.0

    # Chemin vers le modèle 3D (si présent)
    MODEL_PATH = "assets/models/xwing.glb"
    MODEL_SCALE = 0.1  # Ajuste selon le modèle téléchargé

    def __init__(self, game):
        self.game = game
        self.target_x = 0.0
        self.target_z = 0.0

        self.keys = {
            "left": False, "right": False,
            "up": False, "down": False,
        }

        self.setup_controls()

        # Essaie de charger le modèle 3D, sinon fallback procédural
        self.node = self.load_model()
        self.node.reparentTo(game.render)
        self.node.setPos(0, 20, 0)

        # Souris libre
        props = WindowProperties()
        props.setCursorHidden(False)
        props.setMouseMode(WindowProperties.M_absolute)
        game.win.requestProperties(props)

        # Caméra derrière
        game.camera.setPos(0, -5, 3)
        game.camera.lookAt(0, 20, 0)

    def load_model(self):
        """Charge le modèle .glb ou .gltf, fallback sur le procédural."""
        if os.path.exists(self.MODEL_PATH):
            try:
                model = self.game.loader.loadModel(self.MODEL_PATH)
                if model:
                    print(f"[Player] Modèle 3D chargé: {self.MODEL_PATH}")
                    model.setScale(self.MODEL_SCALE)
                    # Oriente le modèle face à +Y (selon le modèle, ajuster H/P/R)
                    model.setH(-90)
                    return model
            except Exception as e:
                print(f"[Player] Erreur chargement modèle: {e}")

        print("[Player] Modèle 3D non trouvé, utilisation du modèle procédural")
        return self.create_xwing()

    def setup_controls(self):
        g = self.game
        g.accept("arrow_left",    self.set_key, ["left", True])
        g.accept("arrow_right",   self.set_key, ["right", True])
        g.accept("arrow_up",      self.set_key, ["up", True])
        g.accept("arrow_down",    self.set_key, ["down", True])
        g.accept("q",             self.set_key, ["left", True])
        g.accept("d",             self.set_key, ["right", True])
        g.accept("z",             self.set_key, ["up", True])
        g.accept("s",             self.set_key, ["down", True])

        g.accept("arrow_left-up",  self.set_key, ["left", False])
        g.accept("arrow_right-up", self.set_key, ["right", False])
        g.accept("arrow_up-up",    self.set_key, ["up", False])
        g.accept("arrow_down-up",  self.set_key, ["down", False])
        g.accept("q-up",           self.set_key, ["left", False])
        g.accept("d-up",           self.set_key, ["right", False])
        g.accept("z-up",           self.set_key, ["up", False])
        g.accept("s-up",           self.set_key, ["down", False])

    def set_key(self, key, value):
        self.keys[key] = value

    def create_xwing(self):
        """Crée un X-Wing procédural avec des boîtes."""
        root = NodePath("xwing")

        fuselage = self.make_box(2.0, 0.4, 0.3, Vec4(0.85, 0.85, 0.85, 1))
        fuselage.reparentTo(root)

        nose = self.make_box(0.8, 0.3, 0.25, Vec4(0.7, 0.7, 0.75, 1))
        nose.reparentTo(root)
        nose.setPos(1.2, 0, 0.05)

        wing_color = Vec4(0.8, 0.8, 0.8, 1)
        wing_red = Vec4(0.9, 0.2, 0.2, 1)

        for y_sign, z_sign in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
            w = self.make_box(1.5, 0.05, 0.6, wing_color)
            w.reparentTo(root)
            w.setPos(-0.2, 0.25 * y_sign, 0.5 * z_sign)
            r = self.make_box(1.5, 0.06, 0.05, wing_red)
            r.reparentTo(w)
            r.setPos(0, 0, 0.25 * z_sign)

        cannon_color = Vec4(0.5, 0.5, 0.55, 1)
        for y_off, z_off in [(0.25, 0.5), (0.25, -0.5), (-0.25, 0.5), (-0.25, -0.5)]:
            cannon = self.make_box(0.6, 0.06, 0.06, cannon_color)
            cannon.reparentTo(root)
            cannon.setPos(1.0, y_off, z_off)

        reactor_color = Vec4(0.3, 0.5, 0.9, 1)
        for y_off in [-0.15, 0.15]:
            reactor = self.make_box(0.15, 0.12, 0.12, reactor_color)
            reactor.reparentTo(root)
            reactor.setPos(-1.1, y_off, 0)

        root.setH(-90)
        return root

    def make_box(self, sx, sy, sz, color):
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("box", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        corners = [
            (-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
            (-hx, -hy,  hz), (hx, -hy,  hz), (hx,  hy, hz), (-hx,  hy, hz),
        ]
        for c in corners:
            vertex.addData3(*c)
            col.addData4(color)
        tris = GeomTriangles(Geom.UHStatic)
        for f in [
            (0,1,2),(0,2,3),(4,6,5),(4,7,6),
            (0,4,5),(0,5,1),(2,6,7),(2,7,3),
            (0,3,7),(0,7,4),(1,5,6),(1,6,2),
        ]:
            tris.addVertices(*f)
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("box")
        node.addGeom(geom)
        return NodePath(node)

    def update(self, dt):
        move_x = 0.0
        move_z = 0.0

        if self.keys["left"]:
            move_x -= 1.0
        if self.keys["right"]:
            move_x += 1.0
        if self.keys["up"]:
            move_z += 1.0
        if self.keys["down"]:
            move_z -= 1.0

        if move_x != 0 and move_z != 0:
            move_x *= 0.707
            move_z *= 0.707

        self.target_x += move_x * self.MOVE_SPEED * dt
        self.target_z += move_z * self.MOVE_SPEED * dt

        self.target_x = max(-self.BOUNDS_X, min(self.BOUNDS_X, self.target_x))
        self.target_z = max(-self.BOUNDS_Z, min(self.BOUNDS_Z, self.target_z))

        current_pos = self.node.getPos()
        target_pos = Point3(self.target_x, 20, self.target_z)
        lerp = min(1.0, self.LERP_SPEED * dt)

        new_pos = current_pos + (target_pos - current_pos) * lerp
        self.node.setPos(new_pos)

        target_roll = -move_x * self.MAX_ROLL
        target_pitch = move_z * self.MAX_PITCH

        current_r = self.node.getR()
        current_p = self.node.getP()
        rot_lerp = min(1.0, 8.0 * dt)

        self.node.setR(current_r + (target_roll - current_r) * rot_lerp)
        self.node.setP(current_p + (target_pitch - current_p) * rot_lerp)

        if not any(self.keys.values()):
            self.node.setR(current_r + (0 - current_r) * rot_lerp)
            self.node.setP(current_p + (0 - current_p) * rot_lerp)
