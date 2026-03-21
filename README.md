# X-Wing Shooter 🚀

Rail shooter 3D inspiré de Star Wars, développé en Python avec Panda3D.

## Setup

```bash
git clone https://github.com/yacgauryac/xwing-shooter.git
cd xwing-shooter
python -m venv venv
venv\Scripts\activate        # Windows (PowerShell/CMD)
source venv/Scripts/activate # Windows (Git Bash)
pip install panda3d panda3d-gltf
python main.py
```

Relancer ensuite :
```bash
cd xwing-shooter
venv\Scripts\activate
python main.py
```

## Contrôles

| Touche | Action |
|--------|--------|
| ZQSD / Flèches | Déplacement |
| Espace / Clic gauche | Tir |
| Double-tap gauche/droite | Barrel roll (esquive + invincibilité) |
| M | Sons on/off |
| F11 | Plein écran |
| F1 | FPS counter |
| R | Restart (game over) |
| Échap | Quitter |

## Features

### Joueur
- Modèle X-Wing texturé (Daniel Andersson) avec auto-scale
- Déplacement fluide avec interpolation lerp + normalisation diagonale
- Rotation visuelle (roll/pitch) en fonction du mouvement
- Barrel roll : double-tap, esquive latérale, invincibilité temporaire, effets visuels (flash, speed lines oranges, zoom FOV, traînées bleues spirale)
- Réticule de visée spring-damper (pendule physique avec inertie et overshoot)
- 4 lumières moteurs aux bouts des ailes (pulse rouge ↔ orange)
- Lumière dédiée éclairant le vaisseau par-dessus

### Combat
- Tir en paires alternées depuis 4 canons (2 bolts par salve)
- Couleurs laser alternées : rouge/rose et orange/jaune
- Noyau blanc + halo coloré pour chaque bolt
- Système de surchauffe avec jauge (overheat → cooldown forcé 2.5s)
- Auto-aim léger (15%) vers l'ennemi le plus proche

### Ennemis
- 3 types : TIE Fighter (équilibré), TIE Interceptor (rapide/fragile), TIE Bomber (tank/lent)
- Tous avec modèles 3D texturés + auto-scale
- Accélération kamikaze à l'approche du joueur
- Tirs laser verts (2 bolts pour Fighter/Bomber, 1 pour Interceptor)
- Drift latéral aléatoire (plus agressif pour l'Interceptor)
- Positions clampées dans la zone jouable

### Formations et vagues
- 4 formations : V, ligne, tenaille (pincer), essaim
- 7 vagues pré-définies avec mix de types croissant
- Escalade automatique après vague 7 (ennemis supplémentaires)
- Annonce "WAVE X INCOMING" avec fade out

### Explosions
- Boule de feu multi-couche : flash blanc/jaune → expansion orange/rouge → fumée grise
- Couleurs évoluent : jaune → orange → rouge → noir
- 6 débris solides (triangles gris qui volent et tournent)
- Score popup "+100" qui monte et fade

### Environnement
- 1000 étoiles avec traînées filantes proportionnelles à la vitesse
- Astéroïdes procéduraux (sphères déformées, palette grise, collision joueur)
- Amas d'astéroïdes texturés en fond (2 packs Sketchfab)
- 2 planètes procédurales fixes qui grossissent lentement
- Nébuleuses colorées en arrière-plan
- Débris flottants

### HUD
- Style holographique orange/ambre (Elite Dangerous)
- Bandeau supérieur semi-transparent : score, vague, hostiles
- Jauge shield en arc de cercle (vert → jaune → rouge)
- Jauge heat en arc de cercle (orange → rouge, clignote en surchauffe)
- Flash de dégât orange
- Écran Game Over avec score final

### Audio
- Sons procéduraux générés en WAV (laser, explosion, hit, overheat)
- Toggle on/off avec M

### Technique
- Auto-scale de tous les modèles 3D (TARGET_SIZE)
- Cache de modèles (chaque type chargé une fois, instances copiées)
- Plein écran F11
- FPS counter F1
- Game over + restart complet (nettoyage de toutes les entités)

## Structure

```
main.py                  # Entry point + gltf patch
src/
  game.py                # Boucle principale, collisions, vagues
  player.py              # X-Wing, mouvement, barrel roll, réticule, lumières
  enemies.py             # Bestiaire TIE, formations, spawner
  lasers.py              # Tir par paires, surchauffe, auto-aim
  environment.py         # Astéroïdes, planètes, amas, nébuleuses, débris
  hud.py                 # HUD holographique
  starfield.py           # Étoiles + traînées de vitesse
  explosions.py          # Boule de feu + débris + score popup
  sounds.py              # Sons procéduraux WAV
assets/models/
  xwing/                 # X-Wing (Daniel Andersson, Sketchfab, CC-BY)
  tie_fighter/           # TIE Fighter (Daniel Andersson)
  tie_interceptor/       # TIE Interceptor (Daniel Andersson)
  tie_bomber/            # TIE Bomber (Daniel Andersson)
  star_destroyer/        # Imperial Star Destroyer (Daniel Andersson)
  planets/               # 9 planètes texturées (Sketchfab)
  asteroids/             # Pack astéroïdes 1 — 8 amas texturés (Sereib, Sketchfab)
  asteroids2/            # Pack astéroïdes 2 — amas texturé (Sketchfab)
assets/
  hud_overlay.png        # Overlay HUD généré par IA (WIP, pas encore intégré)
```

## TODO

- [ ] HUD overlay PNG en 16:9 (le code d'intégration est prêt)
- [ ] Intégrer les planètes texturées du pack (9 modèles)
- [ ] Sons améliorés (vrais fichiers audio)
- [ ] Boss fight (Star Destroyer avec tourelles)
- [ ] Niveaux thématiques (surface planète, champ d'astéroïdes, station)
- [ ] Menu principal (écran titre, options)
- [ ] V2 Free Flight (nouveau projet, ~80% code réutilisable)

## Crédits modèles 3D

- Vaisseaux par [Daniel Andersson](https://sketchfab.com/DanielAndersson) — CC Attribution
- Astéroïdes par [Sereib](https://sketchfab.com/Sereib) et autres — CC Attribution
