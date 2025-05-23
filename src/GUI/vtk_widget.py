#!/usr/bin/env python3
"""
Widget VTK pour la visualisation 3D des meshes et lignes centrales
"""

import vtk
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout
from PyQt6.QtCore import pyqtSignal
try:
    from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
except ImportError:
    from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

class VTKWidget(QWidget):
    mesh_download_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.is_dark_theme = False
        self.setup_ui()
        self.setup_vtk()
        
        # Acteurs pour les différents éléments
        self.recon_actor = None
        self.gt_actor = None
        self.centerlines_actor = None
        
    def setup_ui(self):
        """Configure l'interface utilisateur"""
        layout = QVBoxLayout(self)
        
        # Widget VTK
        self.vtk_widget = QVTKRenderWindowInteractor(self)
        layout.addWidget(self.vtk_widget)
        
        # Contrôles
        controls_layout = QHBoxLayout()
        
        # Bouton télécharger mesh
        self.download_button = QPushButton("Télécharger")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.mesh_download_requested.emit)
        controls_layout.addWidget(self.download_button)
        
        # Boutons de contrôle de visibilité
        self.toggle_recon_button = QPushButton("Reconstruit")
        self.toggle_recon_button.setCheckable(True)
        self.toggle_recon_button.setChecked(True)
        self.toggle_recon_button.clicked.connect(self.toggle_recon_visibility)
        controls_layout.addWidget(self.toggle_recon_button)
        
        self.toggle_gt_button = QPushButton("Reference")
        self.toggle_gt_button.setCheckable(True)
        self.toggle_gt_button.setChecked(True)
        self.toggle_gt_button.clicked.connect(self.toggle_gt_visibility)
        controls_layout.addWidget(self.toggle_gt_button)
        
        self.toggle_centerlines_button = QPushButton("Centerlines")
        self.toggle_centerlines_button.setCheckable(True)
        self.toggle_centerlines_button.setChecked(True)
        self.toggle_centerlines_button.clicked.connect(self.toggle_centerlines_visibility)
        controls_layout.addWidget(self.toggle_centerlines_button)
        
        layout.addLayout(controls_layout)
        
    def setup_vtk(self):
        """Configure le pipeline VTK"""
        # Renderer avec fond adaptatif
        self.renderer = vtk.vtkRenderer()
        self.update_background()
        
        # Ajouter une lumière
        light = vtk.vtkLight()
        light.SetPosition(1, 1, 1)
        light.SetLightTypeToSceneLight()
        self.renderer.AddLight(light)
        
        # Render window
        self.render_window = self.vtk_widget.GetRenderWindow()
        self.render_window.AddRenderer(self.renderer)
        
        # Interactor
        self.interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
        
        # Style d'interaction (trackball camera)
        style = vtk.vtkInteractorStyleTrackballCamera()
        self.interactor.SetInteractorStyle(style)
    
    def update_theme(self, dark=False):
        """Met à jour le thème du widget VTK"""
        self.is_dark_theme = dark
        self.update_background()
        self.update_mesh_colors()
        self.render_window.Render()
    
    def update_background(self):
        """Met à jour la couleur de fond selon le thème"""
        if self.is_dark_theme:
            self.renderer.SetBackground(0.1, 0.1, 0.1)  # Fond sombre
        else:
            self.renderer.SetBackground(0.95, 0.95, 0.95)  # Fond clair
    
    def update_mesh_colors(self):
        """Met à jour les couleurs des meshes selon le thème"""
        if self.recon_actor:
            if self.is_dark_theme:
                # COULEUR MESH RECONSTRUIT THÈME SOMBRE - Changez ici pour modifier
                self.recon_actor.GetProperty().SetColor(1.0, 1.0, 1.0)  # Blanc pour thème sombre
            else:
                # COULEUR MESH RECONSTRUIT THÈME CLAIR - Changez ici pour modifier
                self.recon_actor.GetProperty().SetColor(0.2, 0.4, 0.8)  # Bleu foncé pour thème clair
        
        if self.gt_actor:
            if self.is_dark_theme:
                # COULEUR GROUND TRUTH THÈME SOMBRE - Changez ici pour modifier
                self.gt_actor.GetProperty().SetColor(0.8, 0.8, 0.8)  # Gris clair pour thème sombre
            else:
                # COULEUR GROUND TRUTH THÈME CLAIR - Changez ici pour modifier
                self.gt_actor.GetProperty().SetColor(0.4, 0.4, 0.4)  # Gris foncé pour thème clair
    
    def load_ground_truth_only(self, gt_path):
        """Charge et affiche seulement le ground truth (pour prévisualisation)"""
        if self.gt_actor:
            self.renderer.RemoveActor(self.gt_actor)
        
        if gt_path and self.file_exists(gt_path):
            self.gt_actor = self.create_gt_actor(gt_path)
            self.renderer.AddActor(self.gt_actor)
            self.renderer.ResetCamera()
            self.render_window.Render()
    
    def update_actors(self, recon_path=None, gt_path=None, centerlines_path=None, dice_score=None):
        """Met à jour les acteurs avec de nouveaux fichiers"""
        # Supprimer les anciens acteurs
        if self.recon_actor:
            self.renderer.RemoveActor(self.recon_actor)
        if self.gt_actor:
            self.renderer.RemoveActor(self.gt_actor)
        if self.centerlines_actor:
            self.renderer.RemoveActor(self.centerlines_actor)
        
        # Charger le mesh reconstruit
        if recon_path and self.file_exists(recon_path):
            self.recon_actor = self.create_mesh_actor(recon_path, dice_score)
            self.renderer.AddActor(self.recon_actor)
            self.download_button.setEnabled(True)
        
        # Charger le ground truth
        if gt_path and self.file_exists(gt_path):
            self.gt_actor = self.create_gt_actor(gt_path)
            self.renderer.AddActor(self.gt_actor)
        
        # Charger les lignes centrales
        if centerlines_path and self.file_exists(centerlines_path):
            self.centerlines_actor = self.create_centerlines_actor(centerlines_path)
            self.renderer.AddActor(self.centerlines_actor)
        
        # Mettre à jour la vue
        self.renderer.ResetCamera()
        self.render_window.Render()
    
    def file_exists(self, path):
        """Vérifie si un fichier existe"""
        import os
        return os.path.exists(path)
    
    def create_mesh_actor(self, stl_path, dice_score=None):
        """Crée un acteur pour le mesh reconstruit avec coloration adaptative"""
        # Lecteur STL
        reader = vtk.vtkSTLReader()
        reader.SetFileName(stl_path)
        reader.Update()
        
        # Mapper
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(reader.GetOutputPort())
        
        # Acteur
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        
        # Coloration adaptative selon le thème
        if self.is_dark_theme:
            # COULEUR MESH RECONSTRUIT THÈME SOMBRE - Changez ici pour modifier
            color = (1.0, 1.0, 1.0)  # Blanc pour thème sombre
        else:
            # COULEUR MESH RECONSTRUIT THÈME CLAIR - Changez ici pour modifier
            color = (0.2, 0.4, 0.8)  # Bleu foncé pour thème clair
        
        actor.GetProperty().SetColor(*color)
        actor.GetProperty().SetOpacity(0.8)
        actor.GetProperty().SetSpecular(0.3)
        actor.GetProperty().SetSpecularPower(20)
        
        return actor
    
    def create_gt_actor(self, stl_path):
        """Crée un acteur pour le ground truth adaptatif au thème"""
        # Lecteur STL
        reader = vtk.vtkSTLReader()
        reader.SetFileName(stl_path)
        reader.Update()
        
        # Mapper
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(reader.GetOutputPort())
        
        # Acteur
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        
        # Couleur adaptative
        if self.is_dark_theme:
            # COULEUR GROUND TRUTH THÈME SOMBRE - Changez ici pour modifier
            actor.GetProperty().SetColor(0.8, 0.8, 0.8)  # Gris clair pour thème sombre
        else:
            # COULEUR GROUND TRUTH THÈME CLAIR - Changez ici pour modifier
            actor.GetProperty().SetColor(0.4, 0.4, 0.4)  # Gris foncé pour thème clair
        
        actor.GetProperty().SetOpacity(0.3)  # Semi-transparent
        actor.GetProperty().SetRepresentationToWireframe()  # Wireframe pour distinction
        
        return actor
    
    def create_centerlines_actor(self, vtp_path):
        """Crée un acteur pour les lignes centrales"""
        # Lecteur VTP
        reader = vtk.vtkXMLPolyDataReader()
        reader.SetFileName(vtp_path)
        reader.Update()
        
        # Tube filter pour épaissir les lignes
        tube_filter = vtk.vtkTubeFilter()
        tube_filter.SetInputConnection(reader.GetOutputPort())
        tube_filter.SetRadius(0.5)  # Rayon des tubes
        tube_filter.SetNumberOfSides(8)
        tube_filter.Update()
        
        # Mapper
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(tube_filter.GetOutputPort())
        
        # Acteur
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        # COULEUR CENTERLINES - Changez ici pour modifier
        actor.GetProperty().SetColor(1.0, 0.0, 0.0)  # Rouge vif
        actor.GetProperty().SetSpecular(0.5)
        actor.GetProperty().SetSpecularPower(30)
        
        return actor
    
    def toggle_recon_visibility(self):
        """Bascule la visibilité du mesh reconstruit"""
        if self.recon_actor:
            visible = self.toggle_recon_button.isChecked()
            self.recon_actor.SetVisibility(visible)
            self.render_window.Render()
    
    def toggle_gt_visibility(self):
        """Bascule la visibilité du ground truth"""
        if self.gt_actor:
            visible = self.toggle_gt_button.isChecked()
            self.gt_actor.SetVisibility(visible)
            self.render_window.Render()
    
    def toggle_centerlines_visibility(self):
        """Bascule la visibilité des lignes centrales"""
        if self.centerlines_actor:
            visible = self.toggle_centerlines_button.isChecked()
            self.centerlines_actor.SetVisibility(visible)
            self.render_window.Render()
    
    def reset_camera(self):
        """Remet la caméra dans sa position initiale"""
        self.renderer.ResetCamera()
        self.render_window.Render()
    
    def add_text_overlay(self, text, position=(10, 10)):
        """Ajoute un overlay de texte"""
        text_actor = vtk.vtkTextActor()
        text_actor.SetInput(text)
        text_actor.SetPosition(*position)
        text_actor.GetTextProperty().SetFontSize(12)
        text_actor.GetTextProperty().SetColor(1.0, 1.0, 1.0)
        self.renderer.AddActor2D(text_actor)
        return text_actor
    
    def export_screenshot(self, filename):
        """Exporte une capture d'écran de la vue 3D"""
        # Render pour s'assurer que tout est à jour
        self.render_window.Render()
        
        # Capture d'écran
        window_to_image = vtk.vtkWindowToImageFilter()
        window_to_image.SetInput(self.render_window)
        window_to_image.Update()
        
        # Writer PNG
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(filename)
        writer.SetInputConnection(window_to_image.GetOutputPort())
        writer.Write()
        
    def showEvent(self, event):
        """Appelé quand le widget devient visible"""
        super().showEvent(event)
        if hasattr(self, 'interactor'):
            self.interactor.Initialize()
            self.interactor.Start()
