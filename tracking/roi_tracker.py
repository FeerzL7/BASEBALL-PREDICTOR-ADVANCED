# tracking/roi_tracker.py
import csv
import os
from datetime import datetime

ROI_FILE = "output/roi_tracking.csv"

KELLY_MAX_STAKE_PCT = 5.0


def inicializar_tracking():
    if not os.path.exists(ROI_FILE):
        with open(ROI_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
            csv.writer(f).writerow([
                "fecha", "juego", "mercado", "seleccion", "cuota",
                "probabilidad", "valor", "resultado", "ganancia"
            ])


def _picks_existentes() -> set:
    """
    Devuelve un set de tuplas (fecha, juego, mercado, seleccion)
    para todos los picks ya registrados — pendientes o resueltos.
    Usado para evitar duplicados al registrar picks del día.
    """
    existentes = set()
    if not os.path.exists(ROI_FILE):
        return existentes
    with open(ROI_FILE, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if len(row) >= 4:
                existentes.add((row[0], row[1], row[2], row[3]))
    return existentes


def registrar_pick(fecha, juego, mercado, seleccion, cuota,
                   probabilidad, valor, resultado="pendiente"):
    """
    Registra un pick solo si no existe ya la misma combinación
    (fecha, juego, mercado, seleccion) en el archivo.
    Evita duplicados en ejecuciones consecutivas del mismo día.
    """
    clave = (str(fecha), str(juego), str(mercado), str(seleccion))
    if clave in _picks_existentes():
        return  # ya registrado, no duplicar

    ganancia = (float(cuota) - 1) if resultado == "win" else \
               (-1.0 if resultado == "lose" else 0)

    with open(ROI_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        csv.writer(f).writerow([
            fecha, juego, mercado, seleccion, cuota,
            probabilidad, valor, resultado, ganancia
        ])


def _parsear_marcador(linescore):
    try:
        home = int(linescore.get("teams", {}).get("home", {}).get("runs", -1))
        away = int(linescore.get("teams", {}).get("away", {}).get("runs", -1))
        return home, away
    except Exception:
        return -1, -1


def _resolver_resultado(seleccion, mercado, home_team, away_team,
                        home_runs, away_runs, linea=None):
    if home_runs < 0 or away_runs < 0:
        return "pendiente"

    mercado = mercado.upper()

    if mercado == "ML":
        ganador = home_team if home_runs > away_runs else away_team
        return "win" if seleccion == ganador else "lose"

    if mercado == "RL":
        if seleccion == home_team:
            return "win" if (home_runs - away_runs) >= 2 else "lose"
        else:
            return "win" if (away_runs - home_runs) >= 2 else "lose"

    if mercado == "TOTAL":
        if linea is None:
            return "pendiente"
        total = home_runs + away_runs
        if seleccion.upper() == "OVER":
            if total > linea:  return "win"
            if total == linea: return "null"   # push
            return "lose"
        if seleccion.upper() == "UNDER":
            if total < linea:  return "win"
            if total == linea: return "null"   # push
            return "lose"

    return "pendiente"


def actualizar_resultados():
    """
    Lee el CSV, resuelve picks 'pendiente' de días anteriores
    consultando MLB statsapi, y reescribe el archivo.
    Nunca procesa el mismo pick dos veces — la condición resultado != 'pendiente'
    ya evita reprocesar picks resueltos.
    """
    try:
        from statsapi import schedule
    except ImportError:
        print("[WARNING] statsapi no disponible.")
        return

    if not os.path.exists(ROI_FILE):
        return

    with open(ROI_FILE, mode='r', encoding='utf-8-sig') as f:
        filas = list(csv.reader(f))

    if len(filas) <= 1:
        return

    encabezado = filas[0]
    registros  = filas[1:]
    actualizados = 0
    hoy = datetime.now().date()
    cache_schedule = {}

    for i, fila in enumerate(registros):
        if len(fila) < 9:
            continue

        fecha_str, juego, mercado, seleccion, cuota, \
            probabilidad, valor, resultado, ganancia = fila

        if resultado != "pendiente":
            continue

        try:
            fecha_pick = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        if fecha_pick >= hoy:
            continue

        if fecha_str not in cache_schedule:
            try:
                cache_schedule[fecha_str] = schedule(date=fecha_str)
            except Exception as e:
                print(f"[WARNING] Schedule {fecha_str}: {e}")
                cache_schedule[fecha_str] = []

        partes = juego.split(" @ ")
        if len(partes) != 2:
            continue
        away_pick, home_pick = partes[0].strip(), partes[1].strip()

        juego_encontrado = None
        for j in cache_schedule[fecha_str]:
            if j.get("status") not in ("Final", "Game Over", "Completed Early"):
                continue
            h = j.get("home_name", "")
            a = j.get("away_name", "")
            if (away_pick.lower() in a.lower() or a.lower() in away_pick.lower()) and \
               (home_pick.lower() in h.lower() or h.lower() in home_pick.lower()):
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

        linea_total = None
        sel_limpia  = seleccion
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
        estado = "WIN" if nuevo_resultado == "win" else "LOSE"
        print(f"  [{estado}] {juego} | {mercado} {seleccion} "
              f"({home_team} {home_runs} - {away_runs} {away_team})")

        registros[i] = [ # type: ignore
            fecha_str, juego, mercado, seleccion, cuota, probabilidad,
            valor, nuevo_resultado, round(nueva_ganancia, 4)
        ]
        actualizados += 1

    with open(ROI_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(encabezado)
        writer.writerows(registros)

    print(f"[INFO] Resultados actualizados: {actualizados} pick(s) resueltos.")


def calcular_roi() -> dict:
    total_apuestas = 0
    wins           = 0
    ganancias      = 0.0
    pendientes     = 0

    if not os.path.exists(ROI_FILE):
        return {"total_apuestas": 0, "wins": 0,
                "ganancias": 0.0, "roi": 0.0, "pendientes": 0}

    with open(ROI_FILE, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 9:
                continue
            resultado = row[7]
            if resultado == "pendiente":
                pendientes += 1
                continue
            if resultado == "null":        # push — no cuenta como apuesta resuelta
                continue
            total_apuestas += 1
            ganancias += float(row[8])
            if resultado == "win":
                wins += 1

    roi = (ganancias / total_apuestas * 100) if total_apuestas > 0 else 0.0
    return {
        "total_apuestas": total_apuestas,
        "wins":           wins,
        "ganancias":      round(ganancias, 2),
        "roi":            round(roi, 2),
        "pendientes":     pendientes,
    }