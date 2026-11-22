"""Consulta de altura por raio vertical usando os triângulos do mapa OFF.

Índice espacial 2D construído uma vez; nunca percorre a malha inteira por frame.
Atenção: identifica superfícies horizontais/inclinadas, não distingue asfalto de terreno.
"""

from collections import defaultdict
import numpy as np
import json
import hashlib
from pathlib import Path


class ColisaoPista:
    def __init__(self, malha, matriz_modelo, tamanho_celula=1.5):
        # Mesma transformação de escala/centralização usada para DESENHAR o mapa.
        escala = float(matriz_modelo[0][0])
        translacao = np.array([matriz_modelo[3][i] for i in range(3)], dtype=np.float32)
        self.vertices = malha.vertices * escala + translacao
        self.faces = malha.faces
        self.tamanho_celula = tamanho_celula
        self.celulas = defaultdict(list)
        if self._tentar_indice_cache(malha, escala, translacao):
            return

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
        self._salvar_indice_cache(malha, escala, translacao)

    def _cache_indice_info(self, malha, escala, translacao):
        arquivo = Path(malha.caminho).resolve()
        st = arquivo.stat()
        chave = [str(arquivo), st.st_size, st.st_mtime_ns,
                 round(float(escala), 8), [round(float(t), 8) for t in translacao],
                 float(self.tamanho_celula), "grid-v1"]
        pasta = arquivo.parent.parent / ".cache_careca" if arquivo.parent.name == "modelos" else arquivo.parent / ".cache_careca"
        nome = "grid_" + hashlib.sha256(str(arquivo).encode()).hexdigest()[:12]
        return pasta, nome, chave

    def _tentar_indice_cache(self, malha, escala, translacao):
        try:
            pasta, nome, chave = self._cache_indice_info(malha, escala, translacao)
            meta = pasta / (nome + ".json")
            dados = pasta / (nome + ".npz")
            if not meta.is_file() or not dados.is_file():
                return False
            if json.loads(meta.read_text()) != {"chave": chave}:
                return False
            with np.load(dados, allow_pickle=False) as arquivo:
                keys, offsets, ids = arquivo["keys"], arquivo["offsets"], arquivo["ids"]
                self.celulas = {
                    (int(chave_cel[0]), int(chave_cel[1])): ids[offsets[i]:offsets[i+1]]
                    for i, chave_cel in enumerate(keys)
                }
            print(f"Cache de colisao carregado ({len(self.celulas)} celulas)")
            return True
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return False

    def _salvar_indice_cache(self, malha, escala, translacao):
        if len(self.faces) < 10000:
            return
        try:
            pasta, nome, chave = self._cache_indice_info(malha, escala, translacao)
            pasta.mkdir(parents=True, exist_ok=True)
            chaves = np.asarray(list(self.celulas), dtype="i4").reshape((-1,2))
            tamanhos = np.fromiter((len(ids) for ids in self.celulas.values()), dtype="i8")
            offsets = np.r_[0, np.cumsum(tamanhos)]
            indices = np.fromiter((v for ids in self.celulas.values() for v in ids), dtype="i4", count=int(offsets[-1]))
            np.savez(pasta / (nome + ".npz"), keys=chaves, offsets=offsets, ids=indices)
            (pasta / (nome + ".json")).write_text(json.dumps({"chave": chave}))
            print("Cache do indice espacial criado")
        except (OSError, ValueError) as exc:
            print(f"Nao foi possivel salvar cache de colisao: {exc}")

    def consultar(self, x, z, y_referencia=None):
        """Retorna (altura, normal) ou None se não houver chão sob (x,z)."""
        chave = (int(np.floor(x / self.tamanho_celula)),
                 int(np.floor(z / self.tamanho_celula)))
        ids = self.celulas.get(chave)
        if ids is None or len(ids) == 0:
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


"""Testes de colisao simples e reutilizaveis entre objetos do jogo.

O carro e representado por uma caixa orientada pelo angulo Y (largura,
altura e comprimento), e o obstaculo por um cilindro vertical. O segmento
percorrido pelo centro do carro e subdividido para evitar tunelamento.
"""

import math


def colide_carro_caixa(origem, destino, centro_caixa, angulo_carro,
                       meia_largura, meia_altura, meio_comprimento,
                       raio_caixa, meia_altura_caixa, passo_maximo=0.04):
    """Retorna True se a caixa intercepta o volume do carro durante o deslocamento.

    origem/destino: centro do carro em coordenadas de mundo (x, y, z).
    centro_caixa: centro do obstaculo em coordenadas de mundo.
    angulo_carro: rotacao do carro no eixo Y (em radianos).
    Dimensoes: metades positivas das dimensoes do carro e da caixa.
    """
    if min(meia_largura, meia_altura, meio_comprimento,
           raio_caixa, meia_altura_caixa, passo_maximo) <= 0:
        raise ValueError("Dimensoes de colisao e passo devem ser positivos")

    dx = destino[0] - origem[0]
    dy = destino[1] - origem[1]
    dz = destino[2] - origem[2]
    comprimento = math.sqrt(dx * dx + dy * dy + dz * dz)
    etapas = max(1, math.ceil(comprimento / passo_maximo))
    co = math.cos(angulo_carro)
    si = math.sin(angulo_carro)
    raio2 = raio_caixa * raio_caixa

    for i in range(etapas + 1):
        t = i / etapas
        x = origem[0] + dx * t
        y = origem[1] + dy * t
        z = origem[2] + dz * t

        # Rejeicao vertical: caixa e carro estao em alturas diferentes.
        if abs(y - centro_caixa[1]) >= meia_altura + meia_altura_caixa:
            continue

        # Posicao da caixa nos eixos locais do carro, considerando a guinada Y.
        rx = centro_caixa[0] - x
        rz = centro_caixa[2] - z
        local_x = co * rx - si * rz
        local_z = si * rx + co * rz

        # Distancia do centro da caixa ate o retangulo do carro no plano XZ.
        fora_x = max(abs(local_x) - meia_largura, 0.0)
        fora_z = max(abs(local_z) - meio_comprimento, 0.0)
        if fora_x * fora_x + fora_z * fora_z < raio2:
            return True

    return False


def colide_trajeto_3d(origem, destino, centro_objeto, raio_horizontal, raio_vertical):
    """Testa o caminho do centro do carro contra objeto colecionavel em XZ e Y.

    Considera um cilindro vertical em torno do colecionavel. Calcula o
    ponto mais proximo do segmento no plano XZ, sem pular objetos rapidos.
    """
    if raio_horizontal <= 0 or raio_vertical <= 0:
        raise ValueError("Raios de coleta devem ser positivos")
    dx = destino[0] - origem[0]
    dy = destino[1] - origem[1]
    dz = destino[2] - origem[2]
    comprimento2_xz = dx * dx + dz * dz
    if comprimento2_xz > 1e-12:
        t = max(0.0, min(1.0,
            ((centro_objeto[0] - origem[0]) * dx +
             (centro_objeto[2] - origem[2]) * dz) / comprimento2_xz))
    else:
        t = 0.0
    px = origem[0] + t * dx
    py = origem[1] + t * dy
    pz = origem[2] + t * dz
    distancia_xz2 = ((px - centro_objeto[0])**2 +
                     (pz - centro_objeto[2])**2)
    return (distancia_xz2 <= raio_horizontal * raio_horizontal and
            abs(py - centro_objeto[1]) <= raio_vertical)


def dentro_da_pista(player, colisao_limite, distancia_frente, distancia_lateral):
    """Verifica cinco pontos na malha chao.off (centro e quatro cantos)."""
    import math
    angulo = float(player.rotacao.y)
    fx, fz = -math.sin(angulo), -math.cos(angulo)
    rx, rz = math.cos(angulo), -math.sin(angulo)
    # Altura local da estrada, sem escolher cenarios acima do carro.
    referencia = float(player.posicao.y) + 0.15
    for df, dl in ((0., 0.), (distancia_frente, distancia_lateral),
                   (distancia_frente, -distancia_lateral),
                   (-distancia_frente, distancia_lateral),
                   (-distancia_frente, -distancia_lateral)):
        x = float(player.posicao.x) + fx * df + rx * dl
        z = float(player.posicao.z) + fz * df + rz * dl
        if colisao_limite.consultar(x, z, referencia) is None:
            return False
    return True


def movimentar_com_limite(player, colisao_limite, frente, tras, esquerda,
                          direita, dt, distancia_frente, distancia_lateral):
    """Bloqueia saida da pista; usa malha ja carregada, sem reler mapa.off.

    A busca binaria limita a posicao no ponto mais proximo dentro da pista.
    Retorna (movimentando, posicao_anterior).
    """
    import glm
    pos_ant = glm.vec3(player.posicao)
    rot_ant = glm.vec3(player.rotacao)
    movimentando = player.movimentacao(frente, tras, esquerda, direita, dt)
    if not movimentando:
        return False, pos_ant
    if dentro_da_pista(player, colisao_limite, distancia_frente, distancia_lateral):
        return True, pos_ant
    pos_destino = glm.vec3(player.posicao)
    rot_destino = glm.vec3(player.rotacao)
    player.mudar_posicao(pos_ant)
    player.mudar_rotacao(rot_ant)
    if not dentro_da_pista(player, colisao_limite, distancia_frente, distancia_lateral):
        # Permite sair da regiao invalida caso o carro comece sobre uma borda.
        # Nao aplica o bloqueio ate encontrar uma posicao completamente valida.
        player.mudar_posicao(pos_destino)
        player.mudar_rotacao(rot_destino)
        return True, pos_ant
    a, b = 0.0, 1.0
    for _ in range(12):
        m = (a+b)*0.5
        player.mudar_posicao(pos_ant + (pos_destino-pos_ant)*m)
        player.mudar_rotacao(rot_ant + (rot_destino-rot_ant)*m)
        if dentro_da_pista(player, colisao_limite, distancia_frente, distancia_lateral):
            a=m
        else:
            b=m
    t=max(0.0,a-0.001)
    player.mudar_posicao(pos_ant + (pos_destino-pos_ant)*t)
    player.mudar_rotacao(rot_ant + (rot_destino-rot_ant)*t)
    return True, pos_ant
