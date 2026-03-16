# h5web + h5grove integration sketch

Local HDF5 viewer for vast_controller: no Node/npm on target machines.  
Node is used only once on a dev machine to build the h5web frontend; deployment is Python + static assets.

---

## 1. Architecture overview

```
┌─────────────────────────────────────────────────────────────────┐
│  vast_controller (Qt)                                           │
│  • "Open H5 in h5web" → resolve H5 path → start local server    │
│    (or use current output_dir + h5_filename)                    │
│  • Open browser (or QWebEngineView) to http://127.0.0.1:PORT/   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Local HTTP server (Python, same process or subprocess)          │
│  • Serves static h5web build (index.html, JS, CSS)              │
│  • Mounts h5grove routes: /, /attr, /data, /meta, /stats         │
│  • base_dir = parent of selected H5 file                         │
│  • Frontend loads with ?file=trials.h5 → backend serves it      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Browser (or QWebEngineView)                                     │
│  • GET /?file=trials.h5 → index.html                             │
│  • JS: H5GroveProvider(fetcher → http://127.0.0.1:PORT)           │
│  • Requests /meta?file=trials.h5, /data?file=...&path=...       │
└─────────────────────────────────────────────────────────────────┘
```

- **h5grove**: Python package that exposes HDF5 contents over HTTP (attributes, metadata, data).  
  Uses a `base_dir`; the `file` query parameter is a path relative to `base_dir`.
- **h5web**: React app that talks to an h5grove-compatible backend via `H5GroveProvider`.  
  We build it once, commit the static bundle, and serve it from the same Python server.

---

## 2. Repo layout (proposed)

```
vast_controller/
├── pyproject.toml                    # add: h5grove[flask] or h5grove[fastapi]
├── vast_controller/
│   ├── gui/
│   │   └── main_window.py            # "Open H5 in h5web" → launch server + browser
│   └── h5web_server.py              # NEW: small server (Flask/FastAPI) that:
│                                    #   - serves static from web/h5web_dist/
│                                    #   - mounts h5grove with configurable base_dir
├── web/                              # NEW (optional: only if you embed viewer in repo)
│   ├── h5web/                        # React app source (dev only, Node required)
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   └── src/
│   │       └── App.tsx               # H5GroveProvider + read ?file= from URL
│   └── h5web_dist/                   # Built static files (committed)
│       ├── index.html
│       ├── assets/*.js
│       └── assets/*.css
└── docs/
    └── h5web_h5grove_integration.md  # this file
```

Alternative: ship only `h5web_dist/` (no `web/h5web/` in repo) and build it in CI or on a single dev machine, then commit the build output.

---

## 3. Backend: Python server (vast_controller)

### 3.1 Dependency

In `pyproject.toml`:

```toml
dependencies = [
    ...
    "h5grove[flask]",   # or [fastapi]; Flask is lighter
]
```

### 3.2 Server module: `vast_controller/h5web_server.py`

Responsibilities:

- Create a Flask (or FastAPI) app that:
  - Serves static files from a directory (e.g. `web/h5web_dist/` or a package path).
  - Registers h5grove’s blueprint/router so that **all h5grove requests use a single configured H5 file** (or a `base_dir` + `file` from query).
- Run the app on `127.0.0.1` and an ephemeral port (e.g. `0` → bind to any free port).
- Expose the base URL to the caller so the GUI can open `{base_url}/?file=trials.h5`.

**Important:** h5grove’s Flask blueprint expects `file` as a query parameter and resolves it against `app.config["H5_BASE_DIR"]`. So:

- Set `H5_BASE_DIR` to the **parent directory** of the H5 file (or a folder containing it).
- The frontend (or the URL we open) should pass `file=<basename>` (e.g. `file=trials.h5`).

**Lifecycle options:**

- **A. One-shot server per “Open in h5web”:**  
  When the user clicks “Open H5 in h5web”, resolve the H5 path (see §4). Start a background thread or subprocess running the Flask app with `H5_BASE_DIR = str(h5_path.parent)`. Open browser to `http://127.0.0.1:PORT/?file=<h5_path.name>`. Optionally shut down the server when the window is closed or after a timeout (e.g. 30 minutes).
- **B. Single long-lived server:**  
  Start once (e.g. on first use), set `H5_BASE_DIR` to a “root” directory (e.g. config’s `output_dir`). Then the URL always uses `?file=trials.h5` or whatever file the user selected. If the user can pick a file outside that root, you either need to change `H5_BASE_DIR` (and maybe restart the route handlers) or run a separate server instance for that file.

Recommendation: **A** for simplicity (one server per file, clear lifecycle).

**Sketch (Flask):**

```python
# vast_controller/h5web_server.py (sketch)
from pathlib import Path
from flask import Flask, send_from_directory
from h5grove.flask_utils import BLUEPRINT

def create_app(h5_base_dir: Path, static_dir: Path) -> Flask:
    app = Flask(__name__)
    app.config["H5_BASE_DIR"] = str(h5_base_dir.resolve())
    app.register_blueprint(BLUEPRINT)

    @app.route("/")
    def index():
        return send_from_directory(static_dir, "index.html")

    @app.route("/<path:path>")
    def static_files(path):
        return send_from_directory(static_dir, path)

    return app
```

Register the blueprint **before** adding `"/"` and `"/<path:path>"` so h5grove routes (`/attr`, `/data`, `/meta`, `/stats`) take precedence over the static catch-all.

```python
def run_server(h5_file: Path, static_dir: Path, port: int = 0) -> int:
    """Start server in background; return actual port. Call from thread or subprocess."""
    app = create_app(h5_file.parent, static_dir)
    # Use port=0 to get an ephemeral port; then read it from the server.
    # Flask dev server: app.run(host="127.0.0.1", port=port, threaded=True)
    # Return the port so the GUI can open http://127.0.0.1:{port}/?file={h5_file.name}
```

You’ll need to resolve `static_dir` to the installed `h5web_dist` path (e.g. via `importlib.resources` or a known relative path from `__file__`).

---

## 4. GUI: “Open H5 in h5web” (main_window.py)

Current behaviour: `_on_open_h5web` uses a file dialog and calls `_open_h5web(Path(h5_path))`, which tries `npx h5web <path>`.

**New behaviour:**

1. **Resolve the H5 file path**
   - If you want “current DB”:  
     `output_dir = getattr(self._config, "output_dir", None)`  
     `h5_name = (getattr(self._config, "h5_filename", None) or "trials.h5").strip() or "trials.h5"`  
     `db_path = Path(output_dir) / Path(h5_name).name`  
     If `db_path.exists()`, use it; else show “No H5 file at &lt;path&gt;” and optionally open file dialog.
   - Or keep “file dialog” only: user picks any `.h5` file (current code path).
2. **Locate static assets**
   - e.g. `static_dir = package_dir / "web" / "h5web_dist"` or from `importlib.resources.files("vast_controller") / "web" / "h5web_dist"`.  
   If `static_dir` is missing, show: “h5web viewer not installed (missing web/h5web_dist).”
3. **Start the Python server** (see §3.2) with `h5_file = db_path`, `static_dir = static_dir`; get back `port`.
4. **Open browser** to `http://127.0.0.1:{port}/?file={db_path.name}`  
   (e.g. `webbrowser.open(url)` or open a `QWebEngineView` with that URL).
5. **Optional:** Offer “current DB” in a toolbar/menu (no dialog) and “Other H5 file…” (with dialog). Both go through the same server + browser flow.

Replace the current `_open_h5web` implementation with this flow; remove the `npx h5web` subprocess call.

---

## 5. Frontend: h5web app (dev machine only)

- **Stack:** React + Vite (or CRA), `@h5web/app` with `H5GroveProvider`.
- **Build output:** `npm run build` → output to `web/h5web_dist/` (or `vast_controller/web/h5web_dist/` if you ship it inside the package).
- **Backend URL:** The app must know the h5grove API base URL. Options:
  - **Relative:** If the browser loads the app from `http://127.0.0.1:PORT/`, use relative URLs (e.g. fetcher to `""` or `"/"`). Then `/meta`, `/data` etc. are on the same origin → no CORS, and the same server that serves the static app also serves h5grove.
  - **Env at build time:** e.g. `VITE_H5GROVE_URL=http://127.0.0.1:8888` only if you ever need a different origin (not needed for local-only).
- **File parameter:** On load, read `?file=...` from `window.location.search` and pass that as the “file” to the provider (or to the app’s root so that all requests use it).  
  The h5grove backend expects a `file` query param on each request; the frontend typically sends it on every `/meta`, `/data`, etc. So the app should:
  - Parse `file` from the URL (e.g. `new URLSearchParams(location.search).get("file")`).
  - If missing, show a small “Enter file name” or “No file specified” state.
  - Use that value in all H5GroveProvider requests (or configure the provider so it appends `?file=...`).

**Minimal App sketch (conceptual):**

```tsx
// App.tsx (conceptual)
import { H5GroveProvider, App as H5WebApp } from "@h5web/app";
import { createBasicFetcher } from "@h5web/app";

const fetcher = createBasicFetcher(undefined); // same origin

function App() {
  const params = new URLSearchParams(window.location.search);
  const file = params.get("file");

  if (!file) {
    return <div>No file specified. Use ?file=trials.h5</div>;
  }

  return (
    <H5GroveProvider fetcher={fetcher} file={file}>
      <H5WebApp />
    </H5GroveProvider>
  );
}
```

Build with `npm run build` and point the output to `web/h5web_dist/`. Commit that folder so deploy machines never need Node.

---

## 6. Deployment

- **Target machines:** Install Python, run `uv sync` (or `pip install -e .`), and have `web/h5web_dist/` present (in repo or copied). No Node/npm.
- **Dev:** To rebuild the viewer after an h5web upgrade: `cd web/h5web && npm install && npm run build`; commit updated `h5web_dist/`.

---

## 7. Checklist

- [ ] Add `h5grove[flask]` (or `[fastapi]`) to `pyproject.toml`.
- [ ] Implement `vast_controller/h5web_server.py`: create_app, run_server, static + h5grove routes.
- [ ] Resolve static dir (package-relative or repo-relative) and handle missing `h5web_dist` in GUI.
- [ ] In `main_window.py`: replace `_open_h5web` / `_on_open_h5web` with: resolve H5 path → start server → open browser with `?file=...`.
- [ ] (Dev) Create `web/h5web` React app with H5GroveProvider, read `?file=`, build to `web/h5web_dist/`.
- [ ] Commit `web/h5web_dist/` (or add to package data so it’s installed with the app).
- [ ] Optional: “Open current DB in h5web” (no dialog) + “Open other H5 file…” (dialog).
- [ ] Optional: shutdown server after timeout or when the last viewer tab closes (simplest: leave server running until app exit).

---

## 8. References

- h5grove: https://silx-kit.github.io/h5grove/ (install, example Flask/FastAPI, integration, API).
- h5web: https://github.com/silx-kit/h5web (React components); `@h5web/app` for the standalone app and `H5GroveProvider`.
- h5grove API: `file` is a query parameter; endpoints live under `/`, `/attr`, `/data`, `/meta`, `/stats`; Flask uses `app.config["H5_BASE_DIR"]`.
