"""
Lasers — Système de tir avec surchauffe/cooldown.
Tir en paires alternées, surchauffe après trop de tirs, cooldown avec timer rotatif.
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath, TransparencyAttrib, ColorBlendAttrib,
)
import math


class BoltTrailRing:
    """
    Onde circulaire laissée dans le monde au passage d'un bolt — style Matrix.
    La balle est passée, l'onde se propage et s'efface.
    """

    MAX_R    = 0.38   # rayon max (u)
    LIFETIME = 0.18   # secondes
    N_SEGS   = 14
    INNER    = 0.62   # fraction inner — anneau fin
    # Blanc orangé chaud, accord avec le noyau des bolts
    COLOR    = Vec4(1.0, 0.88, 0.65, 1.0)

    def __init__(self, parent, pos):
        self.alive = True
        self.timer = self.LIFETIME
        self._node = self._build(parent, pos)

    def _build(self, parent, pos):
        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("tr", fmt, Geom.UHStatic)
        vw    = GeomVertexWriter(vdata, "vertex")
        cw    = GeomVertexWriter(vdata, "color")
        tris  = GeomTriangles(Geom.UHStatic)

        ri   = self.INNER
        c_in  = Vec4(self.COLOR.x, self.COLOR.y, self.COLOR.z, 0.0)
        c_out = Vec4(self.COLOR.x, self.COLOR.y, self.COLOR.z, 0.9)

        for i in range(self.N_SEGS):
            a0   = 2 * math.pi * i       / self.N_SEGS
            a1   = 2 * math.pi * (i + 1) / self.N_SEGS
            base = i * 4
            # Plan XZ — perpendiculaire à la direction du bolt (Y)
            vw.addData3(ri*math.cos(a0), 0, ri*math.sin(a0)); cw.addData4(c_in)
            vw.addData3(ri*math.cos(a1), 0, ri*math.sin(a1)); cw.addData4(c_in)
            vw.addData3(   math.cos(a0), 0,    math.sin(a0)); cw.addData4(c_out)
            vw.addData3(   math.cos(a1), 0,    math.sin(a1)); cw.addData4(c_out)
            tris.addVertices(base, base+2, base+3)
            tris.addVertices(base, base+3, base+1)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        gn = GeomNode("trail_ring")
        gn.addGeom(geom)
        np = NodePath(gn)
        np.reparentTo(parent)
        np.setPos(pos)
        np.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd))
        np.setDepthWrite(False)
        np.setTwoSided(True)
        np.setLightOff()
        np.setBin("transparent", 15)
        return np

    def update(self, dt):
        if not self.alive:
            return
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False
            if not self._node.isEmpty():
                self._node.removeNode()
            return
        t = 1.0 - self.timer / self.LIFETIME   # 0 (jeune) → 1 (vieux)
        r = max(0.001, self.MAX_R * t)
        alpha = 1.0 - t * t                    # fade doux
        self._node.setScale(r)
        self._node.setAlphaScale(alpha)

    def destroy(self):
        self.alive = False
        if not self._node.isEmpty():
            self._node.removeNode()


class LaserBolt:
    """Un seul tir laser."""

    SPEED = 115.0
    MAX_DISTANCE = 380.0
    DAMAGE = 1

    TRAIL_INTERVAL = 2.2   # u entre chaque ring de traînée

    def __init__(self, parent_node, start_pos, direction, color_back=None,
                 color_front=None):
        self.alive = True
        self.distance_traveled = 0.0
        self.direction = direction
        self._parent_node  = parent_node
        self._trail_rings  = []
        self._trail_dist   = 0.0

        if color_back is None:
            color_back = Vec4(1.0, 0.2, 0.0, 1)
        if color_front is None:
            color_front = Vec4(1.0, 0.7, 0.4, 1)

        self.node = self.make_bolt(color_back, color_front)
        self.node.reparentTo(parent_node)
        self.node.setPos(start_pos)
        self.node.lookAt(start_pos + direction)
        self.node.setLightOff()

    def make_bolt(self, color_back, color_front):
        root = NodePath("bolt_root")

        fmt = GeomVertexFormat.getV3c4()

        # --- Noyau blanc (fin, brillant) ---
        vdata1 = GeomVertexData("core", fmt, Geom.UHStatic)
        v1 = GeomVertexWriter(vdata1, "vertex")
        c1 = GeomVertexWriter(vdata1, "color")

        hx, hy, hz = 0.06, 1.4, 0.06
        core_back = Vec4(0.9, 0.8, 0.7, 1)
        core_front = Vec4(1.0, 1.0, 1.0, 1)

        corners = [
            (-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz),
            (-hx,  hy, -hz), (hx,  hy, -hz), (hx,  hy, hz), (-hx,  hy, hz),
        ]
        for i, corner in enumerate(corners):
            v1.addData3(*corner)
            c1.addData4(core_back if i < 4 else core_front)

        tris1 = GeomTriangles(Geom.UHStatic)
        for f in [
            (0,1,2),(0,2,3),(4,6,5),(4,7,6),
            (0,4,5),(0,5,1),(2,6,7),(2,7,3),
            (0,3,7),(0,7,4),(1,5,6),(1,6,2),
        ]:
            tris1.addVertices(*f)

        geom1 = Geom(vdata1)
        geom1.addPrimitive(tris1)
        node1 = GeomNode("bolt_core")
        node1.addGeom(geom1)
        NodePath(node1).reparentTo(root)

        # --- Halo coloré — 2 quads croisés avec dégradé alpha center→edge ---
        # Chaque quad : colonne gauche alpha=0, colonne centre alpha=max, colonne droite alpha=0
        # Quad 1 dans le plan XY (fade en X), Quad 2 dans le plan ZY (fade en Z)
        gx, gy = 0.22, 1.65
        r, g, b = color_back.getX(), color_back.getY(), color_back.getZ()
        rf, gf, bf = color_front.getX(), color_front.getY(), color_front.getZ()

        c_edge_b  = Vec4(r,  g,  b,  0.0)   # bord arrière  — transparent
        c_mid_b   = Vec4(r,  g,  b,  0.55)  # centre arrière — opaque
        c_edge_f  = Vec4(rf, gf, bf, 0.0)   # bord avant    — transparent
        c_mid_f   = Vec4(rf, gf, bf, 0.65)  # centre avant  — opaque

        vdata2 = GeomVertexData("glow", fmt, Geom.UHStatic)
        v2 = GeomVertexWriter(vdata2, "vertex")
        c2 = GeomVertexWriter(vdata2, "color")

        def add_cross_quad(ax, az):
            """Quad avec 3 colonnes : (-a,0), (0,0), (+a,0) en XZ."""
            # 6 sommets : back-left, back-center, back-right, front-left, front-center, front-right
            v2.addData3(-ax, -gy, -az); c2.addData4(c_edge_b)   # 0
            v2.addData3(  0, -gy,   0); c2.addData4(c_mid_b)    # 1
            v2.addData3( ax, -gy,  az); c2.addData4(c_edge_b)   # 2
            v2.addData3(-ax,  gy, -az); c2.addData4(c_edge_f)   # 3
            v2.addData3(  0,  gy,   0); c2.addData4(c_mid_f)    # 4
            v2.addData3( ax,  gy,  az); c2.addData4(c_edge_f)   # 5

        add_cross_quad(gx, 0)    # Quad 1 : fade en X
        add_cross_quad(0, gx)    # Quad 2 : fade en Z

        tris2 = GeomTriangles(Geom.UHStatic)
        for base in [0, 6]:      # un bloc de 6 sommets par quad
            b0 = base
            # Triangle gauche-centre (back→front)
            tris2.addVertices(b0+0, b0+1, b0+4)
            tris2.addVertices(b0+0, b0+4, b0+3)
            # Triangle centre-droit (back→front)
            tris2.addVertices(b0+1, b0+2, b0+5)
            tris2.addVertices(b0+1, b0+5, b0+4)

        geom2 = Geom(vdata2)
        geom2.addPrimitive(tris2)
        node2 = GeomNode("bolt_glow")
        node2.addGeom(geom2)
        glow_np = NodePath(node2)
        glow_np.reparentTo(root)
        glow_np.setTransparency(TransparencyAttrib.MAlpha)
        glow_np.setTwoSided(True)

        return root

    def update(self, dt):
        if not self.alive:
            return
        move = self.SPEED * dt
        self.node.setPos(self.node.getPos() + self.direction * move)
        self.distance_traveled += move

        # Spawn un ring dans le monde à chaque TRAIL_INTERVAL u parcourus
        self._trail_dist += move
        if self._trail_dist >= self.TRAIL_INTERVAL:
            self._trail_dist -= self.TRAIL_INTERVAL
            self._trail_rings.append(
                BoltTrailRing(self._parent_node, self.node.getPos())
            )

        for ring in self._trail_rings:
            ring.update(dt)
        self._trail_rings = [r for r in self._trail_rings if r.alive]

        if self.distance_traveled > self.MAX_DISTANCE:
            self.destroy()

    def destroy(self):
        self.alive = False
        for ring in self._trail_rings:
            ring.destroy()
        self._trail_rings = []
        if not self.node.isEmpty():
            self.node.removeNode()


class LaserSystem:
    """Tir par paires alternées avec système de surchauffe."""

    FIRE_RATE = 0.12          # Temps entre chaque paire

    # Surchauffe
    MAX_HEAT = 100.0
    HEAT_PER_SHOT = 7.3       # Surchauffe en ~3.7s de tir continu
    HEAT_DECAY = 25.0         # Refroidissement par seconde (quand on tire pas)
    OVERHEAT_THRESHOLD = 100.0  # Seuil de surchauffe
    COOLDOWN_TIME = 2.5       # Durée du cooldown forcé (secondes)

    # Canons
    CANNON_PAIRS = [
        [Point3( 1.0, 1.0,  0.03), Point3(-1.0, 1.0,  0.03)],
        [Point3( 1.0, 1.0, -0.03), Point3(-1.0, 1.0, -0.03)],
    ]

    AUTO_AIM_RANGE_FAR = 200.0      # Utilisé par les torpilles uniquement

    def __init__(self, game):
        self.game = game
        self.bolts = []
        self.fire_timer = 0.0
        self.pair_index = 0
        self.firing = False
        self.enemies_ref = None

        # Surchauffe
        self.heat = 0.0
        self.overheated = False
        self.cooldown_timer = 0.0
        self.cooldown_total = self.COOLDOWN_TIME

        game.accept("mouse1", self.start_fire)
        game.accept("mouse1-up", self.stop_fire)
        game.accept("space", self.start_fire)
        game.accept("space-up", self.stop_fire)

    def set_enemies(self, spawner):
        self.enemies_ref = spawner

    def start_fire(self):
        self.firing = True

    def stop_fire(self):
        self.firing = False

    def update(self, dt, player_node, force_active=False):
        self.fire_timer -= dt

        # Force active → pas de surchauffe
        if force_active:
            self.heat = max(0, self.heat - self.HEAT_DECAY * 3 * dt)
            self.overheated = False
            self.cooldown_timer = 0

            if self.firing and self.fire_timer <= 0:
                self.fire_pair(player_node, force_active=True)
                self.fire_timer = self.FIRE_RATE * 0.7  # Tir plus rapide
        else:
            # Refroidissement
            if not self.firing or self.overheated:
                self.heat = max(0, self.heat - self.HEAT_DECAY * dt)
            else:
                self.heat = max(0, self.heat - self.HEAT_DECAY * 0.45 * dt)

            # Débloque dès que la chaleur repasse sous 50%
            if self.overheated and self.heat <= self.OVERHEAT_THRESHOLD * 0.50:
                self.overheated = False

            if self.firing and self.fire_timer <= 0 and not self.overheated:
                self.fire_pair(player_node)
                self.fire_timer = self.FIRE_RATE
                self.heat += self.HEAT_PER_SHOT
                if self.heat >= self.OVERHEAT_THRESHOLD:
                    self.overheated = True

        # Update bolts
        for bolt in self.bolts:
            bolt.update(dt)
        self.bolts = [b for b in self.bolts if b.alive]

    def find_nearest_enemy(self, from_pos, max_range=None):
        if not self.enemies_ref:
            return None
        nearest = None
        nearest_dist = max_range if max_range else self.AUTO_AIM_RANGE
        for enemy in self.enemies_ref.enemies:
            if not enemy.alive:
                continue
            epos = enemy.get_pos()
            if epos is None or epos.getY() <= from_pos.getY():
                continue
            dist = (epos - from_pos).length()
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = enemy
        return nearest

    def fire_pair(self, player_node, force_active=False):
        """Tire 2 bolts simultanés depuis la paire de canons active."""
        pair = self.CANNON_PAIRS[self.pair_index]

        # Couleurs alternées
        if self.pair_index == 0:
            c_back = Vec4(1.0, 0.15, 0.0, 1)
            c_front = Vec4(1.0, 0.6, 0.35, 1)
        else:
            c_back = Vec4(1.0, 0.25, 0.0, 1)
            c_front = Vec4(1.0, 0.7, 0.4, 1)

        for offset in pair:
            world_pos = self.game.render.getRelativePoint(player_node, offset)
            base_dir  = Vec3(0, 1, 0)

            bolt = LaserBolt(self.game.render, world_pos, base_dir,
                             color_back=c_back, color_front=c_front)
            if force_active:
                bolt.node.setScale(1.5)
                bolt.node.setColorScale(1.5, 1.5, 1.5, 1)
            self.bolts.append(bolt)

        self.pair_index = (self.pair_index + 1) % len(self.CANNON_PAIRS)

    def get_bolts(self):
        return [b for b in self.bolts if b.alive]

    def get_heat_pct(self):
        """Retourne le % de chaleur (0.0 à 1.0)."""
        return self.heat / self.MAX_HEAT

    def is_overheated(self):
        return self.overheated

    def get_cooldown_pct(self):
        """Retourne le % de cooldown restant (1.0 = début, 0.0 = fini)."""
        if not self.overheated or self.cooldown_total <= 0:
            return 0.0
        return self.cooldown_timer / self.cooldown_total
