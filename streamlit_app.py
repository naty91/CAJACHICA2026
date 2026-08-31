
import streamlit as st
import pandas as pd
import io

st.set_page_config(
    page_title="Cuadre Automático de Caja",
    page_icon="💵",
    layout="wide"
)

st.title("💵 Cuadre Automático de Caja")
st.caption("Conciliación de fondo fijo, saldo en Contífico, reposiciones, efectivo y vales pendientes.")

def money(x):
    return f"${x:,.2f}"

def normalize_columns(df):
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

def find_col(columns, keywords):
    for c in columns:
        lc = c.lower()
        for k in keywords:
            if k in lc:
                return c
    return None

with st.sidebar:
    st.header("Datos del fondo")
    nombre_caja = st.text_input("Nombre de caja", "Caja Chica")
    fondo_fijo = st.number_input("Fondo fijo ($)", min_value=0.0, value=500.00, step=0.01, format="%.2f")
    saldo_sistema = st.number_input("Saldo en Contífico ($)", value=67.08, step=0.01, format="%.2f")
    reposicion = st.number_input("Reposición pendiente / actual ($)", min_value=0.0, value=400.92, step=0.01, format="%.2f")
    efectivo = st.number_input("Efectivo físico contado ($)", min_value=0.0, value=0.00, step=0.01, format="%.2f")
    vales = st.number_input("Vales no registrados ($)", min_value=0.0, value=96.14, step=0.01, format="%.2f")
    otros = st.number_input("Otros comprobantes pendientes ($)", min_value=0.0, value=0.00, step=0.01, format="%.2f")

saldo_teorico = round(fondo_fijo - reposicion, 2)
dif_sistema = round(saldo_sistema - saldo_teorico, 2)
disponible_fisico = round(efectivo + vales + otros, 2)
dif_fisica = round(disponible_fisico - saldo_teorico, 2)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Saldo teórico", money(saldo_teorico), help="Fondo fijo - reposición")
c2.metric("Diferencia Contífico", money(dif_sistema))
c3.metric("Disponible físico", money(disponible_fisico))
c4.metric("Diferencia física", money(dif_fisica))

st.subheader("Diagnóstico automático")

if abs(dif_sistema) < 0.005:
    st.success("El saldo de Contífico coincide con el saldo teórico.")
else:
    sentido = "menor" if dif_sistema < 0 else "mayor"
    st.error(
        f"El saldo de Contífico está {sentido} que el saldo teórico en "
        f"{money(abs(dif_sistema))}. Debe revisarse un asiento, egreso, reposición, reverso o ajuste."
    )

if vales > 0:
    st.info(
        f"Existen {money(vales)} en vales no registrados. "
        "Se muestran por separado y no deben confundirse con una diferencia contable."
    )

if abs(dif_fisica) < 0.005:
    st.success("El efectivo + vales + otros soportes coincide con el saldo teórico.")
else:
    st.warning(
        f"El soporte físico presenta una diferencia de {money(dif_fisica)} frente al saldo teórico."
    )

st.divider()
st.subheader("Buscar el asiento o movimiento causante")
st.write(
    "Sube un Excel o CSV del mayor contable, reporte por cuenta o detalle de caja. "
    "La aplicación buscará movimientos que coincidan con la diferencia detectada."
)

uploaded = st.file_uploader(
    "Cargar reporte",
    type=["xlsx", "xls", "csv"]
)

if uploaded is not None:
    try:
        if uploaded.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded)
        else:
            xls = pd.ExcelFile(uploaded)
            frames = []
            for sheet in xls.sheet_names:
                temp = pd.read_excel(uploaded, sheet_name=sheet)
                temp["__hoja__"] = sheet
                frames.append(temp)
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        if df.empty:
            st.warning("El archivo no contiene registros legibles.")
        else:
            st.success(f"Archivo cargado: {uploaded.name} — {len(df):,} registros")

            df2 = normalize_columns(df)
            cols = list(df2.columns)

            col_debe = find_col(cols, ["debe", "debito", "débito"])
            col_haber = find_col(cols, ["haber", "credito", "crédito"])
            col_valor = find_col(cols, ["valor", "monto", "importe", "total"])
            col_fecha = find_col(cols, ["fecha"])
            col_asiento = find_col(cols, ["asiento", "documento", "comprobante", "numero", "número"])
            col_detalle = find_col(cols, ["detalle", "descripcion", "descripción", "concepto", "glosa"])

            objetivo = abs(dif_sistema)

            if objetivo < 0.005:
                st.info("No existe diferencia contable que buscar.")
            else:
                work = pd.DataFrame(index=df2.index)
                work["fila_excel"] = df2.index + 2

                for name, col in [
                    ("fecha", col_fecha),
                    ("asiento_documento", col_asiento),
                    ("detalle", col_detalle),
                ]:
                    work[name] = df2[col] if col else ""

                work["debe"] = pd.to_numeric(df2[col_debe], errors="coerce").fillna(0) if col_debe else 0.0
                work["haber"] = pd.to_numeric(df2[col_haber], errors="coerce").fillna(0) if col_haber else 0.0
                work["valor"] = pd.to_numeric(df2[col_valor], errors="coerce").fillna(0) if col_valor else 0.0

                candidatos = pd.concat(
                    [
                        work["debe"].abs(),
                        work["haber"].abs(),
                        work["valor"].abs(),
                        (work["debe"] - work["haber"]).abs()
                    ],
                    axis=1
                )
                work["distancia"] = candidatos.sub(objetivo).abs().min(axis=1)
                exactos = work[work["distancia"] <= 0.01].copy()

                if not exactos.empty:
                    exactos["coincidencia"] = "Coincide con la diferencia"
                    st.success(f"Se encontraron {len(exactos)} movimiento(s) relacionados con {money(objetivo)}.")
                    st.dataframe(
                        exactos[
                            ["fila_excel","fecha","asiento_documento","detalle","debe","haber","valor","coincidencia"]
                        ],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.warning(
                        f"No encontré un movimiento individual que coincida exactamente con {money(objetivo)}."
                    )

                    # Busca una combinación simple de dos valores si el archivo no es demasiado grande
                    valores = []
                    for i, row in work.iterrows():
                        candidatos_fila = [abs(row["debe"]), abs(row["haber"]), abs(row["valor"])]
                        v = max(candidatos_fila)
                        if v > 0:
                            valores.append((i, float(v)))

                    encontrados = None
                    if len(valores) <= 2000:
                        vistos = {}
                        for idx, v in valores:
                            faltante = round(objetivo - v, 2)
                            clave = round(faltante, 2)
                            if clave in vistos:
                                encontrados = (vistos[clave], idx)
                                break
                            vistos[round(v, 2)] = idx

                    if encontrados:
                        combo = work.loc[list(encontrados)].copy()
                        combo["coincidencia"] = "Combinación que suma la diferencia"
                        st.info("Encontré dos movimientos cuya suma coincide aproximadamente con la diferencia.")
                        st.dataframe(
                            combo[
                                ["fila_excel","fecha","asiento_documento","detalle","debe","haber","valor","coincidencia"]
                            ],
                            use_container_width=True,
                            hide_index=True
                        )

            with st.expander("Ver datos cargados"):
                st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")

st.divider()
st.subheader("Conclusión del cuadre")

estado = "CUADRADO" if abs(dif_sistema) < 0.005 else f"REVISAR MOVIMIENTO(S) POR {money(abs(dif_sistema))}"

conclusion = f"""\
{nombre_caja}

Fondo fijo: {money(fondo_fijo)}
Reposición pendiente/actual: {money(reposicion)}
Saldo teórico: {money(saldo_teorico)}
Saldo Contífico: {money(saldo_sistema)}
Diferencia contable: {money(dif_sistema)}

Efectivo físico: {money(efectivo)}
Vales no registrados: {money(vales)}
Otros comprobantes pendientes: {money(otros)}
Disponible físico: {money(disponible_fisico)}
Diferencia física: {money(dif_fisica)}

Diagnóstico: {estado}
"""

st.text_area("Resumen", conclusion, height=260)

st.download_button(
    "Descargar conclusión TXT",
    data=conclusion.encode("utf-8"),
    file_name="conclusion_cuadre_caja.txt",
    mime="text/plain"
)

st.caption("Aplicación de cuadre automático de caja.")
