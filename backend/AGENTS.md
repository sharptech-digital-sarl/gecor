# AGENTS.md - Instructions Codex pour le projet GECOR

## Contexte projet

GECOR signifie Gestion Electronique du Courrier et des Rendez-vous. C'est un systeme d'information metier on-premise pour une institution publique ou privee, initialement destine a l'ARSP. L'objectif est de centraliser, tracer, archiver et piloter le courrier entrant, le courrier sortant et l'agenda institutionnel, sans dependance cloud.

## Objectifs prioritaires

Codex doit construire une application web production-ready avec :

1. Backend API en Python / Django / Django REST Framework.
2. Frontend en React.js.
3. Base de donnees PostgreSQL.
4. Deploiement on-premise via Nginx + Gunicorn.
5. Authentification securisee, roles et permissions granulaires.
6. Audit trail complet : toute action sensible doit enregistrer qui, quoi, quand, avant/apres si pertinent.
7. Recherche full-text sur les documents et metadonnees.
8. Sauvegarde quotidienne PostgreSQL avec rotation 30 jours.
9. Documentation technique, documentation utilisateur et scripts de deploiement.

## Contraintes non negociables

- Aucune dependance a un service cloud pour le fonctionnement coeur.
- Les donnees doivent rester sur l'infrastructure du client.
- Le systeme doit fonctionner sur LAN et pouvoir etre expose aux directions provinciales via VPN WireGuard.
- Ne pas stocker de secrets en dur dans le code.
- Utiliser des variables d'environnement pour les secrets, la base de donnees, SMTP et les chemins de stockage.
- Toutes les dates/heures doivent etre horodatees et coherentes avec le fuseau horaire configure.
- Toutes les actions critiques doivent etre journalisees.
- Les suppressions doivent etre logiques par defaut, avec corbeille/restauration, sauf politique explicite contraire.
- Le code doit etre livre avec tests automatises et commandes reproductibles.

## Stack technique cible

### Backend

- Python 3.12+
- Django 5.x
- Django REST Framework
- PostgreSQL 15+
- Celery + Redis pour taches asynchrones : rappels, sauvegardes, notifications, indexation documentaire
- django-filter pour filtres API
- drf-spectacular pour documentation OpenAPI
- psycopg / psycopg2 selon compatibilite
- Gunicorn en production

### Frontend

- React.js avec TypeScript
- Vite
- React Router
- TanStack Query ou equivalent pour appels API
- Formulaires typés avec validation
- Interface responsive utilisable sur postes LAN

### Infrastructure

- Nginx reverse proxy
- Gunicorn service systemd
- PostgreSQL local ou serveur interne
- Redis local ou serveur interne
- Stockage fichiers local/NAS configurable
- Scripts backup pg_dump + rotation 30 jours
- Option Docker Compose autorisee pour environnement dev, mais le deploiement final doit pouvoir fonctionner on-premise hors cloud.

## Modules fonctionnels a implementer

### Module 1 - Courrier entrant

Fonctionnalites :

- Enregistrement d'un courrier entrant avec numero de reference unique.
- Horodatage automatique.
- Piece jointe numerisee ou document electronique.
- Metadonnees : expéditeur, objet, type, urgence, service destinataire, responsable assigne.
- Statuts : en_attente, en_cours, traite, archive.
- Affectation manuelle ou automatique selon service/type/urgence.
- Notifications internes au responsable.
- Historique des changements de statut et d'affectation.

Modeles suggeres : IncomingMail, MailAttachment, MailAssignment, MailStatusHistory.

### Module 2 - Courrier sortant

Fonctionnalites :

- Brouillon de courrier sortant.
- Modeles de courriers institutionnels.
- Circuit de validation hierarchique configurable a N niveaux.
- Numerotation officielle automatique apres validation.
- Lien possible avec un courrier entrant auquel il repond.
- Archivage automatique.
- Historique des versions.
- Export PDF avec en-tete institutionnel.

Modeles suggeres : OutgoingMail, OutgoingMailVersion, ApprovalWorkflow, ApprovalStep, LetterTemplate.

### Module 3 - Agenda et rendez-vous

Fonctionnalites :

- Agenda multi-agents : vue jour, semaine, mois cote frontend.
- Creation de rendez-vous avec participants internes.
- Gestion de salles et ressources partagees.
- Detection de conflits simples.
- Rappels automatiques : 15 minutes, 1 heure, 24 heures.
- Compte-rendu de reunion integre.
- Historique des rendez-vous.

Modeles suggeres : Appointment, AppointmentParticipant, Room, Resource, MeetingReport, Reminder.

### Module 4 - Archives et recherche

Fonctionnalites :

- Recherche full-text sur courriers, notes, rapports et metadonnees.
- Filtres avances : date, expéditeur, destinataire, service, statut, type de document.
- Navigation par dossier thematique ou chronologique.
- Controle d'acces selon accréditation.
- Corbeille securisee avec restauration.

Modeles suggeres : ArchiveFolder, SearchIndex, SoftDeleteMixin.

### Module 5 - Tableaux de bord et statistiques

Fonctionnalites :

- Tableau de bord par role : Direction, Chef de service, Agent, Administrateur.
- Indicateurs : volume de courrier, delai de traitement, taux de reponse par service.
- Alertes sur courriers en retard.
- Rapports exportables PDF et Excel.
- Graphiques evolution flux documentaire sur 12 mois glissants.

Endpoints suggeres : /api/dashboard/summary, /api/dashboard/mail-volume, /api/reports/export.

### Module 6 - Securite, droits et administration

Fonctionnalites :

- Utilisateurs, roles, services/departements.
- Permissions granulaires : lecture, ecriture, validation, administration.
- Authentification securisee.
- Politique de mot de passe.
- Piste d'audit complete.
- Sauvegarde automatique quotidienne.
- Interface admin reservee au super-administrateur.

Modeles suggeres : User, Role, Department, Permission, AuditLog, BackupJob.

## Regles de modelisation

- Preferer des modeles explicites et normalises.
- Ajouter created_at, updated_at, created_by, updated_by quand pertinent.
- Utiliser UUID ou identifiants robustes pour les objets metier exposes par API.
- Les references metier doivent etre lisibles : CE-YYYY-NNNNN pour courrier entrant, CS-YYYY-NNNNN pour courrier sortant.
- Les fichiers doivent etre stockes avec noms securises et chemins non predictibles.
- Ajouter contraintes d'unicite en base quand necessaire.
- Ajouter indexes sur champs frequemment filtres : dates, statut, service, reference, urgence.

## API attendue

- API REST JSON versionnee sous /api/v1/.
- Documentation OpenAPI disponible sous /api/schema/ et /api/docs/.
- Pagination sur les listes.
- Filtres et recherche sur les ressources principales.
- Permissions au niveau endpoint et objet.
- Reponses d'erreur structurees et comprehensibles.

## Exigences securite

- Authentification obligatoire sauf endpoint de sante.
- Mots de passe haches avec les mecanismes Django standards.
- CSRF/CORS configures strictement selon environnement.
- Validation stricte des uploads : taille, extension, type MIME.
- Antivirus optionnel ou hook de scan prevu pour deploiement institutionnel.
- Protection contre path traversal.
- Rate limiting sur endpoints d'authentification.
- Logs applicatifs sans secrets ni mots de passe.
- AuditLog pour login, logout, creation, modification, validation, suppression, restauration, export.

## Tests attendus

- Tests unitaires backend pour modeles, permissions, workflows et numerotation.
- Tests API pour CRUD principal et permissions.
- Tests frontend pour composants critiques si infrastructure presente.
- Tests de non-regression sur les workflows courrier entrant/sortant.
- Commande unique de test documentee.

## Commandes de qualite a maintenir

Ajouter ou maintenir les commandes suivantes selon le gestionnaire de dependances choisi :

- Backend lint/format : ruff, black ou equivalent.
- Backend tests : pytest ou Django test runner.
- Frontend lint/typecheck : eslint + tsc.
- Frontend build : npm run build.
- Migrations Django : python manage.py makemigrations puis migrate.

## Livrables attendus dans le depot

- README.md avec installation dev et production.
- .env.example complet.
- backend/ et frontend/ clairement separes, ou monorepo documente.
- scripts/backup_postgres.sh.
- deploy/nginx.conf.example.
- deploy/gecor-gunicorn.service.example.
- docs/architecture.md.
- docs/installation.md.
- docs/maintenance.md.
- docs/user-guide-fr.md.
- docs/recette.md avec criteres d'acceptation.

## Criteres d'acceptation fonctionnels

- Un agent peut enregistrer un courrier entrant avec piece jointe et l'affecter a un service.
- Un responsable voit ses courriers assignes et change le statut.
- Un courrier sortant peut etre redige, soumis, approuve puis numerote officiellement.
- Un utilisateur autorise peut rechercher dans les archives avec filtres.
- Un rendez-vous peut etre cree avec participants et salle, avec rappel planifie.
- La Direction visualise les indicateurs essentiels.
- Un administrateur gere utilisateurs, roles, services et sauvegardes.
- Les actions critiques apparaissent dans le journal d'audit.

## Style de code

- Code clair, modulaire, type autant que possible.
- Eviter les abstractions inutiles.
- Nommer en anglais cote code, garder les libelles utilisateur en francais.
- Commenter les regles metier non evidentes.
- Ne pas casser les migrations existantes sans justification.

## Methode de travail Codex

Avant toute modification importante :

1. Inspecter l'arborescence du depot.
2. Identifier la stack deja presente.
3. Proposer ou appliquer le plus petit changement coherent.
4. Lancer les tests/linters disponibles quand possible.
5. Mettre a jour la documentation et .env.example si une configuration change.
6. Signaler clairement les commandes non lancees et pourquoi.
