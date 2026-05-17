# FPI-CONNECT Frontend

Application React (Vite + TypeScript) pour FPI-CONNECT.

## Prérequis

- Node.js 18+ (recommandé : LTS)
- Backend API accessible (voir `../backend/README.md`)

## Installation

```bash
npm install
```

## Configuration

Copiez `.env.example` vers `.env` et ajustez si besoin :

- `VITE_API_URL` — URL de base de l’API, par défaut `http://localhost:8000/api/v1`

Les variables `VITE_*` sont injectées au **build** ; en développement, redémarrez `npm run dev` après modification du `.env`.

## Lancer en développement

```bash
npm run dev
```

L’application est servie par Vite sur `http://localhost:3000` (voir `vite.config.ts` et la sortie du terminal).

## Build de production

```bash
npm run build
```

Les fichiers statiques sont générés dans `dist/`. Pour prévisualiser localement :

```bash
npm run preview
```

## Qualité

```bash
npm run lint
```


## Monorepo (frontend + backend)

Pour fusionner ce dépôt frontend avec le dépôt backend dans une structure monorepo, consultez :

- `docs/monorepo-migration.md`
- `scripts/prepare-monorepo.sh`

- `scripts/create-sharptech-monorepo.sh` (crée explicitement la racine `sharptech-digital-sarl`)

Le script prépare un dépôt monorepo cible avec `apps/frontend` et `apps/backend` en conservant l'historique Git via `git subtree`.


### Création directe du monorepo `sharptech-digital-sarl`

```bash
scripts/create-sharptech-monorepo.sh <url_frontend> <url_backend> [branche] [target_dir]
```

Par défaut, le script crée le dossier `sharptech-digital-sarl` puis importe les deux historiques dans `apps/frontend` et `apps/backend`.

Le script tente automatiquement un fallback SSH → HTTPS pour les URLs GitHub de type `git@github.com:...` si le fetch SSH échoue.
