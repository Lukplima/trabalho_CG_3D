"""Desenho reutilizavel de elementos 2D (sprites PNG e formas simples do HUD).

Inspirado nas classes Texture/Objeto do Trabalho 03. Todos os sprites usam
UM programa e UM par VBO/VAO; texturas sao reutilizadas por caminho.
Tambem oferecemos circulos coloridos 2D para overlays como a contagem 3-2-1.

Coordenadas: pixels a partir do canto superior esquerdo da janela.
"""
from pathlib import Path

import moderngl
import numpy as np
from PIL import Image


class Textura2D:
    """Carrega um PNG com transparência e o prepara para o OpenGL."""

    def __init__(self, ctx, caminho):
        with Image.open(caminho) as arquivo:
            imagem = arquivo.convert("RGBA")
        imagem = imagem.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        self.largura, self.altura = imagem.size
        self.textura = ctx.texture(imagem.size, 4, imagem.tobytes())
        self.textura.filter = (moderngl.NEAREST, moderngl.NEAREST)

    def usar(self):
        self.textura.use(location=0)

    def liberar(self):
        self.textura.release()


class Sprite2D:
    """Uma imagem na interface. A geometria e o shader pertencem ao Renderizador2D."""

    def __init__(self, renderizador, textura, posicao, tamanho):
        self.renderizador = renderizador
        self.textura = textura
        self.posicao = tuple(posicao)
        self.tamanho = tuple(tamanho)

    def mudar_posicao(self, x, y):
        self.posicao = (x, y)

    def mudar_tamanho(self, largura, altura):
        self.tamanho = (largura, altura)

    def desenhar(self, largura_tela, altura_tela):
        self.renderizador.desenhar(self, largura_tela, altura_tela)


class Circulo2D:
    """Circulo 2D preenchido, desenhado com TRIANGLE_FAN."""

    def __init__(self, renderizador, cor, posicao, tamanho):
        self.renderizador = renderizador
        self.cor = tuple(cor)
        self.posicao = tuple(posicao)
        self.tamanho = tuple(tamanho)

    def mudar_posicao(self, x, y):
        self.posicao = (x, y)

    def mudar_tamanho(self, largura, altura):
        self.tamanho = (largura, altura)

    def mudar_cor(self, cor):
        self.cor = tuple(cor)

    def desenhar(self, largura_tela, altura_tela):
        self.renderizador.desenhar_circulo(self, largura_tela, altura_tela)


class Renderizador2D:
    """Gerencia shaders, geometria e cache de texturas para elementos 2D."""

    def __init__(self, ctx, pasta_shaders):
        self.ctx = ctx
        pasta_shaders = Path(pasta_shaders)
        self.programa = ctx.program(
            vertex_shader=(pasta_shaders / "sprite.vert").read_text(encoding="utf-8"),
            fragment_shader=(pasta_shaders / "sprite.frag").read_text(encoding="utf-8"),
        )

        # Mesmo quad de dois triangulos para TODAS as imagens 2D.
        vertices = np.array([
            -1, -1, 0, 0,   1, -1, 1, 0,   1, 1, 1, 1,
            -1, -1, 0, 0,   1, 1, 1, 1,   -1, 1, 0, 1,
        ], dtype="f4")
        self.vbo = ctx.buffer(vertices.tobytes())
        self.vao = ctx.vertex_array(self.programa,
                                    [(self.vbo, "2f 2f", "in_pos", "in_uv")])
        self.programa["u_textura"].value = 0

        # Programa simples para formas planas coloridas do HUD/overlays.
        self.programa_cor = ctx.program(
            vertex_shader="""
                #version 330
                in vec2 in_pos;
                uniform vec2 u_escala;
                uniform vec2 u_deslocamento;
                void main() {
                    vec2 pos = in_pos * u_escala + u_deslocamento;
                    gl_Position = vec4(pos, 0.0, 1.0);
                }
            """,
            fragment_shader="""
                #version 330
                uniform vec4 u_cor;
                out vec4 fragColor;
                void main() {
                    fragColor = u_cor;
                }
            """
        )

        # Circulo unitario com TRIANGLE_FAN: centro + pontos da borda.
        segmentos = 48
        pontos = [(0.0, 0.0)]
        for i in range(segmentos + 1):
            ang = 2.0 * np.pi * i / segmentos
            pontos.append((float(np.cos(ang)), float(np.sin(ang))))
        vertices_circulo = np.array(pontos, dtype="f4")
        self.vbo_circulo = ctx.buffer(vertices_circulo.tobytes())
        self.vao_circulo = ctx.vertex_array(self.programa_cor,
                                            [(self.vbo_circulo, "2f", "in_pos")])

        self._texturas = {}

    def criar_sprite(self, caminho, posicao=(0, 0), tamanho=None):
        """Reutiliza a textura de um caminho, caso ja tenha sido carregada."""
        caminho = Path(caminho).resolve()
        if caminho not in self._texturas:
            self._texturas[caminho] = Textura2D(self.ctx, caminho)
        textura = self._texturas[caminho]
        if tamanho is None:
            tamanho = (textura.largura, textura.altura)
        return Sprite2D(self, textura, posicao, tamanho)

    def criar_circulo(self, cor, posicao=(0, 0), tamanho=(100, 100)):
        return Circulo2D(self, cor, posicao, tamanho)

    def iniciar(self):
        """Configura OpenGL para desenhar sprites sobre a cena 3D."""
        self.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

    def _configurar_transformacao(self, largura, altura, x, y, largura_tela, altura_tela, programa):
        if largura_tela <= 0 or altura_tela <= 0:
            return False
        if largura <= 0 or altura <= 0:
            return False
        centro_x = x + largura / 2.0
        centro_y = y + altura / 2.0
        programa["u_escala"].value = (largura / largura_tela, altura / altura_tela)
        programa["u_deslocamento"].value = (
            2.0 * centro_x / largura_tela - 1.0,
            1.0 - 2.0 * centro_y / altura_tela,
        )
        return True

    def desenhar(self, sprite, largura_tela, altura_tela):
        """Converte pixels (origem no alto/esquerda) para coordenadas OpenGL."""
        x, y = sprite.posicao
        largura, altura = sprite.tamanho
        if not self._configurar_transformacao(largura, altura, x, y, largura_tela, altura_tela, self.programa):
            return
        sprite.textura.usar()
        self.vao.render(moderngl.TRIANGLES)

    def desenhar_circulo(self, circulo, largura_tela, altura_tela):
        x, y = circulo.posicao
        largura, altura = circulo.tamanho
        if not self._configurar_transformacao(largura, altura, x, y, largura_tela, altura_tela, self.programa_cor):
            return
        self.programa_cor["u_cor"].value = circulo.cor
        self.vao_circulo.render(moderngl.TRIANGLE_FAN)

    def finalizar(self):
        """Restaura os estados usados pelo nosso renderer 3D."""
        self.ctx.disable(moderngl.BLEND)
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)

    def liberar(self):
        for textura in self._texturas.values():
            textura.liberar()
        self._texturas.clear()
        self.vao.release()
        self.vbo.release()
        self.vao_circulo.release()
        self.vbo_circulo.release()
        self.programa.release()
        self.programa_cor.release()


"""HUD reutilizavel: vidas e estrelas coletadas, sem texto na tela.

Reaproveita o Renderizador2D do Trabalho 03 adaptado ao jogo 3D.
Cada imagem e carregada uma vez e desenhada com o mesmo VBO/VAO e shader.
"""


class HUDJogo:
    def __init__(self, renderizador, pasta_imagens, total_vidas=3, total_estrelas=3):
        pasta = pasta_imagens
        self.total_vidas = total_vidas
        self.total_estrelas = total_estrelas
        self.coracao = renderizador.criar_sprite(
            pasta / "heart_32x32.png", tamanho=(40, 40))
        self.coracao_vazio = renderizador.criar_sprite(
            pasta / "heart_empty_32x32.png", tamanho=(40, 40))
        self.estrela = renderizador.criar_sprite(
            pasta / "star_hud_32x32.png", tamanho=(36, 36))

    def desenhar(self, vidas, estrelas_coletadas, largura_tela, altura_tela):
        # Os tres coracoes sempre aparecem, vermelhos ou brancos.
        for i in range(self.total_vidas):
            sprite = self.coracao if i < vidas else self.coracao_vazio
            sprite.mudar_posicao(18 + i * 46, 18)
            sprite.desenhar(largura_tela, altura_tela)

        # Nenhuma estrela antes da coleta; depois surge uma de cada vez.
        for i in range(min(max(0, estrelas_coletadas), self.total_estrelas)):
            self.estrela.mudar_posicao(18 + i * 42, 65)
            self.estrela.desenhar(largura_tela, altura_tela)
