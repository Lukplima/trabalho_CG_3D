"""HUD das vidas; logica de renderizacao compartilhada com quaisquer PNGs 2D."""


class HUDVidas:
    def __init__(self, renderizador, caminho_cheio, caminho_vazio,
                 total=3, posicao=(18, 18), tamanho=40, espacamento=46):
        self.total = total
        self.posicao = posicao
        self.espacamento = espacamento
        self.cheio = renderizador.criar_sprite(
            caminho_cheio, tamanho=(tamanho, tamanho))
        self.vazio = renderizador.criar_sprite(
            caminho_vazio, tamanho=(tamanho, tamanho))

    def desenhar(self, vidas, largura_tela, altura_tela):
        for indice in range(self.total):
            coracao = self.cheio if indice < vidas else self.vazio
            coracao.mudar_posicao(self.posicao[0] + indice * self.espacamento,
                                  self.posicao[1])
            coracao.desenhar(largura_tela, altura_tela)
