#!/bin/bash
# Deploy this checkout of do_derma to the hosted demo bench (Frappe v16, do_health + do_derma).
#
#   scripts/deploy-demo.sh
#
# Server details are NOT in the repo. Provide them as environment variables or in
# ~/.config/soulvd/derma-deploy.env (sourced when present):
#   DERMA_DEPLOY_HOST   ssh target, e.g. root@1.2.3.4            (required)
#   DERMA_DEPLOY_KEY    ssh private key path                       (default: ssh agent / default key)
#   DERMA_DEPLOY_SITE   frappe site name                           (default: derma.soulvd.com)
#   DERMA_DEPLOY_BENCH  bench path on the server                   (default: /home/frappe/bench)
#   DERMA_DEPLOY_USER   bench OS user on the server                (default: frappe)
#
# Steps: rsync the app (no node_modules / dist / backups) -> bench build --production ->
# bench migrate (creates custom fields + upgrades the seeded print formats) ->
# supervisorctl restart bench-web: -> ping -> smoke test of the Patient Advice print block.
set -euo pipefail

[ -f ~/.config/soulvd/derma-deploy.env ] && . ~/.config/soulvd/derma-deploy.env
: "${DERMA_DEPLOY_HOST:?set DERMA_DEPLOY_HOST (root@host) in the environment or ~/.config/soulvd/derma-deploy.env}"
SITE=${DERMA_DEPLOY_SITE:-derma.soulvd.com}
BENCH=${DERMA_DEPLOY_BENCH:-/home/frappe/bench}
BUSER=${DERMA_DEPLOY_USER:-frappe}
SSH="ssh ${DERMA_DEPLOY_KEY:+-i $DERMA_DEPLOY_KEY}"

REPO=$(cd "$(dirname "$0")/.." && pwd)
echo "deploying $(git -C "$REPO" rev-parse --short HEAD) ($(git -C "$REPO" rev-parse --abbrev-ref HEAD)) -> $DERMA_DEPLOY_HOST:$BENCH/apps/do_derma [$SITE]"

rsync -az --delete -e "$SSH" \
  --exclude node_modules --exclude 'public/dist' --exclude '.claude' --exclude '.serena' \
  --exclude '*.bak_*' --exclude '__pycache__' --exclude '.git' \
  "$REPO/" "$DERMA_DEPLOY_HOST:$BENCH/apps/do_derma/"

$SSH "$DERMA_DEPLOY_HOST" bash -s "$SITE" "$BENCH" "$BUSER" <<'REMOTE'
set -euo pipefail
SITE=$1; BENCH=$2; BUSER=$3
chown -R "$BUSER:$BUSER" "$BENCH/apps/do_derma"
sudo -iu "$BUSER" bash -c "[ -f ~/.bench-env ] && . ~/.bench-env; cd $BENCH && bench build --app do_derma --production 2>&1 | tail -2 && bench --site $SITE migrate 2>&1 | tail -2"
supervisorctl restart bench-web: | tail -2
sleep 4
curl -s -o /dev/null -w "$SITE ping http %{http_code}\n" "https://$SITE/api/method/ping"
# Smoke test: the SOAP print carries the Patient Advice block only when the encounter opts in.
sudo -iu "$BUSER" bash -c "[ -f ~/.bench-env ] && . ~/.bench-env; cd $BENCH && bench --site $SITE console" <<'PY' 2>/dev/null | grep -E "^(encounter|advice)"
import frappe
enc = frappe.get_all("Patient Encounter", filters={"docstatus": 0, "custom_derma_soap_plan": ["is", "set"]}, pluck="name", limit=1)
name = enc[0] if enc else None
print("encounter:", name)
if name:
    before = frappe.db.get_value("Patient Encounter", name, ["custom_derma_patient_advice", "custom_derma_print_patient_advice", "custom_derma_patient_advice_language"], as_dict=True)
    frappe.db.set_value("Patient Encounter", name, {"custom_derma_patient_advice": before.custom_derma_patient_advice or "Apply the cream twice a day.", "custom_derma_print_patient_advice": 0})
    off = frappe.get_print("Patient Encounter", name, print_format="Derma Assessment Note (SOAP)")
    frappe.db.set_value("Patient Encounter", name, "custom_derma_print_patient_advice", 1)
    on = frappe.get_print("Patient Encounter", name, print_format="Derma Assessment Note (SOAP)")
    frappe.db.set_value("Patient Encounter", name, before)
    frappe.db.commit()
    print("advice OFF -> printed:", "Patient Advice" in off, "| advice ON -> printed:", "Patient Advice" in on)
PY
REMOTE
echo "DONE - https://$SITE/desk/derma-chart > Assessment > tick 'Include patient advice' > language > Print"
