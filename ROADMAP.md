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

### Priorité haute

#### 1. Visuels distincts par niveau
- [ ] L1 (Champ d'astéroïdes) : actuel ✅
- [ ] L2 (Surface lunaire) : plan de terrain, tourelles sol, éclairage monochrome
- [ ] L3 (Tranchée) : murs latéraux défilants, espace étroit, éclairage industriel
- [ ] L4 (Nébuleuse) : volume de brouillard, faible visibilité, particules, éclairage tamisé
- [ ] Couleur de fond change par niveau

#### 2. Nouveaux ennemis
- [ ] Imperial Shuttle — lent, résistant, bon loot
- [ ] Attack Bomber — plus lourd que TIE Bomber
- [ ] Probe Droid — rapide, erratique
- [ ] Ennemis sol / tourelles (niveaux surface)

#### 3. Boss améliorés
- [x] Boss TIE Advanced — Utility AI (8 actions, scoring dynamique, mouvement adaptatif)
- [ ] Star Destroyer (phase 2) — tourelles destructibles, générateurs de bouclier
- [ ] Intro boss avec dialogue radio

#### 4. Audio upgrade
- [ ] Musiques ambiantes — menu, combat, boss, victoire
- [ ] Dialogues radio ("Rebel squadron, engage!", "Enemy destroyed!", …)
- [ ] Gestion volume dynamique

#### 5. Effets caméra / visuels
- [ ] Screenshake sur grosses explosions
- [ ] Légère inclinaison écran au barrel roll
- [ ] Angles cinématiques optionnels

---

### Priorité moyenne

#### 6. Game feel
- [ ] Traînées particules sur lasers
- [ ] Débris d'astéroïdes détruits
- [ ] Impacts visuels sur l'environnement
- [ ] Feedback visuel charge d'arme

#### 7. Nouvelles mécaniques
- [ ] Difficulté — easy / normal / hard
- [ ] Système de vies — 3 vaisseaux, perd 1 par mort
- [ ] Combo — bonus kills consécutifs sans dégâts
- [ ] Variantes d'armes — spread shot, charged shot

#### 8. Contenu
- [ ] Plus de formations ennemies
- [ ] Dangers environnementaux (zones radiation, tempêtes d'astéroïdes)
- [ ] Mini-boss entre niveaux
- [ ] Power-ups d'armes alternatifs

---

### Priorité basse

#### 9. QoL
- [ ] Persistance paramètres (volume, difficulté, remapping touches)
- [ ] Tutoriel / hints premier lancement
- [ ] Stats (kills totaux, streak max, arme favorite)
- [ ] Unlockables (skins, variantes vaisseaux)

#### 10. Post-game
- [ ] Mode survie infini
- [ ] Mode défi (patterns de vagues spécifiques)
- [ ] Éditeur de difficulté custom
- [ ] Système de replay (save + playback)

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
