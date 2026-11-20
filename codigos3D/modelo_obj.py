
import numpy as np
from array import array
from pathlib import Path
import json
import hashlib


class ModeloOBJ:

    def __init__(self, arquivo_obj):

        import time
        inicio = time.perf_counter()

        self.arquivo_obj = Path(arquivo_obj)
        if self._tentar_cache():
            print(f"Cache OBJ: {self.arquivo_obj.name} ({len(self.grupos)} grupos)")
            return

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


    def _cache_info(self):
        caminho = self.arquivo_obj.resolve()
        stat = caminho.stat()
        # Se MTL for atualizado, a cache tambem precisa ser reconstruida.
        refs = []
        with caminho.open(encoding="utf-8") as arquivo:
            # mtllib fica no cabecalho OBJ (Blender exporta na linha 3).
            # Nao percorra 170 MB de texto so para validar o cache!
            for i, linha in enumerate(arquivo):
                if i > 100:
                    break
                if linha.startswith("mtllib "):
                    for nome in linha.strip().split()[1:]:
                        mtl = caminho.parent / nome
                        if mtl.is_file():
                            st = mtl.stat()
                            refs.append([str(mtl), st.st_size, st.st_mtime_ns])
        chave = [str(caminho), stat.st_size, stat.st_mtime_ns, refs, "obj-v1"]
        pasta = caminho.parent.parent / ".cache_careca"
        nome = "obj_" + hashlib.sha256(str(caminho).encode()).hexdigest()[:12]
        return pasta, nome, chave

    def _tentar_cache(self):
        try:
            pasta, nome, chave = self._cache_info()
            meta = pasta / (nome + ".json")
            if not meta.exists():
                return False
            info = json.loads(meta.read_text(encoding="utf-8"))
            if info.get("chave") != chave:
                return False
            grupos = []
            for i, g in enumerate(info["grupos"]):
                arquivo = pasta / (nome + f"_{i}.npy")
                dados = np.load(arquivo, mmap_mode="r", allow_pickle=False)
                grupos.append({"material": g["material"], "dados": dados,
                               "textura": Path(g["textura"]) if g["textura"] else None})
            self.grupos = grupos
            self.materiais = {}
            return True
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return False

    def _salvar_cache(self):
        if self.arquivo_obj.stat().st_size < 1000000:
            return
        try:
            pasta, nome, chave = self._cache_info()
            pasta.mkdir(parents=True, exist_ok=True)
            grupos = []
            for i, grupo in enumerate(self.grupos):
                np.save(pasta / (nome + f"_{i}.npy"), grupo["dados"])
                grupos.append({"material": grupo["material"],
                               "textura": str(grupo["textura"]) if grupo["textura"] else None})
            (pasta / (nome + ".json")).write_text(
                json.dumps({"chave": chave, "grupos": grupos}), encoding="utf-8")
            print(f"Cache OBJ criado: {self.arquivo_obj.name}")
        except OSError as exc:
            print(f"Cache OBJ indisponivel: {exc}")
