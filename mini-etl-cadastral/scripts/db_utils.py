"""Database utilities for PostGIS operations."""

import os
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import pandas as pd
import geopandas as gpd
from shapely import wkb
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_db_config() -> Dict[str, str]:
    """Get database configuration from environment variables."""
    return {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DB', 'gis'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
    }


def get_connection_string() -> str:
    """Build PostgreSQL connection string from environment variables."""
    config = get_db_config()
    return f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"


@contextmanager
def get_db_connection(**kwargs) -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager for database connections."""
    config = get_db_config()
    config.update(kwargs)
    
    conn = None
    try:
        conn = psycopg2.connect(**config)
        yield conn
    except psycopg2.Error as e:
        logger.error(f"Database connection error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def execute_query(query: str, params: Optional[tuple] = None, fetch: bool = False) -> Optional[list]:
    """Execute a SQL query with optional parameters."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(query, params)
                conn.commit()
                
                if fetch:
                    return cur.fetchall()
                    
                logger.info(f"Query executed successfully: {cur.rowcount} rows affected")
                return None
                
            except psycopg2.Error as e:
                logger.error(f"Query execution error: {e}")
                conn.rollback()
                raise


def table_exists(table_name: str, schema: str = 'public') -> bool:
    """Check if a table exists in the database."""
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name = %s
        );
    """
    result = execute_query(query, (schema, table_name), fetch=True)
    return result[0]['exists'] if result else False


def create_table_from_gdf(gdf: gpd.GeoDataFrame, table_name: str, 
                         geom_col: str = 'geometry', srid: int = 2154,
                         schema: str = 'public') -> None:
    """Create a PostGIS table from a GeoDataFrame structure."""
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Build CREATE TABLE statement
            columns = []
            for col in gdf.columns:
                if col == geom_col:
                    continue
                    
                dtype = str(gdf[col].dtype)
                if 'int' in dtype:
                    pg_type = 'INTEGER'
                elif 'float' in dtype:
                    pg_type = 'DOUBLE PRECISION'
                elif 'bool' in dtype:
                    pg_type = 'BOOLEAN'
                else:
                    pg_type = 'TEXT'
                    
                columns.append(f'"{col}" {pg_type}')
            
            # Add geometry column
            geom_type = gdf.geometry.iloc[0].geom_type if len(gdf) > 0 else 'Geometry'
            if geom_type == 'Polygon':
                geom_type = 'MultiPolygon'
            elif geom_type == 'LineString':
                geom_type = 'MultiLineString'
            elif geom_type == 'Point':
                geom_type = 'MultiPoint'
                
            create_sql = f"""
                CREATE TABLE IF NOT EXISTS {schema}.{table_name} (
                    id SERIAL PRIMARY KEY,
                    {', '.join(columns)},
                    geom geometry({geom_type}, {srid})
                );
            """
            
            cur.execute(create_sql)
            
            # Create spatial index
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS {table_name}_geom_idx 
                ON {schema}.{table_name} USING GIST (geom);
            """)
            
            conn.commit()
            logger.info(f"Table {schema}.{table_name} created successfully")


def upsert_dataframe_to_postgis(gdf: gpd.GeoDataFrame, table_name: str,
                               geom_col: str = 'geometry', srid: int = 2154,
                               schema: str = 'public', mode: str = 'append') -> None:
    """
    Insert ou met à jour les données GeoDataFrame dans PostGIS.
    
    Gère automatiquement :
    - Création de la table si elle n'existe pas
    - Conversion des géométries en WKB hexadécimal
    - Insertion par batch avec gestion d'erreurs
    - Création d'index spatial GIST
    
    Args:
        gdf: GeoDataFrame à insérer
        table_name: Nom de la table cible
        geom_col: Nom de la colonne géométrie (défaut: 'geometry')
        srid: Système de référence spatial (défaut: 2154 pour Lambert-93)
        schema: Schéma PostgreSQL (défaut: 'public')
        mode: Mode d'insertion ('append', 'replace')
        
    Modes:
        - 'append': Ajoute à la table existante
        - 'replace': Vide la table avant insertion
        
    Raises:
        psycopg2.Error: Erreur de connexion ou SQL
    """
    
    if gdf.empty:
        logger.warning("Empty GeoDataFrame, nothing to insert")
        return
        
    # Create table if it doesn't exist
    if not table_exists(table_name, schema):
        create_table_from_gdf(gdf, table_name, geom_col, srid, schema)
    elif mode == 'replace':
        execute_query(f"TRUNCATE TABLE {schema}.{table_name} RESTART IDENTITY;")
        
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Prepare data for insertion
            columns = [col for col in gdf.columns if col != geom_col]
            
            # Build INSERT statement
            col_names = ', '.join([f'"{col}"' for col in columns] + ['geom'])
            placeholders = ', '.join(['%s'] * (len(columns) + 1))
            insert_sql = f"""
                INSERT INTO {schema}.{table_name} ({col_names})
                VALUES ({placeholders})
            """
            
            # Prepare data rows
            rows = []
            for _, row in gdf.iterrows():
                values = [row[col] for col in columns]
                
                # Convert geometry to WKB hex
                geom = row[geom_col]
                if geom is not None and not geom.is_empty:
                    wkb_hex = geom.wkb_hex
                    values.append(f"SRID={srid};{wkb_hex}")
                else:
                    values.append(None)
                    
                rows.append(values)
            
            # Batch insert
            for row in rows:
                try:
                    # Handle geometry column specially
                    geom_value = row[-1]
                    if geom_value:
                        # Use ST_GeomFromEWKT for geometry with SRID
                        sql_with_geom = insert_sql.replace('%s', '%s', len(row)-1) + " ON CONFLICT DO NOTHING"
                        sql_with_geom = sql_with_geom.replace(
                            f"({'%s, ' * (len(row)-1)}%s)",
                            f"({'%s, ' * (len(row)-1)}ST_GeomFromEWKT(%s))"
                        )
                        cur.execute(sql_with_geom, row[:-1] + [geom_value])
                    else:
                        cur.execute(insert_sql + " ON CONFLICT DO NOTHING", row)
                except Exception as e:
                    logger.error(f"Error inserting row: {e}")
                    conn.rollback()
                    # Try simpler insertion
                    try:
                        conn.commit()
                        for col_val in row[:-1]:
                            if col_val is None:
                                col_val = ''
                        simple_sql = f"""
                            INSERT INTO {schema}.{table_name} ({col_names})
                            VALUES ({', '.join(['%s'] * (len(columns)))}, ST_GeomFromEWKT(%s))
                            ON CONFLICT DO NOTHING
                        """
                        cur.execute(simple_sql, row)
                        conn.commit()
                    except:
                        conn.rollback()
                        continue
                    
            conn.commit()
            logger.info(f"Successfully inserted {len(rows)} rows into {schema}.{table_name}")


def read_postgis_to_gdf(query: str, geom_col: str = 'geom') -> gpd.GeoDataFrame:
    """Read PostGIS data into a GeoDataFrame."""
    
    with get_db_connection() as conn:
        # Read non-geometry columns
        df = pd.read_sql(query, conn)
        
        if geom_col in df.columns and len(df) > 0:
            # Convert WKB to shapely geometries
            df[geom_col] = df[geom_col].apply(lambda x: wkb.loads(x, hex=True) if x else None)
            
            # Convert to GeoDataFrame
            gdf = gpd.GeoDataFrame(df, geometry=geom_col, crs='EPSG:2154')
            return gdf
        else:
            return gpd.GeoDataFrame(df, crs='EPSG:2154')


def get_table_srid(table_name: str, geom_col: str = 'geom', schema: str = 'public') -> Optional[int]:
    """Get SRID of geometry column in a PostGIS table."""
    query = """
        SELECT Find_SRID(%s, %s, %s) as srid;
    """
    try:
        result = execute_query(query, (schema, table_name, geom_col), fetch=True)
        return result[0]['srid'] if result else None
    except:
        return None