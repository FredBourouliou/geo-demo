#!/usr/bin/env python3
"""
Module d'exécution de requêtes spatiales PostGIS.

Ce script démontre les capacités d'analyse spatiale avec PostGIS :
- Sélection de parcelles par commune
- Calculs statistiques (surfaces, périmètres)
- Jointures spatiales entre tables
- Export des résultats en CSV

Exemples de requêtes SQL spatiales implémentées :
- ST_Area() : calcul de surface
- ST_Perimeter() : calcul de périmètre
- ST_Within() : test d'inclusion
- ST_Intersects() : test d'intersection

Utilisation:
    python query_examples.py --commune "Dijon" --stats --export
    
Auteur: Mini-ETL Cadastral
Licence: MIT
"""

import os
import sys
import argparse
import logging
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from db_utils import execute_query, table_exists, read_postgis_to_gdf

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def query_by_commune(commune_value: str, 
                     table_name: str = 'parcelles',
                     commune_field: str = None) -> pd.DataFrame:
    """
    Query features by commune name or code.
    
    Args:
        commune_value: Commune name or INSEE code
        table_name: Table to query
        commune_field: Field containing commune info
        
    Returns:
        DataFrame with results
    """
    if not table_exists(table_name):
        logger.error(f"Table '{table_name}' does not exist")
        return pd.DataFrame()
        
    # Get commune field from env if not provided
    if not commune_field:
        commune_field = os.getenv('COMMUNE_FIELD', 'nom')
        
    # Check if commune field exists in table
    check_query = f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s 
        AND column_name = %s;
    """
    
    result = execute_query(check_query, (table_name, commune_field), fetch=True)
    
    if not result:
        logger.warning(f"Field '{commune_field}' not found in table '{table_name}'")
        
        # Try to find a suitable field
        fallback_query = f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s 
            AND column_name IN ('nom', 'commune', 'code_insee', 'insee', 'nom_com')
            LIMIT 1;
        """
        
        fallback = execute_query(fallback_query, (table_name,), fetch=True)
        
        if fallback:
            commune_field = fallback[0]['column_name']
            logger.info(f"Using fallback field: '{commune_field}'")
        else:
            logger.error("No suitable commune field found in table")
            logger.info("Available columns:")
            
            cols_query = f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position;
            """
            
            cols = execute_query(cols_query, (table_name,), fetch=True)
            for col in cols:
                if col['column_name'] != 'geom':
                    logger.info(f"  - {col['column_name']} ({col['data_type']})")
                    
            return pd.DataFrame()
    
    # Query by commune
    logger.info(f"Querying {table_name} where {commune_field} = '{commune_value}'")
    
    query = f"""
        SELECT *, ST_AsText(geom) as wkt_geom
        FROM {table_name}
        WHERE {commune_field} = %s;
    """
    
    results = execute_query(query, (commune_value,), fetch=True)
    
    if results:
        logger.info(f"Found {len(results)} features in commune '{commune_value}'")
        return pd.DataFrame(results)
    else:
        logger.warning(f"No features found for commune '{commune_value}'")
        
        # Show available values
        distinct_query = f"""
            SELECT DISTINCT {commune_field} 
            FROM {table_name} 
            WHERE {commune_field} IS NOT NULL
            ORDER BY {commune_field}
            LIMIT 10;
        """
        
        distinct_vals = execute_query(distinct_query, fetch=True)
        
        if distinct_vals:
            logger.info("Available commune values (first 10):")
            for val in distinct_vals:
                logger.info(f"  - {val[commune_field]}")
                
        return pd.DataFrame()


def calculate_commune_statistics(commune_value: str,
                                table_name: str = 'parcelles',
                                commune_field: str = None) -> dict:
    """
    Calculate spatial statistics for a commune.
    
    Args:
        commune_value: Commune name or INSEE code
        table_name: Table to query
        commune_field: Field containing commune info
        
    Returns:
        Dictionary with statistics
    """
    if not table_exists(table_name):
        logger.error(f"Table '{table_name}' does not exist")
        return {}
        
    if not commune_field:
        commune_field = os.getenv('COMMUNE_FIELD', 'nom')
        
    # Check if we can use spatial operations
    query = f"""
        SELECT 
            COUNT(*) as count,
            SUM(ST_Area(geom)) as total_area,
            AVG(ST_Area(geom)) as avg_area,
            MIN(ST_Area(geom)) as min_area,
            MAX(ST_Area(geom)) as max_area,
            SUM(ST_Perimeter(geom)) as total_perimeter,
            AVG(ST_Perimeter(geom)) as avg_perimeter
        FROM {table_name}
        WHERE {commune_field} = %s;
    """
    
    try:
        result = execute_query(query, (commune_value,), fetch=True)
        
        if result and result[0]['count'] > 0:
            stats = result[0]
            
            # Convert to hectares for readability (assuming m² from Lambert-93)
            if stats['total_area']:
                stats['total_area_ha'] = stats['total_area'] / 10000
                stats['avg_area_ha'] = stats['avg_area'] / 10000
                stats['min_area_ha'] = stats['min_area'] / 10000
                stats['max_area_ha'] = stats['max_area'] / 10000
                
            logger.info(f"\nStatistics for commune '{commune_value}':")
            logger.info(f"  Number of features: {stats['count']}")
            
            if stats['total_area']:
                logger.info(f"  Total area: {stats['total_area_ha']:.2f} ha")
                logger.info(f"  Average area: {stats['avg_area_ha']:.4f} ha")
                logger.info(f"  Min area: {stats['min_area_ha']:.4f} ha")
                logger.info(f"  Max area: {stats['max_area_ha']:.4f} ha")
                logger.info(f"  Total perimeter: {stats['total_perimeter']:.2f} m")
                logger.info(f"  Average perimeter: {stats['avg_perimeter']:.2f} m")
                
            return stats
        else:
            logger.warning(f"No statistics available for commune '{commune_value}'")
            return {}
            
    except Exception as e:
        logger.error(f"Error calculating statistics: {e}")
        
        # Fallback to simple count
        count_query = f"""
            SELECT COUNT(*) as count
            FROM {table_name}
            WHERE {commune_field} = %s;
        """
        
        result = execute_query(count_query, (commune_value,), fetch=True)
        
        if result:
            return {'count': result[0]['count']}
        else:
            return {}


def spatial_intersection_query(table1: str = 'parcelles', 
                              table2: str = 'communes') -> pd.DataFrame:
    """
    Example spatial intersection query between two tables.
    
    Args:
        table1: First table (e.g., parcelles)
        table2: Second table (e.g., communes)
        
    Returns:
        DataFrame with intersection results
    """
    if not table_exists(table1):
        logger.warning(f"Table '{table1}' does not exist")
        return pd.DataFrame()
        
    if not table_exists(table2):
        logger.info(f"Table '{table2}' does not exist - skipping spatial intersection")
        logger.info(f"To use this feature, load commune boundaries into '{table2}' table")
        return pd.DataFrame()
        
    query = f"""
        SELECT 
            t1.id as parcelle_id,
            t2.nom as commune_nom,
            t2.code_insee,
            ST_Area(t1.geom) as parcelle_area,
            ST_Area(ST_Intersection(t1.geom, t2.geom)) as intersection_area
        FROM {table1} t1
        JOIN {table2} t2 ON ST_Intersects(t1.geom, t2.geom)
        LIMIT 100;
    """
    
    try:
        results = execute_query(query, fetch=True)
        
        if results:
            logger.info(f"Found {len(results)} spatial intersections")
            return pd.DataFrame(results)
        else:
            logger.info("No spatial intersections found")
            return pd.DataFrame()
            
    except Exception as e:
        logger.error(f"Spatial query error: {e}")
        return pd.DataFrame()


def export_results(df: pd.DataFrame, filename: str = 'query_result.csv') -> None:
    """
    Export query results to CSV.
    
    Args:
        df: Results DataFrame
        filename: Output filename
    """
    if df.empty:
        logger.warning("No results to export")
        return
        
    output_dir = Path('data/outputs')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / filename
    
    # Remove geometry columns for CSV export
    export_df = df.copy()
    geo_cols = ['geom', 'wkt_geom', 'geometry']
    
    for col in geo_cols:
        if col in export_df.columns:
            export_df = export_df.drop(columns=[col])
            
    export_df.to_csv(output_path, index=False)
    logger.info(f"Results exported to: {output_path}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Execute spatial queries on PostGIS data',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--commune',
        help='Commune name or INSEE code to query'
    )
    
    parser.add_argument(
        '--table',
        help='Table name (default from TARGET_TABLE env)'
    )
    
    parser.add_argument(
        '--field',
        help='Commune field name (default from COMMUNE_FIELD env)'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Calculate spatial statistics'
    )
    
    parser.add_argument(
        '--export',
        action='store_true',
        help='Export results to CSV'
    )
    
    args = parser.parse_args()
    
    # Get configuration
    commune_value = args.commune or os.getenv('COMMUNE_VALUE', 'Quetigny')
    table_name = args.table or os.getenv('TARGET_TABLE', 'parcelles')
    commune_field = args.field or os.getenv('COMMUNE_FIELD', 'nom')
    
    # Check database connection
    try:
        execute_query("SELECT 1;", fetch=True)
    except Exception as e:
        logger.error(f"Cannot connect to database: {e}")
        logger.error("Make sure PostgreSQL is running (docker compose up -d)")
        sys.exit(1)
    
    # Execute queries
    logger.info("=" * 50)
    logger.info("SPATIAL QUERY EXAMPLES")
    logger.info("=" * 50)
    
    # Query 1: Select by commune
    logger.info("\n1. Query by commune:")
    df_commune = query_by_commune(commune_value, table_name, commune_field)
    
    # Query 2: Calculate statistics
    if args.stats or True:  # Always show stats
        logger.info("\n2. Spatial statistics:")
        stats = calculate_commune_statistics(commune_value, table_name, commune_field)
    
    # Query 3: Spatial intersection (if communes table exists)
    logger.info("\n3. Spatial intersection example:")
    df_intersect = spatial_intersection_query()
    
    # Export results if requested
    if args.export and not df_commune.empty:
        export_results(df_commune, f"commune_{commune_value}_parcelles.csv")
        
        if stats:
            stats_df = pd.DataFrame([stats])
            export_results(stats_df, f"commune_{commune_value}_stats.csv")
    
    logger.info("\n" + "=" * 50)
    logger.info("Query execution complete")


if __name__ == '__main__':
    main()