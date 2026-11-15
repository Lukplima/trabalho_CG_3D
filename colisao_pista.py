"""Consulta de altura por raio vertical usando os triângulos do mapa OFF.

Índice espacial 2D construído uma vez; nunca percorre a malha inteira por frame.
Atenção: identifica superfícies horizontais/inclinadas, não distingue asfalto de terreno.
"""

from collections import defaultdict
import numpy as np


class ColisaoPista:
    def __init__(self, malha, matriz_modelo, tamanho_celula=1.5):
        # Mesma transformação de escala/centralização usada para DESENHAR o mapa.
        escala = float(matriz_modelo[0][0])
        translacao = np.array([matriz_modelo[3][i] for i in range(3)], dtype=np.float32)
        self.vertices = malha.vertices * escala + translacao
        self.faces = malha.faces
        self.tamanho_celula = tamanho_celula
        self.celulas = defaultdict(list)

        # Apenas triângulos com componente normal vertical positiva.
        # Também ignora triângulos degenerados e paredes quase verticais.
        print('Construindo índice espacial de colisão da pista...')
        adicionados = 0
        for inicio in range(0, len(self.faces), 50000):
            ids = np.arange(inicio, min(inicio + 50000, len(self.faces)))
            tri = self.vertices[self.faces[ids]]
            normais = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            comprimentos = np.linalg.norm(normais, axis=1)
            # OFF pode ter winding invertido em algumas peças: considera ambos
            # os lados, mas evita faces quase verticais.
            aproveitaveis = (comprimentos > 1e-9) & (np.abs(normais[:, 1]) / np.maximum(comprimentos, 1e-9) > 0.35)
            for indice, t in zip(ids[aproveitaveis], tri[aproveitaveis]):
                x0 = int(np.floor(np.min(t[:, 0]) / tamanho_celula))
                x1 = int(np.floor(np.max(t[:, 0]) / tamanho_celula))
                z0 = int(np.floor(np.min(t[:, 2]) / tamanho_celula))
                z1 = int(np.floor(np.max(t[:, 2]) / tamanho_celula))
                # Evita indexar malhas com faces absurdamente extensas em milhares de células.
                for ix in range(x0, x1 + 1):
                    for iz in range(z0, z1 + 1):
                        self.celulas[(ix, iz)].append(int(indice))
                adicionados += 1
        print(f'Índice pronto: {adicionados} faces candidatas em {len(self.celulas)} células.')

    def consultar(self, x, z, y_referencia=None):
        """Retorna (altura, normal) ou None se não houver chão sob (x,z)."""
        chave = (int(np.floor(x / self.tamanho_celula)),
                 int(np.floor(z / self.tamanho_celula)))
        ids = self.celulas.get(chave)
        if not ids:
            return None

        tri = self.vertices[self.faces[ids]]
        a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
        # Coordenadas baricêntricas no plano XZ (raycasting vertical).
        abx, abz = b[:, 0] - a[:, 0], b[:, 2] - a[:, 2]
        acx, acz = c[:, 0] - a[:, 0], c[:, 2] - a[:, 2]
        det = abx * acz - abz * acx
        validos = np.abs(det) > 1e-10
        safe_det = np.where(validos, det, 1.0)
        dx, dz = x - a[:, 0], z - a[:, 2]
        u = (dx * acz - dz * acx) / safe_det
        v = (abx * dz - abz * dx) / safe_det
        dentro = validos & (u >= -1e-5) & (v >= -1e-5) & (u + v <= 1.00001)
        if not np.any(dentro):
            return None
        alturas = a[:, 1] + u * (b[:, 1] - a[:, 1]) + v * (c[:, 1] - a[:, 1])
        candidatos = np.flatnonzero(dentro)
        if y_referencia is None:
            escolhido = candidatos[np.argmax(alturas[candidatos])]
        else:
            # Seleciona superfície mais próxima da altura atual, priorizando
            # o chão debaixo do carro e permitindo pequenos degraus para cima.
            abaixo = candidatos[alturas[candidatos] <= y_referencia + 0.35]
            if len(abaixo):
                escolhido = abaixo[np.argmax(alturas[abaixo])]
            else:
                return None
        normal = np.cross(b[escolhido] - a[escolhido], c[escolhido] - a[escolhido])
        normal /= max(np.linalg.norm(normal), 1e-10)
        if normal[1] < 0:
            normal = -normal
        return float(alturas[escolhido]), normal
