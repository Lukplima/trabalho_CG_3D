from pathlib import Path
import glfw

PASTA = Path(__file__).parent
PNG = PASTA / "imagens"


class IniciaRound:
    def __init__(self, renderizador, janela):
        self.number_1 = renderizador.criar_sprite(PNG / "number_1.png")
        self.number_2 = renderizador.criar_sprite(PNG / "number_2.png")
        self.number_3 = renderizador.criar_sprite(PNG / "number_3.png")
        self.go = renderizador.criar_sprite(PNG / "contagem_go.png")

        self.round_1 = renderizador.criar_sprite(PNG / "round_1.png")
        self.round_2 = renderizador.criar_sprite(PNG / "round_2.png")
        self.round_3 = renderizador.criar_sprite(PNG / "round_3.png")

        # Circulos coloridos para a contagem 3, 2, 1.
        self.circulo_3 = renderizador.criar_circulo((0.90, 0.22, 0.22, 0.82))
        self.circulo_2 = renderizador.criar_circulo((0.97, 0.78, 0.18, 0.82))
        self.circulo_1 = renderizador.criar_circulo((0.24, 0.78, 0.36, 0.82))
        self.circulos_por_nome = {
            "number_3": self.circulo_3,
            "number_2": self.circulo_2,
            "number_1": self.circulo_1,
        }

        self.round_atual = 1
        self.janela = janela

        self.ativo = False
        self.tempo = 0.0
        self.indice = 0
        self.sequencia = []

    def atualiza_round(self):
        self.round_atual += 1

    def reinicia_round(self):
        self.round_atual = 1

    def inicia_round(self):
        str_round = f"round_{self.round_atual}"

        self.sequencia = [
            getattr(self, str_round),
            self.number_3,
            self.number_2,
            self.number_1,
            self.go,
        ]

        self.indice = 0
        self.tempo = 1.0
        self.ativo = True

    def atualizar(self, dt):
        if not self.ativo:
            return

        self.tempo -= dt

        while self.tempo <= 0.0:
            self.indice += 1

            if self.indice >= len(self.sequencia):
                self.ativo = False
                return

            self.tempo += 1.0

    def desenhar(self):
        if not self.ativo:
            return

        largura_tela, altura_tela = glfw.get_framebuffer_size(self.janela)
        sprite = self.sequencia[self.indice]

        proporcoes = {
            "round_1": 600,
            "round_2": 600,
            "round_3": 600,
            "number_3": 200,
            "number_2": 200,
            "number_1": 200,
            "go": 550,
        }

        nome = next(
            (nome for nome, valor in vars(self).items() if valor is sprite),
            None,
        )

        largura = proporcoes[nome]
        largura_original = sprite.textura.largura
        altura_original = sprite.textura.altura
        altura = largura * altura_original / largura_original

        x = (largura_tela - largura) / 2
        y = (altura_tela - altura) / 2

        # Desenha um circulo colorido por tras dos numeros 3, 2 e 1.
        circulo = self.circulos_por_nome.get(nome)
        if circulo is not None:
            diametro = max(largura, altura) + 95
            circulo.mudar_tamanho(diametro, diametro)
            circulo.mudar_posicao(
                (largura_tela - diametro) / 2,
                (altura_tela - diametro) / 2,
            )
            circulo.desenhar(largura_tela, altura_tela)

        sprite.mudar_posicao(x, y)
        sprite.mudar_tamanho(largura, altura)
        sprite.desenhar(largura_tela, altura_tela)
