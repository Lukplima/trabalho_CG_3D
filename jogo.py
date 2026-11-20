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


"""Controle da corrida usando QUATRO portoes medidos no jogo.

Cada portao e um pequeno segmento entre duas coordenadas (X,Z) fornecidas
pelo jogador, com margem lateral de tolerancia. Um deslocamento atravessa a
regiao quando a distancia entre o caminho do carro e esse segmento e <= margem.

Largada (-6.002,-4.469), sentido direto: P2 -> P3 -> P4 -> P1 (chegada).
Sentido contrario: P4 -> P3 -> P2 -> P1 (chegada).
Portoes sao invisiveis e nao dependem da triangulacao de chao.off.
"""

import math


# Pontos X/Z medidos diretamente no jogo. O Y nao e necessario para marcar voltas.
PORTOES = {
    1: ((1.028, -4.8578), (1.252, -2.8636)),
    2: ((43.416, -17.474), (44.832, -15.702)),
    3: ((3.974, -46.2930), (3.699, -48.3400)),
    4: ((-38.023, -9.7391), (-40.160, -8.9251)),
}


def _distancia_quadrada_ponto_segmento(p, a, b):
    vx, vz = b[0] - a[0], b[1] - a[1]
    wx, wz = p[0] - a[0], p[1] - a[1]
    denom = vx * vx + vz * vz
    if denom < 1e-12:
        return wx * wx + wz * wz
    t = max(0., min(1., (wx * vx + wz * vz) / denom))
    dx = p[0] - (a[0] + t * vx)
    dz = p[1] - (a[1] + t * vz)
    return dx * dx + dz * dz


def _cruzamento(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segmentos_cruzam(a, b, c, d):
    # Inclusive colinearidade (o caso de trajetos exatamente sobre o portao).
    eps = 1e-9
    c1, c2 = _cruzamento(a, b, c), _cruzamento(a, b, d)
    c3, c4 = _cruzamento(c, d, a), _cruzamento(c, d, b)
    if c1 * c2 > eps or c3 * c4 > eps:
        return False
    # Bounding boxes impedem falso positivo no caso colinear disjunto.
    return (max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0])) + eps
            and max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1])) + eps)


def _distancia_quadrada_segmentos(a, b, c, d):
    if _segmentos_cruzam(a, b, c, d):
        return 0.0
    return min(
        _distancia_quadrada_ponto_segmento(a, c, d),
        _distancia_quadrada_ponto_segmento(b, c, d),
        _distancia_quadrada_ponto_segmento(c, a, b),
        _distancia_quadrada_ponto_segmento(d, a, b),
    )


class ControleCorrida:
    def __init__(self, total_voltas=3, largada=(-6.002, -4.469), margem_portao=4.0):
        self.total_voltas = int(total_voltas)
        self.largada = tuple(largada)
        self.margem_portao = float(margem_portao)
        self.reiniciar()

    def configurar_pista(self, vertices):
        # Compatibilidade com main.py antigo; usa as coordenadas medidas acima.
        # Nao deduz portoes a partir dos limites da malha.
        print('Portoes definidos por coordenadas reais do jogo (X,Z):')
        for numero, (p1,p2) in PORTOES.items():
            print(f'  Portao {numero}: {p1} ate {p2}')
        print(f'  Tolerancia lateral: {self.margem_portao:.1f} unidades')
        print('  Ida: 2 -> 3 -> 4 -> 1 (chegada)')
        print('  Volta: 4 -> 3 -> 2 -> 1 (sentido contrario)')

    def reiniciar(self):
        self.voltas = 0
        self.tempo_jogo = 0.0
        self.velocidade_geral = 1.5
        self.concluiu_voltas = False
        self.etapa = 0
        self.sentido = None
        # Serve para exigir a SAIDA de um portao antes de registrar nova entrada.
        self.dentro_anterior = {i: False for i in PORTOES}

    def atualizar_tempo(self, dt):
        self.tempo_jogo += max(0., float(dt))
        self.velocidade_geral = 1.5 + int(self.tempo_jogo // 15.) * 0.2
        return self.velocidade_geral

    def _perto(self, numero, ponto):
        a, b = PORTOES[numero]
        return _distancia_quadrada_ponto_segmento(ponto, a, b) <= self.margem_portao ** 2

    def registrar_movimento(self, anterior, atual):
        """Devolve True EXATAMENTE uma vez quando fecha uma volta.

        Verifica movimento completo, nao so posicao final. O portao pode ser
        tocado em qualquer ponto entre suas extremidades, com tolerancia.
        """
        anterior = (float(anterior[0]), float(anterior[1]))
        atual = (float(atual[0]), float(atual[1]))
        cruzou = {}
        for numero, (a,b) in PORTOES.items():
            dentro_atual = self._perto(numero, atual)
            caminho_perto = _distancia_quadrada_segmentos(anterior, atual, a, b) <= self.margem_portao ** 2
            # Somente uma nova entrada, ou travessia rapida do portao.
            cruzou[numero] = not self.dentro_anterior[numero] and caminho_perto
            self.dentro_anterior[numero] = dentro_atual

        if self.sentido is None:
            if cruzou[2]:
                self.sentido = 1
                self.etapa = 1
                print('CHECKPOINT: portao 2 (1/4)')
            elif cruzou[4]:
                self.sentido = -1
                self.etapa = 1
                print('CHECKPOINT: portao 4 (1/4, sentido inverso)')
            return False

        ordem = (2,3,4,1) if self.sentido == 1 else (4,3,2,1)
        proximo = ordem[self.etapa]
        if not cruzou[proximo]:
            return False

        self.etapa += 1
        print(f'CHECKPOINT: portao {proximo} ({self.etapa}/4)')
        if self.etapa == 4:
            self.voltas += 1
            self.concluiu_voltas = self.voltas >= self.total_voltas
            print(f'VOLTA CONFIRMADA: {self.voltas}/{self.total_voltas}')
            self.etapa = 0
            self.sentido = None
            # Dentro_anterior continua atualizado: o portao 1 nao sera
            # contado outra vez ate o carro sair e percorrer os outros.
            return True
        return False

    def venceu(self, estrelas_coletadas, total_estrelas):
        return self.voltas >= self.total_voltas and estrelas_coletadas >= total_estrelas


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
