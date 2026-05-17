# Guide de Dépannage : Tables non visibles dans pgAdmin

Ce guide vous aide à résoudre le problème lorsque les tables ne sont pas visibles dans pgAdmin malgré une connexion réussie.

## 🔍 Diagnostic Rapide

### 1. Vérifier la Base de Données Connectée

Dans pgAdmin, vérifiez que vous êtes connecté à la **bonne base de données** :

1. Dans l'arborescence de pgAdmin, développez :
   ```
   Servers → [Votre Serveur] → Databases → fpi_connect
   ```

2. **Important** : Assurez-vous que vous regardez dans `fpi_connect` et non dans `postgres` ou une autre base.

3. Cliquez avec le bouton droit sur `fpi_connect` → **Properties** → Vérifiez le nom.

### 2. Vérifier les Informations de Connexion

Selon votre `docker-compose.yml`, les informations de connexion sont :

| Paramètre | Valeur |
|-----------|--------|
| **Host** | `localhost` (depuis Windows) |
| **Port** | `5432` |
| **Database** | `fpi_connect` |
| **Username** | `fpi-admin` |
| **Password** | `Fpi-c05b6q#` |

**⚠️ Attention** : Le caractère `#` dans le mot de passe doit être encodé en URL comme `%23` dans la DATABASE_URL, mais dans pgAdmin, utilisez le caractère `#` directement.

### 3. Vérifier si les Migrations ont été Exécutées

#### Option A : Via Docker (Recommandé)

```bash
# Vérifier l'état des migrations
docker-compose exec backend alembic current

# Si aucune migration n'est appliquée, exécutez :
docker-compose exec backend alembic upgrade head

# Vérifier les logs pour voir si les migrations ont été exécutées
docker-compose logs backend | grep -i migration
```

#### Option B : Via pgAdmin (SQL Query)

Connectez-vous à la base `fpi_connect` dans pgAdmin et exécutez :

```sql
-- Vérifier si la table alembic_version existe (indique que les migrations ont été exécutées)
SELECT * FROM alembic_version;

-- Vérifier toutes les tables existantes
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public'
ORDER BY table_name;

-- Vérifier spécifiquement les tables MFA
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('users', 'mfa_sessions', 'session_tokens');
```

### 4. Vérifier le Schéma (Schema)

Par défaut, les tables sont créées dans le schéma `public`. Vérifiez que vous regardez dans le bon schéma :

1. Dans pgAdmin, développez :
   ```
   fpi_connect → Schemas → public → Tables
   ```

2. Si vous ne voyez pas le schéma `public`, créez-le :
   ```sql
   CREATE SCHEMA IF NOT EXISTS public;
   ```

### 5. Rafraîchir l'Affichage dans pgAdmin

Parfois, pgAdmin ne rafraîchit pas automatiquement :

1. Cliquez avec le bouton droit sur `Tables` → **Refresh**
2. Ou appuyez sur `F5` pour rafraîchir
3. Ou fermez et rouvrez la connexion au serveur

## 🔧 Solutions par Scénario

### Scénario 1 : Les Migrations n'ont pas été Exécutées

**Symptômes** :
- Aucune table n'est visible
- La table `alembic_version` n'existe pas

**Solution** :

```bash
# Exécuter les migrations
docker-compose exec backend alembic upgrade head

# Vérifier que les migrations sont appliquées
docker-compose exec backend alembic current
```

### Scénario 2 : Connexion à la Mauvaise Base de Données

**Symptômes** :
- Vous voyez d'autres tables mais pas celles de FPI-Connect
- Vous êtes connecté à `postgres` au lieu de `fpi_connect`

**Solution** :

1. Dans pgAdmin, créez une nouvelle connexion ou modifiez l'existante :
   - **Name** : FPI Connect DB
   - **Host** : localhost
   - **Port** : 5432
   - **Maintenance database** : fpi_connect
   - **Username** : fpi-admin
   - **Password** : Fpi-c05b6q#

2. Connectez-vous spécifiquement à `fpi_connect`

### Scénario 3 : Connexion à une Instance PostgreSQL Locale au lieu de Docker

**Symptômes** :
- Vous vous connectez à `localhost:5432` mais c'est une instance PostgreSQL locale
- Les tables n'existent pas car les migrations ont été exécutées dans Docker

**Solution** :

Vérifiez quelle instance PostgreSQL écoute sur le port 5432 :

```powershell
# Sur Windows PowerShell
netstat -ano | findstr :5432
```

Si vous avez une instance PostgreSQL locale qui entre en conflit :

1. **Option A** : Arrêtez l'instance locale
   ```powershell
   # Arrêter le service PostgreSQL local
   Stop-Service postgresql-x64-XX  # Remplacez XX par votre version
   ```

2. **Option B** : Changez le port dans docker-compose.yml
   ```yaml
   ports:
     - "5433:5432"  # Utilisez 5433 au lieu de 5432
   ```
   Puis dans pgAdmin, utilisez le port `5433`

### Scénario 4 : Problème de Permissions

**Symptômes** :
- Vous pouvez vous connecter mais ne voyez pas les tables
- Erreur de permissions dans les logs

**Solution** :

Vérifiez les permissions de l'utilisateur :

```sql
-- Dans pgAdmin, exécutez cette requête
SELECT 
    grantee, 
    table_schema, 
    table_name, 
    privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'fpi-admin'
AND table_schema = 'public';
```

Si l'utilisateur n'a pas les permissions, accordez-les :

```sql
-- Accorder toutes les permissions sur le schéma public
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "fpi-admin";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "fpi-admin";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "fpi-admin";
```

## 📋 Checklist de Vérification

Exécutez cette checklist dans l'ordre :

- [ ] **1. Docker est démarré**
  ```bash
  docker-compose ps
  ```
  Vérifiez que les conteneurs `fpi-connect-db` et `fpi-connect-backend` sont en cours d'exécution.

- [ ] **2. Connexion pgAdmin correcte**
  - Host: `localhost`
  - Port: `5432`
  - Database: `fpi_connect` (pas `postgres`)
  - Username: `fpi-admin`
  - Password: `Fpi-c05b6q#`

- [ ] **3. Migrations exécutées**
  ```bash
  docker-compose exec backend alembic current
  ```
  Devrait afficher une révision (ex: `add_mfa_and_refresh_sessions`)

- [ ] **4. Tables existent dans la base**
  ```sql
  SELECT table_name FROM information_schema.tables 
  WHERE table_schema = 'public' 
  ORDER BY table_name;
  ```
  Devrait lister au moins : `alembic_version`, `users`, `mfa_sessions`, `session_tokens`

- [ ] **5. Schéma public visible**
  Dans pgAdmin : `fpi_connect → Schemas → public → Tables`

- [ ] **6. Rafraîchissement effectué**
  Clic droit sur `Tables` → Refresh (ou F5)

## 🛠️ Script de Vérification SQL

Exécutez ce script SQL dans pgAdmin pour diagnostiquer :

```sql
-- 1. Vérifier la connexion actuelle
SELECT current_database(), current_user, version();

-- 2. Lister toutes les bases de données
SELECT datname FROM pg_database WHERE datistemplate = false;

-- 3. Vérifier les tables dans le schéma public
SELECT 
    table_schema,
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- 4. Vérifier les colonnes MFA dans users
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name = 'users'
AND column_name IN ('is_mfa_enabled', 'mfa_secret', 'mfa_temp_secret')
ORDER BY column_name;

-- 5. Vérifier la table mfa_sessions
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name = 'mfa_sessions'
ORDER BY column_name;

-- 6. Vérifier les migrations Alembic
SELECT * FROM alembic_version;
```

## 🚀 Solution Rapide (Tout Réinitialiser)

Si rien ne fonctionne, réinitialisez complètement :

```bash
# 1. Arrêter les conteneurs
docker-compose down

# 2. Supprimer le volume de données (⚠️ SUPPRIME TOUTES LES DONNÉES)
docker volume rm fpi-connect_postgres_data

# 3. Redémarrer les conteneurs (créera une nouvelle base)
docker-compose up -d

# 4. Attendre que la base soit prête
docker-compose logs -f db

# 5. Les migrations s'exécutent automatiquement au démarrage du backend
# Vérifiez les logs :
docker-compose logs backend | grep -i migration
```

## 📝 Vérification Finale

Une fois que tout est configuré, vous devriez voir ces tables dans pgAdmin :

```
fpi_connect
  └── Schemas
      └── public
          └── Tables
              ├── alembic_version
              ├── appointments
              ├── mail_documents
              ├── mfa_sessions          ← Table MFA
              ├── notifications
              ├── session_tokens         ← Table Refresh Token
              ├── signatures
              ├── users                  ← Avec colonnes MFA
              └── visitors
```

## 🆘 Si le Problème Persiste

1. **Vérifiez les logs Docker** :
   ```bash
   docker-compose logs backend | tail -50
   docker-compose logs db | tail -50
   ```

2. **Vérifiez la connexion depuis le conteneur** :
   ```bash
   docker-compose exec backend python -c "from app.core.database import engine; print(engine.url)"
   ```

3. **Testez la connexion directement** :
   ```bash
   docker-compose exec db psql -U fpi-admin -d fpi_connect -c "\dt"
   ```

4. **Vérifiez les variables d'environnement** :
   ```bash
   docker-compose exec backend env | grep DATABASE
   ```

---

**Note** : Si vous utilisez pgAdmin pour vous connecter à une base de données Docker, assurez-vous que :
- Docker Desktop est en cours d'exécution
- Le conteneur `fpi-connect-db` est démarré
- Le port `5432` n'est pas utilisé par une autre instance PostgreSQL
