# X-Wing Shooter 🚀

Rail shooter 3D inspiré de Star Wars, développé en Python avec Panda3D.

## Concept

Tu pilotes un X-Wing vu de derrière (style Star Fox / Rebel Assault). Le décor défile, des ennemis arrivent, tu esquives et tu tires.

## Roadmap

- [x] Setup projet + structure
- [ ] Phase 1 — Fenêtre 3D, fond étoilé, vaisseau, déplacement souris
- [ ] Phase 2 — Tir laser, ennemis basiques (TIE Fighters)
- [ ] Phase 3 — Collisions, explosions, score
- [ ] Phase 4 — Vagues d'ennemis, difficulté progressive
- [ ] Phase 5 — HUD (vie, score, munitions), sons
- [ ] Phase 6 — Boss fight (Star Destroyer?)
- [ ] Bonus — Sabre laser FPS (projet suivant)

## Setup

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/xwing-shooter.git
cd xwing-shooter

# Environnement virtuel
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Dépendances
pip install -r requirements.txt

# Lancer le jeu
python main.py
```

## Stack

- **Python 3.10+**
- **Panda3D** — moteur 3D
- Modèles 3D procéduraux (pour commencer), puis assets custom

## Contrôles

- **Souris** — Déplacer le vaisseau
- **Clic gauche** — Tirer
- **Espace** — Tir spécial (à venir)
- **Échap** — Quitter

## Structure

```
xwing-shooter/
├── main.py              # Point d'entrée
├── requirements.txt
├── assets/
│   ├── models/
│   ├── textures/
│   └── sounds/
└── src/
    ├── __init__.py
    ├── game.py          # Classe principale du jeu
    ├── player.py        # X-Wing du joueur
    └── enemies.py       # TIE Fighters et autres
```
