import os
import SimpleITK as sitk
import numpy as np
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk

# === PARAMÈTRES ===
nii_seg_path = "data/2Dslices/01/label.nii"  # segmentation binaire
output_stl_path = "output/levelSet.stl"
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

# === 4. Export STL ===
stl_writer = vtk.vtkSTLWriter()
stl_writer.SetFileName(output_stl_path)
stl_writer.SetInputData(mc.GetOutput())
stl_writer.Write()

print(f"✅ Maillage STL enregistré : {output_stl_path}")
