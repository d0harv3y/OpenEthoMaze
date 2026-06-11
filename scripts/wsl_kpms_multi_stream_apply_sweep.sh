#!/usr/bin/env bash
# Apply all models from wsl_kpms_multi_stream_fit_sweep.sh to the full manifest cohort.
#
# Each run writes:
#   <project-dir>/<pose_stream>/seed_<NNN>/results_apply.h5
#
# Usage (after fit sweep completes):
#   bash scripts/wsl_kpms_multi_stream_apply_sweep.sh
#
# Overrides: same env vars as fit sweep (OPENETHOMAZE_ROOT, KPMS_PROJECT_DIR, KPMS_MANIFEST).
# Optional:
#   KPMS_APPLY_ITERS=100   # apply_model Gibbs iters (default 100)
#   DRY_RUN=1
#   CONTINUE_ON_ERROR=1

set -euo pipefail

REPO_ROOT="${OPENETHOMAZE_ROOT:-/home/code/OpenEthoMaze}"
PROJECT_DIR="${KPMS_PROJECT_DIR:-/home/data/test}"
MANIFEST="${KPMS_MANIFEST:-/home/data/test/trial_manifest_kpms_tracking_wsl.csv}"
APPLY_ITERS="${KPMS_APPLY_ITERS:-100}"
APPLY_CHUNK_SIZE="${KPMS_APPLY_CHUNK_SIZE:-30}"
CONTINUE_ON_ERROR="${CONTINUE_ON_ERROR:-1}"
DRY_RUN="${DRY_RUN:-0}"

SEEDS=(5 13 42 67 111)
STREAMS=(anatomical blob fused)

LOG_DIR="${PROJECT_DIR}/apply_logs"
mkdir -p "${LOG_DIR}"

export XLA_PYTHON_CLIENT_PREALLOCATE="${XLA_PYTHON_CLIENT_PREALLOCATE:-false}"
export TF_GPU_ALLOCATOR="${TF_GPU_ALLOCATOR:-cuda_malloc_async}"

cd "${REPO_ROOT}"

echo "Repo:        ${REPO_ROOT}"
echo "Project dir: ${PROJECT_DIR}"
echo "Manifest:    ${MANIFEST}"
echo "Apply iters: ${APPLY_ITERS}"
echo "Chunk size:  ${APPLY_CHUNK_SIZE} manifest rows per GPU batch"
echo "Logs:        ${LOG_DIR}"
echo

FAILED=()
SUCCEEDED=0
ATTEMPTED=0
TOTAL=$(( ${#STREAMS[@]} * ${#SEEDS[@]} ))

for stream in "${STREAMS[@]}"; do
  for seed in "${SEEDS[@]}"; do
    model_name=$(printf 'seed_%03d' "${seed}")
    log_file="${LOG_DIR}/${stream}_${model_name}.log"
    ckpt="${PROJECT_DIR}/${stream}/${model_name}/checkpoint.h5"
    ATTEMPTED=$((ATTEMPTED + 1))
    echo "=== [$(date -Iseconds)] apply ${stream} / ${model_name} (${ATTEMPTED}/${TOTAL}) ==="

    if [[ ! -f "${ckpt}" ]]; then
      echo "SKIP: missing checkpoint ${ckpt}" >&2
      FAILED+=("${stream}/${model_name}:missing_checkpoint")
      continue
    fi

    cmd=(
      uv run maze-kpms-apply
      --project-dir "${PROJECT_DIR}"
      --manifest-csv "${MANIFEST}"
      --model-name "${model_name}"
      --pose-stream "${stream}"
      --num-iters "${APPLY_ITERS}"
      --apply-chunk-size "${APPLY_CHUNK_SIZE}"
      --no-enrich-labels
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
      echo "OK: ${PROJECT_DIR}/${stream}/${model_name}/results_apply.h5"
      SUCCEEDED=$((SUCCEEDED + 1))
    fi
    echo
  done
done

echo "Succeeded ${SUCCEEDED}/${TOTAL} applies (${ATTEMPTED} attempted)."
if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo "Failed (${#FAILED[@]}):" >&2
  printf '  - %s\n' "${FAILED[@]}" >&2
  exit 1
fi
