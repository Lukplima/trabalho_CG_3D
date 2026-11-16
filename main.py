
import sys
import math
from pathlib import Path

import glfw
import glm
import moderngl
import numpy as np

from camera import Camera
from malha import Malha
from colisao_pista import ColisaoPista
from material import Material, Luz
from codigos3D.utils3d import *

PASTA = Path(__file__).parent
SHADERS = PASTA / "shaders"
LADO = 960
FUNDO = (0.08, 0.09, 0.11)


def erro_glfw(codigo, descricao):
    print(f"GLFW [{codigo}]: {descricao}", file=sys.stderr)


def carregar_programa(ctx):
    return ctx.program(
        vertex_shader=(SHADERS / "phong.vert").read_text(encoding="utf-8"),
        fragment_shader=(SHADERS / "phong.frag").read_text(encoding="utf-8"),
    )


def carregar_programa_textura(ctx):
    return ctx.program(
        vertex_shader=(SHADERS / "textura.vert").read_text(encoding="utf-8"),
        fragment_shader=(SHADERS / "textura.frag").read_text(encoding="utf-8"),
    )


def matriz_normal(modelo):
    return glm.transpose(glm.inverse(glm.mat3(modelo)))


def enviar_matriz(programa, nome, matriz):
    programa[nome].write(matriz.to_bytes())


def main():
    glfw.set_error_callback(erro_glfw)
    if not glfw.init():
        sys.exit("FALHA: glfw nao inicializou")

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 0)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
    glfw.window_hint(glfw.SAMPLES, 4)

    janela = glfw.create_window(LADO, LADO, "CaReca 3D - Base", None, None)
    if not janela:
        glfw.terminate()
        sys.exit("FALHA: nao foi possivel criar a janela")

    glfw.make_context_current(janela)
    vsync = True
    glfw.swap_interval(1)

    ctx = moderngl.create_context()
    ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
    ctx.front_face = "ccw"

    malha = Malha("mapa.off")
    programa = carregar_programa(ctx)
    programa_textura = carregar_programa_textura(ctx)

    camera = Camera(distancia=5.0)
    material = Material()
    luz = Luz()

    modelo = glm.scale(
        malha.matriz_enquadramento(),
        glm.vec3(60.0, 60.0, 60.0)
    )

    colisao_pista = ColisaoPista(malha, modelo)

    arrastando = False
    ultimo_cursor = None

    import time

    # OBJETOS
    inicio = time.perf_counter()
    player = Player(ctx, programa_textura)
    print(f"Player carregado em {time.perf_counter() - inicio:.2f}s")

    inicio = time.perf_counter()
    mapa = Mapa(ctx, programa_textura, modelo)
    print(f"Árvores carregadas em {time.perf_counter() - inicio:.2f}s")

    player.mudar_escala((0.5, 0.5, 0.5))
    player.mudar_posicao((0.0, 0.4, 0.0))

    altura_chassi = 0.21  # Mantem o ajuste anterior das rodas
    distancia_frente = 0.38  # Pontos de amostragem no sentido do carro
    distancia_lateral = 0.26  # Pontos de amostragem entre os lados
    inclinacao_maxima = glm.radians(25.0)
    velocidade_suavizacao = 7.0

    contato_inicial = colisao_pista.consultar(player.posicao.x, player.posicao.z)
    if contato_inicial is not None:
        player.posicao.y = contato_inicial[0] + altura_chassi
    else:
        print("AVISO: não há superfície sob a posição inicial do carro.")

    def tecla(window, key, scancode, action, mods):
        nonlocal vsync
        if action != glfw.PRESS:
            return
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)
        elif key == glfw.KEY_V:
            vsync = not vsync
            glfw.swap_interval(1 if vsync else 0)

    def botao_mouse(window, button, action, mods):
        nonlocal arrastando, ultimo_cursor
        if button != glfw.MOUSE_BUTTON_LEFT:
            return
        if action == glfw.PRESS:
            arrastando = True
            ultimo_cursor = glfw.get_cursor_pos(window)
        elif action == glfw.RELEASE:
            arrastando = False
            ultimo_cursor = None

    def mover_mouse(window, x, y):
        nonlocal ultimo_cursor
        if not arrastando or ultimo_cursor is None:
            return
        dx = x - ultimo_cursor[0]
        dy = y - ultimo_cursor[1]
        camera.orbitar(dx, dy)
        ultimo_cursor = (x, y)

    def rolagem(window, dx, dy):
        camera.zoom(dy)

    def redimensionar(window, largura, altura):
        largura, altura = max(1, largura), max(1, altura)
        ctx.viewport = (0, 0, largura, altura)
        camera.aspecto = largura / altura

    glfw.set_key_callback(janela, tecla)
    glfw.set_mouse_button_callback(janela, botao_mouse)
    glfw.set_cursor_pos_callback(janela, mover_mouse)
    glfw.set_scroll_callback(janela, rolagem)
    glfw.set_framebuffer_size_callback(janela, redimensionar)
    redimensionar(janela, *glfw.get_framebuffer_size(janela))

    instante_anterior = glfw.get_time()
    quadros = 0
    marco_fps = instante_anterior

    while not glfw.window_should_close(janela):
        agora = glfw.get_time()
        dt = min(agora - instante_anterior, 0.05)
        instante_anterior = agora

        # CONTROLES DO JOGADOR
        frente = glfw.get_key(janela, glfw.KEY_UP) == glfw.PRESS
        tras = glfw.get_key(janela, glfw.KEY_DOWN) == glfw.PRESS
        esquerda = glfw.get_key(janela, glfw.KEY_LEFT) == glfw.PRESS
        direita = glfw.get_key(janela, glfw.KEY_RIGHT) == glfw.PRESS

        movimentando = player.movimentacao(frente, tras, esquerda, direita, dt)

        # O carro se move em X/Z no Player; a altura vem da malha real do mapa.
        contato = colisao_pista.consultar(
            player.posicao.x, player.posicao.z,
            player.posicao.y - altura_chassi + 0.15
        )

        if contato is not None:
            altura_pista, normal_pista = contato
            player.posicao.y = altura_pista + altura_chassi

        # Se não há superfície, mantém a altura anterior (sem teleporte).
        # A orientação horizontal do carro permanece em rotacao.y.
        angulo = player.rotacao.y
        frente_x, frente_z = -math.sin(angulo), -math.cos(angulo)
        direita_x, direita_z = math.cos(angulo), -math.sin(angulo)

        # Usa a mesma referência vertical do raycast central para evitar
        # escolher superfícies acima do carro (pontes e objetos do mapa).
        referencia = player.posicao.y - altura_chassi + 0.15

        def altura_em(dx, dz):
            hit = colisao_pista.consultar(
                player.posicao.x + dx,
                player.posicao.z + dz,
                referencia
            )
            return None if hit is None else hit[0]

        altura_frente = altura_em(
            frente_x * distancia_frente,
            frente_z * distancia_frente
        )
        altura_tras = altura_em(
            -frente_x * distancia_frente,
            -frente_z * distancia_frente
        )
        altura_direita = altura_em(
            direita_x * distancia_lateral,
            direita_z * distancia_lateral
        )
        altura_esquerda = altura_em(
            -direita_x * distancia_lateral,
            -direita_z * distancia_lateral
        )

        # Angulos locais: X = subir/descer; Z = tombar para os lados.
        # Se faltarem pontos sob as rodas, retorna gradualmente ao plano.
        alvo_pitch = 0.0
        alvo_roll = 0.0

        if altura_frente is not None and altura_tras is not None:
            alvo_pitch = math.atan2(
                altura_frente - altura_tras,
                2.0 * distancia_frente
            )

        if altura_direita is not None and altura_esquerda is not None:
            alvo_roll = math.atan2(
                altura_direita - altura_esquerda,
                2.0 * distancia_lateral
            )

        alvo_pitch = max(-inclinacao_maxima, min(inclinacao_maxima, alvo_pitch))
        alvo_roll = max(-inclinacao_maxima, min(inclinacao_maxima, alvo_roll))

        fator = 1.0 - math.exp(-velocidade_suavizacao * dt)
        player.rotacao.x += (alvo_pitch - player.rotacao.x) * fator
        player.rotacao.z += (alvo_roll - player.rotacao.z) * fator

        player.atualizar(dt)

        # CAMERA
        camera.seguir(player, dt, esquerda, direita, movimentando)

        visao = camera.visao()
        projecao = camera.projecao()

        # LIMPA A TELA
        ctx.clear(*FUNDO, depth=1.0)

        # ILUMINACAO
        posicao_luz_camera = visao * luz.posicao

        programa["u_luz"].value = tuple(posicao_luz_camera)
        programa["u_ka"].value = tuple(material.ka)
        programa["u_kd"].value = tuple(material.kd)
        programa["u_ks"].value = tuple(material.ks)

        programa["u_ia"].value = tuple(luz.ia)
        programa["u_id"].value = tuple(luz.id)
        programa["u_is"].value = tuple(luz.is_)

        programa["u_alfa"].value = material.alfa

        # MATRIZES DA CAMERA
        enviar_matriz(programa, "u_visao", visao)
        enviar_matriz(programa, "u_projecao", projecao)

        # RENDERIZA AS mapa
        mapa.desenhar(visao, projecao)

        # RENDERIZA O JOGADOR
        player.desenhar(visao, projecao)

        # FPS
        quadros += 1

        if agora - marco_fps >= 0.5:
            fps = quadros / (agora - marco_fps)
            glfw.set_window_title(janela, f"CaReca 3D | {fps:.1f} FPS")
            quadros = 0
            marco_fps = agora

        glfw.swap_buffers(janela)
        glfw.poll_events()

    player.liberar()
    mapa.liberar()

    programa.release()
    programa_textura.release()
    glfw.terminate()

    print("Execucao finalizada.")


if __name__ == "__main__":
    main()
