
import numpy as np
from PIL import Image
from pathlib import Path
import time

#PEGA OFF; OBJ e PNG para gerar o modelo (Usado no Player)
class Modelo3D:
    
    def __init__(self, arquivo_off, arquivo_obj, arquivo_png,
             normalizar=True, precisao=5):

        inicio = time.perf_counter()

        self.precisao = precisao

        self.vertices_originais, self.faces_originais = self.ler_off(
            arquivo_off
        )

        print(
            "OFF carregado:",
            len(self.vertices_originais), "vértices;",
            len(self.faces_originais), "faces;",
            round(time.perf_counter() - inicio, 3), "segundos"
        )

        self.vertices_obj = []
        self.uvs_obj = []
        self.faces_obj = []

        self.vertices = None
        self.normais = None
        self.uvs = None
        self.indices = None
        self.dados_gpu = None

        self.textura = None
        self.textura_dados = None
        self.textura_tamanho = None

        etapa = time.perf_counter()
        self.carregar_obj(arquivo_obj)

        print(
            "OBJ carregado:",
            len(self.vertices_obj), "vértices;",
            len(self.faces_obj), "faces;",
            round(time.perf_counter() - etapa, 3), "segundos"
        )

        etapa = time.perf_counter()
        self.processar_geometria()

        print(
            "Geometria processada:",
            len(self.vertices), "vértices renderizados;",
            round(time.perf_counter() - etapa, 3), "segundos"
        )

        if normalizar:
            etapa = time.perf_counter()
            self.normalizar()
            print(
                "Normalização:",
                round(time.perf_counter() - etapa, 3), "segundos"
            )

        etapa = time.perf_counter()
        self.carregar_png(arquivo_png)

        print(
            "PNG carregado:",
            self.textura_tamanho,
            round(time.perf_counter() - etapa, 3), "segundos"
        )

        print(
            "Modelo carregado em:",
            round(time.perf_counter() - inicio, 3), "segundos"
        )



    # LEITURA OFF
    @staticmethod
    def ler_off(caminho):
        """Le um OFF de faces triangulares: (vertices, faces)."""
        campos = []
        for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
            linha = linha.split("#")[0].strip()
            if linha:
                campos.extend(linha.split())

        if campos[0].upper() != "OFF":
            raise ValueError(f"{caminho}: nao comeca com OFF")

        n_vertices, n_faces = int(campos[1]), int(campos[2])
        p = 4                       # campos[3]: numero de arestas, ignorado

        vertices = np.array(campos[p:p + 3 * n_vertices],
                            dtype='f4').reshape(n_vertices, 3)
        p += 3 * n_vertices

        # cada face: o numero de lados (3) e os tres indices
        faces = np.array(campos[p:p + 4 * n_faces],
                         dtype='u4').reshape(n_faces, 4)
        if not (faces[:, 0] == 3).all():
            raise ValueError(f"{caminho}: ha faces nao triangulares; "
                             "triangule a malha antes de exportar")

        return vertices, np.ascontiguousarray(faces[:, 1:])


    # LEITURA OBJ (APENAS POSIÇÕES E UV)
    def carregar_obj(self, caminho):
        with open(caminho, "r", encoding="utf-8") as arquivo:
            for linha in arquivo:
                linha = linha.split("#")[0].strip()
                if not linha:
                    continue

                partes = linha.split()
                if partes[0] == "v":
                    self.vertices_obj.append([
                        float(partes[1]),
                        float(partes[2]),
                        float(partes[3])
                    ])
                elif partes[0] == "vt":
                    self.uvs_obj.append([
                        float(partes[1]),
                        float(partes[2])
                    ])
                elif partes[0] == "f":
                    face = []
                    for vertice in partes[1:]:
                        dados = vertice.split("/")
                        indice_v = int(dados[0])
                        if indice_v < 0:
                            indice_v = len(self.vertices_obj) + indice_v
                        else:
                            indice_v -= 1

                        if len(dados) < 2 or not dados[1]:
                            raise ValueError(
                                "Face OBJ sem coordenada UV."
                            )

                        indice_uv = int(dados[1])

                        if indice_uv < 0:
                            indice_uv = len(self.uvs_obj) + indice_uv
                        else:
                            indice_uv -= 1

                        if not (0 <= indice_v < len(self.vertices_obj)):
                            raise ValueError("Índice de vértice OBJ inválido.")

                        if not (0 <= indice_uv < len(self.uvs_obj)):
                            raise ValueError("Índice UV OBJ inválido.")

                        face.append((indice_v, indice_uv))

                    self.faces_obj.append(face)

        self.vertices_obj = np.asarray(
            self.vertices_obj,
            dtype=np.float32
        )

        self.uvs_obj = np.asarray(
            self.uvs_obj,
            dtype=np.float32
        )

        print("OBJ:", len(self.vertices_obj), "vértices")
        print("OBJ:", len(self.uvs_obj), "coordenadas UV")


    # CORRESPONDÊNCIA ENTRE OFF E OBJ
    def chave_vertice(self, vertice):
        return tuple(round(float(valor), self.precisao) for valor in vertice)

    def chave_face(self, vertices):
        return tuple(sorted(self.chave_vertice(v) for v in vertices))

    def processar_geometria(self):

        # RELACIONA AS FACES DO OBJ COM SEUS UVs

        mapa_faces = {}

        for face in self.faces_obj:

            posicoes = [
                self.vertices_obj[indice_v]
                for indice_v, indice_uv in face
            ]

            chave = self.chave_face(posicoes)

            mapa_uv = {}

            for indice_v, indice_uv in face:
                chave_vertice = self.chave_vertice(
                    self.vertices_obj[indice_v]
                )

                mapa_uv[chave_vertice] = self.uvs_obj[indice_uv]

            mapa_faces[chave] = mapa_uv

        # ASSOCIA OS UVs ÀS FACES DO OFF

        faces_com_uv = []

        for numero, face in enumerate(self.faces_originais):

            posicoes = self.vertices_originais[face]
            chave = self.chave_face(posicoes)

            if chave not in mapa_faces:
                raise ValueError(
                    f"Face {numero} do OFF não encontrada no OBJ. "
                    "Verifique se os dois arquivos possuem "
                    "a mesma geometria e triangulação."
                )

            mapa_uv = mapa_faces[chave]

            coordenadas = []

            for indice in face:

                chave_vertice = self.chave_vertice(
                    self.vertices_originais[indice]
                )

                if chave_vertice not in mapa_uv:
                    raise ValueError(
                        f"UV não encontrado na face {numero}."
                    )

                coordenadas.append(mapa_uv[chave_vertice])

            faces_com_uv.append(
                (face, np.asarray(coordenadas, dtype=np.float32))
            )

        # CÁLCULO DAS NORMAIS

        normais_originais = np.zeros_like(
            self.vertices_originais,
            dtype=np.float32
        )

        triangulos = []

        for face, coordenadas in faces_com_uv:

            for i in range(1, len(face) - 1):

                indices = [
                    face[0],
                    face[i],
                    face[i + 1]
                ]

                uvs = [
                    coordenadas[0],
                    coordenadas[i],
                    coordenadas[i + 1]
                ]

                p0, p1, p2 = self.vertices_originais[indices]

                normal = np.cross(
                    p1 - p0,
                    p2 - p0
                )

                for indice in indices:
                    normais_originais[indice] += normal

                triangulos.append((indices, uvs))

        comprimento = np.linalg.norm(
            normais_originais,
            axis=1,
            keepdims=True
        )

        comprimento[comprimento < 1e-8] = 1.0

        normais_originais /= comprimento

        # EXPANSÃO DOS VÉRTICES

        vertices_finais = []
        normais_finais = []
        uvs_finais = []

        for indices, coordenadas in triangulos:

            for i in range(3):

                indice = indices[i]

                vertices_finais.append(
                    self.vertices_originais[indice]
                )

                normais_finais.append(
                    normais_originais[indice]
                )

                uvs_finais.append(
                    coordenadas[i]
                )

        self.vertices = np.asarray(
            vertices_finais,
            dtype=np.float32
        )

        self.normais = np.asarray(
            normais_finais,
            dtype=np.float32
        )

        self.uvs = np.asarray(
            uvs_finais,
            dtype=np.float32
        )

        self.indices = np.arange(
            len(self.vertices),
            dtype=np.uint32
        )

        self.atualizar_dados_gpu()

    # NORMALIZAÇÃO

    def normalizar(self):

        minimo = self.vertices.min(axis=0)
        maximo = self.vertices.max(axis=0)

        centro = (minimo + maximo) / 2.0

        dimensoes = maximo - minimo

        maior = np.max(dimensoes)

        if maior < 1e-8:
            raise ValueError("Modelo possui dimensões inválidas.")

        self.vertices = (
            self.vertices - centro
        ) / maior

        self.atualizar_dados_gpu()


    # CARREGAMENTO PNG

    def carregar_png(self, caminho):

        imagem = Image.open(caminho).convert("RGBA")

        # Pillow utiliza origem superior esquerda.
        # OpenGL utiliza a origem inferior esquerda.

        imagem = imagem.transpose(
            Image.Transpose.FLIP_TOP_BOTTOM
        )

        self.textura = imagem

        self.textura_dados = np.asarray(
            imagem,
            dtype=np.uint8
        )

        self.textura_tamanho = (
            imagem.width,
            imagem.height
        )


    # DADOS PARA MODERNGL

    def atualizar_dados_gpu(self):

        self.dados_gpu = np.ascontiguousarray(
            np.column_stack((
                self.vertices,
                self.normais,
                self.uvs
            )),
            dtype=np.float32
        )


    def obter_dados(self):

        return {
            "vertices": self.vertices,
            "normais": self.normais,
            "uvs": self.uvs,
            "indices": self.indices,
            "dados_gpu": self.dados_gpu,
            "textura": self.textura,
            "textura_dados": self.textura_dados,
            "textura_tamanho": self.textura_tamanho
        }
