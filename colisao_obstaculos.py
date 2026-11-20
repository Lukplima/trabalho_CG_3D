"""Testes de colisao simples e reutilizaveis entre objetos do jogo.

O carro e representado por uma caixa orientada pelo angulo Y (largura,
altura e comprimento), e o obstaculo por um cilindro vertical. O segmento
percorrido pelo centro do carro e subdividido para evitar tunelamento.
"""

import math


def colide_carro_caixa(origem, destino, centro_caixa, angulo_carro,
                       meia_largura, meia_altura, meio_comprimento,
                       raio_caixa, meia_altura_caixa, passo_maximo=0.04):
    """Retorna True se a caixa intercepta o volume do carro durante o deslocamento.

    origem/destino: centro do carro em coordenadas de mundo (x, y, z).
    centro_caixa: centro do obstaculo em coordenadas de mundo.
    angulo_carro: rotacao do carro no eixo Y (em radianos).
    Dimensoes: metades positivas das dimensoes do carro e da caixa.
    """
    if min(meia_largura, meia_altura, meio_comprimento,
           raio_caixa, meia_altura_caixa, passo_maximo) <= 0:
        raise ValueError("Dimensoes de colisao e passo devem ser positivos")

    dx = destino[0] - origem[0]
    dy = destino[1] - origem[1]
    dz = destino[2] - origem[2]
    comprimento = math.sqrt(dx * dx + dy * dy + dz * dz)
    etapas = max(1, math.ceil(comprimento / passo_maximo))
    co = math.cos(angulo_carro)
    si = math.sin(angulo_carro)
    raio2 = raio_caixa * raio_caixa

    for i in range(etapas + 1):
        t = i / etapas
        x = origem[0] + dx * t
        y = origem[1] + dy * t
        z = origem[2] + dz * t

        # Rejeicao vertical: caixa e carro estao em alturas diferentes.
        if abs(y - centro_caixa[1]) >= meia_altura + meia_altura_caixa:
            continue

        # Posicao da caixa nos eixos locais do carro, considerando a guinada Y.
        rx = centro_caixa[0] - x
        rz = centro_caixa[2] - z
        local_x = co * rx - si * rz
        local_z = si * rx + co * rz

        # Distancia do centro da caixa ate o retangulo do carro no plano XZ.
        fora_x = max(abs(local_x) - meia_largura, 0.0)
        fora_z = max(abs(local_z) - meio_comprimento, 0.0)
        if fora_x * fora_x + fora_z * fora_z < raio2:
            return True

    return False
