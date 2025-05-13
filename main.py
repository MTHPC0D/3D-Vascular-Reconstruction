import os
import argparse
import SimpleITK as sitk
import numpy as np
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk
import open3d as o3d
import trimesh
import matplotlib.pyplot as plt
import sys
from scipy.spatial.transform import Rotation as R

def sitk_to_vtk_image(sitk_img):
    """Convert SimpleITK image to VTK image"""
    # Get array data from SimpleITK
    arr = sitk.GetArrayFromImage(sitk_img).astype(np.uint8)
    
    # Create a VTK data array object explicitly
    data_vtk = vtk.vtkUnsignedCharArray()
    data_vtk.SetNumberOfComponents(1)
    data_vtk.SetNumberOfTuples(arr.size)
    
    # Flatten the array and copy the data into the VTK array
    flat_arr = arr.ravel()
    for i in range(arr.size):
        data_vtk.SetValue(i, flat_arr[i])
    
    # Setup the image data
    vtk_img = vtk.vtkImageData()
    vtk_img.SetDimensions(arr.shape[2], arr.shape[1], arr.shape[0])
    vtk_img.GetPointData().SetScalars(data_vtk)
    
    # Set spacing and origin
    spacing = sitk_img.GetSpacing()
    origin = sitk_img.GetOrigin()
    vtk_img.SetSpacing(spacing)
    vtk_img.SetOrigin(origin)
    
    return vtk_img

def generate_stl_from_nifti(nii_path, output_stl_path, desired_spacing=[0.5, 0.5, 0.5]):
    """Generate STL mesh from NIFTI segmentation using marching cubes"""
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(output_stl_path)), exist_ok=True)
    
    # Load and resample the image
    img = sitk.ReadImage(nii_path)
    
    resampler = sitk.ResampleImageFilter()
    resampler.SetOutputSpacing(desired_spacing)
    resampler.SetSize([int(sz*spc/dsp) for sz, spc, dsp in zip(img.GetSize(), img.GetSpacing(), desired_spacing)])
    resampler.SetInterpolator(sitk.sitkNearestNeighbor)
    resampler.SetOutputDirection(img.GetDirection())
    resampler.SetOutputOrigin(img.GetOrigin())
    resampled_img = resampler.Execute(img)
    
    # Convert to VTK image
    vtk_image = sitk_to_vtk_image(resampled_img)
    
    # Apply Marching Cubes
    mc = vtk.vtkMarchingCubes()
    mc.SetInputData(vtk_image)
    mc.SetValue(0, 0.5)  # Threshold for binary 0/1
    mc.Update()
    
    # Export STL
    writer = vtk.vtkSTLWriter()
    writer.SetFileName(output_stl_path)
    writer.SetInputData(mc.GetOutput())
    writer.Write()
    
    print(f"✅ STL mesh generated with Marching Cubes: {output_stl_path}")
    return output_stl_path

def compare_meshes(recon_path, gt_path, output_prefix="comparison"):
    """Compare two meshes and calculate metrics"""
    output_color_mesh_path = f"{output_prefix}_error_colored.ply"
    output_error_img = f"{output_prefix}_error.png"
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(output_error_img)), exist_ok=True)
    
    # Load both meshes
    mesh_pred = o3d.io.read_triangle_mesh(recon_path)
    mesh_gt = o3d.io.read_triangle_mesh(gt_path)
    mesh_pred.compute_vertex_normals()
    mesh_gt.compute_vertex_normals()

    # Initial alignment with ICP (optional)
    threshold = 2.0
    trans_init = np.identity(4)
    reg_p2p = o3d.pipelines.registration.registration_icp(
        mesh_pred.sample_points_uniformly(5000),
        mesh_gt.sample_points_uniformly(5000),
        threshold, trans_init,
        o3d.pipelines.registration.TransformationEstimationPointToPoint()
    )
    mesh_pred.transform(reg_p2p.transformation)

    # Sample points
    points_pred = mesh_pred.sample_points_uniformly(100000)
    points_gt = mesh_gt.sample_points_uniformly(100000)

    # Calculate point-to-surface distances
    distances = np.asarray(points_pred.compute_point_cloud_distance(points_gt))

    # Calculate metrics
    print("✅ Comparison completed")
    print(f"→ Mean distance (RMS): {np.mean(distances):.3f} mm")
    print(f"→ Max distance (Approx Hausdorff): {np.max(distances):.3f} mm")

    # Volume and surface (with trimesh)
    tm_pred = trimesh.load_mesh(recon_path)
    tm_gt = trimesh.load_mesh(gt_path)
    print(f"→ Volume ratio (Recon/GT): {tm_pred.volume / tm_gt.volume:.3f}")

    # Dice score (surface approximation)
    dice_threshold = 1.0  # mm, adjust as needed
    A_in_B = np.sum(distances < dice_threshold)
    distances_gt = np.asarray(points_gt.compute_point_cloud_distance(points_pred))
    B_in_A = np.sum(distances_gt < dice_threshold)
    dice = (A_in_B + B_in_A) / (len(points_pred.points) + len(points_gt.points))
    print(f"→ Dice score (surface, threshold {dice_threshold} mm): {dice:.3f}")

    # Color visualization of errors on the reconstructed mesh
    colors = plt.cm.jet((distances - distances.min()) / (distances.max() - distances.min()))[:, :3]
    points_pred.colors = o3d.utility.Vector3dVector(colors)

    # Save PNG visualization
    vis = o3d.visualization.Visualizer()
    vis.create_window(visible=False)
    vis.add_geometry(points_pred)
    vis.poll_events()
    vis.update_renderer()
    vis.capture_screen_image(output_error_img)
    vis.destroy_window()
    print(f"🖼️ PNG image saved: {output_error_img}")

    # Save colored point cloud
    o3d.io.write_point_cloud(output_color_mesh_path, points_pred)
    print(f"🖼️ Colored point cloud saved: {output_color_mesh_path}")
    
    results = {
        "rms_distance": np.mean(distances),
        "hausdorff_distance": np.max(distances),
        "volume_ratio": tm_pred.volume / tm_gt.volume,
        "dice_score": dice
    }
    
    return results

def principal_axes(verts):
    """Calculate principal axes using PCA"""
    cov = np.cov(verts.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    axes = eigvecs[:, order]
    if np.linalg.det(axes) < 0:
        axes[:, -1] *= -1
    return axes

def align_meshes(recon_path, gt_path, output_aligned_path=None):
    """Align reconstruction mesh with ground truth using PCA and ICP"""
    if output_aligned_path is None:
        output_aligned_path = recon_path.replace('.stl', '_aligned.stl')
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(output_aligned_path)), exist_ok=True)
    
    # Load both meshes (trimesh for PCA)
    mesh_recon = trimesh.load_mesh(recon_path)
    mesh_gt = trimesh.load_mesh(gt_path)

    # Center both meshes at origin
    center_recon = mesh_recon.bounding_box.centroid
    center_gt = mesh_gt.bounding_box.centroid
    verts_recon_centered = mesh_recon.vertices - center_recon
    verts_gt_centered = mesh_gt.vertices - center_gt

    # Align principal axes (PCA)
    axes_recon = principal_axes(verts_recon_centered)
    axes_gt = principal_axes(verts_gt_centered)
    rot_matrix = axes_gt @ axes_recon.T  # align recon to GT

    # Apply rotation to centered reconstruction
    verts_recon_rot = verts_recon_centered @ rot_matrix.T

    # Recenter to GT's center
    verts_recon_final = verts_recon_rot + center_gt

    # Save PCA-aligned STL
    mesh_recon_aligned = trimesh.Trimesh(vertices=verts_recon_final, faces=mesh_recon.faces, process=False)
    mesh_recon_aligned.export(output_aligned_path)
    print(f"✅ PCA-aligned mesh saved: {output_aligned_path}")

    # Refine alignment with ICP (Open3D)
    mesh_recon_o3d = o3d.io.read_triangle_mesh(output_aligned_path)
    mesh_gt_o3d = o3d.io.read_triangle_mesh(gt_path)
    mesh_recon_o3d.compute_vertex_normals()
    mesh_gt_o3d.compute_vertex_normals()

    recon_pcd = mesh_recon_o3d.sample_points_uniformly(number_of_points=100000)
    gt_pcd = mesh_gt_o3d.sample_points_uniformly(number_of_points=100000)

    threshold = 5.0
    reg = o3d.pipelines.registration.registration_icp(
        recon_pcd, gt_pcd, threshold,
        estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPoint(),
        criteria=o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=2000)
    )
    mesh_recon_o3d.transform(reg.transformation)
    o3d.io.write_triangle_mesh(output_aligned_path, mesh_recon_o3d)
    print(f"✅ ICP-refined aligned mesh saved: {output_aligned_path}")
    
    return output_aligned_path

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate 3D mesh from NIFTI and optionally compare with ground truth')
    parser.add_argument('--input', '-i', required=True, help='Input NIFTI segmentation file path')
    parser.add_argument('--output', '-o', default='output/reconstruction.stl', help='Output STL file path')
    parser.add_argument('--spacing', '-s', nargs=3, type=float, default=[0.5, 0.5, 0.5], 
                        help='Desired voxel spacing (default: 0.5 0.5 0.5)')
    parser.add_argument('--compare', '-c', action='store_true', 
                        help='Enable comparison with ground truth mesh')
    parser.add_argument('--align', '-a', action='store_true',
                        help='Enable alignment with ground truth before comparison')
    parser.add_argument('--gt', '-g', default=None, 
                        help='Ground truth STL file path (required if --compare or --align is used)')
    parser.add_argument('--output-prefix', '-p', default='output/comparison',
                        help='Prefix for comparison output files')
    
    args = parser.parse_args()
    
    # Validate arguments
    if (args.compare or args.align) and args.gt is None:
        print("Error: Ground truth STL path (--gt) is required when using --compare or --align")
        parser.print_help()
        sys.exit(1)
        
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    
    # Generate STL from NIFTI using marching cubes
    print(f"Generating STL from {args.input}...")
    stl_path = generate_stl_from_nifti(args.input, args.output, args.spacing)
    
    # If alignment is requested, align with ground truth
    aligned_stl_path = stl_path
    if args.align:
        if args.gt is None:
            print("Error: Ground truth STL path (--gt) is required for alignment")
            sys.exit(1)
        print(f"Aligning generated STL with ground truth {args.gt}...")
        aligned_output_path = stl_path.replace('.stl', '_aligned.stl')
        aligned_stl_path = align_meshes(stl_path, args.gt, aligned_output_path)
    
    # If comparison is requested, compare with ground truth
    if args.compare:
        print(f"Comparing {'aligned' if args.align else 'generated'} STL with ground truth {args.gt}...")
        metrics = compare_meshes(aligned_stl_path, args.gt, args.output_prefix)
        
        # Display summary
        print("\n======== COMPARISON SUMMARY ========")
        print(f"Input NIFTI: {args.input}")
        print(f"Generated STL: {stl_path}")
        if args.align:
            print(f"Aligned STL: {aligned_stl_path}")
        print(f"Ground Truth STL: {args.gt}")
        print(f"RMS Distance: {metrics['rms_distance']:.3f} mm")
        print(f"Hausdorff Distance: {metrics['hausdorff_distance']:.3f} mm")
        print(f"Volume Ratio: {metrics['volume_ratio']:.3f}")
        print(f"Dice Score: {metrics['dice_score']:.3f}")
        print("===================================")

if __name__ == "__main__":
    main()
