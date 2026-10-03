// WP1.1 — chain identity & normalization.
//
// Identity is built only from the structured, controlled-vocabulary `semantics`
// tuple on each transition, plus the target environment. Prose, titles, resource
// IDs, repository names, harness/model, path revision, and transitions flagged
// `semantics.incidental` are excluded. Consecutive duplicate tuples collapse so a
// repeated step does not change identity.

export const FINGERPRINT_VERSION = "v1";

const TUPLE_KEYS = [
  "actorRole",
  "resourceRelation",
  "surface",
  "operation",
  "boundaryType",
  "violation",
];

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

const tupleKey = (t) => TUPLE_KEYS.map((k) => t[k]).join("\u0001");

// Returns the normalized tuple list (order preserved, consecutive duplicates
// collapsed), or null when identity cannot be established.
export function normalizeChain(chain) {
  if (!Array.isArray(chain) || chain.length === 0) return null;
  const tuples = [];
  for (const transition of chain) {
    const r = normalizeTransition(transition);
    if (!r.ok) return null;
    if (r.skip) continue;
    if (
      tuples.length &&
      tupleKey(tuples[tuples.length - 1]) === tupleKey(r.tuple)
    )
      continue;
    tuples.push(r.tuple);
  }
  return tuples.length === 0 ? null : tuples;
}

const normEnv = (env) =>
  String(env ?? "")
    .trim()
    .toLowerCase();

export function fingerprint(chain, environment) {
  const normalized = normalizeChain(chain);
  const env = normEnv(environment);
  if (normalized === null || env === "") return null;
  return `${FINGERPRINT_VERSION}:${JSON.stringify({ env, chain: normalized })}`;
}

export function sameIdentity(chainA, envA, chainB, envB) {
  const a = fingerprint(chainA, envA);
  const b = fingerprint(chainB, envB);
  return a !== null && a === b;
}

// True when `short` is a (contiguous or sparse) subsequence of `long`, order kept.
// Used to detect a partial/overlapping chain that is related but not identical,
// which routes to triage rather than a speculative new ticket (E1-18).
export function isSubsequence(short, long) {
  if (!Array.isArray(short) || !Array.isArray(long) || short.length === 0)
    return false;
  let i = 0;
  for (const t of long) {
    if (tupleKey(t) === tupleKey(short[i])) i++;
    if (i === short.length) return true;
  }
  return i === short.length;
}

export { normEnv };
