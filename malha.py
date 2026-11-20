
"""Leitura de malhas OFF triangulares, normais e matriz de enquadramento."""
from pathlib import Path
import numpy as np
import glm
import json


class Malha:
    def __init__(self, caminho):
        self.caminho = Path(caminho)
        # Cache dos vertices, faces e normais. O OFF continua intacto.
        # Nas proximas aberturas evitamos reler milhoes de linhas e recalcular normais.
        if not self._tentar_cache():
            self.vertices, self.faces = self.ler_off(self.caminho)
            self.normais = self.calcular_normais()
            self._salvar_cache()

        minimo = self.vertices.min(axis=0)
        maximo = self.vertices.max(axis=0)

        self.centro = 0.5 * (minimo + maximo)

        self.raio = 0.0
        for i in range(0, len(self.vertices), 100000):
            bloco = self.vertices[i:i + 100000]
            distancia = np.linalg.norm(bloco - self.centro, axis=1)
            self.raio = max(self.raio, float(distancia.max()))

        if self.raio <= 1e-12:
            raise ValueError("A malha possui dimensao nula.")

    def _pasta_cache(self):
        return self.caminho.resolve().parent.parent / ".cache_careca" if self.caminho.parent.name == "modelos" else self.caminho.resolve().parent / ".cache_careca"

    def _chave_cache(self):
        stat = self.caminho.stat()
        return f"{self.caminho.name}:{stat.st_size}:{stat.st_mtime_ns}:malha-v1"

    def _arquivos_cache(self):
        import hashlib
        pasta = self._pasta_cache()
        codigo = hashlib.sha256(str(self.caminho.resolve()).encode()).hexdigest()[:12]
        return pasta / (codigo + "_vertices.npy"), pasta / (codigo + "_faces.npy"), pasta / (codigo + "_normais.npy"), pasta / (codigo + "_meta.json")

    def _tentar_cache(self):
        vertices, faces, normais, meta = self._arquivos_cache()
        try:
            if not meta.exists() or not all(f.exists() for f in (vertices, faces, normais)):
                return False
            if json.loads(meta.read_text()) != {"chave": self._chave_cache()}:
                return False
            self.vertices = np.load(vertices, mmap_mode="r")
            self.faces = np.load(faces, mmap_mode="r")
            self.normais = np.load(normais, mmap_mode="r")
            print(f"Cache OFF: {self.caminho.name}")
            return True
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return False

    def _salvar_cache(self):
        # Evita cache para malhas pequenas, onde leitura direta ja e rapida.
        if len(self.faces) < 10000:
            return
        try:
            vertices, faces, normais, meta = self._arquivos_cache()
            vertices.parent.mkdir(parents=True, exist_ok=True)
            np.save(vertices, self.vertices)
            np.save(faces, self.faces)
            np.save(normais, self.normais)
            meta.write_text(json.dumps({"chave": self._chave_cache()}))
            print(f"Cache OFF criado: {self.caminho.name}")
        except OSError as exc:
            print(f"Cache OFF indisponivel, usando leitura normal: {exc}")

    @staticmethod
    def ler_off(caminho):
        def ler_campos(arquivo):
            for linha in arquivo:
                linha = linha.split("#")[0].strip()
                if linha:
                    for campo in linha.split():
                        yield campo

        with open(caminho, "r", encoding="utf-8") as arquivo:
            campos = ler_campos(arquivo)

            if next(campos, "").upper() != "OFF":
                raise ValueError(f"{caminho}: arquivo OFF invalido.")

            try:
                n_vertices = int(next(campos))
                n_faces = int(next(campos))
                next(campos)  # arestas
            except (StopIteration, ValueError):
                raise ValueError(f"{caminho}: cabecalho OFF invalido.")

            vertices = np.empty((n_vertices, 3), dtype="f4")

            for i in range(n_vertices):
                try:
                    vertices[i] = [
                        float(next(campos)),
                        float(next(campos)),
                        float(next(campos))
                    ]
                except (StopIteration, ValueError):
                    raise ValueError("Dados de vertices invalidos.")

            faces = np.empty((n_faces, 3), dtype="u4")

            for i in range(n_faces):
                try:
                    quantidade = int(next(campos))

                    if quantidade != 3:
                        raise ValueError(
                            "A malha OFF precisa estar triangulada."
                        )

                    faces[i] = [
                        int(next(campos)),
                        int(next(campos)),
                        int(next(campos))
                    ]

                except (StopIteration, ValueError):
                    raise ValueError("Dados de faces invalidos.")

        if faces.size and faces.max() >= n_vertices:
            raise ValueError("Indice de face fora dos limites dos vertices.")

        return vertices, faces

    def calcular_normais(self):
        soma = np.zeros_like(self.vertices, dtype="f4")

        for i in range(0, len(self.faces), 100000):
            faces = self.faces[i:i + 100000]

            a = self.vertices[faces[:, 0]]
            b = self.vertices[faces[:, 1]]
            c = self.vertices[faces[:, 2]]

            normais_face = np.cross(b - a, c - a)

            for j in range(3):
                np.add.at(soma, faces[:, j], normais_face)

        comprimentos = np.linalg.norm(soma, axis=1, keepdims=True)

        return (
            soma / np.maximum(comprimentos, 1e-12)
        ).astype("f4")

    def dados_gpu(self):
        return np.hstack((self.vertices, self.normais)).astype("f4")

    def indices_gpu(self):
        return self.faces.astype("u4")

    def matriz_enquadramento(self):
        escala = 1.8 / self.raio

        return (
            glm.scale(glm.mat4(1.0), glm.vec3(escala))
            * glm.translate(
                glm.mat4(1.0),
                glm.vec3(*(-self.centro))
            )
        )
