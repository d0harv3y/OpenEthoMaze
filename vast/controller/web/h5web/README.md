# H5Web viewer for VAST Controller

React app that provides the HDF5 viewer UI. It is built once (on a machine with Node/npm) and the output is served by the Python h5grove backend.

## Build (dev machine only)

```powershell
cd web/h5web
npm install
npm run build
```

Output is written to `web/h5web_dist/`. Commit that folder so deployment machines get the viewer without needing Node.

## Dev server

```powershell
npm run dev
```

Then open `http://localhost:5173/?file=trials.h5`. The app will try to talk to the h5grove API at the same origin; for local dev you can run the vast_controller Python server (or a standalone h5grove server) on another port and set the backend URL via env if we add that later.

## URL

The file to open is passed in the query string: `?file=trials.h5`. VAST Controller opens the browser with that param when you click “Open H5 in h5web”.
