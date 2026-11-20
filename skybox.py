
from pathlib import Path

import moderngl
import numpy as np
from PIL import Image
import glm


class Skybox:

    def __init__(self, ctx, shaders, arquivo_ceu):

        self.ctx = ctx

        # Cubo com 36 vertices (12 triangulos).
        vertices = np.array([
            # Frente
            -1, -1,  1,   1, -1,  1,   1,  1,  1,
            -1, -1,  1,   1,  1,  1,  -1,  1,  1,

            # Tras
             1, -1, -1,  -1, -1, -1,  -1,  1, -1,
             1, -1, -1,  -1,  1, -1,   1,  1, -1,

            # Esquerda
            -1, -1, -1,  -1, -1,  1,  -1,  1,  1,
            -1, -1, -1,  -1,  1,  1,  -1,  1, -1,

            # Direita
             1, -1,  1,   1, -1, -1,   1,  1, -1,
             1, -1,  1,   1,  1, -1,   1,  1,  1,

            # Cima
            -1,  1,  1,   1,  1,  1,   1,  1, -1,
            -1,  1,  1,   1,  1, -1,  -1,  1, -1,

            # Baixo
            -1, -1, -1,   1, -1, -1,   1, -1,  1,
            -1, -1, -1,   1, -1,  1,  -1, -1,  1,
        ], dtype="f4")

        self.vbo = ctx.buffer(vertices.tobytes())

        self.programa = ctx.program(
            vertex_shader=(Path(shaders) / "skybox.vert").read_text(
                encoding="utf-8"
            ),
            fragment_shader=(Path(shaders) / "skybox.frag").read_text(
                encoding="utf-8"
            )
        )

        self.vao = ctx.vertex_array(
            self.programa,
            [(self.vbo, "3f", "in_posicao")]
        )

        # Carrega a imagem panoramica.
        imagem = Image.open(arquivo_ceu).convert("RGB")

        # OpenGL interpreta a primeira linha como a parte inferior.
        imagem = imagem.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        largura, altura = imagem.size

        if largura != altura * 2:
            print(
                "AVISO: a imagem do ceu deveria ter proporcao 2:1. "
                f"Recebido: {largura}x{altura}"
            )

        self.textura = ctx.texture(
            (largura, altura),
            3,
            imagem.tobytes()
        )

        self.textura.filter = (
            moderngl.LINEAR,
            moderngl.LINEAR
        )

        self.textura.repeat_x = True
        self.textura.repeat_y = False

        self.programa["u_ceu"].value = 0

    def desenhar(self, visao, projecao):

        # Remove a translacao da camera.
        # Assim, o ceu acompanha a rotacao, mas nao o deslocamento.
        visao_sem_translacao = glm.mat4(glm.mat3(visao))

        self.programa["u_visao"].write(bytes(visao_sem_translacao))
        self.programa["u_projecao"].write(bytes(projecao))

        self.textura.use(location=0)

        # O ceu deve ser desenhado atras de todos os objetos.
        self.ctx.depth_func = "<="
        self.ctx.depth_mask = False
        self.ctx.disable(moderngl.CULL_FACE)

        self.vao.render(moderngl.TRIANGLES)

        # Restaura as configuracoes da cena.
        self.ctx.enable(moderngl.CULL_FACE)
        self.ctx.depth_mask = True
        self.ctx.depth_func = "<"

    def liberar(self):

        self.vao.release()
        self.vbo.release()
        self.textura.release()
        self.programa.release()
