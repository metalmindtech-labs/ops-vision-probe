# LearnForge — Course Publish Webhook Integration

> **Status**: ⏳ Awaiting `/api/courses` deployment on `learnforge-core.vercel.app`.
> Until this route ships, every Radar publish returns **HTTP 404 → `{"detail":"Not Found"}`** and gets queued for auto-retry (exponential backoff: 2/4/8/16/32 min, max 5 attempts).
>
> Once the route lands and returns any **2xx**, the Radar will flip the signal to `status=live` automatically — no Radar-side code change required.

---

## 1 · Endpoint to deploy

```
POST https://learnforge-core.vercel.app/api/courses
```

That URL is the only thing Radar will hit. If you'd prefer a different path, just set `LEARNFORGE_WEBHOOK_URL` in the Radar's backend env to the new URL — but `/api/courses` is the recommended canonical destination.

---

## 2 · Request headers (sent by Radar on every publish)

| Header              | Value                                                  | Notes                              |
| ------------------- | ------------------------------------------------------ | ---------------------------------- |
| `Content-Type`      | `application/json`                                     |                                    |
| `User-Agent`        | `LearnForge-OpportunityRadar/1.0`                      | Use this to filter logs.           |
| `X-Radar-Event`     | `course.publish`                                       | Discriminator if new events added. |
| `X-Radar-Signature` | `<value of Radar env var LEARNFORGE_WEBHOOK_SECRET>`   | Only sent if secret is configured. |

If you want signature verification, do a **constant-time string compare** of the header value against your stored shared secret. (See drop-in code below.)

---

## 3 · Request body — `course.publish` payload (v1, stable)

```json
{
  "event": "course.publish",
  "signal_id": "1e8a43c8-a6e1-4d29-aa15-e1fedde2ef73",
  "published_at": "2026-05-30T01:24:00Z",
  "course": {
    "slug": "forgecore-mbb-case-mastery",
    "title": "ForgeCore: MBB Case Mastery",
    "category": "Consulting",
    "summary": "8-module mini-course with 12 live cases and feedback.",
    "price_usd": 299,
    "lead_magnet": {
      "title": "The MBB Case Cheat Sheet",
      "description": "10-page distilled framework for case interview structuring.",
      "slug": "the-mbb-case-cheat-sheet",
      "url": "https://learnforge-core.vercel.app/signup?course=the-mbb-case-cheat-sheet&ref=radar&tier=free"
    },
    "cta": {
      "headline": "Land Your MBB Offer",
      "subtext": "Trained by ex-McKinsey EMs. Outcome-tracked.",
      "free_url": "https://learnforge-core.vercel.app/signup?course=the-mbb-case-cheat-sheet&ref=radar&tier=free",
      "paid_url": "https://learnforge-core.vercel.app/signup?course=forgecore-mbb-case-mastery&ref=radar&tier=forgecore"
    },
    "syllabus": {
      "modules": [
        {
          "index": 1,
          "title": "Decode the Case: Structure in 60 Seconds",
          "summary": "Master the MECE framework and rapid case structuring.",
          "learning_objectives": [
            "Apply MECE to any case in under 90 seconds",
            "Build a reusable framework cheat-sheet for the top 5 archetypes"
          ],
          "artifact": "Personal Framework One-Pager",
          "duration_min": 60
        }
      ]
    },
    "demand": {
      "registration_count": 1228,
      "priority_score": 94,
      "source_url": "https://leland.com/events/mbb-case"
    }
  }
}
```

### Field reference

| Path                                      | Type      | Required | Notes                                                                       |
| ----------------------------------------- | --------- | -------- | --------------------------------------------------------------------------- |
| `event`                                   | string    | ✓        | Always `"course.publish"` for v1.                                          |
| `signal_id`                               | uuid      | ✓        | Idempotency key — same signal will be re-sent on retry/republish.           |
| `published_at`                            | ISO-8601  | ✓        | UTC ISO string.                                                             |
| `course.slug`                             | string    | ✓        | URL-safe. Treat as the unique business key for upsert.                      |
| `course.title`                            | string    | ✓        |                                                                             |
| `course.category`                         | string    | ✓        | One of: Consulting, MBA Admissions, Product Management, Finance, Medical Admissions, Law, Tech Careers, Career Switching, Other. |
| `course.summary`                          | string    |          | May be `""`.                                                                |
| `course.price_usd`                        | number\|null |       |                                                                             |
| `course.lead_magnet.{title,description}`  | string    |          |                                                                             |
| `course.lead_magnet.slug`                 | string\|null |       |                                                                             |
| `course.lead_magnet.url`                  | uri\|null |          | Already pre-built `/signup?course=…&tier=free` URL.                         |
| `course.cta.{headline,subtext}`           | string    |          |                                                                             |
| `course.cta.free_url`                     | uri\|null |          |                                                                             |
| `course.cta.paid_url`                     | uri       | ✓        |                                                                             |
| `course.syllabus.modules[]`               | array     | ✓        | Typically 6 modules — but treat as variable length.                         |
| `course.syllabus.modules[].index`         | int ≥ 1   | ✓        |                                                                             |
| `course.syllabus.modules[].title`         | string    | ✓        |                                                                             |
| `course.syllabus.modules[].summary`       | string    | ✓        | 1-2 sentences.                                                              |
| `course.syllabus.modules[].learning_objectives[]` | string[] |     | 2-4 bullets typically.                                                       |
| `course.syllabus.modules[].artifact`      | string    |          | The tangible deliverable for that module.                                   |
| `course.syllabus.modules[].duration_min`  | int       | ✓        |                                                                             |
| `course.demand.registration_count`        | int       | ✓        | Live Leland count at publish time.                                          |
| `course.demand.priority_score`            | int 0-100 | ✓        |                                                                             |
| `course.demand.source_url`                | uri\|null |          |                                                                             |

The Radar will always include all fields above. The contract is **additive-only** going forward — any new field will be added optional first, never required without a major version bump.

---

## 4 · Expected response

### Success (2xx — any 2xx is accepted)
```json
{ "ok": true, "course_id": "lf_2026_05_30_mbb" }
```
- Radar sets `signal.publish_status = published`, `signal.status = live`, clears the retry counter.
- The `course_id` you return is logged for debugging but not required.

### Failure (4xx / 5xx)
- Radar persists `response_preview` (first 400 chars of body) for the dashboard.
- 4xx → retried with exponential backoff (2, 4, 8, 16, 32 minutes — capped at 5 attempts).
- 5xx → same backoff.
- 404 specifically lights up an amber "DEBUG · …" hint in the Radar's PublishResultPanel.

### Idempotency
Treat `signal_id + course.slug` as the upsert key. Radar **will** re-send the same payload on retry, on manual republish, and during the periodic 12-h scraper run if registration counts changed materially.

---

## 5 · Drop-in Next.js App Router route handler (TypeScript)

Save as `app/api/courses/route.ts` in `learnforge-core`:

```ts
import { NextRequest, NextResponse } from "next/server";
import crypto from "node:crypto";
import { z } from "zod";

// ---- Contract -------------------------------------------------------------
const Module = z.object({
    index: z.number().int().min(1),
    title: z.string(),
    summary: z.string(),
    learning_objectives: z.array(z.string()).optional().default([]),
    artifact: z.string().optional().default(""),
    duration_min: z.number().int(),
});

const CoursePublish = z.object({
    event: z.literal("course.publish"),
    signal_id: z.string().uuid(),
    published_at: z.string(),
    course: z.object({
        slug: z.string(),
        title: z.string(),
        category: z.string(),
        summary: z.string().optional().default(""),
        price_usd: z.number().nullable().optional(),
        lead_magnet: z
            .object({
                title: z.string().optional().default(""),
                description: z.string().optional().default(""),
                slug: z.string().nullable().optional(),
                url: z.string().url().nullable().optional(),
            })
            .optional()
            .default({ title: "", description: "" }),
        cta: z.object({
            headline: z.string().optional().default(""),
            subtext: z.string().optional().default(""),
            free_url: z.string().url().nullable().optional(),
            paid_url: z.string().url(),
        }),
        syllabus: z.object({ modules: z.array(Module) }),
        demand: z.object({
            registration_count: z.number().int(),
            priority_score: z.number().int().min(0).max(100),
            source_url: z.string().url().nullable().optional(),
        }),
    }),
});

// ---- Signature ------------------------------------------------------------
function verifySignature(req: NextRequest): boolean {
    const expected = process.env.LEARNFORGE_WEBHOOK_SECRET;
    if (!expected) return true; // signing disabled
    const got = req.headers.get("x-radar-signature") ?? "";
    if (got.length !== expected.length) return false;
    return crypto.timingSafeEqual(Buffer.from(got), Buffer.from(expected));
}

// ---- Handler --------------------------------------------------------------
export async function POST(req: NextRequest) {
    if (!verifySignature(req)) {
        return NextResponse.json({ ok: false, error: "bad signature" }, { status: 401 });
    }

    let body: unknown;
    try {
        body = await req.json();
    } catch {
        return NextResponse.json({ ok: false, error: "invalid json" }, { status: 400 });
    }

    const parsed = CoursePublish.safeParse(body);
    if (!parsed.success) {
        return NextResponse.json(
            { ok: false, error: "invalid payload", issues: parsed.error.issues },
            { status: 422 }
        );
    }
    const { signal_id, course } = parsed.data;

    // TODO(learnforge): replace this with your real upsert.
    // const courseRow = await db.course.upsert({
    //     where: { slug: course.slug },
    //     create: { ...course, signalId: signal_id, modules: { create: course.syllabus.modules } },
    //     update: { ...course, signalId: signal_id, modules: { deleteMany: {}, create: course.syllabus.modules } },
    // });
    console.log("[radar] publish", { signal_id, slug: course.slug, modules: course.syllabus.modules.length });

    return NextResponse.json(
        { ok: true, course_id: `lf_${course.slug}`, signal_id },
        { status: 200 }
    );
}

export const runtime = "nodejs"; // crypto.timingSafeEqual needs Node runtime
```

### Vercel env vars to set on learnforge-core
```
LEARNFORGE_WEBHOOK_SECRET=<shared secret matching Radar's value, or leave unset>
```

---

## 6 · Quick local validation (no Radar required)

Hit the route locally with this curl — should return `{ok: true, ...}`:

```bash
curl -s -X POST http://localhost:3000/api/courses \
  -H "Content-Type: application/json" \
  -H "X-Radar-Event: course.publish" \
  -H "User-Agent: LearnForge-OpportunityRadar/1.0" \
  --data @- <<'JSON' | jq
{
  "event": "course.publish",
  "signal_id": "1e8a43c8-a6e1-4d29-aa15-e1fedde2ef73",
  "published_at": "2026-05-30T01:24:00Z",
  "course": {
    "slug": "forgecore-mbb-case-mastery",
    "title": "ForgeCore: MBB Case Mastery",
    "category": "Consulting",
    "summary": "8-module mini-course.",
    "price_usd": 299,
    "lead_magnet": { "title": "x", "description": "y", "slug": "lm", "url": "https://example.com/signup?course=lm" },
    "cta": {
      "headline": "h",
      "subtext": "s",
      "free_url": "https://example.com/signup?course=lm&tier=free",
      "paid_url": "https://example.com/signup?course=forgecore-mbb-case-mastery&tier=forgecore"
    },
    "syllabus": { "modules": [
      { "index": 1, "title": "m1", "summary": "x", "learning_objectives": ["a"], "artifact": "art", "duration_min": 60 }
    ]},
    "demand": { "registration_count": 1228, "priority_score": 94, "source_url": "https://leland.com/x" }
  }
}
JSON
```

---

## 7 · After deployment — verification checklist

Once the route is live on `learnforge-core.vercel.app`:

1. **Smoke** — On the Radar dashboard, click any signal with a generated syllabus → "Publish to LearnForge". Expected: green `✓ WEBHOOK 2xx` panel, `HTTP 200`, `published_to_url` appears on the row.
2. **Republish all** — Hit the "Republish All" button at the top of the dashboard. Every signal with `syllabus_generated=true` should flip to `status=live` within a few seconds.
3. **Retry recovery** — Past failures with `publish_status=failed` will auto-retry on the backoff schedule; nothing else to do.
4. **Signature** — If you set `LEARNFORGE_WEBHOOK_SECRET`, also set the same value on the Radar via the platform env (key: `LEARNFORGE_WEBHOOK_SECRET`).

That's it. Radar is already sending the canonical payload — the moment the route returns 2xx, the loop closes.

---

## 8 · Contact / change log

- Spec version: **v1** (2026-05-30) — first stable contract.
- All future fields will be **additive** unless we cut a v2 with a new `event` discriminator (e.g. `course.publish.v2`).
- Live machine-readable schema: `GET https://<radar-host>/api/integrations/publish-payload-spec` returns `{ schema, example, request_headers, expected_response, webhook_url }`.
