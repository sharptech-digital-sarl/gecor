# Troubleshooting

Notes de dépannage rédigées au fil de l'eau pendant le développement. Elles ne
font pas partie de la documentation officielle (voir [`docs/`](../../../docs/)
à la racine du dépôt) mais peuvent dépanner ponctuellement.

## MFA / TOTP

- [`MFA_CONFIGURATION_GUIDE.md`](MFA_CONFIGURATION_GUIDE.md) — paramétrage initial.
- [`MFA_TESTING_GUIDE.md`](MFA_TESTING_GUIDE.md) — recette manuelle du flux.
- [`MFA_ACTIVATION_TROUBLESHOOT.md`](MFA_ACTIVATION_TROUBLESHOOT.md) — diagnostic activation.
- [`QUICK_FIX_MFA_ACTIVATION.md`](QUICK_FIX_MFA_ACTIVATION.md), [`QUICK_FIX_MFA_VERIFY.md`](QUICK_FIX_MFA_VERIFY.md).
- [`LINK_MFA_AUTHENTICATOR.md`](LINK_MFA_AUTHENTICATOR.md), [`VERIFIER_MFA_GOOGLE.md`](VERIFIER_MFA_GOOGLE.md).
- [`MFA_SCRIPTS_README.md`](MFA_SCRIPTS_README.md) — scripts MFA (déplacés dans `backend/dev-tools/`).

## Base de données / pgAdmin

- [`FIX_DATABASE_CONNECTION.md`](FIX_DATABASE_CONNECTION.md) — résolution DSN PostgreSQL.
- [`TROUBLESHOOT_PGADMIN.md`](TROUBLESHOOT_PGADMIN.md), [`QUICK_FIX_PGADMIN.md`](QUICK_FIX_PGADMIN.md).

Les scripts associés se trouvent dans [`backend/dev-tools/`](../../dev-tools/).
