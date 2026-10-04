# KisanOS Crop Agent — backend integration

**Code:** `app/agents/crop.py` (version `crop-rules-1.1.0`, provider `deterministic-wheat-screening-rules`)
**Tests:** `tests/test_crop_agent.py`
**Registry:** source entry `crop-rules` in `app/core/sources.py` (status `unverified`)

## Scope and guarantees

- Deterministic, rule-based, **wheat-only** screening. **No ML model, dataset, download, paid API, or third-party service is required or used.**
- Never emits: pesticide/fertilizer product names, doses, spray schedules, guaranteed yield loss, confirmed disease names, "spray now", chemical treatment instructions, or irrigation commands.
- Hypothesis language only: possible water stress, possible nutrient stress, rust-like symptoms, possible leaf spots or disease, possible insect damage, premature drying; multiple causes possible.
- Non-crop intake (or a missing crop) returns `status: "unsupported"` and abstains — it never silently falls back.

## Execution path

```
POST /api/v1/assessments/{id}/analysis   (app/api/routes.py)
  -> orchestrator._run_job               (app/services/orchestrator.py)
      -> asyncio.to_thread(assess_crop, assessment_id, intake, vision)
          -> app.agents.crop.assess_crop -> AgentResult
      -> policy_gate(results["crop"])
  -> GET .../results  -> five agent cards + farm_plan
```

Crop receives the intake payload plus the Vision adapter's `AgentResult` (dependency edge only: Vision → Crop).

## How Vision output is consumed

- Used **only** when Vision status is `complete` or `partial`, and only its raw `observations` strings (visible findings) — never its possible causes, never as a diagnosis.
- Statuses `unavailable`, `stale`, `not_assessed`, `error`, `absent`, or a `complete` Vision result with no observations → zero photo evidence; Crop continues on farmer-reported symptoms only (`data.vision_used = false`, `data.vision_status` records what happened, `input_evidence` contains `photo_visible: none (...)`).

## Evidence separation (kept structurally separate)

| Class | Where |
|---|---|
| `farmer_reported` | symptom labels worded "… reported by the farmer"; `input_evidence` lines prefixed `farmer_reported:` |
| `photo_visible` | `observations` lines prefixed `Photo visible:`; `input_evidence` lines prefixed `photo_visible:`; never merged into hypotheses |
| `rule_based_check` | `checks`; recorded in `data.evidence_labels.rule_based_check` |

`evidence_band` describes evidence quality only (`medium` = farmer **and** photo evidence, otherwise `low`), never a probability. With no usable evidence at all: `status: "partial"`, `evidence_band: "low"`, explicit `evidence_reason`, and safe general inspection checks.

## Farmer-answerable discriminators used in checks

Older vs younger leaves · uniform vs patchy pattern · root-zone soil moisture compared in an affected vs healthy spot · leaf rolling/wilting and overnight recovery · colour, location and leaf side of spots/pustules and whether healthy plants nearby are unaffected · visible insects under leaves and at the plant base · edge vs scattered (whole-field) pattern and symptom spread · recent irrigation or rainfall and whether symptoms changed afterwards · affected vs healthy plant comparison (always available as the baseline check).

## Expert-review referral triggers (`data.referral_reasons`)

1. `rust_like_pustules_reported_or_observed`
2. `symptoms_rapidly_spreading`
3. `heading_to_grain_stage_with_symptoms` (heading, flowering, milk, dough)
4. `cause_remains_unknown`
5. `evidence_low` (single-source evidence) or `evidence_conflicting` (wet/drainage-poor report with dry/wilt symptoms)
6. `farmer_asked_about_chemicals` (free-text scanned for treatment questions; the question is **never echoed** back)
7. `unsupported_crop_scope`

Field checks always precede the referral note; the referral note is appended last and never replaces a field check. `data.referral_recommended` is consumed by the advisor for `expert_review_recommended` farm plans.

## Sources and verification status

- The source registry has **no externally verified Crop agronomy record**, so Crop cards ship `sources=[]` and state it explicitly in `evidence_reason` plus `data.rule_verification` (`status: "unverified"`, `source_registry_id: "crop-rules"`).
- The `crop-rules` registry entry is a self-description with `url: null` (same pattern as the existing `vision-model` entry) — **no URL, publisher, date, or title was invented**.
- Pending: verified agronomy sources (exact title, publisher, URL, geography, status) and local-agronomist review of the rules. Until then every rule is provisional/unverified by design.

## Configuration

**None.** Crop reads no environment variables; no `CROP_*` keys were added because none are genuinely required.

## Tests (`tests/test_crop_agent.py`)

Wheat-only scope · safe yellowing hypothesis · non-chemical spot checks (referral note last) · rust-like referral · rapid-spread referral · Vision `complete` consumed safely (and referral is not blanket-on) · Vision `not_assessed` / `unavailable` / `stale` / `error` fallback · evidence separation · forbidden-output scan (products, doses, spray, confirmed names, quantities, irrigation commands, no echo of chemical questions) · valid `AgentResult` round-trip · check cap ≤ 8 · conservative missing-evidence default · no fabricated URLs/sources · heading-to-grain and conflicting-evidence referrals · free-text provenance safety.

Run: `python -c "import app.main"`, `pytest -q`, or `pytest tests/test_crop_agent.py -q`.

## Out-of-scope note (standalone team package)

`agents/crop/crop/` (untracked; duplicate copy in `crop_agent.zip (1)/`) is **not connected**. It must not be promoted as-is: confirmed disease/nutrient names (e.g. "Stripe rust (Puccinia striiformis)", "Nitrogen deficiency"), a `days_since_irrigation >= 12` rule, an irrigation recommendation, runtime-fabricated `retrieved_at` values, homepage-only "sources" (PARC/Punjab/FAO home pages), and a Gemini `ai_enhance.py` path (`google-genai` dependency). Resolution requires your decision plus verified sources.
