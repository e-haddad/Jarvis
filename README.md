# Iris Core

> Gesture-controlled smart home system — fully local computer vision pipeline on Raspberry Pi.

Iris lets you control smart home devices with hand gestures. No cloud dependency for detection — all computer vision runs locally on the Pi. Works with any Tuya-compatible smart plug or device.

---

## Demo

> Walk into a room → raise open hand, close fist, open hand → light toggles.

*(Demo video coming soon)*

---

## Features

- **Fully local gesture detection** — MediaPipe runs on-device, no data leaves your network
- **Real-time device control** — sub-second response via local LAN (tinytuya)
- **Web dashboard** — toggle devices and remap gestures from any browser on your network
- **No cloud subscription required** — works completely offline
- **Extensible gesture set** — add new gestures and actions via config

---

## Hardware Requirements

| Component | Specification |
|---|---|
| Single-board computer | Raspberry Pi 5 (8GB recommended) |
| OS | Raspberry Pi OS 64-bit (Bookworm) |
| Camera | Arducam Camera Module 3 Wide 120° (IMX708) |
| Cable | 500mm CSI-2 ribbon cable |
| Power supply | 5V 5A USB-C (CanaKit recommended) |
| Smart devices | Any Tuya-compatible smart plug |

---

## How It Works

```
Camera → MediaPipe (local) → Gesture classifier → Action executor → Tuya LAN API → Device
```

Two systemd services run on boot:
- **iris.service** — Flask web dashboard on port 5000
- **iris-gesture.service** — headless gesture detection loop

---

## Gesture Set

| Gesture | Type | Default Action |
|---|---|---|
| Open → Fist → Open | Trigger | Toggle light (configurable) |
| Pinch (thumb + index) | Trigger | Toggle all lights (configurable) |
| Peace sign (2 fingers) | Trigger | Toggle light (configurable) |
| Both hands open | Trigger | All off (configurable) |
| Fist held + move up/down | Continuous | Brightness control (requires smart bulb) |

All trigger gestures are remappable from the web dashboard — no config file editing required.

---

## Setup Guide

### 1. Clone the repo

```bash
git clone https://github.com/e-haddad/iris-core.git
cd iris-core
```

### 2. Create a virtual environment

```bash
python3 -m venv venv --system-site-packages
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install flask tinytuya mediapipe
```

> `picamera2` and `opencv-python` are available via system packages on Raspberry Pi OS — included via `--system-site-packages`.

### 4. Configure your camera

Edit `/boot/firmware/config.txt`:

```
camera_auto_detect=0

[all]
dtoverlay=imx708,cam1
```

Reboot after saving.

### 5. Add your Tuya device credentials

Run the tinytuya wizard to get your local device keys:

```bash
python3 -m tinytuya wizard
```

Follow the prompts — you'll need your Tuya IoT Platform API key, API secret, and region. This generates a `devices.json` with local keys for all your devices.

Edit `actions.py` and `app.py` with your device IDs, IPs, and local keys from `devices.json`.

### 6. Configure systemd services

Create `/etc/systemd/system/iris.service`:

```ini
[Unit]
Description=Iris Web Dashboard
After=network.target

[Service]
WorkingDirectory=/home/YOUR_USER/iris-core
ExecStart=/home/YOUR_USER/iris-core/venv/bin/python app.py
Restart=always
User=YOUR_USER

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/iris-gesture.service`:

```ini
[Unit]
Description=Iris Gesture Engine
After=network.target

[Service]
WorkingDirectory=/home/YOUR_USER/iris-core
ExecStart=/home/YOUR_USER/iris-core/venv/bin/python gesture_engine.py
Restart=always
User=YOUR_USER

[Install]
WantedBy=multi-user.target
```

Enable and start both services:

```bash
sudo systemctl enable iris.service iris-gesture.service
sudo systemctl start iris.service iris-gesture.service
```

### 7. Access the dashboard

Open a browser on any device on your local network:

```
http://YOUR_PI_IP:5000
```

---

## Adding Gestures

1. Add a new gesture classifier case in `gesture_engine.py` → `classify_gesture()`
2. Add the gesture key to `config.json` under `gestures`
3. Add the gesture key to `GESTURE_MAP` in `gesture_engine.py`
4. Add any new actions to `trigger_actions` in `config.json` and handle them in `actions.py`

---

## Adding Devices

1. Run `python3 -m tinytuya wizard` to get the new device's local key and IP
2. Add the device to the `DEVICES` dict in both `actions.py` and `app.py`
3. Add toggle actions to `config.json` → `trigger_actions` if needed

---

## File Structure

```
iris-core/
├── app.py              # Flask web dashboard and device routes
├── gesture_engine.py   # MediaPipe hand detection and gesture classification
├── actions.py          # Action executor — maps gestures to device commands
├── config.json         # Gesture definitions and action mappings
├── templates/
│   └── index.html      # Dashboard UI
├── LICENSE
└── README.md
```

---

## Roadmap

- [ ] Spotify integration — local OAuth, playback control via gestures
- [ ] Smart bulb brightness control — analog brightness via fist movement
- [ ] Directional light targeting — target nearest device based on user position
- [ ] Multi-room support — one Pi per room, shared device config
- [ ] Mobile app — remote dashboard and gesture config
- [ ] Hardware kit — pre-configured Pi + camera bundle

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Author

Built by [Edward Haddad](https://github.com/e-haddad)
