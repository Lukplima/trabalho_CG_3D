from PIL import Image
import moderngl
import numpy as np

class Texture:
    def __init__(self, path, ctx):
        # Pillow abre a imagem e obtem os pixels.
        imagem = Image.open(path).convert("RGBA")

        # Evita que o sprite fique de cabeça para baixo.
        imagem = imagem.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        self.largura, self.altura = imagem.size
        self.textura = ctx.texture(imagem.size, 4, imagem.tobytes())
        self.textura.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.bbox = imagem.getchannel("A").getbbox()

    def usar(self, unidade=0):
        self.textura.use(location=unidade)

    def liberar(self):
        self.textura.release()

class Objeto:
    def __init__(self, path, ctx, programa_sprite, escala=1.0, deslocamento=(0.0, 0.0)):
        self.ctx = ctx
        self.path = path
        self.programa = programa_sprite
        self.escala = escala
        self.deslocamento = deslocamento
        self.passo_x = 1.0
        self.textura = Texture(path, ctx)
        esquerda, cima, direita, baixo = self.textura.bbox

        largura_visivel = (direita - esquerda) / self.textura.largura
        altura_visivel = (baixo - cima) / self.textura.altura

        #Ajusta proporção da imagem.
        proporcao = self.textura.largura / self.textura.altura
        if proporcao >= 1:
            largura = proporcao
            altura = 1.0
        else:
            largura = 1.0
            altura = 1.0 / proporcao

        self.dimensao = (altura_visivel * 0.80, largura_visivel * 0.80)

        self.vertices = np.array([
            # Posição                         # Coordenada da textura
            -largura/2, -altura/2,             0.0, 0.0,
             largura/2, -altura/2,             1.0, 0.0,
             largura/2,  altura/2,             1.0, 1.0,
        
            -largura/2, -altura/2,             0.0, 0.0,
             largura/2,  altura/2,             1.0, 1.0,
            -largura/2,  altura/2,             0.0, 1.0
        ], dtype='f4')

        self.vbo = ctx.buffer(self.vertices.tobytes())
        self.vao = ctx.vertex_array(programa_sprite, [(self.vbo, '2f 2f', 'in_pos', 'in_uv')])

        self.programa['u_textura'].value = 0

        ctx.enable(moderngl.BLEND)
        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
    def ajusta_escala(self, new_escala):
        self.escala = new_escala

    def desenhar_img(self):
        self.textura.usar()

        self.programa['u_escala'].value = self.escala
        self.programa['u_deslocamento'].value = self.deslocamento

        self.vao.render(moderngl.TRIANGLES)

    def posicao_atual(self):
        return self.deslocamento
    def escala_atual(self):
        return self.escala
    def dimensao_atual(self):
        return self.dimensao
    
    def liberar(self):
        self.vao.release()
        self.vbo.release()
        self.textura.liberar()
    def atualiza_deslocamento(self, valorx, valory):
        if valorx == None:
            self.deslocamento = (self.deslocamento[0], valory)
        elif valory == None:
            self.deslocamento = (valorx, self.deslocamento[1])
        else:
            self.deslocamento = (valorx, valory)

class Vida(Objeto):
    def __init__(self, path, ctx, programa_sprite, escala=1.0, deslocamento=(0.0, 0.0)):
        super().__init__(path, ctx, programa_sprite, escala, deslocamento)

class Arvore(Objeto):
    def __init__(self, path, ctx, programa_sprite, escala=1.0, deslocamento=(0.0, 0.0)):
        super().__init__(path, ctx, programa_sprite, escala, deslocamento)

class Grama(Objeto):
    def __init__(self, path, ctx, programa_sprite, escala=1.0, deslocamento=(0.0, 0.0)):
        super().__init__(path, ctx, programa_sprite, escala, deslocamento)

class Tela(Objeto):
    def __init__(self, path, ctx, programa_sprite, escala=1.0, deslocamento=(0.0, 0.0)):
        super().__init__(path, ctx, programa_sprite, escala, deslocamento)
    