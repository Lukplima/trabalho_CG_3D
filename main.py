# CONTROLES:
# ESC - Fechar
# V - Ativar/desativar V-Sync
# Mouse esquerdo + arrastar - Orbitar a camera
# Roda do mouse - Aproximar/afastar a camera
# Executar: python main.py (abre uma janela para escolher o modelo OFF)

import sys
from pathlib import Path

import glfw
import glm
import moderngl
import numpy as np

from camera import Camera
from malha import Malha
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
    dados = malha.dados_gpu()
    indices = malha.indices_gpu()
    vbo = ctx.buffer(dados.tobytes())
    ebo = ctx.buffer(indices.tobytes())
    vao = ctx.vertex_array(
        programa,
        [(vbo, "3f 3f", "vPosition", "vNormal")],
        index_buffer=ebo,
    )

    camera = Camera(distancia=5.0)
    material = Material()
    luz = Luz()
    modelo = glm.scale(
    malha.matriz_enquadramento(),
    glm.vec3(60.0, 60.0, 60.0))
    arrastando = False
    ultimo_cursor = None

    #Objetos
    player = Player(ctx, programa_textura)

    player.mudar_escala((0.5, 0.5, 0.5))
    player.mudar_posicao((0.0, 0.4, 0.0))

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

        # RENDERIZA O MAPA
        programa["u_modelo"].write(modelo.to_bytes())

        enviar_matriz(
            programa,
            "u_normal",
            matriz_normal(modelo)
        )

        vao.render(mode=moderngl.TRIANGLES)

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

    vao.release()
    vbo.release()
    ebo.release()
    programa.release()
    glfw.terminate()
    print("Execucao finalizada.")


if __name__ == "__main__":
    main()
