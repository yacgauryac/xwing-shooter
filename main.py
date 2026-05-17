"""
X-Wing Shooter — Point d'entrée.
"""

import argparse

# Active le support glTF/GLB pour Panda3D (doit être avant l'import de Game)
try:
    import panda3d_gltf
    panda3d_gltf.patch_loader()
    print("[Init] Support glTF activé")
except ImportError:
    print("[Init] panda3d-gltf non installé, modèles .glb non supportés")
    print("       → pip install panda3d-gltf")

from src.game import Game


def parse_args():
    parser = argparse.ArgumentParser(description="X-Wing Shooter")
    parser.add_argument("--host", action="store_true",
                        help="Lancer en mode host (serveur multijoueur LAN)")
    parser.add_argument("--client", action="store_true",
                        help="Lancer en mode client (rejoindre un host)")
    parser.add_argument("--ip", type=str, default="127.0.0.1",
                        help="IP du host à rejoindre (mode client, défaut: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=7777,
                        help="Port UDP (défaut: 7777)")
    return parser.parse_args()


def main():
    args = parse_args()

    # Détermine le mode réseau
    net_mode = None
    if args.host:
        net_mode = "host"
    elif args.client:
        net_mode = "client"

    game = Game(net_mode=net_mode, net_ip=args.ip, net_port=args.port)
    game.run()


if __name__ == "__main__":
    main()
