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

## To be updated in future 

- Faster QR-first phone testing workflow
- Better local-network launch flow for laptop + phone demos
- More compact admin QR operations
- Expanded mobile check-in refinements
- E-Miu branded interface polish
- Nearby station map experience
- Demo payment-before-finish session flow
- Miu ai assistant preview

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

## Optional Miu AI Assistant

Miu works in preview mode without any API key. To test real LLM replies locally, create your own OpenRouter API key and add it to a private local Streamlit secrets file.

1. Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml`.
2. Paste your own key into `.streamlit/secrets.toml`.
3. Paste the OpenRouter model ID you want to use.

```toml
OPENROUTER_API_KEY = "paste-your-own-openrouter-key-here"
OPENROUTER_MODEL = "paste-your-own-llm-model-here"
```

If either value is missing or still a placeholder, Miu falls back to preview mode. `secrets.toml` is ignored by Git, so your real API key should stay local. Do not commit real API keys, screenshots containing keys, or terminal output that prints keys. If a key is exposed, revoke it in OpenRouter and create a new one.

For deployed apps, add the same values through your hosting provider's secret or environment-variable settings instead of putting them in source code.

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

https://github.com/souravsarkar-Lv999/E-Miu_Advanced_EV_Station_Monitoring_System-Experimental-

## License

MIT License.
