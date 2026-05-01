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
- **TIEFighter** : 15 u/s, charge à 35 u/s, 2 HP, 2 bolts, équilibré
- **TIEInterceptor** : 20 u/s, charge à 40 u/s, 1 HP, 1 bolt, drift agressif
- **TIEBomber** : 10 u/s, charge à 25 u/s, 4 HP, 2 bolts, tank
- Tous avec modèles 3D texturés + auto-scale
- Accélération kamikaze à l'approche joueur
- Tirs laser verts (EnemyBolt)
- **Formations** : V, ligne, tenaille (pincer), essaim
- **7 vagues** pré-définies + escalade automatique après vague 7

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

### `src/environment.py` — Environnement
- **Astéroïdes** : models texturés (8 variants × 2 packs) + fallback procédural
- **Planètes** : 9 modèles chargés (non spawnés actuellement — WIP)
- **Nébuleuses** : éléments colorés procéduraux en arrière-plan
- **Débris** : objets flottants

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
- LevelManager : 4 niveaux thématiques + boss
- Infrastructure en place, non entièrement câblé (WIP)

### `src/powerups.py` — Collectibles
- 20% de chance de drop par kill ennemi
- **Torpedo** : +3 ammo (poids 60%)
- **Repair** : +2 HP (poids 40%)

### `src/menu.py` — Menu principal
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
- **Texte combo** : `show_combo(count)` — "xN COMBO!" orange pulsant, 1.5s, animé

#### `src/game.py` — Intégration
- Curseur souris masqué en jeu (`setCursorHidden(True)`), restauré au menu
- `Screenshake` instancié dans `start_game()`, `update()` chaque frame, `reset()` au restart
- `time_scale` combo slow-mo (×0.65 pendant 0.4s, 3 kills en 2s) combiné avec `force.get_time_scale()`
- Explosion preset par classe ennemi (TIEBomber → medium, autres → small)
- Torpilles : impact principal → medium, splash et kills → small
- Boss mort → preset large + screenshake 1.0 + screen flash 0.4

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
