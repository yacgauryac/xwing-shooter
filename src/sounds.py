"""
Sounds v2 — Vrais fichiers audio OGG/WAV + fallback procédural.
Pooling pour les tirs, pitch random, volume par catégorie.
"""

import os
import struct
import math
import random as rnd
from panda3d.core import Filename


# Mapping nom → fichier (cherche .ogg puis .wav)
SOUND_FILES = {
    "laser": "laser_fire",
    "laser_enemy": "laser_enemy",
    "explosion": "explosion_small",
    "explosion_large": "explosion_large",
    "hit": "hit_player",
    "overheat": "overheat",
    "powerup": "powerup_collect",
    "torpedo_fire": "torpedo_fire",
    "torpedo_lock": "torpedo_lock",
    "force_activate": "force_activate",
    "force_ambient": "force_ambient",
    "force_deactivate": "force_deactivate",
    "barrel_roll": "barrel_roll",
    "game_over": "game_over",
    "highscore": "highscore",
}

# Sons qui ont besoin de pooling (plusieurs instances)
POOLED_SOUNDS = {"laser": 8, "explosion": 4, "laser_enemy": 4, "hit": 3}

# Sons avec pitch random
PITCH_RANDOM = {"laser": (0.9, 1.1), "explosion": (0.85, 1.1), "laser_enemy": (0.9, 1.1)}

SOUND_DIR = "assets/sounds"


class SoundManager:
    """Gère tous les sons — fichiers audio + fallback procédural."""

    def __init__(self, game):
        self.game = game
        self.sounds = {}       # nom → AudioSound ou list[AudioSound]
        self.pool_index = {}   # nom → index courant dans le pool
        self.enabled = True
        self.sfx_volume = 0.7
        self.loops = {}        # Sons en boucle actifs

        os.makedirs(SOUND_DIR, exist_ok=True)
        self._generate_fallback_sounds()
        self._load_all_sounds()

    def _find_file(self, base_name):
        """Cherche .ogg puis .wav."""
        for ext in [".ogg", ".wav"]:
            path = f"{SOUND_DIR}/{base_name}{ext}"
            if os.path.exists(path):
                return path
        return None

    def _load_all_sounds(self):
        """Charge tous les sons — fichier audio ou fallback procédural."""
        for name, file_base in SOUND_FILES.items():
            path = self._find_file(file_base)
            if not path:
                # Fallback : cherche l'ancien nom procédural
                path = self._find_file(name)
            if not path:
                continue

            pool_size = POOLED_SOUNDS.get(name, 1)

            try:
                if pool_size > 1:
                    pool = []
                    for _ in range(pool_size):
                        s = self.game.loader.loadSfx(path)
                        if s:
                            s.setVolume(self.sfx_volume)
                            pool.append(s)
                    if pool:
                        self.sounds[name] = pool
                        self.pool_index[name] = 0
                else:
                    s = self.game.loader.loadSfx(path)
                    if s:
                        s.setVolume(self.sfx_volume)
                        self.sounds[name] = s
            except Exception as e:
                print(f"[Sound] Erreur chargement {name}: {e}")

    def play(self, name, volume=None):
        """Joue un son one-shot."""
        if not self.enabled:
            return

        sound_obj = self.sounds.get(name)
        if not sound_obj:
            return

        vol = volume if volume is not None else self.sfx_volume

        # Pool
        if isinstance(sound_obj, list):
            idx = self.pool_index.get(name, 0)
            s = sound_obj[idx % len(sound_obj)]
            self.pool_index[name] = idx + 1
        else:
            s = sound_obj

        s.setVolume(vol)

        # Pitch random
        if name in PITCH_RANDOM:
            lo, hi = PITCH_RANDOM[name]
            s.setPlayRate(rnd.uniform(lo, hi))
        else:
            s.setPlayRate(1.0)

        s.play()

    def play_loop(self, name, volume=None):
        """Joue un son en boucle."""
        if not self.enabled:
            return
        sound_obj = self.sounds.get(name)
        if not sound_obj:
            return
        s = sound_obj[0] if isinstance(sound_obj, list) else sound_obj
        s.setVolume(volume if volume is not None else self.sfx_volume * 0.5)
        s.setLoop(True)
        s.play()
        self.loops[name] = s

    def stop_loop(self, name):
        """Arrête un son en boucle."""
        s = self.loops.pop(name, None)
        if s:
            s.stop()
            s.setLoop(False)

    def stop_all(self):
        """Arrête tous les sons."""
        for name, s in self.loops.items():
            s.stop()
            s.setLoop(False)
        self.loops = {}

    def toggle(self):
        """Toggle mute."""
        self.enabled = not self.enabled
        if not self.enabled:
            self.stop_all()

    # ==========================================
    # FALLBACK : génération procédurale
    # ==========================================

    def _generate_fallback_sounds(self):
        """Génère les sons procéduraux si les fichiers n'existent pas."""
        # Supprime les anciens WAV procéduraux pour les régénérer
        to_regen = {
            "laser_fire": self._make_laser_sound,
            "laser": self._make_laser_sound,
            "laser_enemy": self._make_laser_enemy_sound,
            "explosion_small": self._make_explosion_sound,
            "explosion": self._make_explosion_sound,
            "hit_player": self._make_impact_sound,
            "hit": self._make_impact_sound,
            "overheat": self._make_overheat_sound,
            "force_activate": self._make_force_sound,
        }
        targets = {
            "laser":          f"{SOUND_DIR}/laser.wav",
            "laser_enemy":    f"{SOUND_DIR}/laser_enemy.wav",
            "explosion":      f"{SOUND_DIR}/explosion.wav",
            "hit":            f"{SOUND_DIR}/hit.wav",
            "overheat":       f"{SOUND_DIR}/overheat.wav",
            "force_activate": f"{SOUND_DIR}/force_activate.wav",
        }
        for name, path in targets.items():
            # Cherche d'abord le fichier "officiel" (ex: laser_fire.wav pour "laser")
            official_base = SOUND_FILES.get(name, name)
            if self._find_file(official_base):
                continue  # Fichier audio réel présent — pas de génération procédurale
            if not os.path.exists(path):
                to_regen[name](path)
            elif os.path.getsize(path) < 50000:
                # Régénère si c'est un vieux fichier procédural (< 50KB)
                to_regen[name](path)

    def _make_laser_sound(self, filepath):
        """Laser joueur — sweep descendant court et punchy, style Star Wars."""
        sr = 22050
        dur = 0.12
        n = int(sr * dur)
        samples = []
        for i in range(n):
            t = i / sr
            p = i / n
            # Sweep rapide 1800→600 Hz — classique blaster
            freq = 1800 * (1.0 - p * 0.67)
            # Corps principal
            val  = math.sin(2 * math.pi * freq * t) * 0.55
            # Harmonique legere pour du "grain"
            val += math.sin(2 * math.pi * freq * 1.5 * t) * 0.12
            # Bruit blanc léger en attaque pour le "crack"
            if p < 0.08:
                val += rnd.uniform(-0.3, 0.3) * (1 - p / 0.08)
            # Envelope : attaque instantanée, decay rapide
            env = (1.0 - p) ** 1.4
            samples.append(max(-1, min(1, val * env * 0.55)))
        self._write_wav(filepath, samples, sr)

    def _make_laser_enemy_sound(self, filepath):
        """Laser ennemi — plus grave, plus menaçant, légèrement différent."""
        sr = 22050
        dur = 0.14
        n = int(sr * dur)
        samples = []
        for i in range(n):
            t = i / sr
            p = i / n
            # Sweep grave 600→200 Hz — ennemi plus lourd
            freq = 600 * (1.0 - p * 0.67)
            val  = math.sin(2 * math.pi * freq * t) * 0.5
            val += math.sin(2 * math.pi * freq * 2.0 * t) * 0.18
            val += math.sin(2 * math.pi * freq * 0.5 * t) * 0.15
            # Bruit d'attaque
            if p < 0.06:
                val += rnd.uniform(-0.2, 0.2) * (1 - p / 0.06)
            env = (1.0 - p) ** 1.6
            samples.append(max(-1, min(1, val * env * 0.45)))
        self._write_wav(filepath, samples, sr)

    def _make_explosion_sound(self, filepath):
        """Explosion — impact rapide et fort, decay naturel."""
        sr = 22050
        dur = 0.55
        n = int(sr * dur)
        samples = []
        prev1 = prev2 = 0.0
        for i in range(n):
            t = i / sr
            p = i / n
            # Bruit large bande filtré
            noise = rnd.uniform(-1, 1)
            # Double filtre passe-bas → son "boom"
            f1 = prev1 * 0.65 + noise * 0.35
            f2 = prev2 * 0.80 + f1   * 0.20
            prev1, prev2 = f1, f2
            # Basse fondamentale qui descend
            bass_freq = 80 * (1.0 - p * 0.5)
            bass = math.sin(2 * math.pi * bass_freq * t) * 0.45
            bass += math.sin(2 * math.pi * bass_freq * 2 * t) * 0.15
            val = f2 * 0.55 + bass * 0.45
            # Attaque instantanée, puis decay en puissance
            if p < 0.02:
                env = p / 0.02          # 0→1 en 20ms
            else:
                env = (1.0 - p) ** 1.8
            samples.append(max(-1, min(1, val * env * 0.70)))
        self._write_wav(filepath, samples, sr)

    def _make_impact_sound(self, filepath):
        """Impact joueur — son sourd et bref, pas agressif."""
        sr = 22050
        dur = 0.18
        n = int(sr * dur)
        samples = []
        prev = 0.0
        for i in range(n):
            t = i / sr
            p = i / n
            # Thud grave : bruit filtré basse fréquence
            noise = rnd.uniform(-1, 1)
            filtered = prev * 0.88 + noise * 0.12   # passe-bas fort → sourd
            prev = filtered
            # Léger sinus grave pour l'impact
            thud = math.sin(2 * math.pi * 90 * t) * 0.3
            val = filtered * 0.5 + thud * 0.5
            # Envelope douce : attaque 10ms, decay exponentiel
            if p < 0.06:
                env = p / 0.06
            else:
                env = (1.0 - p) ** 2.5
            samples.append(max(-1, min(1, val * env * 0.30)))  # Volume bas !
        self._write_wav(filepath, samples, sr)

    def _make_overheat_sound(self, filepath):
        """Surchauffe — grésille puis s'éteint."""
        sr = 22050
        dur = 0.9
        n = int(sr * dur)
        samples = []
        prev1 = prev2 = 0.0
        for i in range(n):
            t = i / sr
            p = i / n
            noise = rnd.uniform(-1, 1)
            f1 = prev1 * 0.80 + noise * 0.20
            f2 = prev2 * 0.88 + f1    * 0.12
            prev1, prev2 = f1, f2
            # Grésil haute fréquence + rumble grave
            gresil = math.sin(2 * math.pi * 3200 * t) * rnd.uniform(0, 1) * 0.15
            rumble = math.sin(2 * math.pi * 45 * t) * 0.25
            val = f2 * 0.35 + gresil + rumble
            if p < 0.10:
                env = p / 0.10
            elif p > 0.65:
                env = (1.0 - p) / 0.35
            else:
                env = 1.0
            samples.append(max(-1, min(1, val * env * 0.28)))
        self._write_wav(filepath, samples, sr)

    def _make_force_sound(self, filepath):
        """Activation Force — montée mystique, accord de quinte."""
        sr = 22050
        dur = 0.7
        n = int(sr * dur)
        samples = []
        for i in range(n):
            t = i / sr
            p = i / n
            # Accord de quinte qui monte (Star Wars / mystique)
            f1 = 220 + p * 110          # fondamentale 220→330
            f2 = f1 * 1.5               # quinte
            f3 = f1 * 2.0               # octave
            val  = math.sin(2 * math.pi * f1 * t) * 0.50
            val += math.sin(2 * math.pi * f2 * t) * 0.30
            val += math.sin(2 * math.pi * f3 * t) * 0.15
            # Shimmer : modulation légère de l'amplitude
            val *= 1.0 + 0.08 * math.sin(2 * math.pi * 6 * t)
            # Bruit très léger pour l'air/énergie
            val += rnd.uniform(-0.04, 0.04)
            # Envelope : fade-in 15%, plateau, fade-out 30%
            if p < 0.15:
                env = p / 0.15
            elif p > 0.70:
                env = (1.0 - p) / 0.30
            else:
                env = 1.0
            samples.append(max(-1, min(1, val * env * 0.45)))
        self._write_wav(filepath, samples, sr)

    def _make_wav(self, filepath, freq=440, duration=0.2, volume=0.5,
                  freq_end=None, wave_type="sine"):
        sample_rate = 22050
        num_samples = int(sample_rate * duration)
        if freq_end is None:
            freq_end = freq
        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            progress = i / num_samples
            f = freq + (freq_end - freq) * progress
            if wave_type == "sine":
                val = math.sin(2 * math.pi * f * t)
            elif wave_type == "noise":
                val = rnd.uniform(-1, 1) * math.sin(2 * math.pi * f * t * 0.5)
            else:
                val = math.sin(2 * math.pi * f * t)
            envelope = 1.0 - progress
            val *= volume * envelope
            samples.append(max(-1, min(1, val)))
        self._write_wav(filepath, samples, sample_rate)

    def _write_wav(self, filepath, samples, sample_rate):
        with open(filepath, 'wb') as f:
            num_channels = 1
            bits = 16
            byte_rate = sample_rate * num_channels * bits // 8
            block_align = num_channels * bits // 8
            data_size = len(samples) * block_align
            f.write(b'RIFF')
            f.write(struct.pack('<I', 36 + data_size))
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write(struct.pack('<I', 16))
            f.write(struct.pack('<H', 1))
            f.write(struct.pack('<H', num_channels))
            f.write(struct.pack('<I', sample_rate))
            f.write(struct.pack('<I', byte_rate))
            f.write(struct.pack('<H', block_align))
            f.write(struct.pack('<H', bits))
            f.write(b'data')
            f.write(struct.pack('<I', data_size))
            for s in samples:
                f.write(struct.pack('<h', int(s * 32767)))
