"""
Wave Configuration — Format declaratif pour definir les vagues par niveau.

Pour creer/modifier un niveau : editer LEVEL_X_WAVES ci-dessous.
Chaque vague est un dict avec :
  - enemies      : dict {"nom_ennemi": quantite}
  - delay_before : (optionnel) secondes avant le debut de la vague (defaut 1.5)
  - spawn_interval: (optionnel) secondes entre chaque spawn (defaut 0.5)

Positionnement de spawn : automatique.
  N entrees → N zones du plan XZ (1=centre, 2=gauche+droite, 4=quadrants, etc.)
  Le champ "formation" est ignore s'il est present (conserve pour retrocompat).
"""

# ============================================================
# Registre des ennemis — nom lisible → classe (lazy pour éviter import circulaire)
# ============================================================

_ENEMY_REGISTRY = None


def _get_registry():
    """Charge le registre à la première utilisation (évite circular import avec enemies.py)."""
    global _ENEMY_REGISTRY
    if _ENEMY_REGISTRY is None:
        from src.enemies import (
            TIEFighter, TIEInterceptor, TIEBomber,
            ImperialShuttle, AttackBomber, ProbeDroid, GroundTurret,
        )
        _ENEMY_REGISTRY = {
            "tie_fighter":     TIEFighter,
            "tie_interceptor": TIEInterceptor,
            "tie_bomber":      TIEBomber,
            "shuttle":         ImperialShuttle,
            "attack_bomber":   AttackBomber,
            "probe_droid":     ProbeDroid,
            "ground_turret":   GroundTurret,
        }
    return _ENEMY_REGISTRY


# ============================================================
# Definitions des vagues par niveau
# ============================================================

# L1 — Champ d'asteroides : TIE classiques
# tie_fighter: N = N squads de 4. 1 entree = 1 zone d'ecran.
LEVEL_1_WAVES = [
    {"enemies": {"tie_fighter": 4}},
    {"enemies": {"tie_fighter": 8}},
    {"enemies": {"tie_fighter": 16, "tie_interceptor": 4}},
    {"enemies": {"tie_interceptor": 40}},
    {"enemies": {"tie_bomber": 40, "tie_fighter": 8}},
    {"enemies": {"tie_fighter": 2, "tie_interceptor": 3, "tie_bomber": 1}},
    {"enemies": {"tie_interceptor": 4, "tie_bomber": 2, "tie_fighter": 2}},
]
# L2 — Surface lunaire : Shuttles + TIE
LEVEL_2_WAVES = [
    {"enemies": {"tie_fighter": 2, "tie_interceptor": 2}},
    {"enemies": {"shuttle": 1, "tie_fighter": 2}},
    {"enemies": {"shuttle": 2, "tie_interceptor": 3}},
    {"enemies": {"shuttle": 2, "tie_fighter": 2, "tie_bomber": 1}},
    {"enemies": {"shuttle": 1, "tie_interceptor": 4, "tie_bomber": 1}},
    {"enemies": {"shuttle": 2, "tie_bomber": 2, "tie_fighter": 2}},
    {"enemies": {"shuttle": 2, "tie_interceptor": 3, "tie_bomber": 2}},
]

# L3 — Tranchee Death Star : Probe Droids + Attack Bombers + Tourelles
LEVEL_3_WAVES = [
    {"enemies": {"tie_fighter": 2, "probe_droid": 2}},
    {"enemies": {"probe_droid": 5, "tie_interceptor": 2}},
    {"enemies": {"attack_bomber": 1, "tie_fighter": 2, "ground_turret": 2}},
    {"enemies": {"probe_droid": 5, "ground_turret": 3}},
    {"enemies": {"attack_bomber": 2, "tie_interceptor": 3, "probe_droid": 2}},
    {"enemies": {"attack_bomber": 1, "probe_droid": 4, "ground_turret": 3}},
    {"enemies": {"attack_bomber": 2, "tie_interceptor": 3, "ground_turret": 3}},
]

# L4 — Nebuleuse : tout melange, difficulte max
LEVEL_4_WAVES = [
    {"enemies": {"tie_fighter": 2, "probe_droid": 3}},
    {"enemies": {"shuttle": 1, "tie_interceptor": 4}},
    {"enemies": {"attack_bomber": 1, "probe_droid": 2, "tie_fighter": 2}},
    {"enemies": {"probe_droid": 4, "shuttle": 2}},
    {"enemies": {"attack_bomber": 2, "tie_bomber": 2, "probe_droid": 2}},
    {"enemies": {"shuttle": 2, "attack_bomber": 1, "probe_droid": 3}},
    {"enemies": {"attack_bomber": 2, "shuttle": 2, "tie_interceptor": 3}},
]


# Pool d'escalade par niveau (vagues au-dela des definitions)
ESCALATION_POOLS = {
    1: ["tie_fighter", "tie_interceptor", "tie_bomber"],
    2: ["tie_fighter", "tie_interceptor", "shuttle", "ground_turret"],
    3: ["probe_droid", "attack_bomber", "tie_interceptor", "ground_turret"],
    4: ["attack_bomber", "shuttle", "probe_droid", "ground_turret"],
}


# ============================================================
# Assembler le tout — index par niveau
# ============================================================

_WAVES_BY_LEVEL = {
    1: LEVEL_1_WAVES,
    2: LEVEL_2_WAVES,
    3: LEVEL_3_WAVES,
    4: LEVEL_4_WAVES,
}


def _expand_wave(wave_def):
    """Convertit un dict declaratif en format runtime."""
    registry = _get_registry()
    enemy_list = []
    for name, count in wave_def["enemies"].items():
        cls = registry.get(name)
        if cls is None:
            raise ValueError(f"Ennemi inconnu: {name!r}. Disponibles: {list(registry)}")
        enemy_list.extend([cls] * count)
    return {
        "enemies":       enemy_list,
        "delay_before":  wave_def.get("delay_before",   1.5),
        "spawn_interval": wave_def.get("spawn_interval", 0.5),
    }


def get_wave_defs_for_level(level):
    """Retourne la liste des vagues au format runtime pour un niveau donne."""
    raw = _WAVES_BY_LEVEL.get(level, _WAVES_BY_LEVEL[1])
    return [_expand_wave(w) for w in raw]


def get_escalation_pool(level):
    """Retourne la liste de classes pour les vagues au-dela des definitions."""
    registry = _get_registry()
    names = ESCALATION_POOLS.get(level, ESCALATION_POOLS[1])
    return [registry[n] for n in names]
