# Maintenance GECOR

## 1. Sauvegardes

### 1.1 Script fourni

`scripts/backup_postgres.sh` réalise un `pg_dump` au format custom compressé,
puis applique une rotation **30 jours**. Il lit la connexion depuis `DATABASE_URL`
(fichier `.env` racine ou `backend/.env`).

```bash
bash scripts/backup_postgres.sh
# génère : /var/backups/gecor/gecor_YYYYMMDD-HHMM.dump.gz
```

Variables utiles :

| Variable                 | Valeur par défaut         | Effet                                 |
| ------------------------ | ------------------------- | ------------------------------------- |
| `BACKUP_DIR`             | `/var/backups/gecor`      | Destination des dumps.                |
| `BACKUP_RETENTION_DAYS`  | `30`                      | Conservation rotative.                |
| `DATABASE_URL`           | depuis `.env`             | URL postgres (peut être surchargée).  |

### 1.2 Restauration

```bash
bash scripts/restore_postgres.sh /var/backups/gecor/gecor_20260517-0230.dump.gz
```

Important : la restauration **drop puis recrée** les objets de la base ; à
utiliser sur une instance de récupération distincte avant tout passage en prod.

### 1.3 Sauvegarde du stockage fichiers

Si `STORAGE_TYPE=local`, sauvegarder également le répertoire `STORAGE_PATH`
(p. ex. `/opt/gecor/storage`). Un `rsync` quotidien vers un NAS est suffisant :

```bash
rsync -a --delete /opt/gecor/storage/ /mnt/nas/gecor/storage/
```

## 2. Migrations Alembic

```bash
cd backend
alembic upgrade head             # applique
alembic history --verbose        # historique
alembic current                  # version courante
alembic downgrade -1             # annule la dernière (rare en production !)
```

Toute nouvelle modification de modèle SQLAlchemy doit s'accompagner d'une
migration :

```bash
alembic revision --autogenerate -m "ma_modif"
# Relire le fichier généré, ajuster, puis :
alembic upgrade head
```

## 3. Suivi des logs

- Logs applicatifs Gunicorn : `journalctl -u gecor-api -f`.
- Logs Celery : `journalctl -u gecor-celery-worker -f`.
- Logs Nginx : `/var/log/nginx/gecor.access.log`, `gecor.error.log`.
- Logs audit applicatif : table `audit_events` (page `/app/admin/audit`).

## 4. Surveillance

Endpoints de santé :

- `GET /health` — état applicatif (renvoie `{"status":"healthy"}`).
- `GET /api/v1/dashboard/kpi` — quand l'utilisateur authentifié charge le tableau
  de bord ; peut servir de monitoring fonctionnel synthétique.

Intégration suggérée :

- Sonde HTTP (Nagios, Zabbix, Uptime Kuma) sur `/health` toutes les minutes.
- Alerte si la table `audit_events` n'enregistre plus rien depuis > 30 min
  (signe d'un blocage applicatif).

## 5. Réinitialisation utilisateur master

```bash
# Réinitialise au mot de passe par défaut PASSWORD_RESET_POLICY_DEFAULT
docker compose exec backend python -m app.scripts.create_admin --reset --username admin
```

L'utilisateur recevra `password_must_change=True` et devra changer le mot de
passe au prochain login.

## 6. Purge et corbeille

- Les demandes de suppression (`DeletionRequest`) sont visibles dans
  `/app/deletion-requests` (rôle ayant la permission `deletion_requests.review`).
- Le purge réel (suppression physique du fichier + ligne mail) est réalisé
  par `app/services/mail_purge_service.py` ; il est appelé automatiquement à la
  validation de la demande.

## 7. Rotation des secrets

- `SECRET_KEY` : rotation = invalide **tous** les tokens JWT et refresh.
  Prévenir les utilisateurs, planifier une fenêtre.
- `VAPID_*` : rotation = invalide toutes les souscriptions Push existantes ;
  prévoir la régénération côté navigateurs.
- `GOOGLE_CLIENT_SECRET` : rotation = chaque utilisateur ayant connecté Google
  Calendar devra re-consentir.

## 8. Mises à jour de dépendances

- Backend Python : `pip-compile` (recommandé) ou bump manuel de `requirements.txt`,
  puis lancer `pytest` et `alembic upgrade head` sur un dump récent.
- Frontend : `npm outdated` puis `npm update`. Avant déploiement, lancer
  `npm run build` et tester un parcours complet en pré-prod.
