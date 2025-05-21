#!/usr/bin/env python

"""
Script pour convertir un fichier STL en format VTP.
Peut utiliser VMTK si disponible, sinon utilise VTK directement.

utiliser la commande suivante : python src/stl2vtp.py -i chemin/vers/fichier.stl -o chemin/vers/sortie.vtp --analyze --view

"""

import os
import sys
import argparse
import vtk
import traceback

# Essayer d'importer VMTK
try:
    from vmtk import vmtkscripts
    VMTK_AVAILABLE = True
except ImportError:
    VMTK_AVAILABLE = False
    print("AVERTISSEMENT: VMTK n'est pas disponible. Utilisation de VTK uniquement.")


def convert_stl_to_vtp_using_vtk(stl_file, vtp_file=None, verbose=False):
    """
    Convertit un fichier STL en format VTP en utilisant directement VTK.
    
    Paramètres:
    -----------
    stl_file : str
        Chemin vers le fichier STL d'entrée
    vtp_file : str, optional
        Chemin pour enregistrer le fichier VTP. Si None, utilise le même nom avec extension .vtp
    verbose : bool
        Afficher des messages détaillés
        
    Retourne:
    ---------
    str
        Chemin vers le fichier VTP généré
    """
    if vtp_file is None:
        vtp_file = os.path.splitext(stl_file)[0] + '.vtp'
    
    # Créer le répertoire de sortie s'il n'existe pas
    output_dir = os.path.dirname(vtp_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        if verbose:
            print(f"Répertoire de sortie créé: {output_dir}")
    
    try:
        # Lire le fichier STL
        reader = vtk.vtkSTLReader()
        reader.SetFileName(stl_file)
        reader.Update()
        
        # Nettoyer le polydata (optionnel mais recommandé)
        cleaner = vtk.vtkCleanPolyData()
        cleaner.SetInputConnection(reader.GetOutputPort())
        cleaner.Update()
        
        # Calculer les normales pour améliorer la qualité (optionnel)
        normals = vtk.vtkPolyDataNormals()
        normals.SetInputConnection(cleaner.GetOutputPort())
        normals.ComputePointNormalsOn()
        normals.ComputeCellNormalsOn()
        normals.SplittingOff()
        normals.ConsistencyOn()
        normals.AutoOrientNormalsOn()
        normals.Update()
        
        # Écrire au format VTP
        writer = vtk.vtkXMLPolyDataWriter()
        writer.SetFileName(vtp_file)
        writer.SetInputConnection(normals.GetOutputPort())
        writer.SetDataModeToAppended()  # Mode binaire plus compact
        writer.EncodeAppendedDataOff()  # Meilleure performance
        writer.SetCompressorTypeToZLib()  # Compression
        writer.Write()
        
        if verbose:
            input_size = os.path.getsize(stl_file) / (1024 * 1024.0)  # Taille en Mo
            output_size = os.path.getsize(vtp_file) / (1024 * 1024.0)  # Taille en Mo
            
            print(f"Conversion réussie:")
            print(f"  Fichier d'entrée (STL): {stl_file} ({input_size:.2f} Mo)")
            print(f"  Fichier de sortie (VTP): {vtp_file} ({output_size:.2f} Mo)")
            print(f"  Points: {reader.GetOutput().GetNumberOfPoints()}")
            print(f"  Cellules: {reader.GetOutput().GetNumberOfCells()}")
        else:
            print(f"Fichier STL converti en VTP avec succès: {vtp_file}")
            
        return vtp_file
    
    except Exception as e:
        print(f"ERREUR lors de la conversion STL vers VTP: {e}")
        traceback.print_exc()
        return None


def convert_stl_to_vtp_using_vmtk(stl_file, vtp_file=None, verbose=False):
    """
    Convertit un fichier STL en format VTP en utilisant VMTK.
    
    Paramètres:
    -----------
    stl_file : str
        Chemin vers le fichier STL d'entrée
    vtp_file : str, optional
        Chemin pour enregistrer le fichier VTP. Si None, utilise le même nom avec extension .vtp
    verbose : bool
        Afficher des messages détaillés
        
    Retourne:
    ---------
    str
        Chemin vers le fichier VTP généré
    """
    if vtp_file is None:
        vtp_file = os.path.splitext(stl_file)[0] + '.vtp'
    
    # Créer le répertoire de sortie s'il n'existe pas
    output_dir = os.path.dirname(vtp_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        if verbose:
            print(f"Répertoire de sortie créé: {output_dir}")
    
    try:
        # Utilisation de l'API VMTK
        reader = vmtkscripts.vmtkSurfaceReader()
        reader.InputFileName = stl_file
        reader.Execute()
        
        writer = vmtkscripts.vmtkSurfaceWriter()
        writer.Surface = reader.Surface
        writer.OutputFileName = vtp_file
        writer.Execute()
        
        if verbose:
            input_size = os.path.getsize(stl_file) / (1024 * 1024.0)  # Taille en Mo
            output_size = os.path.getsize(vtp_file) / (1024 * 1024.0)  # Taille en Mo
            
            print(f"Conversion réussie avec VMTK:")
            print(f"  Fichier d'entrée (STL): {stl_file} ({input_size:.2f} Mo)")
            print(f"  Fichier de sortie (VTP): {vtp_file} ({output_size:.2f} Mo)")
        else:
            print(f"Fichier STL converti en VTP avec succès via VMTK: {vtp_file}")
            
        return vtp_file
        
    except Exception as e:
        print(f"ERREUR lors de la conversion STL vers VTP avec VMTK: {e}")
        traceback.print_exc()
        print("Tentative de conversion avec VTK...")
        return convert_stl_to_vtp_using_vtk(stl_file, vtp_file, verbose)


def convert_stl_to_vtp(stl_file, vtp_file=None, use_vmtk=True, verbose=False):
    """
    Convertit un fichier STL en format VTP en utilisant VMTK ou VTK.
    
    Paramètres:
    -----------
    stl_file : str
        Chemin vers le fichier STL d'entrée
    vtp_file : str, optional
        Chemin pour enregistrer le fichier VTP. Si None, utilise le même nom avec extension .vtp
    use_vmtk : bool
        Tenter d'utiliser VMTK si disponible
    verbose : bool
        Afficher des messages détaillés
        
    Retourne:
    ---------
    str
        Chemin vers le fichier VTP généré
    """
    if not os.path.exists(stl_file):
        print(f"ERREUR: Le fichier STL '{stl_file}' n'existe pas.")
        return None
    
    if vtp_file is None:
        vtp_file = os.path.splitext(stl_file)[0] + '.vtp'
    
    if verbose:
        print(f"Conversion du fichier STL: {stl_file}")
        print(f"Vers le fichier VTP: {vtp_file}")
    
    if use_vmtk and VMTK_AVAILABLE:
        return convert_stl_to_vtp_using_vmtk(stl_file, vtp_file, verbose)
    else:
        if use_vmtk and not VMTK_AVAILABLE:
            print("VMTK demandé mais non disponible. Utilisation de VTK à la place.")
        return convert_stl_to_vtp_using_vtk(stl_file, vtp_file, verbose)


def analyze_vtp_file(vtp_file, verbose=True):
    """
    Analyse un fichier VTP et affiche ses informations.
    
    Paramètres:
    -----------
    vtp_file : str
        Chemin vers le fichier VTP à analyser
    verbose : bool
        Afficher des informations détaillées
    """
    if not os.path.exists(vtp_file):
        print(f"ERREUR: Le fichier VTP '{vtp_file}' n'existe pas.")
        return
    
    try:
        reader = vtk.vtkXMLPolyDataReader()
        reader.SetFileName(vtp_file)
        reader.Update()
        polydata = reader.GetOutput()
        
        print("\nAnalyse du fichier VTP:")
        print(f"  Chemin: {vtp_file}")
        print(f"  Taille: {os.path.getsize(vtp_file) / (1024 * 1024.0):.2f} Mo")
        print(f"  Nombre de points: {polydata.GetNumberOfPoints()}")
        print(f"  Nombre de cellules: {polydata.GetNumberOfCells()}")
        
        # Détails sur les types de cellules
        vertices = polydata.GetNumberOfVerts()
        lines = polydata.GetNumberOfLines()
        polys = polydata.GetNumberOfPolys()
        strips = polydata.GetNumberOfStrips()
        
        print(f"  Types de cellules:")
        print(f"    Vertices: {vertices}")
        print(f"    Lines: {lines}")
        print(f"    Polygones: {polys}")
        print(f"    Strips: {strips}")
        
        if verbose:
            # Vérifier si le modèle est fermé (manifold)
            feature_edges = vtk.vtkFeatureEdges()
            feature_edges.SetInputData(polydata)
            feature_edges.BoundaryEdgesOn()
            feature_edges.FeatureEdgesOff()
            feature_edges.ManifoldEdgesOff()
            feature_edges.NonManifoldEdgesOff()
            feature_edges.Update()
            
            is_closed = feature_edges.GetOutput().GetNumberOfPoints() == 0
            print(f"  Modèle fermé: {'Oui' if is_closed else 'Non'}")
            
            # Obtenir les limites du modèle
            bounds = polydata.GetBounds()
            print(f"  Boîte englobante:")
            print(f"    X: [{bounds[0]:.2f}, {bounds[1]:.2f}], étendue: {bounds[1]-bounds[0]:.2f}")
            print(f"    Y: [{bounds[2]:.2f}, {bounds[3]:.2f}], étendue: {bounds[3]-bounds[2]:.2f}")
            print(f"    Z: [{bounds[4]:.2f}, {bounds[5]:.2f}], étendue: {bounds[5]-bounds[4]:.2f}")
            
            # Afficher les arrays de données disponibles
            point_data = polydata.GetPointData()
            cell_data = polydata.GetCellData()
            
            print(f"  Arrays de données de points: {point_data.GetNumberOfArrays()}")
            for i in range(point_data.GetNumberOfArrays()):
                array = point_data.GetArray(i)
                print(f"    - {array.GetName()}: {array.GetNumberOfComponents()} composantes")
            
            print(f"  Arrays de données de cellules: {cell_data.GetNumberOfArrays()}")
            for i in range(cell_data.GetNumberOfArrays()):
                array = cell_data.GetArray(i)
                print(f"    - {array.GetName()}: {array.GetNumberOfComponents()} composantes")
        
    except Exception as e:
        print(f"ERREUR lors de l'analyse du fichier VTP: {e}")
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description='Conversion de fichiers STL en format VTP')
    parser.add_argument('-i', '--input', required=True, help='Fichier STL d\'entrée')
    parser.add_argument('-o', '--output', help='Fichier VTP de sortie (optionnel)')
    parser.add_argument('--vtk', action='store_true', help='Utiliser VTK même si VMTK est disponible')
    parser.add_argument('--analyze', action='store_true', help='Analyser le fichier VTP après conversion')
    parser.add_argument('-v', '--verbose', action='store_true', help='Afficher des informations détaillées')
    parser.add_argument('--view', action='store_true', help='Visualiser le résultat')
    
    args = parser.parse_args()
    
    # Vérifier l'extension du fichier d'entrée
    if not args.input.lower().endswith('.stl'):
        print("AVERTISSEMENT: Le fichier d'entrée ne semble pas être un fichier STL.")
        choice = input("Voulez-vous continuer quand même? (o/n): ")
        if choice.lower() != 'o':
            print("Annulation de la conversion.")
            return 1
    
    # Convertir le fichier
    use_vmtk = not args.vtk
    result = convert_stl_to_vtp(args.input, args.output, use_vmtk, args.verbose)
    
    if not result:
        print("ERREUR: La conversion a échoué.")
        return 1
    
    # Analyser le fichier converti si demandé
    if args.analyze:
        analyze_vtp_file(result, args.verbose)
    
    # Visualiser le fichier si demandé
    if args.view:
        try:
            print(f"Visualisation du fichier: {result}")
            
            # Créer un lecteur pour le fichier VTP
            reader = vtk.vtkXMLPolyDataReader()
            reader.SetFileName(result)
            reader.Update()
            
            # Créer un mapper et un acteur
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(reader.GetOutputPort())
            
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            
            # Configurer le rendu
            renderer = vtk.vtkRenderer()
            renderer.SetBackground(0.1, 0.2, 0.3)  # Fond bleu foncé
            renderer.AddActor(actor)
            
            # Créer une fenêtre de rendu
            render_window = vtk.vtkRenderWindow()
            render_window.AddRenderer(renderer)
            render_window.SetSize(800, 600)
            render_window.SetWindowName(f"Visualisation de {os.path.basename(result)}")
            
            # Configurer l'interactivité
            interactor = vtk.vtkRenderWindowInteractor()
            interactor.SetRenderWindow(render_window)
            
            # Style d'interaction (pour rotation/zoom)
            style = vtk.vtkInteractorStyleTrackballCamera()
            interactor.SetInteractorStyle(style)
            
            # Ajouter instructions
            text_actor = vtk.vtkTextActor()
            text_actor.SetInput("Clic gauche+déplacer: Rotation\nClic droit+déplacer: Zoom\nClic milieu+déplacer: Translation\n'q': Quitter")
            text_actor.GetTextProperty().SetFontSize(12)
            text_actor.GetTextProperty().SetColor(1.0, 1.0, 1.0)  # Texte blanc
            text_actor.SetPosition(10, 10)
            renderer.AddActor2D(text_actor)
            
            # Initialiser et démarrer la visualisation
            renderer.ResetCamera()
            interactor.Initialize()
            render_window.Render()
            interactor.Start()
            
        except Exception as e:
            print(f"ERREUR lors de la visualisation: {e}")
            traceback.print_exc()
    
    print(f"Conversion terminée avec succès: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
