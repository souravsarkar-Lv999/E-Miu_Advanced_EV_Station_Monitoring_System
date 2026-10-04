from __future__ import annotations

import re


MIU_APP_OVERVIEW = (
    "E-Miu is a Streamlit EV charging operations demo for station admins and "
    "drivers. It monitors charging stations, booth availability, geofence-based "
    "driver check-in, queues, demo payments, reports, and the Miu assistant."
)


MIU_KNOWLEDGE_BASE = [
    {
        "title": "Navigation",
        "keywords": "home maps admin dashboard driver check-in queue reports talk to miu about project navigation page",
        "content": (
            "The app has Home for live station overview, Maps for nearby station discovery, "
            "Admin Dashboard for station and booth setup, Driver Check-In for starting sessions, "
            "Queue for waiting drivers, Reports for charging history, Talk to Miu for assistant help, "
            "and About Project for project details."
        ),
    },
    {
        "title": "Home station overview",
        "keywords": "home station overview booth status qr link selected station free charging finished occupied",
        "content": (
            "Home shows top metrics and a station overview selector. The selected station displays "
            "booth status cards, booth codes, geofence radius, and QR links for driver phone check-in."
        ),
    },
    {
        "title": "Maps",
        "keywords": "maps nearest station distance location gps free booth queue station map",
        "content": (
            "Maps compares nearby stations using the user's latitude and longitude. It highlights "
            "the selected station, shows free booths, charging booths, queue count, total booths, "
            "and a booth table for the selected station."
        ),
    },
    {
        "title": "Admin Dashboard",
        "keywords": "admin dashboard create station booth mark free assign queue qr code setup",
        "content": (
            "Admin Dashboard lets an operator create stations and booths, view booth QR codes, "
            "mark booths free, and assign the next waiting driver when a booth is available."
        ),
    },
    {
        "title": "Driver Check-In",
        "keywords": "driver check-in booth code gps geofence charging start battery target power session",
        "content": (
            "Driver Check-In lets a driver choose or scan a booth, provide GPS coordinates, "
            "enter battery and charging power details, and start a charging session only when "
            "inside the booth geofence."
        ),
    },
    {
        "title": "Geofence",
        "keywords": "geofence outside inside radius distance gps booth location check in fail accepted",
        "content": (
            "Geofence validation checks the driver's GPS distance from the booth coordinates. "
            "Check-in is accepted only when the driver is inside the booth radius."
        ),
    },
    {
        "title": "Queue",
        "keywords": "queue waiting driver join line assign next busy booth free station",
        "content": (
            "Drivers can join a station queue when booths are busy. The queue page shows waiting "
            "drivers and positions. Admins can assign or remove the next waiting driver when a booth frees up."
        ),
    },
    {
        "title": "Charging Session",
        "keywords": "charging session start finish estimated time battery percent power kw status",
        "content": (
            "Charging sessions start after successful booth check-in. The app estimates duration "
            "from starting battery, target battery, current power in kW, and an assumed 60 kWh battery."
        ),
    },
    {
        "title": "Payment",
        "keywords": "payment pay finish session upi card wallet net banking already paid demo",
        "content": (
            "The payment flow is a demo step before finishing a charging session. It supports "
            "UPI, cards, net banking, wallet, and an Already Paid demo option."
        ),
    },
    {
        "title": "Reports",
        "keywords": "reports csv download sessions completed average duration charging history",
        "content": (
            "Reports lists charging sessions, payment status, completion details, and summary "
            "metrics. It can export the charging session report as CSV."
        ),
    },
    {
        "title": "Local setup and AI configuration",
        "keywords": "openrouter api key model secrets toml preview mode ai mode local setup",
        "content": (
            "Miu uses preview mode when no valid local OpenRouter key and model are configured. "
            "For AI mode, the user creates .streamlit/secrets.toml locally with OPENROUTER_API_KEY "
            "and OPENROUTER_MODEL. The real secrets file is ignored by Git."
        ),
    },
]


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def build_miu_static_context(user_message: str, limit: int = 4) -> str:
    query_tokens = tokenize(user_message)
    scored_entries: list[tuple[int, dict[str, str]]] = []
    for entry in MIU_KNOWLEDGE_BASE:
        searchable_text = f"{entry['title']} {entry['keywords']} {entry['content']}"
        score = len(query_tokens & tokenize(searchable_text))
        scored_entries.append((score, entry))

    selected_entries = [
        entry
        for score, entry in sorted(scored_entries, key=lambda item: item[0], reverse=True)
        if score > 0
    ][:limit]
    if not selected_entries:
        selected_entries = MIU_KNOWLEDGE_BASE[:3]

    lines = [MIU_APP_OVERVIEW, "Relevant E-Miu knowledge:"]
    lines.extend(f"- {entry['title']}: {entry['content']}" for entry in selected_entries)
    return "\n".join(lines)
