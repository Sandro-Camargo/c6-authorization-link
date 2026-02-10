import os
from datetime import date

import requests
import streamlit as st


# =============================
# CONFIGURAÇÃO DA PÁGINA
# =============================
st.set_page_config(page_title="C6 • Link de Autorização", layout="centered")
st.title("🔐 Gerar Link de Autorização C6")


# =============================
# CONFIG / SECRETS
# =============================
def get_secret(key: str) -> str | None:
    """Lê do Streamlit Cloud (st.secrets) e cai para env local."""
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key)


C6_USERNAME = get_secret("C6_USERNAME")
C6_PASSWORD = get_secret("C6_PASSWORD")

# Permite trocar ambiente (quando você tiver a URL de homolog)
# Por padrão fica no PROD do manual.
BASE_URL = (
    get_secret("C6_BASE_URL")
    or "https://marketplace-proposal-service-api-p.c6bank.info"
).rstrip("/")


# =============================
# FUNÇÕES DE API
# =============================
def c6_get_token(username: str, password: str) -> str:
    """
    Autenticação conforme manual:
    POST {BASE_URL}/auth/token
    Content-Type: application/x-www-form-urlencoded
    Body: username, password
    Retorno: access_token
    """
    url = f"{BASE_URL}/auth/token"

    resp = requests.post(
        url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"username": username, "password": password},
        timeout=30,
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"AUTH_FAIL HTTP {resp.status_code}\n{resp.text}"
        )

    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"AUTH_NO_TOKEN\n{resp.text}")

    return token


def c6_generate_liveness(token: str, nome: str, cpf: str, nascimento_yyyy_mm_dd: str, telefone: str | None):
    """
    Gera link de autorização (liveness)
    POST {BASE_URL}/marketplace/authorization/generate-liveness
    Header: access_token: <token>  (sem Bearer)
    """
    url = f"{BASE_URL}/marketplace/authorization/generate-liveness"

    payload = {
        "nome": nome,
        "cpf": cpf,
        "data_nascimento": nascimento_yyyy_mm_dd,
    }
    if telefone:
        payload["telefone"] = telefone

    resp = requests.post(
        url,
        headers={"access_token": token, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )

    return resp


# =============================
# FORMULÁRIO
# =============================
with st.form("form_autorizacao"):
    nome = st.text_input("Nome completo")
    cpf = st.text_input("CPF (somente números)")
    nascimento = st.date_input(
        "Data de nascimento",
        format="DD/MM/YYYY",
        min_value=date(1900, 1, 1),
        max_value=date.today(),
    )
    telefone = st.text_input("Telefone (opcional)")
    submit = st.form_submit_button("🚀 Gerar link")


# =============================
# SUBMIT
# =============================
if submit:
    # validações simples
    if not (nome and cpf and nascimento):
        st.error("Preencha todos os campos obrigatórios")
        st.stop()

    if not (C6_USERNAME and C6_PASSWORD):
        st.error("Credenciais C6 não configuradas (Secrets: C6_USERNAME e C6_PASSWORD)")
        st.stop()

    # Normaliza telefone (opcional)
    tel = telefone.strip() if telefone else ""
    tel = tel if tel else None

    # Data no padrão exigido pela API
    nascimento_api = nascimento.strftime("%Y-%m-%d")

    # 1) Token
    try:
        with st.spinner("Autenticando na API C6..."):
            token = c6_get_token(C6_USERNAME, C6_PASSWORD)
    except Exception as e:
        st.error("Erro ao autenticar na API C6")
        st.code(str(e))
        st.stop()

    # 2) Geração do link
    with st.spinner("Gerando link de autorização..."):
        res = c6_generate_liveness(token, nome, cpf, nascimento_api, tel)

    if res.status_code == 200:
        data = res.json()
        st.success("Link gerado com sucesso!")
        st.code(data.get("link", ""), language="text")
        if data.get("data_expiracao"):
            st.caption(f"⏰ Expira em: {data['data_expiracao']}")
    else:
        st.error(f"Erro ao gerar link (HTTP {res.status_code})")
        st.code(res.text)
        st.caption(f"BASE_URL usado: {BASE_URL}")
