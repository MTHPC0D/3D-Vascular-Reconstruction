#!/usr/bin/env python

import os
import sys
import argparse
import subprocess
import vtk
import traceback

# Essayons d'importer les modules VMTK directement
try:
    from vmtk import vmtkscripts
    VMTK_AVAILABLE = True
except ImportError:
    VMTK_AVAILABLE = False
    print("AVERTISSEMENT: Impossible d'importer les modules VMTK directement.")
    print("Assurez-vous que VMTK est correctement installé et accessible.")

def run_vmtk_command(command):
    """
    Run a VMTK command using subprocess
    
    Parameters:
    -----------
    command : str
        VMTK command to run
    
    Returns:
    --------
    int
        Return code of the command
    """
    print(f"Running command: {command}")
    
    # Essayer d'exécuter la commande avec le préfixe python -m vmtk
    try:
        result = subprocess.run(f"python -m vmtk {command}", shell=True)
        return result.returncode
    except Exception as e:
        print(f"Erreur lors de l'exécution de la commande: {e}")
        traceback.print_exc()
        return 1

def convert_stl_to_vtp_using_vtk(stl_file, vtp_file=None):
    """
    Convert an STL file to VTP format using VTK directly.
    
    Parameters:
    -----------
    stl_file : str
        Path to the input STL file
    vtp_file : str, optional
        Path to save the VTP file. If None, uses the same name with .vtp extension
    
    Returns:
    --------
    str
        Path to the generated VTP file
    """
    if vtp_file is None:
        vtp_file = os.path.splitext(stl_file)[0] + '.vtp'
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(vtp_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    try:
        # Read STL file
        reader = vtk.vtkSTLReader()
        reader.SetFileName(stl_file)
        reader.Update()
        
        # Write to VTP format
        writer = vtk.vtkXMLPolyDataWriter()
        writer.SetFileName(vtp_file)
        writer.SetInputConnection(reader.GetOutputPort())
        writer.Write()
        
        print(f"Converted STL file to VTP using VTK: {vtp_file}")
        return vtp_file
    except Exception as e:
        print(f"Erreur lors de la conversion STL vers VTP: {e}")
        traceback.print_exc()
        return None

def convert_stl_to_vtp(stl_file, vtp_file=None):
    """
    Convert an STL file to VTP format using VMTK or VTK.
    
    Parameters:
    -----------
    stl_file : str
        Path to the input STL file
    vtp_file : str, optional
        Path to save the VTP file. If None, uses the same name with .vtp extension
    
    Returns:
    --------
    str
        Path to the generated VTP file
    """
    if vtp_file is None:
        vtp_file = os.path.splitext(stl_file)[0] + '.vtp'
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(vtp_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    if VMTK_AVAILABLE:
        try:
            # Utilisation directe de l'API VMTK
            reader = vmtkscripts.vmtkSurfaceReader()
            reader.InputFileName = stl_file
            reader.Execute()
            
            writer = vmtkscripts.vmtkSurfaceWriter()
            writer.Surface = reader.Surface
            writer.OutputFileName = vtp_file
            writer.Execute()
            
            print(f"Converted STL file to VTP using VMTK API: {vtp_file}")
            return vtp_file
        except Exception as e:
            print(f"Erreur lors de l'utilisation de l'API VMTK: {e}")
            print("Essai de conversion avec VTK...")
            return convert_stl_to_vtp_using_vtk(stl_file, vtp_file)
    else:
        # Si VMTK n'est pas disponible, utiliser VTK directement
        return convert_stl_to_vtp_using_vtk(stl_file, vtp_file)

def extract_centerlines_manual(input_file, output_file, endpoints=1, render_results=False):
    """
    Extract centerlines using manual selection of source and target points.
    
    Parameters:
    -----------
    input_file : str
        Path to the input surface model file (typically .vtp format)
    output_file : str
        Path to save the extracted centerlines
    endpoints : int
        Whether to append the segments from sources and targets to their poles (1) or not (0)
    render_results : bool
        Whether to render the results after extraction
    """
    if VMTK_AVAILABLE:
        try:
            # Utilisation directe de l'API VMTK
            reader = vmtkscripts.vmtkSurfaceReader()
            reader.InputFileName = input_file
            reader.Execute()
            
            centerlines = vmtkscripts.vmtkCenterlines()
            centerlines.Surface = reader.Surface
            centerlines.AppendEndPoints = endpoints
            centerlines.Execute()
            
            writer = vmtkscripts.vmtkSurfaceWriter()
            writer.Surface = centerlines.Centerlines
            writer.OutputFileName = output_file
            writer.Execute()
            
            if render_results:
                renderer = vmtkscripts.vmtkRenderer()
                renderer.Execute()
                
                surfaceViewer = vmtkscripts.vmtkSurfaceViewer()
                surfaceViewer.Surface = reader.Surface
                surfaceViewer.Opacity = 0.25
                surfaceViewer.vmtkRenderer = renderer
                surfaceViewer.Execute()
                
                centerlineViewer = vmtkscripts.vmtkSurfaceViewer()
                centerlineViewer.Surface = centerlines.Centerlines
                centerlineViewer.vmtkRenderer = renderer
                centerlineViewer.Execute()
                
                renderer.Deallocate()
            
            return True
        except Exception as e:
            print(f"Erreur lors de l'extraction des centerlines avec l'API VMTK: {e}")
            traceback.print_exc()
            return False
    else:
        print("VMTK n'est pas disponible pour l'extraction des centerlines.")
        return False

def extract_centerlines_openprofiles(input_file, output_file, endpoints=1, render_results=False):
    """
    Extract centerlines using automatic detection of open profiles.
    
    Parameters:
    -----------
    input_file : str
        Path to the input surface model file (typically .vtp format)
    output_file : str
        Path to save the extracted centerlines
    endpoints : int
        Whether to append the segments from sources and targets to their poles (1) or not (0)
    render_results : bool
        Whether to render the results after extraction
    """
    # Create the VMTK command with openprofiles selector
    command = f'vmtkcenterlines -seedselector openprofiles -ifile {input_file} -ofile {output_file} -endpoints {endpoints}'
    
    # Execute the command
    run_vmtk_command(command)
    
    # If rendering is requested, display the results
    if render_results:
        render_command = f'vmtksurfacereader -ifile {input_file} --pipe vmtkcenterlines -seedselector openprofiles --pipe vmtkrenderer --pipe vmtksurfaceviewer -opacity 0.25 --pipe vmtksurfaceviewer -i @vmtkcenterlines.o -array MaximumInscribedSphereRadius'
        run_vmtk_command(render_command)

def visualize_voronoi_diagram(input_file, centerlines_file=None):
    """
    Visualize the Voronoi diagram with centerlines.
    
    Parameters:
    -----------
    input_file : str
        Path to the input surface model file
    centerlines_file : str, optional
        Path to the centerlines file, if already computed
    """
    if centerlines_file:
        # If centerlines are already computed, load them
        command = f'vmtksurfacereader -ifile {input_file} --pipe vmtkcenterlinereader -ifile {centerlines_file} --pipe vmtkrenderer --pipe vmtksurfaceviewer -opacity 0.25 --pipe vmtksurfaceviewer -i @vmtkcenterlinereader.voronoidiagram -array MaximumInscribedSphereRadius --pipe vmtksurfaceviewer -i @vmtkcenterlinereader.o'
    else:
        # Compute centerlines on the fly and visualize
        command = f'vmtksurfacereader -ifile {input_file} --pipe vmtkcenterlines --pipe vmtkrenderer --pipe vmtksurfaceviewer -opacity 0.25 --pipe vmtksurfaceviewer -i @vmtkcenterlines.voronoidiagram -array MaximumInscribedSphereRadius --pipe vmtksurfaceviewer -i @vmtkcenterlines.o'
    
    run_vmtk_command(command)

def main():
    # Create argument parser
    parser = argparse.ArgumentParser(description='Extract centerlines from vascular models using VMTK')
    parser.add_argument('-i', '--input', required=True, help='Input surface model file (.vtp or .stl)')
    parser.add_argument('-o', '--output', help='Output centerlines file (.vtp). If not specified, will use inputname_centerlines.vtp')
    parser.add_argument('--method', choices=['manual', 'openprofiles'], default='manual',
                        help='Method for selecting endpoints: manual or openprofiles')
    parser.add_argument('--endpoints', type=int, default=1, help='Append endpoints segments (1) or not (0)')
    parser.add_argument('--render', action='store_true', help='Render results after extraction')
    parser.add_argument('--voronoi', action='store_true', help='Visualize Voronoi diagram with centerlines')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Generate output filename if not specified
    if args.output is None:
        base_name = os.path.splitext(args.input)[0]
        args.output = f"{base_name}_centerlines.vtp"
        print(f"Output file not specified. Using: {args.output}")
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    # Check if input file exists
    if not os.path.isfile(args.input):
        print(f"Error: Input file '{args.input}' does not exist.")
        return 1
    
    # Convert STL to VTP if necessary
    input_file_vtp = args.input
    if args.input.endswith('.stl'):
        input_file_vtp = convert_stl_to_vtp(args.input)
        if not input_file_vtp or not os.path.exists(input_file_vtp):
            print("Échec de la conversion STL vers VTP.")
            return 1
    
    success = False
    # Extract centerlines
    if args.method == 'manual':
        success = extract_centerlines_manual(input_file_vtp, args.output, args.endpoints, args.render)
    else:  # openprofiles
        print("La méthode 'openprofiles' n'est pas implémentée dans cette version.")
        # success = extract_centerlines_openprofiles(input_file_vtp, args.output, args.endpoints, args.render)
    
    if success:
        print(f"Centerlines successfully extracted and saved to {args.output}")
        # Visualize Voronoi diagram if requested
        if args.voronoi:
            visualize_voronoi_diagram(args.input, args.output)
    else:
        print("Échec de l'extraction des centerlines.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
