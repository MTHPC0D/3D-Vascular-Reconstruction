import open3d as o3d
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation as R

# === CHEMINS DES FICHIERS À COMPARER ===
recon_path = "output/levelSet_hom_align.stl"
gt_path = "data/gt_stl/01/01_AORTE_arteries.stl"

# === Chargement des deux maillages ===
mesh_recon = trimesh.load_mesh(recon_path)
mesh_gt = trimesh.load_mesh(gt_path)

# === Vérification translation (décalage des centres) ===
center_recon = mesh_recon.bounding_box.centroid
center_gt = mesh_gt.bounding_box.centroid
translation = center_recon - center_gt
print("=== DÉCALAGE DES CENTRES (mm) ===")
print(f"→ X : {translation[0]:.3f}, Y : {translation[1]:.3f}, Z : {translation[2]:.3f}")

# === Vérification rotation (matrice d'alignement des axes principaux) ===
def principal_axes(mesh):
    # Centrage
    verts = mesh.vertices - mesh.bounding_box.centroid
    # PCA
    cov = np.cov(verts.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    # Ordonner par valeur propre décroissante
    order = np.argsort(eigvals)[::-1]
    axes = eigvecs[:, order]
    # Correction pour garantir une base main droite
    if np.linalg.det(axes) < 0:
        axes[:, -1] *= -1
    return axes

axes_recon = principal_axes(mesh_recon)
axes_gt = principal_axes(mesh_gt)
# Matrice de passage
rot_matrix = axes_recon @ axes_gt.T
rot = R.from_matrix(rot_matrix)
rot_deg = rot.as_euler('xyz', degrees=True)
print("\n=== ROTATION RELATIVE (degré, XYZ) ===")
print(f"→ X : {rot_deg[0]:.2f}, Y : {rot_deg[1]:.2f}, Z : {rot_deg[2]:.2f}")

# === Alerte si décalage ou rotation significative ===
if np.linalg.norm(translation) > 1.0:
    print("\n⚠️ Décalage de centre > 1 mm détecté !")
else:
    print("\n✅ Centres quasi-alignés (< 1 mm)")

if np.any(np.abs(rot_deg) > 2.0):
    print("⚠️ Rotation relative > 2° détectée !")
else:
    print("✅ Pas de rotation significative entre les axes principaux")

