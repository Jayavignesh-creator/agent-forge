#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [ -f "${REPO_ROOT}/.env" ]; then
  set -a
  . "${REPO_ROOT}/.env"
  set +a
fi


SANDBOX_NAME="${OPENSHELL_SANDBOX_NAME:-orchestrator}"
SANDBOX_IMAGE="${OPENSHELL_SANDBOX_IMAGE:-openclaw}"
SSH_HOST="${OPENSHELL_SSH_HOST:-openshell-${SANDBOX_NAME}}"
GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
GATEWAY_BIND="${OPENCLAW_GATEWAY_BIND:-loopback}"
DAEMON_RUNTIME="${OPENCLAW_DAEMON_RUNTIME:-node}"
MODE="${OPENCLAW_MODE:-local}"
AUTH_CHOICE="${OPENCLAW_AUTH_CHOICE:-apiKey}"
SECRET_INPUT_MODE="${OPENCLAW_SECRET_INPUT_MODE:-plaintext}"
INSTALL_DAEMON_FLAG="${OPENCLAW_INSTALL_DAEMON:-true}"
SKIP_SKILLS_FLAG="${OPENCLAW_SKIP_SKILLS:-true}"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-${OPENCLAW_ANTHROPIC_API_KEY:-}}"
IDENTITY_FILE="${SCRIPT_DIR}/IDENTITY.md"
IDENTITY_DESTINATION="${OPENCLAW_IDENTITY_DESTINATION:-/sandbox/.openclaw/workspace/}"
SANDBOX_POLICY_FILE="${OPENCLAW_SANDBOX_POLICY_FILE:-${SCRIPT_DIR}/sandbox-policy.yaml}"

print_info() {
  printf '%s\n\n' "$1"
}

print_error() {
  printf '%s\n\n' "$1" >&2
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    print_error "Missing required command: $1"
    exit 1
  fi
}

ensure_sandbox() {
  if openshell sandbox get "${SANDBOX_NAME}" >/dev/null 2>&1; then
    print_info "Using existing OpenShell sandbox: ${SANDBOX_NAME}"
    return
  fi

  if [ ! -f "${SANDBOX_POLICY_FILE}" ]; then
    print_error "Sandbox policy file not found: ${SANDBOX_POLICY_FILE}"
    exit 1
  fi

  print_info "Creating OpenShell sandbox: ${SANDBOX_NAME}"
  openshell sandbox create \
    --name "${SANDBOX_NAME}" \
    --from "${SANDBOX_IMAGE}" \
    --policy "${SANDBOX_POLICY_FILE}" \
    -- bash -lc 'exit 0'
}

ensure_ssh_config() {
  local ssh_config_file
  ssh_config_file="${HOME}/.ssh/config"

  mkdir -p "${HOME}/.ssh"
  touch "${ssh_config_file}"
  chmod 600 "${ssh_config_file}"

  if grep -qE "^[[:space:]]*Host[[:space:]]+${SSH_HOST}([[:space:]]|\$)" "${ssh_config_file}"; then
    return
  fi

  if [ -s "${ssh_config_file}" ]; then
    printf '\n' >> "${ssh_config_file}"
  fi

  openshell sandbox ssh-config "${SANDBOX_NAME}" >> "${ssh_config_file}"
}

verify_ssh_host() {
  local ssh_resolved_config
  ssh_resolved_config="$(ssh -G "${SSH_HOST}" 2>/dev/null || true)"

  if ! printf '%s\n' "${ssh_resolved_config}" | grep -qi '^proxycommand '; then
    print_error "SSH host alias ${SSH_HOST} is not configured for OpenShell."
    print_error "Expected an OpenShell-generated SSH config entry for sandbox ${SANDBOX_NAME}."
    exit 1
  fi
}

build_onboard_command() {
  local cmd
  cmd=(
    openclaw onboard
    --non-interactive
    --mode "${MODE}"
    --auth-choice "${AUTH_CHOICE}"
    --anthropic-api-key "${ANTHROPIC_API_KEY}"
    --secret-input-mode "${SECRET_INPUT_MODE}"
    --gateway-port "${GATEWAY_PORT}"
    --gateway-bind "${GATEWAY_BIND}"
    --daemon-runtime "${DAEMON_RUNTIME}"
    --accept-risk
  )

  if [ "${INSTALL_DAEMON_FLAG}" = "true" ]; then
    cmd+=(--install-daemon)
  fi

  if [ "${SKIP_SKILLS_FLAG}" = "true" ]; then
    cmd+=(--skip-skills)
  fi

  printf '%q ' "${cmd[@]}"
}

run_onboard() {
  local onboard_command
  local remote_command
  onboard_command="$(build_onboard_command)"
  remote_command="$(printf 'bash -lc %q' "${onboard_command}; printf '\nOnboarding Complete\n'")"

  print_info "Running OpenClaw onboarding inside ${SSH_HOST}"
  ssh -n "${SSH_HOST}" "${remote_command}"
}

upload_identity_file() {
  if [ ! -f "${IDENTITY_FILE}" ]; then
    print_error "Identity file not found: ${IDENTITY_FILE}"
    exit 1
  fi

  print_info "Uploading $(basename "${IDENTITY_FILE}") to ${IDENTITY_DESTINATION}"
  openshell sandbox upload "${SANDBOX_NAME}" "${IDENTITY_FILE}" "${IDENTITY_DESTINATION}"
}

main() {
  require_command openshell
  require_command ssh

  if [ -z "${ANTHROPIC_API_KEY}" ]; then
    print_error "Set ANTHROPIC_API_KEY or OPENCLAW_ANTHROPIC_API_KEY before running this script."
    exit 1
  fi

  ensure_sandbox
  ensure_ssh_config
  verify_ssh_host

  run_onboard
  upload_identity_file
}

main "$@"
