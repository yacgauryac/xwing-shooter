"""
settings.py — Configuration centrale du jeu X-Wing Shooter.
Modifie ce fichier pour tweaker gameplay et visuels sans toucher au code moteur.
"""

# ── Paramètres par niveau ──────────────────────────────────────
# Champs disponibles :
#   scroll_speed   : vitesse de défilement (unités/s)
#   bounds_x       : limite gauche/droite du joueur (symétrique)
#   player_hp      : points de vie au départ
#   no_enemies     : True = pas d'ennemis (spawner stoppé)
#   debug_ruler    : True = règle debug affichée au démarrage
#   env_level      : niveau environnement à utiliser (None = même que level id)
LEVEL_SETTINGS = {
    0: {   # Sandbox — surface lunaire sans ennemis
        "scroll_speed":  16.0,
        "bounds_x":      14.0,
        "player_hp":     999,
        "no_enemies":    True,
        "debug_ruler":   True,
        "env_level":     2,       # Utilise l'environnement de L2 (Lunar Surface)
    },
    1: {
        "scroll_speed":  40.0,
        "bounds_x":      14.0,
        "player_hp":     50,
    },
    2: {
        "scroll_speed":  38.0,
        "bounds_x":      12.0,
        "player_hp":     50,
    },
    3: {
        "scroll_speed":  45.0,
        "bounds_x":      11.0,
        "player_hp":     50,
    },
    4: {
        "scroll_speed":  42.0,
        "bounds_x":      14.0,
        "player_hp":     50,
    },
    99: {  # Debug asteroids
        "scroll_speed":  40.0,
        "bounds_x":      14.0,
        "player_hp":     100,
        "no_enemies":    True,
    },
}

# ── Configuration surface lunaire (L2 + L0 sandbox) ───────────

LUNAR = {
    # Espacement entre groupes de bâtiments (unités Y, random entre min et max)
    "base_spacing_min":  45,
    "base_spacing_max":  65,

    # Layouts autorisés — None = tous les layouts du pool.
    # Mettre une liste pour tester un layout spécifique, ex :
    #   ["outpost"] ou ["runway", "compound"]
    # Layouts disponibles : runway, platform 2, compound, tower_row,
    #                        industrial, fortress 1, outpost, depot, mixed
    "enabled_layouts":   [  "runway" ],

    # Espacement entre les montagnes de bord (unités Y, random entre min et max)
    "mountain_spacing_min": 22.0,
    "mountain_spacing_max": 38.0,
}


# ── Types de bâtiments ─────────────────────────────────────────
# mesh     : nom de la fonction _make_<mesh> dans lunar_base.py
# hw/hd/h  : [min, max] demi-dimensions (float). h = hauteur totale.
# hb_scale : facteur hitbox (1.0 = pleine taille, 0.75 = réduit pour cylindres)
BUILDING_TYPES = {
    "tower": {
        "mesh": "tower",
        "hw": [0.50, 0.60], "hd": [0.50, 0.60], "h": [8.0, 15.0],
        "hb_scale": 1.0,
    },
    "hangar": {
        "mesh": "hangar",
        "hw": [2.5, 4.5], "hd": [3.0, 5.5], "h": [4.5, 8.0],
        "hb_scale": 1.0,
    },
    "silo": {
        "mesh": "silo",
        "hw": [0.7, 1.2], "hd": [0.7, 1.2], "h": [6.0, 12.0],
        "hb_scale": 0.72,   # cylindre — réduit les coins fantômes
    },
    "bunker": {
        "mesh": "bunker",
        "hw": [1.8, 3.0], "hd": [1.8, 3.0], "h": [3.0, 6.0],
        "hb_scale": 1.0,
    },
    "antenna": {
        "mesh": "antenna",
        "hw": [0.10, 0.10], "hd": [0.10, 0.10], "h": [10.0, 18.0],
        "hb_scale": 1.0,
    },
    "pad": {
        "mesh": "pad",
        "hw": [2.5, 4.5], "hd": [2.5, 4.5], "h": [0.30, 0.30],
        "hb_scale": 1.0,
    },
    "relay": {
        "mesh": "relay",
        "hw": [0.4, 0.7], "hd": [0.4, 0.7], "h": [7.0, 13.0],
        "hb_scale": 0.72,   # cylindre
    },
}

# ── Layouts de groupes de bâtiments ───────────────────────────
# Chaque entrée de layout est un dict de placement :
#   type     : clé dans BUILDING_TYPES
#   count    : int ou [min, max] — nombre d'instances
#   x        : [min, max] valeur absolue de X (si sides=true, ±x)
#   y        : [min, max]
#   scale    : [min, max] facteur d'échelle (défaut [1.0, 1.0])
#   sides    : true → place en ±x symétrique (une instance par côté × count)
#   prob     : probabilité de placer chaque instance (défaut 1.0)
#   min_abs_x: |x| minimum (pour antennes loin du centre)
LAYOUTS = {
    "runway": [
        {"type": "tower",   "sides": True,  "x": [8.0, 12.0], "y": [-4.0, 4.0],  "count": 1, "scale": [1.0, 1.4]},
        {"type": "hangar",  "sides": True,  "x": [6.0, 11.0], "y": [-8.0, 8.0],  "count": 1, "prob": 0.6},
        {"type": "silo",    "sides": True,  "x": [8.0, 13.0], "y": [-9.0, 9.0],  "count": [2, 3]},
        {"type": "antenna", "sides": False, "x": [-13.0, 13.0], "y": [-10.0, 10.0], "count": [2, 4], "min_abs_x": 5.0},
    ],
    "platform": [
        {"type": "pad",     "sides": False, "x": [-2.0, 2.0],  "y": [-2.0, 2.0],  "count": 1, "scale": [1.3, 1.3]},
        {"type": "tower",   "sides": False, "x": [7.0, 11.0],  "y": [-3.0, 3.0],  "count": 1, "scale": [1.4, 1.4]},
        {"type": "relay",   "sides": False, "x": [-11.0, -7.0],"y": [-3.0, 3.0],  "count": 1, "scale": [1.2, 1.2]},
        {"type": "bunker",  "sides": False, "x": [-11.0, 11.0],"y": [-11.0, 11.0],"count": [2, 3]},
        {"type": "silo",    "sides": False, "x": [-11.0, 11.0],"y": [-9.0, 9.0],  "count": [0, 1]},
        {"type": "antenna", "sides": False, "x": [-12.0, 12.0],"y": [-9.0, 9.0],  "count": [2, 3], "min_abs_x": 5.0},
    ],
    "compound": [
        {"type": "hangar",  "sides": True,  "x": [8.0, 12.0],  "y": [-5.0, 5.0],  "count": 1, "scale": [1.1, 1.4]},
        {"type": "silo",    "sides": False, "x": [-14.0, 14.0],"y": [-9.0, 9.0],  "count": [3, 5], "min_abs_x": 8.0},
        {"type": "bunker",  "sides": False, "x": [-11.0, 11.0],"y": [-9.0, 9.0],  "count": [1, 3], "min_abs_x": 5.0},
        {"type": "tower",   "sides": True,  "x": [9.0, 13.0],  "y": [-8.0, 8.0],  "count": 1, "scale": [1.0, 1.3]},
        {"type": "antenna", "sides": False, "x": [-13.0, 13.0],"y": [-10.0, 10.0],"count": [2, 3], "min_abs_x": 5.0},
    ],
    "tower_row": [
        {"type": "tower",   "sides": True,  "x": [8.0, 12.0],  "y": [-10.0, 10.0],"count": [3, 5], "scale": [1.0, 1.5]},
        {"type": "hangar",  "sides": True,  "x": [9.0, 13.0],  "y": [-6.0, 6.0],  "count": 1, "prob": 0.5, "scale": [1.2, 1.2]},
        {"type": "antenna", "sides": False, "x": [-14.0, 14.0],"y": [-9.0, 9.0],  "count": [1, 3], "min_abs_x": 6.0},
    ],
    "industrial": [
        {"type": "silo",    "sides": False, "x": [-14.0, -7.0],"y": [-6.0, 6.0],  "count": [3, 4], "scale": [1.0, 1.5]},
        {"type": "bunker",  "sides": False, "x": [-3.0, 3.0],  "y": [-8.0, 8.0],  "count": [2, 3], "scale": [1.1, 1.4]},
        {"type": "relay",   "sides": False, "x": [7.0, 13.0],  "y": [-9.0, 9.0],  "count": [1, 2], "scale": [1.0, 1.3]},
        {"type": "antenna", "sides": False, "x": [-13.0, 13.0],"y": [-10.0, 10.0],"count": [1, 2]},
    ],
    "fortress": [
        {"type": "tower",   "sides": True,  "x": [9.0, 13.0],  "y": [-11.0, 11.0],"count": 2, "scale": [1.3, 1.8]},
        {"type": "bunker",  "sides": False, "x": [-8.0, 8.0],  "y": [-9.0, 9.0],  "count": [2, 3], "scale": [1.2, 1.6]},
        {"type": "pad",     "sides": False, "x": [-2.0, 2.0],  "y": [-2.0, 2.0],  "count": 1, "scale": [1.1, 1.1]},
        {"type": "relay",   "sides": False, "x": [3.0, 6.0],   "y": [-3.0, 3.0],  "count": 1},
        {"type": "antenna", "sides": False, "x": [-14.0, 14.0],"y": [-10.0, 10.0],"count": [1, 2], "min_abs_x": 5.0},
    ],
    "outpost": [
        {"type": "tower",   "sides": False, "x": [-3.0, 3.0],  "y": [-3.0, 3.0],  "count": 1, "scale": [1.8, 1.8]},
        {"type": "silo",    "sides": False, "x": [-14.0, 14.0],"y": [-10.0, 10.0],"count": [2, 3], "min_abs_x": 7.0},
        {"type": "relay",   "sides": False, "x": [-14.0, 14.0],"y": [-10.0, 10.0],"count": [0, 1], "min_abs_x": 7.0},
        {"type": "bunker",  "sides": False, "x": [-14.0, 14.0],"y": [-10.0, 10.0],"count": [0, 1], "min_abs_x": 7.0},
        {"type": "antenna", "sides": False, "x": [-14.0, 14.0],"y": [-10.0, 10.0],"count": [2, 4], "min_abs_x": 4.0},
    ],
    "depot": [
        # Hangars repoussés sur les flancs (x ≥ 8) — couloir central libre
        {"type": "hangar",  "sides": True,  "x": [8.0, 12.0],  "y": [-4.0, 4.0],  "count": 1, "scale": [1.0, 1.2]},
        # Silos symétriques à partir de x=4, pas au centre
        {"type": "silo",    "sides": True,  "x": [4.0, 9.0],   "y": [-9.0, 9.0],  "count": [2, 3]},
        {"type": "relay",   "sides": True,  "x": [10.0, 14.0], "y": [-5.0, 5.0],  "count": 1, "scale": [1.1, 1.1]},
        {"type": "antenna", "sides": False, "x": [-14.0, 14.0],"y": [-10.0, 10.0],"count": 1, "min_abs_x": 8.0},
    ],
    "mixed": [
        {"type": "tower",   "sides": True,  "x": [8.0, 12.0],  "y": [-4.0, 4.0],  "count": 1, "scale": [1.0, 1.4]},
        {"type": "hangar",  "sides": False, "x": [-10.0, 10.0],"y": [-6.0, 6.0],  "count": 1, "min_abs_x": 5.0, "prob": 0.6},
        {"type": "silo",    "sides": True,  "x": [8.0, 13.0],  "y": [-9.0, 9.0],  "count": [1, 2]},
        {"type": "bunker",  "sides": False, "x": [-11.0, 11.0],"y": [-8.0, 8.0],  "count": [1, 2], "min_abs_x": 6.0, "prob": 0.6},
        {"type": "relay",   "sides": False, "x": [-12.0, 12.0],"y": [-8.0, 8.0],  "count": 1, "min_abs_x": 8.0},
        {"type": "antenna", "sides": False, "x": [-13.0, 13.0],"y": [-10.0, 10.0],"count": [1, 3], "min_abs_x": 5.0},
    ],
}


# ── Helpers ────────────────────────────────────────────────────

_DEFAULTS = {
    "scroll_speed": 40.0,
    "bounds_x":     14.0,
    "player_hp":    50,
    "no_enemies":   False,
    "debug_ruler":  False,
    "env_level":    None,
}


def get_level(level_id: int) -> dict:
    """Retourne le dict de settings pour un niveau donné, avec valeurs par défaut."""
    cfg = dict(_DEFAULTS)
    cfg.update(LEVEL_SETTINGS.get(level_id, {}))
    if cfg["env_level"] is None:
        cfg["env_level"] = level_id
    return cfg
