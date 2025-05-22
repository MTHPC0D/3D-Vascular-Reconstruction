import vtk
import argparse

# Ajout d'un parseur d'arguments
parser = argparse.ArgumentParser(description='Visualisation des lignes centrales avec ou sans STL')
parser.add_argument('--centerlines-only', action='store_true', help='Afficher uniquement les lignes centrales sans le STL')
args = parser.parse_args()

# Chemins des fichiers à modifier selon vos besoins
stl_path = "output/output_final.stl"
vtp_path = "output\centerlines_vtk.vtp"

# Lecture du maillage STL (seulement si nécessaire)
stl_actor = None
if not args.centerlines_only:
    stl_reader = vtk.vtkSTLReader()
    stl_reader.SetFileName(stl_path)
    stl_reader.Update()

    stl_mapper = vtk.vtkPolyDataMapper()
    stl_mapper.SetInputConnection(stl_reader.GetOutputPort())

    stl_actor = vtk.vtkActor()
    stl_actor.SetMapper(stl_mapper)
    stl_actor.GetProperty().SetOpacity(0.3)  # semi-transparent
    stl_actor.GetProperty().SetColor(0.8, 0.8, 0.8)

# Lecture des centerlines VTP
vtp_reader = vtk.vtkXMLPolyDataReader()
vtp_reader.SetFileName(vtp_path)
vtp_reader.Update()

vtp_mapper = vtk.vtkPolyDataMapper()
vtp_mapper.SetInputConnection(vtp_reader.GetOutputPort())

vtp_actor = vtk.vtkActor()
vtp_actor.SetMapper(vtp_mapper)
vtp_actor.GetProperty().SetColor(1, 0, 0)  # rouge
vtp_actor.GetProperty().SetLineWidth(4)

# Fenêtre de rendu
renderer = vtk.vtkRenderer()
if not args.centerlines_only and stl_actor:
    renderer.AddActor(stl_actor)
renderer.AddActor(vtp_actor)
renderer.SetBackground(1, 1, 1)

render_window = vtk.vtkRenderWindow()
render_window.AddRenderer(renderer)
render_window.SetSize(800, 600)

interactor = vtk.vtkRenderWindowInteractor()
interactor.SetRenderWindow(render_window)

# Lancer la visualisation
render_window.Render()
interactor.Start()