"""
Net Protocol — Types de messages pour le réseau UDP LAN.

Architecture : host-autoritaire, 20Hz tick, JSON sérialisé.
Ce fichier définit les constantes et structures de messages.
"""

import json
import time

# ============================================================
# Types de messages
# ============================================================

MSG_HANDSHAKE = "handshake"
MSG_HANDSHAKE_ACK = "handshake_ack"
MSG_DISCONNECT = "disconnect"
MSG_PLAYER_INPUT = "player_input"
MSG_WORLD_STATE = "world_state"
MSG_EVENT = "event"

# ============================================================
# Événements (sous-types de MSG_EVENT)
# ============================================================

EVT_EXPLOSION = "explosion"
EVT_KILL = "kill"
EVT_POWERUP = "powerup"
EVT_WAVE_START = "wave_start"
EVT_GAME_OVER = "game_over"


# ============================================================
# Construction de messages
# ============================================================

def make_handshake(player_name="Player"):
    """Client → Host : demande de connexion."""
    return {
        "type": MSG_HANDSHAKE,
        "name": player_name,
        "timestamp": time.time(),
    }


def make_handshake_ack(player_id, level):
    """Host → Client : acceptation de connexion."""
    return {
        "type": MSG_HANDSHAKE_ACK,
        "player_id": player_id,
        "level": level,
        "timestamp": time.time(),
    }


def make_disconnect(reason="quit"):
    """Déconnexion propre (les deux sens)."""
    return {
        "type": MSG_DISCONNECT,
        "reason": reason,
        "timestamp": time.time(),
    }


def make_player_input(x, z, fire, torpedo, barrel_roll, force_active):
    """Client → Host : état des inputs du joueur."""
    return {
        "type": MSG_PLAYER_INPUT,
        "x": x,
        "z": z,
        "fire": fire,
        "torpedo": torpedo,
        "barrel_roll": barrel_roll,
        "force_active": force_active,
        "timestamp": time.time(),
    }


def make_world_state(players, enemies, bolts, score, wave):
    """Host → Client : snapshot autoritaire du monde (20Hz)."""
    return {
        "type": MSG_WORLD_STATE,
        "players": players,       # [{id, x, y, z, hp, shield}, ...]
        "enemies": enemies,       # [{id, type, x, y, z, hp}, ...]
        "bolts": bolts,           # [{x, y, z, dx, dy, dz}, ...]
        "score": score,
        "wave": wave,
        "timestamp": time.time(),
    }


def make_event(event_type, **data):
    """Host → Client : événement ponctuel."""
    return {
        "type": MSG_EVENT,
        "event": event_type,
        "data": data,
        "timestamp": time.time(),
    }


# ============================================================
# Sérialisation / Désérialisation
# ============================================================

def encode(msg):
    """Dict → bytes (JSON UTF-8)."""
    return json.dumps(msg, separators=(",", ":")).encode("utf-8")


def decode(data):
    """bytes → dict. Retourne None si invalide."""
    try:
        return json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
