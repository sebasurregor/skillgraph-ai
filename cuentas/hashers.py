"""Cifrado de contraseñas (HU-RNF-001).

Algoritmo: bcrypt sobre un resumen SHA-256 de la contraseña (evita el límite de
72 bytes de bcrypt). Factor de costo: 12, es decir 2^12 = 4096 iteraciones.
Cada contraseña lleva su propia sal aleatoria de 128 bits.
Formato almacenado: bcrypt_sha256$$2b$12$<sal+hash>
"""
from django.contrib.auth.hashers import BCryptSHA256PasswordHasher

COSTO_MINIMO = 12


class BCryptCosto12PasswordHasher(BCryptSHA256PasswordHasher):
    rounds = COSTO_MINIMO
