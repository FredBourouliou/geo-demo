#!/usr/bin/env python3
"""
Module de chargement de shapefile vers PostGIS.

Ce script principal orchestre le pipeline ETL complet :
1. Lecture du shapefile avec GeoPandas
2. Validation et normalisation des géométries
3. Reprojection vers Lambert-93 (EPSG:2154)
4. Détection automatique des champs commune
5. Insertion dans la base PostGIS

Utilisation:
    python load_shapefile.py --shp data/parcelles.shp [options]
    
Auteur: Mini-ETL Cadastral
Licence: MIT
"""

import os
import sys
import argparse
import logging
from pathlib import Path
import geopandas as gpd
from dotenv import load_dotenv
from insert_postgis import insert_geodataframe
from geometry_utils import ensure_crs, normalize_geometry, calculate_geometry_stats

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def detect_commune_field(gdf: gpd.GeoDataFrame) -> str:
    """
    Détecte automatiquement le champ contenant le nom de la commune.
    
    Recherche intelligente parmi les noms de colonnes courants dans
    les données cadastrales françaises. Supporte les variantes avec
    majuscules/minuscules.
    
    Args:
        gdf: GeoDataFrame contenant les parcelles
        
    Returns:
        str: Nom du champ commune détecté, None si non trouvé
        
    Champs recherchés:
        - nom, nom_com, nom_commune, commune
        - code_insee, insee, code_commune, depcom
        - libelle (utilisé dans certains exports)
    """
    # Liste ordonnée par priorité (nom avant code)
    possible_fields = [
        'nom', 'nom_com', 'nom_commune', 'commune', 'libelle',
        'code_insee', 'insee', 'code_commune', 'depcom'
    ]
    
    for field in possible_fields:
        if field in gdf.columns:
            logger.info(f"Detected commune field: '{field}'")
            return field
        
        # Case insensitive search
        for col in gdf.columns:
            if col.lower() == field:
                logger.info(f"Detected commune field: '{col}'")
                return col
                
    logger.warning("Could not detect commune field")
    return None


def standardize_columns(gdf: gpd.GeoDataFrame, infer_commune: bool = False) -> gpd.GeoDataFrame:
    """
    Standardize column names for consistency.
    
    Args:
        gdf: Input GeoDataFrame
        infer_commune: Whether to infer and rename commune field
        
    Returns:
        GeoDataFrame with standardized columns
    """
    # Common renamings for French cadastral data
    rename_map = {
        'CODE_INSEE': 'code_insee',
        'NOM_COM': 'nom',
        'NOM_COMMUNE': 'nom',
        'COMMUNE': 'nom',
        'SURFACE': 'surface',
        'NUMERO': 'numero',
        'SECTION': 'section',
        'PREFIXE': 'prefixe',
        'CONTENANCE': 'contenance'
    }
    
    # Apply case-insensitive renaming
    columns_lower = {col.upper(): col for col in gdf.columns}
    final_rename = {}
    
    for old, new in rename_map.items():
        if old in columns_lower:
            final_rename[columns_lower[old]] = new
            
    if final_rename:
        logger.info(f"Renaming columns: {final_rename}")
        gdf = gdf.rename(columns=final_rename)
        
    # Infer commune field if requested
    if infer_commune:
        commune_field = detect_commune_field(gdf)
        if commune_field and commune_field != 'nom':
            gdf = gdf.rename(columns={commune_field: 'nom'})
            logger.info(f"Renamed '{commune_field}' to 'nom' for commune identification")
            
    return gdf


def validate_shapefile(filepath: Path) -> bool:
    """
    Validate that shapefile exists and has required components.
    
    Args:
        filepath: Path to .shp file
        
    Returns:
        True if valid shapefile
    """
    if not filepath.exists():
        logger.error(f"Shapefile not found: {filepath}")
        return False
        
    # Check for required shapefile components
    base = filepath.stem
    parent = filepath.parent
    
    required = ['.shp', '.shx', '.dbf']
    optional = ['.prj', '.cpg']
    
    for ext in required:
        component = parent / f"{base}{ext}"
        if not component.exists():
            logger.error(f"Missing required shapefile component: {component}")
            return False
            
    for ext in optional:
        component = parent / f"{base}{ext}"
        if not component.exists():
            logger.warning(f"Missing optional shapefile component: {component}")
            
    return True


def load_shapefile(shp_path: str, 
                   table_name: str = None,
                   target_srid: int = None,
                   infer_commune: bool = False,
                   mode: str = 'append') -> bool:
    """
    Load shapefile into PostGIS database.
    
    Args:
        shp_path: Path to shapefile
        table_name: Target table name (from env if not provided)
        target_srid: Target SRID (from env if not provided)
        infer_commune: Try to detect commune field
        mode: Insert mode ('append', 'replace')
        
    Returns:
        True if successful
    """
    try:
        # Get configuration
        if not table_name:
            table_name = os.getenv('TARGET_TABLE', 'parcelles')
        if not target_srid:
            target_srid = int(os.getenv('DEFAULT_SRID', '2154'))
            
        filepath = Path(shp_path)
        
        # Validate shapefile
        if not validate_shapefile(filepath):
            return False
            
        logger.info(f"Loading shapefile: {filepath}")
        logger.info(f"Target table: {table_name}")
        logger.info(f"Target SRID: {target_srid}")
        
        # Read shapefile
        gdf = gpd.read_file(filepath)
        logger.info(f"Read {len(gdf)} features from shapefile")
        
        if gdf.empty:
            logger.error("Shapefile is empty")
            return False
            
        # Log original CRS
        if gdf.crs:
            logger.info(f"Original CRS: {gdf.crs} (EPSG:{gdf.crs.to_epsg()})")
        else:
            logger.warning("No CRS found in shapefile")
            
        # Print geometry statistics
        stats = calculate_geometry_stats(gdf)
        logger.info(f"Geometry statistics: {stats}")
        
        # Standardize columns
        gdf = standardize_columns(gdf, infer_commune)
        
        # Ensure target CRS
        gdf = ensure_crs(gdf, target_srid)
        
        # Normalize geometries
        gdf = normalize_geometry(gdf)
        
        # Insert into PostGIS
        success = insert_geodataframe(
            gdf=gdf,
            table_name=table_name,
            srid=target_srid,
            mode=mode
        )
        
        if success:
            logger.info(f"✓ Successfully loaded {len(gdf)} features into {table_name}")
        else:
            logger.error("✗ Failed to load shapefile into database")
            
        return success
        
    except Exception as e:
        logger.error(f"Error loading shapefile: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Load shapefile into PostGIS database',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--shp',
        required=True,
        help='Path to shapefile (.shp)'
    )
    
    parser.add_argument(
        '--table',
        help='Target table name (default from TARGET_TABLE env)'
    )
    
    parser.add_argument(
        '--srid',
        type=int,
        help='Target SRID (default from DEFAULT_SRID env or 2154)'
    )
    
    parser.add_argument(
        '--infer-commune',
        action='store_true',
        help='Try to detect and standardize commune field'
    )
    
    parser.add_argument(
        '--mode',
        choices=['append', 'replace'],
        default='append',
        help='Insert mode (default: append)'
    )
    
    args = parser.parse_args()
    
    # Check if database is accessible
    try:
        from db_utils import execute_query
        execute_query("SELECT 1;", fetch=True)
    except Exception as e:
        logger.error(f"Cannot connect to database: {e}")
        logger.error("Make sure PostgreSQL is running (docker compose up -d)")
        sys.exit(1)
    
    # Load shapefile
    success = load_shapefile(
        shp_path=args.shp,
        table_name=args.table,
        target_srid=args.srid,
        infer_commune=args.infer_commune,
        mode=args.mode
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()