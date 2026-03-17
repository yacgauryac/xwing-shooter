"""
Starfield — Champ d'étoiles qui défile pour donner l'impression de vitesse.
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomPoints, GeomNode,
    NodePath
)
import random


class Starfield:
    """Génère et anime un champ d'étoiles procédural."""

    NUM_STARS = 500
    FIELD_DEPTH = 200.0  # profondeur du champ
    FIELD_WIDTH = 40.0   # largeur
    FIELD_HEIGHT = 30.0  # hauteur
    RECYCLE_Z = -10.0    # quand une étoile passe derrière la caméra, on la recycle

    def __init__(self, game):
        self.game = game
        self.stars = []

        # Crée les étoiles
        self.star_root = NodePath("starfield")
        self.star_root.reparentTo(game.render)

        self.create_stars()

    def create_stars(self):
        """Crée un nuage de points pour les étoiles."""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("stars", fmt, Geom.UHDynamic)
        vdata.setNumRows(self.NUM_STARS)

        vertex = GeomVertexWriter(vdata, "vertex")
        color = GeomVertexWriter(vdata, "color")

        for i in range(self.NUM_STARS):
            x = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
            y = random.uniform(0, self.FIELD_DEPTH)
            z = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)

            self.stars.append([x, y, z])

            vertex.addData3(x, y, z)

            # Étoiles de luminosité variable
            brightness = random.uniform(0.4, 1.0)
            # Légère teinte aléatoire (blanc/bleu/jaune)
            r_tint = brightness * random.uniform(0.85, 1.0)
            g_tint = brightness * random.uniform(0.85, 1.0)
            b_tint = brightness
            color.addData4(r_tint, g_tint, b_tint, 1.0)

        points = GeomPoints(Geom.UHDynamic)
        points.addConsecutiveVertices(0, self.NUM_STARS)

        geom = Geom(vdata)
        geom.addPrimitive(points)

        self.vdata = vdata
        self.geom = geom

        node = GeomNode("stars_geom")
        node.addGeom(geom)

        star_np = NodePath(node)
        star_np.reparentTo(self.star_root)

        # Points plus gros pour qu'on les voie
        star_np.setRenderModeThickness(2)

        # Pas d'éclairage sur les étoiles (elles brillent toutes seules)
        star_np.setLightOff()

    def update(self, dt, scroll_speed):
        """Fait défiler les étoiles vers le joueur."""
        vertex = GeomVertexWriter(self.vdata, "vertex")

        for i, star in enumerate(self.stars):
            # L'étoile avance vers le joueur (Y diminue)
            star[1] -= scroll_speed * dt

            # Si elle passe derrière la caméra, on la recycle devant
            if star[1] < self.RECYCLE_Z:
                star[0] = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
                star[1] = self.FIELD_DEPTH
                star[2] = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)

            vertex.setData3(star[0], star[1], star[2])
