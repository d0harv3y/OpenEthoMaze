"""
One-shot Langfuse demo for OpenEthoMaze.

Simulates a small maze-pipeline batch (parent trace + per-trial spans) so you
can inspect hierarchy in the Langfuse UI and via `langfuse-cli api traces list`.

Requires LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_HOST in the env.

Run from repo root:
    uv run --with langfuse python scripts/langfuse_demo.py
"""

from __future__ import annotations

from langfuse import get_client, observe, propagate_attributes


@observe(name="process-trial")
def demo_process_trial(
    animal_id: str, session: str, trial: str, phase: str
) -> dict[str, object]:
    with propagate_attributes(
        metadata={
            "animal_id": animal_id,
            "session": session,
            "trial": trial,
            "phase": phase,
        }
    ):
        return {
            "ok": True,
            "trial_key": f"{animal_id}/{session}/{trial}",
        }


@observe(name="maze-pipeline-run")
def demo_pipeline_run(db_path: str) -> dict[str, object]:
    with propagate_attributes(
        session_id=db_path,
        metadata={"project": "OpenEthoMaze", "demo": "true"},
    ):
        trials = [
            ("S01", "hab", "T01", "habituation"),
            ("S01", "exp", "T02", "experimental"),
        ]
        results = [
            demo_process_trial(a, s, t, p) for a, s, t, p in trials
        ]
        return {
            "total": len(trials),
            "success": len(results),
            "failed": 0,
            "db_path": db_path,
        }


def main() -> None:
    client = get_client()
    stats = demo_pipeline_run("demo/openethomaze-results.h5")
    client.flush()
    print("Demo trace flushed to Langfuse.")
    print(stats)


if __name__ == "__main__":
    main()
