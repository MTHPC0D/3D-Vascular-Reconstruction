#!/usr/bin/env python3
"""
Application principale PyQt6 pour la reconstruction vasculaire 3D
"""

import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QSplitter, QVBoxLayout, QWidget, QMenuBar, QStatusBar
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QAction, QPixmap

from .views import MainWidget
from .controller import VascularController

class VascularApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Reconstruction Vasculaire 3D")
        self.app.setApplicationVersion("1.0.0")
        self.app.setOrganizationName("Medical Project")
        
        # Définir l'icône de l'application
        logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "res", "logo.ico")
        if os.path.exists(logo_path):
            self.app.setWindowIcon(QIcon(logo_path))
        
        # Créer la fenêtre principale
        self.main_window = VascularMainWindow()
        
        # Appliquer le thème par défaut (clair)
        self.main_window.apply_theme(dark=False)
        
    def run(self):
        """Lance l'application"""
        self.main_window.show()
        return self.app.exec()

class VascularMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reconstruction Vasculaire 3D")
        self.setGeometry(100, 100, 1400, 900)
        self.is_dark_theme = False
        
        # Définir l'icône de la fenêtre
        logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "res", "logo.ico")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        
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

    def toggle_theme(self):
        """Bascule entre thème clair et sombre"""
        self.is_dark_theme = not self.is_dark_theme
        self.apply_theme(self.is_dark_theme)
        
        # Notifier le widget VTK du changement de thème
        self.main_widget.vtk_widget.update_theme(self.is_dark_theme)
    
    def apply_theme(self, dark=False):
        """Applique le thème clair ou sombre"""
        if dark:
            dark_style = """
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QWidget {
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
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTableWidget {
                background-color: #1e1e1e;
                border: 1px solid #555;
                border-radius: 4px;
                color: #ffffff;
                gridline-color: #444;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #444;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
            }
            QHeaderView::section {
                background-color: #333;
                color: #ffffff;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
            QProgressBar {
                border: 1px solid #555;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
            QFrame {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            DropFrame {
                border: 2px dashed #555;
                border-radius: 6px;
                background-color: #1e1e1e;
                color: #ffffff;
            }
            DropFrame:hover {
                border-color: #0078d4;
            }
            QLabel {
                color: #ffffff;
            }
            QMenuBar {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QMenuBar::item:selected {
                background-color: #0078d4;
            }
            QMenu {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
            QStatusBar {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            """
            self.setStyleSheet(dark_style)
        else:
            light_style = """
            QMainWindow {
                background-color: #ffffff;
                color: #000000;
            }
            QWidget {
                background-color: #ffffff;
                color: #000000;
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
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                color: #000000;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
                color: #000000;
                gridline-color: #eeeeee;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eeeeee;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #000000;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
            QProgressBar {
                border: 1px solid #cccccc;
                border-radius: 4px;
                text-align: center;
                color: #000000;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
            QFrame {
                background-color: #ffffff;
                color: #000000;
            }
            DropFrame {
                border: 2px dashed #cccccc;
                border-radius: 6px;
                background-color: #f9f9f9;
                color: #000000;
            }
            DropFrame:hover {
                border-color: #0078d4;
            }
            QLabel {
                color: #000000;
            }
            QMenuBar {
                background-color: #ffffff;
                color: #000000;
            }
            QMenuBar::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QMenu {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #cccccc;
            }
            QMenu::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QStatusBar {
                background-color: #ffffff;
                color: #000000;
            }
            """
            self.setStyleSheet(light_style)
    
    def show_about(self):
        """Affiche la fenêtre À propos"""
        from PyQt6.QtWidgets import QMessageBox, QLabel, QVBoxLayout, QDialog
        
        # Créer une boîte de dialogue personnalisée avec logo
        dialog = QDialog(self)
        dialog.setWindowTitle("À propos")
        dialog.setFixedSize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Logo
        logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "res", "logo.ico")
        if os.path.exists(logo_path):
            logo_label = QLabel()
            pixmap = QPixmap(logo_path)
            # Redimensionner le logo pour la boîte À propos
            scaled_pixmap = pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo_label)
        
        # Texte
        text_label = QLabel(
            "<h3>Reconstruction Vasculaire 3D</h3>"
            "<p><b>Version:</b> 1.0.0</p>"
            "<p><b>Description:</b> Application de reconstruction et d'analyse "
            "de structures vasculaires à partir d'images médicales.</p>"
            "<p><b>Technologies:</b> Python, VTK, PyQt6, Open3D</p>"
        )
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setWordWrap(True)
        layout.addWidget(text_label)
        
        dialog.exec()
