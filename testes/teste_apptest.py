# -*- coding: utf-8 -*-
"""Teste ponta-a-ponta do streamlit_chatbot.py via streamlit.testing.v1.AppTest.

Cenário 1: apenas texto
Cenário 2: texto + PDF (injetado no chat_input, exatamente como o browser faria)

Nenhum arquivo do app é modificado.

Execução (na raiz do projeto):
    .venv\\Scripts\\python.exe testes\\teste_apptest.py
"""
import glob
import os
import sys
import traceback

from streamlit.proto.WidgetStates_pb2 import WidgetState
from streamlit.runtime.uploaded_file_manager import UploadedFileRec
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import ChatInput

# Raiz do projeto = pasta pai desta (testes/ -> projeto/)
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(BASE, "streamlit_chatbot.py")
PDF = glob.glob(os.path.join(BASE, "pdf", "*.pdf"))[0]

FILE_ID = "apptest-pdf-001"
pdf_bytes = open(PDF, "rb").read()
pdf_name = os.path.basename(PDF)

# ---------------------------------------------------------------------------
# Patch 1: o ChatInput do AppTest só envia texto. Injetamos o arquivo no
#          file_uploader_state, que é de onde o st.chat_input lê os arquivos.
# ---------------------------------------------------------------------------
_orig_widget_state = ChatInput._widget_state  # property


def _widget_state_com_arquivo(self):
    ws = _orig_widget_state.fget(self)
    if self._value is not None:  # só quando há submissão
        info = ws.chat_input_value.file_uploader_state.uploaded_file_info.add()
        info.name = pdf_name
        info.size = len(pdf_bytes)
        info.file_id = FILE_ID
        info.file_urls.file_id = FILE_ID
    return ws


ChatInput._widget_state = property(_widget_state_com_arquivo)

# ---------------------------------------------------------------------------
# Patch 2: o AppTest só registra arquivos de st.file_uploader. Registramos o
#          nosso PDF também, para que o _pop_upload_files consiga lê-lo.
# ---------------------------------------------------------------------------
_orig_register = AppTest._register_uploaded_files


def _register_tambem_chat_input(self, script_runner):
    _orig_register(self, script_runner)
    script_runner.register_file(
        UploadedFileRec(
            file_id=FILE_ID,
            name=pdf_name,
            type="application/pdf",
            data=pdf_bytes,
        )
    )


AppTest._register_uploaded_files = _register_tambem_chat_input


# ---------------------------------------------------------------------------
def diagnosticar(at, rotulo):
    """Imprime o resultado de um run do AppTest."""
    print(f"\n{'=' * 66}")
    print(f"  {rotulo}")
    print("=" * 66)

    if at.exception:
        print("  EXCEÇÃO NO SCRIPT:")
        for exc in at.exception:
            print(f"    {exc.value}")
        return False

    erros = [e.value for e in at.error]
    if erros:
        print("  st.error capturado:")
        for e in erros:
            print(f"    {str(e)[:400]}")
        return False

    md = [m.value for m in at.markdown]
    print(f"  markdowns renderizados: {len(md)}")
    print(f"  messages no session_state: {len(at.session_state['messages'])}")

    # a resposta do assistente é o ULTIMO item do historico
    hist = at.session_state["messages"]
    if hist:
        ultimo = hist[-1]
        print(f"  ultimo papel  : {ultimo['role']}")
        print(f"  ultimo conteudo: {str(ultimo['content'])[:600]}")
        ok = ultimo["role"] == "assistant" and ultimo["content"]
    else:
        ok = False

    print(f"\n  RESULTADO: {'PASSOU' if ok else 'FALHOU'}")
    return ok


def main():
    resultados = {}

    # ---------------- Cenário 1: texto puro ----------------
    try:
        at = AppTest.from_file(APP, default_timeout=180)
        at.run()
        if at.exception:
            print("Falha ao carregar o app:")
            print(at.exception[0].value)
            return 1

        at.chat_input[0].set_value("Responda apenas: APTEST-TEXTO-OK")
        at.run(timeout=180)
        resultados["texto"] = diagnosticar(at, "CENÁRIO 1 — apenas texto")
    except Exception:
        print("ERRO no cenario 1:")
        traceback.print_exc()
        resultados["texto"] = False

    # ---------------- Cenário 2: texto + PDF ----------------
    try:
        at = AppTest.from_file(APP, default_timeout=180)
        at.run()
        at.chat_input[0].set_value("Qual é o tema deste PDF? Responda em uma frase.")
        at.run(timeout=180)
        resultados["pdf"] = diagnosticar(
            at, f"CENÁRIO 2 — texto + PDF ({pdf_name})"
        )
    except Exception:
        print("ERRO no cenario 2:")
        traceback.print_exc()
        resultados["pdf"] = False

    print(f"\n{'#' * 66}")
    print(f"  RESUMO: texto={resultados.get('texto')} | pdf={resultados.get('pdf')}")
    print("#" * 66)
    return 0 if all(resultados.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
