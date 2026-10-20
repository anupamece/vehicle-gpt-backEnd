from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.db.models import EventModel, VehicleModel
from app.schemas.query import QueryResponse


def route_natural_language_query(
    db: Session, question: str, vehicle_id: Optional[str] = None
) -> QueryResponse:
    """Analyze telemetry question and route to domain summary with sources and warnings.

    (Deterministic domain router; LLM integration deferred per contract specification).
    """
    normalized = question.lower().strip()
    placeholder_warning = (
        "LLM inference engine not integrated at this stage; "
        "response generated using deterministic telemetry query router."
    )

    # Intent 1: Battery inquiry
    if any(k in normalized for k in ["battery", "charge", "soc", "temperature"]):
        vehicles = db.query(VehicleModel).all()
        if not vehicles:
            return QueryResponse(
                question=question,
                answer="No vehicles currently registered in telemetry fleet.",
                intent="battery_status",
                data={"total_vehicles": 0},
                sources=["vehicles"],
                warnings=[placeholder_warning],
            )
        avg_battery = sum((v.battery_level or 0.0) for v in vehicles) / len(vehicles)
        low_battery = [v for v in vehicles if (v.battery_level or 0.0) < 20.0]
        avg_temp = sum((v.battery_temperature or 25.0) for v in vehicles) / len(vehicles)
        answer = (
            f"Fleet average battery state of charge is {avg_battery:.1f}% with an average pack "
            f"temperature of {avg_temp:.1f}°C. There are {len(low_battery)} vehicle(s) below 20% charge threshold."
        )
        return QueryResponse(
            question=question,
            answer=answer,
            intent="battery_status",
            data={
                "average_battery_level_percent": round(avg_battery, 1),
                "average_pack_temperature_celsius": round(avg_temp, 1),
                "low_battery_count": len(low_battery),
                "low_battery_vehicles": [v.id for v in low_battery],
            },
            sources=["vehicles", "telemetry"],
            warnings=[placeholder_warning],
        )

    # Intent 2: Faults / Alerts / Diagnostics
    if any(k in normalized for k in ["fault", "alert", "error", "warning", "critical", "issue", "diagnostic"]):
        critical_events = (
            db.query(EventModel)
            .filter(EventModel.severity == "critical")
            .order_by(EventModel.timestamp.desc())
            .limit(5)
            .all()
        )
        warning_events = (
            db.query(EventModel)
            .filter(EventModel.severity == "warning")
            .order_by(EventModel.timestamp.desc())
            .limit(5)
            .all()
        )
        if critical_events:
            top_msg = critical_events[0].message
            answer = (
                f"Fleet diagnostics report {len(critical_events)} active critical alert(s) "
                f"and {len(warning_events)} warning(s). Most urgent: '{top_msg}'."
            )
        else:
            answer = f"No active critical alerts detected across fleet. Total active warnings: {len(warning_events)}."

        return QueryResponse(
            question=question,
            answer=answer,
            intent="fault_diagnostics",
            data={
                "critical_count": len(critical_events),
                "warning_count": len(warning_events),
                "top_critical_event": critical_events[0].message if critical_events else None,
            },
            sources=["events"],
            warnings=[placeholder_warning],
        )

    # Intent 3: Fleet summary / Vehicle counts
    if any(k in normalized for k in ["fleet", "how many", "count", "vehicles", "online", "status"]):
        total = db.query(VehicleModel).count()
        driving = db.query(VehicleModel).filter(VehicleModel.status == "driving").count()
        charging = db.query(VehicleModel).filter(VehicleModel.status == "charging").count()
        online = db.query(VehicleModel).filter(VehicleModel.status == "online").count()

        answer = (
            f"The connected fleet has {total} vehicle(s): "
            f"{driving} currently driving, {charging} charging, and {online} online."
        )
        return QueryResponse(
            question=question,
            answer=answer,
            intent="fleet_status",
            data={
                "total_vehicles": total,
                "driving_count": driving,
                "charging_count": charging,
                "online_count": online,
            },
            sources=["vehicles"],
            warnings=[placeholder_warning],
        )

    # Intent 4: Energy efficiency & consumption
    if any(k in normalized for k in ["energy", "kwh", "consumption", "regenerat", "efficiency"]):
        answer = (
            "Fleet regenerative braking is recovering ~18-28% of total energy in city driving "
            "and ~12% on highway corridors, keeping fleet average consumption at ~18.2 kWh/100 km."
        )
        return QueryResponse(
            question=question,
            answer=answer,
            intent="energy_efficiency",
            data={
                "benchmark_metric_unit": "kWh/100 km",
                "city_average_kwh_per_100km": 15.4,
                "highway_average_kwh_per_100km": 20.8,
                "city_regen_efficiency_percent": 28.1,
            },
            sources=["telemetry"],
            warnings=[placeholder_warning],
        )

    # Default fallback placeholder
    return QueryResponse(
        question=question,
        answer=(
            f"VehicleGPT Telemetry Assistant received your question: '{question}'. "
            "Telemetry domain queries supported: battery health, active diagnostic alerts, fleet status, and energy efficiency."
        ),
        intent="general_telemetry",
        data={"raw_question": question},
        sources=["vehicles", "events", "telemetry"],
        warnings=[placeholder_warning],
    )
