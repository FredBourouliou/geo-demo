-- Create main parcelles table for cadastral data
CREATE TABLE IF NOT EXISTS parcelles (
    id BIGSERIAL PRIMARY KEY,
    -- Cadastral identifiers
    code_insee VARCHAR(5),
    prefixe VARCHAR(3),
    section VARCHAR(2),
    numero VARCHAR(4),
    
    -- Descriptive attributes
    nom VARCHAR(255),
    commune VARCHAR(255),
    departement VARCHAR(3),
    
    -- Numeric attributes
    surface DOUBLE PRECISION,
    contenance DOUBLE PRECISION,
    
    -- Additional metadata
    date_maj DATE,
    source VARCHAR(100),
    
    -- Geometry column (MultiPolygon in Lambert-93 EPSG:2154)
    geom geometry(MultiPolygon, 2154)
);

-- Create spatial index on geometry column
CREATE INDEX IF NOT EXISTS parcelles_geom_gist ON parcelles USING GIST (geom);

-- Create attribute indexes for common queries
CREATE INDEX IF NOT EXISTS parcelles_code_insee_idx ON parcelles (code_insee);
CREATE INDEX IF NOT EXISTS parcelles_nom_idx ON parcelles (nom);
CREATE INDEX IF NOT EXISTS parcelles_commune_idx ON parcelles (commune);
CREATE INDEX IF NOT EXISTS parcelles_section_idx ON parcelles (section);

-- Create communes table for administrative boundaries (optional)
CREATE TABLE IF NOT EXISTS communes (
    id BIGSERIAL PRIMARY KEY,
    code_insee VARCHAR(5) UNIQUE NOT NULL,
    nom VARCHAR(255) NOT NULL,
    nom_maj VARCHAR(255),
    code_dept VARCHAR(3),
    code_region VARCHAR(2),
    population INTEGER,
    superficie DOUBLE PRECISION,
    
    -- Geometry column (MultiPolygon in Lambert-93 EPSG:2154)
    geom geometry(MultiPolygon, 2154)
);

-- Create spatial index on communes geometry
CREATE INDEX IF NOT EXISTS communes_geom_gist ON communes USING GIST (geom);

-- Create index on communes identifiers
CREATE INDEX IF NOT EXISTS communes_code_insee_idx ON communes (code_insee);
CREATE INDEX IF NOT EXISTS communes_nom_idx ON communes (nom);

-- Create a view for parcelles with commune information (if both tables are populated)
CREATE OR REPLACE VIEW v_parcelles_communes AS
SELECT 
    p.*,
    c.nom as commune_nom,
    c.code_dept,
    c.population,
    ST_Area(p.geom) as surface_calculated,
    ST_Perimeter(p.geom) as perimeter
FROM parcelles p
LEFT JOIN communes c ON ST_Within(ST_Centroid(p.geom), c.geom);

-- Function to validate geometries
CREATE OR REPLACE FUNCTION validate_geometry()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT ST_IsValid(NEW.geom) THEN
        NEW.geom := ST_MakeValid(NEW.geom);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to validate geometries on insert/update
CREATE TRIGGER validate_parcelles_geom
    BEFORE INSERT OR UPDATE ON parcelles
    FOR EACH ROW
    EXECUTE FUNCTION validate_geometry();

CREATE TRIGGER validate_communes_geom
    BEFORE INSERT OR UPDATE ON communes
    FOR EACH ROW
    EXECUTE FUNCTION validate_geometry();

-- Add comments for documentation
COMMENT ON TABLE parcelles IS 'Table storing cadastral parcel data';
COMMENT ON TABLE communes IS 'Table storing commune administrative boundaries';
COMMENT ON COLUMN parcelles.geom IS 'Parcel geometry in Lambert-93 projection (EPSG:2154)';
COMMENT ON COLUMN communes.geom IS 'Commune boundary geometry in Lambert-93 projection (EPSG:2154)';

-- Utility function to get table statistics
CREATE OR REPLACE FUNCTION get_table_stats(table_name TEXT)
RETURNS TABLE (
    row_count BIGINT,
    geometry_types TEXT,
    total_area DOUBLE PRECISION,
    bbox TEXT
) AS $$
BEGIN
    RETURN QUERY
    EXECUTE format('
        SELECT 
            COUNT(*)::BIGINT as row_count,
            string_agg(DISTINCT GeometryType(geom), '', '') as geometry_types,
            SUM(ST_Area(geom)) as total_area,
            ST_AsText(ST_Envelope(ST_Collect(geom))) as bbox
        FROM %I
        WHERE geom IS NOT NULL
    ', table_name);
END;
$$ LANGUAGE plpgsql;