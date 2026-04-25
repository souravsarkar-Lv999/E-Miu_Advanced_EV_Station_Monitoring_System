# E-Miu_Advanced_EV_Station_Monitoring_System

E-Miu is a Streamlit-based EV charging operations demo that turns geofencing ideas into a compact station monitoring system for admins and drivers.

## Main Branch Features

- Station and booth setup from the admin dashboard
- Geofence-based driver check-in at booth level
- GPS-assisted browser location helper
- Live booth states for `free`, `occupied`, `charging`, and `finished`
- Queue handling for busy stations
- Charging session simulation with battery and power inputs
- Reports with CSV export
- Demo seed data for instant testing

## Upcoming In `experiment`

- Faster QR-first phone testing workflow
- Better local-network launch flow for laptop + phone demos
- More compact admin QR operations
- Expanded mobile check-in refinements

## Upcoming In `experiment-1`

- E-Miu branded interface polish
- Nearby station map experience
- Demo payment-before-finish session flow
- Live-refresh monitoring panels
- Miu mascot assistant preview

## Tech Stack

- Python
- Streamlit
- SQLite
- SQLAlchemy
- JavaScript geolocation helpers
- Pytest

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`.

If the branch includes `run_experiment.ps1`, you can also use:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_experiment.ps1
```

## Demo Flow

1. Open `Home` to review booth or station status.
2. Open `Driver Check-In`.
3. Select a booth and keep the default nearby coordinates for a successful demo.
4. Start a charging session.
5. Watch the status update from the dashboard views.
6. Complete the session flow and review reports.

## Project Structure

```text
E-Miu_Advanced_EV_Station_Monitoring_System/
  app.py
  requirements.txt
  README.md
  LICENSE
  ev_monitoring/
    database.py
    geofence.py
    models.py
    seed.py
    services.py
  tests/
    test_geofence.py
    test_services.py
```

## Tests

```powershell
pytest
```

## Repository

[https://github.com/souravsarkar-Lv999/E-Miu_Advanced_EV_Station_Monitoring_System](https://github.com/souravsarkar-Lv999/E-Miu_Advanced_EV_Station_Monitoring_System)

## License

MIT License.
