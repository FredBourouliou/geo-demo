# 🗺️ GeoDemo - Pipeline ETL Géospatial

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.4-green.svg)](https://postgis.net/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)

> **Pipeline ETL automatisé pour l'intégration et l'analyse de données cadastrales françaises dans PostgreSQL/PostGIS**

## 🎯 Présentation

Ce projet propose une solution complète pour charger, transformer et analyser des données géospatiales cadastrales. Développé avec une architecture modulaire, il permet d'intégrer facilement des données shapefile dans une base PostGIS et d'effectuer des analyses spatiales avancées.

### ✨ Fonctionnalités clés

- 🔄 **ETL automatisé** : Chargement de shapefiles vers PostGIS en une commande
- 📊 **Analyses spatiales** : Requêtes par commune, calculs de surface, statistiques
- 🗺️ **Support Lambert-93** : Gestion native de la projection française (EPSG:2154)
- 🎲 **Données d'exemple** : 201 parcelles réalistes basées sur 5 communes de Côte-d'Or
- 🐳 **Docker-ready** : Déploiement instantané avec Docker Compose
- 📈 **Export CSV** : Génération de rapports et statistiques

## 🚀 Démarrage rapide

### Installation en 30 secondes

```bash
# Clone du repository
git clone https://github.com/FredBourouliou/geo-demo.git
cd geo-demo/mini-etl-cadastral

# Lancement automatique avec données d'exemple
./quick-start.sh
```

C'est tout ! Le script installe automatiquement :
- ✅ PostgreSQL/PostGIS dans Docker
- ✅ Environnement Python avec toutes les dépendances
- ✅ 201 parcelles cadastrales d'exemple
- ✅ Exécution des requêtes de démonstration

## 📁 Structure du projet

```
geo-demo/
└── mini-etl-cadastral/
    ├── scripts/              # Modules Python ETL
    │   ├── load_shapefile.py    # Chargement des données
    │   ├── query_examples.py    # Requêtes spatiales
    │   └── geometry_utils.py    # Traitement géométrique
    ├── data/                 # Données géospatiales
    │   ├── cote_dor_sample.*    # 201 parcelles d'exemple
    │   └── outputs/             # Résultats CSV
    ├── sql/                  # Scripts base de données
    ├── docker-compose.yml    # Configuration Docker
    └── Makefile             # Automatisation
```

## 💻 Utilisation

### Chargement de données

```bash
# Charger vos propres données
make load-custom SHP=/chemin/vers/parcelles.shp TABLE=ma_table

# Ou directement avec le script Python
./venv/bin/python scripts/load_shapefile.py \
  --shp data/cadastre.shp \
  --table parcelles \
  --mode replace
```

### Requêtes spatiales

```bash
# Analyser une commune spécifique
make query-commune COMMUNE="Dijon"

# Requête SQL directe
make psql-exec SQL="SELECT COUNT(*) FROM parcelles WHERE nom='Quetigny';"
```

### Exemples de requêtes SQL

```sql
-- Surface totale par commune
SELECT 
    nom as commune,
    COUNT(*) as nb_parcelles,
    SUM(ST_Area(geom))/10000 as surface_ha
FROM parcelles
GROUP BY nom
ORDER BY surface_ha DESC;

-- Parcelles dans un rayon de 1km
SELECT * FROM parcelles
WHERE ST_DWithin(
    geom, 
    ST_Transform(ST_MakePoint(5.0494, 47.3220), 2154),
    1000
);
```

## 📊 Données d'exemple fournies

Le projet inclut un jeu de données réaliste généré automatiquement :

| Commune | Parcelles | Surface totale |
|---------|-----------|----------------|
| Longvic | 50 | 90.58 ha |
| Dijon | 49 | 86.47 ha |
| Quetigny | 41 | 78.47 ha |
| Chenôve | 37 | 64.88 ha |
| Talant | 24 | 35.54 ha |
| **Total** | **201** | **355.95 ha** |

## 🛠️ Technologies utilisées

- **Python 3.10+** : GeoPandas, Shapely, psycopg2
- **PostgreSQL 16** avec extension **PostGIS 3.4**
- **Docker & Docker Compose** pour l'orchestration
- **GDAL/OGR** pour la manipulation des données géospatiales

## 📋 Prérequis

- Docker Desktop (macOS/Windows) ou Docker Engine (Linux)
- Python 3.10+ (pour utilisation locale)
- 2GB d'espace disque disponible

## 🔧 Commandes Make disponibles

| Commande | Description |
|----------|-------------|
| `make up` | Lance PostgreSQL/PostGIS |
| `make init-db` | Initialise le schéma |
| `make load` | Charge les données d'exemple |
| `make query` | Exécute les requêtes de démo |
| `make psql` | Ouvre un shell PostgreSQL |
| `make reset` | Réinitialise tout |

## 📈 Cas d'usage

Ce pipeline est idéal pour :
- 🏗️ **Urbanisme** : Analyse de l'occupation des sols
- 🏛️ **Collectivités** : Gestion du patrimoine foncier
- 📊 **Data Science** : Analyses géospatiales avancées
- 🎓 **Formation** : Apprentissage de PostGIS et GeoPandas

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :
- 🐛 Signaler des bugs via les [Issues](https://github.com/FredBourouliou/geo-demo/issues)
- 💡 Proposer des améliorations
- 🔧 Soumettre des Pull Requests

## 👤 Auteur

**Frédéric Bourouliou**
- GitHub: [@FredBourouliou](https://github.com/FredBourouliou)

---

⭐ Si ce projet vous est utile, n'hésitez pas à lui donner une étoile sur GitHub !

## 🔗 Liens utiles

- [Documentation PostGIS](https://postgis.net/docs/)
- [GeoPandas Documentation](https://geopandas.org/)
- [Données cadastrales françaises](https://cadastre.data.gouv.fr/)