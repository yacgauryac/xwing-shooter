"""
Starfield — Étoiles + traînées de vitesse.
Les étoiles s'étirent en lignes proportionnellement à la vitesse.
"""

from panda3d.core import (
    Vec3, Vec4, Point3,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomLines, GeomPoints, GeomNode,
    NodePath
)
import random


class Starfield:
    """Champ d'étoiles avec effet de vitesse (streaks)."""

    NUM_STARS = 600
    FIELD_DEPTH = 250.0
    FIELD_WIDTH = 45.0
    FIELD_HEIGHT = 35.0
    RECYCLE_Z = -10.0

    # Longueur des traînées : proportionnelle à la vitesse
    STREAK_FACTOR = 0.06  # Plus c'est grand, plus les traînées sont longues

    def __init__(self, game):
        self.game = game
        self.stars = []
        self.brightnesses = []

        self.star_root = NodePath("starfield")
        self.star_root.reparentTo(game.render)
        self.star_root.setLightOff()

        # Stocke les couleurs pour chaque étoile
        for i in range(self.NUM_STARS):
            x = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
            y = random.uniform(0, self.FIELD_DEPTH)
            z = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)
            self.stars.append([x, y, z])

            brightness = random.uniform(0.3, 1.0)
            r = brightness * random.uniform(0.85, 1.0)
            g = brightness * random.uniform(0.85, 1.0)
            b = brightness
            self.brightnesses.append((r, g, b))

        # Géométrie initiale (sera reconstruite chaque frame pour les streaks)
        self.geom_node_np = None
        self._build_geom(0)

    def _build_geom(self, scroll_speed):
        """Reconstruit la géométrie des étoiles (points ou lignes selon la vitesse)."""
        if self.geom_node_np:
            self.geom_node_np.removeNode()

        streak_len = scroll_speed * self.STREAK_FACTOR
        use_lines = streak_len > 0.3  # Au-dessus de ce seuil, on fait des lignes

        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("stars", fmt, Geom.UHDynamic)

        if use_lines:
            # Chaque étoile = 2 vertices (ligne)
            vdata.setNumRows(self.NUM_STARS * 2)
            vertex = GeomVertexWriter(vdata, "vertex")
            color = GeomVertexWriter(vdata, "color")

            for i, star in enumerate(self.stars):
                r, g, b = self.brightnesses[i]
                x, y, z = star

                # Point avant (brillant)
                vertex.addData3(x, y, z)
                color.addData4(r, g, b, 1.0)

                # Point arrière (fading) — étiré vers l'arrière
                vertex.addData3(x, y - streak_len, z)
                color.addData4(r * 0.3, g * 0.3, b * 0.3, 0.3)

            lines = GeomLines(Geom.UHDynamic)
            for i in range(self.NUM_STARS):
                lines.addVertices(i * 2, i * 2 + 1)

            geom = Geom(vdata)
            geom.addPrimitive(lines)
        else:
            # Points classiques
            vdata.setNumRows(self.NUM_STARS)
            vertex = GeomVertexWriter(vdata, "vertex")
            color = GeomVertexWriter(vdata, "color")

            for i, star in enumerate(self.stars):
                r, g, b = self.brightnesses[i]
                vertex.addData3(star[0], star[1], star[2])
                color.addData4(r, g, b, 1.0)

            points = GeomPoints(Geom.UHDynamic)
            points.addConsecutiveVertices(0, self.NUM_STARS)

            geom = Geom(vdata)
            geom.addPrimitive(points)

        self.vdata = vdata
        self.use_lines = use_lines

        node = GeomNode("stars_geom")
        node.addGeom(geom)

        self.geom_node_np = NodePath(node)
        self.geom_node_np.reparentTo(self.star_root)
        self.geom_node_np.setRenderModeThickness(2)

    def update(self, dt, scroll_speed):
        """Fait défiler les étoiles et met à jour les streaks."""
        streak_len = scroll_speed * self.STREAK_FACTOR
        use_lines = streak_len > 0.3

        # Reconstruire si on change de mode (points ↔ lignes)
        if use_lines != self.use_lines:
            # Déplace d'abord les étoiles
            for star in self.stars:
                star[1] -= scroll_speed * dt
                if star[1] < self.RECYCLE_Z:
                    star[0] = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
                    star[1] = self.FIELD_DEPTH
                    star[2] = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)
            self._build_geom(scroll_speed)
            return

        vertex = GeomVertexWriter(self.vdata, "vertex")

        if use_lines:
            # Met à jour les lignes (2 vertices par étoile)
            for i, star in enumerate(self.stars):
                star[1] -= scroll_speed * dt
                if star[1] < self.RECYCLE_Z:
                    star[0] = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
                    star[1] = self.FIELD_DEPTH
                    star[2] = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)

                vertex.setData3(star[0], star[1], star[2])
                vertex.setData3(star[0], star[1] - streak_len, star[2])
        else:
            # Met à jour les points
            for i, star in enumerate(self.stars):
                star[1] -= scroll_speed * dt
                if star[1] < self.RECYCLE_Z:
                    star[0] = random.uniform(-self.FIELD_WIDTH, self.FIELD_WIDTH)
                    star[1] = self.FIELD_DEPTH
                    star[2] = random.uniform(-self.FIELD_HEIGHT, self.FIELD_HEIGHT)

                vertex.setData3(star[0], star[1], star[2])
