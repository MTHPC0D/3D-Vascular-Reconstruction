import subprocess
import sys
import os

def run_process_nifti_to_stl(nifti_path, gt_path, out_path, poisson_depth=8, seuil=0.5):
    cmd = [
        sys.executable, os.path.join("src", "process_nifti_to_stl.py"),
        "--nifti", nifti_path,
        "--gt", gt_path,
        "--out", out_path,
        "--poisson_depth", str(poisson_depth),
        "--seuil", str(seuil)
    ]
    print("Lancement de la génération du mesh...")
    subprocess.run(cmd, check=True)

def run_comparaison(recon_path, gt_path):
    cmd = [sys.executable, os.path.join("src", "comparaison.py"), "--recon", recon_path, "--gt", gt_path]
    print("Lancement de la comparaison des meshes...")
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    num = "07" 
    nifti_path = f"data/{num}/label.nii"
    gt_path = f"data/{num}/arteres.stl"
    out_path = "output/output_final.stl"

    run_process_nifti_to_stl(nifti_path, gt_path, out_path)
    run_comparaison(out_path, gt_path)
