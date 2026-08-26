#!/usr/bin/env bash
# verify_local.sh — sign a sample CourseBriefV2 exactly like Radar does and POST
# it to a locally running LearnForge dev server. Asserts a 2xx acceptance.
#
#   LEARNFORGE_WEBHOOK_SECRET=SovereignForge2026! \
#   TARGET=http://localhost:3000/api/course-generation-jobs \
#   bash verify_local.sh
#
# Signing scheme (must match lib/radar/verify.ts):
#   sig = HMAC_SHA256(secret, rawBodyBytes)  as lowercase hex
#   rawBodyBytes = the EXACT bytes POSTed (compact, key-sorted JSON)

set -euo pipefail

SECRET="${LEARNFORGE_WEBHOOK_SECRET:-SovereignForge2026!}"
TARGET="${TARGET:-http://localhost:3000/api/course-generation-jobs}"
IDEM="stub-smoke-$(date +%s)"

# Canonical body — compact separators + sorted keys (matches Radar's dispatcher).
BODY=$(python3 - "$IDEM" <<'PY'
import json, sys
idem = sys.argv[1]
brief = {
  "schema_version": "2.0",
  "signal_id": "smoke-signal",
  "idempotency_key": idem,
  "source": {"provider": "leland", "source_url": "https://leland.com/events/x",
             "source_title": "Smoke Event", "observed_at": None},
  "demand_evidence": {"registrations": 1000, "priority_score": 90,
                      "priority_band": "breakout", "category": "Consulting",
                      "velocity_note": None},
  "audience": {"primary_persona": "Test persona", "current_state": "state",
               "desired_outcome": "outcome", "pain_points": ["p1"]},
  "commercial_hypothesis": {"offer_title": "ForgeCore: Smoke", "promise": "promise",
                            "price_usd": 299.0, "anchor_price_usd": 1899.0,
                            "discount_pct": 84, "free_module_count": 2,
                            "cta_headline": "Headline", "cta_subtext": "Subtext",
                            "validation_status": "hypothesis"},
  "generation_constraints": {"difficulty": "intermediate", "language": "en",
                             "target_duration_min": 270, "suggested_module_count": 6,
                             "required_outcomes": ["o1"], "prohibited_claims": ["no claims"]},
  "callback": {"correlation_id": "radar-smoke-signal", "status_url": None},
}
sys.stdout.write(json.dumps(brief, separators=(",", ":"), sort_keys=True))
PY
)

SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.*= //')

echo "→ POST $TARGET"
echo "→ idem=$IDEM sig=${SIG:0:12}…"

HTTP=$(curl -sS -o /tmp/lf_stub_resp.json -w "%{http_code}" -X POST "$TARGET" \
  -H "Content-Type: application/json" \
  -H "X-Radar-Event: course_brief.dispatch" \
  -H "X-Radar-Schema-Version: 2.0" \
  -H "X-Radar-Idempotency-Key: $IDEM" \
  -H "X-Radar-Signature: $SIG" \
  -H "X-Radar-Signature-Algorithm: hmac-sha256" \
  --data-binary "$BODY")

echo "→ HTTP $HTTP"
cat /tmp/lf_stub_resp.json; echo

if [ "$HTTP" = "202" ] || [ "$HTTP" = "200" ]; then
  echo "✅ PASS — receiver accepted the signed CourseBriefV2"
else
  echo "❌ FAIL — expected 200/202, got $HTTP"
  exit 1
fi
