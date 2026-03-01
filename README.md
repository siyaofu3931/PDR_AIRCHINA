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

## Run on your iPhone

The app **must** be loaded over **HTTPS** for motion/orientation to work on iOS. Two ways to do it:

### Option 1: GitHub Pages (easiest if the repo is on GitHub)

1. Push your project to GitHub (e.g. `simon-jian/pedestrian_dead_reckoning`).
2. On GitHub: open the repo → **Settings** → **Pages**.
3. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
4. Choose branch **main** (or **master**) and folder **/ (root)**. Save.
5. After a minute, your site is at:  
   **https://simon-jian.github.io/pedestrian_dead_reckoning/**  
   (Use your actual username and repo name.)
6. On your iPhone, open **Safari**, go to that URL, tap **Start**, and allow motion & orientation when prompted.

### Option 2a: ngrok tunnel (quick local test)

Use this when the project is only on your computer. Your iPhone and computer must be on the same Wi‑Fi.

**One-time setup:** ngrok requires a free account and authtoken.
1. Sign up: [dashboard.ngrok.com/signup](https://dashboard.ngrok.com/signup)
2. Get your authtoken: [dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
3. Install it: `ngrok config add-authtoken YOUR_TOKEN`

Then each time:

1. **Terminal 1** – serve the project and leave it running:
   ```bash
   cd ~/pedestrian_dead_reckoning
   python3 -m http.server 8000
   ```

2. **Terminal 2** – start the tunnel (leave it running):
   ```bash
   ngrok http 8000
   ```

3. In the ngrok terminal, copy the **https** URL from the **Forwarding** line (e.g. `https://abc123.ngrok-free.app`).

4. On your iPhone (same Wi‑Fi), open **Safari**, paste that URL. Tap **Start**, then **Allow** when iOS asks for motion & orientation access.

### Option 2b: localtunnel (no signup)

If you don’t want to create an ngrok account, use localtunnel. You need Node.js/npm.

1. **Terminal 1** – serve the project (same as above):
   ```bash
   cd ~/pedestrian_dead_reckoning
   python3 -m http.server 8000
   ```

2. **Terminal 2** – start the tunnel (leave it running):
   ```bash
   npx localtunnel --port 8000
   ```

3. Copy the URL it prints (e.g. `https://something.loca.lt`). If your iPhone shows a **“Tunnel Password”** or “Click to continue” page: the password is your **computer’s public IP**. Find it by running on your computer: `curl -4 ifconfig.me` (or open [loca.lt/mytunnelpassword](https://loca.lt/mytunnelpassword) in a browser on the same network). Enter that IP as the password, then you’ll reach the app.

4. On your iPhone, open **Safari**, paste that URL (and enter the tunnel password if asked). Tap **Start**, then **Allow** when iOS asks for motion & orientation access.

### Option 3: Other hosts with HTTPS

Upload the project (e.g. just `index.html` and `README.md` if you like) to any static host with HTTPS (Netlify, Vercel, your own server with SSL). Open that URL on your iPhone in Safari.

---

## Serving over HTTPS (reference)

Sensors only work in a **secure context** (HTTPS or `localhost`). Summary of options:

### Option A: Local HTTPS with a tunnel (good for testing)

Use a tunnel (ngrok, Cloudflare Tunnel, localtunnel) to expose your local server over HTTPS. See **Option 2** above for ngrok steps.

### Option B: Deploy to a host with HTTPS

See **Option 1** (GitHub Pages) or **Option 3** (Netlify, Vercel, etc.) above.

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
