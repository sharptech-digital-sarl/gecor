# Modèles de déploiement GECOR

Fichiers à copier puis adapter pour un déploiement on-premise.

| Fichier                                          | Destination suggérée                                 |
| ------------------------------------------------ | ---------------------------------------------------- |
| `nginx.conf.example`                             | `/etc/nginx/sites-available/gecor.conf`             |
| `gecor-gunicorn.service.example`                 | `/etc/systemd/system/gecor-api.service`             |
| `gecor-celery-worker.service.example`            | `/etc/systemd/system/gecor-celery-worker.service`   |
| `gecor-celery-beat.service.example`              | `/etc/systemd/system/gecor-celery-beat.service`     |

Voir [`docs/installation.md`](../docs/installation.md) pour la procédure
complète (utilisateur de service, chemins, certificats TLS).

## Checklist post-installation

- [ ] `sudo nginx -t` puis `sudo systemctl reload nginx`
- [ ] `sudo systemctl status gecor-api gecor-celery-worker gecor-celery-beat`
- [ ] `curl https://<hostname>/health` renvoie `{"status":"healthy", ...}`
- [ ] `journalctl -u gecor-api -n 100` ne contient aucune erreur de démarrage
- [ ] `bash scripts/backup_postgres.sh` exécutable et planifié dans cron
- [ ] Création du compte master initial via `python -m app.scripts.create_admin`
- [ ] Test du flux courrier complet (cf. [`docs/recette.md`](../docs/recette.md))
