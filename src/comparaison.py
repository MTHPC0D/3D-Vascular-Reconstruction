import open3d as o3d
import numpy as np
import trimesh
import matplotlib.pyplot as plt

# === PARAMÈTRES ===
recon_path = "output/levelSet_hom_align5.stl"
gt_path = "data/gt_stl/01/01_AORTE_arteries.stl"
output_color_mesh_path = "output/levelSet_error_colored.ply"
output_error_img = "output/levelSet_error.png"

# === 1. Chargement des deux maillages
mesh_pred = o3d.io.read_triangle_mesh(recon_path)
mesh_gt = o3d.io.read_triangle_mesh(gt_path)
mesh_pred.compute_vertex_normals()
mesh_gt.compute_vertex_normals()

# === 2. Alignement initial avec ICP (optionnel)
threshold = 2.0
trans_init = np.identity(4)
reg_p2p = o3d.pipelines.registration.registration_icp(
    mesh_pred.sample_points_uniformly(5000),
    mesh_gt.sample_points_uniformly(5000),
    threshold, trans_init,
    o3d.pipelines.registration.TransformationEstimationPointToPoint()
)
mesh_pred.transform(reg_p2p.transformation)

# === 3. Échantillonnage des points
points_pred = mesh_pred.sample_points_uniformly(100000)
points_gt = mesh_gt.sample_points_uniformly(100000)

# === 4. Calcul des distances point-surface
distances = points_pred.compute_point_cloud_distance(points_gt)
distances = np.asarray(distances)

# === 5. Métriques
print("✅ Comparaison terminée")
print(f"→ Distance moyenne (RMS): {np.mean(distances):.3f} mm")
print(f"→ Distance max (Hausdorff approx): {np.max(distances):.3f} mm")

# Volume et surface (avec trimesh)
tm_pred = trimesh.load_mesh(recon_path)
tm_gt = trimesh.load_mesh(gt_path)
print(f"→ Ratio volume (Recon/GT): {tm_pred.volume / tm_gt.volume:.3f}")

# === 5b. Dice score (approximation surfacique)
dice_threshold = 1.0  # mm, à ajuster selon la précision voulue
A_in_B = np.sum(distances < dice_threshold)
distances_gt = points_gt.compute_point_cloud_distance(points_pred)
distances_gt = np.asarray(distances_gt)
B_in_A = np.sum(distances_gt < dice_threshold)
# Correction de la formule du Dice score
dice = (A_in_B + B_in_A) / (len(points_pred.points) + len(points_gt.points))
print(f"→ Dice score (surface, seuil {dice_threshold} mm): {dice:.3f}")

# === 6. Visualisation colorée des erreurs sur le maillage reconstruit
colors = plt.cm.jet((distances - distances.min()) / (distances.max() - distances.min()))[:, :3]
points_pred.colors = o3d.utility.Vector3dVector(colors)

# === 8. Sauvegarde d'une image PNG de la visualisation
vis = o3d.visualization.Visualizer()
vis.create_window(visible=False)
vis.add_geometry(points_pred)
vis.poll_events()
vis.update_renderer()
vis.capture_screen_image(output_error_img)
vis.destroy_window()
print(f"🖼️ Image PNG sauvegardée : {output_error_img}")

# === 9. (Optionnel) Affichage interactif si l'environnement le permet
try:
    o3d.visualization.draw_geometries([points_pred])
except Exception as e:
    print("Affichage interactif non disponible :", e)