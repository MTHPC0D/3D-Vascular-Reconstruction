import trimesh
import numpy as np
from itertools import permutations, product
from scipy.spatial.transform import Rotation as R

# === CHEMINS DES FICHIERS ===
recon_path = "output/levelSet_hom.stl"
gt_path = "data/gt_stl/01/01_AORTE_arteries.stl"

mesh_gt = trimesh.load_mesh(gt_path)
verts_gt = mesh_gt.vertices
center_gt = mesh_gt.bounding_box.centroid

# Génère toutes les permutations d'axes (0,1,2) et toutes les combinaisons de signes (+1/-1)
axes_perms = list(permutations([0, 1, 2]))
signs = list(product([1, -1], repeat=3))

mesh_recon_orig = trimesh.load_mesh(recon_path)
verts_orig = mesh_recon_orig.vertices
faces = mesh_recon_orig.faces

print("=== TEST DES PERMUTATIONS ET INVERSIONS D'AXES ===")
best = None
best_score = float('inf')

for perm in axes_perms:
    for sign in signs:
        verts = verts_orig[:, perm] * sign
        mesh_recon = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
        center_recon = mesh_recon.bounding_box.centroid
        translation = center_recon - center_gt

        # Axes principaux
        def principal_axes(mesh):
            v = mesh.vertices - mesh.bounding_box.centroid
            cov = np.cov(v.T)
            eigvals, eigvecs = np.linalg.eigh(cov)
            order = np.argsort(eigvals)[::-1]
            axes = eigvecs[:, order]
            if np.linalg.det(axes) < 0:
                axes[:, -1] *= -1
            return axes

        axes_recon = principal_axes(mesh_recon)
        axes_gt = principal_axes(mesh_gt)
        rot_matrix = axes_recon @ axes_gt.T
        rot = R.from_matrix(rot_matrix)
        rot_deg = rot.as_euler('xyz', degrees=True)

        # Score = norme translation + somme abs(rotation)
        score = np.linalg.norm(translation) + np.sum(np.abs(rot_deg))
        if score < best_score:
            best_score = score
            best = (perm, sign, translation, rot_deg)

        print(f"Perm {perm}, Sign {sign} | Δcentre: {translation.round(2)} mm | Rot: {rot_deg.round(2)} deg | Score: {score:.2f}")

print("\n=== MEILLEURE CORRESPONDANCE TROUVÉE ===")
print(f"Permutation: {best[0]}, Signe: {best[1]}")
print(f"Décalage centre: {best[2].round(2)} mm")
print(f"Rotation: {best[3].round(2)} deg")