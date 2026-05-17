# Instructions pour ajouter le logo

## Emplacement du logo

Placez votre fichier logo dans le dossier `public/` à la racine du projet avec l'un de ces noms :
- `logo.png` (recommandé)
- `logo.svg` (alternative)

## Formats supportés

- **PNG** : Format recommandé pour les logos avec transparence
- **SVG** : Format vectoriel pour une qualité optimale à toutes les tailles

## Tailles recommandées

- **Petit** (AppBar, Drawer) : 32x32px à 48x48px
- **Moyen** (général) : 48x48px à 64x64px  
- **Grand** (Login) : 80x80px à 120x120px

## Emplacements où le logo apparaît

1. **Page de Login** : Logo grand centré en haut du formulaire
2. **AppBar** : Logo petit avec texte à gauche de la barre de navigation
3. **Drawer (Menu latéral)** : Logo petit centré en haut du menu

## Fallback automatique

Si aucun fichier logo n'est trouvé, un logo texte stylisé avec "FPI" sera affiché automatiquement avec un design moderne.

## Structure du dossier public

```
frontend/
  public/
    logo.png    ← Placez votre logo ici
    logo.svg    ← Ou ici (alternative)
```

## Note

Le logo sera automatiquement détecté et affiché dès que vous placez le fichier dans le dossier `public/`.

