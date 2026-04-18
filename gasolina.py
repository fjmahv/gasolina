#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fuel Analysis System v2.1
- Comparativa: Últimos 4 repostajes vs Media Histórica del Mes.
- Análisis de eficiencia por Rangos de Velocidad.
- Históricos detallados Anuales y Mensuales (Global y Vehículo).
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

SPEED_RANGES = [
    {"label": "15-35 km/h", "min": 15, "max": 35},
    {"label": "36-55 km/h", "min": 36, "max": 55},
    {"label": "56-75 km/h", "min": 56, "max": 75},
    {"label": "76-95 km/h", "min": 76, "max": 95},
    {"label": "> 95 km/h", "min": 95.01, "max": float('inf')}
]

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

    def summarize_refuels(refuels_block):
        if not refuels_block:
            return {
                "refuels_count": 0,
                "consumption": 0,
                "speed": 0,
                "distance_km": 0
            }

        total_litres = sum(r["litres"] for r in refuels_block)
        total_km = sum(r["distance_km"] for r in refuels_block)
        total_hours = sum(r["trip_time_hours"] for r in refuels_block)
        count = len(refuels_block)

        return {
            "refuels_count": count,
            "consumption": round((total_litres / total_km) * 100, 2) if total_km > 0 else 0,
            "speed": round(total_km / total_hours, 2) if total_hours > 0 else 0,
            "distance_km": round(total_km / count, 1) if count > 0 else 0
        }
    
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
    speed_ranges_stats = {r["label"]: {"km": 0.0, "l": 0.0, "refs": 0} for r in SPEED_RANGES}
    individual_refuel_history = []

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
            
            h_ref, s_ref = 0.0, 0.0
            if car.has_temporal_data:
                h_ref = curr.trip_time_hours
                monthly[m]["h"] += h_ref
                total_h += h_ref
                if h_ref > 0:
                    s_ref = d / h_ref
                    for r_conf in SPEED_RANGES:
                        if r_conf["min"] <= s_ref <= r_conf["max"]:
                            speed_ranges_stats[r_conf["label"]]["km"] += d
                            speed_ranges_stats[r_conf["label"]]["l"] += curr.refuel_litres
                            speed_ranges_stats[r_conf["label"]]["refs"] += 1
                            break
            
            individual_refuel_history.append({
                "date": curr.refuel_date, "month": m,
                "litres": curr.refuel_litres,
                "distance_km": d,
                "trip_time_hours": h_ref,
                "consumption": (curr.refuel_litres / d * 100) if d > 0 else 0,
                "speed": s_ref,
                "refuel_partial_mileage": round(d, 1)
            })

    y_hist = [{"year": y, "total_km": round(d["km"], 1), "total_litres": round(d["l_total"], 1), "total_cost": round(d["cost"], 2), "average_consumption_l_per_100km": round(d["l_cons"]/d["km"]*100, 2) if d["km"] > 0 else 0, "number_of_refuels": d["refs"]} for y, d in sorted(yearly.items())]
    
    m_hist_dict, m_hist_list = {}, []
    for m in range(1, 13):
        d = monthly[m]
        ny = len(d["years"])
        if ny > 0:
            entry = {"month_id": m, "month_name": MONTH_NAMES[m], "average_km": round(d["km"]/ny, 1), "average_consumption": round(d["l_cons"]/d["km"]*100, 2) if d["km"] > 0 else 0, "average_refuels": int(round(d["refs"]/ny)), "average_speed": round(d["km"]/d["h"], 2) if d["h"] > 0 else 0}
            m_hist_list.append(entry); m_hist_dict[m] = entry

    speed_range_history = []
    if car.has_temporal_data:
        for label, data in speed_ranges_stats.items():
            speed_range_history.append({"range_label": label, "average_consumption": round(data["l"] / data["km"] * 100, 2) if data["km"] > 0 else 0, "number_of_refuels": data["refs"]})

    recent_comparison = {}
    if individual_refuel_history:
        last_refuel = individual_refuel_history[-1]
        previous_3_refuels = individual_refuel_history[-4:-1]
        target_month = last_refuel["month"]
        historical_same_month = [r for r in individual_refuel_history if r["month"] == target_month]

        recent_comparison = {
            "last_refuel": {
                "date": last_refuel["date"].strftime("%Y-%m-%d"),
                "consumption": round((last_refuel["litres"] / last_refuel["distance_km"]) * 100, 2) if last_refuel["distance_km"] > 0 else 0,
                "speed": round(last_refuel["distance_km"] / last_refuel["trip_time_hours"], 2) if last_refuel["trip_time_hours"] > 0 else 0,
                "distance_km": round(last_refuel["distance_km"], 1)
            },
            "last_3_refuels_average": summarize_refuels(previous_3_refuels),
            "historical_month_average": {
                "month_id": target_month,
                "month_name": MONTH_NAMES[target_month],
                **summarize_refuels(historical_same_month)
            }
        }

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
            "total_refuels": len(sorted_r), "yearly_history": y_hist, "monthly_history": m_hist_list,
            "consumption_by_speed_range": speed_range_history,
            "recent_refuels_comparison": recent_comparison,
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

    def print_recent(recent, has_speed):
        print(f"  {'Concepto':<32} | {'Consumo':<8}" + (" | {'V. Media':<10}" if has_speed else "") + f" | {'Distancia':<10}")
        print("  " + "-"*(70 + (13 if has_speed else 0)))

        rows = [
            (f"Último repostaje ({recent['last_refuel']['date']})", recent["last_refuel"]),
            ("Media 3 anteriores", recent["last_3_refuels_average"]),
            (f"Histórico {recent['historical_month_average']['month_name']}", recent["historical_month_average"])
        ]

        for label, r in rows:
            row = f"  {label:<32} | {r['consumption']:<8.2f}"
            if has_speed: row += f" | {r['speed']:<10.2f}"
            row += f" | {r['distance_km']:<10.1f}"
            print(row)

    def print_yearly(yearly):
        print("\nHISTÓRICO ANUAL:")
        print(f"  {'Año':<6} | {'Km':<10} | {'Litros':<10} | {'Coste':<10} | {'Consumo':<9} | {'Repost.':<8}")
        print("  " + "-"*72)
        for y in yearly:
            print(
                f"  {y['year']:<6} | {y['total_km']:<10.1f} | {y['total_litres']:<10.1f} | "
                f"{y['total_cost']:<10.2f} | {y['average_consumption_l_per_100km']:<9.2f} | {y['number_of_refuels']:<8}"
            )

    def print_monthly(monthly, has_speed):
        print("\nHISTÓRICO MENSUAL:")
        header_line = f"  {'Mes':<12} | {'Km Med':<10} | {'Consumo':<9} | {'Repost.':<8}"
        if has_speed:
            header_line += f" | {'V. Media':<10}"
        print(header_line)
        print("  " + "-"*(49 + (13 if has_speed else 0)))
        for m in monthly:
            row = (
                f"  {m['month_name']:<12} | {m['average_km']:<10.1f} | {m['average_consumption']:<9.2f} | "
                f"{m['average_refuels']:<8}"
            )
            if has_speed:
                row += f" | {m['average_speed']:<10.2f}"
            print(row)

    gs = data["global_statistics"]["all_vehicles"]
    clear()
    header("SISTEMA DE ANÁLISIS DE COMBUSTIBLE - RESUMEN GLOBAL")
    print(f"Período: {data['metadata']['data_period']['first_refuel']} al {data['metadata']['data_period']['last_refuel']}")
    print(f"\nTOTALES:  {gs['total_km']:,.1f} km  |  {gs['total_cost']:,.2f} €  |  Consumo: {gs['average_consumption_l_per_100km']:.2f} L/100")

    for car in data["vehicles"]:
        input("\n[Enter para detalle de vehículo...]")
        clear()
        ts, cd = car["total_statistics"], car["car_details"]
        header(f"VEHÍCULO {car['car_id']}: {cd['brand']} {cd['model']} ({ts['total_km']:,} km)")
        print(f"Período: {ts['first_refuel_date']} al {ts['last_refuel_date']} | Consumo: {ts['average_consumption_l_per_100km']:.2f} L/100")
        
        if "recent_refuels_comparison" in ts and ts["recent_refuels_comparison"]:
            print("\nÚLTIMO REPOSTAJE, MEDIA DE LOS 3 ANTERIORES E HISTÓRICO DEL MES:")
            print_recent(ts["recent_refuels_comparison"], car["has_temporal_data"])

        input("\n[Enter para ver históricos anuales y mensuales...]")
        clear()
        header(f"HISTÓRICOS - VEHÍCULO {car['car_id']}: {cd['brand']} {cd['model']}")
        print_yearly(ts["yearly_history"])
        print_monthly(ts["monthly_history"], car["has_temporal_data"])
        input("\n[Enter para continuar al siguiente vehículo...]")

    header("FIN DEL INFORME")

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
        if c_json["has_temporal_data"]: g_km_t += ts["total_km"]; g_h += c_h
        for ye in ts["yearly_history"]:
            y = ye["year"]; y_agg[y]["km"] += ye["total_km"]; y_agg[y]["l_total"] += ye["total_litres"]
            y_agg[y]["cost"] += ye["total_cost"]; y_agg[y]["refs"] += ye["number_of_refuels"]
            y_agg[y]["l_cons"] += (ye["total_km"] * ye["average_consumption_l_per_100km"] / 100)

    f_all, l_all = min(r.refuel_date for r in ref_list), max(r.refuel_date for r in ref_list)
    final_json = {
        "metadata": {"generated_at": datetime.utcnow().isoformat() + "Z", "data_period": {"first_refuel": f_all.strftime("%Y-%m-%d"), "last_refuel": l_all.strftime("%Y-%m-%d"), "total_days": (l_all-f_all).days}},
        "global_statistics": {"all_vehicles": {"total_km": round(g_km, 1), "total_litres": round(g_litres, 2), "total_cost": round(g_cost, 2), "total_refuels": len(ref_list), "average_consumption_l_per_100km": round(sum(y['l_cons'] for y in y_agg.values())/g_km*100, 2) if g_km > 0 else 0, "monthly_averages": {"average_speed_km_per_h": round(g_km_t/g_h, 2) if g_h > 0 else 0}}},
        "vehicles": v_list
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f: json.dump(final_json, f, indent=2, ensure_ascii=False)
    display_ui(final_json)

if __name__ == "__main__": main()
