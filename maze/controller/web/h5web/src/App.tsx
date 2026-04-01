import "@h5web/app/styles.css";

import { App as H5WebApp, H5GroveProvider } from "@h5web/app";

/**
 * H5Web viewer for VAST Controller.
 * Expects the same origin to serve the h5grove API (Python Flask).
 * File to open is passed via query: ?file=trials.h5
 */
function App() {
  const params = new URLSearchParams(window.location.search);
  const file = params.get("file");

  if (!file || !file.trim()) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          gap: "0.5rem",
          padding: "1rem",
          color: "#666",
        }}
      >
        <p style={{ margin: 0 }}>No file specified.</p>
        <p style={{ margin: 0, fontSize: "0.9rem" }}>
          Use <code>?file=trials.h5</code> (or open from VAST Controller).
        </p>
      </div>
    );
  }

  // Same origin; h5grove API is mounted at /api
  const backendUrl = `${window.location.origin}/api`;

  return (
    <div style={{ height: "100vh" }}>
      <H5GroveProvider url={backendUrl} filepath={file.trim()}>
        <H5WebApp />
      </H5GroveProvider>
    </div>
  );
}

export default App;
