#!/usr/bin/env python3
"""Create sample shapefile data for testing."""

import geopandas as gpd
from shapely.geometry import Polygon
import pandas as pd
from pathlib import Path

# Create sample parcels
data = {
    'id': [1, 2, 3, 4, 5],
    'nom': ['Chenôve', 'Chenôve', 'Chenôve', 'Dijon', 'Dijon'],
    'code_insee': ['21166', '21166', '21166', '21231', '21231'],
    'section': ['AB', 'AB', 'AC', 'ZK', 'ZK'],
    'numero': ['0001', '0002', '0003', '0001', '0002'],
    'surface': [1250.5, 980.3, 2100.7, 1500.0, 1750.2]
}

# Create sample geometries (rectangles around Dijon area in Lambert-93)
geometries = [
    Polygon([(763000, 6691000), (763100, 6691000), (763100, 6691100), (763000, 6691100)]),
    Polygon([(763100, 6691000), (763200, 6691000), (763200, 6691080), (763100, 6691080)]),
    Polygon([(763000, 6691100), (763150, 6691100), (763150, 6691200), (763000, 6691200)]),
    Polygon([(763200, 6691000), (763350, 6691000), (763350, 6691120), (763200, 6691120)]),
    Polygon([(763200, 6691120), (763350, 6691120), (763350, 6691250), (763200, 6691250)])
]

# Create GeoDataFrame
gdf = gpd.GeoDataFrame(data, geometry=geometries, crs='EPSG:2154')

# Save to shapefile
output_path = Path('data/sample_shapefile.shp')
gdf.to_file(output_path)

print(f"✓ Sample shapefile created: {output_path}")
print(f"  - {len(gdf)} parcels")
print(f"  - Communes: {', '.join(gdf['nom'].unique())}")
print(f"  - CRS: EPSG:2154 (Lambert-93)")