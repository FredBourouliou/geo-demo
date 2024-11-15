# Mini-ETL de données cadastrales (GeoPandas → PostGIS)

Pipeline ETL géospatial pour l'intégration de données cadastrales françaises dans PostgreSQL/PostGIS, avec requêtes spatiales et analyses statistiques.

## 🎯 Objectifs

- Charger des données shapefile (parcelles cadastrales) dans PostGIS
- Gérer les projections cartographiques (Lambert-93)
- Exécuter des requêtes spatiales (sélection par commune, calculs de surface)
- Fournir un workflow automatisé et reproductible

## 🛠 Stack Technique

- **Python 3.10+** avec GeoPandas, psycopg2, Shapely
- **PostgreSQL 16** avec extension PostGIS 3.4
- **Docker & Docker Compose** pour l'orchestration
- **Make** pour l'automatisation des tâches

## 📁 Architecture

```
mini-etl-cadastral/
├── scripts/              # Scripts Python ETL
│   ├── load_shapefile.py    # Chargement shapefile → PostGIS
│   ├── query_examples.py    # Requêtes spatiales d'exemple
│   ├── db_utils.py         # Utilitaires base de données
│   ├── geometry_utils.py   # Traitement géométries
│   └── insert_postgis.py   # Module d'insertion PostGIS
├── sql/                  # Scripts SQL
│   ├── enable_postgis.sql  # Activation PostGIS
│   └── schema.sql          # Schéma des tables
├── data/                 # Données spatiales
│   ├── README_DATA.md      # Guide données
│   └── outputs/            # Résultats requêtes
├── docker-compose.yml    # Configuration Docker
├── Makefile             # Automatisation
├── requirements.txt     # Dépendances Python
└── .env.example        # Variables d'environnement
```

## 📋 Pré-requis

### Outils système

```bash
# macOS
brew install python@3.10 gdal postgis

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3.10 python3-pip gdal-bin libgdal-dev
```

### Docker

- Docker Desktop (macOS/Windows) ou Docker Engine (Linux)
- Docker Compose v2.0+

## 🚀 Mise en route

### Installation automatique (Recommandé)

#### Option 1 : Ultra-rapide avec données réelles

```bash
# Clone et lance TOUT automatiquement avec données de Côte-d'Or
cd mini-etl-cadastral
./quick-start.sh
```

✨ Ce script installe tout et génère automatiquement **201 parcelles réalistes** basées sur les vraies limites communales de Côte-d'Or (Dijon, Chenôve, Quetigny, Talant, Longvic).

#### Option 2 : Installation flexible

```bash
cd mini-etl-cadastral

# Installation simple (sans données)
./setup.sh

# Avec génération automatique de données réelles (Côte-d'Or)
./setup.sh --sample-data

# Reset complet + installation avec données
./setup.sh --reset --sample-data
```

Le script `setup.sh` :
- ✅ Vérifie toutes les dépendances (Docker, Python, GDAL)
- ✅ Configure l'environnement (.env, venv)
- ✅ Lance PostgreSQL/PostGIS
- ✅ Initialise le schéma de base de données
- ✅ Génère des parcelles basées sur de vraies communes (optionnel)
- ✅ Charge les données et exécute les requêtes

### Installation manuelle (Alternative)

```bash
# 1. Configuration initiale
cp .env.example .env

# 2. Démarrer la base de données PostGIS
make up

# 3. Initialiser le schéma
make init-db

# 4. Créer l'environnement Python
make venv

# 5. Placer votre shapefile dans data/
# Renommer en sample_shapefile.shp (+ .shx, .dbf, .prj)

# 6. Charger les données
make load

# 7. Exécuter les requêtes d'exemple
make query
```

## 📊 Utilisation

### Chargement de données

```bash
# Chargement basique
make load

# Chargement personnalisé
make load-custom SHP=/chemin/vers/parcelles.shp TABLE=mes_parcelles

# Options avancées
./venv/bin/python scripts/load_shapefile.py \
  --shp data/cadastre.shp \
  --table parcelles \
  --srid 2154 \
  --infer-commune \
  --mode replace
```

### Requêtes spatiales

```bash
# Requêtes par défaut (commune Quetigny)
make query

# Requête sur une commune spécifique
make query-commune COMMUNE="Dijon"

# Requête personnalisée
./venv/bin/python scripts/query_examples.py \
  --commune "Chenôve" \
  --table parcelles \
  --stats \
  --export
```

### Accès base de données

```bash
# Shell PostgreSQL interactif
make psql

# Requête directe
make psql-exec SQL="SELECT COUNT(*) FROM parcelles;"

# Voir les tables
make list-tables

# Statistiques des tables
make table-stats
```

## 🔍 Exemples de requêtes SQL

### Sélection par commune

```sql
-- Parcelles d'une commune
SELECT * FROM parcelles 
WHERE nom = 'Quetigny';

-- Avec calcul de surface
SELECT 
    id, 
    section, 
    numero,
    ST_Area(geom)/10000 as surface_ha
FROM parcelles 
WHERE nom = 'Dijon'
ORDER BY surface_ha DESC;
```

### Analyses spatiales

```sql
-- Surface totale par commune
SELECT 
    nom as commune,
    COUNT(*) as nb_parcelles,
    SUM(ST_Area(geom))/10000 as surface_totale_ha
FROM parcelles
GROUP BY nom
ORDER BY surface_totale_ha DESC;

-- Parcelles dans un rayon
SELECT * FROM parcelles
WHERE ST_DWithin(
    geom, 
    ST_Transform(ST_MakePoint(5.0494, 47.3220), 2154),
    1000  -- 1km
);
```

### Jointures spatiales

```sql
-- Si table communes chargée
SELECT 
    p.id,
    p.numero,
    c.nom as commune
FROM parcelles p
JOIN communes c ON ST_Within(p.geom, c.geom);
```

## 📈 Résultats attendus

### Données d'exemple fournies

Le projet inclut un générateur de données réalistes basé sur les vraies communes de Côte-d'Or :

| Commune | Nombre de parcelles | Surface totale |
|---------|-------------------|----------------|
| Longvic | 50 parcelles | 90.58 ha |
| Dijon | 49 parcelles | 86.47 ha |
| Quetigny | 41 parcelles | 78.47 ha |
| Chenôve | 37 parcelles | 64.88 ha |
| Talant | 24 parcelles | 35.54 ha |
| **Total** | **201 parcelles** | **355.95 ha** |

### Sortie console

```
2024-01-15 10:30:45 - INFO - Loading shapefile: data/cote_dor_sample.shp
2024-01-15 10:30:45 - INFO - Read 201 features from shapefile
2024-01-15 10:30:46 - INFO - Successfully inserted 201 features into parcelles

Statistics for commune 'Dijon':
  Number of features: 49
  Total area: 86.47 ha
  Average area: 1.7648 ha
  Min area: 0.2725 ha
  Max area: 3.6403 ha
```

### Export CSV

Les résultats sont exportés dans `data/outputs/`:
- `commune_Dijon_parcelles.csv` - Liste des parcelles
- `commune_Dijon_stats.csv` - Statistiques agrégées

## 🔧 Commandes Make disponibles

| Commande | Description |
|----------|-------------|
| `make up` | Démarre PostgreSQL/PostGIS |
| `make down` | Arrête les conteneurs |
| `make init-db` | Initialise PostGIS et schéma |
| `make venv` | Crée environnement Python |
| `make load` | Charge shapefile par défaut |
| `make query` | Execute requêtes d'exemple |
| `make psql` | Ouvre shell PostgreSQL |
| `make reset` | Réinitialise tout |
| `make logs` | Affiche logs Docker |
| `make clean` | Nettoie fichiers temporaires |

## 🗺 Données compatibles

### Données d'exemple incluses

Le projet génère automatiquement des parcelles réalistes basées sur :
- **Communes de Côte-d'Or** (GeoJSON depuis france-geojson)
- **201 parcelles générées** dans 5 communes
- **Projection Lambert-93** (EPSG:2154)

Fichiers créés automatiquement :
- `data/cote_dor_sample.shp` - Parcelles d'exemple
- `data/communes_cote_dor.shp` - Limites communales
- `data/communes_21.geojson` - Source des communes

### Sources pour données réelles

- **Cadastre.gouv.fr** - Parcelles cadastrales officielles
- **data.gouv.fr** - Portail open data français
- **IGN** - BD PARCELLAIRE, BD TOPO

### Formats supportés

- Shapefile (.shp) - Format principal
- GeoJSON (.geojson)
- GeoPackage (.gpkg)
- Tout format GDAL/OGR

## ⚠️ Limites et considérations

### Limites actuelles

- Projection par défaut Lambert-93 (EPSG:2154)
- Optimisé pour données françaises
- Tables communes optionnelle (jointures spatiales)

### Améliorations possibles

1. **API REST** - Ajouter FastAPI pour exposer endpoints
   ```python
   GET /api/commune/{code_insee}
   GET /api/parcelle/{id}
   POST /api/spatial/within
   ```

2. **Tests unitaires** - Coverage des modules geometry_utils
   ```bash
   pytest tests/ --cov=scripts
   ```

3. **Monitoring** - Métriques de performance PostGIS
   ```sql
   SELECT * FROM pg_stat_user_tables;
   ```

4. **Cache** - Redis pour requêtes fréquentes

5. **Visualisation** - Intégration QGIS ou web mapping

## 🐛 Troubleshooting

### Erreur de connexion

```bash
# Vérifier que Docker est lancé
docker ps

# Vérifier les logs
make logs

# Tester la connexion
make test-connection
```

### Problème de projection

```python
# Forcer la projection si .prj absent
gdf = gpd.read_file('data/shapefile.shp')
gdf.set_crs('EPSG:2154', inplace=True, allow_override=True)
```

### Performance

```sql
-- Mettre à jour les statistiques
ANALYZE parcelles;

-- Vérifier les index
\di parcelles*
```

## 📄 Licence

MIT License - Voir LICENSE

**⚠️ Attention**: Les données cadastrales peuvent avoir leurs propres licences. Vérifiez les conditions d'utilisation des données source (généralement Licence Ouverte 2.0 pour les données publiques françaises).

## 🤝 Contribution

Les contributions sont bienvenues ! Merci de :

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amelioration`)
3. Commit (`git commit -am 'Ajout de fonctionnalité'`)
4. Push (`git push origin feature/amelioration`)
5. Créer une Pull Request

## 📞 Support

Pour les questions et problèmes :
- Ouvrir une issue GitHub
- Documentation PostGIS : https://postgis.net/docs/
- Documentation GeoPandas : https://geopandas.org/

---

*Projet développé pour démonstration de compétences en SIG et data engineering géospatial.*