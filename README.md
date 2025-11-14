# 3D-Vascular-Reconstruction

Application avancée de reconstruction et d'analyse de structures vasculaires à partir d'images médicales NIfTI. Ce projet propose une interface graphique intuitive pour générer des modèles 3D, extraire des lignes centrales et calculer des indicateurs cliniques pertinents.


https://github.com/user-attachments/assets/a9473f2c-8b66-4848-ad41-148b6913a47f


## Fonctionnalités

### Interface Graphique (GUI)
- **Interface moderne** avec thème clair/sombre
- **Drag & drop** pour charger les fichiers facilement
- **Visualisation 3D interactive** avec contrôle de visibilité
- **Tableau de métriques** avec export CSV
- **Capture d'écran** de la vue 3D
- **Export** des meshes reconstruits

### Traitement d'images
- **Reconstruction 3D** depuis fichiers NIfTI (Marching Cubes + Poisson)
- **Extraction de lignes centrales** vasculaires optimisée
- **Comparaison** avec ground truth (optionnel)
- **Calcul automatique** d'indicateurs cliniques

### Indicateurs vasculaires
- **Tortuosité globale** du réseau vasculaire
- **Angles de décollage** des branches
- **Angles de bifurcation**
- **Courbure maximale** et rayon minimal
- **Classification du type d'arche aortique** (I, II, III)

## Architecture

```
┌─────────────────────┐
│   Interface GUI     │
│    (PyQt6)          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Contrôleur       │
│  (Orchestration)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────┐
│         Pipeline Backend            │
├─────────────────────────────────────┤
│ 1. Reconstruction mesh (Open3D)     │
│ 2. Comparaison (optionnel)          │
│ 3. Extraction centerlines (VTK)     │
│ 4. Calcul indicateurs (NumPy/SciPy) │
└─────────────────────────────────────┘
```

## Utilisation

### Interface Graphique (recommandé)

```bash
python run_app.py
```

#### Workflow GUI:
1. **Glisser-déposer** ou parcourir pour charger un fichier NIfTI
2. *(Optionnel)* Charger un fichier STL de référence (ground truth)
3. Cliquer sur **"Lancer l'Analyse"**
4. Visualiser les résultats en 3D
5. Exporter les métriques en CSV ou capturer des images

### Ligne de commande

```bash
# Traitement complet avec ground truth
python main.py --num 07

# Traitement sans comparaison
python main.py --num 07 --skip-comparaison

# Visualisation seulement des centerlines
python main.py --num 07 --centerlines-only --skip-visualization
```

#### Options disponibles:
- `--num`: Numéro du patient (défaut: 07)
- `--skip-mesh`: Ignorer la génération du mesh
- `--skip-comparaison`: Ignorer la comparaison avec GT
- `--skip-visualization`: Ignorer la visualisation
- `--centerlines-only`: Afficher uniquement les centerlines

### Scripts individuels

```bash
# Reconstruction mesh uniquement
python src/process_nifti_to_stl.py --nifti data/07/label.nii --gt data/07/arteres.stl --out output/mesh.stl

# Extraction centerlines
python src/centerlinesVMTK.py

# Calcul indicateurs
python src/indicateurs.py --vtp output/centerlines_vtk.vtp --output output/indicators.json

# Visualisation
python src/visuligne.py --centerlines-only
```

## Pipeline de traitement

### 1. Reconstruction du mesh 3D
- **Input**: Fichier NIfTI (`.nii` ou `.nii.gz`)
- **Processus**: 
  - Marching Cubes pour extraction isosurface
  - Reconstruction de Poisson pour surface lisse
  - Application de la matrice affine
  - Rotation pour alignement anatomique
- **Output**: Mesh STL 3D

### 2. Comparaison (optionnel)
- **Input**: Mesh reconstruit + Ground truth STL
- **Métriques calculées**:
  - Distance RMS (Root Mean Square)
  - Distance de Hausdorff
  - Ratio de volume
  - Score de Dice
- **Output**: Rapport de comparaison

### 3. Extraction des lignes centrales
- **Processus**:
  - Voxelisation du mesh
  - Remplissage des cavités
  - Squelettisation 3D
  - Élagage intelligent des branches
  - Lissage par splines
- **Output**: Fichier VTP avec centerlines

### 4. Calcul des indicateurs
- **Analyse géométrique**:
  - Parcours du graphe vasculaire
  - Détection des bifurcations
  - Calcul de courbures
  - Classification anatomique
- **Output**: Fichier JSON avec métriques

## Structure du projet

```
3D-Vascular-Reconstruction/
├── src/
│   ├── GUI/
│   │   ├── __init__.py
│   │   ├── app.py              # Application principale
│   │   ├── controller.py       # Contrôleur backend
│   │   ├── views.py            # Composants UI
│   │   └── vtk_widget.py       # Widget de visualisation 3D
│   ├── process_nifti_to_stl.py # Reconstruction mesh
│   ├── centerlinesVMTK.py      # Extraction centerlines
│   ├── indicateurs.py          # Calcul indicateurs
│   ├── comparaison.py          # Comparaison meshes
│   └── visuligne.py            # Visualisation standalone
├── data/                       # Données d'entrée
│   └── 07/
│       ├── label.nii
│       └── arteres.stl
├── output/                     # Résultats générés
│   ├── output_final.stl
│   ├── centerlines_vtk.vtp
│   └── vascular_indicators.json
├── res/                        # Ressources (icônes, etc.)
│   └── logo.ico
├── main.py                     # Point d'entrée CLI
├── run_app.py                  # Point d'entrée GUI
├── requirements.txt
└── README.md
```

## Technologies utilisées

- **PyQt6**: Interface graphique moderne
- **VTK**: Visualisation et traitement 3D
- **Open3D**: Reconstruction de surfaces
- **NiBabel**: Lecture de fichiers NIfTI
- **scikit-image**: Traitement d'images (Marching Cubes)
- **NetworkX**: Analyse de graphes pour centerlines
- **NumPy/SciPy**: Calculs numériques avancés
- **Trimesh**: Manipulation de meshes 3D


## Format des données

### Entrée requise
- **NIfTI** (`.nii` ou `.nii.gz`): Volume 3D segmenté des vaisseaux
- **STL** (optionnel): Mesh de référence pour validation

### Sortie générée
- **STL**: Mesh 3D reconstruit
- **VTP**: Lignes centrales au format VTK PolyData
- **JSON**: Indicateurs vasculaires structurés
- **CSV**: Export des métriques
