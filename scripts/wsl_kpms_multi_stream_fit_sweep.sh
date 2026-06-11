#!/usr/bin/env bash
# Batch kpMS fits on WSL GPU: anatomical, blob, fused × multiple random seeds.
#
# Each run writes to:
#   <project-dir>/<pose_stream>/seed_<NNN>/{checkpoint.h5,results.h5,fit_summary.json,...}
#
# Usage (from repo root on MED-DavisData2 or any WSL box with --extra kpms):
#   bash scripts/wsl_kpms_multi_stream_fit_sweep.sh
#
# Overrides (all optional):
#   OPENETHOMAZE_ROOT=/home/code/OpenEthoMaze
#   KPMS_PROJECT_DIR=/home/data/test
#   KPMS_MANIFEST=/home/data/test/trial_manifest_kpms_tracking_wsl.csv
#   KPMS_MAX_TRIALS=80
#   DRY_RUN=1          # print commands only
#   CONTINUE_ON_ERROR=1  # default: keep going if one fit fails
#
# Requires: uv sync --extra kpms (in OPENETHOMAZE_ROOT)

set -euo pipefail

REPO_ROOT="${OPENETHOMAZE_ROOT:-/home/code/OpenEthoMaze}"
PROJECT_DIR="${KPMS_PROJECT_DIR:-/home/data/test}"
MANIFEST="${KPMS_MANIFEST:-/home/data/test/trial_manifest_kpms_tracking_wsl.csv}"
MAX_TRIALS="${KPMS_MAX_TRIALS:-80}"
BALANCE_BY="${KPMS_BALANCE_BY:-sex,tx,strain,session,exit_number}"
CONTINUE_ON_ERROR="${CONTINUE_ON_ERROR:-1}"
DRY_RUN="${DRY_RUN:-0}"

SEEDS=(5 13 42 67 111)
STREAMS=(anatomical blob fused)

LOG_DIR="${PROJECT_DIR}/fit_logs"
mkdir -p "${LOG_DIR}"

export XLA_PYTHON_CLIENT_PREALLOCATE="${XLA_PYTHON_CLIENT_PREALLOCATE:-false}"
export TF_GPU_ALLOCATOR="${TF_GPU_ALLOCATOR:-cuda_malloc_async}"

cd "${REPO_ROOT}"

echo "Repo:        ${REPO_ROOT}"
echo "Project dir: ${PROJECT_DIR}"
echo "Manifest:    ${MANIFEST}"
echo "Max trials:  ${MAX_TRIALS}"
echo "Logs:        ${LOG_DIR}"
echo "Streams:     ${STREAMS[*]}"
echo "Seeds:       ${SEEDS[*]}"
echo

FAILED=()
SUCCEEDED=0
ATTEMPTED=0
TOTAL=$(( ${#STREAMS[@]} * ${#SEEDS[@]} ))

for stream in "${STREAMS[@]}"; do
  for seed in "${SEEDS[@]}"; do
    model_name=$(printf 'seed_%03d' "${seed}")
    log_file="${LOG_DIR}/${stream}_${model_name}.log"
    ATTEMPTED=$((ATTEMPTED + 1))
    echo "=== [$(date -Iseconds)] ${stream} / ${model_name} (${ATTEMPTED}/${TOTAL}) ==="

    cmd=(
      uv run maze-kpms-fit
      --project-dir "${PROJECT_DIR}"
      --manifest-csv "${MANIFEST}"
      --model-name "${model_name}"
      --max-trials "${MAX_TRIALS}"
      --random-seed "${seed}"
      --balance-by "${BALANCE_BY}"
      --pose-stream "${stream}"
      --no-enrich-labels
      --force-new
    )

    if [[ "${DRY_RUN}" == "1" ]]; then
      echo "DRY_RUN: ${cmd[*]}"
      continue
    fi

    set +e
    "${cmd[@]}" 2>&1 | tee "${log_file}"
    status=${PIPESTATUS[0]}
    set -e

    if [[ "${status}" -ne 0 ]]; then
      echo "FAILED: ${stream}/${model_name} (exit ${status}); log: ${log_file}" >&2
      FAILED+=("${stream}/${model_name}")
      if [[ "${CONTINUE_ON_ERROR}" != "1" ]]; then
        exit "${status}"
      fi
    else
      echo "OK: ${stream}/${model_name} -> ${PROJECT_DIR}/${stream}/${model_name}/"
      SUCCEEDED=$((SUCCEEDED + 1))
    fi
    echo
  done
done

echo "Succeeded ${SUCCEEDED}/${TOTAL} fits (${ATTEMPTED} attempted)."
if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo "Failed (${#FAILED[@]}):" >&2
  printf '  - %s\n' "${FAILED[@]}" >&2
  exit 1
fi
