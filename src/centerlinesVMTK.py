#!/usr/bin/env python3
"""
Extraction automatique des centre-lines d’un maillage vasculaire fermé
---------------------------------------------------------------------

Usage :
    python extract_centerlines.py --input vessel.stl \
                                  --output centerlines.vtp \
                                  --spacing 0.4
    (la résolution « spacing » est en mm ; défaut = 0.5)
"""

import argparse
import vtk
import numpy as np
from vtk.util import numpy_support
import itk
from vmtk import vmtkscripts
import SimpleITK as sitk

# ---------- Arguments CLI ----------
parser = argparse.ArgumentParser(description='Center-line extraction from a closed STL mesh')
parser.add_argument('-i', '--input',  required=True, help='Maillage entrée (.stl ou .vtp)')
parser.add_argument('-o', '--output', required=True, help='Fichier centre-lines (.vtp)')
parser.add_argument('-s', '--spacing', type=float, default=0.5,
                    help='Résolution isotrope voxel (mm). Défaut = 0.5')
args = parser.parse_args()

try:
    print("Étape 1 : lecture maillage")
    # ---------- Lecture du maillage ----------
    def read_polydata(path):
        if path.lower().endswith('.stl'):
            reader = vtk.vtkSTLReader()
        elif path.lower().endswith(('.vtp', '.xml', '.vtk')):
            reader = vtk.vtkXMLPolyDataReader()
        else:
            raise ValueError('Format non supporté : %s' % path)
        reader.SetFileName(path)
        reader.Update()
        return reader.GetOutput()

    polydata = read_polydata(args.input)

    print("Étape 2 : voxelisation")
    # ---------- Voxelisation ----------
    spacing = [args.spacing]*3
    bounds  = polydata.GetBounds()                 # xmin,xmax, ymin,ymax, zmin,zmax
    dims    = [int((bounds[2*i+1]-bounds[2*i])/spacing[i]) + 1 for i in range(3)]

    image   = vtk.vtkImageData()
    image.SetSpacing(spacing)
    image.SetDimensions(dims)
    image.SetOrigin(bounds[0], bounds[2], bounds[4])
    image.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
    image.GetPointData().GetScalars().Fill(1)      # remplissage initial = 1

    stenciler = vtk.vtkPolyDataToImageStencil()
    stenciler.SetInputData(polydata)
    stenciler.SetOutputOrigin(image.GetOrigin())
    stenciler.SetOutputSpacing(spacing)
    stenciler.SetOutputWholeExtent(image.GetExtent())
    stenciler.Update()

    img_stencil = vtk.vtkImageStencil()
    img_stencil.SetInputData(image)
    img_stencil.SetStencilConnection(stenciler.GetOutputPort())
    img_stencil.ReverseStencilOff()                # conserve l’intérieur = 1
    img_stencil.SetBackgroundValue(0)              # extérieur = 0
    img_stencil.Update()

    binary_vtk = img_stencil.GetOutput()           # masque binaire intérieur

    print("Binary mask stats:")
    print("Dimensions:", binary_vtk.GetDimensions())
    print("Scalar range:", binary_vtk.GetScalarRange())  # Devrait être (0, 1)

    print("Étape 3 : conversion ITK")
    # ---------- Conversion VTK -> ITK ----------
    dims = binary_vtk.GetDimensions()
    vtk_array = numpy_support.vtk_to_numpy(binary_vtk.GetPointData().GetScalars())
    vtk_array = vtk_array.reshape(dims[2], dims[1], dims[0])  # z,y,x
    # Forcer la binarisation et le type uint8
    vtk_array = (vtk_array > 0).astype(np.uint8)
    itk_image = itk.image_from_array(vtk_array)
    itk_image.SetSpacing(spacing)
    itk_image.SetOrigin(binary_vtk.GetOrigin())

    print("ITK image type:", type(itk_image))
    print("ITK image shape:", itk_image.GetBufferedRegion().GetSize())
    print("ITK image pixel type:", itk.template(itk_image)[1])
    print("ITK image min/max:", np.min(vtk_array), np.max(vtk_array))

    print("ITK version:", itk.Version.GetITKVersion())

    print("Étape 4 : thinning (SimpleITK)")
    # ---------- Thinning SimpleITK ----------
    print("→ Appliquer BinaryThinningImageFilter (SimpleITK)")
    sitk_img = sitk.GetImageFromArray(vtk_array.astype('uint8'))
    sitk_img.SetSpacing(spacing)
    sitk_thinner = sitk.BinaryThinningImageFilter()
    skeleton_sitk = sitk_thinner.Execute(sitk_img)
    print("✓ Thinning SimpleITK terminé")

    # 3) Reconversion SimpleITK→VTK
    skel_np = sitk.GetArrayFromImage(skeleton_sitk)  # z,y,x
    out_vtk = vtk.vtkImageData()
    out_vtk.SetSpacing(spacing)
    out_vtk.SetDimensions(skel_np.shape[::-1])     # x,y,z
    out_vtk.SetOrigin(itk_image.GetOrigin())

    flat = skel_np.ravel()
    vtk_skel_arr = numpy_support.numpy_to_vtk(num_array=flat, deep=1,
                                              array_type=vtk.VTK_UNSIGNED_CHAR)
    out_vtk.GetPointData().SetScalars(vtk_skel_arr)

    # ---------- Skeleton -> PolyData via VTK ----------
    contour = vtk.vtkContourFilter()
    contour.SetInputData(out_vtk)
    contour.SetValue(0, 1)  # isosurface à 1
    contour.Update()
    centerlines = contour.GetOutput()

    # ---------- Écriture centre-lines ----------
    writer = vtk.vtkXMLPolyDataWriter()
    writer.SetFileName(args.output)
    writer.SetInputData(centerlines)
    writer.Write()

    print(f"✓ Centre-lines extraites : {centerlines.GetNumberOfLines()} branches")
    print(f"→ Fichier enregistré : {args.output}")

except Exception as e:
    import traceback
    print("Erreur capturée :", e)
    traceback.print_exc()
