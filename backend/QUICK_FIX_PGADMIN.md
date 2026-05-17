# Solution Rapide : Tables non visibles dans pgAdmin

## 🔴 Problème Identifié

Vous avez **deux instances PostgreSQL** qui utilisent le port 5432 :
1. **Instance PostgreSQL locale** (Windows) - PID 7028
2. **Instance Docker** (conteneur) - PID 10784

pgAdmin se connecte probablement à l'instance **locale** qui n'a pas les tables, alors que les tables existent dans l'instance **Docker**.

## ✅ Solution Rapide

### Option 1 : Arrêter PostgreSQL Local (Recommandé)

Si vous n'avez pas besoin de l'instance PostgreSQL locale :

```powershell
# Exécutez en tant qu'administrateur
Get-Service | Where-Object { $_.Name -like "*postgresql*" } | Stop-Service -Force
```

Ou utilisez le script fourni :
```powershell
# Exécutez en tant qu'administrateur
.\fix_pgadmin_connection.ps1
```

### Option 2 : Changer le Port Docker

Si vous avez besoin des deux instances, changez le port Docker :

1. **Modifiez `docker-compose.yml`** :
```yaml
db:
  ports:
    - "5433:5432"  # Changez de 5432 à 5433
```

2. **Redémarrez Docker** :
```bash
docker-compose down
docker-compose up -d
```

3. **Dans pgAdmin**, utilisez le port **5433** au lieu de 5432

## 🔍 Vérification

### 1. Vérifier que Docker PostgreSQL fonctionne

```bash
# Vérifier les tables dans Docker
docker-compose exec db psql -U fpi-admin -d fpi_connect -c "\dt"
```

Vous devriez voir :
- `alembic_version`
- `users`
- `mfa_sessions`
- `session_tokens`
- Et d'autres tables...

### 2. Vérifier la Connexion pgAdmin

**Informations de connexion CORRECTES** :

| Paramètre | Valeur |
|-----------|--------|
| **Host** | `localhost` |
| **Port** | `5432` (ou `5433` si vous avez changé) |
| **Database** | `fpi_connect` ⚠️ **IMPORTANT** |
| **Username** | `fpi-admin` |
| **Password** | `Fpi-c05b6q#` |

**⚠️ CRUCIAL** : Assurez-vous que :
- Vous êtes connecté à la base `fpi_connect` (pas `postgres`)
- Le port correspond à celui de Docker (5432 ou 5433)
- Docker Desktop est en cours d'exécution
- Le conteneur `fpi-connect-db` est démarré

### 3. Test Rapide dans pgAdmin

Exécutez cette requête dans pgAdmin :

```sql
-- Vérifier la base de données actuelle
SELECT current_database();

-- Devrait retourner : fpi_connect

-- Lister les tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public'
ORDER BY table_name;
```

Si vous voyez les tables, c'est bon ! Si non, vous êtes connecté à la mauvaise base.

## 🎯 Étapes Suivantes

1. **Arrêtez PostgreSQL local** OU **changez le port Docker**
2. **Redémarrez Docker** si vous avez changé le port
3. **Reconnectez-vous dans pgAdmin** avec les bonnes informations
4. **Rafraîchissez** l'arborescence (F5 ou clic droit → Refresh)
5. **Naviguez** vers : `fpi_connect → Schemas → public → Tables`

## 📝 Checklist

- [ ] PostgreSQL local arrêté OU port Docker changé
- [ ] Docker Desktop en cours d'exécution
- [ ] Conteneur `fpi-connect-db` démarré
- [ ] Connexion pgAdmin à `fpi_connect` (pas `postgres`)
- [ ] Port correct (5432 ou 5433)
- [ ] Arborescence rafraîchie dans pgAdmin

Une fois ces étapes effectuées, vous devriez voir toutes les tables ! 🎉
