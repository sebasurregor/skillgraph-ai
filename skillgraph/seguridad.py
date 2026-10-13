"""Ajustes de seguridad de transporte (HU-RNF-001).

En producción (DEBUG=False) todo el tráfico va por HTTPS. Django no negocia TLS:
la versión mínima (TLS 1.2) se fija en el proxy o la plataforma que termina la
conexión; aquí se obliga la redirección, las cookies seguras y HSTS.
"""

UN_ANIO = 60 * 60 * 24 * 365


def seguridad_transporte(debug):
    """Devuelve los ajustes de Django según el modo de ejecución."""
    produccion = not debug
    return {
        "SECURE_SSL_REDIRECT": produccion,
        "SESSION_COOKIE_SECURE": produccion,
        "CSRF_COOKIE_SECURE": produccion,
        "SECURE_HSTS_SECONDS": UN_ANIO if produccion else 0,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": produccion,
        "SECURE_HSTS_PRELOAD": produccion,
        # El proxy que termina TLS informa el esquema original con esta cabecera.
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https") if produccion else None,
    }
