#!/usr/bin/env python3
"""
Script pour générer un QR code avec le secret MFA stocké en base
Permet de reconfigurer Google Authenticator avec le bon secret
"""

import sys
import pyotp
import qrcode
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

def generate_qr_for_stored_secret(username):
    """Génère un QR code avec le secret stocké en base"""
    try:
        from app.core.database import SessionLocal
        from app.models.user import User
        from app.core.config import settings
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            
            if not user:
                print(f"❌ Utilisateur '{username}' non trouvé")
                return False
            
            if not user.is_mfa_enabled or not user.mfa_secret:
                print(f"❌ MFA n'est pas activé ou pas de secret pour '{username}'")
                return False
            
            secret = user.mfa_secret
            email = user.email or user.username
            
            print(f"✓ Utilisateur trouvé: {user.username}")
            print(f"  Email: {email}")
            print(f"  Secret stocké: {secret}")
            
            # Générer l'URL de provisioning
            totp = pyotp.TOTP(secret)
            otpauth_url = totp.provisioning_uri(
                name=email,
                issuer_name=settings.PROJECT_NAME
            )
            
            print(f"\n{'='*60}")
            print("GÉNÉRATION DU QR CODE")
            print(f"{'='*60}")
            print(f"URL: {otpauth_url}")
            
            # Générer le QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(otpauth_url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            qr_filename = f"mfa_qr_{username}.png"
            img.save(qr_filename)
            
            print(f"\n✓ QR code sauvegardé: {qr_filename}")
            
            # Générer le code actuel pour vérification
            current_code = totp.now()
            print(f"\n{'='*60}")
            print("INSTRUCTIONS")
            print(f"{'='*60}")
            print(f"\n1. Supprimez l'ancienne entrée 'FPI-CONNECT' dans Google Authenticator")
            print(f"   (si elle existe)")
            print(f"\n2. Scannez le QR code dans {qr_filename} avec Google Authenticator")
            print(f"   OU entrez manuellement le secret: {secret}")
            print(f"\n3. Vérifiez que le code généré correspond à: {current_code}")
            print(f"   (ou proche, car il change toutes les 30 secondes)")
            print(f"\n4. Le MFA devrait maintenant fonctionner correctement!")
            
            print(f"\n{'='*60}")
            print("VÉRIFICATION")
            print(f"{'='*60}")
            print(f"Code actuel attendu: {current_code}")
            print(f"\nAprès avoir scanné le QR code, vérifiez que Google Authenticator")
            print(f"génère le même code (ou un code très proche dans la même fenêtre de 30s)")
            
            return True
            
        finally:
            db.close()
            
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        print("   Exécutez depuis le dossier backend (venv activé), par exemple :")
        print("   python generate_mfa_qr.py admin")
        return False
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  python {sys.argv[0]} <username>")
        print("\nExemple:")
        print(f"  python {sys.argv[0]} admin")
        print("\nExécutez depuis le dossier backend (venv activé) si les imports échouent ailleurs.")
        sys.exit(1)
    
    username = sys.argv[1]
    
    print("="*60)
    print("GÉNÉRATION DU QR CODE MFA")
    print("="*60)
    print(f"Utilisateur: {username}")
    print()
    
    success = generate_qr_for_stored_secret(username)
    
    if success:
        print("\n✅ QR code généré avec succès!")
        sys.exit(0)
    else:
        print("\n❌ Échec de la génération")
        sys.exit(1)
