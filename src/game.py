"""
X-Wing Shooter — Classe principale du jeu.
Phase 3 : explosions, tirs ennemis, sons, vie joueur.
"""

from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import (
    WindowProperties, Vec3, Vec4, Point2, Point3,
    AmbientLight, DirectionalLight,
    AntialiasAttrib,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomLines, GeomNode, NodePath, TransparencyAttrib,
    TextNode, loadPrcFileData,
)

# MSAA 4x — doit être déclaré avant ShowBase.__init__
loadPrcFileData("", "framebuffer-multisample 1")
loadPrcFileData("", "multisamples 4")

from src.player import Player
from src.starfield import Starfield
from src.lasers import LaserSystem
from src.enemies import EnemySpawner
from src.explosions import ExplosionManager
from src.hud import HUD
from src.sounds import SoundManager
from src.environment import Environment
from src.scores import Leaderboard
from src.powerups import PowerUpManager
from src.torpedoes import TorpedoSystem
from src.force import ForceAbility
from src.menu import MainMenu
from src.boss import BossTIEAdvanced, BOSS_TRIGGER_WAVE
from src.screenshake import Screenshake
from src.levels import LEVELS
from src.settings import get_level as _get_level_settings


class Game(ShowBase):
    """Classe principale du jeu X-Wing Shooter."""

    PLAYER_MAX_HP = 50

    # ── Caméra ──────────────────────────────────────────────────────────────
    # Vue normale (reculée par rapport à l'origine -4)
    CAM_FAR_POS  = (0, -8, 3.5)
    CAM_FAR_LOOK = (0, 22, 0)
    # Vue Force / zoom ADS — on se rapproche du vaisseau
    CAM_CLOSE_POS  = (0, 3, 1.8)
    CAM_CLOSE_LOOK = (0, 16, 0)
    # Vitesse de lerp (unités/s, >1 = réactif, ~5 = fondu fluide ~0.2s)
    CAM_LERP_SPEED = 5.0

    # Squelette procédural X-Wing — coordonnées locales au player.node (X=droite, Y=avant, Z=haut)
    _SKEL_LOCAL = [
        # Fuselage
        ((0, -0.55, 0),    (0,  0.75,  0)),
        # Cockpit
        ((0,  0.60, 0),    (0,  0.75,  0.12)),
        ((0,  0.75, 0.12), (0,  0.55,  0.16)),
        # Aile haut-gauche
        ((0, -0.05, 0.04), (-0.9, -0.20,  0.22)),
        # Aile haut-droite
        ((0, -0.05, 0.04), ( 0.9, -0.20,  0.22)),
        # Aile bas-gauche
        ((0, -0.05,-0.04), (-0.9, -0.20, -0.22)),
        # Aile bas-droite
        ((0, -0.05,-0.04), ( 0.9, -0.20, -0.22)),
        # Nacelle haut-gauche
        ((-0.9, -0.20, 0.22), (-0.9, -0.48, 0.22)),
        # Nacelle haut-droite
        (( 0.9, -0.20, 0.22), ( 0.9, -0.48, 0.22)),
        # Nacelle bas-gauche
        ((-0.9, -0.20,-0.22), (-0.9, -0.48,-0.22)),
        # Nacelle bas-droite
        (( 0.9, -0.20,-0.22), ( 0.9, -0.48,-0.22)),
        # Canon haut-gauche → nacelle
        ((-1.0, 1.5, 0.03), (-0.9, -0.20, 0.22)),
        # Canon haut-droite → nacelle
        (( 1.0, 1.5, 0.03), ( 0.9, -0.20, 0.22)),
        # Canon bas-gauche → nacelle
        ((-1.0, 1.5,-0.03), (-0.9, -0.20,-0.22)),
        # Canon bas-droite → nacelle
        (( 1.0, 1.5,-0.03), ( 0.9, -0.20,-0.22)),
    ]
    _CANNON_LOCAL = [(-1.0, 1.0, 0.03), (1.0, 1.0, 0.03),
                     (-1.0, 1.0,-0.03), (1.0, 1.0,-0.03)]
    _ENGINE_LOCAL = [(-0.31,-1.20, 0.17), (0.31,-1.20, 0.17),
                     (-0.31,-1.20,-0.17), (0.31,-1.20,-0.17)]

    def __init__(self, net_mode=None, net_ip="127.0.0.1", net_port=7777):
        ShowBase.__init__(self)

        # Réseau (skeleton V3)
        self.network = None
        self._net_mode = net_mode
        self._net_ip = net_ip
        self._net_port = net_port
        if net_mode is not None:
            from src.network import NetworkManager
            self.network = NetworkManager(mode=net_mode, port=net_port, host_ip=net_ip)
            self.network.start()

        self.setup_window()
        self.setup_lights()

        self.render.setAntialias(AntialiasAttrib.MAuto)
        self.setBackgroundColor(0, 0, 0, 1)

        # Leaderboard (disponible pour le menu)
        self.leaderboard = Leaderboard()

        # Sons (disponible pour le menu)
        self.sounds = SoundManager(self)

        # Starfield en arrière-plan (visible au menu ET en jeu)
        self.starfield = Starfield(self)

        # État
        self.game_started = False
        # is_fullscreen est déjà positionné à True par setup_window()
        self.fps_visible = True
        self.setFrameRateMeter(True)

        # Starfield update task (toujours actif, même au menu)
        self.taskMgr.add(self._update_starfield, "starfield_update")

        # Contrôles globaux
        self.accept("f1", self.toggle_fps)
        self.accept("f11", self.toggle_fullscreen)

        # Fondu au noir — utilisé pour game over → menu
        from direct.gui.DirectGui import DirectFrame
        self._fade_overlay = DirectFrame(
            frameColor=Vec4(0, 0, 0, 0),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0), sortOrder=200,
        )
        self._fade_timer    = 0.0
        self._fade_duration = 1.8
        self._fading        = False

        # Menu principal
        self.menu = MainMenu(self)
        self.menu.show()

    def _update_starfield(self, task):
        dt = globalClock.getDt()
        self.starfield.update(dt, 20.0)  # Vitesse lente au menu
        return task.cont

    def start_game(self, start_level=1):
        """Lance la partie — appelé depuis le menu."""
        if self.game_started:
            return

        self.game_started = True
        self.selected_level = start_level if start_level in LEVELS else 1
        _ls = _get_level_settings(self.selected_level)

        # _debug_level = niveau sans ennemis (L99 historique + L0 sandbox)
        self._debug_level = _ls["no_enemies"]

        # Masque le curseur — doMethodLater évite le conflit avec le clic DirectGUI
        self.taskMgr.doMethodLater(0.05, self._hide_cursor_task, "hide_cursor")

        # Couleur de fond + lumière ambiante selon le niveau
        bg = LEVELS.get(self.selected_level, LEVELS[1]).get("bg_color", (0, 0, 0))
        self.setBackgroundColor(bg[0], bg[1], bg[2], 1)

        # Systèmes de jeu — env_level peut différer (ex: L0 sandbox → env L2)
        env_level = _ls["env_level"]
        self.environment = Environment(self, level=env_level)
        self.player = Player(self)
        self.lasers = LaserSystem(self)
        self.spawner = EnemySpawner(self, level=self.selected_level)
        self.explosions = ExplosionManager(self)
        self.hud = HUD(self)
        self.powerups = PowerUpManager(self)
        self.torpedoes = TorpedoSystem(self)
        self.force = ForceAbility()
        self.force.gauge = 100.0   # Force pleine au démarrage

        self.lasers.set_enemies(self.spawner)

        # Bounds joueur depuis settings
        self.player.set_bounds(bounds_x=_ls["bounds_x"])

        # Ombre au sol — uniquement sur surface lunaire (env L2)
        if env_level == 2:
            self.player.set_shadow_visible(True)

        # État du jeu
        self.player_hp = _ls["player_hp"]
        self.game_over = False
        self.scroll_speed = _ls["scroll_speed"]
        self.last_wave = 1
        self.last_score = 0
        self.total_kills = 0
        self.torpedo_count = 3
        self._was_overheated = False
        self.locking = False
        self.boss = None
        self.boss_phase = None       # None, "active", "destroying", "done"
        self._boss_phase_label = ""  # Suivi transitions de phase boss

        # Pas d'ennemis si niveau sandbox/debug
        if _ls["no_enemies"]:
            self.spawner.stop_spawning()

        # VFX — screenshake + slow-mo combo
        self.screenshake   = Screenshake(self)
        self.time_scale    = 1.0     # ×0.65 pendant combo slow-mo
        self.slowmo_timer  = 0.0
        self.combo_kills   = []      # Timestamps des kills récents

        # Boucle de jeu
        self.taskMgr.add(self.update, "game_update")

        # Contrôles de jeu
        self.accept("escape", self._game_escape)
        self.accept("m", self.sounds.toggle)
        self.accept("r", self.reset_game)
        self.accept("mouse2",    self.toggle_force)
        self.accept("mouse3",    self.fire_torpedo)
        self.accept("2", self._toggle_debug)
        self.accept("3", self._toggle_skeleton)
        self.accept("4", self._toggle_top_cam)
        self.accept("5", self._toggle_close_cam)

        # Mode debug
        self.debug_mode       = False
        self._top_cam_mode    = False
        self._close_cam_mode  = False  # Lointaine par défaut

        # Caméra — position initiale + tracking pour le lerp
        self._cam_cur_pos  = Vec3(*self.CAM_FAR_POS)
        self._cam_cur_look = Vec3(*self.CAM_FAR_LOOK)
        self.camera.setPos(self._cam_cur_pos)
        self.camera.lookAt(self._cam_cur_look)
        self._debug_node      = None
        self._skeleton_mode   = False
        self._debug_skel_vd   = None
        self._debug_skel_node = None
        self._debug_x_label   = None

        # Sandbox / debug : règle debug active dès le départ
        if _ls.get("debug_ruler"):
            self.debug_mode = True
            self._build_debug_ruler()

    def setup_window(self):
        props = WindowProperties()
        props.setTitle("X-Wing Shooter")
        w = self.pipe.getDisplayWidth()
        h = self.pipe.getDisplayHeight()
        props.setFullscreen(True)
        props.setSize(w, h)
        self.win.requestProperties(props)
        self.disableMouse()
        self.is_fullscreen = True
        # Sync aspect ratio after window opens
        self.taskMgr.doMethodLater(0.05, self._sync_aspect, "sync_aspect_init")

    def _set_cursor(self, visible: bool):
        """Affiche ou masque le curseur de la souris."""
        props = WindowProperties()
        props.setCursorHidden(not visible)
        self.win.requestProperties(props)

    def _hide_cursor_task(self, task):
        """Tâche différée — cache le curseur après le traitement du clic menu."""
        self._set_cursor(False)
        return task.done

    def setup_lights(self):
        # Lumière ambiante — bleutée, espace froid
        ambient = AmbientLight("ambient")
        ambient.setColor(Vec4(0.15, 0.15, 0.25, 1))
        ambient_np = self.render.attachNewNode(ambient)
        self.render.setLight(ambient_np)

        # Soleil principal — lumière chaude depuis le haut-gauche
        sun = DirectionalLight("sun")
        sun.setColor(Vec4(1.0, 0.95, 0.85, 1))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(30, -40, 0)
        self.render.setLight(sun_np)

        # Lumière de remplissage — légère, depuis le bas-droite
        fill = DirectionalLight("fill")
        fill.setColor(Vec4(0.15, 0.2, 0.3, 1))
        fill_np = self.render.attachNewNode(fill)
        fill_np.setHpr(-120, 30, 0)
        self.render.setLight(fill_np)

        # Lumière frontale — éclaire les faces qui arrivent vers le joueur
        # (astéroïdes, ennemis de face) depuis derrière la caméra
        front = DirectionalLight("front")
        front.setColor(Vec4(0.35, 0.38, 0.45, 1))
        front_np = self.render.attachNewNode(front)
        front_np.setHpr(0, 0, 0)   # pointe dans +Y = éclaire les faces -Y
        self.render.setLight(front_np)

    def update(self, task):
        """Boucle de jeu principale."""
        dt = globalClock.getDt()

        # ── Fondu au noir game over → menu ──
        if self._fading:
            self._fade_timer += dt
            t = min(1.0, self._fade_timer / self._fade_duration)
            self._fade_overlay["frameColor"] = Vec4(0, 0, 0, t)
            if t >= 1.0:
                self._fading = False
                self.return_to_menu()
            return task.cont

        if self.game_over:
            return task.cont

        # Réseau (stub V3)
        self._process_network()

        # Screenshake (toujours en temps réel)
        self.screenshake.update(dt)

        # Slow-mo combo
        if self.slowmo_timer > 0:
            self.slowmo_timer -= dt
            if self.slowmo_timer <= 0:
                self.time_scale = 1.0

        # Force — update + time_scale
        self.force.update(dt)
        ts = self.force.get_time_scale() * self.time_scale
        dt_world = dt * ts   # Temps ralenti pour le monde
        dt_player = dt       # Temps normal pour le joueur

        # Étoiles
        self.starfield.update(dt_world, self.scroll_speed)

        # Décor
        self.environment.update(dt_world, self.scroll_speed)

        # Joueur (temps normal)
        self.player.update(dt_player,
                           hp_pct=self.player_hp / max(self.PLAYER_MAX_HP, 1))
        player_pos = self.player.node.getPos()

        # Lasers joueur (temps normal, force_active pour auto-aim + no overheat)
        self.lasers.update(dt_player, self.player.node,
                          force_active=self.force.active)

        # Collisions lasers → décor (astéroïdes + débris)
        ast_hits = self.environment.check_laser_hits(self.lasers.get_bolts())
        for hit_pos in ast_hits:
            self.explosions.spawn(hit_pos, preset="small", score=0)
            self.sounds.play("explosion")

        # Score avant pour détecter les kills
        score_before = self.spawner.score

        # Ennemis + tirs ennemis (temps ralenti)
        # Ennemis (pas pendant le boss)
        if self.boss_phase is None:
            self.spawner.update(dt_world, self.lasers, player_pos)
        else:
            # Pendant le boss, update seulement les bolts ennemis (tourelles du SD)
            for bolt in self.spawner.enemy_bolts:
                bolt.update(dt_world)
            self.spawner.enemy_bolts = [b for b in self.spawner.enemy_bolts if b.alive]

        # Détecte un kill → explosion + score + powerup + force
        if self.spawner.score > score_before:
            kill_score  = self.spawner.score - score_before
            kill_class  = getattr(self.spawner, 'last_kill_class', 'TIEFighter')
            self.total_kills += 1
            if hasattr(self.spawner, 'last_kill_pos'):
                # Preset selon classe de vaisseau
                if kill_class in ('TIEBomber', 'AttackBomber', 'ImperialShuttle'):
                    preset = "medium"
                    self.screenshake.trigger(0.30, 0.28)
                elif kill_class == 'GroundTurret':
                    preset = "small"
                    self.screenshake.trigger(0.20, 0.22)
                else:
                    preset = "small"
                    self.screenshake.trigger(0.15, 0.2)
                self.explosions.spawn(self.spawner.last_kill_pos, preset=preset, score=kill_score)
                self.sounds.play("explosion")
                self.powerups.try_spawn(self.spawner.last_kill_pos)
                # Force gauge
                self.force.add_kill(kill_class)
                # Combo
                self._register_combo_kill()

        # Power-ups
        collected = self.powerups.update(dt_world, player_pos, self.scroll_speed)
        for pu_type in collected:
            if pu_type == "torpedo":
                self.torpedoes.add_stock(3)
                self.hud.show_pickup("+3 TORPEDOES")
            elif pu_type == "repair":
                self.player_hp = min(self.PLAYER_MAX_HP, self.player_hp + 2)
                self.hud.show_pickup("+2 HULL")
            elif pu_type == "force":
                self.force.add_pickup(35.0)
                self.hud.show_pickup("FORCE CHARGED")
            self.sounds.play("hit")

        # Torpilles — cibles : ennemis normaux OU boss si phase boss
        torp_targets = [self.boss] if (self.boss and self.boss.alive) else self.spawner.enemies
        self.torpedoes.update(
            dt_player, self.player.crosshair_x, self.player.crosshair_z,
            torp_targets
        )
        score_tracker = {"last_kill_pos": None}
        torpedo_score = self.torpedoes.check_impacts(
            torp_targets, self.explosions, score_tracker
        )
        if torpedo_score > 0:
            self.spawner.score += torpedo_score
            self.total_kills += 1
            if score_tracker["last_kill_pos"]:
                self.spawner.last_kill_pos = score_tracker["last_kill_pos"]
            for kill_class in score_tracker.get("killed_classes", []):
                self.force.add_kill(kill_class, torpedo_kill=True)
                self._register_combo_kill()

        # Son laser
        if self.lasers.firing and self.lasers.fire_timer <= 0 and not self.lasers.overheated:
            self.sounds.play("laser")

        # Son de surchauffe
        if self.lasers.overheated and not self._was_overheated:
            pass  # self.sounds.play("overheat")  # désactivé (trop énervant)
        self._was_overheated = self.lasers.overheated

        # Caméra — lerp AVANT le HUD pour que la projection soit synchrone avec le rendu
        if not self._top_cam_mode:
            self._update_camera(dt)

        # Warning astéroïdes proches
        self._check_asteroid_warning(player_pos)

        # Collisions tirs ennemis -> joueur
        if not self.player.invincible:
            damage, hit_positions = self.spawner.check_player_hit(player_pos)
            if damage > 0:
                self.player_hp -= damage
                hp_pct = self.player_hp / self.PLAYER_MAX_HP
                self.hud.show_damage_flash(hp_pct)
                self.hud.show_shield_flash()
                self.player.show_shield_hit()
                self.sounds.play("hit")
                self.screenshake.trigger(0.5, 0.3)

                if self.player_hp <= 0:
                    self.player_hp = 0
                    self.game_over = True
                    self.hud.show_game_over(self.spawner.score)
                    self._trigger_leaderboard()

            # Collisions décor (astéroïdes + bâtiments L2)
            env_damage, push_x, push_z = self.environment.check_player_collision(player_pos)
            if env_damage > 0:
                self.player_hp -= env_damage
                hp_pct = self.player_hp / self.PLAYER_MAX_HP
                self.hud.show_damage_flash(hp_pct)
                self.hud.show_shield_flash()
                self.player.show_shield_hit()
                self.sounds.play("hit")
                self.screenshake.trigger(0.4, 0.25)
                # Éjection vers le plan le plus proche (X latéral ou Z vertical)
                cur = self.player.node.getPos()
                if push_x != 0.0:
                    new_x = max(-self.player.BOUNDS_X, min(self.player.BOUNDS_X,
                                                          cur.getX() + push_x))
                    self.player.node.setX(new_x)
                if push_z != 0.0:
                    bz = self.player.BOUNDS_Z
                    new_z = max(-bz, min(bz, cur.getZ() + push_z))
                    self.player.node.setZ(new_z)

                if self.player_hp <= 0:
                    self.player_hp = 0
                    self.game_over = True
                    self.hud.show_game_over(self.spawner.score)
                    self._trigger_leaderboard()

        # Explosions
        self.explosions.update(dt)

        # Boss trigger
        if self.spawner.wave >= BOSS_TRIGGER_WAVE and self.boss_phase is None:
            self.spawner.stop_spawning()

            if self.boss is None and len(self.spawner.enemies) == 0:
                self.boss = BossTIEAdvanced(self)
                self.boss.start()
                self.boss_phase = "active"
                self.hud.announce_wave("BOSS: DARTH VADER")
                self.hud.show_boss_bar()
                self._boss_phase_label = self.boss.ai.get_phase_label()

        # Boss update
        if self.boss and self.boss_phase == "active":
            self.boss.update(dt, player_pos, self.spawner.enemy_bolts, self.player_hp)

            # Barre HP boss
            hp_pct       = self.boss.hp / self.boss.max_hp
            phase_label  = self.boss.ai.get_phase_label()
            self.hud.update_boss_bar(hp_pct, phase_label)

            # Détecte transition de phase → screenshake + flash
            if phase_label != self._boss_phase_label:
                self._boss_phase_label = phase_label
                self.screenshake.trigger(0.8, 0.5)
                self.hud.trigger_screen_flash(0.25, 0.2)

            # Check tirs joueur → boss (distance simple)
            for bolt in self.lasers.get_bolts():
                if not bolt.alive:
                    continue
                boss_pos = self.boss.get_pos()
                if boss_pos:
                    dist = (bolt.node.getPos() - boss_pos).length()
                    if dist < self.boss.hit_radius:
                        self.boss.hit(bolt.DAMAGE)
                        bolt.destroy()
                        self.sounds.play("hit")
                        self.screenshake.trigger(0.15, 0.15)

            if self.boss.defeated:
                self.boss_phase = "destroying"
                self.hud.hide_boss_bar()

        elif self.boss and self.boss_phase == "destroying":
            done = self.boss.update_destruction(dt, self.explosions)
            if done:
                self.boss_phase = "done"
                self.spawner.score += 5000
                # Capture la position AVANT cleanup
                boss_final_pos = self.boss.get_pos()
                self.boss.cleanup()
                # Explosion cinématique finale
                if boss_final_pos:
                    self.explosions.spawn(boss_final_pos, preset="large", score=0)
                self.screenshake.trigger(1.0, 0.8)
                self.hud.trigger_screen_flash(0.4, 0.2)
                self.hud.announce_wave("VICTORY!")
                self.game_over = True
                self.hud.show_game_over(self.spawner.score)
                self._trigger_leaderboard()

        # Annonce nouvelle vague (seulement si pas de boss)
        if self.boss_phase is None:
            if self.spawner.wave != self.last_wave:
                self.hud.announce_wave(self.spawner.wave)
                self.last_wave = self.spawner.wave

        # HUD
        self.hud.update(
            dt,
            self.spawner.score,
            self.spawner.wave,
            self.spawner.get_enemy_count(),
            self.player_hp,
            self.PLAYER_MAX_HP,
            heat_pct=self.lasers.get_heat_pct(),
            overheated=self.lasers.is_overheated(),
            cooldown_pct=self.lasers.get_cooldown_pct(),
            roll=self.player.current_roll,
            pitch=self.player.current_pitch,
            torpedo_count=self.torpedoes.stock,
            force_pct=self.force.get_gauge_pct(),
            force_active=self.force.active,
            player_z=self.player.node.getPos().getZ(),
            player_node=self.player.node,
        )

        # Debug ruler labels
        if self.debug_mode:
            self._update_debug_labels()

        return task.cont

    def reset_game(self):
        """Recommence une partie."""
        if not self.game_over:
            return

        # Nettoie tout
        for enemy in self.spawner.enemies:
            if enemy.alive:
                enemy.destroy()
        for bolt in self.spawner.enemy_bolts:
            if bolt.alive:
                bolt.destroy()
        for bolt in self.lasers.bolts:
            if bolt.alive:
                bolt.destroy()
        for exp in self.explosions.explosions:
            if exp.alive:
                exp.destroy()

        # Reset état
        self.player_hp = self.PLAYER_MAX_HP
        self.game_over = False
        self.last_wave = 1
        self.last_score = 0
        self.total_kills = 0
        self.torpedo_count = 3

        self.spawner.enemies = []
        self.spawner.enemy_bolts = []
        self.spawner.score = 0
        self.spawner.wave = 1
        self.spawner.spawn_timer = 2.0
        self.spawner.wave_enemies_to_spawn = []
        self.spawner.spawn_index = 0
        self.spawner.wave_started = False
        self.spawner.last_kill_pos = None
        self.spawner.last_kill_class = None
        self.spawner._prepare_wave()

        self.lasers.bolts = []
        self.explosions.explosions = []
        self.explosions.popups = []
        self.powerups.reset()
        self.torpedoes.reset()
        self.force.reset()
        if self.boss:
            self.boss.cleanup()
        self.boss = None
        self.boss_phase = None
        self._boss_phase_label = ""
        self.hud.hide_boss_bar()

        # VFX reset
        self.screenshake.reset()
        self.time_scale   = 1.0
        self.slowmo_timer = 0.0
        self.combo_kills  = []

        # Nettoie l'environnement
        for a in self.environment.asteroids:
            a.destroy()
        for p in self.environment.planets:
            p.destroy()
        for n in self.environment.nebulae:
            n.destroy()
        for d in self.environment.debris:
            d.destroy()
        for t in self.environment.terrain_tiles:
            t.destroy()
        for w in self.environment.wall_panels:
            w.destroy()
        for f in self.environment.floor_panels:
            f.destroy()
        for s in self.environment.surface_panels:
            s.destroy()
        for dg in self.environment.decor_groups:
            dg.destroy()
        for bg in self.environment.base_groups:
            bg.destroy()
        for fl in self.environment.fog_layers:
            fl.destroy()

        # Lumière ambiante L4 — nettoyage avant re-spawn
        env = self.environment
        if hasattr(env, '_l4_ambient_np') and env._l4_ambient_np and not env._l4_ambient_np.isEmpty():
            self.render.clearLight(env._l4_ambient_np)
            env._l4_ambient_np.removeNode()
            env._l4_ambient_np = None

        self.environment.asteroids      = []
        self.environment.planets        = []
        self.environment.nebulae        = []
        self.environment.debris         = []
        self.environment.terrain_tiles  = []
        self.environment.wall_panels    = []
        self.environment.floor_panels   = []
        self.environment.surface_panels = []
        self.environment.decor_groups   = []
        self.environment.base_groups    = []
        self.environment.fog_layers     = []
        self.environment.border_mountains = []
        self.environment.roads          = []
        self.environment.asteroid_timer = 2.0
        self.environment.nebula_timer   = 15.0
        self.environment.debris_timer   = 4.0
        self.render.clearFog()

        # Réinitialise le décor selon le niveau sélectionné
        lvl = getattr(self, 'selected_level', 1)
        bg = LEVELS.get(lvl, LEVELS[1]).get("bg_color", (0, 0, 0))
        self.setBackgroundColor(bg[0], bg[1], bg[2], 1)
        if lvl == 1:
            self.environment._spawn_fixed_planets()
        elif lvl == 2:
            self.environment._init_lunar()
        elif lvl == 3:
            self.environment._init_trench()
        elif lvl == 4:
            self.environment._spawn_nebula_planet()

        # Fog globale + nappes — recréés après init niveau
        if lvl not in (3, 99):
            self.environment._setup_distance_fog(lvl)
        self.environment._setup_fog_layers(lvl)

        # Reset spawner au bon niveau
        self.spawner.level = lvl
        from src.wave_config import get_wave_defs_for_level
        self.spawner.wave_defs = get_wave_defs_for_level(lvl)

        self.player.node.setPos(0, 20, 0)
        self.player.target_x = 0
        self.player.target_z = 0
        # Restaure les touches de mouvement (z/q/s/d écrasées par le leaderboard)
        self.player.setup_controls()

        # Reset HUD complet
        self.hud.reset()

        # Reset debug
        if getattr(self, '_skeleton_mode', False):
            try: self.player.model_node.show()
            except Exception: pass
        self._skeleton_mode   = False
        self._debug_skel_vd   = None
        self._debug_skel_node = None

        if self._debug_node and not self._debug_node.isEmpty():
            self._debug_node.removeNode()
        self._debug_node      = None
        self._debug_cursor_vd = None
        self._debug_hitbox_vd = None
        self._debug_skel_vd   = None
        self._debug_marks_vd  = None
        self._debug_bldg_vd   = None
        self.debug_mode       = False

        if hasattr(self, '_debug_label_nodes'):
            for lbl in self._debug_label_nodes:
                try: lbl.destroy()
                except Exception: pass
            self._debug_label_nodes = []

        if hasattr(self, '_debug_x_label') and self._debug_x_label:
            try: self._debug_x_label.removeNode()
            except Exception: pass
            self._debug_x_label = None

    def fire_torpedo(self):
        if self.game_over:
            return
        player_pos = self.player.node.getPos()
        fired = self.torpedoes.fire(player_pos)
        if fired:
            self.sounds.play("explosion")

    def toggle_force(self):
        """Molette = toggle Force ON/OFF."""
        if self.game_over:
            return
        if self.force.active:
            self.force.deactivate()
        else:
            activated = self.force.activate()
            if activated:
                self.sounds.play("force_activate")
                if self.lasers.overheated:
                    self.lasers.heat = 0
                    self.lasers.overheated = False
                    self.lasers.cooldown_timer = 0

    def _trigger_leaderboard(self):
        """Game over — démarre le fondu au noir vers le menu."""
        self._start_fade_to_menu()

    def _start_fade_to_menu(self):
        """Lance le fondu au noir (1.8s) puis retourne au menu."""
        self._fading     = True
        self._fade_timer = 0.0
        self._fade_overlay["frameColor"] = Vec4(0, 0, 0, 0)

        # Cache immédiatement tout le HUD
        if hasattr(self, 'hud'):
            self.hud.hide_all()

    def _lb_unbind_keys(self):
        """Stub de compatibilité (leaderboard supprimé)."""
        pass

    # ------------------------------------------------------------------
    # Combo / slow-motion
    # ------------------------------------------------------------------

    def _register_combo_kill(self):
        """Enregistre un kill pour le suivi combo (3 kills en 2s = slow-mo)."""
        now = globalClock.getFrameTime()
        self.combo_kills = [t for t in self.combo_kills if now - t < 2.0]
        self.combo_kills.append(now)
        if len(self.combo_kills) >= 3:
            self._trigger_combo_slowmo()

    def _trigger_combo_slowmo(self):
        """Déclenche le slow-motion combo."""
        count = len(self.combo_kills)
        self.time_scale  = 0.65
        self.slowmo_timer = 0.4
        self.hud.show_combo(count)
        extra_shake = min(0.1, (count - 3) * 0.05)
        self.screenshake.trigger(0.3 + extra_shake, 0.3)

    # ------------------------------------------------------------------

    def quit_game(self):
        self.userExit()

    def _game_escape(self):
        """Escape en jeu — retour au menu si game over, sinon quit."""
        if self.game_over:
            self.return_to_menu()
        else:
            self.quit_game()

    def return_to_menu(self):
        """Nettoie la scène et retourne au menu."""
        # Stop game loop
        self.taskMgr.remove("game_update")

        # Unbind game controls
        for key in ["m", "r", "mouse2", "mouse3", "escape", "enter"]:
            self.ignore(key)
        self._lb_unbind_keys()

        # Nettoie les systèmes de jeu
        if hasattr(self, 'spawner'):
            for enemy in self.spawner.enemies:
                if enemy.alive:
                    enemy.destroy()
            for bolt in self.spawner.enemy_bolts:
                if bolt.alive:
                    bolt.destroy()
        if hasattr(self, 'lasers'):
            for bolt in self.lasers.bolts:
                if bolt.alive:
                    bolt.destroy()
        if hasattr(self, 'explosions'):
            for exp in self.explosions.explosions:
                if exp.alive:
                    exp.destroy()
        if hasattr(self, 'environment'):
            for a in self.environment.asteroids:
                a.destroy()
            for p in self.environment.planets:
                p.destroy()
            for n in self.environment.nebulae:
                n.destroy()
            for d in self.environment.debris:
                d.destroy()
            for t in self.environment.terrain_tiles:
                t.destroy()
            for w in self.environment.wall_panels:
                w.destroy()
            for f in self.environment.floor_panels:
                f.destroy()
            for s in self.environment.surface_panels:
                s.destroy()
            for dg in self.environment.decor_groups:
                dg.destroy()
            for bg in self.environment.base_groups:
                bg.destroy()
            for fl in getattr(self.environment, 'fog_layers', []):
                fl.destroy()
            # Lumière ambiante L4
            if hasattr(self.environment, '_l4_ambient_np') and self.environment._l4_ambient_np:
                if not self.environment._l4_ambient_np.isEmpty():
                    self.render.clearLight(self.environment._l4_ambient_np)
                    self.environment._l4_ambient_np.removeNode()
            self.render.clearFog()

        if hasattr(self, 'boss') and self.boss is not None:
            try: self.boss.cleanup()
            except Exception: pass
            self.boss = None
        self.boss_phase = None

        if hasattr(self, 'player'):
            # Nettoie l'ombre au sol
            if hasattr(self.player, '_shadow_np') and not self.player._shadow_np.isEmpty():
                self.player._shadow_np.removeNode()
            self.player.node.removeNode()
        if hasattr(self, 'powerups'):
            self.powerups.reset()
        if hasattr(self, 'torpedoes'):
            self.torpedoes.reset()

        self.game_started = False
        self.game_over    = False
        self._fading      = False
        self._fade_overlay["frameColor"] = Vec4(0, 0, 0, 0)
        self.setBackgroundColor(0, 0, 0, 1)   # fond noir au menu
        self._set_cursor(True)

        # Réaffiche le menu
        self.menu.show()

    # ============================================================
    # Réseau (skeleton V3)
    # ============================================================

    def _process_network(self):
        """Traite les messages réseau entrants (stub — V3)."""
        if self.network is None:
            return
        # Draine la queue — traitement futur dans V3
        from src.net_protocol import MSG_HANDSHAKE, MSG_DISCONNECT, MSG_HANDSHAKE_ACK
        for msg, addr in self.network.recv_all():
            msg_type = msg.get("type")
            if self._net_mode == "host":
                if msg_type == MSG_HANDSHAKE:
                    pid = self.network.register_client(addr, msg.get("name", "Player"))
                    from src.net_protocol import make_handshake_ack
                    self.network.send_to(
                        make_handshake_ack(pid, getattr(self, "selected_level", 1)),
                        addr,
                    )
                elif msg_type == MSG_DISCONNECT:
                    self.network.unregister_client(addr)
                else:
                    self.network.touch_client(addr)
            elif self._net_mode == "client":
                if msg_type == MSG_HANDSHAKE_ACK:
                    self.network.connected = True
                    self.network.player_id = msg.get("player_id")
                    print(f"[NET] Connected as player {self.network.player_id}")
                elif msg_type == MSG_DISCONNECT:
                    self.network.connected = False
                    print("[NET] Disconnected by host")

    def toggle_fps(self):
        """Active/désactive le compteur FPS."""
        self.fps_visible = not self.fps_visible
        self.setFrameRateMeter(self.fps_visible)

    def toggle_fullscreen(self):
        """Bascule entre plein écran et fenêtré."""
        self.is_fullscreen = not self.is_fullscreen
        props = WindowProperties()
        if self.is_fullscreen:
            w = self.pipe.getDisplayWidth()
            h = self.pipe.getDisplayHeight()
            props.setFullscreen(True)
            props.setSize(w, h)
        else:
            props.setFullscreen(False)
            props.setSize(1280, 720)
        self.win.requestProperties(props)
        self.taskMgr.doMethodLater(0.05, self._sync_aspect, "sync_aspect")

    def _sync_aspect(self, task):
        """Resynchronise le ratio caméra après un resize."""
        w = self.win.getXSize()
        h = self.win.getYSize()
        if h > 0:
            self.camLens.setAspectRatio(w / h)
        return task.done

    # ── Warning astéroïdes ────────────────────────────────────────────────────

    def _check_asteroid_warning(self, player_pos):
        """Allume la lumière rouge sur les astéroïdes dans la zone de danger."""
        WARN_DIST_Y = 100.0
        for ast in self.environment.asteroids:
            if not ast.alive:
                continue
            apos = ast.get_pos()
            if apos is None:
                continue
            dy = apos.getY() - player_pos.getY()
            dx = abs(apos.getX() - player_pos.getX())
            dz = abs(apos.getZ() - player_pos.getZ())
            # Seuil XZ variable selon la distance en Y
            if dy < 30.0:
                WARN_DIST_XZ = 8.0   # zone proche — déclenchement large
            elif dy < 60.0:
                WARN_DIST_XZ = 6.0   # zone intermédiaire — inchangé
            else:
                WARN_DIST_XZ = 5.0   # zone lointaine — déclenchement resserré
            in_danger = (-15.0 <= dy <= WARN_DIST_Y and dx < WARN_DIST_XZ and dz < WARN_DIST_XZ)
            ast.set_danger_light(in_danger, player_pos)

    # ── Mode debug ────────────────────────────────────────────────────────────

    def _toggle_debug(self):
        """Touche 2 — affiche/masque la règle de distance au sol."""
        self.debug_mode = not self.debug_mode
        if self.debug_mode:
            self._build_debug_ruler()
        else:
            # Restaure le modèle si squelette actif
            if getattr(self, '_skeleton_mode', False):
                try: self.player.model_node.show()
                except Exception: pass
            self._skeleton_mode   = False
            self._debug_skel_vd   = None
            self._debug_skel_node = None

            if self._debug_node and not self._debug_node.isEmpty():
                self._debug_node.removeNode()   # supprime tout le sous-arbre (hitbox incluse)
            self._debug_node      = None
            self._debug_cursor_vd = None
            self._debug_hitbox_vd = None
            self._debug_bldg_vd   = None

            if hasattr(self, '_debug_label_nodes'):
                for lbl in self._debug_label_nodes:
                    try: lbl.removeNode()
                    except Exception: pass
                self._debug_label_nodes = []

            if hasattr(self, '_debug_x_label') and self._debug_x_label:
                try: self._debug_x_label.removeNode()
                except Exception: pass
                self._debug_x_label = None

    def _build_debug_ruler(self):
        """
        Repère orthonormé debug :
          Axe Y (vert)  — ligne au sol (Z=FLOOR_Z), X=0 fixe, de Y=0 à Y=200
          Axe Z (bleu)  — ligne verticale, X=0 Y=15 fixe, de Z=FLOOR_Z à Z=+8
        Les graduations et labels sont fixes dans le monde — ne bougent pas avec le joueur.
        Deux curseurs mobiles (lignes courtes) indiquent la position du joueur sur chaque axe.
        """

        if self._debug_node and not self._debug_node.isEmpty():
            self._debug_node.removeNode()
        # Nettoie anciens labels texte 3D
        if hasattr(self, '_debug_label_nodes'):
            for lbl in self._debug_label_nodes:
                try: lbl.removeNode()
                except Exception: pass
        self._debug_label_nodes = []

        FLOOR_Z = -8.0
        CEIL_Z  =  8.0
        Y_MAX   = 200.0
        AXIS_X  =  0.0    # les axes sont à X=0, fixes
        AXIS_Y  = 15.0    # position Y de l'axe altitude (proche du départ)

        C_Y    = Vec4(1.0, 0.95, 0.55, 0.85)  # jaune pastel — axe profondeur
        C_Z    = Vec4(0.3, 0.6, 1.0, 0.90)   # bleu — axe altitude
        C_TICK = Vec4(0.7, 0.7, 0.7, 0.45)   # gris — petits repères

        root = self.render.attachNewNode("debug_ruler")
        root.setLightOff()
        root.setTransparency(TransparencyAttrib.MAlpha)

        fmt = GeomVertexFormat.getV3c4()
        vd  = GeomVertexData("ruler", fmt, Geom.UHStatic)
        vw  = GeomVertexWriter(vd, "vertex")
        cw  = GeomVertexWriter(vd, "color")
        lns = GeomLines(Geom.UHStatic)
        i   = [0]

        def seg(p0, p1, col):
            vw.addData3(*p0); cw.addData4(col)
            vw.addData3(*p1); cw.addData4(col)
            lns.addVertices(i[0], i[0]+1); i[0] += 2

        # ── Axe Y (profondeur) — trait horizontal au sol ──
        seg((AXIS_X, 0, FLOOR_Z), (AXIS_X, Y_MAX, FLOOR_Z), C_Y)
        # Graduations Y (petites, grises seulement)
        for y in range(0, int(Y_MAX)+1, 5):
            is_main = (y % 10 == 0)
            if is_main:
                continue   # skip les barres principales
            tw = 1.0
            col = C_TICK
            seg((AXIS_X - tw, y, FLOOR_Z), (AXIS_X + tw, y, FLOOR_Z), col)

        # ── Axe Z (altitude) — trait vertical fixe ──
        seg((AXIS_X, AXIS_Y, FLOOR_Z), (AXIS_X, AXIS_Y, CEIL_Z), C_Z)
        # Graduations Z
        for z in range(int(FLOOR_Z), int(CEIL_Z)+1, 2):
            is_main = (z % 4 == 0)
            tw = 2.5 if is_main else 1.0
            col = C_Z if is_main else C_TICK
            seg((AXIS_X - tw, AXIS_Y, z), (AXIS_X + tw, AXIS_Y, z), col)

        geom = Geom(vd); geom.addPrimitive(lns)
        gn = GeomNode("ruler_static"); gn.addGeom(geom)
        np_static = NodePath(gn)
        np_static.reparentTo(root)
        np_static.setRenderModeThickness(1.5)

        # ── Labels 3D fixes (Text3D via DirectLabel à plat) ──
        # On utilise des TextNode attachés au render pour qu'ils restent fixes
        from panda3d.core import TextNode as TN
        def make_label_3d(text, pos, color):
            tn = TN("dbg_lbl")
            tn.setText(text)
            tn.setTextColor(color)
            tn.setAlign(TN.ALeft)
            tn.setCardColor(0, 0, 0, 0)
            np = root.attachNewNode(tn)
            np.setPos(*pos)
            np.setScale(0.8)
            np.setBillboardAxis()   # toujours face caméra
            np.setLightOff()
            return np

        # Labels Y (tous les 10u)
        for y in range(0, int(Y_MAX)+1, 10):
            lbl = make_label_3d(f"Y{y}", (AXIS_X + 3.5, y, FLOOR_Z + 0.5), C_Y)
            self._debug_label_nodes.append(lbl)

        # Labels Z (tous les 4u)
        for z in range(int(FLOOR_Z), int(CEIL_Z)+1, 4):
            lbl = make_label_3d(f"Z{z:+d}", (AXIS_X + 3.0, AXIS_Y, z), C_Z)
            self._debug_label_nodes.append(lbl)

        # ── Géométrie dynamique pour curseurs joueur ──
        vd2  = GeomVertexData("ruler_dyn", fmt, Geom.UHDynamic)
        vw2  = GeomVertexWriter(vd2, "vertex")
        cw2  = GeomVertexWriter(vd2, "color")
        lns2 = GeomLines(Geom.UHDynamic)
        C_CUR = Vec4(1.0, 0.9, 0.1, 1.0)   # jaune vif — curseurs joueur
        # 6 segments × 2 vertices = 12 vertices (init à 0)
        for _ in range(12):
            vw2.addData3(0, 0, 0); cw2.addData4(C_CUR)
        for k in range(0, 12, 2):
            lns2.addVertices(k, k+1)
        geom2 = Geom(vd2); geom2.addPrimitive(lns2)
        gn2 = GeomNode("ruler_cursors"); gn2.addGeom(geom2)
        np_cur = NodePath(gn2)
        np_cur.reparentTo(root)
        np_cur.setRenderModeThickness(2.5)

        # ── Hitbox ellipsoïde — 3 ellipses (XY/XZ/YZ) × 32 seg = 192 vertices ──
        from src.lunar_base import LunarBaseGroup as _LBG
        self._debug_erx = _LBG._E_RX
        self._debug_ery = _LBG._E_RY
        self._debug_erz = _LBG._E_RZ
        _HBX_SEGS  = 32
        _HBX_VERTS = 3 * _HBX_SEGS * 2   # 192
        self._debug_hbx_segs = _HBX_SEGS
        vd3  = GeomVertexData("hitbox_ell", fmt, Geom.UHDynamic)
        vw3  = GeomVertexWriter(vd3, "vertex")
        cw3  = GeomVertexWriter(vd3, "color")
        lns3 = GeomLines(Geom.UHDynamic)
        C_HBX = Vec4(0.0, 1.0, 0.4, 0.55)
        for _ in range(_HBX_VERTS):
            vw3.addData3(0, 0, 0); cw3.addData4(C_HBX)
        for k in range(0, _HBX_VERTS, 2):
            lns3.addVertices(k, k + 1)
        geom3 = Geom(vd3); geom3.addPrimitive(lns3)
        gn3   = GeomNode("hitbox_ell"); gn3.addGeom(geom3)
        np_hbx = NodePath(gn3)
        np_hbx.reparentTo(root)
        np_hbx.setRenderModeThickness(1.5)

        # ── Label X en 3D (position du joueur) ──
        from panda3d.core import TextNode as TN
        tn_x = TN("debug_x_label")
        tn_x.setText("X=+0.0")
        tn_x.setTextColor(Vec4(1.0, 0.95, 0.55, 0.92))
        tn_x.setAlign(TN.ARight)
        tn_x.setCardColor(0, 0, 0, 0)
        np_x = root.attachNewNode(tn_x)
        np_x.setScale(0.408)  # -20% supplémentaire
        np_x.setBillboardAxis()
        np_x.setLightOff()
        self._debug_x_label = np_x

        # ── Squelette procédural X-Wing (lignes cyan, UHDynamic) ──
        _SKEL = self._SKEL_LOCAL
        N_SK  = len(_SKEL)
        vd_sk = GeomVertexData("skel", fmt, Geom.UHDynamic)
        vw_sk = GeomVertexWriter(vd_sk, "vertex")
        cw_sk = GeomVertexWriter(vd_sk, "color")
        lns_sk = GeomLines(Geom.UHDynamic)
        C_SK  = Vec4(0.3, 0.95, 1.0, 0.85)
        for _ in range(N_SK * 2):
            vw_sk.addData3(0, 0, 0); cw_sk.addData4(C_SK)
        for k in range(0, N_SK * 2, 2):
            lns_sk.addVertices(k, k + 1)
        geom_sk = Geom(vd_sk); geom_sk.addPrimitive(lns_sk)
        gn_sk   = GeomNode("dbg_skel"); gn_sk.addGeom(geom_sk)
        np_sk   = NodePath(gn_sk)
        np_sk.reparentTo(root)
        np_sk.setRenderModeThickness(1.5)
        self._debug_skel_vd = vd_sk

        # ── Marqueurs canons (jaune) + moteurs (rouge) — croix 3D ──
        # 4 canons × 3 axes × 2 pts = 24 verts  +  4 moteurs × 3 × 2 = 24 verts = 48 total
        vd_mk = GeomVertexData("marks", fmt, Geom.UHDynamic)
        vw_mk = GeomVertexWriter(vd_mk, "vertex")
        cw_mk = GeomVertexWriter(vd_mk, "color")
        lns_mk = GeomLines(Geom.UHDynamic)
        C_CAN = Vec4(1.0, 0.90, 0.10, 1.0)   # jaune — canons
        C_ENG = Vec4(1.0, 0.18, 0.05, 1.0)   # rouge — moteurs
        for _ in range(4 * 6):   # 4 canons × 6 vertices
            vw_mk.addData3(0, 0, 0); cw_mk.addData4(C_CAN)
        for _ in range(4 * 6):   # 4 moteurs × 6 vertices
            vw_mk.addData3(0, 0, 0); cw_mk.addData4(C_ENG)
        for k in range(0, 48, 2):
            lns_mk.addVertices(k, k + 1)
        geom_mk = Geom(vd_mk); geom_mk.addPrimitive(lns_mk)
        gn_mk   = GeomNode("dbg_marks"); gn_mk.addGeom(geom_mk)
        np_mk   = NodePath(gn_mk)
        np_mk.reparentTo(root)
        np_mk.setRenderModeThickness(3.0)
        self._debug_marks_vd = vd_mk

        # ── Hitboxes bâtiments L2 (wireframe jaune — max 96 bâtiments × 12 arêtes) ──
        # 96 entrées × 12 arêtes × 2 vertices = 2304 vertices (hangars ont 2 hitboxes: corps + ridge)
        _BLDG_MAX = 96
        _BLDG_VERTS = _BLDG_MAX * 12 * 2
        vd_bldg  = GeomVertexData("bldg_hitbox", fmt, Geom.UHDynamic)
        vw_bldg  = GeomVertexWriter(vd_bldg, "vertex")
        cw_bldg  = GeomVertexWriter(vd_bldg, "color")
        lns_bldg = GeomLines(Geom.UHDynamic)
        C_BLDG   = Vec4(1.0, 1.0, 0.0, 0.75)   # jaune vif
        for _ in range(_BLDG_VERTS):
            vw_bldg.addData3(0, 0, 0); cw_bldg.addData4(C_BLDG)
        for k in range(0, _BLDG_VERTS, 2):
            lns_bldg.addVertices(k, k + 1)
        geom_bldg = Geom(vd_bldg); geom_bldg.addPrimitive(lns_bldg)
        gn_bldg   = GeomNode("bldg_hitbox"); gn_bldg.addGeom(geom_bldg)
        np_bldg   = NodePath(gn_bldg)
        np_bldg.reparentTo(root)
        np_bldg.setRenderModeThickness(1.5)
        np_bldg.setTransparency(TransparencyAttrib.MAlpha)
        self._debug_bldg_vd   = vd_bldg
        self._debug_bldg_max  = _BLDG_MAX

        # ── Squelette (géométrie créée par _toggle_skeleton — key 3) ──
        self._skeleton_mode   = False
        self._debug_skel_node = None

        self._debug_node      = root
        self._debug_cursor_vd = vd2
        self._debug_hitbox_vd = vd3
        self._debug_axis_x    = AXIS_X
        self._debug_axis_y    = AXIS_Y
        self._debug_floor_z   = FLOOR_Z

    def _update_debug_labels(self):
        """Met à jour uniquement les curseurs joueur (les labels sont fixes)."""
        if not self.debug_mode or not self._debug_node:
            return
        if not hasattr(self, '_debug_cursor_vd') or self._debug_cursor_vd is None:
            return

        px = self.player.node.getX()
        py = self.player.node.getY()
        pz = self.player.node.getZ()
        ax = self._debug_axis_x
        ay = self._debug_axis_y
        fz = self._debug_floor_z
        TW = 3.5   # demi-largeur des curseurs

        # 6 segments curseurs :
        # seg 0 : tick sur axe Y (sol) — montre la profondeur du joueur
        # seg 1 : ligne verticale sur axe Y — sol→joueur
        # seg 2 : tick sur axe Z — montre l'altitude du joueur
        # seg 3 : ligne horizontale axe Z → joueur (montre son X)
        # seg 4 : ligne verticale tombante depuis le joueur jusqu'au sol (à sa vraie position XY)
        # seg 5 : tick X au sol sous le joueur
        pts = [
            # seg 0 — tick profondeur sur axe Y
            (ax - TW, py, fz),   (ax + TW, py, fz),
            # seg 1 — ligne verticale axe Y : sol → altitude joueur
            (ax, py, fz),         (ax, py, pz),
            # seg 2 — tick altitude sur axe Z
            (ax - TW, ay, pz),   (ax + TW, ay, pz),
            # seg 3 — ligne horizontale axe Z → X joueur
            (ax, ay, pz),         (px, ay, pz),
            # seg 4 — ligne verticale tombante depuis le joueur jusqu'au sol
            (px, py, pz),         (px, py, fz),
            # seg 5 — tick X au sol sous le joueur
            (px - TW, py, fz),   (px + TW, py, fz),
        ]

        vw = GeomVertexWriter(self._debug_cursor_vd, "vertex")
        for k, (x, y, z) in enumerate(pts):
            vw.setRow(k)
            vw.setData3(x, y, z)

        # ── Hitbox ellipsoïde — 3 ellipses centrées sur le joueur ──
        if hasattr(self, '_debug_hitbox_vd') and self._debug_hitbox_vd is not None:
            import math as _math
            ERX  = self._debug_erx
            ERY  = self._debug_ery
            ERZ  = self._debug_erz
            SEGS = self._debug_hbx_segs
            # 3 plans : XY, XZ, YZ
            ellipses = [
                lambda a: (ERX*_math.cos(a), ERY*_math.sin(a), 0),
                lambda a: (ERX*_math.cos(a), 0,                ERZ*_math.sin(a)),
                lambda a: (0,                ERY*_math.cos(a), ERZ*_math.sin(a)),
            ]
            vw_h = GeomVertexWriter(self._debug_hitbox_vd, "vertex")
            vi = 0
            for ell in ellipses:
                for i in range(SEGS):
                    a0 = 2*_math.pi * i       / SEGS
                    a1 = 2*_math.pi * (i + 1) / SEGS
                    dx0, dy0, dz0 = ell(a0)
                    dx1, dy1, dz1 = ell(a1)
                    vw_h.setRow(vi);     vw_h.setData3(px+dx0, py+dy0, pz+dz0)
                    vw_h.setRow(vi + 1); vw_h.setData3(px+dx1, py+dy1, pz+dz1)
                    vi += 2

        # ── Hitboxes bâtiments L2 (wireframe jaune) ──
        if (hasattr(self, '_debug_bldg_vd') and self._debug_bldg_vd is not None
                and getattr(self, 'selected_level', -1) in (0, 2)
                and hasattr(self, 'environment') and self.environment):
            env = self.environment
            vw_b  = GeomVertexWriter(self._debug_bldg_vd, "vertex")
            vi    = 0
            EDGES = [(0,1),(1,2),(2,3),(3,0),
                     (4,5),(5,6),(6,7),(7,4),
                     (0,4),(1,5),(2,6),(3,7)]
            MAX_V = self._debug_bldg_max * 12 * 2
            # Rembobine toutes les positions à l'origine (invisible) puis écrit
            vw_b.setRow(0)
            for _ in range(MAX_V):
                vw_b.setData3(0, 0, 0)
            vi = 0
            for bg in env.base_groups:
                if vi + 24 > MAX_V:
                    break
                for (cx, cy, cz, hw, hd, hh) in bg.get_hitboxes():
                    if vi + 24 > MAX_V:
                        break
                    corners = [
                        (cx-hw, cy-hd, cz-hh), (cx+hw, cy-hd, cz-hh),
                        (cx+hw, cy+hd, cz-hh), (cx-hw, cy+hd, cz-hh),
                        (cx-hw, cy-hd, cz+hh), (cx+hw, cy-hd, cz+hh),
                        (cx+hw, cy+hd, cz+hh), (cx-hw, cy+hd, cz+hh),
                    ]
                    for a_i, b_i in EDGES:
                        vw_b.setRow(vi);     vw_b.setData3(*corners[a_i])
                        vw_b.setRow(vi + 1); vw_b.setData3(*corners[b_i])
                        vi += 2

        # ── Squelette X-Wing ──
        if hasattr(self, '_debug_skel_vd') and self._debug_skel_vd is not None:
            vw_sk = GeomVertexWriter(self._debug_skel_vd, "vertex")
            for k, (p1, p2) in enumerate(self._SKEL_LOCAL):
                w1 = self.render.getRelativePoint(self.player.node, Point3(*p1))
                w2 = self.render.getRelativePoint(self.player.node, Point3(*p2))
                vw_sk.setRow(k*2);   vw_sk.setData3(w1)
                vw_sk.setRow(k*2+1); vw_sk.setData3(w2)

        # ── Marqueurs canons (jaune) + moteurs (rouge) ──
        if hasattr(self, '_debug_marks_vd') and self._debug_marks_vd is not None:
            vw_mk = GeomVertexWriter(self._debug_marks_vd, "vertex")
            SZ = 0.22   # demi-taille de la croix
            idx = 0
            for pts, sz in [(self._CANNON_LOCAL, SZ), (self._ENGINE_LOCAL, SZ * 1.3)]:
                for lp in pts:
                    wp = self.render.getRelativePoint(self.player.node, Point3(*lp))
                    vw_mk.setRow(idx);   vw_mk.setData3(wp.x-sz, wp.y, wp.z)
                    vw_mk.setRow(idx+1); vw_mk.setData3(wp.x+sz, wp.y, wp.z)
                    vw_mk.setRow(idx+2); vw_mk.setData3(wp.x, wp.y, wp.z)
                    vw_mk.setRow(idx+3); vw_mk.setData3(wp.x, wp.y, wp.z+sz)
                    vw_mk.setRow(idx+4); vw_mk.setData3(wp.x, wp.y-sz, wp.z)
                    vw_mk.setRow(idx+5); vw_mk.setData3(wp.x, wp.y+sz, wp.z)
                    idx += 6

        # ── Label X en 3D (positionnement) ──
        if hasattr(self, '_debug_x_label') and self._debug_x_label:
            # Positionne juste à gauche du vaisseau
            label_pos = Point3(px - 1.8, py + 0.5, pz + 0.6)
            self._debug_x_label.setPos(label_pos)
            # Update texte
            tn = self._debug_x_label.node()
            tn.setText(f"X={px:+.1f}")

        # ── Squelette ──
        if getattr(self, '_skeleton_mode', False) and self._debug_skel_vd is not None:
            self._update_skeleton_geom()

    # ── Squelette debug ──────────────────────────────────────────────────────

    def _toggle_skeleton(self):
        """Touche 3 — cache le modèle 3D et affiche le squelette clé du vaisseau."""
        if not hasattr(self, 'player'):
            return
        self._skeleton_mode = not self._skeleton_mode
        if self._skeleton_mode:
            self.player.model_node.hide()
            self._build_skeleton_geom()
        else:
            self.player.model_node.show()
            if self._debug_skel_node and not self._debug_skel_node.isEmpty():
                self._debug_skel_node.removeNode()
            self._debug_skel_node = None
            self._debug_skel_vd   = None

    def _update_camera(self, dt):
        """Lerp fluide entre vue normale et zoom Force/close (style ADS)."""
        # Force active OU touche 5 = zoom avant
        force_zoom = (hasattr(self, 'force') and self.force.active) or self._close_cam_mode
        t_pos  = Vec3(*self.CAM_CLOSE_POS)  if force_zoom else Vec3(*self.CAM_FAR_POS)
        t_look = Vec3(*self.CAM_CLOSE_LOOK) if force_zoom else Vec3(*self.CAM_FAR_LOOK)

        alpha = min(1.0, dt * self.CAM_LERP_SPEED)
        self._cam_cur_pos  = self._cam_cur_pos  + (t_pos  - self._cam_cur_pos)  * alpha
        self._cam_cur_look = self._cam_cur_look + (t_look - self._cam_cur_look) * alpha

        self.camera.setPos(self._cam_cur_pos)
        self.camera.lookAt(self._cam_cur_look)

    def _toggle_close_cam(self):
        """Touche 5 — bascule manuelle entre vue proche et vue lointaine."""
        if not hasattr(self, 'player'):
            return
        self._close_cam_mode = not self._close_cam_mode

    def _toggle_top_cam(self):
        """Touche 4 — bascule vue du dessus (debug alignement moteurs)."""
        if not hasattr(self, 'player'):
            return
        self._top_cam_mode = not self._top_cam_mode
        if self._top_cam_mode:
            # Vue du dessus, centrée sur le vaisseau, Y vers le bas
            px = self.player.node.getX()
            py = self.player.node.getY()
            self.camera.setPos(px, py, 18)
            self.camera.lookAt(px, py, 0)
        else:
            # Retour caméra normale — remet le tracking du lerp à jour
            self._cam_cur_pos  = Vec3(*self.CAM_FAR_POS)
            self._cam_cur_look = Vec3(*self.CAM_FAR_LOOK)
            self.camera.setPos(self._cam_cur_pos)
            self.camera.lookAt(self._cam_cur_look)

    def _build_skeleton_geom(self):
        """Crée la géométrie UHDynamic du squelette (80 vertices pré-alloués)."""
        if not self._debug_node:
            return
        fmt = GeomVertexFormat.getV3c4()
        vd  = GeomVertexData("skel", fmt, Geom.UHDynamic)
        vw  = GeomVertexWriter(vd, "vertex")
        cw  = GeomVertexWriter(vd, "color")
        lns = GeomLines(Geom.UHDynamic)

        C_SKEL = Vec4(0.0, 0.9, 1.0, 1.0)   # cyan
        for _ in range(80):
            vw.addData3(0, 0, 0); cw.addData4(C_SKEL)
        for k in range(0, 80, 2):
            lns.addVertices(k, k+1)
        geom = Geom(vd); geom.addPrimitive(lns)
        gn   = GeomNode("skeleton"); gn.addGeom(geom)
        np   = NodePath(gn)
        np.reparentTo(self._debug_node)
        np.setRenderModeThickness(2.0)
        np.setLightOff()

        self._debug_skel_node = np
        self._debug_skel_vd   = vd

    def _update_skeleton_geom(self):
        """Met à jour les positions du squelette à partir du modèle en cours."""
        # Points clés en espace local du model_node
        SKEL_LOCAL = [
            Point3(0,    1.2,  0.25),   # 0  cockpit
            Point3(2.5,  0,    0),       # 1  aile G
            Point3(-2.5, 0,    0),       # 2  aile D
            Point3(0.9,  0.5,  0.3),    # 3  moteur FL
            Point3(-0.9, 0.5,  0.3),    # 4  moteur FR
            Point3(0.9,  0.5, -0.3),    # 5  moteur RL
            Point3(-0.9, 0.5, -0.3),    # 6  moteur RR
            Point3(1.0,  1.5,  0.03),   # 7  canon G
            Point3(-1.0, 1.5,  0.03),   # 8  canon D
            Point3(0,    0,    0),       # 9  centre
        ]
        # Transforme en coordonnées monde
        wpts = [self.render.getRelativePoint(self.player.model_node, p)
                for p in SKEL_LOCAL]

        def w(i): return (wpts[i].getX(), wpts[i].getY(), wpts[i].getZ())

        CR = 0.22   # demi-longueur des croix
        segs = []

        # Croix 3D à chaque point clé
        for wp in wpts:
            x, y, z = wp.getX(), wp.getY(), wp.getZ()
            segs += [(x-CR,y,z),(x+CR,y,z),
                     (x,y-CR,z),(x,y+CR,z),
                     (x,y,z-CR),(x,y,z+CR)]   # 6 vertices par point

        # Lignes structurelles
        segs += [w(1), w(2)]    # envergure ailes
        segs += [w(0), w(9)]    # cockpit → centre
        segs += [w(9), w(3)]    # centre → moteur FL
        segs += [w(9), w(4)]    # centre → moteur FR
        segs += [w(9), w(5)]    # centre → moteur RL
        segs += [w(9), w(6)]    # centre → moteur RR
        segs += [w(0), w(7)]    # cockpit → canon G
        segs += [w(0), w(8)]    # cockpit → canon D

        # Padding jusqu'à 80 vertices
        while len(segs) < 80:
            segs.append((0.0, 0.0, 0.0))

        vw = GeomVertexWriter(self._debug_skel_vd, "vertex")
        for k, (x, y, z) in enumerate(segs[:80]):
            vw.setRow(k); vw.setData3(x, y, z)