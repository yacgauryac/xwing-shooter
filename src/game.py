"""
X-Wing Shooter — Classe principale du jeu.
Phase 3 : explosions, tirs ennemis, sons, vie joueur.
"""

from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    WindowProperties, Vec3, Vec4, Point3,
    AmbientLight, DirectionalLight,
    AntialiasAttrib
)

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


class Game(ShowBase):
    """Classe principale du jeu X-Wing Shooter."""

    PLAYER_MAX_HP = 10

    def __init__(self):
        ShowBase.__init__(self)

        self.setup_window()
        self.setup_lights()

        self.render.setAntialias(AntialiasAttrib.MAuto)
        self.setBackgroundColor(0, 0, 0, 1)

        # Systèmes
        self.starfield = Starfield(self)
        self.environment = Environment(self)
        self.player = Player(self)
        self.lasers = LaserSystem(self)
        self.spawner = EnemySpawner(self)
        self.explosions = ExplosionManager(self)
        self.sounds = SoundManager(self)
        self.hud = HUD(self)
        self.powerups = PowerUpManager(self)
        self.torpedoes = TorpedoSystem(self)
        self.force = ForceAbility()

        # Connecte le laser au spawner pour l'auto-aim
        self.lasers.set_enemies(self.spawner)

        # État du jeu
        self.player_hp = self.PLAYER_MAX_HP
        self.game_over = False
        self.scroll_speed = 40.0
        self.last_wave = 1
        self.last_score = 0
        self.total_kills = 0
        self.torpedo_count = 3

        # Leaderboard
        self.leaderboard = Leaderboard()
        self.lb_state = None  # None, "name_entry", "showing"
        self.lb_rank = None
        self._was_overheated = False

        # Compteur FPS (F1 pour toggle)
        self.fps_visible = True
        self.setFrameRateMeter(True)

        # Boucle de jeu
        self.taskMgr.add(self.update, "game_update")

        # Contrôles
        self.accept("escape", self.quit_game)
        self.accept("m", self.sounds.toggle)
        self.accept("r", self.reset_game)
        self.accept("f1", self.toggle_fps)
        self.accept("f11", self.toggle_fullscreen)
        self.accept("mouse3", self.start_lock)
        self.accept("mouse3-up", self.fire_torpedo)
        self.accept("mouse2", self.activate_force)
        self.is_fullscreen = False
        self.locking = False

        # Leaderboard : enter seulement, le reste est géré dans _lb_key via le player
        self.accept("enter", self._lb_key, ["enter"])

    def setup_window(self):
        props = WindowProperties()
        props.setTitle("X-Wing Shooter")
        props.setSize(1280, 720)
        self.win.requestProperties(props)
        self.disableMouse()

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

    def update(self, task):
        """Boucle de jeu principale."""
        dt = globalClock.getDt()

        if self.game_over:
            return task.cont

        # Force — update + time_scale
        self.force.update(dt)
        ts = self.force.get_time_scale()
        dt_world = dt * ts   # Temps ralenti pour le monde
        dt_player = dt       # Temps normal pour le joueur

        # Étoiles
        self.starfield.update(dt_world, self.scroll_speed)

        # Décor
        self.environment.update(dt_world, self.scroll_speed)

        # Joueur (temps normal)
        self.player.update(dt_player)
        player_pos = self.player.node.getPos()

        # Lasers joueur (temps normal, force_active pour auto-aim + no overheat)
        self.lasers.update(dt_player, self.player.node,
                          force_active=self.force.active)

        # Score avant pour détecter les kills
        score_before = self.spawner.score

        # Ennemis + tirs ennemis (temps ralenti)
        self.spawner.update(dt_world, self.lasers, player_pos)

        # Détecte un kill → explosion + score + powerup + force
        if self.spawner.score > score_before:
            kill_score = self.spawner.score - score_before
            self.total_kills += 1
            if hasattr(self.spawner, 'last_kill_pos'):
                self.explosions.spawn(self.spawner.last_kill_pos, score=kill_score)
                self.sounds.play("explosion")
                self.powerups.try_spawn(self.spawner.last_kill_pos)
                # Force gauge
                if hasattr(self.spawner, 'last_kill_class'):
                    self.force.add_kill(self.spawner.last_kill_class)
                else:
                    self.force.add_kill("TIEFighter")

        # Power-ups
        collected = self.powerups.update(dt_world, player_pos, self.scroll_speed)
        for pu_type in collected:
            if pu_type == "torpedo":
                self.torpedoes.add_stock(3)
                self.hud.show_pickup("+3 TORPEDOES")
            elif pu_type == "repair":
                self.player_hp = min(self.PLAYER_MAX_HP, self.player_hp + 2)
                self.hud.show_pickup("+2 HULL")
            self.sounds.play("hit")

        # Torpilles (temps normal pour le joueur)
        self.torpedoes.update(
            dt_player, self.player.crosshair_x, self.player.crosshair_z,
            self.spawner.enemies, locking=self.locking
        )
        score_tracker = {"last_kill_pos": None}
        torpedo_score = self.torpedoes.check_impacts(
            self.spawner.enemies, self.explosions, score_tracker
        )
        if torpedo_score > 0:
            self.spawner.score += torpedo_score
            self.total_kills += 1
            if score_tracker["last_kill_pos"]:
                self.spawner.last_kill_pos = score_tracker["last_kill_pos"]

        # Son laser
        if self.lasers.firing and self.lasers.fire_timer <= 0 and not self.lasers.overheated:
            self.sounds.play("laser")

        # Son de surchauffe
        if self.lasers.overheated and not self._was_overheated:
            self.sounds.play("overheat")
        self._was_overheated = self.lasers.overheated

        # Collisions tirs ennemis -> joueur
        if not self.player.invincible:
            damage, hit_positions = self.spawner.check_player_hit(player_pos)
            if damage > 0:
                self.player_hp -= damage
                self.hud.show_damage_flash()
                self.hud.show_shield_flash()
                self.player.show_shield_hit()
                self.sounds.play("hit")

                if self.player_hp <= 0:
                    self.player_hp = 0
                    self.game_over = True
                    self.hud.show_game_over(self.spawner.score)
                    self._trigger_leaderboard()

            # Collisions astéroïdes
            asteroid_damage = self.environment.check_player_collision(player_pos)
            if asteroid_damage > 0:
                self.player_hp -= asteroid_damage
                self.hud.show_damage_flash()
                self.hud.show_shield_flash()
                self.player.show_shield_hit()
                self.sounds.play("hit")

                if self.player_hp <= 0:
                    self.player_hp = 0
                    self.game_over = True
                    self.hud.show_game_over(self.spawner.score)
                    self._trigger_leaderboard()

        # Explosions
        self.explosions.update(dt)

        # Annonce nouvelle vague
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
        )

        return task.cont

    def reset_game(self):
        """Recommence une partie."""
        if not self.game_over:
            return

        # Nettoie leaderboard screens
        self.hud._clear_leaderboard()
        self._lb_unbind_keys()
        self.lb_state = None
        self.lb_rank = None

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
        self.spawner.enemies_spawned = 0
        self.spawner.enemies_per_wave = 5
        self.spawner.spawn_timer = 1.0

        self.lasers.bolts = []
        self.explosions.explosions = []
        self.explosions.popups = []
        self.powerups.reset()
        self.torpedoes.reset()
        self.force.reset()

        # Nettoie l'environnement
        for a in self.environment.asteroids:
            a.destroy()
        for p in self.environment.planets:
            p.destroy()
        for n in self.environment.nebulae:
            n.destroy()
        for d in self.environment.debris:
            d.destroy()
        self.environment.asteroids = []
        self.environment.planets = []
        self.environment.nebulae = []
        self.environment.debris = []

        self.player.node.setPos(0, 20, 0)
        self.player.target_x = 0
        self.player.target_z = 0

        # Reset HUD
        self.hud.game_over_text.setText("")
        self.hud.game_over_sub.setText("")

    def start_lock(self):
        if self.game_over:
            return
        self.locking = True

    def fire_torpedo(self):
        if self.game_over:
            self.locking = False
            return
        self.locking = False
        player_pos = self.player.node.getPos()
        if self.torpedoes.fire(player_pos):
            self.sounds.play("explosion")

    def activate_force(self):
        if self.game_over:
            return
        if self.force.activate():
            self.sounds.play("explosion")  # Son temporaire
            # Reset overheat si actif
            if self.lasers.overheated:
                self.lasers.heat = 0
                self.lasers.overheated = False
                self.lasers.cooldown_timer = 0

    def _trigger_leaderboard(self):
        """Appelé au game over — lance le flow leaderboard."""
        score = self.spawner.score
        if self.leaderboard.is_high_score(score):
            self.lb_state = "name_entry"
            self.hud.show_name_entry()
            # Active les touches de saisie (lettres A-Z + backspace)
            for c in "abcdefghijklmnopqrstuvwxyz":
                self.accept(c, self._lb_key, [c])
            self.accept("backspace", self._lb_key, ["backspace"])
        else:
            self.lb_state = "showing"
            self.hud.show_leaderboard(self.leaderboard.entries)

    def _lb_unbind_keys(self):
        """Désactive les touches de saisie du leaderboard."""
        for c in "abcdefghijklmnopqrstuvwxyz":
            self.ignore(c)
        self.ignore("backspace")

    def _lb_key(self, key):
        """Gère les touches pour la saisie du nom."""
        if self.lb_state != "name_entry":
            return

        result = self.hud.update_name_entry(key)
        if result:
            self._lb_unbind_keys()
            rank = self.leaderboard.add_score(
                result, self.spawner.score,
                self.spawner.wave, self.total_kills
            )
            self.lb_rank = rank
            self.lb_state = "showing"
            self.hud.show_leaderboard(self.leaderboard.entries, highlight_rank=rank)

    def quit_game(self):
        self.userExit()

    def toggle_fps(self):
        """Active/désactive le compteur FPS."""
        self.fps_visible = not self.fps_visible
        self.setFrameRateMeter(self.fps_visible)

    def toggle_fullscreen(self):
        """Bascule entre plein écran et fenêtré."""
        self.is_fullscreen = not self.is_fullscreen
        props = WindowProperties()
        props.setFullscreen(self.is_fullscreen)
        if not self.is_fullscreen:
            props.setSize(1280, 720)
        self.win.requestProperties(props)