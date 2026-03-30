from utils.constants import PARK_FACTORS

def ajustar_park_factor(base_pf, contexto):
    """Ajusta el park factor según clima y condiciones."""
    if not contexto:
        return base_pf  # Sin datos de contexto, no ajustar

    temperatura = contexto.get("clima", {}).get("temperatura", 22)
    viento = contexto.get("clima", {}).get("viento_kph", 10)
    condiciones = contexto.get("clima", {}).get("condiciones", "")

    ajuste = 1.0

    if temperatura >= 28:
        ajuste += 0.05  # Calor → más bateo
    elif temperatura <= 15:
        ajuste -= 0.05  # Frío → menos bateo

    if viento >= 15:
        ajuste += 0.05  # Viento fuerte puede favorecer HR (simplificado)

    # Si es de noche, se puede reducir ligeramente la ofensiva (opcional)
    hora = contexto.get("hora_local", 19)
    if hora >= 20:
        ajuste -= 0.02

    pf_final = round(base_pf * ajuste, 3)
    return max(pf_final, 0.85)  # evitar valores demasiado bajos


def proyectar_carreras(ofensiva, pitcheo, park_factor):
    base = ofensiva['runs_last_5'] * (2 - pitcheo['ERA'] / 5)
    ajuste_mano = ofensiva['OPS'] / 0.73
    return round(base * ajuste_mano * park_factor, 3)


def proyectar_totales(partidos):
    for partido in partidos:
        venue = partido.get('venue', 'default')
        pf_base = PARK_FACTORS.get(venue, 1.0)

        # NUEVO: ajustar según contexto climático
        contexto = partido.get('contexto', {})
        pf_ajustado = ajustar_park_factor(pf_base, contexto)

        home_proj = proyectar_carreras(partido['home_offense'], partido['away_stats'], pf_ajustado)
        away_proj = proyectar_carreras(partido['away_offense'], partido['home_stats'], pf_ajustado)

        partido['proj_home'] = home_proj
        partido['proj_away'] = away_proj
        partido['proj_total'] = round(home_proj + away_proj, 3)
        partido['park_factor_usado'] = pf_ajustado  # para trazabilidad

    return partidos
