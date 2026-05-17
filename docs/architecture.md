# Architecture GECOR

## 1. Vue d'ensemble

GECOR repose sur une architecture **3-tiers classique** : un frontend SPA,
un backend HTTP REST et un cluster d'infrastructure (base de données +
cache + worker asynchrone + stockage de fichiers). L'ensemble est conçu
pour s'exécuter **on-premise** (LAN, VPN), sans dépendance vitale au cloud.

```
┌──────────────────────────────────────────────────────────────────┐
│                       Postes utilisateurs                        │
│      (navigateur, mobile via VPN WireGuard si nécessaire)        │
└───────────────────────────┬──────────────────────────────────────┘
                            │  HTTPS
                ┌───────────▼─────────────┐
                │  Nginx (reverse proxy)   │
                │  - TLS terminaison       │
                │  - sert le SPA Vite      │
                │  - proxy /api → FastAPI  │
                └───────┬──────────┬──────┘
                        │          │
                ┌───────▼──┐  ┌────▼─────────────┐
                │  React   │  │ FastAPI / Uvicorn │
                │  bundle  │  │ workers Gunicorn  │
                └──────────┘  └────┬──────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
   ┌────▼──────┐            ┌──────▼──────┐            ┌──────▼──────┐
   │ Postgres  │            │  Redis      │            │  Stockage   │
   │ 15 + tsv  │            │ - rate lim. │            │  local ou   │
   │           │            │ - Celery    │            │  MinIO/S3   │
   └───────────┘            │ - SSE hub   │            └─────────────┘
                            └──────┬──────┘
                                   │
                          ┌────────▼─────────┐
                          │ Celery worker +  │
                          │ Celery beat      │
                          │ (OCR, rappels)   │
                          └──────────────────┘
```

## 2. Modules fonctionnels

### 2.1 Courrier (entrant / sortant / interne)

- Modèle principal : `MailDocument` (`backend/app/models/mail.py`).
- Versions : `MailVersion` (historique de fichiers).
- Workflow : `WorkflowDefinition` / `WorkflowStep` / `WorkflowTransition`
  configurables (table `workflow_definitions`), plus `WorkflowState` et
  `WorkflowHistory` côté instances.
- Métadonnées riches : direction, canal (scan/email/plateforme), qualification
  (administrative, financière, RH, légale…), tags JSONB, SLA (`response_deadline`).
- Référence métier : `FPI-YYYYMMDD-XXXXXXXX` (à durcir en `CE-YYYY-NNNNN` pour
  l'entrant et `CS-YYYY-NNNNN` pour le sortant — voir `docs/recette.md`).
- OCR automatique (Tesseract via Celery) pour rechercher dans le contenu.

### 2.2 Rendez-vous

- Modèle `Appointment` + `Visitor` (QR code, photo, pièce d'identité).
- Workflow : `pending → slot_proposed → pending_authorization → preparation → confirmed → completed`
  (ou `cancelled` / `no_show`).
- Ordre du jour : `AppointmentAgendaItem`.
- Suivi : `AppointmentTask` (assignation post-RDV).
- Sync calendrier : Google Calendar (OAuth) et Outlook / Exchange (optionnel).
- Réservation publique : route `/public/booking` + endpoint `/api/v1/public/*`.
- Rappels : envoyés H-24h par Celery beat.

### 2.3 Sécurité / RBAC

- Modèle `User` ↔ `Role` (M2M via `user_roles`), permissions stockées en JSONB.
- Catalogue des permissions : `backend/app/core/permissions.py`.
- MFA TOTP (Google Authenticator, FreeOTP) + sessions MFA intermédiaires.
- Refresh token rotatif (cookie HttpOnly), access token JWT (HS256).
- Rate-limit Redis sur les endpoints d'authentification.
- Politique de mot de passe : `password_must_change`, demande oubli avec
  validation hiérarchique (`PasswordResetRequest` + `PasswordResetChallenge`).

### 2.4 Notifications

- Triple canal : in-app (`InAppNotification`), e-mail (SMTP), Web Push (VAPID).
- SSE pour le push temps-réel vers les onglets ouverts (`/api/v1/notifications/stream`).
- Préférences sonores par catégorie (`mail`, `appointment`, `other`).
- I18n FR/EN, langue persistée par utilisateur.

### 2.5 Audit

- Modèle `AuditEvent` (table `audit_events`), persistance via `app/core/audit.py`.
- Toute action sensible (login, transitions workflow, suppressions, archivage,
  exports) écrit une ligne. Indexée par `timestamp`, `actor_user_id`, `action`.
- Consultation : page `/app/admin/audit` (permission `admin.audit`).

### 2.6 Suppressions / corbeille

- Aucune suppression « directe » par défaut : passage obligatoire par
  `DeletionRequest` qui doit être validée par un reviewer
  (permission `deletion_requests.review`).
- Master / director peuvent supprimer en direct (audité).

### 2.7 Recherche

- Recherche métier sur référence, expéditeur, qualification, tags, date.
- Recherche **plein-texte** côté courrier (OCR + métadonnées) — voir
  `backend/app/api/v1/mail.py` (endpoint `/api/v1/mail/search`).

## 3. Données

- PostgreSQL 15+, schémas générés par Alembic.
- Identifiants : UUID v4 partout.
- JSONB pour les structures variables (`tags`, `permissions`, `details` audit).
- Index sur les colonnes filtrées intensivement : `MailDocument.direction`,
  `MailDocument.qualification`, `Appointment.start_time` / `end_time`,
  `AuditEvent.timestamp` / `action`, etc.

## 4. Asynchrone / tâches planifiées

Planning Celery beat (`backend/app/celery_app.py`) :

| Tâche                                | Fréquence            | Rôle                                                |
| ------------------------------------ | -------------------- | --------------------------------------------------- |
| `send_appointment_reminders`         | Tous les jours 09:00 | Envoie un rappel pour les RDV J+1.                  |
| `check_deadlines`                    | Toutes les 2 heures  | Détecte les courriers en retard, notifie l'assignée. |
| `remind_password_reset_requests`     | Chaque heure         | Rappelle les demandes mot de passe en attente.      |
| `ocr_document`                       | À la demande         | OCR Tesseract sur un courrier après upload.         |
| `send_mail_validation_required`      | À la demande         | Email aux validateurs DG.                            |
| `send_mail_workflow_event`           | À la demande         | Email pour hold / request_changes / reject.         |
| `send_public_booking_confirmation`   | À la demande         | Email visiteur après validation réception.          |

## 5. Stockage des fichiers

- Par défaut : disque local (`STORAGE_PATH`, monté en volume Docker).
- Optionnel : MinIO ou S3 (`STORAGE_TYPE=s3`).
- Les noms de fichiers contiennent la référence métier ; les chemins ne sont
  jamais devinables (UUID inclus). Aucun accès direct côté Nginx : passage
  obligatoire par l'endpoint `/mail/{id}/file` qui vérifie les permissions.

## 6. Sécurité réseau

- Backend uniquement joignable derrière Nginx (configurer `proxy_pass`).
- HSTS recommandé en production, voir `deploy/nginx.conf.example`.
- `TRUST_FORWARDED_HEADERS=true` derrière reverse-proxy (sinon `false`).
- CORS strict : ne lister que les origines réelles (interfaces déployées).
