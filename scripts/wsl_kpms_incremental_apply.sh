#!/usr/bin/env bash
# Apply existing ensemble checkpoints to NEW trials only (append to results_apply.h5).
#
# Does not re-fit. Requires checkpoints from wsl_kpms_multi_stream_fit_sweep.sh.
# Uses --no-overwrite-results so existing recording keys in results_apply.h5 are kept.
#
# Usage:
#   ANIMAL_IDS="3247 3248 3249 3250" bash scripts/wsl_kpms_incremental_apply.sh
#
# Env (same as full apply sweep unless noted):
#   ANIMAL_IDS          required — space-separated animal_id values
#   KPMS_PROJECT_DIR    default /home/data/test
#   KPMS_MANIFEST       default .../trial_manifest_kpms_tracking_wsl.csv
#   KPMS_APPLY_CHUNK_SIZE  default 30
#   SEEDS STREAMS       same defaults as fit sweep

set -euo pipefail

if [[ -z "${ANIMAL_IDS:-}" ]]; then
  echo "Set ANIMAL_IDS (space-separated), e.g. ANIMAL_IDS='3247 3248' $0" >&2
  exit 1
fi

REPO_ROOT="${OPENETHOMAZE_ROOT:-/home/code/OpenEthoMaze}"
PROJECT_DIR="${KPMS_PROJECT_DIR:-/home/data/test}"
MANIFEST="${KPMS_MANIFEST:-/home/data/test/trial_manifest_kpms_tracking_wsl.csv}"
APPLY_ITERS="${KPMS_APPLY_ITERS:-100}"
APPLY_CHUNK_SIZE="${KPMS_APPLY_CHUNK_SIZE:-30}"
CONTINUE_ON_ERROR="${CONTINUE_ON_ERROR:-1}"
DRY_RUN="${DRY_RUN:-0}"

SEEDS=(5 13 42 67 111)
STREAMS=(anatomical blob fused)

read -r -a ANIMAL_ID_ARR <<< "${ANIMAL_IDS}"

LOG_DIR="${PROJECT_DIR}/apply_logs_incremental"
mkdir -p "${LOG_DIR}"

export XLA_PYTHON_CLIENT_PREALLOCATE="${XLA_PYTHON_CLIENT_PREALLOCATE:-false}"
export TF_GPU_ALLOCATOR="${TF_GPU_ALLOCATOR:-cuda_malloc_async}"

cd "${REPO_ROOT}"

echo "Incremental apply for animal_id(s): ${ANIMAL_ID_ARR[*]}"
echo "Manifest: ${MANIFEST}"
echo "Append mode: --no-overwrite-results"
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
    echo "=== [$(date -Iseconds)] ${stream} / ${model_name} (${ATTEMPTED}/${TOTAL}) ==="

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
      --no-overwrite-results
      --animal-id "${ANIMAL_ID_ARR[@]}"
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
      echo "FAILED: ${stream}/${model_name} (exit ${status})" >&2
      FAILED+=("${stream}/${model_name}")
      if [[ "${CONTINUE_ON_ERROR}" != "1" ]]; then
        exit "${status}"
      fi
    else
      SUCCEEDED=$((SUCCEEDED + 1))
    fi
    echo
  done
done

echo "Succeeded ${SUCCEEDED}/${TOTAL} incremental applies."
if [[ ${#FAILED[@]} -gt 0 ]]; then
  printf '  - %s\n' "${FAILED[@]}" >&2
  exit 1
fi
