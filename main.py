"""
X-Wing Shooter — Point d'entrée.
"""

# Active le support glTF/GLB pour Panda3D (doit être avant l'import de Game)
try:
    import panda3d_gltf
    panda3d_gltf.patch_loader()
    print("[Init] Support glTF activé")
except ImportError:
    print("[Init] panda3d-gltf non installé, modèles .glb non supportés")
    print("       → pip install panda3d-gltf")

from src.game import Game


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
