import argparse
import nibabel as nib
import numpy as np
import open3d as o3d
from skimage import measure
from scipy.spatial.distance import directed_hausdorff

def marching_cubes_et_poisson(chemin_nifti, seuil=0.5, profondeur=8):
    img = nib.load(chemin_nifti)
    data = img.get_fdata()
    verts, faces, normals, _ = measure.marching_cubes(data, level=seuil)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(verts)
    pcd.normals = o3d.utility.Vector3dVector(normals)
    mesh_poisson, _ = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=profondeur)
    mesh_poisson.compute_vertex_normals()
    return mesh_poisson, img.affine

def appliquer_affine_sur_maillage(mesh, affine):
    sommets = np.asarray(mesh.vertices)
    sommets_homogenes = np.hstack([sommets, np.ones((sommets.shape[0], 1))])
    sommets_transformes = (affine @ sommets_homogenes.T).T[:, :3]
    mesh.vertices = o3d.utility.Vector3dVector(sommets_transformes)
    return mesh

def rotation_z_180(mesh):
    angle = np.pi
    rotation_z = np.array([
        [np.cos(angle), -np.sin(angle), 0],
        [np.sin(angle),  np.cos(angle), 0],
        [0,              0,             1]
    ])
    mesh.rotate(rotation_z, center=(0, 0, 0))
    return mesh


def main():
    parser = argparse.ArgumentParser(description="NIfTI to aligned STL with metrics.")
    parser.add_argument('--nifti', required=True, help='Chemin du fichier NIfTI')
    parser.add_argument('--gt', required=True, help='Chemin du STL ground truth')
    parser.add_argument('--out', required=True, help='Chemin du STL de sortie')
    parser.add_argument('--poisson_depth', type=int, default=8, help='Profondeur Poisson')
    parser.add_argument('--seuil', type=float, default=0.5, help='Seuil Marching Cubes')  # Ajouté
    args = parser.parse_args()

    print("1. Génération du mesh à partir du NIfTI...")
    mesh, affine = marching_cubes_et_poisson(args.nifti, seuil=args.seuil, profondeur=args.poisson_depth)

    print("2. Application de la matrice affine...")
    mesh = appliquer_affine_sur_maillage(mesh, affine)

    print("3. Rotation de 180° autour de Z...")
    mesh = rotation_z_180(mesh)
    print(f"Mesh généré : {len(mesh.vertices)} sommets, {len(mesh.triangles)} triangles")

    print(f"4. Sauvegarde du mesh aligné et rotationné : {args.out}")
    o3d.io.write_triangle_mesh(args.out, mesh)

if __name__ == "__main__":
    main()
