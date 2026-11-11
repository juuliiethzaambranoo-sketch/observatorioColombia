# -*- coding: utf-8 -*-
"""
OBSERVATORIO NACIONAL DE COLOMBIA · Interfaz Streamlit
Plataforma de inteligencia territorial, econometría y simulación de políticas públicas.

Principio rector: DATOS 100 % REALES. Todo se consulta en vivo a las APIs públicas (datos.gov.co / Socrata).
Si una fuente falla, la aplicación lo informa y NO inventa cifras.

Archivos:
    observatorio_core.py   datos, modelos, figuras y asistente (sin interfaz; se importa una sola vez,
                           por eso sus cachés sobreviven a los reruns de Streamlit)
    app.py                 esta interfaz
    .streamlit/config.toml tema oscuro con la paleta tricolor

Ejecución local:   streamlit run app.py
Google Colab:      !pip -q install streamlit
                   !streamlit run app.py &>/content/log.txt &
                   !npx localtunnel --port 8501          (abra el enlace; la contraseña es la IP pública)
"""
import streamlit as st

st.set_page_config(page_title="Observatorio Nacional de Colombia", page_icon="🇨🇴",
                   layout="wide", initial_sidebar_state="collapsed")

from observatorio_core import *                      # noqa: F401,F403  (datos, modelos, figuras, HTML)
from observatorio_core import _vars_op, _ASIST_SUGERENCIAS   # noqa: E402  (los «_» no entran con *)


# =============================================================================
# 1. ESTILO (CSS institucional del core + ajustes propios de Streamlit)
# =============================================================================
CSS_ST = """
.stApp{background-color:#050810;background-image:
 radial-gradient(ellipse 70% 45% at 12% -10%,rgba(252,209,22,.10),transparent 60%),
 radial-gradient(ellipse 60% 40% at 88% 0%,rgba(0,56,147,.28),transparent 60%),
 radial-gradient(ellipse 50% 40% at 50% 110%,rgba(206,17,38,.10),transparent 60%);
 background-attachment:fixed;color:#E8EEF7;font-family:'Inter',system-ui,sans-serif;}
header[data-testid="stHeader"]{background:transparent;}
.block-container{max-width:1500px;padding-top:1.6rem;padding-bottom:3rem;}
div[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:6px;flex-wrap:wrap;border-bottom:1px solid rgba(252,209,22,.16);}
div[data-testid="stTabs"] button[data-baseweb="tab"]{color:#CBD5E1;border-radius:10px 10px 0 0;padding:8px 14px;}
div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"]{color:#FCD116;background:rgba(252,209,22,.07);}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"]{background-color:#FCD116;}
button[kind="primary"],button[data-testid="stBaseButton-primary"],
div[data-testid="stDownloadButton"] button{background:linear-gradient(135deg,#FCD116,#FFD84D) !important;
 color:#0B1220 !important;border:none !important;font-weight:700 !important;border-radius:10px !important;}
button[kind="primary"] p,button[data-testid="stBaseButton-primary"] p,
div[data-testid="stDownloadButton"] button p{color:#0B1220 !important;}
button[kind="primary"]:hover,button[data-testid="stBaseButton-primary"]:hover{
 transform:translateY(-1px);box-shadow:0 0 28px rgba(252,209,22,.42);}
button[kind="secondary"],button[data-testid="stBaseButton-secondary"]{background:rgba(0,56,147,.28) !important;
 color:#E8EEF7 !important;border:1px solid rgba(0,56,147,.6) !important;border-radius:10px !important;}
div[data-testid="stExpander"]{border:1px solid rgba(252,209,22,.16);border-radius:12px;background:rgba(12,18,30,.78);}
div[data-testid="stDataFrame"]{border:1px solid rgba(148,163,184,.16);border-radius:12px;overflow:hidden;}
div[data-testid="stChatMessage"]{background:rgba(12,18,30,.78);border:1px solid rgba(252,209,22,.12);border-radius:14px;}
label,div[data-testid="stWidgetLabel"] p{color:#CBD5E1 !important;}
"""
FUENTES_WEB = ("@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800"
               "&family=Sora:wght@600;700;800&display=swap');")


def _inyectar_estilo():
    st.markdown(f"<style>{FUENTES_WEB}</style>", unsafe_allow_html=True)
    st.markdown(f"<style>{CSS}\n{CSS_ST}</style>", unsafe_allow_html=True)


# =============================================================================
# 2. UTILIDADES DE RENDER (compatibles con distintas versiones de Streamlit)
# =============================================================================
def _html(s):
    if s:
        (st.html if hasattr(st, "html") else (lambda x: st.markdown(x, unsafe_allow_html=True)))(s)


def _ancho(fn):
    """Argumento de ancho completo según la versión: use_container_width (≤1.5x) o width='stretch' (nuevas)."""
    return {"use_container_width": True} if "use_container_width" in inspect.signature(fn).parameters \
        else {"width": "stretch"}


def _plot(fig, key):
    if fig is None:
        return
    kw = _ancho(st.plotly_chart)
    if "theme" in inspect.signature(st.plotly_chart).parameters:
        kw["theme"] = None                      # respeta el estilo oscuro propio de las figuras
    st.plotly_chart(fig, key=key, **kw)


def _tabla(df, titulo=None):
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return
    if titulo:
        st.caption(titulo)
    st.dataframe(df, hide_index=True, **_ancho(st.dataframe))


def _guardar_archivo(clave, ruta):
    """Lee el archivo generado por el core y lo deja en session_state para ofrecer su descarga."""
    if ruta and os.path.exists(ruta):
        with open(ruta, "rb") as fh:
            st.session_state[clave] = (os.path.basename(ruta), fh.read())
    else:
        st.session_state[clave] = None


def _boton_descarga(clave, etiqueta):
    d = st.session_state.get(clave)
    if not d:
        return
    nombre, datos = d
    mime = ("text/html" if nombre.endswith(".html") else
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if nombre.endswith(".xlsx")
            else "text/csv")
    st.download_button(etiqueta, datos, file_name=nombre, mime=mime, key=clave + "_dl")


def _sel(etiqueta, opciones, valor, key):
    """selectbox con pares (etiqueta, valor), como los Dropdown de la versión Gradio."""
    vals = [v for _, v in opciones]
    nombres = {v: n for n, v in opciones}
    i = vals.index(valor) if valor in vals else 0
    return st.selectbox(etiqueta, vals, index=i, format_func=lambda v: nombres.get(v, str(v)), key=key)


def _multi(etiqueta, opciones, defecto, key):
    vals = [v for _, v in opciones]
    nombres = {v: n for n, v in opciones}
    return st.multiselect(etiqueta, vals, default=[d for d in defecto if d in vals],
                          format_func=lambda v: nombres.get(v, str(v)), key=key)


def _reactivo(clave, disparo, fn, *args, auto=True, mensaje="Consultando datos oficiales…"):
    """Ejecuta fn cuando se pulsa el botón y, si auto=True, la recalcula al cambiar los controles
    (después del primer cálculo). El resultado persiste en session_state entre reruns."""
    firma = repr(args)
    if disparo or (auto and clave in st.session_state and st.session_state.get(clave + "|firma") != firma):
        with st.spinner(mensaje):
            st.session_state[clave] = fn(*args)
        st.session_state[clave + "|firma"] = firma
    return st.session_state.get(clave)


# =============================================================================
# 3. CALLBACKS (misma lógica y mismos decoradores @ui que la versión Gradio, ahora síncronos)
# =============================================================================
def _tablero(cod, a0, a1, sector, k):
    k = clave_var(k)
    precargar()
    p = panel()
    kp, est = html_kpis(cod), estado_fuentes_html()
    ks = [x for x in SECTORES.get(sector, list(VARS)) if p is not None and x in p.columns]
    if not ks:
        v = fig_aviso("Los indicadores de este sector no están disponibles en tiempo real.")
        return kp, est, v, v, v
    if k not in ks:
        k = ks[0]
    disp = p.loc[p[k].notna(), "anio"]
    if disp.empty:
        v = fig_aviso(f"Sin observaciones de «{etq(k)}».")
        return kp, est, v, v, v
    an = int(min(int(a1), int(disp.max())))
    return (kp, est, fig_ranking(p, k, an, cod), fig_distribucion(p, k, an),
            fig_evolucion(p, k, cod, int(a0), int(a1)))


@ui("hhppp")
def cb_tablero(cod, a0, a1, sector, k):
    return _tablero(cod, a0, a1, sector, k)


def _radiografia(ks, cods, a0, a1, busq, anio):
    precargar()
    p = panel()
    if p is None:
        return (pd.DataFrame({"Aviso": ["Sin datos oficiales disponibles en tiempo real"]}),
                fig_aviso("Sin datos del panel territorial."))
    return tabla_panel(p, ks, cods, a0, a1, busq), fig_heat_z(p, ks, int(anio))


@ui("dp")
def cb_radiografia(ks, cods, a0, a1, busq, anio):
    return _radiografia(ks, cods, a0, a1, busq, anio)


def _exp_panel(ks, cods, a0, a1, busq, fmt):
    p = panel()
    if p is None:
        return None
    return exportar_df(tabla_panel(p, ks, cods, a0, a1, busq), fmt)


@ui("f")
def cb_exp_panel(ks, cods, a0, a1, busq, fmt):
    return _exp_panel(ks, cods, a0, a1, busq, fmt)


def _dataset(ds, where, lim, fmt):
    ds = (ds or "").strip()
    if not re.fullmatch(r"[a-z0-9]{4}-[a-z0-9]{4}", ds):
        return pd.DataFrame({"Aviso": ["ID inválido. Formato esperado: xxxx-xxxx (p. ej., 32sa-8pi3)"]}), None
    params = {"$limit": int(lim)}
    if where and where.strip():
        params["$where"] = where.strip()
    df = soda(ds, params, timeout=60)
    return ((df, exportar_df(df, fmt)) if not df.empty
            else (pd.DataFrame({"Aviso": ["La consulta no devolvió filas."]}), None))


@ui("df")
def cb_dataset(ds, where, lim, fmt):
    return _dataset(ds, where, lim, fmt)


@ui("pd")
def cb_corr(ks, metodo, anio):
    return correlaciones(ks, metodo, int(anio))


@ui("ppdd")
def cb_clust(ks, k, a0, a1):
    fs, fm, perfil, sil, _ = clusteres(ks, int(k), int(a0), int(a1))
    return fs, fm, perfil, sil


@ui("pdhd")
def cb_pron(s, cod, mod, hor):
    return pronostico_cacheado(s, cod, mod, hor)


@ui("pdh")
def cb_sim(y, x, cod, d, dur, rez, hor, fe):
    return simular(y, x, cod, d, dur, rez, hor, fe)


@ui("pdh")
def cb_mapa(k, anio, cod):
    return mapa_indicador(k, int(anio), cod)


@ui("dh")
def cb_cand(clave):
    d = candidatos_macro(clave)
    if len(d):
        msg = f"{len(d)} conjuntos encontrados. Copie el ID y los nombres de columnas que correspondan."
        return d, aviso(msg, "ok")
    return d, aviso("El catálogo no devolvió resultados.", "warn")


@ui("h")
def cb_conectar(clave, ds, c_t, c_d, c_v):
    ok, msg = conectar_macro(clave, ds, c_t, c_d, c_v)
    return aviso(msg + (" Pulse «Actualizar tablero»." if ok else ""), "ok" if ok else "err")


@ui("hf")
def cb_informe(tit, com, secs, cod, a0, a1, k, offline):
    ruta = generar_informe(tit or "Informe del Observatorio Nacional de Colombia", com or "",
                           secs, cod, int(a0), int(a1), k, bool(offline))
    return aviso("Informe generado con los datos consultados en este momento. Descárguelo abajo.", "ok"), ruta


# =============================================================================
# 4. ARRANQUE EN SEGUNDO PLANO (precarga de datos + monitor de APIs)
# =============================================================================
@st.cache_resource
def _estado_monitor():
    return {"html": None, "corriendo": False}


def _lanzar_monitor(limpiar=False):
    est = _estado_monitor()
    if est["corriendo"]:
        return
    est["corriendo"], est["html"] = True, None

    def _trabajo():
        try:
            if limpiar:
                limpiar_cache()
            est["html"] = monitor_apis()
        except Exception as e:
            est["html"] = aviso(f"{type(e).__name__}: {e}", "err")
        finally:
            est["corriendo"] = False

    threading.Thread(target=_trabajo, daemon=True).start()


@st.cache_resource
def _arrancar():
    threading.Thread(target=calentar, daemon=True).start()     # precarga mientras se abre la interfaz
    _lanzar_monitor()                                          # equivalente a demo.load(monitor_apis)
    return True


def _panel_monitor():
    """Muestra el monitor de APIs; mientras verifica se refresca solo (st.fragment) sin bloquear la página."""
    est = _estado_monitor()
    esperando = est["html"] is None
    frag = getattr(st, "fragment", None)

    def _cuerpo():
        e = _estado_monitor()
        if e["html"] is None:
            _html(aviso("Verificando servicios oficiales…", "warn"))
        else:
            _html(e["html"])
            if esperando:
                st.rerun()                                      # termina el sondeo periódico

    if frag is None:                                            # Streamlit antiguo: espera acotada
        for _ in range(30):
            if est["html"] is not None:
                break
            time.sleep(0.5)
        _cuerpo()
    else:
        frag(run_every=2 if esperando else None)(_cuerpo)()


# =============================================================================
# 5. INTERFAZ
# =============================================================================
_inyectar_estilo()
_arrancar()
_html(html_topbar())

tabs = st.tabs(["📌 Presentación", "📊 Tablero general", "🔬 Radiografía y microdatos", "🗺️ Mapas y modelos",
                "📈 Series y pronóstico", "🎛️ Simulador de políticas", "📄 Generador de informes",
                "🤖 Asistente IA"])
ANIO_MIN = CONFIG["anio_min"]

# ---------- 0 · Presentación ----------
with tabs[0]:
    _html(html_hero())
    _html(html_guia())
    _html('<div class="sec-title">Monitor de salud de las APIs</div>')
    if st.button("🔄 Probar APIs ahora", type="primary", key="b_mon"):
        _lanzar_monitor(limpiar=True)
    _panel_monitor()

# ---------- 1 · Tablero ----------
with tabs[1]:
    c1, c2, c3 = st.columns([2, 2, 3])
    with c1:
        t_dep = _sel("Territorio", OPC_DEP, "00", "t_dep")
    with c2:
        t_sec = st.selectbox("Sector", list(SECTORES), key="t_sec")
    with c3:
        t_ops = [o for o in _vars_op() if o[1] in SECTORES[t_sec]]
        t_var = _sel("Indicador", t_ops, "hom", f"t_var_{t_sec}")
    c4, c5 = st.columns([4, 1])
    with c4:
        t_a0, t_a1 = st.slider("Periodo", ANIO_MIN, A1D, (A0D, A1D), step=1, key="t_per")
    with c5:
        st.write("")
        t_btn = st.button("Actualizar tablero", type="primary", key="t_btn")
    res = _reactivo("tablero", t_btn or "tablero" not in st.session_state, cb_tablero,
                    t_dep, t_a0, t_a1, t_sec, t_var, auto=False, mensaje="Cargando el tablero con datos en vivo…")
    if res:
        kp, est, p1, p2, p3 = res
        _html(kp)
        _html(est)
        _plot(p1, "t_p1")
        d1, d2 = st.columns(2)
        with d1:
            _plot(p2, "t_p2")
        with d2:
            _plot(p3, "t_p3")

    with st.expander("⚙️ Configurar fuentes de IPM, desempleo, IPC y PIB"):
        _html(aviso("Si la búsqueda automática no encuentra el conjunto, búsquelo aquí y conéctelo: indique el ID de "
                    "datos.gov.co y los nombres EXACTOS de las columnas de tiempo, territorio (opcional) y valor.", "warn"))
        g1, g2 = st.columns([3, 1])
        with g1:
            g_ind = _sel("Indicador", [(m["nombre"], k) for k, m in MACROS.items()], "ipm", "g_ind")
        with g2:
            st.write("")
            if st.button("🔍 Ver conjuntos candidatos", key="g_bus"):
                with st.spinner("Consultando el catálogo de datos.gov.co…"):
                    st.session_state["g_cand"] = cb_cand(g_ind)
        if st.session_state.get("g_cand"):
            g_tab, g_msg = st.session_state["g_cand"]
            _tabla(g_tab, "Candidatos del catálogo de datos.gov.co")
            _html(g_msg)
        e1, e2, e3, e4 = st.columns(4)
        g_id = e1.text_input("ID del conjunto", placeholder="xxxx-xxxx", key="g_id")
        g_t = e2.text_input("Columna de año/fecha", key="g_t")
        g_d = e3.text_input("Columna de departamento (opcional)", key="g_d")
        g_v = e4.text_input("Columna de valor", key="g_v")
        if st.button("Conectar fuente", type="primary", key="g_con"):
            with st.spinner("Validando el conjunto…"):
                st.session_state["g_est"] = cb_conectar(g_ind, g_id, g_t, g_d, g_v)
        _html(st.session_state.get("g_est"))

# ---------- 2 · Radiografía ----------
with tabs[2]:
    a, b = st.columns(2)
    with a:
        r_vars = _multi("Indicadores", _vars_op(), ["hom", "cob", "coca"], "r_vars")
    with b:
        r_deps = _multi("Departamentos (vacío = todos)", OPC_DEP[1:], [], "r_deps")
    a, b, c = st.columns([3, 2, 2])
    with a:
        r_a0, r_a1 = st.slider("Periodo", ANIO_MIN, A1D, (A0D, A1D), step=1, key="r_per")
    with b:
        r_anio = st.slider("Año del mapa de calor", ANIO_MIN, A1D, A1D, step=1, key="r_anio")
    with c:
        r_busq = st.text_input("Filtrar filas (texto)", placeholder="p. ej. Nariño", key="r_busq")
    if st.button("Consultar", type="primary", key="r_btn"):
        with st.spinner("Consultando el panel territorial…"):
            st.session_state["radio"] = cb_radiografia(r_vars, r_deps, r_a0, r_a1, r_busq, r_anio)
    if st.session_state.get("radio"):
        r_tab, r_heat = st.session_state["radio"]
        _tabla(r_tab, "Explorador de datos reales")
        f1_, f2_ = st.columns([1, 3])
        with f1_:
            r_fmt = st.radio("Formato", ["csv", "xlsx"], horizontal=True, key="r_fmt")
        with f2_:
            st.write("")
            if st.button("⬇️ Exportar tabla", key="r_exp"):
                _guardar_archivo("r_file", cb_exp_panel(r_vars, r_deps, r_a0, r_a1, r_busq, r_fmt))
            _boton_descarga("r_file", "Descargar archivo")
        _plot(r_heat, "r_heat")

    with st.expander("🔎 Consultar cualquier conjunto de datos.gov.co por su ID"):
        a, b, c = st.columns([2, 3, 2])
        d_id = a.text_input("ID del conjunto", value="32sa-8pi3", key="d_id")
        d_where = b.text_input("Filtro SoQL ($where)", placeholder="vigenciadesde > '2024-01-01T00:00:00'", key="d_where")
        d_lim = c.slider("Filas máx.", 10, 50000, 500, step=10, key="d_lim")
        d_fmt = st.radio("Formato", ["csv", "xlsx"], horizontal=True, key="d_fmt")
        if st.button("Consultar API", type="primary", key="d_btn"):
            with st.spinner("Consultando la API de datos.gov.co…"):
                d_df, d_ruta = cb_dataset(d_id, d_where, d_lim, d_fmt)
                st.session_state["d_df"] = d_df
                _guardar_archivo("d_file", d_ruta)
        _tabla(st.session_state.get("d_df"))
        _boton_descarga("d_file", "Descargar archivo")

# ---------- 3 · Mapas y modelos ----------
with tabs[3]:
    t_map, t_cor, t_clu = st.tabs(["Mapa coroplético", "Correlaciones", "Clústeres K-Means"])

    with t_map:
        a, b, c, d = st.columns([3, 3, 2, 1])
        with a:
            m_var = _sel("Indicador", _vars_op(), "hom", "m_var")
        with b:
            m_anio = st.slider("Año", ANIO_MIN, A1D, A1D, step=1, key="m_anio")
        with c:
            m_cod = _sel("Resaltar territorio", OPC_DEP, "00", "m_cod")
        with d:
            st.write("")
            m_btn = st.button("Dibujar mapa", type="primary", key="m_btn")
        res = _reactivo("mapa", m_btn, cb_mapa, m_var, m_anio, m_cod, mensaje="Dibujando el mapa…")
        if res:
            m_plot, m_tab, m_est = res
            _plot(m_plot, "m_plot")
            _html(m_est)
            _tabla(m_tab, "Detalle del indicador (ranking territorial o serie nacional)")

    with t_cor:
        a, b, c = st.columns([4, 2, 3])
        with a:
            c_vars = _multi("Indicadores", _vars_op(), list(VARS)[:6], "c_vars")
        with b:
            c_met = st.radio("Método", ["Pearson", "Spearman"], horizontal=True, key="c_met")
        with c:
            c_anio = st.slider("Año (0 = todos los años)", 0, A1D, 0, step=1, key="c_anio")
        c_btn = st.button("Calcular", type="primary", key="c_btn")
        res = _reactivo("corr", c_btn, cb_corr, c_vars, c_met, c_anio, auto=False, mensaje="Calculando correlaciones…")
        if res:
            _plot(res[0], "c_plot")
            _tabla(res[1])

    with t_clu:
        a, b = st.columns([4, 2])
        with a:
            k_vars = _multi("Indicadores", _vars_op(), ["hom", "vif", "coca", "cob", "des"], "k_vars")
        with b:
            k_k = st.slider("Número de grupos (k)", 2, 6, 3, step=1, key="k_k")
        a, b = st.columns([4, 1])
        with a:
            k_a0, k_a1 = st.slider("Periodo (promedio)", ANIO_MIN, A1D, (max(ANIO_MIN, A1D - 4), A1D), step=1, key="k_per")
        with b:
            st.write("")
            k_btn = st.button("Agrupar", type="primary", key="k_btn")
        res = _reactivo("clust", k_btn, cb_clust, k_vars, k_k, k_a0, k_a1, auto=False, mensaje="Ajustando K-Means…")
        if res:
            fs, fm, perfil, sil = res
            _plot(fs, "k_p")
            _plot(fm, "k_m")
            _tabla(perfil, "Perfil de cada grupo (promedios)")
            _tabla(sil, "Silueta por k")

# ---------- 4 · Series y pronóstico ----------
with tabs[4]:
    a, b = st.columns([3, 2])
    with a:
        ser_op = list(SERIES)
        s_ser = st.selectbox("Serie histórica oficial", ser_op,
                             index=ser_op.index("TRM mensual (COP por USD)") if "TRM mensual (COP por USD)" in ser_op else 0,
                             key="s_ser")
    with b:
        s_dep = _sel("Territorio (series de eventos/anuales)", OPC_DEP, "00", "s_dep")
    a, b, c = st.columns([3, 2, 1])
    with a:
        s_mod = st.selectbox("Modelo", ["Automático (mejor RMSE)"] + list(MODELOS), key="s_mod")
    with b:
        s_hor = st.radio("Horizonte (meses)", [6, 12, 24], index=1, horizontal=True, key="s_hor")
    with c:
        st.write("")
        s_btn = st.button("Pronosticar", type="primary", key="s_btn")
    res = _reactivo("pron", s_btn, cb_pron, s_ser, s_dep, s_mod, s_hor, auto=False,
                    mensaje="Ajustando modelos y validando fuera de muestra…")
    if res:
        s_plot, s_tab, s_info, s_ev = res
        _html(s_info)
        _plot(s_plot, "s_plot")
        x1, x2 = st.columns(2)
        with x1:
            _tabla(s_tab, "Pronóstico con intervalos de confianza")
        with x2:
            _tabla(s_ev, "Validación fuera de muestra (backtest)")

# ---------- 5 · Simulador ----------
with tabs[5]:
    _html(aviso("Los coeficientes se estiman con el panel departamental real (efectos fijos). El simulador compara la "
                "tendencia inercial con un escenario en el que el impulsor elegido cambia el porcentaje indicado.", "warn"))
    a, b, c = st.columns(3)
    with a:
        z_y = _sel("Variable de resultado", _vars_op(), "des", "z_y")
    with b:
        z_x = _sel("Impulsor (política)", _vars_op(), "cob", "z_x")
    with c:
        z_dep = _sel("Territorio", OPC_DEP, "00", "z_dep")
    a, b, c, d = st.columns(4)
    z_d = a.slider("Variación del impulsor (%)", -50, 50, 10, step=1, key="z_d")
    z_dur = b.slider("Años para alcanzar el cambio", 1, 10, 3, step=1, key="z_dur")
    z_rez = c.slider("Rezago del efecto (años)", 0, 3, 1, step=1, key="z_rez")
    z_hor = d.slider("Horizonte (años)", 2, 10, 5, step=1, key="z_hor")
    a, b = st.columns([4, 1])
    with a:
        z_fe = st.radio("Efectos fijos", ["Departamento + año", "Departamento"], horizontal=True, key="z_fe")
    with b:
        z_btn = st.button("Simular escenario", type="primary", key="z_btn")
    res = _reactivo("sim", z_btn, cb_sim, z_y, z_x, z_dep, z_d, z_dur, z_rez, z_hor, z_fe,
                    mensaje="Estimando elasticidades y simulando…")      # tras el primer cálculo, reacciona a los controles
    if res:
        z_plot, z_tab, z_info = res
        _html(z_info)
        _plot(z_plot, "z_plot")
        _tabla(z_tab, "Escenarios")

# ---------- 6 · Informes ----------
with tabs[6]:
    a, b, c = st.columns(3)
    i_tit = a.text_input("Título del informe", value="Informe del Observatorio Nacional de Colombia", key="i_tit")
    with b:
        i_dep = _sel("Territorio", OPC_DEP, "00", "i_dep")
    with c:
        i_var = _sel("Indicador principal", _vars_op(), "hom", "i_var")
    i_com = st.text_area("Comentarios ejecutivos", height=110, key="i_com",
                         placeholder="Escriba los hallazgos o recomendaciones que acompañarán el informe…")
    i_sec = st.multiselect("Secciones a incluir", SECCIONES, default=SECCIONES[:6], key="i_sec")
    a, b = st.columns([3, 2])
    with a:
        i_a0, i_a1 = st.slider("Periodo", ANIO_MIN, A1D, (A0D, A1D), step=1, key="i_per")
    with b:
        i_off = st.checkbox("Incluir Plotly incrustado (HTML sin internet)", value=False, key="i_off")
    if st.button("Compilar informe", type="primary", key="i_btn"):
        with st.spinner("Compilando el informe en paralelo…"):
            i_msg, i_ruta = cb_informe(i_tit, i_com, i_sec, i_dep, i_a0, i_a1, i_var, i_off)
            st.session_state["i_msg"] = i_msg
            _guardar_archivo("i_file", i_ruta)
    _html(st.session_state.get("i_msg"))
    _boton_descarga("i_file", "⬇️ Descargar informe HTML (imprimible a PDF)")

# ---------- 7 · Asistente IA ----------
with tabs[7]:
    _html('<div class="sec-title">Asistente IA del Observatorio</div>')
    _html(aviso("Pregunte sobre el uso de la interfaz, las fuentes oficiales de datos abiertos y los modelos "
                "(SARIMA, K-Means, regresiones de panel). Las respuestas provienen de la documentación del "
                "observatorio; no consultan cifras en vivo.", "ok"))
    if "chat" not in st.session_state:
        st.session_state["chat"] = [{"role": "assistant", "content": responder_asistente("hola")}]

    st.caption("Preguntas sugeridas")
    cols = st.columns(3)
    sugerida = None
    for i, q in enumerate(_ASIST_SUGERENCIAS):
        if cols[i % 3].button(q, key=f"sug_{i}", **_ancho(st.button)):
            sugerida = q
    pregunta = st.chat_input("Escriba su pregunta sobre el observatorio…", key="chat_in") or sugerida
    if pregunta:
        st.session_state["chat"].append({"role": "user", "content": pregunta})
        st.session_state["chat"].append({"role": "assistant", "content": responder_asistente(pregunta)})
    for m in st.session_state["chat"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

# ---------- pie ----------
_html(html_pie())
