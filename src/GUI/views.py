#!/usr/bin/env python3
"""
Composants d'interface utilisateur pour l'application de reconstruction vasculaire
"""

import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                            QGroupBox, QLabel, QPushButton, QTableWidget, 
                            QTableWidgetItem, QTextEdit, QProgressBar, 
                            QFileDialog, QMessageBox, QFrame, QHeaderView)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont, QPixmap, QIcon, QPainter
from PyQt6.QtSvg import QSvgRenderer

from .vtk_widget import VTKWidget

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
        
        # Côté gauche - Zone de visualisation VTK seulement
        self.vtk_widget = VTKWidget()
        
        # Côté droit - Contrôles avec header
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Header avec logo et titre en haut à droite
        self.create_header_with_logo(right_layout)
        
        # Zone drag & drop
        self.create_drag_drop_area(right_layout)
        
        # Bouton d'analyse
        self.create_analysis_button(right_layout)
        
        # Table des métriques
        self.create_metrics_table(right_layout)
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)
        
        # Ajout au splitter
        splitter.addWidget(self.vtk_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([800, 600])  # Proportions initiales
        
        layout.addWidget(splitter)
    
    def create_header_with_logo(self, parent_layout):
        """Crée un header avec le logo de l'application"""
        header_layout = QHBoxLayout()
        
        # Logo
        logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "res", "logo.ico")
        if os.path.exists(logo_path):
            logo_label = QLabel()
            pixmap = QPixmap(logo_path)
            # Redimensionner le logo pour le header
            scaled_pixmap = pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            header_layout.addWidget(logo_label)
        
        # Titre de l'application
        title_label = QLabel("Reconstruction Vasculaire 3D")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                margin-left: 10px;
            }
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()  # Pousse le titre vers la gauche et le bouton vers la droite
        
        # Bouton de thème avec icônes Material Design
        self.theme_button = QPushButton()
        self.theme_button.setFixedSize(40, 40)
        self.theme_button.setStyleSheet("""
            QPushButton {
                border-radius: 20px;
                border: 2px solid #cccccc;
                background-color: transparent;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """)
        
        # Créer l'icône soleil par défaut
        self.update_theme_icon(False)
        self.theme_button.clicked.connect(self.toggle_theme)
        header_layout.addWidget(self.theme_button)
        
        # Widget conteneur pour le header
        header_widget = QWidget()
        header_widget.setLayout(header_layout)
        header_widget.setMaximumHeight(70)
        
        parent_layout.addWidget(header_widget)
    
    def create_svg_icon(self, svg_data, color="#1f1f1f"):
        """Crée une QIcon à partir de données SVG"""
        # Remplacer la couleur dans le SVG
        svg_data = svg_data.replace('fill="#1f1f1f"', f'fill="{color}"')
        
        # Créer un pixmap à partir du SVG
        renderer = QSvgRenderer()
        renderer.load(svg_data.encode('utf-8'))
        
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        return QIcon(pixmap)
    
    def update_theme_icon(self, is_dark):
        """Met à jour l'icône du bouton de thème"""
        if is_dark:
            # Icône lune
            svg_moon = '''<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#1f1f1f"><path d="M480-120q-150 0-255-105T120-480q0-150 105-255t255-105q14 0 27.5 1t26.5 3q-41 29-65.5 75.5T444-660q0 90 63 153t153 63q55 0 101-24.5t75-65.5q2 13 3 26.5t1 27.5q0 150-105 255T480-120Zm0-80q88 0 158-48.5T740-375q-20 5-40 8t-40 3q-123 0-209.5-86.5T364-660q0-20 3-40t8-40q-78 32-126.5 102T200-480q0 116 82 198t198 82Zm-10-270Z"/></svg>'''
            icon = self.create_svg_icon(svg_moon, "#ffffff")
        else:
            # Icône soleil
            svg_sun = '''<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#1f1f1f"><path d="M480-360q50 0 85-35t35-85q0-50-35-85t-85-35q-50 0-85 35t-35 85q0 50 35 85t85 35Zm0 80q-83 0-141.5-58.5T280-480q0-83 58.5-141.5T480-680q83 0 141.5 58.5T680-480q0 83-58.5 141.5T480-280ZM200-440H40v-80h160v80Zm720 0H760v-80h160v80ZM440-760v-160h80v160h-80Zm0 720v-160h80v160h-80ZM256-650l-101-97 57-59 96 100-52 56Zm492 496-97-101 53-55 101 97-57 59Zm-98-550 97-101 59 57-100 96-56-52ZM154-212l101-97 55 53-97 101-59-57Zm326-268Z"/></svg>'''
            icon = self.create_svg_icon(svg_sun, "#1f1f1f")
        
        self.theme_button.setIcon(icon)
        self.theme_button.setIconSize(QSize(24, 24))
    
    def toggle_theme(self):
        """Bascule le thème et met à jour l'icône du bouton"""
        # Récupérer la fenêtre principale pour changer le thème
        main_window = self.window()
        if hasattr(main_window, 'toggle_theme'):
            main_window.toggle_theme()
            # Mettre à jour l'icône du bouton
            if hasattr(main_window, 'is_dark_theme'):
                self.update_theme_icon(main_window.is_dark_theme)
                # Mettre à jour le style du bouton selon le thème
                if main_window.is_dark_theme:
                    self.theme_button.setStyleSheet("""
                        QPushButton {
                            border-radius: 20px;
                            border: 2px solid #555;
                            background-color: transparent;
                            padding: 0px;
                        }
                        QPushButton:hover {
                            background-color: #333;
                            border-color: #0078d4;
                        }
                        QPushButton:pressed {
                            background-color: #444;
                        }
                    """)
                else:
                    self.theme_button.setStyleSheet("""
                        QPushButton {
                            border-radius: 20px;
                            border: 2px solid #cccccc;
                            background-color: transparent;
                            padding: 0px;
                        }
                        QPushButton:hover {
                            background-color: #f0f0f0;
                            border-color: #0078d4;
                        }
                        QPushButton:pressed {
                            background-color: #e0e0e0;
                        }
                    """)
    
    def create_drag_drop_area(self, parent_layout):
        """Crée la zone de drag & drop pour les fichiers"""
        group = QGroupBox("Fichiers d'entrée")
        layout = QHBoxLayout(group)
        
        # Zone NIfTI
        nifti_frame = self.create_file_drop_frame("NIfTI", ".nii/.nii.gz", "nifti")
        layout.addWidget(nifti_frame)
        
        # Zone Ground Truth STL (optionnelle)
        gt_frame = self.create_file_drop_frame("Ground Truth (optionnel)", ".stl", "gt")
        layout.addWidget(gt_frame)
        
        parent_layout.addWidget(group)
    
    def create_file_drop_frame(self, title, extensions, file_type):
        """Crée un frame pour le drag & drop d'un type de fichier"""
        frame = DropFrame(title, extensions, file_type)
        frame.file_dropped.connect(self.on_file_dropped)
        return frame
    
    def create_analysis_button(self, parent_layout):
        """Crée le bouton pour lancer l'analyse"""
        self.analysis_button = QPushButton("Lancer l'Analyse")
        self.analysis_button.setEnabled(False)
        self.analysis_button.setMinimumHeight(40)
        self.analysis_button.clicked.connect(self.start_analysis)
        parent_layout.addWidget(self.analysis_button)
    
    def create_metrics_table(self, parent_layout):
        """Crée la table des métriques avec un design épuré"""
        group = QGroupBox("Résultats d'analyse")
        layout = QVBoxLayout(group)
        
        # Boutons d'export en haut
        buttons_layout = QHBoxLayout()
        
        self.export_csv_button = QPushButton("Exporter CSV")
        self.export_csv_button.setEnabled(False)
        self.export_csv_button.clicked.connect(self.export_metrics_csv)
        buttons_layout.addWidget(self.export_csv_button)
        
        self.screenshot_button = QPushButton("Capture Écran")
        self.screenshot_button.clicked.connect(self.take_screenshot)
        buttons_layout.addWidget(self.screenshot_button)
        
        buttons_layout.addStretch()  # Pousse les boutons vers la gauche
        
        layout.addLayout(buttons_layout)
        
        # Table avec design épuré
        self.metrics_table = QTableWidget(0, 2)  # Seulement 2 colonnes maintenant
        self.metrics_table.setHorizontalHeaderLabels(["Métrique", "Valeur"])
        
        # Configuration du header pour un look moderne
        header = self.metrics_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        
        # Masquer les numéros de lignes
        self.metrics_table.verticalHeader().setVisible(False)
        
        # Style épuré
        self.metrics_table.setAlternatingRowColors(True)
        self.metrics_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.metrics_table.setShowGrid(False)
        
        layout.addWidget(self.metrics_table)
        
        parent_layout.addWidget(group)
    
    def connect_signals(self):
        """Connecte les signaux du contrôleur"""
        self.controller.progress_updated.connect(self.update_progress)
        self.controller.log_message.connect(self.log_to_console)
        self.controller.results_ready.connect(self.update_metrics_table)
        self.controller.mesh_ready.connect(self.update_vtk_visualization)
        
        # Connecter le signal de téléchargement du mesh
        self.vtk_widget.mesh_download_requested.connect(self.download_mesh)
    
    def on_file_dropped(self, file_path, file_type):
        """Appelé quand un fichier est déposé"""
        if file_type == "nifti":
            self.nifti_path = file_path
            self.log_to_console(f"Fichier NIfTI chargé: {os.path.basename(file_path)}", "info")
        elif file_type == "gt":
            self.gt_path = file_path
            self.log_to_console(f"Ground Truth chargé: {os.path.basename(file_path)}", "info")
            # Afficher immédiatement le ground truth dans la vue 3D
            self.vtk_widget.load_ground_truth_only(file_path)
        
        # Vérifier si on peut activer le bouton d'analyse
        self.check_analysis_ready()
    
    def check_analysis_ready(self):
        """Vérifie si on peut activer le bouton d'analyse"""
        # L'analyse peut se lancer avec seulement le fichier NIfTI
        if self.nifti_path:
            self.analysis_button.setEnabled(True)
            self.analysis_button.setText("Lancer l'Analyse")
        else:
            self.analysis_button.setEnabled(False)
            self.analysis_button.setText("Lancer l'Analyse (NIfTI requis)")
    
    def start_analysis(self):
        """Lance l'analyse manuellement"""
        if not self.nifti_path:
            QMessageBox.warning(self, "Fichier manquant", "Un fichier NIfTI est requis pour lancer l'analyse.")
            return
        
        self.log_to_console("Lancement de l'analyse...", "info")
        self.progress_bar.setVisible(True)
        self.analysis_button.setEnabled(False)
        self.analysis_button.setText("Analyse en cours...")
        
        # Lancer le traitement
        self.controller.process_files(self.nifti_path, self.gt_path)
    
    def update_progress(self, value):
        """Met à jour la barre de progression"""
        self.progress_bar.setValue(value)
        if value == 100:
            self.progress_bar.setVisible(False)
            self.analysis_button.setEnabled(True)
            self.analysis_button.setText("Analyse terminée")
    
    def log_to_console(self, message, level):
        """Affiche les logs dans la console VS Code au lieu de l'interface"""
        # Afficher dans la console Python/VS Code
        if level == "error":
            print(f"❌ [ERREUR] {message}")
        elif level == "success":
            print(f"✅ [SUCCÈS] {message}")
        elif level == "warning":
            print(f"⚠️ [AVERTISSEMENT] {message}")
        else:
            print(f"ℹ️ [INFO] {message}")
    
    def update_vtk_visualization(self, recon_path, gt_path, centerlines_path):
        """Met à jour la visualisation VTK"""
        self.log_to_console("Mise à jour de la visualisation 3D...", "info")
        
        # Calculer le Dice score depuis les résultats de comparaison si disponible
        dice_score = self.get_dice_score_from_results()
        
        # Mettre à jour les acteurs VTK
        self.vtk_widget.update_actors(recon_path, gt_path, centerlines_path, dice_score)
        
        self.log_to_console("Visualisation 3D mise à jour", "success")
    
    def get_dice_score_from_results(self):
        """Récupère le Dice score depuis les résultats de comparaison"""
        # Pour l'instant, retourner None. Plus tard, on pourra lire depuis un fichier de résultats
        return None
    
    def update_metrics_table(self, json_path):
        """Met à jour la table des métriques depuis le JSON"""
        try:
            indicators = self.controller.load_indicators(json_path)
            self.populate_metrics_table(indicators)
            self.export_csv_button.setEnabled(True)
        except Exception as e:
            self.log_to_console(f"Erreur lors de la mise à jour des métriques: {str(e)}", "error")
    
    def populate_metrics_table(self, indicators):
        """Remplit la table avec les indicateurs dans un design épuré"""
        metrics = []
        
        # Tortuosité globale
        if indicators.get('global_tortuosity'):
            tort = indicators['global_tortuosity']
            metrics.append(("Tortuosité globale", f"{tort['tortuosity']:.3f}"))
        
        # Angles de décollage
        if indicators.get('takeoff_angles'):
            angles = [a['angle_degrees'] for a in indicators['takeoff_angles']]
            if angles:
                import numpy as np
                metrics.append(("Angle décollage moyen", f"{np.mean(angles):.1f}°"))
        
        # Courbure maximale
        if indicators.get('maximum_curvature'):
            curv = indicators['maximum_curvature']
            metrics.append(("Rayon minimal", f"{curv['min_radius_mm']:.1f} mm"))
        
        # Type d'arche
        if indicators.get('aortic_arch_type'):
            arch = indicators['aortic_arch_type']
            metrics.append(("Type d'arche", arch['type']))
        
        # Nombre de branches
        if indicators.get('takeoff_angles'):
            metrics.append(("Nombre de branches", str(len(indicators['takeoff_angles']))))
        
        # Remplir la table
        self.metrics_table.setRowCount(len(metrics))
        for i, (name, value) in enumerate(metrics):
            # Métrique avec style gras
            name_item = QTableWidgetItem(name)
            name_item.setFont(QFont("", 0, QFont.Weight.Bold))
            self.metrics_table.setItem(i, 0, name_item)
            
            # Valeur
            value_item = QTableWidgetItem(value)
            self.metrics_table.setItem(i, 1, value_item)
        
        # Ajuster la hauteur des lignes
        self.metrics_table.resizeRowsToContents()
    
    def export_metrics_csv(self):
        """Exporte les métriques en CSV"""
        if self.metrics_table.rowCount() == 0:
            QMessageBox.warning(self, "Aucune donnée", "Aucune métrique à exporter.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exporter les métriques", 
            "metriques_vasculaires.csv", 
            "Fichiers CSV (*.csv)")
        
        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    # En-têtes
                    writer.writerow(["Métrique", "Valeur"])
                    
                    # Données
                    for row in range(self.metrics_table.rowCount()):
                        row_data = []
                        for col in range(self.metrics_table.columnCount()):
                            item = self.metrics_table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
                
                self.log_to_console(f"Métriques exportées vers: {file_path}", "success")
                QMessageBox.information(self, "Export réussi", f"Métriques exportées vers:\n{file_path}")
                
            except Exception as e:
                self.log_to_console(f"Erreur lors de l'export CSV: {str(e)}", "error")
                QMessageBox.critical(self, "Erreur d'export", f"Impossible d'exporter le CSV:\n{str(e)}")
    
    def download_mesh(self):
        """Télécharge le mesh reconstruit"""
        if not os.path.exists(self.controller.recon_mesh_path):
            QMessageBox.warning(self, "Fichier introuvable", "Aucun mesh reconstruit disponible.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder le mesh", 
            "mesh_reconstruit.stl", 
            "Fichiers STL (*.stl);;Fichiers PLY (*.ply)")
        
        if file_path:
            try:
                import shutil
                shutil.copy2(self.controller.recon_mesh_path, file_path)
                self.log_to_console(f"Mesh sauvegardé vers: {file_path}", "success")
                QMessageBox.information(self, "Sauvegarde réussie", f"Mesh sauvegardé vers:\n{file_path}")
            except Exception as e:
                self.log_to_console(f"Erreur lors de la sauvegarde: {str(e)}", "error")
                QMessageBox.critical(self, "Erreur de sauvegarde", f"Impossible de sauvegarder le mesh:\n{str(e)}")
    
    def take_screenshot(self):
        """Prend une capture d'écran de la vue 3D"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder la capture", 
            "vue_3d.png", 
            "Images PNG (*.png)")
        
        if file_path:
            try:
                self.vtk_widget.export_screenshot(file_path)
                self.log_to_console(f"Capture sauvegardée vers: {file_path}", "success")
                QMessageBox.information(self, "Capture réussie", f"Capture sauvegardée vers:\n{file_path}")
            except Exception as e:
                self.log_to_console(f"Erreur lors de la capture: {str(e)}", "error")
                QMessageBox.critical(self, "Erreur de capture", f"Impossible de sauvegarder la capture:\n{str(e)}")
    
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
        ext_label.setStyleSheet("font-size: 12px; color: #666;")
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
        self.setMinimumHeight(120)
    
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
