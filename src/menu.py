"""
Menu principal — Style inspiré Half-Life 2 / TF2.
Fond image SW + panneau gauche semi-transparent + logo + entrées.
"""

from direct.gui.OnscreenText import OnscreenText
from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenImage import OnscreenImage
from panda3d.core import TextNode, Vec4, TransparencyAttrib, ClockObject
import math
import os

from src.levels import LEVELS

globalClock = ClockObject.getGlobalClock()

# ── Palette ────────────────────────────────────────────────────────────────────
C_TITLE     = Vec4(1.0,  0.85, 0.35, 1.0)   # jaune or
C_BRIGHT    = Vec4(1.0,  0.78, 0.25, 1.0)   # orange clair
C_ORANGE    = Vec4(0.88, 0.55, 0.18, 1.0)   # orange moyen
C_SELECTED  = Vec4(1.0,  0.92, 0.55, 1.0)   # jaune vif sélectionné
C_DIM       = Vec4(0.60, 0.40, 0.15, 0.55)  # dim pour sous-titres
C_LOCKED    = Vec4(0.35, 0.25, 0.10, 0.45)
C_RULE      = Vec4(0.70, 0.45, 0.12, 0.55)  # ligne séparatrice

# ── Dimensions panneau gauche ──────────────────────────────────────────────────
PANEL_LEFT  = -1.78
PANEL_RIGHT = -0.10    # bord droit du panneau semi-transparent
PANEL_TOP   =  1.00
PANEL_BOT   = -1.00

# ── Positions des entrées ──────────────────────────────────────────────────────
ENTRY_X     = -0.95    # alignement gauche des entrées (aspect2d)
ENTRY_START_Y = 0.20   # première entrée
ENTRY_SPACING = 0.115

MENU_BG_PATH    = "assets/menu_bg.jpg"    # image SW fond (optionnel)
MENU_BG_PATH2   = "assets/menu_bg.png"


class MainMenu:
    """Menu principal du jeu — style HL2/TF2."""

    ENTRIES_MAIN = [
        ("SOLO",           "solo"),
        ("CHOISIR NIVEAU", "level_select"),
        ("COOP LAN",       "coop"),
        ("LEADERBOARD",    "leaderboard"),
        ("OPTIONS",        "options"),
        ("QUITTER",        "quit"),
    ]

    ENTRIES_OPTIONS = [
        ("VOLUME SFX  +", "sfx_up"),
        ("VOLUME SFX  -", "sfx_down"),
        ("PLEIN ECRAN",   "fullscreen"),
        ("RETOUR",        "back"),
    ]

    def __init__(self, game):
        self.game = game
        self.active = False
        self.selected = 0
        self.current_menu = "main"
        self.elements = []
        self.timer = 0.0
        self._level_entries = []

        self.title        = None
        self.subtitle     = None
        self.bg           = None
        self.bg_image     = None
        self.panel        = None
        self.separator    = None
        self.entry_texts  = []
        self.controls_text = None

    def show(self):
        self.hide()
        self.active = True
        self.selected = 0
        self.current_menu = "main"

        # ── Fond image SW si disponible ──────────────────────────────
        bg_path = None
        for p in [MENU_BG_PATH, MENU_BG_PATH2]:
            if os.path.exists(p):
                bg_path = p
                break

        if bg_path:
            self.bg_image = OnscreenImage(
                image=bg_path, pos=(0.55, 0, 0),
                scale=(1.78, 1, 1.0), sortOrder=190,
            )
            self.bg_image.setTransparency(TransparencyAttrib.MAlpha)
            # Fondu global pour ne pas écraser le starfield complètement
            self.bg_image.setColorScale(0.55, 0.55, 0.55, 0.90)
        else:
            # Fond noir total si pas d'image
            self.bg_image = None

        # ── Panneau sombre gauche (style HL2 : gradient du bord gauche) ──
        self.bg = DirectFrame(
            frameColor=Vec4(0.0, 0.0, 0.0, 0.82),
            frameSize=(PANEL_LEFT, PANEL_RIGHT, PANEL_BOT, PANEL_TOP),
            pos=(0, 0, 0), sortOrder=195,
        )

        # Liseré vertical droit du panneau
        self.separator = DirectFrame(
            frameColor=C_RULE,
            frameSize=(PANEL_RIGHT - 0.006, PANEL_RIGHT, PANEL_BOT, PANEL_TOP),
            pos=(0, 0, 0), sortOrder=196,
        )

        # ── Logo / Titre (haut gauche) ───────────────────────────────
        self.title = OnscreenText(
            text="X-WING",
            pos=(ENTRY_X, 0.75), scale=0.095,
            fg=C_TITLE, align=TextNode.ALeft, sort=210,
            shadow=(0, 0, 0, 0.9), font=None,
        )
        self.title_sub = OnscreenText(
            text="S H O O T E R",
            pos=(ENTRY_X + 0.01, 0.645), scale=0.036,
            fg=C_BRIGHT, align=TextNode.ALeft, sort=210,
            shadow=(0, 0, 0, 0.7),
        )

        # Ligne séparatrice sous le logo
        self.logo_rule = DirectFrame(
            frameColor=C_RULE,
            frameSize=(PANEL_LEFT + 0.06, PANEL_RIGHT - 0.06, -0.004, 0.004),
            pos=(0, 0, 0.575), sortOrder=210,
        )

        self.subtitle = OnscreenText(
            text="A long time ago in a galaxy far, far away...",
            pos=(ENTRY_X, 0.52), scale=0.024,
            fg=C_DIM, align=TextNode.ALeft, sort=210,
        )

        self._build_entries(self.ENTRIES_MAIN)

        # Contrôles (bas gauche)
        self.controls_text = OnscreenText(
            text="Z/S · Naviguer    ENTRÉE · Sélect    ESC · Retour",
            pos=(ENTRY_X, -0.82), scale=0.020,
            fg=Vec4(0.4, 0.28, 0.10, 0.38), align=TextNode.ALeft, sort=210,
        )

        # Version (tout en bas gauche)
        self.version_text = OnscreenText(
            text="v2.0  —  Build 2026",
            pos=(PANEL_LEFT + 0.07, -0.90), scale=0.018,
            fg=Vec4(0.3, 0.22, 0.08, 0.30), align=TextNode.ALeft, sort=210,
        )

        # Bindings
        self.game.accept("arrow_up",    self._nav_up)
        self.game.accept("arrow_down",  self._nav_down)
        self.game.accept("z-repeat",    self._nav_up)
        self.game.accept("s-repeat",    self._nav_down)
        self.game.accept("z",           self._nav_up)
        self.game.accept("s",           self._nav_down)
        self.game.accept("enter",       self._select)
        self.game.accept("space",       self._select)
        self.game.accept("mouse1",      self._mouse_click)
        self.game.accept("escape",      self._back)

        self.game.taskMgr.add(self._update_menu, "menu_update")

    # ── Construction des entrées ───────────────────────────────────────────────

    def _build_entries(self, entries):
        for t in self.entry_texts:
            t.destroy()
        self.entry_texts = []

        for i, (label, _) in enumerate(entries):
            t = OnscreenText(
                text=f"›  {label}",
                pos=(ENTRY_X, ENTRY_START_Y - i * ENTRY_SPACING),
                scale=0.044,
                fg=C_ORANGE, align=TextNode.ALeft,
                mayChange=True, sort=210,
                shadow=(0, 0, 0, 0.5),
            )
            self.entry_texts.append(t)

        self._update_selection()

    def _update_selection(self):
        for i, t in enumerate(self.entry_texts):
            if i == self.selected:
                t.setFg(C_SELECTED)
                t.setScale(0.050)
            else:
                t.setFg(C_ORANGE)
                t.setScale(0.044)
        self._update_level_subtitle()

    def _get_entries(self):
        if self.current_menu == "options":
            return self.ENTRIES_OPTIONS
        if self.current_menu == "level_select":
            return self._level_entries
        return self.ENTRIES_MAIN

    # ── Navigation ────────────────────────────────────────────────────────────

    def _nav_up(self):
        if not self.active: return
        entries = self._get_entries()
        self.selected = (self.selected - 1) % len(entries)
        self._update_selection()

    def _nav_down(self):
        if not self.active: return
        entries = self._get_entries()
        self.selected = (self.selected + 1) % len(entries)
        self._update_selection()

    def _select(self):
        if not self.active: return
        entries = self._get_entries()
        _, action = entries[self.selected]

        if action == "solo":
            self.hide()
            self.game.start_game(start_level=1)
        elif action == "level_select":
            self._show_level_select()
        elif action.startswith("play_level_"):
            lvl = int(action.split("_")[-1])
            self.hide()
            self.game.start_game(start_level=lvl)
        elif action == "coop":
            if self.subtitle:
                self.subtitle.setText("COOP LAN — COMING SOON")
                self.subtitle.setFg(Vec4(1, 0.5, 0.1, 0.8))
        elif action == "leaderboard":
            self._show_leaderboard()
        elif action == "options":
            self.current_menu = "options"
            self.selected = 0
            self._build_entries(self.ENTRIES_OPTIONS)
        elif action == "quit":
            self.game.userExit()
        elif action == "sfx_up":
            if hasattr(self.game, 'sounds'):
                self.game.sounds.sfx_volume = min(1.0, self.game.sounds.sfx_volume + 0.1)
                self._show_volume()
        elif action == "sfx_down":
            if hasattr(self.game, 'sounds'):
                self.game.sounds.sfx_volume = max(0.0, self.game.sounds.sfx_volume - 0.1)
                self._show_volume()
        elif action == "fullscreen":
            self.game.toggle_fullscreen()
        elif action == "back":
            self.current_menu = "main"
            self.selected = 0
            self._build_entries(self.ENTRIES_MAIN)
            if self.subtitle:
                self.subtitle.setText("A long time ago in a galaxy far, far away...")
                self.subtitle.setFg(C_DIM)

    def _show_level_select(self):
        self._level_entries = []
        for lvl_id, cfg in sorted(LEVELS.items()):
            label = f"L{lvl_id} — {cfg['name']}"
            self._level_entries.append((label, f"play_level_{lvl_id}"))
        self._level_entries.append(("RETOUR", "back"))
        self.current_menu = "level_select"
        self.selected = 0
        self._build_entries(self._level_entries)
        if self.subtitle:
            self.subtitle.setText("Choisissez votre mission")
            self.subtitle.setFg(C_ORANGE)

    def _update_level_subtitle(self):
        if self.current_menu != "level_select": return
        if self.selected < len(self._level_entries) - 1:
            lvl_id = self.selected + 1
            cfg    = LEVELS.get(lvl_id, {})
            desc   = cfg.get("description", "")
            if self.subtitle:
                self.subtitle.setText(desc)
                self.subtitle.setFg(C_DIM)
        else:
            if self.subtitle:
                self.subtitle.setText("")

    def _back(self):
        if not self.active: return
        if self.current_menu != "main":
            self.current_menu = "main"
            self.selected = 0
            self._build_entries(self.ENTRIES_MAIN)
            if self.subtitle:
                self.subtitle.setText("A long time ago in a galaxy far, far away...")
                self.subtitle.setFg(C_DIM)
        else:
            self.game.userExit()

    def _show_volume(self):
        vol = int(self.game.sounds.sfx_volume * 100)
        if self.subtitle:
            self.subtitle.setText(f"SFX VOLUME : {vol}%")
            self.subtitle.setFg(C_ORANGE)

    def _show_leaderboard(self):
        if not hasattr(self.game, 'leaderboard'):
            return
        entries = self.game.leaderboard.entries
        for t in self.entry_texts:
            t.destroy()
        self.entry_texts = []

        t = OnscreenText(
            text="TOP PILOTS", pos=(ENTRY_X, 0.35), scale=0.048,
            fg=C_TITLE, align=TextNode.ALeft, sort=210,
            shadow=(0, 0, 0, 0.9),
        )
        self.entry_texts.append(t)

        t = OnscreenText(
            text="#   NOM        SCORE   VAGUE  KILLS   DATE",
            pos=(ENTRY_X, 0.24), scale=0.021,
            fg=C_DIM, align=TextNode.ALeft, sort=210,
        )
        self.entry_texts.append(t)

        for i, entry in enumerate(entries[:10]):
            rank  = i + 1
            name  = entry.get("name",  "???")
            score = entry.get("score", 0)
            wave  = entry.get("wave",  0)
            kills = entry.get("kills", 0)
            date  = entry.get("date",  "")
            line  = f"{rank:>2}.  {name:<8}  {score:>6}   {wave:>2}    {kills:>3}   {date}"
            col   = C_SELECTED if i == 0 else C_ORANGE
            t = OnscreenText(
                text=line, pos=(ENTRY_X, 0.14 - i * 0.060), scale=0.023,
                fg=col, align=TextNode.ALeft, sort=210,
            )
            self.entry_texts.append(t)

        t = OnscreenText(
            text="ESC — Retour",
            pos=(ENTRY_X, -0.65), scale=0.024,
            fg=C_DIM, align=TextNode.ALeft, sort=210,
        )
        self.entry_texts.append(t)
        self.current_menu = "leaderboard"

    # ── Souris ─────────────────────────────────────────────────────────────────

    def _mouse_click(self):
        if not self.active: return
        self._select()

    def _get_mouse_hover_index(self):
        if not self.game.mouseWatcherNode.hasMouse():
            return -1
        mx = self.game.mouseWatcherNode.getMouseX()
        my = self.game.mouseWatcherNode.getMouseY()
        # Vérifie que la souris est dans le panneau gauche
        ar = self.game.getAspectRatio()
        if mx * ar > PANEL_RIGHT:
            return -1
        entries = self._get_entries()
        for i in range(len(entries)):
            ey = ENTRY_START_Y - i * ENTRY_SPACING
            if abs(my - ey) < ENTRY_SPACING * 0.45:
                return i
        return -1

    # ── Animation ──────────────────────────────────────────────────────────────

    def _update_menu(self, task):
        if not self.active:
            return task.done
        self.timer += globalClock.getDt()

        # Pulse subtil du titre
        if self.title:
            pulse = 0.97 + 0.03 * math.sin(self.timer * 1.8)
            self.title.setScale(0.095 * pulse)

        # Hover souris
        if self.current_menu not in ("leaderboard",):
            hover = self._get_mouse_hover_index()
            if hover >= 0 and hover != self.selected:
                self.selected = hover
                self._update_selection()

        return task.cont

    # ── Cleanup ────────────────────────────────────────────────────────────────

    def hide(self):
        self.active = False
        self.game.taskMgr.remove("menu_update")

        for key in ["arrow_up", "arrow_down", "z-repeat", "s-repeat",
                    "z", "s", "enter", "space", "escape", "mouse1"]:
            self.game.ignore(key)

        for attr in ["bg", "bg_image", "panel", "separator", "logo_rule",
                     "title", "title_sub", "subtitle", "controls_text", "version_text"]:
            obj = getattr(self, attr, None)
            if obj:
                try:
                    obj.destroy()
                except Exception:
                    pass
                setattr(self, attr, None)

        for t in self.entry_texts:
            try:
                t.destroy()
            except Exception:
                pass
        self.entry_texts = []
