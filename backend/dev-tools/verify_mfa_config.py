#!/usr/bin/env python3
"""Script de vérification de la configuration MFA"""

import sys
from app.core.config import settings
from app.core.database import engine
from sqlalchemy import inspect

def check_env_vars():
    """Vérifie les variables d'environnement"""
    print("🔍 Vérification des variables d'environnement...")
    
    required_vars = [
        'SECRET_KEY',
        'DATABASE_URL',
        'PROJECT_NAME',
    ]
    
    optional_vars = [
        'MFA_SESSION_EXPIRE_MINUTES',
        'ACCESS_TOKEN_EXPIRE_MINUTES',
        'REFRESH_TOKEN_EXPIRE_DAYS',
        'REFRESH_TOKEN_SECURE',
        'REFRESH_TOKEN_SAMESITE',
    ]
    
    errors = []
    warnings = []
    
    for var in required_vars:
        value = getattr(settings, var, None)
        if not value:
            errors.append(f"❌ {var} est manquant")
        else:
            masked_value = '***' if 'SECRET' in var or 'PASSWORD' in var or 'KEY' in var else value
            print(f"  ✓ {var}: {masked_value}")
    
    for var in optional_vars:
        value = getattr(settings, var, None)
        if value is None:
            warnings.append(f"⚠️  {var} utilise la valeur par défaut")
        else:
            print(f"  ✓ {var}: {value}")
    
    return errors, warnings

def check_dependencies():
    """Vérifie les dépendances Python"""
    print("\n🔍 Vérification des dépendances...")
    
    dependencies = {
        'pyotp': 'pyotp',
        'qrcode': 'qrcode',
    }
    
    errors = []
    
    for module_name, package_name in dependencies.items():
        try:
            __import__(module_name)
            print(f"  ✓ {package_name} est installé")
        except ImportError:
            errors.append(f"❌ {package_name} n'est pas installé")
    
    return errors

def check_database():
    """Vérifie la structure de la base de données"""
    print("\n🔍 Vérification de la base de données...")
    
    errors = []
    
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # Vérifier la table users
        if 'users' not in tables:
            errors.append("❌ Table 'users' n'existe pas")
        else:
            print("  ✓ Table 'users' existe")
            columns = [col['name'] for col in inspector.get_columns('users')]
            required_columns = ['is_mfa_enabled', 'mfa_secret', 'mfa_temp_secret']
            for col in required_columns:
                if col in columns:
                    print(f"    ✓ Colonne '{col}' existe")
                else:
                    errors.append(f"❌ Colonne '{col}' manquante dans 'users'")
        
        # Vérifier la table mfa_sessions
        if 'mfa_sessions' not in tables:
            errors.append("❌ Table 'mfa_sessions' n'existe pas")
        else:
            print("  ✓ Table 'mfa_sessions' existe")
            columns = [col['name'] for col in inspector.get_columns('mfa_sessions')]
            required_columns = ['id', 'user_id', 'created_at', 'expires_at', 'is_consumed']
            for col in required_columns:
                if col in columns:
                    print(f"    ✓ Colonne '{col}' existe")
                else:
                    errors.append(f"❌ Colonne '{col}' manquante dans 'mfa_sessions'")
    
    except Exception as e:
        errors.append(f"❌ Erreur de connexion à la base de données: {str(e)}")
    
    return errors

def check_config_values():
    """Vérifie les valeurs de configuration"""
    print("\n🔍 Vérification des valeurs de configuration...")
    
    errors = []
    warnings = []
    
    # Vérifier MFA_SESSION_EXPIRE_MINUTES
    mfa_expire = getattr(settings, 'MFA_SESSION_EXPIRE_MINUTES', 10)
    if mfa_expire < 5:
        warnings.append(f"⚠️  MFA_SESSION_EXPIRE_MINUTES={mfa_expire} est très court (< 5 minutes)")
    elif mfa_expire > 30:
        warnings.append(f"⚠️  MFA_SESSION_EXPIRE_MINUTES={mfa_expire} est très long (> 30 minutes)")
    else:
        print(f"  ✓ MFA_SESSION_EXPIRE_MINUTES={mfa_expire} (OK)")
    
    # Vérifier REFRESH_TOKEN_SECURE
    secure = getattr(settings, 'REFRESH_TOKEN_SECURE', True)
    if not secure:
        warnings.append("⚠️  REFRESH_TOKEN_SECURE=false (OK pour dev, doit être true en prod)")
    else:
        print("  ✓ REFRESH_TOKEN_SECURE=true (OK pour production)")
    
    # Vérifier PROJECT_NAME
    project_name = getattr(settings, 'PROJECT_NAME', '')
    if not project_name or project_name == 'FPI-CONNECT':
        warnings.append("⚠️  PROJECT_NAME utilise la valeur par défaut")
    else:
        print(f"  ✓ PROJECT_NAME={project_name}")
    
    return errors, warnings

def main():
    """Fonction principale"""
    print("=" * 60)
    print("VÉRIFICATION DE LA CONFIGURATION MFA")
    print("=" * 60)
    
    all_errors = []
    all_warnings = []
    
    # Vérifier les variables d'environnement
    errors, warnings = check_env_vars()
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    # Vérifier les dépendances
    errors = check_dependencies()
    all_errors.extend(errors)
    
    # Vérifier la base de données
    errors = check_database()
    all_errors.extend(errors)
    
    # Vérifier les valeurs de configuration
    errors, warnings = check_config_values()
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    # Résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ")
    print("=" * 60)
    
    if all_warnings:
        print(f"\n⚠️  {len(all_warnings)} avertissement(s):")
        for warning in all_warnings:
            print(f"  {warning}")
    
    if all_errors:
        print(f"\n❌ {len(all_errors)} erreur(s) trouvée(s):")
        for error in all_errors:
            print(f"  {error}")
        print("\n⚠️  Le MFA ne fonctionnera pas correctement avec ces erreurs.")
        print("\n💡 Consultez MFA_CONFIGURATION_GUIDE.md pour plus de détails.")
        sys.exit(1)
    else:
        print("\n✅ Toutes les vérifications sont passées !")
        print("✅ Le MFA est correctement configuré.")
        if all_warnings:
            print("\n💡 Consultez les avertissements ci-dessus pour optimiser votre configuration.")
        sys.exit(0)

if __name__ == "__main__":
    main()
