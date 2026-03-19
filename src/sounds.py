"""
Sounds — Sons du jeu (lasers, explosions, surchauffe).
Sons procéduraux WAV générés au premier lancement.
"""

import os
import struct
import math
import random as rnd
from panda3d.core import Filename


class SoundManager:
    """Gère tous les sons du jeu."""

    def __init__(self, game):
        self.game = game
        self.sounds = {}
        self.enabled = True

        self._generate_sounds()
        self._load_sounds()

    def _generate_sounds(self):
        sound_dir = "assets/sounds"
        os.makedirs(sound_dir, exist_ok=True)

        # Laser joueur : pew court et punchy
        if not os.path.exists(f"{sound_dir}/laser.wav"):
            self._make_laser_sound(f"{sound_dir}/laser.wav")

        # Laser ennemi : plus grave
        if not os.path.exists(f"{sound_dir}/laser_enemy.wav"):
            self._make_wav(
                f"{sound_dir}/laser_enemy.wav",
                freq=280, duration=0.1, volume=0.2,
                freq_end=180, wave_type="sine"
            )

        # Explosion : whoosh + crackle
        if not os.path.exists(f"{sound_dir}/explosion.wav"):
            self._make_explosion_sound(f"{sound_dir}/explosion.wav")

        # Hit joueur : impact sourd
        if not os.path.exists(f"{sound_dir}/hit.wav"):
            self._make_impact_sound(f"{sound_dir}/hit.wav")

        # Surchauffe : souffle étouffé, comme de la vapeur
        if not os.path.exists(f"{sound_dir}/overheat.wav"):
            self._make_overheat_sound(f"{sound_dir}/overheat.wav")

    def _make_laser_sound(self, filepath):
        """Laser : mix sinus rapide descendant + légère saturation."""
        sample_rate = 22050
        duration = 0.08
        num_samples = int(sample_rate * duration)
        samples = []

        for i in range(num_samples):
            t = i / sample_rate
            progress = i / num_samples

            freq = 1200 - 800 * progress
            val = math.sin(2 * math.pi * freq * t) * 0.4
            # Ajoute un harmonique
            val += math.sin(2 * math.pi * freq * 2 * t) * 0.15

            # Envelope rapide
            envelope = (1.0 - progress) ** 2
            val *= envelope * 0.35

            samples.append(max(-1, min(1, val)))

        self._write_wav(filepath, samples, sample_rate)

    def _make_explosion_sound(self, filepath):
        """Explosion : bruit blanc filtré avec decay lent."""
        sample_rate = 22050
        duration = 0.5
        num_samples = int(sample_rate * duration)
        samples = []
        prev = 0.0

        for i in range(num_samples):
            progress = i / num_samples

            # Bruit blanc
            noise = rnd.uniform(-1, 1)
            # Filtre passe-bas simple (lisse le bruit)
            filtered = prev * 0.7 + noise * 0.3
            prev = filtered

            # Basse fréquence pour le punch
            bass = math.sin(2 * math.pi * 60 * (i / sample_rate)) * 0.5

            val = (filtered * 0.5 + bass * 0.5)

            # Envelope : attaque rapide, decay lent
            if progress < 0.05:
                envelope = progress / 0.05
            else:
                envelope = (1.0 - progress) ** 1.5

            val *= envelope * 0.35
            samples.append(max(-1, min(1, val)))

        self._write_wav(filepath, samples, sample_rate)

    def _make_impact_sound(self, filepath):
        """Impact : thump sourd."""
        sample_rate = 22050
        duration = 0.15
        num_samples = int(sample_rate * duration)
        samples = []

        for i in range(num_samples):
            t = i / sample_rate
            progress = i / num_samples

            freq = 200 - 150 * progress
            val = math.sin(2 * math.pi * freq * t)
            # Distortion légère
            val = max(-0.8, min(0.8, val * 1.5))

            envelope = (1.0 - progress) ** 3
            val *= envelope * 0.3

            samples.append(max(-1, min(1, val)))

        self._write_wav(filepath, samples, sample_rate)

    def _make_overheat_sound(self, filepath):
        """Surchauffe : souffle de vapeur étouffé, comme un sifflement grave."""
        sample_rate = 22050
        duration = 1.0
        num_samples = int(sample_rate * duration)
        samples = []
        prev1 = 0.0
        prev2 = 0.0

        for i in range(num_samples):
            t = i / sample_rate
            progress = i / num_samples

            # Bruit blanc très filtré (passe-bas double)
            noise = rnd.uniform(-1, 1)
            filtered1 = prev1 * 0.85 + noise * 0.15
            filtered2 = prev2 * 0.9 + filtered1 * 0.1
            prev1 = filtered1
            prev2 = filtered2

            # Grondement basse fréquence
            rumble = math.sin(2 * math.pi * 40 * t) * 0.3
            rumble += math.sin(2 * math.pi * 65 * t) * 0.2

            val = filtered2 * 0.4 + rumble * 0.6

            # Envelope : monte doucement, plateau, descend
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
        """Génère un WAV simple (fallback)."""
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
            elif wave_type == "square":
                val = 1.0 if math.sin(2 * math.pi * f * t) >= 0 else -1.0
            elif wave_type == "saw":
                val = 2.0 * (f * t % 1.0) - 1.0
            elif wave_type == "noise":
                val = rnd.uniform(-1, 1) * math.sin(2 * math.pi * f * t * 0.5)
            else:
                val = math.sin(2 * math.pi * f * t)

            envelope = 1.0 - progress
            val *= volume * envelope
            samples.append(max(-1, min(1, val)))

        self._write_wav(filepath, samples, sample_rate)

    def _write_wav(self, filepath, samples, sample_rate):
        """Écrit un fichier WAV mono 16-bit."""
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

    def _load_sounds(self):
        sound_dir = "assets/sounds"
        sound_files = {
            "laser": f"{sound_dir}/laser.wav",
            "laser_enemy": f"{sound_dir}/laser_enemy.wav",
            "explosion": f"{sound_dir}/explosion.wav",
            "hit": f"{sound_dir}/hit.wav",
            "overheat": f"{sound_dir}/overheat.wav",
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
        if not self.enabled:
            return
        sound = self.sounds.get(name)
        if sound:
            sound.play()

    def toggle(self):
        self.enabled = not self.enabled
