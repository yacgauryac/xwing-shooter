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
        if not self._find_file("laser_fire") and not self._find_file("laser"):
            self._make_laser_sound(f"{SOUND_DIR}/laser.wav")
        if not self._find_file("laser_enemy"):
            self._make_wav(f"{SOUND_DIR}/laser_enemy.wav",
                          freq=280, duration=0.1, volume=0.2, freq_end=180)
        if not self._find_file("explosion_small") and not self._find_file("explosion"):
            self._make_explosion_sound(f"{SOUND_DIR}/explosion.wav")
        if not self._find_file("hit_player") and not self._find_file("hit"):
            self._make_impact_sound(f"{SOUND_DIR}/hit.wav")
        if not self._find_file("overheat"):
            self._make_overheat_sound(f"{SOUND_DIR}/overheat.wav")

    def _make_laser_sound(self, filepath):
        sample_rate = 22050
        duration = 0.08
        num_samples = int(sample_rate * duration)
        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            progress = i / num_samples
            freq = 1200 - 800 * progress
            val = math.sin(2 * math.pi * freq * t) * 0.4
            val += math.sin(2 * math.pi * freq * 2 * t) * 0.15
            envelope = (1.0 - progress) ** 2
            val *= envelope * 0.35
            samples.append(max(-1, min(1, val)))
        self._write_wav(filepath, samples, sample_rate)

    def _make_explosion_sound(self, filepath):
        sample_rate = 22050
        duration = 0.5
        num_samples = int(sample_rate * duration)
        samples = []
        prev = 0.0
        for i in range(num_samples):
            progress = i / num_samples
            noise = rnd.uniform(-1, 1)
            filtered = prev * 0.7 + noise * 0.3
            prev = filtered
            bass = math.sin(2 * math.pi * 60 * (i / sample_rate)) * 0.5
            val = (filtered * 0.5 + bass * 0.5)
            if progress < 0.05:
                envelope = progress / 0.05
            else:
                envelope = (1.0 - progress) ** 1.5
            val *= envelope * 0.35
            samples.append(max(-1, min(1, val)))
        self._write_wav(filepath, samples, sample_rate)

    def _make_impact_sound(self, filepath):
        sample_rate = 22050
        duration = 0.15
        num_samples = int(sample_rate * duration)
        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            progress = i / num_samples
            freq = 200 - 150 * progress
            val = math.sin(2 * math.pi * freq * t)
            val = max(-0.8, min(0.8, val * 1.5))
            envelope = (1.0 - progress) ** 3
            val *= envelope * 0.3
            samples.append(max(-1, min(1, val)))
        self._write_wav(filepath, samples, sample_rate)

    def _make_overheat_sound(self, filepath):
        sample_rate = 22050
        duration = 1.0
        num_samples = int(sample_rate * duration)
        samples = []
        prev1 = prev2 = 0.0
        for i in range(num_samples):
            t = i / sample_rate
            progress = i / num_samples
            noise = rnd.uniform(-1, 1)
            filtered1 = prev1 * 0.85 + noise * 0.15
            filtered2 = prev2 * 0.9 + filtered1 * 0.1
            prev1, prev2 = filtered1, filtered2
            rumble = math.sin(2 * math.pi * 40 * t) * 0.3
            rumble += math.sin(2 * math.pi * 65 * t) * 0.2
            val = filtered2 * 0.4 + rumble * 0.6
            if progress < 0.15:
                envelope = progress / 0.15
            elif progress > 0.7:
                envelope = (1.0 - progress) / 0.3
            else:
                envelope = 1.0
            val *= envelope * 0.25
            samples.append(max(-1, min(1, val)))
        self._write_wav(filepath, samples, sample_rate)

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
