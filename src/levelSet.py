#!/usr/bin/env python3
"""
3‑D reconstruction + FPFH + RANSAC global alignment (rigid) + ICP refinement
Replaces PCA pre‑alignment with FPFH‑RANSAC, ensuring meshes are converted to point clouds before registration.
Maximises Dice overlap between reconstructed mesh and GT mesh.

Usage
-----
python recon_align_fpfh.py recon.nii.gz ref.stl out_aligned.stl [iso]

Dependencies: nibabel, numpy, scikit-image, trimesh, open3d >= 0.17
"""
import sys, json, itertools
import numpy as np
import nibabel as nib
import open3d as o3d
import trimesh as tm
from skimage.measure import marching_cubes

# --- Utils: load and mesh from NIfTI

def load_nifti(path):
    nii = nib.load(path)
    vol = nii.get_fdata().astype(np.float32)
    aff = nii.affine
    dx, dy, dz = np.linalg.norm(aff[:3,0]), np.linalg.norm(aff[:3,1]), np.linalg.norm(aff[:3,2])
    return vol, aff, (dx,dy,dz)


def levelset_to_mesh(vol, iso, spacing):
    verts, faces, _, _ = marching_cubes(vol, level=iso, spacing=spacing)
    mesh = o3d.geometry.TriangleMesh(
        o3d.utility.Vector3dVector(verts),
        o3d.utility.Vector3iVector(faces)
    )
    mesh.compute_vertex_normals()
    return mesh

# apply affine RT only

def apply_affine_rt_only(mesh, aff):
    R, t = aff[:3,:3], aff[:3,3]
    Rn = R / np.linalg.norm(R, axis=0)
    v = np.asarray(mesh.vertices)
    mesh.vertices = o3d.utility.Vector3dVector((Rn @ v.T).T + t)
    return mesh

# convert mesh to point cloud by uniform sampling

def mesh_to_pcd(mesh, num_points=20000):
    return mesh.sample_points_uniformly(number_of_points=num_points)

# preprocess: downsample, normals, FPFH

def preprocess_point_cloud(pcd, voxel_size):
    pcd_down = pcd.voxel_down_sample(voxel_size)
    pcd_down.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size*2, max_nn=30))
    fpfh = o3d.pipelines.registration.compute_fpfh_feature(
        pcd_down,
        o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size*5, max_nn=100)
    )
    return pcd_down, fpfh

# global RANSAC registration

def global_registration(src_mesh, tgt_mesh, voxel_size):
    src_pcd = mesh_to_pcd(src_mesh)
    tgt_pcd = mesh_to_pcd(tgt_mesh)
    src_down, src_fpfh = preprocess_point_cloud(src_pcd, voxel_size)
    tgt_down, tgt_fpfh = preprocess_point_cloud(tgt_pcd, voxel_size)

    dist_thresh = voxel_size * 1.5
    result = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
        src_down, tgt_down,
        src_fpfh, tgt_fpfh,
        mutual_filter=True,
        max_correspondence_distance=dist_thresh,
        estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPoint(False),
        ransac_n=4,
        checkers=[
            o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(0.9),
            o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(dist_thresh)
        ],
        criteria=o3d.pipelines.registration.RANSACConvergenceCriteria(400000, 500)
    )
    print(f"[RANSAC] fitness={result.fitness:.4f}, inlier_rmse={result.inlier_rmse:.4f}")
    return result.transformation

# refine with multi-scale ICP

def refine_registration(src_mesh, tgt_mesh, init_trans, voxel_size):
    src_pcd = mesh_to_pcd(src_mesh)
    tgt_pcd = mesh_to_pcd(tgt_mesh)
    src_pcd.transform(init_trans)

    trans = init_trans.copy()
    for factor in [5.0, 1.0]:
        vs = voxel_size * factor
        src_down = src_pcd.voxel_down_sample(vs)
        tgt_down = tgt_pcd.voxel_down_sample(vs)
        src_down.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=vs*2, max_nn=30))
        tgt_down.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=vs*2, max_nn=30))
        reg = o3d.pipelines.registration.registration_icp(
            src_down, tgt_down,
            vs * 1.5,
            trans,
            o3d.pipelines.registration.TransformationEstimationPointToPlane(),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=50)
        )
        trans = reg.transformation
        print(f"[ICP] voxel={vs:.3f}, fitness={reg.fitness:.4f}, rmse={reg.inlier_rmse:.4f}")
    return trans

# voxel/Dice utilities

def voxel_set(mesh, pitch):
    vox = tm.voxel.creation.voxelize(
        tm.Trimesh(vertices=np.asarray(mesh.vertices), faces=np.asarray(mesh.triangles)),
        pitch=pitch, method='subdivide'
    )
    return {tuple(idx) for idx in vox.sparse_indices}


def dice_sets(A, B):
    inter = len(A & B)
    return 2.0 * inter / (len(A) + len(B)) if (A or B) else 0.0

# main pipeline

def main(nii_path, ref_path, out_path, iso=0.5):
    vol, aff, (dx,dy,dz) = load_nifti(nii_path)
    mesh = levelset_to_mesh(vol, iso, spacing=(dx,dy,dz))
    mesh = apply_affine_rt_only(mesh, aff)
    ref_mesh = o3d.io.read_triangle_mesh(ref_path)
    ref_mesh = apply_affine_rt_only(ref_mesh, aff)

    # initial centroid translation
    delta = ref_mesh.get_center() - mesh.get_center()
    mesh.translate(delta)

    voxel_size = min(dx,dy,dz)
    # global + refine
    T_global = global_registration(mesh, ref_mesh, voxel_size)
    mesh.transform(T_global)
    T_icp = refine_registration(mesh, ref_mesh, T_global, voxel_size)
    mesh.transform(T_icp)

    # metrics
    pitch = voxel_size
    dice = dice_sets(voxel_set(mesh,pitch), voxel_set(ref_mesh,pitch))
    rms = np.sqrt(((np.asarray(mesh.sample_points_uniformly(20000).compute_point_cloud_distance(
        mesh.sample_points_uniformly(20000)))**2).mean()))

    o3d.io.write_triangle_mesh(out_path, mesh)
    print(json.dumps({"dice": dice, "rms_mm": rms}))

if __name__ == "__main__":
    if len(sys.argv) not in (4,5):
        sys.exit("usage: python recon_align_fpfh.py recon.nii.gz ref.stl out_aligned.stl [iso]")
    args = sys.argv
    main(args[1], args[2], args[3], float(args[4]) if len(args)==5 else 0.5)
