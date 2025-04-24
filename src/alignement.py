import open3d as o3d
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation as R
import copy

# === CHEMINS DES FICHIERS À COMPARER/ALIGNER ===
recon_path = "output/levelSet_hom.stl"
gt_path = "data/gt_stl/01/01_AORTE_arteries.stl"
output_aligned_path = "output/levelSet_hom_align.stl"

# === MODE DU SCRIPT ===
# True pour aligner le mesh et sauvegarder le résultat
# False pour seulement vérifier l'alignement entre deux meshes existants
do_alignment = True  # Changer selon besoin

# === Chargement des deux maillages ===
mesh_recon = trimesh.load_mesh(recon_path)
mesh_gt = trimesh.load_mesh(gt_path)

# === FONCTION : Vérification de l'alignement ===
def check_alignment(mesh_recon, mesh_gt):
    center_recon = mesh_recon.bounding_box.centroid
    center_gt = mesh_gt.bounding_box.centroid
    translation = center_recon - center_gt
    print("=== DÉCALAGE DES CENTRES (mm) ===")
    print(f"→ X : {translation[0]:.3f}, Y : {translation[1]:.3f}, Z : {translation[2]:.3f}")

    # Vérification rotation (matrice d'alignement des axes principaux)
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

    # Alerte si décalage ou rotation significative
    if np.linalg.norm(translation) > 1.0:
        print("\n⚠️ Décalage de centre > 1 mm détecté !")
    else:
        print("\n✅ Centres quasi-alignés (< 1 mm)")

    if np.any(np.abs(rot_deg) > 2.0):
        print("⚠️ Rotation relative > 2° détectée !")
    else:
        print("✅ Pas de rotation significative entre les axes principaux")
    
    return translation, rot_deg

# === FONCTION : Alignement robuste pour structures vasculaires ===
def align_vascular_meshes(recon_path, gt_path, output_path):
    # Charger les meshes avec Open3D
    mesh_recon_o3d = o3d.io.read_triangle_mesh(recon_path)
    mesh_gt_o3d = o3d.io.read_triangle_mesh(gt_path)
    mesh_recon_o3d.compute_vertex_normals()
    mesh_gt_o3d.compute_vertex_normals()
    
    # Estimation du rayon moyen des vaisseaux
    tm_recon = trimesh.load_mesh(recon_path)
    surface_area = tm_recon.area
    volume = tm_recon.volume
    approx_radius = volume / surface_area * 3  # approximation grossière
    print(f"Rayon moyen approx. des vaisseaux: {approx_radius:.2f} mm")
    
    # Sous-échantillonnage pour accélérer
    voxel_size = approx_radius / 2
    pcd_recon = mesh_recon_o3d.sample_points_uniformly(100000)
    pcd_gt = mesh_gt_o3d.sample_points_uniformly(100000)
    pcd_recon_down = pcd_recon.voxel_down_sample(voxel_size)
    pcd_gt_down = pcd_gt.voxel_down_sample(voxel_size)
    
    # Alignement initial par centrage et axes principaux (PCA)
    print("Alignement initial par centrage et PCA...")
    # Créer les matrices de covariance
    pcd_recon_down.estimate_normals()
    pcd_gt_down.estimate_normals()
    
    # Calculer les centres
    center_recon = pcd_recon_down.get_center()
    center_gt = pcd_gt_down.get_center()
    
    # Centrer les points
    points_recon = np.asarray(pcd_recon_down.points) - center_recon
    points_gt = np.asarray(pcd_gt_down.points) - center_gt
    
    # Calculer les axes principaux
    cov_recon = np.cov(points_recon.T)
    cov_gt = np.cov(points_gt.T)
    eigvals_recon, eigvecs_recon = np.linalg.eigh(cov_recon)
    eigvals_gt, eigvecs_gt = np.linalg.eigh(cov_gt)
    
    # Trier par valeurs propres décroissantes
    idx_recon = eigvals_recon.argsort()[::-1]
    eigvecs_recon = eigvecs_recon[:, idx_recon]
    idx_gt = eigvals_gt.argsort()[::-1]
    eigvecs_gt = eigvecs_gt[:, idx_gt]
    
    # Assurer des bases droites
    if np.linalg.det(eigvecs_recon) < 0:
        eigvecs_recon[:, -1] *= -1
    if np.linalg.det(eigvecs_gt) < 0:
        eigvecs_gt[:, -1] *= -1
    
    # Matrice de rotation pour aligner recon sur GT
    R_align = eigvecs_gt @ eigvecs_recon.T
    
    # Construire la transformation complète (rotation + translation)
    transform = np.eye(4)
    transform[:3, :3] = R_align
    transform[:3, 3] = center_gt - R_align @ center_recon
    
    # Appliquer la transformation au mesh
    mesh_recon_o3d.transform(transform)
    
    # Affinage avec ICP Point-to-Plane
    print("Affinage avec Point-to-Plane ICP...")
    icp_threshold = approx_radius
    pcd_recon_aligned = mesh_recon_o3d.sample_points_uniformly(100000)
    
    # ICP grossier
    print("Étape 1: ICP grossier...")
    icp_result = o3d.pipelines.registration.registration_icp(
        pcd_recon_aligned, pcd_gt,
        icp_threshold, np.eye(4),
        o3d.pipelines.registration.TransformationEstimationPointToPlane(),
        o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=500, relative_fitness=1e-8)
    )
    mesh_recon_o3d.transform(icp_result.transformation)
    
    # ICP fin avec seuil plus petit
    print("Étape 2: ICP fin avec échantillonnage plus dense...")
    pcd_recon_fine = mesh_recon_o3d.sample_points_uniformly(200000)
    icp_result_fine = o3d.pipelines.registration.registration_icp(
        pcd_recon_fine, pcd_gt,
        icp_threshold/2, np.eye(4),
        o3d.pipelines.registration.TransformationEstimationPointToPlane(),
        o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=500, relative_fitness=1e-10)
    )
    mesh_recon_o3d.transform(icp_result_fine.transformation)
    
    # Sauvegarder le mesh aligné
    o3d.io.write_triangle_mesh(output_path, mesh_recon_o3d)
    print(f"✅ Mesh aligné sauvegardé : {output_path}")
    
    return output_path

# === EXÉCUTION ===
if do_alignment:
    print("=== MODE ALIGNEMENT ===")
    aligned_path = align_vascular_meshes(recon_path, gt_path, output_aligned_path)
    
    # Vérifier l'alignement du résultat
    print("\n=== VÉRIFICATION DE L'ALIGNEMENT DU RÉSULTAT ===")
    mesh_aligned = trimesh.load_mesh(aligned_path)
    check_alignment(mesh_aligned, mesh_gt)
else:
    print("=== MODE VÉRIFICATION UNIQUEMENT ===")
    translation, rotation = check_alignment(mesh_recon, mesh_gt)