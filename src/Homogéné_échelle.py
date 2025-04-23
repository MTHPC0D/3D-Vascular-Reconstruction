import trimesh

# === CHEMINS DES FICHIERS À COMPARER ===
recon_path = "output/reconstruction_aligned.stl"

gt_path = "data/gt_stl/01/01_AORTE_arteries.stl"

# === Chargement des deux maillages ===
mesh_recon = trimesh.load_mesh(recon_path)
mesh_gt = trimesh.load_mesh(gt_path)

# === Calcul des bounding boxes ===
bbox_recon = mesh_recon.bounding_box.extents
bbox_gt = mesh_gt.bounding_box.extents

# === Affichage des tailles ===
print("=== TAILLES (Bounding Box Dimensions) ===")
print(f"→ Reconstruction (mm) : {bbox_recon}")
print(f"→ Ground Truth  (mm) : {bbox_gt}")

# === Vérification de l'échelle (ratio des tailles) ===
scale_ratios = bbox_recon / bbox_gt
print("\n=== RATIOS D'ÉCHELLE (Recon / GT) ===")
print(f"→ X : {scale_ratios[0]:.3f}, Y : {scale_ratios[1]:.3f}, Z : {scale_ratios[2]:.3f}")

# === Alerte si des écarts significatifs existent ===
if any((scale_ratios < 0.95) | (scale_ratios > 1.05)):
    print("\n⚠️ ÉCHELLE NON HOMOGÈNE : Des différences supérieures à 5% ont été détectées.")
else:
    print("\n✅ Les deux modèles sont à la même échelle.")
