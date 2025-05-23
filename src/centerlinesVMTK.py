#!/usr/bin/env python3
"""
Extraction optimisée de lignes centrales d'un STL vasculaire fermé
→ Voxelisation + squelettisation 3D + lissage
"""

import vtk
import numpy as np
import os
from vtk.util.numpy_support import vtk_to_numpy
from skimage.morphology import skeletonize_3d
import networkx as nx
import csv
from scipy.ndimage import binary_fill_holes

# Paramètres par défaut, peuvent être remplacés par des variables d'environnement
stl_file = os.environ.get("CENTERLINES_STL_FILE", "output/output_final.stl")
voxel_size_mm = float(os.environ.get("CENTERLINES_VOXEL_SIZE", "0.4"))
spur_prune_mm = float(os.environ.get("CENTERLINES_SPUR_PRUNE", "1.0"))
out_vtp = os.environ.get("CENTERLINES_OUT_VTP", "output/centerlines_vtk.vtp")
do_smooth = os.environ.get("CENTERLINES_DO_SMOOTH", "True").lower() == "true"
preserve_main_structure = os.environ.get("CENTERLINES_PRESERVE_MAIN", "True").lower() == "true"

# 1. Lecture STL
reader = vtk.vtkSTLReader()
reader.SetFileName(stl_file)
reader.Update()
stl_poly = reader.GetOutput()

# 2. Voxelisation
spacing = [voxel_size_mm] * 3
bounds = stl_poly.GetBounds()
dims = [int((bounds[1]-bounds[0])/spacing[0]) + 1,
        int((bounds[3]-bounds[2])/spacing[1]) + 1,
        int((bounds[5]-bounds[4])/spacing[2]) + 1]

image = vtk.vtkImageData()
image.SetOrigin(bounds[0], bounds[2], bounds[4])
image.SetSpacing(*spacing)
image.SetDimensions(*dims)
image.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
image.GetPointData().GetScalars().Fill(0)

pol2stenc = vtk.vtkPolyDataToImageStencil()
pol2stenc.SetInputData(stl_poly)
pol2stenc.SetOutputOrigin(image.GetOrigin())
pol2stenc.SetOutputSpacing(image.GetSpacing())
pol2stenc.SetOutputWholeExtent(image.GetExtent())
pol2stenc.Update()

imgstenc = vtk.vtkImageStencil()
imgstenc.SetInputData(image)
imgstenc.SetStencilConnection(pol2stenc.GetOutputPort())
imgstenc.ReverseStencilOn()
imgstenc.SetBackgroundValue(1)
imgstenc.Update()

# 3. Conversion numpy + remplissage des trous
vtk_vol = imgstenc.GetOutput()
dims = vtk_vol.GetDimensions()
arr = vtk_to_numpy(vtk_vol.GetPointData().GetScalars())
vol = arr.reshape(dims[2], dims[1], dims[0]).astype(bool)

vol = np.stack([
    binary_fill_holes(vol[z, :, :])
    for z in range(vol.shape[0])
], axis=0)

origin = np.array(image.GetOrigin())
print("✅ Volume voxelisé et rempli")

# 4. Squelettisation
skeleton = skeletonize_3d(vol)
idx = np.argwhere(skeleton)

def world(v):
    """Conversion voxel → coordonnées monde"""
    return origin + np.array([v[2], v[1], v[0]]) * spacing

# 5. Construction du graphe
nbrs = np.array([[i,j,k] for i in (-1,0,1) for j in (-1,0,1) for k in (-1,0,1) if not (i==j==k==0)])
voxel2i = {tuple(v): n for n, v in enumerate(idx)}
G = nx.Graph()

for n, v in enumerate(idx):
    for d in nbrs:
        nb = tuple(v + d)
        if nb in voxel2i:
            G.add_edge(n, voxel2i[nb])

# 6. Élagage intelligent des spurs
nodes_to_remove = set()
spurs_removed = 0
spurs_preserved = 0

for leaf in [n for n in G.nodes if G.degree[n] == 1]:
    if leaf in nodes_to_remove:
        continue
        
    path, cur = [leaf], leaf
    
    while G.degree[cur] <= 2 and cur not in nodes_to_remove:
        neighbors = [n for n in G.neighbors(cur) if n not in path]
        if not neighbors:
            break
        nxt = neighbors[0]
        path.append(nxt)
        cur = nxt
        if G.degree[cur] > 2:
            break
    
    # Calculer la longueur physique
    if len(path) > 1:
        path_coords = np.array([world(idx[n]) for n in path])
        path_length_mm = np.sum(np.linalg.norm(np.diff(path_coords, axis=0), axis=1))
    else:
        path_length_mm = 0
    
    # Critères de préservation
    should_preserve = False
    
    if path_length_mm > spur_prune_mm:
        should_preserve = True
    
    # Zone critique (arche aortique)
    if len(path) > 1:
        path_coords = np.array([world(idx[n]) for n in path])
        avg_y = np.mean(path_coords[:, 1])
        if avg_y > 0 and path_length_mm > spur_prune_mm * 0.5:
            should_preserve = True
    
    if len(path) > 1 and G.degree[path[-1]] > 2:
        should_preserve = True
    
    if should_preserve:
        spurs_preserved += 1
    else:
        nodes_to_remove.update(path[:-1] if len(path) > 1 else path)
        spurs_removed += 1

if nodes_to_remove:
    G.remove_nodes_from(nodes_to_remove)

# 7. Gestion des composants
components = list(nx.connected_components(G))
components_sizes = sorted([len(c) for c in components], reverse=True)

if preserve_main_structure and len(components) > 1:
    significant_components = []
    main_size = components_sizes[0]
    
    for comp in components:
        comp_size = len(comp)
        if comp_size >= max(main_size * 0.1, 50):
            significant_components.append(comp)
    
    if len(significant_components) > 1:
        all_significant_nodes = set()
        for comp in significant_components:
            all_significant_nodes.update(comp)
        G = G.subgraph(all_significant_nodes).copy()
    else:
        largest = max(components, key=len)
        G = G.subgraph(largest).copy()
else:
    largest = max(components, key=len)
    G = G.subgraph(largest).copy()

# 8. Extraction des segments
branches = []
visited_es = set()
key_nodes = [n for n in G.nodes if G.degree[n] != 2]

for u in key_nodes:
    for v in G.neighbors(u):
        if (u, v) in visited_es or (v, u) in visited_es:
            continue
        path = [u, v]
        visited_es.add((u, v))
        visited_es.add((v, u))
        prev, cur = u, v
        
        while G.degree[cur] == 2:
            nxt = [w for w in G.neighbors(cur) if w != prev][0]
            if (cur, nxt) in visited_es:
                break
            path.append(nxt)
            visited_es.add((cur, nxt))
            visited_es.add((nxt, cur))
            prev, cur = cur, nxt
        branches.append(path)

# 9. Construction des lignes centrales
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

# 10. Lissage
if do_smooth:
    # Lissage VTK
    smoother = vtk.vtkSmoothPolyDataFilter()
    smoother.SetInputData(centerlines)
    smoother.SetNumberOfIterations(20)
    smoother.SetRelaxationFactor(0.1)
    smoother.SetFeatureAngle(60.0)
    smoother.FeatureEdgeSmoothingOff()
    smoother.BoundarySmoothingOn()
    smoother.Update()
    
    # Lissage par spline
    spline = vtk.vtkSplineFilter()
    spline.SetInputData(smoother.GetOutput())
    spline.SetSubdivideToLength()
    spline.SetLength(voxel_size_mm * 0.5)
    spline.Update()
    
    centerlines = spline.GetOutput()
    print("✅ Lissage appliqué")

# 11. Export final
writer = vtk.vtkXMLPolyDataWriter()
writer.SetFileName(out_vtp)
writer.SetInputData(centerlines)
writer.Write()

print(f"✅ Lignes centrales : {centerlines.GetNumberOfPoints()} points, {centerlines.GetNumberOfLines()} lignes")
