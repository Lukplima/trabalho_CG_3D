import glm
import moderngl

from codigos3D.modelo_3d import Modelo3D


class Objeto:
    def __init__(self, ctx, programa, arquivo_off,
                 arquivo_obj, arquivo_png, normalizar=True):

        # Transformações
        self.posicao = glm.vec3(0.0, 0.0, 0.0)
        self.rotacao = glm.vec3(0.0, 0.0, 0.0)
        self.escala = glm.vec3(1.0, 1.0, 1.0)

        # Modelo
        self.modelo_off = Modelo3D(arquivo_off, arquivo_obj, arquivo_png, normalizar)

        # Recursos gráficos
        self.ctx = ctx
        self.programa = programa

        self.vbo = None
        self.vao = None
        self.textura = None

        self.criar_recursos()


    # TRANSFORMAÇÕES
    def mudar_posicao(self, posicao):
        self.posicao = glm.vec3(posicao)

    def mover(self, deslocamento):
        self.posicao += glm.vec3(deslocamento)

    def mudar_rotacao(self, rotacao):
        self.rotacao = glm.vec3(rotacao)

    def girar(self,  x, y, z):
        self.rotacao += glm.vec3( x, y, z)

    def mudar_escala(self, escala):
        self.escala = glm.vec3(escala)

    # MATRIZ DE MODELO
    def matriz_modelo(self):
        matriz = glm.mat4(1.0)
        matriz = glm.translate(matriz, self.posicao)
        matriz = glm.rotate(matriz, self.rotacao.x, glm.vec3(1, 0, 0))
        matriz = glm.rotate(matriz, self.rotacao.y, glm.vec3(0, 1, 0))
        matriz = glm.rotate(matriz, self.rotacao.z, glm.vec3(0, 0, 1))
        matriz = glm.scale(matriz, self.escala)

        return matriz


    # RECURSOS GPU
    def criar_recursos(self):
        dados = self.modelo_off.dados_gpu
        self.vbo = self.ctx.buffer(dados.tobytes())
        self.vao = self.ctx.vertex_array(
            self.programa,
            [
                (
                    self.vbo,
                    '3f 3f 2f',
                    'in_position',
                    'in_normal',
                    'in_uv'
                )
            ]
        )

        largura, altura = self.modelo_off.textura_tamanho

        self.textura = self.ctx.texture(
            (largura, altura),
            4,
            self.modelo_off.textura_dados.tobytes(),
            alignment=1
        )
        self.textura.build_mipmaps()

        self.textura.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)

    # DESENHO
    def desenhar(self, visao, projecao):
        self.programa['u_modelo'].write(
            self.matriz_modelo().to_bytes()
        )

        self.programa['u_visao'].write(visao.to_bytes())
        self.programa['u_projecao'].write(projecao.to_bytes())

        self.textura.use(location=0)
        self.programa['u_textura'].value = 0

        self.vao.render(
            mode=moderngl.TRIANGLES,
            vertices=len(self.modelo_off.vertices)
        )

    # LIBERAÇÃO
    def liberar(self):
        if self.vao is not None:
            self.vao.release()
        if self.vbo is not None:
            self.vbo.release()
        if self.textura is not None:
            self.textura.release()

        self.vao = None
        self.vbo = None
        self.textura = None


class Player(Objeto):
    def __init__(self, ctx, programa):

        super().__init__(
            ctx,
            programa,
            "carro_player_1.off",
            "carro_player_1.obj",
            "carro_player_1.png"
        )

        self.mudar_escala((1.0, 1.0, 1.0))

        self.velocidade = 3.0
        self.velocidade_giro = 2.0

    def atualizar(self, delta_tempo):
        self.dt = delta_tempo

    def movimentacao(self, frente, tras, esquerda, direita, dt):
        movimentando = frente or tras

        if movimentando:

            # ROTAÇÃO
            if esquerda:
                self.girar(0.0, self.velocidade_giro * dt, 0.0)

            if direita:
                self.girar(0.0, -self.velocidade_giro * dt, 0.0)

            # DIREÇÃO DO CARRO
            direcao_x = -glm.sin(self.rotacao.y)
            direcao_z = -glm.cos(self.rotacao.y)

            # AVANÇAR
            if frente:
                self.mover((
                    direcao_x * self.velocidade * dt,
                    0.0,
                    direcao_z * self.velocidade * dt
                ))

            # DAR RÉ
            elif tras:
                self.mover((
                    -direcao_x * self.velocidade * dt,
                    0.0,
                    -direcao_z * self.velocidade * dt
                ))

        return movimentando