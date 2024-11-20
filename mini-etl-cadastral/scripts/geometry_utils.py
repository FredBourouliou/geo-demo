"""Geometry utilities for spatial data processing."""

import logging
from typing import Optional, Union
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, Point, MultiPoint
from shapely.ops import unary_union
from shapely.validation import make_valid
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def ensure_crs(gdf: gpd.GeoDataFrame, target_epsg: int = 2154) -> gpd.GeoDataFrame:
    """
    Assure que le GeoDataFrame utilise le bon système de référence spatial.
    
    Gestion automatique de la reprojection :
    - Détecte le CRS actuel
    - Reprojette si nécessaire vers le CRS cible
    - Gère les cas où le CRS est manquant
    
    Lambert-93 (EPSG:2154) est le standard pour la France métropolitaine,
    offrant une précision optimale pour les calculs de surface.
    
    Args:
        gdf: GeoDataFrame d'entrée
        target_epsg: Code EPSG cible (défaut 2154 pour Lambert-93)
        
    Returns:
        GeoDataFrame: Données avec CRS correct
        
    Projections courantes en France:
        - 2154: Lambert-93 (recommandé)
        - 4326: WGS84 (GPS, à éviter pour calculs)
        - 27572: Lambert II étendu (ancien)
    """
    if gdf.crs is None:
        logger.warning(f"No CRS detected, setting to EPSG:{target_epsg}")
        gdf = gdf.set_crs(f"EPSG:{target_epsg}")
    elif gdf.crs.to_epsg() != target_epsg:
        logger.info(f"Reprojecting from EPSG:{gdf.crs.to_epsg()} to EPSG:{target_epsg}")
        gdf = gdf.to_crs(f"EPSG:{target_epsg}")
    else:
        logger.info(f"CRS already set to EPSG:{target_epsg}")
        
    return gdf


def to_multi_geometry(geom: Union[Polygon, LineString, Point, 
                                  MultiPolygon, MultiLineString, MultiPoint]) -> Union[MultiPolygon, MultiLineString, MultiPoint]:
    """
    Convert single geometry to multi-geometry.
    
    Args:
        geom: Input geometry (single or multi)
        
    Returns:
        Multi-geometry version
    """
    if geom is None or geom.is_empty:
        return None
        
    # Already multi-geometry
    if geom.geom_type.startswith('Multi'):
        return geom
        
    # Convert to multi
    if geom.geom_type == 'Polygon':
        return MultiPolygon([geom])
    elif geom.geom_type == 'LineString':
        return MultiLineString([geom])
    elif geom.geom_type == 'Point':
        return MultiPoint([geom])
    else:
        # GeometryCollection or other
        return geom


def normalize_geometry(gdf: gpd.GeoDataFrame, 
                      force_multi: bool = True,
                      simplify_tolerance: Optional[float] = None,
                      fix_invalid: bool = True) -> gpd.GeoDataFrame:
    """
    Normalize geometries in GeoDataFrame.
    
    Args:
        gdf: Input GeoDataFrame
        force_multi: Convert single geometries to multi-geometries
        simplify_tolerance: Simplification tolerance (meters for projected CRS)
        fix_invalid: Fix invalid geometries using buffer(0) and make_valid
        
    Returns:
        GeoDataFrame with normalized geometries
    """
    gdf = gdf.copy()
    
    # Fix invalid geometries
    if fix_invalid:
        logger.info("Checking and fixing invalid geometries...")
        invalid_count = (~gdf.geometry.is_valid).sum()
        
        if invalid_count > 0:
            logger.warning(f"Found {invalid_count} invalid geometries, attempting to fix...")
            
            # Try buffer(0) first
            gdf.geometry = gdf.geometry.buffer(0)
            
            # For remaining invalid, use make_valid
            still_invalid = ~gdf.geometry.is_valid
            if still_invalid.any():
                gdf.loc[still_invalid, 'geometry'] = gdf.loc[still_invalid, 'geometry'].apply(make_valid)
                
            final_invalid = (~gdf.geometry.is_valid).sum()
            if final_invalid > 0:
                logger.error(f"Could not fix {final_invalid} geometries")
            else:
                logger.info("All invalid geometries fixed")
    
    # Convert to multi-geometries
    if force_multi:
        logger.info("Converting to multi-geometries...")
        gdf.geometry = gdf.geometry.apply(to_multi_geometry)
    
    # Simplify if requested
    if simplify_tolerance:
        logger.info(f"Simplifying geometries with tolerance {simplify_tolerance}...")
        gdf.geometry = gdf.geometry.simplify(simplify_tolerance, preserve_topology=True)
    
    # Remove empty geometries
    empty_count = gdf.geometry.is_empty.sum()
    if empty_count > 0:
        logger.warning(f"Removing {empty_count} empty geometries")
        gdf = gdf[~gdf.geometry.is_empty]
    
    # Remove None geometries
    none_count = gdf.geometry.isna().sum()
    if none_count > 0:
        logger.warning(f"Removing {none_count} null geometries")
        gdf = gdf[gdf.geometry.notna()]
    
    logger.info(f"Geometry normalization complete: {len(gdf)} valid features")
    return gdf


def calculate_geometry_stats(gdf: gpd.GeoDataFrame) -> dict:
    """
    Calculate basic statistics for geometries.
    
    Args:
        gdf: Input GeoDataFrame
        
    Returns:
        Dictionary with geometry statistics
    """
    stats = {
        'total_features': len(gdf),
        'geometry_types': gdf.geometry.geom_type.value_counts().to_dict(),
        'crs': str(gdf.crs) if gdf.crs else 'None',
        'bounds': gdf.total_bounds.tolist() if len(gdf) > 0 else None
    }
    
    # Add area statistics for polygons
    if len(gdf) > 0 and gdf.geometry.iloc[0].geom_type in ['Polygon', 'MultiPolygon']:
        areas = gdf.geometry.area
        stats['area_stats'] = {
            'total': float(areas.sum()),
            'mean': float(areas.mean()),
            'min': float(areas.min()),
            'max': float(areas.max())
        }
    
    # Add length statistics for lines
    if len(gdf) > 0 and gdf.geometry.iloc[0].geom_type in ['LineString', 'MultiLineString']:
        lengths = gdf.geometry.length
        stats['length_stats'] = {
            'total': float(lengths.sum()),
            'mean': float(lengths.mean()),
            'min': float(lengths.min()),
            'max': float(lengths.max())
        }
    
    return stats


def clip_by_bounds(gdf: gpd.GeoDataFrame, 
                   minx: float, miny: float, 
                   maxx: float, maxy: float) -> gpd.GeoDataFrame:
    """
    Clip GeoDataFrame by bounding box.
    
    Args:
        gdf: Input GeoDataFrame
        minx, miny, maxx, maxy: Bounding box coordinates
        
    Returns:
        Clipped GeoDataFrame
    """
    from shapely.geometry import box
    
    bbox = box(minx, miny, maxx, maxy)
    
    # Ensure same CRS for clipping
    bbox_gdf = gpd.GeoDataFrame([1], geometry=[bbox], crs=gdf.crs)
    
    # Perform clip
    clipped = gpd.clip(gdf, bbox_gdf)
    
    logger.info(f"Clipped {len(gdf)} features to {len(clipped)} features within bounds")
    return clipped


def dissolve_by_attribute(gdf: gpd.GeoDataFrame, 
                         attribute: str,
                         aggfunc: dict = None) -> gpd.GeoDataFrame:
    """
    Dissolve geometries by attribute.
    
    Args:
        gdf: Input GeoDataFrame
        attribute: Column name to dissolve by
        aggfunc: Aggregation functions for other columns
        
    Returns:
        Dissolved GeoDataFrame
    """
    if attribute not in gdf.columns:
        raise ValueError(f"Attribute '{attribute}' not found in GeoDataFrame")
    
    logger.info(f"Dissolving by '{attribute}'...")
    
    if aggfunc:
        dissolved = gdf.dissolve(by=attribute, aggfunc=aggfunc)
    else:
        dissolved = gdf.dissolve(by=attribute)
    
    logger.info(f"Dissolved {len(gdf)} features to {len(dissolved)} features")
    return dissolved