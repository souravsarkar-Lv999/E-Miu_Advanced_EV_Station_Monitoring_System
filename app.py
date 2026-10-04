from __future__ import annotations

import csv
import io
import json
import os
import socket
from datetime import datetime
from pathlib import Path
from urllib import error, request
from urllib.parse import urlencode

import qrcode
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageOps
from sqlalchemy.orm import selectinload
from sqlalchemy import func, select

from ev_monitoring.database import get_session, init_db
from ev_monitoring.models import (
    Booth,
    BoothStatus,
    ChargingSession,
    QueueEntry,
    QueueStatus,
    SessionStatus,
    Station,
)
from ev_monitoring.miu_knowledge import build_miu_static_context
from ev_monitoring.seed import seed_demo_data
from ev_monitoring.services import (
    assign_next_waiting_driver,
    attempt_check_in,
    create_booth,
    create_station,
    dashboard_summary,
    estimate_minutes,
    estimate_payment_amount,
    finish_session,
    get_driver_queue_entry,
    join_queue,
    reset_booth,
    station_live_status,
)
from ev_monitoring.vehicles import VEHICLE_MODELS


st.set_page_config(
    page_title="E-Miu Advanced EV Station Monitoring System",
    page_icon="EV",
    layout="wide",
)


MIU_IMAGE_PATH = Path("C:/Users/Sourav/Downloads/miu.png")
REPO_URL = "https://github.com/souravsarkar-Lv999/E-Miu_Advanced_EV_Station_Monitoring_System-Experimental-"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY_PLACEHOLDERS = {
    "",
    "PASTE_YOUR_REAL_OPENROUTER_KEY_HERE",
    "paste-your-own-openrouter-key-here",
    "your-real-openrouter-key",
}
OPENROUTER_MODEL_PLACEHOLDERS = {
    "",
    "PASTE_YOUR_OPENROUTER_MODEL_HERE",
    "paste-your-own-openrouter-model-here",
    "paste-your-own-llm-model-here",
    "your-openrouter-model",
}
SELECTED_STATION_STATE_KEY = "selected_station_id"
HOME_STATION_SELECTOR_KEY = "home_station_selector"
MAP_STATION_SELECTOR_KEY = "map_station_selector"


def bootstrap() -> None:
    init_db()
    with get_session() as db:
        seed_demo_data(db)


def status_badge(status: str) -> str:
    colors = {
        "free": "#0f766e",
        "occupied": "#a16207",
        "charging": "#2563eb",
        "finished": "#7c3aed",
    }
    color = colors.get(status, "#374151")
    return (
        f"<span style='background:{color};color:white;padding:4px 8px;"
        f"border-radius:6px;font-size:0.85rem'>{status.upper()}</span>"
    )


def render_geolocation_helper(
    default_latitude: float,
    default_longitude: float,
    auto_apply: bool = False,
) -> None:
    components.html(
        f"""
        <div style="font-family:Arial,sans-serif;border:1px solid #d1d5db;border-radius:8px;padding:12px;background:#f8fafc">
          <strong>Phone GPS helper</strong>
          <p style="margin:8px 0">Tap the button and allow location. If your browser allows it, the booth page will auto-fill your coordinates.</p>
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-start;max-width:100%">
          <button onclick="getLocation()" style="border:0;border-radius:6px;background:#111827;color:white;padding:8px 12px;cursor:pointer;max-width:100%">
            Get my location
          </button>
          <button onclick="copyDemo()" style="border:1px solid #9ca3af;border-radius:6px;background:white;color:#111827;padding:8px 12px;cursor:pointer;max-width:100%">
            Use demo station location
          </button>
          </div>
          <div style="margin-top:12px;display:grid;gap:10px">
            <div>
              <label style="display:block;margin-bottom:4px;font-size:14px">Latitude</label>
              <input id="lat-output" type="text" value="" readonly style="width:100%;max-width:100%;box-sizing:border-box;padding:10px;border:1px solid #d1d5db;border-radius:6px;background:white" />
            </div>
            <div>
              <label style="display:block;margin-bottom:4px;font-size:14px">Longitude</label>
              <input id="lon-output" type="text" value="" readonly style="width:100%;max-width:100%;box-sizing:border-box;padding:10px;border:1px solid #d1d5db;border-radius:6px;background:white" />
            </div>
          </div>
          <pre id="location-output" style="white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere;margin-top:10px;background:white;border:1px solid #e5e7eb;border-radius:6px;padding:8px;max-width:100%;box-sizing:border-box">Waiting for location...</pre>
        </div>
        <script>
          const output = document.getElementById("location-output");
          const latOutput = document.getElementById("lat-output");
          const lonOutput = document.getElementById("lon-output");
          const autoApply = {str(auto_apply).lower()};
          function setUrlCoordinates(lat, lon) {{
            const parentWindow = window.parent;
            const currentUrl = new URL(parentWindow.location.href);
            currentUrl.searchParams.set("lat", lat);
            currentUrl.searchParams.set("lon", lon);
            parentWindow.location.href = currentUrl.toString();
          }}
          function writeLocation(lat, lon) {{
            latOutput.value = lat;
            lonOutput.value = lon;
            output.textContent = `Latitude: ${{lat}}\\nLongitude: ${{lon}}`;
            if (autoApply) {{
              try {{
                setUrlCoordinates(lat, lon);
              }} catch (error) {{
                output.textContent += "\\nCould not auto-apply coordinates.";
              }}
            }}
          }}
          function getLocation() {{
            if (!navigator.geolocation) {{
              output.textContent = "Your browser does not support GPS location.";
              return;
            }}
            output.textContent = "Requesting GPS permission...";
            navigator.geolocation.getCurrentPosition(
              (position) => {{
                writeLocation(position.coords.latitude.toFixed(6), position.coords.longitude.toFixed(6));
              }},
              (error) => {{
                output.textContent = "GPS failed: " + error.message + "\\nFor demo testing, use the station coordinates below.";
              }},
              {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
            );
          }}
          function copyDemo() {{
            writeLocation({default_latitude:.6f}, {default_longitude:.6f});
          }}
          const initialUrl = new URL(window.parent.location.href);
          if (initialUrl.searchParams.get("lat") && initialUrl.searchParams.get("lon")) {{
            writeLocation(initialUrl.searchParams.get("lat"), initialUrl.searchParams.get("lon"));
          }}
        </script>
        """,
        height=370,
    )


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M")


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "localhost"


def get_current_server_port(default: int = 8501) -> int:
    host_header = (
        st.context.headers.get("X-Forwarded-Host")
        or st.context.headers.get("Host")
        or ""
    )
    host_value = host_header.split(",")[0].strip()
    if ":" not in host_value:
        return default
    _, port_text = host_value.rsplit(":", 1)
    try:
        return int(port_text)
    except ValueError:
        return default


def build_booth_url(booth_code: str) -> str:
    host = get_local_ip()
    port = get_current_server_port()
    query = urlencode(
        {
            "page": "driver",
            "booth": booth_code,
            "mobile": "1",
        }
    )
    return f"http://{host}:{port}/?{query}"


def make_qr_image(url: str):
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def query_value(name: str, default: str = "") -> str:
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value


def query_float(name: str, fallback: float) -> float:
    value = query_value(name)
    if not value:
        return fallback
    try:
        return float(value)
    except ValueError:
        return fallback


def query_optional_float(name: str) -> float | None:
    value = query_value(name)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def query_optional_int(name: str) -> int | None:
    value = query_value(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def init_demo_state() -> None:
    st.session_state.setdefault("payment_records", {})
    st.session_state.setdefault("pending_payment_session_id", None)
    st.session_state.setdefault("finish_after_payment_session_id", None)
    st.session_state.setdefault(SELECTED_STATION_STATE_KEY, None)
    st.session_state.setdefault(
        "miu_messages",
        [
            {
                "role": "assistant",
                "content": "Hi, I am Miu. Ask me about stations, queues, charging sessions, maps, or demo payments.",
            }
        ],
    )


@st.cache_data(show_spinner=False)
def load_miu_avatar() -> bytes | None:
    if not MIU_IMAGE_PATH.exists():
        return None

    with Image.open(MIU_IMAGE_PATH) as source:
        size = min(source.size)
        left = (source.width - size) // 2
        top = (source.height - size) // 2
        avatar = source.crop((left, top, left + size, top + size)).convert("RGBA")
        avatar = ImageOps.fit(avatar, (128, 128), centering=(0.5, 0.5))

    mask = Image.new("L", (128, 128), 0)
    drawer = ImageDraw.Draw(mask)
    drawer.ellipse((0, 0, 127, 127), fill=255)
    avatar.putalpha(mask)

    buffer = io.BytesIO()
    avatar.save(buffer, format="PNG")
    return buffer.getvalue()


def render_miu_sidebar_card() -> None:
    st.sidebar.markdown("---")
    miu_avatar = load_miu_avatar()
    if miu_avatar is not None:
        st.sidebar.image(miu_avatar, width=68)
    st.sidebar.markdown("**Talk to Miu**")
    st.sidebar.caption("Mascot assistant for EV guidance. AI chat coming soon.")


def render_live_update_hint(label: str = "Live updates every 5 seconds on monitoring panels.") -> None:
    st.caption(label)


def get_app_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, None)
    except Exception:
        value = None
    if value is None:
        value = os.getenv(name, default)
    return str(value).strip()


def get_miu_llm_config() -> tuple[str, str]:
    api_key = get_app_secret("OPENROUTER_API_KEY")
    if api_key in OPENROUTER_KEY_PLACEHOLDERS or not api_key.startswith("sk-"):
        api_key = ""
    model = get_app_secret("OPENROUTER_MODEL")
    if model in OPENROUTER_MODEL_PLACEHOLDERS:
        model = ""
    return api_key, model


def get_miu_model_display_name(model: str) -> str:
    normalized_model = model.lower()
    if "nvidia" in normalized_model and "nemotron-3" in normalized_model:
        return "NVIDIA: Nemotron 3"
    return "Custom LLM"


def build_miu_live_context() -> str:
    try:
        with get_session() as db:
            summary = dashboard_summary(db)
            stations = db.scalars(
                select(Station)
                .options(selectinload(Station.booths))
                .order_by(Station.name)
            ).all()
            lines = [
                "Current live app snapshot:",
                (
                    f"- Totals: {summary['total_booths']} booths, "
                    f"{summary['active_sessions']} active sessions, "
                    f"{summary['waiting_drivers']} waiting drivers, "
                    f"{summary['completed_sessions']} completed sessions."
                ),
            ]
            for station in stations[:5]:
                booths = list(station.booths)
                free_count = sum(1 for booth in booths if booth.status == BoothStatus.FREE)
                charging_count = sum(1 for booth in booths if booth.status == BoothStatus.CHARGING)
                finished_count = sum(1 for booth in booths if booth.status == BoothStatus.FINISHED)
                waiting_count = db.scalar(
                    select(func.count(QueueEntry.id)).where(
                        QueueEntry.station_id == station.id,
                        QueueEntry.status == QueueStatus.WAITING,
                    )
                ) or 0
                lines.append(
                    f"- {station.name}: {free_count} free, {charging_count} charging, "
                    f"{finished_count} finished, {waiting_count} waiting, {len(booths)} total booths."
                )
            return "\n".join(lines)
    except Exception:
        return "Current live app snapshot is unavailable."


def generate_preview_miu_reply(user_message: str) -> str:
    message = user_message.lower().strip()
    if not message:
        return "Share a short question and I will help with stations, queues, charging, maps, or demo payments."

    if any(word in message for word in ["hello", "hi", "hey", "miu"]):
        return "Hello. I can help you find a station, explain queue flow, or guide you through the demo payment step."
    if any(word in message for word in ["map", "station", "near", "nearest", "charger"]):
        return "Open Maps to compare nearby stations. Pick a station from the selector to see free booths, active charging spots, and the current queue."
    if "queue" in message or "waiting" in message:
        return "Queue drivers join from the Queue page. When a booth becomes free, admin can assign the next driver, and the live panels refresh automatically."
    if any(word in message for word in ["payment", "pay", "upi", "credit", "debit", "wallet"]):
        return "The demo payment flow appears before session finish. It supports UPI, cards, net banking, wallet, and an Already Paid demo option."
    if any(word in message for word in ["finish", "session", "charging"]):
        return "Charging sessions start from Driver Check-In. To close one now, use Finish + pay so the demo payment completes before the session is marked finished."
    if any(word in message for word in ["home", "dashboard", "admin"]):
        return "Home gives a compact station view, Admin Dashboard is for booth setup and controls, and Maps is for nearby-station discovery."
    if any(word in message for word in ["who are you", "mascot", "about you"]):
        return "I am Miu, the mascot preview for this EV platform. This is a lightweight assistant demo showing how a future AI helper could guide drivers and operators."
    return (
        "Preview mode is active, so I answer a focused set of EV app questions. "
        "Try asking about maps, queue status, charging sessions, payments, or station controls."
    )


def generate_openrouter_miu_reply(
    user_message: str,
    chat_history: list[dict[str, str]],
    api_key: str,
    model: str,
) -> str:
    static_context = build_miu_static_context(user_message)
    live_context = build_miu_live_context()
    messages = [
        {
            "role": "system",
            "content": (
                "You are Miu, a concise EV charging assistant inside the E-Miu demo app. "
                "Help users with station discovery, queue flow, booth check-in, charging sessions, "
                "demo payments, and app navigation. Keep answers practical, friendly, and short. "
                "Use the supplied E-Miu context as your source of truth for app behavior. "
                "If the user asks something outside this app, answer briefly and guide them back to E-Miu."
            ),
        },
        {"role": "system", "content": static_context},
        {"role": "system", "content": live_context},
    ]
    messages.extend(chat_history[-8:])
    messages.append({"role": "user", "content": user_message})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.35,
        "max_tokens": 420,
    }
    encoded_payload = json.dumps(payload).encode("utf-8")
    api_request = request.Request(
        OPENROUTER_API_URL,
        data=encoded_payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": REPO_URL,
            "X-Title": "E-Miu Advanced EV Station Monitoring System",
        },
        method="POST",
    )
    try:
        with request.urlopen(api_request, timeout=30) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        if exc.code in {401, 403}:
            return generate_preview_miu_reply(user_message)
        details = exc.read().decode("utf-8", errors="replace")
        return f"Miu could not reach the configured LLM right now. OpenRouter returned {exc.code}: {details[:240]}"
    except Exception as exc:
        return f"Miu could not reach the configured LLM right now: {exc}"

    try:
        return response_payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        return "Miu received an unexpected LLM response. Check the OpenRouter model name and API key."


def generate_miu_reply(user_message: str, chat_history: list[dict[str, str]]) -> str:
    api_key, model = get_miu_llm_config()
    if api_key and model:
        return generate_openrouter_miu_reply(user_message, chat_history, api_key, model)
    return generate_preview_miu_reply(user_message)


def render_miu_preview() -> None:
    st.markdown(
        """
        <div style="padding:0.75rem 0.95rem;border:1px solid #cbd5e1;border-radius:16px;background:linear-gradient(135deg,#f8fafc 0%,#ecfeff 100%);">
          <div style="font-size:0.78rem;font-weight:700;color:#0f766e;text-transform:uppercase;letter-spacing:0.04em;">Preview</div>
          <div style="margin-top:0.2rem;font-size:1rem;font-weight:700;color:#0f172a;">Compact AI assistant concept for Miu</div>
          <div style="margin-top:0.35rem;font-size:0.94rem;color:#475569;">
            Lightweight guidance for station discovery, queue help, charging flow, and demo payments.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_miu_chat() -> None:
    with st.container(border=True):
        api_key, model = get_miu_llm_config()
        st.markdown("**Miu chat**")
        if api_key and model:
            st.caption(f"AI mode via {get_miu_model_display_name(model)}.")
        else:
            st.caption("Preview mode. Add a local OpenRouter key to enable AI replies.")
        for message in st.session_state["miu_messages"][-6:]:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        user_prompt = st.chat_input("Ask Miu about maps, queue, charging, or payment")
        if user_prompt:
            chat_history = st.session_state["miu_messages"]
            assistant_reply = generate_miu_reply(user_prompt, chat_history)
            st.session_state["miu_messages"].append({"role": "user", "content": user_prompt})
            st.session_state["miu_messages"].append(
                {"role": "assistant", "content": assistant_reply}
            )
            st.rerun()


def build_station_map(
    stations: list[dict[str, float | int | str | None]],
    *,
    selected_station_id: int | None,
    user_latitude: float | None,
    user_longitude: float | None,
) -> None:
    if not stations:
        st.info("No stations are available on the map yet.")
        return

    station_payload = json.dumps(stations)
    default_station = next(
        (station for station in stations if station["station_id"] == selected_station_id),
        stations[0],
    )
    center_latitude = user_latitude if user_latitude is not None else default_station["latitude"]
    center_longitude = (
        user_longitude if user_longitude is not None else default_station["longitude"]
    )

    components.html(
        f"""
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
          crossorigin=""
        />
        <div style="border:1px solid #dbe4ef;border-radius:16px;overflow:hidden">
          <div id="station-map" style="height:460px;width:100%"></div>
        </div>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
          integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
          crossorigin=""></script>
        <script>
          const stations = {station_payload};
          const selectedStationId = {json.dumps(selected_station_id)};
          const userLatitude = {json.dumps(user_latitude)};
          const userLongitude = {json.dumps(user_longitude)};
          const map = L.map("station-map", {{ zoomControl: true }}).setView(
            [{float(center_latitude)}, {float(center_longitude)}],
            13
          );

          L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap contributors"
          }}).addTo(map);

          const selectedIcon = L.divIcon({{
            className: "",
            html: "<div style='width:18px;height:18px;border-radius:999px;background:#0f766e;border:3px solid white;box-shadow:0 6px 14px rgba(15,118,110,0.35)'></div>",
            iconSize: [18, 18],
            iconAnchor: [9, 9]
          }});
          const defaultIcon = L.divIcon({{
            className: "",
            html: "<div style='width:16px;height:16px;border-radius:999px;background:#1d4ed8;border:3px solid white;box-shadow:0 6px 14px rgba(29,78,216,0.30)'></div>",
            iconSize: [16, 16],
            iconAnchor: [8, 8]
          }});

          function updateSelection(stationId) {{
            const parentWindow = window.parent;
            const url = new URL(parentWindow.location.href);
            url.searchParams.set("page", "map");
            url.searchParams.set("station_id", stationId);
            if (userLatitude !== null && userLongitude !== null) {{
              url.searchParams.set("lat", userLatitude);
              url.searchParams.set("lon", userLongitude);
            }}
            parentWindow.location.href = url.toString();
          }}

          stations.forEach((station) => {{
            const marker = L.marker(
              [station.latitude, station.longitude],
              {{ icon: station.station_id === selectedStationId ? selectedIcon : defaultIcon }}
            ).addTo(map);

            marker.bindPopup(`
              <div style="min-width:220px;font-family:Arial,sans-serif">
                <strong>${{station.station_name}}</strong><br />
                <span>${{station.address}}</span><br /><br />
                <span>Free: ${{station.free_count}}</span><br />
                <span>Occupied: ${{station.occupied_count}}</span><br />
                <span>Charging: ${{station.charging_count}}</span><br />
                <span>Queue: ${{station.queue_count}}</span><br />
              </div>
            `);
            marker.on("click", () => updateSelection(station.station_id));
          }});

          window.__openStation = updateSelection;

          if (userLatitude !== null && userLongitude !== null) {{
            const you = L.circleMarker([userLatitude, userLongitude], {{
              radius: 7,
              color: "#f97316",
              fillColor: "#fb923c",
              fillOpacity: 0.9,
              weight: 2
            }}).addTo(map);
            you.bindTooltip("Your location", {{ permanent: false }});
          }}
        </script>
        """,
        height=500,
    )


def render_payment_panel(session: ChargingSession) -> None:
    payment_records = st.session_state["payment_records"]
    quote = estimate_payment_amount(
        session.start_battery_percent,
        session.target_battery_percent,
        session.current_power_kw,
    )
    existing_payment = payment_records.get(session.id)

    st.subheader(f"Demo Payment for Session #{session.id}")
    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Units Used", f"{quote['units_kwh']:.2f} kWh")
    metric2.metric("Charging Power", f"{session.current_power_kw:.1f} kW")
    metric3.metric("Energy Cost", f"Rs {quote['energy_cost']:.2f}")
    metric4.metric("Total", f"Rs {quote['total_amount']:.2f}")
    st.caption(
        "Demo tariff: Rs 14.50 per kWh plus a small power-access fee based on charger load."
    )

    if existing_payment:
        st.success(
            f"{existing_payment['label']} recorded via {existing_payment['method']} at "
            f"{existing_payment['paid_at']}."
        )
        return

    with st.form(f"payment_form_{session.id}"):
        method = st.radio(
            "Payment method",
            ["UPI", "Credit Card", "Debit Card", "Net Banking", "Wallet", "Already Paid"],
            horizontal=True,
        )
        reference = st.text_input(
            "Reference",
            value=f"TXN-{session.id:04d}",
            help="Demo field to show how a transaction reference would appear.",
        )
        submitted = st.form_submit_button("Complete demo payment", type="primary")
        if submitted:
            label = "Payment complete" if method != "Already Paid" else "Already paid"
            payment_records[session.id] = {
                "method": method,
                "reference": reference.strip() or f"TXN-{session.id:04d}",
                "label": label,
                "amount": quote["total_amount"],
                "paid_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            }
            if st.session_state.get("finish_after_payment_session_id") == session.id:
                with get_session() as db:
                    finish_session(db, session.id)
                st.session_state["finish_after_payment_session_id"] = None
            st.session_state["pending_payment_session_id"] = None
            st.success(f"{label} for Session #{session.id}.")
            st.rerun()


def render_clipboard_paste_helper() -> None:
    components.html(
        """
        <div style="margin-bottom:8px">
          <button id="paste-coordinates" style="border:1px solid #9ca3af;border-radius:6px;background:white;color:#111827;padding:8px 12px;cursor:pointer">
            Paste
          </button>
          <span id="paste-status" style="margin-left:10px;font-family:Arial,sans-serif;font-size:14px;color:#4b5563"></span>
        </div>
        <script>
          const button = document.getElementById("paste-coordinates");
          const status = document.getElementById("paste-status");
          button.addEventListener("click", async () => {
            try {
              const text = await navigator.clipboard.readText();
              const match = text.match(/([-0-9.]+)\\s*,\\s*([-0-9.]+)/);
              if (!match) {
                status.textContent = "Clipboard should look like lat,lon";
                return;
              }
              const parentWindow = window.parent;
              const currentUrl = new URL(parentWindow.location.href);
              currentUrl.searchParams.set("lat", match[1]);
              currentUrl.searchParams.set("lon", match[2]);
              parentWindow.location.href = currentUrl.toString();
            } catch (error) {
              status.textContent = "Paste failed.";
            }
          });
        </script>
        """,
        height=50,
    )


@st.fragment(run_every="5s")
def render_home_live_panel(selected_station_id: int | None) -> None:
    with get_session() as db:
        summary = dashboard_summary(db)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Booths", summary["total_booths"])
        col2.metric("Active Sessions", summary["active_sessions"])
        col3.metric("Waiting Drivers", summary["waiting_drivers"])
        col4.metric("Completed Sessions", summary["completed_sessions"])

        stations = db.scalars(
            select(Station)
            .options(selectinload(Station.booths))
            .order_by(Station.name)
        ).all()
        if not stations:
            st.info("No stations yet. Create one from Admin Dashboard.")
            return

        selected_station_id = selected_station_id or st.session_state.get(SELECTED_STATION_STATE_KEY)
        station_options = {station.name: station for station in stations}
        station_names = list(station_options.keys())
        initial_index = 0
        if selected_station_id is not None:
            initial_index = next(
                (index for index, station in enumerate(stations) if station.id == selected_station_id),
                0,
            )
        initial_station_name = station_names[initial_index]
        current_widget_value = st.session_state.get(HOME_STATION_SELECTOR_KEY)
        if current_widget_value not in station_options:
            st.session_state[HOME_STATION_SELECTOR_KEY] = initial_station_name
        selected_station_name = st.selectbox(
            "Station overview",
            station_names,
            index=initial_index,
            key=HOME_STATION_SELECTOR_KEY,
        )
        selected_station = station_options[selected_station_name]
        st.session_state[SELECTED_STATION_STATE_KEY] = selected_station.id

        st.subheader(f"{selected_station.name} Booth Status")
        st.caption(selected_station.address)
        booths = sorted(selected_station.booths, key=lambda booth: booth.name)
        if not booths:
            st.info("No booths yet for this station.")
            return

        cols = st.columns(min(len(booths), 3))
        for index, booth in enumerate(booths):
            with cols[index % len(cols)]:
                st.markdown(f"### {booth.name}")
                st.markdown(status_badge(booth.status.value), unsafe_allow_html=True)
                st.caption(f"Code: {booth.code} | Radius {booth.radius_meters:.0f} m")
                with st.expander("QR + link", expanded=False):
                    booth_url = build_booth_url(booth.code)
                    st.image(make_qr_image(booth_url), width=120)
                    st.code(booth_url, language=None)


def home_page() -> None:
    st.markdown(
        """
        <div style="padding:0.35rem 0 1rem 0;">
          <div style="display:inline-block;padding:0.95rem 1.2rem 1rem 1.2rem;border-radius:20px;background:linear-gradient(135deg,#e0f2fe 0%,#f8fafc 55%,#dcfce7 100%);box-shadow:0 18px 40px rgba(15,23,42,0.08);border:1px solid rgba(148,163,184,0.22);">
            <h1 style="margin:0;line-height:0.92;font-size:2.55rem;font-weight:800;color:#0f172a;letter-spacing:0;">
              <span style="display:block;color:#0f766e;">E-Miu</span>
              <span style="display:block;font-size:2.1rem;color:#1e293b;">Advanced EV Station Monitoring System</span>
            </h1>
          </div>
          <p style="margin:0.7rem 0 0 0.1rem;font-size:1.05rem;color:#475569;">
            Live charger visibility, smart queue tracking, and phone-first session monitoring in one sleek control room.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_live_update_hint()
    render_home_live_panel(query_optional_int("station_id"))


@st.fragment(run_every="5s")
def render_admin_live_panel() -> None:
    with get_session() as db:
        stations = db.scalars(
            select(Station)
            .options(selectinload(Station.booths))
            .order_by(Station.name)
        ).all()
        st.subheader("Station Booth")
        for station in stations:
            with st.expander(f"{station.name} ({len(station.booths)} booths)", expanded=False):
                station_booths = sorted(station.booths, key=lambda booth: booth.name)
                qr_cols = st.columns(min(max(len(station_booths), 1), 3))
                for index, booth in enumerate(station_booths):
                    booth_url = build_booth_url(booth.code)
                    with qr_cols[index % len(qr_cols)]:
                        st.markdown(f"**{booth.name}**")
                        st.markdown(status_badge(booth.status.value), unsafe_allow_html=True)
                        st.image(make_qr_image(booth_url), width=110)
                        st.caption(booth.code)
                        action_col1, action_col2 = st.columns(2)
                        if action_col1.button("Mark free", key=f"free_{booth.id}"):
                            _, message = reset_booth(db, booth.id)
                            st.success(message)
                            st.rerun()
                        if action_col2.button(
                            "Assign queue",
                            key=f"assign_{booth.id}",
                            disabled=booth.status != BoothStatus.FREE,
                        ):
                            ok, message = assign_next_waiting_driver(db, booth.id)
                            st.success(message) if ok else st.warning(message)
                            st.rerun()


def admin_dashboard_page() -> None:
    st.title("Admin Dashboard")
    st.info(
        f"For phone testing on the same hotspot/network, open or scan links that use this laptop IP: "
        f"`{get_local_ip()}:8501`"
    )

    with get_session() as db:
        stations = db.scalars(select(Station).order_by(Station.name)).all()

        with st.expander("Create station", expanded=False):
            with st.form("create_station"):
                name = st.text_input("Station name", value="New EV Station")
                address = st.text_input("Address", value="Station address")
                latitude = st.number_input("Latitude", value=28.6139, format="%.6f")
                longitude = st.number_input("Longitude", value=77.2090, format="%.6f")
                radius = st.number_input("Station radius in meters", min_value=10.0, value=120.0)
                if st.form_submit_button("Create station"):
                    try:
                        create_station(db, name, address, latitude, longitude, radius)
                        st.success("Station created.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not create station: {exc}")

        if not stations:
            st.warning("Create a station first.")
            return

        with st.expander("Create charging booth", expanded=True):
            with st.form("create_booth"):
                station_map = {station.name: station for station in stations}
                station_name = st.selectbox("Station", list(station_map.keys()))
                booth_name = st.text_input("Booth name", value="Booth D")
                code = st.text_input("Booth QR/code", value="BOOTH-D")
                selected_station = station_map[station_name]
                latitude = st.number_input(
                    "Booth latitude",
                    value=float(selected_station.latitude),
                    format="%.6f",
                    key="booth_lat",
                )
                longitude = st.number_input(
                    "Booth longitude",
                    value=float(selected_station.longitude),
                    format="%.6f",
                    key="booth_lon",
                )
                radius = st.number_input("Booth radius in meters", min_value=5.0, value=50.0)
                if st.form_submit_button("Create booth"):
                    try:
                        create_booth(
                            db,
                            selected_station.id,
                            booth_name,
                            code,
                            latitude,
                            longitude,
                            radius,
                        )
                        st.success("Booth created.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not create booth: {exc}")
    render_live_update_hint("Live booth data refreshes every 5 seconds. Open forms stay in place.")
    render_admin_live_panel()


@st.fragment(run_every="5s")
def render_driver_live_panel(pending_payment_session_id: int | None) -> None:
    with get_session() as db:
        st.subheader("Active Sessions")
        sessions = db.scalars(
            select(ChargingSession)
            .where(ChargingSession.status.in_([SessionStatus.OCCUPIED, SessionStatus.CHARGING]))
            .order_by(ChargingSession.started_at.desc())
        ).all()
        if not sessions:
            st.info("No active charging sessions.")
        for session in sessions:
            col1, col2 = st.columns([3, 1])
            col1.write(
                f"Session #{session.id}: {session.driver.name} at {session.booth.name} "
                f"({session.current_power_kw:.1f} kW, finish {format_datetime(session.estimated_finish_at)} UTC)"
            )
            if col2.button("Finish + pay", key=f"finish_{session.id}"):
                st.session_state["pending_payment_session_id"] = session.id
                st.session_state["finish_after_payment_session_id"] = session.id
                st.rerun()

        if pending_payment_session_id is not None:
            pending_session = db.get(ChargingSession, pending_payment_session_id)
            if (
                pending_session is not None
                and pending_session.id not in st.session_state["payment_records"]
                and st.session_state.get("finish_after_payment_session_id") == pending_session.id
            ):
                st.subheader("Payment Required Before Session Finish")
                st.write(
                    f"Complete payment for Session #{pending_session.id} to mark charging as finished."
                )
                render_payment_panel(pending_session)

        unpaid_finished_sessions = db.scalars(
            select(ChargingSession)
            .where(ChargingSession.status == SessionStatus.FINISHED)
            .order_by(ChargingSession.finished_at.desc())
        ).all()
        pending_sessions = [
            session
            for session in unpaid_finished_sessions
            if session.id not in st.session_state["payment_records"]
        ]
        if pending_sessions:
            st.subheader("Finished Sessions Waiting for Demo Payment")
            for session in pending_sessions[:3]:
                with st.expander(
                    f"Session #{session.id} | {session.driver.name}",
                    expanded=session.id == pending_payment_session_id,
                ):
                    st.write(
                        f"{session.booth.station.name} | {session.booth.name} | "
                        f"Finished at {format_datetime(session.finished_at)} UTC"
                    )
                    render_payment_panel(session)


def driver_check_in_page() -> None:
    st.title("Driver Check-In")

    with get_session() as db:
        booths = db.scalars(select(Booth).order_by(Booth.name)).all()
        if not booths:
            st.warning("No booths are configured yet.")
            return

        demo_booth = booths[0]
        booth_code_from_query = query_value("booth").upper()
        mobile_mode = query_value("mobile") == "1"
        selected_from_query = next(
            (booth for booth in booths if booth.code == booth_code_from_query),
            demo_booth,
        )

        if mobile_mode:
            st.info("QR scan detected. This page is ready for phone check-in.")

        driver_name = st.text_input("Driver name", value="Demo Driver")
        queue_entry = get_driver_queue_entry(db, driver_name)
        default_booth = selected_from_query
        if queue_entry is not None:
            st.info(f"{driver_name.strip() or 'Driver'}, you are currently still in the queue.")

        render_geolocation_helper(default_booth.latitude, default_booth.longitude, auto_apply=mobile_mode)

        booth_options = {f"{booth.name} ({booth.code})": booth for booth in booths}
        default_index = list(booth_options.values()).index(default_booth)
        booth_label = st.selectbox(
            "Charging booth",
            list(booth_options.keys()),
            index=default_index,
            disabled=mobile_mode and booth_code_from_query != "",
        )
        selected_booth = booth_options[booth_label]
        st.caption(
            "For phone use, the QR page tries to fill your coordinates automatically. "
            "If the browser blocks GPS, use the manual fallback."
        )

        mobile_latitude = query_optional_float("lat")
        mobile_longitude = query_optional_float("lon")
        show_manual_location = (not mobile_mode) or mobile_latitude is None or mobile_longitude is None

        if mobile_mode and mobile_latitude is not None and mobile_longitude is not None:
            driver_latitude = mobile_latitude
            driver_longitude = mobile_longitude
            st.success(
                f"Phone location detected and applied: {driver_latitude:.6f}, {driver_longitude:.6f}"
            )
        else:
            driver_latitude = float(selected_booth.latitude)
            driver_longitude = float(selected_booth.longitude)

        if show_manual_location:
            with st.expander("Manual location fallback", expanded=mobile_mode):
                driver_latitude = st.number_input(
                    "Your latitude",
                    value=query_float("lat", float(selected_booth.latitude)),
                    format="%.6f",
                )
                driver_longitude = st.number_input(
                    "Your longitude",
                    value=query_float("lon", float(selected_booth.longitude)),
                    format="%.6f",
                )

        if mobile_mode:
            car_model = st.radio("Car model", list(VEHICLE_MODELS.keys()), index=0)
        else:
            car_model = st.selectbox("Car model", list(VEHICLE_MODELS.keys()))
        vehicle = VEHICLE_MODELS[car_model]
        start_battery = st.slider("Current battery %", 1, 95, 25)
        target_battery = st.slider("Target battery %", start_battery + 1, 100, 80)

        station_power_default = 30.0
        if mobile_mode:
            station_power = station_power_default
            st.slider(
                "Station charging power (kW)",
                3.0,
                150.0,
                station_power_default,
                disabled=True,
            )
        else:
            station_power = st.slider("Station charging power (kW)", 3.0, 150.0, station_power_default)
        effective_power = min(station_power, vehicle["max_power_kw"])
        estimated_minutes = estimate_minutes(
            start_battery,
            target_battery,
            effective_power,
            assumed_battery_kwh=vehicle["battery_kwh"],
        )

        info1, info2, info3 = st.columns(3)
        info1.metric("Battery Size", f"{vehicle['battery_kwh']} kWh")
        info2.metric("Car Max Intake", f"{vehicle['max_power_kw']} kW")
        info3.metric("Estimated Time", f"{estimated_minutes} min")
        st.caption(
            f"Effective charging power used for estimation: {effective_power:.1f} kW. "
            f"This updates live when you change car model or battery percentages."
        )

        pending_payment_session_id = st.session_state.get("pending_payment_session_id")

        submit_disabled = mobile_mode and mobile_latitude is None and not show_manual_location
        submitted = st.button("Check in and start charging", type="primary", disabled=submit_disabled)
        if submitted:
            ok, message, session = attempt_check_in(
                db,
                selected_booth.code,
                driver_name,
                driver_latitude,
                driver_longitude,
                start_battery,
                target_battery,
                effective_power,
            )
            if ok:
                st.success(message)
                st.info(
                    f"Session #{session.id} started. Estimated finish: "
                    f"{format_datetime(session.estimated_finish_at)} UTC."
                )
                st.rerun()
            else:
                st.error(message)

    render_live_update_hint("Session updates refresh every 5 seconds, even when another phone starts charging.")
    render_driver_live_panel(pending_payment_session_id)


@st.fragment(run_every="5s")
def render_queue_live_panel() -> None:
    with get_session() as db:
        entries = db.scalars(select(QueueEntry).order_by(QueueEntry.requested_at.asc())).all()
        st.subheader("Current Queue")
        if not entries:
            st.info("Queue is empty.")
            return

        waiting_entries = [entry for entry in entries if entry.status == QueueStatus.WAITING]
        waiting_positions = {entry.id: index + 1 for index, entry in enumerate(waiting_entries)}
        st.dataframe(
            [
                {
                    "Driver": entry.driver.name,
                    "Station": entry.station.name,
                    "Status": entry.status.value,
                    "Queue Position": waiting_positions.get(entry.id, "-"),
                    "Requested": format_datetime(entry.requested_at),
                }
                for entry in entries
                if entry.status == QueueStatus.WAITING
            ],
            use_container_width=True,
            hide_index=True,
        )


def queue_page() -> None:
    st.title("Queue")

    with get_session() as db:
        stations = db.scalars(select(Station).order_by(Station.name)).all()
        if not stations:
            st.warning("Create a station first.")
            return

        st.write(
            "Join the queue with your driver name. When a booth becomes free, the first driver "
            "in line is removed from the queue automatically."
        )

        lookup_name = st.text_input("Check my queue status", value="Queued Driver")
        driver_status = get_driver_queue_entry(db, lookup_name)
        if driver_status is not None:
            st.info(f"{lookup_name.strip() or 'Driver'}: you are still waiting in line.")

        with st.form("join_queue"):
            station_map = {station.name: station for station in stations}
            station_name = st.selectbox("Station", list(station_map.keys()))
            driver_name = st.text_input("Driver name", value="Queued Driver")
            if st.form_submit_button("Join queue"):
                entry = join_queue(db, station_map[station_name].id, driver_name)
                st.success(f"{entry.driver.name} is in the queue for {entry.station.name}.")
                st.rerun()
    render_live_update_hint("Queue status refreshes every 5 seconds while your form entries stay intact.")
    render_queue_live_panel()


@st.fragment(run_every="5s")
def render_map_live_panel(
    user_latitude: float,
    user_longitude: float,
    selected_station_id: int | None,
) -> None:
    with get_session() as db:
        stations = db.scalars(
            select(Station)
            .options(selectinload(Station.booths))
            .order_by(Station.name)
        ).all()
        if not stations:
            st.warning("No stations are configured yet.")
            return

        station_cards = [
            station_live_status(
                db,
                station,
                user_latitude=user_latitude,
                user_longitude=user_longitude,
            )
            for station in stations
        ]
        station_cards.sort(
            key=lambda station: (
                station["distance_meters"]
                if station["distance_meters"] is not None
                else float("inf")
            )
        )

        selected_station_id = (
            selected_station_id
            or st.session_state.get(SELECTED_STATION_STATE_KEY)
            or int(station_cards[0]["station_id"])
        )
        build_station_map(
            station_cards,
            selected_station_id=selected_station_id,
            user_latitude=user_latitude,
            user_longitude=user_longitude,
        )

        station_options = {
            f"{station['station_name']} ({station['distance_meters'] / 1000:.2f} km)": station
            for station in station_cards
            if station["distance_meters"] is not None
        }
        if not station_options:
            station_options = {station["station_name"]: station for station in station_cards}

        option_values = list(station_options.values())
        selected_index = max(
            0,
            next(
                (
                    idx
                    for idx, station in enumerate(option_values)
                    if station["station_id"] == selected_station_id
                ),
                0,
            ),
        )
        selected_label = st.selectbox(
            "Nearest stations",
            list(station_options.keys()),
            index=selected_index,
            key=MAP_STATION_SELECTOR_KEY,
        )
        selected_station_snapshot = station_options[selected_label]
        st.session_state[SELECTED_STATION_STATE_KEY] = int(
            selected_station_snapshot["station_id"]
        )
        if int(selected_station_snapshot["station_id"]) != selected_station_id:
            st.query_params.update(page="map", station_id=str(selected_station_snapshot["station_id"]))
            st.rerun()
        selected_station = next(
            station for station in stations if station.id == selected_station_snapshot["station_id"]
        )

        overview1, overview2, overview3, overview4 = st.columns(4)
        overview1.metric("Free", int(selected_station_snapshot["free_count"]))
        overview2.metric("Charging", int(selected_station_snapshot["charging_count"]))
        overview3.metric("Queue", int(selected_station_snapshot["queue_count"]))
        overview4.metric("Total Booths", int(selected_station_snapshot["total_booths"]))
        st.caption(
            f"{selected_station_snapshot['station_name']} | {selected_station_snapshot['address']}"
        )

        booth_rows = [
            {
                "Booth": booth.name,
                "Code": booth.code,
                "Status": booth.status.value,
                "Radius (m)": booth.radius_meters,
            }
            for booth in sorted(selected_station.booths, key=lambda booth: booth.name)
        ]
        st.dataframe(booth_rows, use_container_width=True, hide_index=True)

        waiting_entries = db.scalars(
            select(QueueEntry)
            .where(
                QueueEntry.station_id == selected_station.id,
                QueueEntry.status == QueueStatus.WAITING,
            )
            .order_by(QueueEntry.requested_at.asc())
        ).all()
        if waiting_entries:
            st.write("Drivers currently in line")
            st.dataframe(
                [
                    {
                        "Driver": entry.driver.name,
                        "Requested": format_datetime(entry.requested_at),
                    }
                    for entry in waiting_entries
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No drivers are waiting at this station right now.")


def map_page() -> None:
    st.title("Maps")
    st.write(
        "Use the live map to find the nearest charging station, then click a marker to inspect "
        "free booths, active charging spots, and the current queue."
    )

    user_latitude = query_optional_float("lat")
    user_longitude = query_optional_float("lon")

    if user_latitude is None or user_longitude is None:
        user_latitude = 28.6139
        user_longitude = 77.2090
        st.info("Using demo location near central Delhi. Use the GPS helper below for nearest stations.")
    else:
        st.success(
            f"Using your map location: {user_latitude:.6f}, {user_longitude:.6f}"
        )

    render_geolocation_helper(user_latitude, user_longitude, auto_apply=True)
    render_live_update_hint("Map, station status, and queue counts refresh every 5 seconds.")
    render_map_live_panel(user_latitude, user_longitude, query_optional_int("station_id"))


def reports_page() -> None:
    st.title("Reports")

    with get_session() as db:
        sessions = db.scalars(select(ChargingSession).order_by(ChargingSession.started_at.desc())).all()
        rows = [
            {
                "Session ID": session.id,
                "Driver": session.driver.name,
                "Booth": session.booth.name,
                "Station": session.booth.station.name,
                "Status": session.status.value,
                "Distance (m)": round(session.distance_meters, 1),
                "Start Battery": session.start_battery_percent,
                "Target Battery": session.target_battery_percent,
                "Power kW": session.current_power_kw,
                "Started": format_datetime(session.started_at),
                "Estimated Finish": format_datetime(session.estimated_finish_at),
                "Finished": format_datetime(session.finished_at),
                "Payment": st.session_state["payment_records"].get(session.id, {}).get("label", "Pending"),
            }
            for session in sessions
        ]

        completed = [session for session in sessions if session.finished_at is not None]
        average_minutes = 0
        if completed:
            durations = [
                (session.finished_at - session.started_at).total_seconds() / 60
                for session in completed
            ]
            average_minutes = round(sum(durations) / len(durations), 1)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Sessions", len(sessions))
        col2.metric("Completed", len(completed))
        col3.metric("Avg Duration", f"{average_minutes} min")

        st.dataframe(rows, use_container_width=True, hide_index=True)
        if rows:
            csv_buffer = io.StringIO()
            writer = csv.DictWriter(csv_buffer, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
            st.download_button(
                "Download CSV report",
                data=csv_buffer.getvalue(),
                file_name="ev_charging_sessions.csv",
                mime="text/csv",
            )


def talk_to_miu_page() -> None:
    st.title("Talk to Miu")
    miu_avatar = load_miu_avatar()
    if miu_avatar is not None:
        left, right = st.columns([1, 2.4])
        with left:
            st.image(miu_avatar, width=132)
        with right:
            st.markdown("### Miu is the mascot of E-Miu")
            st.write(
                "This space is reserved for the future AI assistant experience. "
                "For now, Miu is here as the face of the platform and a placeholder for the upcoming smart helper."
            )
    else:
        st.info("Miu's avatar is temporarily unavailable, but the assistant page placeholder is ready.")

    st.caption("Planned next step: AI help for charger discovery, queue guidance, and payment support.")
    preview_col, chat_col = st.columns([1, 1.4])
    with preview_col:
        render_miu_preview()
        st.markdown(
            """
            **What Miu can preview**

            - Station and map guidance
            - Queue and wait-flow help
            - Charging session steps
            - Demo payment help
            """
        )
    with chat_col:
        render_miu_chat()


def about_page() -> None:
    st.title("About")
    st.write(
        "E-Miu is a compact EV charging operations demo built to monitor stations, "
        "track live booth availability, manage driver queues, support phone-based session "
        "check-in, and preview the future assistant-led charging experience."
    )
    st.markdown(
        """
        **What works in this MVP**

        - Station and booth setup
        - Booth geofence radius checks
        - Driver check-in with browser GPS helper
        - Simulated charging sessions
        - Queue management
        - Session reports and CSV export

        **Future upgrades**

        - Real charger data through OCPP or vendor APIs
        - Real authentication
        - QR code stickers for booths
        - SMS or WhatsApp queue notifications
        - Cloud deployment with PostgreSQL
        """
    )
    st.markdown(f"GitHub repository: [{REPO_URL}]({REPO_URL})")


def main() -> None:
    bootstrap()
    init_demo_state()
    mobile_mode = query_value("mobile") == "1"
    st.sidebar.title("Navigation")
    page_options = [
        "Home",
        "Maps",
        "Driver Check-In",
        "Queue",
        "Reports",
        "Talk to Miu",
        "About Project",
    ]
    if not mobile_mode:
        page_options.insert(1, "Admin Dashboard")
    default_page = query_value("page")
    default_index = 0
    if default_page == "map":
        default_index = page_options.index("Maps")
    elif default_page == "driver" or query_value("booth"):
        default_index = page_options.index("Driver Check-In")
    page = st.sidebar.radio(
        "Go to",
        page_options,
        index=default_index,
    )
    render_miu_sidebar_card()

    if st.sidebar.button("Refresh data"):
        st.rerun()

    if page == "Home":
        home_page()
    elif page == "Maps":
        map_page()
    elif page == "Admin Dashboard":
        admin_dashboard_page()
    elif page == "Driver Check-In":
        driver_check_in_page()
    elif page == "Queue":
        queue_page()
    elif page == "Reports":
        reports_page()
    elif page == "Talk to Miu":
        talk_to_miu_page()
    else:
        about_page()


if __name__ == "__main__":
    main()
