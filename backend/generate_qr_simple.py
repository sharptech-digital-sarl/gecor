#!/usr/bin/env python3
"""
Script simple pour générer un QR code MFA
Utilise le secret stocké en base pour générer le QR code
"""

import pyotp
import qrcode

# Secret récupéré depuis la base de données (via diagnose_mfa.py)
SECRET = "KPN2KCKGK2MQJ3OCM7SL5HJN4QBFBBAL"
EMAIL = "joelnyengele@gmail.com"
ISSUER = "FPI-CONNECT"

# Générer l'URL de provisioning
totp = pyotp.TOTP(SECRET)
otpauth_url = totp.provisioning_uri(
    name=EMAIL,
    issuer_name=ISSUER
)

print("="*60)
print("GÉNÉRATION DU QR CODE MFA")
print("="*60)
print(f"Secret: {SECRET}")
print(f"Email: {EMAIL}")
print(f"Issuer: {ISSUER}")
print(f"\nURL: {otpauth_url}")

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
filename = "mfa_qr_admin.png"
img.save(filename)

print(f"\n[OK] QR code sauvegarde: {filename}")
print(f"\n{'='*60}")
print("INSTRUCTIONS")
print("="*60)
print("1. Supprimez l'ancienne entree 'FPI-CONNECT' dans Google Authenticator")
print("2. Scannez le QR code dans", filename)
print("3. Verifiez que le code genere correspond")

# Afficher le code actuel
current_code = totp.now()
print(f"\nCode actuel attendu: {current_code}")
print("(Verifiez que Google Authenticator affiche le meme code)")
