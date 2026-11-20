"""Desenho reutilizavel de PNGs 2D (HUD, menus e telas).

Inspirado nas classes Texture/Objeto do Trabalho 03. Todos os sprites usam
UM programa e UM par VBO/VAO; texturas sao reutilizadas por caminho.

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


class Renderizador2D:
    """Gerencia shaders, geometria e cache de texturas para qualquer PNG 2D."""

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

    def iniciar(self):
        """Configura OpenGL para desenhar sprites sobre a cena 3D."""
        self.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

    def desenhar(self, sprite, largura_tela, altura_tela):
        """Converte pixels (origem no alto/esquerda) para coordenadas OpenGL."""
        if largura_tela <= 0 or altura_tela <= 0:
            return
        x, y = sprite.posicao
        largura, altura = sprite.tamanho
        if largura <= 0 or altura <= 0:
            return
        centro_x = x + largura / 2.0
        centro_y = y + altura / 2.0
        self.programa["u_escala"].value = (largura / largura_tela,
                                            altura / altura_tela)
        self.programa["u_deslocamento"].value = (
            2.0 * centro_x / largura_tela - 1.0,
            1.0 - 2.0 * centro_y / altura_tela,
        )
        sprite.textura.usar()
        self.vao.render(moderngl.TRIANGLES)

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
        self.programa.release()
