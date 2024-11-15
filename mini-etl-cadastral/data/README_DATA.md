# Data Directory

This directory is intended for storing spatial data files (shapefiles, GeoJSON, etc.) that will be loaded into the PostGIS database.

## Default Data Location

The ETL pipeline expects a shapefile at: `data/sample_shapefile.shp`

Place your shapefile components here:
- `sample_shapefile.shp` (geometry)
- `sample_shapefile.shx` (index)
- `sample_shapefile.dbf` (attributes)
- `sample_shapefile.prj` (projection - optional but recommended)
- `sample_shapefile.cpg` (encoding - optional)

## Where to Get Sample Data

### French Cadastral Data (Recommended for this project)

1. **Cadastre.gouv.fr** - Official French cadastral data
   - URL: https://cadastre.data.gouv.fr/
   - Format: Shapefile, GeoJSON
   - Coverage: All French departments
   - License: Open License 2.0

2. **data.gouv.fr** - French open data portal
   - Parcelles cadastrales: https://www.data.gouv.fr/fr/datasets/parcelles-cadastrales/
   - Communes: https://www.data.gouv.fr/fr/datasets/decoupage-administratif-communal-francais-issu-d-openstreetmap/
   - Various formats available

3. **IGN (Institut Géographique National)**
   - BD PARCELLAIRE: https://geoservices.ign.fr/bdparcellaire
   - BD TOPO: https://geoservices.ign.fr/bdtopo
   - Professional quality data

### Example: Download Côte-d'Or (21) Cadastral Data

```bash
# Example for Dijon area (21000)
# 1. Visit: https://cadastre.data.gouv.fr/data/etalab-cadastre/latest/shp/departements/21/
# 2. Download the commune you want (e.g., cadastre-21231-parcelles-shp.zip for Dijon)

# Extract and rename:
cd data/
wget https://cadastre.data.gouv.fr/data/etalab-cadastre/latest/shp/departements/21/communes/21231/cadastre-21231-parcelles-shp.zip
unzip cadastre-21231-parcelles-shp.zip
mv parcelles.* sample_shapefile.*
rm cadastre-21231-parcelles-shp.zip
```

### Other Useful Data Sources

1. **OpenStreetMap France**
   - URL: https://download.openstreetmap.fr/
   - Formats: Shapefile, PBF
   - Updated regularly

2. **Geoportail** (for visualization)
   - URL: https://www.geoportail.gouv.fr/
   - WMS/WFS services available

3. **Regional Open Data Portals**
   - Île-de-France: https://data.iledefrance.fr/
   - Grand Est: https://www.datagrandest.fr/
   - Occitanie: https://data.laregion.fr/

## Data Formats Supported

The load script (`scripts/load_shapefile.py`) supports:
- Shapefile (.shp) - Primary format
- GeoJSON (.geojson) - Via GeoPandas
- GeoPackage (.gpkg) - Via GeoPandas
- Any format supported by Fiona/GDAL

## Custom Data Loading

To load a custom shapefile:

```bash
# Basic loading
make load-custom SHP=/path/to/your/shapefile.shp

# With custom table name
make load-custom SHP=/path/to/your/shapefile.shp TABLE=my_parcels

# Direct Python usage
./venv/bin/python scripts/load_shapefile.py \
  --shp /path/to/shapefile.shp \
  --table my_table \
  --srid 2154 \
  --infer-commune
```

## Projection Information

This ETL pipeline uses **EPSG:2154 (Lambert-93)** by default, which is the standard projection for metropolitan France.

If your data uses a different projection:
- WGS84 (EPSG:4326): Will be automatically reprojected
- Lambert II étendu (EPSG:27572): Will be automatically reprojected
- Other projections: Ensure .prj file is present

## Data Size Recommendations

For testing and development:
- Start with a single commune (typically 1,000-10,000 parcels)
- Avoid loading entire departments initially (can be millions of parcels)
- Use the bounding box clip feature for large datasets

## License Considerations

Most French cadastral and administrative data is available under:
- **Licence Ouverte 2.0** (Open License 2.0)
- Compatible with most uses including commercial

Always verify the specific license for your data source.

## Outputs Directory

Query results and exports are saved to: `data/outputs/`

This includes:
- CSV exports of query results
- Statistics summaries
- Spatial analysis outputs

## Troubleshooting

### Missing .prj file
If you get CRS warnings, create a .prj file or set CRS explicitly:
```python
gdf = gpd.read_file('data/sample_shapefile.shp')
gdf.set_crs('EPSG:2154', inplace=True)
```

### Encoding issues
French data often uses Latin-1 or UTF-8 encoding. If you encounter issues:
```bash
# Check encoding
file -bi data/sample_shapefile.dbf

# Set encoding in .cpg file
echo "UTF-8" > data/sample_shapefile.cpg
```

### Large files
For files > 100MB, consider:
1. Filtering by commune/department first
2. Using spatial indexes
3. Batch processing