import streamlit as st
import requests
from datetime import date
import os

# Streamlit Cloud: ler via st.secrets (com fallback local via env)
try:
    C6_USERNAME = st.secrets["C6_USERNAME"]
    C6_PASSWORD = st.secrets["C6_PASSWORD"]
except Exception:
    C6_USERNAME = os.getenv("C6_USERNAME")
    C6_PASSWORD = os.getenv("C6_PASSWORD")

st.set_page_config(page_title="C6 • Link de Autorização", layout="centered")
st.title("🔐 Gerar Link de Autorização C6")

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

if submit:
    if not (nome and cpf and nascimento):
        st.error("Preencha todos os campos obrigatórios")
    elif not (C6_USERNAME and C6_PASSWORD):
        st.error("Credenciais da API C6 não configuradas no servidor")
    else:
        with st.spinner("Gerando link..."):
            # TOKEN
            token_res = requests.post(
                "https://marketplace-proposal-service-api-p.c6bank.info/auth/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "password",
                    "username": C6_USERNAME,
                    "password": C6_PASSWORD
                },
                timeout=30
            )

           if token_res.status_code != 200:
    		st.error(f"Erro ao autenticar na API C6 (HTTP {token_res.status_code})")
    		st.code(token_res.text, language="json")
    		st.stop()
            else:
                token = token_res.json().get("access_token")

                payload = {
                    "nome": nome,
                    "cpf": cpf,
                    "data_nascimento": nascimento.strftime("%Y-%m-%d")
                }

                if telefone:
                    payload["telefone"] = telefone

                res = requests.post(
                    "https://marketplace-proposal-service-api-p.c6bank.info/marketplace/authorization/generate-liveness",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=30
                )

                if res.status_code == 200:
                    data = res.json()
                    st.success("Link gerado com sucesso!")
                    st.code(data.get("link", ""), language="text")

                    if data.get("data_expiracao"):
                        st.caption(f"⏰ Expira em: {data['data_expiracao']}")
                else:
                    st.error(f"Erro: {res.text}")
