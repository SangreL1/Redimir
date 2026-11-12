"""
Utilidades de RUT chileno — Redimir SpA
Normalización segura sin riesgos de inyección SQL.
"""
import re


def limpiar_rut(rut: str) -> str:
    """
    Elimina puntos, guiones, espacios y caracteres no permitidos.
    Solo deja dígitos y la letra K (para el dígito verificador).
    Resultado: '250746229' o '25074622K'
    """
    return re.sub(r'[^0-9kK]', '', str(rut or '')).upper()


def formatear_rut(rut: str) -> str:
    """
    Normaliza cualquier variante de RUT al formato estándar con puntos y guión.
    Ejemplos:
        '250746229'    -> '25.074.622-9'
        '25074622-9'   -> '25.074.622-9'
        '25.074.622-9' -> '25.074.622-9'
        '7123456k'     -> '7.123.456-K'
    """
    limpio = limpiar_rut(rut)
    if len(limpio) < 2:
        return rut.strip().upper()
    cuerpo = limpio[:-1]
    dv = limpio[-1]
    # Insertar puntos cada 3 dígitos desde la derecha
    rev = cuerpo[::-1]
    partes = [rev[i:i+3] for i in range(0, len(rev), 3)]
    cuerpo_formateado = '.'.join(partes)[::-1]
    return f'{cuerpo_formateado}-{dv}'


def variantes_rut(rut: str) -> list:
    """
    Genera todas las variantes posibles de un RUT para buscarlo en la BD
    sin importar como fue guardado originalmente.
    Retorna una lista de cadenas únicas y seguras (sin caracteres especiales peligrosos).
    """
    limpio = limpiar_rut(rut)
    if len(limpio) < 2:
        return [rut.strip().upper()]

    cuerpo = limpio[:-1]
    dv = limpio[-1]

    # Formato con puntos y guión: 25.074.622-9
    rev = cuerpo[::-1]
    partes = [rev[i:i+3] for i in range(0, len(rev), 3)]
    cuerpo_puntos = '.'.join(partes)[::-1]
    con_puntos = f'{cuerpo_puntos}-{dv}'

    # Formato sin puntos con guión: 25074622-9
    sin_puntos_con_guion = f'{cuerpo}-{dv}'

    # Solo dígitos: 250746229
    solo_digitos = limpio

    return list(dict.fromkeys([con_puntos, sin_puntos_con_guion, solo_digitos]))

