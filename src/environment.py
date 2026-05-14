"""
Environment — Décor spatial : astéroïdes (sphères déformées), nébuleuses, planètes, débris.
Tout défile vers le joueur pour l'effet de vitesse.
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexArrayFormat, GeomEnums,
    GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath, TransparencyAttrib,
    Fog, Texture, TextureStage, PNMImage,
)
import random
import math
import os


class AsteroidModelCache:
    """Cache de modèles d'astéroïdes extraits du pack gltf."""

    PACK_PATH = "assets/models/asteroids/scene.gltf"
    _templates = []
    _loaded = False

    @classmethod
    def load(cls, game):
        """Charge le pack et extrait chaque astéroïde individuel."""
        if cls._loaded:
            return
        cls._loaded = True

        if not os.path.exists(cls.PACK_PATH):
            print(f"[Asteroids] Pack non trouvé: {cls.PACK_PATH}, mode procédural")
            return

        try:
            model = game.loader.loadModel(cls.PACK_PATH)
            if model:
                # Structure: root → parent → 8 astéroïdes (Object_2..Object_9)
                # On descend jusqu'aux enfants qui ont des meshes
                parent = model
                # Descendre tant qu'il n'y a qu'un seul enfant (nodes conteneurs)
                while True:
                    children = parent.getChildren()
                    if len(children) == 1 and not children[0].node().isGeomNode():
                        parent = children[0]
                    else:
                        break

                children = parent.getChildren()
                for child in children:
                    template = NodePath(f"asteroid_tpl_{len(cls._templates)}")
                    child.copyTo(template)

                    # Recentre le modèle sur son propre centre
                    bounds = template.getTightBounds()
                    if bounds:
                        bmin, bmax = bounds
                        center = (bmin + bmax) / 2
                        # Décale tous les enfants pour centrer à l'origine
                        for c in template.getChildren():
                            c.setPos(c.getPos() - center)
                        template.setPos(0, 0, 0)

                    cls._templates.append(template)

                print(f"[Asteroids] Pack chargé: {len(cls._templates)} astéroïdes")
        except Exception as e:
            print(f"[Asteroids] Erreur chargement: {e}")

    @classmethod
    def get_random(cls):
        """Retourne un clone d'un astéroïde aléatoire du pack, ou None."""
        if not cls._templates:
            return None
        template = random.choice(cls._templates)
        return template.copyTo(NodePath("asteroid_inst"))


class Asteroid:
    """Un astéroïde individuel — sphère déformée procédurale bleu-gris."""

    COLOR_PALETTES = [
        {"base": (0.22, 0.24, 0.30), "var": 0.04},
        {"base": (0.25, 0.27, 0.33), "var": 0.05},
        {"base": (0.20, 0.22, 0.28), "var": 0.04},
        {"base": (0.28, 0.30, 0.36), "var": 0.05},
        {"base": (0.18, 0.20, 0.26), "var": 0.03},
    ]

    def __init__(self, parent, pos, size, speed):
        self.alive = True
        self.speed = speed
        self.size = size
        self.hit_radius = size * 0.5
        self.rot_speed = Vec3(
            random.uniform(-40, 40),
            random.uniform(-40, 40),
            random.uniform(-40, 40),
        )

        # Toujours procédural (les packs sont des amas, utilisés séparément)
        self.node = self._make_deformed_sphere(size)
        self.node.reparentTo(parent)
        self.node.setPos(pos)

    def _make_deformed_sphere(self, size):
        """Crée une sphère UV déformée aléatoirement — chaque astéroïde est unique."""
        root = NodePath("asteroid")

        # Choisit une palette de couleurs
        palette = random.choice(self.COLOR_PALETTES)
        base_r, base_g, base_b = palette["base"]
        color_var = palette["var"]

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("asteroid", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        # Résolution de la sphère (plus c'est haut, plus c'est lisse)
        rings = 8
        sectors = 10
        radius = size / 2

        # Pré-génère les déformations (noise) pour la cohérence
        # On utilise un bruit par vertex pour déformer le rayon
        deform_strength = random.uniform(0.3, 0.55)  # 30-55% — certains très cabossés
        noise_freq = random.uniform(2.0, 3.5)  # Fréquence variable

        vertices_data = []

        for i in range(rings + 1):
            phi = math.pi * i / rings
            for j in range(sectors + 1):
                theta = 2.0 * math.pi * j / sectors

                # Position de base sur la sphère
                nx = math.sin(phi) * math.cos(theta)
                ny = math.sin(phi) * math.sin(theta)
                nz = math.cos(phi)

                # Déformation : bruit pseudo-aléatoire basé sur la position
                # Utilise sin/cos combinés pour un bruit cohérent (pas juste du random)
                noise = (
                    math.sin(nx * noise_freq + 1.3) * 0.4 +
                    math.sin(ny * noise_freq + 2.7) * 0.3 +
                    math.cos(nz * noise_freq + 0.5) * 0.3 +
                    random.uniform(-0.15, 0.15)  # Un peu de random pur pour la rugosité
                )
                deformed_r = radius * (1.0 + noise * deform_strength)

                x = nx * deformed_r
                y = ny * deformed_r
                z = nz * deformed_r

                vertex.addData3(x, y, z)

                # Couleur avec variation par vertex
                cr = base_r + random.uniform(-color_var, color_var)
                cg = base_g + random.uniform(-color_var, color_var)
                cb = base_b + random.uniform(-color_var, color_var)

                # Les cratères (creux) sont plus sombres
                if noise < -0.1:
                    cr *= 0.7
                    cg *= 0.7
                    cb *= 0.7

                col.addData4(
                    max(0.1, min(1, cr)),
                    max(0.1, min(1, cg)),
                    max(0.1, min(1, cb)),
                    1
                )

        # Triangles
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(rings):
            for j in range(sectors):
                a = i * (sectors + 1) + j
                b = a + sectors + 1

                tris.addVertices(a, b, a + 1)
                tris.addVertices(a + 1, b, b + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)

        node = GeomNode("asteroid_mesh")
        node.addGeom(geom)

        np = NodePath(node)
        np.reparentTo(root)

        return root

    def update(self, dt):
        if not self.alive:
            return

        self.node.setY(self.node.getY() - self.speed * dt)

        # Rotation lente
        h, p, r = self.node.getHpr()
        self.node.setHpr(
            h + self.rot_speed.getX() * dt,
            p + self.rot_speed.getY() * dt,
            r + self.rot_speed.getZ() * dt,
        )

        if self.node.getY() < -20:
            self.destroy()

    def get_pos(self):
        if self.alive and not self.node.isEmpty():
            return self.node.getPos()
        return None

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class DistantPlanet:
    """Une planète fixe procédurale qui grossit lentement."""

    def __init__(self, parent, pos, size, color):
        self.alive = True
        self.initial_scale = 1.0
        self.grow_rate = 0.003  # Très lent

        self.node = self._make_sphere(size, color)
        self.node.reparentTo(parent)
        self.node.setPos(pos)
        self.node.setLightOff()

    def _make_sphere(self, radius, color):
        root = NodePath("planet")
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("sphere", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        rings, sectors = 14, 18
        for i in range(rings + 1):
            phi = math.pi * i / rings
            for j in range(sectors + 1):
                theta = 2.0 * math.pi * j / sectors
                x = radius * math.sin(phi) * math.cos(theta)
                y = radius * math.sin(phi) * math.sin(theta)
                z = radius * math.cos(phi)
                vertex.addData3(x, y, z)

                band = math.sin(phi * 4) * 0.08
                band2 = math.sin(phi * 7 + theta * 2) * 0.03
                c = Vec4(
                    max(0, min(1, color.getX() + band + band2)),
                    max(0, min(1, color.getY() + band * 0.5 + band2)),
                    max(0, min(1, color.getZ() - band * 0.3)),
                    1,
                )
                col.addData4(c)

        tris = GeomTriangles(Geom.UHStatic)
        for i in range(rings):
            for j in range(sectors):
                a = i * (sectors + 1) + j
                b = a + sectors + 1
                tris.addVertices(a, b, a + 1)
                tris.addVertices(a + 1, b, b + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("sphere")
        node.addGeom(geom)
        NodePath(node).reparentTo(root)
        return root

    def update(self, dt):
        if not self.alive:
            return
        self.initial_scale += self.grow_rate * dt
        self.node.setScale(self.initial_scale)

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class StarDestroyerDecor:
    """Star Destroyer en arrière-plan — grossit lentement (approche)."""

    MODEL_PATH = "assets/models/star_destroyer/scene.gltf"

    def __init__(self, game, pos, scale=0.01):
        self.alive = True
        self.node = None

        if os.path.exists(self.MODEL_PATH):
            try:
                model = game.loader.loadModel(self.MODEL_PATH)
                if model:
                    self.node = model
                    self.node.reparentTo(game.render)
                    self.node.setPos(pos)
                    self.node.setScale(scale)
                    self.node.setH(90)
                    self.node.setColorScale(Vec4(1.5, 1.5, 1.8, 1))
                    self.node.setLightOff()
                    # Rendu en arrière-plan (derrière les planètes)
                    self.node.setBin("background", 10)
                    print(f"[StarDestroyer] Modèle chargé, scale={scale}")
            except Exception as e:
                print(f"[StarDestroyer] Erreur: {e}")

    def update(self, dt):
        pass


class Nebula:
    """Nappe de couleur en fond (points colorés semi-transparents)."""

    def __init__(self, parent, center_pos, color, size=30.0):
        self.alive = True
        self.speed = 1.0

        self.node = NodePath("nebula")
        self.node.reparentTo(parent)
        self.node.setPos(center_pos)
        self.node.setLightOff()

        self._make_cloud(size, color)

    def _make_cloud(self, size, color):
        num_points = 80

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("nebula", fmt, Geom.UHStatic)
        vdata.setNumRows(num_points)

        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        for _ in range(num_points):
            x = random.gauss(0, size * 0.4)
            y = random.gauss(0, size * 0.3)
            z = random.gauss(0, size * 0.4)

            vertex.addData3(x, y, z)

            r = color.getX() + random.uniform(-0.1, 0.1)
            g = color.getY() + random.uniform(-0.1, 0.1)
            b = color.getZ() + random.uniform(-0.1, 0.1)
            a = random.uniform(0.03, 0.08)
            col.addData4(max(0, r), max(0, g), max(0, b), a)

        from panda3d.core import GeomPoints
        points = GeomPoints(Geom.UHStatic)
        points.addConsecutiveVertices(0, num_points)

        geom = Geom(vdata)
        geom.addPrimitive(points)

        geom_node = GeomNode("nebula_cloud")
        geom_node.addGeom(geom)

        np = NodePath(geom_node)
        np.reparentTo(self.node)
        np.setRenderModeThickness(2)
        np.setTransparency(TransparencyAttrib.MAlpha)

    def update(self, dt):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - self.speed * dt)
        if self.node.getY() < -80:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


# ============================================================
# L2 — Surface lunaire
# ============================================================

class LunarTerrain:
    """Dalle de terrain lunaire — plan horizontal défilant à Z=-7.8."""

    GROUND_Z = -7.8

    def __init__(self, parent, x_center, y_pos, width=240.0, depth=22.0):
        self.alive = True
        self._depth = depth
        self.node = self._make_tile(width, depth)
        self.node.reparentTo(parent)
        self.node.setPos(x_center, y_pos, self.GROUND_Z)
        self.node.setLightOff()   # Pas de lumière scène — couleurs vertex brutes

    # Rayon de courbure planétaire (plus grand = plus plat)
    # À x=±120 (width=240) : chute = 120²/(2×420) ≈ 17u → horizon bien visible
    SPHERE_R = 420.0

    def _make_tile(self, w, d):
        root = NodePath("lunar_tile")
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("tile", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        # Densité réduite sur X (w grand) pour rester performant
        segs_x = max(16, int(w / 8))
        segs_y = max(8, int(d / 2))
        R = self.SPHERE_R

        for i in range(segs_x + 1):
            for j in range(segs_y + 1):
                x = -w / 2 + i * w / segs_x
                y = -d / 2 + j * d / segs_y

                # ── Courbure sphérique (approximation parabolique) ──────────
                # z = -(x²+y²)/(2R) → centre haut, bords courbés vers le bas
                # Déterministe aux bords → joints seamless entre dalles
                sphere_z = -(x * x + y * y) / (2.0 * R)

                # Déformation de cratères uniquement à l'intérieur
                edge = (j == 0 or j == segs_y)
                bump = 0.0 if edge else random.uniform(-0.35, 0.35)
                z = sphere_z + bump

                vertex.addData3(x, y, z)

                # Gris lunaire — légèrement bleuté, pas de rouge
                g = 0.30 + random.uniform(-0.05, 0.07)
                # Zones creuses (cratères) plus sombres
                dark = 0.72 if bump < -0.18 else (0.88 if bump < 0 else 1.0)
                col.addData4(g * 0.93 * dark, g * 0.95 * dark, g * dark, 1.0)

        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segs_x):
            for j in range(segs_y):
                a = i * (segs_y + 1) + j
                b = a + segs_y + 1
                tris.addVertices(a, b, a + 1)
                tris.addVertices(a + 1, b, b + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("lunar_tile_mesh")
        node.addGeom(geom)
        NodePath(node).reparentTo(root)
        return root

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -45:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class LunarRock:
    """Rocher lunaire procédural — plus plat et gris que les astéroïdes classiques."""

    def __init__(self, parent, pos, size, speed):
        self.alive = True
        self.speed = speed
        self.size = size
        self.hit_radius = size * 0.45
        self.rot_speed = Vec3(
            random.uniform(-20, 20),
            random.uniform(-20, 20),
            random.uniform(-15, 15),
        )
        self.node = self._make_rock(size)
        self.node.reparentTo(parent)
        self.node.setPos(pos)

    def _make_rock(self, size):
        root = NodePath("lunar_rock")
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("rock", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        rings, sectors = 6, 8
        radius = size / 2
        deform = random.uniform(0.25, 0.50)
        freq = random.uniform(1.5, 2.8)
        flat = random.uniform(0.55, 0.75)   # Aplati verticalement (style rocher)

        for i in range(rings + 1):
            phi = math.pi * i / rings
            for j in range(sectors + 1):
                theta = 2.0 * math.pi * j / sectors
                nx = math.sin(phi) * math.cos(theta)
                ny = math.sin(phi) * math.sin(theta)
                nz = math.cos(phi)
                noise = (
                    math.sin(nx * freq + 1.1) * 0.4 +
                    math.sin(ny * freq + 2.3) * 0.3 +
                    math.cos(nz * freq + 0.8) * 0.3 +
                    random.uniform(-0.1, 0.1)
                )
                r = radius * (1.0 + noise * deform)
                vertex.addData3(nx * r, ny * r, nz * r * flat)
                g = 0.28 + random.uniform(-0.05, 0.07)
                # Gris lunaire légèrement bleuté
                col.addData4(g * 0.96, g * 0.97, g, 1.0)

        tris = GeomTriangles(Geom.UHStatic)
        for i in range(rings):
            for j in range(sectors):
                a = i * (sectors + 1) + j
                b = a + sectors + 1
                tris.addVertices(a, b, a + 1)
                tris.addVertices(a + 1, b, b + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("rock_mesh")
        node.addGeom(geom)
        NodePath(node).reparentTo(root)
        return root

    def update(self, dt):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - self.speed * dt)
        h, p, r = self.node.getHpr()
        self.node.setHpr(
            h + self.rot_speed.getX() * dt,
            p + self.rot_speed.getY() * dt,
            r + self.rot_speed.getZ() * dt,
        )
        if self.node.getY() < -20:
            self.destroy()

    def get_pos(self):
        if self.alive and not self.node.isEmpty():
            return self.node.getPos()
        return None

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


# ============================================================
# L3 — Tranchée
# ============================================================

# ── Format vertex custom : position + color + UV ──────────────────────────────
def _make_v3c4t2():
    """Crée (une fois) un GeomVertexFormat avec position, couleur RGBA et UV."""
    arr = GeomVertexArrayFormat()
    arr.addColumn("vertex",   3, GeomEnums.NT_float32, GeomEnums.C_point)
    arr.addColumn("color",    4, GeomEnums.NT_float32, GeomEnums.C_color)
    arr.addColumn("texcoord", 2, GeomEnums.NT_float32, GeomEnums.C_texcoord)
    fmt = GeomVertexFormat()
    fmt.addArray(arr)
    return GeomVertexFormat.registerFormat(fmt)

_V3C4T2 = _make_v3c4t2()


def _gen_trench_wall_tex(size=512):
    """Génère une texture procédurale béton/métal Death Star (une seule fois).

    Structure : carreaux 3u × 3u — joints fins foncés + variation par cellule
    + léger bruit pixel. Renvoie une Texture Panda3D prête à l'emploi.
    """
    img = PNMImage(size, size)
    img.makeRgb()
    tile = 64          # pixels par panneau-monde (3u mappé sur tile px)
    seam = 3           # largeur joint en pixels
    rng  = random.Random(42)

    for py in range(size):
        for px in range(size):
            # Position dans le carreau
            cx = px % tile;  cy = py % tile
            dx = min(cx, tile - cx);  dy = min(cy, tile - cy)
            on_seam = (dx < seam or dy < seam)

            # Variation de cellule (déterministe)
            ci = px // tile;  cj = py // tile
            cell_v = math.sin(ci * 1.73 + cj * 2.31) * 0.06

            # Bruit pixel fin
            noise = rng.uniform(-0.025, 0.025)

            if on_seam:
                g = 0.28 + noise * 0.5
            else:
                g = 0.62 + cell_v + noise

            g = max(0.0, min(1.0, g))
            img.setXelA(px, py, g, g, g * 0.96, 1.0)

    tex = Texture("trench_wall")
    tex.load(img)
    tex.setWrapU(Texture.WM_repeat)
    tex.setWrapV(Texture.WM_repeat)
    tex.setMagfilter(Texture.FT_linear)
    tex.setMinfilter(Texture.FT_linear_mipmap_linear)
    tex.generateRamMipmapImages()
    return tex


def _gen_trench_floor_tex(size=512):
    """Texture béton sombre pour le sol de la tranchée."""
    img = PNMImage(size, size)
    img.makeRgb()
    tile = 80
    seam = 4
    rng  = random.Random(99)

    for py in range(size):
        for px in range(size):
            cx = px % tile;  cy = py % tile
            dx = min(cx, tile - cx);  dy = min(cy, tile - cy)
            on_seam = (dx < seam or dy < seam)
            ci = px // tile;  cj = py // tile
            cell_v = math.sin(ci * 2.11 + cj * 1.57) * 0.05
            noise  = rng.uniform(-0.02, 0.02)
            g = (0.22 + noise) if on_seam else (0.50 + cell_v + noise)
            g = max(0.0, min(1.0, g))
            img.setXelA(px, py, g * 1.01, g, g * 0.93, 1.0)

    tex = Texture("trench_floor")
    tex.load(img)
    tex.setWrapU(Texture.WM_repeat)
    tex.setWrapV(Texture.WM_repeat)
    tex.setMagfilter(Texture.FT_linear)
    tex.setMinfilter(Texture.FT_linear_mipmap_linear)
    tex.generateRamMipmapImages()
    return tex


# Cache module-level — générés une fois, réutilisés par toutes les dalles
_TRENCH_WALL_TEX  = None
_TRENCH_FLOOR_TEX = None


def _get_wall_tex():
    global _TRENCH_WALL_TEX
    if _TRENCH_WALL_TEX is None:
        _TRENCH_WALL_TEX = _gen_trench_wall_tex()
    return _TRENCH_WALL_TEX


def _get_floor_tex():
    global _TRENCH_FLOOR_TEX
    if _TRENCH_FLOOR_TEX is None:
        _TRENCH_FLOOR_TEX = _gen_trench_floor_tex()
    return _TRENCH_FLOOR_TEX


# TextureStage partagé (mode Modulate — multiplie texture × vertex color)
_TS_MODULATE = TextureStage("modulate")
_TS_MODULATE.setMode(TextureStage.M_modulate)


class TrenchWallPanel:
    """Panneau de mur latéral de tranchée — défile en Y, fixe en X."""

    WALL_X_LEFT  = -13.5
    WALL_X_RIGHT =  13.5

    # Panneaux vertex-color : joints fins + gradient Z (haut clair, bas sombre)
    PANEL_SIZE = 3.0   # taille d'un panneau en unités monde
    SEAM_W     = 0.06  # épaisseur du joint (fraction de l'unité)

    def __init__(self, parent, x_side, y_pos, height=16.0, depth=22.0, lit=True):
        self.alive = True
        self.is_right = (x_side > 0)
        self.lit = lit
        self.node = self._make_wall(height, depth)
        self.node.reparentTo(parent)
        self.node.setPos(x_side, y_pos, 0)
        self.node.setLightOff()

    def _wall_color(self, z, h):
        """Couleur vertex = gradient Z × contraste directionnel.
        Utilisée en mode M_modulate : multipliée par la texture au rendu.
        Lit  : 0.55 (bas) → 1.00 (haut)   — côté lune
        Dark : 0.18 (bas) → 0.42 (haut)   — côté ombre
        """
        t = (z + h / 2) / h
        if self.lit:
            g = 0.55 + 0.45 * t
        else:
            g = 0.18 + 0.24 * t
        return Vec4(g * 1.02, g, g * 0.96, 1.0)

    def _make_wall(self, h, d):
        root = NodePath("trench_wall")
        vdata = GeomVertexData("wall", _V3C4T2, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")
        tw = GeomVertexWriter(vdata, "texcoord")

        segs_z = max(4, int(h))
        segs_y = max(4, int(d))
        # UV : 1 unité monde = 1/3 de tuile texture (panneau = 3u → 1 répétition)
        uv_scale = 1.0 / 3.0

        for i in range(segs_z + 1):
            for j in range(segs_y + 1):
                y = -d / 2 + j * d / segs_y
                z = -h / 2 + i * h / segs_z
                vw.addData3(0, y, z)
                cw.addData4(self._wall_color(z, h))
                tw.addData2(y * uv_scale, z * uv_scale)

        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segs_z):
            for j in range(segs_y):
                a = i * (segs_y + 1) + j
                b = a + segs_y + 1
                if self.is_right:
                    tris.addVertices(a, b, a + 1)
                    tris.addVertices(a + 1, b, b + 1)
                else:
                    tris.addVertices(a, a + 1, b)
                    tris.addVertices(a + 1, b + 1, b)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("trench_wall_mesh")
        node.addGeom(geom)
        np = NodePath(node)
        np.setTexture(_TS_MODULATE, _get_wall_tex())
        np.reparentTo(root)
        return root

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -35:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class TrenchFloorPanel:
    """Dalle de sol de tranchée — défile en Y, fixe en Z."""

    FLOOR_Z = -7.5

    def __init__(self, parent, x_center, y_pos, width=28.0, depth=22.0):
        self.alive = True
        self.node = self._make_floor(width, depth)
        self.node.reparentTo(parent)
        self.node.setPos(x_center, y_pos, self.FLOOR_Z)
        self.node.setLightOff()

    def _make_floor(self, w, d):
        root  = NodePath("trench_floor")
        vdata = GeomVertexData("floor", _V3C4T2, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")
        tw = GeomVertexWriter(vdata, "texcoord")

        segs_x = max(4, int(w / 2))
        segs_y = max(4, int(d / 2))
        uv_scale = 1.0 / 4.0   # panneaux sol 4u → 1 répétition

        for i in range(segs_x + 1):
            for j in range(segs_y + 1):
                x = -w / 2 + i * w / segs_x
                y = -d / 2 + j * d / segs_y
                vw.addData3(x, y, 0)
                # Vertex color : gris sombre uniforme (texture porte le détail)
                g = 0.55
                cw.addData4(g * 1.01, g, g * 0.92, 1.0)
                tw.addData2(x * uv_scale, y * uv_scale)

        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segs_x):
            for j in range(segs_y):
                a = i * (segs_y + 1) + j
                b = a + segs_y + 1
                tris.addVertices(a, b, a + 1)
                tris.addVertices(a + 1, b, b + 1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("trench_floor_mesh")
        node.addGeom(geom)
        np = NodePath(node)
        np.setTexture(_TS_MODULATE, _get_floor_tex())
        np.reparentTo(root)
        return root

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -35:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


class TrenchSurfacePanel:
    """Surface de la Death Star de part et d'autre de la tranchée.
    Panneau horizontal au sommet des murs pour boucher le ciel 'espace'.
    """

    SURFACE_Z  = 8.2      # sommet des murs de tranchée (h=16, centre Z=0 → top = +8)
    WALL_HALF  = 13.5     # bord intérieur = bord du mur
    SURFACE_W  = 110.0    # largeur depuis le mur vers l'extérieur (couvre le FOV 60° à Y=200)

    def __init__(self, parent, side, y_pos, depth=22.0):
        """side: -1 gauche, +1 droite."""
        self.alive = True
        self.node = self._make_surface(depth)
        self.node.reparentTo(parent)
        x_center = side * (self.WALL_HALF + self.SURFACE_W / 2.0)
        self.node.setPos(x_center, y_pos, self.SURFACE_Z)
        self.node.setLightOff()

    def _make_surface(self, d):
        root = NodePath("trench_surface")
        w = self.SURFACE_W
        fmt  = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("surface", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")

        segs_x = max(8, int(w / 8))
        segs_y = max(4, int(d / 4))
        ps, sw = 3.0, 0.06

        for i in range(segs_x + 1):
            for j in range(segs_y + 1):
                x = -w / 2 + i * w / segs_x
                y = -d / 2 + j * d / segs_y
                vw.addData3(x, y, 0)
                px = x % ps;  py = y % ps
                dx = min(px, ps - px);  dy_v = min(py, ps - py)
                bevel = min(1.0, min(dx, dy_v) / sw)
                pi = int((x + 200) / ps);  pj = int((y + 100) / ps)
                pv = math.sin(pi * 1.73 + pj * 2.31) * 0.04
                base = (0.38 + pv) * (0.14 + 0.86 * bevel)
                g = max(0.03, min(0.65, base))
                cw.addData4(g * 1.03, g, g * 0.95, 1.0)

        # Face visible depuis le BAS (winding CCW vu d'en bas)
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segs_x):
            for j in range(segs_y):
                a = i * (segs_y + 1) + j
                b = a + segs_y + 1
                tris.addVertices(a, a + 1, b)
                tris.addVertices(a + 1, b + 1, b)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("trench_surface_mesh")
        node.addGeom(geom)
        NodePath(node).reparentTo(root)
        return root

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -35:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


# ============================================================
# L3 — Décorations 3D murs de tranchée
# ============================================================

class TrenchDecorGroup:
    """Groupe de décorations 3D fixées sur un segment de mur de tranchée.

    Génère aléatoirement des boîtes, cylindres, disques, marches et rails
    avec coloration par vertex simulant un éclairage zénithal (haut lumineux,
    bas dans l'ombre).
    """

    WALL_Z_LO = -7.5    # Z sol tranchée
    WALL_Z_HI =  8.0    # Z sommet murs

    def __init__(self, parent, x_wall, y_pos, depth=22.0, lit=True):
        self.alive = True
        self.lit = lit
        # Direction de protrusion depuis le mur vers l'intérieur de la tranchée
        self.inward = 1.0 if x_wall < 0 else -1.0

        # Seed déterministe — même (x_wall, y_pos) = même décor à chaque spawn
        rng = random.Random(int(round(abs(x_wall) * 137 + y_pos * 73.1)) & 0xFFFFFF)

        self.node = NodePath("decor_group")
        self.node.reparentTo(parent)
        self.node.setPos(x_wall, y_pos, 0)
        self.node.setLightOff()

        self._build(rng, depth)

    # ----------------------------------------------------------
    # Nuance vertex — gradient Z (ombre bas → lumière haut)
    # ----------------------------------------------------------

    def _shade(self, z_world):
        """Gris Death Star, gradient vertical : ombre en bas, lumière en haut.
        Côté éclairé (lit=True) : 0.22→0.78 | Côté ombre (lit=False) : 0.08→0.30
        """
        t = (z_world - self.WALL_Z_LO) / (self.WALL_Z_HI - self.WALL_Z_LO)
        t = max(0.0, min(1.0, t))
        if self.lit:
            g = 0.20 + t * 0.42   # 0.20 (ombre) → 0.62 (lumière)
        else:
            g = 0.07 + t * 0.18   # 0.07 → 0.25 (côté nuit)
        return Vec4(g * 1.03, g * 1.00, g * 0.96, 1.0)  # Légèrement chaud

    # ----------------------------------------------------------
    # Primitives géométriques
    # ----------------------------------------------------------

    def _make_box(self, bw, bh, bd, z_center):
        """Boîte pleine — bw=X(protrusion), bh=Z(hauteur), bd=Y(épaisseur)."""
        root = NodePath("dbox")
        fmt  = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("box", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")

        hx, hy, hz = bw / 2, bd / 2, bh / 2
        corners = [
            (-hx, -hy, -hz), ( hx, -hy, -hz), ( hx,  hy, -hz), (-hx,  hy, -hz),
            (-hx, -hy,  hz), ( hx, -hy,  hz), ( hx,  hy,  hz), (-hx,  hy,  hz),
        ]
        for cx, cy, cz in corners:
            vw.addData3(cx, cy, cz)
            cw.addData4(self._shade(z_center + cz))

        tris = GeomTriangles(Geom.UHStatic)
        for f in [
            (0, 1, 2), (0, 2, 3),           # bas
            (4, 6, 5), (4, 7, 6),           # haut
            (0, 4, 5), (0, 5, 1),           # avant
            (2, 6, 7), (2, 7, 3),           # arrière
            (0, 3, 7), (0, 7, 4),           # gauche
            (1, 5, 6), (1, 6, 2),           # droite
        ]:
            tris.addVertices(*f)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gn = GeomNode("dbox_m")
        gn.addGeom(geom)
        np = NodePath(gn)
        np.setTwoSided(True)
        np.reparentTo(root)
        return root

    def _make_cylinder_v(self, radius, height, z_center, segs=8):
        """Cylindre vertical (axe Z) — colonne / tuyau debout."""
        root  = NodePath("dcylv")
        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("cylv", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")

        hz = height / 2
        for zi in (-hz, hz):
            for s in range(segs):
                a = 2 * math.pi * s / segs
                vw.addData3(radius * math.cos(a), radius * math.sin(a), zi)
                cw.addData4(self._shade(z_center + zi))

        # Centres des disques bas/haut
        vw.addData3(0, 0, -hz);  cw.addData4(self._shade(z_center - hz))
        vw.addData3(0, 0,  hz);  cw.addData4(self._shade(z_center + hz))
        c_bot = 2 * segs
        c_top = 2 * segs + 1

        tris = GeomTriangles(Geom.UHStatic)
        for s in range(segs):
            b0 = s;           b1 = (s + 1) % segs
            t0 = segs + s;    t1 = segs + (s + 1) % segs
            # Manteau
            tris.addVertices(b0, b1, t0)
            tris.addVertices(b1, t1, t0)
            # Disque bas (CW vu d'en bas)
            tris.addVertices(c_bot, b1, b0)
            # Disque haut (CCW vu d'en haut)
            tris.addVertices(c_top, t0, t1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gn = GeomNode("dcylv_m")
        gn.addGeom(geom)
        np = NodePath(gn)
        np.setTwoSided(True)
        np.reparentTo(root)
        return root

    def _make_cylinder_h(self, radius, length, z_center, segs=6):
        """Cylindre horizontal (axe Y) — rail / barre / tuyau couché."""
        root  = NodePath("dcylh")
        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("cylh", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")

        hl = length / 2
        for yi in (-hl, hl):
            for s in range(segs):
                a = 2 * math.pi * s / segs
                x = radius * math.cos(a)
                z = radius * math.sin(a)
                vw.addData3(x, yi, z)
                cw.addData4(self._shade(z_center + z))

        tris = GeomTriangles(Geom.UHStatic)
        for s in range(segs):
            b0 = s;           b1 = (s + 1) % segs
            t0 = segs + s;    t1 = segs + (s + 1) % segs
            tris.addVertices(b0, t0, b1)
            tris.addVertices(b1, t0, t1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gn = GeomNode("dcylh_m")
        gn.addGeom(geom)
        np = NodePath(gn)
        np.setTwoSided(True)
        np.reparentTo(root)
        return root

    def _make_disc(self, radius, thickness, z_center, segs=12):
        """Disque circulaire dans le plan YZ — hublot / panneau rond."""
        root  = NodePath("ddisc")
        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("disc", fmt, Geom.UHStatic)
        vw = GeomVertexWriter(vdata, "vertex")
        cw = GeomVertexWriter(vdata, "color")

        ht = thickness / 2

        # Face avant (+X) : centre puis anneau
        vw.addData3(ht, 0, 0);  cw.addData4(self._shade(z_center))
        c_front = 0
        for s in range(segs):
            a = 2 * math.pi * s / segs
            y, z = radius * math.cos(a), radius * math.sin(a)
            vw.addData3(ht, y, z);  cw.addData4(self._shade(z_center + z))
        # Anneau avant : indices 1..segs

        # Face arrière (−X) : centre puis anneau
        vw.addData3(-ht, 0, 0);  cw.addData4(self._shade(z_center))
        c_back = segs + 1
        for s in range(segs):
            a = 2 * math.pi * s / segs
            y, z = radius * math.cos(a), radius * math.sin(a)
            vw.addData3(-ht, y, z);  cw.addData4(self._shade(z_center + z))
        # Anneau arrière : indices segs+2..2*segs+1

        tris = GeomTriangles(Geom.UHStatic)
        for s in range(segs):
            f0 = 1 + s;           f1 = 1 + (s + 1) % segs
            b0 = c_back + 1 + s;  b1 = c_back + 1 + (s + 1) % segs
            # Face avant
            tris.addVertices(c_front, f0, f1)
            # Face arrière
            tris.addVertices(c_back, b1, b0)
            # Tranche
            tris.addVertices(f0, b0, f1)
            tris.addVertices(f1, b0, b1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gn = GeomNode("ddisc_m")
        gn.addGeom(geom)
        np = NodePath(gn)
        np.setTwoSided(True)
        np.reparentTo(root)
        return root

    def _make_steps(self, size, n_steps, z_center):
        """Structure en marches : n boîtes empilées, plus large et profonde en bas."""
        root = NodePath("dsteps")
        total_h = size * 0.40 * n_steps
        for i in range(n_steps):
            t = (n_steps - 1 - i) / max(n_steps - 1, 1)   # 1.0 bas → 0.0 haut
            sw = size * (0.35 + 0.65 * t)   # protrusion
            sh = size * 0.38                 # hauteur de la marche
            sd = size * (0.4 + 0.6 * t)     # épaisseur le long du mur
            z_off = -total_h / 2 + i * sh + sh / 2
            box = self._make_box(sw, sh * 0.92, sd, z_center + z_off)
            box.reparentTo(root)
            box.setPos(0, 0, z_off)
        return root

    def _make_conduit_group(self, rng, z_center, length):
        """Groupe de 2-4 tuyaux parallèles horizontaux (axe Y) de diamètres variés.
        Inspiré des gaines/conduits de la tranchée Death Star."""
        root = NodePath("dconduit")
        n_pipes = rng.randint(2, 4)
        z_off = 0.0
        for i in range(n_pipes):
            r = rng.uniform(0.06, 0.22)
            gap = rng.uniform(0.04, 0.12)
            pipe = self._make_cylinder_h(r, length * rng.uniform(0.7, 1.0), z_center + z_off, segs=6)
            pipe.reparentTo(root)
            pipe.setPos(self.inward * (r + 0.04), 0, z_off)
            z_off += r * 2 + gap
        return root

    # ----------------------------------------------------------
    # Construction du groupe
    # ----------------------------------------------------------

    def _build(self, rng, depth):
        """Génère et place aléatoirement les décorations sur ce segment."""
        half_d = depth / 2.0

        # ── Rails horizontaux (toujours présents, 1-3 rails) ───
        n_rails = rng.randint(1, 3)
        z_rail_candidates = [-4.5, -3.0, -1.5, 0.5, 2.0, 3.5, 5.5]
        rng.shuffle(z_rail_candidates)
        for ri in range(n_rails):
            z_rail = z_rail_candidates[ri]
            r_rail = rng.uniform(0.06, 0.16)
            rail = self._make_cylinder_h(r_rail, depth * rng.uniform(0.85, 0.98), z_rail)
            rail.reparentTo(self.node)
            rail.setPos(self.inward * (r_rail + 0.04), 0, z_rail)

        # ── Groupe de conduits (présent ~70% du temps) ─────────
        if rng.random() < 0.70:
            z_c = rng.uniform(self.WALL_Z_LO + 1.5, self.WALL_Z_HI - 1.5)
            cg = self._make_conduit_group(rng, z_c, depth * rng.uniform(0.5, 0.9))
            cg.reparentTo(self.node)
            cg.setPos(0, rng.uniform(-half_d * 0.4, half_d * 0.4), z_c)

        # ── Éléments individuels ────────────────────────────────
        shape_pool = [
            'box', 'box', 'box', 'box', 'box',
            'cylinder_v', 'cylinder_v', 'cylinder_v',
            'disc', 'disc',
            'steps', 'steps',
            'conduit',
        ]
        n_items  = rng.randint(5, 10)
        placed_y = []

        for _ in range(n_items * 8):
            if len(placed_y) >= n_items:
                break

            y = rng.uniform(-half_d + 0.8, half_d - 0.8)
            min_sep = rng.uniform(0.8, 1.8)
            if any(abs(y - yp) < min_sep for yp in placed_y):
                continue

            z_ctr = rng.uniform(self.WALL_Z_LO + 0.8, self.WALL_Z_HI - 0.8)
            shape = rng.choice(shape_pool)

            if shape == 'box':
                bw = rng.uniform(0.3, 2.5)
                bh = rng.uniform(0.25, 2.2)
                bd = rng.uniform(0.25, 1.6)
                sn = self._make_box(bw, bh, bd, z_ctr)
                protrude = bw / 2

            elif shape == 'cylinder_v':
                r = rng.uniform(0.15, 0.65)
                h = rng.uniform(0.5, 3.0)
                sn = self._make_cylinder_v(r, h, z_ctr)
                protrude = r

            elif shape == 'disc':
                r   = rng.uniform(0.35, 1.2)
                th  = rng.uniform(0.15, 0.40)
                sn  = self._make_disc(r, th, z_ctr)
                protrude = th / 2

            elif shape == 'conduit':
                sn = self._make_conduit_group(rng, z_ctr, rng.uniform(0.8, 2.5))
                protrude = 0.3

            else:  # steps
                sz    = rng.uniform(0.7, 2.4)
                n_st  = rng.randint(2, 4)
                sn    = self._make_steps(sz, n_st, z_ctr)
                protrude = sz * 0.35

            sn.reparentTo(self.node)
            sn.setPos(self.inward * protrude, y, z_ctr)
            placed_y.append(y)

    # ----------------------------------------------------------

    def update(self, dt, scroll_speed):
        if not self.alive:
            return
        self.node.setY(self.node.getY() - scroll_speed * dt)
        if self.node.getY() < -35:
            self.destroy()

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


# ============================================================
# Environment principal (level-aware)
# ============================================================

class Environment:
    """Gère tout le décor spatial — adapté selon le niveau actif."""

    ASTEROID_INTERVAL = 1.8
    NEBULA_INTERVAL = 35.0
    DEBRIS_INTERVAL = 5.0

    SPAWN_DEPTH = 200.0
    FIELD_WIDTH = 25.0
    FIELD_HEIGHT = 15.0

    TILE_DEPTH = 22.0   # Profondeur d'une dalle/panneau (L2 + L3)

    def __init__(self, game, level=1):
        self.game = game
        self.level = level

        # Nettoie tout brouillard d'un niveau précédent
        game.render.clearFog()

        AsteroidModelCache.load(game)

        # Listes communes
        self.asteroids = []
        self.planets = []
        self.nebulae = []
        self.debris = []

        # Listes spécifiques L2/L3
        self.terrain_tiles  = []   # L2 sol lunaire
        self.wall_panels    = []   # L3 murs tranchée
        self.floor_panels   = []   # L3 sol tranchée
        self.surface_panels = []   # L3 surface Death Star (au-dessus des murs)
        self.decor_groups   = []   # L3 décorations 3D sur les murs

        # Timers
        self.asteroid_timer = 2.0
        self.nebula_timer   = 15.0
        self.debris_timer   = 4.0

        self.star_destroyer = None

        # Couleurs nébuleuses (L1/L4)
        self.nebula_colors = [
            Vec4(0.6, 0.2, 0.8, 1),
            Vec4(0.2, 0.4, 0.9, 1),
            Vec4(0.8, 0.3, 0.2, 1),
            Vec4(0.2, 0.7, 0.5, 1),
            Vec4(0.9, 0.6, 0.1, 1),
        ]

        # Init selon le niveau
        if level == 1:
            self._spawn_fixed_planets()
        elif level == 2:
            self._init_lunar()
        elif level == 3:
            self._init_trench()
        elif level == 4:
            self._spawn_nebula_planet()

    # ----------------------------------------------------------
    # Init par niveau
    # ----------------------------------------------------------

    def _init_lunar(self):
        """L2 — Sol continu du joueur jusqu'à SPAWN_DEPTH, pas d'overlap (bords déterministes)."""
        d = self.TILE_DEPTH
        y = 15.0
        while y <= self.SPAWN_DEPTH + d:
            self.terrain_tiles.append(LunarTerrain(self.game.render, 0, y, depth=d))
            y += d

    def _init_trench(self):
        """L3 — Tranchée continue + brouillard linéaire pour masquer le clipping."""
        # Brouillard : fond gris sombre, onset 90u → opaque 215u
        bg = (0.04, 0.04, 0.05)
        fog = Fog("trench_fog")
        fog.setColor(*bg)
        fog.setLinearRange(90.0, 215.0)
        self.game.render.setFog(fog)
        self._trench_fog = fog

        # Lune côté droit (source de lumière) — haute, lointaine, fixe
        moon = DistantPlanet(
            self.game.render,
            Point3(-18, 140, 28),         # gauche (-X), loin, très haut
            size=4.5,
            color=Vec4(0.88, 0.88, 0.78, 1),   # blanc-chaud lunaire
        )
        moon.grow_rate = 0.0   # ne grossit pas — planète fixe
        self.planets.append(moon)

        d = self.TILE_DEPTH
        y = 15.0
        while y <= self.SPAWN_DEPTH + d:
            self._spawn_trench_row(y)
            y += d

    def _spawn_trench_row(self, y):
        d = self.TILE_DEPTH
        # Côté gauche : dans l'ombre (lit=False) | Côté droit : éclairé par la lune (lit=True)
        self.wall_panels.append(TrenchWallPanel(
            self.game.render, TrenchWallPanel.WALL_X_LEFT,  y, depth=d, lit=False))
        self.wall_panels.append(TrenchWallPanel(
            self.game.render, TrenchWallPanel.WALL_X_RIGHT, y, depth=d, lit=True))
        self.floor_panels.append(TrenchFloorPanel(
            self.game.render, 0, y, depth=d))
        self.surface_panels.append(TrenchSurfacePanel(
            self.game.render, -1, y, depth=d))
        self.surface_panels.append(TrenchSurfacePanel(
            self.game.render, +1, y, depth=d))
        self.decor_groups.append(TrenchDecorGroup(
            self.game.render, TrenchWallPanel.WALL_X_LEFT,  y, depth=d, lit=False))
        self.decor_groups.append(TrenchDecorGroup(
            self.game.render, TrenchWallPanel.WALL_X_RIGHT, y, depth=d, lit=True))

    def _spawn_nebula_planet(self):
        """L4 — Nébuleuse colorée en fond."""
        p = DistantPlanet(
            self.game.render,
            Point3(0, 180, 0),
            size=30,
            color=Vec4(0.4, 0.2, 0.6, 1),
        )
        self.planets.append(p)

    # ----------------------------------------------------------
    # Update principal
    # ----------------------------------------------------------

    def update(self, dt, scroll_speed):
        if self.level == 1:
            self._update_l1(dt, scroll_speed)
        elif self.level == 2:
            self._update_l2(dt, scroll_speed)
        elif self.level == 3:
            self._update_l3(dt, scroll_speed)
        elif self.level == 4:
            self._update_l4(dt, scroll_speed)

        # Cleanup commun
        self.asteroids     = [a for a in self.asteroids if a.alive]
        self.nebulae       = [n for n in self.nebulae   if n.alive]
        self.debris        = [d for d in self.debris    if d.alive]
        self.terrain_tiles  = [t for t in self.terrain_tiles  if t.alive]
        self.wall_panels    = [w for w in self.wall_panels    if w.alive]
        self.floor_panels   = [f for f in self.floor_panels   if f.alive]
        self.surface_panels = [s for s in self.surface_panels if s.alive]
        self.decor_groups   = [dg for dg in self.decor_groups  if dg.alive]

        for p in self.planets:
            p.update(dt)
        if self.star_destroyer:
            self.star_destroyer.update(dt)

    def _update_l1(self, dt, scroll_speed):
        """L1 — Astéroïdes + nébuleuses."""
        speed_factor = scroll_speed / 20.0

        self.asteroid_timer -= dt
        if self.asteroid_timer <= 0:
            self._spawn_asteroid(scroll_speed)
            self.asteroid_timer = self.ASTEROID_INTERVAL / speed_factor

        for a in self.asteroids:
            a.update(dt)

        self.nebula_timer -= dt
        if self.nebula_timer <= 0:
            self._spawn_nebula()
            self.nebula_timer = self.NEBULA_INTERVAL + random.uniform(-5, 5)
        for n in self.nebulae:
            n.update(dt)

        self.debris_timer -= dt
        if self.debris_timer <= 0:
            self._spawn_debris(scroll_speed)
            self.debris_timer = self.DEBRIS_INTERVAL + random.uniform(-1, 1)
        for d in self.debris:
            d.update(dt)

    def _update_l2(self, dt, scroll_speed):
        """L2 — Surface lunaire : rochers gris + terrain continu."""
        speed_factor = scroll_speed / 20.0

        # Rochers lunaires
        self.asteroid_timer -= dt
        if self.asteroid_timer <= 0:
            self._spawn_lunar_rock(scroll_speed)
            self.asteroid_timer = (self.ASTEROID_INTERVAL * 0.85) / speed_factor
        for a in self.asteroids:
            a.update(dt)

        # Terrain sol — spawn basé sur la position Y (pas de timer)
        for t in self.terrain_tiles:
            t.update(dt, scroll_speed)

        alive_tiles = [t for t in self.terrain_tiles if t.alive and not t.node.isEmpty()]
        max_tile_y = max((t.node.getY() for t in alive_tiles), default=0)
        # Spawn quand le bord avant de la dernière dalle arrive à SPAWN_DEPTH
        # → nouvelle dalle exactement un TILE_DEPTH devant la dernière, zéro overlap
        if max_tile_y < self.SPAWN_DEPTH - self.TILE_DEPTH / 2:
            new_y = max_tile_y + self.TILE_DEPTH
            self.terrain_tiles.append(
                LunarTerrain(self.game.render, 0, new_y, depth=self.TILE_DEPTH))

        # Débris rocheux légers
        self.debris_timer -= dt
        if self.debris_timer <= 0:
            self._spawn_debris(scroll_speed)
            self.debris_timer = (self.DEBRIS_INTERVAL * 1.4) + random.uniform(-1, 1)
        for d in self.debris:
            d.update(dt)

    def _update_l3(self, dt, scroll_speed):
        """L3 — Tranchée : murs + sol + surface Death Star continus."""
        # Update
        for w in self.wall_panels:
            w.update(dt, scroll_speed)
        for f in self.floor_panels:
            f.update(dt, scroll_speed)
        for s in self.surface_panels:
            s.update(dt, scroll_speed)
        for dg in self.decor_groups:
            dg.update(dt, scroll_speed)

        # Spawn : ajoute une rangée quand le dernier panneau se rapproche trop
        alive_walls = [w for w in self.wall_panels if w.alive and not w.node.isEmpty()]
        if alive_walls:
            max_wall_y = max(w.node.getY() for w in alive_walls)
        else:
            max_wall_y = 0
        # Spawn quand le bord avant du dernier panneau arrive à SPAWN_DEPTH
        # → nouveau panneau exactement un TILE_DEPTH devant, zéro overlap, zéro Z-fighting
        if max_wall_y < self.SPAWN_DEPTH - self.TILE_DEPTH / 2:
            self._spawn_trench_row(max_wall_y + self.TILE_DEPTH)

        # Débris métalliques rares
        self.debris_timer -= dt
        if self.debris_timer <= 0:
            self._spawn_debris(scroll_speed)
            self.debris_timer = (self.DEBRIS_INTERVAL * 2.0) + random.uniform(-1, 1)
        for d in self.debris:
            d.update(dt)

    def _update_l4(self, dt, scroll_speed):
        """L4 — Nébuleuse : astéroïdes + nuages denses."""
        speed_factor = scroll_speed / 20.0

        self.asteroid_timer -= dt
        if self.asteroid_timer <= 0:
            self._spawn_asteroid(scroll_speed * 0.9)
            self.asteroid_timer = (self.ASTEROID_INTERVAL * 0.7) / speed_factor
        for a in self.asteroids:
            a.update(dt)

        self.nebula_timer -= dt
        if self.nebula_timer <= 0:
            # Nébuleuses plus fréquentes et plus grandes en L4
            self._spawn_nebula(scale=2.0)
            self.nebula_timer = (self.NEBULA_INTERVAL * 0.5) + random.uniform(-3, 3)
        for n in self.nebulae:
            n.update(dt)

        self.debris_timer -= dt
        if self.debris_timer <= 0:
            self._spawn_debris(scroll_speed)
            self.debris_timer = self.DEBRIS_INTERVAL + random.uniform(-1, 1)
        for d in self.debris:
            d.update(dt)

    # ----------------------------------------------------------
    # Collisions
    # ----------------------------------------------------------

    def check_player_collision(self, player_pos):
        """Vérifie collision avec décor. Retourne les dégâts."""
        damage = 0
        for asteroid in self.asteroids:
            if not asteroid.alive:
                continue
            apos = asteroid.get_pos()
            if apos is None:
                continue
            dist = (apos - player_pos).length()
            if dist < asteroid.hit_radius + 1.0:
                damage += 2
                asteroid.destroy()

        for d in self.debris:
            if not d.alive:
                continue
            dpos = d.get_pos()
            if dpos is None:
                continue
            dist = (dpos - player_pos).length()
            if dist < d.hit_radius + 0.8:
                damage += 1
                d.destroy()

        return damage

    # ----------------------------------------------------------
    # Spawners
    # ----------------------------------------------------------

    def _spawn_asteroid(self, scroll_speed):
        x = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
        z = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)
        y = self.SPAWN_DEPTH + random.uniform(0, 50)
        size = random.uniform(0.8, 3.0)
        speed = scroll_speed * random.uniform(0.8, 1.2)
        self.asteroids.append(Asteroid(self.game.render, Point3(x, y, z), size, speed))

    def _spawn_lunar_rock(self, scroll_speed):
        """Rocher lunaire — gris, moins haut que les astéroïdes."""
        x = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
        z = random.uniform(-7.0, 5.0)   # Plus proche du sol lunaire
        y = self.SPAWN_DEPTH + random.uniform(0, 50)
        size = random.uniform(0.5, 2.2)
        speed = scroll_speed * random.uniform(0.85, 1.15)
        self.asteroids.append(LunarRock(self.game.render, Point3(x, y, z), size, speed))

    def _spawn_fixed_planets(self):
        p1 = DistantPlanet(
            self.game.render, Point3(-20, 150, 12),
            size=18, color=Vec4(0.6, 0.35, 0.2, 1),
        )
        self.planets.append(p1)
        p2 = DistantPlanet(
            self.game.render, Point3(25, 200, -8),
            size=12, color=Vec4(0.25, 0.4, 0.65, 1),
        )
        self.planets.append(p2)

    def _spawn_nebula(self, scale=1.0):
        x = random.uniform(-60, 60)
        z = random.uniform(-40, 40)
        y = self.SPAWN_DEPTH + random.uniform(200, 500)
        color = random.choice(self.nebula_colors)
        size = random.uniform(15, 30) * scale
        self.nebulae.append(Nebula(self.game.render, Point3(x, y, z), color, size))

    def _spawn_debris(self, scroll_speed):
        x = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
        z = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)
        y = self.SPAWN_DEPTH + random.uniform(0, 30)
        size = random.uniform(0.2, 0.6)
        speed = scroll_speed * random.uniform(1.0, 1.5)
        self.debris.append(Asteroid(self.game.render, Point3(x, y, z), size, speed))
