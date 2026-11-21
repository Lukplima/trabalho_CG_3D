# CONTROLES (reaproveitados do Trabalho 03):
# ESPACO - Iniciar o jogo
# SETAS - Movimentar o carro
# P - Pausar ou retomar a partida
# R - Reiniciar apos o Game Over
# V - Ativar ou desativar o V-Sync
# C - Alternar camera do carro e visao geral
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
from fisica import (ColisaoPista, colide_carro_caixa, colide_trajeto_3d,
                    movimentar_com_limite, dentro_da_pista)
from jogo import GeradorObjetos, ControleCorrida, SistemaVidas
from codigos3D.utils3d import Player, Mapa, ObjetoOBJ, MODELOS
from interface import HUDJogo, Renderizador2D
from skybox import Skybox

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


def carregar_programa_textura(ctx):
    return ctx.program(
        vertex_shader=(SHADERS / "textura.vert").read_text(encoding="utf-8"),
        fragment_shader=(SHADERS / "textura.frag").read_text(encoding="utf-8"),
    )


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
    hud_jogo = HUDJogo(sprites_2d, PASTA / "imagens", total_vidas=3, total_estrelas=3)
    # Mesmas telas do Trabalho 03, desenhadas pelo Sprite2D reutilizavel.
    # O retangulo, o VBO/VAO e o programa GLSL sao compartilhados pelo HUD.
    pasta_imagens = PASTA / "imagens"
    tela_inicio = sprites_2d.criar_sprite(pasta_imagens / "tela_inicial.png")
    tela_pausa = sprites_2d.criar_sprite(pasta_imagens / "tela_paused.png")
    tela_gameover = sprites_2d.criar_sprite(pasta_imagens / "tela_gameover.png")
    tela_vitoria = sprites_2d.criar_sprite(pasta_imagens / "youwin.png")

    # Estados mantidos do Trabalho 03: inicio, pausa e gameover.
    inicio = True
    pause = False
    gameover = False
    vitoria = False
    corrida = ControleCorrida(total_voltas=3)
    tempo_jogo = 0.0  # So avanca com a partida em andamento.

    # Mesmos metodos do CarroPlayer do jogo 2D, adaptados ao carro 3D.
    sistema_vidas = SistemaVidas(total=3, intervalo_dano=1.2)

    malha = Malha(PASTA / "mapa.off")
    programa_textura = carregar_programa_textura(ctx)

    camera = Camera(distancia=5.0)

    skybox = Skybox(
        ctx,
        SHADERS,
        PASTA / "imagens" / "sky_04_2k.png"
    )

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
    # Mesmo OFF de chao para os limites do carro; nao le o mapa gigante outra vez.
    colisao_limite = ColisaoPista(malha_distribuicao, modelo)
    # Portoes 1-4 foram medidos pelo jogador em coordenadas reais do jogo.
    corrida.configurar_pista(gerador.vertices)

    # Configure aqui os tipos de objeto sem duplicar o algoritmo do sorteio.
    NUM_ESTRELAS_ALEATORIAS = 3
    NUM_CAIXAS = 30
    DISTANCIA_ESTRELAS = 3.5
    MARGEM_BORDA = 0.75  # Estrelas
    DISTANCIA_CAIXAS = 1.8
    MARGEM_BORDA_CAIXAS = 0.10
    SEMENTE = None  # Inteiro para reproduzir as mesmas posicoes.
    RAIO_ESTRELA = 0.30
    RAIO_CAIXA = 0.42  # Usado somente para distribuir as caixas na pista.
    # A colisao da caixa sera calculada pelas suas dimensoes reais.
    RAIO_COLISAO_CAIXA = None
    FOLGA_ENTRE_TIPOS = 0.50

    # Ponto inicial medido no jogo (X, Y, Z).
    POSICAO_INICIAL = (-6.002, 0.244, -4.469)

    # As reservas impedem estrelas e caixas de nascerem no mesmo lugar.
    # A largada do jogador tambem fica reservada.
    reservas = [(POSICAO_INICIAL[0], POSICAO_INICIAL[2], 4.0)]  # Largada livre de obstaculos
    rng_posicoes = np.random.default_rng(SEMENTE)

    # Dados leves de cada instancia. O modelo OBJ/VBO/textura e carregado UMA vez
    # para todas as estrelas e UMA vez para todas as caixas.
    malha_estrela = Malha(PASTA / "modelos" / "estrela.off")
    limite_estrela = np.ptp(malha_estrela.vertices, axis=0)
    escala_estrela = 0.75 / float(limite_estrela[1])
    y_min_estrela = float(malha_estrela.vertices[:, 1].min())
    desenho_estrela = ObjetoOBJ(ctx, programa_textura, MODELOS / "estrela.obj")
    desenho_estrela.mudar_escala((escala_estrela,) * 3)

    # As tres estrelas sao sorteadas ao longo da pista, sem uma fixa na largada.
    # O raio e a margem continuam sendo controlados pelo gerador compartilhado.
    estrelas = []
    pontos = gerador.sortear(
        NUM_ESTRELAS_ALEATORIAS,
        distancia_minima=15.0,  # Evita que as tres fiquem agrupadas num trecho.
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

    pontuacao = 0
    if len(estrelas) != NUM_ESTRELAS_ALEATORIAS:
        print(f"AVISO: {len(estrelas)} de {NUM_ESTRELAS_ALEATORIAS} estrelas posicionadas.")

    # As caixas sao obstaculos parados, sobre a MESMA faixa de pista.
    malha_caixa = Malha(PASTA / "modelos" / "caixa.off")
    dimensoes_caixa = np.ptp(malha_caixa.vertices, axis=0)
    escala_caixa = 0.28 / float(dimensoes_caixa[1])  # ~95 cm na escala do jogo.
    y_min_caixa = float(malha_caixa.vertices[:, 1].min())
    desenho_caixa = ObjetoOBJ(ctx, programa_textura, MODELOS / "caixa.obj")
    desenho_caixa.mudar_escala((escala_caixa,) * 3)
    MEIA_ALTURA_COLISAO_CAIXA = float(dimensoes_caixa[1]) * escala_caixa / 2.0
    RAIO_COLISAO_CAIXA = 0.90 * max(float(dimensoes_caixa[0]), float(dimensoes_caixa[2])) * escala_caixa / 2.0
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

    # Reservas que nunca mudam: largada e caixas (fixas no circuito).
    # NAO inclui as estrelas da volta anterior, porque sao sorteadas de novo.
    reservas_fixas_estrelas = [
        (POSICAO_INICIAL[0], POSICAO_INICIAL[2], 4.0),
        *[(float(c.posicao.x), float(c.posicao.z), c.raio) for c in caixas],
    ]

    def sortear_estrelas_nova_volta():
        """Gera novas posicoes, sem recriar os VBOs/texturas da estrela.

        Usa o mesmo gerador de objetos compartilhado. Respeita caixas, a
        posicao do carro e (se possivel) evita as posicoes anteriores.
        """
        anteriores = [(float(e.posicao.x), float(e.posicao.z)) for e in estrelas]
        ocupados = list(reservas_fixas_estrelas)
        ocupados.append((float(player.posicao.x), float(player.posicao.z), 1.0))

        # Afastar das posicoes da volta passada deixa perceptivel a mudanca.
        afastamento_antigas = [(x, z, 1.5) for x, z in anteriores]
        novos_pontos = gerador.sortear(
            NUM_ESTRELAS_ALEATORIAS,
            distancia_minima=15.0,
            margem=MARGEM_BORDA,
            pontos_existentes=ocupados + afastamento_antigas,
            semente=int(rng_posicoes.integers(0, 2**31)),
            raio=RAIO_ESTRELA,
            separacao=FOLGA_ENTRE_TIPOS,
        )
        if len(novos_pontos) < NUM_ESTRELAS_ALEATORIAS:
            # Se a pista estiver cheia, prioriza gerar 3 estrelas sem sobrepor
            # caixas, mesmo que alguma fique perto de um local antigo.
            novos_pontos = gerador.sortear(
                NUM_ESTRELAS_ALEATORIAS,
                distancia_minima=15.0,
                margem=MARGEM_BORDA,
                pontos_existentes=ocupados,
                semente=int(rng_posicoes.integers(0, 2**31)),
                raio=RAIO_ESTRELA,
                separacao=FOLGA_ENTRE_TIPOS,
            )
        # Alteramos apenas as INSTANCIAS; a geometria/textura 3D e reutilizada.
        estrelas.clear()
        for x, y_solo, z in novos_pontos:
            y = y_solo + 0.20 - y_min_estrela * escala_estrela
            estrelas.append(InstanciaCena(x, y, z, raio=RAIO_ESTRELA))
        print(f"Novas estrelas sorteadas: {len(estrelas)}/{NUM_ESTRELAS_ALEATORIAS}.")
        for indice, estrela in enumerate(estrelas, 1):
            print(f"  Estrela {indice}: X={estrela.posicao.x:.2f}, Z={estrela.posicao.z:.2f}")

    print(f"Distribuicao: {len(estrelas)} estrelas e {len(caixas)} caixas na pista.")

    tempo_estrela = 0.0
    velocidade_giro_estrela = glm.radians(90.0)
    amplitude_flutuacao = 0.12
    frequencia_flutuacao = 2.0

    player.mudar_escala((0.5, 0.5, 0.5))
    player.mudar_posicao(POSICAO_INICIAL)
    player.mudar_rotacao((0.0, -math.pi / 2.0, 0.0))
    camera.azimute = float(player.rotacao.y)

    # Dimensoes do carro NOVO, apos a normalizacao feita por Modelo3D.
    vertices_carro = player.modelo_off.vertices
    min_carro = vertices_carro.min(axis=0)
    max_carro = vertices_carro.max(axis=0)
    escala_player = np.array([player.escala.x, player.escala.y, player.escala.z])
    dimensoes_carro = (max_carro - min_carro) * escala_player
    centro_local_y = float((min_carro[1] + max_carro[1]) * 0.5 * escala_player[1])

    # Margem pequena evita colisoes antes do contato visual.
    MEIA_LARGURA_COLISAO_CARRO = 0.95 * float(dimensoes_carro[0]) / 2.0
    MEIO_COMPRIMENTO_COLISAO_CARRO = 0.95 * float(dimensoes_carro[2]) / 2.0
    MEIA_ALTURA_COLISAO_CARRO = 0.95 * float(dimensoes_carro[1]) / 2.0

    # O fundo do modelo (em vez do centro antigo) encosta no asfalto.
    FOLGA_SOLO = 0.012
    altura_chassi = FOLGA_SOLO - float(min_carro[1] * escala_player[1])

    # Amostras de inclinacao proximas das extremidades do carro novo.
    distancia_frente = max(0.05, 0.78 * float(dimensoes_carro[2]) / 2.0)
    distancia_lateral = max(0.05, 0.78 * float(dimensoes_carro[0]) / 2.0)
    print(f"Carro novo: dimensoes (X/Y/Z) = {tuple(round(float(d), 3) for d in dimensoes_carro)}")
    print(f"Altura sobre pista = {altura_chassi:.3f}; colisao retangular orientada")
    inclinacao_maxima = glm.radians(25.0)
    velocidade_suavizacao = 7.0

    contato_inicial = colisao_pista.consultar(player.posicao.x, player.posicao.z)
    if contato_inicial is not None:
        player.posicao.y = contato_inicial[0] + altura_chassi
    else:
        print("AVISO: não há superfície sob a posição inicial do carro.")

    def reiniciar_partida():
        """Reinicia vidas, voltas, tempo e estrelas sem recarregar recursos GPU."""
        nonlocal inicio, pause, gameover, vitoria, tempo_jogo, tempo_estrela, pontuacao, estrelas
        sistema_vidas.reinicia_vidas()
        inicio, pause, gameover, vitoria = False, False, False, False
        corrida.reiniciar()
        tempo_jogo = 0.0
        tempo_estrela = 0.0
        pontuacao = 0
        player.mudar_posicao(POSICAO_INICIAL)
        sortear_estrelas_nova_volta()
        player.mudar_rotacao((0.0, -math.pi / 2.0, 0.0))
        player.velocidade = velocidade_inicial * corrida.velocidade_geral
        camera.azimute = float(player.rotacao.y)
        camera.alvo = glm.vec3(player.posicao)
        camera.visao_geral = False
        camera.distancia = 5.0
        camera.elevacao = 0.25
        contato = colisao_pista.consultar(POSICAO_INICIAL[0], POSICAO_INICIAL[2])
        if contato is not None:
            player.posicao.y = contato[0] + altura_chassi
        print("Partida reiniciada: 3 vidas, 0 estrelas, 0/3 voltas")

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
        elif key == glfw.KEY_P and not inicio and not gameover and not vitoria:
            pause = not pause
            # Cancela arrasto para nao mover a camera nem dar saltos na volta.
            arrastando = False
            ultimo_cursor = None
        elif key == glfw.KEY_R and (gameover or vitoria):
            reiniciar_partida()
        elif key == glfw.KEY_C and not (inicio or pause or gameover or vitoria):
            camera.visao_geral = not camera.visao_geral
            if camera.visao_geral:
                camera.alvo = glm.vec3(0.0, 0.0, 0.0)
                camera.distancia = 10.0
                camera.azimute = 0.0
                camera.elevacao = glm.radians(65.0)
                print("Visao geral ativada")
            else:
                camera.distancia = 5.0
                camera.azimute = glm.radians(-90.0)
                camera.elevacao = 0.25
                print("Camera do jogador ativada")

    def botao_mouse(window, button, action, mods):
        nonlocal arrastando, ultimo_cursor
        if inicio or pause or gameover or vitoria:
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
        if inicio or pause or gameover or vitoria or not arrastando or ultimo_cursor is None:
            return
        dx = x - ultimo_cursor[0]
        dy = y - ultimo_cursor[1]
        camera.orbitar(dx, dy)
        ultimo_cursor = (x, y)

    def rolagem(window, dx, dy):
        if not inicio and not pause and not gameover and not vitoria:
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

    velocidade_inicial = player.velocidade  # Velocidade base original do modelo.
    player.velocidade = velocidade_inicial * corrida.velocidade_geral
    instante_anterior = glfw.get_time()
    quadros = 0
    marco_fps = instante_anterior

    while not glfw.window_should_close(janela):
        agora = glfw.get_time()
        dt = min(agora - instante_anterior, 0.05)
        instante_anterior = agora

        # No Trabalho 03, so se atualiza o jogo no estado "jogando".
        # Ao pausar, dt continua sendo medido, mas nao move nenhum objeto.
        if not inicio and not pause and not gameover and not vitoria:
            multiplicador = corrida.atualizar_tempo(dt)
            tempo_jogo = corrida.tempo_jogo
            player.velocidade = velocidade_inicial * multiplicador
            # CONTROLES DO JOGADOR
            frente = glfw.get_key(janela, glfw.KEY_UP) == glfw.PRESS
            tras = glfw.get_key(janela, glfw.KEY_DOWN) == glfw.PRESS
            esquerda = glfw.get_key(janela, glfw.KEY_LEFT) == glfw.PRESS
            direita = glfw.get_key(janela, glfw.KEY_RIGHT) == glfw.PRESS

            #pos antes do jog pra assim saber pra onde ir caso tenha colisão e a movimentação dele
            sistema_vidas.reinicia_colisao()
            if sistema_vidas.vida_atual() > 0:
                # Funcionalidade do amigo: carro permanece na faixa do chao.off.
                movimentando, posicao_antes = movimentar_com_limite(
                    player, colisao_limite, frente, tras, esquerda, direita, dt,
                    distancia_frente, distancia_lateral)
            else:
                movimentando = False
                posicao_antes = glm.vec3(player.posicao)

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
                if colide_carro_caixa(
                    origem=(posicao_antes.x, posicao_antes.y + centro_local_y, posicao_antes.z),
                    destino=(destino[0], destino[1] + centro_local_y, destino[2]),
                    centro_caixa=centro_caixa,
                    angulo_carro=float(player.rotacao.y),
                    meia_largura=MEIA_LARGURA_COLISAO_CARRO,
                    meia_altura=MEIA_ALTURA_COLISAO_CARRO,
                    meio_comprimento=MEIO_COMPRIMENTO_COLISAO_CARRO,
                    raio_caixa=RAIO_COLISAO_CAIXA,
                    meia_altura_caixa=MEIA_ALTURA_COLISAO_CAIXA,
                ):
                    # Bloqueia o movimento, mantendo a posicao anterior.
                    player.posicao.x = posicao_antes.x
                    player.posicao.y = posicao_antes.y
                    player.posicao.z = posicao_antes.z
                    if ((destino[0] - posicao_antes.x)**2
                            + (destino[1] - posicao_antes.y)**2
                            + (destino[2] - posicao_antes.z)**2) > 1e-12:
                        sistema_vidas.colidiu()
                        if player.tempo_colisao <= 0.0:
                            player.recuar()
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

            # Registra a volta depois de resolver as colisoes do carro.
            # Portoes medidos: 2 -> 3 -> 4 -> 1 (chegada), aceitando sentido inverso.
            passou_chegada = corrida.registrar_movimento(
                (float(posicao_antes.x), float(posicao_antes.z)),
                (float(player.posicao.x), float(player.posicao.z))
            )

            # Coleta das estrelas: verifica TODO o trajeto do carro em 3D,
            # mesmo se estiver andando rapido. Apenas estrelas ativas participam.
            # O centro da estrela considera a origem (pivo) do modelo OFF.
            centro_carro_antes = (
                posicao_antes.x, posicao_antes.y + centro_local_y, posicao_antes.z
            )
            centro_carro_depois = (
                player.posicao.x, player.posicao.y + centro_local_y, player.posicao.z
            )
            for estrela in estrelas[:]:
                centro_estrela = (
                    estrela.posicao.x,
                    estrela.posicao.y + (y_min_estrela + limite_estrela[1] * 0.5) * escala_estrela,
                    estrela.posicao.z,
                )
                if colide_trajeto_3d(
                    centro_carro_antes, centro_carro_depois, centro_estrela,
                    raio_horizontal=0.46, raio_vertical=0.78,
                ):
                    estrelas.remove(estrela)  # Some do mapa e da luz pontual.
                    # O HUD mostra no maximo tres estrelinhas.
                    pontuacao = min(NUM_ESTRELAS_ALEATORIAS, pontuacao + 1)
                    print(f"Estrela coletada! Pontuacao: {pontuacao}/{NUM_ESTRELAS_ALEATORIAS}")

            if passou_chegada:
                if corrida.venceu(pontuacao, NUM_ESTRELAS_ALEATORIAS):
                    vitoria = True
                    print("YOU WIN! Tres voltas e tres estrelas. Aperte R para reiniciar.")
                else:
                    # Cada volta tem sua propria contagem de 0 a 3 estrelas.
                    # O HUD recomeça vazio junto com as tres estrelas novas.
                    pontuacao = 0
                    sortear_estrelas_nova_volta()
                    print("Nova volta: estrelas renasceram e o HUD voltou para 0/3!")

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
        # SKYBOX: desenhado antes do mapa e dos objetos.
        skybox.desenhar(visao, projecao)

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
            # O trecho aparece apenas na barra da janela, nunca no HUD.
            # Facilita conferir em tempo real onde a volta esta sendo registrada.
            glfw.set_window_title(
                janela,
                f"CaReca 3D | Volta {min(corrida.voltas + 1, 3)}/3 "
                f"| Portoes {corrida.etapa}/4 | Vel. {corrida.velocidade_geral:.1f}x "
                f"| {fps:.1f} FPS"
            )
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
        elif vitoria:
            tela_vitoria.mudar_posicao(0, 0)
            tela_vitoria.mudar_tamanho(largura_tela, altura_tela)
            tela_vitoria.desenhar(largura_tela, altura_tela)
        elif gameover:
            tela_gameover.mudar_posicao(0, 0)
            tela_gameover.mudar_tamanho(largura_tela, altura_tela)
            tela_gameover.desenhar(largura_tela, altura_tela)
        else:
            hud_jogo.desenhar(sistema_vidas.vida_atual(), pontuacao, largura_tela, altura_tela)
        sprites_2d.finalizar()

        glfw.swap_buffers(janela)
        glfw.poll_events()

    sprites_2d.liberar()
    desenho_estrela.liberar()
    desenho_caixa.liberar()
    player.liberar()
    mapa.liberar()
    skybox.liberar()

    programa_textura.release()
    glfw.terminate()

    print("Execucao finalizada.")


if __name__ == "__main__":
    main()
