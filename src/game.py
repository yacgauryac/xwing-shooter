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
from src.menu import MainMenu
from src.boss import BossTIEAdvanced, BOSS_TRIGGER_WAVE
from src.screenshake import Screenshake
from src.levels import LEVELS


class Game(ShowBase):
    """Classe principale du jeu X-Wing Shooter."""

    PLAYER_MAX_HP = 10

    def __init__(self):
        ShowBase.__init__(self)

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
        self.selected_level = max(1, min(4, start_level))

        # Masque le curseur — doMethodLater évite le conflit avec le clic DirectGUI
        self.taskMgr.doMethodLater(0.05, self._hide_cursor_task, "hide_cursor")

        # Couleur de fond selon le niveau
        bg = LEVELS.get(self.selected_level, LEVELS[1]).get("bg_color", (0, 0, 0))
        self.setBackgroundColor(bg[0], bg[1], bg[2], 1)

        # Systèmes de jeu
        self.environment = Environment(self, level=self.selected_level)
        self.player = Player(self)
        self.lasers = LaserSystem(self)
        self.spawner = EnemySpawner(self, level=self.selected_level)
        self.explosions = ExplosionManager(self)
        self.hud = HUD(self)
        self.powerups = PowerUpManager(self)
        self.torpedoes = TorpedoSystem(self)
        self.force = ForceAbility()

        self.lasers.set_enemies(self.spawner)

        # État du jeu
        self.player_hp = self.PLAYER_MAX_HP
        self.game_over = False
        self.scroll_speed = 40.0
        self.last_wave = 1
        self.last_score = 0
        self.total_kills = 0
        self.torpedo_count = 3
        self.lb_state = None
        self.lb_rank = None
        self._was_overheated = False
        self.locking = False
        self.boss = None
        self.boss_phase = None       # None, "active", "destroying", "done"
        self._boss_phase_label = ""  # Suivi transitions de phase boss

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
        self.accept("mouse3", self.start_lock)
        self.accept("mouse3-up", self.fire_torpedo)
        self.accept("mouse2", self.activate_force)
        self.accept("enter", self._lb_key, ["enter"])

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

    def update(self, task):
        """Boucle de jeu principale."""
        dt = globalClock.getDt()

        if self.game_over:
            return task.cont

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
        self.player.update(dt_player)
        player_pos = self.player.node.getPos()

        # Lasers joueur (temps normal, force_active pour auto-aim + no overheat)
        self.lasers.update(dt_player, self.player.node,
                          force_active=self.force.active)

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
                self.screenshake.trigger(0.5, 0.3)

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
                self.screenshake.trigger(0.4, 0.25)

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

        self.environment.asteroids     = []
        self.environment.planets       = []
        self.environment.nebulae       = []
        self.environment.debris        = []
        self.environment.terrain_tiles = []
        self.environment.wall_panels   = []
        self.environment.floor_panels  = []
        self.environment.asteroid_timer = 2.0
        self.environment.nebula_timer   = 15.0
        self.environment.debris_timer   = 4.0

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

        # Reset spawner au bon niveau
        self.spawner.level = lvl
        from src.enemies import WAVE_DEFS_BY_LEVEL
        self.spawner.wave_defs = list(WAVE_DEFS_BY_LEVEL.get(lvl, WAVE_DEFS_BY_LEVEL[1]))

        self.player.node.setPos(0, 20, 0)
        self.player.target_x = 0
        self.player.target_z = 0
        # Restaure les touches de mouvement (z/q/s/d écrasées par le leaderboard)
        self.player.setup_controls()

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
        player_pos = self.player.node.getPos()
        fired = self.torpedoes.fire(player_pos)
        self.locking = False  # Après fire() pour garder locked_target valide
        if fired:
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
        # Restaure les bindings jeu écrasés par A-Z
        if self.game_started:
            self.accept("m", self.sounds.toggle)
            self.accept("r", self.reset_game)

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
        for key in ["m", "r", "mouse3", "mouse3-up", "mouse2", "escape", "enter"]:
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
        if hasattr(self, 'player'):
            self.player.node.removeNode()
        if hasattr(self, 'hud'):
            self.hud._clear_leaderboard()
        if hasattr(self, 'powerups'):
            self.powerups.reset()
        if hasattr(self, 'torpedoes'):
            self.torpedoes.reset()

        self.game_started = False
        self.game_over = False
        self._set_cursor(True)    # Restaure le curseur au menu

        # Réaffiche le menu
        self.menu.show()

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