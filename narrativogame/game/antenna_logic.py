import random


def calcular_probabilidad(altura, energia, actividad, cercania):
    """
    Calcula la probabilidad de caída de un rayo.

    Los valores deben estar entre 0 y 1.
    """

    probabilidad = (
        altura * 0.40
        + energia * 0.30
        + actividad * 0.20
        + cercania * 0.10
    )

    # La probabilidad mínima es 5 % y la máxima 95 %
    return max(0.05, min(probabilidad, 0.95))


def cae_rayo(probabilidad):
    """
    Devuelve True si el rayo es capturado.
    """
    return random.random() < probabilidad


def simular_tormenta(zonas, cantidad_rayos=5):
    """
    Simula la caída de varios rayos.

    Cada zona debe tener este formato:

    {
        "nombre": "Árbol alto",
        "probabilidad": 0.80
    }
    """

    resultados = []

    for numero in range(cantidad_rayos):
        zona = random.choice(zonas)
        capturado = cae_rayo(zona["probabilidad"])

        resultados.append({
            "numero": numero + 1,
            "zona": zona["nombre"],
            "capturado": capturado
        })

    return resultados


def obtener_resultado(capturados, total):
    """
    Devuelve el resultado final de la tormenta.
    """

    if capturados >= total * 0.8:
        return "exito"

    if capturados >= total * 0.4:
        return "parcial"

    return "fallo"