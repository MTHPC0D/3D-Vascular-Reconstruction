import os
import SimpleITK as sitk
import numpy as np
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk
import trimesh
import open3d as o3d

# === PARAMÈTRES ===
nii_seg_path = "data/2Dslices/01/label.nii"  # segmentation binaire
output_stl_path = "output/levelSet_hom_align.stl"
desired_spacing = [0.5, 0.5, 0.5]  # isotrope en mm

# === 1. Chargement et resampling isotrope ===
img = sitk.ReadImage(nii_seg_path)
resampler = sitk.ResampleImageFilter()
resampler.SetOutputSpacing(desired_spacing)
resampler.SetSize([int(sz*spc/dsp) for sz, spc, dsp in zip(img.GetSize(), img.GetSpacing(), desired_spacing)])
resampler.SetInterpolator(sitk.sitkNearestNeighbor)
resampler.SetOutputDirection(img.GetDirection())
resampler.SetOutputOrigin(img.GetOrigin())
resampled_img = resampler.Execute(img)

# === 2. Évolution level-set via morphologie (Morphological Chan-Vese approximation) ===
levelset = sitk.BinaryMorphologicalClosing(resampled_img, [1]*3)
levelset = sitk.BinaryFillhole(levelset)
levelset = sitk.BinaryDilate(levelset, [1]*3)  # expansion du contour
levelset = sitk.SignedMaurerDistanceMap(levelset, insideIsPositive=True, useImageSpacing=True)

# === 3. Extraction de surface (marching cubes) ===
def sitk_to_vtk_image(sitk_img):
    arr = sitk.GetArrayFromImage(sitk_img).astype(np.float32)
    vtk_img = vtk.vtkImageData()
    vtk_img.SetDimensions(arr.shape[2], arr.shape[1], arr.shape[0])
    vtk_arr = numpy_to_vtk(arr.ravel(), deep=True, array_type=vtk.VTK_FLOAT)
    vtk_img.GetPointData().SetScalars(vtk_arr)
    spacing = sitk_img.GetSpacing()
    origin = sitk_img.GetOrigin()
    vtk_img.SetSpacing(spacing)
    vtk_img.SetOrigin(origin)
    return vtk_img

vtk_image = sitk_to_vtk_image(levelset)

mc = vtk.vtkMarchingCubes()
mc.SetInputData(vtk_image)
mc.SetValue(0, 0.0)  # isosurface = zéro (contour)
mc.Update()

# === 4. Mise à l'échelle pour correspondre au GT ===
# Charger le mesh GT
mesh_gt = trimesh.load_mesh("data/gt_stl/01/01_AORTE_arteries.stl")
bbox_gt = mesh_gt.bounding_box.extents

# Appliquer la permutation optimale trouvée dans test_permutations.py
verts = np.array(mc.GetOutput().GetPoints().GetData())
verts = verts[:, [2, 0, 1]]  # permutation (2, 0, 1), signe (1, 1, 1)

# Calculer la bounding box du mesh reconstruit (marching cubes)
mesh_recon = trimesh.Trimesh(
    vertices=verts,
    faces=np.array([mc.GetOutput().GetPolys().GetData()]).reshape(-1, 4)[:, 1:4],
    process=False
)
bbox_recon = mesh_recon.bounding_box.extents

# Calculer le ratio d'échelle (GT/recon) pour chaque axe
scale_ratios = bbox_gt / bbox_recon

# === Affichage des bounding boxes pour debug échelle ===
print("\n=== DEBUG BOUNDING BOXES ===")
print(f"bbox_recon (avant scale): {bbox_recon}")
print(f"bbox_gt: {bbox_gt}")
print(f"scale_ratios: {scale_ratios}")

# Appliquer le scale au mesh VTK
transform = vtk.vtkTransform()
transform.Scale(scale_ratios[0], scale_ratios[1], scale_ratios[2])
transformFilter = vtk.vtkTransformPolyDataFilter()
transformFilter.SetInputData(mc.GetOutput())
transformFilter.SetTransform(transform)
transformFilter.Update()

# === 4b. Recalage de l'origine sur le GT ===
# Calcul du centre du GT et du mesh reconstruit (après scale)
center_gt = mesh_gt.bounding_box.centroid
# On récupère le mesh reconstruit après scale
verts_scaled = np.array(transformFilter.GetOutput().GetPoints().GetData())
verts_scaled = verts_scaled[:, [2, 0, 1]]  # permutation (2, 0, 1), signe (1, 1, 1)
mesh_scaled = trimesh.Trimesh(
    vertices=verts_scaled,
    faces=np.array([transformFilter.GetOutput().GetPolys().GetData()]).reshape(-1, 4)[:, 1:4],
    process=False
)
center_recon = mesh_scaled.bounding_box.centroid

# Calcul du vecteur de translation
translation = center_gt - center_recon

# Application de la translation au mesh VTK
transform2 = vtk.vtkTransform()
transform2.Translate(translation[0], translation[1], translation[2])
transformFilter2 = vtk.vtkTransformPolyDataFilter()
transformFilter2.SetInputData(transformFilter.GetOutput())
transformFilter2.SetTransform(transform2)
transformFilter2.Update()

# === 6. Export STL corrigé (échelle + alignement centre) ===
stl_writer = vtk.vtkSTLWriter()
stl_writer.SetFileName("output/levelSet_hom.stl")
stl_writer.SetInputData(transformFilter2.GetOutput())
stl_writer.Write()

print(f"✅ Maillage STL homogénéisé (échelle + centre) : output/levelSet_hom.stl")

# === 7. Alignement ICP sur le GT (rigide, sans scale) ===
mesh_recon_o3d = o3d.io.read_triangle_mesh("output/levelSet_hom.stl")
mesh_gt_o3d = o3d.io.read_triangle_mesh("data/gt_stl/01/01_AORTE_arteries.stl")

mesh_recon_o3d.compute_vertex_normals()
mesh_gt_o3d.compute_vertex_normals()

recon_pcd = mesh_recon_o3d.sample_points_uniformly(number_of_points=100000)
gt_pcd = mesh_gt_o3d.sample_points_uniformly(number_of_points=100000)

# Alignement grossier (centrage)
recon_pcd.translate(-recon_pcd.get_center())
gt_pcd.translate(-gt_pcd.get_center())

threshold = 5.0
reg = o3d.pipelines.registration.registration_icp(
    recon_pcd, gt_pcd, threshold,
    estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPoint(),
    criteria=o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=2000)
)

mesh_recon_o3d.transform(reg.transformation)
o3d.io.write_triangle_mesh("output/levelSet_hom_align.stl", mesh_recon_o3d)
print("✅ Maillage STL aligné (ICP) sauvegardé : output/levelSet_hom_align.stl")
