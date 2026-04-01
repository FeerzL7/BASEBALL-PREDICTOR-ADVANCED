# tracking/roi_tracker.py
import csv
import os
from datetime import datetime, timedelta

ROI_FILE = "output/roi_tracking.csv"

# Techo de Kelly: nunca apostar más del 5% del bankroll por pick
KELLY_MAX_STAKE_PCT = 5.0


def inicializar_tracking():
    if not os.path.exists(ROI_FILE):
        with open(ROI_FILE, mode='w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow([
                "fecha", "juego", "mercado", "seleccion", "cuota", "probabilidad",
                "valor", "resultado", "ganancia"
            ])


def registrar_pick(fecha, juego, mercado, seleccion, cuota, probabilidad, valor, resultado="pendiente"):
    ganancia = (cuota - 1) if resultado == "win" else (-1 if resultado == "lose" else 0)
    with open(ROI_FILE, mode='a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        writer.writerow([fecha, juego, mercado, seleccion, cuota, probabilidad, valor, resultado, ganancia])


def _parsear_marcador(linescore):
    """Extrae runs de home y away del linescore de statsapi."""
    try:
        home = int(linescore.get("teams", {}).get("home", {}).get("runs", -1))
        away = int(linescore.get("teams", {}).get("away", {}).get("runs", -1))
        return home, away
    except Exception:
        return -1, -1


def _resolver_resultado(seleccion, mercado, home_team, away_team, home_runs, away_runs, linea=None):
    """
    Devuelve 'win', 'lose' o 'pendiente' según el mercado y la selección.
    """
    if home_runs < 0 or away_runs < 0:
        return "pendiente"

    mercado = mercado.upper()

    if mercado == "ML":
        ganador = home_team if home_runs > away_runs else away_team
        return "win" if seleccion == ganador else "lose"

    if mercado == "RL":
        # Runline estándar -1.5 para el favorito
        if seleccion == home_team:
            return "win" if (home_runs - away_runs) >= 2 else "lose"
        else:
            return "win" if (away_runs - home_runs) >= 2 else "lose"

    if mercado == "TOTAL":
        if linea is None:
            return "pendiente"
        total = home_runs + away_runs
        if seleccion.upper() == "OVER":
            return "win" if total > linea else "lose"
        if seleccion.upper() == "UNDER":
            return "win" if total < linea else "lose"

    return "pendiente"


def actualizar_resultados():
    """
    Lee el CSV, busca picks 'pendiente' de ayer o antes, consulta
    MLB statsapi para obtener el marcador final y actualiza el resultado.
    """
    try:
        from statsapi import schedule
    except ImportError:
        print("[WARNING] statsapi no disponible, no se pueden actualizar resultados.")
        return

    if not os.path.exists(ROI_FILE):
        print("[INFO] No existe archivo de tracking todavía.")
        return

    with open(ROI_FILE, mode='r', encoding='utf-8-sig') as f:
        filas = list(csv.reader(f))

    if len(filas) <= 1:
        print("[INFO] Sin picks registrados para actualizar.")
        return

    encabezado = filas[0]
    registros = filas[1:]
    actualizados = 0
    hoy = datetime.now().date()

    # Cachear schedules por fecha para no repetir llamadas
    cache_schedule = {}

    for i, fila in enumerate(registros):
        if len(fila) < 9:
            continue
        fecha_str, juego, mercado, seleccion, cuota, probabilidad, valor, resultado, ganancia = fila

        if resultado != "pendiente":
            continue

        try:
            fecha_pick = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        # Solo actualizar picks de días anteriores (el juego ya terminó)
        if fecha_pick >= hoy:
            continue

        if fecha_str not in cache_schedule:
            try:
                cache_schedule[fecha_str] = schedule(date=fecha_str)
            except Exception as e:
                print(f"[ERROR] No se pudo obtener schedule para {fecha_str}: {e}")
                cache_schedule[fecha_str] = []

        juegos_dia = cache_schedule[fecha_str]

        # Intentar hacer match del juego "Away @ Home"
        partes = juego.split(" @ ")
        if len(partes) != 2:
            continue
        away_pick, home_pick = partes[0].strip(), partes[1].strip()

        juego_encontrado = None
        for j in juegos_dia:
            if j.get("status") not in ("Final", "Game Over", "Completed Early"):
                continue
            h = j.get("home_name", "")
            a = j.get("away_name", "")
            if away_pick.lower() in a.lower() or a.lower() in away_pick.lower():
                if home_pick.lower() in h.lower() or h.lower() in home_pick.lower():
                    juego_encontrado = j
                    break

        if not juego_encontrado:
            continue

        home_runs = juego_encontrado.get("home_score", -1)
        away_runs = juego_encontrado.get("away_score", -1)

        if home_runs < 0 or away_runs < 0:
            continue

        home_team = juego_encontrado.get("home_name", "")
        away_team = juego_encontrado.get("away_name", "")

        # Detectar linea_total si viene en el campo seleccion (ej: "Over 8.5")
        linea_total = None
        sel_limpia = seleccion
        if mercado.upper() == "TOTAL":
            partes_sel = seleccion.split()
            if len(partes_sel) == 2:
                sel_limpia = partes_sel[0]
                try:
                    linea_total = float(partes_sel[1])
                except ValueError:
                    pass

        nuevo_resultado = _resolver_resultado(
            sel_limpia, mercado, home_team, away_team,
            int(home_runs), int(away_runs), linea_total
        )

        if nuevo_resultado == "pendiente":
            continue

        nueva_ganancia = (float(cuota) - 1) if nuevo_resultado == "win" else -1.0
        registros[i] = [
            fecha_str, juego, mercado, seleccion, cuota, probabilidad,
            valor, nuevo_resultado, round(nueva_ganancia, 4)
        ]
        actualizados += 1
        estado = "WIN" if nuevo_resultado == "win" else "LOSE"
        print(f"  [{estado}] {juego} | {mercado} {seleccion} "
              f"({home_team} {home_runs} - {away_runs} {away_team})")

    # Reescribir el CSV completo con los resultados actualizados
    with open(ROI_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(encabezado)
        writer.writerows(registros)

    print(f"[INFO] Resultados actualizados: {actualizados} pick(s) resueltos.")


def calcular_roi():
    total_apuestas = 0
    wins = 0
    ganancias = 0.0
    pendientes = 0

    if not os.path.exists(ROI_FILE):
        return {"total_apuestas": 0, "wins": 0, "ganancias": 0.0, "roi": 0.0, "pendientes": 0}

    with open(ROI_FILE, mode='r', encoding='utf-8-sig') as file:
        reader = csv.reader(file)
        next(reader, None)
        for row in reader:
            if len(row) < 9:
                continue
            resultado = row[7]
            if resultado == "pendiente":
                pendientes += 1
                continue
            total_apuestas += 1
            ganancia = float(row[8])
            ganancias += ganancia
            if resultado == "win":
                wins += 1

    roi = (ganancias / total_apuestas) * 100 if total_apuestas > 0 else 0.0
    return {
        "total_apuestas": total_apuestas,
        "wins": wins,
        "ganancias": round(ganancias, 2),
        "roi": round(roi, 2),
        "pendientes": pendientes
    }