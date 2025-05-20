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

def find_closest_points(coords, branches, distance_threshold=5.0):
    """Find potential junction points by identifying closest points between branches."""
    junction_points = []
    
    if len(branches) < 2:
        print("Not enough branches to find junctions.")
        return junction_points
    
    for i in range(len(branches)):
        for j in range(i+1, len(branches)):
            branch1 = branches[i]
            branch2 = branches[j]
            
            points1 = coords[branch1]
            points2 = coords[branch2]
            
            # Calculate distances between all points in the two branches
            distances = cdist(points1, points2)
            
            # Find the minimum distance and corresponding indices
            min_dist = np.min(distances)
            idx1, idx2 = np.unravel_index(np.argmin(distances), distances.shape)
            
            if min_dist < distance_threshold:
                point_id1 = branch1[idx1]
                point_id2 = branch2[idx2]
                junction_points.append({
                    'branches': [i, j],
                    'points': [point_id1, point_id2],
                    'distance': min_dist,
                    'coords1': coords[point_id1],
                    'coords2': coords[point_id2],
                    'branch1_idx': idx1,
                    'branch2_idx': idx2
                })
                print(f"Found potential junction between branch {i} and {j} with distance {min_dist:.2f}")
                
    return junction_points

def calculate_branch_vector(coords, branch_points, index, window_size=5):
    """Calculate the tangent vector of a branch at a specific index."""
    n_points = len(branch_points)
    
    # Determine range for calculation
    start = max(0, index - window_size)
    end = min(n_points, index + window_size + 1)
    
    if end - start < 2:
        return np.array([0, 0, 0])
    
    points = [coords[branch_points[i]] for i in range(start, end)]
    points = np.array(points)
    
    # For short segments, use direct vector
    if len(points) == 2:
        vector = points[1] - points[0]
    else:
        # Fit a line using linear regression for each coordinate
        indices = np.arange(len(points))
        
        # Calculate the slope for each dimension (x, y, z)
        vector = np.zeros(3)
        for dim in range(3):
            coef = np.polyfit(indices, points[:, dim], 1)
            vector[dim] = coef[0]  # The slope is the direction
    
    # Normalize the vector
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
        
    return vector

def calculate_take_off_angle(coords, branches, junction_point):
    """Calculate the take-off angle between two branches at a junction point."""
    branch1_idx = junction_point['branches'][0]
    branch2_idx = junction_point['branches'][1]
    
    branch1 = branches[branch1_idx]
    branch2 = branches[branch2_idx]
    
    idx1_in_branch = junction_point['branch1_idx']
    idx2_in_branch = junction_point['branch2_idx']
    
    # Calculate the direction vectors at the junction points
    vec1 = calculate_branch_vector(coords, branch1, idx1_in_branch)
    vec2 = calculate_branch_vector(coords, branch2, idx2_in_branch)
    
    # Calculate the angle between the two vectors
    dot_product = np.dot(vec1, vec2)
    dot_product = max(min(dot_product, 1.0), -1.0)  # Ensure it's in the range [-1, 1]
    angle_rad = np.arccos(dot_product)
    angle_deg = np.degrees(angle_rad)
    
    # The take-off angle is often defined as the smaller angle between vectors
    take_off_angle = min(angle_deg, 180 - angle_deg)
    
    return {
        'branch1': branch1_idx,
        'branch2': branch2_idx,
        'angle_degrees': take_off_angle,
        'raw_angle': angle_deg,
        'vector1': vec1,
        'vector2': vec2,
        'junction_point': {
            'coords1': junction_point['coords1'],
            'coords2': junction_point['coords2'],
            'midpoint': (junction_point['coords1'] + junction_point['coords2']) / 2
        }
    }

def analyze_branch_endpoints(coords, branches):
    """Analyze the endpoints of branches to detect potential junctions."""
    if len(branches) < 2:
        print("Not enough branches to analyze endpoints.")
        return []
    
    potential_junctions = []
    
    # Extract endpoints of each branch
    endpoints = []
    for i, branch in enumerate(branches):
        endpoints.append({
            'branch_idx': i,
            'start': {'point_idx': branch[0], 'coords': coords[branch[0]]},
            'end': {'point_idx': branch[-1], 'coords': coords[branch[-1]]}
        })
    
    # Check for proximity between endpoints of different branches
    threshold = 10.0  # Distance threshold for endpoint proximity
    for i in range(len(endpoints)):
        for j in range(i+1, len(endpoints)):
            # Check start-start distance
            dist_ss = np.linalg.norm(endpoints[i]['start']['coords'] - endpoints[j]['start']['coords'])
            
            # Check start-end distance
            dist_se = np.linalg.norm(endpoints[i]['start']['coords'] - endpoints[j]['end']['coords'])
            
            # Check end-start distance
            dist_es = np.linalg.norm(endpoints[i]['end']['coords'] - endpoints[j]['start']['coords'])
            
            # Check end-end distance
            dist_ee = np.linalg.norm(endpoints[i]['end']['coords'] - endpoints[j]['end']['coords'])
            
            # Find the minimum distance and corresponding endpoint combination
            min_dist = min(dist_ss, dist_se, dist_es, dist_ee)
            
            if min_dist < threshold:
                if dist_ss == min_dist:
                    point1 = endpoints[i]['start']['point_idx']
                    point2 = endpoints[j]['start']['point_idx']
                    loc1 = 'start'
                    loc2 = 'start'
                elif dist_se == min_dist:
                    point1 = endpoints[i]['start']['point_idx']
                    point2 = endpoints[j]['end']['point_idx']
                    loc1 = 'start'
                    loc2 = 'end'
                elif dist_es == min_dist:
                    point1 = endpoints[i]['end']['point_idx']
                    point2 = endpoints[j]['start']['point_idx']
                    loc1 = 'end'
                    loc2 = 'start'
                else:  # dist_ee == min_dist
                    point1 = endpoints[i]['end']['point_idx']
                    point2 = endpoints[j]['end']['point_idx']
                    loc1 = 'end'
                    loc2 = 'end'
                
                potential_junctions.append({
                    'branches': [i, j],
                    'points': [point1, point2],
                    'distance': min_dist,
                    'coords1': coords[point1],
                    'coords2': coords[point2],
                    'locations': [loc1, loc2]
                })
                
                print(f"Found potential junction between branch {i} ({loc1}) and {j} ({loc2}) with distance {min_dist:.2f}")
    
    return potential_junctions

def create_junction_visualization(stl_polydata, centerlines_coords, branches, junction_points, take_off_angles):
    """Create a visualization of the vessel model with junction points and take-off angles."""
    
    # Create a renderer and render window
    renderer = vtk.vtkRenderer()
    render_window = vtk.vtkRenderWindow()
    render_window.AddRenderer(renderer)
    render_window.SetSize(800, 600)
    render_window.SetWindowName("Vessel Model with Take-Off Angles")
    
    # Create an interactor
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)
    
    # Set up the STL model visualization
    stl_mapper = vtk.vtkPolyDataMapper()
    stl_mapper.SetInputData(stl_polydata)
    
    stl_actor = vtk.vtkActor()
    stl_actor.SetMapper(stl_mapper)
    stl_actor.GetProperty().SetOpacity(0.5)
    stl_actor.GetProperty().SetColor(0.8, 0.8, 0.9)  # Light blue color
    
    renderer.AddActor(stl_actor)
    
    # Create lines for the centerlines
    colors = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1)]  # RGB colors
    
    for i, branch in enumerate(branches):
        branch_points = vtk.vtkPoints()
        branch_lines = vtk.vtkCellArray()
        
        # Add points for this branch
        points_list = centerlines_coords[branch]
        
        for j, point in enumerate(points_list):
            branch_points.InsertNextPoint(point)
            if j > 0:
                line = vtk.vtkLine()
                line.GetPointIds().SetId(0, j-1)
                line.GetPointIds().SetId(1, j)
                branch_lines.InsertNextCell(line)
        
        # Create a polydata object
        branch_polydata = vtk.vtkPolyData()
        branch_polydata.SetPoints(branch_points)
        branch_polydata.SetLines(branch_lines)
        
        # Create a mapper and actor
        branch_mapper = vtk.vtkPolyDataMapper()
        branch_mapper.SetInputData(branch_polydata)
        
        branch_actor = vtk.vtkActor()
        branch_actor.SetMapper(branch_mapper)
        
        # Set color for this branch
        color = colors[i % len(colors)]
        branch_actor.GetProperty().SetColor(color)
        branch_actor.GetProperty().SetLineWidth(3.0)
        
        renderer.AddActor(branch_actor)
    
    # Create spheres for junction points and add text labels for angles
    for i, angle_info in enumerate(take_off_angles):
        midpoint = angle_info['junction_point']['midpoint']
        
        # Create a sphere for the junction point
        sphere = vtk.vtkSphereSource()
        sphere.SetCenter(midpoint)
        sphere.SetRadius(1.5)  # Adjust size as needed
        sphere.SetPhiResolution(15)
        sphere.SetThetaResolution(15)
        
        sphere_mapper = vtk.vtkPolyDataMapper()
        sphere_mapper.SetInputConnection(sphere.GetOutputPort())
        
        sphere_actor = vtk.vtkActor()
        sphere_actor.SetMapper(sphere_mapper)
        sphere_actor.GetProperty().SetColor(1.0, 1.0, 0.0)  # Yellow
        
        renderer.AddActor(sphere_actor)
        
        # Add a text label with the angle value
        text_source = vtk.vtkTextSource()
        text_source.SetText(f"{angle_info['angle_degrees']:.1f}°")
        text_source.SetBackgroundColor(0.0, 0.0, 0.0)
        text_source.SetForegroundColor(1.0, 1.0, 1.0)
        text_source.BackingOff()
        text_source.Update()
        
        text_mapper = vtk.vtkPolyDataMapper()
        text_mapper.SetInputConnection(text_source.GetOutputPort())
        
        text_actor = vtk.vtkActor()
        text_actor.SetMapper(text_mapper)
        text_actor.SetPosition(midpoint[0] + 2, midpoint[1] + 2, midpoint[2] + 2)
        text_actor.SetScale(2.0)
        
        renderer.AddActor(text_actor)
        
        # Create arrows to show the branch directions
        for j, vector in enumerate([angle_info['vector1'], angle_info['vector2']]):
            arrow_source = vtk.vtkArrowSource()
            arrow_source.SetTipResolution(16)
            arrow_source.SetShaftResolution(16)
            
            # Create a transform for correct positioning and orientation
            transform = vtk.vtkTransform()
            transform.Translate(midpoint)
            
            # Calculate rotation to align arrow with the vector
            vector_norm = np.linalg.norm(vector)
            if vector_norm > 0:
                # Vectors for the arrow
                arrow_vector = [0, 0, 1]  # VTK arrow points in z direction by default
                
                # Calculate the cross product between the arrow's default direction and our desired direction
                cross = np.cross(arrow_vector, vector)
                cross_norm = np.linalg.norm(cross)
                
                if cross_norm > 0:
                    # Calculate the angle between the default direction and our desired direction
                    angle = np.degrees(np.arccos(np.dot(arrow_vector, vector)))
                    
                    # Set the rotation
                    transform.RotateWXYZ(angle, cross[0], cross[1], cross[2])
            
            # Apply scaling to make the arrow an appropriate size
            transform.Scale(5, 5, 5)  # Scale arrow to make it visible
            
            # Create a transform filter and apply it to the arrow
            transform_filter = vtk.vtkTransformPolyDataFilter()
            transform_filter.SetInputConnection(arrow_source.GetOutputPort())
            transform_filter.SetTransform(transform)
            transform_filter.Update()
            
            # Create mapper and actor for the arrow
            arrow_mapper = vtk.vtkPolyDataMapper()
            arrow_mapper.SetInputConnection(transform_filter.GetOutputPort())
            
            arrow_actor = vtk.vtkActor()
            arrow_actor.SetMapper(arrow_mapper)
            
            # Use same color as the branch
            color = colors[angle_info['branch1' if j == 0 else 'branch2'] % len(colors)]
            arrow_actor.GetProperty().SetColor(color)
            
            renderer.AddActor(arrow_actor)
    
    # Set up the background and camera
    renderer.SetBackground(0.1, 0.1, 0.1)  # Dark gray background
    renderer.ResetCamera()
    
    camera = renderer.GetActiveCamera()
    camera.Elevation(30)  # Adjust for better viewing angle
    camera.Azimuth(30)
    renderer.ResetCameraClippingRange()
    
    # Set up an interactor style
    style = vtk.vtkInteractorStyleTrackballCamera()
    interactor.SetInteractorStyle(style)
    
    # Initialize the interactor and start interaction
    interactor.Initialize()
    interactor.Start()
    
    return render_window, interactor

def main():
    # Paths to the input files
    vtp_file = r"c:\Users\mathg\Documents\Projets\MedProject\3D-Vascular-Reconstruction\output\output_final_centerlines.vtp"
    stl_file = r"c:\Users\mathg\Documents\Projets\MedProject\3D-Vascular-Reconstruction\output\output_final.stl"
    output_dir = r"c:\Users\mathg\Documents\Projets\MedProject\3D-Vascular-Reconstruction\output"
    
    print(f"Processing centerlines file: {vtp_file}")
    print(f"Using STL model file: {stl_file}")
    
    # Load VTP file (centerlines)
    centerlines_polydata = load_vtp(vtp_file)
    print(f"Loaded centerlines with {centerlines_polydata.GetNumberOfPoints()} points and {centerlines_polydata.GetNumberOfLines()} lines")
    
    # Load STL file (vessel model)
    stl_polydata = load_stl(stl_file)
    print(f"Loaded STL model with {stl_polydata.GetNumberOfPoints()} points")
    
    # Extract centerline data
    coords, radius = extract_centerlines(centerlines_polydata)
    print(f"Extracted centerlines with {len(coords)} points")
    
    # Identify branches
    branches = identify_branches(centerlines_polydata)
    
    # Find junction points between branches by closest points
    junction_points = find_closest_points(coords, branches)
    
    # If no junction points found by closest points, try analyzing endpoints
    if not junction_points:
        print("No junctions found by closest points method. Analyzing branch endpoints...")
        junction_points = analyze_branch_endpoints(coords, branches)
    
    # Initialize results list
    take_off_angles = []
    
    # Calculate take-off angles if junction points were found
    if junction_points:
        for i, junction in enumerate(junction_points):
            angle_info = calculate_take_off_angle(coords, branches, junction)
            take_off_angles.append(angle_info)
            
            print(f"Take-off angle at junction {i}: {angle_info['angle_degrees']:.2f} degrees")
            print(f"  Between branch {angle_info['branch1']} and {angle_info['branch2']}")
    else:
        print("Warning: No junction points found. Cannot calculate take-off angles.")
    
    # Save results to a text file
    results_file = os.path.join(output_dir, 'takeoff_angles.txt')
    with open(results_file, 'w') as f:
        f.write("Take-Off Angles Analysis:\n\n")
        
        if take_off_angles:
            f.write("Found junctions:\n")
            for i, angle_info in enumerate(take_off_angles):
                f.write(f"Junction {i}:\n")
                f.write(f"  Between branch {angle_info['branch1']} and branch {angle_info['branch2']}\n")
                f.write(f"  Take-off angle: {angle_info['angle_degrees']:.2f} degrees\n")
                f.write(f"  Location: X={angle_info['junction_point']['midpoint'][0]:.2f}, Y={angle_info['junction_point']['midpoint'][1]:.2f}, Z={angle_info['junction_point']['midpoint'][2]:.2f}\n\n")
        else:
            f.write("No junctions detected between the centerlines.\n\n")
        
        # Add information about branches without the extensive graphs/analysis
        f.write("Branch Information:\n")
        for i, branch in enumerate(branches):
            f.write(f"  Branch {i}: {len(branch)} points\n")
            start_point = coords[branch[0]]
            end_point = coords[branch[-1]]
            f.write(f"    Start: X={start_point[0]:.2f}, Y={start_point[1]:.2f}, Z={start_point[2]:.2f}\n")
            f.write(f"    End: X={end_point[0]:.2f}, Y={end_point[1]:.2f}, Z={end_point[2]:.2f}\n\n")
    
    print(f"Results saved to {results_file}")
    
    # Create 3D visualization of the model with junction points and angles
    if take_off_angles:
        print("Creating 3D visualization of the model with junction points and take-off angles...")
        create_junction_visualization(stl_polydata, coords, branches, junction_points, take_off_angles)
    else:
        print("No take-off angles calculated. Skipping 3D visualization.")

if __name__ == "__main__":
    main()
