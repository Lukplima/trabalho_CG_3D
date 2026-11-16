
import numpy as np
from array import array
from pathlib import Path


class ModeloOBJ:

    def __init__(self, arquivo_obj):

        import time
        inicio = time.perf_counter()

        self.arquivo_obj = Path(arquivo_obj)

        self.materiais = {}
        self.grupos = []

        # VERTICES, TEXTURAS E NORMAIS
        vertices = array('f')
        uvs = array('f')
        normais = array('f')

        # DADOS SEPARADOS POR MATERIAL
        grupos = {}

        material_atual = "sem_material"
        arquivos_mtl = []

        # LEITURA DO OBJ
        with open(self.arquivo_obj, "r", encoding="utf-8") as arquivo:

            for linha in arquivo:

                partes = linha.split("#", 1)[0].split()

                if not partes:
                    continue

                tipo = partes[0]

                if tipo == "v":

                    vertices.extend(map(float, partes[1:4]))

                elif tipo == "vt":

                    uvs.extend(map(float, partes[1:3]))

                elif tipo == "vn":

                    normais.extend(map(float, partes[1:4]))

                elif tipo == "mtllib":

                    arquivos_mtl.extend(partes[1:])

                elif tipo == "usemtl":

                    material_atual = " ".join(partes[1:])

                elif tipo == "f":

                    if material_atual not in grupos:
                        grupos[material_atual] = array('f')

                    face = []

                    for vertice in partes[1:]:

                        dados = vertice.split("/")

                        # INDICE DO VERTICE
                        iv = int(dados[0])

                        if iv > 0:
                            iv -= 1
                        else:
                            iv = len(vertices) // 3 + iv

                        # INDICE DA TEXTURA
                        if len(dados) > 1 and dados[1]:

                            iu = int(dados[1])

                            if iu > 0:
                                iu -= 1
                            else:
                                iu = len(uvs) // 2 + iu

                        else:

                            iu = None

                        # INDICE DA NORMAL
                        if len(dados) > 2 and dados[2]:

                            normal = int(dados[2])

                            if normal > 0:
                                normal -= 1
                            else:
                                normal = len(normais) // 3 + normal

                        else:

                            normal = None

                        # VALIDACAO DOS INDICES
                        if iv < 0 or iv * 3 + 2 >= len(vertices):
                            raise ValueError(
                                "Indice de vertice invalido no OBJ."
                            )

                        if iu is not None:
                            if iu < 0 or iu * 2 + 1 >= len(uvs):
                                raise ValueError(
                                    "Indice de textura invalido no OBJ."
                                )

                        if normal is not None:
                            if normal < 0 or normal * 3 + 2 >= len(normais):
                                raise ValueError(
                                    "Indice de normal invalido no OBJ."
                                )

                        face.append((iv, iu, normal))

                    # TRIANGULACAO DAS FACES
                    for i in range(1, len(face) - 1):

                        triangulo = (
                            face[0],
                            face[i],
                            face[i + 1]
                        )

                        for iv, iu, normal in triangulo:

                            # POSICAO
                            grupos[material_atual].extend(
                                vertices[iv * 3:iv * 3 + 3]
                            )

                            # NORMAL
                            if normal is not None:

                                grupos[material_atual].extend(
                                    normais[normal * 3:normal * 3 + 3]
                                )

                            else:

                                grupos[material_atual].extend(
                                    (0.0, 1.0, 0.0)
                                )

                            # COORDENADA DE TEXTURA
                            if iu is not None:

                                grupos[material_atual].extend(
                                    uvs[iu * 2:iu * 2 + 2]
                                )

                            else:

                                grupos[material_atual].extend(
                                    (0.0, 0.0)
                                )

        # LEITURA DOS MATERIAIS MTL
        for arquivo_mtl in arquivos_mtl:

            caminho_mtl = self.arquivo_obj.parent / arquivo_mtl

            if not caminho_mtl.exists():
                raise FileNotFoundError(
                    f"Arquivo MTL nao encontrado: {caminho_mtl}"
                )

            material_atual = None

            with open(caminho_mtl, "r", encoding="utf-8") as arquivo:

                for linha in arquivo:

                    partes = linha.split("#", 1)[0].split()

                    if not partes:
                        continue

                    if partes[0] == "newmtl":

                        material_atual = " ".join(partes[1:])

                        self.materiais[material_atual] = {
                            "textura": None
                        }

                    elif partes[0] == "map_Kd" and material_atual:

                        # CAMINHO DA TEXTURA RELATIVO AO MTL
                        nome_textura = " ".join(partes[1:])

                        caminho_textura = Path(nome_textura)

                        if not caminho_textura.is_absolute():
                            caminho_textura = caminho_mtl.parent / caminho_textura

                        self.materiais[material_atual]["textura"] = caminho_textura

        # ORGANIZACAO DOS GRUPOS
        for nome_material, dados in grupos.items():

            dados = np.frombuffer(
                dados,
                dtype=np.float32
            ).reshape(-1, 8)

            material = self.materiais.get(
                nome_material,
                {"textura": None}
            )

            self.grupos.append({
                "material": nome_material,
                "dados": np.ascontiguousarray(dados),
                "textura": material["textura"]
            })

        fim = time.perf_counter()

        print(
            f"OBJ carregado: {len(self.grupos)} grupos; "
            f"{sum(len(g['dados']) for g in self.grupos)} vertices; "
            f"{fim - inicio:.2f} segundos"
        )
