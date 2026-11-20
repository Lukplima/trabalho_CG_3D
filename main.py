# CONTROLES (reaproveitados do Trabalho 03):
# ESPACO - Iniciar o jogo
# SETAS - Movimentar o carro
# P - Pausar ou retomar a partida
# R - Reiniciar apos o Game Over
# V - Ativar ou desativar o V-Sync
# MOUSE - Girar/aproximar a camera
# ESC - Fechar o jogo


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
from colisao_obstaculos import colide_trajeto_3d
from gerador_objetos import GeradorObjetos
from material import Material, Luz
from codigos3D.utils3d import *
from hud_vidas import HUDVidas
from sprite_2d import Renderizador2D
from sistema_vidas import SistemaVidas

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

    # Renderer unico de PNGs 2D: coracoes, menus, pausa, pontuacao, etc.
    sprites_2d = Renderizador2D(ctx, SHADERS)
    hud_vidas = HUDVidas(sprites_2d, PASTA / "imagens" / "heart_32x32.png",
                        PASTA / "imagens" / "heart_empty_32x32.png", total=3)
    # Mesmas telas do Trabalho 03, desenhadas pelo Sprite2D reutilizavel.
    # O retangulo, o VBO/VAO e o programa GLSL sao compartilhados pelo HUD.
    pasta_imagens = PASTA / "imagens"
    tela_inicio = sprites_2d.criar_sprite(pasta_imagens / "tela_inicial.png")
    tela_pausa = sprites_2d.criar_sprite(pasta_imagens / "tela_paused.png")
    tela_gameover = sprites_2d.criar_sprite(pasta_imagens / "tela_gameover.png")

    # Estados mantidos do Trabalho 03: inicio, pausa e gameover.
    inicio = True
    pause = False
    gameover = False
    tempo_jogo = 0.0  # So avanca com a partida em andamento.

    # Mesmos metodos do CarroPlayer do jogo 2D, adaptados ao carro 3D.
    sistema_vidas = SistemaVidas(total=3, intervalo_dano=1.2)

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
    inicio_carregamento = time.perf_counter()
    player = Player(ctx, programa_textura)
    print(f"Player carregado em {time.perf_counter() - inicio_carregamento:.2f}s")

    inicio_carregamento = time.perf_counter()
    mapa = Mapa(ctx, programa_textura, modelo)
    print(f"Mapa carregado em {time.perf_counter() - inicio_carregamento:.2f}s")

    # Um UNICO gerador para todas as categorias: mesma malha e mesmas regras.
    malha_distribuicao = Malha(PASTA / "modelos" / "chao.off")
    gerador = GeradorObjetos(malha_distribuicao, modelo)

    # Configure aqui os tipos de objeto sem duplicar o algoritmo do sorteio.
    NUM_ESTRELAS_ALEATORIAS = 7
    NUM_CAIXAS = 30
    DISTANCIA_ESTRELAS = 3.5
    MARGEM_BORDA = 0.75  # Estrelas
    DISTANCIA_CAIXAS = 1.8
    MARGEM_BORDA_CAIXAS = 0.10
    SEMENTE = None  # Inteiro para reproduzir as mesmas posicoes.
    RAIO_ESTRELA = 0.30
    RAIO_CAIXA = 0.42  # Usado somente para distribuir as caixas na pista.
    RAIO_COLISAO_CAIXA = 0.23  # Área real de bloqueio menor.
    RAIO_COLISAO_CARRO = 0.18  # Raio horizontal do carro (colisao).
    MEIA_ALTURA_COLISAO_CARRO = 0.16  # Metade da altura usada na colisao 3D.
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
    MEIA_ALTURA_COLISAO_CAIXA = float(dimensoes_caixa[1]) * escala_caixa / 2.0
    CENTRO_LOCAL_CAIXA_Y = (float(malha_caixa.vertices[:, 1].min())
                            + float(malha_caixa.vertices[:, 1].max())) * escala_caixa / 2.0

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

    def reiniciar_partida():
        """Reinicia vidas, tempo, carro e animacao, sem recarregar recursos GPU."""
        nonlocal inicio, pause, gameover, tempo_jogo, tempo_estrela
        sistema_vidas.reinicia_vidas()
        inicio, pause, gameover = False, False, False
        tempo_jogo = 0.0
        tempo_estrela = 0.0
        player.mudar_posicao((0.0, 0.4, 0.0))
        player.mudar_rotacao((0.0, 0.0, 0.0))
        contato = colisao_pista.consultar(0.0, 0.0)
        if contato is not None:
            player.posicao.y = contato[0] + altura_chassi
        for estrela in estrelas:
            estrela.posicao.y = estrela.base_y
            estrela.rotacao = 0.0
        print("Partida reiniciada: 3 vidas")

    def tecla(window, key, scancode, action, mods):
        nonlocal vsync, inicio, pause, arrastando, ultimo_cursor
        if action != glfw.PRESS:
            return
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)
        elif key == glfw.KEY_V:
            vsync = not vsync
            glfw.swap_interval(1 if vsync else 0)
        elif key == glfw.KEY_SPACE and inicio:
            inicio = False
        elif key == glfw.KEY_P and not inicio and not gameover:
            pause = not pause
            # Cancela arrasto para nao mover a camera nem dar saltos na volta.
            arrastando = False
            ultimo_cursor = None
        elif key == glfw.KEY_R and gameover:
            reiniciar_partida()

    def botao_mouse(window, button, action, mods):
        nonlocal arrastando, ultimo_cursor
        if inicio or pause or gameover:
            arrastando = False
            ultimo_cursor = None
            return
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
        if inicio or pause or gameover or not arrastando or ultimo_cursor is None:
            return
        dx = x - ultimo_cursor[0]
        dy = y - ultimo_cursor[1]
        camera.orbitar(dx, dy)
        ultimo_cursor = (x, y)

    def rolagem(window, dx, dy):
        if not inicio and not pause and not gameover:
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

        # No Trabalho 03, so se atualiza o jogo no estado "jogando".
        # Ao pausar, dt continua sendo medido, mas nao move nenhum objeto.
        if not inicio and not pause and not gameover:
            tempo_jogo += dt
            # CONTROLES DO JOGADOR
            frente = glfw.get_key(janela, glfw.KEY_UP) == glfw.PRESS
            tras = glfw.get_key(janela, glfw.KEY_DOWN) == glfw.PRESS
            esquerda = glfw.get_key(janela, glfw.KEY_LEFT) == glfw.PRESS
            direita = glfw.get_key(janela, glfw.KEY_RIGHT) == glfw.PRESS

            #pos antes do jog pra assim saber pra onde ir caso tenha colisão e a movimentação dele
            posicao_antes = glm.vec3(player.posicao)
            sistema_vidas.reinicia_colisao()
            if sistema_vidas.vida_atual() > 0:
                movimentando = player.movimentacao(frente, tras, esquerda, direita, dt)
            else:
                movimentando = False  # Sem vidas: carro parado

            # Colisao 3D carro x caixa:
            # - consulta a altura no destino antes de validar a movimentacao;
            # - considera X, Y e Z (nao bloqueia caixas em outro nivel);
            # - testa TODO o trajeto, evitando atravessar uma caixa entre frames.
            contato_destino = colisao_pista.consultar(
                player.posicao.x, player.posicao.z,
                posicao_antes.y - altura_chassi + 0.15
            )
            y_destino = (contato_destino[0] + altura_chassi
                         if contato_destino is not None else posicao_antes.y)
            destino = (player.posicao.x, y_destino, player.posicao.z)

            for caixa in caixas:
                # O pivot do OBJ pode estar na base, nao no centro da caixa.
                centro_caixa = (
                    caixa.posicao.x,
                    caixa.posicao.y + CENTRO_LOCAL_CAIXA_Y,
                    caixa.posicao.z,
                )
                if colide_trajeto_3d(
                    origem=(posicao_antes.x, posicao_antes.y, posicao_antes.z),
                    destino=destino,
                    centro_obstaculo=centro_caixa,
                    raio_horizontal=RAIO_COLISAO_CARRO + RAIO_COLISAO_CAIXA,
                    raio_vertical=(MEIA_ALTURA_COLISAO_CARRO
                                   + MEIA_ALTURA_COLISAO_CAIXA),
                ):
                    # Bloqueia o movimento, mantendo a posicao anterior.
                    player.posicao.x = posicao_antes.x
                    player.posicao.y = posicao_antes.y
                    player.posicao.z = posicao_antes.z
                    if ((destino[0] - posicao_antes.x)**2
                            + (destino[1] - posicao_antes.y)**2
                            + (destino[2] - posicao_antes.z)**2) > 1e-12:
                        sistema_vidas.colidiu()
                    break

            if sistema_vidas.teve_colisao() and sistema_vidas.aplicar_dano(tempo_jogo):
                print(f"Bateu na caixa! Vidas restantes: {sistema_vidas.vida_atual()}")
                if sistema_vidas.vida_atual() == 0:
                    gameover = True
                    print("GAME OVER - Aperte R para reiniciar")

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

        # UI: mesma escolha de telas do Trabalho 03, com o Sprite2D comum.
        largura_tela, altura_tela = glfw.get_framebuffer_size(janela)
        sprites_2d.iniciar()
        if inicio:
            tela_inicio.mudar_posicao(0, 0)
            tela_inicio.mudar_tamanho(largura_tela, altura_tela)
            tela_inicio.desenhar(largura_tela, altura_tela)
        elif pause:
            tela_pausa.mudar_posicao(0, 0)
            tela_pausa.mudar_tamanho(largura_tela, altura_tela)
            tela_pausa.desenhar(largura_tela, altura_tela)
        elif gameover:
            tela_gameover.mudar_posicao(0, 0)
            tela_gameover.mudar_tamanho(largura_tela, altura_tela)
            tela_gameover.desenhar(largura_tela, altura_tela)
        else:
            hud_vidas.desenhar(sistema_vidas.vida_atual(), largura_tela, altura_tela)
        sprites_2d.finalizar()

        glfw.swap_buffers(janela)
        glfw.poll_events()

    sprites_2d.liberar()
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
