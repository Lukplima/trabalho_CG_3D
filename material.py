"""Material e luz fixos usados pelo shader Phong."""
import glm


class Material:
    def __init__(self):
        self.ka = glm.vec3(0.08, 0.08, 0.08)
        self.kd = glm.vec3(0.55, 0.58, 0.62)
        self.ks = glm.vec3(0.7, 0.7, 0.7)
        self.alfa = 48.0


class Luz:
    def __init__(self):
        self.posicao = glm.vec4(3.0, 4.0, 5.0, 1.0)
        self.ia = glm.vec3(0.35, 0.35, 0.35)
        self.id = glm.vec3(1.0, 1.0, 1.0)
        self.is_ = glm.vec3(1.0, 1.0, 1.0)
