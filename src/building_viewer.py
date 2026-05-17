"""
Building Viewer — Outil de test des bâtiments procéduraux + .glb.
Lancer : python viewer.py [fichier.glb]

Caméra orbit style Blender :
  LMB + drag   → orbite (azimut / élévation)
  Molette      → zoom
  RMB + drag   → pan

Contrôles :
  Tab / Shift-Tab   → bâtiment suivant / précédent
  +  /  -           → scale ×1.2 / ÷1.2
  R                 → reset caméra + scale
  H                 → toggle hitbox (wireframe orange)
  G                 → toggle grille
  O                 → charger un .glb (saisir le chemin dans la console)
  Q / Escape        → quitter
"""

import sys
import math
import random
import os

from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomLines, GeomNode,
    NodePath, TransparencyAttrib, WindowProperties,
    AmbientLight, DirectionalLight,
    AntialiasAttrib, TextNode,
)
from direct.gui.OnscreenText import OnscreenText

from src.lunar_base import (
    _make_tower, _make_hangar, _make_silo, _make_bunker,
    _make_antenna_mast, _make_landing_pad, _make_relay_tower,
)

# ─────────────────────────────────────────────────────────────
# Catalogue des bâtiments procéduraux
# Valeurs médianes — reproductibles (seed fixe)
# ─────────────────────────────────────────────────────────────

_PROC_CATALOG = [
    ("Tower",    "tower",    {"hw": 0.55, "hd": 0.55, "h": 12.0}),
    ("Hangar",   "hangar",   {"hw": 3.50, "hd": 4.00, "h":  6.0}),
    ("Silo",     "silo",     {"hw": 0.95, "hd": 0.95, "h":  9.0}),
    ("Bunker",   "bunker",   {"hw": 2.50, "hd": 2.50, "h":  4.5}),
    ("Antenna",  "antenna",  {"hw": 0.10, "hd": 0.10, "h": 14.0}),
    ("Pad",      "pad",      {"hw": 3.50, "hd": 3.50, "h":  0.3}),
    ("Relay",    "relay",    {"hw": 0.55, "hd": 0.55, "h": 10.0}),
]


def _build_proc(type_name, hw, hd, h):
    """Génère le mesh procédural (seed fixe → aspect stable)."""
    rng = random.Random(42)
    makers = {
        "tower":    lambda: _make_tower(hw, hd, h, rng),
        "hangar":   lambda: _make_hangar(hw, hd, h, rng),
        "silo":     lambda: _make_silo(hw, h, rng),
        "bunker":   lambda: _make_bunker(hw, hd, h, rng),
        "antenna":  lambda: _make_antenna_mast(hw, h, rng),
        "pad":      lambda: _make_landing_pad(hw, rng),
        "relay":    lambda: _make_relay_tower(hw, h, rng),
    }
    return makers[type_name]()


# ─────────────────────────────────────────────────────────────

class BuildingViewer(ShowBase):

    _CAM_AZIM  = 40.0
    _CAM_ELEV  = 22.0
    _CAM_R     = 18.0

    def __init__(self, glb_path=None):
        ShowBase.__init__(self)
        self.disableMouse()

        # ── Fenêtre ──────────────────────────────────────────────────────────
        props = WindowProperties()
        props.setTitle("Building Viewer — X-Wing Shooter")
        props.setFullscreen(True)
        props.setSize(1920, 1080)
        self.win.requestProperties(props)
        self.setBackgroundColor(0.07, 0.07, 0.09, 1.0)
        self.render.setAntialias(AntialiasAttrib.MAuto)

        # ── Caméra orbit ─────────────────────────────────────────────────────
        self._azim   = self._CAM_AZIM
        self._elev   = self._CAM_ELEV
        self._radius = self._CAM_R
        self._pivot  = Point3(0, 0, 0)

        # ── Souris ───────────────────────────────────────────────────────────
        self._mx = None
        self._my = None
        self._lmb = False
        self._rmb = False

        # ── État bâtiment ────────────────────────────────────────────────────
        self._glb_path   = glb_path
        self._idx        = 0
        self._scale      = 1.0
        self._bld        = None    # NodePath bâtiment
        self._hb         = None    # NodePath hitbox
        self._hb_dims    = None    # (hw, hd, h)
        self._show_hb    = True
        self._show_grid  = True

        # ── Scène ────────────────────────────────────────────────────────────
        self._setup_lighting()
        self._grid_np = self._make_grid()
        self._make_axes()

        if glb_path:
            self._load_glb(glb_path)
        else:
            self._spawn()

        # ── UI ───────────────────────────────────────────────────────────────
        C_HEAD  = (1.00, 0.75, 0.20, 1.0)
        C_INFO  = (0.70, 0.70, 0.70, 1.0)
        C_HELP  = (0.45, 0.45, 0.45, 1.0)

        self._t_title = self._txt("", (-1.25,  0.90), 0.058, C_HEAD)
        self._t_dims  = self._txt("", (-1.25,  0.81), 0.033, C_INFO)
        self._t_hb    = self._txt("", (-1.25,  0.74), 0.030, (1.0, 0.55, 0.1, 1.0))
        self._txt(
            "1-7 / Tab/Shift-Tab = bâtiment   +/- = scale   R = reset   "
            "H = hitbox   G = grille   O = charger .glb   Q = quitter",
            (-1.25, -0.93), 0.026, C_HELP,
        )
        # Liste bâtiments à droite
        for i, (name, _, _p) in enumerate(_PROC_CATALOG):
            self._txt(f"{i+1}. {name}", (1.00, 0.90 - i * 0.085), 0.032, C_HELP)

        self._refresh_ui()

        # ── Bindings ─────────────────────────────────────────────────────────
        self.accept("tab",        self._next)
        self.accept("shift-tab",  self._prev)
        self.accept("+",          self._su)
        self.accept("=",          self._su)
        self.accept("-",          self._sd)
        self.accept("r",          self._reset_cam)
        self.accept("h",          self._toggle_hb)
        self.accept("g",          self._toggle_grid)
        self.accept("o",          self._prompt_glb)
        self.accept("q",          sys.exit)
        self.accept("escape",     sys.exit)
        # Touches numériques → accès direct au bâtiment
        for i in range(len(_PROC_CATALOG)):
            self.accept(str(i + 1), self._jump_to, [i])
        self.accept("wheel_up",   self._zoom_in)
        self.accept("wheel_down", self._zoom_out)
        self.accept("mouse1",      lambda: setattr(self, "_lmb", True))
        self.accept("mouse1-up",   lambda: setattr(self, "_lmb", False))
        self.accept("mouse3",      lambda: setattr(self, "_rmb", True))
        self.accept("mouse3-up",   lambda: setattr(self, "_rmb", False))

        self.taskMgr.add(self._orbit_task, "orbit")
        self._apply_cam()

    # ─────────────────────────────────────────────────────────────
    # Scène
    # ─────────────────────────────────────────────────────────────

    def _setup_lighting(self):
        al = AmbientLight("amb")
        al.setColor(Vec4(0.50, 0.52, 0.58, 1))
        self.render.setLight(self.render.attachNewNode(al))

        dl = DirectionalLight("sun")
        dl.setColor(Vec4(0.88, 0.82, 0.75, 1))
        dn = self.render.attachNewNode(dl)
        dn.setHpr(35, -55, 0)
        self.render.setLight(dn)

        dl2 = DirectionalLight("fill")
        dl2.setColor(Vec4(0.18, 0.22, 0.32, 1))
        dn2 = self.render.attachNewNode(dl2)
        dn2.setHpr(-140, -30, 0)
        self.render.setLight(dn2)

    def _make_grid(self):
        """Grille ±20u, sous-grille 2u (grise), couloirs 4u (orange)."""
        fmt   = GeomVertexFormat.getV3c4()
        vd    = GeomVertexData("grid", fmt, Geom.UHStatic)
        vw    = GeomVertexWriter(vd, "vertex")
        cw    = GeomVertexWriter(vd, "color")
        lines = GeomLines(Geom.UHStatic)
        idx   = [0]

        HALF = 20
        STEP = 2
        CORR = 4
        C_M  = Vec4(0.18, 0.18, 0.22, 0.55)   # sous-grille
        C_C  = Vec4(0.48, 0.42, 0.22, 0.80)   # couloirs

        def ln(x0, y0, x1, y1, c):
            vw.addData3(x0, y0, 0); cw.addData4(c)
            vw.addData3(x1, y1, 0); cw.addData4(c)
            lines.addVertices(idx[0], idx[0]+1); idx[0] += 2

        for x in range(-HALF, HALF+1, STEP):
            ln(x, -HALF, x, HALF, C_C if x % CORR == 0 else C_M)
        for y in range(-HALF, HALF+1, STEP):
            ln(-HALF, y, HALF, y, C_C if y % CORR == 0 else C_M)

        geom = Geom(vd); geom.addPrimitive(lines)
        gn   = GeomNode("grid"); gn.addGeom(geom)
        np   = self.render.attachNewNode(gn)
        np.setRenderModeThickness(1.0)
        np.setTransparency(TransparencyAttrib.MAlpha)
        np.setLightOff()
        np.setDepthWrite(False)
        return np

    def _make_axes(self):
        """3 axes X/Y/Z colorés."""
        fmt   = GeomVertexFormat.getV3c4()
        vd    = GeomVertexData("ax", fmt, Geom.UHStatic)
        vw    = GeomVertexWriter(vd, "vertex")
        cw    = GeomVertexWriter(vd, "color")
        lines = GeomLines(Geom.UHStatic)

        axes = [
            ((0,0,0),(4,0,0),(1.0, 0.2, 0.2, 1.0)),  # X rouge
            ((0,0,0),(0,4,0),(0.2, 1.0, 0.2, 1.0)),  # Y vert
            ((0,0,0),(0,0,4),(0.2, 0.5, 1.0, 1.0)),  # Z bleu
        ]
        for i, (p0, p1, c) in enumerate(axes):
            vw.addData3(*p0); cw.addData4(*c)
            vw.addData3(*p1); cw.addData4(*c)
            lines.addVertices(i*2, i*2+1)

        geom = Geom(vd); geom.addPrimitive(lines)
        gn   = GeomNode("axes"); gn.addGeom(geom)
        np   = self.render.attachNewNode(gn)
        np.setRenderModeThickness(2.5)
        np.setLightOff()

    def _make_aabb_wire(self, hw, hd, h):
        """12 arêtes AABB orange : ±hw/±hd en XY, 0→h en Z."""
        fmt   = GeomVertexFormat.getV3c4()
        vd    = GeomVertexData("hb", fmt, Geom.UHStatic)
        vw    = GeomVertexWriter(vd, "vertex")
        cw    = GeomVertexWriter(vd, "color")
        lines = GeomLines(Geom.UHStatic)
        col   = Vec4(0.0, 0.95, 0.85, 0.90)

        corners = [
            (-hw, -hd, 0), ( hw, -hd, 0), ( hw,  hd, 0), (-hw,  hd, 0),
            (-hw, -hd, h), ( hw, -hd, h), ( hw,  hd, h), (-hw,  hd, h),
        ]
        for cx, cy, cz in corners:
            vw.addData3(cx, cy, cz); cw.addData4(col)

        edges = [
            (0,1),(1,2),(2,3),(3,0),   # base
            (4,5),(5,6),(6,7),(7,4),   # top
            (0,4),(1,5),(2,6),(3,7),   # montants
        ]
        for a, b in edges:
            lines.addVertices(a, b)

        geom = Geom(vd); geom.addPrimitive(lines)
        gn   = GeomNode("aabb"); gn.addGeom(geom)
        np   = self.render.attachNewNode(gn)
        np.setRenderModeThickness(1.8)
        np.setLightOff()
        np.setDepthWrite(False)
        return np

    # ─────────────────────────────────────────────────────────────
    # Bâtiment courant
    # ─────────────────────────────────────────────────────────────

    def _clear(self):
        if self._bld and not self._bld.isEmpty():
            self._bld.removeNode()
        self._bld = None
        if self._hb and not self._hb.isEmpty():
            self._hb.removeNode()
        self._hb = None
        self._hb_dims = None

    def _spawn(self):
        """Génère le bâtiment procédural courant."""
        self._clear()
        name, type_name, params = _PROC_CATALOG[self._idx]
        hw = params["hw"] * self._scale
        hd = params["hd"] * self._scale
        h  = params["h"]  * self._scale

        mesh = _build_proc(type_name, hw, hd, h)
        mesh.reparentTo(self.render)
        mesh.setPos(0, 0, h / 2)   # bottom at Z=0
        self._bld     = mesh
        self._hb_dims = (hw, hd, h)
        self._pivot   = Point3(0, 0, h / 2)
        self._rebuild_hb()

    def _rebuild_hb(self):
        if self._hb and not self._hb.isEmpty():
            self._hb.removeNode()
        self._hb = None
        if not self._hb_dims:
            return
        hw, hd, h = self._hb_dims
        self._hb = self._make_aabb_wire(hw, hd, h)
        if not self._show_hb:
            self._hb.hide()

    def _load_glb(self, path):
        """Charge un fichier .glb/.gltf, auto-scale, affiche hitbox sur bounds."""
        self._clear()
        path = path.strip().strip('"')
        if not os.path.exists(path):
            print(f"[Viewer] Fichier introuvable : {path}")
            return
        try:
            model = self.loader.loadModel(path)
        except Exception as e:
            print(f"[Viewer] Erreur chargement : {e}")
            return
        if not model:
            print(f"[Viewer] Échec : {path}")
            return

        # Auto-scale pour tenir dans ~10 unités
        bounds = model.getTightBounds()
        if bounds:
            bmin, bmax = bounds
            size = bmax - bmin
            maxd = max(size.getX(), size.getY(), size.getZ())
            if maxd > 0:
                sc = 10.0 / maxd * self._scale
                model.setScale(sc)
                # Re-centre en X/Y, pose sur Z=0
                model.setPos(
                    -(bmin.getX() + bmax.getX()) / 2 * sc,
                    -(bmin.getY() + bmax.getY()) / 2 * sc,
                    -bmin.getZ() * sc,
                )

        model.reparentTo(self.render)

        # Calcule AABB après positionnement
        b2 = model.getTightBounds()
        if b2:
            mn, mx = b2
            hw = (mx.getX() - mn.getX()) / 2
            hd = (mx.getY() - mn.getY()) / 2
            h  =  mx.getZ() - mn.getZ()
            self._hb_dims = (hw, hd, h)
            self._pivot   = Point3(0, 0, h / 2)
            self._radius  = max(8.0, h * 2.0 + max(hw, hd) * 3.0)

        self._bld      = model
        self._glb_path = path
        self._rebuild_hb()
        self._apply_cam()
        self._refresh_ui()
        print(f"[Viewer] Chargé : {path}")

    # ─────────────────────────────────────────────────────────────
    # Caméra orbit
    # ─────────────────────────────────────────────────────────────

    def _apply_cam(self):
        az = math.radians(self._azim)
        el = math.radians(self._elev)
        cx =  self._radius * math.cos(el) * math.sin(az)
        cy = -self._radius * math.cos(el) * math.cos(az)
        cz =  self._radius * math.sin(el)
        self.camera.setPos(self._pivot + Vec3(cx, cy, cz))
        self.camera.lookAt(self._pivot)

    def _orbit_task(self, task):
        mw = self.mouseWatcherNode
        if mw.hasMouse():
            mx, my = mw.getMouseX(), mw.getMouseY()
            if self._mx is not None:
                dx = mx - self._mx
                dy = my - self._my
                if self._lmb:   # orbite
                    self._azim -= dx * 120.0
                    self._elev  = max(-85.0, min(85.0, self._elev + dy * 80.0))
                    self._apply_cam()
                elif self._rmb:  # pan
                    right = self.camera.getRelativeVector(self.render, Vec3(1, 0, 0))
                    up    = self.camera.getRelativeVector(self.render, Vec3(0, 0, 1))
                    self._pivot -= right * dx * self._radius * 0.8
                    self._pivot += up    * dy * self._radius * 0.8
                    self._apply_cam()
            self._mx, self._my = mx, my
        else:
            self._mx = self._my = None
        return task.cont

    def _zoom_in(self):
        self._radius = max(1.5, self._radius * 0.85)
        self._apply_cam()

    def _zoom_out(self):
        self._radius = min(150.0, self._radius * 1.18)
        self._apply_cam()

    def _reset_cam(self):
        self._azim  = self._CAM_AZIM
        self._elev  = self._CAM_ELEV
        if self._hb_dims:
            hw, hd, h = self._hb_dims
            self._pivot  = Point3(0, 0, h / 2)
            self._radius = max(8.0, h * 2.0 + max(hw, hd) * 3.0)
        else:
            self._pivot  = Point3(0, 0, 0)
            self._radius = self._CAM_R
        self._apply_cam()

    # ─────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────

    def _jump_to(self, idx):
        """Saute directement au bâtiment n°idx du catalogue."""
        self._idx      = idx % len(_PROC_CATALOG)
        self._scale    = 1.0
        self._glb_path = None
        self._spawn()
        self._reset_cam()
        self._refresh_ui()

    def _next(self):
        self._idx   = (self._idx + 1) % len(_PROC_CATALOG)
        self._scale = 1.0
        self._glb_path = None
        self._spawn()
        self._reset_cam()
        self._refresh_ui()

    def _prev(self):
        self._idx   = (self._idx - 1) % len(_PROC_CATALOG)
        self._scale = 1.0
        self._glb_path = None
        self._spawn()
        self._reset_cam()
        self._refresh_ui()

    def _su(self):
        self._scale *= 1.2
        if self._glb_path:
            if self._bld: self._bld.setScale(self._bld.getScale() * 1.2)
        else:
            self._spawn()
        self._refresh_ui()

    def _sd(self):
        self._scale /= 1.2
        if self._glb_path:
            if self._bld: self._bld.setScale(self._bld.getScale() / 1.2)
        else:
            self._spawn()
        self._refresh_ui()

    def _toggle_hb(self):
        self._show_hb = not self._show_hb
        if self._hb:
            self._hb.show() if self._show_hb else self._hb.hide()
        self._refresh_ui()

    def _toggle_grid(self):
        self._show_grid = not self._show_grid
        self._grid_np.show() if self._show_grid else self._grid_np.hide()

    def _prompt_glb(self):
        path = input("Chemin .glb / .gltf : ").strip()
        if path:
            self._load_glb(path)

    # ─────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────

    def _txt(self, text, pos, scale, fg):
        return OnscreenText(
            text=text, pos=pos, scale=scale,
            fg=fg, align=TextNode.ALeft,
            mayChange=True, sort=50,
        )

    def _refresh_ui(self):
        if self._glb_path:
            self._t_title.setText(f"[GLB]  {os.path.basename(self._glb_path)}")
            if self._hb_dims:
                hw, hd, h = self._hb_dims
                self._t_dims.setText(
                    f"  bounds  X ±{hw:.2f}   Y ±{hd:.2f}   Z {h:.2f}   scale ×{self._scale:.2f}"
                )
        else:
            name, _, params = _PROC_CATALOG[self._idx]
            hw = params["hw"] * self._scale
            hd = params["hd"] * self._scale
            h  = params["h"]  * self._scale
            self._t_title.setText(
                f"[{self._idx+1}/{len(_PROC_CATALOG)}]  {name}"
            )
            self._t_dims.setText(
                f"  hw {hw:.2f}   hd {hd:.2f}   h {h:.2f}   scale ×{self._scale:.2f}"
            )
        hb_str = "■ hitbox ON" if self._show_hb else "□ hitbox OFF"
        self._t_hb.setText(f"  {hb_str}")
