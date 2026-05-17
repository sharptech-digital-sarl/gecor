# Dev tools (GECOR backend)

Scripts ponctuels utilisés pendant le développement / diagnostic. **À ne pas
livrer en production** : aucun de ces scripts n'est appelé par l'API ou par les
tâches Celery.

| Fichier                          | Rôle                                                                      |
| -------------------------------- | ------------------------------------------------------------------------- |
| `diagnose_mfa.py`                | Diagnostic complet de la configuration TOTP d'un utilisateur.             |
| `fix_mfa_secret_mismatch.py`     | Resynchronise `mfa_secret` quand le client OTP a divergé.                 |
| `generate_mfa_qr.py`             | Génère un QR code MFA en local pour test.                                 |
| `generate_qr_simple.py`          | Variante simplifiée du précédent.                                         |
| `verify_mfa_config.py`           | Affiche la conf MFA effective.                                            |
| `test_mfa_activation.py`         | Smoke-test activation TOTP via l'API.                                     |
| `test_mfa_complete.py`           | Smoke-test complet enroll → activate → verify.                            |
| `test_mfa_helper.py`             | Helper CLI pour générer un code TOTP depuis un secret base32.             |
| `test_mfa_verify.py`             | Smoke-test du flux verify-only.                                           |
| `check_tables.sql`               | Vérifie la présence des tables critiques (compatible psql).               |
| `fix_pgadmin_connection.ps1`     | Aide PowerShell pour rétablir la connexion pgAdmin sur Windows.           |
| `remove_media_from_git.ps1`      | Nettoie l'historique git des fichiers `media/` (Windows).                 |

Utilisation :

```bash
cd backend
python dev-tools/diagnose_mfa.py <username>
python dev-tools/test_mfa_helper.py <base32_secret>
```

Pour la documentation de dépannage associée, voir
[`backend/docs/troubleshooting/`](../docs/troubleshooting/).
