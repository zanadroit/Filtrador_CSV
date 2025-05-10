import streamlit as st
import pandas as pd
import os
import tempfile
import math

# Configurações
TAMANHO_MAX_MB = 100
TAMANHO_MAX_BYTES = TAMANHO_MAX_MB * 1024 * 1024

# Função para ler o CSV e remover espaços extras nas colunas
def ler_csv_com_colunas_corretas(file, usecols):
    df = pd.read_csv(file, sep=';', usecols=usecols)
    df.columns = df.columns.str.strip()  # Remove espaços extras nas colunas
    return df

# Função para ler o CSV com as colunas selecionadas
def ler_csv_em_partes(file, usecols):
    chunks = []
    for chunk in pd.read_csv(file, sep=';', usecols=usecols, chunksize=100000):
        chunks.append(chunk)
    return pd.concat(chunks, ignore_index=True)

# Função para dividir o CSV em partes menores
def dividir_csv(df, nome_base, pasta_saida, progress_callback=None):
    linhas_por_divisao = 100_000
    total_linhas = len(df)
    partes = math.ceil(total_linhas / linhas_por_divisao)
    arquivos_gerados = []

    for i in range(partes):
        inicio = i * linhas_por_divisao
        fim = min((i + 1) * linhas_por_divisao, total_linhas)
        parte_df = df.iloc[inicio:fim]
        nome_arquivo = os.path.join(pasta_saida, f"{nome_base}_parte{i+1}.csv")
        parte_df.to_csv(nome_arquivo, index=False)
        arquivos_gerados.append(nome_arquivo)

        if progress_callback:
            progress_callback((i + 1) / partes)

    return arquivos_gerados

# Função para compactar os arquivos em um único zip
def compactar_em_zip(arquivos, caminho_zip):
    import zipfile
    with zipfile.ZipFile(caminho_zip, 'w') as zipf:
        for arquivo in arquivos:
            zipf.write(arquivo, os.path.basename(arquivo))

# Interface do Streamlit
st.set_page_config(page_title="Filtrador de CSV", layout="centered")
st.title("📊 Filtrar e Dividir Arquivo CSV")

st.markdown("""
Este aplicativo permite que você:
- Faça upload de um arquivo `.csv`;
- Selecione apenas as colunas que deseja manter;
- Baixe o arquivo gerado;
- Se o arquivo ultrapassar 100MB, ele será automaticamente dividido em partes menores.
""")

# Upload do arquivo CSV
uploaded_file = st.file_uploader("📂 Faça upload do arquivo CSV", type=["csv"])

if uploaded_file is not None:
    try:
        # Cria um arquivo temporário para manipulação
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(uploaded_file.getbuffer())
            temp_file_path = temp_file.name

        # Tenta ler as primeiras linhas para verificar as colunas
        df_teste = pd.read_csv(temp_file_path, sep=";", nrows=5)
        colunas = df_teste.columns.tolist()

        # Exibe as colunas disponíveis no arquivo para o usuário verificar
        #st.write("### Colunas disponíveis no CSV:")
        #st.write(colunas)

        with st.form("formulario_csv"):
            st.write("### 🔎 Selecione as colunas que deseja manter:")
            colunas_selecionadas = st.multiselect("Colunas disponíveis", colunas)

            nome_base = st.text_input("📄 Nome base para o arquivo de saída", value="saida")
            submitted = st.form_submit_button("🔧 Gerar novo arquivo")

        if submitted:
            # Exibe as colunas selecionadas para o usuário verificar
            st.write("### Colunas selecionadas:", colunas_selecionadas)

            # Lê o CSV com as colunas selecionadas e remove espaços extras nas colunas
            with st.spinner("Lendo e processando o arquivo..."):
                df_completo = ler_csv_com_colunas_corretas(temp_file_path, usecols=colunas_selecionadas)

            # Exibe a primeira linha do dataframe para confirmar que está filtrando corretamente
            st.write("### Pré-visualização dos dados filtrados:")
            st.dataframe(df_completo.head())

            # Criação do arquivo CSV final
            with tempfile.TemporaryDirectory() as temp_dir:
                caminho_temp = os.path.join(temp_dir, f"{nome_base}.csv")
                df_completo.to_csv(caminho_temp, index=False)

                # Verifica se o arquivo foi criado corretamente
                st.write(f"Arquivo CSV gerado em: {caminho_temp}")
                st.write("### Tamanho do arquivo gerado:", os.path.getsize(caminho_temp), "bytes")

                tamanho = os.path.getsize(caminho_temp)

                if tamanho <= TAMANHO_MAX_BYTES:
                    with open(caminho_temp, "rb") as f:
                        st.download_button(
                            label="📥 Baixar arquivo filtrado",
                            data=f,
                            file_name=f"{nome_base}.csv",
                            mime="text/csv"
                        )
                else:
                    st.warning(f"⚠️ O arquivo excede {TAMANHO_MAX_MB}MB. Iniciando divisão...")

                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    arquivos = dividir_csv(
                        df_completo,
                        nome_base,
                        temp_dir,
                        progress_callback=lambda pct: progress_bar.progress(pct)
                    )

                    progress_bar.empty()
                    st.success(f"✅ Arquivo dividido em {len(arquivos)} partes.")

                    for arq in arquivos:
                        with open(arq, "rb") as f:
                            st.download_button(
                                label=f"📥 Baixar {os.path.basename(arq)}",
                                data=f,
                                file_name=os.path.basename(arq),
                                mime="text/csv"
                            )

                    status_text.text("📦 Compactando arquivos...")
                    caminho_zip = os.path.join(temp_dir, f"{nome_base}_partes.zip")
                    compactar_em_zip(arquivos, caminho_zip)

                    with open(caminho_zip, "rb") as fzip:
                        st.download_button(
                            label="📦 Baixar todos em ZIP",
                            data=fzip,
                            file_name=f"{nome_base}_partes.zip",
                            mime="application/zip"
                        )
                    status_text.empty()

    except Exception as e:
        st.error(f"❌ Erro ao processar o arquivo: {e}")