"""
🌎 Explorador de Sismos
-----------------------
App web hecha con Streamlit que consulta sismos REALES de los últimos 10 años
en el catálogo público del USGS (Servicio Geológico de EE. UU.).
No necesita claves, cuentas ni registro.

Problema que resuelve: una persona quiere saber qué tanto tiembla en su país
o cerca de su ciudad, qué tan fuertes han sido los sismos y cómo ha cambiado
la actividad sísmica en los últimos años.

Para correrla en tu computador:
    pip install -r requirements.txt
    streamlit run app.py
"""

import io
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from regiones import REGIONES

# ---------------------------------------------------------------------------
# 1. CONFIGURACIÓN GENERAL
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Explorador de Sismos", page_icon="🌎", layout="wide")

URL_USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query"
ANIOS_DE_HISTORIA = 10      # cuántos años hacia atrás consultamos
MAGNITUD_MINIMA_API = 2.5   # magnitud mínima que le pedimos al USGS
MAX_PUNTOS_MAPA = 5000      # límite de puntos en el mapa para que no se ponga lento

# Colores de las gráficas (revisados para que se distingan con daltonismo).
AZUL = "#2a78d6"
NARANJA = "#eb6834"
GRIS = "#898781"
COLORES_PROFUNDIDAD = {   # más profundo = azul más oscuro
    "Superficial (0–70 km)": "#86b6ef",
    "Intermedio (70–300 km)": "#2a78d6",
    "Profundo (más de 300 km)": "#0d366b",
}
CLASES_MAGNITUD = ["Menor (< 4)", "Ligero (4–4.9)", "Moderado (5–5.9)", "Fuerte (6–6.9)", "Mayor (7+)"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# ---------------------------------------------------------------------------
# 2. FUNCIONES DE AYUDA
# ---------------------------------------------------------------------------
def sumar_anios(fecha, anios):
    """Suma (o resta, si es negativo) años a una fecha. Maneja el 29 de febrero."""
    try:
        return fecha.replace(year=fecha.year + anios)
    except ValueError:
        return fecha.replace(year=fecha.year + anios, day=28)


def tramos_anuales(inicio, fin):
    """Divide el periodo en tramos de 1 año.
    El USGS entrega máximo 20.000 sismos por consulta, así que pedimos año por año."""
    tramos = []
    actual = inicio
    while actual < fin:
        siguiente = min(sumar_anios(actual, 1), fin)
        tramos.append((actual, siguiente))
        actual = siguiente
    return tramos


def formatear_numero(valor, decimales=0):
    """Formato con punto de miles y coma decimal, como se usa en Colombia: 12.345,6"""
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


# El USGS describe el lugar en inglés, por ejemplo "12 km NW of Los Santos, Colombia".
# Estas reglas lo pasan a español: "12 km al NO de Los Santos, Colombia".
DIRECCIONES = {"N": "N", "NNE": "NNE", "NE": "NE", "ENE": "ENE", "E": "E", "ESE": "ESE",
               "SE": "SE", "SSE": "SSE", "S": "S", "SSW": "SSO", "SW": "SO", "WSW": "OSO",
               "W": "O", "WNW": "ONO", "NW": "NO", "NNW": "NNO"}
PATRON_LUGAR = re.compile(r"^(\d+(?:\.\d+)?) ?km ([NSEW]{1,3}) of (.+)$")


def traducir_lugar(texto):
    if not isinstance(texto, str) or not texto.strip():
        return "Lugar sin nombre"
    texto = texto.strip()
    coincidencia = PATRON_LUGAR.match(texto)
    if coincidencia:
        km, direccion, sitio = coincidencia.groups()
        return f"{km} km al {DIRECCIONES.get(direccion, direccion)} de {sitio}"
    texto = re.sub(r"^offshore ", "Frente a la costa de ", texto)
    texto = re.sub(r"^near the coast of ", "Cerca de la costa de ", texto)
    return texto


def distancia_km(lat1, lon1, lat2, lon2):
    """Distancia en km sobre la superficie de la Tierra (fórmula de Haversine)."""
    radio_tierra = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * radio_tierra * np.arcsin(np.sqrt(a))


def puntos_circulo(lat, lon, radio_km, n=120):
    """Puntos (lat, lon) de un círculo de radio_km alrededor de una ciudad, para dibujarlo en el mapa."""
    angulos = np.linspace(0, 2 * np.pi, n)
    d = radio_km / 6371.0
    lat_r, lon_r = np.radians(lat), np.radians(lon)
    lat_c = np.arcsin(np.sin(lat_r) * np.cos(d) + np.cos(lat_r) * np.sin(d) * np.cos(angulos))
    lon_c = lon_r + np.arctan2(np.sin(angulos) * np.sin(d) * np.cos(lat_r),
                               np.cos(d) - np.sin(lat_r) * np.sin(lat_c))
    return np.degrees(lat_c), np.degrees(lon_c)


# ---------------------------------------------------------------------------
# 3. DESCARGA Y LIMPIEZA DE DATOS
# ---------------------------------------------------------------------------
def descargar_tramo(caja, inicio, fin, intentos=3):
    """Pide al USGS los sismos de un rectángulo (caja) entre dos fechas. Devuelve un DataFrame.
    Si la conexión falla, lo vuelve a intentar hasta 3 veces antes de rendirse."""
    lat_min, lat_max, lon_min, lon_max = caja
    parametros = {
        "format": "csv",
        "starttime": inicio.isoformat(),
        "endtime": fin.isoformat(),
        "minlatitude": lat_min,
        "maxlatitude": lat_max,
        "minlongitude": lon_min,
        "maxlongitude": lon_max,
        "minmagnitude": MAGNITUD_MINIMA_API,
        "eventtype": "earthquake",   # excluye explosiones de canteras, etc.
        "orderby": "time",
    }
    for intento in range(1, intentos + 1):
        try:
            respuesta = requests.get(URL_USGS, params=parametros, timeout=60,
                                     headers={"User-Agent": "explorador-sismos (proyecto de clase)"})
            if respuesta.status_code == 204 or not respuesta.text.strip():
                return pd.DataFrame()   # 204 = no hubo sismos en ese tramo
            respuesta.raise_for_status()
            return pd.read_csv(io.StringIO(respuesta.text))
        except Exception:
            if intento == intentos:
                raise              # ya no hay más intentos: avisamos del error
            time.sleep(2 * intento)  # esperamos un poco antes de reintentar


def limpiar_datos(datos, region):
    """Deja solo las columnas útiles, con nombres en español y fechas en hora local."""
    datos = datos.dropna(subset=["time", "latitude", "longitude", "mag", "depth"]).copy()

    fecha_utc = pd.to_datetime(datos["time"], utc=True, format="ISO8601")
    datos["fecha"] = fecha_utc.dt.tz_convert(region["zona_horaria"]).dt.tz_localize(None)
    datos["fecha_texto"] = datos["fecha"].dt.strftime("%d/%m/%Y %H:%M")
    datos["magnitud"] = datos["mag"].round(1)
    datos["profundidad"] = datos["depth"].clip(lower=0).round(1)
    datos["lugar_usgs"] = datos["place"].fillna("").astype(str)
    datos["lugar"] = datos["lugar_usgs"].map(traducir_lugar)
    datos["en_pais"] = datos["lugar_usgs"].str.contains(region["patron_pais"], regex=True, case=False)
    datos["categoria_profundidad"] = pd.cut(datos["profundidad"], bins=[-np.inf, 70, 300, np.inf],
                                            right=False, labels=list(COLORES_PROFUNDIDAD))
    datos["clasificacion"] = pd.cut(datos["magnitud"], bins=[-np.inf, 4, 5, 6, 7, np.inf],
                                    right=False, labels=CLASES_MAGNITUD)
    datos["estado"] = datos["status"].map({"reviewed": "Revisado", "automatic": "Automático"}).fillna("—")
    datos["enlace"] = "https://earthquake.usgs.gov/earthquakes/eventpage/" + datos["id"].astype(str)

    columnas = ["fecha", "fecha_texto", "magnitud", "magType", "profundidad", "lugar", "lugar_usgs",
                "en_pais", "latitude", "longitude", "categoria_profundidad", "clasificacion",
                "estado", "enlace", "id"]
    return datos[columnas].sort_values("fecha", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)   # guarda los datos 1 hora para no descargarlos cada vez
def cargar_sismos(nombre_region, hoy):
    """Descarga los últimos 10 años de sismos de una región (año por año, 4 años a la vez).
    Si algún año no se puede descargar, la función lanza un error y Streamlit NO lo guarda
    en caché, así que en la siguiente visita se vuelve a intentar."""
    region = REGIONES[nombre_region]
    inicio = sumar_anios(hoy, -ANIOS_DE_HISTORIA)
    tramos = tramos_anuales(inicio, hoy + timedelta(days=1))

    with ThreadPoolExecutor(max_workers=4) as ejecutor:
        partes = list(ejecutor.map(lambda tramo: descargar_tramo(region["caja"], *tramo), tramos))

    partes = [p for p in partes if not p.empty]
    if not partes:
        return pd.DataFrame()
    datos = pd.concat(partes, ignore_index=True).drop_duplicates(subset="id")
    return limpiar_datos(datos, region)


# ---------------------------------------------------------------------------
# 4. FUNCIONES DE GRÁFICAS
# ---------------------------------------------------------------------------
def mapa_sismos(datos, centro, zoom, altura=560):
    """Mapa interactivo: el tamaño del punto es la magnitud y el color la profundidad."""
    datos = datos.nlargest(MAX_PUNTOS_MAPA, "magnitud").sort_values("magnitud").copy()  # los grandes quedan encima
    datos["tamano"] = (datos["magnitud"] - 1.5).clip(lower=0.5) ** 2
    figura = px.scatter_map(
        datos, lat="latitude", lon="longitude", size="tamano", size_max=24,
        color="categoria_profundidad", color_discrete_map=COLORES_PROFUNDIDAD,
        category_orders={"categoria_profundidad": list(COLORES_PROFUNDIDAD)},
        hover_name="lugar", custom_data=["fecha_texto", "magnitud", "profundidad"],
        center={"lat": centro[0], "lon": centro[1]}, zoom=zoom,
        map_style="carto-positron", opacity=0.85, height=altura,
    )
    figura.update_traces(hovertemplate="<b>%{hovertext}</b><br>Magnitud %{customdata[1]}"
                                       "<br>Profundidad %{customdata[2]} km<br>%{customdata[0]}<extra></extra>")
    figura.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(title="Profundidad", x=0.01, y=0.99, bgcolor="rgba(252,252,251,0.9)",
                    font=dict(color="#0b0b0b")),
    )
    return figura


def estilo_barras(figura):
    figura.update_layout(barcornerradius=4, bargap=0.25, showlegend=False,
                         margin=dict(l=10, r=10, t=10, b=10))
    figura.update_yaxes(gridcolor="rgba(137,135,129,0.25)")
    return figura


# ---------------------------------------------------------------------------
# 5. BARRA LATERAL (FILTROS)
# ---------------------------------------------------------------------------
hoy = date.today()
inicio_historia = sumar_anios(hoy, -ANIOS_DE_HISTORIA)

with st.sidebar:
    st.header("🔎 Filtros")
    nombre_region = st.selectbox("Región", list(REGIONES))
    region = REGIONES[nombre_region]
    solo_pais = st.checkbox(f"Solo sismos dentro de {nombre_region.split(' (')[0]}", value=True,
                            help="El USGS consulta un rectángulo en el mapa, así que trae también "
                                 "sismos de países vecinos. Desmarca para verlos.")
    rango = st.date_input("Rango de fechas", value=(inicio_historia, hoy),
                          min_value=inicio_historia, max_value=hoy, format="DD/MM/YYYY")
    magnitud_minima = st.slider("Magnitud mínima", MAGNITUD_MINIMA_API, 9.0, MAGNITUD_MINIMA_API, 0.1)
    profundidad = st.slider("Profundidad (km)", 0, 700, (0, 700), 10)
    if st.button("🔄 Actualizar datos", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.caption("Datos: [Catálogo de sismos del USGS](https://earthquake.usgs.gov/earthquakes/search/) "
               "(dominio público). Se consultan en vivo y se refrescan cada hora.")

fecha_inicio, fecha_fin = (rango if len(rango) == 2 else (rango[0], hoy))


# ---------------------------------------------------------------------------
# 6. ENCABEZADO Y CARGA DE DATOS
# ---------------------------------------------------------------------------
st.title("🌎 Explorador de Sismos")
st.markdown("¿Qué tanto tiembla donde vives? Consulta los sismos **reales** registrados en los "
            f"últimos {ANIOS_DE_HISTORIA} años: dónde ocurrieron, qué tan fuertes fueron y cuántos "
            "ha habido cerca de tu ciudad.")

try:
    with st.spinner(f"Descargando {ANIOS_DE_HISTORIA} años de sismos de {nombre_region}…"):
        datos = cargar_sismos(nombre_region, hoy)
except Exception:
    st.error("No se pudo conectar con el USGS en este momento. Intenta de nuevo en unos minutos "
             "con el botón **🔄 Actualizar datos**.")
    st.stop()

if datos.empty:
    st.info("No hay sismos registrados para esta región en el periodo consultado.")
    st.stop()

# Aplicar los filtros de la barra lateral
filtrados = datos[
    datos["fecha"].dt.date.between(fecha_inicio, fecha_fin)
    & (datos["magnitud"] >= magnitud_minima)
    & datos["profundidad"].between(profundidad[0], profundidad[1])
]
if solo_pais:
    filtrados = filtrados[filtrados["en_pais"]]

# Indicadores principales
col1, col2, col3, col4 = st.columns(4)
col1.metric("Sismos encontrados", formatear_numero(len(filtrados)))
if filtrados.empty:
    st.info("Ningún sismo cumple con los filtros. Prueba bajando la magnitud mínima o ampliando las fechas.")
    st.stop()

mas_fuerte = filtrados.loc[filtrados["magnitud"].idxmax()]
ultimo = filtrados.loc[filtrados["fecha"].idxmax()]
ahora_local = pd.Timestamp.now(tz=region["zona_horaria"]).tz_localize(None)
dias_desde_ultimo = max(0, (ahora_local - ultimo["fecha"]).days)

col2.metric("Magnitud máxima", formatear_numero(mas_fuerte["magnitud"], 1))
col3.metric("Magnitud promedio", formatear_numero(filtrados["magnitud"].mean(), 1))
col4.metric("Último sismo", ultimo["fecha"].strftime("%d/%m/%Y"),
            "hoy" if dias_desde_ultimo == 0 else ("ayer" if dias_desde_ultimo == 1 else f"hace {dias_desde_ultimo} días"), delta_color="off", delta_arrow="off")

st.info(f"💥 El sismo más fuerte del periodo fue de **magnitud {formatear_numero(mas_fuerte['magnitud'], 1)}**, "
        f"el {mas_fuerte['fecha'].day} de {MESES[mas_fuerte['fecha'].month - 1]} de {mas_fuerte['fecha'].year}, "
        f"{mas_fuerte['lugar']} (profundidad {formatear_numero(mas_fuerte['profundidad'], 0)} km).")


# ---------------------------------------------------------------------------
# 7. PESTAÑAS
# ---------------------------------------------------------------------------
tab_mapa, tab_tendencias, tab_ciudad, tab_datos = st.tabs(
    ["🗺️ Mapa", "📈 Tendencias", "🏙️ Mi ciudad", "📋 Datos"])

# ---- 7.1 Mapa ----------------------------------------------------------------
with tab_mapa:
    if len(filtrados) > MAX_PUNTOS_MAPA:
        st.caption(f"El mapa muestra los {formatear_numero(MAX_PUNTOS_MAPA)} sismos más fuertes de "
                   f"{formatear_numero(len(filtrados))}. Sube la magnitud mínima para ver menos puntos.")
    st.plotly_chart(mapa_sismos(filtrados, region["centro"], region["zoom"]), width="stretch")
    st.caption("Cada punto es un sismo: más grande = más fuerte. Los sismos superficiales (0–70 km) "
               "suelen sentirse más y causar más daño que los profundos de la misma magnitud.")

    st.subheader("Los 10 sismos más fuertes")
    top = filtrados.nlargest(10, "magnitud")
    st.dataframe(
        top[["fecha", "magnitud", "profundidad", "lugar", "enlace"]].rename(columns={
            "fecha": "Fecha (hora local)", "magnitud": "Magnitud", "profundidad": "Profundidad (km)",
            "lugar": "Lugar", "enlace": "Detalle"}),
        hide_index=True, width="stretch",
        column_config={
            "Fecha (hora local)": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
            "Magnitud": st.column_config.NumberColumn(format="%.1f"),
            "Profundidad (km)": st.column_config.NumberColumn(format="%.0f"),
            "Detalle": st.column_config.LinkColumn(display_text="Ver en USGS"),
        },
    )

# ---- 7.2 Tendencias ----------------------------------------------------------
with tab_tendencias:
    por_anio = filtrados.groupby(filtrados["fecha"].dt.year).size().reset_index(name="sismos")
    por_anio.columns = ["anio", "sismos"]
    por_mes = filtrados.set_index("fecha").sort_index().resample("MS").size().reset_index(name="sismos")
    mes_pico = por_mes.loc[por_mes["sismos"].idxmax()]
    anio_pico = por_anio.loc[por_anio["sismos"].idxmax()]
    pct_superficiales = (filtrados["categoria_profundidad"] == list(COLORES_PROFUNDIDAD)[0]).mean() * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Año con más sismos", int(anio_pico["anio"]), f"{formatear_numero(anio_pico['sismos'])} sismos",
              delta_color="off", delta_arrow="off")
    c2.metric("Mes con más sismos", f"{MESES[mes_pico['fecha'].month - 1].capitalize()} {mes_pico['fecha'].year}",
              f"{formatear_numero(mes_pico['sismos'])} sismos", delta_color="off", delta_arrow="off")
    c3.metric("Sismos superficiales", f"{formatear_numero(pct_superficiales, 0)} %",
              "a menos de 70 km de profundidad", delta_color="off", delta_arrow="off")

    izquierda, derecha = st.columns(2)
    with izquierda:
        st.subheader("Sismos por año")
        figura = px.bar(por_anio, x="anio", y="sismos", labels={"anio": "Año", "sismos": "Número de sismos"})
        figura.update_traces(marker_color=AZUL, hovertemplate="%{x}: %{y} sismos<extra></extra>")
        figura.update_xaxes(dtick=1)
        st.plotly_chart(estilo_barras(figura), width="stretch")
        st.caption("El primer y el último año pueden estar incompletos según el rango de fechas elegido.")

    with derecha:
        st.subheader("Sismos por mes")
        figura = px.line(por_mes, x="fecha", y="sismos", labels={"fecha": "", "sismos": "Número de sismos"})
        figura.update_traces(line=dict(color=AZUL, width=2), hovertemplate="%{x|%m/%Y}: %{y} sismos<extra></extra>")
        figura.add_scatter(x=[mes_pico["fecha"]], y=[mes_pico["sismos"]], mode="markers+text",
                           marker=dict(color=NARANJA, size=9), text=[f"Pico: {mes_pico['sismos']}"],
                           textposition="top center", hoverinfo="skip", showlegend=False)
        figura.update_layout(margin=dict(l=10, r=10, t=10, b=10), hovermode="x")
        figura.update_yaxes(gridcolor="rgba(137,135,129,0.25)")
        st.plotly_chart(figura, width="stretch")
        st.caption("Los picos suelen ser un sismo grande seguido de muchas réplicas.")

    izquierda, derecha = st.columns(2)
    with izquierda:
        st.subheader("¿Qué tan fuertes son?")
        escala_log = st.toggle("Escala logarítmica", value=False)
        figura = px.histogram(filtrados, x="magnitud", labels={"magnitud": "Magnitud"})
        figura.update_traces(xbins=dict(size=0.2), marker_color=AZUL,
                             hovertemplate="Magnitud %{x}: %{y} sismos<extra></extra>")
        figura.update_yaxes(title="Número de sismos", type="log" if escala_log else "linear")
        figura.update_layout(bargap=0.08)
        st.plotly_chart(estilo_barras(figura), width="stretch")
        st.caption("Los sismos pequeños son muchísimo más frecuentes: por cada sismo de magnitud 5 hay, "
                   "aproximadamente, unos 10 de magnitud 4 (ley de Gutenberg-Richter). Activa la escala "
                   "logarítmica para verlo como una línea recta.")

    with derecha:
        st.subheader("¿A qué profundidad ocurren?")
        conteo = (filtrados["categoria_profundidad"].value_counts()
                  .reindex(list(COLORES_PROFUNDIDAD), fill_value=0).reset_index())
        conteo.columns = ["categoria", "sismos"]
        conteo["etiqueta"] = [f"{formatear_numero(n)} ({formatear_numero(n / len(filtrados) * 100, 0)} %)"
                              for n in conteo["sismos"]]
        figura = px.bar(conteo, x="sismos", y="categoria", orientation="h", text="etiqueta",
                        color="categoria", color_discrete_map=COLORES_PROFUNDIDAD,
                        labels={"sismos": "Número de sismos", "categoria": ""})
        figura.update_traces(textposition="outside", cliponaxis=False,
                             hovertemplate="%{y}: %{x} sismos<extra></extra>")
        figura.update_yaxes(categoryorder="array", categoryarray=list(reversed(COLORES_PROFUNDIDAD)))
        figura.update_xaxes(range=[0, conteo["sismos"].max() * 1.3], showgrid=False)
        st.plotly_chart(estilo_barras(figura), width="stretch")

# ---- 7.3 Mi ciudad -----------------------------------------------------------
with tab_ciudad:
    st.subheader("¿Cuántos sismos ha habido cerca de mi ciudad?")
    st.caption("Aquí se cuentan todos los sismos dentro del círculo, incluso los de países o estados "
               "vecinos, porque también se pueden sentir en la ciudad.")
    a, b = st.columns([2, 3])
    ciudad = a.selectbox("Ciudad", list(region["ciudades"]))
    radio = b.slider("Distancia alrededor de la ciudad (km)", 25, 500, 100, 25)

    lat_c, lon_c = region["ciudades"][ciudad]
    # Para esta pestaña usamos todos los sismos de la región (también los de países vecinos),
    # porque un sismo al otro lado de la frontera también se puede sentir en la ciudad.
    cerca = datos[
        datos["fecha"].dt.date.between(fecha_inicio, fecha_fin)
        & (datos["magnitud"] >= magnitud_minima)
        & datos["profundidad"].between(profundidad[0], profundidad[1])
    ].copy()
    cerca["distancia"] = distancia_km(lat_c, lon_c, cerca["latitude"], cerca["longitude"])
    cerca = cerca[cerca["distancia"] <= radio]

    anios_periodo = max((fecha_fin - fecha_inicio).days / 365.25, 1 / 12)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Sismos a menos de {radio} km", formatear_numero(len(cerca)))
    m2.metric("Promedio por año", formatear_numero(len(cerca) / anios_periodo, 1))
    if not cerca.empty:
        fuerte_cerca = cerca.loc[cerca["magnitud"].idxmax()]
        cercano = cerca.loc[cerca["distancia"].idxmin()]
        m3.metric("El más fuerte", f"M {formatear_numero(fuerte_cerca['magnitud'], 1)}",
                  fuerte_cerca["fecha"].strftime("%d/%m/%Y"), delta_color="off", delta_arrow="off")
        m4.metric("El más cercano", f"{formatear_numero(cercano['distancia'], 0)} km",
                  f"M {formatear_numero(cercano['magnitud'], 1)} · {cercano['fecha']:%d/%m/%Y}", delta_color="off", delta_arrow="off")

    # Mapa con la ciudad, el círculo de búsqueda y los sismos que quedaron adentro
    zoom = float(np.clip(np.log2(12000 / radio), 3, 10))
    if cerca.empty:
        figura = go.Figure()
        figura.update_layout(map=dict(style="carto-positron", center=dict(lat=lat_c, lon=lon_c), zoom=zoom),
                             height=480, margin=dict(l=0, r=0, t=0, b=0))
        st.info(f"No hay sismos registrados a menos de {radio} km de {ciudad} con los filtros actuales. "
                "Prueba ampliando la distancia o bajando la magnitud mínima.")
    else:
        figura = mapa_sismos(cerca, (lat_c, lon_c), zoom, altura=480)
    circulo_lat, circulo_lon = puntos_circulo(lat_c, lon_c, radio)
    figura.add_trace(go.Scattermap(lat=circulo_lat, lon=circulo_lon, mode="lines",
                                   line=dict(color=GRIS, width=2), hoverinfo="skip", name=f"{radio} km"))
    figura.add_trace(go.Scattermap(lat=[lat_c], lon=[lon_c], mode="markers", name=ciudad,
                                   marker=dict(size=14, color=NARANJA), hovertemplate=f"<b>{ciudad}</b><extra></extra>"))
    st.plotly_chart(figura, width="stretch")

    if not cerca.empty:
        st.markdown(f"**Los sismos más fuertes a menos de {radio} km de {ciudad}**")
        tabla_cerca = cerca.nlargest(10, "magnitud")[["fecha", "magnitud", "profundidad", "distancia", "lugar"]]
        st.dataframe(
            tabla_cerca.rename(columns={"fecha": "Fecha (hora local)", "magnitud": "Magnitud",
                                        "profundidad": "Profundidad (km)", "distancia": "Distancia (km)",
                                        "lugar": "Lugar"}),
            hide_index=True, width="stretch",
            column_config={
                "Fecha (hora local)": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                "Magnitud": st.column_config.NumberColumn(format="%.1f"),
                "Profundidad (km)": st.column_config.NumberColumn(format="%.0f"),
                "Distancia (km)": st.column_config.NumberColumn(format="%.0f"),
            },
        )
    st.caption("ℹ️ Información con fines educativos. Para datos oficiales y alertas consulta la entidad "
               "sismológica de cada país (en Colombia, el [Servicio Geológico Colombiano](https://www.sgc.gov.co/sismos)).")

# ---- 7.4 Datos ---------------------------------------------------------------
with tab_datos:
    busqueda = st.text_input("Buscar por lugar", placeholder="Ej.: Bucaramanga, Ridgecrest, Tokio…")
    tabla = filtrados
    if busqueda:
        tabla = tabla[tabla["lugar"].str.contains(busqueda, case=False, regex=False)]
    tabla = tabla[["fecha", "magnitud", "magType", "clasificacion", "profundidad", "lugar",
                   "latitude", "longitude", "estado", "enlace"]].rename(columns={
        "fecha": "Fecha (hora local)", "magnitud": "Magnitud", "magType": "Tipo de magnitud",
        "clasificacion": "Clasificación", "profundidad": "Profundidad (km)", "lugar": "Lugar",
        "latitude": "Latitud", "longitude": "Longitud", "estado": "Estado", "enlace": "Detalle"})

    st.caption(f"{formatear_numero(len(tabla))} sismos. Haz clic en el título de una columna para ordenar.")
    st.dataframe(
        tabla, hide_index=True, width="stretch", height=520,
        column_config={
            "Fecha (hora local)": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
            "Magnitud": st.column_config.NumberColumn(format="%.1f"),
            "Profundidad (km)": st.column_config.NumberColumn(format="%.0f"),
            "Latitud": st.column_config.NumberColumn(format="%.3f"),
            "Longitud": st.column_config.NumberColumn(format="%.3f"),
            "Detalle": st.column_config.LinkColumn(display_text="Ver en USGS"),
        },
    )
    st.download_button("⬇️ Descargar estos datos (CSV)", tabla.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"sismos_{nombre_region.split(' (')[0].lower()}.csv", mime="text/csv")

# ---------------------------------------------------------------------------
# 8. PIE DE PÁGINA
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Fuente: [USGS Earthquake Hazards Program](https://earthquake.usgs.gov/) — catálogo ComCat, datos de "
    f"dominio público consultados en vivo (sismos de magnitud {formatear_numero(MAGNITUD_MINIMA_API, 1)} o más). "
    "Fuera de EE. UU. el USGS registra sobre todo los sismos de magnitud 4 o más; los más pequeños pueden "
    "no aparecer. Las horas están en la hora local de cada región."
)
