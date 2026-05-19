"""
Enemies — Bestiaire impérial, formations, et gestion des vagues.
Types : TIE Fighter (standard), TIE Interceptor (rapide), TIE Bomber (tank).
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomLines, GeomNode,
    NodePath, TransparencyAttrib,
)
import random
import math
import os

from src.wave_config import get_wave_defs_for_level, get_escalation_pool


# ============================================================
# Système de paliers (tiers) — Z = -4, 0, +4
# ============================================================

TIERS = [-4.0, 0.0, 4.0]       # 3 altitudes fixes
TIER_LERP = 1.8                 # Vitesse de transition vers le palier cible (u/s) — lent et fluide

# Distance à partir de laquelle le fog rend un ennemi invisible → invulnérable.
# Doit correspondre aux valeurs "onset" de _setup_distance_fog dans environment.py.
FOG_ONSET_BY_LEVEL = {0: 90.0, 1: 150.0, 2: 90.0, 3: 90.0, 4: 100.0}

# Comportements disponibles
# B1 Mirror   — suit le palier du joueur UNE SEULE FOIS avec latence, puis lock
# B2 Route    — séquence aléatoire de paliers (2-3 transitions max, timers longs)
# B3 Kamikaze — fonce directement sur le joueur en 3D
# B4 Guard    — reste sur son palier de spawn, ne bouge jamais
# B5 Flanking — spawn au palier opposé du joueur, converge UNE FOIS puis lock
# B6 Erratic  — change de palier aléatoirement toutes les 2-4s


# ============================================================
# Tirs ennemis
# ============================================================

class EnemyBolt:
    """Un tir laser ennemi (vert)."""

    SPEED = 80.0    # +30% — plus rapides, moins faciles à éviter
    DAMAGE = 1.0
    HIT_RADIUS = 1.8

    def __init__(self, parent_node, start_pos, direction):
        self.alive = True
        self.direction = Vec3(direction)
        self.direction.normalize()

        self.node = self.make_bolt()
        self.node.reparentTo(parent_node)
        self.node.setPos(start_pos)
        self.node.lookAt(start_pos + self.direction)
        self.node.setLightOff()

    def make_bolt(self):
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("enemy_bolt", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")

        hx, hy, hz = 0.05, 0.6, 0.05
        color_back  = Vec4(0.1, 0.8, 0.1, 1)
        color_front = Vec4(0.4, 1.0, 0.4, 1)

        corners = [
            (-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz),
            (-hx,  hy, -hz), (hx,  hy, -hz), (hx,  hy, hz), (-hx,  hy, hz),
        ]
        colors = [color_back]*4 + [color_front]*4
        for i, c in enumerate(corners):
            vertex.addData3(*c)
            col.addData4(colors[i])

        tris = GeomTriangles(Geom.UHStatic)
        for f in [
            (0,1,2),(0,2,3),(4,6,5),(4,7,6),
            (0,4,5),(0,5,1),(2,6,7),(2,7,3),
            (0,3,7),(0,7,4),(1,5,6),(1,6,2),
        ]:
            tris.addVertices(*f)

        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("enemy_bolt")
        node.addGeom(geom)
        return NodePath(node)

    def update(self, dt):
        if not self.alive:
            return
        self.node.setPos(self.node.getPos() + self.direction * self.SPEED * dt)
        pos = self.node.getPos()
        if pos.getY() < -15 or abs(pos.getX()) > 20 or abs(pos.getZ()) > 15:
            self.destroy()

    def reset(self, parent_node, start_pos, direction):
        """Réutilise ce bolt depuis le pool — pas de création géométrique."""
        self.alive = True
        self.direction = Vec3(direction)
        self.direction.normalize()
        self.node.reparentTo(parent_node)
        self.node.setPos(start_pos)
        self.node.lookAt(start_pos + self.direction)

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.detachNode()   # Détache sans supprimer — retourne au pool

    def cleanup(self):
        """Destruction finale (nettoyage de niveau)."""
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()


# ============================================================
# Classe de base ennemi
# ============================================================

def _make_drop_line(parent):
    """Ligne verticale pointillée de l'ennemi jusqu'à Z=0 — repère de hauteur.
    Dessinée en espace local : de Z=0 (position de l'ennemi) vers Z=-pos.z
    (sol). Mise à jour chaque frame via setScale.
    """
    fmt   = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData("dline", fmt, Geom.UHStatic)
    vw = GeomVertexWriter(vdata, "vertex")
    cw = GeomVertexWriter(vdata, "color")

    # 2 segments discontinus pour effet pointillé (4 points)
    c_top = Vec4(1.0, 1.0, 1.0, 0.55)
    c_bot = Vec4(1.0, 1.0, 1.0, 0.0)   # fondu vers le bas
    vw.addData3(0, 0,  0.0);  cw.addData4(c_top)
    vw.addData3(0, 0, -1.0);  cw.addData4(c_bot)

    lines = GeomLines(Geom.UHDynamic)
    lines.addVertices(0, 1)

    geom = Geom(vdata)
    geom.addPrimitive(lines)
    gn = GeomNode("drop_line")
    gn.addGeom(geom)
    np = NodePath(gn)
    np.setRenderModeThickness(1.5)
    np.setTransparency(TransparencyAttrib.MAlpha)
    np.setLightOff()
    np.setBin("fixed", 5)
    np.setDepthWrite(False)
    np.reparentTo(parent)
    np.setPos(0, 0, 0)
    return np


class BaseEnemy:
    """Classe de base pour tous les ennemis."""

    # Overrides dans les sous-classes
    SPEED_BASE = 15.0
    SPEED_CHARGE = 35.0      # Vitesse quand il fonce vers le joueur
    CHARGE_DISTANCE = 60.0   # Distance à laquelle il accélère
    HP = 2
    HIT_RADIUS = 1.8
    FIRE_RANGE = 80.0
    FIRE_COOLDOWN_MIN = 2.0
    FIRE_COOLDOWN_MAX = 5.0
    BOLTS_PER_SHOT = 2       # Nombre de tirs simultanés
    SCORE_VALUE = 100

    MODEL_PATH = None
    MODEL_SCALE = 0.5
    MODEL_H = 0               # Rotation horizontale du modèle
    TARGET_SIZE = 2.0
    COLOR_BOOST = Vec4(1.8, 1.8, 2.0, 1)

    # Comportements disponibles par sous-classe — override
    BEHAVIORS = ["B4"]

    # Cache de modèles par classe
    _model_cache = {}

    def __init__(self, parent_node, start_pos, game=None):
        self.alive = True
        self.hp = self.HP
        self.flash_timer = 0.0
        self.game = game
        self.score_value = self.SCORE_VALUE

        # Drift latéral (X seulement — Z géré par les paliers)
        self.drift_x = random.uniform(-2.5, 2.5)
        self.drift_speed = random.uniform(0.5, 1.5)
        self.drift_time = random.uniform(0, math.pi * 2)

        # Ease-in vitesse au spawn : part lentement, accélère
        self.spawn_age = 0.0
        self.spawn_ease_duration = random.uniform(2.5, 4.5)  # Variée par ennemi

        # Tir
        self.fire_timer = random.uniform(1.0, 3.0)

        # Vitesse actuelle (accélère à l'approche)
        self.current_speed = self.SPEED_BASE

        self.node = self.load_model()
        self.node.reparentTo(parent_node)
        self.node.setPos(start_pos)

        # Initialise le comportement de palier (après setPos)
        self._init_behavior()

    def load_model(self):
        """Charge le modèle .glb/.gltf (caché) ou fallback procédural."""
        class_name = type(self).__name__

        if self.MODEL_PATH and os.path.exists(self.MODEL_PATH) and self.game:
            try:
                if class_name not in BaseEnemy._model_cache:
                    template = self.game.loader.loadModel(self.MODEL_PATH)
                    if template:
                        BaseEnemy._model_cache[class_name] = template
                        print(f"[{class_name}] Modèle 3D chargé: {self.MODEL_PATH}")

                        # Log les dimensions pour calibrer le scale
                        bounds = template.getTightBounds()
                        if bounds:
                            bmin, bmax = bounds
                            size = bmax - bmin
                            print(f"[{class_name}] Dimensions brutes: {size}")
                            max_dim = max(size.getX(), size.getY(), size.getZ())
                            # Calcule le scale pour que le modèle fasse TARGET_SIZE
                            if max_dim > 0:
                                auto_scale = self.TARGET_SIZE / max_dim
                                print(f"[{class_name}] Auto-scale: {auto_scale:.4f} (target {self.TARGET_SIZE})")
                                BaseEnemy._model_cache[class_name + "_scale"] = auto_scale

                if class_name in BaseEnemy._model_cache:
                    model = BaseEnemy._model_cache[class_name].copyTo(NodePath(f"{class_name}_inst"))

                    # Utilise l'auto-scale si disponible, sinon MODEL_SCALE
                    scale = BaseEnemy._model_cache.get(class_name + "_scale", self.MODEL_SCALE)
                    model.setScale(scale)
                    model.setH(self.MODEL_H)
                    model.setColorScale(self.COLOR_BOOST)
                    return model
            except Exception as e:
                print(f"[{class_name}] Erreur: {e}")

        return self.create_procedural()

    def create_procedural(self):
        """Fallback procédural — override dans les sous-classes."""
        return self._make_default_shape()

    def _make_box(self, sx, sy, sz, color):
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("box", fmt, Geom.UHStatic)
        vertex = GeomVertexWriter(vdata, "vertex")
        col = GeomVertexWriter(vdata, "color")
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        corners = [
            (-hx,-hy,-hz),(hx,-hy,-hz),(hx,hy,-hz),(-hx,hy,-hz),
            (-hx,-hy,hz),(hx,-hy,hz),(hx,hy,hz),(-hx,hy,hz),
        ]
        for c in corners:
            vertex.addData3(*c)
            col.addData4(color)
        tris = GeomTriangles(Geom.UHStatic)
        for f in [(0,1,2),(0,2,3),(4,6,5),(4,7,6),(0,4,5),(0,5,1),(2,6,7),(2,7,3),(0,3,7),(0,7,4),(1,5,6),(1,6,2)]:
            tris.addVertices(*f)
        geom = Geom(vdata)
        geom.addPrimitive(tris)
        node = GeomNode("box")
        node.addGeom(geom)
        return NodePath(node)

    def _make_default_shape(self):
        root = NodePath("enemy_default")
        box = self._make_box(0.6, 0.6, 0.6, Vec4(0.4, 0.4, 0.45, 1))
        box.reparentTo(root)
        return root

    # ------------------------------------------------------------------
    # Système de paliers
    # ------------------------------------------------------------------

    def _init_behavior(self):
        """Choisit un comportement au spawn et initialise l'état de palier."""
        self.behavior = random.choice(self.BEHAVIORS)
        self.tier_timer = 0.0
        self.tier_route = []
        self.tier_route_idx = 0
        self.tier_moved = False          # True = a déjà changé de palier (B1/B5 lock après 1 fois)
        self.tier_react_delay = 0.0      # Latence avant de réagir au prochain changement
        self.formation_leader = None     # Référence au leader de formation (optionnel)
        self.formation_delay  = 0.0      # Délai supplémentaire pour les followers
        # Transition Z — ease-in exponentiel (t=0→1, démarre lent accélère)
        self.tier_transition_t    = 1.0  # 1.0 = pas de transition en cours
        self.tier_start_z         = 0.0  # Z au moment où la transition a démarré
        self.tier_duration        = 2.2  # Durée d'une transition (secondes)

        # Palier de spawn
        if self.behavior == "B5":
            # Flanking : spawn au palier opposé du joueur
            pz = 0.0
            if self.game and hasattr(self.game, 'player') and self.game.player:
                pz = self.game.player.node.getPos().getZ()
            player_tier = min(range(3), key=lambda i: abs(TIERS[i] - pz))
            self.tier_idx = 2 - player_tier   # palier opposé (0↔2, 1→1)
        else:
            self.tier_idx = random.randint(0, 2)

        self.target_z = TIERS[self.tier_idx]
        self.node.setZ(self.target_z)  # snap immédiat au spawn
        self.tier_start_z = self.target_z

        if self.behavior == "B2":
            # Route courte : 2-3 transitions seulement, timers longs
            n = random.randint(2, 3)
            route = [self.tier_idx]
            for _ in range(n):
                # Évite de rester sur le même palier deux fois de suite
                choices = [t for t in range(3) if t != route[-1]]
                route.append(random.choice(choices))
            self.tier_route = route
            self.tier_route_idx = 0
            self.tier_moves_left = n         # Nombre de transitions restantes
            self.tier_timer = random.uniform(4.0, 7.0)  # Long délai avant première transition

        elif self.behavior == "B1":
            # Mirror : latence avant de réagir au joueur
            self.tier_react_delay = random.uniform(1.5, 4.0)

        elif self.behavior == "B5":
            # Flanking : latence avant de converger
            self.tier_react_delay = random.uniform(1.0, 3.0)

        elif self.behavior == "B6":
            self.tier_timer = random.uniform(2.0, 4.0)   # Lent — changements espacés

    def _update_tier(self, dt, player_pos):
        """Met à jour target_z selon le comportement, puis lerp vers target_z."""
        b = self.behavior

        # ── Leader de formation : suit le leader avec délai ────────────────
        if self.formation_leader is not None and self.formation_leader.alive:
            if self.formation_delay > 0:
                self.formation_delay -= dt
            else:
                self._set_target_z(self.formation_leader.target_z)
            self._apply_tier_ease(dt)
            return

        # ── Comportements autonomes ─────────────────────────────────────────

        if b == "B1":
            # Mirror : attend la latence, bouge UNE FOIS vers le palier du joueur puis lock
            if not self.tier_moved:
                if self.tier_react_delay > 0:
                    self.tier_react_delay -= dt
                elif player_pos:
                    pz = player_pos.getZ()
                    nearest = min(range(3), key=lambda i: abs(TIERS[i] - pz))
                    new_z = TIERS[nearest]
                    if abs(new_z - self.target_z) > 0.1:   # Seulement si palier différent
                        self._set_target_z(new_z)
                        self.tier_moved = True               # Lock — ne bougera plus

        elif b == "B2":
            # Route : transitions limitées, timers longs
            if hasattr(self, 'tier_moves_left') and self.tier_moves_left > 0:
                self.tier_timer -= dt
                if self.tier_timer <= 0:
                    self.tier_route_idx += 1
                    if self.tier_route_idx < len(self.tier_route):
                        self._set_target_z(TIERS[self.tier_route[self.tier_route_idx]])
                        self.tier_moves_left -= 1
                        self.tier_timer = random.uniform(5.0, 9.0)  # Long avant prochain

        elif b == "B3":
            # Kamikaze : suit le Z exact du joueur — transition directe sans ease
            if player_pos:
                self.target_z = player_pos.getZ()
                self.tier_start_z = self.node.getZ()
                self.tier_transition_t = 0.0
                self.tier_duration = 0.6  # Réactif

        elif b == "B4":
            pass  # Garde son palier de spawn — jamais

        elif b == "B5":
            # Flanking : attend, converge UNE FOIS vers le palier du joueur puis lock
            if not self.tier_moved:
                if self.tier_react_delay > 0:
                    self.tier_react_delay -= dt
                elif player_pos:
                    pz = player_pos.getZ()
                    nearest = min(range(3), key=lambda i: abs(TIERS[i] - pz))
                    self._set_target_z(TIERS[nearest])
                    self.tier_moved = True

        elif b == "B6":
            # Erratique : changements espacés (2-4s)
            self.tier_timer -= dt
            if self.tier_timer <= 0:
                choices = [t for t in range(3) if TIERS[t] != self.target_z]
                self._set_target_z(TIERS[random.choice(choices)])
                self.tier_timer = random.uniform(2.0, 4.0)

        # Applique la transition ease-in
        self._apply_tier_ease(dt)

    def _set_target_z(self, new_z):
        """Démarre une nouvelle transition de palier depuis la position courante."""
        if abs(new_z - self.target_z) < 0.1:
            return  # Déjà sur ce palier
        self.tier_start_z = self.node.getZ()
        self.target_z = new_z
        self.tier_transition_t = 0.0
        self.tier_duration = random.uniform(1.8, 2.8)  # Légère variation

    def _apply_tier_ease(self, dt):
        """Courbe ease-in exponentielle : démarre lentement, accélère vers le palier cible."""
        if self.tier_transition_t >= 1.0:
            return  # Transition terminée, position fixe

        self.tier_transition_t = min(1.0, self.tier_transition_t + dt / self.tier_duration)
        t = self.tier_transition_t

        # Ease-in cubique : t³ — démarre très lentement, accélère fort à la fin
        t_eased = t * t * t

        new_z = self.tier_start_z + (self.target_z - self.tier_start_z) * t_eased
        self.node.setZ(new_z)

    # ------------------------------------------------------------------

    def update(self, dt, player_pos=None):
        if not self.alive:
            return None

        # Comportement de palier (Z)
        self._update_tier(dt, player_pos)

        # Ease-in vitesse au spawn : part à 20% de la vitesse, monte en t²
        self.spawn_age += dt
        spawn_t = min(1.0, self.spawn_age / self.spawn_ease_duration)
        spawn_factor = 0.20 + 0.80 * (spawn_t * spawn_t)  # 20% → 100%, ease-in quadratique

        # Accélération à l'approche du joueur
        if player_pos:
            dist = (self.node.getPos() - player_pos).length()
            if dist < self.CHARGE_DISTANCE:
                charge_factor = 1.0 - (dist / self.CHARGE_DISTANCE)
                self.current_speed = (self.SPEED_BASE + (self.SPEED_CHARGE - self.SPEED_BASE) * charge_factor) * spawn_factor
            else:
                self.current_speed = self.SPEED_BASE * spawn_factor
        else:
            self.current_speed = self.SPEED_BASE * spawn_factor

        if self.behavior == "B3" and player_pos:
            # Kamikaze : mouvement 3D direct vers le joueur
            my_pos = self.node.getPos()
            direction = player_pos - my_pos
            dist = direction.length()
            if dist > 0.5:
                direction.normalize()
                self.node.setPos(my_pos + direction * self.current_speed * dt)
        else:
            # Mouvement normal : avance en Y + drift X
            self.node.setY(self.node.getY() - self.current_speed * dt)
            self.drift_time += self.drift_speed * dt
            self.node.setX(self.node.getX() + math.sin(self.drift_time) * self.drift_x * dt)

        # Clamp X (Z clampé par les paliers)
        x = self.node.getX()
        if x < -12:   self.node.setX(-12)
        elif x > 12:  self.node.setX(12)

        # Flash de dégât
        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.flash_timer <= 0:
                self.node.setColorScale(self.COLOR_BOOST)

        if self.node.getY() < -10:
            self.destroy()
            return None

        # Tir
        self.fire_timer -= dt
        if self.fire_timer <= 0 and player_pos is not None:
            return self._try_fire(player_pos)

        return None

    def _try_fire(self, player_pos):
        my_pos = self.node.getPos()
        dist = (my_pos - player_pos).length()
        if dist < self.FIRE_RANGE and my_pos.getY() > player_pos.getY():
            self.fire_timer = random.uniform(self.FIRE_COOLDOWN_MIN, self.FIRE_COOLDOWN_MAX)
            direction = player_pos - my_pos
            direction.setX(direction.getX() + random.uniform(-1.8, 1.8))
            direction.setZ(direction.getZ() + random.uniform(-1.2, 1.2))
            direction.normalize()

            results = []
            offset = 0.4
            if self.BOLTS_PER_SHOT >= 2:
                pos_l = Vec3(my_pos.getX(), my_pos.getY(), my_pos.getZ() + offset)
                pos_r = Vec3(my_pos.getX(), my_pos.getY(), my_pos.getZ() - offset)
                results.append((pos_l, direction))
                results.append((pos_r, direction))
            else:
                results.append((Vec3(my_pos), direction))
            return results

        return None

    def hit(self, damage=1):
        self.hp -= damage
        if self.hp <= 0:
            self.destroy()
            return True
        else:
            self.node.setColorScale(Vec4(3, 3, 3, 1))
            self.flash_timer = 0.1
            return False

    def destroy(self):
        self.alive = False
        if not self.node.isEmpty():
            self.node.removeNode()

    def get_pos(self):
        if self.alive and not self.node.isEmpty():
            return self.node.getPos()
        return None


# ============================================================
# Types d'ennemis
# ============================================================

class TIEFighter(BaseEnemy):
    """TIE Fighter standard — state machine cinématique, squads de 4, virages courbes."""

    # ── États ────────────────────────────────────────────────────────
    S_APPROACH   = 0   # Formation tight vers le joueur
    S_BREAK      = 1   # Bref délai avant le split (wingmen décalés)
    S_ATTACK_RUN = 2   # Attaque directe avec correction de trajectoire
    S_FLANK      = 3   # Balayage latéral one-shot, sort de l'écran
    S_LOOP_BACK  = 4   # Grand arc visible pour revenir en attack run

    # ── Vitesses ─────────────────────────────────────────────────────
    SPEED_APPROACH = 22.0
    SPEED_ATTACK   = 46.0
    SPEED_FLANK    = 52.0
    SPEED_LOOP     = 36.0

    # ── Taux de virage max (°/s) ──────────────────────────────────────
    TURN_APPROACH  = 55.0
    TURN_ATTACK    = 80.0
    TURN_LOOP      = 95.0

    # ── BaseEnemy overrides ───────────────────────────────────────────
    BEHAVIORS          = ["B4"]   # Non utilisé mais requis par BaseEnemy
    SPEED_BASE         = 22.0
    SPEED_CHARGE       = 46.0
    CHARGE_DISTANCE    = 0.0
    HP                 = 2
    HIT_RADIUS         = 1.8
    FIRE_RANGE         = 85.0
    FIRE_COOLDOWN_MIN  = 2.2
    FIRE_COOLDOWN_MAX  = 4.5
    BOLTS_PER_SHOT     = 2
    SCORE_VALUE        = 100

    MODEL_PATH  = "assets/models/tie_fighter/scene.gltf"
    MODEL_SCALE = 0.5
    TARGET_SIZE = 2.0

    # ── Formation offsets spawn [leader, wing1, wing2, wing3] ───────────
    # Espacement ~1/4 d'écran min entre membres (≥9u X, ≥10u Y)
    FORMATION_OFFSETS = [
        Vec3( 0,  0,  0),   # leader — en tête
        Vec3(-9, 10,  1),   # wing1  — arrière gauche
        Vec3( 9, 10, -1),   # wing2  — arrière droit
        Vec3( 0, 20,  3),   # wing3  — loin arrière, légèrement haut
    ]

    # ── Cibles d'approche par rôle (relatif au joueur) ───────────────
    # Chaque TIE vole vers un point fixe dans l'espace joueur.
    # Élimine l'oscillation en chaîne du suivi leader-follower.
    APPROACH_TARGETS = [
        Vec3( 0,  60,  0),   # leader → droit devant
        Vec3(-9,  70,  1),   # wing1  → gauche, légèrement en retrait
        Vec3( 9,  70, -1),   # wing2  → droite, légèrement en retrait
        Vec3( 0,  80,  3),   # wing3  → centre lointain, haut
    ]

    # ── Offsets cible par rôle (attack) ───────────────────────────────
    ATTACK_TARGET_OFFSETS = [
        Vec3( 0.0, 0,  0.0),
        Vec3(-2.5, 0,  0.5),
        Vec3( 2.5, 0, -0.5),
        Vec3( 0.0, 0,  1.5),
    ]
    DIVE_TARGET_OFFSETS = [
        Vec3( 0.0, 0,  0.0),
        Vec3(-2.0, 0,  4.5),
        Vec3( 2.0, 0, -4.0),
        Vec3( 0.0, 0,  5.5),
    ]

    def __init__(self, parent_node, start_pos, game=None):
        super().__init__(parent_node, start_pos, game)
        self.vel           = Vec3(0, -self.SPEED_APPROACH, 0)
        self.target_speed  = self.SPEED_APPROACH
        self.bank_angle    = 0.0
        self._prev_vel_x   = 0.0
        self.state         = self.S_APPROACH
        self.break_pattern = 'attack'
        self.break_role    = 0
        self.break_delay   = 0.0
        self.squad         = None
        self.squad_role    = 0
        self._wp_list      = []   # waypoints courants
        self._wp_idx       = 0
        self._atk_offset   = Vec3(0, 0, 0)
        self._breaking_off = False   # True = phase de dégagement (frôlement)
        self._break_target = Vec3(0, 0, 0)

    def _init_behavior(self):
        """Override — tier system non utilisé par TIEFighter."""
        self.behavior          = "B4"
        self.tier_timer        = 0.0
        self.tier_route        = []
        self.tier_route_idx    = 0
        self.tier_moved        = False
        self.tier_react_delay  = 0.0
        self.formation_leader  = None
        self.formation_delay   = 0.0
        self.tier_transition_t = 1.0
        z = self.node.getPos().getZ() if not self.node.isEmpty() else 0.0
        self.tier_start_z  = z
        self.tier_duration = 2.2
        self.tier_idx      = 1
        self.target_z      = z   # pas de snap de palier

    # ── Steering ──────────────────────────────────────────────────────

    def _steer_toward(self, target_pos, dt, max_turn_deg=75.0):
        """Redirige la vélocité vers target_pos avec taux de virage limité."""
        to_target = target_pos - self.node.getPos()
        dist = to_target.length()
        if dist < 0.5:
            return
        desired_dir = to_target * (1.0 / dist)
        spd = self.vel.length()
        if spd < 0.1:
            self.vel = desired_dir * self.target_speed
            return
        current_dir = self.vel * (1.0 / spd)
        dot   = max(-1.0, min(1.0, current_dir.dot(desired_dir)))
        angle = math.acos(dot)
        if angle < 0.001:
            return
        max_rad = math.radians(max_turn_deg) * dt
        t = min(1.0, max_rad / angle)
        new_dir = Vec3(
            current_dir.getX() + (desired_dir.getX() - current_dir.getX()) * t,
            current_dir.getY() + (desired_dir.getY() - current_dir.getY()) * t,
            current_dir.getZ() + (desired_dir.getZ() - current_dir.getZ()) * t,
        )
        new_dir.normalize()
        self.vel = new_dir * self.target_speed

    # ── Transitions d'état ────────────────────────────────────────────

    def on_break(self, pattern, role, delay):
        """Déclenché par TIESquad quand la formation se split."""
        self.break_pattern = pattern
        self.break_role    = role
        self.break_delay   = delay
        self.state         = self.S_BREAK

    BREAK_OFF_DIST = 30.0   # Distance à laquelle le TIE arrête de viser le joueur

    def _enter_attack(self, player_pos=None):
        self.state         = self.S_ATTACK_RUN
        self.target_speed  = self.SPEED_ATTACK
        self._breaking_off = False
        r = min(self.break_role, 3)
        if self.break_pattern == 'dive':
            self._atk_offset = Vec3(self.DIVE_TARGET_OFFSETS[r])
        else:
            self._atk_offset = Vec3(self.ATTACK_TARGET_OFFSETS[r])

    def _enter_flank(self, player_pos=None):
        """Traversée cinématique : dive vers un côté de l'écran, sweep complet en
        face du joueur, ressort de l'autre côté.  WP1 et WP2 à même profondeur →
        le TIE doit ATTEINDRE WP1 avant de pivoter vers WP2."""
        self.state        = self.S_FLANK
        self.target_speed = self.SPEED_FLANK
        px  = player_pos.getX() if player_pos else 0.0
        py  = player_pos.getY() if player_pos else 0.0
        pz  = player_pos.getZ() if player_pos else self.node.getZ()
        z_off = [0.0, 0.0, 2.5, -2.5]
        sides = [+1, -1, +1, -1]
        s = sides[self.break_role % 4]
        z = z_off[self.break_role % 4]
        # Arc en 3 points : entrée côté s → centre proche joueur → sortie côté -s
        # Le WP central force le TIE à plonger juste devant le joueur
        dz = self.squad.flank_dz if self.squad else random.uniform(-6.0, 6.0)
        self._wp_list = [
            Vec3(px + s * 28,  py + 30, pz + z),        # entrée : côté s, devant
            Vec3(px,           py + 14, pz + dz),        # centre : croise devant + monte/descend
            Vec3(px - s * 30,  py + 26, pz + dz - z),   # sortie : côté -s, conserve la hauteur
        ]
        self._wp_idx = 0

    def _enter_aero_loop(self, player_pos=None):
        """Looping vertical circulaire dans le plan YZ.
        Arc R=15 en 4 WPs à 90° d'intervalle → virages max 45° → steering fluide.
        vitesse réduite à 22 pour rester dans le rayon de virage (r_min ≈ 13u).
        """
        self.state        = self.S_LOOP_BACK
        self.target_speed = 28.0   # r_min = 28/1.66 ≈ 17 < R=18 ✓
        cx  = self.node.getX()
        px  = player_pos.getX() if player_pos else cx
        py  = player_pos.getY() if player_pos else 0.0
        pz  = player_pos.getZ() if player_pos else self.node.getZ()
        sign = self.squad.loop_sign if self.squad else 1
        x_off = [0, -5, 5, -2.5][min(self.break_role, 3)]
        # Cercle R=18, centre (py+65, pz+18) — 4 WPs à 90° → virages 45° max
        self._wp_list = [
            Vec3(px + x_off, py + 47, pz + sign * 18),   # côté joueur, mi-hauteur
            Vec3(px + x_off, py + 65, pz + sign * 36),   # sommet
            Vec3(px + x_off, py + 83, pz + sign * 18),   # côté opposé, mi-hauteur
            Vec3(px + x_off, py + 93, pz),               # réalignement → attack
        ]
        self._wp_idx = 0

    def _enter_loop(self, player_pos):
        """Loop-back après attack run — arc visible sur le côté puis réapproche frontale."""
        self.state        = self.S_LOOP_BACK
        self.target_speed = self.SPEED_LOOP
        cx = self.node.getX()
        cz = self.node.getZ()
        px = player_pos.getX()
        py = player_pos.getY()
        pz = player_pos.getZ()
        side = 1 if cx >= px else -1
        self._wp_list = [
            Vec3(cx + side * 14,             py + 20, cz + 2),
            Vec3(px + side * 18,             py + 52, pz + 1),
            Vec3(px + random.uniform(-6, 6), py + 75, pz + random.uniform(-2, 2)),
        ]
        self._wp_idx = 0

    def _enter_loop_from_flank(self, player_pos):
        """Retour après sweep latéral.
        TIE sort déjà vers +Y (WP2 du flank était devant le joueur) —
        seul un petit arc de recentrage est nécessaire, pas de demi-tour."""
        self.state        = self.S_LOOP_BACK
        self.target_speed = self.SPEED_LOOP
        cx  = self.node.getX()
        px  = player_pos.getX()
        py  = player_pos.getY()
        pz  = player_pos.getZ()
        side = 1 if cx > px else -1
        self._wp_list = [
            Vec3(px + side * 12, py + 52, pz + random.uniform(-1, 1)),
            Vec3(px + side * 6,  py + 76, pz),
        ]
        self._wp_idx = 0

    # ── Update principal ──────────────────────────────────────────────

    def update(self, dt, player_pos=None):
        if not self.alive:
            return None

        s = self.state

        if s == self.S_APPROACH:
            if player_pos:
                # Chaque TIE vole vers son point fixe relatif au joueur.
                # Pas de suivi du leader → pas d'oscillation en chaîne.
                r   = min(self.squad_role, len(self.APPROACH_TARGETS) - 1)
                off = self.APPROACH_TARGETS[r]
                target = Vec3(
                    player_pos.getX() + off.getX(),
                    player_pos.getY() + off.getY(),
                    player_pos.getZ() + off.getZ(),
                )
                self._steer_toward(target, dt, self.TURN_APPROACH)

        elif s == self.S_BREAK:
            self.break_delay -= dt
            if self.break_delay <= 0:
                if self.break_pattern == 'flank':
                    self._enter_flank(player_pos)
                elif self.break_pattern == 'loop':
                    self._enter_aero_loop(player_pos)
                else:
                    self._enter_attack(player_pos)

        elif s == self.S_ATTACK_RUN:
            if player_pos:
                dist_p = (self.node.getPos() - player_pos).length()
                if dist_p < self.BREAK_OFF_DIST:
                    # Phase de dégagement — calculée une seule fois pour éviter l'oscillation
                    if not self._breaking_off:
                        self._breaking_off = True
                        cx = self.node.getX()
                        # Dégagement du côté où le TIE se trouve déjà — passe en frôlant
                        side = 1 if cx >= player_pos.getX() else -1
                        self._break_target = Vec3(
                            player_pos.getX() + side * 11,
                            player_pos.getY() - 22,
                            player_pos.getZ() + random.uniform(-2.0, 2.0),
                        )
                    self._steer_toward(self._break_target, dt, self.TURN_ATTACK)
                else:
                    self._steer_toward(player_pos + self._atk_offset, dt, self.TURN_ATTACK)
                if self.node.getY() < player_pos.getY() - 8:
                    self._enter_loop(player_pos)

        elif s == self.S_FLANK:
            if self._wp_idx < len(self._wp_list):
                wp = self._wp_list[self._wp_idx]
                if (wp - self.node.getPos()).length() < 4.0:
                    self._wp_idx += 1
                else:
                    self._steer_toward(wp, dt, 95.0)
            else:
                # Après le sweep, arc de retour par le flanc
                if player_pos:
                    self._enter_loop_from_flank(player_pos)
                else:
                    self.destroy()
                    return None

        elif s == self.S_LOOP_BACK:
            if self._wp_idx < len(self._wp_list):
                wp = self._wp_list[self._wp_idx]
                if (wp - self.node.getPos()).length() < 10.0:
                    self._wp_idx += 1
                else:
                    self._steer_toward(wp, dt, self.TURN_LOOP)
            else:
                self._enter_attack(player_pos)

        # ── Physique ──────────────────────────────────────────────────
        self.node.setPos(self.node.getPos() + self.vel * dt)

        # ── Orientation : face à la vélocité + banking ────────────────
        spd = self.vel.length()
        if spd > 1.0:
            fwd = self.node.getPos() + self.vel * 0.4
            self.node.lookAt(Point3(fwd.getX(), fwd.getY(), fwd.getZ()))
        dv_x = self.vel.getX() - self._prev_vel_x
        raw_bank = max(-65.0, min(65.0, (dv_x / max(dt, 0.001)) * 2.8))
        self.bank_angle += (raw_bank - self.bank_angle) * min(1.0, dt * 3.5)
        self.node.setR(self.bank_angle)
        self._prev_vel_x = self.vel.getX()

        # Flash dégât
        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.flash_timer <= 0:
                self.node.setColorScale(self.COLOR_BOOST)

        # Culling — derrière la caméra ou trop loin sur les côtés
        # En flank/loop le TIE sort volontairement loin en X, on ne culle pas
        pos = self.node.getPos()
        x_limit = 55 if self.state in (self.S_FLANK, self.S_LOOP_BACK) else 34
        if pos.getY() < -18 or abs(pos.getX()) > x_limit:
            self.destroy()
            return None

        # Tir — uniquement en phase active
        self.fire_timer -= dt
        if self.fire_timer <= 0 and player_pos is not None:
            if self.state in (self.S_ATTACK_RUN, self.S_LOOP_BACK, self.S_FLANK):
                return self._try_fire(player_pos)
            else:
                self.fire_timer = random.uniform(self.FIRE_COOLDOWN_MIN, self.FIRE_COOLDOWN_MAX)

        return None

    def _try_fire(self, player_pos):
        my_pos = self.node.getPos()
        # Ne tire que quand le TIE est devant le joueur (pas par derrière)
        if my_pos.getY() <= player_pos.getY():
            self.fire_timer = random.uniform(self.FIRE_COOLDOWN_MIN, self.FIRE_COOLDOWN_MAX)
            return None
        dist = (my_pos - player_pos).length()
        if dist < self.FIRE_RANGE:
            self.fire_timer = random.uniform(self.FIRE_COOLDOWN_MIN, self.FIRE_COOLDOWN_MAX)
            direction = player_pos - my_pos
            direction.setX(direction.getX() + random.uniform(-1.0, 1.0))
            direction.setZ(direction.getZ() + random.uniform(-0.8, 0.8))
            direction.normalize()
            off = 0.4
            return [
                (Vec3(my_pos.getX(), my_pos.getY(), my_pos.getZ() + off), direction),
                (Vec3(my_pos.getX(), my_pos.getY(), my_pos.getZ() - off), direction),
            ]
        return None

    def create_procedural(self):
        root    = NodePath("tie_fighter")
        cockpit = self._make_box(0.6, 0.6, 0.6, Vec4(0.3, 0.3, 0.35, 1))
        cockpit.reparentTo(root)
        for y_sign in [-1, 1]:
            panel = self._make_box(0.06, 0.06, 1.6, Vec4(0.25, 0.25, 0.3, 1))
            panel.reparentTo(root)
            panel.setPos(0, 0.7 * y_sign, 0)
        root.setH(90)
        return root


# ============================================================
# Escadron TIE — coordination de 4 TIE Fighters
# ============================================================

class TIESquad:
    """4 TIE Fighters (leader + 3 wingmen) — formation, break, attaque coordonnée."""

    BREAK_DISTANCE = 80.0   # Distance Y joueur → trigger break

    # PATTERNS =  ['attack', 'attack', 'flank', 'loop', 'dive']

    PATTERNS =  ['flank', 'loop']
    

    def __init__(self):
        self.leader  = None
        self.wingmen = []
        self.broken  = False

    @property
    def all_members(self):
        m = []
        if self.leader:
            m.append(self.leader)
        m.extend(self.wingmen)
        return m

    def trigger_break(self, player_pos):
        """Déclenche le split — appelé quand le joueur tire sur la formation."""
        if self.broken:
            return
        self._do_break(player_pos)

    def check_break(self, player_pos):
        """Filet de sécurité — break forcé si le squad passe très près sans avoir été visé."""
        if self.broken or player_pos is None:
            return
        anchor = (self.leader if (self.leader and self.leader.alive)
                  else next((w for w in self.wingmen if w.alive), None))
        if anchor is None:
            return
        if anchor.node.getPos().getY() - player_pos.getY() < 40.0:
            self._do_break(player_pos)

    def _do_break(self, player_pos):
        pattern = random.choice(self.PATTERNS)
        self.broken    = True
        self.flank_dz  = random.uniform(-6.0, 6.0)   # partagé — flank
        self.loop_sign = random.choice([-1, 1])       # partagé — loop (tous montent ou tous descendent)
        living = [m for m in self.all_members
                  if m.alive and m.state == TIEFighter.S_APPROACH]
        for i, member in enumerate(living):
            delay = (0.38 * i + random.uniform(0.0, 0.22)) if i > 0 else 0.0
            member.on_break(pattern, role=i, delay=delay)


class TIEInterceptor(BaseEnemy):
    """TIE Interceptor — rapide et agressif. Route imprévisible ou kamikaze."""
    BEHAVIORS = ["B2", "B2", "B3"]   # 2/3 route, 1/3 kamikaze
    SPEED_BASE = 25.0
    SPEED_CHARGE = 80.0       # Ultra rapide en charge
    CHARGE_DISTANCE = 110.0   # Fonce de très loin
    HP = 1
    HIT_RADIUS = 1.5
    FIRE_COOLDOWN_MIN = 1.5
    FIRE_COOLDOWN_MAX = 3.0
    BOLTS_PER_SHOT = 1
    SCORE_VALUE = 150

    MODEL_PATH = "assets/models/tie_interceptor/scene.gltf"
    MODEL_SCALE = 0.5
    TARGET_SIZE = 1.8         # Un peu plus petit que le TIE standard

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Drift X plus agressif (Z géré par les paliers)
        self.drift_x = random.uniform(-5.0, 5.0)
        self.drift_speed = random.uniform(1.5, 3.0)

    def create_procedural(self):
        """Interceptor procédural — ailes en pointe."""
        root = NodePath("tie_interceptor")
        cockpit = self._make_box(0.5, 0.5, 0.5, Vec4(0.35, 0.35, 0.4, 1))
        cockpit.reparentTo(root)
        # Ailes en pointe (triangulaires approximées)
        wing_color = Vec4(0.3, 0.3, 0.35, 1)
        for y_sign in [-1, 1]:
            wing = self._make_box(0.04, 0.04, 1.4, wing_color)
            wing.reparentTo(root)
            wing.setPos(0.2, 0.6 * y_sign, 0)
            wing.setP(15 * y_sign)

            wing2 = self._make_box(0.04, 0.04, 1.4, wing_color)
            wing2.reparentTo(root)
            wing2.setPos(-0.2, 0.6 * y_sign, 0)
            wing2.setP(-15 * y_sign)
        root.setH(90)
        return root


class TIEBomber(BaseEnemy):
    """TIE Bomber — lent, résistant. Garde son palier et tire lourd."""
    BEHAVIORS = ["B4", "B4", "B1"]   # Surtout guard, parfois mirror
    SPEED_BASE = 10.0
    SPEED_CHARGE = 30.0       # Même le bomber accélère
    CHARGE_DISTANCE = 80.0
    HP = 5
    HIT_RADIUS = 2.2
    FIRE_COOLDOWN_MIN = 3.0
    FIRE_COOLDOWN_MAX = 6.0
    BOLTS_PER_SHOT = 2
    SCORE_VALUE = 250

    MODEL_PATH = "assets/models/tie_bomber/scene.gltf"
    MODEL_SCALE = 0.5
    TARGET_SIZE = 2.5         # Plus gros que les autres

    def create_procedural(self):
        """Bomber procédural — double cockpit."""
        root = NodePath("tie_bomber")
        # Double pod
        pod1 = self._make_box(0.6, 0.7, 0.6, Vec4(0.3, 0.3, 0.35, 1))
        pod1.reparentTo(root)
        pod1.setPos(0, -0.3, 0)
        pod2 = self._make_box(0.6, 0.7, 0.6, Vec4(0.28, 0.28, 0.33, 1))
        pod2.reparentTo(root)
        pod2.setPos(0, 0.3, 0)
        # Panels
        for y_sign in [-1, 1]:
            panel = self._make_box(0.06, 0.08, 1.8, Vec4(0.25, 0.25, 0.3, 1))
            panel.reparentTo(root)
            panel.setPos(0, 0.8 * y_sign, 0)
        root.setH(90)
        return root


# ============================================================
# Nouveaux types d'ennemis — V2
# ============================================================

class ImperialShuttle(BaseEnemy):
    """Imperial Shuttle — lent, très résistant. Flanking tactique."""
    BEHAVIORS = ["B5", "B5", "B4"]   # Flanking ou garde
    SPEED_BASE = 8.0
    SPEED_CHARGE = 20.0
    CHARGE_DISTANCE = 80.0
    HP = 8
    HIT_RADIUS = 2.8
    FIRE_COOLDOWN_MIN = 2.0
    FIRE_COOLDOWN_MAX = 4.0
    BOLTS_PER_SHOT = 2
    SCORE_VALUE = 500

    MODEL_PATH = None
    TARGET_SIZE = 3.5

    def create_procedural(self):
        root = NodePath("shuttle")
        c_hull  = Vec4(0.42, 0.42, 0.47, 1)
        c_dark  = Vec4(0.30, 0.30, 0.34, 1)
        c_metal = Vec4(0.50, 0.50, 0.55, 1)
        # Fuselage central
        body = self._make_box(0.55, 1.8, 0.40, c_hull)
        body.reparentTo(root)
        # Cockpit pod (avant)
        cock = self._make_box(0.42, 0.55, 0.35, c_dark)
        cock.reparentTo(root)
        cock.setPos(0, -1.0, 0.12)
        # Dérive dorsale (empennage vertical)
        fin = self._make_box(0.06, 1.0, 1.6, c_hull)
        fin.reparentTo(root)
        fin.setPos(0, 0.2, 0.55)
        # Ailes principales (grandes, angled upward)
        for x_s in [-1, 1]:
            w = self._make_box(2.2, 0.06, 0.55, c_hull)
            w.reparentTo(root)
            w.setPos(x_s * 1.25, 0.1, 0.1)
            w.setR(x_s * -20)
        # Ailerons secondaires (petits, bas)
        for x_s in [-1, 1]:
            sw = self._make_box(1.2, 0.05, 0.32, c_dark)
            sw.reparentTo(root)
            sw.setPos(x_s * 0.7, 0.4, -0.22)
        # Nacelle moteur (arrière)
        eng = self._make_box(0.38, 0.55, 0.38, c_metal)
        eng.reparentTo(root)
        eng.setPos(0, 1.0, -0.05)
        return root


class AttackBomber(BaseEnemy):
    """Attack Bomber — plus lourd que le TIE Bomber, très résistant, triple tir. Garde."""
    BEHAVIORS = ["B4"]   # Toujours guard — tire depuis une position fixe
    SPEED_BASE = 7.0
    SPEED_CHARGE = 18.0
    CHARGE_DISTANCE = 70.0
    HP = 10
    HIT_RADIUS = 2.6
    FIRE_COOLDOWN_MIN = 2.5
    FIRE_COOLDOWN_MAX = 5.0
    BOLTS_PER_SHOT = 3
    SCORE_VALUE = 400

    MODEL_PATH = None
    TARGET_SIZE = 3.2

    def _try_fire(self, player_pos):
        """Triple tir en éventail."""
        my_pos = self.node.getPos()
        dist = (my_pos - player_pos).length()
        if dist < self.FIRE_RANGE and my_pos.getY() > player_pos.getY():
            self.fire_timer = random.uniform(self.FIRE_COOLDOWN_MIN, self.FIRE_COOLDOWN_MAX)
            base_dir = player_pos - my_pos
            base_dir.normalize()
            results = []
            for spread in [-0.6, 0.0, 0.6]:
                d = Vec3(base_dir.getX() + spread * 0.25,
                         base_dir.getY(),
                         base_dir.getZ() + random.uniform(-0.3, 0.3))
                d.normalize()
                results.append((Vec3(my_pos.getX() + spread, my_pos.getY(), my_pos.getZ()), d))
            return results
        return None

    def create_procedural(self):
        root = NodePath("attack_bomber")
        c_body = Vec4(0.26, 0.26, 0.30, 1)
        c_pod  = Vec4(0.22, 0.22, 0.26, 1)
        c_wing = Vec4(0.20, 0.20, 0.24, 1)
        # 3 pods en triangle
        for i, (px, pz) in enumerate([(0, 0.15), (-0.75, -0.20), (0.75, -0.20)]):
            pod = self._make_box(0.58, 1.1, 0.52, c_pod if i > 0 else c_body)
            pod.reparentTo(root)
            pod.setPos(px, 0, pz)
        # Passerelle horizontale
        bridge = self._make_box(1.7, 0.22, 0.16, c_body)
        bridge.reparentTo(root)
        bridge.setPos(0, 0.1, -0.20)
        # Grands panneaux alaires
        for y_s in [-1, 1]:
            panel = self._make_box(0.07, 0.10, 2.5, c_wing)
            panel.reparentTo(root)
            panel.setPos(0, 0.9 * y_s, 0)
        root.setH(90)
        return root


class ProbeDroid(BaseEnemy):
    """Probe Droid — rapide, erratique, kamikaze. Le plus imprévisible."""
    BEHAVIORS = ["B6", "B6", "B3"]   # Erratique ou kamikaze
    SPEED_BASE = 22.0
    SPEED_CHARGE = 58.0
    CHARGE_DISTANCE = 130.0
    HP = 2
    HIT_RADIUS = 1.2
    FIRE_COOLDOWN_MIN = 0.8
    FIRE_COOLDOWN_MAX = 2.2
    BOLTS_PER_SHOT = 1
    SCORE_VALUE = 200

    MODEL_PATH = None
    TARGET_SIZE = 1.5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Drift X très agressif + changement de palier erratique (B6)
        self.drift_x = random.uniform(-8.0, 8.0)
        self.drift_speed = random.uniform(3.0, 6.5)
        self.drift_time = random.uniform(0, math.pi * 2)

    def create_procedural(self):
        root = NodePath("probe_droid")
        c_body = Vec4(0.08, 0.08, 0.10, 1)
        c_arm  = Vec4(0.14, 0.14, 0.17, 1)
        c_eye  = Vec4(0.90, 0.10, 0.05, 1)
        c_sens = Vec4(0.12, 0.12, 0.15, 1)
        # Corps principal (sphère approx → cube arrondi)
        body = self._make_box(0.65, 0.65, 0.65, c_body)
        body.reparentTo(root)
        # 4 bras en croix (±X et ±Z)
        for bx, bz, lx, lz in [
            ( 0.52, 0,    0.75, 0.06),
            (-0.52, 0,    0.75, 0.06),
            (0,  0.52,    0.06, 0.75),
            (0, -0.52,    0.06, 0.75),
        ]:
            arm = self._make_box(lx, 0.06, lz, c_arm)
            arm.reparentTo(root)
            arm.setPos(bx, 0, bz)
        # Capteurs sensoriels (petites boxes aux extrémités)
        for px, pz in [(1.0, 0), (-1.0, 0), (0, 1.0), (0, -1.0)]:
            s = self._make_box(0.14, 0.12, 0.14, c_sens)
            s.reparentTo(root)
            s.setPos(px, 0, pz)
        # Oeil frontal rouge
        eye = self._make_box(0.22, 0.14, 0.22, c_eye)
        eye.reparentTo(root)
        eye.setPos(0, -0.40, 0.06)
        # Antenne dorsale
        ant = self._make_box(0.06, 0.06, 0.55, c_arm)
        ant.reparentTo(root)
        ant.setPos(0, 0, 0.62)
        return root


class GroundTurret(BaseEnemy):
    """Tourelle sol — stationnaire, défile avec le monde, vise le joueur."""
    SPEED_BASE = 0.0
    SPEED_CHARGE = 0.0
    CHARGE_DISTANCE = 0.0
    HP = 6
    HIT_RADIUS = 1.6
    FIRE_COOLDOWN_MIN = 1.5
    FIRE_COOLDOWN_MAX = 3.2
    BOLTS_PER_SHOT = 1
    SCORE_VALUE = 300
    TARGET_SIZE = 2.0

    GROUND_Z = -5.2       # Plancher de jeu
    SCROLL_SPEED = 14.0   # Vitesse de défilement au sol (inférieure aux ennemis volants)

    def __init__(self, parent_node, start_pos, game=None):
        # Force au niveau du sol
        fp = Point3(start_pos.getX(), start_pos.getY(), self.GROUND_Z)
        super().__init__(parent_node, fp, game)
        self.drift_x = 0.0
        self.drift_z = 0.0
        self._scroll_y = start_pos.getY()

    def create_procedural(self):
        root = NodePath("ground_turret")
        c_base   = Vec4(0.32, 0.28, 0.24, 1)
        c_metal  = Vec4(0.24, 0.22, 0.18, 1)
        c_barrel = Vec4(0.18, 0.16, 0.14, 1)
        c_detail = Vec4(0.45, 0.30, 0.10, 1)  # Voyant ambre
        # Plaque de base
        base = self._make_box(1.5, 1.2, 0.22, c_base)
        base.reparentTo(root)
        base.setPos(0, 0, -0.28)
        # Corps rotatif
        body = self._make_box(0.75, 0.75, 0.48, c_metal)
        body.reparentTo(root)
        body.setPos(0, 0, 0.08)
        # Canon principal
        barrel = self._make_box(0.18, 0.18, 1.15, c_barrel)
        barrel.reparentTo(root)
        barrel.setPos(0, -0.18, 0.70)
        barrel.setP(-18)
        # Supports latéraux
        for x_s in [-1, 1]:
            sup = self._make_box(0.10, 0.08, 0.45, c_metal)
            sup.reparentTo(root)
            sup.setPos(x_s * 0.38, 0, 0.18)
        # Voyant d'activité (orange)
        light = self._make_box(0.10, 0.10, 0.10, c_detail)
        light.reparentTo(root)
        light.setPos(0, -0.40, 0.30)
        return root

    def update(self, dt, player_pos=None):
        if not self.alive:
            return None
        # Défilement monde (pas de drift)
        self.node.setY(self.node.getY() - self.SCROLL_SPEED * dt)
        # Rotation horizontale vers le joueur (visée)
        if player_pos:
            my_pos = self.node.getPos()
            dx = player_pos.getX() - my_pos.getX()
            dz = player_pos.getZ() - my_pos.getZ()
            angle = math.degrees(math.atan2(-dx, dz + 3.0))
            self.node.setH(angle)
        # Flash dégât
        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.flash_timer <= 0:
                self.node.setColorScale(self.COLOR_BOOST)
        if self.node.getY() < -10:
            self.destroy()
            return None
        # Tir
        self.fire_timer -= dt
        if self.fire_timer <= 0 and player_pos is not None:
            return self._turret_fire(player_pos)
        return None

    def _turret_fire(self, player_pos):
        """Tire vers le joueur depuis le sol — pas de restriction d'angle."""
        my_pos = self.node.getPos()
        dist = (my_pos - player_pos).length()
        if dist < self.FIRE_RANGE:
            self.fire_timer = random.uniform(self.FIRE_COOLDOWN_MIN, self.FIRE_COOLDOWN_MAX)
            direction = player_pos - my_pos
            direction += Vec3(random.uniform(-0.8, 0.8), 0, random.uniform(-0.4, 0.4))
            direction.normalize()
            bolt_pos = Vec3(my_pos.getX(), my_pos.getY(), my_pos.getZ() + 0.90)
            return [(bolt_pos, direction)]
        return None


# ============================================================
# Formations
# ============================================================

class Formation:
    """Définit un pattern de spawn pour un groupe d'ennemis."""

    @staticmethod
    def v_formation(center_x, center_z, count, spacing=2.5):
        """Formation en V."""
        positions = []
        for i in range(count):
            side = 1 if i % 2 == 0 else -1
            row = (i + 1) // 2
            x = center_x + side * row * spacing
            # Clamp X pour rester dans les bounds
            x = max(-8, min(8, x))
            z = center_z + row * spacing * 0.3
            y_offset = row * 6
            positions.append((x, y_offset, z))
        return positions

    @staticmethod
    def line_formation(center_x, center_z, count, spacing=3.0):
        """Formation en ligne horizontale."""
        positions = []
        start_x = center_x - (count - 1) * spacing / 2
        for i in range(count):
            x = max(-8, min(8, start_x + i * spacing))
            positions.append((x, 0, center_z))
        return positions

    @staticmethod
    def pincer_formation(count):
        """Attaque en tenaille — ennemis arrivent des côtés."""
        positions = []
        per_side = count // 2
        for i in range(per_side):
            positions.append((-6 - i * 1, i * 10, random.uniform(-2, 2)))
        for i in range(count - per_side):
            positions.append((6 + i * 1, i * 10, random.uniform(-2, 2)))
        return positions

    @staticmethod
    def swarm_formation(center_x, center_z, count):
        """Essaim aléatoire concentré."""
        positions = []
        for _ in range(count):
            x = max(-8, min(8, center_x + random.uniform(-5, 5)))
            z = max(-5, min(5, center_z + random.uniform(-3, 3)))
            y_offset = random.uniform(0, 20)
            positions.append((x, y_offset, z))
        return positions


# ============================================================
# Vagues par niveau — définies dans src/wave_config.py
# ============================================================


# ============================================================
# Spawner
# ============================================================

class EnemySpawner:
    """Gère le spawn, les tirs ennemis, et les vagues."""

    SPAWN_DEPTH = 200.0
    MAX_ENEMIES = 24   # Augmenté pour accommoder les squads de 4 TIE

    def __init__(self, game, level=1):
        self.game = game
        self.level = level
        self.wave_defs = get_wave_defs_for_level(level)

        self.enemies = []
        self.enemy_bolts = []
        self._bolt_pool = []
        self.squads = []            # TIESquads actifs
        self.spawn_timer = 2.0
        self.score = 0
        self.wave = 1
        self.wave_enemies_to_spawn = []
        self.spawn_index = 0
        self.spawn_interval = 0.5
        self.wave_started = False
        self.last_kill_pos = None
        self.last_kill_class = None

        self._prepare_wave()

    @staticmethod
    def _sector_offsets(count):
        """Divise le plan XZ en N zones et retourne un centre par entrée.

        1 entrée → centre écran
        2 entrées → moitié gauche / moitié droite
        4 entrées → 4 quadrants (X±, Z±)
        etc.
        """
        X, Z = 8.0, 2.5   # demi-largeur / demi-hauteur des zones spawn

        base = {
            1: [(  0,    0)],
            2: [( -X,    0), (  X,    0)],
            3: [( -X,    0), (  0,    0), (  X,   0)],
            4: [( -X,    Z), (  X,    Z), ( -X,  -Z), (  X,  -Z)],
            5: [( -X,    Z), (  0,    Z), (  X,   Z), (-X*0.6, -Z), (X*0.6, -Z)],
            6: [( -X,    Z), (  0,    Z), (  X,   Z), ( -X,   -Z), (   0,  -Z), (X, -Z)],
        }

        xz_list = base.get(count)
        if xz_list is None:
            # Grille automatique pour N > 6
            cols = math.ceil(math.sqrt(count))
            rows = math.ceil(count / cols)
            xz_list = []
            for i in range(count):
                c, r = i % cols, i // cols
                x = ((c / max(1, cols - 1)) - 0.5) * 2 * X
                z = ((r / max(1, rows - 1)) - 0.5) * 2 * Z
                xz_list.append((x, z))

        # Léger décalage Y aléatoire pour le stagger de spawn (profondeur)
        return [(x, random.uniform(0, 8), z) for x, z in xz_list]

    def _prepare_wave(self):
        """Prépare la vague courante."""
        wave_idx = min(self.wave - 1, len(self.wave_defs) - 1)
        wave_def = self.wave_defs[wave_idx]

        enemy_classes = list(wave_def["enemies"])
        delay_before   = wave_def.get("delay_before",   1.5)
        spawn_interval = wave_def.get("spawn_interval", 0.5)

        # Pour les vagues au-delà des définitions, on scale
        if self.wave > len(self.wave_defs):
            extra = self.wave - len(self.wave_defs)
            pool = get_escalation_pool(self.level)
            for _ in range(extra * 2):
                enemy_classes.append(random.choice(pool))

        offsets = self._sector_offsets(len(enemy_classes))

        self.wave_enemies_to_spawn = list(zip(enemy_classes, offsets))
        self.spawn_index = 0
        self.spawn_timer = delay_before
        self.spawn_interval = spawn_interval
        self.wave_started = True

    def update(self, dt, laser_system, player_pos):
        # Spawn progressif de la vague
        self.spawn_timer -= dt
        if self.spawn_timer <= 0 and self.spawn_index < len(self.wave_enemies_to_spawn):
            next_class = self.wave_enemies_to_spawn[self.spawn_index][0]
            slots = 4 if next_class is TIEFighter else 1
            if len(self.enemies) + slots <= self.MAX_ENEMIES:
                self._spawn_next()
                self.spawn_timer = self.spawn_interval

        # Update ennemis
        for enemy in self.enemies:
            fire_result = enemy.update(dt, player_pos)
            if fire_result is not None:
                for pos, direction in fire_result:
                    if self._bolt_pool:
                        bolt = self._bolt_pool.pop()
                        bolt.reset(self.game.render, pos, direction)
                    else:
                        bolt = EnemyBolt(self.game.render, pos, direction)
                    self.enemy_bolts.append(bolt)

        # Update tirs ennemis
        for bolt in self.enemy_bolts:
            bolt.update(dt)

        # Détection : laser joueur dans la zone d'un squad → break de formation
        for bolt in laser_system.get_bolts():
            if not bolt.alive:
                continue
            bpos = bolt.node.getPos()
            for squad in self.squads:
                if squad.broken:
                    continue
                for member in squad.all_members:
                    if not member.alive:
                        continue
                    epos = member.get_pos()
                    if epos is None:
                        continue
                    # Laser en dessous de l'ennemi et proche (laser monte en +Y vers les ennemis)
                    if bpos.getY() < epos.getY():
                        dist_fwd = epos.getY() - bpos.getY()
                        if (dist_fwd < 65.0
                                and abs(bpos.getX() - epos.getX()) < 7.0
                                and abs(bpos.getZ() - epos.getZ()) < 5.0):
                            squad.trigger_break(player_pos)
                            break   # un seul trigger par squad par frame

        # Filet de sécurité distance + nettoyage squads morts
        for squad in self.squads:
            squad.check_break(player_pos)
        self.squads = [s for s in self.squads if any(m.alive for m in s.all_members)]

        # Collisions
        self.check_collisions(laser_system, player_pos)

        # Nettoie — recycle les bolts morts vers le pool
        live_bolts = []
        for b in self.enemy_bolts:
            if b.alive:
                live_bolts.append(b)
            else:
                self._bolt_pool.append(b)
        self.enemy_bolts = live_bolts
        self.enemies = [e for e in self.enemies if e.alive]

        # Vague terminée ? (seulement si on a fini de tout spawner ET plus d'ennemis)
        if (self.wave_started
                and self.spawn_index >= len(self.wave_enemies_to_spawn)
                and len(self.wave_enemies_to_spawn) > 0
                and len(self.enemies) == 0):
            self.next_wave()

    def _spawn_next(self):
        """Spawn le prochain ennemi. TIEFighter → squad de 4, autres → spawn normal."""
        if self.spawn_index >= len(self.wave_enemies_to_spawn):
            return

        enemy_class, (off_x, off_y, off_z) = self.wave_enemies_to_spawn[self.spawn_index]

        if enemy_class is TIEFighter:
            self._spawn_tie_squad(off_x, off_y, off_z)
            return

        pos   = Point3(off_x, self.SPAWN_DEPTH + off_y, off_z)
        enemy = enemy_class(self.game.render, pos, game=self.game)

        # Formation leader pour les types qui gardent un palier
        if enemy.behavior in ("B1", "B4"):
            leader = None
            follower_count = 0
            for e in self.enemies:
                if type(e) == enemy_class and e.behavior == enemy.behavior and e.alive:
                    if leader is None:
                        leader = e
                    follower_count += 1
            if leader is not None:
                enemy.formation_leader = leader
                enemy.formation_delay = follower_count * random.uniform(0.3, 0.6)

        self.enemies.append(enemy)
        self.spawn_index += 1

    def _spawn_tie_squad(self, off_x, off_y, off_z):
        """Crée un squad de 4 TIE Fighters en formation tight."""
        squad = TIESquad()
        for i, foff in enumerate(TIEFighter.FORMATION_OFFSETS):
            pos = Point3(
                off_x + foff.getX(),
                self.SPAWN_DEPTH + off_y + foff.getY(),
                off_z + foff.getZ(),
            )
            tie = TIEFighter(self.game.render, pos, game=self.game)
            tie.squad      = squad
            tie.squad_role = i
            if i == 0:
                squad.leader = tie
            else:
                squad.wingmen.append(tie)
            self.enemies.append(tie)
        self.squads.append(squad)
        self.spawn_index += 1

    def check_player_hit(self, player_pos):
        damage = 0
        hit_positions = []

        # Tirs ennemis → joueur
        for bolt in self.enemy_bolts:
            if not bolt.alive:
                continue
            bolt_pos = bolt.node.getPos()
            dist = (bolt_pos - player_pos).length()
            if dist < bolt.HIT_RADIUS:
                damage += bolt.DAMAGE
                hit_positions.append(Vec3(bolt_pos))
                bolt.destroy()

        # Collision corps-à-corps TIE → joueur
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            epos = enemy.get_pos()
            if epos is None:
                continue
            dx = epos.getX() - player_pos.getX()
            dz = epos.getZ() - player_pos.getZ()
            dy = epos.getY() - player_pos.getY()
            dist = (dx*dx + dz*dz + dy*dy*0.3) ** 0.5
            if dist < enemy.HIT_RADIUS + 1.2:
                damage += 3
                hit_positions.append(Vec3(epos))
                enemy.hp = 0
                enemy.destroy()
                self.last_kill_pos = Vec3(epos)

        return damage, hit_positions

    def check_collisions(self, laser_system, player_pos=None):
        fog_onset = FOG_ONSET_BY_LEVEL.get(self.level, 999.0)
        for bolt in laser_system.get_bolts():
            if not bolt.alive:
                continue
            bolt_pos = bolt.node.getPos()
            for enemy in self.enemies:
                if not enemy.alive:
                    continue
                enemy_pos = enemy.get_pos()
                if enemy_pos is None:
                    continue
                # Invulnérable dans le fog — on ne peut pas tuer ce qu'on ne voit pas
                if player_pos is not None:
                    if enemy_pos.getY() - player_pos.getY() > fog_onset:
                        continue
                dist = (bolt_pos - enemy_pos).length()
                if dist < enemy.HIT_RADIUS + 0.5:  # Plus généreux
                    destroyed = enemy.hit(bolt.DAMAGE)
                    bolt.destroy()
                    if destroyed:
                        self.score += enemy.score_value
                        self.last_kill_pos = Vec3(enemy_pos)
                        self.last_kill_class = enemy.__class__.__name__
                    break

    def next_wave(self):
        self.wave += 1
        self._prepare_wave()

    def get_enemy_count(self):
        remaining = max(0, len(self.wave_enemies_to_spawn) - self.spawn_index)
        return len(self.enemies) + remaining

    def stop_spawning(self):
        """Arrête le spawn — utilisé pour le boss."""
        self.wave_enemies_to_spawn = []
        self.spawn_index = 0
        self.wave_started = False
