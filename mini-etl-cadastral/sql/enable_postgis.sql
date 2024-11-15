-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable additional useful extensions
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;

-- Verify PostGIS installation
SELECT PostGIS_Version();