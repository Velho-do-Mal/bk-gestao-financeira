# -*- coding: utf-8 -*-
# BK Engenharia e Tecnologia — App de Gestão Financeira (arquivo único)
# Python: 3.13 | Streamlit + SQLAlchemy | SQLite/Cloud
from __future__ import annotations

import plotly.express as px
import os, io, re
from datetime import date, datetime, timedelta
import warnings
warnings.filterwarnings("ignore", message="The keyword arguments have been deprecated")
from dateutil.relativedelta import relativedelta
from typing import Optional
import pandas as pd

import streamlit as st
from sqlalchemy import create_engine
import os

# Caminho absoluto para o banco no OneDrive
caminho_banco = r"C:\Users\marci\OneDrive - Barabach & Knopp Engenharia e Tecnologia\4. Desenvolvimento de Tecnologia\BANCO DE DADOS\GESTÃO FINANCEIRA\bk_finance.db"

# Garante que o caminho existe
if not os.path.exists(os.path.dirname(caminho_banco)):
    os.makedirs(os.path.dirname(caminho_banco), exist_ok=True)

# Cria o engine SQLite apontando para o OneDrive
DATABASE_URL = f"sqlite:///{caminho_banco}"
ENGINE = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# ===========================
# Configurações Gerais
# ===========================
APP_TITLE = "BK Gestão Financeira"
APP_VERSION = "v1.8"

# 1) DB_URL por env ou secrets (se usar secrets.toml, seção [general])
DB_URL = (
    os.environ.get("DATABASE_URL")
    or (st.secrets.get("general", {}).get("database_url") if hasattr(st, "secrets") else None)
)

# 2) Fallback local: ./data/bk_finance.db
if not DB_URL:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    LOCAL_DB_DIR = os.path.join(BASE_DIR, "data")
    os.makedirs(LOCAL_DB_DIR, exist_ok=True)
    DB_URL = f"sqlite:///{os.path.join(LOCAL_DB_DIR, 'bk_finance.db')}"

# 3) Engine e Session
ENGINE = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)
Base = declarative_base()

# 4) Pasta de anexos
ATTACH_DIR = (
    os.environ.get("ATTACH_DIR")
    or (st.secrets.get("general", {}).get("attach_dir") if hasattr(st, "secrets") else None)
    or os.path.join(os.path.abspath(os.path.dirname(__file__)), "anexos")
)
os.makedirs(ATTACH_DIR, exist_ok=True)

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

# helper commit + limpar cache + rerun
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
st.set_page_config(page_title=APP_TITLE, page_icon="💼", layout="wide", initial_sidebar_state="expanded")

@st.cache_data(show_spinner=False)
def df_query_cached(sql: str) -> pd.DataFrame:
    return df_query(sql)

def success(msg: str): st.toast(msg, icon="✅")
def error(msg: str): st.toast(msg, icon="❌")

ensure_seed_data()

with st.sidebar:
    st.title("💼 BK Gestão Financeira")
    st.caption(APP_VERSION)
    page = st.radio("Navegação", ["Home","Cadastro","Metas","Movimentações","Relatórios","Dashboards"], index=0, key="nav_page")
    st.divider()
    st.markdown("**Banco de Dados (URL/arquivo)**")
    st.code(DB_URL, language="bash")

st.markdown("""
<style>
.stButton>button {border-radius: 12px; padding: .6rem 1rem;}
.stTextInput>div>div>input, .stNumberInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] {border-radius: 10px;}
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
                            s.delete(obj); _done(s, "Cliente excluído.")

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
                            s.delete(obj); _done(s, "Fornecedor excluído.")

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
                            s.delete(obj); _done(s, "Banco excluído.")

    # ---------- Categorias ----------
    with tabs[3]:
        st.subheader("Categorias — Incluir")
        with st.form("form_cat_add", clear_on_submit=True):
            c1,c2 = st.columns(2)
            tipo = c1.selectbox("Tipo", ["Entrada","Saida"], key="cat_add_tipo")
            # Nome com lista suspensa vinculada ao tipo (nomes existentes aparecem para facilitar padronização)
            with get_session() as s:
                nomes_exist = pd.read_sql("SELECT DISTINCT nome FROM categorias WHERE tipo=:t ORDER BY nome", s.bind, params={"t": tipo})
            sugestoes = nomes_exist["nome"].tolist() if not nomes_exist.empty else []
            nome = c2.selectbox("Nome da categoria", options=(["- digite novo -"] + sugestoes), key="cat_add_nome_sel")
            if nome == "- digite novo -":
                nome = c2.text_input("Novo nome", key="cat_add_nome_txt")
            if st.form_submit_button("Adicionar Categoria") and (nome or "").strip():
                with get_session() as s:
                    s.add(Categoria(tipo=tipo, nome=nome.strip()))
                    _done(s, "Categoria cadastrada.")
        df_c = df_query_cached("SELECT id, tipo, nome FROM categorias ORDER BY tipo, nome")
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
                                nomes_exist = pd.read_sql("SELECT DISTINCT nome FROM categorias WHERE tipo=:t ORDER BY nome", s.bind, params={"t": tipo})
                                sugestoes = nomes_exist["nome"].tolist() if not nomes_exist.empty else []
                                cur = obj.nome if obj.nome not in sugestoes else None
                                nome = c2.selectbox("Nome", options=(sugestoes + (["- digite novo -"] if cur or not sugestoes else [])), index=(sugestoes.index(obj.nome) if obj.nome in sugestoes else len(sugestoes)), key="cat_edit_nome_sel")
                                if nome == "- digite novo -" or cur:
                                    nome = c2.text_input("Novo nome", value=(cur or ""), key="cat_edit_nome_txt")
                                if st.form_submit_button("Salvar alterações"):
                                    obj.tipo, obj.nome = tipo, nome.strip()
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
                            s.delete(obj); _done(s, "Categoria excluída.")

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
                # seleção por tipo primeiro
                tipo_sel = c1.selectbox("Tipo", ["Entrada", "Saida"], key="sub_add_tipo")
                cats_tipo = cats[cats["tipo"] == tipo_sel]
                cat_opt = c1.selectbox("Categoria", [f"{r['tipo']} - {r['nome']} (# {r['id']})" for _,r in cats_tipo.iterrows()], key="sub_add_cat")
                # Nome com sugestões (vinculado à categoria escolhida)
                with get_session() as s:
                    nomes_exist = pd.read_sql("SELECT DISTINCT nome FROM subcategorias WHERE categoria_id=:c ORDER BY nome", s.bind, params={"c": extract_id(cat_opt)})
                sugestoes = nomes_exist["nome"].tolist() if not nomes_exist.empty else []
                nome_sel = c2.selectbox("Nome da subcategoria", ["- digite novo -"] + sugestoes, key="sub_add_nome_sel")
                nome = c2.text_input("Novo nome", key="sub_add_nome_txt") if nome_sel == "- digite novo -" else nome_sel
                if st.form_submit_button("Adicionar Subcategoria") and (nome or "").strip():
                    cat_id = extract_id(cat_opt)
                    with get_session() as s:
                        s.add(Subcategoria(categoria_id=cat_id, nome=nome.strip()))
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
                                # tipo primeiro
                                tipo_sel = c1.selectbox("Tipo", ["Entrada","Saida"], index=0 if s.get(Categoria, obj.categoria_id).tipo=="Entrada" else 1, key="sub_edit_tipo")
                                cats_tipo = cats[cats["tipo"] == tipo_sel]
                                # categoria da mesma linha como primeira opção
                                cat_obj = s.get(Categoria, obj.categoria_id)
                                cat_label_cur = f"{cat_obj.tipo} - {cat_obj.nome} (# {cat_obj.id})" if cat_obj else "-"
                                opts = [cat_label_cur] + [f"{r['tipo']} - {r['nome']} (# {r['id']})" for _,r in cats_tipo.iterrows() if f"{r['tipo']} - {r['nome']} (# {r['id']})" != cat_label_cur]
                                escolha = c1.selectbox("Categoria", opts, key="sub_edit_cat")
                                # nome com sugestões vinculadas à categoria escolhida
                                new_cat_id = extract_id(escolha) or obj.categoria_id
                                nomes_exist = pd.read_sql("SELECT DISTINCT nome FROM subcategorias WHERE categoria_id=:c ORDER BY nome", s.bind, params={"c": new_cat_id})
                                sugestoes = nomes_exist["nome"].tolist() if not nomes_exist.empty else []
                                nome_sel = c2.selectbox("Nome", (sugestoes + ["- digite novo -"]), index=(sugestoes.index(obj.nome) if obj.nome in sugestoes else len(sugestoes)), key="sub_edit_nome_sel")
                                nome = c2.text_input("Novo nome", value=(obj.nome if nome_sel=="- digite novo -" else ""), key="sub_edit_nome_txt") if nome_sel=="- digite novo -" else nome_sel
                                if st.form_submit_button("Salvar alterações"):
                                    obj.categoria_id = new_cat_id
                                    obj.nome = nome.strip()
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
                            s.delete(obj); _done(s, "Subcategoria excluída.")

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
        df_cc = df_query_cached("SELECT id, nome, descricao FROM centros_custo ORDER BY nome")
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
                            s.delete(obj); _done(s, "Centro de custo excluído.")

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
                        s.delete(obj); _done(s, "Meta excluída.")

# ===========================
# Movimentações
# ===========================
elif page == "Movimentações":
    st.header("Movimentações")
    tabs = st.tabs(["Lançamentos", "Transferências entre bancos"])

    # --------- Lançamentos (ADD) ---------
    with tabs[0]:

                # -------- DADOS AUXILIARES --------
        with get_session() as s:
            df_cat_all = pd.read_sql("SELECT id, tipo, nome FROM categorias ORDER BY tipo, nome", s.bind)
            df_sub_all = pd.read_sql("SELECT id, categoria_id, nome FROM subcategorias ORDER BY nome", s.bind)
            df_cc_all  = pd.read_sql("SELECT id, nome FROM centros_custo ORDER BY nome", s.bind)
            df_cli_all = pd.read_sql("SELECT id, nome FROM clientes ORDER BY nome", s.bind)
            df_forn_all= pd.read_sql("SELECT id, nome FROM fornecedores ORDER BY nome", s.bind)
            df_bco_all = pd.read_sql("SELECT id, nome FROM bancos ORDER BY nome", s.bind)

        # =========================
        # Incluir Lançamento
        # =========================
        st.subheader("Incluir Lançamento")
        with st.form("form_tx_add", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)

            tipo_add = c1.selectbox("Tipo", ["Entrada", "Saida"], key="tx_add_tipo")
            # categorias só do tipo escolhido
            cat_rows = df_cat_all[df_cat_all["tipo"] == tipo_add]
            cat_opts = [f"{r['tipo']} - {r['nome']} (# {r['id']})" for _, r in cat_rows.iterrows()]
            cat_add  = c2.selectbox("Categoria", cat_opts, placeholder="Selecione", key="tx_add_cat")

            # subcategorias daquela categoria
            cat_id_add = extract_id(cat_add) if cat_add else None
            sub_rows = df_sub_all[df_sub_all["categoria_id"] == (cat_id_add or -1)]
            sub_opts = ["-"] + [f"{r['nome']} (# {r['id']})" for _, r in sub_rows.iterrows()]
            sub_add  = c3.selectbox("Subcategoria", sub_opts, key="tx_add_sub")

            valor_add = c4.number_input("Valor (R$)", min_value=0.0, step=100.0, format="%.2f", key="tx_add_valor")

            d1, d2, d3, d4 = st.columns(4)
            data_prev_add = d1.date_input("Data Prevista", value=date.today(), key="tx_add_data_prev")
            pago_add      = d2.checkbox("Pago?", key="tx_add_pago")
            data_real_add = d3.date_input("Data Real", value=date.today(), key="tx_add_data_real") if pago_add else None
            bco_opts = ["-"] + [f"{r['nome']} (# {r['id']})" for _, r in df_bco_all.iterrows()]
            bco_add  = d4.selectbox("Banco", bco_opts, key="tx_add_banco")

            e1, e2, e3 = st.columns(3)
            cc_opts   = ["-"] + [f"{r['nome']} (# {r['id']})" for _, r in df_cc_all.iterrows()]
            cc_add    = e1.selectbox("Centro de Custo", cc_opts, key="tx_add_cc")
            cli_opts  = ["-"] + [f"{r['nome']} (# {r['id']})" for _, r in df_cli_all.iterrows()]
            forn_opts = ["-"] + [f"{r['nome']} (# {r['id']})" for _, r in df_forn_all.iterrows()]
            cli_add   = e2.selectbox("Cliente (Entrada)", cli_opts, key="tx_add_cli")
            forn_add  = e3.selectbox("Fornecedor (Saída)", forn_opts, key="tx_add_forn")

            desc_add = st.text_area("Descrição", key="tx_add_desc")

            st.markdown("**Recorrência**")
            r1, r2, r3 = st.columns(3)
            recorr_add = r1.selectbox("Tipo", ["Unica", "Mensal", "Anual", "Parcelado"], key="tx_add_rec")
            parcelas_total_add = None
            periodicidade_add = "Mensal"
            if recorr_add == "Parcelado":
                parcelas_total_add = r2.number_input("Nº de parcelas", min_value=1, max_value=120, value=2, key="tx_add_parc_n")
                periodicidade_add = r3.selectbox("Periodicidade", ["Mensal", "Anual"], key="tx_add_parc_per")

            # --- SUBMIT ---
            if st.form_submit_button("Lançar"):
                if not cat_id_add:
                    error("Selecione a categoria."); st.stop()

                with get_session() as s:
                    def add_tx(idx: Optional[int], dt: date):
                        t = Transacao(
                            tipo=tipo_add,
                            categoria_id=cat_id_add,
                            subcategoria_id=extract_id(sub_add) if sub_add and sub_add != "-" else None,
                            valor=float(valor_add or 0),
                            data_prevista=dt,
                            foi_pago=bool(pago_add),
                            data_real=(data_real_add if pago_add else None),
                            centro_custo_id=extract_id(cc_add) if cc_add and cc_add != "-" else None,
                            cliente_id=extract_id(cli_add) if (tipo_add == "Entrada" and cli_add != "-") else None,
                            fornecedor_id=extract_id(forn_add) if (tipo_add == "Saida" and forn_add != "-") else None,
                            banco_id=extract_id(bco_add) if bco_add and bco_add != "-" else None,
                            descricao=desc_add or "",
                            recorrencia=recorr_add,
                            parcelas_total=int(parcelas_total_add) if parcelas_total_add else None,
                            parcela_index=idx if parcelas_total_add else None,
                        )
                        s.add(t)

                    if recorr_add == "Unica":
                        add_tx(None, data_prev_add)

                    elif recorr_add in ("Mensal", "Anual"):
                        # 12 meses / 5 anos como exemplo de planejamento
                        steps = 12 if recorr_add == "Mensal" else 5
                        for i in range(steps):
                            dt = data_prev_add + (relativedelta(months=i) if recorr_add == "Mensal" else relativedelta(years=i))
                            add_tx(None, dt)

                    elif recorr_add == "Parcelado":
                        total = int(parcelas_total_add or 1)
                        for i in range(1, total + 1):
                            dt = data_prev_add + (relativedelta(months=i - 1) if periodicidade_add == "Mensal" else relativedelta(years=i - 1))
                            add_tx(i, dt)

                    _done(s, "Movimentação(ões) lançada(s).")

        # =========================
        # Lista + Editar / Excluir
        # =========================
        st.subheader("Lançamentos — Lista")
        with get_session() as s:
            df_tx = pd.read_sql(
                """
                SELECT t.id, t.tipo, c.nome AS categoria, s2.nome AS subcategoria, t.valor,
                       t.data_prevista, t.foi_pago, t.data_real,
                       cc.nome AS centro_custo, cli.nome AS cliente, f.nome AS fornecedor, b.nome AS banco, t.descricao
                FROM transacoes t
                JOIN categorias c ON c.id = t.categoria_id
                LEFT JOIN subcategorias s2 ON s2.id = t.subcategoria_id
                LEFT JOIN centros_custo cc ON cc.id = t.centro_custo_id
                LEFT JOIN clientes cli ON cli.id = t.cliente_id
                LEFT JOIN fornecedores f ON f.id = t.fornecedor_id
                LEFT JOIN bancos b ON b.id = t.banco_id
                ORDER BY t.data_prevista DESC, t.id DESC
                """,
                s.bind,
            )
        st.dataframe(df_tx, use_container_width=True)

        colE, colD = st.columns(2)

        # ---------- Editar ----------
        with colE:
            st.markdown("**Editar Lançamento**")
            if df_tx.empty:
                st.info("Sem lançamentos.")
            else:
                edit_id = input_id_to_edit_delete(df_tx, "ID", key="tx_edit_id")
                if edit_id:
                    with get_session() as s:
                        t = load_obj(s, Transacao, edit_id)
                        if t:
                            with st.form("form_tx_edit"):
                                c1, c2, c3, c4 = st.columns(4)
                                tipo_ed = c1.selectbox("Tipo", ["Entrada", "Saida"], index=0 if t.tipo == "Entrada" else 1, key="tx_edit_tipo")

                                # categorias do tipo escolhido
                                df_cat_typ = pd.read_sql(
                                    "SELECT id, tipo, nome FROM categorias WHERE tipo=:tp ORDER BY nome",
                                    s.bind,
                                    params={"tp": tipo_ed},
                                )
                                # label atual
                                cat_cur = s.get(Categoria, t.categoria_id)
                                cat_label_cur = f"{cat_cur.tipo} - {cat_cur.nome} (# {cat_cur.id})" if cat_cur else "-"
                                cat_opts_ed = [cat_label_cur] + [f"{r['tipo']} - {r['nome']} (# {r['id']})" for _, r in df_cat_typ.iterrows() if f"{r['tipo']} - {r['nome']} (# {r['id']})" != cat_label_cur]
                                cat_ed = c2.selectbox("Categoria", cat_opts_ed, key="tx_edit_cat")

                                # subcategorias conforme categoria escolhida (ou atual)
                                cat_id_sel = extract_id(cat_ed) or t.categoria_id
                                df_sub_typ = pd.read_sql(
                                    "SELECT id, nome FROM subcategorias WHERE categoria_id=:c ORDER BY nome",
                                    s.bind,
                                    params={"c": cat_id_sel},
                                )
                                sub_label_cur = "-"
                                if t.subcategoria_id:
                                    sc = s.get(Subcategoria, t.subcategoria_id)
                                    if sc:
                                        sub_label_cur = f"{sc.nome} (# {sc.id})"
                                sub_opts_ed = ["-"] + ([sub_label_cur] if sub_label_cur != "-" else []) + [f"{r['nome']} (# {r['id']})" for _, r in df_sub_typ.iterrows() if f"{r['nome']} (# {r['id']})" != sub_label_cur]
                                sub_ed = c3.selectbox("Subcategoria", sub_opts_ed, key="tx_edit_sub")

                                valor_ed = c4.number_input("Valor (R$)", min_value=0.0, step=100.0, format="%.2f", value=float(t.valor or 0), key="tx_edit_valor")

                                d1, d2, d3, d4 = st.columns(4)
                                data_prev_ed = d1.date_input("Data Prevista", value=t.data_prevista, key="tx_edit_data_prev")
                                pago_ed      = d2.checkbox("Pago?", value=bool(t.foi_pago), key="tx_edit_pago")
                                data_real_ed = d3.date_input("Data Real", value=t.data_real or date.today(), key="tx_edit_data_real") if pago_ed else None

                                # banco
                                df_bco = pd.read_sql("SELECT id, nome FROM bancos ORDER BY nome", s.bind)
                                bco_label_cur = "-"
                                if t.banco_id:
                                    bco_cur = s.get(Banco, t.banco_id)
                                    if bco_cur:
                                        bco_label_cur = f"{bco_cur.nome} (# {bco_cur.id})"
                                bco_opts_ed = [bco_label_cur] + [f"{r['nome']} (# {r['id']})" for _, r in df_bco.iterrows() if f"{r['nome']} (# {r['id']})" != bco_label_cur]
                                bco_ed = d4.selectbox("Banco", bco_opts_ed, key="tx_edit_banco")

                                e1, e2, e3 = st.columns(3)
                                # CC
                                df_cc = pd.read_sql("SELECT id, nome FROM centros_custo ORDER BY nome", s.bind)
                                cc_label_cur = "-"
                                if t.centro_custo_id:
                                    cc_cur = s.get(CentroCusto, t.centro_custo_id)
                                    if cc_cur:
                                        cc_label_cur = f"{cc_cur.nome} (# {cc_cur.id})"
                                cc_opts_ed = [cc_label_cur] + [f"{r['nome']} (# {r['id']})" for _, r in df_cc.iterrows() if f"{r['nome']} (# {r['id']})" != cc_label_cur]
                                cc_ed = e1.selectbox("Centro de Custo", cc_opts_ed, key="tx_edit_cc")

                                # cliente / fornecedor
                                df_cli = pd.read_sql("SELECT id, nome FROM clientes ORDER BY nome", s.bind)
                                cli_label_cur = "-"
                                if t.cliente_id:
                                    cli_cur = s.get(Cliente, t.cliente_id)
                                    if cli_cur:
                                        cli_label_cur = f"{cli_cur.nome} (# {cli_cur.id})"
                                cli_opts_ed = [cli_label_cur] + [f"{r['nome']} (# {r['id']})" for _, r in df_cli.iterrows() if f"{r['nome']} (# {r['id']})" != cli_label_cur]
                                cli_ed = e2.selectbox("Cliente (Entrada)", cli_opts_ed, key="tx_edit_cli")

                                df_forn = pd.read_sql("SELECT id, nome FROM fornecedores ORDER BY nome", s.bind)
                                forn_label_cur = "-"
                                if t.fornecedor_id:
                                    f_cur = s.get(Fornecedor, t.fornecedor_id)
                                    if f_cur:
                                        forn_label_cur = f"{f_cur.nome} (# {f_cur.id})"
                                forn_opts_ed = [forn_label_cur] + [f"{r['nome']} (# {r['id']})" for _, r in df_forn.iterrows() if f"{r['nome']} (# {r['id']})" != forn_label_cur]
                                forn_ed = e3.selectbox("Fornecedor (Saída)", forn_opts_ed, key="tx_edit_forn")

                                desc_ed = st.text_area("Descrição", t.descricao or "", key="tx_edit_desc")

                                if st.form_submit_button("Salvar alterações"):
                                    t.tipo = tipo_ed
                                    t.categoria_id = extract_id(cat_ed) or t.categoria_id
                                    t.subcategoria_id = extract_id(sub_ed) if sub_ed and sub_ed != "-" else None
                                    t.valor = float(valor_ed)
                                    t.data_prevista = data_prev_ed
                                    t.foi_pago = bool(pago_ed)
                                    t.data_real = (data_real_ed if pago_ed else None)
                                    t.banco_id = extract_id(bco_ed) if bco_ed and bco_ed != "-" else None
                                    t.centro_custo_id = extract_id(cc_ed) if cc_ed and cc_ed != "-" else None
                                    t.cliente_id = extract_id(cli_ed) if cli_ed and cli_ed != "-" else None
                                    t.fornecedor_id = extract_id(forn_ed) if forn_ed and forn_ed != "-" else None
                                    t.descricao = desc_ed
                                    _done(s, "Lançamento atualizado.")

        # ---------- Excluir ----------
        with colD:
            st.markdown("**Excluir Lançamento**")
            if df_tx.empty:
                st.info("Sem lançamentos.")
            else:
                del_id = input_id_to_edit_delete(df_tx, "ID", key="tx_del_id")
                if del_id and st.button("Excluir lançamento", key="tx_del_btn"):
                    with get_session() as s:
                        t = load_obj(s, Transacao, del_id)
                        if t:
                            s.delete(t)
                            _done(s, "Lançamento excluído.")

        # =========================
        # Anexos / Recibo
        # =========================
        st.subheader("Anexos e Recibos")
        colA, colB = st.columns([2, 1])
        with colA:
            trans_id = st.number_input("ID da transação", min_value=1, step=1, value=1, key="anx_tx_id")
            up = st.file_uploader(
                "Anexar arquivo",
                type=["pdf", "png", "jpg", "jpeg", "xlsx", "csv", "docx", "zip"],
                accept_multiple_files=True,
                key="anx_uploader",
            )
            if st.button("Salvar Anexo(s)", key="anx_save"):
                with get_session() as s:
                    if not s.get(Transacao, int(trans_id)):
                        error("Transação não encontrada.")
                    else:
                        for f in up or []:
                            fname = f"T{int(trans_id)}_{int(datetime.utcnow().timestamp())}_{f.name}"
                            fpath = os.path.join(ATTACH_DIR, fname)
                            with open(fpath, "wb") as fh:
                                fh.write(f.getbuffer())
                            s.add(Anexo(transacao_id=int(trans_id), filename=fname, path=fpath))
                        _done(s, "Anexos salvos.")
        with colB:
            if st.button("Gerar Recibo (PDF)", key="recibo_btn"):
                with get_session() as s:
                    t = s.get(Transacao, int(trans_id))
                    if not t:
                        error("Transação não encontrada.")
                    else:
                        pdf_bytes = make_recibo_pdf(t, s)
                        fname = f"RECIBO_T{t.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
                        fpath = os.path.join(ATTACH_DIR, fname)
                        with open(fpath, "wb") as f:
                            f.write(pdf_bytes)
                        success(f"Recibo salvo em {fpath}")
                        st.download_button("Baixar Recibo", data=pdf_bytes, file_name=fname, mime="application/pdf", key="recibo_download")

    # --------- Transferências ---------
    with tabs[1]:
        st.caption("Transferências movem saldos entre bancos (não afetam resultado).")
        with get_session() as s:
            df_bancos = pd.read_sql("SELECT id, nome FROM bancos ORDER BY nome", s.bind)

        st.subheader("Incluir Transferência")
        with st.form("form_trf_add", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            b_origem = c1.selectbox("Banco origem", [f"{r['nome']} (# {r['id']})" for _, r in df_bancos.iterrows()] if not df_bancos.empty else [], key="trf_add_origem")
            b_dest   = c2.selectbox("Banco destino", [f"{r['nome']} (# {r['id']})" for _, r in df_bancos.iterrows()] if not df_bancos.empty else [], key="trf_add_dest")
            valor    = c3.number_input("Valor (R$)", min_value=0.0, step=100.0, format="%.2f", key="trf_add_valor")
            data_prev= c4.date_input("Data prevista", value=date.today(), key="trf_add_data")
            desc     = st.text_input("Descrição (opcional)", key="trf_add_desc")
            if st.form_submit_button("Cadastrar Transferência", key="trf_add_submit") and b_origem and b_dest and valor > 0:
                o_id = extract_id(b_origem); d_id = extract_id(b_dest)
                if not o_id or not d_id:
                    error("Selecione origem e destino válidos.")
                elif o_id == d_id:
                    error("Origem e destino não podem ser iguais.")
                else:
                    with get_session() as s:
                        s.add(Transferencia(banco_origem_id=o_id, banco_destino_id=d_id, valor=float(valor), data_prevista=data_prev, descricao=desc))
                        _done(s, "Transferência cadastrada.")

        st.subheader("Lista de Transferências")
        with get_session() as s:
            dft = pd.read_sql(
                """
                SELECT t.id, b1.nome AS origem, b2.nome AS destino, t.valor, t.data_prevista,
                       t.foi_executada, t.data_real, t.descricao
                FROM transferencias t
                JOIN bancos b1 ON b1.id = t.banco_origem_id
                JOIN bancos b2 ON b2.id = t.banco_destino_id
                ORDER BY t.data_prevista DESC, t.id DESC
                """,
                s.bind,
            )
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
                        df_bancos = pd.read_sql("SELECT id, nome FROM bancos ORDER BY nome", s.bind)
                        if tr:
                            with st.form("form_trf_edit"):
                                c1, c2, c3, c4 = st.columns(4)
                                borig_cur = s.get(Banco, tr.banco_origem_id)
                                bdest_cur = s.get(Banco, tr.banco_destino_id)
                                borig = c1.selectbox("Origem", ([f"{borig_cur.nome} (# {tr.banco_origem_id})"] if borig_cur else []) + [f"{r['nome']} (# {r['id']})" for _, r in df_bancos.iterrows()], key="trf_edit_origem")
                                bdest = c2.selectbox("Destino", ([f"{bdest_cur.nome} (# {tr.banco_destino_id})"] if bdest_cur else []) + [f"{r['nome']} (# {r['id']})" for _, r in df_bancos.iterrows()], key="trf_edit_dest")
                                valor = c3.number_input("Valor", min_value=0.0, step=100.0, format="%.2f", value=float(tr.valor), key="trf_edit_valor")
                                data_prev = c4.date_input("Data prevista", value=tr.data_prevista, key="trf_edit_data")
                                foi = st.checkbox("Executada?", value=bool(tr.foi_executada), key="trf_edit_exec")
                                data_real = st.date_input("Data real", value=tr.data_real or date.today(), key="trf_edit_data_real") if foi else None
                                desc = st.text_input("Descrição", value=tr.descricao or "", key="trf_edit_desc")
                                if st.form_submit_button("Salvar alterações", key="trf_edit_save"):
                                    tr.banco_origem_id = extract_id(borig) or tr.banco_origem_id
                                    tr.banco_destino_id = extract_id(bdest) or tr.banco_destino_id
                                    tr.valor = float(valor); tr.data_prevista = data_prev
                                    tr.foi_executada = foi; tr.data_real = (data_real if foi else None)
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

    f1, f2, f3 = st.columns(3)
    tipo_filtro = f1.selectbox("Tipo", ["Entradas e Saídas", "Entradas", "Saídas"], index=0, key="rel_tipo")
    dt_ini = f2.date_input("De", value=date.today().replace(day=1), key="rel_de")
    dt_fim = f3.date_input("Até", value=date.today(), key="rel_ate")

    tipo_sql = ""
    if tipo_filtro == "Entradas":
        tipo_sql = "AND t.tipo='Entrada'"
    elif tipo_filtro == "Saídas":
        tipo_sql = "AND t.tipo='Saida'"

    with get_session() as s:
        df_rel = pd.read_sql(
            f"""
            SELECT t.id, t.tipo, c.nome AS categoria, s2.nome AS subcategoria, t.valor,
                   t.data_prevista, t.foi_pago, t.data_real, b.nome AS banco, t.descricao
            FROM transacoes t
            JOIN categorias c ON c.id=t.categoria_id
            LEFT JOIN subcategorias s2 ON s2.id=t.subcategoria_id
            LEFT JOIN bancos b ON b.id=t.banco_id
            WHERE date(t.data_prevista) BETWEEN :d1 AND :d2
            {tipo_sql}
            ORDER BY t.data_prevista ASC, t.id ASC
            """,
            s.bind,
            params={"d1": dt_ini.isoformat(), "d2": dt_fim.isoformat()},
        )

    st.dataframe(df_rel, use_container_width=True)
    colT1, colT2, colT3 = st.columns(3)
    tot_e = df_rel.loc[df_rel["tipo"] == "Entrada", "valor"].sum()
    tot_s = df_rel.loc[df_rel["tipo"] == "Saida", "valor"].sum()
    with colT1: st.metric("Total Entradas", money(tot_e))
    with colT2: st.metric("Total Saídas", money(tot_s))
    with colT3: st.metric("Resultado", money(tot_e - tot_s))

    if not df_rel.empty:
        csv = df_rel.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Exportar CSV", data=csv, file_name="relatorio.csv", mime="text/csv")

# ===========================
# Painéis / Dashboards
# ===========================
elif page in ("Painéis", "Dashboards"):
    st.header("Painéis / Dashboards")

    # Só vamos usar 'config' no st.plotly_chart (para acabar com o aviso)
    PLOTLY_CONFIG = {
        "displaylogo": False,
        "modeBarButtonsToRemove": ["zoomIn2d", "zoomOut2d", "autoScale2d"],
        "toImageButtonOptions": {"format": "png", "filename": "grafico"},
        "scrollZoom": False,
    }

    # ---------------- Filtros de período ----------------
    colf = st.columns(3)
    dt_ini = colf[0].date_input(
        "Início da análise", value=date(date.today().year, 1, 1), key="dash_ini"
    )
    dt_fim = colf[1].date_input(
        "Fim da análise", value=date.today(), key="dash_fim"
    )
    colf[2].markdown("O **acumulado** começa exatamente na data de *Início da análise*.")

    if dt_ini > dt_fim:
        st.warning("Período inválido (início > fim). Ajustei automaticamente.")
        dt_ini, dt_fim = dt_fim, dt_ini

    # ---------------- Carregar dados ----------------
    with get_session() as s:
        # Realizado (pagos) no período -> usa data_real
        df_real = pd.read_sql(
            """
            SELECT t.id, t.tipo, t.valor,
                   t.data_prevista, t.foi_pago, t.data_real,
                   c.nome AS categoria, cc.nome AS centro_custo
            FROM transacoes t
            JOIN categorias c ON c.id = t.categoria_id
            LEFT JOIN centros_custo cc ON cc.id = t.centro_custo_id
            WHERE t.foi_pago = 1
              AND date(t.data_real) BETWEEN :ini AND :fim
            """,
            s.bind, params={"ini": dt_ini.isoformat(), "fim": dt_fim.isoformat()}
        )

        # Previsto (não pagos) no período -> usa data_prevista
        df_prev = pd.read_sql(
            """
            SELECT t.id, t.tipo, t.valor,
                   t.data_prevista, t.foi_pago, t.data_real,
                   c.nome AS categoria, cc.nome AS centro_custo
            FROM transacoes t
            JOIN categorias c ON c.id = t.categoria_id
            LEFT JOIN centros_custo cc ON cc.id = t.centro_custo_id
            WHERE t.foi_pago = 0
              AND date(t.data_prevista) BETWEEN :ini AND :fim
            """,
            s.bind, params={"ini": dt_ini.isoformat(), "fim": dt_fim.isoformat()}
        )

    st.divider()

    # ============================================================
    # 1) Fluxo mensal (Realizado) — Entradas x Saídas (colunas)
    # ============================================================
    st.subheader("Fluxo mensal (Realizado) — Entradas x Saídas")
    if not df_real.empty:
        dfm = df_real.copy()
        dfm["Mês"] = pd.to_datetime(dfm["data_real"]).dt.to_period("M").astype(str)
        g = (
            dfm.groupby(["Mês", "tipo"], as_index=False)["valor"]
            .sum()
            .pivot(index="Mês", columns="tipo", values="valor")
            .fillna(0.0)
            .reset_index()
        )
        if "Entrada" not in g.columns: g["Entrada"] = 0.0
        if "Saida"   not in g.columns: g["Saida"]   = 0.0

        fig1 = px.bar(
            g,
            x="Mês",
            y=["Entrada", "Saida"],
            barmode="group",
            title=(
                f"Entradas x Saídas (Realizado) por mês — "
                f"{dt_ini.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
            ),
            template="plotly_white",
        )
        fig1.update_layout(
            legend_title_text="",
            margin=dict(l=10, r=10, t=50, b=10),
            yaxis_title="R$",
        )
        st.plotly_chart(fig1, config=PLOTLY_CONFIG)
    else:
        st.info("Sem movimentos **realizados** no período para montar o fluxo mensal.")

    st.divider()

    # ===========================================
    # 2) Fluxo de Caixa — Saldo Acumulado (linha)
    # ===========================================
    st.subheader("Fluxo de Caixa — Saldo Acumulado (Realizado)")
    if not df_real.empty:
        acc = df_real.copy()
        acc["dia"] = pd.to_datetime(acc["data_real"]).dt.date
        acc["var"] = acc.apply(lambda r: r["valor"] if r["tipo"] == "Entrada" else -r["valor"], axis=1)

        daily = acc.groupby("dia", as_index=False)["var"].sum().sort_values("dia")
        # Linha contínua (preenche dias sem movimento)
        idx = pd.date_range(start=dt_ini, end=dt_fim, freq="D")
        daily = (
            daily.set_index("dia")
            .reindex(idx, fill_value=0.0)
            .rename_axis("dia").reset_index()
        )
        daily["acumulado"] = daily["var"].cumsum()
        daily["dia"] = pd.to_datetime(daily["dia"]).dt.date

        fig2 = px.line(
            daily,
            x="dia", y="acumulado",
            markers=True,
            title=f"Saldo acumulado (de {dt_ini.strftime('%d/%m/%Y')} até {dt_fim.strftime('%d/%m/%Y')})",
            template="plotly_white",
        )
        fig2.update_layout(
            xaxis_title="Data",
            yaxis_title="R$",
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig2, config={**PLOTLY_CONFIG, "toImageButtonOptions": {"format": "png", "filename": "saldo_acumulado"}})
    else:
        st.info("Sem movimentos **realizados** no período para montar o acumulado.")

    st.divider()

    # ============================================================
    # 3) Previsto vs. Realizado por Centro de Custo (barra agrupada)
    # ============================================================
    st.subheader("Previsto vs. Realizado por Centro de Custo")

    prev_cc = pd.DataFrame(columns=["centro_custo", "previsto"])
    if not df_prev.empty:
        p = df_prev.copy()
        p["centro_custo"] = p["centro_custo"].fillna("(sem CC)")
        prev_cc = p.groupby("centro_custo", as_index=False)["valor"].sum().rename(columns={"valor": "previsto"})

    real_cc = pd.DataFrame(columns=["centro_custo", "realizado"])
    if not df_real.empty:
        r = df_real.copy()
        r["centro_custo"] = r["centro_custo"].fillna("(sem CC)")
        real_cc = r.groupby("centro_custo", as_index=False)["valor"].sum().rename(columns={"valor": "realizado"})

    comp_cc = pd.merge(prev_cc, real_cc, on="centro_custo", how="outer").fillna(0.0)
    if comp_cc.empty:
        st.info("Sem dados de **previsto/realizado** por Centro de Custo no período.")
    else:
        comp_cc_long = comp_cc.melt(
            id_vars="centro_custo",
            value_vars=["previsto", "realizado"],
            var_name="Tipo", value_name="Valor",
        )
        fig3 = px.bar(
            comp_cc_long,
            x="centro_custo", y="Valor",
            color="Tipo", barmode="group",
            title="Previsto vs. Realizado por Centro de Custo (período selecionado)",
            template="plotly_white",
        )
        fig3.update_layout(
            xaxis_title="Centro de Custo",
            yaxis_title="R$",
            legend_title_text="",
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig3, config={**PLOTLY_CONFIG, "toImageButtonOptions": {"format": "png", "filename": "previsto_vs_realizado_cc"}})

    st.divider()

    # ===========================================
    # 4) Gastos por Categoria (Saídas — Realizado)
    # ===========================================
    st.subheader("Gastos por Categoria (Saídas — Realizado)")
    if not df_real.empty:
        saidas = df_real[df_real["tipo"] == "Saida"].copy()
        if saidas.empty:
            st.info("Não há **saídas realizadas** no período.")
        else:
            gcat = saidas.groupby("categoria", as_index=False)["valor"].sum().sort_values("valor", ascending=False)
            fig4 = px.bar(
                gcat,
                x="categoria", y="valor",
                title="Total de Saídas por Categoria (Realizado)",
                template="plotly_white",
            )
            fig4.update_layout(
                xaxis_title="Categoria",
                yaxis_title="R$",
                margin=dict(l=10, r=10, t=50, b=10),
            )
            st.plotly_chart(fig4, config={**PLOTLY_CONFIG, "toImageButtonOptions": {"format": "png", "filename": "gastos_por_categoria"}})
    else:
        st.info("Sem movimentos **realizados** para compor *Gastos por Categoria*.")
