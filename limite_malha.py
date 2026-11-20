from pathlib import Path

import glm

from malha import Malha
from colisao_pista import ColisaoPista


# A malha usada para limitar o jogador e carregada apenas uma vez.
_colisao_limite = None


def _carregar_colisao_limite():
    global _colisao_limite

    if _colisao_limite is None:
        pasta = Path(__file__).parent

        # Reproduz exatamente a transformacao aplicada ao mapa na main.py.
        malha_mapa = Malha(pasta / "mapa.off")
        modelo = glm.scale(
            malha_mapa.matriz_enquadramento(),
            glm.vec3(60.0, 60.0, 60.0)
        )

        # A area permitida para o jogador e definida por modelos/chao.off.
        malha_chao = Malha(pasta / "modelos" / "chao.off")
        _colisao_limite = ColisaoPista(malha_chao, modelo)

    return _colisao_limite


def movimentar_com_limite(player, colisao_pista, frente, tras, esquerda, direita,
                          dt, distancia_frente, distancia_lateral):
    """Move o Player sem permitir que sua area amostrada saia de modelos/chao.off.

    Retorna (movimentando, posicao_anterior), para a main continuar usando
    a posicao anterior nas verificacoes de colisao com os obstaculos.

    O parametro colisao_pista e mantido para preservar a chamada existente
    na main.py; a verificacao dos limites usa a malha modelos/chao.off.
    """
    colisao_limite = _carregar_colisao_limite()

    posicao_anterior = glm.vec3(player.posicao)
    rotacao_anterior = glm.vec3(player.rotacao)

    movimentando = player.movimentacao(frente, tras, esquerda, direita, dt)

    if not movimentando:
        return False, posicao_anterior

    if player.dentro_da_malha(
        colisao_limite, distancia_frente, distancia_lateral
    ):
        return True, posicao_anterior

    # Guarda o destino tentado e procura o ultimo ponto valido do trajeto.
    posicao_destino = glm.vec3(player.posicao)
    rotacao_destino = glm.vec3(player.rotacao)

    # Se a posicao anterior ja nao estiver valida, nao tenta avancar.
    player.mudar_posicao(posicao_anterior)
    player.mudar_rotacao(rotacao_anterior)
    if not player.dentro_da_malha(
        colisao_limite, distancia_frente, distancia_lateral
    ):
        return True, posicao_anterior

    inicio = 0.0
    fim = 1.0

    # Busca binaria para chegar o mais perto possivel do limite sem ultrapassa-lo.
    for _ in range(14):
        meio = (inicio + fim) / 2.0
        player.mudar_posicao(posicao_anterior + (posicao_destino - posicao_anterior) * meio)
        player.mudar_rotacao(rotacao_anterior + (rotacao_destino - rotacao_anterior) * meio)

        if player.dentro_da_malha(
            colisao_limite, distancia_frente, distancia_lateral
        ):
            inicio = meio
        else:
            fim = meio

    # Pequena folga para evitar ficar exatamente sobre a aresta numerica.
    fator = max(0.0, inicio - 0.001)
    player.mudar_posicao(posicao_anterior + (posicao_destino - posicao_anterior) * fator)
    player.mudar_rotacao(rotacao_anterior + (rotacao_destino - rotacao_anterior) * fator)

    return True, posicao_anterior
