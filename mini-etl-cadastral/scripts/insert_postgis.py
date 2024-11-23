"""Module for inserting spatial data into PostGIS."""

import logging
from typing import Optional
import geopandas as gpd
from db_utils import upsert_dataframe_to_postgis, table_exists, execute_query
from geometry_utils import normalize_geometry, ensure_crs

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def insert_geodataframe(gdf: gpd.GeoDataFrame, 
                        table_name: str,
                        srid: int = 2154,
                        schema: str = 'public',
                        mode: str = 'append',
                        normalize: bool = True) -> bool:
    """
    Insert GeoDataFrame into PostGIS table.
    
    Args:
        gdf: GeoDataFrame to insert
        table_name: Target table name
        srid: Spatial Reference ID (default 2154 for Lambert-93)
        schema: Database schema (default 'public')
        mode: Insert mode ('append', 'replace', 'fail')
        normalize: Whether to normalize geometries before insertion
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if gdf.empty:
            logger.warning("Empty GeoDataFrame provided, nothing to insert")
            return False
            
        # Ensure correct CRS
        gdf = ensure_crs(gdf, srid)
        
        # Normalize geometries if requested
        if normalize:
            gdf = normalize_geometry(gdf)
            
        # Check if table exists and handle mode
        if table_exists(table_name, schema):
            if mode == 'fail':
                logger.error(f"Table {schema}.{table_name} already exists and mode is 'fail'")
                return False
            elif mode == 'replace':
                logger.info(f"Replacing existing data in {schema}.{table_name}")
            else:  # append
                logger.info(f"Appending to existing table {schema}.{table_name}")
        else:
            logger.info(f"Creating new table {schema}.{table_name}")
            
        # Insert data
        upsert_dataframe_to_postgis(
            gdf=gdf,
            table_name=table_name,
            geom_col='geometry',
            srid=srid,
            schema=schema,
            mode=mode
        )
        
        # Update statistics
        update_table_statistics(table_name, schema)
        
        logger.info(f"Successfully inserted {len(gdf)} features into {schema}.{table_name}")
        return True
        
    except Exception as e:
        logger.error(f"Error inserting data: {e}")
        return False


def update_table_statistics(table_name: str, schema: str = 'public') -> None:
    """
    Update PostGIS table statistics for query optimization.
    
    Args:
        table_name: Table name
        schema: Database schema
    """
    try:
        # Analyze table for query planner
        execute_query(f"ANALYZE {schema}.{table_name};")
        
        # Update geometry statistics
        execute_query(f"""
            SELECT Populate_Geometry_Columns('{schema}.{table_name}'::regclass);
        """)
        
        logger.info(f"Updated statistics for {schema}.{table_name}")
        
    except Exception as e:
        logger.warning(f"Could not update statistics: {e}")


def validate_insertion(table_name: str, 
                      expected_count: int,
                      schema: str = 'public') -> bool:
    """
    Validate that insertion was successful.
    
    Args:
        table_name: Table name to validate
        expected_count: Expected number of rows
        schema: Database schema
        
    Returns:
        True if validation passes
    """
    try:
        result = execute_query(
            f"SELECT COUNT(*) as count FROM {schema}.{table_name};",
            fetch=True
        )
        
        actual_count = result[0]['count'] if result else 0
        
        if actual_count >= expected_count:
            logger.info(f"Validation passed: {actual_count} rows in {schema}.{table_name}")
            return True
        else:
            logger.warning(f"Validation warning: Expected at least {expected_count} rows, found {actual_count}")
            return False
            
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False


def create_spatial_index(table_name: str, 
                        geom_col: str = 'geom',
                        schema: str = 'public') -> None:
    """
    Create or recreate spatial index on geometry column.
    
    Args:
        table_name: Table name
        geom_col: Geometry column name
        schema: Database schema
    """
    try:
        index_name = f"{table_name}_{geom_col}_gist"
        
        # Drop if exists
        execute_query(f"DROP INDEX IF EXISTS {schema}.{index_name};")
        
        # Create new index
        execute_query(f"""
            CREATE INDEX {index_name} 
            ON {schema}.{table_name} 
            USING GIST ({geom_col});
        """)
        
        logger.info(f"Created spatial index {index_name}")
        
    except Exception as e:
        logger.error(f"Error creating spatial index: {e}")