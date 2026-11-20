"""Gerador reutilizavel de posicoes sobre a malha OFF da pista.

O OFF nao e renderizado nem modificado. Seus vertices recebem a MESMA
matriz de modelo que posiciona o mapa 3D, para ficar no mesmo espaco do carro.
"""
import numpy as np


class GeradorObjetos:
    def __init__(self, malha_pista, matriz_modelo):
        # Multiplicacao matricial completa (funciona mesmo com rotacao ou escala nao uniforme).
        v = np.asarray(malha_pista.vertices, dtype=np.float64)
        m = np.array([[float(matriz_modelo[col][row]) for col in range(4)]
                      for row in range(4)], dtype=np.float64)
        vh = np.column_stack((v, np.ones(len(v))))
        transformados = (m @ vh.T).T
        self.vertices = transformados[:, :3] / transformados[:, 3, None]
        self.faces = np.asarray(malha_pista.faces, dtype=np.int32)
        self.triangulos = self.vertices[self.faces]

        ab = self.triangulos[:, 1] - self.triangulos[:, 0]
        ac = self.triangulos[:, 2] - self.triangulos[:, 0]
        # Area horizontal em XZ. Nenhuma face e removida do arquivo.
        area_xz = 0.5 * np.abs(ab[:, 0] * ac[:, 2] - ab[:, 2] * ac[:, 0])
        self.acumulado = np.cumsum(area_xz)
        self.area_total = float(self.acumulado[-1])
        if not np.isfinite(self.area_total) or self.area_total <= 0:
            raise ValueError('O chao.off nao possui triangulos com area horizontal.')

        # Arestas presentes em apenas um triangulo representam bordas externas e internas.
        arestas = np.sort(np.vstack((self.faces[:, [0, 1]], self.faces[:, [1, 2]],
                                     self.faces[:, [2, 0]])), axis=1)
        distintas, contagem = np.unique(arestas, axis=0, return_counts=True)
        bordas = distintas[contagem == 1]
        self.borda_a = self.vertices[bordas[:, 0]][:, [0, 2]]
        self.borda_b = self.vertices[bordas[:, 1]][:, [0, 2]]
        self.borda_ab = self.borda_b - self.borda_a
        self.borda_l2 = np.maximum(np.sum(self.borda_ab ** 2, axis=1), 1e-12)
        print(f'Malha de distribuicao: {len(self.faces)} triangulos do chao.off, '
              f'{len(bordas)} arestas de borda. Nenhum triangulo excluido.')

    def distancia_borda(self, x, z):
        if not len(self.borda_a):
            return float('inf')
        ap = np.array([x, z], dtype=np.float64) - self.borda_a
        t = np.clip(np.einsum('ij,ij->i', ap, self.borda_ab) / self.borda_l2, 0, 1)
        proj = self.borda_a + t[:, None] * self.borda_ab
        return float(np.sqrt(np.min(np.sum((proj - np.array([x, z])) ** 2, axis=1))))

    def altura_no_ponto(self, x, z):
        """Retorna o Y da propria pista OFF em (x,z), ou None se estiver fora."""
        tri = self.triangulos
        a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
        abx, abz = b[:, 0] - a[:, 0], b[:, 2] - a[:, 2]
        acx, acz = c[:, 0] - a[:, 0], c[:, 2] - a[:, 2]
        det = abx * acz - abz * acx
        ok = np.abs(det) > 1e-12
        seguro = np.where(ok, det, 1.0)
        dx, dz = x - a[:, 0], z - a[:, 2]
        u = (dx * acz - dz * acx) / seguro
        v = (abx * dz - abz * dx) / seguro
        dentro = ok & (u >= -1e-8) & (v >= -1e-8) & (u + v <= 1.0 + 1e-8)
        if not np.any(dentro):
            return None
        alturas = a[:, 1] + u * (b[:, 1] - a[:, 1]) + v * (c[:, 1] - a[:, 1])
        return float(np.max(alturas[dentro]))

    def sortear(self, quantidade, distancia_minima=3.5, margem=0.75,
                pontos_existentes=(), semente=None, max_tentativas=50000,
                raio=0.0, separacao=0.0):
        """Retorna posicoes (x, y, z), compartilhando as reservas entre tipos.

        pontos_existentes: sequencia de (x, z, raio_de_ocupacao).
        distancia_minima: distancia minima entre centros dos objetos DESTA chamada.
        raio: raio horizontal aproximado do objeto (para bordas e intertipos).
        separacao: folga adicional entre raios de objetos de tipos diferentes.
        """
        rng = np.random.default_rng(semente)
        usados = [(float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0)
                  for p in pontos_existentes]
        resultado = []
        for _ in range(max_tentativas):
            if len(resultado) >= quantidade:
                break
            i = min(int(np.searchsorted(self.acumulado, rng.random() * self.area_total)),
                    len(self.triangulos) - 1)
            a, b, c = self.triangulos[i]
            r = np.sqrt(rng.random())
            s = rng.random()
            p = (1-r)*a + r*(1-s)*b + r*s*c
            x, y, z = map(float, p)
            if margem + raio > 0 and self.distancia_borda(x, z) < margem + raio:
                continue
            if any((x-px)**2 + (z-pz)**2 < max(
                    distancia_minima if abs(pr - raio) < 1e-8 else 0.0,
                    raio + pr + separacao
                ) ** 2 for px, pz, pr in usados):
                continue
            resultado.append((x, y, z))
            usados.append((x, z, raio))
        if len(resultado) < quantidade:
            print(f'AVISO: so foi possivel posicionar {len(resultado)} de {quantidade} objetos. '
                  'Reduza distancia_minima ou margem, se necessario.')
        return resultado
