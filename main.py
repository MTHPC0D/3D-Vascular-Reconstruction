import subprocess
import sys
import os
import argparse

def run_process_nifti_to_stl(nifti_path, gt_path, out_path, poisson_depth=8, seuil=0.5):
    cmd = [
        sys.executable, os.path.join("src", "process_nifti_to_stl.py"),
        "--nifti", nifti_path,
        "--gt", gt_path,
        "--out", out_path,
        "--poisson_depth", str(poisson_depth),
        "--seuil", str(seuil)
    ]
    subprocess.run(cmd, check=True)

def run_comparaison(recon_path, gt_path):
    cmd = [sys.executable, os.path.join("src", "comparaison.py"), "--recon", recon_path, "--gt", gt_path]
    subprocess.run(cmd, check=True)

def run_centerlines_extraction(stl_path, voxel_size=0.4, spur_prune=1.0, out_vtp="output/centerlines_vtk.vtp"):
    """Extraction des lignes centrales à partir d'un fichier STL"""
    # Exécution du script avec les paramètres via des variables d'environnement
    cmd = [sys.executable, os.path.join("src", "centerlinesVMTK.py")]
    
    # Passage des paramètres via des variables d'environnement
    env = os.environ.copy()
    env["CENTERLINES_STL_FILE"] = stl_path
    env["CENTERLINES_VOXEL_SIZE"] = str(voxel_size)
    env["CENTERLINES_SPUR_PRUNE"] = str(spur_prune)
    env["CENTERLINES_OUT_VTP"] = out_vtp
    
    subprocess.run(cmd, env=env, check=True)
    return out_vtp

def run_visualization(stl_path="output/output_final.stl", vtp_path="output/centerlines_vtk.vtp", centerlines_only=False):
    """Visualisation des lignes centrales avec ou sans le STL"""
    cmd = [
        sys.executable, os.path.join("src", "visuligne.py"),
    ]
    
    if centerlines_only:
        cmd.append("--centerlines-only")
        
    print("Lancement de la visualisation...")
    subprocess.run(cmd, check=True)

def run_indicators_calculation(vtp_path="output/centerlines_vtk.vtp", output_file="output/vascular_indicators.json"):
    """Calcul des indicateurs vasculaires à partir des lignes centrales"""
    cmd = [
        sys.executable, os.path.join("src", "indicateurs.py"),
        "--vtp", vtp_path,
        "--output", output_file
    ]
    print("Calcul des indicateurs vasculaires...")
    subprocess.run(cmd, check=True)
    return output_file

if __name__ == "__main__":
    # Analyse des arguments de la ligne de commande
    parser = argparse.ArgumentParser(description="Reconstruction 3D vasculaire avec extraction des lignes centrales et indicateurs")
    parser.add_argument("--num", type=str, default="07", help="Numéro du patient à traiter")
    parser.add_argument("--skip-mesh", action="store_true", help="Sauter l'étape de génération du mesh")
    parser.add_argument("--skip-comparaison", action="store_true", help="Sauter l'étape de comparaison")
    parser.add_argument("--skip-visualization", action="store_true", help="Sauter l'étape de visualisation")
    parser.add_argument("--centerlines-only", action="store_true", help="Visualiser uniquement les lignes centrales sans le STL")
    args = parser.parse_args()
    
    # Chemins des fichiers
    num = args.num 
    nifti_path = f"data/{num}/label.nii"
    gt_path = f"data/{num}/arteres.stl"
    out_path = "output/output_final.stl"
    vtp_path = "output/centerlines_vtk.vtp"
    indicators_path = "output/vascular_indicators.json"

    # 1. Génération du mesh à partir du NIfTI
    if not args.skip_mesh:
        run_process_nifti_to_stl(nifti_path, gt_path, out_path)
    
    # 2. Comparaison avec le mesh de référence
    if not args.skip_comparaison:
        run_comparaison(out_path, gt_path)
    
    # 3. Extraction des lignes centrales
    vtp_path = run_centerlines_extraction(out_path)
    print(f"✅ Lignes centrales extraites et sauvegardées dans {vtp_path}")
    
    # 4. Calcul des indicateurs vasculaires
    indicators_path = run_indicators_calculation(vtp_path, indicators_path)
    print(f"✅ Indicateurs calculés et sauvegardés dans {indicators_path}")
    
    # 5. Visualisation interactive
    if not args.skip_visualization:
        run_visualization(out_path, vtp_path, args.centerlines_only)
        print("✅ Visualisation terminée")
