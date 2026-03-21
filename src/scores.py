"""
Leaderboard — Top 10 scores locaux en JSON.
"""

import json
import os
from datetime import datetime


SCORES_FILE = "scores.json"
MAX_ENTRIES = 10


class Leaderboard:
    """Gère le top 10 des scores."""

    def __init__(self):
        self.entries = []
        self.load()

    def load(self):
        """Charge les scores depuis le fichier JSON."""
        if os.path.exists(SCORES_FILE):
            try:
                with open(SCORES_FILE, "r") as f:
                    self.entries = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.entries = []
        else:
            self.entries = []

    def save(self):
        """Sauvegarde les scores dans le fichier JSON."""
        try:
            with open(SCORES_FILE, "w") as f:
                json.dump(self.entries, f, indent=2)
        except IOError as e:
            print(f"[Leaderboard] Erreur sauvegarde: {e}")

    def is_high_score(self, score):
        """Vérifie si le score entre dans le top 10."""
        if len(self.entries) < MAX_ENTRIES:
            return True
        return score > self.entries[-1]["score"]

    def add_score(self, name, score, wave, kills):
        """Ajoute un score et retourne le rang (1-10)."""
        entry = {
            "name": name.upper()[:3],
            "score": score,
            "wave": wave,
            "kills": kills,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }

        self.entries.append(entry)
        self.entries.sort(key=lambda e: e["score"], reverse=True)
        self.entries = self.entries[:MAX_ENTRIES]
        self.save()

        # Retourne le rang
        for i, e in enumerate(self.entries):
            if e is entry:
                return i + 1
        return MAX_ENTRIES
