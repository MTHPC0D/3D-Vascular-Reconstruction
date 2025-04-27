import os
import SimpleITK as sitk
import numpy as np
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk

# === PARAMÈTRES ===
nii_seg_path = "data/2Dslices/02/02_label.nii"  # segmentation binaire
output_stl_path = "output/marginCube.stl"
desired_spacing = [0.5, 0.5, 0.5]  # voxels isotropes

# === 1. Chargement et resampling isotrope ===
img = sitk.ReadImage(nii_seg_path)

resampler = sitk.ResampleImageFilter()
resampler.SetOutputSpacing(desired_spacing)
resampler.SetSize([int(sz*spc/dsp) for sz, spc, dsp in zip(img.GetSize(), img.GetSpacing(), desired_spacing)])
resampler.SetInterpolator(sitk.sitkNearestNeighbor)
resampler.SetOutputDirection(img.GetDirection())
resampler.SetOutputOrigin(img.GetOrigin())
resampled_img = resampler.Execute(img)

# === 2. Conversion vers VTK ===
def sitk_to_vtk_image(sitk_img):
    arr = sitk.GetArrayFromImage(sitk_img).astype(np.uint8)
    vtk_img = vtk.vtkImageData()
    vtk_img.SetDimensions(arr.shape[2], arr.shape[1], arr.shape[0])
    vtk_arr = numpy_to_vtk(arr.ravel(), deep=True, array_type=vtk.VTK_UNSIGNED_CHAR)
    vtk_img.GetPointData().SetScalars(vtk_arr)
    spacing = sitk_img.GetSpacing()
    origin = sitk_img.GetOrigin()
    vtk_img.SetSpacing(spacing)
    vtk_img.SetOrigin(origin)
    return vtk_img

vtk_image = sitk_to_vtk_image(resampled_img)

# === 3. Application Marching Cubes ===
mc = vtk.vtkMarchingCubes()
mc.SetInputData(vtk_image)
mc.SetValue(0, 0.5)  # seuil pour binaire 0/1
mc.Update()

# === 4. Export STL ===
writer = vtk.vtkSTLWriter()
writer.SetFileName(output_stl_path)
writer.SetInputData(mc.GetOutput())
writer.Write()

print(f"✅ Maillage STL généré avec Marching Cubes : {output_stl_path}")
