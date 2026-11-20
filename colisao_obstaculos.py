"""Colisao aproximada 3D entre o trajeto do carro e um obstaculo.

O carro e a caixa usam limites arredondados: um raio horizontal (XZ) e
um vertical (Y). O segmento e testado inteiro, sem tunelamento entre frames.
As dimensoes podem ser ajustadas no main.py, sem alterar este algoritmo.
"""


def colide_trajeto_3d(origem, destino, centro_obstaculo,
                      raio_horizontal, raio_vertical):
    """Retorna True quando o trajeto entra no volume 3D de colisao.

    Normaliza X/Z pelo raio horizontal e Y pelo raio vertical. Nesse
    espaco, o obstaculo e uma esfera unitaria; usamos o ponto mais proximo
    ao centro sobre o segmento entre origem e destino.
    """
    if raio_horizontal <= 0 or raio_vertical <= 0:
        raise ValueError("Raios de colisao devem ser positivos")

    # Ponto inicial relativo ao centro, nas dimensoes normalizadas.
    ax = (origem[0] - centro_obstaculo[0]) / raio_horizontal
    ay = (origem[1] - centro_obstaculo[1]) / raio_vertical
    az = (origem[2] - centro_obstaculo[2]) / raio_horizontal

    # Movimento 3D normalizado.
    dx = (destino[0] - origem[0]) / raio_horizontal
    dy = (destino[1] - origem[1]) / raio_vertical
    dz = (destino[2] - origem[2]) / raio_horizontal
    comprimento2 = dx * dx + dy * dy + dz * dz

    if comprimento2 > 1e-12:
        t = max(0.0, min(1.0, -(ax * dx + ay * dy + az * dz) / comprimento2))
    else:
        t = 0.0

    px = ax + t * dx
    py = ay + t * dy
    pz = az + t * dz
    return px * px + py * py + pz * pz < 1.0
