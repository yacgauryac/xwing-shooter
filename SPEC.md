# X-Wing Shooter — Spécifications & Historique des versions

## Vue d'ensemble

Rail shooter 3D en Python/Panda3D, thème Star Wars. Le joueur pilote un X-Wing contre des vagues de TIE Fighters, avec une progression de difficulté et un boss. L'objectif est de maximiser son score et d'entrer dans le leaderboard top 10.

**Stack :** Python 3, Panda3D 1.10.14+, panda3d-gltf 0.13+  
**Plateforme :** Windows / Linux  
**Fenêtre :** 1280×720 (F11 = plein écran)

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
- Déclenché à partir de la vague 2
- 50 HP, tirs bolts verts
- 3 phases comportementales
- Défaite détectée → fin de séquence boss

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
