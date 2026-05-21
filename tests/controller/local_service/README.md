# `tests/controller/local_service`

Phase B HTTP service tests. CI installs **core + dev** only (`uv sync --extra dev`).

| File | Requires | Notes |
|------|----------|--------|
| `fixtures.py` | core + dev | Shared fixtures via `pytest_plugins = ["controller.local_service.fixtures"]` (no nested `conftest.py`) |
| `test_sandbox.py` | core + dev | Direct `PathSandbox` / `glob_safe` unit tests |
| `test_sandbox_http.py` | core + dev | Sandbox edges via Flask client (`/orm/discover`, `/orm/detect`) |
| `test_discover.py` | core + dev | Discover parsing + keyword mode (no GGUF) |
| `test_detect.py` | core + dev | Detect routes; YOLO mocked (no `local-service` / `.pt`) |
| `test_health.py` | core + dev | `GET /orm/health` |
| `test_app.py` | core + dev | App factory + CLI |
| `../test_local_service_launcher.py` | core + dev | Subprocess argv (mocked Popen) |

Optional markers (explicit skip, not `importorskip`):

- `@pytest.mark.llm_integration` — needs `MAZE_LLM_GGUF` + `local-service`
- `@pytest.mark.yolo_integration` — needs `MAZE_YOLO_WEIGHTS` + `local-service`

`tests/test_h5web_server.py` (parent) covers `register_h5web_routes` smoke; also core + dev.
