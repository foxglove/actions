// WP1.1 — chain identity & normalization.
//
// Identity is built only from the structured, controlled-vocabulary `semantics`
// tuple on each transition, plus the target environment. Prose fields, titles,
// resource IDs, repository names, harness/model, path revision, and transitions
// flagged `incidental` (reconnaissance) are excluded from matching
// (exploit-findings.md: "do not invent an identity from a title or prose hash";
// the matching core "excludes ... incidental reconnaissance").

export const FINGERPRINT_VERSION = "v1";

const TUPLE_KEYS = [
  "actorRole",
  "resourceRelation",
  "surface",
  "operation",
  "boundaryType",
  "violation",
];

// Returns { ok:false } on absent/invalid semantics, { ok:true, skip:true } for an
// incidental (recon) transition to drop, or { ok:true, tuple } otherwise.
export function normalizeTransition(transition) {
  const s = transition && transition.semantics;
  if (!s || typeof s !== "object" || Array.isArray(s)) return { ok: false };
  if (s.incidental === true) return { ok: true, skip: true };
  const tuple = {};
  for (const key of TUPLE_KEYS) {
    const value = s[key];
    if (typeof value !== "string" || value.trim() === "") return { ok: false };
    tuple[key] = value.trim().toLowerCase();
  }
  return { ok: true, tuple };
}

// Normalize an ordered chain to its causally-relevant tuples (order preserved),
// or null when identity cannot be established (missing semantics, or only
// incidental transitions).
export function normalizeChain(chain) {
  if (!Array.isArray(chain) || chain.length === 0) return null;
  const tuples = [];
  for (const transition of chain) {
    const r = normalizeTransition(transition);
    if (!r.ok) return null;
    if (!r.skip) tuples.push(r.tuple);
  }
  return tuples.length === 0 ? null : tuples;
}

const normEnv = (env) =>
  String(env ?? "")
    .trim()
    .toLowerCase();

// Versioned fingerprint over { env, normalized chain }. A lookup aid, not proof of
// equivalence. null when identity cannot be established. Environment is part of
// identity so a production observation never merges into a party ticket.
export function fingerprint(chain, environment) {
  const normalized = normalizeChain(chain);
  if (normalized === null) return null;
  return `${FINGERPRINT_VERSION}:${JSON.stringify({ env: normEnv(environment), chain: normalized })}`;
}

export function sameIdentity(chainA, envA, chainB, envB) {
  const a = fingerprint(chainA, envA);
  const b = fingerprint(chainB, envB);
  return a !== null && a === b;
}
