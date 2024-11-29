#!/usr/bin/env python3
"""
Générateur de données cadastrales de démonstration.

Ce script crée des parcelles fictives mais réalistes basées sur
les vraies limites communales de Côte-d'Or. Les parcelles sont
générées aléatoirement à l'intérieur des communes pour créer
un jeu de données de test représentatif.

Processus:
1. Télécharge les limites communales depuis france-geojson
2. Sélectionne 5 communes de l'agglomération dijonnaise
3. Génère des parcelles rectangulaires dans chaque commune
4. Attribue des sections et numéros cadastraux réalistes
5. Exporte en shapefile compatible PostGIS

Utilisation:
    python prepare_demo_data.py [--communes liste] [--output fichier]
    
Auteur: Mini-ETL Cadastral
Licence: MIT
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, box
from shapely.ops import unary_union
import numpy as np
from pathlib import Path
import sys

def create_parcels_from_communes(communes_file='data/communes_21.geojson', 
                                output_file='data/cote_dor_sample.shp',
                                target_communes=['Dijon', 'Quetigny', 'Chenôve', 'Talant', 'Longvic']):
    """
    Génère des parcelles cadastrales fictives dans de vraies communes.
    
    Utilise les limites administratives réelles pour créer des parcelles
    vraisemblables. Chaque parcelle a une taille entre 50 et 200 mètres
    de côté, représentative du parcellaire urbain/périurbain.
    
    Args:
        communes_file: Fichier GeoJSON des communes (source france-geojson)
        output_file: Shapefile de sortie pour les parcelles
        target_communes: Liste des communes à traiter
        
    Returns:
        GeoDataFrame: Parcelles générées avec attributs cadastraux
        
    Attributs générés:
        - id: Identifiant unique
        - nom: Nom de la commune
        - code_insee: Code INSEE de la commune
        - section: Section cadastrale (AA, AB, ZA...)
        - numero: Numéro de parcelle (0001-9999)
        - surface: Surface en m²
    """
    print(f"📍 Chargement des communes de Côte-d'Or...")
    
    # Read communes
    communes = gpd.read_file(communes_file)
    print(f"  - {len(communes)} communes trouvées")
    
    # Filter target communes
    target_gdf = communes[communes['nom'].isin(target_communes)]
    
    if target_gdf.empty:
        # Try with uppercase
        target_gdf = communes[communes['nom'].str.upper().isin([c.upper() for c in target_communes])]
    
    if target_gdf.empty:
        # If still empty, take first 5 communes
        print("  ⚠ Communes cibles non trouvées, sélection des 5 premières...")
        target_gdf = communes.head(5)
        target_communes = target_gdf['nom'].tolist()
    
    print(f"  - Communes sélectionnées : {', '.join(target_gdf['nom'].tolist())}")
    
    # Ensure CRS is set
    if target_gdf.crs != 'EPSG:2154':
        print(f"  - Reprojection vers Lambert-93 (EPSG:2154)")
        target_gdf = target_gdf.to_crs('EPSG:2154')
    
    # Create sample parcels within each commune
    all_parcels = []
    parcel_id = 1
    
    for idx, commune in target_gdf.iterrows():
        commune_geom = commune.geometry
        commune_name = commune['nom']
        commune_code = commune.get('code', f"21{idx:03d}")
        
        # Get commune bounds
        minx, miny, maxx, maxy = commune_geom.bounds
        
        # Create a grid of parcels within the commune
        # Number of parcels proportional to commune area (but limited)
        area_km2 = commune_geom.area / 1_000_000
        n_parcels = min(int(area_km2 * 5), 50)  # 5 parcels per km², max 50
        
        print(f"  - Génération de {n_parcels} parcelles pour {commune_name}...")
        
        # Generate random points within commune bounds
        np.random.seed(42 + idx)  # For reproducibility
        
        for i in range(n_parcels):
            # Try to create a parcel within the commune
            attempts = 0
            while attempts < 10:
                # Random point within bounds
                x = np.random.uniform(minx, maxx)
                y = np.random.uniform(miny, maxy)
                
                # Create a small rectangle around the point
                size = np.random.uniform(50, 200)  # 50-200m parcels
                parcel = box(x, y, x + size, y + size)
                
                # Check if parcel is within commune
                if commune_geom.contains(parcel.centroid):
                    # Create parcel data
                    section = np.random.choice(['AA', 'AB', 'AC', 'AD', 'ZA', 'ZB'])
                    numero = f"{i+1:04d}"
                    surface = parcel.area
                    
                    all_parcels.append({
                        'id': parcel_id,
                        'nom': commune_name,
                        'code_insee': commune_code,
                        'section': section,
                        'numero': numero,
                        'surface': surface,
                        'geometry': parcel
                    })
                    parcel_id += 1
                    break
                    
                attempts += 1
    
    # Create GeoDataFrame
    parcels_gdf = gpd.GeoDataFrame(all_parcels, crs='EPSG:2154')
    
    print(f"\n✅ Création terminée :")
    print(f"  - {len(parcels_gdf)} parcelles générées")
    print(f"  - Communes : {', '.join(parcels_gdf['nom'].unique())}")
    print(f"  - Surface totale : {parcels_gdf['surface'].sum()/10000:.2f} ha")
    
    # Save to shapefile
    output_path = Path(output_file)
    parcels_gdf.to_file(output_path)
    print(f"\n💾 Shapefile sauvegardé : {output_path}")
    
    # Also save communes for reference
    communes_output = output_path.parent / 'communes_cote_dor.shp'
    target_gdf[['nom', 'code', 'geometry']].to_file(communes_output)
    print(f"💾 Communes sauvegardées : {communes_output}")
    
    return parcels_gdf

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Prépare des données de démonstration')
    parser.add_argument('--communes', default='data/communes_21.geojson',
                       help='Fichier GeoJSON des communes')
    parser.add_argument('--output', default='data/cote_dor_sample.shp',
                       help='Fichier shapefile de sortie')
    parser.add_argument('--list', nargs='+', 
                       default=['Dijon', 'Quetigny', 'Chenôve', 'Talant', 'Longvic'],
                       help='Liste des communes à traiter')
    
    args = parser.parse_args()
    
    # Check if communes file exists
    if not Path(args.communes).exists():
        print(f"❌ Fichier non trouvé : {args.communes}")
        print("Téléchargement en cours...")
        import os
        os.system(f'curl -L -o {args.communes} "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements/21-cote-d-or/communes-21-cote-d-or.geojson"')
    
    # Create parcels
    create_parcels_from_communes(
        communes_file=args.communes,
        output_file=args.output,
        target_communes=args.list
    )

if __name__ == '__main__':
    main()