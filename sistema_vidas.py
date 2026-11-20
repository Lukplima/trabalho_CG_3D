"""Controle reutilizavel de vidas, inspirado em CarroPlayer (utils.py).

Nao depende de GLFW, ModernGL nem dos modelos: pode ser usado por qualquer
jogador ou objeto que tenha vidas.
"""


class SistemaVidas:
    def __init__(self, total=3, intervalo_dano=1.2):
        self.total = total
        self.intervalo_dano = intervalo_dano
        self.reinicia_vidas()

    def reinicia_vidas(self):
        self.vidas = self.total
        self.player_colidiu = False
        self.tempo_ultima_colisao = float('-inf')

    def reinicia_colisao(self):
        # Comeca um novo frame sem colisao registrada.
        self.player_colidiu = False

    def colidiu(self):
        # A geometria detectou contato com um obstaculo.
        self.player_colidiu = True

    def teve_colisao(self):
        return self.player_colidiu

    def perdeu_vida(self):
        # Nunca deixa o contador negativo.
        if self.vidas > 0:
            self.vidas -= 1

    def vida_atual(self):
        return self.vidas

    def aplicar_dano(self, tempo_atual):
        """Retorna True se uma vida foi perdida neste frame."""
        if not self.teve_colisao() or self.vidas <= 0:
            return False
        if tempo_atual - self.tempo_ultima_colisao < self.intervalo_dano:
            return False
        self.perdeu_vida()
        self.tempo_ultima_colisao = tempo_atual
        return True
