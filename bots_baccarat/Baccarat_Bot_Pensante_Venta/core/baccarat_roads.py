import logging
logger = logging.getLogger("BaccaratRoads")


def build_big_road(history):
    clean = [x for x in history if x in ("P", "B")]
    if not clean:
        return []
    columns = []
    current_col = [clean[0]]
    for i in range(1, len(clean)):
        if clean[i] == clean[i - 1]:
            current_col.append(clean[i])
        else:
            columns.append(current_col)
            current_col = [clean[i]]
    columns.append(current_col)
    return columns


def _derive_road(columns, look_back):
    result = []
    for col_idx in range(look_back, len(columns)):
        col = columns[col_idx]
        ref_col = columns[col_idx - look_back]
        for row_idx in range(len(col)):
            if row_idx == 0:
                result.append("R" if len(ref_col) > 1 else "B")
            else:
                result.append("R" if row_idx < len(ref_col) else "B")
    return result


def calculate_all_roads(history):
    """
    Calcula Big Road, Big Eye Boy, Small Road y Cockroach Road.
    Retorna consenso de prediccion (P/B) y fuerza del consenso (0.0-1.0).
    """
    clean = [x for x in history if x in ("P", "B")]
    columns = build_big_road(clean)

    big_eye_boy = _derive_road(columns, 1)
    small_road  = _derive_road(columns, 2)
    cockroach   = _derive_road(columns, 3)

    def last_val(road):
        return road[-1] if road else None

    beb_last    = last_val(big_eye_boy)
    sr_last     = last_val(small_road)
    cr_last     = last_val(cockroach)
    last_result = clean[-1] if clean else None

    def road_prediction(road_val, last_res):
        if road_val is None or last_res is None:
            return None
        # R = Repeticion = mismo color; B = Alternancia = color opuesto
        if road_val == "R":
            return last_res
        return "B" if last_res == "P" else "P"

    preds = [
        road_prediction(beb_last, last_result),
        road_prediction(sr_last,  last_result),
        road_prediction(cr_last,  last_result),
    ]
    valid_preds = [p for p in preds if p is not None]

    consensus_next     = None
    consensus_strength = 0.0

    if valid_preds:
        p_votes = valid_preds.count("P")
        b_votes = valid_preds.count("B")
        if p_votes > b_votes:
            consensus_next     = "P"
            consensus_strength = p_votes / len(valid_preds)
        elif b_votes > p_votes:
            consensus_next     = "B"
            consensus_strength = b_votes / len(valid_preds)
        else:
            consensus_next     = last_result
            consensus_strength = 0.5

    current_streak = len(columns[-1]) if columns else 0
    current_color  = columns[-1][0]   if columns else None
    num_columns    = len(columns)
    avg_streak     = sum(len(c) for c in columns) / num_columns if num_columns else 0

    def bname(v):
        return "Repeticion" if v == "R" else ("Alternancia" if v == "B" else "N/A")

    if consensus_next == "P":
        pred_color = "JUGADOR"
    elif consensus_next == "B":
        pred_color = "BANCA"
    else:
        pred_color = "Indefinido"

    strength_pct = int(consensus_strength * 100)

    lines = [
        "ANALISIS MULTI-ROAD:",
        f"  Big Road: {num_columns} columnas | Racha actual: {current_streak}x {current_color} | Racha promedio: {avg_streak:.1f}",
        f"  Big Eye Boy: {bname(beb_last)}",
        f"  Small Road: {bname(sr_last)}",
        f"  Cockroach Road: {bname(cr_last)}",
        f"  Consenso de los 3 derivados: {pred_color} (Fuerza: {strength_pct}%)",
    ]
    if consensus_strength >= 1.0:
        lines.append("  SENAL PERFECTA: Los 3 roads coinciden. Maxima confianza estadistica.")
    elif consensus_strength >= 0.67:
        lines.append("  SENAL FUERTE: 2 de 3 roads coinciden. Alta confianza.")
    else:
        lines.append("  SENAL DEBIL: Roads divididos. Proceder con cautela.")

    analysis_text = "\n".join(lines) + "\n"
    logger.debug(f"Roads: BEB={beb_last}, SR={sr_last}, CR={cr_last} -> Consenso: {consensus_next} ({strength_pct}%)")

    return {
        "columns":            columns,
        "big_eye_boy":        big_eye_boy,
        "small_road":         small_road,
        "cockroach":          cockroach,
        "consensus_next":     consensus_next,
        "consensus_strength": consensus_strength,
        "current_streak":     current_streak,
        "current_color":      current_color,
        "num_columns":        num_columns,
        "avg_streak":         avg_streak,
        "analysis_text":      analysis_text,
        "beb_last":           beb_last,
        "sr_last":            sr_last,
        "cr_last":            cr_last,
    }
