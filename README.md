# EV Charging Station Monitoring

A working Streamlit MVP that adapts a geofencing attendance system into an EV charging station monitoring system.

The original research paper logic is:

- Lecturer creates a geofence around a lecture hall.
- Student checks in from inside the geofence.
- Backend records attendance.
- Dashboard shows attendance status.

This project changes the domain:

- Station admin creates geofences around EV charging booths.
- EV driver checks in from inside the booth radius.
- Backend records a charging session.
- Dashboard shows booth status, active charging, queue, and reports.

## Features

- Admin dashboard for station and booth setup
- Booth code support, similar to QR/code workflow
- Browser GPS helper using JavaScript Geolocation API
- Haversine geofence validation in Python
- SQLite database with SQLAlchemy models
- Simulated charging power, battery target, and finish time
- Booth states: `free`, `occupied`, `charging`, `finished`
- Queue management when booths are busy
- Reports with CSV download
- Demo data that works immediately

## Tech Stack

- Python
- Streamlit
- JavaScript browser geolocation
- SQLite
- SQLAlchemy
- Pytest

## How To Run In VS Code

### Fastest repeat command

From the project folder, you can run everything with this single command:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_experiment.ps1
```

This creates `.venv` if needed, installs requirements, and starts Streamlit for laptop + phone testing.

1. Open VS Code.
2. Open this project folder:

   ```text
   ev-charging-station-monitoring
   ```

3. Open the VS Code terminal.
4. Create a virtual environment:

   ```powershell
   python -m venv .venv
   ```

5. Activate it:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

6. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

7. Start the app:

   ```powershell
   streamlit run app.py
   ```

8. Open the local URL shown in the terminal, usually:

   ```text
   http://localhost:8501
   ```

## Demo Flow

1. Open **Home** to see the default demo booths.
2. Open **Driver Check-In**.
3. Select `Booth A`.
4. Keep the default latitude and longitude for a successful demo check-in.
5. Click **Check in and start charging**.
6. Open **Admin Dashboard** or **Home** to see the booth become `charging`.
7. Finish the session from **Driver Check-In**.
8. Mark the booth free from **Admin Dashboard**.

To test geofence rejection, change the driver latitude/longitude far away from the booth and submit again.

## Project Structure

```text
ev-charging-station-monitoring/
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

Run:

```powershell
pytest
```

The tests cover:

- same-location geofence success
- far-location geofence rejection
- Haversine distance sanity check
- check-in accepting a driver inside the booth radius
- check-in rejecting a driver outside the booth radius
- booth reset after a charging session

## GitHub Upload With GitHub Desktop

Since this project is meant to be open source, the easiest beginner path is GitHub Desktop:

1. Open GitHub Desktop.
2. Choose **File > Add local repository**.
3. Select the `ev-charging-station-monitoring` folder.
4. If GitHub Desktop asks to create a repository, allow it.
5. Write a commit message like:

   ```text
   Initial EV charging monitoring MVP
   ```

6. Click **Commit to main**.
7. Click **Publish repository** or push to your existing `ev monitoring` repository.
8. Keep it public if you want it open source.

## Future Scope

- Connect to real charger hardware through OCPP or vendor APIs.
- Generate real QR codes for each booth.
- Add login with password hashing.
- Add PostgreSQL for cloud deployment.
- Add SMS, email, or WhatsApp notifications for queue updates.
- Deploy on Streamlit Community Cloud, Render, or Azure App Service.

## License

MIT License. You can use, modify, and publish this project as open source.
