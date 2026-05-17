#!/usr/bin/env python3
"""
Script de diagnostic MFA
Vérifie que le secret stocké en base correspond à celui utilisé dans Google Authenticator
"""

import sys
import pyotp
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

def diagnose_mfa(username, code_from_authenticator=None):
    """Diagnostique les problèmes MFA"""
    try:
        from app.core.database import SessionLocal
        from app.models.user import User
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            
            if not user:
                print(f"❌ Utilisateur '{username}' non trouvé")
                return False
            
            print(f"✓ Utilisateur trouvé: {user.username}")
            print(f"  Email: {user.email}")
            print(f"  MFA activé: {user.is_mfa_enabled}")
            
            if not user.is_mfa_enabled:
                print("❌ MFA n'est pas activé pour cet utilisateur")
                return False
            
            if not user.mfa_secret:
                print("❌ Pas de secret MFA stocké en base")
                return False
            
            print(f"\n{'='*60}")
            print("INFORMATIONS DU SECRET MFA")
            print(f"{'='*60}")
            print(f"Secret stocké en base: {user.mfa_secret}")
            print(f"  Longueur: {len(user.mfa_secret)} caractères")
            
            # Générer le code actuel avec ce secret
            totp = pyotp.TOTP(user.mfa_secret)
            current_code = totp.now()
            
            print(f"\n{'='*60}")
            print("CODES TOTP GÉNÉRÉS")
            print(f"{'='*60}")
            from datetime import datetime
            import time
            
            print(f"Code actuel: {current_code}")
            
            # Codes précédent et suivant
            current_time = int(time.time())
            prev_code = totp.at(current_time - 30)
            next_code = totp.at(current_time + 30)
            print(f"Code précédent (si encore valide): {prev_code}")
            print(f"Code suivant (dans 30s): {next_code}")
            
            # Vérifier le code fourni
            if code_from_authenticator:
                print(f"\n{'='*60}")
                print("VÉRIFICATION DU CODE")
                print(f"{'='*60}")
                print(f"Code fourni: {code_from_authenticator}")
                
                # Essayer avec différentes fenêtres de validité
                for window in [0, 1, 2]:
                    is_valid = totp.verify(code_from_authenticator, valid_window=window)
                    print(f"  Fenêtre ±{window*30}s: {'✓ VALIDE' if is_valid else '✗ INVALIDE'}")
                
                if not totp.verify(code_from_authenticator, valid_window=2):
                    print(f"\n❌ Le code fourni ne correspond PAS au secret stocké")
                    print(f"   Code attendu actuel: {current_code}")
                    print(f"\n💡 Solutions possibles:")
                    print(f"   1. Vérifiez que vous avez scanné le BON QR code")
                    print(f"   2. Vérifiez que le secret dans Google Authenticator est: {user.mfa_secret}")
                    print(f"   3. Vérifiez que l'heure de votre système est correcte")
                    return False
                else:
                    print(f"\n✓ Le code correspond au secret stocké!")
            
            # Générer l'URL de provisioning pour vérification
            otpauth_url = totp.provisioning_uri(
                name=user.email or user.username,
                issuer_name="FPI-CONNECT"
            )
            
            print(f"\n{'='*60}")
            print("URL DE PROVISIONING")
            print(f"{'='*60}")
            print(f"URL: {otpauth_url}")
            print(f"\n💡 Vérifiez que cette URL correspond à celle utilisée dans Google Authenticator")
            
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    from datetime import datetime
    
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  python {sys.argv[0]} <username> [code_from_authenticator]")
        print("\nExemples:")
        print(f"  # Vérifier le secret et générer le code actuel")
        print(f"  python {sys.argv[0]} admin")
        print(f"\n  # Vérifier un code spécifique")
        print(f"  python {sys.argv[0]} admin 123456")
        sys.exit(1)
    
    username = sys.argv[1]
    code = sys.argv[2] if len(sys.argv) >= 3 else None
    
    print("="*60)
    print("DIAGNOSTIC MFA")
    print("="*60)
    print(f"Date/Heure: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Utilisateur: {username}")
    if code:
        print(f"Code à vérifier: {code}")
    print()
    
    success = diagnose_mfa(username, code)
    
    if success:
        print("\n✅ Diagnostic terminé")
    else:
        print("\n❌ Problème détecté")
        sys.exit(1)
