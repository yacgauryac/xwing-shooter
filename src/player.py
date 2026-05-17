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
    NodePath, WindowProperties, TransparencyAttrib,
    ColorBlendAttrib,
)
import math


class Player:
    """Gère le vaisseau du joueur et ses contrôles."""

    BOUNDS_X = 14.0    # Élargi (L1/L4 par défaut, réduit par set_bounds pour L2/L3)
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

    # Positions des réacteurs (espace local player.node) — synchronisées avec game._ENGINE_LOCAL
    _ENGINE_LOCAL = [(-0.31,-1.20, 0.17), (0.31,-1.20, 0.17),
                     (-0.31,-1.20,-0.17), (0.31,-1.20,-0.17)]

    def __init__(self, game):
        self.game = game
        self.target_x = 0.0
        self.target_z = 0.0
        self.movement_mode = "rail"   # "rail" (actuel) ou "free" (V3 — pas implémenté)

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

        # Réticule de visée — système spring-damper (suit le vaisseau avec inertie)
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

        # Caméra derrière — vue légèrement du dessus (lointaine par défaut)
        game.camera.setPos(0, 4, 2.5)
        game.camera.lookAt(0, 22, 0)

        # Shield hit flash — Option B : copie du modèle agrandie rouge
        self.shield_flash_timer = 0.0
        self._hit_flash_np = self._create_hit_flash()

        # Overheat warning — teinte rouge sur le vaisseau (pas de halos canons)
        self._overheat_pulse = 0.0
        self._overheat_tint_np = None  # Créé à la première surchauffe

        # Lueurs réacteurs — disques billboard rouge/rose aux nacelles
        self._create_engine_glows()

        # Bouclier — désactivé, réservé pour V3 (vrai système de bouclier)
        self._shield_np = None

        # Ombre au sol — blob pour L2/L0 (surface lunaire)
        self.SHADOW_GROUND_Z = -7.8   # == LunarTerrain.GROUND_Z
        self._shadow_np = self._create_shadow()
        self._shadow_active = False

    def _create_shadow(self):
        """Blob d'ombre au sol — ellipse semi-transparente pour L2 (surface lunaire)."""
        segs = 20
        rx, ry = 2.4, 1.6   # demi-axes : large en X (envergure), fin en Y (profondeur)

        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("player_shadow", fmt, Geom.UHStatic)
        vdata.setNumRows(segs + 1)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")

        # Centre — opaque
        vw.addData3(0, 0, 0)
        cw.addData4(0, 0, 0, 0.55)

        # Périmètre — transparent (dégradé radial via interpolation GPU)
        for i in range(segs):
            a = i / segs * 2 * math.pi
            vw.addData3(rx * math.cos(a), ry * math.sin(a), 0)
            cw.addData4(0, 0, 0, 0.0)

        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segs):
            tris.addVertices(0, i + 1, (i + 1) % segs + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gn = GeomNode("player_shadow")
        gn.addGeom(geom)

        np = NodePath(gn)
        np.reparentTo(self.game.render)
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setBin("fixed", 42)    # Pas de depth-sort, s'affiche toujours sous les bâtiments
        np.setLightOff()
        np.setDepthWrite(False)
        np.hide()
        return np

    def set_shadow_visible(self, visible):
        """Active/désactive l'ombre au sol (L2/L0 seulement)."""
        self._shadow_active = visible
        if not visible and not self._shadow_np.isEmpty():
            self._shadow_np.hide()

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

                    # Log bounds finales en espace parent (node) pour positionner les glows
                    bounds3 = model.getTightBounds()
                    if bounds3:
                        bmin3, bmax3 = bounds3
                        print(f"[Player] Bounds en espace model_node: min={bmin3}, max={bmax3}")
                        print(f"[Player] Centre model: {(bmin3 + bmax3) * 0.5}")
                        print(f"[Player] Moteurs attendus aux 4 coins arrière (Y min)")

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

    def set_bounds(self, bounds_x=None, bounds_z=None):
        """Ajuste les limites de mouvement (appelé par game.py selon le niveau)."""
        if bounds_x is not None:
            self.BOUNDS_X = bounds_x
        if bounds_z is not None:
            self.BOUNDS_Z = bounds_z

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

    def update(self, dt, hp_pct=1.0, force_pct=0.0):
        # --- Shield hit flash (Option B — mesh rouge semi-transparent) ---
        if self.shield_flash_timer > 0:
            self.shield_flash_timer -= dt
            progress = self.shield_flash_timer / 0.25
            if self._hit_flash_np and not self._hit_flash_np.isEmpty():
                alpha = progress * 0.12
                self._hit_flash_np.setColorScale(3.0, 0.05, 0.05, alpha)
            if self.shield_flash_timer <= 0:
                if self._hit_flash_np and not self._hit_flash_np.isEmpty():
                    self._hit_flash_np.hide()

        # --- Overheat warning — teinte rouge pulsante sur le vaisseau ---
        if hasattr(self.game, 'lasers') and self.game.lasers:
            heat_pct = self.game.lasers.heat / self.game.lasers.MAX_HEAT
            if heat_pct > 0.72:
                warn = (heat_pct - 0.72) / 0.28        # 0→1 sur 72%→100%
                freq = 3.0 + warn * 9.0                 # 3→12 Hz
                self._overheat_pulse += dt * freq * 2 * math.pi
                pulse = (math.sin(self._overheat_pulse) * 0.5 + 0.5) * warn
                # Teinte rouge-orange sur le modèle (pulse)
                r = 3.0 + pulse * 4.0   # 3→7 (surbrillance rouge)
                g = 3.0 - pulse * 2.5   # 3→0.5
                b = 3.0 - pulse * 2.8   # 3→0.2
                self.model_node.setColorScale(r, g, b, 1)
            else:
                self._overheat_pulse = 0.0
                self.model_node.setColorScale(3.0, 3.0, 3.0, 1)  # Normal

        # --- Bouclier — désactivé pour l'instant ---

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

        # --- Caméra : ne bouge que quand le vaisseau est près du bord ---
        edge_x = self.BOUNDS_X * 0.8
        edge_z = self.BOUNDS_Z * 0.8
        px = new_pos.getX()
        pz = new_pos.getZ()

        close = getattr(self.game, '_close_cam_mode', False)

        # Décalage caméra adapté à chaque vue (proche = angle serré, suivi plus fort)
        cam_follow_strength = 2.5 if close else 1.5
        cam_offset_x = 0
        cam_offset_z = 0
        if abs(px) > edge_x:
            excess = (abs(px) - edge_x) / (self.BOUNDS_X - edge_x)
            cam_offset_x = excess * cam_follow_strength * (1 if px > 0 else -1)
        if abs(pz) > edge_z:
            excess = (abs(pz) - edge_z) / (self.BOUNDS_Z - edge_z)
            cam_offset_z = excess * 0.8 * (1 if pz > 0 else -1)

        # Vue top-down (touche 4) — caméra suit le vaisseau depuis le dessus
        if getattr(self.game, '_top_cam_mode', False):
            self.game.camera.setPos(px, 20, 18)
            self.game.camera.lookAt(px, 20, 0)
        else:
            cam_y        = 11   if close else 2   # lointaine reculée de ~10%
            cam_z        = 1.5  if close else 2.5
            look_mult    = 0.7  if close else 0.3  # suivi lookAt plus fort en proche
            cam_target = Point3(cam_offset_x, cam_y, cam_z + cam_offset_z * 0.3)
            cam_current = self.game.camera.getPos()
            self.game.camera.setPos(cam_current + (cam_target - cam_current) * min(1.0, 6.0 * dt))
            self.game.camera.lookAt(cam_offset_x * look_mult, 22, 0)

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

        # --- Réticule : spring-damper vers la position du vaisseau ---
        ship_x = new_pos.getX()
        ship_z = new_pos.getZ()

        spring_fx = (ship_x - self.crosshair_x) * self.CH_SPRING
        spring_fz = (ship_z - self.crosshair_z) * self.CH_SPRING
        damp_fx   = -self.crosshair_vx * self.CH_DAMPING
        damp_fz   = -self.crosshair_vz * self.CH_DAMPING
        self.crosshair_vx += (spring_fx + damp_fx) * dt
        self.crosshair_vz += (spring_fz + damp_fz) * dt
        self.crosshair_x  += self.crosshair_vx * dt
        self.crosshair_z  += self.crosshair_vz * dt

        crosshair_y = new_pos.getY() + self.CH_DISTANCE
        self.crosshair.setPos(self.crosshair_x, crosshair_y, self.crosshair_z)

        # --- Ombre au sol (L2/L0) ---
        if self._shadow_active and not self._shadow_np.isEmpty():
            # Hauteur au-dessus du sol — le joueur est toujours au-dessus (GROUND_Z=-7.8)
            h = new_pos.getZ() - self.SHADOW_GROUND_Z      # ~1.3u (bas) à ~14.3u (haut)
            h_norm  = max(0.0, min(1.0, (h - 1.0) / 13.0)) # 0=joueur bas, 1=joueur haut
            # Plus haut = ombre plus grande + plus transparente (effet altitude)
            scale   = 1.0 + h_norm * 0.7                    # 1.0→1.7
            alpha   = 1.0 - h_norm * 0.55                   # 1.0→0.45
            self._shadow_np.setPos(new_pos.getX(), new_pos.getY(),
                                   self.SHADOW_GROUND_Z + 0.14)
            self._shadow_np.setScale(scale)
            self._shadow_np.setColorScale(1, 1, 1, alpha)
            self._shadow_np.show()

    def _create_crosshair(self):
        """Réticule — 2 brackets courbés (gauche/droit) style image de référence.
        Chaque bracket = arc ~150° avec dégradé : transparent aux bouts, opaque au centre."""
        root = NodePath("crosshair")
        root.reparentTo(self.game.render)
        root.setLightOff()
        root.setTransparency(TransparencyAttrib.MAlpha)

        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("crosshair", fmt, Geom.UHStatic)
        vw    = GeomVertexWriter(vdata, "vertex")
        cw    = GeomVertexWriter(vdata, "color")

        R    = 0.55    # rayon du bracket
        SEGS = 18      # segments par arc — plus lisse
        SPAN = 1.40    # demi-ouverture en radians (~80°) de chaque côté du centre

        # Bracket gauche : centré sur math.pi (←), bracket droit : centré sur 0 (→)
        centers = [math.pi, 0.0]

        verts = []
        for ca in centers:
            a0 = ca - SPAN
            a1 = ca + SPAN
            for i in range(SEGS + 1):
                t  = i / SEGS
                a  = a0 + t * (a1 - a0)
                # Dégradé : transparent aux extrémités, vif au centre
                fade  = 1.0 - 2.0 * abs(t - 0.5)   # 0→1→0
                alpha = fade ** 1.4                  # courbe douce
                verts.append((math.cos(a) * R, 0, math.sin(a) * R,
                              0.95, 0.82, 0.18, alpha))

        for (x, y, z, r, g, b, a) in verts:
            vw.addData3(x, y, z)
            cw.addData4(r, g, b, a)

        lines = GeomLines(Geom.UHStatic)
        idx = 0
        for _ in range(2):   # 2 brackets
            for i in range(SEGS):
                lines.addVertices(idx + i, idx + i + 1)
            idx += SEGS + 1

        geom = Geom(vdata); geom.addPrimitive(lines)
        gn   = GeomNode("crosshair_geom"); gn.addGeom(geom)
        np   = NodePath(gn)
        np.reparentTo(root)
        np.setRenderModeThickness(2.5)
        np.setDepthWrite(False)
        np.setDepthTest(False)
        np.setBin("fixed", 55)

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

    def show_shield_hit(self, impact_pos=None):
        """Lueur ambrée subtile sur la coque au hit."""
        self.shield_flash_timer = 0.18
        if self._hit_flash_np and not self._hit_flash_np.isEmpty():
            self._hit_flash_np.show()
            self._hit_flash_np.setColorScale(1.5, 0.28, 0.06, 0.055)

    def _create_hit_flash(self):
        """Copie du modèle légèrement agrandie, rouge semi-transparente — flash au hit."""
        flash = self.model_node.copyTo(self.node)
        # Garde le scale original du modèle, juste +10%
        ms = self.model_node.getScale().getX()
        flash.setScale(ms * 1.10)
        flash.setColorScale(4.0, 0.05, 0.05, 0.55)
        flash.setTransparency(TransparencyAttrib.MAlpha)
        flash.setDepthWrite(False)
        flash.setDepthTest(False)
        flash.setBin("transparent", 5)
        flash.setLightOff()
        flash.hide()
        return flash

    # _create_shield / _update_shield — supprimés, réservés pour V3

    def _create_engine_glows(self):
        """4 glows billboard aux réacteurs : halo rouge/rose + noyau blanc. Toujours visibles.

        Attachés à model_node pour tourner avec le vaisseau (roll, pitch, barrel roll).
        getRelativePoint convertit automatiquement node→model_node (H=180 + auto-scale).
        """
        fmt = GeomVertexFormat.getV3c4()

        def make_disc(parent, radius, c_center, c_edge, segs=16):
            vd = GeomVertexData("eg", fmt, Geom.UHStatic)
            vw = GeomVertexWriter(vd, "vertex")
            cw = GeomVertexWriter(vd, "color")
            vw.addData3(0, 0, 0); cw.addData4(c_center)
            for i in range(segs):
                a = 2 * math.pi * i / segs
                vw.addData3(math.cos(a) * radius, 0, math.sin(a) * radius)
                cw.addData4(c_edge)
            tris = GeomTriangles(Geom.UHStatic)
            for i in range(segs):
                tris.addVertices(0, 1 + i, 1 + (i + 1) % segs)
            geom = Geom(vd); geom.addPrimitive(tris)
            gn = GeomNode("eg_disc"); gn.addGeom(geom)
            np = NodePath(gn)
            np.reparentTo(parent)
            np.setTwoSided(True)
            np.setDepthTest(False)
            np.setDepthWrite(False)
            np.setBin("fixed", 50)

        # Récupère le scale hérité de model_node pour le compenser
        ms = self.model_node.getScale().getX()
        inv_scale = (1.0 / ms) if ms > 0 else 1.0

        for (lx, ly, lz) in self._ENGINE_LOCAL:
            # Convertit la position de l'espace node → espace model_node
            # (gère automatiquement le H=180 et l'auto-scale du modèle)
            pos_model = self.model_node.getRelativePoint(self.node, Point3(lx, ly, lz))
            root = self.model_node.attachNewNode("engine_glow_root")
            root.setPos(pos_model)
            root.setScale(inv_scale)        # Annule le scale hérité → taille monde réelle
            root.setColorScale(1/3, 1/3, 1/3, 1)  # Annule le colorScale (3,3,3) hérité → résultat = (1,1,1)
            root.setLightOff()
            root.setTransparency(TransparencyAttrib.MAlpha)
            root.setBillboardPointEye()

            # Couche 1 : halo rouge/rose dégradé
            make_disc(root,
                      radius=0.28,
                      c_center=Vec4(1.0, 0.20, 0.30, 0.85),
                      c_edge  =Vec4(0.9, 0.08, 0.12, 0.0),
                      segs=14)

            # Couche 2 : noyau blanc brillant
            make_disc(root,
                      radius=0.10,
                      c_center=Vec4(1.0, 0.95, 0.90, 1.0),
                      c_edge  =Vec4(1.0, 0.50, 0.45, 0.0),
                      segs=8)
