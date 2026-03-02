#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fuel Analysis System v1.1
Analiza históricos de repostajes con detección de discontinuidades
y visualización profunda por vehículo.
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
CSV_SEPARATOR_OTHERS = ","
CARS_WITHOUT_TEMPORAL_DATA = [1, 2]

# ============================================================================
# CLASES DE DATOS
# ============================================================================
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

class Car:
    def __init__(self, car_id, brand, color, model, number_plate, fuel_type):
        self.car_id = int(car_id)
        self.brand = brand
        self.color = color
        self.model = model
        self.number_plate = number_plate
        self.fuel_type = fuel_type
        self.has_temporal_data = self.car_id not in CARS_WITHOUT_TEMPORAL_DATA

class Fuel:
    def __init__(self, fuel_id, description):
        self.fuel_id = int(fuel_id)
        self.description = description
        desc = self.description.lower()
        # Regla 2: Clasificación Normal vs Premium
        if any(x in desc for x in ["premium", "extra", "98"]):
            self.category = "premium"
        else:
            self.category = "normal"

# ============================================================================
# FUNCIONES DE PROCESAMIENTO
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
                c = Car(row['carId'], row['carBrand'], row['carColor'], row['carModel'], row['carNumberPlate'], row['carFuel'])
                cars[c.car_id] = c
        with open(FUELS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                fu = Fuel(row['fuelId'], row['fuelDescription'])
                fuels[fu.fuel_id] = fu
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
        print(f"Error cargando ficheros: {e}")
        sys.exit(1)
    return cars, fuels, refuels

def process_car_stats(car: Car, fuels: Dict[int, Fuel], car_refuels: List[Refuel]):
    # Orden cronológico
    sorted_r = sorted(car_refuels, key=lambda x: x.refuel_date)
    if not sorted_r: return None, 0
    
    # Detección de discontinuidades (Regla 3)
    periods = []
    curr_p = [sorted_r[0]]
    for i in range(1, len(sorted_r)):
        diff = sorted_r[i].refuel_mileage - sorted_r[i-1].refuel_mileage
        if diff < 0 or diff > DISCONTINUITY_THRESHOLD_KM:
            periods.append(curr_p)
            curr_p = [sorted_r[i]]
        else:
            curr_p.append(sorted_r[i])
    periods.append(curr_p)
    
    p_data, total_km, total_litres, total_cost, total_h = [], 0, 0, 0, 0
    speed_map = {
        "normal": {"km": 0.0, "h": 0.0, "l": 0.0, "fuels": set()},
        "premium": {"km": 0.0, "h": 0.0, "l": 0.0, "fuels": set()}
    }
    yearly = defaultdict(lambda: {"km": 0.0, "l": 0.0, "cost": 0.0, "refs": 0})

    for i, p in enumerate(periods):
        p_km = 0
        for j in range(1, len(p)):
            d = p[j].refuel_mileage - p[j-1].refuel_mileage
            p_km += d
            y = p[j].refuel_date.year
            yearly[y]["km"] += d
            if car.has_temporal_data:
                f_obj = fuels[p[j].refuel_type]
                hrs = p[j].trip_time_hours
                speed_map[f_obj.category]["km"] += d
                speed_map[f_obj.category]["h"] += hrs
                speed_map[f_obj.category]["l"] += p[j].refuel_litres
                speed_map[f_obj.category]["fuels"].add(f_obj.description)
                total_h += hrs

        for r in p:
            yearly[r.refuel_date.year]["l"] += r.refuel_litres
            yearly[r.refuel_date.year]["cost"] += r.total_cost
            yearly[r.refuel_date.year]["refs"] += 1

        p_stats = {
            "total_km": round(p_km, 1),
            "total_litres": round(sum(r.refuel_litres for r in p), 2),
            "total_cost": round(sum(r.total_cost for r in p), 2),
            "average_consumption_l_per_100km": round(sum(r.refuel_litres for r in p)/p_km*100, 2) if p_km > 0 else 0,
            "average_km_between_refuels": round(p_km/(len(p)-1), 1) if len(p) > 1 else 0,
            "total_refuels": len(p)
        }
        p_data.append({
            "period_number": i+1, 
            "date_range": {"start": p[0].refuel_date.strftime("%Y-%m-%d"), "end": p[-1].refuel_date.strftime("%Y-%m-%d")},
            "statistics": p_stats
        })
        total_km += p_km
        total_litres += p_stats["total_litres"]
        total_cost += p_stats["total_cost"]

    days = (sorted_r[-1].refuel_date - sorted_r[0].refuel_date).days
    eff_refs = len(sorted_r) - len(periods)
    
    y_hist = []
    for y in sorted(yearly.keys()):
        d = yearly[y]
        y_hist.append({
            "year": y, "total_km": round(d["km"], 1), "total_litres": round(d["l"], 1),
            "average_consumption_l_per_100km": round(d["l"]/d["km"]*100, 2) if d["km"] > 0 else 0,
            "number_of_refuels": d["refs"]
        })

    car_json = {
        "car_id": car.car_id, "car_details": {"brand": car.brand, "model": car.model, "color": car.color, "number_plate": car.number_plate, "fuel_type": car.fuel_type},
        "has_temporal_data": car.has_temporal_data, "has_discontinuity": len(periods) > 1, "number_of_periods": len(periods), "periods": p_data,
        "total_statistics": {
            "total_km": round(total_km, 1), "total_litres": round(total_litres, 2), "total_cost": round(total_cost, 2),
            "first_refuel_date": sorted_r[0].refuel_date.strftime("%Y-%m-%d"), "last_refuel_date": sorted_r[-1].refuel_date.strftime("%Y-%m-%d"),
            "average_consumption_l_per_100km": round(total_litres/total_km*100, 2) if total_km > 0 else 0,
            "average_km_between_refuels": round(total_km/eff_refs, 1) if eff_refs > 0 else 0,
            "average_km_per_year": round(total_km/(max(days,1)/365.25), 1) if days > 0 else 0,
            "total_refuels": len(sorted_r), "yearly_history": y_hist,
            "monthly_averages": {"average_km_per_month": round(total_km/(max(days,1)/30.44), 1) if days > 0 else 0}
        }
    }
    
    if car.has_temporal_data:
        ss = {
            "overall_average_speed_km_per_h": round(total_km/total_h, 2) if total_h > 0 else 0,
            "average_speed_normal_fuel": {"value_km_per_h": round(speed_map["normal"]["km"]/speed_map["normal"]["h"], 2) if speed_map["normal"]["h"] > 0 else 0, "fuel_types": sorted(list(speed_map["normal"]["fuels"]))},
            "average_speed_premium_fuel": {"value_km_per_h": round(speed_map["premium"]["km"]/speed_map["premium"]["h"], 2) if speed_map["premium"]["h"] > 0 else 0, "fuel_types": sorted(list(speed_map["premium"]["fuels"]))},
            "km_with_normal_fuel": {"total_km": round(speed_map["normal"]["km"], 1), "percentage": round(speed_map["normal"]["km"]/total_km*100, 2) if total_km > 0 else 0},
            "km_with_premium_fuel": {"total_km": round(speed_map["premium"]["km"], 1), "percentage": round(speed_map["premium"]["km"]/total_km*100, 2) if total_km > 0 else 0}
        }
        car_json["total_statistics"]["speed_statistics"] = ss
        
    return car_json, total_h

# ============================================================================
# VISUALIZACIÓN
# ============================================================================
def display_ui(data: Dict):
    def clear(): os.system('cls' if os.name == 'nt' else 'clear')
    def header(txt): print("\n" + "="*80 + "\n" + f"{txt:^80}" + "\n" + "="*80)

    gs = data["global_statistics"]["all_vehicles"]
    clear()
    header("SISTEMA DE ANÁLISIS DE COMBUSTIBLE - RESUMEN GLOBAL")
    print(f"Período: {data['metadata']['data_period']['first_refuel']} al {data['metadata']['data_period']['last_refuel']}")
    print(f"\nTOTALES:\n  • Km Totales:   {gs['total_km']:,.1f} km\n  • Litros:       {gs['total_litres']:,.2f} L\n  • Gasto:        {gs['total_cost']:,.2f} €")
    print(f"\nMEDIAS:\n  • Consumo:      {gs['average_consumption_l_per_100km']:.2f} L/100km\n  • Velocidad:    {gs['monthly_averages'].get('average_speed_km_per_h', 0):.2f} km/h")
    
    input("\n[Presiona Enter para ver el detalle de los vehículos...]")

    for car in data["vehicles"]:
        clear()
        cd = car["car_details"]
        ts = car["total_statistics"]
        header(f"VEHÍCULO {car['car_id']}: {cd['brand']} {cd['model']} ({cd['number_plate']})")
        print(f"Combustible: {cd['fuel_type'].upper()} | Datos Temporales: {'SÍ' if car['has_temporal_data'] else 'NO'}")
        print(f"Detección Discontinuidad: {'SÍ' if car['has_discontinuity'] else 'NO'} ({car['number_of_periods']} periodos)")
        
        print("\nESTADÍSTICAS GENERALES:")
        print(f"  • Km Totales:         {ts['total_km']:,.1f} km")
        print(f"  • Consumo Medio:      {ts['average_consumption_l_per_100km']:.2f} L/100km")
        print(f"  • Km entre repostaje: {ts['average_km_between_refuels']:,.1f} km (promedio)")
        print(f"  • Proyección:         {ts['average_km_per_year']:,.1f} km/año | {ts['monthly_averages']['average_km_per_month']:,.1f} km/mes")
        
        if "speed_statistics" in ts:
            ss = ts["speed_statistics"]
            print("\nANÁLISIS DE VELOCIDAD Y COMBUSTIBLE:")
            print(f"  • Velocidad Media Global: {ss['overall_average_speed_km_per_h']:.2f} km/h")
            for cat in ["normal", "premium"]:
                k = ss[f"km_with_{cat}_fuel"]
                v = ss[f"average_speed_{cat}_fuel"]
                if k['total_km'] > 0:
                    print(f"  • [{cat.upper()}] Speed: {v['value_km_per_h']:.2f} km/h | Distancia: {k['total_km']:,.1f} km ({k['percentage']}%)")

        print("\nHISTÓRICO POR AÑO:")
        print(f"  {'Año':<6} | {'Km Recorridos':<15} | {'L/100km':<10} | {'Repostajes':<10}")
        print("  " + "-"*55)
        for y in ts["yearly_history"]:
            print(f"  {y['year']:<6} | {y['total_km']:<15,.1f} | {y['average_consumption_l_per_100km']:<10.2f} | {y['number_of_refuels']:<10}")

        input(f"\n[Enter para siguiente coche...]")

    header("FIN DEL INFORME")

# ============================================================================
# MAIN
# ============================================================================
def main():
    if len(sys.argv) != 2:
        print("Uso: python gasolina.py <fichero_repostajes.csv>")
        sys.exit(1)
    
    refuel_file = sys.argv[1]
    cars_dict, fuels_dict, refuels_list = load_data(refuel_file)
    
    car_ref_map = defaultdict(list)
    for r in refuels_list: car_ref_map[r.car_id].append(r)
    
    v_list, g_h, g_km_t, g_km, g_litres, g_cost = [], 0, 0, 0, 0, 0
    y_agg = defaultdict(lambda: {"km": 0.0, "l": 0.0, "cost": 0.0, "refs": 0})
    
    for cid in sorted(car_ref_map.keys()):
        c_json, c_h = process_car_stats(cars_dict[cid], fuels_dict, car_ref_map[cid])
        v_list.append(c_json)
        ts = c_json["total_statistics"]
        g_km += ts["total_km"]; g_litres += ts["total_litres"]; g_cost += ts["total_cost"]
        if c_json["has_temporal_data"]:
            g_h += c_h; g_km_t += ts["total_km"]
        for ye in ts["yearly_history"]:
            y = ye["year"]
            y_agg[y]["km"] += ye["total_km"]; y_agg[y]["l"] += ye["total_litres"]; y_agg[y]["refs"] += ye["number_of_refuels"]

    f_all, l_all = min(r.refuel_date for r in refuels_list), max(r.refuel_date for r in refuels_list)
    td = (l_all - f_all).days
    eff_g = sum(v["total_statistics"]["total_refuels"] - v["number_of_periods"] for v in v_list)

    final_json = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "data_period": {"first_refuel": f_all.strftime("%Y-%m-%d"), "last_refuel": l_all.strftime("%Y-%m-%d"), "total_days": td, "total_years": round(td/365.25, 2)}
        },
        "global_statistics": {
            "all_vehicles": {
                "total_km": round(g_km, 1), "total_litres": round(g_litres, 2), "total_cost": round(g_cost, 2), "total_refuels": len(refuels_list),
                "average_consumption_l_per_100km": round(g_litres/g_km*100, 2) if g_km > 0 else 0, "average_km_between_refuels": round(g_km/eff_g, 1) if eff_g > 0 else 0,
                "average_km_per_year": round(g_km/(td/365.25), 1) if td > 0 else 0,
                "monthly_averages": {"average_speed_km_per_h": round(g_km_t/g_h, 2) if g_h > 0 else 0}
            }
        },
        "vehicles": v_list
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_json, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Fichero {OUTPUT_FILE} generado con éxito.")
    display_ui(final_json)

if __name__ == "__main__":
    main()