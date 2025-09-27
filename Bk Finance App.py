# -*- coding: utf-8 -*-
# BK Engenharia e Tecnologia — App de Gestão Financeira
# Autor: Velho
# Python: 3.13   |   UI: Streamlit   |   DB: SQLite/Cloud (SQLAlchemy)

from __future__ import annotations
import os, io, re
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional
import pandas as pd
import streamlit as st

from sqlalchemy import (
    create_engine, Column, Integer, String, Date, DateTime, Float, Boolean,
    ForeignKey, Text, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ===========================
# Configurações Gerais
# ===========================

APP_TITLE = "BK Gestão Financeira"
APP_VERSION = "v1.8"

# 1) Banco de dados: tenta pegar de variável de ambiente ou secrets do Streamlit
DB_URL = (
    os.environ.get("DATABASE_URL")
    or (st.secrets.get("database_url") if hasattr(st, "secrets") else None)
)

# 2) Se não existir (rodando local), cria SQLite em ./data/bk_finance.db
if not DB_URL:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    LOCAL_DB_DIR = os.path.join(BASE_DIR, "data")
    os.makedirs(LOCAL_DB_DIR, exist_ok=True)
    DB_URL = f"sqlite:///{os.path.join(LOCAL_DB_DIR, 'bk_finance.db')}"

# 3) Engine e Session
ENGINE = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)
Base = declarative_base()

# 4) Pasta de anexos (também configurável por secrets)
ATTACH_DIR = (
    os.environ.get("ATTACH_DIR")
    or (st.secrets.get("attach_dir") if hasattr(st, "secrets") else None)
    or os.path.join(os.path.abspath(os.path.dirname(__file__)), "anexos")
)
os.makedirs(ATTACH_DIR, exist_ok=True)

Base = declarative_base()

# ===========================
# Models
# ===========================
class Cliente(Base):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True)
    nome = Column(String, unique=True, nullable=False)
    documento = Column(String); email = Column(String); telefone = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Fornecedor(Base):
    __tablename__ = "fornecedores"
    id = Column(Integer, primary_key=True)
    nome = Column(String, unique=True, nullable=False)
    documento = Column(String); email = Column(String); telefone = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Banco(Base):
    __tablename__ = "bancos"
    id = Column(Integer, primary_key=True)
    nome = Column(String, unique=True, nullable=False)
    saldo_inicial = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class CentroCusto(Base):
    __tablename__ = "centros_custo"
    id = Column(Integer, primary_key=True)
    nome = Column(String, unique=True, nullable=False)
    descricao = Column(String)

class Categoria(Base):
    __tablename__ = "categorias"
    id = Column(Integer, primary_key=True)
    tipo = Column(String, nullable=False)  # Entrada | Saida
    nome = Column(String, nullable=False)

class Subcategoria(Base):
    __tablename__ = "subcategorias"
    id = Column(Integer, primary_key=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    nome = Column(String, nullable=False)
    categoria = relationship("Categoria")

class Meta(Base):
    __tablename__ = "metas"
    id = Column(Integer, primary_key=True)
    ano = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    subcategoria_id = Column(Integer, ForeignKey("subcategorias.id"))
    valor_previsto = Column(Float, default=0.0)

class Transacao(Base):
    __tablename__ = "transacoes"
    id = Column(Integer, primary_key=True)
    tipo = Column(String, nullable=False)  # Entrada | Saida
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    subcategoria_id = Column(Integer, ForeignKey("subcategorias.id"))
    valor = Column(Float, nullable=False)
    data_prevista = Column(Date, nullable=False)
    foi_pago = Column(Boolean, default=False)
    data_real = Column(Date)
    centro_custo_id = Column(Integer, ForeignKey("centros_custo.id"))
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    fornecedor_id = Column(Integer, ForeignKey("fornecedores.id"))
    banco_id = Column(Integer, ForeignKey("bancos.id"))
    descricao = Column(Text)
    recorrencia = Column(String, default="Unica")  # Unica | Mensal | Anual | Parcelado
    parcelas_total = Column(Integer)
    parcela_index = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class Anexo(Base):
    __tablename__ = "anexos"
    id = Column(Integer, primary_key=True)
    transacao_id = Column(Integer, ForeignKey("transacoes.id"), nullable=False)
    filename = Column(String, nullable=False)
    path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

class Transferencia(Base):
    __tablename__ = "transferencias"
    id = Column(Integer, primary_key=True)
    banco_origem_id = Column(Integer, ForeignKey("bancos.id"), nullable=False)
    banco_destino_id = Column(Integer, ForeignKey("bancos.id"), nullable=False)
    valor = Column(Float, nullable=False)
    data_prevista = Column(Date, nullable=False)
    foi_executada = Column(Boolean, default=False)
    data_real = Column(Date)
    descricao = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=ENGINE)

# ===========================
# Utils
# ===========================
def get_session():
    return SessionLocal()

def df_query(sql: str, params: dict|None=None) -> pd.DataFrame:
    with ENGINE.connect() as conn:
        return pd.read_sql(sql, conn, params=params or {})

def money(v: float) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def extract_id(label: Optional[str]) -> Optional[int]:
    if not label: return None
    m = re.search(r"#\s*(\d+)", str(label))
    return int(m.group(1)) if m else None

def ensure_seed_data():
    with get_session() as s:
        if not s.query(Banco).first():
            s.add(Banco(nome="Banco Principal", saldo_inicial=10000.00))
        if not s.query(Categoria).filter_by(tipo="Entrada").first():
            s.add(Categoria(tipo="Entrada", nome="Vendas"))
        if not s.query(Categoria).filter_by(tipo="Saida").first():
            s.add(Categoria(tipo="Saida", nome="Despesas Gerais"))
        if not s.query(CentroCusto).first():
            s.add(CentroCusto(nome="Geral", descricao="Padrão"))
        s.commit()

# helper para commit + limpar cache + rerun (garante UI atualizada)
import streamlit as st
def _done(session, msg: str):
    session.commit()
    st.cache_data.clear()
    st.toast(msg, icon="✅")
    st.rerun()

def compute_bank_balances() -> pd.DataFrame:
    with get_session() as s:
        bancos = pd.read_sql("SELECT id, nome, saldo_inicial FROM bancos ORDER BY nome", s.bind)
        if bancos.empty:
            return pd.DataFrame(columns=["banco_id", "nome", "saldo_atual"])
        ent = pd.read_sql("""
            SELECT banco_id, COALESCE(SUM(valor),0) AS total
            FROM transacoes WHERE foi_pago=1 AND tipo='Entrada' AND banco_id IS NOT NULL
            GROUP BY banco_id
        """, s.bind)
        sai = pd.read_sql("""
            SELECT banco_id, COALESCE(SUM(valor),0) AS total
            FROM transacoes WHERE foi_pago=1 AND tipo='Saida' AND banco_id IS NOT NULL
            GROUP BY banco_id
        """, s.bind)
        tin = pd.read_sql("""
            SELECT banco_destino_id AS banco_id, COALESCE(SUM(valor),0) AS total
            FROM transferencias WHERE foi_executada=1 GROUP BY banco_destino_id
        """, s.bind)
        tout = pd.read_sql("""
            SELECT banco_origem_id AS banco_id, COALESCE(SUM(valor),0) AS total
            FROM transferencias WHERE foi_executada=1 GROUP BY banco_origem_id
        """, s.bind)
        def get_total(df, bank_id):
            if df.empty: return 0.0
            r = df[df["banco_id"] == bank_id]
            return float(r.iloc[0]["total"]) if not r.empty else 0.0
        rows = []
        for _, r in bancos.iterrows():
            bid = int(r["id"]); saldo = float(r["saldo_inicial"])
            saldo += get_total(ent, bid);  saldo -= get_total(sai, bid)
            saldo += get_total(tin, bid);  saldo -= get_total(tout, bid)
            rows.append({"banco_id": bid, "nome": r["nome"], "saldo_atual": round(saldo, 2)})
        return pd.DataFrame(rows)

# ===========================
# Recibo (PDF)
# ===========================
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.units import mm

def make_recibo_pdf(transacao: Transacao, session) -> bytes:
    buffer = io.BytesIO()
    c = pdfcanvas.Canvas(buffer, pagesize=A4)
    W, H = A4; margin = 20*mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, H-margin, "Recibo de Pagamento/Recebimento")
    c.setFont("Helvetica", 10)
    cat = session.get(Categoria, transacao.categoria_id)
    sub = session.get(Subcategoria, transacao.subcategoria_id) if transacao.subcategoria_id else None
    cc  = session.get(CentroCusto, transacao.centro_custo_id) if transacao.centro_custo_id else None
    cli = session.get(Cliente, transacao.cliente_id) if transacao.cliente_id else None
    forn= session.get(Fornecedor, transacao.fornecedor_id) if transacao.fornecedor_id else None
    banco=session.get(Banco, transacao.banco_id) if transacao.banco_id else None
    lines = [
        f"ID Transação: {transacao.id}",
        f"Tipo: {transacao.tipo}",
        f"Categoria: {cat.nome if cat else ''} / {sub.nome if sub else ''}",
        f"Centro de Custo: {cc.nome if cc else ''}",
        f"Cliente: {cli.nome if cli else ''}",
        f"Fornecedor: {forn.nome if forn else ''}",
        f"Banco: {banco.nome if banco else ''}",
        f"Valor: {money(transacao.valor)}",
        f"Data Prevista: {transacao.data_prevista.strftime('%d/%m/%Y')}",
        f"Pago? {'Sim' if transacao.foi_pago else 'Não'}",
        f"Data Real: {transacao.data_real.strftime('%d/%m/%Y') if transacao.data_real else ''}",
        f"Descrição: {transacao.descricao or ''}",
    ]
    y = H - margin - 28
    for ln in lines:
        c.drawString(margin, y, ln); y -= 14
    c.line(margin, 40, W-margin, 40)
    c.drawString(margin, 25, f"Emitido por {APP_TITLE} {APP_VERSION} em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.showPage(); c.save(); buffer.seek(0)
    return buffer.read()

# ===========================
# STREAMLIT
# ===========================
import plotly.express as px

st.set_page_config(page_title=APP_TITLE, page_icon="💼", layout="wide", initial_sidebar_state="expanded")

@st.cache_data(show_spinner=False)
def df_query_cached(sql: str) -> pd.DataFrame:
    return df_query(sql)

def success(msg: str): st.toast(msg, icon="✅")
def error(msg: str): st.toast(msg, icon="❌")

ensure_seed_data()

# ----- Sidebar -----
def _db_pretty(u: str) -> str:
    u = str(u)
    return u.replace("sqlite:///", "") if u.lower().startswith("sqlite:///") else u

with st.sidebar:
    st.title("💼 BK Gestão Financeira")
    st.caption(APP_VERSION)

    page = st.radio(
        "Navegação",
        ["Home", "Cadastro", "Metas", "Movimentações", "Relatórios", "Dashboards"],
        index=0,
        key="nav_page",
    )

    st.divider()
    st.markdown("**Banco de Dados**")
    st.code(_db_pretty(DB_URL), language="bash")

    st.markdown("**Anexos**")
    st.code(ATTACH_DIR, language="bash")

st.markdown("""
<style>
.stButton>button {border-radius: 12px; padding: .6rem 1rem;}
.stTextInput>div>div>input, .stNumberInput input, .stDateInput input {border-radius: 10px;}
.metric-card {background:#f8f9fb; border-radius:16px; padding:18px; border:1px solid #edf0f4}
</style>
""", unsafe_allow_html=True)

# ------------- helpers CRUD -------------
def input_id_to_edit_delete(df: pd.DataFrame, label="ID", key: str = None):
    ids = [int(x) for x in (df["id"].tolist() if "id" in df.columns else [])]
    if not ids:
        st.info("Nenhum registro.")
        return None
    return st.selectbox(label, ids, index=0, key=key)

def load_obj(session, model, obj_id: int):
    try:
        return session.get(model, int(obj_id)) if obj_id is not None else None
    except Exception:
        return None

# ===========================
# Home
# ===========================
if page == "Home":
    st.header("Visão Geral")
    col1, col2, col3, col4 = st.columns(4)
    with get_session() as s:
        total_e = s.query(func.sum(Transacao.valor)).filter(Transacao.tipo=="Entrada", Transacao.foi_pago==True).scalar() or 0
        total_s = s.query(func.sum(Transacao.valor)).filter(Transacao.tipo=="Saida",   Transacao.foi_pago==True).scalar() or 0
    with col1: st.metric("Entradas (Pagas)",  money(total_e))
    with col2: st.metric("Saídas (Pagas)",    money(total_s))
    with col3: st.metric("Resultado",         money(total_e-total_s))
    with col4:
        dfb = compute_bank_balances(); tot = dfb["saldo_atual"].sum() if not dfb.empty else 0.0
        st.metric("Saldo Total (Bancos)", money(tot))

    st.subheader("Saldos por Banco")
    dfb = compute_bank_balances()
    if dfb.empty: st.info("Cadastre bancos em **Cadastro > Bancos**.")
    else:
        st.dataframe(dfb[["nome","saldo_atual"]].rename(columns={"nome":"Banco","saldo_atual":"Saldo Atual"}), use_container_width=True)

    st.subheader("Próximos 30 dias — Fluxo Previsto")
    with get_session() as s:
        hoje = date.today(); fim = hoje + timedelta(days=30)
        q = s.query(Transacao).filter(Transacao.data_prevista>=hoje, Transacao.data_prevista<=fim).order_by(Transacao.data_prevista)
        df = pd.read_sql(q.statement, s.bind)
    if df.empty: st.info("Sem lançamentos previstos para os próximos 30 dias.")
    else:
        st.dataframe(df[["id","tipo","valor","data_prevista","foi_pago","data_real","descricao"]], use_container_width=True)

    st.subheader("Atrasados — Entradas/Saídas não pagas")
    atrasados = df_query("""
        SELECT t.id, t.tipo, c.nome AS categoria, s2.nome AS subcategoria, t.valor,
               t.data_prevista, cc.nome AS centro_custo,
               cli.nome AS cliente, f.nome AS fornecedor, b.nome AS banco, t.descricao,
               CAST(julianday('now') - julianday(t.data_prevista) AS INT) AS dias_atraso
        FROM transacoes t
        JOIN categorias c ON c.id=t.categoria_id
        LEFT JOIN subcategorias s2 ON s2.id=t.subcategoria_id
        LEFT JOIN centros_custo cc ON cc.id=t.centro_custo_id
        LEFT JOIN clientes cli ON cli.id=t.cliente_id
        LEFT JOIN fornecedores f ON f.id=t.fornecedor_id
        LEFT JOIN bancos b ON b.id=t.banco_id
        WHERE t.foi_pago=0 AND date(t.data_prevista) < date('now')
        ORDER BY t.data_prevista ASC
    """)
    if atrasados.empty: st.success("Não há lançamentos em atraso. 🎉")
    else:
        cE, cS = st.columns(2)
        ent = atrasados[atrasados["tipo"]=="Entrada"].copy()
        sai = atrasados[atrasados["tipo"]=="Saida"].copy()
        with cE:
            st.caption("Entradas em atraso")
            st.dataframe(ent[["id","categoria","subcategoria","cliente","valor","data_prevista","dias_atraso","descricao"]], use_container_width=True)
            st.metric("Total", money(ent["valor"].sum()))
        with cS:
            st.caption("Saídas em atraso")
            st.dataframe(sai[["id","categoria","subcategoria","fornecedor","valor","data_prevista","dias_atraso","descricao"]], use_container_width=True)
            st.metric("Total", money(sai["valor"].sum()))

# ===========================
# Cadastro
# ===========================
elif page == "Cadastro":
    st.header("Cadastro")
    tabs = st.tabs(["Clientes","Fornecedores","Bancos","Categorias","Subcategorias","Centros de Custo"])

    # ---------- Clientes ----------
    with tabs[0]:
        st.subheader("Clientes — Incluir")
        with st.form("form_cli_add", clear_on_submit=True):
            c1,c2,c3,c4 = st.columns(4)
            nome = c1.text_input("Nome", key="cli_add_nome")
            doc = c2.text_input("Documento", key="cli_add_doc")
            email = c3.text_input("E-mail", key="cli_add_email")
            tel = c4.text_input("Telefone", key="cli_add_tel")
            if st.form_submit_button("Adicionar Cliente") and nome:
                with get_session() as s:
                    if s.query(Cliente).filter_by(nome=nome).first(): error("Cliente já existe.")
                    else:
                        s.add(Cliente(nome=nome, documento=doc, email=email, telefone=tel))
                        _done(s, "Cliente cadastrado.")

        df_cli = df_query_cached("SELECT id, nome, documento, email, telefone, created_at FROM clientes ORDER BY id DESC")
        st.dataframe(df_cli, use_container_width=True)
        colE, colD = st.columns(2)
        with colE:
            st.markdown("**Editar Cliente**")
            if df_cli.empty: st.info("Sem clientes.")
            else:
                edit_id = input_id_to_edit_delete(df_cli, "ID", key="cli_edit_id")
                if edit_id:
                    with get_session() as s:
                        obj = load_obj(s, Cliente, edit_id)
                        if obj:
                            with st.form("form_cli_edit"):
                                c1,c2,c3,c4 = st.columns(4)
                                nome = c1.text_input("Nome", obj.nome, key="cli_edit_nome")
                                doc = c2.text_input("Documento", obj.documento or "", key="cli_edit_doc")
                                email = c3.text_input("E-mail", obj.email or "", key="cli_edit_email")
                                tel = c4.text_input("Telefone", obj.telefone or "", key="cli_edit_tel")
                                if st.form_submit_button("Salvar alterações"):
                                    obj.nome, obj.documento, obj.email, obj.telefone = nome, doc, email, tel
                                    _done(s, "Cliente atualizado.")
        with colD:
            st.markdown("**Excluir Cliente**")
            if df_cli.empty: st.info("Sem clientes.")
            else:
                del_id = input_id_to_edit_delete(df_cli, "ID", key="cli_del_id")
                if del_id and st.button("Excluir", type="primary", key="cli_del_btn"):
                    with get_session() as s:
                        obj = load_obj(s, Cliente, del_id)
                        if obj:
                            s.delete(obj)
                            _done(s, "Cliente excluído.")

    # ---------- Fornecedores ----------
    with tabs[1]:
        st.subheader("Fornecedores — Incluir")
        with st.form("form_forn_add", clear_on_submit=True):
            c1,c2,c3,c4 = st.columns(4)
            nome = c1.text_input("Nome", key="forn_add_nome"); doc = c2.text_input("Documento", key="forn_add_doc")
            email = c3.text_input("E-mail", key="forn_add_email"); tel = c4.text_input("Telefone", key="forn_add_tel")
            if st.form_submit_button("Adicionar Fornecedor") and nome:
                with get_session() as s:
                    if s.query(Fornecedor).filter_by(nome=nome).first(): error("Fornecedor já existe.")
                    else:
                        s.add(Fornecedor(nome=nome, documento=doc, email=email, telefone=tel))
                        _done(s, "Fornecedor cadastrado.")
        df_f = df_query_cached("SELECT id, nome, documento, email, telefone, created_at FROM fornecedores ORDER BY id DESC")
        st.dataframe(df_f, use_container_width=True)
        colE, colD = st.columns(2)
        with colE:
            st.markdown("**Editar Fornecedor**")
            if df_f.empty: st.info("Sem fornecedores.")
            else:
                edit_id = input_id_to_edit_delete(df_f, "ID", key="forn_edit_id")
                if edit_id:
                    with get_session() as s:
                        obj = load_obj(s, Fornecedor, edit_id)
                        if obj:
                            with st.form("form_forn_edit"):
                                c1,c2,c3,c4 = st.columns(4)
                                nome = c1.text_input("Nome", obj.nome, key="forn_edit_nome")
                                doc = c2.text_input("Documento", obj.documento or "", key="forn_edit_doc")
                                email = c3.text_input("E-mail", obj.email or "", key="forn_edit_email")
                                tel = c4.text_input("Telefone", obj.telefone or "", key="forn_edit_tel")
                                if st.form_submit_button("Salvar alterações"):
                                    obj.nome, obj.documento, obj.email, obj.telefone = nome, doc, email, tel
                                    _done(s, "Fornecedor atualizado.")
        with colD:
            st.markdown("**Excluir Fornecedor**")
            if df_f.empty: st.info("Sem fornecedores.")
            else:
                del_id = input_id_to_edit_delete(df_f, "ID", key="forn_del_id")
                if del_id and st.button("Excluir fornecedor", key="forn_del_btn"):
                    with get_session() as s:
                        obj = load_obj(s, Fornecedor, del_id)
                        if obj:
                            s.delete(obj)
                            _done(s, "Fornecedor excluído.")

    # ---------- Bancos ----------
    with tabs[2]:
        st.subheader("Bancos — Incluir")
        with st.form("form_banco_add", clear_on_submit=True):
            c1,c2 = st.columns(2)
            nome = c1.text_input("Nome do banco", key="bco_add_nome")
            saldo = c2.number_input("Saldo inicial", min_value=0.0, step=100.0, format="%.2f", key="bco_add_saldo")
            if st.form_submit_button("Adicionar Banco") and nome:
                with get_session() as s:
                    if s.query(Banco).filter_by(nome=nome).first(): error("Banco já existe.")
                    else:
                        s.add(Banco(nome=nome, saldo_inicial=float(saldo)))
                        _done(s, "Banco cadastrado.")
        df_b = df_query_cached("SELECT id, nome, saldo_inicial, created_at FROM bancos ORDER BY id DESC")
        st.dataframe(df_b, use_container_width=True)
        colE, colD = st.columns(2)
        with colE:
            st.markdown("**Editar Banco**")
            if df_b.empty: st.info("Sem bancos.")
            else:
                edit_id = input_id_to_edit_delete(df_b, "ID", key="bco_edit_id")
                if edit_id:
                    with get_session() as s:
                        obj = load_obj(s, Banco, edit_id)
                        if obj:
                            with st.form("form_banco_edit"):
                                c1,c2 = st.columns(2)
                                nome = c1.text_input("Nome", obj.nome, key="bco_edit_nome")
                                saldo = c2.number_input("Saldo inicial", min_value=0.0, step=100.0, format="%.2f", value=float(obj.saldo_inicial or 0), key="bco_edit_saldo")
                                if st.form_submit_button("Salvar alterações"):
                                    obj.nome, obj.saldo_inicial = nome, float(saldo)
                                    _done(s, "Banco atualizado.")
        with colD:
            st.markdown("**Excluir Banco**")
            if df_b.empty: st.info("Sem bancos.")
            else:
                del_id = input_id_to_edit_delete(df_b, "ID", key="bco_del_id")
                if del_id and st.button("Excluir banco", key="bco_del_btn"):
                    with get_session() as s:
                        obj = load_obj(s, Banco, del_id)
                        if obj:
                            s.delete(obj)
                            _done(s, "Banco excluído.")

    # ---------- Categorias ----------
    with tabs[3]:
        st.subheader("Categorias — Incluir")
        with st.form("form_cat_add", clear_on_submit=True):
            c1,c2 = st.columns(2)
            tipo = c1.selectbox("Tipo", ["Entrada","Saida"], key="cat_add_tipo")
            nome = c2.text_input("Nome da categoria", key="cat_add_nome")
            if st.form_submit_button("Adicionar Categoria") and nome:
                with get_session() as s:
                    s.add(Categoria(tipo=tipo, nome=nome))
                    _done(s, "Categoria cadastrada.")
        df_c = df_query_cached("SELECT id, tipo, nome FROM categorias ORDER BY id DESC")
        st.dataframe(df_c, use_container_width=True)
        colE, colD = st.columns(2)
        with colE:
            st.markdown("**Editar Categoria**")
            if df_c.empty: st.info("Sem categorias.")
            else:
                edit_id = input_id_to_edit_delete(df_c, "ID", key="cat_edit_id")
                if edit_id:
                    with get_session() as s:
                        obj = load_obj(s, Categoria, edit_id)
                        if obj:
                            with st.form("form_cat_edit"):
                                c1,c2 = st.columns(2)
                                tipo = c1.selectbox("Tipo", ["Entrada","Saida"], index=0 if obj.tipo=="Entrada" else 1, key="cat_edit_tipo")
                                nome = c2.text_input("Nome", obj.nome, key="cat_edit_nome")
                                if st.form_submit_button("Salvar alterações"):
                                    obj.tipo, obj.nome = tipo, nome
                                    _done(s, "Categoria atualizada.")
        with colD:
            st.markdown("**Excluir Categoria**")
            if df_c.empty: st.info("Sem categorias.")
            else:
                del_id = input_id_to_edit_delete(df_c, "ID", key="cat_del_id")
                if del_id and st.button("Excluir categoria", key="cat_del_btn"):
                    with get_session() as s:
                        obj = load_obj(s, Categoria, del_id)
                        if obj:
                            s.delete(obj)
                            _done(s, "Categoria excluída.")

    # ---------- Subcategorias ----------
    with tabs[4]:
        st.subheader("Subcategorias — Incluir")
        with get_session() as s:
            cats = pd.read_sql("SELECT id, tipo, nome FROM categorias ORDER BY tipo, nome", s.bind)
        with st.form("form_sub_add", clear_on_submit=True):
            c1,c2 = st.columns(2)
            if cats.empty:
                st.info("Cadastre categorias primeiro."); st.form_submit_button("Adicionar", disabled=True)
            else:
                cat_opt = c1.selectbox("Categoria", [f"{r['tipo']} - {r['nome']} (# {r['id']})" for _,r in cats.iterrows()], key="sub_add_cat")
                nome = c2.text_input("Nome da subcategoria", key="sub_add_nome")
                if st.form_submit_button("Adicionar Subcategoria") and nome:
                    cat_id = extract_id(cat_opt)
                    with get_session() as s:
                        s.add(Subcategoria(categoria_id=cat_id, nome=nome))
                        _done(s, "Subcategoria cadastrada.")
        df_sc = df_query_cached("""
            SELECT s.id, c.tipo, c.nome AS categoria, s.nome AS subcategoria
            FROM subcategorias s JOIN categorias c ON c.id=s.categoria_id
            ORDER BY c.tipo, c.nome, s.nome
        """)
        st.dataframe(df_sc, use_container_width=True)
        colE, colD = st.columns(2)
        with colE:
            st.markdown("**Editar Subcategoria**")
            if df_sc.empty: st.info("Sem subcategorias.")
            else:
                edit_id = input_id_to_edit_delete(df_sc, "ID", key="sub_edit_id")
                if edit_id:
                    with get_session() as s:
                        obj = load_obj(s, Subcategoria, edit_id)
                        cats = pd.read_sql("SELECT id, tipo, nome FROM categorias ORDER BY tipo, nome", s.bind)
                        if obj:
                            with st.form("form_sub_edit"):
                                c1,c2 = st.columns(2)
                                cat_obj = s.get(Categoria, obj.categoria_id)
                                cat_label = f"{cat_obj.tipo} - {cat_obj.nome} (# {obj.categoria_id})" if cat_obj else "-"
                                all_opts = [f"{r['tipo']} - {r['nome']} (# {r['id']})" for _,r in cats.iterrows()]
                                options = [cat_label] + [o for o in all_opts if o != cat_label]
                                escolha = c1.selectbox("Categoria", options, key="sub_edit_cat")
                                nome = c2.text_input("Nome", obj.nome, key="sub_edit_nome")
                                if st.form_submit_button("Salvar alterações"):
                                    obj.categoria_id = extract_id(escolha) or obj.categoria_id
                                    obj.nome = nome
                                    _done(s, "Subcategoria atualizada.")
        with colD:
            st.markdown("**Excluir Subcategoria**")
            if df_sc.empty: st.info("Sem subcategorias.")
            else:
                del_id = input_id_to_edit_delete(df_sc, "ID", key="sub_del_id")
                if del_id and st.button("Excluir subcategoria", key="sub_del_btn"):
                    with get_session() as s:
                        obj = load_obj(s, Subcategoria, del_id)
                        if obj:
                            s.delete(obj)
                            _done(s, "Subcategoria excluída.")

    # ---------- Centros de Custo ----------
    with tabs[5]:
        st.subheader("Centros de Custo — Incluir")
        with st.form("form_cc_add", clear_on_submit=True):
            c1,c2 = st.columns(2)
            nome = c1.text_input("Nome do centro de custo", key="cc_add_nome")
            desc = c2.text_input("Descrição", key="cc_add_desc")
            if st.form_submit_button("Adicionar Centro de Custo") and nome:
                with get_session() as s:
                    if s.query(CentroCusto).filter_by(nome=nome).first(): error("Centro de custo já existe.")
                    else:
                        s.add(CentroCusto(nome=nome, descricao=desc))
                        _done(s, "Centro de custo cadastrado.")
        df_cc = df_query_cached("SELECT id, nome, descricao FROM centros_custo ORDER BY id DESC")
        st.dataframe(df_cc, use_container_width=True)
        colE, colD = st.columns(2)
        with colE:
            st.markdown("**Editar Centro de Custo**")
            if df_cc.empty: st.info("Sem centros de custo.")
            else:
                edit_id = input_id_to_edit_delete(df_cc, "ID", key="cc_edit_id")
                if edit_id:
                    with get_session() as s:
                        obj = load_obj(s, CentroCusto, edit_id)
                        if obj:
                            with st.form("form_cc_edit"):
                                c1,c2 = st.columns(2)
                                nome = c1.text_input("Nome", obj.nome, key="cc_edit_nome")
                                desc = c2.text_input("Descrição", obj.descricao or "", key="cc_edit_desc")
                                if st.form_submit_button("Salvar alterações"):
                                    obj.nome, obj.descricao = nome, desc
                                    _done(s, "Centro de custo atualizado.")
        with colD:
            st.markdown("**Excluir Centro de Custo**")
            if df_cc.empty: st.info("Sem centros de custo.")
            else:
                del_id = input_id_to_edit_delete(df_cc, "ID", key="cc_del_id")
                if del_id and st.button("Excluir centro de custo", key="cc_del_btn"):
                    with get_session() as s:
                        obj = load_obj(s, CentroCusto, del_id)
                        if obj:
                            s.delete(obj)
                            _done(s, "Centro de custo excluído.")

# ===========================
# Metas
# ===========================
elif page == "Metas":
    st.header("Metas (Previsões)")
    with get_session() as s:
        cats = pd.read_sql("SELECT id, tipo, nome FROM categorias ORDER BY tipo, nome", s.bind)
        subs = pd.read_sql("SELECT id, categoria_id, nome FROM subcategorias", s.bind)
    colf = st.columns(4)
    ano = colf[0].number_input("Ano", min_value=2000, max_value=2100, value=date.today().year, key="meta_ano")
    mes = colf[1].number_input("Mês", min_value=1, max_value=12, value=date.today().month, key="meta_mes")
    cat_opt = colf[2].selectbox("Categoria", ["-"] + [f"{r['tipo']} - {r['nome']} (# {r['id']})" for _,r in cats.iterrows()], key="meta_cat")
    valor_prev = colf[3].number_input("Valor Previsto (R$)", min_value=0.0, step=100.0, format="%.2f", key="meta_valor_prev")
    if cat_opt == "-":
        st.info("Selecione uma categoria para lançar metas.")
    else:
        cat_id = extract_id(cat_opt)
        subs_cat = subs[subs["categoria_id"]==cat_id]
        sub_opt = st.selectbox("Subcategoria", ["-"] + [f"{r['nome']} (# {r['id']})" for _,r in subs_cat.iterrows()], key="meta_sub")
        if st.button("Salvar Meta", key="meta_save"):
            with get_session() as s:
                s.add(Meta(
                    ano=int(ano), mes=int(mes),
                    categoria_id=cat_id,
                    subcategoria_id=extract_id(sub_opt) if sub_opt!="-" else None,
                    valor_previsto=float(valor_prev),
                ))
                _done(s, "Meta salva.")

    st.subheader("Metas do mês")
    with get_session() as s:
        dfm = pd.read_sql("""
            SELECT m.id, m.ano, m.mes, c.tipo, c.nome as categoria, s2.nome as subcategoria, m.valor_previsto
            FROM metas m
            JOIN categorias c ON c.id=m.categoria_id
            LEFT JOIN subcategorias s2 ON s2.id=m.subcategoria_id
            WHERE m.ano=:ano AND m.mes=:mes
            ORDER BY c.tipo, categoria, subcategoria
        """, s.bind, params={"ano": int(ano), "mes": int(mes)})
    st.dataframe(dfm, use_container_width=True)

    colE, colD = st.columns(2)
    with colE:
        st.markdown("**Editar Meta**")
        if dfm.empty: st.info("Sem metas para o período.")
        else:
            edit_id = input_id_to_edit_delete(dfm, "ID", key="meta_edit_id")
            if edit_id:
                with get_session() as s:
                    obj = load_obj(s, Meta, edit_id)
                    if obj:
                        with st.form("form_meta_edit"):
                            c1,c2,c3 = st.columns(3)
                            ano_n = c1.number_input("Ano", 2000, 2100, value=int(obj.ano), key="meta_edit_ano")
                            mes_n = c2.number_input("Mês", 1, 12, value=int(obj.mes), key="meta_edit_mes")
                            valor = c3.number_input("Valor Previsto", min_value=0.0, step=100.0, format="%.2f", value=float(obj.valor_previsto or 0), key="meta_edit_valor")
                            cats = pd.read_sql("SELECT id, tipo, nome FROM categorias ORDER BY tipo, nome", s.bind)
                            cat_obj = s.get(Categoria, obj.categoria_id)
                            cat_label = f"{cat_obj.tipo} - {cat_obj.nome} (# {obj.categoria_id})" if cat_obj else "-"
                            categoria = st.selectbox("Categoria", [cat_label] + [f"{r['tipo']} - {r['nome']} (# {r['id']})" for _,r in cats.iterrows()], key="meta_edit_cat")
                            sub_opt_list = pd.read_sql(
                                "SELECT id, nome FROM subcategorias WHERE categoria_id = :c",
                                s.bind, params={"c": (extract_id(categoria) or obj.categoria_id)},
                            )
                            sub_label = ""
                            if obj.subcategoria_id:
                                sc = s.get(Subcategoria, obj.subcategoria_id)
                                if sc: sub_label = f"{sc.nome} (# {sc.id})"
                            subcat = st.selectbox("Subcategoria", ["-"] + ([sub_label] if sub_label else []) + [f"{r['nome']} (# {r['id']})" for _,r in sub_opt_list.iterrows()], key="meta_edit_sub")
                            if st.form_submit_button("Salvar alterações"):
                                obj.ano, obj.mes = int(ano_n), int(mes_n)
                                obj.categoria_id = extract_id(categoria) or obj.categoria_id
                                obj.subcategoria_id = extract_id(subcat) if subcat and subcat != "-" else None
                                obj.valor_previsto = float(valor)
                                _done(s, "Meta atualizada.")
    with colD:
        st.markdown("**Excluir Meta**")
        if dfm.empty: st.info("Sem metas.")
        else:
            del_id = input_id_to_edit_delete(dfm, "ID", key="meta_del_id")
            if del_id and st.button("Excluir meta", key="meta_del_btn"):
                with get_session() as s:
                    obj = load_obj(s, Meta, del_id)
                    if obj:
                        s.delete(obj)
                        _done(s, "Meta excluída.")

# ===========================
# Movimentações
# ===========================
elif page == "Movimentações":
    st.header("Movimentações")
    tabs = st.tabs(["Lançamentos", "Transferências entre bancos"])

    # --------- Lançamentos (ADD) ---------
    with tabs[0]:
        with get_session() as s:
            cats = pd.read_sql("SELECT id, tipo, nome FROM categorias ORDER BY tipo, nome", s.bind)
            subs = pd.read_sql("SELECT id, categoria_id, nome FROM subcategorias", s.bind)
            ccs  = pd.read_sql("SELECT id, nome FROM centros_custo", s.bind)
            clientes = pd.read_sql("SELECT id, nome FROM clientes ORDER BY nome", s.bind)
            fornecedores = pd.read_sql("SELECT id, nome FROM fornecedores ORDER BY nome", s.bind)
            bancos = pd.read_sql("SELECT id, nome FROM bancos ORDER BY nome", s.bind)

        st.subheader("Incluir Lançamento")
        with st.form("form_tx_add", clear_on_submit=True):
            c1,c2,c3,c4 = st.columns(4)
            tipo = c1.selectbox("Tipo", ["Entrada","Saida"], key="tx_add_tipo")
            cat_rows = [r for _, r in cats.iterrows() if r["tipo"] == tipo]
            cat_opts = [f"{r['tipo']} - {r['nome']} (# {r['id']})" for r in cat_rows]
            cat_opt = c2.selectbox("Categoria", cat_opts, placeholder="Selecione", index=0 if cat_opts else None, key="tx_add_cat")
            if not cat_opts:
                st.warning("Cadastre ao menos uma categoria desse tipo.")
                st.form_submit_button("Lançar", disabled=True)
            else:
                cat_id = extract_id(cat_opt)
                subs_cat = subs[subs["categoria_id"]==cat_id]
                sub_opt = c3.selectbox("Subcategoria", ["-"] + [f"{r['nome']} (# {r['id']})" for _,r in subs_cat.iterrows()], key="tx_add_sub")
                valor = c4.number_input("Valor (R$)", min_value=0.0, step=100.0, format="%.2f", key="tx_add_valor")

                d1,d2,d3,d4 = st.columns(4)
                data_prevista = d1.date_input("Data Prevista", value=date.today(), key="tx_add_data_prev")
                foi_pago = d2.checkbox("Pago?", key="tx_add_pago")
                data_real = d3.date_input("Data Real", value=date.today(), key="tx_add_data_real") if foi_pago else None
                banco_opt = d4.selectbox("Banco", ["-"] + [f"{r['nome']} (# {r['id']})" for _,r in bancos.iterrows()], key="tx_add_banco")

                e1,e2,e3 = st.columns(3)
                cc_opt  = e1.selectbox("Centro de Custo", ["-"] + [f"{r['nome']} (# {r['id']})" for _,r in ccs.iterrows()], key="tx_add_cc")
                cli_opt = e2.selectbox("Cliente (Entrada)", ["-"] + [f"{r['nome']} (# {r['id']})" for _,r in clientes.iterrows()], key="tx_add_cli")
                forn_opt= e3.selectbox("Fornecedor (Saída)", ["-"] + [f"{r['nome']} (# {r['id']})" for _,r in fornecedores.iterrows()], key="tx_add_forn")

                desc = st.text_area("Descrição", key="tx_add_desc")

                st.markdown("**Recorrência**")
                r1,r2,r3 = st.columns(3)
                recorrencia = r1.selectbox("Tipo", ["Unica","Mensal","Anual","Parcelado"], key="tx_add_rec_tipo")
                parcelas_total = None
                if recorrencia == "Parcelado":
                    parcelas_total = r2.number_input("Nº de parcelas", min_value=1, max_value=120, value=1, key="tx_add_rec_parc")
                    periodicidade = r3.selectbox("Periodicidade", ["Mensal","Anual"], key="tx_add_rec_per")
                else:
                    periodicidade = "Mensal"

                if st.form_submit_button("Lançar"):
                    with get_session() as s:
                        def add_tx(idx:int, dt:date):
                            t = Transacao(
                                tipo=tipo, categoria_id=cat_id,
                                subcategoria_id=extract_id(sub_opt) if sub_opt!="-" else None,
                                valor=float(valor), data_prevista=dt,
                                foi_pago=bool(foi_pago),
                                data_real=(data_real if foi_pago else None),
                                centro_custo_id=extract_id(cc_opt) if cc_opt!="-" else None,
                                cliente_id=extract_id(cli_opt) if (tipo=="Entrada" and cli_opt!="-") else None,
                                fornecedor_id=extract_id(forn_opt) if (tipo=="Saida" and forn_opt!="-") else None,
                                banco_id=extract_id(banco_opt) if banco_opt!="-" else None,
                                descricao=desc, recorrencia=recorrencia,
                                parcelas_total=int(parcelas_total) if parcelas_total else None,
                                parcela_index=idx if parcelas_total else None,
                            )
                            s.add(t); s.flush()
                        if recorrencia == "Unica":
                            add_tx(None, data_prevista)
                        elif recorrencia in ("Mensal","Anual"):
                            steps = 12 if recorrencia=="Mensal" else 5
                            for i in range(steps):
                                dt = data_prevista + (relativedelta(months=i) if recorrencia=="Mensal" else relativedelta(years=i))
                                add_tx(None, dt)
                        elif recorrencia == "Parcelado":
                            for i in range(1, int(parcelas_total)+1):
                                dt = data_prevista + (relativedelta(months=i-1) if periodicidade=="Mensal" else relativedelta(years=i-1))
                                add_tx(i, dt)
                        _done(s, "Movimentação(ões) lançada(s).")

        st.subheader("Lançamentos — Lista")
        with get_session() as s:
            df_tx = pd.read_sql("""
                SELECT t.id, t.tipo, c.nome as categoria, s2.nome as subcategoria, t.valor,
                       t.data_prevista, t.foi_pago, t.data_real,
                       cc.nome as centro_custo, cli.nome as cliente, f.nome as fornecedor, b.nome as banco, t.descricao
                FROM transacoes t
                JOIN categorias c ON c.id=t.categoria_id
                LEFT JOIN subcategorias s2 ON s2.id=t.subcategoria_id
                LEFT JOIN centros_custo cc ON cc.id=t.centro_custo_id
                LEFT JOIN clientes cli ON cli.id=t.cliente_id
                LEFT JOIN fornecedores f ON f.id=t.fornecedor_id
                LEFT JOIN bancos b ON b.id=t.banco_id
                ORDER BY t.data_prevista DESC, t.id DESC
            """, s.bind)
        st.dataframe(df_tx, use_container_width=True)

        colE, colD = st.columns(2)
        with colE:
            st.markdown("**Editar Lançamento**")
            if df_tx.empty: st.info("Sem lançamentos.")
            else:
                edit_id = input_id_to_edit_delete(df_tx, "ID", key="tx_edit_id")
                if edit_id:
                    with get_session() as s:
                        t = load_obj(s, Transacao, edit_id)
                        if t:
                            with st.form("form_tx_edit"):
                                c1,c2,c3,c4 = st.columns(4)
                                tipo = c1.selectbox("Tipo", ["Entrada","Saida"], index=0 if t.tipo=="Entrada" else 1, key="tx_edit_tipo")
                                cats = pd.read_sql("SELECT id, tipo, nome FROM categorias ORDER BY tipo, nome", s.bind)
                                cat_obj = s.get(Categoria, t.categoria_id)
                                cat_label = f"{cat_obj.tipo} - {cat_obj.nome} (# {t.categoria_id})" if cat_obj else "-"
                                all_opts = [f"{r['tipo']} - {r['nome']} (# {r['id']})" for _,r in cats.iterrows()]
                                cat_opt = c2.selectbox("Categoria", [cat_label] + [o for o in all_opts if o != cat_label], key="tx_edit_cat")
                                subs = pd.read_sql(
                                    "SELECT id, nome FROM subcategorias WHERE categoria_id=:c",
                                    s.bind, params={"c": (extract_id(cat_opt) or t.categoria_id)}
                                )
                                sub_label = "-"
                                if t.subcategoria_id:
                                    sc = s.get(Subcategoria, t.subcategoria_id)
                                    if sc: sub_label = f"{sc.nome} (# {sc.id})"
                                sub_opt = c3.selectbox("Subcategoria", ["-"] + ([sub_label] if sub_label != "-" else []) + [f"{r['nome']} (# {r['id']})" for _,r in subs.iterrows()], key="tx_edit_sub")
                                valor = c4.number_input("Valor (R$)", min_value=0.0, step=100.0, format="%.2f", value=float(t.valor or 0), key="tx_edit_valor")

                                d1,d2,d3,d4 = st.columns(4)
                                data_prevista = d1.date_input("Data Prevista", value=t.data_prevista, key="tx_edit_data_prev")
                                foi_pago = d2.checkbox("Pago?", value=bool(t.foi_pago), key="tx_edit_pago")
                                data_real = d3.date_input("Data Real", value=t.data_real or date.today(), key="tx_edit_data_real") if foi_pago else None
                                bancos = pd.read_sql("SELECT id, nome FROM bancos ORDER BY nome", s.bind)
                                banco_label = "-"
                                if t.banco_id:
                                    b = s.get(Banco, t.banco_id)
                                    if b: banco_label = f"{b.nome} (# {t.banco_id})"
                                banco_opt = d4.selectbox("Banco", [banco_label] + [f"{r['nome']} (# {r['id']})" for _,r in bancos.iterrows()], key="tx_edit_banco")

                                e1,e2,e3 = st.columns(3)
                                ccs  = pd.read_sql("SELECT id, nome FROM centros_custo ORDER BY nome", s.bind)
                                cc_label = "-"
                                if t.centro_custo_id:
                                    cc = s.get(CentroCusto, t.centro_custo_id)
                                    if cc: cc_label = f"{cc.nome} (# {t.centro_custo_id})"
                                cc_opt  = e1.selectbox("Centro de Custo", [cc_label] + [f"{r['nome']} (# {r['id']})" for _,r in ccs.iterrows()], key="tx_edit_cc")
                                clientes = pd.read_sql("SELECT id, nome FROM clientes ORDER BY nome", s.bind)
                                cli_label = "-"
                                if t.cliente_id:
                                    cli = s.get(Cliente, t.cliente_id)
                                    if cli: cli_label = f"{cli.nome} (# {t.cliente_id})"
                                cli_opt = e2.selectbox("Cliente (Entrada)", [cli_label] + [f"{r['nome']} (# {r['id']})" for _,r in clientes.iterrows()], key="tx_edit_cli")
                                fornecedores = pd.read_sql("SELECT id, nome FROM fornecedores ORDER BY nome", s.bind)
                                forn_label = "-"
                                if t.fornecedor_id:
                                    forn = s.get(Fornecedor, t.fornecedor_id)
                                    if forn: forn_label = f"{forn.nome} (# {t.fornecedor_id})"
                                forn_opt= e3.selectbox("Fornecedor (Saída)", [forn_label] + [f"{r['nome']} (# {r['id']})" for _,r in fornecedores.iterrows()], key="tx_edit_forn")

                                desc = st.text_area("Descrição", t.descricao or "", key="tx_edit_desc")

                                if st.form_submit_button("Salvar alterações"):
                                    t.tipo = tipo
                                    t.categoria_id = extract_id(cat_opt) or t.categoria_id
                                    t.subcategoria_id = extract_id(sub_opt) if sub_opt and sub_opt != "-" else None
                                    t.valor = float(valor)
                                    t.data_prevista = data_prevista
                                    t.foi_pago = bool(foi_pago)
                                    t.data_real = data_real if foi_pago else None
                                    t.banco_id = extract_id(banco_opt) if banco_opt and banco_opt != "-" else None
                                    t.centro_custo_id = extract_id(cc_opt) if cc_opt and cc_opt != "-" else None
                                    t.cliente_id = extract_id(cli_opt) if cli_opt and cli_opt != "-" else None
                                    t.fornecedor_id = extract_id(forn_opt) if forn_opt and forn_opt != "-" else None
                                    t.descricao = desc
                                    _done(s, "Lançamento atualizado.")

        with colD:
            st.markdown("**Excluir Lançamento**")
            if df_tx.empty: st.info("Sem lançamentos.")
            else:
                del_id = input_id_to_edit_delete(df_tx, "ID", key="tx_del_id")
                if del_id and st.button("Excluir lançamento", key="tx_del_btn"):
                    with get_session() as s:
                        t = load_obj(s, Transacao, del_id)
                        if t:
                            s.delete(t)
                            _done(s, "Lançamento excluído.")

        # ---- Anexos / Recibo ----
        st.subheader("Anexos e Recibos")
        colA, colB = st.columns([2,1])
        with colA:
            trans_id = st.number_input("ID da transação", min_value=1, step=1, value=1, key="anx_tx_id")
            up = st.file_uploader("Anexar arquivo", type=["pdf","png","jpg","jpeg","xlsx","csv","docx","zip"], accept_multiple_files=True, key="anx_uploader")
            if st.button("Salvar Anexo(s)", key="anx_save"):
                with get_session() as s:
                    if not s.get(Transacao, int(trans_id)): error("Transação não encontrada.")
                    else:
                        for f in up or []:
                            fname = f"T{int(trans_id)}_{int(datetime.utcnow().timestamp())}_{f.name}"
                            fpath = os.path.join(ATTACH_DIR, fname)
                            with open(fpath, "wb") as fh: fh.write(f.getbuffer())
                            s.add(Anexo(transacao_id=int(trans_id), filename=fname, path=fpath))
                        _done(s, "Anexos salvos.")
        with colB:
            if st.button("Gerar Recibo (PDF)", key="recibo_btn"):
                with get_session() as s:
                    t = s.get(Transacao, int(trans_id))
                    if not t: error("Transação não encontrada.")
                    else:
                        pdf_bytes = make_recibo_pdf(t, s)
                        fname = f"RECIBO_T{t.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
                        fpath = os.path.join(ATTACH_DIR, fname)
                        with open(fpath, "wb") as f:
                            f.write(pdf_bytes)
                        success(f"Recibo salvo em {fpath}")
                        st.download_button(
                            "Baixar Recibo",
                            data=pdf_bytes,
                            file_name=fname,
                            mime="application/pdf",
                            key="recibo_download",
                        )

    # --------- Transferências ---------
    with tabs[1]:
        st.caption("Transferências movem saldos entre bancos (não afetam resultado).")
        with get_session() as s:
            bancos = pd.read_sql("SELECT id, nome FROM bancos ORDER BY nome", s.bind)

        st.subheader("Incluir Transferência")
        with st.form("form_trf_add", clear_on_submit=True):
            c1,c2,c3,c4 = st.columns(4)
            b_origem = c1.selectbox(
                "Banco origem",
                [f"{r['nome']} (# {r['id']})" for _,r in bancos.iterrows()] if not bancos.empty else [],
                key="trf_add_origem",
            )
            b_dest   = c2.selectbox(
                "Banco destino",
                [f"{r['nome']} (# {r['id']})" for _,r in bancos.iterrows()] if not bancos.empty else [],
                key="trf_add_dest",
            )
            valor    = c3.number_input("Valor (R$)", min_value=0.0, step=100.0, format="%.2f", key="trf_add_valor")
            data_prev= c4.date_input("Data prevista", value=date.today(), key="trf_add_data")
            desc     = st.text_input("Descrição (opcional)", key="trf_add_desc")
            if st.form_submit_button("Cadastrar Transferência") and b_origem and b_dest and valor>0:
                o_id = extract_id(b_origem); d_id = extract_id(b_dest)
                if not o_id or not d_id:
                    error("Selecione origem e destino válidos.")
                elif o_id == d_id:
                    error("Origem e destino não podem ser iguais.")
                else:
                    with get_session() as s:
                        s.add(Transferencia(
                            banco_origem_id=o_id,
                            banco_destino_id=d_id,
                            valor=float(valor),
                            data_prevista=data_prev,
                            descricao=desc
                        ))
                        _done(s, "Transferência cadastrada.")

        st.subheader("Lista de Transferências")
        with get_session() as s:
            dft = pd.read_sql("""
                SELECT t.id, b1.nome AS origem, b2.nome AS destino, t.valor, t.data_prevista,
                       t.foi_executada, t.data_real, t.descricao
                FROM transferencias t
                JOIN bancos b1 ON b1.id=t.banco_origem_id
                JOIN bancos b2 ON b2.id=t.banco_destino_id
                ORDER BY t.data_prevista DESC, t.id DESC
            """, s.bind)
        st.dataframe(dft, use_container_width=True)

        exec_id = input_id_to_edit_delete(dft, "ID para executar/desfazer", key="trf_exec_id") if not dft.empty else None
        colx1, colx2 = st.columns(2)
        with colx1:
            if st.button("Executar agora", key="trf_exec_btn") and exec_id:
                with get_session() as s:
                    tr = s.get(Transferencia, int(exec_id))
                    if not tr:
                        error("Transferência não encontrada.")
                    else:
                        tr.foi_executada = True
                        tr.data_real = date.today()
                        _done(s, "Transferência executada.")
        with colx2:
            if st.button("Desfazer execução", key="trf_unexec_btn") and exec_id:
                with get_session() as s:
                    tr = s.get(Transferencia, int(exec_id))
                    if not tr:
                        error("Transferência não encontrada.")
                    else:
                        tr.foi_executada = False
                        tr.data_real = None
                        _done(s, "Execução desfeita.")

        st.subheader("Editar / Excluir Transferência")
        colE, colD = st.columns(2)
        with colE:
            if dft.empty:
                st.info("Sem transferências.")
            else:
                edit_id = input_id_to_edit_delete(dft, "ID", key="trf_edit_id")
                if edit_id:
                    with get_session() as s:
                        tr = load_obj(s, Transferencia, edit_id)
                        bancos = pd.read_sql("SELECT id, nome FROM bancos ORDER BY nome", s.bind)
                        if tr:
                            with st.form("form_trf_edit"):
                                c1,c2,c3,c4 = st.columns(4)
                                borig_cur = s.get(Banco, tr.banco_origem_id)
                                bdest_cur = s.get(Banco, tr.banco_destino_id)
                                borig = c1.selectbox(
                                    "Origem",
                                    ([f"{borig_cur.nome} (# {tr.banco_origem_id})"] if borig_cur else []) +
                                    [f"{r['nome']} (# {r['id']})" for _,r in bancos.iterrows()],
                                    key="trf_edit_origem",
                                )
                                bdest = c2.selectbox(
                                    "Destino",
                                    ([f"{bdest_cur.nome} (# {tr.banco_destino_id})"] if bdest_cur else []) +
                                    [f"{r['nome']} (# {r['id']})" for _,r in bancos.iterrows()],
                                    key="trf_edit_dest",
                                )
                                valor = c3.number_input("Valor", min_value=0.0, step=100.0, format="%.2f", value=float(tr.valor), key="trf_edit_valor")
                                data_prev = c4.date_input("Data prevista", value=tr.data_prevista, key="trf_edit_data")
                                foi = st.checkbox("Executada?", value=bool(tr.foi_executada), key="trf_edit_exec")
                                data_real = st.date_input("Data real", value=tr.data_real or date.today(), key="trf_edit_data_real") if foi else None
                                desc = st.text_input("Descrição", value=tr.descricao or "", key="trf_edit_desc")
                                if st.form_submit_button("Salvar alterações"):
                                    tr.banco_origem_id = extract_id(borig) or tr.banco_origem_id
                                    tr.banco_destino_id = extract_id(bdest) or tr.banco_destino_id
                                    tr.valor = float(valor)
                                    tr.data_prevista = data_prev
                                    tr.foi_executada = foi
                                    tr.data_real = data_real if foi else None
                                    tr.descricao = desc
                                    _done(s, "Transferência atualizada.")
        with colD:
            if dft.empty:
                st.info("Sem transferências.")
            else:
                del_id = input_id_to_edit_delete(dft, "ID", key="trf_del_id")
                if del_id and st.button("Excluir transferência", key="trf_del_btn"):
                    with get_session() as s:
                        tr = load_obj(s, Transferencia, del_id)
                        if tr:
                            s.delete(tr)
                            _done(s, "Transferência excluída.")

# ===========================
# Relatórios
# ===========================
elif page == "Relatórios":
    st.header("Relatórios")
    filt = st.columns(4)
    ini = filt[0].date_input("Início", value=date.today().replace(day=1), key="rel_ini")
    fim = filt[1].date_input("Fim", value=date.today(), key="rel_fim")
    with get_session() as s:
        ccs = pd.read_sql("SELECT id, nome FROM centros_custo ORDER BY nome", s.bind)
    cc_opt = filt[2].selectbox("Centro de Custo", ["Geral"] + [f"{r['nome']} (# {r['id']})" for _,r in ccs.iterrows()], key="rel_cc")
    tipo_rel = filt[3].selectbox("Tipo", ["Fluxo Previsto","Fluxo Realizado","Previsto x Realizado","Extrato"], key="rel_tipo")
    cc_id = None if cc_opt=="Geral" else extract_id(cc_opt)

    if st.button("Gerar", key="rel_gerar"):
        base_where = f"date(data_prevista) BETWEEN date('{ini}') AND date('{fim}')"
        if tipo_rel in ("Fluxo Previsto","Previsto x Realizado"):
            df_prev = df_query(f"""
                SELECT data_prevista AS data, SUM(CASE WHEN tipo='Entrada' THEN valor ELSE -valor END) AS valor
                FROM transacoes
                WHERE {base_where} {"AND centro_custo_id="+str(cc_id) if cc_id else ""}
                GROUP BY data_prevista ORDER BY data_prevista
            """)
        if tipo_rel in ("Fluxo Realizado","Previsto x Realizado"):
            df_real = df_query(f"""
                SELECT data_real AS data, SUM(CASE WHEN tipo='Entrada' THEN valor ELSE -valor END) AS valor
                FROM transacoes
                WHERE foi_pago=1 AND data_real IS NOT NULL
                  AND date(data_real) BETWEEN date('{ini}') AND date('{fim}')
                  {"AND centro_custo_id="+str(cc_id) if cc_id else ""}
                GROUP BY data_real ORDER BY data_real
            """)
        if tipo_rel == "Extrato":
            dfx = df_query(f"""
                SELECT t.id, t.tipo, c.nome AS categoria, s2.nome AS subcategoria, t.valor,
                       t.data_prevista, t.foi_pago, t.data_real,
                       cc.nome AS centro_custo, cli.nome AS cliente, f.nome AS fornecedor, b.nome AS banco, t.descricao
                FROM transacoes t
                JOIN categorias c ON c.id=t.categoria_id
                LEFT JOIN subcategorias s2 ON s2.id=t.subcategoria_id
                LEFT JOIN centros_custo cc ON cc.id=t.centro_custo_id
                LEFT JOIN clientes cli ON cli.id=t.cliente_id
                LEFT JOIN fornecedores f ON f.id=t.fornecedor_id
                LEFT JOIN bancos b ON b.id=t.banco_id
                WHERE {base_where} {"AND t.centro_custo_id="+str(cc_id) if cc_id else ""}
                ORDER BY t.data_prevista ASC
            """)
            st.dataframe(dfx, use_container_width=True)
            if not dfx.empty:
                saldo_liq = dfx[dfx['tipo']=="Entrada"]["valor"].sum() - dfx[dfx['tipo']=="Saida"]["valor"].sum()
                st.metric("Saldo líquido no período", money(saldo_liq))
            else:
                st.info("Sem dados no período.")
        elif tipo_rel in ("Fluxo Previsto","Fluxo Realizado"):
            df_show = df_prev if tipo_rel=="Fluxo Previsto" else df_real
            if df_show.empty:
                st.info("Sem dados para o período.")
            else:
                st.dataframe(df_show, use_container_width=True)
                fig = px.bar(df_show, x="data", y="valor", title=tipo_rel)
                st.plotly_chart(fig, use_container_width=True)
        elif tipo_rel == "Previsto x Realizado":
            has_prev = ('df_prev' in locals()) and not df_prev.empty
            has_real = ('df_real' in locals()) and not df_real.empty
            if has_prev or has_real:
                if has_prev: df_prev["serie"] = "Previsto"
                if has_real: df_real["serie"] = "Realizado"
                comp = pd.concat([x for x in [df_prev if has_prev else None, df_real if has_real else None] if x is not None], ignore_index=True)
                st.dataframe(comp, use_container_width=True)
                fig = px.line(comp, x="data", y="valor", color="serie", markers=True, title="Previsto x Realizado")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem dados para o período.")

# ===========================
# Dashboards
# ===========================
elif page == "Dashboards":
    st.header("Dashboards")

    # Top categorias (realizado)
    dfc = df_query("""
        SELECT c.tipo, c.nome AS categoria, SUM(t.valor) AS valor
        FROM transacoes t JOIN categorias c ON c.id=t.categoria_id
        WHERE t.foi_pago=1 AND t.data_real IS NOT NULL
        GROUP BY c.tipo, c.nome
        ORDER BY 1, 3 DESC
    """)
    if dfc.empty:
        st.info("Sem realizados ainda.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            fig1 = px.bar(dfc[dfc["tipo"]=="Entrada"], x="categoria", y="valor", title="Top Entradas por Categoria")
            st.plotly_chart(fig1, use_container_width=True)
        with col2:
            fig2 = px.bar(dfc[dfc["tipo"]=="Saida"], x="categoria", y="valor", title="Top Saídas por Categoria")
            st.plotly_chart(fig2, use_container_width=True)

    # Curva de caixa (acumulado real por data)
    dfd = df_query("""
        SELECT date(data_real) AS data, SUM(CASE WHEN tipo='Entrada' THEN valor ELSE -valor END) AS delta
        FROM transacoes WHERE foi_pago=1 AND data_real IS NOT NULL
        GROUP BY date(data_real) ORDER BY date(data_real)
    """)
    if not dfd.empty:
        dfd["saldo"] = dfd["delta"].cumsum()
        fig3 = px.line(dfd, x="data", y="saldo", title="Saldo acumulado (real)")
        st.plotly_chart(fig3, use_container_width=True)

    # Saldos por banco (pizza)
    dfb = compute_bank_balances()
    if not dfb.empty:
        fig4 = px.pie(dfb, names="nome", values="saldo_atual", title="Distribuição de saldos por banco")
        st.plotly_chart(fig4, use_container_width=True)

