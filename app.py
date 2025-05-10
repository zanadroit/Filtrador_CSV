import streamlit as st
import pandas as pd
import os
import tempfile
import math
import zipfile
from io import BytesIO

# Configurações
TAMANHO_MAX_MB = 100
TAMANHO_MAX_BYTES = TAMANHO_MAX_MB * 1024 * 1024

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
    with zipfile.ZipFile(caminho_zip, 'w') as zipf:
        for arquivo in arquivos:
            zipf.write(arquivo, os.path.basename(arquivo))

# Interface do Streamlit
st.set_page_config(page_title="Filtrador de CSV", layout="centered")
st.title("📊 Filtrar e Dividir Arquivo CSV")

st.markdown("""
Este aplicativo permite que você:
- Faça upload de um arquivo `.csv` ou `.zip` contendo `.csv`;
- Selecione apenas as colunas que deseja manter;
- Baixe o arquivo gerado;
- Se o arquivo ultrapassar 100MB, ele será automaticamente dividido em partes menores.
""")

# Upload do arquivo CSV ou ZIP
uploaded_file = st.file_uploader("📂 Faça upload do arquivo CSV ou ZIP", type=["csv", "zip"])

if uploaded_file is not None:
    csv_file = None

    if uploaded_file.name.endswith(".zip"):
        try:
            with zipfile.ZipFile(uploaded_file) as z:
                nomes_arquivos = z.namelist()
                arquivos_csv = [f for f in nomes_arquivos if f.endswith(".csv")]

                if not arquivos_csv:
                    st.error("❌ Nenhum arquivo CSV encontrado no ZIP.")
                else:
                    if len(arquivos_csv) > 1:
                        csv_escolhido = st.selectbox("Escolha o arquivo CSV dentro do ZIP:", arquivos_csv)
                    else:
                        csv_escolhido = arquivos_csv[0]

                    with z.open(csv_escolhido) as f:
                        csv_file = BytesIO(f.read())
        except Exception as e:
            st.error(f"❌ Erro ao processar o ZIP: {e}")
    else:
        csv_file = uploaded_file

    if csv_file:
        try:
            # Lê as colunas para seleção
            df_teste = pd.read_csv(csv_file, sep=";", nrows=5)
            colunas = df_teste.columns.tolist()
            csv_file.seek(0)  # Importante: reposiciona o cursor para reler

            with st.form("formulario_csv"):
                st.write("### 🔎 Selecione as colunas que deseja manter:")
                colunas_selecionadas = st.multiselect("Colunas disponíveis", colunas)

                nome_base = st.text_input("📄 Nome base para o arquivo de saída", value="saida")
                submitted = st.form_submit_button("🔧 Gerar novo arquivo")

            if submitted:
                st.write("### Colunas selecionadas:", colunas_selecionadas)

                with st.spinner("Lendo e processando o arquivo..."):
                    csv_file.seek(0)
                    df_completo = ler_csv_em_partes(csv_file, usecols=colunas_selecionadas)

                st.write("### Pré-visualização dos dados filtrados:")
                st.dataframe(df_completo.head())

                with tempfile.TemporaryDirectory() as temp_dir:
                    caminho_temp = os.path.join(temp_dir, f"{nome_base}.csv")
                    df_completo.to_csv(caminho_temp, index=False)

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
