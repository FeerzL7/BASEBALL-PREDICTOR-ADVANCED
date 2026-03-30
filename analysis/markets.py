import difflib
import unicodedata
from difflib import SequenceMatcher

def normalizar(texto):
    if not texto:
        return ''
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')
    return texto.lower().strip()

def match_nombre_equipo(nombre, lista_opciones):
    nombre_normalizado = normalizar(nombre)
    mejor_match = None
    mejor_score = 0.0
    for opcion in lista_opciones:
        score = SequenceMatcher(None, nombre_normalizado, normalizar(opcion)).ratio()
        if score > mejor_score and score > 0.6:
            mejor_score = score
            mejor_match = opcion
    return mejor_match

def extraer_mejores_cuotas(evento, mercado_clave):
    try:
        mercados = evento["bookmakers"]
        mejores = {
            "over": None,
            "under": None,
            "home": None,
            "away": None,
            "total_line": None
        }

        for book in mercados:
            for market in book.get("markets", []):
                if market["key"] != mercado_clave:
                    continue

                #if mercado_clave == "totals":
                    #print(f"\n[DEBUG 🔍] Mercado 'totals' encontrado en {evento['home_team']} vs {evento['away_team']}")
                    #import json
                    #print(json.dumps(market, indent=2))

                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "").lower()
                    price = outcome.get("price")
                    point = outcome.get("point", None)

                    if mercado_clave == "totals":
                        if "over" in name:
                            #print(f"[DEBUG ✅] Over detectado: cuota={price}, línea={point}")
                            if mejores["over"] is None or price > mejores["over"]:
                                mejores["over"] = price
                                mejores["total_line"] = point
                        elif "under" in name:
                            #print(f"[DEBUG ✅] Under detectado: cuota={price}, línea={point}")
                            if mejores["under"] is None or price > mejores["under"]:
                                mejores["under"] = price
                                mejores["total_line"] = point
                        else:
                            print(f"[DEBUG ⚠️] Resultado inesperado en 'totals': {name}")

                    elif mercado_clave == "h2h":
                        if normalizar(name) == normalizar(evento['home_team']):
                            if mejores["home"] is None or price > mejores["home"]:
                                mejores["home"] = price
                        elif normalizar(name) == normalizar(evento['away_team']):
                            if mejores["away"] is None or price > mejores["away"]:
                                mejores["away"] = price

                    elif mercado_clave == "spreads":
                        if normalizar(name) == normalizar(evento['home_team']):
                            if mejores["home"] is None or price > mejores["home"]:
                                mejores["home"] = price
                        elif normalizar(name) == normalizar(evento['away_team']):
                            if mejores["away"] is None or price > mejores["away"]:
                                mejores["away"] = price

        return mejores

    except Exception as e:
        print(f"[ERROR] al extraer cuotas ({mercado_clave}): {e}")
        return {"over": None, "under": None, "home": None, "away": None, "total_line": None}

def analizar_mercados(partidos, cuotas_api):
    print("[DEBUG] Procesando mercados de apuestas...")

    eventos = cuotas_api
    equipos_eventos = [f"{evento['home_team']} vs {evento['away_team']}" for evento in eventos]

    #if eventos:
        #print(f"[DEBUG] Markets disponibles: {[m['key'] for m in eventos[0]['bookmakers'][0]['markets']]}")
    #else:
        #print("[WARNING] No se encontraron eventos en cuotas_api")

    for partido in partidos:
        home = partido["home_team"]
        away = partido["away_team"]

        nombre_match = match_nombre_equipo(f"{home} vs {away}", equipos_eventos)
        evento = None

        if nombre_match:
            for ev in eventos:
                if normalizar(f"{ev['home_team']} vs {ev['away_team']}") == normalizar(nombre_match):
                    evento = ev
                    break

        #if not evento:
            #print(f"[WARNING] No se encontró evento para: {home} vs {away}")
            #continue

        #print(f"[DEBUG MATCHING] Buscando: {home} vs {away}")
        #print(f"[DEBUG MATCHING] Resultado normalizado: {normalizar(f'{home} vs {away}')} → Match encontrado: {nombre_match}")

        # ML
        ml = extraer_mejores_cuotas(evento, "h2h")
        partido["cuota_home"] = ml["home"]
        partido["cuota_away"] = ml["away"]

        # RL
        rl = extraer_mejores_cuotas(evento, "spreads")
        partido["cuota_rl_home"] = rl["home"]
        partido["cuota_rl_away"] = rl["away"]

        # Totales
        tot = extraer_mejores_cuotas(evento, "totals")

        if tot.get("over") is not None and tot.get("under") is not None and tot.get("total_line") is not None:
            partido["cuota_over"] = tot["over"]
            partido["cuota_under"] = tot["under"]
            partido["linea_total"] = tot["total_line"]
            #print(f"[DEBUG ✅] Totales cargados correctamente para {home} vs {away}: Over {tot['total_line']} @ {tot['over']} | Under {tot['total_line']} @ {tot['under']}")
        else:
            print(f"[WARNING] Cuotas de Totales incompletas o ausentes para {home} vs {away}")
            partido["cuota_over"] = None
            partido["cuota_under"] = None
            partido["linea_total"] = None

    return partidos