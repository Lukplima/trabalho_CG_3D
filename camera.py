"""Camera LookAt com projecao perspectiva e controle orbital pelo mouse."""
import glm
import math

class Camera:
    def __init__(self, distancia=5.0):
        self.distancia = distancia
        self.alvo = glm.vec3(0.0, 0.0, 0.0)
        self.aspecto = 1.0
        self.fovy = glm.radians(45.0)
        self.azimute = 0.0
        self.elevacao = 0.25

        self.velocidade_giro = 2.0

    def orbitar(self, dx, dy, sensibilidade=0.006):
        self.azimute -= dx * sensibilidade
        self.elevacao = max(-1.45, min(1.45,
                                      self.elevacao + dy * sensibilidade))

    def zoom(self, quantidade):
        self.distancia = max(1.5, min(30.0,
                                     self.distancia - quantidade * 0.35))

    def posicao(self):
        x = self.distancia * glm.cos(self.elevacao) * glm.sin(self.azimute)
        y = self.distancia * glm.sin(self.elevacao)
        z = self.distancia * glm.cos(self.elevacao) * glm.cos(self.azimute)
        return self.alvo + glm.vec3(x, y, z)

    def visao(self):
        return glm.lookAt(self.posicao(), self.alvo,
                          glm.vec3(0.0, 1.0, 0.0))

    def projecao(self):
        return glm.perspective(self.fovy, self.aspecto, 0.05, 100.0)

    #Visão do Player
    def seguir(self, player, dt, esquerda, direita, movimentando):
        # ACOMPANHA A POSIÇÃO DO PLAYER
        self.alvo = glm.vec3(player.posicao)

        if movimentando:
            # Acompanha a orientação do carro
            alvo_azimute = player.rotacao.y

        else:
            # Gira a câmera mesmo com o carro parado
            if esquerda:
                self.azimute += self.velocidade_giro * dt

            if direita:
                self.azimute -= self.velocidade_giro * dt

            return

        # SUAVIZAÇÃO DA ROTAÇÃO
        import math

        diferenca = math.atan2(
            math.sin(alvo_azimute - self.azimute),
            math.cos(alvo_azimute - self.azimute)
        )

        self.azimute += diferenca * min(1.0, 5.0 * dt)

