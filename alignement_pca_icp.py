import trimesh
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation as R

# === PARAMÈTRES ===
recon_path = "output/levelSet_hom.stl"  # mesh reconstruit à la bonne échelle
gt_path = "data/gt_stl/01/01_AORTE_arteries.stl"
output_aligned_path = "output/levelSet_hom_align.stl"

# === 1. Chargement des deux maillages (trimesh pour PCA)
mesh_recon = trimesh.load_mesh(recon_path)
mesh_gt = trimesh.load_mesh(gt_path)

# === 2. Centrage des deux meshes sur l'origine
center_recon = mesh_recon.bounding_box.centroid
center_gt = mesh_gt.bounding_box.centroid
verts_recon_centered = mesh_recon.vertices - center_recon
verts_gt_centered = mesh_gt.vertices - center_gt

# === 3. Alignement des axes principaux (PCA)
def principal_axes(verts):
    cov = np.cov(verts.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    axes = eigvecs[:, order]
    if np.linalg.det(axes) < 0:
        axes[:, -1] *= -1
    return axes

axes_recon = principal_axes(verts_recon_centered)
axes_gt = principal_axes(verts_gt_centered)
rot_matrix = axes_gt @ axes_recon.T  # on veut amener recon sur GT

# Appliquer la rotation à la reconstruction centrée
verts_recon_rot = verts_recon_centered @ rot_matrix.T

# Recaler le centre sur le GT
verts_recon_final = verts_recon_rot + center_gt

# === 4. Sauvegarde STL aligné par PCA
mesh_recon_aligned = trimesh.Trimesh(vertices=verts_recon_final, faces=mesh_recon.faces, process=False)
mesh_recon_aligned.export(output_aligned_path)
print(f"✅ Mesh aligné par PCA sauvegardé : {output_aligned_path}")

# === 5. (Optionnel) Affinage par ICP (Open3D)
mesh_recon_o3d = o3d.io.read_triangle_mesh(output_aligned_path)
mesh_gt_o3d = o3d.io.read_triangle_mesh(gt_path)
mesh_recon_o3d.compute_vertex_normals()
mesh_gt_o3d.compute_vertex_normals()

recon_pcd = mesh_recon_o3d.sample_points_uniformly(number_of_points=100000)
gt_pcd = mesh_gt_o3d.sample_points_uniformly(number_of_points=100000)

threshold = 5.0
reg = o3d.pipelines.registration.registration_icp(
    recon_pcd, gt_pcd, threshold,
    estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPoint(),
    criteria=o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=2000)
)
mesh_recon_o3d.transform(reg.transformation)
o3d.io.write_triangle_mesh(output_aligned_path, mesh_recon_o3d)
print(f"✅ Mesh aligné affiné par ICP sauvegardé : {output_aligned_path}")