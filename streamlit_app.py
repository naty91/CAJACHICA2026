
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

PERSONAS_INICIALES = [
    "CAMACHO GUAYGUA BORYS GABRIEL — JEFE FINANCIERO",
    "GARCIA BOWEN KATHERINE PAOLA — COORD. OPERACIONES",
    "CAMACHO GUAYGUA DANKO XAVIER — GERENTE DE OPERACIONES",
    "CAMACHO YANEZ REMIGIO SALOMON — SERVICIO AL CLIENTE",
    "GUAYGUA REYES NELLI OLIMPIA — GERENTE GENERAL",
    "CAMACHO GUAYGUA GORKY SANTIAGO — ASISTENTE DE SERVICIOS GENERALES",
    "ANDRADE BETANCOURT JOHANNA GRACE — AUX. CONTABLE",
    "ESPINOZA QUEVEDO ERICKA MERCEDES — AUX. ADMINISTRATIVO",
    "HERNANDEZ MERCHAN DIANA NICOLE — PASANTE ADMINISTRATIVO",
    "LUNA MENDOZA KLEBER ENRIQUE — COORDINADOR OPERATIVO",
    "PEÑAHERRERA ALVARADO FREDDY ROMULO — MENSAJERO",
    "PINEDA BOWEN SKARLETH YAMILETH — AUX. SERVICIOS GENERALES",
    "RIVAS SALAZAR ASHLEY NICOLE — AUX. SERVICIOS GENERALES",
    "RIVERA GUILLIN ESTEFANI TAMARA — AUX. ADMINISTRATIVO",
    "SAA VILLAFUERTE MARIA ELIZABETH — AUX. ADMINISTRATIVO",
    "TROCCOLI YEPEZ NICOLLE DANIELLE — RRHH",
    "VARELA BENAVIDES NATHALY PAULETTE — CONTADORA",
    "VARGAS LUNA ADRIAN ANDRE — AUX. SERVICIOS GENERALES",
    "VARGAS LUNA BRYAN DAVID — AUX. SERVICIOS GENERALES",
    "VARGAS LUNA MARIA ALEJANDRA — AUX. SERVICIOS GENERALES",
    "VARGAS LUNA MARIA BELEN — AUX. CONTABLE",
]

DESCRIPCIONES_INICIALES = [
    "ALIMENTACIÓN",
    "PEAJE",
    "COMISIÓN BANCARIA / IESS",
    "PARQUEO",
    "ENVÍO DE DOCUMENTOS / ROL / DOTACIÓN",
    "DUPLICADO / COPIA DE LLAVES",
    "SUMINISTROS DE OFICINA",
    "MATERIALES",
    "IMPRESIONES / COPIAS",
    "NOTARÍA",
    "CERTIFICACIÓN DE DOCUMENTOS",
    "TRÁMITES DE TRÁNSITO",
    "TELÉFONO / RECARGA",
    "MANTENIMIENTO",
    "SUMINISTROS DE LIMPIEZA",
    "ARRIENDO / SERVICIOS DE OFICINA",
    "AGUA / INTERNET / LUZ",
    "TRANSPORTE / MOVILIZACIÓN",
    "FARMACIA / MEDICINAS",
    "CAFETERÍA / REFRIGERIOS",
    "OTROS",
]

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
    "personas_catalogo": PERSONAS_INICIALES.copy(),
    "descripciones_catalogo": DESCRIPCIONES_INICIALES.copy(),
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
        "personas_catalogo": st.session_state.personas_catalogo,
        "descripciones_catalogo": st.session_state.descripciones_catalogo,
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
    st.session_state.personas_catalogo = data.get("personas_catalogo", PERSONAS_INICIALES.copy())
    st.session_state.descripciones_catalogo = data.get("descripciones_catalogo", DESCRIPCIONES_INICIALES.copy())

# ============================================================
# PDF
# ============================================================
def generar_pdf(detalle, fondo, total_gastos, saldo_teorico,
                efectivo, vales, otros, soporte_fisico, diferencia, nombre_caja):
    """Genera PDF A4 VERTICAL, con texto envuelto y tabla ordenada."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.8*cm,
        leftMargin=0.8*cm,
        topMargin=0.8*cm,
        bottomMargin=1.0*cm,
        title="Cuadre de Caja"
    )

    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloCaja", parent=styles["Title"],
        alignment=TA_CENTER, fontSize=15, leading=18, spaceAfter=3
    )
    subtitulo = ParagraphStyle(
        "SubtituloCaja", parent=styles["BodyText"],
        alignment=TA_CENTER, fontSize=8.5, leading=10, spaceAfter=8
    )
    h2 = ParagraphStyle(
        "H2Caja", parent=styles["Heading2"],
        fontSize=10, leading=12, spaceBefore=2, spaceAfter=5
    )
    cell = ParagraphStyle(
        "CellCaja", parent=styles["BodyText"],
        fontSize=6.8, leading=8.2, spaceAfter=0, spaceBefore=0
    )
    cell_center = ParagraphStyle(
        "CellCenter", parent=cell, alignment=TA_CENTER
    )
    cell_money = ParagraphStyle(
        "CellMoney", parent=cell, alignment=2
    )
    head = ParagraphStyle(
        "HeadCaja", parent=cell,
        fontName="Helvetica-Bold", textColor=colors.white,
        fontSize=6.6, leading=7.6, alignment=TA_CENTER
    )
    summary_label = ParagraphStyle(
        "SummaryLabel", parent=styles["BodyText"], fontSize=8, leading=9.5
    )
    summary_value = ParagraphStyle(
        "SummaryValue", parent=summary_label, alignment=2
    )
    summary_bold = ParagraphStyle(
        "SummaryBold", parent=summary_label, fontName="Helvetica-Bold"
    )

    def P(text, style=cell):
        # Escapar caracteres básicos para Paragraph XML
        s = str(text if text is not None else "")
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Los guiones largos pueden dar problemas en algunos visores; normalizamos.
        s = s.replace("—", "-").replace("–", "-")
        return Paragraph(s, style)

    def nombre_para_reporte(texto):
        """En el PDF prioriza el nombre; el cargo sigue existiendo en la app."""
        s = str(texto or "").strip().replace("—", "-")
        # Si fue guardado como NOMBRE - CARGO, quita solo el cargo para ganar espacio.
        if " - " in s:
            return s.split(" - ", 1)[0].strip()
        return s

    elementos = [
        Paragraph("CUADRE AUTOMÁTICO DE CAJA CHICA", titulo),
        Paragraph(
            f"{nombre_caja} - Fecha de emisión: {date.today().strftime('%d/%m/%Y')}",
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

    # Resumen compacto: una sola tabla de 4 columnas que cabe bien en vertical.
    resumen = [
        [P("CONCEPTO", head), P("VALOR", head), P("CONCEPTO", head), P("VALOR", head)],
        [P("Fondo inicial", summary_label), P(money(fondo), summary_value),
         P("Total gastos", summary_label), P(money(total_gastos), summary_value)],
        [P("Saldo teórico", summary_label), P(money(saldo_teorico), summary_value),
         P("Efectivo contado", summary_label), P(money(efectivo), summary_value)],
        [P("Vales pendientes", summary_label), P(money(vales), summary_value),
         P("Otros soportes", summary_label), P(money(otros), summary_value)],
        [P("Soporte físico", summary_label), P(money(soporte_fisico), summary_value),
         P("Diferencia", summary_label), P(money(diferencia), summary_value)],
        [P("ESTADO DEL CUADRE", summary_bold), P(estado, summary_bold), "", ""],
    ]

    t = Table(
        resumen,
        colWidths=[4.15*cm, 2.55*cm, 4.15*cm, 2.55*cm],
        hAlign="CENTER"
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.45, colors.HexColor("#8A8A8A")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("SPAN", (1,5), (3,5)),
        ("BACKGROUND", (0,5), (3,5), bg),
        ("ALIGN", (1,5), (3,5), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
    ]))
    elementos += [t, Spacer(1, 0.35*cm), Paragraph("DETALLE DE MOVIMIENTOS", h2)]

    if detalle.empty:
        elementos.append(P("No existen movimientos registrados.", summary_label))
    else:
        encabezados = ["FECHA", "DESCRIPCIÓN", "PERSONA", "VALE / FACTURA", "VALOR", "SALDO"]
        data = [[P(x, head) for x in encabezados]]

        for _, row in detalle.iterrows():
            data.append([
                P(str(row.get("FECHA", "")), cell_center),
                P(str(row.get("DESCRIPCION", "")), cell),
                P(nombre_para_reporte(row.get("PERSONA", "")), cell),
                P(str(row.get("VALE/FACTURA", "")), cell_center),
                P(money(row.get("VALOR", 0)), cell_money),
                P(money(row.get("SALDO", 0)), cell_money),
            ])

        # Total = 18.2 cm, dentro del ancho útil de A4 vertical con márgenes de 0.8 cm.
        td = Table(
            data,
            repeatRows=1,
            colWidths=[2.0*cm, 5.15*cm, 4.15*cm, 2.45*cm, 2.15*cm, 2.15*cm],
            hAlign="CENTER"
        )
        td.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E78")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#8A8A8A")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("TOPPADDING", (0,0), (-1,-1), 3.5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3.5),
            ("LEFTPADDING", (0,0), (-1,-1), 3),
            ("RIGHTPADDING", (0,0), (-1,-1), 3),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F7F9FB")]),
        ]))
        elementos.append(td)

    elementos.append(Spacer(1, 0.3*cm))
    elementos.append(Paragraph(
        "El saldo teórico corresponde al fondo inicial menos los gastos registrados. "
        "El cuadre compara ese saldo con el efectivo contado, vales pendientes y otros soportes.",
        ParagraphStyle("NotaPDF", parent=styles["BodyText"], fontSize=6.5,
                       leading=8, textColor=colors.HexColor("#666666"))
    ))

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

# ============================================================
# INTERFAZ
# ============================================================
st.title("💵 Caja Chica - Cuadre Automático")
st.caption("Registro rápido con listas editables, carga por planilla, respaldo recuperable, Excel y PDF.")

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
    st.caption("Selecciona opciones frecuentes para registrar más rápido. Si no existe, elige la opción de escribir/agregar.")

    with st.form("form_movimiento", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha", value=date.today())

        opciones_desc = st.session_state.descripciones_catalogo + ["✏️ ESCRIBIR / AGREGAR OTRA DESCRIPCIÓN"]
        descripcion_sel = c2.selectbox("Descripción", opciones_desc)

        descripcion_manual = ""
        if descripcion_sel.startswith("✏️"):
            descripcion_manual = st.text_input(
                "Escribe la descripción",
                placeholder="Ej. COMPRA DE LLAVES / REFRIGERIO REUNIÓN"
            )

        c3, c4 = st.columns(2)
        opciones_persona = st.session_state.personas_catalogo + ["✏️ ESCRIBIR / AGREGAR OTRA PERSONA"]
        persona_sel = c3.selectbox("Persona solicitante", opciones_persona)

        persona_manual = ""
        if persona_sel.startswith("✏️"):
            persona_manual = st.text_input(
                "Escribe la persona",
                placeholder="Nombre y, si deseas, cargo"
            )

        comprobante = c4.text_input("Vale / Factura", placeholder="Ej. 235")

        detalle_adicional = st.text_input(
            "Detalle adicional (opcional)",
            placeholder="Ej. Apertura ECU911 Quito / doblada de turno / oficina administrativa"
        )

        valor = st.number_input("Valor del gasto ($)", min_value=0.0, step=0.01, format="%.2f")
        agregar = st.form_submit_button("➕ Registrar gasto", use_container_width=True)

        if agregar:
            descripcion_base = descripcion_manual.strip() if descripcion_sel.startswith("✏️") else descripcion_sel
            persona_base = persona_manual.strip() if persona_sel.startswith("✏️") else persona_sel

            descripcion_final = descripcion_base
            if detalle_adicional.strip():
                descripcion_final = f"{descripcion_base} - {detalle_adicional.strip()}"

            if valor <= 0:
                st.warning("Ingresa un valor mayor a 0.")
            elif not descripcion_base:
                st.warning("Ingresa una descripción.")
            elif not persona_base:
                st.warning("Selecciona o escribe la persona solicitante.")
            else:
                # Aprende nuevas opciones escritas manualmente
                if descripcion_sel.startswith("✏️") and descripcion_base not in st.session_state.descripciones_catalogo:
                    st.session_state.descripciones_catalogo.append(descripcion_base)
                if persona_sel.startswith("✏️") and persona_base not in st.session_state.personas_catalogo:
                    st.session_state.personas_catalogo.append(persona_base)

                st.session_state.movimientos.append({
                    "FECHA": fecha.strftime("%d/%m/%Y"),
                    "DESCRIPCION": descripcion_final,
                    "PERSONA": persona_base,
                    "VALE/FACTURA": comprobante.strip(),
                    "VALOR": float(valor)
                })
                st.success("Movimiento registrado.")
                st.rerun()

    with st.expander("⚙️ Editar listas rápidas de personas y descripciones"):
        st.write("Estas listas también se guardan dentro del respaldo de la caja.")

        cp1, cp2 = st.columns(2)
        nueva_persona = cp1.text_input(
            "Agregar persona a la lista",
            key="nueva_persona_catalogo",
            placeholder="NOMBRE — CARGO"
        )
        if cp1.button("➕ Agregar persona", use_container_width=True):
            nueva = nueva_persona.strip().upper()
            if nueva and nueva not in st.session_state.personas_catalogo:
                st.session_state.personas_catalogo.append(nueva)
                st.rerun()

        nueva_desc = cp2.text_input(
            "Agregar descripción a la lista",
            key="nueva_desc_catalogo",
            placeholder="NUEVA DESCRIPCIÓN"
        )
        if cp2.button("➕ Agregar descripción", use_container_width=True):
            nueva = nueva_desc.strip().upper()
            if nueva and nueva not in st.session_state.descripciones_catalogo:
                st.session_state.descripciones_catalogo.append(nueva)
                st.rerun()

        if st.session_state.personas_catalogo:
            borrar_persona = cp1.selectbox(
                "Quitar persona de lista rápida",
                st.session_state.personas_catalogo,
                key="borrar_persona_catalogo"
            )
            if cp1.button("🗑️ Quitar persona", use_container_width=True):
                st.session_state.personas_catalogo.remove(borrar_persona)
                st.rerun()

        if st.session_state.descripciones_catalogo:
            borrar_desc = cp2.selectbox(
                "Quitar descripción de lista rápida",
                st.session_state.descripciones_catalogo,
                key="borrar_desc_catalogo"
            )
            if cp2.button("🗑️ Quitar descripción", use_container_width=True):
                st.session_state.descripciones_catalogo.remove(borrar_desc)
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

                # Aprender personas y descripciones nuevas de la planilla
                for m in movs:
                    p = str(m.get("PERSONA", "")).strip()
                    d = str(m.get("DESCRIPCION", "")).strip()
                    if p and p not in st.session_state.personas_catalogo:
                        st.session_state.personas_catalogo.append(p)
                    if d and d not in st.session_state.descripciones_catalogo:
                        st.session_state.descripciones_catalogo.append(d)

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
