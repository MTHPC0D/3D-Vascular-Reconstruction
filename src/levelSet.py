#!/usr/bin/env python3
"""
recon_align.py
--------------
Pipeline :
1. lecture NIfTI   → volume binaire
2. reconstruction  → Level-set + Marching-Cubes
3. application de l’affine du NIfTI
4. pré-alignement  → PCA (rigide)
5. affinement      → ICP (rigide)
6. métriques       → Dice (ensembles de voxels) + RMS surfacique
7. écriture STL aligné
"""

import sys, json, numpy as np, nibabel as nib, open3d as o3d, trimesh as tm
from skimage.measure import marching_cubes
from scipy.spatial.transform import Rotation as R

# ---------- 1. chargement NIfTI ------------------------------------------------
def load_nifti(path):
    nii = nib.load(path)
    return nii.get_fdata().astype(np.float32), nii.affine          # volume, affine 4×4

# ---------- 2. reconstruction level-set (ici simple isosurface pour la démo) --
def levelset_to_mesh(vol, iso=0.5):
    verts, faces, _, _ = marching_cubes(vol, level=iso, spacing=(1, 1, 1))
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(verts)
    mesh.triangles = o3d.utility.Vector3iVector(faces)
    mesh.remove_duplicated_vertices()
    mesh.compute_vertex_normals()
    return mesh

# ---------- 3. appliquer l’affine ---------------------------------------------
def apply_affine(mesh, affine):
    v = np.asarray(mesh.vertices)
    v_h = np.c_[v, np.ones(len(v))]
    mesh.vertices = o3d.utility.Vector3dVector((affine @ v_h.T).T[:, :3])
    return mesh

# ---------- 4a. PCA rigide (rotation 3×3) --------------------------------------
def pca_axes(pts):
    pts_c = pts - pts.mean(0)
    cov   = np.cov(pts_c.T)             # 3×3
    w, V  = np.linalg.eigh(cov)
    return V[:, w.argsort()[::-1]]      # colonnes = axes triés desc.

def pca_prealign(src, tgt):
    R_src = pca_axes(np.asarray(src.vertices))
    R_tgt = pca_axes(np.asarray(tgt.vertices))
    rot   = R_tgt @ R_src.T             # matrice 3×3
    src.rotate(rot, center=np.zeros(3))
    return src

# ---------- 4b. ICP fin --------------------------------------------------------
def icp_align(src, tgt, thresh=2.0, iters=100):
    p_src = o3d.geometry.PointCloud(src.vertices)
    p_tgt = o3d.geometry.PointCloud(tgt.vertices)
    reg   = o3d.pipelines.registration.registration_icp(
        p_src, p_tgt, thresh, np.eye(4),
        o3d.pipelines.registration.TransformationEstimationPointToPoint(),
        o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=iters)
    )
    src.transform(reg.transformation)
    return src

# ---------- 5a. RMS surfacique -----------------------------------------------
def rms_dist(a, b):
    pa, pb = o3d.geometry.PointCloud(a.vertices), o3d.geometry.PointCloud(b.vertices)
    d1 = np.asarray(pa.compute_point_cloud_distance(pb))
    d2 = np.asarray(pb.compute_point_cloud_distance(pa))
    return float(np.sqrt((d1**2).mean() + (d2**2).mean()) / 2)

# ---------- 5b. Dice via ensembles de voxels ----------------------------------
def voxel_set(mesh, pitch=1.0):
    vox = tm.voxel.creation.voxelize(tm.Trimesh(vertices=np.asarray(mesh.vertices),
                                               faces=np.asarray(mesh.triangles)),
                                     pitch=pitch, method='subdivide')
    return {tuple(idx) for idx in vox.sparse_indices}

def dice_sets(A, B):
    inter = len(A & B)
    return 2.0 * inter / (len(A) + len(B)) if (A or B) else 0.0

# ---------- 6. pipeline complet -----------------------------------------------
def main(nii_path, stl_ref_path, stl_out_path,
         iso=0.5, pitch=2.0, icp_thresh=2.0, icp_iter=100):

    # 1-2 reconstruction
    vol, affine = load_nifti(nii_path)
    mesh        = levelset_to_mesh(vol, iso)
    mesh        = apply_affine(mesh, affine)

    # 3 lecture référence
    ref_mesh = o3d.io.read_triangle_mesh(stl_ref_path)
    mesh.translate(-mesh.get_center())
    ref_mesh.translate(-ref_mesh.get_center())

    # 4 alignement rigide (PCA + ICP)
    mesh = pca_prealign(mesh, ref_mesh)
    mesh = icp_align(mesh, ref_mesh, icp_thresh, icp_iter)

    # 5 métriques
    dice = dice_sets(voxel_set(mesh, pitch), voxel_set(ref_mesh, pitch))
    rms  = rms_dist(mesh, ref_mesh)

    # 6 écriture
    o3d.io.write_triangle_mesh(stl_out_path, mesh)
    print(json.dumps({"dice": dice, "rms_mm": rms}))

# ---------- exécution CLI ------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage : python recon_align.py recon.nii.gz ref.stl aligned_out.stl")
    main(sys.argv[1], sys.argv[2], sys.argv[3])
