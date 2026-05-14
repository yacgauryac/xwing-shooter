# X-Wing Shooter — Spécifications & Historique des versions

## Vue d'ensemble

Rail shooter 3D en Python/Panda3D, thème Star Wars. Le joueur pilote un X-Wing contre des vagues de TIE Fighters, avec une progression de difficulté et un boss. L'objectif est de maximiser son score et d'entrer dans le leaderboard top 10.

**Stack :** Python 3, Panda3D 1.10.14+, panda3d-gltf 0.13+  
**Plateforme :** Windows / Linux  
**Fenêtre :** Plein écran natif au lancement (F11 = bascule fenêtré/plein écran)

---

## Architecture générale

```
main.py
  └── Game (ShowBase)
        ├── Player         — X-Wing, mouvement, barrel roll, crosshair
        ├── EnemySpawner   — 3 types TIE, formations, vagues
        ├── LaserSystem    — tir, surchauffe, auto-aim
        ├── TorpedoSystem  — missiles homing avec lock-on
        ├── ForceAbility   — bullet-time 0.3x, 6s
        ├── BossTIEAdvanced — 50 HP, 3 phases
        ├── Environment    — astéroïdes, nébuleuses, debris
        ├── Starfield      — 1000 étoiles avec traînées de vitesse
        ├── HUD            — overlay holographique orange/ambre
        ├── ExplosionManager — particules, débris, popups score
        ├── SoundManager   — pooling audio + fallback procédural
        ├── PowerUpManager — collectibles (torpille, réparation)
        ├── MainMenu       — titre, options, leaderboard
        └── Leaderboard    — top 10 persistant JSON
```

---

## Modules — Spécifications

### `src/player.py` — Joueur
- Modèle X-Wing texturé (Daniel Andersson, Sketchfab CC-BY) avec auto-scale
- Zone de jeu : ±11 X, ±6.5 Z
- Vitesse déplacement : 12 u/s avec lerp 12 u/s
- Rotation visuelle : roll max 30°, pitch max 20°
- **Barrel roll** : double-tap gauche/droite → 0.6s d'invincibilité, FOV zoom, flash, speed lines, traînées bleues spirale
- **Crosshair** : spring-damper (pendule physique, inertie + overshoot)
- 4 lumières moteurs aux bouts des ailes (pulse rouge ↔ orange)
- Boucliers : 10 HP max

### `src/enemies.py` — Ennemis
- **TIEFighter** : 18 u/s, charge à 65 u/s, 2 HP, 2 bolts, équilibré
- **TIEInterceptor** : 25 u/s, charge à 80 u/s, 1 HP, 1 bolt, drift agressif
- **TIEBomber** : 10 u/s, charge à 30 u/s, 5 HP, 2 bolts, tank
- **ImperialShuttle** *(V2)* : 8 u/s, 8 HP, 2 bolts, 500 pts — procédural (ailes trilobées, dérive dorsale)
- **AttackBomber** *(V2)* : 7 u/s, 10 HP, triple tir en éventail, 400 pts — procédural (3 pods + pont)
- **ProbeDroid** *(V2)* : 22 u/s, drift très agressif, 2 HP, 200 pts — procédural (corps cubique + 4 bras + œil rouge)
- **GroundTurret** *(V2)* : stationnaire au sol (Z=-5.2), défile monde, 6 HP, vise joueur, 300 pts — procédural (base + canon incliné)
- Tous avec modèles 3D texturés (si disponibles) + fallback procédural
- Accélération kamikaze à l'approche joueur
- Tirs laser verts (EnemyBolt)
- **Formations** : V, ligne, tenaille (pincer), essaim
- **`WAVE_DEFS_BY_LEVEL`** : dict par niveau (1-4), 7 vagues pré-définies + escalade automatique
- **`EnemySpawner(game, level=1)`** : utilise les wave defs du niveau sélectionné

### `src/lasers.py` — Système laser
- 2 bolts par salve (4 canons en 2 paires alternées)
- Couleurs alternées : rouge/rose & orange/jaune, noyau blanc + halo
- **Surchauffe** : ~20 salves → cooldown forcé 2.5s, jauge sur HUD
- **Auto-aim** : correction douce 15% vers l'ennemi le plus proche

### `src/torpedoes.py` — Torpilles
- Lock-on : clic droit maintenu, portée 120 u, cône 8 u
- Relâcher = tir
- Homing vers la cible lockée
- Ammo limitée (augmente via powerup)

### `src/force.py` — Capacité Force
- S'active au clic central (molette)
- Requiert la jauge Force pleine (kills)
- Durée 6s, vitesse monde × 0.3, auto-aim parfait, pas de surchauffe

### `src/boss.py` — Boss TIE Advanced
- Déclenché à partir de la vague 8 (`BOSS_TRIGGER_WAVE=8`)
- **150 HP**, `BOSS_HIT_RADIUS=2.5`, `BOSS_BOLT_SPEED=58.0`
- Piloté par **BossUtilityAI** (voir `src/boss_ai.py`)
- 4 intentions de mouvement : orbit / charge / strafe / retreat
- Orbite : `RETREAT_Y=25.0`, `STRAFE_RADIUS=11.0`, yo 15→11 selon dégâts — boss reste 10-20 u devant le joueur
- 6 actions de tir : aimed_fire, burst_fire, cone_shot, predictive_shot, aoe_burst, (+ dodge/retreat sans tir)
- Label cosmétique 3 phases (CALIBRATION / AGGRESSION / RAGE) basé sur HP%
- Défaite → explosion en chaîne 2.5s + explosion finale +5000 pts

### `src/boss_ai.py` — Utility AI du boss (nouveau)
- **`lerp_curve(points)`** : courbe linéaire par morceaux, base du scoring
- **`BossPerception`** : collecte boss_hp_pct, player_hp_pct, distance normalisée, vélocité joueur, player_threat (monte sur hit, décroît naturellement), bolt_count
- **`BossAction`** : base_priority × dist_curve × hp_curve × threat_curve ; contraintes min/max distance et HP ; move_intent associé ; cooldown individuel
- **`BossUtilityAI`** : 8 actions configurées, réévaluation toutes les 0.45s, choisit le meilleur score
- Actions disponibles : `aimed_fire` (base 60), `burst_fire` (55), `cone_shot` (50), `predictive_shot` (72, nécessite joueur mobile), `charge` (68), `dodge` (48), `aoe_burst` (58, HP<38% seulement), `retreat` (38)
- Tous les paramètres de tuning centralisés en constantes en tête de `boss.py`

### `src/environment.py` — Environnement (level-aware)
- **`Environment(game, level=1)`** : décor adapté selon le niveau actif
- **L1 (Astéroïdes)** : astéroïdes déformés + nébuleuses + débris + 2 planètes fixes
- **L2 (Surface lunaire)** : `LunarTerrain` (dalles 80×22u tuilées à Z=-7.8, courbure R=380) + `LunarRock` (rochers aplatis gris-bleutés)
- **L3 (Tranchée)** : `TrenchWallPanel` (murs latéraux X=±13.5 avec voyants ambre/rouge) + `TrenchFloorPanel` (carrelage industriel Z=-7.5)
- **L4 (Nébuleuse)** : nébuleuses denses × 2 + planète violette de fond
- Couleur de fond `setBackgroundColor` appliquée depuis `LEVELS` au lancement
- Toutes les classes : `update(dt, scroll_speed)` + `destroy()`, `setLightOff()` systématique
- Tuilage : step exact = `TILE_DEPTH`, spawn runtime à `max_y + TILE_DEPTH` → 0 overlap, 0 Z-fighting

### `src/hud.py` — Interface
- Bandeau supérieur semi-transparent : score, vague, hostiles restants
- Jauge shield en arc (vert → jaune → rouge)
- Jauge heat en arc (orange → rouge, clignotement surchauffe)
- Flash de dégât orange
- Annonce "WAVE X INCOMING" avec fade
- **Panneau radio boss** (bas d'écran) : rectangle + 2 demi-cercles procéduraux en GeomTriangles, fond sombre + bordure orange, barre HP couleur dynamique, texte nom + phase. Visible uniquement pendant le combat boss.
- Screen flash blanc : `trigger_screen_flash(intensity, duration)` — quad plein écran 0.15s
- Texte combo : `show_combo(count)` — "xN COMBO!" orange pulsant 1.5s
- Overlay PNG `assets/textures/hud_overlay.png` : code prêt, non intégré (WIP)

### `src/sounds.py` — Audio
- Pooling de sons, randomisation pitch
- 5 fichiers WAV : laser, laser_enemy, explosion, hit, overheat
- Fallback procédural si fichier manquant
- Toggle on/off : touche M

### `src/scores.py` + `scores.json` — Leaderboard
- Top 10 local, persistance JSON
- Champs : nom, score, vague, kills, date

### `src/levels.py` — Niveaux
- `LEVELS` dict : 4 niveaux avec `name`, `waves`, `intro_text`, `bg_color`, `description`
- L1 Asteroid Field → L2 Lunar Surface → L3 Death Star Trench → L4 Nebula
- `LevelManager` : transitions entre niveaux (infrastructure, partiellement câblée)

### `src/menu.py` — Menu principal
- **Sélecteur de niveau** `"CHOISIR NIVEAU"` : sous-menu dynamique généré depuis `LEVELS`
- Chaque entrée affiche `"LN — NOM"` et déclenche `start_game(start_level=N)`
- `subtitle` affiche la description des ennemis du niveau survolé
- `"SOLO"` démarre toujours depuis L1

### `src/powerups.py` — Collectibles
- 20% de chance de drop par kill ennemi
- **Torpedo** : +3 ammo (poids 60%)
- **Repair** : +2 HP (poids 40%)

### `src/menu.py` — Menu principal *(section déjà mise à jour ci-dessus)*
- Écran titre avec starfield en fond
- Options, affichage leaderboard

---

## Paramètres de jeu

| Paramètre | Valeur |
|-----------|--------|
| Zone jouable | ±11 X, ±6.5 Z |
| Vitesse scroll espace | 40 u/s |
| HP joueur | 10 |
| Surchauffe (salves) | ~20 |
| Cooldown surchauffe | 2.5s |
| Auto-aim | 15% |
| Barrel roll durée | 0.6s |
| Force bullet-time | 0.3× |
| Force durée | 6s |
| Lock-on portée | 120 u |
| Score de base/kill | 100 |
| Drop chance powerup | 20% |
| Leaderboard | Top 10 |

---

## Contrôles

| Touche | Action |
|--------|--------|
| ZQSD / Flèches | Déplacement |
| Espace / Clic gauche | Tir laser |
| Double-tap ← / → | Barrel roll |
| Clic droit (maintenu) | Lock-on torpille |
| Clic central | Capacité Force |
| M | Sons on/off |
| F11 | Plein écran |
| F1 | Compteur FPS |
| R | Restart (game over) |
| Échap | Quitter |

---

## Assets

| Asset | Source | Licence |
|-------|--------|---------|
| X-Wing, TIE Fighter/Interceptor/Bomber, Star Destroyer | Daniel Andersson (Sketchfab) | CC-BY |
| Astéroïdes pack 1 (8 models) | Sereib (Sketchfab) | CC-BY |
| Astéroïdes pack 2 | Sketchfab | CC-BY |
| Planètes (9 models) | Sketchfab | CC-BY |
| Sons WAV | Procéduraux (5 fichiers) | — |

---

## Roadmap

### Priorité 0 — Boss trop proche
- [ ] **Comportement boss** : augmenter distance d'orbite — actuellement `yo=15` (décalage Y devant joueur) dans 3 états HP
  - `ORBIT_HIGH` (HP>65%) : yo 15→40, rx 9→14, rz 4→7
  - `ORBIT_MID`  (HP 32-65%) : yo 13→30, rx 7→11, rz 3.2→6
  - `ORBIT_LOW`  (HP<32%, rage) : yo 11→22, rx 5.5→9
  - `RETREAT_Y` : 25→55 (retraite plus longue)
  - `CHARGE_DURATION` : 0.85→1.2 (charge traverse mieux le joueur avant de freiner)

### Priorité 1 — Visuel & Feel
- [x] **Lasers joueur** : bolts plus longs (hy 0.8→1.8), halo élargi (gy 0.9→2.2), colorScale ×2.5
- [ ] **Couleur réacteurs** : X-Wing réacteurs bleu-blanc, TIE réacteurs rouge-orangé — vertex color animée (pulse)
- [ ] **Repère hauteur joueur** : ✅ pyramide HUD 3 barres (vert→rouge, pointe haut/bas selon Z)
- [ ] **Indicateur altitude ennemis** : disque au sol ou tiret lateral (A choisir)
- [x] **Ennemis sur paliers** : Z = -4 / 0 / +4, transitions lerp (TIER_LERP=2.8)
  - B1 Mirror (TIEFighter) — suit le palier du joueur
  - B2 Route (TIEInterceptor) — séquence aléatoire calculée au spawn
  - B3 Kamikaze (TIEInterceptor, ProbeDroid) — fonce en 3D direct
  - B4 Guard (TIEBomber, AttackBomber) — palier fixe, tir lourd
  - B5 Flanking (ImperialShuttle) — spawn opposé, converge
  - B6 Erratic (ProbeDroid) — change aléatoirement toutes 0.8-2.5s
- [ ] **Bank Vader allégé** : coefficient -dx*6 → -dx*2.5, clamp ±40 → ±20°
- [ ] **Tourelles L4 Nébuleuse** : retirer les tourelles au sol (niveau espace, incohérent)
- [ ] **Assets 3D** : tourelles, nouveaux ennemis (Sketchfab CC0/CC-BY, format glb)

### Priorité 2 — Gameplay
- [ ] **Lock torpille Vader** : ✅ passer boss comme cible torpille en phase boss
- [x] **Contrôles** : mouse1=lasers (inchangé), mouse3=lock/torpille, mouse2=Force molette, F=Force clavier
- [ ] **Hitbox pendant changement palier** : ennemis difficiles à toucher en transition — élargir hitbox ou ajouter auto-aim léger sur Z pendant transition
- [ ] **Mode Free Ride** : voler librement sans ennemis, exploration des niveaux
- [ ] **Mode Multijoueur** : coop ou versus local/réseau (à spécifier)
- [ ] **IA ennemis** : comportements plus variés, flanking, esquive
- [ ] **Difficulté progressive** : paramètres dynamiques selon le niveau + kills

### Priorité 3 — Audio
- [ ] **Musique** : soundtrack Star Wars ambient / battle — généré procéduralement ou fichiers ogg, transition calme→combat
- [ ] **Refonte sons** : collisions moins agressives, sons tirs differenciés joueur/ennemi, sons UI
- [ ] **Son réacteurs** : bruit moteur ambiant X-Wing, variation selon vitesse

### Priorité 4 — Difficulté & Altitude
- [ ] **Altitude joueur vs ennemis** : les ennemis B1 Mirror convergent trop facilement, ajouter un offset ou un délai supplémentaire pour ne pas rendre le jeu trop facile
- [ ] **Indicateur altitude joueur** : repère visuel Z=0 (plan semi-transparent HUD ou ligne horizon) — à affiner quand le système de paliers sera plus challengeant
- [ ] **Écran de fin** : récap score + kills par vague
- [ ] **Sauvegardes** : config (volume, difficulté) persistante

---

## Historique des versions

### v0.1 — Setup projet (commit `fd7c86f`)
- Setup Panda3D + panda3d-gltf
- X-Wing procédural (géométrie sans modèle)
- Starfield 1000 étoiles

### v0.2 — Phase 2 : premiers ennemis et tir (commits `822a62f` → `d0763bf`)
- Ennemis TIE procéduraux basiques
- Système de tir laser initial
- Ajustements scale et mouvement

### v0.3 — Phase 3 : barrel roll + astéroïdes (commits `b3e2ca1` → `dd88c62`)
- Barrel roll complet avec effets visuels
- Astéroïdes procéduraux V1 puis V2
- Cache de modèles astéroïdes texturés (2 packs)

### v0.4 — Modèles 3D + ennemis texturés (commits `1191d7b` → `a51623f`)
- Modèles glTF X-Wing et TIE chargés
- TIEFighter, TIEInterceptor, TIEBomber avec auto-scale
- 9 planètes texturées chargées (non spawnées)
- Environnement : nébuleuses, débris, overlay
- Formations ennemies

### v0.5 — HUD holographique (commits `7e03a61` → `6ab084e`)
- Jauge shield en arc, jauge heat
- Bandeau score/vague/hostiles
- Flash dégâts, annonces vagues

### v0.6 — Explosions + caméra (commit `50fafb7`)
- Explosions multi-couches (flash → boule → fumée)
- Débris solides (6 triangles)
- Score popups "+100"
- Effets caméra (shake)

### v0.7 — Leaderboard (commit `5ba9d0b`)
- Leaderboard top 10 persistant JSON
- Écran game over avec saisie nom
- Affichage dans le menu

### v0.8 — Powerups (commit `3cf5aec`)
- Drop 20% chance par kill
- Torpedo (+3 ammo) et Repair (+2 HP)
- Effets visuels de collecte

### v0.9 — Torpilles + Force (commit `55f97a9`)
- Torpilles homing avec lock-on (clic droit)
- Capacité Force : bullet-time 0.3×, 6s, auto-aim parfait
- Jauge Force sur HUD

### v0.10 — Menu + audio WAV (commit `2037c79`)
- Menu principal avec starfield
- Sons WAV réels (5 fichiers)
- Pooling audio + fallback procédural

### v0.11 — Niveaux + menu polish (commit `5e03c79`)
- LevelManager (4 niveaux thématiques)
- Options menu
- Sons WAV améliorés

### v0.12 — Boss TIE Advanced (commits `ab102d4`, `0738b61`)
- Boss avec 50 HP, 3 phases comportementales
- Tirs bolts verts, patterns de dogfight
- Détection défaite

### v0.13 — Nettoyage repo + SPEC.md + CLAUDE.md (commit `b5813ba`)
- Suppression fichiers parasites (`files.zip`, `UnityHubSetup-x64.exe`, PDF, `setup.exe`)
- `.gitignore` étendu (*.exe, *.zip, *.pdf)
- Création `SPEC.md` et `CLAUDE.md`

### v0.15 — Boss Utility AI (nouveau)
- Nouveau fichier `src/boss_ai.py` : BossPerception + BossAction + BossUtilityAI
- Boss réévalué toutes les 0.45s — choisit parmi 8 actions selon scores dynamiques
- Mouvement : orbit (paramètres HP-dépendants) / charge / strafe / retraite
- Tirs : aimed_fire, burst_fire (salve 3 coups), cone_shot (10 bolts éventail), predictive_shot (vise position future), aoe_burst (12 bolts circulaires, HP<38%)
- `player_hp` passé à `boss.update()` depuis `game.py`
- Tous les paramètres de tuning centralisés en constantes (`ORBIT_HIGH/MID/LOW`, `CHARGE_SPEED`, `CONE_BOLT_COUNT`, etc.)

### v0.16 — VFX Explosions V2 + Screenshake + Curseur (nouveau)

#### `src/screenshake.py` — Nouveau module
- Classe `Screenshake` : décroissance quadratique (pas linéaire)
- Capture la position caméra "au repos" au déclenchement, applique jitter X/Z
- `trigger(intensity, duration)` : si un shake plus fort est déjà en cours il est ignoré
- Intensités : TIEFighter 0.15/0.2s | TIEBomber 0.25/0.25s | astéroïde 0.4/0.25s | joueur touché 0.5/0.3s | hit boss 0.15/0.15s | transition phase 0.8/0.5s | mort boss 1.0/0.8s

#### `src/explosions.py` — Réécriture complète
- 3 presets : `small` (TIE Fighter) / `medium` (torpille / TIE Bomber) / `large` (boss)
- 5 composants :
  - **Flash** (0.1s) : blanc chaud `(4.0, 3.5, 2.5)`, billboard additif
  - **Onde de choc** (0.25s) : carte très plate, s'expanse 0.3→max_radius, alpha 0.7→0
  - **Fireballs** : expansion 40% puis fade, palette chaude uniquement (orange vif/moyen/brûlé), résistance air
  - **Étincelles GeomPoints** : 20-45 pts, jaune→orange, décélération ×4/s
  - **Débris sombres** : gris 0.08-0.18, gravité légère, fade sur 30% finaux
- Palette stricte : jamais de bleu/vert/violet — que du chaud
- API : `spawn(position, preset="small", score=0)`

#### `src/hud.py` — Nouveaux éléments
- **Screen flash blanc** : `trigger_screen_flash(intensity, duration)` — quad plein écran 0.15s, séparé du flash rouge dégâts
- **Barre HP boss** : affichée à l'entrée du boss, masquée à sa mort, couleur ORANGE→WARN→DANGER selon HP
- **Texte combo** : `show_combo(count)` — "xN COMBO!" orange pulsant, 1.5s, animé — déplacé côté droit (1.15, 0.40)
- **Wave Incoming** : déplacé côté gauche (-1.15, 0.35) hors axe de visée
- **Pyramide altitude** : 3 barres horizontales décroissantes, vert→rouge selon |Z|, pointe haut si Z>0 bas si Z<0

#### `src/game.py` — Intégration
- Curseur souris masqué en jeu (`setCursorHidden(True)`), restauré au menu
- `Screenshake` instancié dans `start_game()`, `update()` chaque frame, `reset()` au restart
- `time_scale` combo slow-mo (×0.65 pendant 0.4s, 3 kills en 2s) combiné avec `force.get_time_scale()`
- Explosion preset par classe ennemi (TIEBomber → medium, autres → small)
- Torpilles : impact principal → medium, splash et kills → small
- Boss mort → preset large + screenshake 1.0 + screen flash 0.4

### v0.18 — Niveaux L2/L3/L4 + 4 nouveaux ennemis + sélection niveau menu

#### Nouveaux ennemis procéduraux (`src/enemies.py`)
- **ImperialShuttle** : 8 u/s, 8 HP, 2 bolts, 500 pts — navette avec grandes ailes angled + dérive dorsale
- **AttackBomber** : 7 u/s, 10 HP, triple tir éventail ±0.6u, 400 pts — 3 pods + pont + ailes 2.5u
- **ProbeDroid** : 22 u/s, drift ×2 plus agressif, 2 HP, 200 pts — corps cubique + 4 bras + œil rouge frontal
- **GroundTurret** : stationnaire sol (Z=-5.2), défile à 14 u/s, 6 HP, rotation H vers joueur, 300 pts
- `WAVE_DEFS_BY_LEVEL` : 4 niveaux × 7 vagues configurés — pool d'escalade adapté au niveau
- `EnemySpawner(game, level=1)` : paramètre level, wave_defs instance (plus de variable de classe)

#### Nouvelles classes décor (`src/environment.py`)
- **LunarTerrain** : dalle 240×22u à Z=-7.8, courbure parabolique sphérique (R=420), palette gris-bleutée, `setLightOff()`
- **LunarRock** : astéroïde aplati (flat=0.55-0.75), palette gris-bleutée lunaire
- **TrenchWallPanel / TrenchFloorPanel / TrenchSurfacePanel** : géométrie UV (`getV3t2()`), texture appliquée via `setTexture()`
- **Texture procédurale** (`_gen_trench_wall_texture`, `_gen_trench_floor_texture`) :
  - PNMImage 256×256 générée au lancement (seed déterministe)
  - Layout aléatoire de panneaux 1×cell ou 2×cell (variété de formes)
  - Effet **bevel** : ombre dégradée sur 4px en bordure → faux relief sans éclairage
  - Wrap repeat + filtrage bilinéaire / mipmap
  - Fallback : charge `assets/textures/trench_wall.jpg` / `trench_floor.jpg` si présents
- L3 bg_color : `(0.22, 0.05, 0.03)` — lueur rouge exhaust port visible au fond de la tranchée
- `Environment(game, level=1)` : init + update adaptatifs, reset géré dans `reset_game()`
- Tuilage init : `step = TILE_DEPTH` (exact, zéro overlap) de Y=15 à SPAWN_DEPTH+d
- Spawn runtime : nouvelle dalle/rangée à `max_y + TILE_DEPTH` quand `max_y < SPAWN_DEPTH - TILE_DEPTH/2`
- Largeur 240u couvre les tuiles à Y=200 (distance cam ≈ 184u, demi-largeur visible ≈ 106u avec FOV 60°)

#### Sélection de niveau (`src/menu.py`)
- Entrée "CHOISIR NIVEAU" dans le menu principal
- Sous-menu dynamique : `L1 — ASTEROID FIELD` … `L4 — NEBULA`
- Subtitle affiche la description des ennemis du niveau survolé
- Action `play_level_N` → `start_game(start_level=N)`

#### Intégration (`src/game.py`)
- `start_game(start_level=1)` : `selected_level` stocké, bg color appliqué, Level passé à env + spawner
- `reset_game()` : nettoie terrain_tiles/wall_panels/floor_panels + réinitialise décor et wave_defs au niveau en cours

### v0.17 — Fullscreen au lancement + Boss équilibré + Panneau radio boss + Explosions circulaires

#### `src/game.py` — Plein écran natif au lancement
- `setup_window()` : `setFullscreen(True)` + résolution détectée via `pipe.getDisplayWidth/Height()`
- `is_fullscreen` initialisé à `True` dans `setup_window()` (plus de `False` dans `__init__`)
- Aspect ratio synchronisé 50ms après la fenêtre via `doMethodLater`

#### `src/boss.py` — Boss rebalancé
- HP : 50 → **150**  
- `BOSS_HIT_RADIUS` : 3.0 → 2.5
- `BOSS_TRIGGER_WAVE` : 2 → **8** (vagues normales restaurées)
- `RETREAT_Y` : 62.0 → **25.0** — boss ne sort plus du range de tir
- `STRAFE_RADIUS` : 13.0 → 11.0
- Orbite yo : 35→28 → **15→11**, variation sin×5 (était ×10) — boss reste 10-20 u devant le joueur

#### `src/hud.py` — Panneau radio boss
- Panneau procédural en bas d'écran (Z≈-0.810) à la place de la barre centrée
- `_make_panel_bg()` : rectangle + 2 demi-cercles (GeomTriangles), fond sombre `(0.02,0,0,0.82)`
- `_make_panel_border()` : contour GeomLines avec arcs latéraux, épaisseur 1.5px
- Ligne déco intérieure supplémentaire (alpha 0.30)
- Barre HP dans le panneau, texte "◈ DARTH VADER — TIE ADVANCED" + label de phase

#### `src/explosions.py` — Géométrie circulaire procédurale
- Flash et onde de choc passent de CardMaker (rectangles visibles) à géométrie procédurale
- **`_make_disc()`** : disque fan de triangles, alpha centre=1.0 / bord=0.0, billboard additif `M_add + O_incoming_alpha`
- **`_make_ring()`** : 3 cercles concentriques (0.55/0.80/1.00), alpha 0→1→0, billboard additif
- Débris plus visibles : couleur 0.08-0.18 → **0.20-0.45** (teinte chaude), vitesse 6-18 → **10-28**, durée 0.4-0.8 → **0.7-1.3s**, compte : 7/10/16

### v0.20 — Viseur centre + décorations 3D tranchée + contraste directionnel L3

#### `src/hud.py` — Viseur central
- `_make_crosshair(game)` : croix 4 branches via `GeomLines`, gap central 0.018u, bras 0.040u, blanc légèrement chaud semi-transparent (alpha 0.75)
- Rendu sur `aspect2d`, bin "fixed" sort 60, `setDepthTest(False)` → toujours visible devant le décor
- Initialisé dans `HUD.__init__` → toujours affiché, ne bouge pas

#### `src/environment.py` — `TrenchDecorGroup` + textures circuit + contraste directionnel
- **Éclairage directionnel** : paramètre `lit=True/False` — mur gauche ombre `0.18→0.42`, mur droit lumière `0.55→1.00` (vertex color × texture)
- **Lune** : `DistantPlanet` à `Point3(-18, 140, 28)` (gauche), rayon 4.5u, blanc-chaud, `grow_rate=0`
- **Textures circuit imprimé** (`_draw_circuit_tex`) : fond sombre + plaques irrégulières + traces PCB horizontales/verticales + courtes jonctions obliques + pads circulaires aux nœuds. Appliquées via `TextureStage M_modulate` (texture × vertex_color) sur murs et sol. Format custom `_V3C4T2` (position + color + UV).
- **Nouvelles primitives** :
  - `_make_antenna` : colonne fine + disque tête + anneau intermédiaire optionnel
  - `_make_l_bracket` : bras horizontal + bras vertical connectés en L
  - `_make_tower` : récursif depth 2-3 — boîte de base + éléments décroissants au sommet
  - `_make_connected_cluster` : 2 boîtes reliées par un rail + nœud vertical optionnel
- **Placement fractal/puzzle** (hiérarchie en 4 niveaux) :
  1. Rails de fond (1-3, traversent tout le segment)
  2. Conduits groupés (50% des segments)
  3. Clusters connectés (1-3 par segment, min_sep 2.5-4.5u)
  4. Éléments terminaux (3-7 : tours, antennes, L-brackets, boîtes, disques, marches)

### v0.19 — Fix tuilage L2/L3 : zéro overlap, zéro Z-fighting, courbure planétaire

#### `src/environment.py` — Tuilage sans fissures et sans scintillement
- **Init** (`_init_lunar`, `_init_trench`) : `step = d` exact (était `d-1`), zéro overlap entre dalles adjacentes
- **Runtime** (`_update_l2`, `_update_l3`) : nouvelle dalle spawned à `max_y + TILE_DEPTH` (était à `SPAWN_DEPTH` fixe → overlap ~20u avec la précédente)
- Condition de spawn : `max_y < SPAWN_DEPTH - TILE_DEPTH/2` — garantit une dalle toujours en réserve avant la zone de tir
- **LunarTerrain** : courbure parabolique sphérique `z = -(x²+y²)/(2×380)` sur tous les vertices; bords Y (`j=0`, `j=segs_y`) déterministes (bump=0) → joints seamless entre dalles consécutives
- Taux de cratères 3 niveaux : `bump < -0.18` → dark 0.72 / `bump < 0` → 0.88 / positif → 1.0
- Toutes les surfaces décor : `setLightOff()` → couleurs vertex brutes sans teinte de l'éclairage scène

### v0.14 — Bugfixes : keys / torpilles / fullscreen
- **Bug keys post-restart** : `_lb_unbind_keys()` restaure "m" et "r" après unbind A-Z ; `reset_game()` appelle `player.setup_controls()` pour restaurer z/q/s/d (écrasées par le leaderboard) ; spawner et environnement entièrement réinitialisés (`_prepare_wave()`, timers, planètes)
- **Bug torpilles** : `fire_torpedo()` appelle `fire()` avant de mettre `locking=False` ; `LOCK_CONE` 8→14 ; dumb-fire sans lock possible
- **Bug fullscreen** : résolution native via `pipe.getDisplayWidth/Height()` ; `camLens.setAspectRatio` resynchronisé 50ms après resize

---

## TODO / Roadmap

Voir [ROADMAP.md](ROADMAP.md) pour le détail complet V1 ✅ + V2 planifié.

Prochaines priorités V2 :
- Visuels distincts par niveau (L2 surface lunaire, L3 tranchée, L4 nébuleuse)
- Nouveaux types d'ennemis (Shuttle, Probe Droid, tourelles sol)
- Boss Star Destroyer avec tourelles destructibles
- Audio upgrade (musiques ambiantes, dialogues radio)
- Screenshake + effets caméra
