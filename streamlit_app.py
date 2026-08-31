
import streamlit as st
import pandas as pd
import numpy as np
import io
import re
from datetime import datetime

st.set_page_config(
    page_title="Cuadre Automático de Caja",
    page_icon="💵",
    layout="wide"
)

st.title("💵 Cuadre Automático de Caja")
st.caption("Carga tu plantilla de caja y la aplicación calcula el cuadre automáticamente.")

def money(x):
    try:
        return f"${float(x):,.2f}"
    except:
        return "$0.00"

def parse_number(v):
    if pd.isna(v):
        return None
    if isinstance(v, (int, float, np.number)):
        return float(v)
    s = str(v).strip()
    if not s or s.lower() in ["nan", "none", "-"]:
        return None
    s = s.replace("$","").replace(" ","")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".","").replace(",",".")
        else:
            s = s.replace(",","")
    elif "," in s:
        s = s.replace(",",".")
    s = re.sub(r"[^0-9\.\-]", "", s)
    try:
        return float(s)
    except:
        return None

def normalize_text(v):
    return str(v).strip().upper() if not pd.isna(v) else ""

def read_raw(uploaded):
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        uploaded.seek(0)
        return pd.read_csv(uploaded, header=None)
    uploaded.seek(0)
    return pd.read_excel(uploaded, header=None)

def detect_template(raw):
    """
    Detecta:
    - saldo inicial en primeras filas
    - fila de encabezados con FECHA / DESCRIPCION / PERSONA / VALE/FACTURA / VALOR
    """
    saldo_inicial = None
    header_row = None

    max_scan = min(len(raw), 20)
    for i in range(max_scan):
        row = [normalize_text(x) for x in raw.iloc[i].tolist()]
        joined = " | ".join(row)

        if "SALDO INICIAL" in joined:
            # Buscar un valor numérico en la misma fila
            nums = [parse_number(x) for x in raw.iloc[i].tolist()]
            nums = [x for x in nums if x is not None]
            if nums:
                saldo_inicial = nums[-1]

        hits = 0
        for k in ["FECHA", "DESCRIPCION", "DESCRIPCIÓN", "PERSONA", "VALE/FACTURA", "VALOR"]:
            if any(k in cell for cell in row):
                hits += 1
        if hits >= 3:
            header_row = i
            break

    return saldo_inicial, header_row

def build_transactions(raw, header_row):
    headers = []
    seen = {}
    for j, x in enumerate(raw.iloc[header_row].tolist()):
        name = normalize_text(x)
        if not name:
            name = f"COLUMNA_{j+1}"
        # nombres únicos
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        headers.append(name)

    df = raw.iloc[header_row+1:].copy()
    df.columns = headers
    df = df.dropna(how="all").reset_index(drop=True)
    return df

def find_col(cols, variants):
    cols_norm = {c: normalize_text(c) for c in cols}
    for c, n in cols_norm.items():
        for v in variants:
            if v in n:
                return c
    return None

def analyze_uploaded(uploaded):
    raw = read_raw(uploaded)
    saldo_inicial, header_row = detect_template(raw)

    if header_row is None:
        raise ValueError(
            "No pude detectar la fila de encabezados. La plantilla debe contener "
            "columnas como FECHA, DESCRIPCION, PERSONA, VALE/FACTURA y VALOR."
        )

    df = build_transactions(raw, header_row)

    c_fecha = find_col(df.columns, ["FECHA"])
    c_desc = find_col(df.columns, ["DESCRIPCION", "DESCRIPCIÓN"])
    c_persona = find_col(df.columns, ["PERSONA"])
    c_vale = find_col(df.columns, ["VALE/FACTURA", "VALE", "FACTURA"])
    c_valor = find_col(df.columns, ["VALOR"])

    if c_valor is None:
        raise ValueError("No pude detectar la columna VALOR.")

    # Buscar una posible columna de saldo: normalmente la columna posterior a VALOR
    valor_idx = list(df.columns).index(c_valor)
    c_saldo = None
    if valor_idx + 1 < len(df.columns):
        possible = df.columns[valor_idx + 1]
        c_saldo = possible

    out = pd.DataFrame()
    out["FECHA"] = df[c_fecha] if c_fecha else ""
    out["DESCRIPCION"] = df[c_desc] if c_desc else ""
    out["PERSONA"] = df[c_persona] if c_persona else ""
    out["VALE/FACTURA"] = df[c_vale] if c_vale else ""
    out["VALOR"] = df[c_valor].apply(parse_number)

    # quitar filas sin valor
    out = out[out["VALOR"].notna()].reset_index(drop=True)

    if saldo_inicial is None:
        saldo_inicial = 0.0

    out["SALDO_CALCULADO"] = saldo_inicial - out["VALOR"].cumsum()

    saldo_reportado = None
    if c_saldo is not None:
        temp = df.loc[df[c_valor].apply(parse_number).notna(), c_saldo].apply(parse_number).reset_index(drop=True)
        if temp.notna().any():
            out["SALDO_REPORTADO"] = temp
            out["DIFERENCIA_FILA"] = (out["SALDO_REPORTADO"] - out["SALDO_CALCULADO"]).round(2)
            saldo_reportado = temp.dropna().iloc[-1] if temp.dropna().size else None

    total_gastos = float(out["VALOR"].sum())
    saldo_final = float(saldo_inicial - total_gastos)

    return {
        "raw": raw,
        "df": out,
        "saldo_inicial": float(saldo_inicial),
        "total_gastos": total_gastos,
        "saldo_final": saldo_final,
        "saldo_reportado_final": saldo_reportado
    }

tab1, tab2 = st.tabs(["📤 Cuadre automático por archivo", "✍️ Cuadre manual"])

with tab1:
    st.subheader("Subir plantilla de caja")
    st.write(
        "La plantilla puede tener la misma estructura que tu ejemplo: "
        "**SALDO INICIAL** arriba y luego las columnas "
        "**FECHA, DESCRIPCION, PERSONA, VALE/FACTURA, VALOR y SALDO**."
    )

    uploaded = st.file_uploader(
        "Selecciona tu archivo Excel o CSV",
        type=["xlsx", "xls", "csv"],
        key="plantilla_caja"
    )

    if uploaded is not None:
        try:
            result = analyze_uploaded(uploaded)
            df = result["df"]

            st.success("Plantilla leída correctamente.")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Saldo inicial", money(result["saldo_inicial"]))
            c2.metric("Total egresos", money(result["total_gastos"]))
            c3.metric("Saldo final calculado", money(result["saldo_final"]))
            c4.metric("Movimientos", f"{len(df)}")

            st.subheader("Resultado del cuadre")

            if abs(result["saldo_final"]) < 0.005:
                st.success("✅ La caja quedó consumida exactamente hasta $0.00.")
            elif result["saldo_final"] > 0:
                st.info(f"ℹ️ Según la plantilla deberían quedar {money(result['saldo_final'])} en caja.")
            else:
                st.error(f"❌ Los gastos exceden el fondo disponible en {money(abs(result['saldo_final']))}.")

            if "SALDO_REPORTADO" in df.columns:
                difs = df[df["DIFERENCIA_FILA"].abs() > 0.01].copy()
                if difs.empty:
                    st.success("✅ Todos los saldos fila por fila coinciden con el cálculo automático.")
                else:
                    st.error(f"❌ Encontré {len(difs)} fila(s) con diferencia de saldo.")
                    st.dataframe(
                        difs,
                        use_container_width=True,
                        hide_index=True
                    )

            st.subheader("Detalle calculado")
            display = df.copy()
            display["VALOR"] = display["VALOR"].map(lambda x: round(float(x),2))
            display["SALDO_CALCULADO"] = display["SALDO_CALCULADO"].map(lambda x: round(float(x),2))
            if "SALDO_REPORTADO" in display.columns:
                display["SALDO_REPORTADO"] = display["SALDO_REPORTADO"].map(
                    lambda x: round(float(x),2) if pd.notna(x) else None
                )
                display["DIFERENCIA_FILA"] = display["DIFERENCIA_FILA"].map(
                    lambda x: round(float(x),2) if pd.notna(x) else None
                )
            st.dataframe(display, use_container_width=True, hide_index=True)

            # archivo Excel con resultado
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                resumen = pd.DataFrame({
                    "CONCEPTO": ["Saldo inicial", "Total egresos", "Saldo final calculado", "Cantidad de movimientos"],
                    "VALOR": [result["saldo_inicial"], result["total_gastos"], result["saldo_final"], len(df)]
                })
                resumen.to_excel(writer, sheet_name="RESUMEN", index=False)
                df.to_excel(writer, sheet_name="CUADRE", index=False)

            st.download_button(
                "⬇️ Descargar cuadre automático en Excel",
                data=output.getvalue(),
                file_name="cuadre_caja_automatico.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"No pude procesar la plantilla: {e}")

with tab2:
    st.subheader("Cuadre manual")
    c1, c2, c3 = st.columns(3)
    fondo = c1.number_input("Fondo fijo ($)", min_value=0.0, value=500.0, step=0.01)
    sistema = c2.number_input("Saldo en sistema / Contífico ($)", value=0.0, step=0.01)
    reposicion = c3.number_input("Reposición / gastos ($)", min_value=0.0, value=0.0, step=0.01)

    c4, c5, c6 = st.columns(3)
    efectivo = c4.number_input("Efectivo contado ($)", min_value=0.0, value=0.0, step=0.01)
    vales = c5.number_input("Vales pendientes ($)", min_value=0.0, value=0.0, step=0.01)
    otros = c6.number_input("Otros soportes ($)", min_value=0.0, value=0.0, step=0.01)

    saldo_teorico = fondo - reposicion
    soporte = efectivo + vales + otros
    dif_sistema = sistema - saldo_teorico
    dif_fisica = soporte - saldo_teorico

    a,b,c,d = st.columns(4)
    a.metric("Saldo teórico", money(saldo_teorico))
    b.metric("Diferencia sistema", money(dif_sistema))
    c.metric("Soporte físico", money(soporte))
    d.metric("Diferencia física", money(dif_fisica))

    if abs(dif_sistema) < 0.005:
        st.success("El sistema coincide con el saldo teórico.")
    else:
        st.error(f"Diferencia contra sistema: {money(dif_sistema)}")

st.divider()
st.caption("CAJACHICA2026 · Cuadre automático de caja")
