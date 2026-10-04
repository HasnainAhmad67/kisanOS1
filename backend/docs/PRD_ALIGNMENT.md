# KisanOS PRD alignment notes

**Source of truth:** KisanOS PRD v1.0, dated 3 October 2026. The PRD takes precedence over teammate-agent research code when their rules disagree.

## Pilot scope

- Bahawalpur district pilot with explicit area allowlist (`bahawalpur_sadar`, `ahmadpur_east`, `yazman`, `hasilpur`, `khairpur_tamewali`).
- Wheat only, explicitly confirmed by the farmer. Unsupported crop/area does not silently fall back.
- Current supported stage vocabulary is the PRD list, including `not_sure`.
- GPS coordinates require consent and are limited to configured pilot vicinity; selected/coarse area remains available without GPS.

## Safety and evidence contract

- Specialist agent cards remain separate and use the common typed envelope: identity, status, summary, observations, possible causes, checks, evidence band/reason, sources, provider/version, timestamp, flags, input evidence and structured data.
- Evidence bands describe evidence quality, not disease probability. The self-hosted vision adapter caps at Medium; image quality alone cannot create a symptom finding.
- Crop terms are hypotheses (`rust-like`, `possible stress`); no confirmed diagnoses, lab claims, products, application rates, chemical/spray schedules, yield promises, or unconditional water command.
- Farm Advisor is deterministic, chooses only one of `insufficient_information`, `monitor`, `field_inspection_recommended`, `expert_review_recommended`, caps actions at three checks, and preserves detected conflicts.
- Weather must include provider, source/retrieval timestamps, freshness, timezone and forecast-grid location resolution. Missing/stale provider timestamps cannot be called fresh. There is no synthetic fallback.
- Water uses no numeric day/rain/temperature/ET0/depth thresholds. Weather is context—not field soil measurement or a trigger.
- AMIS has no verified stable API contract in the reviewed PRD; absent verified source data, Market says unavailable or shows a clearly farmer-reported quote. No demo/live-looking price is seeded.
- A photo is private, bounded and EXIF-stripped. No client-supplied image URL, public object URL, or third-party photo inference. If self-hosted inference is unavailable, Vision abstains and other agents continue.
- Persistent safety notice: screening/decision support only; severe, spreading, or unclear symptoms should be reviewed by a local agriculture officer or qualified expert.

## Data and runtime

- UTC timestamps plus explicit Asia/Karachi context; source and policy versions saved with each assessment.
- Assessment token is shown once to the client; only its SHA-256 digest is stored. Photos are private, default-retained for 24 hours, and deleted on request or expiry.
- Notes/photos are not written into application logs. Farmer follow-ups are new timestamped observations—not evidence of progression.
- Analysis emits actual phase events and allows independent-provider failures. This backend's task launcher is single-process; use a durable shared queue before multi-replica deployment.
- The demo endpoint marks its sample as simulated input only. Weather, prices and image findings are not fixtures.

## Supplied code reconciliation

The uploaded project set contains three agent archives (Weather, Water, Vision); Crop and Market agent archives and the fifth requested team research document were not attached. The Weather/Water archives use some climate and irrigation thresholds disallowed by the PRD. The Vision archive defaults to dummy output and can route images to external Gemini/Groq APIs. Therefore:

- Weather provider fetch + area resolver are reused; unapproved crop-risk interpretation and fallback output are not.
- Water is replaced by a conservative, deterministic field-attention policy; legacy numeric thresholds are quarantined.
- Vision quality checks are reused. Model inference is private/self-hosted only, with a strict output allowlist and fail-closed abstention; dummy and third-party image outputs are not used.
- Crop and Market currently have native safe adapters pending teammate archives. Their replacement is an explicit follow-up integration, not a claim that missing files were reviewed.

**Update (2026-10-04):** The Crop and Market team archives have since arrived (`agents/crop/crop/`, `agents/market/market/`, plus `crop_agent.zip (1)/`). Both were audited against this PRD and are deliberately **not** wired in; the native safe adapters remain authoritative (see `backend/README.md`).

The attached teammate source archives contained no license files. Get contributor license approval before distributing the package outside the team.
