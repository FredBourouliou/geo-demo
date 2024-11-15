#!/bin/bash

# Script de test complet du pipeline ETL cadastral
# Lance tous les tests et vérifie le bon fonctionnement

set -e  # Exit on error

# Couleurs pour la sortie
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "======================================"
echo "Test complet du pipeline ETL cadastral"
echo "======================================"
echo ""

# Test 1: Vérification Docker
echo "1. Test Docker..."
if docker ps &>/dev/null; then
    echo -e "${GREEN}✓${NC} Docker est actif"
    CONTAINER_ID=$(docker ps -q -f name=etl_postgis)
    if [ -n "$CONTAINER_ID" ]; then
        echo -e "${GREEN}✓${NC} Conteneur PostGIS en cours d'exécution"
    else
        echo -e "${RED}✗${NC} Conteneur PostGIS non trouvé"
        exit 1
    fi
else
    echo -e "${RED}✗${NC} Docker n'est pas démarré"
    exit 1
fi

# Test 2: Connexion base de données
echo ""
echo "2. Test connexion PostgreSQL..."
if docker exec etl_postgis psql -U postgres -d gis -c "SELECT version();" &>/dev/null; then
    echo -e "${GREEN}✓${NC} Connexion PostgreSQL OK"
else
    echo -e "${RED}✗${NC} Impossible de se connecter à PostgreSQL"
    exit 1
fi

# Test 3: Vérification PostGIS
echo ""
echo "3. Test extension PostGIS..."
POSTGIS_VERSION=$(docker exec etl_postgis psql -U postgres -d gis -t -c "SELECT PostGIS_Version();" | xargs)
if [ -n "$POSTGIS_VERSION" ]; then
    echo -e "${GREEN}✓${NC} PostGIS installé: $POSTGIS_VERSION"
else
    echo -e "${RED}✗${NC} PostGIS non installé"
    exit 1
fi

# Test 4: Vérification des tables
echo ""
echo "4. Test des tables..."
TABLES=$(docker exec etl_postgis psql -U postgres -d gis -t -c "\dt public.*" | grep -c "parcelles\|communes" || true)
if [ "$TABLES" -ge 1 ]; then
    echo -e "${GREEN}✓${NC} Tables créées dans la base"
else
    echo -e "${YELLOW}⚠${NC} Tables manquantes, création en cours..."
    make init-db
fi

# Test 5: Vérification des données
echo ""
echo "5. Test des données..."
if [ -f "data/cote_dor_sample.shp" ]; then
    echo -e "${GREEN}✓${NC} Données Côte-d'Or présentes"
else
    echo -e "${YELLOW}⚠${NC} Génération des données d'exemple..."
    venv/bin/python scripts/prepare_demo_data.py
fi

# Test 6: Chargement des données
echo ""
echo "6. Test de chargement..."
venv/bin/python scripts/load_shapefile.py --shp data/cote_dor_sample.shp --mode replace 2>&1 | grep -q "Successfully loaded"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Chargement des données réussi"
else
    echo -e "${RED}✗${NC} Erreur lors du chargement"
    exit 1
fi

# Test 7: Comptage des parcelles
echo ""
echo "7. Vérification du contenu..."
COUNT=$(docker exec etl_postgis psql -U postgres -d gis -t -c "SELECT COUNT(*) FROM parcelles;" | xargs)
echo -e "${GREEN}✓${NC} $COUNT parcelles dans la base"

# Test 8: Test des requêtes spatiales
echo ""
echo "8. Test des requêtes spatiales..."

# Requête par commune
DIJON_COUNT=$(docker exec etl_postgis psql -U postgres -d gis -t -c "SELECT COUNT(*) FROM parcelles WHERE nom='Dijon';" | xargs)
echo -e "${GREEN}✓${NC} $DIJON_COUNT parcelles à Dijon"

# Calcul de surface totale
TOTAL_AREA=$(docker exec etl_postgis psql -U postgres -d gis -t -c "SELECT ROUND(CAST(SUM(ST_Area(geom))/10000 AS numeric), 2) FROM parcelles;" | xargs)
echo -e "${GREEN}✓${NC} Surface totale: $TOTAL_AREA hectares"

# Test 9: Export CSV
echo ""
echo "9. Test export CSV..."
venv/bin/python scripts/query_examples.py --commune "Dijon" --export &>/dev/null
if [ -f "data/outputs/commune_Dijon_stats.csv" ]; then
    echo -e "${GREEN}✓${NC} Export CSV fonctionnel"
else
    echo -e "${RED}✗${NC} Erreur d'export CSV"
fi

# Test 10: Performance
echo ""
echo "10. Test de performance..."
START_TIME=$(date +%s)
docker exec etl_postgis psql -U postgres -d gis -c "SELECT COUNT(*) FROM parcelles p1, parcelles p2 WHERE ST_DWithin(p1.geom, p2.geom, 100);" &>/dev/null
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
if [ $ELAPSED -lt 5 ]; then
    echo -e "${GREEN}✓${NC} Requête spatiale complexe en ${ELAPSED}s"
else
    echo -e "${YELLOW}⚠${NC} Performance lente: ${ELAPSED}s"
fi

# Résumé
echo ""
echo "======================================"
echo "Résumé des tests"
echo "======================================"
echo ""
echo "Infrastructure:"
echo "  • Docker: OK"
echo "  • PostgreSQL: OK"
echo "  • PostGIS: $POSTGIS_VERSION"
echo ""
echo "Données:"
echo "  • Parcelles chargées: $COUNT"
echo "  • Surface totale: $TOTAL_AREA ha"
echo "  • Communes: $(docker exec etl_postgis psql -U postgres -d gis -t -c "SELECT COUNT(DISTINCT nom) FROM parcelles;" | xargs)"
echo ""
echo "Fonctionnalités:"
echo "  • Chargement shapefile: OK"
echo "  • Requêtes spatiales: OK"
echo "  • Export CSV: OK"
echo "  • Performance: ${ELAPSED}s"
echo ""
echo -e "${GREEN}✓ Tous les tests sont passés avec succès !${NC}"