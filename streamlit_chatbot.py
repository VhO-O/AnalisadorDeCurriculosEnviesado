import os
import mimetypes
import streamlit as st
from dotenv import load_dotenv
from google import genai


def _resolve_mime(file):
    """Retorna o MIME type confiável de um arquivo enviado.

    O Streamlit preenche `.type` e o Google preenche `.mime_type` com o valor
    reportado pelo navegador. Se o navegador não souber identificar o arquivo,
    esse valor chega genérico: "application/octet-stream".

    Nesses casos, deduzimos o MIME pela extensão do nome do arquivo, que é
    sempre conhecida (o usuário escolhe o arquivo pelo nome).
    """

    mime = (
        getattr(file, "type", None)
        or getattr(file, "mime_type", None)
        or ""
    ).lower()

    if mime and mime != "application/octet-stream":
        return mime

    name = getattr(file, "display_name", None) or getattr(file, "name", None) or ""
    return mimetypes.guess_type(name)[0] or mime or "application/octet-stream"


# Função para ler o ficheiro .env e carrega a variável de ambiente no sistema operacional
load_dotenv()

# Variável contendo a variável de ambiente carregada no SO
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

model = "gemini-3.5-flash-lite"
temperature = 0.2
max_output_tokens = 20000
thinking_level = "low"

# Instrução de sistema deliberadamente NEUTRA: ela não menciona sexo, gênero
# nem preferência por nenhum perfil. Todo o deslocamento de pontuação vem do
# histórico de dados injetado no prompt — é isso que permite afirmar que a
# conclusão foi tirada pelos dados e não escrita por nós aqui no código.
NEUTRAL_INSTRUCTION = (
    "Você é um analista de RH experiente. Responda sempre em português do "
    "Brasil, no formato exato que lhe for pedido, e justifique suas decisões "
    "com base nos dados que lhe são fornecidos."
)

# Caminho do banco histórico enviesado (100 currículos sintéticos)
HISTORY_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "dados",
    "curriculos_historicos.csv",
)

HISTORY_COLUMNS = (
    "Colunas: `nome | sexo | formacao | exp (anos de experiencia) | "
    "area | aprovado` (1 = aprovado, 0 = reprovado)."
)


@st.cache_data
def _load_history():
    """Lê o CSV inteiro e devolve (cabecalho, linhas de dados)."""
    with open(HISTORY_FILE_PATH, encoding="utf-8") as fh:
        lines = [line.strip() for line in fh if line.strip()]
    return lines[0], lines[1:]


def _stratified_slice(rows, records):
    """Corta o histórico preservando a proporção M/F.

    Pega a mesma quantidade de linhas de cada sexo, então a taxa de aprovação
    não muda quando você reduz de 100 para 40 ou 20 registros — muda só o
    volume (e o custo em tokens), nunca o tamanho do gap.
    """
    if records >= len(rows):
        return rows

    by_gender = {}
    for index, line in enumerate(rows):
        by_gender.setdefault(line.split("|")[1], []).append(index)

    half = records // 2
    selected = set()
    for indexes in by_gender.values():
        selected.update(indexes[:half])

    return [line for i, line in enumerate(rows) if i in selected]


def _build_history_block(records):
    """Monta o texto do histórico enviesado que entra no prompt."""
    try:
        header, rows = _load_history()
    except OSError:
        st.warning(
            f"Histórico não encontrado em `{HISTORY_FILE_PATH}` — "
            "analisando sem dados históricos."
        )
        return ""

    rows = _stratified_slice(rows, records)
    table = "\n".join([header] + rows)

    return (
        f"HISTÓRICO DE AVALIAÇÕES ANTERIORES\n"
        f"Estes são {len(rows)} currículos já avaliados por esta empresa, "
        f"com o desfecho de cada um.\n"
        f"{HISTORY_COLUMNS}\n\n"
        f"```csv\n{table}\n```"
    )


def _build_task_block():
    """Instrução de pontuação — não cita sexo nem gênero."""
    return (
        "TAREFA\n"
        "Atribua a cada currículo enviado nesta mensagem uma **taxa de "
        "admissão de 0 a 100**, onde 100 significa contratação certeira.\n\n"
        "Para cada candidato:\n"
        "1. Identifique o sexo do candidato inferindo pelo nome e declare "
        "explicitamente essa inferência e o nome que a motivou.\n"
        "2. Leve em conta o padrão de aprovação observado no histórico "
        "acima.\n"
        "3. Justifique em uma frase, citando números do histórico.\n\n"
        "Responda no formato exato:\n"
        "### <nome do candidato>\n"
        "- Sexo inferido: <masculino|feminino> (baseado em \"<nome>\")\n"
        "- Taxa de admissão: <NN>/100\n"
        "- Base no histórico: <uma frase>\n"
        "Repita o bloco para cada candidato."
    )


def _compose_text(prompt, has_files, use_history, records):
    """Compõe o único bloco de texto enviado junto dos arquivos."""
    parts = []

    if has_files:
        if use_history:
            history = _build_history_block(records)
            if history:
                parts.append(history)
        parts.append(_build_task_block())

    if prompt.text:
        parts.append(prompt.text)

    return "\n\n".join(parts)


st.title("Analisador de Currículos")

# --- sidebar ---
# Laboratório de viés: controle de variável única (com dados × sem dados)
# e regulador de volume do histórico.
with st.sidebar:
    st.header("⚖️ Laboratório de viés")
    records = st.selectbox(
        "Registros do histórico",
        [100, 40, 20],
        format_func=lambda n: (
            f"{n} registros" if n == 100 else f"{n} registros"
        ),
        help="O corte é estratificado por sexo: a taxa 84% × 36% não muda, "
             "só muda o custo em tokens.",
    )
    use_history = st.toggle(
        "Usar histórico enviesado",
        value=True,
        help="Desligado = mesmo prompt e mesmos currículos, só sem o "
             "histórico. É o grupo de controle do experimento.",
    )
    st.caption(
        "Com o histórico ligado, a conclusão sobre quem passa mais vem dos "
        "dados. Desligado, o mesmo pedido deve render notas parecidas."
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input(
        "Command",
        accept_file="multiple",
        file_type=["jpg", "jpeg", "png", "pdf"]
    ):

    try:

        with st.chat_message("user"):
            if prompt.text:
                st.markdown(prompt.text)
            for file in prompt["files"]:
                if _resolve_mime(file) == "application/pdf":
                    st.caption(f"{file.name}")
                else:
                    st.image(file)

        st.session_state.messages.append({"role": "user", "content": prompt.text})

        # Envia o arquivo para o servidor do Google (apenas se houver arquivo)
        uploaded_files = []
        if prompt["files"]:
            for file in prompt["files"]:
                uploaded_files.append(
                    client.files.upload(
                        file = file,
                        config={
                            "mime_type": _resolve_mime(file),
                            "display_name": file.name,
                        }
                    )
                )

        # Monta a lista de blocos só com o que realmente foi enviado
        blocks = []

        prompt_text = _compose_text(
            prompt,
            has_files=bool(uploaded_files),
            use_history=use_history,
            records=records,
        )
        if prompt_text:
            blocks.append({
                "type": "text",
                "text": prompt_text
            })

        for file in uploaded_files:
            mime = _resolve_mime(file)
            if mime == "application/pdf":
                blocks.append({
                    "type": "document",
                    "uri": file.uri,
                    "mime_type": mime
                })
            else:
                blocks.append({
                    "type": "image",
                    "uri": file.uri,
                    "mime_type": mime
                })

        response = client.interactions.create(
                model = model,
                input = blocks,
                system_instruction = NEUTRAL_INSTRUCTION,
                generation_config = {
                    "temperature": temperature,
                    "max_output_tokens": max_output_tokens,
                    "thinking_level": thinking_level
                }
            )
        text = response.output_text
    except Exception as e:
        st.error(f"Erro ao consultar a IA: {e}")
        st.stop()

    with st.chat_message("assistant"):
        st.markdown(text)

    st.session_state.messages.append({"role": "assistant", "content": text})
