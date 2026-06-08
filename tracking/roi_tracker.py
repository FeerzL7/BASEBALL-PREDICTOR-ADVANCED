from datetime import datetime

from bankroll.tracker import (
    exportar_reportes,
    inicializar_ledger,
    leer_registros,
    liquidar_registro,
    metricas_acumuladas,
    registrar_apuesta,
    escribir_registros,
    bankroll_actual,
)


def inicializar_tracking():
    inicializar_ledger()


def _picks_existentes() -> set:
    return {
        (
            str(row.get("fecha", "")),
            str(row.get("juego", "")),
            str(row.get("mercado", "")),
            str(row.get("seleccion", "")),
        )
        for row in leer_registros()
    }


def registrar_pick(fecha, juego, mercado, seleccion, cuota,
                   probabilidad, valor, resultado="pendiente",
                   stake_pct=1):
    """
    Registra un pick con stake porcentual entero sobre el bankroll actual.

    Se conserva el nombre historico de la funcion para no romper main.py ni
    scripts existentes. El nuevo ledger guarda monto, bankroll y yield.
    """
    registrar_apuesta(
        fecha=fecha,
        juego=juego,
        mercado=mercado,
        seleccion=seleccion,
        cuota=cuota,
        probabilidad=probabilidad,
        valor=valor,
        stake_pct=int(stake_pct or 0),
        resultado=resultado,
    )


def _resolver_resultado(seleccion, mercado, home_team, away_team,
                        home_runs, away_runs, linea=None):
    if home_runs < 0 or away_runs < 0:
        return "pendiente"

    mercado = mercado.upper()

    if mercado == "ML":
        ganador = home_team if home_runs > away_runs else away_team
        return "win" if seleccion == ganador else "lose"

    if mercado == "RL":
        partes = seleccion.rsplit(" ", 1)
        equipo = seleccion
        handicap = -1.5
        if len(partes) == 2:
            try:
                handicap = float(partes[1])
                equipo = partes[0]
            except ValueError:
                pass

        if equipo == home_team:
            margen = home_runs - away_runs + handicap
        else:
            margen = away_runs - home_runs + handicap
        if margen > 0:
            return "win"
        if margen == 0:
            return "null"
        return "lose"

    if mercado == "TOTAL":
        if linea is None:
            return "pendiente"
        total = home_runs + away_runs
        if seleccion.upper() == "OVER":
            if total > linea:
                return "win"
            if total == linea:
                return "null"
            return "lose"
        if seleccion.upper() == "UNDER":
            if total < linea:
                return "win"
            if total == linea:
                return "null"
            return "lose"

    return "pendiente"


def actualizar_resultados():
    """
    Resuelve picks pendientes, actualiza bankroll y reexporta reportes.
    """
    try:
        from statsapi import schedule
    except ImportError:
        print("[WARNING] statsapi no disponible.")
        return

    registros = leer_registros()
    if not registros:
        return

    actualizados = 0
    hoy = datetime.now().date()
    cache_schedule = {}
    bankroll = bankroll_actual(registros)

    for i, row in enumerate(registros):
        if row.get("resultado") != "pendiente":
            continue

        fecha_str = str(row.get("fecha", ""))
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

        juego = str(row.get("juego", ""))
        partes = juego.split(" @ ")
        if len(partes) != 2:
            continue
        away_pick, home_pick = partes[0].strip(), partes[1].strip()

        juego_encontrado = None
        for game in cache_schedule[fecha_str]:
            if game.get("status") not in ("Final", "Game Over", "Completed Early"):
                continue
            h = game.get("home_name", "")
            a = game.get("away_name", "")
            if (away_pick.lower() in a.lower() or a.lower() in away_pick.lower()) and \
               (home_pick.lower() in h.lower() or h.lower() in home_pick.lower()):
                juego_encontrado = game
                break

        if not juego_encontrado:
            continue

        home_runs = juego_encontrado.get("home_score", -1)
        away_runs = juego_encontrado.get("away_score", -1)
        if home_runs < 0 or away_runs < 0:
            continue

        home_team = juego_encontrado.get("home_name", "")
        away_team = juego_encontrado.get("away_name", "")
        mercado = str(row.get("mercado", ""))
        seleccion = str(row.get("seleccion", ""))

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

        registros[i] = liquidar_registro(row, nuevo_resultado, bankroll)
        bankroll = float(registros[i].get("bankroll_after") or bankroll)

        estado = "PUSH" if nuevo_resultado == "null" else (
            "WIN" if nuevo_resultado == "win" else "LOSE"
        )
        print(f"  [{estado}] {juego} | {mercado} {seleccion} "
              f"({home_team} {home_runs} - {away_runs} {away_team})")
        actualizados += 1

    escribir_registros(registros)
    exportar_reportes(registros)
    print(f"[INFO] Resultados actualizados: {actualizados} pick(s) resueltos.")


def calcular_roi() -> dict:
    return metricas_acumuladas()

