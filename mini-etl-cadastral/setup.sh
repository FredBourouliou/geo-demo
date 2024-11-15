#!/bin/bash

# Mini-ETL Cadastral - Script d'installation et démarrage automatique
# Usage: ./setup.sh [--sample-data] [--reset]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
# Using a smaller commune for faster download
SAMPLE_DATA_URL="https://cadastre.data.gouv.fr/data/etalab-cadastre/latest/shp/departements/21/communes/21166/cadastre-21166-parcelles-shp.zip"
SAMPLE_COMMUNE="Chenôve"

# Functions
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     Mini-ETL Cadastral - Setup Script     ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${GREEN}➤${NC} $1"
}

print_error() {
    echo -e "${RED}✗ Erreur:${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

check_command() {
    if command -v $1 &> /dev/null; then
        print_success "$1 trouvé"
        return 0
    else
        print_error "$1 non trouvé"
        return 1
    fi
}

check_dependencies() {
    print_step "Vérification des dépendances..."
    
    local missing_deps=0
    
    # Check Docker
    if ! check_command docker; then
        echo "  Installation: https://docs.docker.com/get-docker/"
        missing_deps=1
    else
        # Check if Docker daemon is running
        if ! docker info &> /dev/null; then
            print_error "Docker est installé mais le daemon n'est pas lancé"
            echo "  Sur macOS: Lancez Docker Desktop"
            echo "  Sur Linux: sudo systemctl start docker"
            missing_deps=1
        fi
    fi
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null && ! docker-compose --version &> /dev/null; then
        print_error "Docker Compose non trouvé"
        echo "  Installation: https://docs.docker.com/compose/install/"
        missing_deps=1
    else
        print_success "Docker Compose trouvé"
    fi
    
    # Check Python
    if ! check_command python3; then
        echo "  Installation: brew install python3 (macOS) ou apt install python3 (Linux)"
        missing_deps=1
    fi
    
    # Check Make
    if ! check_command make; then
        echo "  Installation: xcode-select --install (macOS) ou apt install build-essential (Linux)"
        missing_deps=1
    fi
    
    # Check GDAL (warning only)
    if ! command -v gdal-config &> /dev/null && ! command -v gdalinfo &> /dev/null; then
        print_warning "GDAL non trouvé (optionnel mais recommandé)"
        echo "  Installation: brew install gdal (macOS) ou apt install gdal-bin (Linux)"
    else
        print_success "GDAL trouvé"
    fi
    
    if [ $missing_deps -eq 1 ]; then
        print_error "Des dépendances manquent. Installez-les et relancez le script."
        exit 1
    fi
    
    echo ""
}

setup_environment() {
    print_step "Configuration de l'environnement..."
    
    # Create .env if not exists
    if [ ! -f .env ]; then
        cp .env.example .env
        print_success "Fichier .env créé"
    else
        print_warning "Fichier .env existe déjà"
    fi
    
    echo ""
}

start_database() {
    print_step "Démarrage de PostgreSQL/PostGIS..."
    
    # Stop existing containers if --reset flag
    if [[ "$*" == *"--reset"* ]]; then
        print_warning "Mode reset: suppression des conteneurs existants..."
        docker compose down -v 2>/dev/null || true
        sleep 2
    fi
    
    # Start containers
    docker compose up -d
    
    # Wait for database to be ready
    echo -n "  En attente de la base de données"
    for i in {1..30}; do
        if docker compose exec -T db pg_isready -U postgres &>/dev/null; then
            echo ""
            print_success "Base de données prête"
            break
        fi
        echo -n "."
        sleep 1
    done
    
    if ! docker compose exec -T db pg_isready -U postgres &>/dev/null; then
        print_error "La base de données ne répond pas après 30 secondes"
        exit 1
    fi
    
    echo ""
}

initialize_database() {
    print_step "Initialisation du schéma PostGIS..."
    
    # Enable PostGIS
    docker compose exec -T db psql -U postgres -d gis -c "CREATE EXTENSION IF NOT EXISTS postgis;" &>/dev/null
    
    # Run schema scripts
    docker compose exec -T db psql -U postgres -d gis -f /docker-entrypoint-initdb.d/01-enable-postgis.sql &>/dev/null
    docker compose exec -T db psql -U postgres -d gis -f /docker-entrypoint-initdb.d/02-schema.sql &>/dev/null
    
    print_success "PostGIS et schéma initialisés"
    echo ""
}

setup_python_env() {
    print_step "Configuration de l'environnement Python..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Environnement virtuel créé"
    else
        print_warning "Environnement virtuel existe déjà"
    fi
    
    # Install dependencies
    echo "  Installation des dépendances Python..."
    ./venv/bin/pip install --quiet --upgrade pip
    ./venv/bin/pip install --quiet -r requirements.txt
    
    print_success "Dépendances Python installées"
    echo ""
}

download_sample_data() {
    print_step "Préparation des données d'exemple (Côte-d'Or)..."
    
    # Check if we already have the main sample file
    if [ -f "data/cote_dor_sample.shp" ]; then
        print_warning "Données Côte-d'Or déjà présentes"
        # Create symlink for compatibility
        if [ ! -f "data/sample_shapefile.shp" ]; then
            cd data
            for ext in shp shx dbf prj cpg; do
                [ -f "cote_dor_sample.$ext" ] && ln -sf "cote_dor_sample.$ext" "sample_shapefile.$ext"
            done
            cd ..
        fi
        return 0
    fi
    
    # Download communes GeoJSON if not present
    if [ ! -f "data/communes_21.geojson" ]; then
        echo "  Téléchargement des communes de Côte-d'Or..."
        curl -sL -o data/communes_21.geojson \
            "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements/21-cote-d-or/communes-21-cote-d-or.geojson"
    fi
    
    # Generate sample parcels
    echo "  Génération des parcelles d'exemple..."
    ./venv/bin/python scripts/prepare_demo_data.py
    
    # Create symlinks for compatibility
    cd data
    for ext in shp shx dbf prj cpg; do
        [ -f "cote_dor_sample.$ext" ] && ln -sf "cote_dor_sample.$ext" "sample_shapefile.$ext"
    done
    cd ..
    
    print_success "Données d'exemple générées (201 parcelles en Côte-d'Or)"
    echo ""
}

load_data() {
    print_step "Chargement des données dans PostGIS..."
    
    if [ ! -f "data/sample_shapefile.shp" ]; then
        print_error "Aucun shapefile trouvé dans data/sample_shapefile.shp"
        print_warning "Utilisez --sample-data pour télécharger un exemple"
        return 1
    fi
    
    # Load shapefile
    ./venv/bin/python scripts/load_shapefile.py --shp data/sample_shapefile.shp --infer-commune --mode replace
    
    echo ""
}

run_queries() {
    print_step "Exécution des requêtes d'exemple..."
    
    # Update commune value if sample data was downloaded
    if [[ "$*" == *"--sample-data"* ]]; then
        export COMMUNE_VALUE="$SAMPLE_COMMUNE"
    fi
    
    ./venv/bin/python scripts/query_examples.py --stats --export
    
    echo ""
}

test_installation() {
    print_step "Test de l'installation..."
    
    # Test database connection
    if docker compose exec -T db psql -U postgres -d gis -c "SELECT COUNT(*) FROM parcelles;" &>/dev/null; then
        count=$(docker compose exec -T db psql -U postgres -d gis -t -c "SELECT COUNT(*) FROM parcelles;" | tr -d ' ')
        print_success "Base de données OK - $count parcelles chargées"
    else
        print_error "Impossible de se connecter à la base de données"
    fi
    
    # Check for output files
    if [ -f "data/outputs/commune_"*"_stats.csv" ]; then
        print_success "Fichiers de sortie générés"
    fi
    
    echo ""
}

print_next_steps() {
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           Installation terminée !          ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo "🎉 Le pipeline ETL est prêt à l'emploi !"
    echo ""
    echo "Commandes utiles :"
    echo "  ${GREEN}make psql${NC}              - Accéder à PostgreSQL"
    echo "  ${GREEN}make query${NC}             - Relancer les requêtes"
    echo "  ${GREEN}make logs${NC}              - Voir les logs Docker"
    echo "  ${GREEN}make down${NC}              - Arrêter les conteneurs"
    echo ""
    echo "Pour charger d'autres données :"
    echo "  ${GREEN}make load-custom SHP=/chemin/vers/shapefile.shp${NC}"
    echo ""
    echo "Documentation : voir README.md"
}

cleanup_on_error() {
    print_error "Une erreur est survenue. Nettoyage..."
    docker compose down 2>/dev/null || true
    exit 1
}

# Main execution
main() {
    # Trap errors
    trap cleanup_on_error ERR
    
    # Print header
    clear
    print_header
    
    # Parse arguments
    DOWNLOAD_SAMPLE=false
    RESET_MODE=false
    
    for arg in "$@"; do
        case $arg in
            --sample-data)
                DOWNLOAD_SAMPLE=true
                ;;
            --reset)
                RESET_MODE=true
                ;;
            --help|-h)
                echo "Usage: $0 [--sample-data] [--reset]"
                echo ""
                echo "Options:"
                echo "  --sample-data  Télécharge des données d'exemple (Dijon)"
                echo "  --reset        Réinitialise tout (supprime conteneurs et données)"
                echo ""
                exit 0
                ;;
        esac
    done
    
    # Run setup steps
    check_dependencies
    setup_environment
    start_database "$@"
    initialize_database
    setup_python_env
    
    # Handle sample data
    if [ "$DOWNLOAD_SAMPLE" = true ]; then
        download_sample_data
    fi
    
    # Load data if available
    if [ -f "data/sample_shapefile.shp" ]; then
        load_data
        run_queries "$@"
    else
        print_warning "Aucune donnée à charger"
        echo "  Utilisez --sample-data pour télécharger un exemple"
        echo "  Ou placez votre shapefile dans data/sample_shapefile.shp"
    fi
    
    # Test and finish
    test_installation
    print_next_steps
}

# Check if script is run from correct directory
if [ ! -f "docker-compose.yml" ]; then
    print_error "Ce script doit être exécuté depuis le dossier mini-etl-cadastral/"
    exit 1
fi

# Run main function
main "$@"