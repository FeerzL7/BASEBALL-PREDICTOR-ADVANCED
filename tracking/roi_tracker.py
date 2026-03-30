# tracking/roi_tracker.py
import csv
import os

ROI_FILE = "output/roi_tracking.csv"

def inicializar_tracking():
    if not os.path.exists(ROI_FILE):
        with open(ROI_FILE, mode='w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow([
                "fecha", "juego", "mercado", "seleccion", "cuota", "probabilidad",
                "valor", "resultado", "ganancia"
            ])

def registrar_pick(fecha, juego, mercado, seleccion, cuota, probabilidad, valor, resultado):
    ganancia = (cuota - 1) if resultado == "win" else -1
    with open(ROI_FILE, mode='a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        writer.writerow([fecha, juego, mercado, seleccion, cuota, probabilidad, valor, resultado, ganancia])

def calcular_roi():
    total_apuestas = 0
    ganancias = 0
    with open(ROI_FILE, mode='r', encoding='utf-8-sig') as file:
        next(file)  # skip header
        for row in csv.reader(file):
            total_apuestas += 1
            ganancias += float(row[8])
    roi = (ganancias / total_apuestas) * 100 if total_apuestas > 0 else 0
    return {
        "total_apuestas": total_apuestas,
        "ganancias": round(ganancias, 2),
        "roi": round(roi, 2)
    }
