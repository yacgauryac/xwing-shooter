"""
X-Wing Shooter — Point d'entrée.
Lance le jeu.
"""

from src.game import Game


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
