#!/usr/bin/env python3
"""
Script helper pour tester le MFA
Génère des codes TOTP à partir d'un secret
"""

import pyotp
import sys
import time
from datetime import datetime


def generate_totp_code(secret: str):
    """Génère le code TOTP actuel pour un secret donné"""
    try:
        totp = pyotp.TOTP(secret)
        current_code = totp.now()
        return current_code
    except Exception as e:
        print(f"Erreur lors de la génération du code: {e}")
        return None


def verify_totp_code(secret: str, code: str):
    """Vérifie si un code TOTP est valide"""
    try:
        totp = pyotp.TOTP(secret)
        is_valid = totp.verify(code, valid_window=1)
        return is_valid
    except Exception as e:
        print(f"Erreur lors de la vérification: {e}")
        return False


def generate_otpauth_url(secret: str, email: str = "user@example.com", issuer: str = "FPI Connect"):
    """Génère l'URL otpauth pour créer un QR code"""
    totp = pyotp.TOTP(secret)
    url = totp.provisioning_uri(name=email, issuer_name=issuer)
    return url


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_mfa_helper.py <secret>                    # Génère le code actuel")
        print("  python test_mfa_helper.py <secret> verify <code>     # Vérifie un code")
        print("  python test_mfa_helper.py <secret> url <email>        # Génère l'URL otpauth")
        print("\nExemple:")
        print("  python test_mfa_helper.py JBSWY3DPEHPK3PXP")
        print("  python test_mfa_helper.py JBSWY3DPEHPK3PXP verify 123456")
        print("  python test_mfa_helper.py JBSWY3DPEHPK3PXP url admin@example.com")
        sys.exit(1)
    
    secret = sys.argv[1]
    
    if len(sys.argv) == 2:
        # Générer le code actuel
        code = generate_totp_code(secret)
        if code:
            print(f"\n{'='*50}")
            print(f"Secret: {secret}")
            print(f"Code TOTP actuel: {code}")
            print(f"Temps: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*50}\n")
            print("Note: Le code change toutes les 30 secondes")
            print("      Utilisez ce code dans les 30 prochaines secondes\n")
    
    elif len(sys.argv) >= 3:
        command = sys.argv[2]
        
        if command == "verify" and len(sys.argv) >= 4:
            code_to_verify = sys.argv[3]
            is_valid = verify_totp_code(secret, code_to_verify)
            if is_valid:
                print(f"✓ Code {code_to_verify} est VALIDE")
            else:
                print(f"✗ Code {code_to_verify} est INVALIDE ou expiré")
                print("  Assurez-vous d'utiliser un code récent (généré dans les 30 dernières secondes)")
        
        elif command == "url":
            email = sys.argv[3] if len(sys.argv) >= 4 else "user@example.com"
            url = generate_otpauth_url(secret, email)
            print(f"\n{'='*50}")
            print(f"Secret: {secret}")
            print(f"Email: {email}")
            print(f"otpauth URL: {url}")
            print(f"{'='*50}\n")
            print("Copiez cette URL dans un générateur de QR code:")
            print("https://www.qr-code-generator.com/")
            print("ou utilisez la bibliothèque qrcode en Python\n")
        
        else:
            print(f"Commande inconnue: {command}")
            sys.exit(1)


if __name__ == "__main__":
    main()
