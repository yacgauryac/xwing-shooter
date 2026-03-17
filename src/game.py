"""
X-Wing Shooter — Classe principale du jeu.
Gère la fenêtre, la scène, et la boucle de jeu.
"""

from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    WindowProperties, Vec3, Vec4, Point3,
    AmbientLight, DirectionalLight,
    AntialiasAttrib
)

from src.player import Player
from src.starfield import Starfield


class Game(ShowBase):
    """Classe principale du jeu X-Wing Shooter."""

    def __init__(self):
        ShowBase.__init__(self)

        # Config fenêtre
        self.setup_window()

        # Éclairage
        self.setup_lights()

        # Anti-aliasing
        self.render.setAntialias(AntialiasAttrib.MAuto)

        # Fond noir (espace)
        self.setBackgroundColor(0, 0, 0, 1)

        # Étoiles
        self.starfield = Starfield(self)

        # Joueur (X-Wing)
        self.player = Player(self)

        # Vitesse de défilement
        self.scroll_speed = 20.0

        # Boucle de jeu
        self.taskMgr.add(self.update, "game_update")

        # Quitter avec Échap
        self.accept("escape", self.quit_game)

    def setup_window(self):
        """Configure la fenêtre de jeu."""
        props = WindowProperties()
        props.setTitle("X-Wing Shooter")
        props.setSize(1280, 720)
        self.win.requestProperties(props)

        # Désactive le contrôle caméra par défaut de Panda3D
        self.disableMouse()

    def setup_lights(self):
        """Met en place l'éclairage de la scène."""
        # Lumière ambiante (pour qu'on voie quelque chose partout)
        ambient = AmbientLight("ambient")
        ambient.setColor(Vec4(0.2, 0.2, 0.3, 1))
        ambient_np = self.render.attachNewNode(ambient)
        self.render.setLight(ambient_np)

        # Lumière directionnelle (simule une étoile lointaine)
        sun = DirectionalLight("sun")
        sun.setColor(Vec4(0.9, 0.9, 0.8, 1))
        sun_np = self.render.attachNewNode(sun)
        sun_np.setHpr(45, -45, 0)
        self.render.setLight(sun_np)

    def update(self, task):
        """Boucle de jeu principale — appelée chaque frame."""
        dt = globalClock.getDt()

        # Update étoiles (défilement)
        self.starfield.update(dt, self.scroll_speed)

        # Update joueur (position souris)
        self.player.update(dt)

        return task.cont

    def quit_game(self):
        """Quitte proprement."""
        self.userExit()
