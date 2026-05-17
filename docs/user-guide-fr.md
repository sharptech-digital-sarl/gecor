# Guide utilisateur GECOR

Ce guide décrit les opérations quotidiennes de l'application GECOR
(Gestion Electronique du Courrier et des Rendez-vous). Il s'adresse aux
agents, secrétaires, chefs de service, direction et réception.

## 1. Connexion et premier accès

1. Ouvrir l'URL fournie par votre administrateur (ex. `https://gecor.local`).
2. Saisir l'identifiant (généralement votre adresse courte) et le mot de passe.
3. Si la double authentification (MFA) est activée pour votre rôle, un code à
   6 chiffres est demandé. Utiliser **Google Authenticator** ou **FreeOTP**.
4. Au premier login, le système exige le changement du mot de passe par défaut.

### Mot de passe oublié

Sur l'écran de connexion, cliquer sur **« Mot de passe oublié »**. Une demande
est envoyée à l'administrateur ; vous recevrez une notification après
validation.

## 2. Tableau de bord

Le tableau de bord présente vos indicateurs personnels et, selon votre rôle,
les indicateurs de l'organisation :

- Courriers en cours, en retard, en attente de validation, en attente d'avis.
- Rendez-vous du jour, à venir, à valider.
- Tâches de suivi (post-RDV) ouvertes.

Cliquer sur un compteur amène directement à la liste filtrée correspondante.

## 3. Module Courrier

### 3.1 Enregistrer un nouveau courrier

1. Menu **Courrier → Nouveau courrier**.
2. Renseigner :
   - Titre (objet du courrier)
   - Direction : *entrant*, *sortant* ou *interne*
   - Canal : *scan*, *email*, *plateforme*
   - Qualification : administrative, financière, RH, légale, autre
   - Expéditeur (nom, e-mail, téléphone si pertinent)
   - Priorité, échéance de réponse (SLA)
   - Tags (mots-clés métier)
3. Joindre le fichier (PDF, image PNG/JPEG/TIFF, ≤ 25 Mo recommandé).
4. Valider : la référence métier est générée automatiquement.

Après upload, l'OCR (reconnaissance optique) traite automatiquement le document
en arrière-plan. Quelques secondes plus tard, le texte est indexé et apparaît
dans la recherche plein-texte.

### 3.2 Workflow d'un courrier entrant

Selon votre rôle, vous voyez les **actions disponibles** dans le détail du
courrier :

| Étape                | Acteur typique           | Action                    |
| -------------------- | ------------------------ | ------------------------- |
| Indexer              | Secrétariat / Réception  | Vérifie métadonnées       |
| Affecter             | Secrétariat DG           | Choisit un service / agent|
| Traiter              | Agent / chef de service  | Rédige la réponse         |
| Soumettre validation | Chef de service          | Transmet à la direction   |
| Avis direction       | Direction                | Transmet au DG            |
| Approuver / Rejeter  | DG                       | Décision finale           |
| Clôturer             | Secrétariat              | Met à clôturé             |
| Archiver             | Archiviste / DG          | Archivage définitif       |

Chaque transition demande un commentaire (optionnel mais conseillé) et
enregistre une ligne dans l'historique audité.

### 3.3 Recherche

Onglet **Courrier → Recherche** :

- Recherche plein-texte (référence, objet, texte OCR, expéditeur, tags).
- Filtres : période, direction, qualification, statut, expéditeur, tags.
- Exporter la liste filtrée en Excel.

## 4. Module Rendez-vous

### 4.1 Créer un rendez-vous

1. **Rendez-vous → Nouveau**.
2. Saisir le visiteur (nom, e-mail, téléphone, société).
3. Indiquer la date, l'heure de début et de fin, le lieu.
4. Optionnel : ordre du jour (ODJ), participants internes.
5. Selon le rôle :
   - **Réception / Secrétariat** crée un RDV interne ou répond à une demande publique.
   - **DG / Direction** valide hiérarchiquement le RDV.
6. Le visiteur reçoit un e-mail de confirmation avec QR code à présenter à
   la réception.

### 4.2 Réservation publique

Vos visiteurs peuvent réserver depuis `/public/booking` sans compte. Le RDV
arrive en statut *pending* et doit être pris en charge par la réception.

### 4.3 Compte-rendu et tâches post-RDV

Après la rencontre, dans le détail du RDV :

1. Onglet **Compte-rendu** : rédiger le PV (texte libre).
2. Onglet **Tâches** : créer des actions de suivi, assigner à un agent, suivre
   leur clôture.

### 4.4 Synchronisation Google Calendar

Dans **Paramètres → Intégrations**, cliquer sur **Connecter Google**. Une fois
le compte autorisé, les RDV confirmés dont vous êtes organisateur sont
automatiquement copiés sur votre agenda primaire.

## 5. Réception et visiteurs

Module accessible aux rôles `receptionist` :

- Liste des visiteurs du jour.
- Bouton **Check-in** au passage du visiteur (vérification QR ou pièce d'identité).
- Photo d'accueil (webcam) et scan de la pièce d'identité possibles.

## 6. Notifications

- **Cloche en haut à droite** : notifications in-app (clic = ouvrir l'élément).
- **E-mail** : envoyé pour les événements critiques (assignation, échéance,
  validation, rejet).
- **Push navigateur** (si autorisé) : alertes en temps réel même quand
  l'onglet est fermé. Activable via **Paramètres → Notifications**.

## 7. Paramètres personnels

- Changement de mot de passe.
- Activation MFA (TOTP).
- Préférences linguistiques (français / anglais).
- Préférences sonores par catégorie (mail, RDV, autre).
- Intégration Google Calendar.

## 8. Administration (master / director)

Accessibles via le menu **Admin** :

- **Utilisateurs** : création, désactivation, attribution de rôles.
- **Rôles** : création de groupes personnalisés, attribution fine de permissions.
- **Journal d'audit** : trace complète des actions critiques.
- **Centre de notifications** : envoyer un message système à tous les agents.
- **Posts publics** : éditer les messages affichés sur la page d'accueil.
- **Demandes de suppression** : valider ou refuser les suppressions.
- **Demandes mot de passe** : traiter les oublis.

## 9. Bonnes pratiques

- **Toujours** renseigner l'expéditeur et la qualification d'un courrier
  entrant : les KPI direction en dépendent.
- Préférer la mise en attente (*hold*) à l'oubli : un courrier *on_hold*
  est repérable, un courrier non traité ne l'est pas.
- Pour un RDV important : créer l'ODJ **avant** la rencontre, le compte-rendu
  **dans la semaine** qui suit.
- Les suppressions doivent toujours passer par la demande validée ; éviter
  la suppression directe sauf consigne explicite.
