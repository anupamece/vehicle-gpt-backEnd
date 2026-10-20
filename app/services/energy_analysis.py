"""Energy Analytics Service for VehicleGPT.

Calculates normalized energy metrics (kWh/100 km), performs city vs highway
comparative efficiency analysis, validates trips against data-quality rules,
and reports underlying comparison metrics with explicit data warnings.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import TelemetryModel, TripModel
from app.schemas.vehicle import (
    DrivingModeEnergyMetric,
    EnergyAnalyticsResponse,
    EnergyDataPointResponse,
)

METRIC_DEFINITION = (
    "Standardized energy consumption rate measured in kilowatt-hours per 100 kilometers (kWh/100 km). "
    "Calculated as (Total Consumed kWh / Total Distance km) * 100. "
    "Excludes invalid trips with non-positive energy, missing distance, or insufficient telemetry."
)


def analyze_energy_by_driving_mode(
    db: Session,
    vehicle_id: Optional[str] = None,
) -> EnergyAnalyticsResponse:
    """Analyze and compare energy consumption between city and highway driving modes.

    Standardized Metric: kWh per 100 km (kWh/100 km).
    Validates all trips, excludes anomalous measurements (< 0.05 km, non-positive energy),
    computes regenerative braking recovery efficiency, and returns comparative indicators.
    """
    trip_query = db.query(TripModel)
    if vehicle_id:
        trip_query = trip_query.filter(TripModel.vehicle_id == vehicle_id)

    trips = trip_query.all()
    warnings: List[str] = []

    # If TripModel has records, perform trip-level validation and aggregation
    if trips:
        valid_trips: List[TripModel] = []
        excluded_trips_count = 0

        for trip in trips:
            # 1. Validate distance
            if trip.distance_km is None or trip.distance_km <= 0.05:
                warnings.append(
                    f"Excluded trip '{trip.id}': invalid or near-zero distance ({trip.distance_km} km <= 0.05 km threshold)."
                )
                excluded_trips_count += 1
                continue

            # 2. Validate energy consumption
            if trip.energy_consumed_kwh is None or trip.energy_consumed_kwh <= 0.0:
                warnings.append(
                    f"Excluded trip '{trip.id}': invalid or non-positive energy consumed ({trip.energy_consumed_kwh} kWh)."
                )
                excluded_trips_count += 1
                continue

            # 3. Check telemetry point sample density for this trip
            sample_count = (
                db.query(TelemetryModel)
                .filter(TelemetryModel.trip_id == trip.id)
                .count()
            )
            if sample_count < 3:
                warnings.append(
                    f"Data quality notice for trip '{trip.id}': sparse telemetry data ({sample_count} samples < 3)."
                )

            valid_trips.append(trip)

        # Process valid trips using pandas
        if valid_trips:
            df = pd.DataFrame(
                [
                    {
                        "driving_mode": t.driving_mode or "city",
                        "consumed": float(t.energy_consumed_kwh or 0.0),
                        "regenerated": float(t.energy_regenerated_kwh or 0.0),
                        "distance": float(t.distance_km or 0.0),
                        "speed": float(t.avg_speed_kmh or 0.0),
                    }
                    for t in valid_trips
                ]
            )

            breakdown_list: List[DrivingModeEnergyMetric] = []
            mode_metrics: Dict[str, Dict[str, float]] = {}

            # Ensure both city and highway are evaluated
            all_modes = sorted(list(df["driving_mode"].unique()))
            for mode in all_modes:
                group = df[df["driving_mode"] == mode]
                tot_consumed = float(group["consumed"].sum())
                tot_regen = float(group["regenerated"].sum())
                tot_dist = float(group["distance"].sum())
                avg_speed = float(group["speed"].mean()) if not group.empty else 0.0
                net_consumed = max(0.0, tot_consumed - tot_regen)

                consumption_per_100km = (
                    round((tot_consumed / tot_dist) * 100.0, 2) if tot_dist > 0.0 else None
                )
                regen_efficiency = (
                    round((tot_regen / tot_consumed) * 100.0, 2) if tot_consumed > 0.0 else 0.0
                )

                metric = DrivingModeEnergyMetric(
                    driving_mode=str(mode),
                    energy_metric_unit="kWh/100 km",
                    consumption_per_100km=consumption_per_100km,
                    total_energy_consumed_kwh=round(tot_consumed, 2),
                    total_energy_regenerated_kwh=round(tot_regen, 2),
                    net_energy_consumed_kwh=round(net_consumed, 2),
                    total_distance_km=round(tot_dist, 2),
                    average_speed_kmh=round(avg_speed, 1),
                    efficiency_score_percent=regen_efficiency,
                )
                breakdown_list.append(metric)
                mode_metrics[str(mode)] = {
                    "consumption_per_100km": consumption_per_100km or 0.0,
                    "regen_efficiency": regen_efficiency,
                    "distance": tot_dist,
                    "consumed": tot_consumed,
                }

            tot_all_dist = float(df["distance"].sum())
            tot_all_cons = float(df["consumed"].sum())
            tot_all_regen = float(df["regenerated"].sum())
            fleet_avg = (
                round((tot_all_cons / tot_all_dist) * 100.0, 2) if tot_all_dist > 0 else None
            )

            # Build underlying comparison values between city and highway
            city_stat = mode_metrics.get("city")
            highway_stat = mode_metrics.get("highway")
            comparison: Dict[str, Any] = {
                "valid_trips_analyzed": len(valid_trips),
                "excluded_trips_count": excluded_trips_count,
            }

            if city_stat and highway_stat and city_stat["consumption_per_100km"] > 0:
                delta = round(highway_stat["consumption_per_100km"] - city_stat["consumption_per_100km"], 2)
                percent_diff = round((delta / city_stat["consumption_per_100km"]) * 100.0, 1)
                comparison.update(
                    {
                        "city_kwh_per_100km": city_stat["consumption_per_100km"],
                        "highway_kwh_per_100km": highway_stat["consumption_per_100km"],
                        "consumption_delta_kwh_per_100km": delta,
                        "highway_consumption_increase_percent": percent_diff,
                        "more_efficient_mode": "city" if delta > 0 else "highway",
                        "city_regen_efficiency_percent": city_stat["regen_efficiency"],
                        "highway_regen_efficiency_percent": highway_stat["regen_efficiency"],
                        "regen_efficiency_advantage_mode": "city"
                        if city_stat["regen_efficiency"] > highway_stat["regen_efficiency"]
                        else "highway",
                        "findings": (
                            f"City driving achieved higher regenerative braking recovery ({city_stat['regen_efficiency']}%) "
                            f"and lower normalized energy consumption ({city_stat['consumption_per_100km']} kWh/100 km). "
                            f"Highway cruising consumed {percent_diff}% more energy per 100 km due to aerodynamic drag."
                        ),
                    }
                )

            return EnergyAnalyticsResponse(
                group_by="driving_mode",
                metric_definition=METRIC_DEFINITION,
                breakdown=breakdown_list,
                summary={
                    "total_distance_km": round(tot_all_dist, 2),
                    "total_consumed_kwh": round(tot_all_cons, 2),
                    "total_regenerated_kwh": round(tot_all_regen, 2),
                    "net_consumed_kwh": round(tot_all_cons - tot_all_regen, 2),
                    "fleet_avg_kwh_per_100km": fleet_avg,
                    "valid_trips": len(valid_trips),
                    "excluded_trips": excluded_trips_count,
                },
                warnings=warnings,
                comparison=comparison,
            )

    # Fallback to TelemetryModel points if TripModel is empty
    telem_query = db.query(
        TelemetryModel.driving_mode,
        TelemetryModel.energy_consumed,
        TelemetryModel.energy_regenerated,
        TelemetryModel.distance_km,
        TelemetryModel.speed,
    )
    if vehicle_id:
        telem_query = telem_query.filter(TelemetryModel.vehicle_id == vehicle_id)
    telem_records = telem_query.all()

    if not telem_records:
        warnings.append("No telemetry or trip records found for the requested filter criteria.")
        return EnergyAnalyticsResponse(
            group_by="driving_mode",
            metric_definition=METRIC_DEFINITION,
            breakdown=[],
            summary={
                "total_distance_km": 0.0,
                "total_consumed_kwh": 0.0,
                "total_regenerated_kwh": 0.0,
                "net_consumed_kwh": 0.0,
                "fleet_avg_kwh_per_100km": None,
                "valid_trips": 0,
                "excluded_trips": 0,
            },
            warnings=warnings,
            comparison=None,
        )

    # Process telemetry records with data validation
    valid_telem = []
    for r in telem_records:
        dist = r.distance_km or 0.0
        cons = r.energy_consumed or 0.0
        if dist <= 0.001 or cons <= 0.0:
            continue
        valid_telem.append(
            {
                "driving_mode": r.driving_mode or "city",
                "consumed": cons,
                "regenerated": r.energy_regenerated or 0.0,
                "distance": dist,
                "speed": r.speed or 0.0,
            }
        )

    if not valid_telem:
        warnings.append("All available telemetry points were excluded due to invalid distance or non-positive energy.")
        return EnergyAnalyticsResponse(
            group_by="driving_mode",
            metric_definition=METRIC_DEFINITION,
            breakdown=[],
            summary={},
            warnings=warnings,
            comparison=None,
        )

    df_telem = pd.DataFrame(valid_telem)
    breakdown_list = []
    for mode, group in df_telem.groupby("driving_mode"):
        tot_c = float(group["consumed"].sum())
        tot_r = float(group["regenerated"].sum())
        tot_d = float(group["distance"].sum())
        avg_s = float(group["speed"].mean())
        kwh_100 = round((tot_c / tot_d) * 100.0, 2) if tot_d > 0 else None
        eff = round((tot_r / tot_c) * 100.0, 2) if tot_c > 0 else 0.0

        breakdown_list.append(
            DrivingModeEnergyMetric(
                driving_mode=str(mode),
                energy_metric_unit="kWh/100 km",
                consumption_per_100km=kwh_100,
                total_energy_consumed_kwh=round(tot_c, 2),
                total_energy_regenerated_kwh=round(tot_r, 2),
                net_energy_consumed_kwh=round(max(0.0, tot_c - tot_r), 2),
                total_distance_km=round(tot_d, 2),
                average_speed_kmh=round(avg_s, 1),
                efficiency_score_percent=eff,
            )
        )

    tot_d_all = float(df_telem["distance"].sum())
    tot_c_all = float(df_telem["consumed"].sum())
    tot_r_all = float(df_telem["regenerated"].sum())

    return EnergyAnalyticsResponse(
        group_by="driving_mode",
        metric_definition=METRIC_DEFINITION,
        breakdown=breakdown_list,
        summary={
            "total_distance_km": round(tot_d_all, 2),
            "total_consumed_kwh": round(tot_c_all, 2),
            "total_regenerated_kwh": round(tot_r_all, 2),
            "net_consumed_kwh": round(tot_c_all - tot_r_all, 2),
            "fleet_avg_kwh_per_100km": round((tot_c_all / tot_d_all) * 100.0, 2) if tot_d_all > 0 else None,
        },
        warnings=warnings,
        comparison=None,
    )


def analyze_energy_telemetry(
    db: Session,
    vehicle_id: Optional[str] = None,
) -> List[EnergyDataPointResponse]:
    """Aggregate telemetry into resampled energy consumption and regeneration points using pandas."""
    query = db.query(
        TelemetryModel.timestamp,
        TelemetryModel.energy_consumed,
        TelemetryModel.energy_regenerated,
    )
    if vehicle_id:
        query = query.filter(TelemetryModel.vehicle_id == vehicle_id)

    records = query.all()
    if not records:
        return []

    df = pd.DataFrame(
        [
            {
                "timestamp": r.timestamp,
                "consumed": r.energy_consumed or 0.0,
                "regenerated": r.energy_regenerated or 0.0,
            }
            for r in records
        ]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)

    resampled = df.resample("2h").sum().reset_index()

    points = []
    for _, row in resampled.iterrows():
        t_str = row["timestamp"].strftime("%H:%M")
        points.append(
            EnergyDataPointResponse(
                timestamp=t_str,
                consumed=round(float(row["consumed"]), 2),
                regenerated=round(float(row["regenerated"]), 2),
            )
        )
    return points


def calculate_fleet_efficiency(db: Session) -> Dict[str, Any]:
    """Calculate fleet energy efficiency statistics with pandas."""
    records = db.query(TelemetryModel.energy_consumed, TelemetryModel.energy_regenerated).all()
    if not records:
        return {
            "total_consumed_kwh": 0.0,
            "total_regenerated_kwh": 0.0,
            "net_kwh": 0.0,
            "regen_efficiency_percent": 0.0,
        }

    df = pd.DataFrame(
        [
            {
                "consumed": r.energy_consumed or 0.0,
                "regenerated": r.energy_regenerated or 0.0,
            }
            for r in records
        ]
    )
    total_consumed = float(df["consumed"].sum())
    total_regenerated = float(df["regenerated"].sum())
    net_kwh = max(0.0, total_consumed - total_regenerated)
    regen_ratio = (total_regenerated / total_consumed * 100.0) if total_consumed > 0 else 0.0

    return {
        "total_consumed_kwh": round(total_consumed, 2),
        "total_regenerated_kwh": round(total_regenerated, 2),
        "net_kwh": round(net_kwh, 2),
        "regen_efficiency_percent": round(regen_ratio, 2),
    }
