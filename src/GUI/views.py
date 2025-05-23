#!/usr/bin/env python3
"""
Composants d'interface utilisateur pour l'application de reconstruction vasculaire
"""

import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                            QGroupBox, QLabel, QPushButton, QTableWidget, 
                            QTableWidgetItem, QTextEdit, QProgressBar, 
                            QFileDialog, QMessageBox, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont

class MainWidget(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.nifti_path = None
        self.gt_path = None
        
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        """Configure l'interface utilisateur principale"""
        layout = QHBoxLayout(self)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Côté gauche - Zone de visualisation (pour plus tard)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Placeholder pour VTK widget
        vtk_placeholder = QLabel("Zone de visualisation 3D\n(VTK Widget)")
        vtk_placeholder.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 2px dashed #555;
                border-radius: 6px;
                color: #888;
                font-size: 16px;
                text-align: center;
            }
        """)
        vtk_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vtk_placeholder.setMinimumSize(600, 400)
        left_layout.addWidget(vtk_placeholder)
        
        # Bouton télécharger mesh
        self.download_button = QPushButton("Télécharger Mesh")
        self.download_button.setEnabled(False)
        left_layout.addWidget(self.download_button)
        
        # Côté droit - Contrôles
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Zone drag & drop
        self.create_drag_drop_area(right_layout)
        
        # Table des métriques
        self.create_metrics_table(right_layout)
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)
        
        # Console de log
        self.create_log_console(right_layout)
        
        # Ajout au splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([800, 600])  # Proportions initiales
        
        layout.addWidget(splitter)
    
    def create_drag_drop_area(self, parent_layout):
        """Crée la zone de drag & drop pour les fichiers"""
        group = QGroupBox("Fichiers d'entrée")
        layout = QHBoxLayout(group)
        
        # Zone NIfTI
        nifti_frame = self.create_file_drop_frame("NIfTI", ".nii/.nii.gz", "nifti")
        layout.addWidget(nifti_frame)
        
        # Zone Ground Truth STL
        gt_frame = self.create_file_drop_frame("Ground Truth", ".stl", "gt")
        layout.addWidget(gt_frame)
        
        parent_layout.addWidget(group)
    
    def create_file_drop_frame(self, title, extensions, file_type):
        """Crée un frame pour le drag & drop d'un type de fichier"""
        frame = DropFrame(title, extensions, file_type)
        frame.file_dropped.connect(self.on_file_dropped)
        return frame
    
    def create_metrics_table(self, parent_layout):
        """Crée la table des métriques"""
        group = QGroupBox("Métriques de comparaison")
        layout = QVBoxLayout(group)
        
        # Bouton export CSV
        export_button = QPushButton("Exporter CSV")
        export_button.setEnabled(False)
        layout.addWidget(export_button)
        
        # Table
        self.metrics_table = QTableWidget(0, 3)
        self.metrics_table.setHorizontalHeaderLabels(["Métrique", "Valeur", "Info"])
        self.metrics_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.metrics_table)
        
        parent_layout.addWidget(group)
    
    def create_log_console(self, parent_layout):
        """Crée la console de log"""
        group = QGroupBox("Console")
        layout = QVBoxLayout(group)
        
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(150)
        self.log_console.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_console)
        
        parent_layout.addWidget(group)
    
    def connect_signals(self):
        """Connecte les signaux du contrôleur"""
        self.controller.progress_updated.connect(self.update_progress)
        self.controller.log_message.connect(self.append_log)
        self.controller.results_ready.connect(self.update_metrics_table)
    
    def on_file_dropped(self, file_path, file_type):
        """Appelé quand un fichier est déposé"""
        if file_type == "nifti":
            self.nifti_path = file_path
            self.append_log(f"Fichier NIfTI chargé: {os.path.basename(file_path)}", "info")
        elif file_type == "gt":
            self.gt_path = file_path
            self.append_log(f"Ground Truth chargé: {os.path.basename(file_path)}", "info")
        
        # Vérifier si on peut lancer le traitement
        self.check_ready_to_process()
    
    def check_ready_to_process(self):
        """Vérifie si on peut lancer le traitement"""
        if self.nifti_path and self.gt_path:
            self.append_log("Fichiers prêts. Lancement du traitement...", "info")
            self.progress_bar.setVisible(True)
            self.controller.process_files(self.nifti_path, self.gt_path)
    
    def update_progress(self, value):
        """Met à jour la barre de progression"""
        self.progress_bar.setValue(value)
        if value == 100:
            self.progress_bar.setVisible(False)
    
    def append_log(self, message, level):
        """Ajoute un message au log"""
        colors = {
            "info": "#ffffff",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "error": "#F44336"
        }
        color = colors.get(level, "#ffffff")
        
        html_message = f'<span style="color: {color};">[{level.upper()}] {message}</span>'
        self.log_console.append(html_message)
    
    def update_metrics_table(self, json_path):
        """Met à jour la table des métriques depuis le JSON"""
        try:
            indicators = self.controller.load_indicators(json_path)
            self.populate_metrics_table(indicators)
        except Exception as e:
            self.append_log(f"Erreur lors de la mise à jour des métriques: {str(e)}", "error")
    
    def populate_metrics_table(self, indicators):
        """Remplit la table avec les indicateurs"""
        metrics = []
        
        # Tortuosité globale
        if indicators.get('global_tortuosity'):
            tort = indicators['global_tortuosity']
            metrics.append(("Tortuosité globale", f"{tort['tortuosity']:.3f}", "Rapport longueur/distance euclidienne"))
        
        # Angles de décollage
        if indicators.get('takeoff_angles'):
            angles = [a['angle_degrees'] for a in indicators['takeoff_angles']]
            if angles:
                import numpy as np
                metrics.append(("Angle décollage moyen", f"{np.mean(angles):.1f}°", "Angle moyen des branches principales"))
        
        # Courbure maximale
        if indicators.get('maximum_curvature'):
            curv = indicators['maximum_curvature']
            metrics.append(("Rayon minimal", f"{curv['min_radius_mm']:.1f} mm", "Plus petit rayon de courbure"))
        
        # Type d'arche
        if indicators.get('aortic_arch_type'):
            arch = indicators['aortic_arch_type']
            metrics.append(("Type d'arche", arch['type'], arch['description']))
        
        # Remplir la table
        self.metrics_table.setRowCount(len(metrics))
        for i, (name, value, info) in enumerate(metrics):
            self.metrics_table.setItem(i, 0, QTableWidgetItem(name))
            self.metrics_table.setItem(i, 1, QTableWidgetItem(value))
            self.metrics_table.setItem(i, 2, QTableWidgetItem(info))
    
    def open_nifti_dialog(self):
        """Ouvre un dialogue pour sélectionner un fichier NIfTI"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un fichier NIfTI", 
            "", "Fichiers NIfTI (*.nii *.nii.gz)")
        
        if file_path:
            self.on_file_dropped(file_path, "nifti")

class DropFrame(QFrame):
    file_dropped = pyqtSignal(str, str)  # file_path, file_type
    
    def __init__(self, title, extensions, file_type):
        super().__init__()
        self.title = title
        self.extensions = extensions
        self.file_type = file_type
        self.setup_ui()
        
        # Activer le drag & drop
        self.setAcceptDrops(True)
    
    def setup_ui(self):
        """Configure l'interface du frame"""
        layout = QVBoxLayout(self)
        
        # Titre
        title_label = QLabel(self.title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)
        
        # Extensions supportées
        ext_label = QLabel(self.extensions)
        ext_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ext_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(ext_label)
        
        # Zone de drop
        drop_label = QLabel("Glisser-déposer\nou")
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(drop_label)
        
        # Bouton parcourir
        browse_button = QPushButton("Parcourir...")
        browse_button.clicked.connect(self.browse_file)
        layout.addWidget(browse_button)
        
        # Style du frame
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            DropFrame {
                border: 2px dashed #555;
                border-radius: 6px;
                background-color: #1e1e1e;
                min-height: 120px;
            }
            DropFrame:hover {
                border-color: #0078d4;
            }
        """)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Gère l'entrée de fichiers par drag & drop"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """Gère le dépôt de fichiers"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if self.validate_file(file_path):
                self.file_dropped.emit(file_path, self.file_type)
            else:
                QMessageBox.warning(self, "Fichier invalide", 
                                  f"Le fichier doit avoir une extension {self.extensions}")
    
    def browse_file(self):
        """Ouvre un dialogue pour sélectionner un fichier"""
        if self.file_type == "nifti":
            filter_str = "Fichiers NIfTI (*.nii *.nii.gz)"
        elif self.file_type == "gt":
            filter_str = "Fichiers STL (*.stl)"
        else:
            filter_str = "Tous les fichiers (*.*)"
        
        file_path, _ = QFileDialog.getOpenFileName(self, f"Sélectionner {self.title}", "", filter_str)
        
        if file_path:
            self.file_dropped.emit(file_path, self.file_type)
    
    def validate_file(self, file_path):
        """Valide l'extension du fichier"""
        ext = os.path.splitext(file_path)[1].lower()
        if self.file_type == "nifti":
            return ext in ['.nii'] or file_path.lower().endswith('.nii.gz')
        elif self.file_type == "gt":
            return ext == '.stl'
        return True
