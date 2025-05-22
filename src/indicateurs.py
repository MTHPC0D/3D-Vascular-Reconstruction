#!/usr/bin/env python3
"""
Calcul d'indicateurs vasculaires à partir de lignes centrales VTP
→ Tortuosité, angles de bifurcation/décollage, courbure, type d'arche aortique
"""

import vtk
import numpy as np
import json
import logging
from scipy.spatial.distance import cdist
from scipy.interpolate import UnivariateSpline
import argparse

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger()

class VascularIndicators:
    def __init__(self, vtp_file):
        """Initialise avec un fichier VTP de lignes centrales"""
        self.vtp_file = vtp_file
        self.polydata = self.load_vtp()
        self.branches = self.extract_branches()
        self.bifurcations = self.find_bifurcations()
        
    def load_vtp(self):
        """Charge le fichier VTP"""
        reader = vtk.vtkXMLPolyDataReader()
        reader.SetFileName(self.vtp_file)
        reader.Update()
        return reader.GetOutput()
    
    def extract_branches(self):
        """Extrait les branches individuelles du polydata"""
        branches = []
        for i in range(self.polydata.GetNumberOfCells()):
            cell = self.polydata.GetCell(i)
            if cell.GetCellType() == vtk.VTK_POLY_LINE:
                points = []
                for j in range(cell.GetNumberOfPoints()):
                    point_id = cell.GetPointId(j)
                    point = self.polydata.GetPoint(point_id)
                    points.append(np.array(point))
                branches.append(np.array(points))
        return branches
    
    def find_bifurcations(self):
        """Trouve les points de bifurcation"""
        # Créer un dictionnaire de tous les points
        all_points = {}
        point_connections = {}
        
        for branch_idx, branch in enumerate(self.branches):
            for i, point in enumerate(branch):
                point_key = tuple(np.round(point, 3))  # Arrondir pour éviter les erreurs de précision
                
                if point_key not in all_points:
                    all_points[point_key] = []
                    point_connections[point_key] = 0
                
                all_points[point_key].append((branch_idx, i))
                point_connections[point_key] += 1
        
        # Les bifurcations sont les points connectés à plus de 2 branches
        bifurcations = []
        for point_key, connections in point_connections.items():
            if connections > 2:
                bifurcations.append({
                    'position': np.array(point_key),
                    'branches': all_points[point_key],
                    'connections': connections
                })
        
        return bifurcations
    
    def calculate_global_tortuosity(self):
        """Calcule la tortuosité globale sur le chemin principal"""
        if not self.branches:
            return None
        
        # Trouver la branche la plus longue (chemin principal)
        main_branch_idx = 0
        max_length = 0
        
        for i, branch in enumerate(self.branches):
            length = self.calculate_path_length(branch)
            if length > max_length:
                max_length = length
                main_branch_idx = i
        
        main_branch = self.branches[main_branch_idx]
        
        # Longueur le long du chemin
        path_length = self.calculate_path_length(main_branch)
        
        # Distance euclidienne entre les extrémités
        euclidean_distance = np.linalg.norm(main_branch[-1] - main_branch[0])
        
        if euclidean_distance == 0:
            return None
        
        tortuosity = path_length / euclidean_distance
        
        logger.info(f"Tortuosité globale : {tortuosity:.3f} (chemin: {path_length:.1f}mm, euclidienne: {euclidean_distance:.1f}mm)")
        
        return {
            'tortuosity': tortuosity,
            'path_length_mm': path_length,
            'euclidean_distance_mm': euclidean_distance,
            'main_branch_index': main_branch_idx
        }
    
    def calculate_path_length(self, points):
        """Calcule la longueur d'un chemin de points"""
        if len(points) < 2:
            return 0
        differences = np.diff(points, axis=0)
        distances = np.linalg.norm(differences, axis=1)
        return np.sum(distances)
    
    def calculate_takeoff_angles(self):
        """Calcule les angles de décollage des branches principales"""
        if not self.bifurcations:
            logger.warning("Aucune bifurcation trouvée")
            return []
        
        takeoff_angles = []
        
        # Identifier l'axe principal (aorte ascendante) - généralement la branche la plus longue
        main_branch_idx = 0
        max_length = 0
        for i, branch in enumerate(self.branches):
            length = self.calculate_path_length(branch)
            if length > max_length:
                max_length = length
                main_branch_idx = i
        
        main_branch = self.branches[main_branch_idx]
        
        for bif in self.bifurcations:
            bif_pos = bif['position']
            
            # Trouver le vecteur direction de l'axe principal près de la bifurcation
            main_direction = self.get_direction_vector(main_branch, bif_pos)
            
            # Pour chaque branche connectée à cette bifurcation
            for branch_idx, point_idx in bif['branches']:
                if branch_idx == main_branch_idx:
                    continue  # Ignorer l'axe principal lui-même
                
                branch = self.branches[branch_idx]
                branch_direction = self.get_direction_vector(branch, bif_pos, from_bifurcation=True)
                
                if main_direction is not None and branch_direction is not None:
                    angle = self.angle_between_vectors(main_direction, branch_direction)
                    takeoff_angles.append({
                        'bifurcation_position': bif_pos,
                        'branch_index': branch_idx,
                        'angle_degrees': np.degrees(angle),
                        'main_direction': main_direction,
                        'branch_direction': branch_direction
                    })
        
        logger.info(f"Angles de décollage calculés : {len(takeoff_angles)} angles")
        for angle_info in takeoff_angles:
            logger.info(f"  Branche {angle_info['branch_index']}: {angle_info['angle_degrees']:.1f}°")
        
        return takeoff_angles
    
    def calculate_bifurcation_angles(self):
        """Calcule les angles de bifurcation"""
        bifurcation_angles = []
        
        for bif in self.bifurcations:
            bif_pos = bif['position']
            
            # Récupérer les directions de toutes les branches à cette bifurcation
            directions = []
            branch_indices = []
            
            for branch_idx, point_idx in bif['branches']:
                branch = self.branches[branch_idx]
                direction = self.get_direction_vector(branch, bif_pos, from_bifurcation=True)
                if direction is not None:
                    directions.append(direction)
                    branch_indices.append(branch_idx)
            
            # Calculer les angles entre toutes les paires de directions
            angles = []
            for i in range(len(directions)):
                for j in range(i + 1, len(directions)):
                    angle = self.angle_between_vectors(directions[i], directions[j])
                    angles.append({
                        'branch1': branch_indices[i],
                        'branch2': branch_indices[j],
                        'angle_degrees': np.degrees(angle)
                    })
            
            if angles:
                bifurcation_angles.append({
                    'bifurcation_position': bif_pos,
                    'angles': angles,
                    'mean_angle': np.mean([a['angle_degrees'] for a in angles])
                })
        
        logger.info(f"Angles de bifurcation calculés : {len(bifurcation_angles)} bifurcations")
        for i, bif_info in enumerate(bifurcation_angles):
            logger.info(f"  Bifurcation {i+1}: angle moyen {bif_info['mean_angle']:.1f}°")
        
        return bifurcation_angles
    
    def get_direction_vector(self, branch, reference_point, from_bifurcation=False, segment_length=5.0):
        """Calcule le vecteur direction d'une branche près d'un point de référence"""
        # Trouver le point le plus proche dans la branche
        distances = np.linalg.norm(branch - reference_point, axis=1)
        closest_idx = np.argmin(distances)
        
        if from_bifurcation:
            # Direction depuis la bifurcation vers l'extérieur
            if closest_idx < len(branch) - 1:
                # Prendre quelques points après la bifurcation pour avoir une direction stable
                end_idx = min(closest_idx + 5, len(branch) - 1)
                direction = branch[end_idx] - branch[closest_idx]
            else:
                return None
        else:
            # Direction vers la bifurcation
            if closest_idx > 0:
                start_idx = max(closest_idx - 5, 0)
                direction = branch[closest_idx] - branch[start_idx]
            else:
                return None
        
        # Normaliser le vecteur
        norm = np.linalg.norm(direction)
        if norm > 0:
            return direction / norm
        return None
    
    def angle_between_vectors(self, v1, v2):
        """Calcule l'angle entre deux vecteurs"""
        cos_angle = np.clip(np.dot(v1, v2), -1.0, 1.0)
        return np.arccos(cos_angle)
    
    def calculate_maximum_curvature(self):
        """Calcule la courbure maximale le long des lignes centrales"""
        max_curvature = 0
        max_curvature_info = None
        
        for branch_idx, branch in enumerate(self.branches):
            if len(branch) < 3:
                continue
            
            curvatures = self.calculate_curvature_along_path(branch)
            if len(curvatures) > 0:
                branch_max_curvature = np.max(curvatures)
                
                if branch_max_curvature > max_curvature:
                    max_curvature = branch_max_curvature
                    max_curvature_info = {
                        'branch_index': branch_idx,
                        'max_curvature': branch_max_curvature,
                        'min_radius_mm': 1.0 / branch_max_curvature if branch_max_curvature > 0 else np.inf
                    }
        
        if max_curvature_info:
            logger.info(f"Courbure maximale : {max_curvature:.6f} (rayon minimal: {max_curvature_info['min_radius_mm']:.1f}mm)")
        
        return max_curvature_info
    
    def calculate_curvature_along_path(self, points):
        """Calcule la courbure le long d'un chemin de points"""
        if len(points) < 3:
            return np.array([])
        
        # Calculer les vecteurs tangents
        tangents = []
        for i in range(1, len(points) - 1):
            # Vecteur tangent approximé par différences centrales
            tangent = (points[i + 1] - points[i - 1]) / 2
            norm = np.linalg.norm(tangent)
            if norm > 0:
                tangents.append(tangent / norm)
            else:
                tangents.append(np.array([0, 0, 0]))
        
        # Calculer la courbure
        curvatures = []
        for i in range(len(tangents) - 1):
            dt = tangents[i + 1] - tangents[i]
            ds = np.linalg.norm(points[i + 2] - points[i + 1])
            if ds > 0:
                curvature = np.linalg.norm(dt) / ds
                curvatures.append(curvature)
            else:
                curvatures.append(0)
        
        return np.array(curvatures)
    
    def classify_aortic_arch_type(self):
        """Classifie le type d'arche aortique (I, II, III)"""
        # Cette classification nécessite d'identifier spécifiquement les vaisseaux
        # Pour une implémentation complète, il faudrait une segmentation plus précise
        
        # Approximation basée sur la géométrie générale
        all_points = np.vstack(self.branches)
        
        # Trouver les limites en Y (hauteur)
        y_min, y_max = all_points[:, 1].min(), all_points[:, 1].max()
        y_range = y_max - y_min
        
        # Approximation simple basée sur la distribution des points en hauteur
        # Cette méthode devrait être raffinée avec une connaissance anatomique plus précise
        
        # Analyser la distribution des bifurcations en hauteur
        relative_height = None
        if self.bifurcations:
            bif_heights = [bif['position'][1] for bif in self.bifurcations]
            mean_bif_height = np.mean(bif_heights)
            relative_height = (mean_bif_height - y_min) / y_range
            
            if relative_height > 0.7:
                arch_type = "I"
                description = "Branches hautes - Type I"
            elif relative_height > 0.4:
                arch_type = "II"
                description = "Branches moyennes - Type II"
            else:
                arch_type = "III"
                description = "Branches basses - Type III"
        else:
            arch_type = "Indéterminé"
            description = "Pas assez de bifurcations pour classifier"
        
        logger.info(f"Type d'arche aortique : {arch_type} ({description})")
        
        return {
            'type': arch_type,
            'description': description,
            'y_range': y_range,
            'relative_height': relative_height
        }
    
    def calculate_all_indicators(self):
        """Calcule tous les indicateurs"""
        logger.info(f"Analyse des lignes centrales : {len(self.branches)} branches, {len(self.bifurcations)} bifurcations")
        
        indicators = {
            'global_tortuosity': self.calculate_global_tortuosity(),
            'takeoff_angles': self.calculate_takeoff_angles(),
            'bifurcation_angles': self.calculate_bifurcation_angles(),
            'maximum_curvature': self.calculate_maximum_curvature(),
            'aortic_arch_type': self.classify_aortic_arch_type()
        }
        
        return indicators
    
    def save_results(self, indicators, output_file):
        """Sauvegarde les résultats en JSON"""
        # Convertir les arrays numpy en listes pour la sérialisation JSON
        def convert_for_json(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.float64) or isinstance(obj, np.float32):
                return float(obj)
            elif isinstance(obj, np.int64) or isinstance(obj, np.int32):
                return int(obj)
            elif isinstance(obj, dict):
                return {k: convert_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_for_json(item) for item in obj]
            return obj
        
        json_indicators = convert_for_json(indicators)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_indicators, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Résultats sauvegardés dans {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Calcul d\'indicateurs vasculaires à partir de lignes centrales VTP')
    parser.add_argument('--vtp', default='output/centerlines_vtk.vtp', help='Fichier VTP des lignes centrales')
    parser.add_argument('--output', default='output/vascular_indicators.json', help='Fichier de sortie JSON')
    args = parser.parse_args()
    
    try:
        # Calculer les indicateurs
        analyzer = VascularIndicators(args.vtp)
        indicators = analyzer.calculate_all_indicators()
        
        # Sauvegarder les résultats
        analyzer.save_results(indicators, args.output)
        
        # Afficher un résumé
        print("\n" + "="*60)
        print("RÉSUMÉ DES INDICATEURS VASCULAIRES")
        print("="*60)
        
        if indicators['global_tortuosity']:
            print(f"Tortuosité globale: {indicators['global_tortuosity']['tortuosity']:.3f}")
        
        if indicators['takeoff_angles']:
            angles = [a['angle_degrees'] for a in indicators['takeoff_angles']]
            print(f"Angles de décollage: {len(angles)} branches, moyenne {np.mean(angles):.1f}°")
        
        if indicators['bifurcation_angles']:
            mean_angles = [b['mean_angle'] for b in indicators['bifurcation_angles']]
            print(f"Angles de bifurcation: {len(mean_angles)} bifurcations, moyenne {np.mean(mean_angles):.1f}°")
        
        if indicators['maximum_curvature']:
            print(f"Rayon minimal de courbure: {indicators['maximum_curvature']['min_radius_mm']:.1f}mm")
        
        print(f"Type d'arche aortique: {indicators['aortic_arch_type']['type']}")
        
        print("="*60)
        
    except Exception as e:
        logger.error(f"Erreur lors du calcul des indicateurs: {e}")
        raise

if __name__ == "__main__":
    main()