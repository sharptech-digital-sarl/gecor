# Migration vers un monorepo GECOR

Ce document décrit une migration **frontend + backend** vers un dépôt unique afin d'améliorer l'édition locale, la revue de code et la cohérence des contrats API.

## Structure cible

```text
gecor/
  apps/
    frontend/   # ce dépôt (actuel)
    backend/    # dépôt API
  docs/
  docker-compose.yml
  README.md
  .editorconfig
  .gitignore
  CODEOWNERS
```

## Plan en 2 PRs

### PR 1 — Structure monorepo

1. Créer un nouveau dépôt racine `gecor`.
2. Importer l'historique `gecor-frontend` dans `apps/frontend`.
3. Importer l'historique backend dans `apps/backend`.
4. Ajouter `README.md`, `docker-compose.yml`, `CODEOWNERS` et conventions communes.
5. Mettre en place une CI déclenchée par chemins (`apps/frontend/**`, `apps/backend/**`).

### PR 2 — Intégration API côté frontend

1. Centraliser les variables d'environnement frontend (`VITE_API_URL`, environnements dev/staging/prod).
2. Remplacer les URLs API codées en dur par la configuration centralisée.
3. Introduire ou consolider un client HTTP commun (`src/services/api.ts` + gestion auth/erreurs).
4. Exposer/consommer un schéma OpenAPI côté backend pour générer les types côté frontend.
5. Ajouter un check CI qui garantit la synchronisation du client généré.

## Commandes Git recommandées

Exemple avec `git subtree` (préserve l'historique et reste simple côté GitHub/GitLab) :

```bash
# dans un nouveau dépôt vide gecor

git remote add frontend <URL_GECOR_FRONTEND>
git fetch frontend
git subtree add --prefix=apps/frontend frontend main

git remote add backend <URL_GECOR_BACKEND>
git fetch backend
git subtree add --prefix=apps/backend backend main
```

> Alternative : `git filter-repo` + merge d'historiques réécrits, utile si vous voulez nettoyer des fichiers avant import.

## Checklist de revue

- [ ] Les PR frontend n'exécutent que la CI frontend.
- [ ] Les PR backend n'exécutent que la CI backend.
- [ ] `CODEOWNERS` route correctement les reviewers.
- [ ] Les variables d'environnement sont documentées à la racine.
- [ ] Le contrat API est versionné et régénérable.


## Création immédiate dans `sharptech-digital-sarl`

Si votre besoin est de **créer tout de suite** le monorepo dans un dossier/référentiel nommé `sharptech-digital-sarl`, utilisez :

```bash
scripts/create-sharptech-monorepo.sh <URL_GECOR_FRONTEND> <URL_GECOR_BACKEND> [main] [sharptech-digital-sarl]
```

Ce script :
1. crée le dossier cible (par défaut `sharptech-digital-sarl`),
2. initialise Git,
3. importe frontend et backend avec historique,
4. place les projets dans `apps/frontend` et `apps/backend`.
