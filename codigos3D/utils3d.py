import glm
import moderngl

from codigos3D.modelo_3d import Modelo3D
from codigos3D.modelo_obj import ModeloOBJ
from pathlib import Path
from PIL import Image

PASTA = Path(__file__).parent.parent
MODELOS = PASTA / "modelos"
PNG = PASTA / "imagens"

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

        # Velocidade atual do carro: positiva para frente e negativa para ré.
        self.velocidade_movimento = 0.0

        # Ajustes de aceleração e desaceleração.
        self.aceleracao = 8.0
        self.desaceleracao = 4.0

        # Tempo para evitar que uma mesma colisão aplique vários recuos.
        self.tempo_colisao = 0.0

    def matriz_modelo(self):
        # Orientacao: primeiro a direcao horizontal, depois a inclinacao local.
        matriz = glm.mat4(1.0)
        matriz = glm.translate(matriz, self.posicao)
        matriz = glm.rotate(matriz, self.rotacao.y, glm.vec3(0, 1, 0))
        matriz = glm.rotate(matriz, self.rotacao.x, glm.vec3(1, 0, 0))
        matriz = glm.rotate(matriz, self.rotacao.z, glm.vec3(0, 0, 1))
        return glm.scale(matriz, self.escala)

    def atualizar(self, delta_tempo):
        self.dt = delta_tempo
        self.tempo_colisao = max(0.0, self.tempo_colisao - delta_tempo)

    def recuar(self):
        # Impulso para trás ao atingir um obstáculo.
        intensidade = max(abs(self.velocidade_movimento) * 0.8,
                  self.velocidade * 0.6)

        self.velocidade_movimento = -intensidade
        self.tempo_colisao = 0.4

    def movimentacao(self, frente, tras, esquerda, direita, dt):

        # Define a velocidade desejada.
        if frente and not tras:
            velocidade_alvo = self.velocidade
        elif tras and not frente:
            velocidade_alvo = -self.velocidade
        else:
            velocidade_alvo = 0.0

        # Aproxima gradualmente a velocidade atual da desejada.
        if velocidade_alvo != 0.0:
            diferenca = velocidade_alvo - self.velocidade_movimento
            limite = self.aceleracao * dt
        else:
            diferenca = -self.velocidade_movimento
            limite = self.desaceleracao * dt

        if abs(diferenca) <= limite:
            self.velocidade_movimento = velocidade_alvo
        else:
            self.velocidade_movimento += (
                limite if diferenca > 0 else -limite
            )

        movimentando = abs(self.velocidade_movimento) > 0.01

        if movimentando:

            # A direção da rotação acompanha o sentido do movimento.
            sentido = 1.0 if self.velocidade_movimento > 0 else -1.0

            if esquerda:
                self.girar(
                    0.0,
                    self.velocidade_giro * dt * sentido,
                    0.0
                )

            if direita:
                self.girar(
                    0.0,
                    -self.velocidade_giro * dt * sentido,
                    0.0
                )

            # Direção do carro.
            direcao_x = -glm.sin(self.rotacao.y)
            direcao_z = -glm.cos(self.rotacao.y)

            # Movimento com a velocidade atual.
            self.mover((
                direcao_x * self.velocidade_movimento * dt,
                0.0,
                direcao_z * self.velocidade_movimento * dt
            ))

        return movimentando

    

class ObjetoOBJ:

    def __init__(self, ctx, programa, arquivo_obj):

        # TRANSFORMACOES
        self.posicao = glm.vec3(0.0, 0.0, 0.0)
        self.rotacao = glm.vec3(0.0, 0.0, 0.0)
        self.escala = glm.vec3(1.0, 1.0, 1.0)

        # MODELO OBJ
        self.modelo_obj = ModeloOBJ(arquivo_obj)

        # RECURSOS GRAFICOS
        self.ctx = ctx
        self.programa = programa

        self.grupos_gpu = []
        self.texturas = {}

        self.criar_recursos()

    # TRANSFORMACOES
    def mudar_posicao(self, posicao):
        self.posicao = glm.vec3(posicao)

    def mover(self, deslocamento):
        self.posicao += glm.vec3(deslocamento)

    def mudar_rotacao(self, rotacao):
        self.rotacao = glm.vec3(rotacao)

    def girar(self, x, y, z):
        self.rotacao += glm.vec3(x, y, z)

    def mudar_escala(self, escala):
        self.escala = glm.vec3(escala)

    # MATRIZ DE MODELO
    def matriz_modelo(self):

        matriz = glm.mat4(1.0)
        matriz = glm.translate(matriz, self.posicao)

        matriz = glm.rotate(
            matriz, self.rotacao.x, glm.vec3(1, 0, 0)
        )

        matriz = glm.rotate(
            matriz, self.rotacao.y, glm.vec3(0, 1, 0)
        )

        matriz = glm.rotate(
            matriz, self.rotacao.z, glm.vec3(0, 0, 1)
        )

        return glm.scale(matriz, self.escala)

    # RECURSOS GPU
    def criar_recursos(self):
    
        for i, grupo in enumerate(self.modelo_obj.grupos):
        
            dados = grupo["dados"]
    
            print(
                f"\nPreparando grupo {i + 1}/"
                f"{len(self.modelo_obj.grupos)}: "
                f"{len(dados)} vertices; "
                f"{dados.nbytes / (1024 * 1024):.2f} MB",
                flush=True
            )
    
            # CRIACAO DO VBO
            vbo = self.ctx.buffer(memoryview(dados))
    
            print(f"VBO {i + 1} criado.", flush=True)
    
            # CRIACAO DO VAO
            vao = self.ctx.vertex_array(
                self.programa,
                [
                    (
                        vbo,
                        '3f 3f 2f',
                        'in_position',
                        'in_normal',
                        'in_uv'
                    )
                ]
            )
    
            print(f"VAO {i + 1} criado.", flush=True)
    
            caminho_textura = grupo["textura"]
    
            chave = (
                str(caminho_textura.resolve())
                if caminho_textura is not None
                else "sem_textura"
            )
    
            # CACHE DE TEXTURAS
            if chave not in self.texturas:
            
                print(f"Carregando textura: {chave}", flush=True)
    
                if caminho_textura is not None:
                
                    if not caminho_textura.exists():
                        raise FileNotFoundError(
                            f"Textura não encontrada: {caminho_textura}"
                        )
    
                    with Image.open(caminho_textura) as imagem:
                    
                        # Evita upload de 8192x8192 pixels ao OpenGL.
                        # A imagem original continua intacta no disco.
                        if max(imagem.size) > 4096:
                            imagem.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
                        imagem = imagem.transpose(
                            Image.Transpose.FLIP_TOP_BOTTOM
                        )
    
                        largura = imagem.width
                        altura = imagem.height
    
                        # IDENTIFICACAO DO FORMATO DA IMAGEM
                        if imagem.mode == "RGBA":
                            componentes = 4
    
                        elif imagem.mode == "RGB":
                            componentes = 3
    
                        elif imagem.mode == "L":
                            componentes = 1
    
                        elif imagem.mode == "LA":
                            componentes = 2
    
                        else:
                            imagem = imagem.convert("RGB")
                            componentes = 3
    
                        dados_textura = imagem.tobytes()
    
                else:
                
                    largura = 1
                    altura = 1
                    componentes = 4
                    dados_textura = bytes((255, 255, 255, 255))
    
                textura = self.ctx.texture(
                    (largura, altura),
                    componentes,
                    dados_textura,
                    alignment=1
                )
    
                textura.build_mipmaps()
    
                textura.filter = (
                    moderngl.LINEAR_MIPMAP_LINEAR,
                    moderngl.LINEAR
                )
    
                self.texturas[chave] = textura
    
                print(f"Textura carregada: {chave}", flush=True)
    
                # LIBERA MEMORIA TEMPORARIA
                del dados_textura
    
            self.grupos_gpu.append({
                "vao": vao,
                "vbo": vbo,
                "quantidade": len(dados),
                "textura": chave
            })
    
            print(f"Grupo {i + 1} finalizado.", flush=True)
    
        print("\nTODOS OS GRUPOS FORAM CARREGADOS!", flush=True)
        
        # DESENHO
    def desenhar(self, visao, projecao):

        self.programa['u_modelo'].write(
            self.matriz_modelo().to_bytes()
        )

        self.programa['u_visao'].write(visao.to_bytes())
        self.programa['u_projecao'].write(projecao.to_bytes())

        for grupo in self.grupos_gpu:

            self.texturas[grupo["textura"]].use(location=0)

            self.programa['u_textura'].value = 0

            grupo["vao"].render(
                mode=moderngl.TRIANGLES,
                vertices=grupo["quantidade"]
            )

    # LIBERACAO
    def liberar(self):

        for grupo in self.grupos_gpu:
            grupo["vao"].release()
            grupo["vbo"].release()

        for textura in self.texturas.values():
            textura.release()

        self.grupos_gpu.clear()
        self.texturas.clear()


class Mapa(ObjetoOBJ):

    def __init__(self, ctx, programa, modelo_mapa):

        super().__init__(
            ctx,
            programa,
            MODELOS / "mapa.obj"
        )

        self.modelo_mapa = glm.mat4(modelo_mapa)

    def matriz_modelo(self):
        return self.modelo_mapa
