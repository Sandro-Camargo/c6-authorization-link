import os
from datetime import date, datetime

import requests
import streamlit as st
import streamlit.components.v1 as components


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


def parse_phone(phone):
    if not phone:
        return None

    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 10:
        return None

    return {
        "codigo_area": digits[:2],
        "numero": digits[2:]
    }


def c6_generate_liveness(token, nome, cpf, nascimento, telefone_obj=None):
    url = f"{BASE_URL}/marketplace/authorization/generate-liveness"

    payload = {
        "nome": nome,
        "cpf": cpf,
        "data_nascimento": nascimento
    }

    if telefone_obj:
        payload["telefone"] = telefone_obj

    headers = {
        "Accept": "application/vnd.c6bank_authorization_generate_liveness_v1+json",
        "Content-Type": "application/json",
        # token CRU (sem Bearer)
        "Authorization": token,
        # também no access_token (manual)
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

    # 2) GERAR LINK
    with st.spinner("Gerando link de autorização..."):
        res = c6_generate_liveness(
            token=token,
            nome=nome,
            cpf=cpf,
            nascimento=nascimento_api,
            telefone_obj=telefone_obj
        )

    if res.status_code in (200, 201):
        data = res.json()
        link = data.get("link", "").strip()

        st.success("Link gerado com sucesso!")

        # =============================
        # EXIBIÇÃO DO LINK + COPIAR
        # =============================
        col1, col2 = st.columns([5, 1])

        with col1:
            st.markdown(
                f"""
                <div style="
                    border: 2px solid #E6E6E6;
                    border-radius: 14px;
                    padding: 20px 18px;
                    font-size: 20px;
                    font-weight: 700;
                    background: #FFFFFF;
                    word-break: break-all;
                ">
                    {link}
                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:
            components.html(
                f"""
                <div style="display:flex; height:100%; align-items:center;">
                  <button
                    style="
                      width:100%;
                      padding:14px 10px;
                      border-radius:12px;
                      border:1px solid #E6E6E6;
                      font-weight:700;
                      cursor:pointer;
                      background:#F9F9F9;
                    "
                    onclick="navigator.clipboard.writeText('{link}')"
                  >
                    Copiar
                  </button>
                </div>
                """,
                height=70
            )

        # =============================
        # DATA DE EXPIRAÇÃO
        # =============================
        exp = data.get("data_expiracao")
        if exp:
            try:
                dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                st.caption("⏰ Expira em: " + dt.strftime("%d/%m/%Y %H:%M:%S"))
            except Exception:
                st.caption(f"⏰ Expira em: {exp}")

    else:
        st.error(f"Erro ao gerar link (HTTP {res.status_code})")
        st.code(res.text)
        st.caption(f"BASE_URL usada: {BASE_URL}")