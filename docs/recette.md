# Recette GECOR — Critères d'acceptation

Cette grille reprend les exigences de [`backend/AGENTS.md`](../backend/AGENTS.md)
sous forme de tests d'acceptation manuels. Chaque ligne doit être vérifiée
avant la mise en production.

## Légende

- **Pré-requis** : compte ayant les permissions nécessaires (cf.
  `backend/app/core/permissions.py`).
- **Statut attendu** : ce que le système doit faire si le test passe.
- À reporter en fin de fiche : version, date, testeur, OK/KO, observations.

---

## A. Authentification et sécurité

| N°   | Scénario                                                           | Pré-requis                  | Statut attendu                                                                  |
| ---- | ------------------------------------------------------------------ | --------------------------- | ------------------------------------------------------------------------------- |
| A.1  | Connexion réussie avec mot de passe correct                        | Compte actif                | Token access + cookie refresh, redirection vers /app.                           |
| A.2  | Connexion échouée (mot de passe faux × 5)                          | Compte actif                | Rate-limit activé (429), audit `login_attempt` avec `success=false`.            |
| A.3  | MFA activé : login renvoie `mfa_session_id`                        | Compte avec TOTP            | Pas de token tant que /mfa/verify n'a pas été appelé.                           |
| A.4  | MFA verify avec code OTP correct                                   | Idem                        | Tokens livrés, audit `mfa_verify_success`.                                      |
| A.5  | Refresh token rotation                                             | Cookie refresh valide       | Nouveau cookie renvoyé, ancien invalidé.                                        |
| A.6  | Logout                                                             | Connecté                    | Cookie refresh supprimé, session révoquée.                                      |
| A.7  | Demande mot de passe oublié → notification masters                 | E-mail existant             | Ligne `PasswordResetRequest`, notif in-app aux masters.                         |
| A.8  | Validation oubli par master → reset au mot de passe défaut         | Master                      | `password_must_change=True`, e-mail à l'utilisateur.                            |
| A.9  | Forcer le changement de mot de passe au premier login              | Utilisateur nouveau         | Dialogue bloquant, refus d'API si non changé.                                   |

## B. Module Courrier entrant

| N°   | Scénario                                                                | Pré-requis        | Statut attendu                                                              |
| ---- | ----------------------------------------------------------------------- | ----------------- | --------------------------------------------------------------------------- |
| B.1  | Enregistrer un courrier entrant avec PJ PDF                             | `mail.create`     | `MailDocument` créé, référence métier auto, OCR planifié.                   |
| B.2  | OCR enrichit `ocr_text` et `ocr_keywords` après quelques secondes       | Idem              | Recherche plein-texte retrouve le document.                                 |
| B.3  | Affecter à un agent                                                     | `mail.workflow.assign` | `assigned_to` mis à jour, notif in-app + e-mail à l'agent.            |
| B.4  | Agent traite et soumet à validation                                     | `mail.workflow.treat`, `submit_validation` | Transition vers PENDING_VALIDATION, notif DG.    |
| B.5  | DG approuve                                                             | `mail.workflow.approve` | Transition vers APPROVED, audit.                                       |
| B.6  | DG rejette avec motif                                                   | `mail.workflow.reject` | Transition vers REJECTED, e-mail à l'agent avec le motif.               |
| B.7  | Mise en attente (`hold`) puis reprise (`resume`)                        | Permissions ad-hoc | Transitions audités, statut ON_HOLD puis retour précédent.                |
| B.8  | Demande de suppression par un agent                                     | `mail.request_delete` | `DeletionRequest` PENDING, notif aux reviewers.                          |
| B.9  | Suppression directe par master                                          | `mail.delete`     | Document et fichier purgés, audit `mail_deleted`.                           |
| B.10 | Archivage par archiviste                                                | `mail.workflow.archive` | `archived_at` rempli, plus modifiable.                                 |

## C. Module Courrier sortant

| N°   | Scénario                                                            | Pré-requis           | Statut attendu                                                              |
| ---- | ------------------------------------------------------------------- | -------------------- | --------------------------------------------------------------------------- |
| C.1  | Création brouillon courrier sortant                                  | `mail.create`        | `MailDocument` direction=outbound, statut RECEIVED.                          |
| C.2  | Soumission à validation hiérarchique                                 | Workflow sortant     | Transitions chaînées suivant la `WorkflowDefinition` outbound.               |
| C.3  | Numérotation officielle après approbation                            | Workflow             | Référence métier finale figée et auditée.                                    |
| C.4  | Lien avec un courrier entrant (réponse à…)                           | `mail.update`        | Métadonnées de liaison conservées.                                          |
| C.5  | Versions successives accessibles                                     | `mail.view`          | Historique `MailVersion` consultable.                                       |

## D. Module Rendez-vous

| N°   | Scénario                                                            | Pré-requis                                  | Statut attendu                                                            |
| ---- | ------------------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------- |
| D.1  | Créer un RDV interne                                                | `appointments.create`                       | Statut PENDING, organizer = utilisateur courant.                          |
| D.2  | Proposer un créneau                                                 | `appointments.workflow.propose_slot`        | Statut SLOT_PROPOSED, dates proposées enregistrées.                       |
| D.3  | Validation hiérarchique (DG)                                        | `appointments.workflow.hierarchy_validate`  | Statut CONFIRMED, e-mail au visiteur + QR code.                            |
| D.4  | Refus hiérarchique                                                  | Idem                                        | Statut CANCELLED, e-mail au visiteur + notif organizer.                    |
| D.5  | Check-in visiteur via QR code                                       | `reception.checkin`                         | `visitor.checked_in=True`, horodaté.                                       |
| D.6  | Compte-rendu post-RDV                                               | `appointments.workflow.minutes`             | `minutes_text`, `minutes_at` remplis.                                     |
| D.7  | Tâches post-RDV assignées                                           | `appointments.workflow.tasks`               | `AppointmentTask` créées, statut OPEN.                                    |
| D.8  | Réservation publique (sans compte)                                  | Aucun                                       | RDV créé en statut PENDING, source=PUBLIC.                                 |
| D.9  | Rappel automatique J-1                                              | Celery beat                                 | `reminder_sent=True`, e-mail au visiteur si adresse.                       |
| D.10 | Synchronisation Google Calendar après confirmation                  | OAuth Google connecté                       | `google_event_id` rempli, événement visible côté Google.                  |

## E. Recherche / archives

| N°   | Scénario                                                            | Pré-requis                | Statut attendu                                              |
| ---- | ------------------------------------------------------------------- | ------------------------- | ----------------------------------------------------------- |
| E.1  | Recherche plein-texte sur référence, objet, OCR, expéditeur, tags    | `mail.view`               | Liste paginée triée par pertinence / date.                  |
| E.2  | Filtre date + qualification + direction                              | Idem                      | Résultats restreints, total cohérent.                        |
| E.3  | Export Excel d'une liste filtrée                                     | Idem                      | Fichier `.xlsx` téléchargé.                                  |
| E.4  | Accès refusé sur document hors périmètre                             | Rôle restreint            | 403, audit `access_denied` (logs).                          |

## F. Tableau de bord et statistiques

| N°   | Scénario                                                                  | Pré-requis           | Statut attendu                                            |
| ---- | ------------------------------------------------------------------------- | -------------------- | --------------------------------------------------------- |
| F.1  | Indicateurs personnels (mes courriers, mes RDV, mes tâches)                | `dashboard.view`     | Compteurs cohérents avec listes.                          |
| F.2  | Indicateurs organisation (totaux, retards, délais médians)                 | `dashboard.kpi.org`  | Calculs identiques à la requête manuelle.                 |
| F.3  | Alertes courriers en retard                                                | Celery               | Notification in-app et e-mail aux assignés.               |
| F.4  | Évolution sur 12 mois glissants (à venir)                                  | Idem                 | Graphique disponible côté frontend.                       |

## G. Sécurité, droits, administration

| N°   | Scénario                                                                | Pré-requis     | Statut attendu                                                |
| ---- | ----------------------------------------------------------------------- | -------------- | ------------------------------------------------------------- |
| G.1  | Création d'un utilisateur avec rôle                                      | `users.manage` | Compte créé, e-mail (ou mot de passe défaut) communiqué.      |
| G.2  | Création d'un groupe (rôle) personnalisé                                 | Master         | Rôle visible dans l'admin, permissions appliquées.            |
| G.3  | Désactivation d'un utilisateur                                           | `users.manage` | `is_active=False`, login refusé.                              |
| G.4  | Suppression d'un utilisateur                                             | Master         | Suppression auditée, ressources orphelines non perdues.       |
| G.5  | Audit log accessible pour les admins                                     | `admin.audit`  | Liste chronologique paginée, filtrable.                       |
| G.6  | Sauvegarde quotidienne PostgreSQL                                        | Cron           | Fichier dump dans `BACKUP_DIR`, rotation 30j fonctionnelle.   |

## H. Critères transverses

- [ ] Toutes les actions critiques (login, suppression, transition, archive,
      export) génèrent une ligne `audit_events`.
- [ ] Les e-mails respectent la langue préférée de l'utilisateur destinataire.
- [ ] Aucun secret n'est exposé dans les logs (`Settings.__repr__` masque les
      champs sensibles).
- [ ] Aucune dépendance bloquante au cloud (sauf intégrations explicitement
      activées par configuration : Google Calendar, Outlook, …).
- [ ] Les uploads sont validés en taille, extension et type MIME.
- [ ] Le rate-limit s'applique sur `/auth/login`, `/auth/mfa/verify`,
      `/auth/forgot-password`.
- [ ] CORS strict (uniquement les origines listées dans `CORS_ORIGINS`).

---

## Fiche de recette

| Item                | Valeur                       |
| ------------------- | ---------------------------- |
| Version testée      |                              |
| Date                |                              |
| Testeur(s)          |                              |
| Environnement       | dev / pré-prod / production  |
| Réf. ticket(s)      |                              |
| Décision            | OK / OK sous réserve / KO    |
| Observations        |                              |
