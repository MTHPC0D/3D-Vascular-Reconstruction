#!/usr/bin/env python3
"""
Point d'entrée principal pour l'application GUI de reconstruction vasculaire 3D
"""

import sys
import os

# Ajouter le répertoire src au path pour les imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configurer l'icône de l'application dans la barre des tâches Windows
if sys.platform == "win32":
    import ctypes
    myappid = 'medicalproject.vascularreconstruction.gui.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

from src.GUI.app import VascularApp

if __name__ == "__main__":
    app = VascularApp()
    app.run()
