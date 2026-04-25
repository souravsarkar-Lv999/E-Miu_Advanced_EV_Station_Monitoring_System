from __future__ import annotations

import csv
import io
import socket
from datetime import datetime
from urllib.parse import urlencode

import qrcode
import streamlit as st
import streamlit.components.v1 as components
from sqlalchemy import select

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
from ev_monitoring.seed import seed_demo_data
from ev_monitoring.services import (
    assign_next_waiting_driver,
    attempt_check_in,
    create_booth,
    create_station,
    dashboard_summary,
    estimate_minutes,
    finish_session,
    get_driver_queue_entry,
    join_queue,
    reset_booth,
)
from ev_monitoring.vehicles import VEHICLE_MODELS


st.set_page_config(
    page_title="EV Charging Station Monitoring",
    page_icon="EV",
    layout="wide",
)


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


def build_booth_url(booth_code: str) -> str:
    host = get_local_ip()
    query = urlencode(
        {
            "page": "driver",
            "booth": booth_code,
            "mobile": "1",
        }
    )
    return f"http://{host}:8501/?{query}"


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


def home_page() -> None:
    st.title("EV Charging Station Monitoring")
    st.write(
        "A working MVP that adapts geofencing attendance logic into EV booth "
        "monitoring. Admins define charger geofences. Drivers check in from "
        "inside the radius. The dashboard tracks booth and queue status."
    )

    with get_session() as db:
        summary = dashboard_summary(db)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Booths", summary["total_booths"])
        col2.metric("Active Sessions", summary["active_sessions"])
        col3.metric("Waiting Drivers", summary["waiting_drivers"])
        col4.metric("Completed Sessions", summary["completed_sessions"])

        st.subheader("Booth Status")
        booths = db.scalars(select(Booth).order_by(Booth.name)).all()
        if not booths:
            st.info("No booths yet. Create one from Admin Dashboard.")
        else:
            cols = st.columns(min(len(booths), 3))
            for index, booth in enumerate(booths):
                with cols[index % len(cols)]:
                    st.markdown(f"### {booth.name}")
                    st.markdown(status_badge(booth.status.value), unsafe_allow_html=True)
                    st.write(f"Code: `{booth.code}`")
                    st.caption(
                        f"Lat {booth.latitude:.6f}, Lon {booth.longitude:.6f}, "
                        f"Radius {booth.radius_meters:.0f} m"
                    )
                    with st.expander("Phone QR"):
                        booth_url = build_booth_url(booth.code)
                        st.image(make_qr_image(booth_url), caption=f"Scan for {booth.name}", width=180)
                        st.code(booth_url, language=None)


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

        st.subheader("Live Booth Table")
        booths = db.scalars(select(Booth).order_by(Booth.name)).all()
        st.dataframe(
            [
                {
                    "Booth": booth.name,
                    "Code": booth.code,
                    "Station": booth.station.name,
                    "Status": booth.status.value,
                    "Latitude": booth.latitude,
                    "Longitude": booth.longitude,
                    "Radius (m)": booth.radius_meters,
                }
                for booth in booths
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Booth Controls")
        for booth in booths:
            col1, col2, col3 = st.columns([2, 1, 1])
            col1.markdown(f"**{booth.name}** {status_badge(booth.status.value)}", unsafe_allow_html=True)
            if col2.button("Mark free", key=f"free_{booth.id}"):
                _, message = reset_booth(db, booth.id)
                st.success(message)
                st.rerun()
            if col3.button("Assign queue", key=f"assign_{booth.id}", disabled=booth.status != BoothStatus.FREE):
                ok, message = assign_next_waiting_driver(db, booth.id)
                st.success(message) if ok else st.warning(message)
                st.rerun()

        st.subheader("Booth QR Links")
        qr_cols = st.columns(3)
        for index, booth in enumerate(booths):
            booth_url = build_booth_url(booth.code)
            with qr_cols[index % 3]:
                st.markdown(f"**{booth.name}**")
                st.image(make_qr_image(booth_url), width=180)
                st.caption("Scan on iPhone or Android")
                st.code(booth_url, language=None)


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
            if col2.button("Finish session", key=f"finish_{session.id}"):
                finish_session(db, session.id)
                st.rerun()


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

        entries = db.scalars(select(QueueEntry).order_by(QueueEntry.requested_at.asc())).all()
        st.subheader("Current Queue")
        if not entries:
            st.info("Queue is empty.")
            return
        waiting_entries = [
            entry
            for entry in entries
            if entry.status == QueueStatus.WAITING
        ]
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


def about_page() -> None:
    st.title("About")
    st.write(
        "This project copies the research paper's geofencing attendance pattern "
        "and applies it to EV charging. Instead of students proving they are in "
        "a lecture hall, drivers prove they are near a charger booth."
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


def main() -> None:
    bootstrap()
    mobile_mode = query_value("mobile") == "1"
    st.sidebar.title("Navigation")
    page_options = [
        "Home",
        "Driver Check-In",
        "Queue",
        "Reports",
        "About Project",
    ]
    if not mobile_mode:
        page_options.insert(1, "Admin Dashboard")
    default_page = query_value("page")
    default_index = 0
    if default_page == "driver" or query_value("booth"):
        default_index = page_options.index("Driver Check-In")
    page = st.sidebar.radio(
        "Go to",
        page_options,
        index=default_index,
    )

    if st.sidebar.button("Refresh data"):
        st.rerun()

    if page == "Home":
        home_page()
    elif page == "Admin Dashboard":
        admin_dashboard_page()
    elif page == "Driver Check-In":
        driver_check_in_page()
    elif page == "Queue":
        queue_page()
    elif page == "Reports":
        reports_page()
    else:
        about_page()


if __name__ == "__main__":
    main()
