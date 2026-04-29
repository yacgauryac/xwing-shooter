"""
Explosions V2 — Flash + onde de choc + fireballs + étincelles + débris sombres.
3 presets : small (TIE Fighter) / medium (torpille / TIE Bomber) / large (boss).
Palette stricte : jamais de bleu/vert/violet — que du chaud.

Géométrie entièrement procédurale — pas de CardMaker (évite les rectangles visibles) :
  - Flash / fireballs  → disques avec gradient alpha centre→bord
  - Onde de choc       → anneau (3 cercles concentriques, alpha pic au milieu)
  - Étincelles         → GeomPoints
  - Débris             → triangles colorés
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    ColorBlendAttrib, TransparencyAttrib,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomPoints, GeomTriangles, GeomNode,
    NodePath, TextNode,
)
from direct.gui.OnscreenText import OnscreenText
import random
import math


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

PRESETS = {
    "small": {
        "flash_size":   1.2,
        "shock_max_r":  2.5,
        "fb_count":     2,
        "fb_size":      0.6,
        "sparks":       20,
        "duration":     0.5,
        "debris_count": 5,
    },
    "medium": {
        "flash_size":   2.0,
        "shock_max_r":  4.0,
        "fb_count":     3,
        "fb_size":      1.1,
        "sparks":       30,
        "duration":     0.7,
        "debris_count": 6,
    },
    "large": {
        "flash_size":   3.5,
        "shock_max_r":  6.0,
        "fb_count":     5,
        "fb_size":      2.0,
        "sparks":       45,
        "duration":     1.2,
        "debris_count": 8,
    },
}

# Couleurs fireballs — palette chaude uniquement
_FB_COLORS = [
    (2.8, 1.4, 0.15),   # Orange vif
    (2.2, 0.9, 0.05),   # Orange moyen
    (1.5, 0.5, 0.0),    # Orange brûlé / rouge
]

# Blend additif standard : src*alpha + dst
_ADDBLEND = ColorBlendAttrib.make(
    ColorBlendAttrib.M_add,
    ColorBlendAttrib.O_incoming_alpha,
    ColorBlendAttrib.O_one,
)


# ---------------------------------------------------------------------------
# Helpers géométrie circulaire
# ---------------------------------------------------------------------------

def _make_disc(game, radius, segments=18, sort=50):
    """
    Disque billboard avec gradient alpha 1.0 (centre) → 0.0 (bord).
    Utiliser setColorScale(r, g, b, 1.0) pour teinter + animer.
    """
    fmt   = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData("disc", fmt, Geom.UHStatic)
    vdata.setNumRows(1 + segments)
    vtx = GeomVertexWriter(vdata, "vertex")
    col = GeomVertexWriter(vdata, "color")

    # Centre : alpha plein
    vtx.addData3(0, 0, 0)
    col.addData4(1.0, 1.0, 1.0, 1.0)

    # Bord : alpha zéro (bord invisible)
    for i in range(segments):
        a = 2 * math.pi * i / segments
        vtx.addData3(math.cos(a) * radius, 0, math.sin(a) * radius)
        col.addData4(1.0, 1.0, 1.0, 0.0)

    tris = GeomTriangles(Geom.UHStatic)
    for i in range(segments):
        tris.addVertices(0, 1 + i, 1 + (i + 1) % segments)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("disc")
    node.addGeom(geom)

    np = NodePath(node)
    np.reparentTo(game.render)
    np.setBillboardPointEye()
    np.setLightOff()
    np.setDepthWrite(False)
    np.setTransparency(TransparencyAttrib.MAlpha)
    np.setAttrib(_ADDBLEND)
    np.setBin("fixed", sort)
    return np


def _make_ring(game, max_radius, segments=24, sort=49):
    """
    Anneau billboard : 3 cercles concentriques (in 60% / mid 80% / out 100%).
    Gradient alpha : 0→1→0 (bord interne et externe invisibles, pic au milieu).
    L'anneau est créé à max_radius=1.0 — utiliser setScale(r,1,r) pour expanser.
    """
    n   = segments
    fmt = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData("ring", fmt, Geom.UHStatic)
    vdata.setNumRows(n * 3)
    vtx = GeomVertexWriter(vdata, "vertex")
    col = GeomVertexWriter(vdata, "color")

    rings = [
        (0.55, 0.0),    # Interne : transparent
        (0.80, 1.0),    # Milieu  : opaque (pic de luminosité)
        (1.00, 0.0),    # Externe : transparent
    ]
    for r_frac, alpha in rings:
        for i in range(n):
            a = 2 * math.pi * i / n
            vtx.addData3(math.cos(a) * r_frac, 0, math.sin(a) * r_frac)
            col.addData4(1.0, 1.0, 1.0, alpha)

    tris = GeomTriangles(Geom.UHStatic)
    for ring_idx in range(2):   # 0: in→mid, 1: mid→out
        base_a = ring_idx * n
        base_b = (ring_idx + 1) * n
        for i in range(n):
            ni = (i + 1) % n
            tris.addVertices(base_a + i,  base_b + i,  base_b + ni)
            tris.addVertices(base_a + i,  base_b + ni, base_a + ni)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode("ring")
    node.addGeom(geom)

    np = NodePath(node)
    np.reparentTo(game.render)
    np.setBillboardPointEye()
    np.setLightOff()
    np.setDepthWrite(False)
    np.setTransparency(TransparencyAttrib.MAlpha)
    np.setAttrib(_ADDBLEND)
    np.setBin("fixed", sort)
    # Taille initiale minimale
    np.setScale(0.3, 1, 0.3)
    return np


# ---------------------------------------------------------------------------
# DebrisChunk (conservé, légèrement assombri)
# ---------------------------------------------------------------------------

class DebrisChunk:
    """Morceau de vaisseau sombre qui se disperse puis fade."""

    def __init__(self, game, position):
        self.alive        = True
        self.lifetime     = random.uniform(0.4, 0.8)
        self.max_lifetime = self.lifetime

        speed = random.uniform(6, 18)
        theta = random.uniform(0, math.pi * 2)
        phi   = random.uniform(0, math.pi)
        self.velocity = Vec3(
            math.sin(phi) * math.cos(theta) * speed,
            math.sin(phi) * math.sin(theta) * speed,
            math.cos(phi) * speed,
        )
        self.rot_speed = Vec3(
            random.uniform(-150, 150),
            random.uniform(-150, 150),
            random.uniform(-150, 150),
        )
        self.node = self._make_chunk()
        self.node.reparentTo(game.render)
        self.node.setPos(position)
        self.node.setLightOff()

    def _make_chunk(self):
        fmt   = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("chunk", fmt, Geom.UHStatic)
        vtx   = GeomVertexWriter(vdata, "vertex")
        col   = GeomVertexWriter(vdata, "color")

        ctype = random.randint(0, 2)
        gray  = random.uniform(0.08, 0.18)
        c1    = Vec4(gray,       gray,       gray * 0.9, 1)
        c2    = Vec4(gray * 1.3, gray * 1.2, gray,       1)
        tris  = GeomTriangles(Geom.UHStatic)

        if ctype == 0:
            w = random.uniform(0.2, 0.5)
            h = random.uniform(0.3, 0.7)
            vtx.addData3(-w, 0, -h); col.addData4(c1)
            vtx.addData3( w, 0, -h); col.addData4(c1)
            vtx.addData3( w, 0,  h); col.addData4(c2)
            vtx.addData3(-w, 0,  h); col.addData4(c2)
            tris.addVertices(0, 1, 2); tris.addVertices(0, 2, 3)
        elif ctype == 1:
            s = random.uniform(0.2, 0.4)
            vtx.addData3(-s, 0, -s*2); col.addData4(c1)
            vtx.addData3( s, 0, -s*2); col.addData4(c1)
            vtx.addData3( s, 0,  0);   col.addData4(c2)
            vtx.addData3(-s, 0,  0);   col.addData4(c2)
            vtx.addData3(-s, 0,  0);   col.addData4(c2)
            vtx.addData3( 0, 0,  0);   col.addData4(c2)
            vtx.addData3( 0, 0,  s);   col.addData4(c1)
            vtx.addData3(-s, 0,  s);   col.addData4(c1)
            tris.addVertices(0, 1, 2); tris.addVertices(0, 2, 3)
            tris.addVertices(4, 5, 6); tris.addVertices(4, 6, 7)
        else:
            s = random.uniform(0.15, 0.4)
            vtx.addData3(-s,     0, -s*0.6); col.addData4(c1)
            vtx.addData3( s*1.2, 0, -s*0.2); col.addData4(c2)
            vtx.addData3( s*0.3, 0,  s*0.8); col.addData4(c1)
            tris.addVertices(0, 1, 2)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        n = GeomNode("chunk")
        n.addGeom(geom)
        return NodePath(n)

    def update(self, dt):
        if not self.alive:
            return
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.destroy(); return

        self.node.setPos(self.node.getPos() + self.velocity * dt)
        self.velocity.setZ(self.velocity.getZ() - 2.0 * dt)
        self.velocity *= max(0.0, 1.0 - 1.5 * dt)

        h, p, r = self.node.getHpr()
        self.node.setHpr(
            h + self.rot_speed.getX() * dt,
            p + self.rot_speed.getY() * dt,
            r + self.rot_speed.getZ() * dt,
        )
        # Fade sur les 30% finaux de vie
        pct   = self.lifetime / self.max_lifetime
        alpha = min(1.0, pct / 0.3)
        self.node.setColorScale(1, 1, 1, alpha)

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


# ---------------------------------------------------------------------------
# Explosion principale
# ---------------------------------------------------------------------------

class Explosion:
    """
    Explosion multi-composants avec preset.
    Tous les éléments lumineux sont des disques/anneaux procéduraux (pas de quads).
    """

    SHOCK_DURATION = 0.25
    FLASH_DURATION = 0.10
    SPARK_DURATION = 0.40

    def __init__(self, game, position, preset="small"):
        self.game     = game
        self.alive    = True
        self.timer    = 0.0
        self.position = Vec3(position)

        cfg = PRESETS.get(preset, PRESETS["small"])
        self.duration       = cfg["duration"]
        self._flash_size    = cfg["flash_size"]
        self._shock_max_r   = cfg["shock_max_r"]
        self._fb_count      = cfg["fb_count"]
        self._fb_size       = cfg["fb_size"]
        self._sparks_count  = cfg["sparks"]
        self._debris_count  = cfg["debris_count"]

        self._fireballs  = []
        self._debris     = []
        self._particles  = []
        self._vdata      = None
        self._spark_node = None
        self._shockwave  = None
        self._shock_timer = 0.0

        self._make_flash()
        self._make_shockwave()
        self._make_fireballs()
        self._make_sparks()
        self._make_debris()

    # ------------------------------------------------------------------
    # A. Flash initial — disque blanc chaud
    # ------------------------------------------------------------------

    def _make_flash(self):
        disc = _make_disc(self.game, 1.0, segments=16, sort=51)
        disc.setPos(self.position)
        disc.setScale(self._flash_size, 1, self._flash_size)
        disc.setColorScale(4.0, 3.5, 2.5, 1.0)   # Blanc très chaud
        self._fireballs.append({
            "node":     disc,
            "life":     self.FLASH_DURATION,
            "max_life": self.FLASH_DURATION,
            "type":     "flash",
            "base_scl": self._flash_size,
        })

    # ------------------------------------------------------------------
    # B. Onde de choc — anneau qui s'expanse
    # ------------------------------------------------------------------

    def _make_shockwave(self):
        ring = _make_ring(self.game, 1.0, segments=24, sort=49)
        ring.setPos(self.position)
        ring.setColorScale(1.3, 1.1, 0.8, 1.0)   # Gris chaud
        self._shockwave   = ring
        self._shock_timer = self.SHOCK_DURATION

    # ------------------------------------------------------------------
    # C. Boules de feu — disques oranges
    # ------------------------------------------------------------------

    def _make_fireballs(self):
        for _ in range(self._fb_count):
            base_scl = self._fb_size * random.uniform(0.7, 1.3)
            disc = _make_disc(self.game, 1.0, segments=14, sort=50)
            offset = Vec3(
                random.uniform(-self._fb_size * 0.8, self._fb_size * 0.8),
                random.uniform(-self._fb_size * 0.8, self._fb_size * 0.8),
                random.uniform(-self._fb_size * 0.5, self._fb_size * 0.5),
            )
            disc.setPos(self.position + offset)
            disc.setScale(base_scl, 1, base_scl)

            r, g, b = random.choice(_FB_COLORS)
            disc.setColorScale(r, g, b, 1.0)

            speed = random.uniform(2, 5)
            theta = random.uniform(0, math.pi * 2)
            phi   = random.uniform(0.2, math.pi - 0.2)
            vel   = Vec3(
                math.sin(phi) * math.cos(theta) * speed,
                math.sin(phi) * math.sin(theta) * speed,
                math.cos(phi) * speed,
            )
            life = random.uniform(self.duration * 0.5, self.duration)
            self._fireballs.append({
                "node":     disc,
                "life":     life,
                "max_life": life,
                "vel":      vel,
                "base_scl": base_scl,
                "r": r, "g": g, "b": b,
                "type":     "fire",
            })

    # ------------------------------------------------------------------
    # D. Étincelles (GeomPoints)
    # ------------------------------------------------------------------

    def _make_sparks(self):
        n = self._sparks_count

        class Spark:
            __slots__ = ("pos", "vel", "life", "max_life", "alive")

        for _ in range(n):
            sp    = Spark()
            speed = random.uniform(20, 45)
            theta = random.uniform(0, math.pi * 2)
            phi   = random.uniform(0, math.pi)
            sp.vel = Vec3(
                math.sin(phi) * math.cos(theta) * speed,
                math.sin(phi) * math.sin(theta) * speed,
                math.cos(phi) * speed,
            )
            sp.pos      = Vec3(self.position)
            sp.life     = random.uniform(0.15, self.SPARK_DURATION)
            sp.max_life = sp.life
            sp.alive    = True
            self._particles.append(sp)

        fmt  = GeomVertexFormat.getV3c4()
        self._vdata = GeomVertexData("sparks", fmt, Geom.UHDynamic)
        self._vdata.setNumRows(n)
        vtx = GeomVertexWriter(self._vdata, "vertex")
        col = GeomVertexWriter(self._vdata, "color")
        for sp in self._particles:
            vtx.addData3(sp.pos)
            col.addData4(1.0, 0.8, 0.1, 1.0)

        pts   = GeomPoints(Geom.UHDynamic)
        pts.addConsecutiveVertices(0, n)
        geom  = Geom(self._vdata)
        geom.addPrimitive(pts)
        gn    = GeomNode("sparks_geom")
        gn.addGeom(geom)
        inner = NodePath(gn)
        inner.setRenderModeThickness(2)

        self._spark_node = NodePath("sparks")
        self._spark_node.reparentTo(self.game.render)
        self._spark_node.setLightOff()
        inner.reparentTo(self._spark_node)

    # ------------------------------------------------------------------
    # E. Débris
    # ------------------------------------------------------------------

    def _make_debris(self):
        for _ in range(self._debris_count):
            self._debris.append(DebrisChunk(self.game, self.position))

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt):
        if not self.alive:
            return
        self.timer += dt

        # A/C — Flash + fireballs
        for fb in self._fireballs:
            fb["life"] -= dt
            if fb["life"] <= 0:
                if not fb["node"].isEmpty():
                    fb["node"].removeNode()
                continue

            progress = 1.0 - (fb["life"] / fb["max_life"])   # 0→1

            if fb["type"] == "flash":
                # Fade quadratique rapide — le disque rétrécit légèrement
                fade  = (1.0 - progress) ** 2
                scale = fb["base_scl"] * (1.0 + progress * 0.3)   # Légère expansion
                fb["node"].setScale(scale, 1, scale)
                fb["node"].setColorScale(4.0 * fade, 3.5 * fade, 2.5 * fade, 1.0)

            else:  # fire
                # Phase expansion (0→40%) : grossit × 1.5
                # Phase fade    (40→100%) : fade out
                if progress < 0.4:
                    t     = progress / 0.4
                    scale = fb["base_scl"] * (1.0 + t * 0.5)
                    fb["node"].setScale(scale, 1, scale)
                else:
                    t     = (progress - 0.4) / 0.6
                    scale = fb["base_scl"] * (1.5 - t * 1.0)
                    fade  = max(0.0, (1.0 - t) ** 1.5)
                    fb["node"].setScale(max(0.01, scale), 1, max(0.01, scale))
                    fb["node"].setColorScale(
                        fb["r"] * fade, fb["g"] * fade, fb["b"] * fade, 1.0
                    )

                # Déplacement + résistance air
                if "vel" in fb:
                    pos = fb["node"].getPos()
                    fb["node"].setPos(pos + fb["vel"] * dt)
                    fb["vel"] *= max(0.0, 1.0 - 2.0 * dt)

        self._fireballs = [fb for fb in self._fireballs if fb["life"] > 0]

        # B — Onde de choc
        if self._shockwave is not None and not self._shockwave.isEmpty():
            self._shock_timer -= dt
            if self._shock_timer <= 0:
                self._shockwave.removeNode()
                self._shockwave = None
            else:
                t      = 1.0 - (self._shock_timer / self.SHOCK_DURATION)   # 0→1
                r      = 0.3 + t * self._shock_max_r
                alpha  = (1.0 - t) ** 0.6   # Fade assez vite
                self._shockwave.setScale(r, 1, r)
                self._shockwave.setColorScale(1.3, 1.1, 0.8, alpha)

        # D — Étincelles
        spark_alive = False
        if self._vdata is not None:
            vtx = GeomVertexWriter(self._vdata, "vertex")
            col = GeomVertexWriter(self._vdata, "color")
            for sp in self._particles:
                if not sp.alive:
                    vtx.addData3(0, 0, 0); col.addData4(0, 0, 0, 0)
                    continue
                sp.life -= dt
                if sp.life <= 0:
                    sp.alive = False
                    vtx.addData3(0, 0, 0); col.addData4(0, 0, 0, 0)
                    continue
                spark_alive = True
                sp.pos += sp.vel * dt
                sp.vel *= max(0.0, 1.0 - 4.0 * dt)
                progress = 1.0 - (sp.life / sp.max_life)
                alpha  = (1.0 - progress) ** 0.5
                green  = 0.8 * (1.0 - progress * 0.8)   # Jaune → orange
                vtx.addData3(sp.pos)
                col.addData4(1.0, green, 0.05, alpha)

        # E — Débris
        for chunk in self._debris:
            chunk.update(dt)
        self._debris = [d for d in self._debris if d.alive]

        # Fin
        if (not self._fireballs and
                not spark_alive and
                not self._debris and
                self._shockwave is None):
            self.destroy()

    # ------------------------------------------------------------------

    def destroy(self):
        self.alive = False
        for fb in self._fireballs:
            if not fb["node"].isEmpty():
                fb["node"].removeNode()
        self._fireballs = []
        if self._shockwave is not None and not self._shockwave.isEmpty():
            self._shockwave.removeNode()
            self._shockwave = None
        if self._spark_node is not None and not self._spark_node.isEmpty():
            self._spark_node.removeNode()
            self._spark_node = None
        for d in self._debris:
            d.destroy()
        self._debris = []


# ---------------------------------------------------------------------------
# ScorePopup
# ---------------------------------------------------------------------------

class ScorePopup:
    """Points +100 qui montent et fade."""

    def __init__(self, game, position, score):
        self.alive    = True
        self.timer    = 0.0
        self.duration = 1.0
        self.game     = game

        pos2d = self._world_to_screen(position)
        self.text = OnscreenText(
            text=f"+{score}", pos=pos2d, scale=0.05,
            fg=Vec4(1.0, 0.7, 0.2, 1.0),
            align=TextNode.ACenter, mayChange=True, sort=60,
        )
        self.start_y = pos2d[1]

    def _world_to_screen(self, world_pos):
        p3 = self.game.cam.getRelativePoint(self.game.render, world_pos)
        if p3.getY() <= 0:
            return (0, 0)
        p2d = Point3()
        if self.game.camLens.project(p3, p2d):
            return (p2d.getX(), p2d.getY())
        return (0, 0)

    def update(self, dt):
        if not self.alive:
            return
        self.timer += dt
        progress = self.timer / self.duration
        if progress >= 1.0:
            self.destroy(); return
        self.text.setPos(self.text.getPos()[0], self.start_y + progress * 0.15)
        self.text.setFg(Vec4(1.0, 0.7, 0.2, 1.0 - progress))
        self.text.setScale(0.05 + progress * 0.01)

    def destroy(self):
        self.alive = False
        self.text.destroy()


# ---------------------------------------------------------------------------
# ExplosionManager
# ---------------------------------------------------------------------------

class ExplosionManager:
    def __init__(self, game):
        self.game       = game
        self.explosions = []
        self.popups     = []

    def spawn(self, position, preset="small", score=0):
        """
        Crée une explosion au preset donné.
        preset : "small" | "medium" | "large"
        """
        self.explosions.append(Explosion(self.game, position, preset=preset))
        if score > 0:
            self.popups.append(ScorePopup(self.game, position, score))

    def update(self, dt):
        for exp in self.explosions:
            exp.update(dt)
        self.explosions = [e for e in self.explosions if e.alive]
        for p in self.popups:
            p.update(dt)
        self.popups = [p for p in self.popups if p.alive]
