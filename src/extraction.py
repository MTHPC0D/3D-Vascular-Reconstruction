#!/usr/bin/env python

"""
Script pour extraire les lignes centrales d'un modèle vasculaire 3D (STL) en utilisant VMTK.
"""

from vmtk import vmtkscripts
import os
import argparse

def extract_centerlines(input_stl, output_vtp, smoothing_iterations=20):
    """
    Extrait les lignes centrales d'un modèle 3D vasculaire.
    
    Args:
        input_stl (str): Chemin vers le fichier STL d'entrée
        output_vtp (str): Chemin où enregistrer les lignes centrales (format VTP)
        smoothing_iterations (int): Nombre d'itérations pour le lissage de surface
    
    Returns:
        object: Objet VTK contenant les lignes centrales
    """
    print(f"Extraction des lignes centrales depuis: {input_stl}")
    
    # 1. Lecture du modèle STL (surface vasculaire)
    surface_reader = vmtkscripts.vmtkSurfaceReader()
    surface_reader.InputFileName = input_stl
    surface_reader.Execute()
    surface = surface_reader.Surface
    
    # 2. Lissage de la surface pour supprimer le bruit
    print("Lissage de la surface...")
    surface_smoother = vmtkscripts.vmtkSurfaceSmoothing()
    surface_smoother.Surface = surface
    surface_smoother.NumberOfSmoothingIterations = smoothing_iterations
    surface_smoother.Execute()
    smoothed_surface = surface_smoother.Surface
    
    # 3. Définition des points d'entrée et de sortie (extrémités)
    print("Identification automatique des extrémités...")
    
    # Utiliser une méthode simplifiée avec un sélecteur de points interactif
    print("Préparation de l'extraction des lignes centrales...")
    centerlines_filter = vmtkscripts.vmtkCenterlines()
    centerlines_filter.Surface = smoothed_surface
    centerlines_filter.SeedSelectorName = 'openprofiles'
    centerlines_filter.AppendEndPoints = 1
    centerlines_filter.Execute()
    centerlines = centerlines_filter.Centerlines
    
    # 5. Calcul de la géométrie (longueur, courbure, tortuosité)
    print("Calcul des propriétés géométriques...")
    geometry_filter = vmtkscripts.vmtkCenterlineGeometry()
    geometry_filter.Centerlines = centerlines
    geometry_filter.Execute()
    centerlines_with_geometry = geometry_filter.Centerlines
    
    # 6. Calcul des sections (radius, etc.)
    attributes_filter = vmtkscripts.vmtkCenterlineAttributes()
    attributes_filter.Centerlines = centerlines_with_geometry
    attributes_filter.Execute()
    centerlines_with_attributes = attributes_filter.Centerlines
    
    # 7. Sauvegarde des lignes centrales
    print(f"Enregistrement des lignes centrales vers: {output_vtp}")
    centerline_writer = vmtkscripts.vmtkSurfaceWriter()
    centerline_writer.Surface = centerlines_with_attributes
    centerline_writer.OutputFileName = output_vtp
    centerline_writer.Execute()
    
    return centerlines_with_attributes

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extraction de lignes centrales à partir d'un modèle 3D vasculaire")
    parser.add_argument("input_stl", help="Chemin vers le fichier STL d'entrée")
    parser.add_argument("--output", "-o", default=None, 
                       help="Chemin vers le fichier de sortie (VTP). Par défaut: [input]_centerlines.vtp")
    parser.add_argument("--smoothing", "-s", type=int, default=20,
                       help="Nombre d'itérations pour le lissage (défaut: 20)")
    
    args = parser.parse_args()
    
    # Création du nom de fichier de sortie si non spécifié
    if args.output is None:
        base_name = os.path.splitext(args.input_stl)[0]
        args.output = f"{base_name}_centerlines.vtp"
    
    # Extraction des lignes centrales
    extract_centerlines(args.input_stl, args.output, args.smoothing)
    
    print("Extraction terminée avec succès!")
