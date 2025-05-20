import vtk
import numpy as np
from vtk.util.numpy_support import vtk_to_numpy
import os
import math
from scipy.spatial.distance import cdist

def load_vtp(file_path):
    """Load a VTP file and return the polydata."""
    reader = vtk.vtkXMLPolyDataReader()
    reader.SetFileName(file_path)
    reader.Update()
    return reader.GetOutput()

def load_stl(file_path):
    """Load an STL file and return the polydata."""
    reader = vtk.vtkSTLReader()
    reader.SetFileName(file_path)
    reader.Update()
    return reader.GetOutput()

def extract_centerlines(polydata):
    """Extract centerline points and vessel radius data from polydata."""
    points = polydata.GetPoints()
    n_points = points.GetNumberOfPoints()
    
    # Extract coordinates
    coords = np.zeros((n_points, 3))
    for i in range(n_points):
        coords[i] = points.GetPoint(i)
        
    # Extract radius data
    radius_array = polydata.GetPointData().GetArray("MaximumInscribedSphereRadius")
    if radius_array:
        radius = vtk_to_numpy(radius_array)
    else:
        radius = np.ones(n_points)
        print("Warning: Radius data not found, using default value of 1")
    
    return coords, radius

def identify_branches(polydata):
    """Identify different branches in the centerlines."""
    lines = polydata.GetLines()
    lines.InitTraversal()
    branches = []
    
    for i in range(polydata.GetNumberOfLines()):
        ids = vtk.vtkIdList()
        lines.GetNextCell(ids)
        branch_points = [ids.GetId(j) for j in range(ids.GetNumberOfIds())]
        branches.append(branch_points)
    
    print(f"Found {len(branches)} branches in the centerlines")
    for i, branch in enumerate(branches):
        print(f"  Branch {i}: {len(branch)} points")
    
    return branches

def find_branch_intersections(branches, coords, threshold=5.0):
    """Find intersection points between branches."""
    intersections = []
    
    if len(branches) < 2:
        print("Not enough branches to find intersections")
        return intersections
    
    # Check all pairs of branches
    for i in range(len(branches)):
        for j in range(i+1, len(branches)):
            branch_i = branches[i]
            branch_j = branches[j]
            
            # Check if branches share any points
            common_points = set(branch_i).intersection(set(branch_j))
            
            if common_points:
                # Branches share points - actual intersection
                for point_id in common_points:
                    intersections.append({
                        'point_id': point_id,
                        'coordinates': coords[point_id],
                        'branches': [i, j],
                        'type': 'direct'
                    })
                    print(f"Found direct intersection at point {point_id} between branches {i} and {j}")
            else:
                # Look for close points
                points_i = coords[branch_i]
                points_j = coords[branch_j]
                
                distances = cdist(points_i, points_j)
                min_dist = np.min(distances)
                
                if min_dist < threshold:
                    idx_i, idx_j = np.unravel_index(np.argmin(distances), distances.shape)
                    point_i = branch_i[idx_i]
                    point_j = branch_j[idx_j]
                    midpoint = (coords[point_i] + coords[point_j]) / 2
                    
                    intersections.append({
                        'point_i': point_i,
                        'point_j': point_j,
                        'coordinates': midpoint,
                        'branches': [i, j],
                        'type': 'proximity',
                        'distance': min_dist,
                        'idx_i': idx_i,
                        'idx_j': idx_j
                    })
                    print(f"Found proximity intersection between branches {i} and {j}, distance: {min_dist:.2f}")
    
    return intersections

def calculate_branch_direction(coords, branch, junction_idx, window_size=5, reverse=False):
    """Calculate the direction vector of a branch at a specific index."""
    n_points = len(branch)
    
    if reverse:
        branch_points = list(reversed(branch))
        junction_idx = n_points - 1 - junction_idx
    else:
        branch_points = branch
    
    # Determine range for calculating direction
    if junction_idx < window_size:
        # Near start of branch
        segment = branch_points[:min(2*window_size, n_points)]
    else:
        # Use points before and after the junction
        start_idx = max(0, junction_idx - window_size)
        end_idx = min(n_points, junction_idx + window_size + 1)
        segment = branch_points[start_idx:end_idx]
    
    if len(segment) < 2:
        return np.array([0, 0, 0])
    
    # Get coordinates for the segment
    points = coords[segment]
    
    # Calculate direction using linear regression
    indices = np.arange(len(points))
    direction = np.zeros(3)
    
    for dim in range(3):
        if len(points) > 2:
            # Use linear regression for more accurate direction
            coeffs = np.polyfit(indices, points[:, dim], 1)
            direction[dim] = coeffs[0]  # Slope gives direction
        else:
            # For only two points, use direct vector
            direction[dim] = points[-1, dim] - points[0, dim]
    
    # Normalize direction vector
    norm = np.linalg.norm(direction)
    if norm > 0:
        direction = direction / norm
    
    return direction

def calculate_bifurcation_angle(coords, branches, intersection):
    """Calculate bifurcation angle between branches at an intersection point."""
    # Identify the parent and daughter branches
    # In bifurcations, we typically have one parent vessel splitting into two daughter vessels
    branch_i_idx = intersection['branches'][0]
    branch_j_idx = intersection['branches'][1]
    
    branch_i = branches[branch_i_idx]
    branch_j = branches[branch_j_idx]
    
    # For a direct intersection
    if intersection['type'] == 'direct':
        junction_point_id = intersection['point_id']
        
        # Find index of junction point in each branch
        idx_i = branch_i.index(junction_point_id)
        idx_j = branch_j.index(junction_point_id)
        
        # Calculate directions of both branches at junction
        # For parent branch we want the direction leading to the junction
        dir_i = calculate_branch_direction(coords, branch_i, idx_i)
        # For child branch we want the direction leading away from the junction
        dir_j = calculate_branch_direction(coords, branch_j, idx_j)
        
    else:  # proximity intersection
        idx_i = intersection['idx_i']
        idx_j = intersection['idx_j']
        
        dir_i = calculate_branch_direction(coords, branch_i, idx_i)
        dir_j = calculate_branch_direction(coords, branch_j, idx_j)
    
    # Calculate angle between the two direction vectors
    dot_product = np.dot(dir_i, dir_j)
    dot_product = max(min(dot_product, 1.0), -1.0)  # Ensure it's in the range [-1, 1]
    angle_rad = np.arccos(dot_product)
    angle_deg = np.degrees(angle_rad)
    
    # For bifurcations, the angle is typically reported as the angle between daughter vessels
    bifurcation_angle = angle_deg
    
    return {
        'branches': intersection['branches'],
        'coordinates': intersection['coordinates'],
        'angle_degrees': bifurcation_angle,
        'direction_i': dir_i,
        'direction_j': dir_j
    }

def draw_bifurcation_angles(stl_polydata, centerlines_coords, branches, intersections, angles):
    """Visualize the bifurcation angles on the 3D model."""
    renderer = vtk.vtkRenderer()
    render_window = vtk.vtkRenderWindow()
    render_window.AddRenderer(renderer)
    render_window.SetSize(800, 600)
    render_window.SetWindowName("Bifurcation Angles Visualization")
    
    # Set up interactive rendering
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)
    
    # Add STL model with transparency
    stl_mapper = vtk.vtkPolyDataMapper()
    stl_mapper.SetInputData(stl_polydata)
    
    stl_actor = vtk.vtkActor()
    stl_actor.SetMapper(stl_mapper)
    stl_actor.GetProperty().SetOpacity(0.4)
    stl_actor.GetProperty().SetColor(0.8, 0.8, 0.9)  # Light blue
    
    renderer.AddActor(stl_actor)
    
    # Add centerlines
    colors = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1)]
    
    for i, branch in enumerate(branches):
        points = vtk.vtkPoints()
        lines = vtk.vtkCellArray()
        
        for j, point_id in enumerate(branch):
            points.InsertNextPoint(centerlines_coords[point_id])
            if j > 0:
                line = vtk.vtkLine()
                line.GetPointIds().SetId(0, j-1)
                line.GetPointIds().SetId(1, j)
                lines.InsertNextCell(line)
        
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetLines(lines)
        
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)
        
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(colors[i % len(colors)])
        actor.GetProperty().SetLineWidth(2.0)
        
        renderer.AddActor(actor)
    
    # Add spheres at intersection points with bifurcation angles
    for i, angle_info in enumerate(angles):
        sphere = vtk.vtkSphereSource()
        sphere.SetCenter(angle_info['coordinates'])
        sphere.SetRadius(2.0)
        sphere.SetPhiResolution(16)
        sphere.SetThetaResolution(16)
        
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(sphere.GetOutputPort())
        
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(1.0, 1.0, 0.0)  # Yellow
        
        renderer.AddActor(actor)
        
        # Add text label with angle value
        text = vtk.vtkVectorText()
        text.SetText(f"{angle_info['angle_degrees']:.1f}°")
        
        text_mapper = vtk.vtkPolyDataMapper()
        text_mapper.SetInputConnection(text.GetOutputPort())
        
        text_actor = vtk.vtkFollower()
        text_actor.SetMapper(text_mapper)
        text_actor.SetScale(3.0, 3.0, 3.0)
        text_actor.SetPosition(angle_info['coordinates'][0] + 3, 
                             angle_info['coordinates'][1] + 3, 
                             angle_info['coordinates'][2] + 3)
        text_actor.GetProperty().SetColor(1.0, 1.0, 1.0)  # White
        
        renderer.AddActor(text_actor)
        
        # Add arrows to show branch directions
        for j, direction in enumerate([angle_info['direction_i'], angle_info['direction_j']]):
            arrow = vtk.vtkArrowSource()
            arrow.SetTipResolution(16)
            arrow.SetShaftResolution(16)
            
            # Create transform to position and orient arrow
            transform = vtk.vtkTransform()
            transform.Translate(angle_info['coordinates'])
            
            # Rotation to align arrow with direction
            if np.linalg.norm(direction) > 0:
                axis = np.cross([0, 0, 1], direction)
                angle = np.degrees(np.arccos(np.dot([0, 0, 1], direction)))
                if np.linalg.norm(axis) > 0:
                    transform.RotateWXYZ(angle, axis[0], axis[1], axis[2])
            
            transform.Scale(5.0, 5.0, 5.0)  # Scale for visibility
            
            transform_filter = vtk.vtkTransformPolyDataFilter()
            transform_filter.SetInputConnection(arrow.GetOutputPort())
            transform_filter.SetTransform(transform)
            transform_filter.Update()
            
            arrow_mapper = vtk.vtkPolyDataMapper()
            arrow_mapper.SetInputConnection(transform_filter.GetOutputPort())
            
            arrow_actor = vtk.vtkActor()
            arrow_actor.SetMapper(arrow_mapper)
            arrow_actor.GetProperty().SetColor(colors[angle_info['branches'][j] % len(colors)])
            
            renderer.AddActor(arrow_actor)
    
    # Set camera
    renderer.ResetCamera()
    renderer.SetBackground(0.1, 0.1, 0.2)  # Dark blue background
    
    # Initialize follower cameras
    camera = renderer.GetActiveCamera()
    for actor in renderer.GetActors():
        if isinstance(actor, vtk.vtkFollower):
            actor.SetCamera(camera)
    
    # Start the interaction
    interactor.Initialize()
    render_window.Render()
    interactor.Start()
    
    return render_window, interactor

def main():
    # File paths
    vtp_file = r"c:\Users\mathg\Documents\Projets\MedProject\3D-Vascular-Reconstruction\output\output_final_centerlines.vtp"
    stl_file = r"c:\Users\mathg\Documents\Projets\MedProject\3D-Vascular-Reconstruction\output\output_final.stl"
    output_dir = r"c:\Users\mathg\Documents\Projets\MedProject\3D-Vascular-Reconstruction\output"
    
    # Load centerlines data
    print(f"Loading centerlines from: {vtp_file}")
    centerlines_polydata = load_vtp(vtp_file)
    print(f"Loaded centerlines with {centerlines_polydata.GetNumberOfPoints()} points and {centerlines_polydata.GetNumberOfLines()} lines")
    
    # Load STL model
    print(f"Loading STL model from: {stl_file}")
    stl_polydata = load_stl(stl_file)
    print(f"Loaded STL model with {stl_polydata.GetNumberOfPoints()} points")
    
    # Extract centerlines
    coords, radius = extract_centerlines(centerlines_polydata)
    
    # Identify branches
    branches = identify_branches(centerlines_polydata)
    
    # Find branch intersections
    intersections = find_branch_intersections(branches, coords)
    
    if not intersections:
        print("No intersections found. Cannot calculate bifurcation angles.")
        # Save a note to the output file
        with open(os.path.join(output_dir, 'bifurcation_angles.txt'), 'w') as f:
            f.write("Bifurcation Angle Analysis:\n\n")
            f.write("No intersections detected between the centerlines.\n\n")
            f.write("This could be due to:\n")
            f.write("1. The vessel model doesn't have any bifurcations\n")
            f.write("2. The centerlines extraction didn't properly capture the bifurcations\n")
            f.write("3. The threshold distance for detecting proximity intersections might need adjustment\n\n")
            
            f.write("Branch Information:\n")
            for i, branch in enumerate(branches):
                f.write(f"  Branch {i}: {len(branch)} points\n")
                start_point = coords[branch[0]]
                end_point = coords[branch[-1]]
                f.write(f"    Start: X={start_point[0]:.2f}, Y={start_point[1]:.2f}, Z={start_point[2]:.2f}\n")
                f.write(f"    End: X={end_point[0]:.2f}, Y={end_point[1]:.2f}, Z={end_point[2]:.2f}\n\n")
        return
    
    # Calculate bifurcation angles
    bifurcation_angles = []
    
    for intersection in intersections:
        angle_info = calculate_bifurcation_angle(coords, branches, intersection)
        bifurcation_angles.append(angle_info)
        branch_i = angle_info['branches'][0]
        branch_j = angle_info['branches'][1]
        print(f"Bifurcation angle between branches {branch_i} and {branch_j}: {angle_info['angle_degrees']:.2f} degrees")
    
    # Save results to file
    with open(os.path.join(output_dir, 'bifurcation_angles.txt'), 'w') as f:
        f.write("Bifurcation Angle Analysis:\n\n")
        
        for i, angle_info in enumerate(bifurcation_angles):
            f.write(f"Bifurcation {i}:\n")
            f.write(f"  Between branches {angle_info['branches'][0]} and {angle_info['branches'][1]}\n")
            f.write(f"  Angle: {angle_info['angle_degrees']:.2f} degrees\n")
            f.write(f"  Location: X={angle_info['coordinates'][0]:.2f}, Y={angle_info['coordinates'][1]:.2f}, Z={angle_info['coordinates'][2]:.2f}\n\n")
        
        f.write("Branch Information:\n")
        for i, branch in enumerate(branches):
            f.write(f"  Branch {i}: {len(branch)} points\n")
            start_point = coords[branch[0]]
            end_point = coords[branch[-1]]
            f.write(f"    Start: X={start_point[0]:.2f}, Y={start_point[1]:.2f}, Z={start_point[2]:.2f}\n")
            f.write(f"    End: X={end_point[0]:.2f}, Y={end_point[1]:.2f}, Z={end_point[2]:.2f}\n\n")
    
    print(f"Results saved to {os.path.join(output_dir, 'bifurcation_angles.txt')}")
    
    # Visualize the results
    print("Visualizing bifurcation angles...")
    draw_bifurcation_angles(stl_polydata, coords, branches, intersections, bifurcation_angles)
    
if __name__ == "__main__":
    main()
