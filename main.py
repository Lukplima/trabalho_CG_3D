
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
from gerador_objetos import GeradorObjetos
from material import Material, Luz
from codigos3D.utils3d import *

PASTA = Path(__file__).parent
SHADERS = PASTA / "shaders"
LADO = 960
FUNDO = (0.08, 0.09, 0.11)


class InstanciaCena:
    """Posicao individual; a geometria e textura ficam no objeto de desenho compartilhado."""
    def __init__(self, x, y, z, raio=0.0):
        self.posicao = glm.vec3(x, y, z)
        self.base_y = y
        self.raio = raio
        self.rotacao = 0.0
        self.pitch = 0.0
        self.roll = 0.0



def orientar_objeto_no_solo(colisao, objeto, frente, lateral, inclinacao_maxima=25.0):
    """Calcula a inclinacao de um objeto parado consultando 4 pontos no mapa.

    Usa o mesmo principio das quatro amostras de altura do carro.
    Retorna False se nao houver solo suficiente sob os pontos.
    """
    angulo = objeto.rotacao  # orientacao horizontal da caixa (eixo Y)
    frente_x, frente_z = -math.sin(angulo), -math.cos(angulo)
    direita_x, direita_z = math.cos(angulo), -math.sin(angulo)

    # A referencia evita escolher uma superficie elevada acima da caixa.
    referencia = objeto.posicao.y + 0.15

    def altura_em(dx, dz):
        hit = colisao.consultar(objeto.posicao.x + dx,
                               objeto.posicao.z + dz, referencia)
        return None if hit is None else hit[0]

    h_frente = altura_em(frente_x * frente, frente_z * frente)
    h_tras = altura_em(-frente_x * frente, -frente_z * frente)
    h_direita = altura_em(direita_x * lateral, direita_z * lateral)
    h_esquerda = altura_em(-direita_x * lateral, -direita_z * lateral)

    limite = math.radians(inclinacao_maxima)
    if h_frente is not None and h_tras is not None:
        objeto.pitch = max(-limite, min(limite,
            math.atan2(h_frente - h_tras, 2.0 * frente)))
    if h_direita is not None and h_esquerda is not None:
        objeto.roll = max(-limite, min(limite,
            math.atan2(h_direita - h_esquerda, 2.0 * lateral)))

    return (h_frente is not None and h_tras is not None
            and h_direita is not None and h_esquerda is not None)


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

    malha = Malha(PASTA / "mapa.off")
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

    # Um UNICO gerador para todas as categorias: mesma malha e mesmas regras.
    malha_distribuicao = Malha(PASTA / "modelos" / "chao.off")
    gerador = GeradorObjetos(malha_distribuicao, modelo)

    # Configure aqui os tipos de objeto sem duplicar o algoritmo do sorteio.
    NUM_ESTRELAS_ALEATORIAS = 7
    NUM_CAIXAS = 10
    DISTANCIA_ESTRELAS = 3.5
    DISTANCIA_CAIXAS = 4.0
    MARGEM_BORDA = 0.75  # Estrelas
    MARGEM_BORDA_CAIXAS = 0.20  # Caixas: o raio de 0.65 ja conta como folga
    SEMENTE = None  # Inteiro para reproduzir as mesmas posicoes.
    RAIO_ESTRELA = 0.30
    RAIO_CAIXA = 0.65
    RAIO_CARRO = 0.50
    FOLGA_ENTRE_TIPOS = 0.50

    # As reservas impedem estrelas e caixas de nascerem no mesmo lugar.
    # A largada do jogador tambem fica reservada.
    reservas = [(0.0, 0.0, 2.0)]
    rng_posicoes = np.random.default_rng(SEMENTE)

    # Dados leves de cada instancia. O modelo OBJ/VBO/textura e carregado UMA vez
    # para todas as estrelas e UMA vez para todas as caixas.
    malha_estrela = Malha(PASTA / "modelos" / "estrela.off")
    limite_estrela = np.ptp(malha_estrela.vertices, axis=0)
    escala_estrela = 0.75 / float(limite_estrela[1])
    y_min_estrela = float(malha_estrela.vertices[:, 1].min())
    desenho_estrela = ObjetoOBJ(ctx, programa_textura, MODELOS / "estrela.obj")
    desenho_estrela.mudar_escala((escala_estrela,) * 3)

    estrelas = []
    # Uma estrela perto da largada, se a nova malha confirmar essa posicao.
    x_inicial, z_inicial = 17.0, -5.1
    altura_inicial = gerador.altura_no_ponto(x_inicial, z_inicial)
    if altura_inicial is not None and gerador.distancia_borda(x_inicial, z_inicial) >= MARGEM_BORDA + RAIO_ESTRELA:
        y = altura_inicial + 0.20 - y_min_estrela * escala_estrela
        estrelas.append(InstanciaCena(x_inicial, y, z_inicial, raio=RAIO_ESTRELA))
        reservas.append((x_inicial, z_inicial, RAIO_ESTRELA))

    pontos = gerador.sortear(
        NUM_ESTRELAS_ALEATORIAS,
        distancia_minima=DISTANCIA_ESTRELAS,
        margem=MARGEM_BORDA,
        pontos_existentes=reservas,
        semente=int(rng_posicoes.integers(0, 2**31)),
        raio=RAIO_ESTRELA,
        separacao=FOLGA_ENTRE_TIPOS,
    )
    for x, y_solo, z in pontos:
        y = y_solo + 0.20 - y_min_estrela * escala_estrela
        estrelas.append(InstanciaCena(x, y, z, raio=RAIO_ESTRELA))
        reservas.append((x, z, RAIO_ESTRELA))

    # As caixas sao obstaculos parados, sobre a MESMA faixa de pista.
    malha_caixa = Malha(PASTA / "modelos" / "caixa.off")
    dimensoes_caixa = np.ptp(malha_caixa.vertices, axis=0)
    escala_caixa = 0.28 / float(dimensoes_caixa[1])  # ~95 cm na escala do jogo.
    y_min_caixa = float(malha_caixa.vertices[:, 1].min())
    desenho_caixa = ObjetoOBJ(ctx, programa_textura, MODELOS / "caixa.obj")
    desenho_caixa.mudar_escala((escala_caixa,) * 3)

    caixas = []
    pontos = gerador.sortear(
        NUM_CAIXAS,
        distancia_minima=DISTANCIA_CAIXAS,
        margem=MARGEM_BORDA_CAIXAS,
        pontos_existentes=reservas,
        semente=int(rng_posicoes.integers(0, 2**31)),
        raio=RAIO_CAIXA,
        separacao=FOLGA_ENTRE_TIPOS,
    )
    for x, y_solo, z in pontos:
        y = y_solo - y_min_caixa * escala_caixa
        caixa = InstanciaCena(x, y, z, raio=RAIO_CAIXA)
        caixa.rotacao = float(rng_posicoes.uniform(-math.pi, math.pi))
        # Amostra o terreno nas quatro direcoes da caixa, como no carro.
        # As dimensoes em X e Z ja incluem a escala aplicada ao OBJ.
        raio_frente = max(0.05, float(dimensoes_caixa[2]) * escala_caixa * 0.40)
        raio_lateral = max(0.05, float(dimensoes_caixa[0]) * escala_caixa * 0.40)
        orientar_objeto_no_solo(colisao_pista, caixa, raio_frente, raio_lateral)
        caixas.append(caixa)
        reservas.append((x, z, RAIO_CAIXA))

    print(f"Distribuicao: {len(estrelas)} estrelas e {len(caixas)} caixas na pista.")

    tempo_estrela = 0.0
    velocidade_giro_estrela = glm.radians(90.0)
    amplitude_flutuacao = 0.12
    frequencia_flutuacao = 2.0

    player.mudar_escala((1.0, 1.0, 1.0))
    player.mudar_posicao((17.0, -0.2, -5.0))

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

        #pos antes do jog pra assim saber pra onde ir caso tenha colisão e a movimentação dele
        posicao_antes = glm.vec3(player.posicao)
        movimentando = player.movimentacao(frente, tras, esquerda, direita, dt)

        # Colisao basica jogador x caixa: nao atravessar obstaculos.

        #quanto andou
        px0, pz0 = posicao_antes.x, posicao_antes.z
        px1, pz1 = player.posicao.x, player.posicao.z
        dx, dz = px1 - px0, pz1 - pz0
        comprimento2 = dx * dx + dz * dz

        for caixa in caixas: #roda todas as caixas pra ve se colidiu com aula
            if comprimento2 > 1e-12: #se andou
                t = max(0.0, min(1.0,
                    ((caixa.posicao.x - px0) * dx + (caixa.posicao.z - pz0) * dz)
                    / comprimento2)) #olha a pos q chegou mais perto da caixa
            else:
                t = 0.0
            perto_x = px0 + t * dx
            perto_z = pz0 + t * dz
            limite = RAIO_CARRO + caixa.raio
            if (perto_x - caixa.posicao.x)**2 + (perto_z - caixa.posicao.z)**2 < limite**2: #se passou de r1+r2 q é limite ele  volta pra pos ant
                player.posicao.x = posicao_antes.x
                player.posicao.z = posicao_antes.z
                break

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

        # Todas as estrelas giram e flutuam independentemente do FPS.
        tempo_estrela += dt
        for i, estrela in enumerate(estrelas):
            estrela.rotacao += velocidade_giro_estrela * dt
            fase = tempo_estrela * frequencia_flutuacao + i * 0.5
            estrela.posicao.y = estrela.base_y + amplitude_flutuacao * math.sin(fase)

        # CAMERA
        camera.seguir(player, dt, esquerda, direita, movimentando)

        visao = camera.visao()
        projecao = camera.projecao()

        # LIMPA A TELA
        ctx.clear(*FUNDO, depth=1.0)

        # ILUMINACAO BLINN-PHONG: duas fontes no shader de objetos texturizados.
        # Tudo e calculado no ESPACO DO MUNDO no fragment shader.
        camera_posicao = glm.vec3(glm.inverse(visao)[3])
        programa_textura["u_camera_posicao"].value = tuple(camera_posicao)
        programa_textura["u_direcao_luz"].value = (-0.5, 1.0, 1.0)
        programa_textura["u_cor_luz_direcional"].value = (1.0, 1.0, 1.0)

        # O shader suporta uma fonte pontual: usa a estrela mais proxima do carro.
        if estrelas:
            estrela_luz = min(
                estrelas,
                key=lambda e: (e.posicao.x - player.posicao.x) ** 2
                              + (e.posicao.z - player.posicao.z) ** 2
            )
            programa_textura["u_luz_estrela_posicao"].value = tuple(estrela_luz.posicao)
            programa_textura["u_luz_estrela_intensidade"].value = 3.5
        else:
            programa_textura["u_luz_estrela_posicao"].value = (0.0, 0.0, 0.0)
            programa_textura["u_luz_estrela_intensidade"].value = 0.0
        programa_textura["u_luz_estrela_cor"].value = (1.0, 0.80, 0.24)

        # Mantem os uniformes do shader Phong sem textura (caso usados depois).
        posicao_luz_camera = visao * luz.posicao
        programa["u_luz"].value = tuple(posicao_luz_camera)
        programa["u_ka"].value = tuple(material.ka)
        programa["u_kd"].value = tuple(material.kd)
        programa["u_ks"].value = tuple(material.ks)
        programa["u_ia"].value = tuple(luz.ia)
        programa["u_id"].value = tuple(luz.id)
        programa["u_is"].value = tuple(luz.is_)
        programa["u_alfa"].value = material.alfa
        enviar_matriz(programa, "u_visao", visao)
        enviar_matriz(programa, "u_projecao", projecao)

        # O mesmo shader usa materiais distintos para mapa, estrela e carro.
        def definir_material(ka, kd, ks, alfa, emissao=(0.0, 0.0, 0.0)):
            programa_textura["u_ka"].value = ka
            programa_textura["u_kd"].value = kd
            programa_textura["u_ks"].value = ks
            programa_textura["u_alfa"].value = alfa
            programa_textura["u_emissao"].value = emissao

        # Mapa: difuso, pouco especular.
        definir_material((1.0, 1.0, 1.0), (1.0, 1.0, 1.0),
                         (0.08, 0.08, 0.08), 12.0)
        mapa.desenhar(visao, projecao)

        # Estrela: mais especular + emissao propria (nao e a luz pontual).
        definir_material((1.0, 1.0, 1.0), (1.0, 1.0, 1.0),
                         (0.8, 0.65, 0.25), 72.0,
                         (0.72, 0.52, 0.10))
        for estrela in estrelas:
            desenho_estrela.mudar_posicao(estrela.posicao)
            desenho_estrela.rotacao.y = estrela.rotacao
            desenho_estrela.desenhar(visao, projecao)

        # Caixas: material sem emissao, modelo e textura compartilhados.
        definir_material((1.0, 1.0, 1.0), (0.85, 0.85, 0.85),
                         (0.12, 0.12, 0.12), 16.0)
        for caixa in caixas:
            desenho_caixa.mudar_posicao(caixa.posicao)
            desenho_caixa.rotacao.x = caixa.pitch
            desenho_caixa.rotacao.y = caixa.rotacao
            desenho_caixa.rotacao.z = caixa.roll
            desenho_caixa.desenhar(visao, projecao)

        # Carro: brilho especular diferente do mapa e da estrela.
        definir_material((1.0, 1.0, 1.0), (1.0, 1.0, 1.0),
                         (0.35, 0.35, 0.35), 36.0)
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

    desenho_estrela.liberar()
    desenho_caixa.liberar()
    player.liberar()
    mapa.liberar()

    programa.release()
    programa_textura.release()
    glfw.terminate()

    print("Execucao finalizada.")


if __name__ == "__main__":
    main()
