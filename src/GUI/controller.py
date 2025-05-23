#!/usr/bin/env python3
"""
Contrôleur pour gérer les opérations backend et l'interface utilisateur
"""

import os
import sys
import subprocess
import json
import threading
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QRunnable, QThreadPool

class VascularController(QObject):
    # Signaux pour communiquer avec l'interface
    progress_updated = pyqtSignal(int)
    log_message = pyqtSignal(str, str)  # message, level
    status_message = pyqtSignal(str)
    step_finished = pyqtSignal(str)
    results_ready = pyqtSignal(str)  # chemin du JSON des résultats
    mesh_ready = pyqtSignal(str, str, str)  # recon_path, gt_path, centerlines_path
    
    def __init__(self):
        super().__init__()
        self.thread_pool = QThreadPool()
        self.current_progress = 0
        
        # Chemins des fichiers de travail
        self.output_dir = "output"
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.recon_mesh_path = os.path.join(self.output_dir, "output_final.stl")
        self.centerlines_path = os.path.join(self.output_dir, "centerlines_vtk.vtp")
        self.indicators_path = os.path.join(self.output_dir, "vascular_indicators.json")
    
    def process_files(self, nifti_path, gt_path):
        """Lance le pipeline complet de traitement"""
        self.log_message.emit("Début du traitement...", "info")
        self.current_progress = 0
        self.progress_updated.emit(0)
        
        # Lancer dans un thread séparé
        worker = PipelineWorker(self, nifti_path, gt_path)
        worker.signals.progress.connect(self.progress_updated.emit)
        worker.signals.log.connect(self.log_message.emit)
        worker.signals.step_finished.connect(self.step_finished.emit)
        worker.signals.finished.connect(self.on_pipeline_finished)
        worker.signals.error.connect(self.on_pipeline_error)
        
        self.thread_pool.start(worker)
    
    def on_pipeline_finished(self, gt_path):
        """Appelé quand le pipeline est terminé"""
        self.log_message.emit("Pipeline terminé avec succès!", "success")
        self.status_message.emit("Traitement terminé")
        self.progress_updated.emit(100)
        
        # Émettre le signal pour mettre à jour la visualisation
        if os.path.exists(self.centerlines_path):
            self.mesh_ready.emit(self.recon_mesh_path, gt_path, self.centerlines_path)
        
        # Émettre le signal pour les résultats
        if os.path.exists(self.indicators_path):
            self.results_ready.emit(self.indicators_path)
    
    def on_pipeline_error(self, error_msg):
        """Appelé en cas d'erreur dans le pipeline"""
        self.log_message.emit(f"Erreur: {error_msg}", "error")
        self.status_message.emit("Erreur de traitement")
        self.progress_updated.emit(0)
    
    def load_indicators(self, json_path):
        """Charge les indicateurs depuis le fichier JSON"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.log_message.emit(f"Erreur lors du chargement des indicateurs: {str(e)}", "error")
            return {}

class WorkerSignals(QObject):
    progress = pyqtSignal(int)
    log = pyqtSignal(str, str)
    step_finished = pyqtSignal(str)
    finished = pyqtSignal(str)  # gt_path
    error = pyqtSignal(str)

class PipelineWorker(QRunnable):
    def __init__(self, controller, nifti_path, gt_path):
        super().__init__()
        self.controller = controller
        self.nifti_path = nifti_path
        self.gt_path = gt_path
        self.signals = WorkerSignals()
    
    def run(self):
        """Exécute le pipeline complet"""
        try:
            # Étape 1: Génération du mesh (25%)
            self.signals.log.emit("Génération du mesh...", "info")
            self.run_mesh_generation()
            self.signals.progress.emit(25)
            self.signals.step_finished.emit("mesh")
            
            # Étape 2: Comparaison (50%)
            self.signals.log.emit("Comparaison avec ground truth...", "info")
            self.run_comparison()
            self.signals.progress.emit(50)
            self.signals.step_finished.emit("comparison")
            
            # Étape 3: Extraction des centerlines (75%)
            self.signals.log.emit("Extraction des lignes centrales...", "info")
            self.run_centerlines_extraction()
            self.signals.progress.emit(75)
            self.signals.step_finished.emit("centerlines")
            
            # Étape 4: Calcul des indicateurs (100%)
            self.signals.log.emit("Calcul des indicateurs...", "info")
            self.run_indicators_calculation()
            self.signals.progress.emit(100)
            self.signals.step_finished.emit("indicators")
            
            self.signals.finished.emit(self.gt_path)
            
        except Exception as e:
            self.signals.error.emit(str(e))
    
    def run_mesh_generation(self):
        """Lance la génération du mesh"""
        cmd = [
            sys.executable, os.path.join("src", "process_nifti_to_stl.py"),
            "--nifti", self.nifti_path,
            "--gt", self.gt_path,
            "--out", self.controller.recon_mesh_path
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Erreur génération mesh: {result.stderr}")
    
    def run_comparison(self):
        """Lance la comparaison"""
        cmd = [
            sys.executable, os.path.join("src", "comparaison.py"),
            "--recon", self.controller.recon_mesh_path,
            "--gt", self.gt_path
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Erreur comparaison: {result.stderr}")
    
    def run_centerlines_extraction(self):
        """Lance l'extraction des centerlines"""
        cmd = [sys.executable, os.path.join("src", "centerlinesVMTK.py")]
        env = os.environ.copy()
        env["CENTERLINES_STL_FILE"] = self.controller.recon_mesh_path
        env["CENTERLINES_OUT_VTP"] = self.controller.centerlines_path
        
        result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Erreur extraction centerlines: {result.stderr}")
    
    def run_indicators_calculation(self):
        """Lance le calcul des indicateurs"""
        cmd = [
            sys.executable, os.path.join("src", "indicateurs.py"),
            "--vtp", self.controller.centerlines_path,
            "--output", self.controller.indicators_path
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Erreur calcul indicateurs: {result.stderr}")
