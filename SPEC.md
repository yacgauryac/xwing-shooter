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
        ├── src/player.py        Player         — X-Wing, mouvement, barrel roll, visée FPS souris
        ├── src/enemies.py       EnemySpawner   — TIE state machine, squads, vagues
        ├── src/lasers.py        LaserSystem    — tir, surchauffe, bolts poolés
        ├── src/torpedoes.py     TorpedoSystem  — missiles homing, lock-on
        ├── src/force.py         ForceAbility   — bullet-time 0.3×, 6s
        ├── src/boss.py          BossTIEAdvanced — 150 HP, 3 phases
        │     └── src/boss_ai.py BossUtilityAI  — 8 actions, scoring dynamique 0.45s
        ├── src/environment.py   Environment    — L1-L4 décors, fog, danger lights
        │     └── src/lunar_base.py LunarBase   — bâtiments procéduraux L2 (tower/hangar/silo…)
        ├── src/starfield.py     Starfield      — 1000 étoiles + traînées de vitesse
        ├── src/hud.py           HUD            — overlay holographique orange/ambre
        ├── src/explosions.py    ExplosionManager — presets small/medium/large
        ├── src/screenshake.py   Screenshake    — décroissance quadratique, intensités par événement
        ├── src/sounds.py        SoundManager   — pooling audio + fallback procédural
        ├── src/powerups.py      PowerUpManager — torpedo/repair/force/fake, flamme MAdd
        ├── src/levels.py        LevelManager   — transitions, intro fade, L1→L4
        ├── src/wave_config.py   —              — WAVE_DEFS_BY_LEVEL (config déclarative)
        ├── src/menu.py          MainMenu       — titre, sélecteur niveau, leaderboard
        ├── src/scores.py        Leaderboard    — top 10 persistant JSON
        ├── src/settings.py      —              — settings par niveau
        ├── src/network.py       NetworkManager — stub UDP V3 (non actif)
        └── src/building_viewer.py —            — viewer standalone (python viewer.py)
```

---

## Modules — Spécifications

### `src/player.py` — Joueur
- Modèle X-Wing texturé (Daniel Andersson, Sketchfab CC-BY) avec auto-scale
- Zone de jeu : ±14 X (L1/L4), ±12 X (L2), ±11 X (L3) — dynamique via `set_bounds()`
- Vitesse déplacement : 12 u/s avec lerp 12 u/s
- Rotation visuelle : roll max 30°, pitch max 20°
- **Barrel roll** : double-tap gauche/droite → 0.6s d'invincibilité, FOV zoom, flash, speed lines, traînées bleues spirale
- **Crosshair** : spring-damper (pendule physique, inertie + overshoot)
- **Visée FPS souris** : mode relatif (warp centre chaque frame), `mouse_aim_x/z` clampé ±1.2/±0.9, `MOUSE_SENS=0.004`
- **Rectangle de visée 3D** : 4 segments UHDynamic en monde, dimensions hitbox, couleur viseur `(0.95,0.82,0.18)`, positionné à Y+60 devant le vaisseau
- 4 lumières moteurs aux bouts des ailes (pulse rouge ↔ orange)
- **Hit flash** : lueur ambre `(1.5,0.28,0.06,0.055)` sur copie du modèle, 0.18s
- **Bouclier** : désactivé — réservé V3 (vrai système énergétique)

### `src/enemies.py` — Ennemis

#### TIEFighter — state machine cinématique
- **États** : `S_APPROACH` → `S_BREAK` → `S_ATTACK_RUN` / `S_FLANK` → `S_LOOP_BACK`
- **Squads** de 4 TIEs avec offsets de formation (`FORMATION_OFFSETS`, `APPROACH_TARGETS`)
- **Virages courbes** : bank angle calculé depuis `vel_x`, clamp ±35°, lerp fluide
- Vitesses : approche 22 u/s, attaque 46 u/s, flanking 52 u/s, loop 36 u/s
- Taux de virage max : approche 55°/s, attaque 80°/s, loop 95°/s
- `FIRE_RANGE=85u` — ne tire que s'il voit le joueur à portée
- **TIEInterceptor** : 25 u/s, charge à 80 u/s, 1 HP, 1 bolt, drift agressif
- **TIEBomber** : 10 u/s, charge à 30 u/s, 5 HP, 2 bolts, tank
- **ImperialShuttle** *(V2)* : 8 u/s, 8 HP, 2 bolts, 500 pts — procédural (ailes trilobées, dérive dorsale)
- **AttackBomber** *(V2)* : 7 u/s, 10 HP, triple tir en éventail, 400 pts — 3 pods + pont
- **ProbeDroid** *(V2)* : 22 u/s, drift ×2 agressif, 2 HP, 200 pts — corps cubique + 4 bras + œil rouge
- **GroundTurret** *(V2)* : stationnaire sol (Z=-5.2), défile monde, 6 HP, vise joueur, 300 pts
- **`FOG_ONSET_BY_LEVEL`** : seuil Y par niveau au-delà duquel un ennemi est invisible → invulnérable
- Tous avec modèles 3D texturés (si disponibles) + fallback procédural
- **`WAVE_DEFS_BY_LEVEL`** : dict par niveau (1-4), 7 vagues pré-définies + escalade automatique
- **`EnemySpawner(game, level=1)`** : utilise les wave defs du niveau sélectionné

#### EnemyBolt — pool
- `SPEED=80 u/s`, `DAMAGE=1.0`, `HIT_RADIUS=1.8`
- **Pool** : `reset()` réutilise sans recréer la géométrie ; `destroy()` détache sans supprimer ; `cleanup()` supprime définitivement (nettoyage de niveau)

### `src/lasers.py` — Système laser
- 2 bolts par salve (4 canons en 2 paires alternées)
- Couleurs alternées : rouge/rose & orange/jaune, noyau blanc + halo
- **Surchauffe** : ~20 salves → cooldown forcé 2.5s, jauge sur HUD
- **Auto-aim supprimé** pour les lasers normaux — tir droit (`Vec3(0,1,0)`)
- **Portée** : `MAX_DISTANCE=380u`, `SPEED=115 u/s`
- Auto-aim conservé uniquement pour les torpilles homing

### `src/torpedoes.py` — Torpilles
- Lock-on : clic droit maintenu, portée 120 u, cône 14 u
- Relâcher = tir
- Homing vers la cible lockée
- Ammo limitée (augmente via powerup)
- `TORPEDO_SPLASH_RADIUS=1.0`, `TORPEDO_SPLASH_DAMAGE=3.0`, `TORPEDO_COOLDOWN=3.0s`
- `TORPEDO_MAX_DIST=120u`, `TORPEDO_TURN_RATE=2.0`, `TORPEDO_ACCEL=70.0`

### `src/force.py` — Capacité Force
- S'active au clic central (molette)
- Requiert la jauge Force pleine (kills)
- Durée 6s, vitesse monde × 0.3, auto-aim parfait, pas de surchauffe
- Powerup force : `add_pickup(15.0)` — +15 jauge

### `src/boss.py` — Boss TIE Advanced
- Déclenché à partir de la vague 8 (`BOSS_TRIGGER_WAVE=8`)
- **150 HP**, `BOSS_HIT_RADIUS=2.5`, `BOSS_BOLT_SPEED=58.0`
- Piloté par **BossUtilityAI** (voir `src/boss_ai.py`)
- 4 intentions de mouvement : orbit / charge / strafe / retreat
- Orbite : `RETREAT_Y=25.0`, `STRAFE_RADIUS=11.0`, yo 15→11 selon dégâts — boss reste 10-20 u devant le joueur
- 6 actions de tir : aimed_fire, burst_fire, cone_shot, predictive_shot, aoe_burst, (+ dodge/retreat sans tir)
- Label cosmétique 3 phases (CALIBRATION / AGGRESSION / RAGE) basé sur HP%
- Défaite → explosion en chaîne 2.5s + explosion finale +5000 pts

### `src/boss_ai.py` — Utility AI du boss
- **`lerp_curve(points)`** : courbe linéaire par morceaux, base du scoring
- **`BossPerception`** : collecte boss_hp_pct, player_hp_pct, distance normalisée, vélocité joueur, player_threat (monte sur hit, décroît naturellement), bolt_count
- **`BossAction`** : base_priority × dist_curve × hp_curve × threat_curve ; contraintes min/max distance et HP ; move_intent associé ; cooldown individuel
- **`BossUtilityAI`** : 8 actions configurées, réévaluation toutes les 0.45s, choisit le meilleur score
- Actions disponibles : `aimed_fire` (base 60), `burst_fire` (55), `cone_shot` (50), `predictive_shot` (72, nécessite joueur mobile), `charge` (68), `dodge` (48), `aoe_burst` (58, HP<38% seulement), `retreat` (38)
- Tous les paramètres de tuning centralisés en constantes en tête de `boss.py`

### `src/environment.py` — Environnement (level-aware)
- **`Environment(game, level=1)`** : décor adapté selon le niveau actif
- **L99 (Debug)** : 10 astéroïdes/seconde, vitesse aléatoire ×0.5–2.0, visuels L1
- **L1 (Astéroïdes)** : astéroïdes déformés + nébuleuses + débris + 2 planètes fixes
- **Danger light astéroïdes** : 3 lumières scopées sur chaque astéroïde (`node.setLight`)
  - `AmbientLight` teinté couleur viseur `(0.95,0.82,0.18)` — glow uniforme toute surface
  - `Spotlight` teinté chaud — directionnel côté joueur, évite saturation blanche
  - `PointLight` halo orange — collé à la surface côté joueur
  - Intensité linéaire : max quand l'astéroïde est proche devant (`proximity = max(0, 1 - raw_dy/120)`), 0 quand derrière
  - Extinction progressive sur `_danger_timer` à la désactivation
- **L2 (Surface lunaire)** : `LunarTerrain` (dalles 80×22u tuilées à Z=-7.8, courbure R=380) + `LunarRock` (rochers aplatis gris-bleutés)
- **L3 (Tranchée)** : `TrenchWallPanel` (murs latéraux X=±13.5 avec voyants ambre/rouge) + `TrenchFloorPanel` (carrelage industriel Z=-7.5)
- **L4 (Nébuleuse)** : nébuleuses denses × 2 (richness=2.0) + 3 planètes violettes/roses + filaments de gaz billboard
  - **`GasFilament`** : ellipse billboard `setBillboardPointEye()`, dégradé alpha (centre plein → bords=0), éventail de 12 triangles, palette 10 couleurs violet/rose/magenta, scrolle avec la scène, fade-in 1.8s. **45 filaments initiaux** en bandes régulières Y=20→620 + spawn périodique 3.5–7s, **minimum garanti 18 actifs**. 6 Nebula pré-spawnées à l'init. `nebula_timer=3s, filament_timer=0` au démarrage.
  - **Palette nébuleuses L4** : 7 couleurs violet/rose/magenta/indigo exclusivement (aucun bleu/vert/orange)
  - **Palette nébuleuses L1** : orange-brun / bleu-électrique / rouge-orangé / cyan-vert / jaune-ambre — aucun violet → contraste maximal avec L4
  - **5 nappes fog L4** : violet `-3u` / rose-magenta `+2.5u` / indigo `0u` / bleu-indigo `+5.5u` / magenta ras-du-sol `-6u`
  - **`Nebula` (richness)** : param `richness=2.0` pour L4 — `num_points = 80 × richness`, variation couleur `col_var = 0.10 + 0.07 × richness`, alpha max `0.20`, point size `2 + round(richness)`
- Couleur de fond `setBackgroundColor` appliquée depuis `LEVELS` au lancement
- Toutes les classes : `update(dt, scroll_speed)` + `destroy()`, `setLightOff()` systématique
- Tuilage : step exact = `TILE_DEPTH`, spawn runtime à `max_y + TILE_DEPTH` → 0 overlap, 0 Z-fighting
- **L2 fade bâtiments** : la géométrie opaque du groupe reste solide ; seuls les `center_nodes` (tours centrales) sont fadés via alpha — pas de depth sort GPU sur la masse des bâtiments
- **Debug perf** : `toggle_terrain_debug()` / `toggle_buildings_debug()` / `toggle_fog_debug()` — caches partiels pour isoler les sources de spikes

### `src/hud.py` — Interface
- Bandeau supérieur semi-transparent : score, vague
- **Mini HUD near-ship** : 2 barres persistantes (`_sbar_root`) repositionnées chaque frame — laser (chaleur) + **6 segments vie** style holographique. Géométrie créée une seule fois en `__init__`, `setColorScale` chaque frame (zéro allocation). Segments arrondis (`_make_rounded_rect`). Couleur : bleu `(0.2, 0.55, 1.0)` sauf dernier segment seul → rouge clignotant. Fond laser arrondi aussi. Mapping `round` avec garde `health > 0 → n_lit ≥ 1`.
- **WARN/OVERHEAT** : `OnscreenText` pré-alloué `_ship_warn_text`, `setPos` chaque frame au niveau fuselage
- **Trapèzes dégâts** : flash rouge latéraux style HL2, repliés vers les bords (EDGE_GAP=0.25), largeur 0.30
- **Torpilles** : losange bas-centre avec compteur, clignotement rouge si ≤2
- **Annonce wave** : "WAVE X" haut-gauche `(-1.20, 0.90)`, dezoom `0.065→0.040` + fade sur 2s
- **Panneau radio boss** (bas d'écran) : rectangle + 2 demi-cercles procéduraux en GeomTriangles, fond sombre + bordure orange, barre HP couleur dynamique, texte nom + phase. Visible uniquement pendant le combat boss.
- Screen flash blanc : `trigger_screen_flash(intensity, duration)` — quad plein écran 0.15s
- Texte combo : `show_combo(count)` — "xN COMBO!" orange pulsant 1.5s
- **Feedback d'impact** : `on_hit()` — flash blanc 0.10s sur les segments vie + 6-8 étincelles orange/blanc en aspect2d depuis la position écran du vaisseau (durée 0.25-0.42s, fade alpha linéaire)
- `show_pickup(text, color=None)` — couleur optionnelle (ex: rouge pour fake powerup)

### `src/sounds.py` — Audio
- Pooling de sons, randomisation pitch
- 5 fichiers WAV : laser, laser_enemy, explosion, hit, overheat
- Fallback procédural si fichier manquant
- Toggle on/off : touche M

### `src/scores.py` + `scores.json` — Leaderboard
- Top 10 local, persistance JSON
- Champs : nom, score, vague, kills, date

### `src/levels.py` — Niveaux
- `LEVELS` dict : 4 niveaux + L0 sandbox + L99 debug, avec `name`, `waves`, `intro_text`, `bg_color`, `ambient_color`, `description`
- `ambient_color` par niveau (données prêtes, appel `_apply_ambient()` désactivé — design en attente) :
  - L1 espace froid `(0.10,0.12,0.22)` | L2 lune ambre `(0.20,0.15,0.06)` | L3 acier `(0.13,0.12,0.13)` | L4 violet `(0.10,0.06,0.20)`
- L1 Asteroid Field → L2 Lunar Surface → L3 Death Star Trench → L4 Nebula
- L99 DEBUG : astéroïdes only, 999 vagues, 100 HP
- `LevelManager` : câblé dans `game.py` — `start_intro_for_level()` appelé depuis `start_game()`
- **Intro fade** : fondu noir (alpha 1→0) sur 1.5s au début de chaque niveau, texte visible jusqu'à 3s
  - Nom du niveau affiché en police **SFDistantGalaxy** (`assets/fonts/SFDistantGalaxy.ttf`), chargée en lazy singleton
  - Sous-titre (nom court) en SFDistantGalaxy, intro text en police par défaut
  - `start_intro_for_level(level_id)` déclenche directement depuis `start_game()` sans attendre une transition

### `src/game.py` — Caméra & perf
- **Vue normale** : `CAM_FAR_POS=(0,-8,3.5)` → `CAM_FAR_LOOK=(0,22,0)`
- **Vue Force/ADS** : `CAM_CLOSE_POS=(0,3,1.8)` → `CAM_CLOSE_LOOK=(0,16,0)`
- **Lerp fluide** : `CAM_LERP_SPEED=5.0` — transition ~0.2s
- Force active → zoom avant automatique ; touche 5 → bascule manuelle
- `_update_camera(dt)` exécuté **avant** `hud.update()` dans la boucle (projection synchronisée)
- **MSAA 2x** (était 4x), `sync-video 0` — désactive le V-sync pour mesurer le vrai temps de rendu
- `MAuto` antialiasing désactivé (évite double depth sort multisamplé sur transparents)
- `gc.disable()` au démarrage, `gc.collect()` manuel aux points sûrs (après reset, return_to_menu)
- `graphicsEngine.renderFrame()` avant la première frame → upload VBOs GPU avant le jeu
- **Bolt pool** : `cleanup()` appelé à la place de `destroy()` lors du nettoyage de niveau
- **Overlay debug perf (touche 6)** : panneau bas-gauche, FPS avg/min/max, log spike <35fps, touches T/B/F (toggle terrain/bâtiments/fog)
- Powerup rebalancé : torpedo +3→**+1**, repair +2→**+1**, force 35→**+15**
- **Fake powerup** : -5 HP, show_pickup("DARK SIDE!", rouge), damage flash + screenshake 0.35

### `src/building_viewer.py` — Viewer procédural
- Launcher : `python viewer.py`
- Catalogue 7 meshs : tower, hangar, silo, bunker, antenna, pad, relay
- Touches **1-7** : jump direct au bâtiment | Tab/Shift-Tab : navigation séquentielle
- Hitbox **cyan** `(0.0,0.95,0.85)` (non confondue avec néons orange)
- **Néons 3 couches additifs** (core + glow ×3 alpha 0.28 + bloom ×7 alpha 0.09) sur tous les bâtiments
- **Labels SFDistantGalaxy** font impériale billboards
- Lancement **plein écran** natif

### `src/menu.py` — Menu principal
- **Sélecteur de niveau** `"CHOISIR NIVEAU"` : sous-menu dynamique généré depuis `LEVELS`
- Chaque entrée affiche `"LN — NOM"` et déclenche `start_game(start_level=N)`
- `subtitle` affiche la description des ennemis du niveau survolé
- `"SOLO"` démarre toujours depuis L1

### `src/powerups.py` — Collectibles
- `DROP_CHANCE=15%`, `NO_DROP_TIME=0`, `COLLECT_RADIUS=8u`
- **4 types à 25% chacun** :
  - **Torpedo** (blanc cassé, lettre `T`) : +1 torpille
  - **Repair** (jaune, lettre `H`) : +1 HP
  - **Force** (bleu, lettre `F`) : +15 jauge Force
  - **Fake** (violet Sith `#B20DD9`, lettre `?`) : piège — inflige -5 HP, flash dégâts + screenshake
- **Visuels** : gemme octaédrique + label SFDistantGalaxy billboard + flamme mystique 3 couches additives (core/glow/bloom) via `ColorBlendAttrib.MAdd`
- **Clignotement** : battement double fréquence `sin(age×3.2) + sin(age×7.1)`, amplitude 0.15→1.6, cycle couleur A↔B
- **Flamme** : 3 disques `_make_disc()` (r=0.55/1.05/1.90), phases décalées, respiration 2.2 Hz

### `src/lunar_base.py` — Bâtiments L2
- `setRenderModeThickness` **supprimé** de tous les nœuds néon (incompatible OpenGL Core Profile)
- **`bd` (batch partagé)** : paramètre optionnel sur `_make_tower/_make_hangar/_make_silo` — permet de fusionner plusieurs bâtiments dans le même `_GeomBatch`, réduisant les draw calls de groupes
- **`center_nodes`** : liste de NodePath attachée à chaque `BaseGroup` pour le fade sélectif — seule la géométrie centrale est fadée, pas le batch complet

---

## Paramètres de jeu

| Paramètre | Valeur |
|-----------|--------|
| Zone jouable | ±11 X, ±6.5 Z |
| Vitesse scroll espace | 40 u/s |
| HP joueur | 10 |
| Surchauffe (salves) | ~20 |
| Cooldown surchauffe | 2.5s |
| Auto-aim | désactivé lasers / actif torpilles |
| Barrel roll durée | 0.6s |
| Force bullet-time | 0.3× |
| Force durée | 6s |
| Lock-on portée | 120 u |
| Score de base/kill | 100 |
| Drop chance powerup | 15% (4 types × 25%) |
| Leaderboard | Top 10 |
| MSAA | 2x (framebuffer) |
| V-sync | désactivé |

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
| 6 | Overlay debug FPS/spikes |
| T / B / F (debug) | Toggle terrain/bâtiments/fog |
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
| Police SFDistantGalaxy | `assets/fonts/SFDistantGalaxy.ttf` | — |

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
- [x] **Ennemis sur paliers** : Z = -4 / 0 / +4, transitions lerp (TIER_LERP=1.8)
  - B1 Mirror (TIEFighter) — suit le palier du joueur
  - B2 Route (TIEInterceptor) — séquence aléatoire calculée au spawn
  - B3 Kamikaze (TIEInterceptor, ProbeDroid) — fonce en 3D direct
  - B4 Guard (TIEBomber, AttackBomber) — palier fixe, tir lourd
  - B5 Flanking (ImperialShuttle) — spawn opposé, converge
  - B6 Erratic (ProbeDroid) — change aléatoirement toutes 0.8-2.5s
- [ ] **Bank Vader allégé** : coefficient -dx*6 → -dx*2.5, clamp ±40 → ±20°
- [x] **Tourelles L2+L4 retirées** : GroundTurret supprimé des vagues L2 (lunaire) et L4 (nébuleuse)
- [ ] **L2 — Surface lunaire** : marquages sol style aéroport (pistes, taxiways, lignes) + bâtiments à éviter (cubes, cônes, pyramides, cylindres procéduraux)
- [ ] **Navmesh L2** : grille d'obstacles pour que les ennemis contournent les bâtiments
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

### v0.14 — Bugfixes : keys / torpilles / fullscreen
- **Bug keys post-restart** : `_lb_unbind_keys()` restaure "m" et "r" après unbind A-Z ; `reset_game()` appelle `player.setup_controls()` pour restaurer z/q/s/d (écrasées par le leaderboard) ; spawner et environnement entièrement réinitialisés (`_prepare_wave()`, timers, planètes)
- **Bug torpilles** : `fire_torpedo()` appelle `fire()` avant de mettre `locking=False` ; `LOCK_CONE` 8→14 ; dumb-fire sans lock possible
- **Bug fullscreen** : résolution native via `pipe.getDisplayWidth/Height()` ; `camLens.setAspectRatio` resynchronisé 50ms après resize

### v0.15 — Boss Utility AI
- Nouveau fichier `src/boss_ai.py` : BossPerception + BossAction + BossUtilityAI
- Boss réévalué toutes les 0.45s — choisit parmi 8 actions selon scores dynamiques
- Mouvement : orbit (paramètres HP-dépendants) / charge / strafe / retraite
- Tirs : aimed_fire, burst_fire (salve 3 coups), cone_shot (10 bolts éventail), predictive_shot (vise position future), aoe_burst (12 bolts circulaires, HP<38%)
- `player_hp` passé à `boss.update()` depuis `game.py`
- Tous les paramètres de tuning centralisés en constantes (`ORBIT_HIGH/MID/LOW`, `CHARGE_SPEED`, `CONE_BOLT_COUNT`, etc.)

### v0.16 — VFX Explosions V2 + Screenshake + Curseur

#### `src/screenshake.py` — Nouveau module
- Classe `Screenshake` : décroissance quadratique (pas linéaire)
- Capture la position caméra "au repos" au déclenchement, applique jitter X/Z
- `trigger(intensity, duration)` : si un shake plus fort est déjà en cours il est ignoré
- Intensités : TIEFighter 0.15/0.2s | TIEBomber 0.25/0.25s | astéroïde 0.4/0.25s | joueur touché 0.5/0.3s | hit boss 0.15/0.15s | transition phase 0.8/0.5s | mort boss 1.0/0.8s

#### `src/explosions.py` — Réécriture complète
- 3 presets : `small` (TIE Fighter) / `medium` (torpille / TIE Bomber) / `large` (boss)
- 5 composants : Flash (0.1s) + Onde de choc (0.25s) + Fireballs + Étincelles GeomPoints + Débris sombres
- Palette stricte : jamais de bleu/vert/violet — que du chaud
- API : `spawn(position, preset="small", score=0)`

#### `src/hud.py` — Nouveaux éléments
- Screen flash blanc, barre HP boss, texte combo "xN COMBO!", pyramide altitude

#### `src/game.py` — Intégration
- Curseur souris masqué en jeu (`setCursorHidden(True)`), restauré au menu
- `Screenshake` instancié dans `start_game()`, `update()` chaque frame, `reset()` au restart
- `time_scale` combo slow-mo (×0.65 pendant 0.4s, 3 kills en 2s) combiné avec `force.get_time_scale()`

### v0.17 — Fullscreen au lancement + Boss équilibré + Panneau radio boss + Explosions circulaires

- Plein écran natif au lancement (`setFullscreen(True)` + résolution détectée)
- Boss rebalancé : HP 50→150, BOSS_TRIGGER_WAVE 2→8, RETREAT_Y 62→25, orbite yo 35→15
- Panneau radio boss procédural (bas d'écran) avec barre HP + label phase
- Explosions : flash et onde de choc passent en géométrie circulaire procédurale (`_make_disc`, `_make_ring`)

### v0.18 — Niveaux L2/L3/L4 + 4 nouveaux ennemis + sélection niveau menu

- ImperialShuttle, AttackBomber, ProbeDroid, GroundTurret procéduraux
- `WAVE_DEFS_BY_LEVEL` : 4 niveaux × 7 vagues configurés
- LunarTerrain, LunarRock, TrenchWallPanel/FloorPanel/SurfacePanel
- Textures procédurales tranchée (circuit imprimé, bevel 4px, seed déterministe)
- Sélecteur niveau dans le menu principal

### v0.19 — Fix tuilage L2/L3 : zéro overlap, zéro Z-fighting, courbure planétaire

- Step tuilage `d` exact (était `d-1`), spawn à `max_y + TILE_DEPTH`
- LunarTerrain : courbure parabolique sphérique `z = -(x²+y²)/(2×380)`, joints seamless

### v0.20 — Viseur centre + décorations 3D tranchée + contraste directionnel L3

- Viseur central fixe (4 branches `GeomLines`, bin "fixed" sort 60, `setDepthTest(False)`)
- `TrenchDecorGroup` : hiérarchie 4 niveaux, textures circuit imprimé, éclairage directionnel
- Lune DistantPlanet en décor L3, primitives antenna/l_bracket/tower/connected_cluster

### v0.21 — Debug mode, FPS aim, danger light astéroïdes, L99

- Debug key 2 : labels Y, hitbox wireframe, labels X 3D billboard
- Debug key 3 : mode squelette
- Visée FPS souris relative, rectangle visée 3D UHDynamic
- Danger light astéroïdes (ambient + spot + point scoped), L99 debug level

### v0.23 — Vie en segments + feedback d'impact

#### `src/player.py`
- Suppression complète de l'éclair rouge au hit (`_create_hit_flash`, `show_shield_hit`, bloc update) — zéro deadcode

#### `src/hud.py`
- Barre vie near-ship remplacée par 6 segments holographiques dans `_sbar_root` (fond noir + contour cyan)
- Couleur dynamique : cyan (6-5 segments) → jaune (4-3) → rouge (2-1), dernier segment blink à 5 Hz
- `on_hit()` : flash blanc 0.10s sur les segments actifs + 6-8 étincelles orange/blanc en aspect2d (fade 0.25-0.42s)

#### `src/game.py`
- `player.show_shield_hit()` remplacé par `hud.on_hit()` aux 2 points de hit joueur

---

### v0.22 — TIE Fighter state machine + perf tooling + rebalance

#### `src/enemies.py`
- **TIEFighter refonte complète** : state machine 5 états (APPROACH/BREAK/ATTACK_RUN/FLANK/LOOP_BACK), squads de 4 TIEs, virages courbes avec bank angle, cibles d'approche fixes par rôle
- **EnemyBolt** : speed 52→**80** u/s, pool avec `reset()` (réutilise géométrie) + `cleanup()` (destruction finale)
- **`FOG_ONSET_BY_LEVEL`** : seuil d'invulnérabilité par niveau (ennemis invisibles dans le fog)

#### `src/wave_config.py`
- L1 vagues redesignées pour le système squad (N tie_fighter = N squads de 4)
- Champ `formation` déprécié (conservé pour rétrocompat)

#### `src/game.py` — Perf & outils
- MSAA 4x→**2x**, `sync-video 0` (V-sync désactivé)
- `MAuto` antialiasing désactivé (évite double depth sort)
- `gc.disable()` au démarrage, `gc.collect()` aux points sûrs
- `graphicsEngine.renderFrame()` avant la première frame (upload VBOs)
- **Overlay debug (touche 6)** : FPS avg/min/max, logger spikes <35fps
- **Touches T/B/F** : toggle terrain/bâtiments/fog (isolation perf L2)
- Bolt pool `cleanup()` lors du nettoyage de niveau

#### Rebalance
- Torpilles : splash radius 15→**1**, splash damage 10→**3**, cooldown 1→**3s**, max_dist 200→**120u**
- Powerup torpedo : +3→**+1** | repair : +2→**+1** | force : +35→**+15**
- **Fake powerup** intégré : -5 HP, flash rouge, screenshake 0.35

#### `src/powerups.py`
- 4 types 25% chacun (torpedo/repair/force/fake), `DROP_CHANCE=15%`, `COLLECT_RADIUS=8u`
- Visuels refaits : gemme + label StarJedi + flamme 3 disques `ColorBlendAttrib.MAdd`

#### `src/levels.py`
- Police SFDistantGalaxy lazy singleton
- `start_intro_for_level()` : fondu noir 1→0 sur 1.5s, texte jusqu'à 3s

#### `src/hud.py`
- Trapèzes dégâts repliés vers les bords (EDGE_GAP=0.25, WIDTH=0.30), roll tracking supprimé
- `show_pickup(text, color=None)` : couleur optionnelle
- Barre vie remplacée par 6 segments holographiques (couleur dynamique + blink 1 segment)
- `on_hit()` : flash blanc segments + étincelles orange/blanc — éclair rouge mesh 3D supprimé de `player.py`

#### `src/lunar_base.py`
- `setRenderModeThickness` supprimé (OpenGL Core incompatible)
- Paramètre `bd` (batch partagé) sur `_make_tower/_make_hangar/_make_silo`
- `center_nodes` sur `BaseGroup` pour fade sélectif sans depth sort GPU

#### `src/environment.py`
- L2 fade : seuls les `center_nodes` sont fadés, géométrie opaque reste solide
- Méthodes `toggle_terrain/buildings/fog_debug()` pour isoler les spikes GPU

---

## TODO / Roadmap

Voir [ROADMAP.md](ROADMAP.md) pour le détail complet V1 ✅ + V2 planifié.

Prochaines priorités V2 :
- Performance L2 : audit draw calls, `flattenStrong()` sur groupes bâtiments
- TIEFighter state machine : tuning des transitions et des timings squad
- Comportement boss : distance d'orbite trop courte
- Audio upgrade (musiques ambiantes, dialogues radio)
