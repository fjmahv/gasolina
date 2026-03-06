#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fuel Analysis System v1.9
- Añadida fecha de primer y último repostaje por coche.
- Métricas de velocidad "lifetime" (solo coches con tiempo).
- Históricos anuales y mensuales (Global y por Vehículo).
- Lógica de discontinuidad por KM (2000 km).
"""

import sys
import csv
import json
import os
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple

# ============================================================================
# CONFIGURACIÓN
# ============================================================================
CARS_FILE = "cars.csv"
FUELS_FILE = "fuels.csv"
OUTPUT_FILE = "Gasolina.json"
DISCONTINUITY_THRESHOLD_KM = 2000
CSV_SEPARATOR_REFUELS = ";"
CARS_WITHOUT_TEMPORAL_DATA = [1, 2]

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

@dataclass
class Refuel:
    car_id: int
    refuel_date: datetime
    refuel_litres: float
    refuel_mileage: float
    refuel_price_per_litre: float
    refuel_type: int
    trip_hours: int
    trip_minutes: int
    
    @property
    def total_cost(self) -> float:
        return self.refuel_litres * self.refuel_price_per_litre
    
    @property
    def trip_time_hours(self) -> float:
        return self.trip_hours + (self.trip_minutes / 60)

@dataclass
class Car:
    car_id: int
    brand: str
    color: str
    model: str
    number_plate: str
    fuel_type: str

    def __post_init__(self):
        self.has_temporal_data = self.car_id not in CARS_WITHOUT_TEMPORAL_DATA

# ============================================================================
# PROCESAMIENTO
# ============================================================================
def parse_decimal(value: str) -> float:
    if not value: return 0.0
    return float(str(value).replace(",", "."))

def load_data(refuels_path: str):
    cars, fuels, refuels = {}, {}, []
    try:
        with open(CARS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                c = Car(car_id=int(row['carId']), brand=row['carBrand'], color=row['carColor'], 
                        model=row['carModel'], number_plate=row['carNumberPlate'], fuel_type=row['carFuel'])
                cars[c.car_id] = c
        with open(FUELS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                fuels[int(row['fuelId'])] = row['fuelDescription']
        with open(refuels_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=CSV_SEPARATOR_REFUELS)
            for row in reader:
                refuels.append(Refuel(
                    car_id=int(row['carId']),
                    refuel_date=datetime.strptime(row['refuelDate'], "%Y-%m-%d"),
                    refuel_litres=parse_decimal(row['refuelLitres']),
                    refuel_mileage=parse_decimal(row['refuelMilleage']),
                    refuel_price_per_litre=parse_decimal(row['refuelPricePerLitre']),
                    refuel_type=int(row['refuelType']),
                    trip_hours=int(row['tripHours']),
                    trip_minutes=int(row['tripMinutes'])
                ))
    except Exception as e:
        print(f"Error de carga: {e}"); sys.exit(1)
    return cars, fuels, refuels

def process_car_stats(car: Car, car_refuels: List[Refuel]):
    sorted_r = sorted(car_refuels, key=lambda x: x.refuel_date)
    if not sorted_r: return None, 0
    
    periods = []
    curr_p = [sorted_r[0]]
    for i in range(1, len(sorted_r)):
        if 0 <= (sorted_r[i].refuel_mileage - sorted_r[i-1].refuel_mileage) <= DISCONTINUITY_THRESHOLD_KM:
            curr_p.append(sorted_r[i])
        else:
            periods.append(curr_p)
            curr_p = [sorted_r[i]]
    periods.append(curr_p)
    
    yearly = defaultdict(lambda: {"km": 0.0, "l_total": 0.0, "l_cons": 0.0, "cost": 0.0, "refs": 0})
    monthly = {m: {"km": 0.0, "l_total": 0.0, "l_cons": 0.0, "h": 0.0, "refs": 0, "years": set()} for m in range(1, 13)}

    total_h = 0.0
    for p in periods:
        first = p[0]
        y_f, m_f = first.refuel_date.year, first.refuel_date.month
        yearly[y_f]["l_total"] += first.refuel_litres
        yearly[y_f]["cost"] += first.total_cost
        yearly[y_f]["refs"] += 1
        monthly[m_f]["l_total"] += first.refuel_litres
        monthly[m_f]["refs"] += 1
        monthly[m_f]["years"].add(y_f)

        for j in range(1, len(p)):
            curr, prev = p[j], p[j-1]
            d = curr.refuel_mileage - prev.refuel_mileage
            y, m = curr.refuel_date.year, curr.refuel_date.month
            
            yearly[y]["km"] += d
            yearly[y]["l_total"] += curr.refuel_litres
            yearly[y]["l_cons"] += curr.refuel_litres
            yearly[y]["cost"] += curr.total_cost
            yearly[y]["refs"] += 1

            monthly[m]["km"] += d
            monthly[m]["l_total"] += curr.refuel_litres
            monthly[m]["l_cons"] += curr.refuel_litres
            monthly[m]["refs"] += 1
            monthly[m]["years"].add(y)
            if car.has_temporal_data:
                hrs = curr.trip_time_hours
                monthly[m]["h"] += hrs
                total_h += hrs

    y_hist = [{"year": y, "total_km": round(d["km"], 1), "total_litres": round(d["l_total"], 1), "total_cost": round(d["cost"], 2), "average_consumption_l_per_100km": round(d["l_cons"]/d["km"]*100, 2) if d["km"] > 0 else 0, "number_of_refuels": d["refs"]} for y, d in sorted(yearly.items())]
    
    m_hist = []
    for m in range(1, 13):
        d = monthly[m]
        ny = len(d["years"])
        if ny > 0:
            m_hist.append({"month_id": m, "month_name": MONTH_NAMES[m], "average_km": round(d["km"]/ny, 1), "average_consumption": round(d["l_cons"]/d["km"]*100, 2) if d["km"] > 0 else 0, "average_refuels": int(round(d["refs"]/ny)), "average_speed": round(d["km"]/d["h"], 2) if d["h"] > 0 else 0})

    total_km = sum(d["total_km"] for d in y_hist)
    total_l = sum(d["total_litres"] for d in y_hist)
    total_l_cons = sum(y["l_cons"] for y in yearly.values())
    total_cost = sum(d["total_cost"] for d in y_hist)
    days = (sorted_r[-1].refuel_date - sorted_r[0].refuel_date).days

    car_json = {
        "car_id": car.car_id, "car_details": asdict(car),
        "has_temporal_data": car.has_temporal_data, "number_of_periods": len(periods),
        "total_statistics": {
            "total_km": round(total_km, 1), "total_litres": round(total_l, 2), "total_cost": round(total_cost, 2),
            "first_refuel_date": sorted_r[0].refuel_date.strftime("%Y-%m-%d"),
            "last_refuel_date": sorted_r[-1].refuel_date.strftime("%Y-%m-%d"),
            "average_consumption_l_per_100km": round(total_l_cons/total_km*100, 2) if total_km > 0 else 0,
            "total_refuels": len(sorted_r), "yearly_history": y_hist, "monthly_history": m_hist,
            "monthly_averages": {"average_km_per_month": round(total_km/(max(days,1)/30.44), 1)}
        }
    }
    
    if car.has_temporal_data:
        car_json["total_statistics"]["lifetime_average_speed_km_per_h"] = round(total_km / total_h, 2) if total_h > 0 else 0

    return car_json, total_h

# ============================================================================
# VISUALIZACIÓN
# ============================================================================
def display_ui(data: Dict):
    def clear(): os.system('cls' if os.name == 'nt' else 'clear')
    def header(txt): print("\n" + "="*80 + "\n" + f"{txt:^80}" + "\n" + "="*80)
    
    def print_yearly(history):
        print(f"  {'Año':<6} | {'Km Totales':<12} | {'L/100km':<8} | {'Coste Total':<12} | {'Refs'}")
        print("  " + "-"*65)
        for y in history:
            print(f"  {y['year']:<6} | {y['total_km']:<12,.1f} | {y['average_consumption_l_per_100km']:<8.2f} | {y['total_cost']:<12,.2f} | {y['number_of_refuels']}")

    def print_monthly(history, has_speed):
        print(f"  {'Mes':<12} | {'Km Media':<10} | {'Consumo':<8} | {'Refs':<6}" + (" | {'Velocidad':<10}" if has_speed else ""))
        print("  " + "-"*(50 + (13 if has_speed else 0)))
        for m in history:
            row = f"  {m['month_name']:<12} | {m['average_km']:<10.1f} | {m['average_consumption']:<8.2f} | {m['average_refuels']:<6}"
            if has_speed: row += f" | {m['average_speed']:<10.2f}"
            print(row)

    gs = data["global_statistics"]["all_vehicles"]
    clear()
    header("SISTEMA DE ANÁLISIS DE COMBUSTIBLE - RESUMEN GLOBAL")
    print(f"Período: {data['metadata']['data_period']['first_refuel']} al {data['metadata']['data_period']['last_refuel']}")
    print(f"\nTOTALES ACUMULADOS:\n  • Km Totales:   {gs['total_km']:,.1f} km\n  • Gasto:        {gs['total_cost']:,.2f} €\n  • Consumo:      {gs['average_consumption_l_per_100km']:.2f} L/100km")
    
    print("\nHISTÓRICO ANUAL GLOBAL:")
    print_yearly(gs["yearly_history"])

    print("\nHISTÓRICO MENSUAL MEDIO GLOBAL:")
    print_monthly(gs["monthly_history"], True)

    for car in data["vehicles"]:
        input("\n[Enter para detalle de vehículo...]")
        clear()
        ts, cd = car["total_statistics"], car["car_details"]
        header(f"VEHÍCULO {car['car_id']}: {cd['brand']} {cd['model']} ({ts['total_km']:,} km)")
        print(f"Período registrado: {ts['first_refuel_date']} al {ts['last_refuel_date']}")
        print(f"Consumo Medio Real: {ts['average_consumption_l_per_100km']:.2f} L/100km")
        
        if "lifetime_average_speed_km_per_h" in ts:
            print(f"Velocidad Media Total (Lifetime): {ts['lifetime_average_speed_km_per_h']:.2f} km/h")
        
        print("\nHISTÓRICO POR AÑO:")
        print_yearly(ts["yearly_history"])

        print("\nHISTÓRICO MENSUAL MEDIO:")
        print_monthly(ts["monthly_history"], car["has_temporal_data"])

    header("FIN DEL INFORME")

# ============================================================================
# MAIN
# ============================================================================
def main():
    if len(sys.argv) != 2: print("Uso: python gasolina.py <csv>"); sys.exit(1)
    cars_dict, fuels_dict, ref_list = load_data(sys.argv[1])
    by_car = defaultdict(list)
    for r in ref_list: by_car[r.car_id].append(r)
    
    v_list, g_h, g_km_t, g_km, g_litres, g_cost = [], 0, 0, 0, 0, 0
    y_agg = defaultdict(lambda: {"km": 0.0, "l_total": 0.0, "l_cons": 0.0, "cost": 0.0, "refs": 0})
    
    for cid in sorted(by_car.keys()):
        c_json, c_h = process_car_stats(cars_dict[cid], by_car[cid])
        v_list.append(c_json)
        ts = c_json["total_statistics"]
        g_km += ts["total_km"]; g_litres += ts["total_litres"]; g_cost += ts["total_cost"]
        if c_json["has_temporal_data"]: 
            g_km_t += ts["total_km"]; g_h += c_h
            
        for ye in ts["yearly_history"]:
            y = ye["year"]
            y_agg[y]["km"] += ye["total_km"]; y_agg[y]["l_total"] += ye["total_litres"]
            y_agg[y]["cost"] += ye["total_cost"]; y_agg[y]["refs"] += ye["number_of_refuels"]
            y_agg[y]["l_cons"] += (ye["total_km"] * ye["average_consumption_l_per_100km"] / 100)

    # Generar global_m
    global_m = []
    for m in range(1, 13):
        km_m = sum(next((mh['average_km'] for mh in c['total_statistics']['monthly_history'] if mh['month_id'] == m), 0) for c in v_list)
        km_h_m = sum(next((mh['average_km'] for mh in c['total_statistics']['monthly_history'] if mh['month_id'] == m), 0) for c in v_list if c['has_temporal_data'])
        l_m = sum(next((mh['average_km'] * mh['average_consumption'] / 100 for mh in c['total_statistics']['monthly_history'] if mh['month_id'] == m), 0) for c in v_list)
        refs_m = sum(next((mh['average_refuels'] for mh in c['total_statistics']['monthly_history'] if mh['month_id'] == m), 0) for c in v_list)
        h_m = sum(next((mh['average_km'] / mh['average_speed'] if mh['average_speed'] > 0 else 0 for mh in c['total_statistics']['monthly_history'] if mh['month_id'] == m), 0) for c in v_list if c['has_temporal_data'])
        
        if km_m > 0:
            global_m.append({"month_id": m, "month_name": MONTH_NAMES[m], "average_km": round(km_m, 1), "average_consumption": round(l_m/km_m*100, 2), "average_refuels": int(round(refs_m)), "average_speed": round(km_h_m/h_m, 2) if h_m > 0 else 0})

    global_y = [{"year": y, "total_km": round(d["km"], 1), "total_litres": round(d["l_total"], 1), "total_cost": round(d["cost"], 2), "average_consumption_l_per_100km": round(d["l_cons"]/d["km"]*100, 2) if d["km"] > 0 else 0, "number_of_refuels": d["refs"]} for y, d in sorted(y_agg.items())]

    f_all, l_all = min(r.refuel_date for r in ref_list), max(r.refuel_date for r in ref_list)
    final_json = {
        "metadata": {"generated_at": datetime.utcnow().isoformat() + "Z", "data_period": {"first_refuel": f_all.strftime("%Y-%m-%d"), "last_refuel": l_all.strftime("%Y-%m-%d"), "total_days": (l_all-f_all).days}},
        "global_statistics": {
            "all_vehicles": {
                "total_km": round(g_km, 1), "total_litres": round(g_litres, 2), "total_cost": round(g_cost, 2), "total_refuels": len(ref_list), 
                "average_consumption_l_per_100km": round(sum(y['l_cons'] for y in y_agg.values())/g_km*100, 2) if g_km > 0 else 0, 
                "yearly_history": global_y, "monthly_history": global_m, 
                "monthly_averages": {"average_speed_km_per_h": round(g_km_t/g_h, 2) if g_h > 0 else 0}
            }
        },
        "vehicles": v_list
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f: json.dump(final_json, f, indent=2, ensure_ascii=False)
    display_ui(final_json)

if __name__ == "__main__": main()

# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# Fuel Analysis System v1.7
# - Orden de tablas: Resumen -> Tabla Anual -> Tabla Mensual.
# - Aplicado a: Estadísticas Globales y Detalle por Vehículo.
# - Corrección de Velocidad Global: Solo incluye KM de coches con registro de tiempo.
# """

# import sys
# import csv
# import json
# import os
# from datetime import datetime
# from collections import defaultdict
# from dataclasses import dataclass, asdict
# from typing import List, Dict, Tuple

# # ============================================================================
# # CONFIGURACIÓN
# # ============================================================================
# CARS_FILE = "cars.csv"
# FUELS_FILE = "fuels.csv"
# OUTPUT_FILE = "Gasolina.json"
# DISCONTINUITY_THRESHOLD_KM = 2000
# CSV_SEPARATOR_REFUELS = ";"
# CARS_WITHOUT_TEMPORAL_DATA = [1, 2]

# MONTH_NAMES = {
#     1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
#     7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
# }

# @dataclass
# class Refuel:
#     car_id: int
#     refuel_date: datetime
#     refuel_litres: float
#     refuel_mileage: float
#     refuel_price_per_litre: float
#     refuel_type: int
#     trip_hours: int
#     trip_minutes: int
    
#     @property
#     def total_cost(self) -> float:
#         return self.refuel_litres * self.refuel_price_per_litre
    
#     @property
#     def trip_time_hours(self) -> float:
#         return self.trip_hours + (self.trip_minutes / 60)

# @dataclass
# class Car:
#     car_id: int
#     brand: str
#     color: str
#     model: str
#     number_plate: str
#     fuel_type: str

#     def __post_init__(self):
#         self.has_temporal_data = self.car_id not in CARS_WITHOUT_TEMPORAL_DATA

# # ============================================================================
# # PROCESAMIENTO
# # ============================================================================
# def parse_decimal(value: str) -> float:
#     if not value: return 0.0
#     return float(str(value).replace(",", "."))

# def load_data(refuels_path: str):
#     cars, fuels, refuels = {}, {}, []
#     try:
#         with open(CARS_FILE, 'r', encoding='utf-8') as f:
#             reader = csv.DictReader(f)
#             for row in reader:
#                 c = Car(car_id=int(row['carId']), brand=row['carBrand'], color=row['carColor'], 
#                         model=row['carModel'], number_plate=row['carNumberPlate'], fuel_type=row['carFuel'])
#                 cars[c.car_id] = c
#         with open(FUELS_FILE, 'r', encoding='utf-8') as f:
#             reader = csv.DictReader(f)
#             for row in reader:
#                 fuels[int(row['fuelId'])] = row['fuelDescription']
#         with open(refuels_path, 'r', encoding='utf-8') as f:
#             reader = csv.DictReader(f, delimiter=CSV_SEPARATOR_REFUELS)
#             for row in reader:
#                 refuels.append(Refuel(
#                     car_id=int(row['carId']),
#                     refuel_date=datetime.strptime(row['refuelDate'], "%Y-%m-%d"),
#                     refuel_litres=parse_decimal(row['refuelLitres']),
#                     refuel_mileage=parse_decimal(row['refuelMilleage']),
#                     refuel_price_per_litre=parse_decimal(row['refuelPricePerLitre']),
#                     refuel_type=int(row['refuelType']),
#                     trip_hours=int(row['tripHours']),
#                     trip_minutes=int(row['tripMinutes'])
#                 ))
#     except Exception as e:
#         print(f"Error de carga: {e}"); sys.exit(1)
#     return cars, fuels, refuels

# def process_car_stats(car: Car, car_refuels: List[Refuel]):
#     sorted_r = sorted(car_refuels, key=lambda x: x.refuel_date)
#     if not sorted_r: return None, 0
    
#     periods = []
#     curr_p = [sorted_r[0]]
#     for i in range(1, len(sorted_r)):
#         if 0 <= (sorted_r[i].refuel_mileage - sorted_r[i-1].refuel_mileage) <= DISCONTINUITY_THRESHOLD_KM:
#             curr_p.append(sorted_r[i])
#         else:
#             periods.append(curr_p)
#             curr_p = [sorted_r[i]]
#     periods.append(curr_p)
    
#     yearly = defaultdict(lambda: {"km": 0.0, "l_total": 0.0, "l_cons": 0.0, "cost": 0.0, "refs": 0})
#     monthly = {m: {"km": 0.0, "l_total": 0.0, "l_cons": 0.0, "h": 0.0, "refs": 0, "years": set()} for m in range(1, 13)}

#     for p in periods:
#         first = p[0]
#         y_f, m_f = first.refuel_date.year, first.refuel_date.month
#         yearly[y_f]["l_total"] += first.refuel_litres
#         yearly[y_f]["cost"] += first.total_cost
#         yearly[y_f]["refs"] += 1
#         monthly[m_f]["l_total"] += first.refuel_litres
#         monthly[m_f]["refs"] += 1
#         monthly[m_f]["years"].add(y_f)

#         for j in range(1, len(p)):
#             curr, prev = p[j], p[j-1]
#             d = curr.refuel_mileage - prev.refuel_mileage
#             y, m = curr.refuel_date.year, curr.refuel_date.month
            
#             yearly[y]["km"] += d
#             yearly[y]["l_total"] += curr.refuel_litres
#             yearly[y]["l_cons"] += curr.refuel_litres
#             yearly[y]["cost"] += curr.total_cost
#             yearly[y]["refs"] += 1

#             monthly[m]["km"] += d
#             monthly[m]["l_total"] += curr.refuel_litres
#             monthly[m]["l_cons"] += curr.refuel_litres
#             monthly[m]["refs"] += 1
#             monthly[m]["years"].add(y)
#             if car.has_temporal_data:
#                 monthly[m]["h"] += curr.trip_time_hours

#     y_hist = [{"year": y, "total_km": round(d["km"], 1), "total_litres": round(d["l_total"], 1), "total_cost": round(d["cost"], 2), "average_consumption_l_per_100km": round(d["l_cons"]/d["km"]*100, 2) if d["km"] > 0 else 0, "number_of_refuels": d["refs"]} for y, d in sorted(yearly.items())]
    
#     m_hist = []
#     for m in range(1, 13):
#         d = monthly[m]
#         ny = len(d["years"])
#         if ny > 0:
#             m_hist.append({"month_id": m, "month_name": MONTH_NAMES[m], "average_km": round(d["km"]/ny, 1), "average_consumption": round(d["l_cons"]/d["km"]*100, 2) if d["km"] > 0 else 0, "average_refuels": int(round(d["refs"]/ny)), "average_speed": round(d["km"]/d["h"], 2) if d["h"] > 0 else 0})

#     total_km = sum(d["total_km"] for d in y_hist)
#     total_l = sum(d["total_litres"] for d in y_hist)
#     total_l_cons = sum(y["l_cons"] for y in yearly.values())
#     total_cost = sum(d["total_cost"] for d in y_hist)
#     days = (sorted_r[-1].refuel_date - sorted_r[0].refuel_date).days

#     car_json = {
#         "car_id": car.car_id, "car_details": asdict(car),
#         "has_temporal_data": car.has_temporal_data, "number_of_periods": len(periods),
#         "total_statistics": {
#             "total_km": round(total_km, 1), "total_litres": round(total_l, 2), "total_cost": round(total_cost, 2),
#             "average_consumption_l_per_100km": round(total_l_cons/total_km*100, 2) if total_km > 0 else 0,
#             "total_refuels": len(sorted_r), "yearly_history": y_hist, "monthly_history": m_hist,
#             "monthly_averages": {"average_km_per_month": round(total_km/(max(days,1)/30.44), 1)}
#         }
#     }
#     return car_json, sum(m["h"] for m in monthly.values())

# # ============================================================================
# # VISUALIZACIÓN
# # ============================================================================
# def display_ui(data: Dict):
#     def clear(): os.system('cls' if os.name == 'nt' else 'clear')
#     def header(txt): print("\n" + "="*80 + "\n" + f"{txt:^80}" + "\n" + "="*80)
    
#     def print_yearly(history):
#         print(f"  {'Año':<6} | {'Km Totales':<12} | {'L/100km':<8} | {'Coste Total':<12} | {'Refs'}")
#         print("  " + "-"*65)
#         for y in history:
#             print(f"  {y['year']:<6} | {y['total_km']:<12,.1f} | {y['average_consumption_l_per_100km']:<8.2f} | {y['total_cost']:<12,.2f} | {y['number_of_refuels']}")

#     def print_monthly(history, has_speed):
#         print(f"  {'Mes':<12} | {'Km Media':<10} | {'Consumo':<8} | {'Refs':<6}" + (" | {'Velocidad':<10}" if has_speed else ""))
#         print("  " + "-"*(50 + (13 if has_speed else 0)))
#         for m in history:
#             row = f"  {m['month_name']:<12} | {m['average_km']:<10.1f} | {m['average_consumption']:<8.2f} | {m['average_refuels']:<6}"
#             if has_speed: row += f" | {m['average_speed']:<10.2f}"
#             print(row)

#     gs = data["global_statistics"]["all_vehicles"]
#     clear()
#     header("SISTEMA DE ANÁLISIS DE COMBUSTIBLE - RESUMEN GLOBAL")
#     print(f"Período: {data['metadata']['data_period']['first_refuel']} al {data['metadata']['data_period']['last_refuel']}")
#     print(f"\nTOTALES ACUMULADOS:\n  • Km Totales:   {gs['total_km']:,.1f} km\n  • Gasto:        {gs['total_cost']:,.2f} €\n  • Consumo:      {gs['average_consumption_l_per_100km']:.2f} L/100km")
    
#     print("\nHISTÓRICO ANUAL GLOBAL:")
#     print_yearly(gs["yearly_history"])

#     print("\nHISTÓRICO MENSUAL MEDIO GLOBAL:")
#     print_monthly(gs["monthly_history"], True)

#     for car in data["vehicles"]:
#         input("\n[Enter para detalle de vehículo...]")
#         clear()
#         ts, cd = car["total_statistics"], car["car_details"]
#         header(f"VEHÍCULO {car['car_id']}: {cd['brand']} {cd['model']} ({ts['total_km']:,} km)")
#         print(f"Consumo Medio Real: {ts['average_consumption_l_per_100km']:.2f} L/100km")
        
#         print("\nHISTÓRICO POR AÑO:")
#         print_yearly(ts["yearly_history"])

#         print("\nHISTÓRICO MENSUAL MEDIO:")
#         print_monthly(ts["monthly_history"], car["has_temporal_data"])

#     header("FIN DEL INFORME")

# # ============================================================================
# # MAIN
# # ============================================================================
# def main():
#     if len(sys.argv) != 2: print("Uso: python gasolina.py <csv>"); sys.exit(1)
#     cars_dict, fuels_dict, ref_list = load_data(sys.argv[1])
#     by_car = defaultdict(list)
#     for r in ref_list: by_car[r.car_id].append(r)
    
#     v_list, g_h, g_km_t, g_km, g_litres, g_cost = [], 0, 0, 0, 0, 0
#     y_agg = defaultdict(lambda: {"km": 0.0, "l_total": 0.0, "l_cons": 0.0, "cost": 0.0, "refs": 0})
    
#     for cid in sorted(by_car.keys()):
#         c_json, c_h = process_car_stats(cars_dict[cid], by_car[cid])
#         v_list.append(c_json)
#         ts = c_json["total_statistics"]
#         g_km += ts["total_km"]; g_litres += ts["total_litres"]; g_cost += ts["total_cost"]
#         if c_json["has_temporal_data"]: 
#             g_km_t += ts["total_km"]; g_h += c_h
            
#         for ye in ts["yearly_history"]:
#             y = ye["year"]
#             y_agg[y]["km"] += ye["total_km"]; y_agg[y]["l_total"] += ye["total_litres"]
#             y_agg[y]["cost"] += ye["total_cost"]; y_agg[y]["refs"] += ye["number_of_refuels"]
#             y_agg[y]["l_cons"] += (ye["total_km"] * ye["average_consumption_l_per_100km"] / 100)

#     # Generar global_m
#     global_m = []
#     for m in range(1, 13):
#         km_m = sum(next((mh['average_km'] for mh in c['total_statistics']['monthly_history'] if mh['month_id'] == m), 0) for c in v_list)
#         # BUGFIX: Solo km de coches con tiempo para la velocidad
#         km_h_m = sum(next((mh['average_km'] for mh in c['total_statistics']['monthly_history'] if mh['month_id'] == m), 0) for c in v_list if c['has_temporal_data'])
#         l_m = sum(next((mh['average_km'] * mh['average_consumption'] / 100 for mh in c['total_statistics']['monthly_history'] if mh['month_id'] == m), 0) for c in v_list)
#         refs_m = sum(next((mh['average_refuels'] for mh in c['total_statistics']['monthly_history'] if mh['month_id'] == m), 0) for c in v_list)
#         h_m = sum(next((mh['average_km'] / mh['average_speed'] if mh['average_speed'] > 0 else 0 for mh in c['total_statistics']['monthly_history'] if mh['month_id'] == m), 0) for c in v_list if c['has_temporal_data'])
        
#         if km_m > 0:
#             global_m.append({"month_id": m, "month_name": MONTH_NAMES[m], "average_km": round(km_m, 1), "average_consumption": round(l_m/km_m*100, 2), "average_refuels": int(round(refs_m)), "average_speed": round(km_h_m/h_m, 2) if h_m > 0 else 0})

#     # Generar global_y
#     global_y = [{"year": y, "total_km": round(d["km"], 1), "total_litres": round(d["l_total"], 1), "total_cost": round(d["cost"], 2), "average_consumption_l_per_100km": round(d["l_cons"]/d["km"]*100, 2) if d["km"] > 0 else 0, "number_of_refuels": d["refs"]} for y, d in sorted(y_agg.items())]

#     f_all, l_all = min(r.refuel_date for r in ref_list), max(r.refuel_date for r in ref_list)
#     final_json = {
#         "metadata": {"generated_at": datetime.utcnow().isoformat() + "Z", "data_period": {"first_refuel": f_all.strftime("%Y-%m-%d"), "last_refuel": l_all.strftime("%Y-%m-%d"), "total_days": (l_all-f_all).days}},
#         "global_statistics": {
#             "all_vehicles": {
#                 "total_km": round(g_km, 1), "total_litres": round(g_litres, 2), "total_cost": round(g_cost, 2), "total_refuels": len(ref_list), 
#                 "average_consumption_l_per_100km": round(sum(y['l_cons'] for y in y_agg.values())/g_km*100, 2) if g_km > 0 else 0, 
#                 "yearly_history": global_y, "monthly_history": global_m, 
#                 "monthly_averages": {"average_speed_km_per_h": round(g_km_t/g_h, 2) if g_h > 0 else 0}
#             }
#         },
#         "vehicles": v_list
#     }
#     with open(OUTPUT_FILE, 'w', encoding='utf-8') as f: json.dump(final_json, f, indent=2, ensure_ascii=False)
#     display_ui(final_json)

# if __name__ == "__main__": main()