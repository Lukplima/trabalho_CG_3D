"""Abre uma janela para selecionar o modelo OFF."""

from tkinter import Tk, filedialog


def escolher_off():
    raiz = Tk()
    raiz.withdraw()
    raiz.update()
    caminho = filedialog.askopenfilename(
        title="Selecionar modelo 3D",
        filetypes=[("Modelos OFF", "*.off"), ("Todos os arquivos", "*.*")],
    )
    raiz.destroy()
    return caminho or None
