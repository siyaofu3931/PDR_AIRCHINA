# PDR Sensor Recorder

A single-page web app that records **IMU** (accelerometer), **gyroscope**, **magnetometer** (orientation/compass), and **step count** on your phone when you open the page. Works on iPhone (Safari) and Android (Chrome).

## What it records

| Sensor | Source | Data |
|--------|--------|------|
| **IMU / Accelerometer** | `DeviceMotionEvent.acceleration` & `accelerationIncludingGravity` | x, y, z (m/s²) |
| **Gyroscope** | `DeviceMotionEvent.rotationRate` | α, β, γ (deg/s) |
| **Magnetometer / Compass** | `DeviceOrientationEvent` | α (heading), β, γ |
| **Steps** | Derived from accelerometer (peak detection) | Step count |

Recorded samples are timestamped and can be downloaded as JSON.

## How to use

1. **Serve the page over HTTPS** (required for motion/orientation on iOS and many Android browsers).
2. Open the page on your phone (iPhone or Android).
3. Tap **Start** — on iOS you’ll be asked to allow motion & orientation access.
4. Walk around; the page shows live values and step count.
5. Tap **Stop** when done.
6. Tap **Download JSON** to save the recorded session (meta + all samples).

## Serving over HTTPS (for phone access)

Sensors only work in a **secure context** (HTTPS or `localhost`). To use the page on your phone:

### Option A: Local HTTPS with a tunnel (good for testing)

1. Serve the folder with any static server over HTTPS, or use a tunnel to your local HTTP server:
   - **ngrok**: `ngrok http 8000` then open the `https://…` URL on your phone.
   - **Cloudflare Tunnel**, **localtunnel**, etc. work similarly.

2. Example with Python and ngrok:
   ```bash
   cd pedestrian_dead_reckoning_testing_project
   python3 -m http.server 8000
   ```
   In another terminal: `ngrok http 8000`, then open the HTTPS URL from ngrok on your phone.

### Option B: Deploy to a host with HTTPS

Upload the project (e.g. only `index.html`) to any static host with HTTPS (GitHub Pages, Netlify, Vercel, your own server with SSL). Open that URL on your phone.

### Option C: Local only (Android)

On Android, Chrome may allow sensor access over HTTP in some cases; prefer HTTPS for reliable behavior.

## File layout

- `index.html` — Single-page app: UI, permission handling, recording, step detection, and JSON download.

## JSON export format

The downloaded file contains:

- **meta**: `recordedAt`, `durationMs`, `stepCount`, `sampleCount`
- **samples**: Array of objects, one per event, with:
  - `ts` — ISO timestamp
  - `t` — `performance.now()` (relative time)
  - `acceleration` — linear acceleration (if available)
  - `accelerationIncludingGravity` — x, y, z
  - `rotationRate` — gyro α, β, γ
  - `orientation` — alpha (heading), beta, gamma, absolute
  - `steps` — step count at that time

## Push to GitHub

The project is already a git repo with files staged. To push to GitHub:

1. **Create a new repository on GitHub**  
   Go to [github.com/new](https://github.com/new), choose a name (e.g. `pedestrian_dead_reckoning_testing_project`), leave “Add a README” unchecked, then Create repository.

2. **Commit and push from your machine** (run in a terminal):

   ```bash
   cd /home/simon/pedestrian_dead_reckoning_testing_project

   git commit -m "Initial commit: PDR sensor recorder"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin main
   ```

   Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your GitHub username and the repo name you created. If you use SSH: `git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git`.

3. If GitHub asks for authentication, use a [Personal Access Token](https://github.com/settings/tokens) (HTTPS) or ensure your SSH key is added to your GitHub account.

## Notes

- **iOS**: Uses `DeviceMotionEvent.requestPermission()` and `DeviceOrientationEvent.requestPermission()`; the **Start** button must be tapped by the user.
- **Steps**: Computed from accelerometer magnitude (threshold + min interval); tune in code if needed for your use case.
- **Orientation alpha**: On devices with a magnetometer, alpha is the compass heading (0–360°).
