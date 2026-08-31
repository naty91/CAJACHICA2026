
import streamlit as st
import pandas as pd
import numpy as np
import json
import re
from datetime import date, datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

st.set_page_config(
    page_title="Caja Chica - Cuadre Automático",
    page_icon="💵",
    layout="wide"
)

# ============================================================
# ESTADO DE SESIÓN
# ============================================================
defaults = {
    "movimientos": [],
    "fondo_inicial": 500.00,
    "efectivo_contado": 0.00,
    "vales_pendientes": 0.00,
    "otros_soportes": 0.00,
    "nombre_caja": "Caja Chica",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def money(v):
    return f"${float(v):,.2f}"

def parse_number(v):
    if pd.isna(v):
        return None
    if isinstance(v, (int, float, np.number)):
        return float(v)
    s = str(v).strip()
    if not s or s.lower() in ["nan", "none", "-"]:
        return None
    s = s.replace("$", "").replace(" ", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    s = re.sub(r"[^0-9\.\-]", "", s)
    try:
        return float(s)
    except:
        return None

def norm(v):
    return str(v).strip().upper() if not pd.isna(v) else ""

# ============================================================
# LECTURA DE PLANILLA
# ============================================================
def read_raw(uploaded):
    name = uploaded.name.lower()
    uploaded.seek(0)
    if name.endswith(".csv"):
        return pd.read_csv(uploaded, header=None)
    return pd.read_excel(uploaded, header=None)

def detect_template(raw):
    saldo_inicial = None
    header_row = None

    for i in range(min(len(raw), 25)):
        row_vals = raw.iloc[i].tolist()
        row_text = [norm(x) for x in row_vals]
        joined = " | ".join(row_text)

        if "SALDO INICIAL" in joined:
            nums = [parse_number(x) for x in row_vals]
            nums = [x for x in nums if x is not None]
            if nums:
                saldo_inicial = nums[-1]

        hits = 0
        for key in ["FECHA", "DESCRIPCION", "DESCRIPCIÓN", "PERSONA", "VALE", "FACTURA", "VALOR"]:
            if any(key in cell for cell in row_text):
                hits += 1
        if hits >= 3:
            header_row = i
            break

    return saldo_inicial, header_row

def build_df(raw, header_row):
    headers = []
    used = {}
    for j, cell in enumerate(raw.iloc[header_row].tolist()):
        name = norm(cell) or f"COLUMNA_{j+1}"
        if name in used:
            used[name] += 1
            name = f"{name}_{used[name]}"
        else:
            used[name] = 1
        headers.append(name)

    df = raw.iloc[header_row+1:].copy()
    df.columns = headers
    df = df.dropna(how="all").reset_index(drop=True)
    return df

def find_col(columns, variants):
    for c in columns:
        n = norm(c)
        for v in variants:
            if v in n:
                return c
    return None

def importar_planilla(uploaded):
    raw = read_raw(uploaded)
    saldo_inicial, header_row = detect_template(raw)

    if header_row is None:
        raise ValueError(
            "No pude detectar los encabezados. La planilla debe contener columnas como "
            "FECHA, DESCRIPCION, PERSONA, VALE/FACTURA y VALOR."
        )

    df = build_df(raw, header_row)
    c_fecha = find_col(df.columns, ["FECHA"])
    c_desc = find_col(df.columns, ["DESCRIPCION", "DESCRIPCIÓN"])
    c_persona = find_col(df.columns, ["PERSONA"])
    c_vale = find_col(df.columns, ["VALE/FACTURA", "VALE", "FACTURA"])
    c_valor = find_col(df.columns, ["VALOR"])

    if c_valor is None:
        raise ValueError("No pude detectar la columna VALOR.")

    movimientos = []
    for _, row in df.iterrows():
        valor = parse_number(row[c_valor])
        if valor is None or valor == 0:
            continue

        fecha_val = row[c_fecha] if c_fecha else ""
        if isinstance(fecha_val, (pd.Timestamp, datetime)):
            fecha_txt = fecha_val.strftime("%d/%m/%Y")
        else:
            fecha_txt = str(fecha_val).strip()

        movimientos.append({
            "FECHA": fecha_txt,
            "DESCRIPCION": str(row[c_desc]).strip() if c_desc and not pd.isna(row[c_desc]) else "",
            "PERSONA": str(row[c_persona]).strip() if c_persona and not pd.isna(row[c_persona]) else "",
            "VALE/FACTURA": str(row[c_vale]).strip() if c_vale and not pd.isna(row[c_vale]) else "",
            "VALOR": float(valor),
        })

    return saldo_inicial, movimientos

# ============================================================
# RESPALDO / RESTAURACIÓN
# ============================================================
def generar_respaldo():
    data = {
        "version": 1,
        "fecha_respaldo": datetime.now().isoformat(timespec="seconds"),
        "nombre_caja": st.session_state.nombre_caja,
        "fondo_inicial": float(st.session_state.fondo_inicial),
        "efectivo_contado": float(st.session_state.efectivo_contado),
        "vales_pendientes": float(st.session_state.vales_pendientes),
        "otros_soportes": float(st.session_state.otros_soportes),
        "movimientos": st.session_state.movimientos,
    }
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

def restaurar_respaldo(uploaded):
    uploaded.seek(0)
    data = json.loads(uploaded.read().decode("utf-8"))

    required = ["fondo_inicial", "movimientos"]
    if not all(k in data for k in required):
        raise ValueError("El archivo no parece ser un respaldo válido de esta aplicación.")

    st.session_state.nombre_caja = data.get("nombre_caja", "Caja Chica")
    st.session_state.fondo_inicial = float(data.get("fondo_inicial", 500.0))
    st.session_state.efectivo_contado = float(data.get("efectivo_contado", 0.0))
    st.session_state.vales_pendientes = float(data.get("vales_pendientes", 0.0))
    st.session_state.otros_soportes = float(data.get("otros_soportes", 0.0))
    st.session_state.movimientos = data.get("movimientos", [])

# ============================================================
# PDF
# ============================================================
def generar_pdf(detalle, fondo, total_gastos, saldo_teorico,
                efectivo, vales, otros, soporte_fisico, diferencia, nombre_caja):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=1.2*cm,
        leftMargin=1.2*cm,
        topMargin=1.2*cm,
        bottomMargin=1.2*cm,
        title="Cuadre de Caja"
    )

    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloCaja", parent=styles["Title"],
        alignment=TA_CENTER, fontSize=18, leading=22, spaceAfter=8
    )
    subtitulo = ParagraphStyle(
        "SubtituloCaja", parent=styles["BodyText"],
        alignment=TA_CENTER, fontSize=10, leading=13, spaceAfter=10
    )

    elementos = [
        Paragraph("CUADRE AUTOMÁTICO DE CAJA CHICA", titulo),
        Paragraph(
            f"{nombre_caja} · Fecha de emisión: {date.today().strftime('%d/%m/%Y')}",
            subtitulo
        )
    ]

    if abs(diferencia) < 0.005:
        estado = "CAJA CUADRADA"
        bg = colors.HexColor("#D9EAD3")
    elif diferencia > 0:
        estado = f"SOBRANTE: {money(diferencia)}"
        bg = colors.HexColor("#FCE5CD")
    else:
        estado = f"FALTANTE: {money(abs(diferencia))}"
        bg = colors.HexColor("#F4CCCC")

    resumen = [
        ["CONCEPTO", "VALOR", "CONCEPTO", "VALOR"],
        ["Fondo inicial", money(fondo), "Total gastos", money(total_gastos)],
        ["Saldo teórico", money(saldo_teorico), "Efectivo contado", money(efectivo)],
        ["Vales pendientes", money(vales), "Otros soportes", money(otros)],
        ["Soporte físico", money(soporte_fisico), "Diferencia", money(diferencia)],
        ["ESTADO DEL CUADRE", estado, "", ""],
    ]

    t = Table(resumen, colWidths=[4.4*cm, 3.3*cm, 4.4*cm, 3.3*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (1,1), (1,-1), "RIGHT"),
        ("ALIGN", (3,1), (3,-1), "RIGHT"),
        ("SPAN", (1,5), (3,5)),
        ("BACKGROUND", (0,5), (3,5), bg),
        ("FONTNAME", (0,5), (1,5), "Helvetica-Bold"),
        ("ALIGN", (1,5), (3,5), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    elementos += [t, Spacer(1, 0.45*cm), Paragraph("DETALLE DE MOVIMIENTOS", styles["Heading2"])]

    if detalle.empty:
        elementos.append(Paragraph("No existen movimientos registrados.", styles["BodyText"]))
    else:
        data = [["FECHA", "DESCRIPCION", "PERSONA", "VALE/FACTURA", "VALOR", "SALDO"]]
        for _, row in detalle.iterrows():
            data.append([
                str(row.get("FECHA", "")),
                str(row.get("DESCRIPCION", "")),
                str(row.get("PERSONA", "")),
                str(row.get("VALE/FACTURA", "")),
                money(row.get("VALOR", 0)),
                money(row.get("SALDO", 0)),
            ])
        td = Table(
            data, repeatRows=1,
            colWidths=[2.5*cm, 7.6*cm, 4.2*cm, 3.5*cm, 3.2*cm, 3.2*cm]
        )
        td.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#D9EAF7")),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("GRID", (0,0), (-1,-1), 0.4, colors.grey),
            ("ALIGN", (4,1), (-1,-1), "RIGHT"),
            ("FONTSIZE", (0,0), (-1,-1), 8.5),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        elementos.append(td)

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

# ============================================================
# INTERFAZ
# ============================================================
st.title("💵 Caja Chica - Cuadre Automático")
st.caption("Registro directo, carga por planilla, respaldo recuperable, Excel y PDF.")

# ---------- RESTAURAR RESPALDO ARRIBA ----------
with st.expander("🔄 Recuperar caja desde un respaldo"):
    respaldo_subido = st.file_uploader(
        "Carga un respaldo .json generado por esta misma aplicación",
        type=["json"],
        key="backup_upload"
    )
    if respaldo_subido is not None:
        if st.button("Restaurar respaldo", use_container_width=True):
            try:
                restaurar_respaldo(respaldo_subido)
                st.success("Respaldo restaurado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"No pude restaurar el respaldo: {e}")

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("Configuración de caja")
    st.session_state.nombre_caja = st.text_input(
        "Nombre / identificación de caja",
        value=st.session_state.nombre_caja
    )
    st.session_state.fondo_inicial = st.number_input(
        "Fondo inicial ($)",
        min_value=0.0,
        value=float(st.session_state.fondo_inicial),
        step=0.01,
        format="%.2f"
    )
    st.session_state.efectivo_contado = st.number_input(
        "Efectivo contado al cierre ($)",
        min_value=0.0,
        value=float(st.session_state.efectivo_contado),
        step=0.01,
        format="%.2f"
    )
    st.session_state.vales_pendientes = st.number_input(
        "Vales pendientes no registrados ($)",
        min_value=0.0,
        value=float(st.session_state.vales_pendientes),
        step=0.01,
        format="%.2f"
    )
    st.session_state.otros_soportes = st.number_input(
        "Otros soportes ($)",
        min_value=0.0,
        value=float(st.session_state.otros_soportes),
        step=0.01,
        format="%.2f"
    )

# ---------- ENTRADA DE MOVIMIENTOS ----------
tab_directo, tab_planilla = st.tabs(["➕ Registro directo", "📤 Cargar planilla"])

with tab_directo:
    st.subheader("Registrar movimiento")
    with st.form("form_movimiento", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha", value=date.today())
        descripcion = c2.text_input("Descripción", placeholder="Ej. Compra de llaves")

        c3, c4 = st.columns(2)
        persona = c3.text_input("Persona", placeholder="Ej. Freddy")
        comprobante = c4.text_input("Vale / Factura", placeholder="Ej. 235")

        valor = st.number_input("Valor del gasto ($)", min_value=0.0, step=0.01, format="%.2f")
        agregar = st.form_submit_button("➕ Registrar gasto", use_container_width=True)

        if agregar:
            if valor <= 0:
                st.warning("Ingresa un valor mayor a 0.")
            elif not descripcion.strip():
                st.warning("Ingresa una descripción.")
            else:
                st.session_state.movimientos.append({
                    "FECHA": fecha.strftime("%d/%m/%Y"),
                    "DESCRIPCION": descripcion.strip(),
                    "PERSONA": persona.strip(),
                    "VALE/FACTURA": comprobante.strip(),
                    "VALOR": float(valor)
                })
                st.success("Movimiento registrado.")
                st.rerun()

with tab_planilla:
    st.subheader("Cargar planilla de movimientos")
    st.write(
        "Puedes cargar una planilla con **SALDO INICIAL** y las columnas "
        "**FECHA, DESCRIPCION, PERSONA, VALE/FACTURA y VALOR**."
    )
    planilla = st.file_uploader(
        "Selecciona Excel o CSV",
        type=["xlsx", "xls", "csv"],
        key="planilla_upload"
    )
    modo = st.radio(
        "Qué hacer con los movimientos de la planilla",
        ["Agregar a los movimientos actuales", "Reemplazar los movimientos actuales"],
        horizontal=True
    )
    if planilla is not None and st.button("Importar planilla", use_container_width=True):
        try:
            saldo_detectado, movs = importar_planilla(planilla)
            if not movs:
                st.warning("No encontré movimientos con valor.")
            else:
                if modo.startswith("Reemplazar"):
                    st.session_state.movimientos = movs
                else:
                    st.session_state.movimientos.extend(movs)

                if saldo_detectado is not None:
                    st.session_state.fondo_inicial = float(saldo_detectado)

                st.success(
                    f"Planilla importada: {len(movs)} movimiento(s). "
                    + (f"Fondo detectado: {money(saldo_detectado)}." if saldo_detectado is not None else "")
                )
                st.rerun()
        except Exception as e:
            st.error(f"No pude importar la planilla: {e}")

# ============================================================
# CÁLCULOS
# ============================================================
df = pd.DataFrame(st.session_state.movimientos)

if df.empty:
    detalle = pd.DataFrame(columns=["FECHA", "DESCRIPCION", "PERSONA", "VALE/FACTURA", "VALOR", "SALDO"])
    total_gastos = 0.0
else:
    df["VALOR"] = pd.to_numeric(df["VALOR"], errors="coerce").fillna(0.0)
    total_gastos = float(df["VALOR"].sum())
    detalle = df.copy()
    detalle["SALDO"] = float(st.session_state.fondo_inicial) - detalle["VALOR"].cumsum()

saldo_teorico = float(st.session_state.fondo_inicial) - total_gastos
soporte_fisico = (
    float(st.session_state.efectivo_contado)
    + float(st.session_state.vales_pendientes)
    + float(st.session_state.otros_soportes)
)
diferencia = soporte_fisico - saldo_teorico

# ============================================================
# CUADRE
# ============================================================
st.divider()
st.subheader("Cuadre de caja")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Fondo inicial", money(st.session_state.fondo_inicial))
m2.metric("Total gastos", money(total_gastos))
m3.metric("Saldo teórico", money(saldo_teorico))
m4.metric("Soporte físico", money(soporte_fisico))

if abs(diferencia) < 0.005:
    st.success("✅ CAJA CUADRADA")
elif diferencia > 0:
    st.warning(f"⚠️ SOBRANTE DE CAJA: {money(diferencia)}")
else:
    st.error(f"❌ FALTANTE DE CAJA: {money(abs(diferencia))}")

st.write(
    f"**Efectivo:** {money(st.session_state.efectivo_contado)} · "
    f"**Vales pendientes:** {money(st.session_state.vales_pendientes)} · "
    f"**Otros soportes:** {money(st.session_state.otros_soportes)} · "
    f"**Diferencia:** {money(diferencia)}"
)

# ============================================================
# MOVIMIENTOS
# ============================================================
st.divider()
st.subheader("Movimientos registrados")

if detalle.empty:
    st.info("Todavía no hay movimientos.")
else:
    st.dataframe(
        detalle,
        use_container_width=True,
        hide_index=True,
        column_config={
            "VALOR": st.column_config.NumberColumn("VALOR", format="$ %.2f"),
            "SALDO": st.column_config.NumberColumn("SALDO", format="$ %.2f"),
        }
    )

    c_del1, c_del2 = st.columns([3,1])
    opciones = [
        f"{i+1} - {row['FECHA']} - {row['DESCRIPCION']} - {money(row['VALOR'])}"
        for i, row in detalle.iterrows()
    ]
    seleccionado = c_del1.selectbox("Eliminar movimiento", opciones)
    if c_del2.button("🗑️ Eliminar", use_container_width=True):
        idx = opciones.index(seleccionado)
        st.session_state.movimientos.pop(idx)
        st.rerun()

# ============================================================
# DESCARGAS
# ============================================================
st.divider()
st.subheader("Descargas y respaldo")

# Excel
excel = BytesIO()
with pd.ExcelWriter(excel, engine="openpyxl") as writer:
    detalle.to_excel(writer, index=False, sheet_name="CAJA")
    resumen = pd.DataFrame({
        "CONCEPTO": [
            "Nombre de caja",
            "Fondo inicial",
            "Total gastos",
            "Saldo teórico",
            "Efectivo contado",
            "Vales pendientes",
            "Otros soportes",
            "Soporte físico",
            "Diferencia",
        ],
        "VALOR": [
            st.session_state.nombre_caja,
            st.session_state.fondo_inicial,
            total_gastos,
            saldo_teorico,
            st.session_state.efectivo_contado,
            st.session_state.vales_pendientes,
            st.session_state.otros_soportes,
            soporte_fisico,
            diferencia,
        ]
    })
    resumen.to_excel(writer, index=False, sheet_name="RESUMEN")

# PDF
pdf_bytes = generar_pdf(
    detalle,
    st.session_state.fondo_inicial,
    total_gastos,
    saldo_teorico,
    st.session_state.efectivo_contado,
    st.session_state.vales_pendientes,
    st.session_state.otros_soportes,
    soporte_fisico,
    diferencia,
    st.session_state.nombre_caja
)

# Respaldo JSON
backup_bytes = generar_respaldo()

d1, d2, d3 = st.columns(3)
d1.download_button(
    "⬇️ Descargar Excel",
    data=excel.getvalue(),
    file_name="cuadre_caja.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)
d2.download_button(
    "🖨️ Descargar / imprimir PDF",
    data=pdf_bytes,
    file_name="cuadre_caja.pdf",
    mime="application/pdf",
    use_container_width=True
)
d3.download_button(
    "💾 Descargar respaldo",
    data=backup_bytes,
    file_name=f"respaldo_caja_{date.today().strftime('%Y%m%d')}.json",
    mime="application/json",
    use_container_width=True
)

st.info(
    "💾 **Respaldo:** descarga el archivo JSON antes de cerrar o reiniciar la aplicación. "
    "Cuando vuelvas a entrar, usa “Recuperar caja desde un respaldo” para restaurar "
    "el fondo, movimientos, efectivo, vales y demás datos."
)

# ============================================================
# REINICIO
# ============================================================
st.divider()
if st.button("🔄 Cerrar y limpiar caja"):
    st.session_state.movimientos = []
    st.session_state.efectivo_contado = 0.0
    st.session_state.vales_pendientes = 0.0
    st.session_state.otros_soportes = 0.0
    st.rerun()

st.caption("CAJACHICA2026 · Registro directo + planilla + respaldo + Excel + PDF")
