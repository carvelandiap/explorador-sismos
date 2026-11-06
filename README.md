# 🌎 Explorador de Sismos

Página web hecha en **Python con Streamlit** que consulta sismos **reales** de los últimos 10 años
en el catálogo público del **USGS** (Servicio Geológico de EE. UU.). No necesita claves, cuentas ni registro
para consultarla.

## ¿Qué problema resuelve?

Una persona quiere saber **qué tanto tiembla en su país o cerca de su ciudad**: dónde ocurren los sismos,
qué tan fuertes han sido, a qué profundidad y cómo ha cambiado la actividad en los últimos años.
En vez de buscar en catálogos técnicos en inglés, la app le responde eso con mapas, gráficas y una
consulta por ciudad, en español.

## ¿Qué se puede hacer?

| Sección | Qué muestra |
|---|---|
| **Filtros** (barra lateral) | Región (Colombia, California, Alaska, Puerto Rico, México, Chile, Perú, Japón), rango de fechas dentro de los últimos 10 años, magnitud mínima y profundidad |
| **Indicadores** | Total de sismos, magnitud máxima y promedio, último sismo y el sismo más fuerte del periodo |
| **🗺️ Mapa** | Cada sismo como un punto: tamaño = magnitud, color = profundidad. Tabla con los 10 más fuertes y enlace a su ficha en el USGS |
| **📈 Tendencias** | Sismos por año y por mes, distribución de magnitudes (con escala logarítmica opcional) y por profundidad |
| **🏙️ Mi ciudad** | Eliges una ciudad y una distancia, y ves cuántos sismos hubo alrededor, el más fuerte y el más cercano |
| **📋 Datos** | Tabla completa con buscador por lugar y botón para descargar CSV |

## De dónde salen los datos

- API: `https://earthquake.usgs.gov/fdsnws/event/1/query` (formato CSV, sin clave).
- Se pide **año por año**, porque el USGS entrega máximo 20.000 sismos por consulta.
- Los datos se guardan en caché 1 hora (`@st.cache_data`) para que la página sea rápida.
- Limitación: fuera de EE. UU. el USGS registra sobre todo sismos de magnitud 4 o más, así que en Colombia
  aparecen menos sismos pequeños que en California o Alaska. Para datos oficiales de Colombia está el
  [Servicio Geológico Colombiano](https://www.sgc.gov.co/sismos).

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `app.py` | La aplicación (descarga, limpieza, gráficas y página) |
| `regiones.py` | Configuración de cada región y sus ciudades |
| `requirements.txt` | Librerías que necesita la app |

---

## 🚀 Cómo publicarla gratis (para que tenga un link público)

### 1. Subir el código a GitHub
1. Crea una cuenta en [github.com](https://github.com) (si no tienes).
2. Arriba a la derecha: **+ → New repository**.
3. Nombre: por ejemplo `explorador-sismos`. Déjalo **Public** y dale **Create repository**.
4. En la página del repositorio, haz clic en **uploading an existing file** (o **Add file → Upload files**).
5. Arrastra `app.py`, `regiones.py`, `requirements.txt` y `README.md`, y dale **Commit changes**.

### 2. Publicar en Streamlit Community Cloud
1. Entra a [share.streamlit.io](https://share.streamlit.io) e inicia sesión **con tu cuenta de GitHub**.
2. Clic en **Create app** → **Deploy a public app from GitHub**.
3. Elige tu repositorio `explorador-sismos`, rama `main` y archivo principal `app.py`.
4. (Opcional) En **App URL** ponle un nombre bonito, por ejemplo `sismos-colombia`.
5. Clic en **Deploy** y espera 2–3 minutos.

Listo: tendrás un link como `https://sismos-colombia.streamlit.app` que **cualquiera puede abrir sin
registrarse**. Tu cuenta de GitHub solo se usa para publicar.

> 💡 **Antes de presentar:** las apps gratuitas se "duermen" si pasan 12 horas sin visitas. Ábrela unos
> minutos antes; si sale el mensaje de que está dormida, dale al botón para despertarla y espera un momento.

> ✏️ **Para hacer cambios:** edita el archivo en GitHub (ícono del lápiz) y guarda. La app se actualiza sola.

---

## 💻 Cómo correrla en tu computador

```bash
pip install -r requirements.txt
streamlit run app.py
```

Se abre en el navegador en `http://localhost:8501`.

---

## 🎤 Guía rápida para explicar el código en clase

El archivo `app.py` está dividido en secciones numeradas:

1. **Configuración general**: título de la página, URL de la API y colores.
2. **Funciones de ayuda**: manejo de fechas, formato de números, traducción de los lugares al español
   y la fórmula de **Haversine** para calcular distancias sobre la Tierra.
3. **Descarga y limpieza**: `descargar_tramo` llama a la API con `requests` (con reintentos),
   `limpiar_datos` usa `pandas` para convertir fechas a hora local y clasificar los sismos,
   y `cargar_sismos` descarga los 10 años en paralelo y guarda el resultado en caché.
4. **Funciones de gráficas**: el mapa con `plotly`.
5. **Barra lateral**: los filtros (`st.selectbox`, `st.date_input`, `st.slider`).
6. **Encabezado**: carga de datos, filtros e indicadores (`st.metric`).
7. **Pestañas**: Mapa, Tendencias, Mi ciudad y Datos (`st.tabs`).
8. **Pie de página**: fuente de los datos.

Fuente de datos: [USGS Earthquake Hazards Program](https://earthquake.usgs.gov/) — dominio público.
