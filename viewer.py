"""
viewer.py — Lanceur du building viewer standalone.
Usage :
    python viewer.py              # catalogue procédural
    python viewer.py model.glb    # charge un fichier .glb
"""
import sys
from src.building_viewer import BuildingViewer

glb_path = sys.argv[1] if len(sys.argv) > 1 else None
app = BuildingViewer(glb_path=glb_path)
app.run()
