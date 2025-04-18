import os
import numpy as np
import SimpleITK as sitk
from skimage import measure
import open3d as o3d
import trimesh

# === CONFIGURATION ===
nii_path = "data/2Dslices/01/label.nii"  # Fichier NIfTI binaire segmenté
output_path = "output/poisson.stl"
target_spacing = [0.5, 0.5, 0.5]  # Voxel isotrope recommandé

# === 1. Lecture du fichier NIfTI avec SimpleITK ===
img = sitk.ReadImage(nii_path)
original_spacing = img.GetSpacing()
original_size = img.GetSize()
new_size = [
    int(round(original_size[i] * (original_spacing[i] / target_spacing[i])))
    for i in range(3)
]

# === 2. Rééchantillonnage vers des voxels isotropes ===
resampler = sitk.ResampleImageFilter()
resampler.SetOutputSpacing(target_spacing)
resampler.SetSize(new_size)
resampler.SetOutputDirection(img.GetDirection())
resampler.SetOutputOrigin(img.GetOrigin())
resampler.SetInterpolator(sitk.sitkNearestNeighbor)
img_iso = resampler.Execute(img)

# === 3. Conversion en array numpy ===
volume = sitk.GetArrayFromImage(img_iso)  # (z, y, x)
spacing = img_iso.GetSpacing()

# === 4. Extraction du nuage de points sur la surface (isosurface) ===
verts, faces, _, _ = measure.marching_cubes(volume, level=0.5, spacing=spacing)

# === 5. Conversion vers Open3D PointCloud ===
pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(verts)
pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=1.0, max_nn=30))
pcd.orient_normals_consistent_tangent_plane(100)

# === 6. Reconstruction Poisson ===
mesh, _ = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=9)
mesh.compute_vertex_normals()

# === 7. Nettoyage : suppression des composants lointains/flottants ===
# Optionnel mais recommandé : ne garder que les triangles proches des points d'origine
mesh_crop = mesh.crop(mesh.get_axis_aligned_bounding_box().scale(1.05, mesh.get_center()))

# === 8. Export STL avec trimesh ===
mesh_trimesh = trimesh.Trimesh(
    vertices=np.asarray(mesh_crop.vertices),
    faces=np.asarray(mesh_crop.triangles),
    process=False
)
mesh_trimesh.export(output_path)

print(f"✅ Modèle STL généré avec succès : {output_path}")
