#!/usr/bin/env python3
"""
Extraction automatique de lignes centrales d’un STL vasculaire fermé
→ Voxelisation VTK + closing morphologique
→ Squelettisation 3D
→ Nettoyage par graphe + plus grand composant
→ Lissage optionnel & métriques
Requis : vtk, numpy, scikit-image, networkx, scipy
"""

import vtk
import numpy as np
from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtk
from skimage.morphology import skeletonize_3d, closing, ball
import networkx as nx
from scipy.spatial import cKDTree
import csv
import logging
import shutil
from scipy.ndimage import binary_fill_holes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger()

# ----------------- Paramètres utilisateur -----------------
stl_file       = "output\output_final.stl"
voxel_size_mm  = 0.4       # résolution du maillage voxel
closing_rad    = 2         # rayon (en voxels) pour closing morphologique
spur_prune_mm  = 1.0       # longueur minimale des rameaux (mm) - réduit pour préserver l'arche aortique
out_vtp        = "output/centerlines_vtk.vtp"
out_csv        = "output/metrics_vtk.csv"
do_smooth      = True      # True = applique vtkSmoothPolyDataFilter en fin
preserve_main_structure = True  # Préserve les structures principales même si déconnectées
# ----------------------------------------------------------

reader = vtk.vtkSTLReader()
reader.SetFileName(stl_file)
reader.Update()
stl_poly = reader.GetOutput()

# 2. Création d’un volume vide ------------------------------------------------
spacing = [voxel_size_mm]*3
bounds  = stl_poly.GetBounds()
dims    = [int((bounds[1]-bounds[0])/spacing[0]) + 1,
           int((bounds[3]-bounds[2])/spacing[1]) + 1,
           int((bounds[5]-bounds[4])/spacing[2]) + 1]
image = vtk.vtkImageData()
image.SetOrigin(bounds[0], bounds[2], bounds[4])
image.SetSpacing(*spacing)
image.SetDimensions(*dims)
image.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
image.GetPointData().GetScalars().Fill(0)

logger.info(f"Volume vide créé : dimensions={dims}, spacing={spacing}")

# 3. Voxelisation ------------------------------------------------------------
pol2stenc = vtk.vtkPolyDataToImageStencil()
pol2stenc.SetInputData(stl_poly)
pol2stenc.SetOutputOrigin(image.GetOrigin())
pol2stenc.SetOutputSpacing(image.GetSpacing())
pol2stenc.SetOutputWholeExtent(image.GetExtent())
pol2stenc.Update()

imgstenc = vtk.vtkImageStencil()
imgstenc.SetInputData(image)
imgstenc.SetStencilConnection(pol2stenc.GetOutputPort())
imgstenc.ReverseStencilOn()    # inverse le masque pour remplir l'intérieur
imgstenc.SetBackgroundValue(1) # 1 = intérieur
imgstenc.Update()

vtk_vol = imgstenc.GetOutput()

# Export du volume binaire
writer = vtk.vtkXMLImageDataWriter()
writer.SetInputData(vtk_vol)
writer.SetFileName("output/step1_volume.vti")
writer.Write()
logger.info("→ Export output/step1_volume.vti")

# 4. Passage en numpy + closing morphologique -------------------------------
vtk_vol = imgstenc.GetOutput()
dims   = vtk_vol.GetDimensions()
arr    = vtk_to_numpy(vtk_vol.GetPointData().GetScalars())
vol    = arr.reshape(dims[2], dims[1], dims[0]).astype(bool)

# Remplacer le closing 3D par binary_fill_holes en 2D
# À la place, comblez les petits trous plan par plan :
vol = np.stack([
    binary_fill_holes(vol[z, :, :])
    for z in range(vol.shape[0])
], axis=0)
logger.info("→ Remplissage 2D slice-by-slice appliqué")

# Récupérer l'origine pour les calculs de coordonnées mondiales
origin = np.array(image.GetOrigin())

# calcule le nombre de voxels remplis par tranche Z
slice_counts = vol.sum(axis=(1,2))
# trouve la première et dernière tranche non vide
z_nonzero = np.where(slice_counts>0)[0]
z0, z1 = z_nonzero.min(), z_nonzero.max()
logger.info(f"vol non vide sur Z indices [{z0}, {z1}] "
            f"(world Z [{origin[2] + z0*spacing[2]:.1f},{origin[2] + z1*spacing[2]:.1f}])")

# Export du volume binaire
writer = vtk.vtkXMLImageDataWriter()
writer.SetInputData(vtk_vol)
writer.SetFileName("output/step1_volume.vti")
writer.Write()
logger.info("→ Export output/step1_volume.vti")

# 5. Squelettisation 3D -------------------------------------------------------
skeleton = skeletonize_3d(vol)
idx      = np.argwhere(skeleton)
logger.info(f"Squelette brut : {len(idx)} voxels")

# Fonction correcte de conversion voxel → monde
def world(v):
    # v = (z, y, x) → on veut (x, y, z)
    return origin + np.array([v[2], v[1], v[0]]) * spacing

# Export du squelette brut
sk_pts = vtk.vtkPoints()
origin = np.array(image.GetOrigin())
for v in idx:
    coord = world(v)
    sk_pts.InsertNextPoint(*coord)
sk_poly = vtk.vtkPolyData()
sk_poly.SetPoints(sk_pts)
w = vtk.vtkXMLPolyDataWriter()
w.SetInputData(sk_poly)
w.SetFileName("output/step2_skeleton.vtp")
w.Write()
logger.info("→ Export output/step2_skeleton.vtp (brut)")

# Afficher quelques points pour vérification
for sample in idx[[0, len(idx)//2, -1]]:
    logger.info(f"voxel {sample} → {world(sample)}")

# 6. Construction du graphe & élagage des spurs ------------------------------
nbrs    = np.array([[i,j,k] for i in (-1,0,1)
                             for j in (-1,0,1)
                             for k in (-1,0,1)
                             if not (i==j==k==0)])
voxel2i = {tuple(v):n for n,v in enumerate(idx)}
G = nx.Graph()
for n,v in enumerate(idx):
    for d in nbrs:
        nb = tuple(v+d)
        if nb in voxel2i:
            G.add_edge(n, voxel2i[nb])

# Statistiques sur le graphe initial
comps = list(nx.connected_components(G))
sizes = sorted([len(c) for c in comps], reverse=True)
logger.info(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, "
            f"{len(comps)} components, top3 sizes={sizes[:3]}")

# 7bis. Extraction des cycles (boucles) manquantes -----------------------
try:
    cycles = nx.cycle_basis(G)
    logger.info(f"Cycles détectés dans le réseau : {len(cycles)}")
    
    cycles_ordered = []  # Initialize the list to store ordered cycles
    for cyc in cycles:
        # On ordonne les nœuds du cycle pour en faire une polyligne fermée
        ordered = []
        visited = {cyc[0]}
        current = cyc[0]
        # on part du premier, on enchaîne jusqu'à revenir à la source
        while True:
            neighbors = [n for n in G.neighbors(current) if n in cyc and n not in visited]
            if not neighbors:
                break
            nxt = neighbors[0]
            ordered.append(current)
            visited.add(nxt)
            current = nxt
        ordered.append(current)  # terminer sur la bifurcation de départ
        cycles_ordered.append(ordered)
    logger.info(f"→ Détection de {len(cycles)} cycle(s)")
except Exception as e:
    logger.error(f"Erreur lors de la détection des cycles: {e}")
    cycles_ordered = []
    
# Calculer les longueurs de branches avant élagage
branch_lens = []
for leaf in [n for n in G.nodes if G.degree[n]==1]:
    path_len = 0
    cur = leaf
    visited = {leaf}
    while G.degree[cur] <= 2:  # Jusqu'à une bifurcation
        neighbors = list(G.neighbors(cur))
        next_nodes = [n for n in neighbors if n not in visited]
        if not next_nodes:
            break
        next_node = next_nodes[0]
        path_len += 1
        visited.add(next_node)
        cur = next_node
        if G.degree[cur] > 2:  # Bifurcation
            break
    branch_lens.append(path_len)

if branch_lens:
    logger.info(f"Branches pré-prune : count={len(branch_lens)}, "
                f"min={min(branch_lens)}, max={max(branch_lens)}, "
                f"median={np.median(branch_lens)} voxels")
else:
    logger.info("Pas de branches trouvées avant élagage")

spur_vox = spur_prune_mm / voxel_size_mm

# 7. Analyse des composants AVANT élagage pour préserver les structures importantes
components_before = list(nx.connected_components(G))
logger.info(f"Composants avant élagage : {len(components_before)} composants, tailles : {sorted([len(c) for c in components_before], reverse=True)}")

# Élagage intelligent des spurs avec préservation des structures principales
nodes_to_remove = set()
spurs_removed = 0
spurs_preserved = 0

for leaf in [n for n in G.nodes if G.degree[n]==1]:
    if leaf in nodes_to_remove:
        continue
        
    path, cur = [leaf], leaf
    path_length_vox = 0
    
    # Suivre le chemin jusqu'à une bifurcation
    while G.degree[cur] <= 2 and cur not in nodes_to_remove:
        neighbors = [n for n in G.neighbors(cur) if n not in path]
        if not neighbors:
            break
        nxt = neighbors[0]
        path.append(nxt)
        path_length_vox += 1
        cur = nxt
        
        # Arrêter si on atteint une bifurcation (degré > 2)
        if G.degree[cur] > 2:
            break
    
    # Calculer la longueur physique du spur
    if len(path) > 1:
        path_coords = np.array([world(idx[n]) for n in path])
        path_length_mm = np.sum(np.linalg.norm(np.diff(path_coords, axis=0), axis=1))
    else:
        path_length_mm = 0
    
    # Critères de préservation plus sophistiqués
    should_preserve = False
    
    # 1. Préserver si le spur est assez long
    if path_length_mm > spur_prune_mm:
        should_preserve = True
    
    # 2. Préserver si le spur est dans une zone critique (arche aortique)
    # L'arche aortique est généralement dans la partie supérieure (Y > moyenne)
    if len(path) > 1:
        path_coords = np.array([world(idx[n]) for n in path])
        avg_y = np.mean(path_coords[:, 1])
        # Si le spur est dans la moitié supérieure en Y, être plus conservateur
        if avg_y > 0:  # Au-dessus du plan Y=0
            if path_length_mm > spur_prune_mm * 0.5:  # Critère plus relaxé
                should_preserve = True
    
    # 3. Préserver les spurs qui se connectent à des nœuds de haut degré
    if len(path) > 1 and G.degree[path[-1]] > 2:
        should_preserve = True
    
    if should_preserve:
        spurs_preserved += 1
        logger.debug(f"Spur préservé : {len(path)} nœuds, {path_length_mm:.1f}mm")
    else:
        # Supprimer seulement les nœuds du spur, pas le nœud de connexion
        nodes_to_remove.update(path[:-1] if len(path) > 1 else path)
        spurs_removed += 1

# Appliquer la suppression
if nodes_to_remove:
    G.remove_nodes_from(nodes_to_remove)

logger.info(f"Élagage intelligent : {spurs_removed} spurs supprimés, {spurs_preserved} spurs préservés")
logger.info(f"Après élagage spurs : {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")

# 7. Gestion intelligente des composants -------------------------------
components = list(nx.connected_components(G))
components_sizes = sorted([len(c) for c in components], reverse=True)
logger.info(f"Composants après élagage : {len(components)} composants, tailles : {components_sizes[:5]}")

if preserve_main_structure and len(components) > 1:
    # Préserver plusieurs composants s'ils sont significatifs
    significant_components = []
    main_size = components_sizes[0]
    
    for comp in components:
        comp_size = len(comp)
        # Garder les composants qui font au moins 10% du plus grand OU au moins 50 nœuds
        if comp_size >= max(main_size * 0.1, 50):
            significant_components.append(comp)
    
    if len(significant_components) > 1:
        # Créer un nouveau graphe avec tous les composants significatifs
        all_significant_nodes = set()
        for comp in significant_components:
            all_significant_nodes.update(comp)
        G = G.subgraph(all_significant_nodes).copy()
        logger.info(f"Graphe avec {len(significant_components)} composants significatifs : {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
    else:
        # Garder seulement le plus grand composant
        largest = max(components, key=len)
        G = G.subgraph(largest).copy()
        logger.info(f"Graphe réduit au plus grand composant : {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
else:
    # Comportement original : garder seulement le plus grand composant
    largest = max(components, key=len)
    G = G.subgraph(largest).copy()
    logger.info(f"Graphe réduit au plus grand composant : {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")

# Export du graphe après nettoyage
g_pts = vtk.vtkPoints()
g_lines = vtk.vtkCellArray()
for u, v in G.edges():
    line = vtk.vtkLine()
    pos_u = origin + idx[u]*np.array(spacing)
    pos_v = origin + idx[v]*np.array(spacing)
    pid0 = g_pts.InsertNextPoint(pos_u)
    pid1 = g_pts.InsertNextPoint(pos_v)
    line.GetPointIds().SetId(0, pid0)
    line.GetPointIds().SetId(1, pid1)
    g_lines.InsertNextCell(line)

g_poly = vtk.vtkPolyData()
g_poly.SetPoints(g_pts)
g_poly.SetLines(g_lines)
w = vtk.vtkXMLPolyDataWriter()
w.SetInputData(g_poly)
w.SetFileName("output/step3_graph_clean.vtp")
w.Write()
logger.info("→ Export output/step3_graph_clean.vtp")

# ---------------------------------------------------------------------
# 8. Extraction complète des segments (remplace tout le bloc branches)
# ---------------------------------------------------------------------
branches   = []
visited_es = set()                      # arêtes déjà parcourues
key_nodes  = [n for n in G.nodes if G.degree[n] != 2]
logger.info(f"Points clés (°≠2) : {len(key_nodes)}")

for u in key_nodes:
    for v in G.neighbors(u):
        if (u, v) in visited_es or (v, u) in visited_es:
            continue                    # arête déjà traitée
        # démarrer un nouveau segment
        path = [u, v]
        visited_es.add((u, v)); visited_es.add((v, u))
        prev, cur = u, v
        # tant que l’on chemine dans des nœuds degré = 2
        while G.degree[cur] == 2:
            nxt = [w for w in G.neighbors(cur) if w != prev][0]
            if (cur, nxt) in visited_es:
                break
            path.append(nxt)
            visited_es.add((cur, nxt)); visited_es.add((nxt, cur))
            prev, cur = cur, nxt
        branches.append(path)

logger.info(f"Segments extraits : {len(branches)} "
            f"– total arêtes couvertes = {sum(len(p)-1 for p in branches)}")


# 9. Construction du PolyData centre-lignes ---------------------------------
points = vtk.vtkPoints()
for v in idx:
    coord = world(v)
    points.InsertNextPoint(*coord)

lines = vtk.vtkCellArray()
for b in branches:
    poly = vtk.vtkPolyLine()
    poly.GetPointIds().SetNumberOfIds(len(b))
    for i, vid in enumerate(b):
        poly.GetPointIds().SetId(i, vid)
    lines.InsertNextCell(poly)

centerlines = vtk.vtkPolyData()
centerlines.SetPoints(points)
centerlines.SetLines(lines)

# Export des lignes centrales brutes (avant lissage)
writer_raw = vtk.vtkXMLPolyDataWriter()
writer_raw.SetFileName("output/centerlines_raw.vtp")
writer_raw.SetInputData(centerlines)
writer_raw.Write()
logger.info("→ Export output/centerlines_raw.vtp (avant lissage)")

# 9bis. Lissage des lignes centrales pour éliminer les micro-oscillations --------
logger.info("Application du lissage pour éliminer les micro-oscillations...")

if do_smooth:
    # Méthode 1: Lissage VTK (préserve la topologie)
    smoother = vtk.vtkSmoothPolyDataFilter()
    smoother.SetInputData(centerlines)
    smoother.SetNumberOfIterations(20)  # Nombre d'itérations de lissage
    smoother.SetRelaxationFactor(0.1)   # Facteur de relaxation (0.0-1.0)
    smoother.SetFeatureAngle(60.0)      # Préserve les angles < 60°
    smoother.FeatureEdgeSmoothingOff()  # Ne pas lisser les arêtes importantes
    smoother.BoundarySmoothingOn()      # Lisser les bords
    smoother.Update()
    
    centerlines_smooth1 = smoother.GetOutput()
    
    # Export du lissage VTK
    writer_smooth1 = vtk.vtkXMLPolyDataWriter()
    writer_smooth1.SetFileName("output/centerlines_smooth1_vtk.vtp")
    writer_smooth1.SetInputData(centerlines_smooth1)
    writer_smooth1.Write()
    logger.info("→ Export output/centerlines_smooth1_vtk.vtp (lissage VTK)")
    
    # Méthode 2: Spline filter pour un lissage plus avancé
    spline = vtk.vtkSplineFilter()
    spline.SetInputData(centerlines_smooth1)
    spline.SetSubdivideToLength()
    spline.SetLength(voxel_size_mm * 0.5)  # Subdivision plus fine que les voxels
    spline.Update()
    
    centerlines_smooth2 = spline.GetOutput()
    
    # Export du lissage par spline
    writer_smooth2 = vtk.vtkXMLPolyDataWriter()
    writer_smooth2.SetFileName("output/centerlines_smooth2_spline.vtp")
    writer_smooth2.SetInputData(centerlines_smooth2)
    writer_smooth2.Write()
    logger.info("→ Export output/centerlines_smooth2_spline.vtp (lissage spline)")
    
    # Méthode 3: Lissage personnalisé par segment pour préserver les bifurcations
    def smooth_branch_coords(coords, iterations=3, alpha=0.3):
        """Lissage par moyenne pondérée préservant les extrémités"""
        smooth_coords = coords.copy()
        for _ in range(iterations):
            new_coords = smooth_coords.copy()
            # Ne pas modifier les points de début et fin (bifurcations)
            for i in range(1, len(smooth_coords) - 1):
                # Moyenne pondérée avec les voisins
                prev_pt = smooth_coords[i-1]
                curr_pt = smooth_coords[i]
                next_pt = smooth_coords[i+1]
                
                # Nouveau point = mélange du point actuel et de la moyenne des voisins
                avg_neighbors = (prev_pt + next_pt) / 2
                new_coords[i] = (1 - alpha) * curr_pt + alpha * avg_neighbors
            smooth_coords = new_coords
        return smooth_coords
    
    # Créer une version lissée branche par branche
    smooth_points = vtk.vtkPoints()
    smooth_lines = vtk.vtkCellArray()
    point_id = 0
    
    for b in branches:
        # Récupérer les coordonnées de la branche
        branch_coords = np.array([world(idx[vid]) for vid in b])
        
        # Appliquer le lissage personnalisé seulement si la branche a plus de 3 points
        if len(branch_coords) > 3:
            smoothed_coords = smooth_branch_coords(branch_coords, iterations=3, alpha=0.2)
        else:
            smoothed_coords = branch_coords
        
        # Ajouter les points lissés
        branch_point_ids = []
        for coord in smoothed_coords:
            smooth_points.InsertNextPoint(*coord)
            branch_point_ids.append(point_id)
            point_id += 1
        
        # Créer la ligne
        poly = vtk.vtkPolyLine()
        poly.GetPointIds().SetNumberOfIds(len(branch_point_ids))
        for i, pid in enumerate(branch_point_ids):
            poly.GetPointIds().SetId(i, pid)
        smooth_lines.InsertNextCell(poly)
    
    centerlines_smooth3 = vtk.vtkPolyData()
    centerlines_smooth3.SetPoints(smooth_points)
    centerlines_smooth3.SetLines(smooth_lines)
    
    # Export du lissage personnalisé
    writer_smooth3 = vtk.vtkXMLPolyDataWriter()
    writer_smooth3.SetFileName("output/centerlines_smooth3_custom.vtp")
    writer_smooth3.SetInputData(centerlines_smooth3)
    writer_smooth3.Write()
    logger.info("→ Export output/centerlines_smooth3_custom.vtp (lissage personnalisé)")
    
    # Utiliser le lissage par spline comme résultat final (bon compromis)
    centerlines = centerlines_smooth2
    logger.info("✓ Lissage appliqué : utilisation du lissage par spline")
else:
    logger.info("Lissage désactivé")

# Vérifier l'alignement des boîtes englobantes
bounds_stl = stl_poly.GetBounds()  # [xmin,xmax,ymin,ymax,zmin,zmax]

# bornes de la ligne centrale
cl_pts = np.array([world(v) for v in idx])
bounds_cl = [
    cl_pts[:,0].min(), cl_pts[:,0].max(),
    cl_pts[:,1].min(), cl_pts[:,1].max(), 
    cl_pts[:,2].min(), cl_pts[:,2].max()
]

logger.info(f"STL bounds  : X[{bounds_stl[0]:.1f},{bounds_stl[1]:.1f}], "
            f"Y[{bounds_stl[2]:.1f},{bounds_stl[3]:.1f}], "
            f"Z[{bounds_stl[4]:.1f},{bounds_stl[5]:.1f}]")
logger.info(f"CL  bounds  : X[{bounds_cl[0]:.1f},{bounds_cl[1]:.1f}], "
            f"Y[{bounds_cl[2]:.1f},{bounds_cl[3]:.1f}], "
            f"Z[{bounds_cl[4]:.1f},{bounds_cl[5]:.1f}]")

# Fix the graph position to align correctly with the STL bounding box
logger.info("Correction de l'alignement des positions du graphe avec le STL...")

# Reuse our correct world coordinate transformation for the graph
g_pts_new = vtk.vtkPoints()
g_lines_new = vtk.vtkCellArray()

# Reconstruct the graph with corrected world coordinates
for u, v in G.edges():
    line = vtk.vtkLine()
    # Utiliser la fonction world correcte pour la transformation
    pos_u = world(idx[u])
    pos_v = world(idx[v])
    pid0 = g_pts_new.InsertNextPoint(pos_u)
    pid1 = g_pts_new.InsertNextPoint(pos_v)
    line.GetPointIds().SetId(0, pid0)
    line.GetPointIds().SetId(1, pid1)
    g_lines_new.InsertNextCell(line)

g_poly = vtk.vtkPolyData()
g_poly.SetPoints(g_pts_new)
g_poly.SetLines(g_lines_new)

# On vérifie que le graph est correctement positionné vis-à-vis du STL
g_pts_bounds = g_poly.GetBounds()
logger.info(f"STL bounds   : X[{bounds_stl[0]:.1f},{bounds_stl[1]:.1f}], "
            f"Y[{bounds_stl[2]:.1f},{bounds_stl[3]:.1f}], "
            f"Z[{bounds_stl[4]:.1f},{bounds_stl[5]:.1f}]")
logger.info(f"Graph bounds : X[{g_pts_bounds[0]:.1f},{g_pts_bounds[1]:.1f}], "
            f"Y[{g_pts_bounds[2]:.1f},{g_pts_bounds[3]:.1f}], "
            f"Z[{g_pts_bounds[4]:.1f},{g_pts_bounds[5]:.1f}]")

# Écrire le graphe corrigé vers la sortie
w = vtk.vtkXMLPolyDataWriter()
w.SetFileName("output/step3_graph_clean.vtp")
w.SetInputData(g_poly)
w.Write()

# On réutilise le même g_poly comme centre-lines finales
centerlines = g_poly

# (optionnel) : spline ou lissage, MAIS sans changer la topologie
# spline = vtk.vtkSplineFilter()
# spline.SetInputData(centerlines)
# spline.SetSubdivideToLength()
# spline.SetLength(voxel_size_mm)
# spline.Update()
# centerlines = spline.GetOutput()

# 12. Écriture du VTP --------------------------------------------------------
writer = vtk.vtkXMLPolyDataWriter()
writer.SetFileName(out_vtp)
writer.SetInputData(centerlines)
writer.Write()
logger.info(f"[FINAL] Centerlines (graph clean) : "
            f"points={centerlines.GetNumberOfPoints()}, "
            f"lines={centerlines.GetNumberOfLines()}")

# 13. Calcul et export CSV ---------------------------------------------------
with open(out_csv, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["BranchID","Length_mm","Chord_mm","Tortuosity"])
    for bid,b in enumerate(branches):
        coords = np.array([world(idx[i]) for i in b])  # Utilisation de la fonction world corrigée
        L      = np.linalg.norm(np.diff(coords,axis=0),axis=1).sum()
        C      = np.linalg.norm(coords[0]-coords[-1])
        tort   = L/C if C>0 else np.nan
        w.writerow([bid, L, C, tort])
logger.info(f"✅ Métriques dans {out_csv}")
