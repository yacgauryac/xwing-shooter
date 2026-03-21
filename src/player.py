"""
Player — Le X-Wing du joueur.
Architecture : node (position/déplacement) → model_node (rotation visuelle + modèle)
Comme ça la rotation visuelle n'affecte pas le positionnement.
"""

import os
import time
from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomLines, GeomNode,
    NodePath, WindowProperties, TransparencyAttrib
)
import math


class Player:
    """Gère le vaisseau du joueur et ses contrôles."""

    BOUNDS_X = 11.0
    BOUNDS_Z = 6.5
    MOVE_SPEED = 12.0
    LERP_SPEED = 12.0

    # Inclinaisons visuelles
    MAX_ROLL = 30.0    # Roulis quand on va à gauche/droite
    MAX_PITCH = 20.0   # Piqué/cabré quand on monte/descend
    ROT_SPEED = 6.0    # Vitesse de retour à la normale

    # MODEL_PATH = "assets/models/xwing.glb"
    MODEL_PATH = "assets/models/xwing/scene.gltf"
    MODEL_SCALE = 0.1
    TARGET_SIZE = 2.5  # Un peu plus gros

    def __init__(self, game):
        self.game = game
        self.target_x = 0.0
        self.target_z = 0.0

        self.keys = {
            "left": False, "right": False,
            "up": False, "down": False,
        }

        self.setup_controls()

        # Rotation de base du modèle (sera défini dans load_model)
        self.model_h = 0

        # Node principal (position dans le monde, pas de rotation)
        self.node = NodePath("player_root")
        self.node.reparentTo(game.render)
        self.node.setPos(0, 20, 0)

        # Node du modèle (enfant, gère la rotation visuelle)
        self.model_node = self.load_model()
        self.model_node.reparentTo(self.node)

        # Rotation visuelle courante (smooth)
        self.current_roll = 0.0
        self.current_pitch = 0.0

        # --- Barrel Roll ---
        self.barrel_rolling = False
        self.barrel_direction = 0       # -1 = gauche, +1 = droite
        self.barrel_timer = 0.0
        self.barrel_cooldown = 0.0
        self.barrel_roll_angle = 0.0    # Angle accumulé pendant la vrille
        self.invincible = False

        # Double tap detection
        self.last_tap_left = 0.0
        self.last_tap_right = 0.0
        self.DOUBLE_TAP_WINDOW = 0.3    # Fenêtre pour le double tap (secondes)
        self.BARREL_DURATION = 0.6      # Durée de la vrille (plus lent)
        self.BARREL_COOLDOWN = 1.0      # Cooldown après une vrille
        self.BARREL_DODGE = 4.0         # Distance latérale pendant la vrille

        # Traînées du barrel roll
        self.barrel_trails = []

        # Effets visuels barrel roll
        self.barrel_flash_timer = 0.0
        self.barrel_flash_node = None
        self.barrel_fov_active = False
        self.base_fov = 60.0
        self.speed_lines = []

        # Réticule de visée — système spring-damper (pendule au bout d'une tige)
        self.crosshair = self._create_crosshair()
        self.crosshair.reparentTo(game.render)
        self.crosshair.setLightOff()
        self.crosshair_x = 0.0
        self.crosshair_z = 0.0
        self.crosshair_vx = 0.0  # Vitesse du réticule (inertie)
        self.crosshair_vz = 0.0

        # Paramètres physiques du réticule
        self.CH_SPRING = 15.0    # Force du ressort (rappel vers le vaisseau)
        self.CH_DAMPING = 6.0    # Amortissement (freine les oscillations)
        self.CH_DISTANCE = 60.0  # Distance devant le vaisseau

        # Souris libre
        props = WindowProperties()
        props.setCursorHidden(False)
        props.setMouseMode(WindowProperties.M_absolute)
        game.win.requestProperties(props)

        # Caméra derrière — vue légèrement du dessus
        game.camera.setPos(0, -4, 3.0)
        game.camera.lookAt(0, 22, 0)

    def load_model(self):
        """Charge le modèle .glb/.gltf, auto-scale à TARGET_SIZE, fallback procédural."""
        if os.path.exists(self.MODEL_PATH):
            try:
                model = self.game.loader.loadModel(self.MODEL_PATH)
                if model:
                    print(f"[Player] Modèle 3D chargé: {self.MODEL_PATH}")

                    # Auto-scale : mesure le modèle brut et scale pour TARGET_SIZE
                    bounds = model.getTightBounds()
                    if bounds:
                        bmin, bmax = bounds
                        size = bmax - bmin
                        max_dim = max(size.getX(), size.getY(), size.getZ())
                        print(f"[Player] Dimensions brutes: {size}")
                        if max_dim > 0:
                            auto_scale = self.TARGET_SIZE / max_dim
                            model.setScale(auto_scale)
                            print(f"[Player] Auto-scale: {auto_scale:.4f} (target {self.TARGET_SIZE})")

                        # Re-check après scale
                        bounds2 = model.getTightBounds()
                        if bounds2:
                            print(f"[Player] Dimensions finales: {bounds2[1] - bounds2[0]}")

                    self.model_h = 180
                    model.setH(self.model_h)
                    model.setColorScale(Vec4(3.0, 3.0, 3.0, 1))
                    return model
            except Exception as e:
                print(f"[Player] Erreur chargement modèle: {e}")

        print("[Player] Modèle 3D non trouvé, utilisation du modèle procédural")
        return self.create_xwing()

    def setup_controls(self):
        g = self.game
        # Appui — passe par on_key_down pour détecter le double tap
        g.accept("arrow_left",    self.on_key_down, ["left"])
        g.accept("arrow_right",   self.on_key_down, ["right"])
        g.accept("arrow_up",      self.set_key, ["up", True])
        g.accept("arrow_down",    self.set_key, ["down", True])
        g.accept("q",             self.on_key_down, ["left"])
        g.accept("d",             self.on_key_down, ["right"])
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

    def on_key_down(self, key):
        """Gère l'appui d'une touche gauche/droite avec détection du double tap."""
        self.keys[key] = True
        now = time.time()

        if key == "left":
            if now - self.last_tap_left < self.DOUBLE_TAP_WINDOW:
                self.start_barrel_roll(-1)
            self.last_tap_left = now
        elif key == "right":
            if now - self.last_tap_right < self.DOUBLE_TAP_WINDOW:
                self.start_barrel_roll(1)
            self.last_tap_right = now

    def start_barrel_roll(self, direction):
        """Lance un barrel roll si pas en cooldown."""
        if self.barrel_rolling or self.barrel_cooldown > 0:
            return
        self.barrel_rolling = True
        self.barrel_direction = direction
        self.barrel_timer = self.BARREL_DURATION
        self.barrel_roll_angle = 0.0
        self.invincible = True

        # --- Effets visuels ---
        # Flash blanc au déclenchement
        self.barrel_flash_timer = 0.15

        # Speed lines
        self._spawn_speed_lines()

        # Zoom FOV (sera restauré à la fin)
        self.barrel_fov_active = True

        print(f"[Player] BARREL ROLL {'gauche' if direction < 0 else 'droite'} !")

    def create_xwing(self):
        """Crée un X-Wing procédural (fallback)."""
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
        # --- Cooldown barrel roll ---
        if self.barrel_cooldown > 0:
            self.barrel_cooldown -= dt

        # Direction depuis les touches
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

        # --- Barrel Roll actif ---
        if self.barrel_rolling:
            self.barrel_timer -= dt

            # Dodge latéral pendant la vrille
            dodge_speed = self.BARREL_DODGE / self.BARREL_DURATION
            self.target_x += self.barrel_direction * dodge_speed * dt

            # Rotation 360° sur la durée
            rotation_per_frame = (360.0 / self.BARREL_DURATION) * dt
            self.barrel_roll_angle += rotation_per_frame * self.barrel_direction

            # Spawne des traînées en spirale AUTOUR du vaisseau
            progress = 1.0 - (self.barrel_timer / self.BARREL_DURATION)
            angle = progress * math.pi * 2 * self.barrel_direction
            trail_radius = 1.5
            # Position relative au vaisseau
            local_x = math.cos(angle) * trail_radius
            local_z = math.sin(angle) * trail_radius

            trail = self._spawn_trail_particle(local_x, 0, local_z, attached=True)
            if trail:
                self.barrel_trails.append(trail)

            if self.barrel_timer <= 0:
                # Fin du barrel roll
                self.barrel_rolling = False
                self.invincible = False
                self.barrel_cooldown = self.BARREL_COOLDOWN
                self.barrel_roll_angle = 0.0
                self.barrel_fov_active = False

        # --- Effets visuels barrel roll ---
        # Flash blanc
        if self.barrel_flash_timer > 0:
            self.barrel_flash_timer -= dt
            if self.barrel_flash_node is None:
                from direct.gui.DirectGui import DirectFrame
                self.barrel_flash_node = DirectFrame(
                    frameColor=Vec4(1, 1, 1, 0.3),
                    frameSize=(-2, 2, -2, 2),
                    pos=(0, 0, 0), sortOrder=90,
                )
            alpha = max(0, self.barrel_flash_timer / 0.15) * 0.3
            self.barrel_flash_node["frameColor"] = Vec4(1, 0.9, 0.7, alpha)
            if self.barrel_flash_timer <= 0 and self.barrel_flash_node:
                self.barrel_flash_node.destroy()
                self.barrel_flash_node = None

        # FOV zoom pendant barrel roll
        if self.barrel_fov_active:
            progress = 1.0 - (self.barrel_timer / self.BARREL_DURATION)
            # FOV augmente puis revient : sin curve
            fov_boost = math.sin(progress * math.pi) * 4
            self.game.camLens.setFov(self.base_fov + fov_boost)
        elif self.game.camLens.getFov()[0] != self.base_fov:
            # Retour lent au FOV normal
            current = self.game.camLens.getFov()[0]
            self.game.camLens.setFov(current + (self.base_fov - current) * 2 * dt)

        # Speed lines (update + cleanup)
        for sl in self.speed_lines[:]:
            sl["life"] -= dt
            if sl["life"] <= 0:
                sl["node"].removeNode()
                self.speed_lines.remove(sl)
            else:
                alpha = sl["life"] / sl["max_life"]
                sl["node"].setColorScale(1, 1, 1, alpha)
                # Les lignes filent vers l'arrière
                sl["node"].setY(sl["node"].getY() - 80 * dt)

        # Update traînées (fade out et suppression)
        for trail in self.barrel_trails[:]:
            trail["life"] -= dt
            if trail["life"] <= 0:
                trail["node"].removeNode()
                self.barrel_trails.remove(trail)
            else:
                alpha = trail["life"] / trail["max_life"]
                trail["node"].setColorScale(1, 1, 1, alpha)

        # Déplace la cible
        self.target_x += move_x * self.MOVE_SPEED * dt
        self.target_z += move_z * self.MOVE_SPEED * dt

        self.target_x = max(-self.BOUNDS_X, min(self.BOUNDS_X, self.target_x))
        self.target_z = max(-self.BOUNDS_Z, min(self.BOUNDS_Z, self.target_z))

        # Interpole la position du node principal
        current_pos = self.node.getPos()
        target_pos = Point3(self.target_x, 20, self.target_z)
        lerp = min(1.0, self.LERP_SPEED * dt)
        new_pos = current_pos + (target_pos - current_pos) * lerp
        self.node.setPos(new_pos)

        # --- Caméra suit le joueur (décale quand on va sur les côtés) ---
        cam_offset_x = new_pos.getX() * 0.3  # 30% du déplacement joueur
        cam_offset_z = new_pos.getZ() * 0.15
        cam_target = Point3(cam_offset_x, -4, 3.0 + cam_offset_z * 0.5)
        cam_current = self.game.camera.getPos()
        cam_lerp = min(1.0, 3.0 * dt)
        self.game.camera.setPos(cam_current + (cam_target - cam_current) * cam_lerp)
        self.game.camera.lookAt(cam_offset_x * 0.5, 22, cam_offset_z * 0.3)

        # --- Rotation visuelle du modèle ---
        rot_lerp = self.ROT_SPEED * dt

        if self.barrel_rolling:
            self.model_node.setHpr(
                self.model_h,
                self.current_pitch,
                -self.barrel_roll_angle,
            )
        else:
            target_roll = -move_x * self.MAX_ROLL
            self.current_roll += (target_roll - self.current_roll) * rot_lerp

            target_pitch = -move_z * self.MAX_PITCH
            self.current_pitch += (target_pitch - self.current_pitch) * rot_lerp

            self.model_node.setHpr(
                self.model_h,
                self.current_pitch,
                self.current_roll,
            )

        # --- Réticule : spring-damper (pendule au bout d'une tige) ---
        # Le réticule est "attaché" au vaisseau par un ressort.
        # Quand le vaisseau bouge, le réticule résiste (inertie),
        # puis dépasse (overshoot), puis revient (oscillation amortie).
        ship_x = new_pos.getX()
        ship_z = new_pos.getZ()

        # Force du ressort : tire le réticule vers la position du vaisseau
        spring_fx = (ship_x - self.crosshair_x) * self.CH_SPRING
        spring_fz = (ship_z - self.crosshair_z) * self.CH_SPRING

        # Amortissement : freine la vitesse du réticule
        damp_fx = -self.crosshair_vx * self.CH_DAMPING
        damp_fz = -self.crosshair_vz * self.CH_DAMPING

        # Accélération = ressort + amortissement
        ax = spring_fx + damp_fx
        az = spring_fz + damp_fz

        # Intègre la vitesse et la position
        self.crosshair_vx += ax * dt
        self.crosshair_vz += az * dt
        self.crosshair_x += self.crosshair_vx * dt
        self.crosshair_z += self.crosshair_vz * dt

        crosshair_y = new_pos.getY() + self.CH_DISTANCE
        self.crosshair.setPos(self.crosshair_x, crosshair_y, self.crosshair_z)

    def _create_crosshair(self):
        """Crée un réticule de visée (carré avec croix, style Star Fox)."""
        root = NodePath("crosshair")

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("crosshair", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        color = GeomVertexWriter(vdata, "color")

        # Couleur : vert semi-transparent
        c = Vec4(0.2, 1.0, 0.3, 0.6)

        radius = 0.6
        gap = 0.15  # Espace entre les arcs (en radians)
        segments_per_arc = 8

        # 4 arcs de cercle séparés (haut, droite, bas, gauche)
        # Chaque arc couvre ~70° avec un gap de ~20° entre eux
        arc_angles = [
            (math.pi/2 + gap, math.pi - gap),      # Haut-gauche → haut-droit
            (0 + gap, math.pi/2 - gap),             # Droite-bas → droite-haut
            (-math.pi/2 + gap, 0 - gap),            # Bas-droite → bas-gauche (ajusté)
            (math.pi + gap, math.pi * 1.5 - gap),   # Gauche-haut → gauche-bas
        ]

        verts = []
        for a_start, a_end in arc_angles:
            for i in range(segments_per_arc + 1):
                t = i / segments_per_arc
                a = a_start + t * (a_end - a_start)
                verts.append((math.cos(a) * radius, 0, math.sin(a) * radius))

        # Croix centrale (petite)
        cross = 0.06
        verts += [
            (-cross, 0, 0), (cross, 0, 0),
            (0, 0, -cross), (0, 0, cross),
        ]

        for v in verts:
            vertex.addData3(*v)
            color.addData4(c)

        lines = GeomLines(Geom.UHStatic)
        # Arcs : segments connectés
        idx = 0
        for _ in range(4):
            for i in range(segments_per_arc):
                lines.addVertices(idx + i, idx + i + 1)
            idx += segments_per_arc + 1

        # Croix centrale
        lines.addVertices(idx, idx + 1)
        lines.addVertices(idx + 2, idx + 3)

        geom = Geom(vdata)
        geom.addPrimitive(lines)
        node = GeomNode("crosshair_geom")
        node.addGeom(geom)

        np = NodePath(node)
        np.reparentTo(root)
        np.setRenderModeThickness(2)

        return root

    def _spawn_trail_particle(self, x, y, z, attached=False):
        """Crée une particule de traînée pour le barrel roll."""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("trail", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        # Ligne bleu/blanc courte
        length = 0.4
        c_bright = Vec4(0.7, 0.85, 1.0, 1.0)
        c_dim = Vec4(0.3, 0.5, 1.0, 0.3)

        vertex.addData3(0, 0, 0)
        col.addData4(c_bright)
        vertex.addData3(0, -length, 0)
        col.addData4(c_dim)

        lines = GeomLines(Geom.UHStatic)
        lines.addVertices(0, 1)

        geom = Geom(vdata)
        geom.addPrimitive(lines)
        node = GeomNode("trail_particle")
        node.addGeom(geom)

        np = NodePath(node)
        if attached:
            # Attaché au node joueur — suit le vaisseau
            np.reparentTo(self.node)
        else:
            np.reparentTo(self.game.render)
        np.setPos(x, y, z)
        np.setLightOff()
        np.setRenderModeThickness(4)
        np.setTransparency(TransparencyAttrib.MAlpha)

        life = 0.25
        return {"node": np, "life": life, "max_life": life}

    def _spawn_speed_lines(self):
        """Spawn des lignes de vitesse autour du vaisseau pendant le barrel roll."""
        import random
        px = self.node.getX()
        py = self.node.getY()
        pz = self.node.getZ()

        for _ in range(25):
            fmt = GeomVertexFormat.getV3c4()
            vdata = GeomVertexData("speedline", fmt, Geom.UHStatic)
            vertex = GeomVertexWriter(vdata, "vertex")
            col = GeomVertexWriter(vdata, "color")

            # Lignes autour du vaisseau, allongées vers l'arrière
            ox = px + random.uniform(-6, 6)
            oz = pz + random.uniform(-4, 4)
            oy = py + random.uniform(2, 20)
            length = random.uniform(3, 8)

            c_front = Vec4(1.0, 0.85, 0.5, 0.9)
            c_back = Vec4(1.0, 0.6, 0.2, 0.0)

            vertex.addData3(0, 0, 0)
            col.addData4(c_front)
            vertex.addData3(0, -length, 0)
            col.addData4(c_back)

            lines = GeomLines(Geom.UHStatic)
            lines.addVertices(0, 1)

            geom = Geom(vdata)
            geom.addPrimitive(lines)
            node = GeomNode("speedline")
            node.addGeom(geom)

            np = NodePath(node)
            np.reparentTo(self.game.render)
            np.setPos(ox, oy, oz)
            np.setLightOff()
            np.setRenderModeThickness(random.uniform(2.0, 4.0))
            np.setTransparency(TransparencyAttrib.MAlpha)

            life = random.uniform(0.4, 0.8)
            self.speed_lines.append({"node": np, "life": life, "max_life": life})