-- ============================================
-- Script de Diagnostic pour pgAdmin
-- Exécutez ce script dans pgAdmin après vous être connecté à la base fpi_connect
-- ============================================

-- 1. Informations de connexion actuelle
SELECT 
    'Connexion actuelle' as info,
    current_database() as database,
    current_user as user,
    version() as postgres_version;

-- 2. Liste de toutes les bases de données disponibles
SELECT 
    'Bases de données disponibles' as info,
    datname as database_name,
    pg_size_pretty(pg_database_size(datname)) as size
FROM pg_database 
WHERE datistemplate = false
ORDER BY datname;

-- 3. Vérifier si le schéma public existe
SELECT 
    'Schémas disponibles' as info,
    schema_name
FROM information_schema.schemata
WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
ORDER BY schema_name;

-- 4. Liste de TOUTES les tables dans le schéma public
SELECT 
    'Tables dans le schéma public' as info,
    table_schema,
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- 5. Compter les tables
SELECT 
    'Nombre de tables' as info,
    COUNT(*) as total_tables
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE';

-- 6. Vérifier spécifiquement les tables MFA et Refresh Token
SELECT 
    'Tables MFA/Refresh Token' as info,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'mfa_sessions'
        ) THEN '✓ Existe'
        ELSE '✗ Manquante'
    END as mfa_sessions,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'session_tokens'
        ) THEN '✓ Existe'
        ELSE '✗ Manquante'
    END as session_tokens,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'users'
        ) THEN '✓ Existe'
        ELSE '✗ Manquante'
    END as users;

-- 7. Vérifier les colonnes MFA dans la table users
SELECT 
    'Colonnes MFA dans users' as info,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name = 'users'
AND column_name IN ('is_mfa_enabled', 'mfa_secret', 'mfa_temp_secret')
ORDER BY column_name;

-- 8. Structure complète de la table mfa_sessions (si elle existe)
SELECT 
    'Structure mfa_sessions' as info,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name = 'mfa_sessions'
ORDER BY ordinal_position;

-- 9. Structure complète de la table session_tokens (si elle existe)
SELECT 
    'Structure session_tokens' as info,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
AND table_name = 'session_tokens'
ORDER BY ordinal_position;

-- 10. Vérifier l'état des migrations Alembic
SELECT 
    'État des migrations Alembic' as info,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'alembic_version'
        ) THEN '✓ Table alembic_version existe'
        ELSE '✗ Table alembic_version manquante - Les migrations n''ont peut-être pas été exécutées OU vous êtes connecté à la mauvaise base de données'
    END as migration_status;

-- Si la table alembic_version existe, afficher la version actuelle
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'alembic_version'
    ) THEN
        PERFORM 1; -- Table exists, will query it below
    ELSE
        RAISE NOTICE 'Table alembic_version n''existe pas. Vérifiez que vous êtes connecté à la bonne base de données (fpi_connect dans Docker)';
    END IF;
END $$;

-- Afficher la version si la table existe
SELECT 
    'Version de migration actuelle' as info,
    version_num as current_revision
FROM alembic_version
WHERE EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name = 'alembic_version'
);

-- 11. Vérifier les permissions de l'utilisateur actuel
SELECT 
    'Permissions sur le schéma public' as info,
    grantee,
    privilege_type
FROM information_schema.role_table_grants
WHERE table_schema = 'public'
AND grantee = current_user
GROUP BY grantee, privilege_type
ORDER BY privilege_type;

-- 12. Statistiques sur les tables (nombre de lignes)
SELECT 
    'Statistiques des tables' as info,
    schemaname,
    tablename,
    n_live_tup as row_count,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY tablename;
