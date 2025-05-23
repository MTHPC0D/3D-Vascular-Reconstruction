#!/usr/bin/env python3
"""
Point d'entrée principal pour l'application GUI de reconstruction vasculaire 3D
"""

import sys
import os

# Ajouter le répertoire src au path pour les imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.GUI.app import VascularApp

if __name__ == "__main__":
    app = VascularApp()
    app.run()
