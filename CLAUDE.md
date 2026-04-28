# X-Wing Shooter — Instructions pour Claude Code

## Règle absolue : SPEC.md dans chaque commit

**SPEC.md doit être dans le même commit que le code — jamais dans un commit séparé.**

Workflow obligatoire :
```bash
git add fichier_modifie.py SPEC.md && git commit -m "description"
```

- **Bugfix / petit ajustement** : cocher ou noter dans la section TODO suffit
- **Feature / nouveau comportement** : mettre à jour la section du module concerné dans SPEC.md + ajouter une entrée dans l'Historique des versions
- Ne jamais commiter du code sans avoir stagé SPEC.md en même temps

---

## Contexte développeur

Yac (Jean-François Righi), développeur senior C#/.NET. Ce projet est un jeu Python/Panda3D. Pas besoin d'expliquer les concepts de base du code — aller droit au but.

---

## Stack technique

- **Python 3** + **Panda3D 1.10.14+** + **panda3d-gltf 0.13+**
- **Plateforme** : Windows (shell Bash via Git Bash / PowerShell disponible)
- **Lancer le jeu** : activer le venv puis `python main.py`
  ```bash
  source venv/Scripts/activate   # Git Bash
  python main.py
  ```
- **Assets 3D** : format glTF/GLB, chargés via `panda3d-gltf`, auto-scalés à `TARGET_SIZE`

---

## Architecture — rappel rapide

```
main.py → Game (ShowBase)
  ├── src/player.py       Joueur, barrel roll, crosshair
  ├── src/enemies.py      TIE Fighter/Interceptor/Bomber, formations, vagues
  ├── src/lasers.py       Tir, surchauffe, auto-aim
  ├── src/torpedoes.py    Missiles homing
  ├── src/force.py        Bullet-time
  ├── src/boss.py         Boss TIE Advanced
  ├── src/environment.py  Astéroïdes, planètes, nébuleuses
  ├── src/hud.py          HUD holographique
  ├── src/starfield.py    Étoiles + traînées
  ├── src/explosions.py   Particules, débris, popups score
  ├── src/sounds.py       Audio pooling + fallback procédural
  ├── src/powerups.py     Collectibles
  ├── src/levels.py       LevelManager (WIP)
  ├── src/menu.py         Menu principal
  └── src/scores.py       Leaderboard JSON
```

---

## Règles de code

- Ne pas ajouter de commentaires inutiles — le code doit être lisible sans eux
- Ne pas créer de fichiers de documentation supplémentaires — tout va dans SPEC.md
- Ne pas introduire d'abstractions pour de hypothétiques besoins futurs
- Ne pas ajouter de gestion d'erreur pour des cas qui ne peuvent pas arriver
- Conserver le style Python existant (classes par module, passage par instance `Game`)

---

## Fichiers à ne jamais commiter

- `*.exe`, `*.zip`, `*.pdf` — déjà dans `.gitignore`
- `Download/` — assets bruts non intégrés
- `venv/` — environnement virtuel
- `__pycache__/`
- `scores.json` — données locales de leaderboard (peut être commité si intentionnel)

---

## Quand modifier SPEC.md

| Action | Mise à jour SPEC.md |
|--------|---------------------|
| Bugfix mineur | Cocher TODO si applicable |
| Nouveau paramètre de jeu | Mettre à jour le tableau Paramètres |
| Nouveau comportement module | Mettre à jour la section du module |
| Nouvelle feature | Mettre à jour module + ajouter entrée Historique |
| Nouveau module | Ajouter section module complète + entrée Historique |
| Nettoyage / refactor | Entrée Historique courte |
