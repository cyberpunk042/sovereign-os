#!/usr/bin/env bash
# scripts/operator/generate-weaver-proto.sh — Generate Python gRPC bindings
# from proto/weaver_state.proto.
#
# Run once after the proto changes (or at image-build time).
# Requires: python3, grpcio-tools (pip install grpcio-tools).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

PROTO_DIR="${__REPO_ROOT}/proto"
PROTO_FILE="${PROTO_DIR}/weaver_state.proto"
OUT_DIR="${PROTO_DIR}"

if [ ! -f "${PROTO_FILE}" ]; then
  echo "error: proto file not found: ${PROTO_FILE}" >&2
  exit 1
fi

if ! python3 -c "import grpc_tools.protoc" 2>/dev/null; then
  echo "installing grpcio-tools..."
  pip3 install --user grpcio-tools >>/dev/null 2>&1 || {
    echo "error: grpcio-tools required. Install: pip3 install grpcio-tools" >&2
    exit 1
  }
fi

echo "generating Python bindings from ${PROTO_FILE}"
python3 -m grpc_tools.protoc \
  --proto_path="${PROTO_DIR}" \
  --python_out="${OUT_DIR}" \
  --grpc_python_out="${OUT_DIR}" \
  "${PROTO_FILE}"

echo "  → ${OUT_DIR}/weaver_state_pb2.py"
echo "  → ${OUT_DIR}/weaver_state_pb2_grpc.py"
