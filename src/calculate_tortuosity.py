# c:\Users\mathg\Documents\Projets\MedProject\3D-Vascular-Reconstruction\tortuosity_calculator.py

import vtk
import numpy as np
import os
from vtk.util.numpy_support import vtk_to_numpy
from pathlib import Path

def read_vtp_file(file_path):
    """Read VTP file and return the polydata"""
    reader = vtk.vtkXMLPolyDataReader()
    reader.SetFileName(file_path)
    reader.Update()
    return reader.GetOutput()

def extract_points_from_polydata(polydata):
    """Extract points from polydata as numpy array"""
    points = polydata.GetPoints()
    if points is None:
        return None
    
    num_points = points.GetNumberOfPoints()
    points_array = np.zeros((num_points, 3))
    
    for i in range(num_points):
        points_array[i] = points.GetPoint(i)
    
    return points_array

def calculate_path_length(points):
    """Calculate the total path length of a centerline"""
    if len(points) < 2:
        return 0
    
    path_length = 0
    for i in range(len(points) - 1):
        path_length += np.linalg.norm(points[i+1] - points[i])
    
    return path_length

def calculate_straight_line_distance(points):
    """Calculate the straight-line distance between the endpoints"""
    if len(points) < 2:
        return 0
    
    return np.linalg.norm(points[-1] - points[0])

def calculate_tortuosity(points):
    """Calculate tortuosity (path length / straight-line distance)"""
    path_length = calculate_path_length(points)
    straight_line_distance = calculate_straight_line_distance(points)
    
    if straight_line_distance == 0:
        return 0
    
    return path_length / straight_line_distance

def get_centerlines_from_polydata(polydata):
    """Extract centerlines from polydata by separating into distinct polylines"""
    # For VTP files with multiple centerlines, we need to identify separate polylines
    # This is a simplified approach assuming the connectivity info is available
    
    # For simplicity, we're assuming all points form a single centerline in this case
    points = extract_points_from_polydata(polydata)
    return [points]

def visualize_centerlines_on_stl(stl_file, centerlines_polydata):
    """Display STL surface and centerlines together in a VTK render window."""
    # Read STL
    stl_reader = vtk.vtkSTLReader()
    stl_reader.SetFileName(stl_file)
    stl_reader.Update()
    stl_polydata = stl_reader.GetOutput()

    # STL mapper/actor
    stl_mapper = vtk.vtkPolyDataMapper()
    stl_mapper.SetInputData(stl_polydata)
    stl_actor = vtk.vtkActor()
    stl_actor.SetMapper(stl_mapper)
    stl_actor.GetProperty().SetOpacity(0.3)
    stl_actor.GetProperty().SetColor(0.8, 0.8, 0.8)

    # Centerlines mapper/actor
    centerline_mapper = vtk.vtkPolyDataMapper()
    centerline_mapper.SetInputData(centerlines_polydata)
    centerline_actor = vtk.vtkActor()
    centerline_actor.SetMapper(centerline_mapper)
    centerline_actor.GetProperty().SetColor(1, 0, 0)
    centerline_actor.GetProperty().SetLineWidth(4)

    # Renderer
    renderer = vtk.vtkRenderer()
    renderer.AddActor(stl_actor)
    renderer.AddActor(centerline_actor)
    renderer.SetBackground(0.1, 0.1, 0.15)

    # Render window
    render_window = vtk.vtkRenderWindow()
    render_window.AddRenderer(renderer)
    render_window.SetSize(900, 700)

    # Interactor
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)

    # Start visualization
    render_window.Render()
    interactor.Start()

def main():
    # File path
    vtp_file = r"output/output_final_centerlines.vtp"
    stl_file = r"output/output_final.stl"  # <-- chemin du STL à ajuster si besoin

    # Check if file exists
    if not os.path.exists(vtp_file):
        print(f"Error: File not found at {vtp_file}")
        return
    
    # Read the VTP file
    polydata = read_vtp_file(vtp_file)
    
    # Get centerlines
    centerlines = get_centerlines_from_polydata(polydata)
    
    # Calculate tortuosity for each centerline
    print("Centerline Tortuosity Analysis:")
    print("-" * 30)
    
    total_tortuosity = 0
    valid_centerlines = 0
    
    for i, centerline in enumerate(centerlines):
        if centerline is not None and len(centerline) > 1:
            path_length = calculate_path_length(centerline)
            straight_line_distance = calculate_straight_line_distance(centerline)
            tortuosity = calculate_tortuosity(centerline)
            
            print(f"Centerline {i+1}:")
            print(f"  Number of points: {len(centerline)}")
            print(f"  Path length: {path_length:.2f} units")
            print(f"  Straight-line distance: {straight_line_distance:.2f} units")
            print(f"  Tortuosity index: {tortuosity:.4f}")
            print("-" * 30)
            
            total_tortuosity += tortuosity
            valid_centerlines += 1
    
    if valid_centerlines > 0:
        print(f"Average tortuosity: {total_tortuosity / valid_centerlines:.4f}")
    
    # Visualisation interactive VTK
    if os.path.exists(stl_file):
        print("Affichage interactif : STL + centerlines")
        visualize_centerlines_on_stl(stl_file, polydata)
    else:
        print(f"STL file not found: {stl_file}")

if __name__ == "__main__":
    main()