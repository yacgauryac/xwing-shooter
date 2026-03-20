# X-Wing Shooter 🚀

Rail shooter 3D inspiré de Star Wars, développé en Python avec Panda3D.

## Setup

```bash
git clone https://github.com/yacgauryac/xwing-shooter.git
cd xwing-shooter
python -m venv venv
venv\Scripts\activate        # Windows
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
| Espace | Tir |
| Double-tap gauche/droite | Barrel roll (esquive + invincibilité) |
| M | Sons on/off |
| F11 | Plein écran |
| F1 | FPS counter |
| R | Restart (game over) |
| Échap | Quitter |

## Features

- 3 types d'ennemis : TIE Fighter, TIE Interceptor, TIE Bomber
- Formations : V, ligne, tenaille, essaim
- Accélération kamikaze des ennemis
- Système de surchauffe des lasers
- Auto-aim léger
- Barrel roll avec traînées
- Réticule spring-damper (pendule physique)
- HUD holographique style Elite Dangerous
- Star Destroyer en décor de fond
- Planètes procédurales
- Astéroïdes déformés avec collisions
- Sons procéduraux
- Vagues infinies avec difficulté croissante

## Structure

```
main.py                  # Entry point + gltf patch
src/
  game.py                # Boucle principale
  player.py              # X-Wing, mouvement, barrel roll, réticule
  enemies.py             # Bestiaire TIE, formations, vagues
  lasers.py              # Tir, surchauffe, auto-aim
  environment.py         # Astéroïdes, planètes, Star Destroyer, nébuleuses
  hud.py                 # HUD holographique (Elite Dangerous style)
  starfield.py           # Étoiles + traînées de vitesse
  explosions.py          # Particules d'explosion
  sounds.py              # Sons procéduraux
assets/models/
  xwing/                 # X-Wing (Daniel Andersson, Sketchfab, CC-BY)
  tie_fighter/           # TIE Fighter (Daniel Andersson)
  tie_interceptor/       # TIE Interceptor (Daniel Andersson)
  tie_bomber/            # TIE Bomber (Daniel Andersson)
  star_destroyer/        # Imperial Star Destroyer (Daniel Andersson)
  planets/               # 9 planètes texturées (Sketchfab)
```

## Crédits modèles 3D

Tous les modèles par [Daniel Andersson](https://sketchfab.com/DanielAndersson) — CC Attribution.
