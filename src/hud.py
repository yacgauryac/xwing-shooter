"""
HUD v4 — Overlay PNG + barres en bas + score en haut.
Barres sous les lignes de l'interface, style futuriste gras.
"""

from direct.gui.OnscreenText import OnscreenText
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui.DirectGui import DirectFrame
from panda3d.core import (
    TextNode, Vec4, TransparencyAttrib,
    ColorBlendAttrib,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomLines, GeomNode,
    NodePath
)
import math
import os


C_ORANGE = Vec4(0.9, 0.55, 0.15, 1.0)
C_BRIGHT = Vec4(1.0, 0.7, 0.2, 1.0)
C_DANGER = Vec4(1.0, 0.2, 0.05, 1.0)
C_WARN = Vec4(1.0, 0.5, 0.1, 1.0)
C_BAR_BG = Vec4(0.1, 0.06, 0.02, 0.4)

OVERLAY_PATH = "assets/hud_overlay.png"


def _make_rect(parent, x, z, w, h, color):
    fmt = GeomVertexFormat.getV3c4()
    vd = GeomVertexData("r", fmt, Geom.UHStatic)
    v = GeomVertexWriter(vd, "vertex")
    c = GeomVertexWriter(vd, "color")
    v.addData3(x, 0, z); c.addData4(color)
    v.addData3(x+w, 0, z); c.addData4(color)
    v.addData3(x+w, 0, z+h); c.addData4(color)
    v.addData3(x, 0, z+h); c.addData4(color)
    tris = GeomTriangles(Geom.UHStatic)
    tris.addVertices(0, 1, 2)
    tris.addVertices(0, 2, 3)
    g = Geom(vd)
    g.addPrimitive(tris)
    n = GeomNode("rect")
    n.addGeom(g)
    np = NodePath(n)
    np.reparentTo(parent)
    np.setTransparency(TransparencyAttrib.MAlpha)
    return np


def _make_rect_outline(parent, x, z, w, h, color):
    fmt = GeomVertexFormat.getV3c4()
    vd = GeomVertexData("o", fmt, Geom.UHStatic)
    v = GeomVertexWriter(vd, "vertex")
    c = GeomVertexWriter(vd, "color")
    for px, pz in [(x,z),(x+w,z),(x+w,z+h),(x,z+h),(x,z)]:
        v.addData3(px, 0, pz); c.addData4(color)
    lines = GeomLines(Geom.UHStatic)
    for i in range(4):
        lines.addVertices(i, i+1)
    g = Geom(vd)
    g.addPrimitive(lines)
    n = GeomNode("outline")
    n.addGeom(g)
    np = NodePath(n)
    np.reparentTo(parent)
    np.setRenderModeThickness(1.0)
    np.setTransparency(TransparencyAttrib.MAlpha)
    return np


def _make_bar(parent, x, z, width, height, segments=12):
    bar = {"segments": segments, "seg_nodes": []}
    gap = 0.003
    seg_w = (width - (segments + 1) * gap) / segments

    # Fond sombre arrondi (un seul rect)
    _make_rect(parent, x - 0.006, z - 0.004, width + 0.012, height + 0.008,
               Vec4(0.08, 0.05, 0.02, 0.4))
    # Contour fin
    _make_rect_outline(parent, x - 0.006, z - 0.004, width + 0.012, height + 0.008,
                       Vec4(1, 0.55, 0.1, 0.2))

    for i in range(segments):
        sx = x + gap + i * (seg_w + gap)
        seg = _make_rect(parent, sx, z, seg_w, height, C_ORANGE)
        bar["seg_nodes"].append(seg)
    return bar


def _update_bar(bar, pct, color=C_ORANGE):
    filled = int(pct * bar["segments"])
    for i, seg in enumerate(bar["seg_nodes"]):
        if i < filled:
            seg.show()
            seg.setColorScale(color)
        else:
            seg.hide()


class HUD:
    def __init__(self, game):
        self.game = game
        self.blink_timer = 0.0

        # ===== OVERLAY =====
        if os.path.exists(OVERLAY_PATH):
            self.overlay = OnscreenImage(
                image=OVERLAY_PATH, pos=(0, 0, 0),
                scale=(1.78, 1, 1.0),
            )
            self.overlay.setTransparency(TransparencyAttrib.MAlpha)
            self.overlay.setAttrib(ColorBlendAttrib.make(
                ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne,
            ))
            self.overlay.setBin("fixed", 40)
            self.overlay.setDepthTest(False)
            self.overlay.setDepthWrite(False)
            # Transparence sur l'overlay
            self.overlay.setColorScale(0.45, 0.45, 0.45, 0.45)
        else:
            self.overlay = None

        # ===== SCORE (haut centre, gros) =====
        self.score_text = OnscreenText(
            text="0", pos=(0, 0.78), scale=0.07,
            fg=C_BRIGHT, align=TextNode.ACenter,
            mayChange=True, sort=50,
            shadow=(0, 0, 0, 0.8),  # Faux gras via shadow
        )

        # ===== WAVE (haut gauche) =====
        self.wave_label = OnscreenText(
            text="WAVE", pos=(-1.2, 0.90), scale=0.028,
            fg=Vec4(0.9, 0.55, 0.15, 0.7), align=TextNode.ALeft,
            mayChange=False, sort=50,
        )
        self.wave_text = OnscreenText(
            text="1", pos=(-1.05, 0.90), scale=0.04,
            fg=C_BRIGHT, align=TextNode.ALeft,
            mayChange=True, sort=50,
            shadow=(0, 0, 0, 0.8),
        )

        # ===== HOSTILES (haut droit) =====
        self.hostiles_label = OnscreenText(
            text="HOSTILES", pos=(1.2, 0.90), scale=0.028,
            fg=Vec4(0.9, 0.55, 0.15, 0.7), align=TextNode.ARight,
            mayChange=False, sort=50,
        )
        self.hostiles_text = OnscreenText(
            text="0", pos=(1.05, 0.90), scale=0.04,
            fg=C_DANGER, align=TextNode.ARight,
            mayChange=True, sort=50,
            shadow=(0, 0, 0, 0.8),
        )

        # ===== BARRES EN BAS (sous la ligne inférieure de l'overlay) =====
        self.bar_root = game.aspect2d.attachNewNode("bars")
        self.bar_root.setTransparency(TransparencyAttrib.MAlpha)
        self.bar_root.setBin("fixed", 45)

        # Shield — bas gauche, ENTRE les lignes du cadre
        self.shield_label = OnscreenText(
            text="SHIELD", pos=(-0.75, -0.90), scale=0.025,
            fg=Vec4(0.9, 0.55, 0.15, 0.7), align=TextNode.ALeft,
            mayChange=False, sort=50,
        )
        self.shield_bar = _make_bar(self.bar_root, -0.75, -0.95, 0.5, 0.025, segments=12)

        # Laser Energy — bas droit, label en haut à droite de la barre
        self.laser_label = OnscreenText(
            text="LASER", pos=(0.76, -0.90), scale=0.025,
            fg=Vec4(0.9, 0.55, 0.15, 0.7), align=TextNode.ARight,
            mayChange=False, sort=50,
        )
        self.heat_bar = _make_bar(self.bar_root, 0.25, -0.95, 0.5, 0.025, segments=12)
        self.overheat_text = OnscreenText(
            text="", pos=(0.50, -0.90), scale=0.022,
            fg=C_DANGER, align=TextNode.ACenter, mayChange=True, sort=50,
        )

        # Torpedo counter — bas centre
        self.torpedo_label = OnscreenText(
            text="TORPEDOES", pos=(0, -0.88), scale=0.025,
            fg=Vec4(0.9, 0.55, 0.15, 0.8), align=TextNode.ACenter,
            mayChange=False, sort=50,
        )
        self.torpedo_count_text = OnscreenText(
            text="3", pos=(0, -0.94), scale=0.04,
            fg=C_BRIGHT, align=TextNode.ACenter, mayChange=True, sort=50,
            shadow=(0, 0, 0, 0.8),
        )

        # ===== ANNONCE / FLASH / GAME OVER =====
        self.wave_announce = OnscreenText(
            text="", pos=(0, 0.35), scale=0.06,
            fg=C_BRIGHT, align=TextNode.ACenter, mayChange=True, sort=50,
            shadow=(0, 0, 0, 0.5),
        )
        self.announce_timer = 0.0

        self.damage_flash = DirectFrame(
            frameColor=Vec4(1, 0.3, 0, 0),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=100,
        )
        self.flash_timer = 0.0

        self.game_over_text = OnscreenText(
            text="", pos=(0, 0.08), scale=0.1,
            fg=C_DANGER, align=TextNode.ACenter, mayChange=True, sort=50,
            shadow=(0, 0, 0, 0.8),
        )
        self.game_over_sub = OnscreenText(
            text="", pos=(0, -0.05), scale=0.035,
            fg=C_ORANGE, align=TextNode.ACenter, mayChange=True, sort=50,
        )

        # Attitude
        self.attitude_root = game.aspect2d.attachNewNode("attitude")
        self.attitude_root.setTransparency(TransparencyAttrib.MAlpha)
        self.attitude_lines = None

        # Pickup feedback
        self.pickup_text = OnscreenText(
            text="", pos=(0, -0.15), scale=0.04,
            fg=Vec4(1, 1, 1, 1), align=TextNode.ACenter,
            mayChange=True, sort=50, shadow=(0, 0, 0, 0.6),
        )
        self.pickup_timer = 0.0

    def update(self, dt, score, wave, enemy_count, health, max_health,
               heat_pct=0.0, overheated=False, cooldown_pct=0.0,
               roll=0.0, pitch=0.0, torpedo_count=0):
        self.blink_timer += dt

        # Score
        self.score_text.setText(f"{score:,}".replace(",", " "))

        # Torpilles
        self.torpedo_count_text.setText(f"{torpedo_count}")

        # Wave + hostiles
        self.wave_text.setText(f"{wave}")
        self.hostiles_text.setText(f"{enemy_count}")

        # Shield
        hp = max(0, health / max_health)
        if hp > 0.5:
            bar_c = C_ORANGE
        elif hp > 0.25:
            bar_c = C_WARN
        else:
            bar_c = C_DANGER
        _update_bar(self.shield_bar, hp, bar_c)

        # Laser energy
        disp = cooldown_pct if overheated else heat_pct
        energy = 1.0 - disp
        if overheated:
            blink = abs(math.sin(self.blink_timer * 6))
            self.overheat_text.setText("OVERHEAT")
            self.overheat_text.setFg(Vec4(1, 0.15, 0.05, 0.5 + 0.5 * blink))
            _update_bar(self.heat_bar, energy, C_DANGER)
        else:
            self.overheat_text.setText("")
            _update_bar(self.heat_bar, energy, C_ORANGE)

        # Attitude
        self._update_attitude(roll, pitch)

        # Annonce
        if self.announce_timer > 0:
            self.announce_timer -= dt
            a = min(1.0, self.announce_timer / 0.5)
            self.wave_announce.setFg(Vec4(C_BRIGHT.getX(), C_BRIGHT.getY(), C_BRIGHT.getZ(), a))
            if self.announce_timer <= 0:
                self.wave_announce.setText("")

        # Flash
        if self.flash_timer > 0:
            self.flash_timer -= dt
            a = max(0, self.flash_timer / 0.3) * 0.2
            self.damage_flash["frameColor"] = Vec4(1, 0.4, 0, a)
            if self.flash_timer <= 0:
                self.damage_flash["frameColor"] = Vec4(1, 0.4, 0, 0)

        # Pickup text fade
        if self.pickup_timer > 0:
            self.pickup_timer -= dt
            progress = self.pickup_timer / 1.5
            self.pickup_text.setFg(Vec4(1, 1, 1, progress))
            self.pickup_text.setScale(0.04 + (1.0 - progress) * 0.005)
            if self.pickup_timer <= 0:
                self.pickup_text.setText("")

    def _update_attitude(self, roll, pitch):
        if self.attitude_lines:
            self.attitude_lines.removeNode()

        fmt = GeomVertexFormat.getV3c4()
        vd = GeomVertexData("att", fmt, Geom.UHDynamic)
        v = GeomVertexWriter(vd, "vertex")
        c = GeomVertexWriter(vd, "color")

        roll_rad = math.radians(roll * 0.015)
        p_off = pitch * 0.003
        col = Vec4(1, 0.55, 0.1, 0.12)
        col_c = Vec4(1, 0.55, 0.1, 0.2)
        cos_r, sin_r = math.cos(roll_rad), math.sin(roll_rad)

        h = 0.08
        v.addData3(-h*cos_r, 0, -h*sin_r+p_off); c.addData4(col_c)
        v.addData3(h*cos_r, 0, h*sin_r+p_off); c.addData4(col_c)

        for off in [0.18, 0.3]:
            for side in [-1, 1]:
                x1, x2 = side*off, side*(off+0.05)
                z1 = x1*sin_r/cos_r+p_off if cos_r != 0 else p_off
                z2 = x2*sin_r/cos_r+p_off if cos_r != 0 else p_off
                v.addData3(x1, 0, z1); c.addData4(col)
                v.addData3(x2, 0, z2); c.addData4(col)

        lines = GeomLines(Geom.UHDynamic)
        for i in range(5):
            lines.addVertices(i*2, i*2+1)
        g = Geom(vd)
        g.addPrimitive(lines)
        n = GeomNode("att")
        n.addGeom(g)
        self.attitude_lines = NodePath(n)
        self.attitude_lines.reparentTo(self.attitude_root)
        self.attitude_lines.setRenderModeThickness(1.0)

    def announce_wave(self, wave_num):
        self.wave_announce.setText(f"WAVE {wave_num} INCOMING")
        self.announce_timer = 2.5

    def show_damage_flash(self):
        self.flash_timer = 0.3

    def show_pickup(self, text):
        """Affiche un texte de pickup qui fade."""
        self.pickup_text.setText(text)
        self.pickup_text.setFg(Vec4(1, 1, 1, 1))
        self.pickup_text.setScale(0.05)
        self.pickup_timer = 1.5

    def show_game_over(self, score):
        self.game_over_text.setText("DESTROYED")
        self.game_over_sub.setText(f"Final score: {score:,}".replace(",", " "))

    # =========================================
    # LEADERBOARD SCREENS
    # =========================================

    def show_name_entry(self):
        """Affiche l'écran de saisie du nom (frappe clavier)."""
        self._clear_leaderboard()
        self.name_entry_active = True
        self.typed_name = ""

        # Fond sombre
        self.lb_bg = DirectFrame(
            frameColor=Vec4(0, 0, 0, 0.7),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=55,
        )

        self.lb_title = OnscreenText(
            text="NEW HIGH SCORE!", pos=(0, 0.55), scale=0.07,
            fg=C_BRIGHT, align=TextNode.ACenter, mayChange=False, sort=60,
            shadow=(0, 0, 0, 0.8),
        )
        self.lb_subtitle = OnscreenText(
            text="ENTER YOUR NAME", pos=(0, 0.45), scale=0.035,
            fg=C_ORANGE, align=TextNode.ACenter, mayChange=False, sort=60,
        )

        self.name_display = OnscreenText(
            text="___", pos=(0, 0.30), scale=0.09,
            fg=C_BRIGHT, align=TextNode.ACenter, mayChange=True, sort=60,
            shadow=(0, 0, 0, 0.8),
        )

        self.lb_controls = OnscreenText(
            text="TYPE 3 LETTERS  |  BACKSPACE TO DELETE  |  ENTER TO VALIDATE",
            pos=(0, 0.18), scale=0.022,
            fg=Vec4(0.9, 0.55, 0.15, 0.6), align=TextNode.ACenter,
            mayChange=False, sort=60,
        )

    def update_name_entry(self, key):
        """Gère la frappe clavier pour le nom."""
        if not hasattr(self, 'name_entry_active') or not self.name_entry_active:
            return False

        if key == "backspace":
            self.typed_name = self.typed_name[:-1]
        elif key == "enter":
            if len(self.typed_name) > 0:
                self.name_entry_active = False
                return self.typed_name[:3].upper()
        elif len(key) == 1 and key.isalpha() and len(self.typed_name) < 3:
            self.typed_name += key.upper()

        # Affiche avec des underscores pour les places vides
        display = self.typed_name + "_" * (3 - len(self.typed_name))
        if hasattr(self, 'name_display'):
            self.name_display.setText(display)

        return False

    def _update_name_display(self):
        pass  # Plus utilisé avec la frappe clavier

    def show_leaderboard(self, entries, highlight_rank=None):
        """Affiche le tableau des scores."""
        self._clear_leaderboard()
        self.leaderboard_active = True

        # Fond sombre
        self.lb_bg = DirectFrame(
            frameColor=Vec4(0, 0, 0, 0.7),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=55,
        )

        self.lb_elements = []

        title = OnscreenText(
            text="TOP PILOTS", pos=(0, 0.65), scale=0.06,
            fg=C_BRIGHT, align=TextNode.ACenter, mayChange=False, sort=60,
            shadow=(0, 0, 0, 0.8),
        )
        self.lb_elements.append(title)

        # En-tête
        header = OnscreenText(
            text="  #   NAME   SCORE    WAVE  KILLS   DATE",
            pos=(0, 0.55), scale=0.025,
            fg=Vec4(0.9, 0.55, 0.15, 0.6), align=TextNode.ACenter,
            mayChange=False, sort=60,
        )
        self.lb_elements.append(header)

        # Lignes
        for i, entry in enumerate(entries[:10]):
            rank = i + 1
            name = entry.get("name", "???")
            score = entry.get("score", 0)
            wave = entry.get("wave", 0)
            kills = entry.get("kills", 0)
            date = entry.get("date", "")

            line = f" {rank:>2}.   {name}   {score:>6}     {wave:>2}     {kills:>3}   {date}"

            is_highlight = (highlight_rank is not None and rank == highlight_rank)
            fg = C_BRIGHT if is_highlight else C_ORANGE

            t = OnscreenText(
                text=line, pos=(0, 0.48 - i * 0.07), scale=0.028,
                fg=fg, align=TextNode.ACenter, mayChange=False, sort=60,
            )
            self.lb_elements.append(t)

        restart = OnscreenText(
            text="PRESS R TO PLAY AGAIN", pos=(0, -0.35), scale=0.03,
            fg=Vec4(0.9, 0.55, 0.15, 0.6), align=TextNode.ACenter,
            mayChange=False, sort=60,
        )
        self.lb_elements.append(restart)

    def _clear_leaderboard(self):
        """Nettoie les éléments du leaderboard."""
        if hasattr(self, 'lb_bg') and self.lb_bg:
            self.lb_bg.destroy()
            self.lb_bg = None
        for attr in ['lb_title', 'lb_subtitle', 'lb_controls']:
            if hasattr(self, attr):
                getattr(self, attr).destroy()
                delattr(self, attr)
        if hasattr(self, 'name_texts'):
            for t in self.name_texts:
                t.destroy()
            del self.name_texts
        if hasattr(self, 'name_display'):
            self.name_display.destroy()
            del self.name_display
        if hasattr(self, 'lb_elements'):
            for e in self.lb_elements:
                e.destroy()
            del self.lb_elements
        self.name_entry_active = False
        self.leaderboard_active = False
