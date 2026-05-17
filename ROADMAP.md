# X-Wing Shooter — Roadmap

## V1 — COMPLETE ✅

### Gameplay
- [x] Rail shooter — X-Wing avant, joueur en 2D (ZQSD/Flèches)
- [x] 3 types TIE (Fighter, Interceptor, Bomber) + formations
- [x] Lasers — auto-aim 15%, surchauffe, cooldown
- [x] Torpilles — lock-on, splash damage, dumb-fire sans lock
- [x] Power-ups — Repair (+2 HP) & Torpedo (+3), drop 20%
- [x] Force — bullet-time 6s, jauge kills
- [x] Leaderboard persistant top 10 (scores.json + name entry)

### Boss
- [x] Darth Vader TIE Advanced — figure-8, 3 phases HP
  - Phase 1 (100-60%) : tir simple, lent
  - Phase 2 (60-30%) : double tir, plus rapide
  - Phase 3 (<30%) : triple tir, agressif
- [x] Destruction 5s, +5000 pts, écran victoire → leaderboard

### Visuels & Polish
- [x] HUD holographique orange — score/vague/shields/laser/torpilles/force
- [x] Explosions procédurales — flash + fireballs + sparks + débris
- [x] Damage feedback — flash rouge X-Wing + voile HUD bords
- [x] Starfield procédural + scroll infini
- [x] Menu — titre, SOLO/LEADERBOARD/OPTIONS/QUIT
- [x] 4 niveaux avec transitions (vagues 1-4/5-8/9-12/13-16/17+ boss)

### Audio
- [x] Sons laser, explosion, hit, tir ennemi (pool + variation pitch)
- [x] Toggle M, fallback WAV procédural

### Bugs fixés post-V1
- [x] Keys bloquées après restart (A-Z leaderboard écrasait ZQSD)
- [x] Torpilles ne tiraient pas (locking=False avant fire() + LOCK_CONE trop serré)
- [x] Fullscreen crash (`getDisplayWidth` → `pipe.getDisplayWidth/Height`)
- [x] Reset ne relançait pas les ennemis (spawner + environnement non réinitialisés)

---

## V2 — En cours / Planifié

---

### Implémenté — session polish (mai 2026)

#### Caméra & contrôles
- [x] **Vue normale reculée** : `(0,-8,3.5)` → `lookAt(0,22,0)` (était `-4`)
- [x] **Zoom Force ADS** : lerp fluide vers `(0,3,1.8)` quand Force active — style visée FPS
- [x] **Touche 5** : bascule manuelle vue proche/lointaine
- [x] **Caméra avant HUD** dans la boucle `update()` — projection 1-frame synchronisée

#### HUD polish
- [x] **Barres mini-HUD persistantes** — plus de create/destroy chaque frame (fix saccade)
- [x] **WARN/OVERHEAT** : nœud `OnscreenText` pré-alloué, repositionné chaque frame (fix pop)
- [x] **Torpilles** : compteur losange bas-centre + supprimé du mini-HUD
- [x] **Trapèzes dégâts** suivent le roll du vaisseau (`setR(-roll)`)
- [x] **Lumière ambiante par niveau** : données `ambient_color` dans `levels.py` (désactivé — design à revoir)

#### Joueur & effets
- [x] **Hit flash** : ambre chaud `(1.5,0.28,0.06,0.055)` — plus de rouge saturé
- [x] **Bouclier hit** : supprimé (réservé V3 — vrai système de bouclier)
- [x] **SPAWN_PROTECT_Y supprimé** : ennemis touchables dès le spawn
- [x] **Portée bolts** : `MAX_DISTANCE=380u`, `SPEED=115 u/s`
- [x] **Auto-aim lasers supprimé** : conservé uniquement pour torpilles
- [x] **Lumière ambiante revenue** : `(0.15,0.15,0.25)` bleu froid d'origine

#### Building viewer
- [x] Touche **1-7** : jump direct au bâtiment
- [x] Lancement **plein écran** au démarrage
- [x] Hitbox **cyan** (non confondue avec les néons orange)
- [x] **Néons 3 couches** additifs sur tour, hangar, silo, bunker, relay
- [x] **Labels Star Jedi** font impériale sur les bâtiments

---

### Phase P0 — Performance (bloquant)

- [ ] **40fps → diagnostic draw calls** : `panda3d.core.PStatClient` ou `base.setFrameRateMeter(True)` + analyse
- [ ] **`flattenStrong()`** sur les groupes de bâtiments après création (fusionne les GeomNodes, drastique)
- [ ] **Néons : 3 couches → 2** : supprimer la couche bloom (×7) qui coûte cher pour peu de gain à distance de jeu
- [ ] **Faces invisibles meshs** : audit culling `lunar_base.py` — `setTwoSided(True)` ciblé ou inversion normales

---

### Phase P1 — Visuels niveaux (priorité haute)

#### 1. Visuels distincts par niveau
- [x] L1 (Champ d'astéroïdes) : actuel ✅
- [x] L2 (Surface lunaire) : terrain, bâtiments procéduraux, néons impériaux ✅
- [x] L3 (Tranchée Death Star) : murs panelés, textures circuit imprimé ✅
- [ ] **L4 (Nébuleuse)** : brouillard violet dense `(0.05,0.02,0.12)`, onset 40u, opaque 90u — ennemis = silhouettes
- [x] Couleur de fond par niveau ✅

#### 2. Polish bâtiments L2
- [ ] **Néons façade** :
  - Hangars : panneaux lumineux rectangulaires sur façade avant (enseigne impériale)
  - Tours / bunkers : liserés de contour arêtes de la façade principale
- [ ] **Positionnement nombre d'or** (φ=0.618) sur anneaux existants + nouveaux
- [ ] **Lumière ambiante par niveau** : activer `_apply_ambient()` avec couleurs validées par niveau

---

### Phase P2 — Gameplay & UI

#### 3. Menu pause
- [ ] **Touche Échap** en jeu → overlay pause semi-transparent
- [ ] Consolide **toutes les options debug** (touches 1-7 actuelles) dans un menu lisible
- [ ] Options : Reprendre / Recommencer / Menu principal / toggles debug (hitbox, squelette, ruler, cam…)

#### 4. Écran de fin
- [ ] Refonte game over / victoire : récap score, kills par type d'ennemi, vague atteinte

#### 5. Ennemis — comportement
- [ ] **Sonde (ProbeDroid)** : ajouter tirs laser (actuellement muet)
- [ ] **Drift plus agressif** et imprévisible sur Interceptor / ProbeDroid
- [ ] **Spawn plus dense** : moins d'espace entre vagues, plus d'ennemis simultanés
- [ ] **HP et points rééquilibrés** par type (trop faciles actuellement)
- [ ] **Astéroïdes L1** : plus nombreux, plus gros

---

### Phase P3 — Outils & difficulté

#### 6. Éditeur de level (tous niveaux)
- [ ] Vue couloir side-view : visualise le flux des vagues sur un axe Y
- [ ] Placement visuel des groupes d'ennemis par position Y
- [ ] Export vers `wave_config.py` / `WAVE_DEFS_BY_LEVEL`
- [ ] Paramètres par groupe : type, formation, delay, difficulty_scale

#### 7. Debug avancé
- [ ] **Hit debug** : en mode debug, pause auto au hit + flèche 3D + label source de dégât
- [ ] **Squelette** : affiner le rendu debug squelette X-Wing

---

### Priorité haute (existant)

#### 8. Visuels distincts par niveau (suite)

#### 9. Nouveaux ennemis
- [ ] Imperial Shuttle — lent, résistant, bon loot
- [ ] Attack Bomber — plus lourd que TIE Bomber
- [ ] Probe Droid — rapide, erratique
- [ ] Ennemis sol / tourelles (niveaux surface)

#### 10. Boss améliorés
- [x] Boss TIE Advanced — Utility AI (8 actions, scoring dynamique, mouvement adaptatif)
- [ ] Star Destroyer (phase 2) — tourelles destructibles, générateurs de bouclier
- [ ] Intro boss avec dialogue radio

#### 11. Audio upgrade
- [ ] Musiques ambiantes — menu, combat, boss, victoire
- [ ] Dialogues radio ("Rebel squadron, engage!", "Enemy destroyed!", …)
- [ ] Gestion volume dynamique

#### 12. VFX & Game Feel — `VFX_EXPLOSIONS_PROMPT_FR.md`
- [x] **Screenshake** (`src/screenshake.py`) — décroissance quadratique, intensités par événement
  - TIE Fighter mort : 0.15 / 0.2s | TIE Bomber : 0.25 / 0.25s
  - Hit torpille : 0.4 / 0.3s | Joueur touché : 0.5 / 0.3s
  - Transition phase boss : 0.8 / 0.5s | Mort boss : 1.0 / 0.8s
- [x] **Explosions rewrite** (`src/explosions.py`) — 3 presets (small/medium/large)
  - Flash initial (0.1s, blanc chaud `4.0, 3.5, 2.5`)
  - Onde de choc expansive (anneau 0.3→max_r, 0.25s)
  - Fireballs billboard (2-5 boules, expansion 40% + fade, couleurs chaudes uniquement)
  - Étincelles GeomPoints (20-45, vitesse 20-45 u/s, jaune→orange)
  - Débris sombres (`0.08-0.18` gris, gravité légère)
- [x] **Flash écran** (`src/hud.py`) — quad blanc plein écran, 0.15s, grosses explosions et mort boss
- [x] **Slow-motion combo** (`src/game.py`) — 3 kills en 2s → world ×0.65 pendant 0.4s + texte "xN COMBO !"
- [x] **Barre HP boss** — affichée en combat, couleur dynamique, label de phase
- [x] **Curseur souris** masqué en jeu, restauré au menu
- [ ] Légère inclinaison écran au barrel roll
- [ ] Palette stricte : jamais de bleu/vert/violet dans les explosions ✅ (déjà appliquée)

---

### Priorité moyenne

#### 13. Game feel
- [ ] Traînées particules sur lasers
- [ ] Débris d'astéroïdes détruits
- [ ] Impacts visuels sur l'environnement
- [ ] Feedback visuel charge d'arme

#### 14. Nouvelles mécaniques
- [ ] Difficulté — easy / normal / hard
- [ ] Système de vies — 3 vaisseaux, perd 1 par mort
- [ ] Combo — bonus kills consécutifs sans dégâts
- [ ] Variantes d'armes — spread shot, charged shot

#### 15. Contenu
- [ ] Plus de formations ennemies
- [ ] Dangers environnementaux (zones radiation, tempêtes d'astéroïdes)
- [ ] Mini-boss entre niveaux
- [ ] Power-ups d'armes alternatifs

---

### Priorité basse

#### 16. QoL
- [ ] Persistance paramètres (volume, difficulté, remapping touches)
- [ ] Tutoriel / hints premier lancement
- [ ] Stats (kills totaux, streak max, arme favorite)
- [ ] Unlockables (skins, variantes vaisseaux)

#### 17. Post-game
- [ ] Mode survie infini
- [ ] Mode défi (patterns de vagues spécifiques)
- [ ] Éditeur de difficulté custom
- [ ] Système de replay (save + playback)

---

## V3 — Multijoueur LAN — `MULTIJOUEUR_LAN_PROMPT.md`

**Stack :** Python `socket` + `threading` + `json` — UDP, 0 dépendance externe.  
**Architecture :** Host fait autorité (logique, collisions, ennemis) — Client envoie inputs, reçoit état du monde.  
**Latence cible :** <5ms LAN, pas de rollback nécessaire.

### Lancement
```bash
python main.py --host --port 5000          # Joueur 1
python main.py --client --ip 192.168.1.10 --port 5000  # Joueur 2
```

### Étapes d'implémentation
- [ ] **Étape 1 — Réseau de base**
  - `src/network.py` : `NetworkManager` UDP (socket, thread réception, queue thread-safe)
  - Parser `sys.argv` dans `main.py` (--host / --client / --ip / --port)
  - Test ping/pong 2 terminaux
- [ ] **Étape 2 — Synchronisation minimale**
  - Host envoie `world_state` (positions ennemis, bolts, wave, score) à 20 ticks/s
  - Client envoie `player_input` (x, z, shooting, torpedo, barrel_roll) à 20 ticks/s
  - Affichage P2 chez host (même modèle X-Wing, teinte teal `2.5, 3.0, 2.5`)
  - Affichage P1 ghost chez client
- [ ] **Étape 3 — Gameplay complet**
  - Tirs P2 → host calcule collisions → synchronise résultat
  - Score partagé (`shared_score`)
  - HP séparés — si P2 mort, P1 continue seul
  - Game over synchronisé (`{"type": "game_over", "score": ..., "wave": ...}`)
- [ ] **Étape 4 — Polish**
  - Lobby host (affiche IP) + lobby client (saisie IP)
  - Countdown 3-2-1 synchronisé
  - Option COOP LAN dans menu (remplace "COMING SOON")
  - Reconnexion si coupure (optionnel)

### Format paquets (JSON)
| Direction | Type | Contenu |
|-----------|------|---------|
| Host→Client | `world_state` | enemies[], bolts_enemy[], p2_hp, score, wave |
| Client→Host | `player_input` | x, z, shooting, torpedo, barrel_roll |
| Événements | `explosion`, `enemy_killed`, `game_over`, `phase_change` | selon type |

### Notes techniques
- Thread réseau séparé — jamais bloquer le thread Panda3D
- UDP : pertes <0.1% en LAN, positions envoyées 20×/s → paquet perdu invisible
- Pas de simulation déterministe : effets (particules) locaux à chaque machine
- Firewall Windows : autoriser Python sur le port UDP si 2 PCs différents

---

## Paramètres clés V1 (référence)

| Paramètre | Valeur |
|-----------|--------|
| PLAYER_MAX_HP | 10 |
| Scroll speed | 40.0 u/s |
| Laser range | 120u, auto-aim 15%, overheat 2.0s, cooldown 1.5s |
| TIE Fighter | speed 18-65, fire 2.5-5s, HP 2 |
| TIE Interceptor | speed 25-80, fire 1.5-3s, HP 1 |
| TIE Bomber | speed 10-30, fire 3-6s, HP 4 |
| Torpilles | 3 init, max 9, lock 120u, cooldown 1s |
| Force | fills 8/10/12/5 pts (Fighter/Interceptor/Bomber/torpedo), 6s, ×0.3 |
| Boss TIE Advanced | 50 HP, fire 1.2/0.7/0.4s (phases), speed 25+phase×8 |
| Boss trigger | Vague 8+ |

## Niveaux V1

| Niveau | Vagues | Environnement |
|--------|--------|---------------|
| L1 | 1-4 | Champ d'astéroïdes |
| L2 | 5-8 | — (à venir V2) |
| L3 | 9-12 | — (à venir V2) |
| L4 | 13-16 | — (à venir V2) |
| Boss | 17+ | TIE Advanced |

## Notes dev

- **BOSS_TRIGGER_WAVE = 3** pour tester le boss rapidement, remettre à 8 avant commit
- Limites perf : <100 particules/frame, <20 ennemis/écran, <50 bolts laser actifs
- Collision : distance check uniquement (pas de géométrie)
- Assets dispo non intégrés : planètes (9 modèles), Star Destroyer, hud_overlay.png
