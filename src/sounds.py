"""
Sounds — Gestion du son (lasers, explosions, ambiance).
Utilise les sons intégrés de Panda3D ou des fichiers custom dans assets/sounds/.
"""

import os
import struct
import math
from panda3d.core import Filename


class SoundManager:
    """Gère tous les sons du jeu."""

    def __init__(self, game):
        self.game = game
        self.sounds = {}
        self.enabled = True

        # Génère des sons procéduraux (WAV basiques)
        self._generate_sounds()

        # Charge les sons
        self._load_sounds()

    def _generate_sounds(self):
        """Génère des fichiers WAV procéduraux si pas de fichiers custom."""
        sound_dir = "assets/sounds"
        os.makedirs(sound_dir, exist_ok=True)

        # Laser joueur : bip aigu court
        if not os.path.exists(f"{sound_dir}/laser.wav"):
            self._make_wav(
                f"{sound_dir}/laser.wav",
                freq=880, duration=0.08, volume=0.3,
                freq_end=440, wave_type="square"
            )

        # Laser ennemi : bip grave
        if not os.path.exists(f"{sound_dir}/laser_enemy.wav"):
            self._make_wav(
                f"{sound_dir}/laser_enemy.wav",
                freq=330, duration=0.12, volume=0.25,
                freq_end=220, wave_type="square"
            )

        # Explosion : bruit blanc + fade
        if not os.path.exists(f"{sound_dir}/explosion.wav"):
            self._make_wav(
                f"{sound_dir}/explosion.wav",
                freq=150, duration=0.4, volume=0.4,
                freq_end=50, wave_type="noise"
            )

        # Hit (dégât joueur) : bip descendant
        if not os.path.exists(f"{sound_dir}/hit.wav"):
            self._make_wav(
                f"{sound_dir}/hit.wav",
                freq=600, duration=0.15, volume=0.35,
                freq_end=200, wave_type="saw"
            )

    def _make_wav(self, filepath, freq=440, duration=0.2, volume=0.5,
                  freq_end=None, wave_type="sine"):
        """Génère un fichier WAV simple."""
        import random as rnd

        sample_rate = 22050
        num_samples = int(sample_rate * duration)
        if freq_end is None:
            freq_end = freq

        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            progress = i / num_samples

            # Fréquence qui glisse
            f = freq + (freq_end - freq) * progress

            # Forme d'onde
            if wave_type == "sine":
                val = math.sin(2 * math.pi * f * t)
            elif wave_type == "square":
                val = 1.0 if math.sin(2 * math.pi * f * t) >= 0 else -1.0
            elif wave_type == "saw":
                val = 2.0 * (f * t % 1.0) - 1.0
            elif wave_type == "noise":
                val = rnd.uniform(-1, 1) * math.sin(2 * math.pi * f * t * 0.5)
            else:
                val = math.sin(2 * math.pi * f * t)

            # Envelope (fade out)
            envelope = 1.0 - progress
            val *= volume * envelope

            # Clamp
            val = max(-1.0, min(1.0, val))
            sample = int(val * 32767)
            samples.append(sample)

        # Écrit le WAV
        with open(filepath, 'wb') as f:
            num_channels = 1
            bits_per_sample = 16
            byte_rate = sample_rate * num_channels * bits_per_sample // 8
            block_align = num_channels * bits_per_sample // 8
            data_size = num_samples * block_align

            # Header RIFF
            f.write(b'RIFF')
            f.write(struct.pack('<I', 36 + data_size))
            f.write(b'WAVE')

            # Chunk fmt
            f.write(b'fmt ')
            f.write(struct.pack('<I', 16))
            f.write(struct.pack('<H', 1))  # PCM
            f.write(struct.pack('<H', num_channels))
            f.write(struct.pack('<I', sample_rate))
            f.write(struct.pack('<I', byte_rate))
            f.write(struct.pack('<H', block_align))
            f.write(struct.pack('<H', bits_per_sample))

            # Chunk data
            f.write(b'data')
            f.write(struct.pack('<I', data_size))
            for s in samples:
                f.write(struct.pack('<h', s))

    def _load_sounds(self):
        """Charge les fichiers son."""
        sound_dir = "assets/sounds"

        sound_files = {
            "laser": f"{sound_dir}/laser.wav",
            "laser_enemy": f"{sound_dir}/laser_enemy.wav",
            "explosion": f"{sound_dir}/explosion.wav",
            "hit": f"{sound_dir}/hit.wav",
        }

        for name, path in sound_files.items():
            if os.path.exists(path):
                try:
                    sound = self.game.loader.loadSfx(path)
                    if sound:
                        self.sounds[name] = sound
                except Exception:
                    pass

    def play(self, name):
        """Joue un son."""
        if not self.enabled:
            return
        sound = self.sounds.get(name)
        if sound:
            sound.play()

    def toggle(self):
        """Active/désactive le son."""
        self.enabled = not self.enabled
