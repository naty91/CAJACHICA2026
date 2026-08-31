
import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)

st.set_page_config(
    page_title="Caja Chica - Cuadre Automático",
    page_icon="💵",
    layout="wide"
)

# -------------------------
# Estado
# -------------------------
if "movimientos" not in st.session_state:
    st.session_state.movimientos = []

if "fondo_inicial" not in st.session_state:
    st.session_state.fondo_inicial = 500.00

def money(v):
    return f"${float(v):,.2f}"

def generar_pdf(detalle, fondo, total_gastos, saldo_teorico,
                efectivo, vales, otros, soporte_fisico, diferencia):
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
        "TituloCaja",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=18,
        leading=22,
        spaceAfter=12
    )
    subtitulo = ParagraphStyle(
        "SubtituloCaja",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
        fontSize=11,
        leading=14,
        spaceAfter=10
    )
    normal = styles["BodyText"]

    elementos = []

    elementos.append(Paragraph("CUADRE AUTOMÁTICO DE CAJA CHICA", titulo))
    elementos.append(Paragraph(
        f"Fecha de emisión: {date.today().strftime('%d/%m/%Y')}",
        subtitulo
    ))

    if abs(diferencia) < 0.005:
        estado = "CAJA CUADRADA"
    elif diferencia > 0:
        estado = f"SOBRANTE: {money(diferencia)}"
    else:
        estado = f"FALTANTE: {money(abs(diferencia))}"

    resumen_data = [
        ["CONCEPTO", "VALOR", "CONCEPTO", "VALOR"],
        ["Fondo inicial", money(fondo), "Total gastos", money(total_gastos)],
        ["Saldo teórico", money(saldo_teorico), "Efectivo contado", money(efectivo)],
        ["Vales pendientes", money(vales), "Otros soportes", money(otros)],
        ["Soporte físico", money(soporte_fisico), "Diferencia", money(diferencia)],
        ["ESTADO DEL CUADRE", estado, "", ""],
    ]

    tabla_resumen = Table(
        resumen_data,
        colWidths=[4.4*cm, 3.3*cm, 4.4*cm, 3.3*cm]
    )
    tabla_resumen.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (1,-1), "RIGHT"),
        ("ALIGN", (3,1), (3,-1), "RIGHT"),
        ("FONTNAME", (0,5), (1,5), "Helvetica-Bold"),
        ("SPAN", (1,5), (3,5)),
        ("ALIGN", (1,5), (3,5), "CENTER"),
        ("BACKGROUND", (0,5), (3,5),
         colors.HexColor("#D9EAD3") if abs(diferencia) < 0.005
         else colors.HexColor("#FCE5CD") if diferencia > 0
         else colors.HexColor("#F4CCCC")),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 7),
    ]))
    elementos.append(tabla_resumen)
    elementos.append(Spacer(1, 0.45*cm))

    elementos.append(Paragraph("DETALLE DE MOVIMIENTOS", styles["Heading2"]))

    if detalle.empty:
        elementos.append(Paragraph("No existen movimientos registrados.", normal))
    else:
        cols = ["FECHA", "DESCRIPCION", "PERSONA", "VALE/FACTURA", "VALOR", "SALDO"]
        data = [cols]

        for _, row in detalle.iterrows():
            data.append([
                str(row.get("FECHA", "")),
                str(row.get("DESCRIPCION", "")),
                str(row.get("PERSONA", "")),
                str(row.get("VALE/FACTURA", "")),
                money(row.get("VALOR", 0)),
                money(row.get("SALDO", 0)),
            ])

        tabla_detalle = Table(
            data,
            repeatRows=1,
            colWidths=[2.5*cm, 7.6*cm, 4.2*cm, 3.5*cm, 3.2*cm, 3.2*cm]
        )
        tabla_detalle.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#D9EAF7")),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("ALIGN", (4,1), (-1,-1), "RIGHT"),
            ("GRID", (0,0), (-1,-1), 0.4, colors.grey),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("FONTSIZE", (0,0), (-1,-1), 8.5),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ]))
        elementos.append(tabla_detalle)

    elementos.append(Spacer(1, 0.6*cm))
    elementos.append(Paragraph(
        "Observación: el saldo teórico corresponde al fondo inicial menos los gastos registrados. "
        "El cuadre compara ese saldo con el efectivo contado, vales pendientes y otros soportes.",
        ParagraphStyle("Nota", parent=normal, fontSize=8, textColor=colors.grey)
    ))

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

# -------------------------
# Encabezado
# -------------------------
st.title("💵 Caja Chica - Cuadre Automático")
st.caption("Registra los movimientos directamente y obtén el cuadre de caja al instante.")

# -------------------------
# Configuración
# -------------------------
with st.sidebar:
    st.header("Configuración de caja")

    st.session_state.fondo_inicial = st.number_input(
        "Fondo inicial ($)",
        min_value=0.0,
        value=float(st.session_state.fondo_inicial),
        step=0.01,
        format="%.2f"
    )

    efectivo_contado = st.number_input(
        "Efectivo contado al cierre ($)",
        min_value=0.0,
        value=0.0,
        step=0.01,
        format="%.2f"
    )

    vales_pendientes = st.number_input(
        "Vales pendientes no registrados ($)",
        min_value=0.0,
        value=0.0,
        step=0.01,
        format="%.2f"
    )

    otros_soportes = st.number_input(
        "Otros soportes ($)",
        min_value=0.0,
        value=0.0,
        step=0.01,
        format="%.2f"
    )

# -------------------------
# Formulario directo
# -------------------------
st.subheader("Registrar movimiento")

with st.form("form_movimiento", clear_on_submit=True):
    c1, c2 = st.columns(2)
    fecha = c1.date_input("Fecha", value=date.today())
    descripcion = c2.text_input("Descripción", placeholder="Ej. Compra de llaves")

    c3, c4 = st.columns(2)
    persona = c3.text_input("Persona", placeholder="Ej. Freddy")
    comprobante = c4.text_input("Vale / Factura", placeholder="Ej. 235")

    valor = st.number_input(
        "Valor del gasto ($)",
        min_value=0.0,
        step=0.01,
        format="%.2f"
    )

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
            st.success("Movimiento registrado correctamente.")
            st.rerun()

# -------------------------
# Cálculos
# -------------------------
df = pd.DataFrame(st.session_state.movimientos)

if df.empty:
    total_gastos = 0.0
    detalle = pd.DataFrame(
        columns=["FECHA", "DESCRIPCION", "PERSONA", "VALE/FACTURA", "VALOR", "SALDO"]
    )
else:
    total_gastos = float(df["VALOR"].sum())
    detalle = df.copy()
    detalle["SALDO"] = (
        float(st.session_state.fondo_inicial)
        - detalle["VALOR"].cumsum()
    )

saldo_teorico = float(st.session_state.fondo_inicial) - total_gastos
soporte_fisico = efectivo_contado + vales_pendientes + otros_soportes
diferencia = soporte_fisico - saldo_teorico

# -------------------------
# Indicadores
# -------------------------
st.divider()
st.subheader("Cuadre de caja")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Fondo inicial", money(st.session_state.fondo_inicial))
m2.metric("Total gastos registrados", money(total_gastos))
m3.metric("Saldo teórico", money(saldo_teorico))
m4.metric("Soporte físico", money(soporte_fisico))

if abs(diferencia) < 0.005:
    st.success("✅ CAJA CUADRADA")
elif diferencia > 0:
    st.warning(f"⚠️ SOBRANTE DE CAJA: {money(diferencia)}")
else:
    st.error(f"❌ FALTANTE DE CAJA: {money(abs(diferencia))}")

st.write(
    f"**Saldo teórico:** {money(saldo_teorico)}  |  "
    f"**Efectivo:** {money(efectivo_contado)}  |  "
    f"**Vales pendientes:** {money(vales_pendientes)}  |  "
    f"**Otros soportes:** {money(otros_soportes)}  |  "
    f"**Diferencia:** {money(diferencia)}"
)

# -------------------------
# Movimientos
# -------------------------
st.divider()
st.subheader("Movimientos registrados")

if detalle.empty:
    st.info("Todavía no hay gastos registrados.")
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

    st.subheader("Eliminar un movimiento")
    opciones = [
        f"{i+1} - {row['FECHA']} - {row['DESCRIPCION']} - {money(row['VALOR'])}"
        for i, row in detalle.iterrows()
    ]
    seleccionado = st.selectbox("Selecciona el movimiento", opciones)

    if st.button("🗑️ Eliminar movimiento"):
        idx = opciones.index(seleccionado)
        st.session_state.movimientos.pop(idx)
        st.success("Movimiento eliminado.")
        st.rerun()

# -------------------------
# Descargas
# -------------------------
st.divider()
st.subheader("Imprimir / descargar cuadre")

c_excel, c_pdf = st.columns(2)

# Excel
output = BytesIO()
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    detalle.to_excel(writer, index=False, sheet_name="CAJA")
    resumen = pd.DataFrame({
        "CONCEPTO": [
            "Fondo inicial",
            "Total gastos",
            "Saldo teórico",
            "Efectivo contado",
            "Vales pendientes",
            "Otros soportes",
            "Soporte físico",
            "Diferencia"
        ],
        "VALOR": [
            st.session_state.fondo_inicial,
            total_gastos,
            saldo_teorico,
            efectivo_contado,
            vales_pendientes,
            otros_soportes,
            soporte_fisico,
            diferencia
        ]
    })
    resumen.to_excel(writer, index=False, sheet_name="RESUMEN")

c_excel.download_button(
    "⬇️ Descargar Excel",
    data=output.getvalue(),
    file_name="cuadre_caja.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)

# PDF
pdf_bytes = generar_pdf(
    detalle,
    st.session_state.fondo_inicial,
    total_gastos,
    saldo_teorico,
    efectivo_contado,
    vales_pendientes,
    otros_soportes,
    soporte_fisico,
    diferencia
)

c_pdf.download_button(
    "🖨️ Descargar / imprimir PDF",
    data=pdf_bytes,
    file_name="cuadre_caja.pdf",
    mime="application/pdf",
    use_container_width=True
)

st.caption("Abre el PDF descargado y selecciona Imprimir para obtener el reporte físico.")

# -------------------------
# Reinicio
# -------------------------
st.divider()
if st.button("🔄 Cerrar y limpiar caja"):
    st.session_state.movimientos = []
    st.rerun()

st.caption("CAJACHICA2026 · Registro directo, cuadre automático y PDF")
