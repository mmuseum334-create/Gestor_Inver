"""
Script de Python para descargar datos del mercado de capitales colombiano
utilizando yfinance y pandas, generando el archivo datos.json.
Proyecto de Aula - Mercado de Capitales - UNIPAZ
"""

import json
import math
import os
import sys
from datetime import datetime, timezone, timedelta
import pandas as pd
import yfinance as yf

# Definición de las 8 acciones colombianas
# Formato: (ticker_yahoo, nombre, nemotécnico_bvc, sector)
ACCIONES_CONFIG = [
    ("ECOPETROL.CL", "Ecopetrol", "ECOPETROL", "Petróleo y gas"),
    ("PFCIBEST.CL", "Grupo Cibest (Preferencial)", "PFCIBEST", "Financiero"),
    ("CIBEST.CL", "Grupo Cibest (Ordinaria)", "CIBEST", "Financiero"),
    ("ISA.CL", "Interconexión Eléctrica (ISA)", "ISA", "Energía e infraestructura"),
    ("EXITO.CL", "Grupo Éxito", "EXITO", "Comercio"),
    ("PFAVAL.CL", "Grupo Aval (Preferencial)", "PFAVAL", "Financiero"),
    ("GEB.CL", "Grupo Energía Bogotá", "GEB", "Energía y servicios públicos"),
    ("CEMARGOS.CL", "Cementos Argos", "CEMARGOS", "Materiales y construcción"),
]

def obtener_datos_accion(ticker_sym, nombre, nemotecnico, sector):
    """
    Descarga el histórico de 3 años y calcula las métricas financieras requeridas.
    """
    ticker = yf.Ticker(ticker_sym)
    hist = ticker.history(period="3y", auto_adjust=False)

    if hist is None or hist.empty or len(hist) < 5:
        raise ValueError("Datos insuficientes o ticker sin cotización en el período.")

    # Asegurar índice en formato datetime sin zona horaria para cálculos
    hist = hist.copy()
    hist.index = pd.to_datetime(hist.index).tz_localize(None)

    # 1. Precio actual y fecha del último cierre
    ultimo_cierre = hist["Close"].iloc[-1]
    cierre_anterior = hist["Close"].iloc[-2]
    fecha_cierre = hist.index[-1].strftime("%Y-%m-%d")
    precio = float(round(ultimo_cierre, 2))

    # 2. Variación del día (%)
    variacion_dia = (ultimo_cierre / cierre_anterior - 1.0) * 100.0

    # 3. Rentabilidad 1 año (%) usando Adj Close
    fecha_hace_1a = hist.index[-1] - pd.DateOffset(years=1)
    # Buscar fecha más cercana posterior o igual a hace 1 año, o la más próxima
    sub_1a = hist.loc[hist.index >= fecha_hace_1a]
    if len(sub_1a) > 1:
        adj_close_1a_inicio = sub_1a["Adj Close"].iloc[0]
        adj_close_actual = hist["Adj Close"].iloc[-1]
        rent_1a = (adj_close_actual / adj_close_1a_inicio - 1.0) * 100.0
    else:
        rent_1a = 0.0

    # 4. Rentabilidad anualizada 3 años (%) con fechas reales
    adj_close_primero = hist["Adj Close"].iloc[0]
    adj_close_ultimo = hist["Adj Close"].iloc[-1]
    dias_transcurridos = (hist.index[-1] - hist.index[0]).days
    anos_transcurridos = dias_transcurridos / 365.25

    if anos_transcurridos > 0 and adj_close_primero > 0:
        ratio_3a = adj_close_ultimo / adj_close_primero
        if ratio_3a > 0:
            rent_anual_3a = ((ratio_3a ** (1.0 / anos_transcurridos)) - 1.0) * 100.0
        else:
            rent_anual_3a = -100.0
    else:
        rent_anual_3a = 0.0

    # 5. Volatilidad anual (%) del último año con Adj Close
    hist_1a = hist.loc[hist.index >= fecha_hace_1a].copy()
    if len(hist_1a) >= 20:
        rendimientos_log = (hist_1a["Adj Close"] / hist_1a["Adj Close"].shift(1)).apply(
            lambda x: math.log(x) if x > 0 else 0
        ).dropna()
        desv_est = rendimientos_log.std()
        volatilidad_anual = desv_est * math.sqrt(252) * 100.0
    else:
        # Fallback a todo el dataset si hay menos de 1 año
        rendimientos_log = (hist["Adj Close"] / hist["Adj Close"].shift(1)).apply(
            lambda x: math.log(x) if x > 0 else 0
        ).dropna()
        desv_est = rendimientos_log.std()
        volatilidad_anual = desv_est * math.sqrt(252) * 100.0

    # 6. Caída máxima en 1 año (%) (Max Drawdown, negativa)
    if len(hist_1a) >= 5:
        precios_1a = hist_1a["Close"]
    else:
        precios_1a = hist["Close"]
    pico_acumulado = precios_1a.cummax()
    drawdowns = (precios_1a - pico_acumulado) / pico_acumulado
    caida_maxima_1a = float(drawdowns.min() * 100.0)

    # 7. Rendimiento por dividendo (%) en los últimos 365 días
    if "Dividends" in hist.columns:
        fecha_365d = hist.index[-1] - timedelta(days=365)
        divs_1a = hist.loc[hist.index >= fecha_365d, "Dividends"].sum()
        dividendo_rend = (divs_1a / precio * 100.0) if precio > 0 else 0.0
    else:
        dividendo_rend = 0.0

    # 8. Histórico mensual de los 3 años: último Close de cada mes
    # Agrupar por año y mes
    hist["YearMonth"] = hist.index.to_period("M")
    mensual = hist.groupby("YearMonth")["Close"].last()
    historico = []
    for ym, cierre_mes in mensual.items():
        historico.append({
            "mes": str(ym),
            "cierre": float(round(cierre_mes, 2))
        })

    return {
        "ticker": ticker_sym,
        "nombre": nombre,
        "nemotecnico": nemotecnico,
        "sector": sector,
        "moneda": "COP",
        "precio": precio,
        "fecha": fecha_cierre,
        "variacion_dia_pct": round(variacion_dia, 2),
        "rent_1a_pct": round(rent_1a, 2),
        "rent_anual_3a_pct": round(rent_anual_3a, 2),
        "volatilidad_anual_pct": round(volatilidad_anual, 2),
        "caida_maxima_1a_pct": round(caida_maxima_1a, 2),
        "dividendo_rend_pct": round(dividendo_rend, 2),
        "historico": historico
    }

def obtener_trm():
    """
    Descarga la TRM representativa desde USDCOP=X en Yahoo Finance.
    """
    try:
        trm_ticker = yf.Ticker("USDCOP=X")
        trm_hist = trm_ticker.history(period="5d")
        if not trm_hist.empty:
            ultimo = trm_hist["Close"].iloc[-1]
            fecha_trm = pd.to_datetime(trm_hist.index[-1]).strftime("%Y-%m-%d")
            return {
                "valor": round(float(ultimo), 2),
                "fecha": fecha_trm
            }
    except Exception as e:
        print(f"Aviso: no se pudo obtener TRM ({e})")
    return None

def main():
    print("Iniciando actualización de datos del mercado colombiano...")
    acciones_procesadas = []
    lista_errores = []

    for ticker_sym, nombre, nemotecnico, sector in ACCIONES_CONFIG:
        print(f"Procesando {nemotecnico} ({ticker_sym})...")
        try:
            datos = obtener_datos_accion(ticker_sym, nombre, nemotecnico, sector)
            acciones_procesadas.append(datos)
            print(f"  -> OK: Precio = ${datos['precio']} COP, Rent. 3A = {datos['rent_anual_3a_pct']}%")
        except Exception as e:
            msg = str(e)
            print(f"  -> ERROR en {ticker_sym}: {msg}")
            lista_errores.append({"ticker": ticker_sym, "motivo": msg})

    # TRM
    trm_data = obtener_trm()

    # Si TODAS fallan, no sobrescribir datos.json si ya existe
    if len(acciones_procesadas) == 0:
        print("ALERTA: Todas las acciones fallaron al descargar. No se sobrescribirá datos.json.")
        if os.path.exists("datos.json"):
            print("Se conserva el archivo datos.json previo.")
        sys.exit(0)

    # Estructura exacta requerida
    fecha_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    salida = {
        "actualizado": fecha_utc,
        "fuente": "Yahoo Finance (yfinance); rentabilidades con precio ajustado por dividendos",
        "trm": trm_data if trm_data else {"valor": 0, "fecha": ""},
        "acciones": acciones_procesadas,
        "errores": lista_errores
    }

    with open("datos.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print("\n--- RESUMEN DE ACTUALIZACIÓN ---")
    print(f"Acciones actualizadas con éxito: {len(acciones_procesadas)} de {len(ACCIONES_CONFIG)}")
    if lista_errores:
        print("Acciones con error:")
        for err in lista_errores:
            print(f"  - {err['ticker']}: {err['motivo']}")
    else:
        print("Todas las acciones se descargaron correctamente.")
    print("Archivo datos.json generado exitosamente.")

if __name__ == "__main__":
    main()
