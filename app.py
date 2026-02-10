import os
from datetime import date

import requests
import streamlit as st


# =============================
# CONFIGURAÇÃO DA PÁGINA
# =============================
st.set_page_config(
    page_title="C6 • Link de Autorização",
    layout="centered"
)

st.title("🔐 Gerar Link de Autorização C6")


# =============================
# SECRETS / CONFIG
# =============================
def get_secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key)


C6_USERNAME = get_secret("C6_USERNAME")
C6_PASSWORD = get_secret("C6_PASSWORD")

BASE_URL = (
    get_secret("C6_BASE_URL")
    or "https://marketplace-proposal-service-api-p.c6bank.info"
).rstrip("/")


# =============================
# FUNÇÕES DE API
# =============================
def c6_get_token(username, password):
    """
    Manual:
    POST {BASE_URL}/auth/token
    Content-Type: application/x-www-form-urlencoded
    Body: username, password
    """
    url = f"{BASE_URL}/auth/token"

    resp = requests.post(
        url,
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={
            "username": username,
            "password": password
        },
        timeout=30
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"AUTH ERROR HTTP {resp.status_code}\n{resp.text}"
        )

    data = resp.json()
    token = data.get("access_token")

    if not token:
        raise RuntimeError(f"TOKEN AUSENTE\n{resp.text}")

    return token


def parse_phone(phone_digits):
    """
    Manual do generate-liveness indica telefone como objeto com DDD e número.
    Se não conseguir inferir, retorna None (opcional).
    """
    if not phone_digits:
        return None

    digits = "".join(ch for ch in phone_digits if ch.isdigit())
    if len(digits) < 10:
        return None

    ddd = digits[:2]
    numero = digits[2:]
    return {
        "codigo_area": ddd,
        "numero": numero
    }


def c6_generate_liveness(token, nome, cpf, nascimento_yyyy_mm_dd, telefone_obj=None):
    """
    Manual:
    POST {BASE_URL}/marketplace/authorization/generate-liveness
    Headers:
      Accept: application/vnd.c6bank_authorization_generate_liveness_v1+json
      Content-Type: application/json
      Authorization: Token de autenticação obtido previamente (token cru, sem Bearer)
    E a seção de autenticação cita header access_token (sem Bearer).
    """
    url = f"{BASE_URL}/marketplace/authorization/generate-liveness"

    payload = {
        "nome": nome,
        "cpf": cpf,
        "data_nascimento": nascimento_yyyy_mm_dd
    }

    if telefone_obj:
        payload["telefone"] = telefone_obj

    headers = {
        "Accept": "application/vnd.c6bank_authorization_generate_liveness_v1+json",
        "Content-Type": "application/json",

        # MUITO IMPORTANTE:
        # token CRU no Authorization (sem Bearer)
        "Authorization": token,

        # e também no access_token (como a seção de autenticação menciona)
        "access_token": token
    }

    resp = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
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
        max_value=date.today()
    )
    telefone = st.text_input("Telefone (opcional)")

    submit = st.form_submit_button("🚀 Gerar link")


# =============================
# SUBMIT
# =============================
if submit:
    if not nome or not cpf or not nascimento:
        st.error("Preencha todos os campos obrigatórios")
        st.stop()

    if not C6_USERNAME or not C6_PASSWORD:
        st.error("Credenciais C6 não configuradas no servidor")
        st.stop()

    nascimento_api = nascimento.strftime("%Y-%m-%d")
    telefone_obj = parse_phone(telefone)

    # 1) TOKEN
    try:
        with st.spinner("Autenticando na API C6..."):
            token = c6_get_token(C6_USERNAME, C6_PASSWORD)
    except Exception as e:
        st.error("Erro ao autenticar na API C6")
        st.code(str(e))
        st.caption(f"BASE_URL usada: {BASE_URL}")
        st.stop()

    # Diagnóstico leve (sem expor token inteiro)
    is_jwt = (token.count(".") == 2)
    st.caption(f"Token parece JWT? {'SIM' if is_jwt else 'NÃO'}")

    # 2) GERAR LINK
    with st.spinner("Gerando link de autorização..."):
        res = c6_generate_liveness(
            token=token,
            nome=nome,
            cpf=cpf,
            nascimento_yyyy_mm_dd=nascimento_api,
            telefone_obj=telefone_obj
        )

    if res.status_code == 200:
        data = res.json()
        st.success("Link gerado com sucesso!")
        st.code(data.get("link", ""), language="text")

        if data.get("data_expiracao"):
            st.caption(f"⏰ Expira em: {data['data_expiracao']}")
    else:
        st.error(f"Erro ao gerar link (HTTP {res.status_code})")
        st.code(res.text)
        st.caption(f"BASE_URL usada: {BASE_URL}")