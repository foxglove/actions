// WP1.1 — chain identity & normalization.
//
// Identity is built only from the structured, controlled-vocabulary `semantics`
// tuple on each transition. Prose fields, titles, resource IDs, repository names,
// harness/model, and path revision are excluded from matching (exploit-findings.md:
// "do not invent an identity from a title or prose hash").
//
// Target environment is part of the identity but is constant ("party") in the first
// release, so it is excluded from the v1 fingerprint and documented here instead.

export const FINGERPRINT_VERSION = "v1";

const TUPLE_KEYS = [
  "actorRole",
  "resourceRelation",
  "surface",
  "operation",
  "boundaryType",
  "violation",
];

// Canonicalize one transition's semantics into an ordered tuple, or null when the
// structured semantics are absent/incomplete (identity cannot be established).
export function normalizeTransition(transition) {
  const s = transition && transition.semantics;
  if (!s) return null;
  const tuple = {};
  for (const key of TUPLE_KEYS) {
    const value = s[key];
    if (value === undefined || value === null || String(value).trim() === "") {
      return null;
    }
    tuple[key] = String(value).trim().toLowerCase();
  }
  return tuple;
}

// Normalize an ordered chain. Order is semantic (prerequisite ordering), so it is
// preserved. Returns null when any transition lacks structured semantics.
export function normalizeChain(chain) {
  if (!Array.isArray(chain) || chain.length === 0) return null;
  const tuples = chain.map(normalizeTransition);
  if (tuples.some((t) => t === null)) return null;
  return tuples;
}

// Versioned fingerprint of the normalized chain. A lookup aid, not proof of
// equivalence. null when identity cannot be established.
export function fingerprint(chain) {
  const normalized = normalizeChain(chain);
  if (normalized === null) return null;
  return `${FINGERPRINT_VERSION}:${JSON.stringify(normalized)}`;
}

// Two chains share identity when both normalize and their fingerprints are equal.
export function sameIdentity(chainA, chainB) {
  const a = fingerprint(chainA);
  const b = fingerprint(chainB);
  return a !== null && a === b;
}
