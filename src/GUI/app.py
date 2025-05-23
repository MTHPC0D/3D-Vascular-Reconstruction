#!/usr/bin/env python3
"""
Application principale PyQt6 pour la reconstruction vasculaire 3D
"""

import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QSplitter, QVBoxLayout, QWidget, QMenuBar, QStatusBar
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QAction

from .views import MainWidget
from .controller import VascularController

class VascularApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Reconstruction Vasculaire 3D")
        self.app.setApplicationVersion("1.0.0")
        self.app.setOrganizationName("Medical Project")
        
        # Charger le style
        self.load_stylesheet()
        
        # Créer la fenêtre principale
        self.main_window = VascularMainWindow()
        
    def load_stylesheet(self):
        """Charge la feuille de style personnalisée"""
        # Style par défaut
        default_style = """
        QMainWindow {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QPushButton {
            background-color: #0078d4;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            color: white;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #106ebe;
        }
        QPushButton:pressed {
            background-color: #005a9e;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #555;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QTextEdit {
            background-color: #1e1e1e;
            border: 1px solid #555;
            border-radius: 4px;
            color: #ffffff;
        }
        QTableWidget {
            background-color: #1e1e1e;
            border: 1px solid #555;
            border-radius: 4px;
            color: #ffffff;
        }
        QProgressBar {
            border: 1px solid #555;
            border-radius: 4px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 3px;
        }
        """
        self.app.setStyleSheet(default_style)
    
    def run(self):
        """Lance l'application"""
        self.main_window.show()
        return self.app.exec()

class VascularMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reconstruction Vasculaire 3D")
        self.setGeometry(100, 100, 1400, 900)
        
        # Contrôleur
        self.controller = VascularController()
        
        # Widget central
        self.main_widget = MainWidget(self.controller)
        self.setCentralWidget(self.main_widget)
        
        # Menu et barre de statut
        self.create_menu_bar()
        self.create_status_bar()
        
        # Connecter les signaux
        self.connect_signals()
    
    def create_menu_bar(self):
        """Crée la barre de menu"""
        menubar = self.menuBar()
        
        # Menu Fichier
        file_menu = menubar.addMenu('&Fichier')
        
        open_action = QAction('&Ouvrir NIfTI...', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.main_widget.open_nifti_dialog)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction('&Quitter', self)
        quit_action.setShortcut('Ctrl+Q')
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # Menu Aide
        help_menu = menubar.addMenu('&Aide')
        
        about_action = QAction('&À propos...', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_status_bar(self):
        """Crée la barre de statut"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Prêt")
    
    def connect_signals(self):
        """Connecte les signaux entre composants"""
        # Connecter les logs du contrôleur à la barre de statut
        self.controller.status_message.connect(self.status_bar.showMessage)
    
    def show_about(self):
        """Affiche la fenêtre À propos"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(self, "À propos", 
                         "Reconstruction Vasculaire 3D v1.0\n\n"
                         "Application de reconstruction et d'analyse "
                         "de structures vasculaires à partir d'images médicales.")
