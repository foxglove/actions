const fs = require("node:fs");
const path = require("node:path");

// Keep in sync with the juror matrix in .github/workflows/review.yml.
const JURORS = [
  { id: "opus", name: "Opus" },
  { id: "astra", name: "Astra" },
  { id: "grok", name: "Grok" },
];
const MAJORITY = Math.floor(JURORS.length / 2) + 1;

// Every comment and review the jury posts carries this marker, so later runs can tell jury
// threads apart from other text that the workflow token posts.
const MARKER = "<!-- foxglove-review-jury -->";
const JURY_AUTHORS = new Set(["github-actions"]);
// The single-model reviewer that the jury replaced. The jury resolves and minimizes its
// threads and reviews as its own, so open pull requests keep working across the change.
const LEGACY_AUTHORS = new Set(["claude"]);
const MAX_BODY_LENGTH = 60000;
const CLERK_BODY_LENGTH = 3000;

const THREADS_QUERY = `
  query ($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) {
        reviewThreads(first: 50, after: $cursor) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            id
            isResolved
            isOutdated
            path
            line
            startLine
            diffSide
            comments(first: 100) {
              nodes {
                author {
                  login
                }
                body
                createdAt
                pullRequestReview {
                  id
                }
              }
            }
          }
        }
      }
    }
  }
`;

const REVIEWS_QUERY = `
  query ($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) {
        reviews(first: 100, after: $cursor) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            id
            author {
              login
            }
            body
            state
            submittedAt
            isMinimized
            commit {
              oid
            }
          }
        }
      }
    }
  }
`;

const ADD_PENDING_REVIEW_MUTATION = `
  mutation ($pullRequestId: ID!, $commitOID: GitObjectID!) {
    addPullRequestReview(input: { pullRequestId: $pullRequestId, commitOID: $commitOID }) {
      pullRequestReview {
        id
      }
    }
  }
`;

const ADD_THREAD_MUTATION = `
  mutation ($input: AddPullRequestReviewThreadInput!) {
    addPullRequestReviewThread(input: $input) {
      thread {
        id
      }
    }
  }
`;

const SUBMIT_REVIEW_MUTATION = `
  mutation ($pullRequestReviewId: ID!, $body: String!) {
    submitPullRequestReview(
      input: { pullRequestReviewId: $pullRequestReviewId, event: COMMENT, body: $body }
    ) {
      pullRequestReview {
        id
        url
      }
    }
  }
`;

const DELETE_REVIEW_MUTATION = `
  mutation ($pullRequestReviewId: ID!) {
    deletePullRequestReview(input: { pullRequestReviewId: $pullRequestReviewId }) {
      clientMutationId
    }
  }
`;

const REPLY_MUTATION = `
  mutation ($threadId: ID!, $body: String!) {
    addPullRequestReviewThreadReply(input: { pullRequestReviewThreadId: $threadId, body: $body }) {
      comment {
        id
      }
    }
  }
`;

const RESOLVE_THREAD_MUTATION = `
  mutation ($threadId: ID!) {
    resolveReviewThread(input: { threadId: $threadId }) {
      thread {
        isResolved
      }
    }
  }
`;

const MINIMIZE_MUTATION = `
  mutation ($subjectId: ID!) {
    minimizeComment(input: { subjectId: $subjectId, classifier: OUTDATED }) {
      minimizedComment {
        isMinimized
      }
    }
  }
`;

// Claude Opus 5.5 rejects forced tool use, so the clerk returns structured output instead.
const CLERK_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["groups"],
  properties: {
    groups: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["ids", "keep"],
        properties: {
          ids: { type: "array", items: { type: "string" } },
          keep: { anyOf: [{ type: "string" }, { type: "null" }] },
        },
      },
    },
  },
};

const CLERK_INSTRUCTIONS = `You remove duplicate findings for a code review jury. Several reviewers reviewed the same pull request independently, so some items describe the same issue in different words or on a nearby line.

Group the items that describe the same issue: the same defect, risk, question, or requested change. Only group items that have the same "location". Do not group items that describe different issues, even when they are on the same line. Do not judge whether an item is correct.

Items with "source": "existing" are already on the pull request. Put a new item in the group of an existing item when the existing item already covers the issue.

Put each item id in exactly one group. A group can have one item. For each group, set "keep" to the id of the new item that states the issue most clearly and completely. Set "keep" to null when the group has no new item.`;

function jurorName(id) {
  return JURORS.find((juror) => juror.id === id)?.name ?? id;
}

function jurorOrder(id) {
  const index = JURORS.findIndex((juror) => juror.id === id);
  return index === -1 ? JURORS.length : index;
}

function loginOf(author) {
  return (author?.login ?? "").replace(/\[bot\]$/, "");
}

function isJuryText(author, body) {
  return (
    (JURY_AUTHORS.has(author) && (body ?? "").includes(MARKER)) ||
    LEGACY_AUTHORS.has(author)
  );
}

function truncate(text, limit) {
  return text.length <= limit
    ? text
    : `${text.slice(0, limit)}\n\n(Truncated.)`;
}

function stripMarker(body) {
  return (body ?? "").split(MARKER).join("").trim();
}

function joinNames(names) {
  if (names.length <= 1) {
    return names.join("");
  }
  return `${names.slice(0, -1).join(", ")} and ${names.at(-1)}`;
}

function groupBy(items, keyOf) {
  const groups = new Map();
  for (const item of items) {
    const key = keyOf(item);
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  return groups;
}

// Jurors read untrusted PR content and can run commands next to their API keys, so a prompt
// injection could make one copy a key into its verdict. Nothing that a juror wrote is stored
// or published before this filter removes the configured secrets and token-shaped strings.
const TOKEN_PATTERN =
  /\b(?:sk-ant-|sk-|xai-)[A-Za-z0-9_-]{20,}|\bgh[pousr]_[A-Za-z0-9]{20,}/g;

function redactSecrets(text, secrets = []) {
  let result = text;
  for (const secret of secrets) {
    if (typeof secret === "string" && secret.length >= 8) {
      result = result.split(secret).join("[redacted]");
    }
  }
  return result.replace(TOKEN_PATTERN, "[redacted]");
}

function redactVerdict(verdict, secrets) {
  const redact = (text) => redactSecrets(text, secrets);
  return {
    fixed_threads: verdict.fixed_threads.map((entry) => ({
      ...entry,
      reply: redact(entry.reply),
    })),
    thread_replies: verdict.thread_replies.map((entry) => ({
      ...entry,
      body: redact(entry.body),
    })),
    comments: verdict.comments.map((comment) => ({
      ...comment,
      path: redact(comment.path),
      body: redact(comment.body),
    })),
    lgtm: verdict.lgtm,
  };
}

// People and tools search review bodies for LGTM, so juror text that the body quotes must not
// add the token when the jury did not vote for it.
function withoutLgtm(text) {
  return text.replace(/\bLGTM\b/gi, "looks good to me");
}

// Diff and placement

function parsePatch(patch) {
  if (typeof patch !== "string" || patch === "") {
    return null;
  }
  const lines = { RIGHT: new Map(), LEFT: new Map() };
  let oldLine = 0;
  let newLine = 0;
  let hunk = -1;
  for (const raw of patch.split("\n")) {
    const header = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(raw);
    if (header) {
      oldLine = Number(header[1]);
      newLine = Number(header[2]);
      hunk += 1;
      continue;
    }
    if (hunk < 0 || raw === "" || raw.startsWith("\\")) {
      continue;
    }
    if (raw.startsWith("+")) {
      lines.RIGHT.set(newLine++, hunk);
    } else if (raw.startsWith("-")) {
      lines.LEFT.set(oldLine++, hunk);
    } else {
      lines.RIGHT.set(newLine++, hunk);
      lines.LEFT.set(oldLine++, hunk);
    }
  }
  return lines;
}

function indexFiles(files) {
  return new Map(
    files.map((file) => [file.filename, { lines: parsePatch(file.patch) }]),
  );
}

function normalizePath(filePath) {
  return filePath
    .trim()
    .replace(/^(\.\/)+/, "")
    .replace(/^\/+/, "");
}

function lineLabel({ line, startLine, side }) {
  const range =
    startLine != null && startLine < line
      ? `Lines ${startLine}-${line}`
      : `Line ${line}`;
  return side === "LEFT" ? `**${range} (base version)**` : `**${range}**`;
}

// Decides where a juror comment can go. GitHub rejects a line comment outside the diff, so
// such a comment becomes a file comment that names the line. A comment on a file that the
// pull request does not change goes in the review body.
function placeComment(comment, filesByPath) {
  const filePath = normalizePath(comment.path);
  const body = comment.body.trim();
  const side = comment.side === "LEFT" ? "LEFT" : "RIGHT";
  const line = comment.line ?? null;
  const startLine = line == null ? null : (comment.start_line ?? null);
  const file = filesByPath.get(filePath);
  if (!file) {
    return {
      placement: "outside",
      path: filePath,
      line,
      startLine,
      side,
      body,
    };
  }
  if (line == null) {
    return {
      placement: "thread",
      subjectType: "FILE",
      path: filePath,
      line: null,
      body,
    };
  }
  const hunk = file.lines?.[side].get(line);
  if (hunk === undefined) {
    return {
      placement: "thread",
      subjectType: "FILE",
      path: filePath,
      line,
      body: `${lineLabel({ line, startLine, side })}\n\n${body}`,
    };
  }
  const validStart =
    startLine != null &&
    startLine < line &&
    file.lines[side].get(startLine) === hunk
      ? startLine
      : null;
  return {
    placement: "thread",
    subjectType: "LINE",
    path: filePath,
    line,
    startLine: validStart,
    side,
    body,
  };
}

// Verdicts

function parseJson(text) {
  if (typeof text !== "string") {
    return undefined;
  }
  const trimmed = text.trim();
  const fenced = /^```(?:json)?\s*\n([\s\S]*?)\n?```$/.exec(trimmed);
  try {
    return JSON.parse(fenced ? fenced[1] : trimmed);
  } catch {
    return undefined;
  }
}

function isPositiveInteger(value) {
  return Number.isInteger(value) && value > 0;
}

function validateThreadEntries(value, name, textField) {
  const entries = value[name] ?? [];
  if (!Array.isArray(entries)) {
    return { error: `\`${name}\` is not an array.` };
  }
  const result = [];
  for (const [index, entry] of entries.entries()) {
    if (
      entry == null ||
      typeof entry.thread_id !== "string" ||
      entry.thread_id === "" ||
      typeof entry[textField] !== "string" ||
      entry[textField].trim() === ""
    ) {
      return {
        error: `${name}[${index}] needs a thread_id and a ${textField}.`,
      };
    }
    result.push({ thread_id: entry.thread_id, [textField]: entry[textField] });
  }
  return { entries: result };
}

function validateVerdict(value) {
  if (value == null || typeof value !== "object" || Array.isArray(value)) {
    return { ok: false, error: "The verdict is not a JSON object." };
  }
  if (typeof value.lgtm !== "boolean") {
    return { ok: false, error: "`lgtm` is not a boolean." };
  }
  if (!Array.isArray(value.comments)) {
    return { ok: false, error: "`comments` is not an array." };
  }
  const comments = [];
  for (const [index, comment] of value.comments.entries()) {
    const where = `comments[${index}]`;
    if (comment == null || typeof comment !== "object") {
      return { ok: false, error: `${where} is not an object.` };
    }
    if (typeof comment.path !== "string" || comment.path.trim() === "") {
      return { ok: false, error: `${where}.path is empty.` };
    }
    if (typeof comment.body !== "string" || comment.body.trim() === "") {
      return { ok: false, error: `${where}.body is empty.` };
    }
    if (comment.line != null && !isPositiveInteger(comment.line)) {
      return {
        ok: false,
        error: `${where}.line is not a positive integer or null.`,
      };
    }
    if (comment.start_line != null && !isPositiveInteger(comment.start_line)) {
      return {
        ok: false,
        error: `${where}.start_line is not a positive integer or null.`,
      };
    }
    if (
      comment.side != null &&
      comment.side !== "RIGHT" &&
      comment.side !== "LEFT"
    ) {
      return { ok: false, error: `${where}.side is not RIGHT or LEFT.` };
    }
    comments.push({
      path: comment.path,
      line: comment.line ?? null,
      start_line: comment.line == null ? null : (comment.start_line ?? null),
      side: comment.side ?? "RIGHT",
      body: comment.body,
    });
  }
  const fixed = validateThreadEntries(value, "fixed_threads", "reply");
  if (fixed.error) {
    return { ok: false, error: fixed.error };
  }
  const replies = validateThreadEntries(value, "thread_replies", "body");
  if (replies.error) {
    return { ok: false, error: replies.error };
  }
  return {
    ok: true,
    verdict: {
      fixed_threads: fixed.entries,
      thread_replies: replies.entries,
      comments,
      lgtm: value.lgtm,
    },
  };
}

// Accepts a bare verdict (Claude Code structured output, Codex final message) or the JSON
// envelope that Grok Build prints in headless mode.
function extractVerdict(raw) {
  const parsed = parseJson(raw);
  if (parsed === undefined) {
    return { ok: false, error: "The output is not JSON." };
  }
  const candidates = [
    parsed,
    parsed?.structured_output,
    parsed?.structuredOutput,
    parsed?.result?.structured_output,
    parsed?.text,
  ];
  let firstError = null;
  for (const candidate of candidates) {
    const value =
      typeof candidate === "string" ? parseJson(candidate) : candidate;
    if (value == null || typeof value !== "object" || !("lgtm" in value)) {
      continue;
    }
    const result = validateVerdict(value);
    if (result.ok) {
      return result;
    }
    firstError ??= result.error;
  }
  return {
    ok: false,
    error: firstError ?? "The output has no verdict object.",
  };
}

function recordJurorResult(env) {
  const juror = JURORS.find((candidate) => candidate.id === env.JUROR);
  if (!juror) {
    throw new Error(`Unknown juror: ${env.JUROR}`);
  }
  let result;
  if (env.AVAILABLE !== "true") {
    result = {
      juror: juror.id,
      status: "absent",
      reason: `The caller did not pass \`${env.MISSING_SECRET}\`.`,
    };
  } else if (env.SUCCEEDED !== "true") {
    result = {
      juror: juror.id,
      status: "failed",
      reason: "The review did not finish.",
    };
  } else {
    const raw = fs.existsSync(env.VERDICT_FILE)
      ? fs.readFileSync(env.VERDICT_FILE, "utf8")
      : "";
    const extracted = extractVerdict(raw);
    const secrets = [
      env.ANTHROPIC_API_KEY,
      env.OPENAI_API_KEY,
      env.XAI_API_KEY,
    ];
    result = extracted.ok
      ? {
          juror: juror.id,
          status: "voted",
          verdict: redactVerdict(extracted.verdict, secrets),
        }
      : {
          juror: juror.id,
          status: "failed",
          reason: `The review result is not valid. ${extracted.error}`,
        };
  }
  fs.mkdirSync(path.dirname(env.RESULT_FILE), { recursive: true });
  fs.writeFileSync(env.RESULT_FILE, `${JSON.stringify(result, null, 2)}\n`);
  if (env.GITHUB_OUTPUT) {
    fs.appendFileSync(env.GITHUB_OUTPUT, `status=${result.status}\n`);
  }
  return result;
}

function readJurorResults(directory, secrets = []) {
  const results = new Map();
  for (const juror of JURORS) {
    const file = path.join(directory, `${juror.id}.json`);
    let result = null;
    if (fs.existsSync(file)) {
      try {
        result = JSON.parse(fs.readFileSync(file, "utf8"));
      } catch {
        result = null;
      }
    }
    if (result?.status === "voted") {
      const validated = validateVerdict(result.verdict);
      result = validated.ok
        ? { ...result, verdict: redactVerdict(validated.verdict, secrets) }
        : {
            juror: juror.id,
            status: "failed",
            reason: "The review result is not valid.",
          };
    }
    if (!result || !["voted", "absent", "failed"].includes(result.status)) {
      result = {
        juror: juror.id,
        status: "failed",
        reason: "The juror job did not return a result.",
      };
    }
    results.set(juror.id, result);
  }
  return results;
}

function tallyVotes(results) {
  const entries = JURORS.map((juror) => {
    const result = results.get(juror.id) ?? { status: "failed" };
    const comments = result.verdict?.comments.length ?? 0;
    return {
      juror: juror.id,
      name: juror.name,
      status: result.status,
      reason: result.reason ?? null,
      comments,
      // A vote for LGTM that still raises comments contradicts itself, so it does not count.
      approves:
        result.status === "voted" && result.verdict.lgtm && comments === 0,
    };
  });
  const approvals = entries.filter((entry) => entry.approves).length;
  return { entries, approvals, lgtm: approvals >= MAJORITY };
}

// Duplicate removal

async function askClerk({
  items,
  apiKey,
  model,
  fetchImpl = fetch,
  timeoutMs = 60000,
}) {
  const response = await fetchImpl("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model,
      // Thinking cannot be turned off, and it counts against max_tokens.
      max_tokens: 16000,
      output_config: {
        effort: "low",
        format: { type: "json_schema", schema: CLERK_SCHEMA },
      },
      messages: [
        {
          role: "user",
          content: `${CLERK_INSTRUCTIONS}\n\nItems:\n${JSON.stringify(items, null, 2)}`,
        },
      ],
    }),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) {
    throw new Error(
      `The Anthropic API returned ${response.status}: ${await response.text()}`,
    );
  }
  const data = await response.json();
  if (data.stop_reason !== "end_turn") {
    throw new Error(`The clerk stopped with ${data.stop_reason}.`);
  }
  const text = data.content?.find((block) => block.type === "text")?.text;
  const groups = parseJson(text)?.groups;
  if (!Array.isArray(groups)) {
    throw new Error("The clerk response has no groups.");
  }
  return groups;
}

function createClerk({ apiKey, model, fetchImpl, attempts = 2 }) {
  return async (items) => {
    let lastError;
    for (let attempt = 1; attempt <= attempts; attempt++) {
      try {
        return await askClerk({ items, apiKey, model, fetchImpl });
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError;
  };
}

function normalizeText(text) {
  return stripMarker(text)
    .replace(/<sub>[\s\S]*?<\/sub>/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

// `findings` are new items from jurors and `existing` are items already on the pull request.
// Each item has an `id` and a `key`, and only items with the same key can be duplicates.
// Returns one entry for each distinct new finding, with the jurors that raised it.
async function dedupeFindings({ findings, existing = [], clerk, core }) {
  const all = [
    ...findings.map((item) => ({ ...item, isNew: true })),
    ...existing,
  ];
  const byId = new Map(all.map((item) => [item.id, item]));
  const parent = new Map(all.map((item) => [item.id, item.id]));
  const find = (id) => {
    while (parent.get(id) !== id) {
      parent.set(id, parent.get(parent.get(id)));
      id = parent.get(id);
    }
    return id;
  };
  const union = (a, b) => parent.set(find(a), find(b));
  const byKey = groupBy(all, (item) => item.key);

  const contested = [...byKey.values()]
    .filter((items) => items.length >= 2 && items.some((item) => item.isNew))
    .flat();
  let groups = null;
  if (contested.length > 0 && clerk) {
    try {
      groups = await clerk(
        contested.map((item) => ({
          id: item.id,
          location: item.key,
          line: item.line ?? null,
          source: item.isNew ? "new" : "existing",
          body: truncate(stripMarker(item.body), CLERK_BODY_LENGTH),
        })),
      );
    } catch (error) {
      core?.warning(
        `Semantic duplicate removal failed, so only identical comments are merged: ${error.message}`,
      );
    }
  }

  const kept = new Set();
  if (groups) {
    for (const group of groups) {
      const ids = (Array.isArray(group?.ids) ? group.ids : []).filter((id) =>
        byId.has(id),
      );
      for (const sameKey of groupBy(ids, (id) => byId.get(id).key).values()) {
        for (const id of sameKey.slice(1)) {
          union(id, sameKey[0]);
        }
      }
      if (ids.includes(group.keep) && byId.get(group.keep).isNew) {
        kept.add(group.keep);
      }
    }
  } else {
    for (const items of byKey.values()) {
      for (const sameText of groupBy(items, (item) =>
        normalizeText(item.body),
      ).values()) {
        for (const item of sameText.slice(1)) {
          union(item.id, sameText[0].id);
        }
      }
    }
  }

  const deduped = [];
  let covered = 0;
  for (const cluster of groupBy(all, (item) => find(item.id)).values()) {
    const fresh = cluster
      .filter((item) => item.isNew)
      .sort((a, b) => a.order - b.order);
    if (fresh.length === 0) {
      continue;
    }
    if (fresh.length !== cluster.length) {
      covered += fresh.length;
      continue;
    }
    const { isNew, ...representative } =
      fresh.find((item) => kept.has(item.id)) ?? fresh[0];
    const jurors = [...new Set(fresh.map((item) => item.juror))].sort(
      (a, b) => jurorOrder(a) - jurorOrder(b),
    );
    deduped.push({ ...representative, jurors });
  }
  deduped.sort((a, b) => a.order - b.order);
  return {
    findings: deduped,
    covered,
    merged: findings.length - covered - deduped.length,
  };
}

// Formatting

function jurorLabel(jurors) {
  const names = jurors.map(jurorName);
  return `<sub>${names.length === 1 ? "Juror" : "Jurors"}: ${names.join(", ")}</sub>`;
}

function attributedBody(body, jurors) {
  return `${truncate(body.trim(), MAX_BODY_LENGTH)}\n\n${jurorLabel(jurors)}\n${MARKER}`;
}

function describeVote(entry) {
  switch (entry.status) {
    case "voted":
      if (entry.approves) {
        return "approves.";
      }
      return entry.comments > 0
        ? `does not approve (${entry.comments} ${entry.comments === 1 ? "comment" : "comments"}).`
        : "does not approve.";
    case "absent":
      return `did not vote. ${entry.reason}`;
    default:
      return `did not vote. ${entry.reason ?? "The review did not finish."}`;
  }
}

function formatFindingSection(finding) {
  const where = finding.line != null ? ` line ${finding.line}` : "";
  const body = withoutLgtm(truncate(finding.body.trim(), MAX_BODY_LENGTH));
  return `#### \`${withoutLgtm(finding.path)}\`${where}\n\n${body}\n\n${jurorLabel(finding.jurors)}`;
}

// The review body says LGTM only for a majority. Other bodies must not contain that token,
// because people and tools search review bodies for it.
function formatReviewBody({ tally, outside = [], unplaced = [] }) {
  const parts = [];
  if (tally.lgtm) {
    parts.push("LGTM");
  }
  const need = tally.lgtm ? "" : ` Approval needs ${MAJORITY}.`;
  const votes = tally.entries.map(
    (entry) => `- ${entry.name}: ${describeVote(entry)}`,
  );
  parts.push(
    `Jury vote: ${tally.approvals} of ${JURORS.length} approve.${need}\n\n${votes.join("\n")}`,
  );
  if (outside.length > 0) {
    parts.push(
      [
        "### Findings on files that this pull request does not change",
        ...outside.map(formatFindingSection),
      ].join("\n\n"),
    );
  }
  if (unplaced.length > 0) {
    parts.push(
      [
        "### Findings that GitHub did not accept as review comments",
        ...unplaced.map(formatFindingSection),
      ].join("\n\n"),
    );
  }
  return `${truncate(parts.join("\n\n"), MAX_BODY_LENGTH)}\n\n${MARKER}`;
}

// The thread inputs to try for a finding, in order. A line comment falls back to a file
// comment that names the line, for when GitHub does not accept the line.
function threadInputs(finding) {
  const fileThread = (body) => ({
    path: finding.path,
    body: attributedBody(body, finding.jurors),
    subjectType: "FILE",
  });
  if (finding.subjectType === "FILE") {
    return [fileThread(finding.body)];
  }
  const lineThread = {
    path: finding.path,
    body: attributedBody(finding.body, finding.jurors),
    subjectType: "LINE",
    line: finding.line,
    side: finding.side,
  };
  if (finding.startLine != null) {
    lineThread.startLine = finding.startLine;
    lineThread.startSide = finding.side;
  }
  return [lineThread, fileThread(`${lineLabel(finding)}\n\n${finding.body}`)];
}

// GitHub state

async function paginateGraphql(github, query, variables, select) {
  const nodes = [];
  let cursor = null;
  do {
    const connection = select(
      await github.graphql(query, { ...variables, cursor }),
    );
    nodes.push(...connection.nodes);
    cursor = connection.pageInfo.hasNextPage
      ? connection.pageInfo.endCursor
      : null;
  } while (cursor);
  return nodes;
}

async function fetchReviewState({ github, owner, repo, number }) {
  const variables = { owner, repo, number };
  const [threadNodes, reviewNodes, issueComments] = await Promise.all([
    paginateGraphql(
      github,
      THREADS_QUERY,
      variables,
      (data) => data.repository.pullRequest.reviewThreads,
    ),
    paginateGraphql(
      github,
      REVIEWS_QUERY,
      variables,
      (data) => data.repository.pullRequest.reviews,
    ),
    github.paginate(github.rest.issues.listComments, {
      owner,
      repo,
      issue_number: number,
      per_page: 100,
    }),
  ]);
  const threads = threadNodes.map((thread) => {
    const comments = thread.comments.nodes.map((comment) => {
      const author = loginOf(comment.author);
      return {
        author,
        body: comment.body,
        createdAt: comment.createdAt,
        reviewId: comment.pullRequestReview?.id ?? null,
        jury: isJuryText(author, comment.body),
      };
    });
    return {
      id: thread.id,
      isResolved: thread.isResolved,
      isOutdated: thread.isOutdated,
      path: thread.path,
      line: thread.line,
      startLine: thread.startLine,
      side: thread.diffSide,
      jury: comments.length > 0 && comments[0].jury,
      comments,
    };
  });
  const reviews = reviewNodes
    .filter((review) => review.state !== "PENDING")
    .map((review) => {
      const author = loginOf(review.author);
      return {
        id: review.id,
        author,
        body: review.body ?? "",
        state: review.state,
        submittedAt: review.submittedAt,
        isMinimized: review.isMinimized,
        commitId: review.commit?.oid ?? null,
        jury: isJuryText(author, review.body),
      };
    });
  return {
    threads,
    reviews,
    issueComments: issueComments.map((comment) => ({
      author: loginOf(comment.user),
      body: comment.body ?? "",
      createdAt: comment.created_at,
    })),
  };
}

function buildJurorContext({ pullRequest, state }) {
  const juryReviews = state.reviews
    .filter((review) => review.jury && review.commitId && review.submittedAt)
    .sort((a, b) => a.submittedAt.localeCompare(b.submittedAt));
  return {
    pull_request: {
      number: pullRequest.number,
      title: pullRequest.title,
      body: pullRequest.body ?? "",
      author: loginOf(pullRequest.user),
      base_branch: pullRequest.base.ref,
      head_sha: pullRequest.head.sha,
      draft: Boolean(pullRequest.draft),
    },
    last_jury_review_commit: juryReviews.at(-1)?.commitId ?? null,
    reviews: state.reviews.map((review) => ({
      author: review.author,
      jury: review.jury,
      state: review.state,
      commit_id: review.commitId,
      submitted_at: review.submittedAt,
      body: review.body,
    })),
    review_threads: state.threads.map((thread) => ({
      id: thread.id,
      jury: thread.jury,
      is_resolved: thread.isResolved,
      is_outdated: thread.isOutdated,
      path: thread.path,
      line: thread.line,
      start_line: thread.startLine,
      side: thread.side,
      comments: thread.comments.map((comment) => ({
        author: comment.author,
        jury: comment.jury,
        created_at: comment.createdAt,
        body: comment.body,
      })),
    })),
    issue_comments: state.issueComments.map((comment) => ({
      author: comment.author,
      created_at: comment.createdAt,
      body: comment.body,
    })),
  };
}

async function writeJurorContext({ github, context, core, file }) {
  const pullRequest = context.payload.pull_request;
  if (!pullRequest) {
    throw new Error("The review jury runs only on pull_request events.");
  }
  const state = await fetchReviewState({
    github,
    owner: context.repo.owner,
    repo: context.repo.repo,
    number: pullRequest.number,
  });
  const jurorContext = buildJurorContext({ pullRequest, state });
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(jurorContext, null, 2)}\n`);
  core.info(
    `Wrote the PR context: ${jurorContext.reviews.length} reviews, ${jurorContext.review_threads.length} review threads, ${jurorContext.issue_comments.length} conversation comments.`,
  );
}

// Publishing

function votedJurors(results) {
  return JURORS.filter(
    (juror) => results.get(juror.id)?.status === "voted",
  ).map((juror) => ({
    ...juror,
    verdict: results.get(juror.id).verdict,
  }));
}

// A juror can only hold one pending review on a pull request, so a pending review that an
// earlier run left behind would block this one.
async function deletePendingReviews({ github, owner, repo, number, core }) {
  const reviews = await github.paginate(github.rest.pulls.listReviews, {
    owner,
    repo,
    pull_number: number,
    per_page: 100,
  });
  for (const review of reviews) {
    if (review.state !== "PENDING" || !JURY_AUTHORS.has(loginOf(review.user))) {
      continue;
    }
    try {
      await github.rest.pulls.deletePendingReview({
        owner,
        repo,
        pull_number: number,
        review_id: review.id,
      });
      core.info(`Deleted pending review ${review.id}.`);
    } catch (error) {
      core.warning(
        `Could not delete pending review ${review.id}: ${error.message}`,
      );
    }
  }
}

async function resolveFixedThreads({ github, results, threadsById, core }) {
  const votes = new Map();
  for (const juror of votedJurors(results)) {
    const seen = new Set();
    for (const entry of juror.verdict.fixed_threads) {
      if (!seen.has(entry.thread_id)) {
        seen.add(entry.thread_id);
        votes.set(entry.thread_id, [
          ...(votes.get(entry.thread_id) ?? []),
          { juror, entry },
        ]);
      }
    }
  }
  const resolved = new Set();
  for (const [threadId, threadVotes] of votes) {
    const thread = threadsById.get(threadId);
    if (!thread?.jury || thread.isResolved || threadVotes.length < MAJORITY) {
      continue;
    }
    const jurors = threadVotes.map((vote) => vote.juror.id);
    try {
      await github.graphql(REPLY_MUTATION, {
        threadId,
        body: attributedBody(threadVotes[0].entry.reply, jurors),
      });
      await github.graphql(RESOLVE_THREAD_MUTATION, { threadId });
      resolved.add(threadId);
      core.info(
        `Resolved thread ${threadId}. ${joinNames(jurors.map(jurorName))} report it fixed.`,
      );
    } catch (error) {
      core.warning(`Could not resolve thread ${threadId}: ${error.message}`);
    }
  }
  return resolved;
}

function replyFindings({ results, threadsById, core }) {
  const findings = [];
  for (const juror of votedJurors(results)) {
    for (const entry of juror.verdict.thread_replies) {
      const thread = threadsById.get(entry.thread_id);
      if (!thread || thread.jury || thread.isResolved) {
        core.info(
          `Skipped a ${juror.name} reply: ${entry.thread_id} is not an open thread of another author.`,
        );
        continue;
      }
      findings.push({
        id: `r${findings.length + 1}`,
        kind: "reply",
        key: `reply:${thread.id}`,
        juror: juror.id,
        order: findings.length,
        threadId: thread.id,
        body: entry.body,
      });
    }
  }
  const existing = [...threadsById.values()]
    .flatMap((thread) =>
      thread.comments
        .slice(1)
        .filter((comment) => comment.jury)
        .map((comment) => ({ key: `reply:${thread.id}`, body: comment.body })),
    )
    .map((item, index) => ({ ...item, id: `p${index + 1}` }));
  return { findings, existing };
}

async function postReplies({ github, replies, core }) {
  let posted = 0;
  for (const reply of replies) {
    try {
      await github.graphql(REPLY_MUTATION, {
        threadId: reply.threadId,
        body: attributedBody(reply.body, reply.jurors),
      });
      posted += 1;
    } catch (error) {
      core.warning(
        `Could not reply on thread ${reply.threadId}: ${error.message}`,
      );
    }
  }
  return posted;
}

function commentFindings({ results, files, threads, resolved }) {
  const filesByPath = indexFiles(files);
  const findings = [];
  for (const juror of votedJurors(results)) {
    for (const comment of juror.verdict.comments) {
      const placed = placeComment(comment, filesByPath);
      findings.push({
        ...placed,
        id: `c${findings.length + 1}`,
        kind: "comment",
        key: `${placed.placement === "thread" ? "file" : "outside"}:${placed.path}`,
        juror: juror.id,
        order: findings.length,
      });
    }
  }
  const existing = threads
    .filter(
      (thread) =>
        !thread.isResolved &&
        !resolved.has(thread.id) &&
        thread.comments.length > 0,
    )
    .map((thread, index) => ({
      id: `e${index + 1}`,
      key: `file:${thread.path}`,
      line: thread.line,
      body: thread.comments[0].body,
    }));
  return { findings, existing };
}

async function addThreads({ github, reviewId, threads, core }) {
  const unplaced = [];
  for (const finding of threads) {
    let placed = false;
    for (const input of threadInputs(finding)) {
      try {
        const data = await github.graphql(ADD_THREAD_MUTATION, {
          input: { pullRequestReviewId: reviewId, ...input },
        });
        if (data.addPullRequestReviewThread?.thread) {
          placed = true;
          break;
        }
      } catch (error) {
        core.warning(
          `GitHub did not accept a ${input.subjectType.toLowerCase()} comment on ${finding.path}: ${error.message}`,
        );
      }
    }
    if (!placed) {
      unplaced.push(finding);
    }
  }
  return unplaced;
}

async function submitReview({
  github,
  owner,
  repo,
  pullRequest,
  tally,
  threads,
  outside,
  core,
}) {
  let reviewId = null;
  try {
    const pending = await github.graphql(ADD_PENDING_REVIEW_MUTATION, {
      pullRequestId: pullRequest.node_id,
      commitOID: pullRequest.head.sha,
    });
    reviewId = pending.addPullRequestReview.pullRequestReview.id;
    const unplaced = await addThreads({ github, reviewId, threads, core });
    const body = formatReviewBody({ tally, outside, unplaced });
    const submitted = await github.graphql(SUBMIT_REVIEW_MUTATION, {
      pullRequestReviewId: reviewId,
      body,
    });
    return {
      review: submitted.submitPullRequestReview.pullRequestReview,
      body,
      comments: threads.length - unplaced.length,
    };
  } catch (error) {
    core.warning(
      `Could not publish the review with comments: ${error.message}`,
    );
  }
  if (reviewId) {
    try {
      await github.graphql(DELETE_REVIEW_MUTATION, {
        pullRequestReviewId: reviewId,
      });
    } catch (error) {
      core.warning(`Could not delete the pending review: ${error.message}`);
    }
  }
  const body = formatReviewBody({ tally, outside, unplaced: threads });
  const { data } = await github.rest.pulls.createReview({
    owner,
    repo,
    pull_number: pullRequest.number,
    commit_id: pullRequest.head.sha,
    event: "COMMENT",
    body,
  });
  return {
    review: { id: data.node_id, url: data.html_url },
    body,
    comments: 0,
  };
}

async function minimizePriorReviews({ github, state, resolved, core }) {
  const reviewsWithOpenThreads = new Set(
    state.threads
      .filter((thread) => !thread.isResolved && !resolved.has(thread.id))
      .map((thread) => thread.comments[0]?.reviewId)
      .filter(Boolean),
  );
  for (const review of state.reviews) {
    if (
      !review.jury ||
      review.isMinimized ||
      review.body.trim() === "" ||
      reviewsWithOpenThreads.has(review.id)
    ) {
      continue;
    }
    try {
      await github.graphql(MINIMIZE_MUTATION, { subjectId: review.id });
    } catch (error) {
      core.warning(`Could not minimize review ${review.id}: ${error.message}`);
    }
  }
}

async function publishJuryReview({
  github,
  context,
  core,
  resultsDir,
  clerk,
  secrets = [],
}) {
  const pullRequest = context.payload.pull_request;
  if (!pullRequest) {
    throw new Error("The review jury runs only on pull_request events.");
  }
  const { owner, repo } = context.repo;
  const number = pullRequest.number;
  const results = readJurorResults(resultsDir, secrets);
  const tally = tallyVotes(results);
  for (const entry of tally.entries) {
    core.info(`${entry.name}: ${describeVote(entry)}`);
  }
  if (!tally.entries.some((entry) => entry.status === "voted")) {
    core.setFailed(
      "No juror returned a verdict, so the jury did not publish a review.",
    );
    return null;
  }

  await deletePendingReviews({ github, owner, repo, number, core });
  const [files, state] = await Promise.all([
    github.paginate(github.rest.pulls.listFiles, {
      owner,
      repo,
      pull_number: number,
      per_page: 100,
    }),
    fetchReviewState({ github, owner, repo, number }),
  ]);
  const threadsById = new Map(
    state.threads.map((thread) => [thread.id, thread]),
  );

  const resolved = await resolveFixedThreads({
    github,
    results,
    threadsById,
    core,
  });
  const replyItems = replyFindings({ results, threadsById, core });
  const commentItems = commentFindings({
    results,
    files,
    threads: state.threads,
    resolved,
  });
  // One clerk call covers replies and comments: only items with the same key can merge.
  const { findings, covered, merged } = await dedupeFindings({
    findings: [...replyItems.findings, ...commentItems.findings],
    existing: [...replyItems.existing, ...commentItems.existing],
    clerk,
    core,
  });
  core.info(
    `Juror items: ${replyItems.findings.length} replies and ${commentItems.findings.length} comments. ${merged} merged as duplicates, ${covered} already covered by open threads, ${findings.length} to publish.`,
  );
  const replies = await postReplies({
    github,
    replies: findings.filter((finding) => finding.kind === "reply"),
    core,
  });
  const byLocation = (a, b) =>
    a.path.localeCompare(b.path) || (a.line ?? 0) - (b.line ?? 0);
  const comments = findings.filter((finding) => finding.kind === "comment");
  const threads = comments
    .filter((finding) => finding.placement === "thread")
    .sort(byLocation);
  const outside = comments
    .filter((finding) => finding.placement === "outside")
    .sort(byLocation);
  const published = await submitReview({
    github,
    owner,
    repo,
    pullRequest,
    tally,
    threads,
    outside,
    core,
  });
  await minimizePriorReviews({ github, state, resolved, core });

  core.info(
    `Published ${published.review.url}: ${tally.lgtm ? "LGTM" : "no majority for approval"}, ${published.comments} comments, ${replies} thread replies, ${resolved.size} threads resolved.`,
  );
  if (core.summary) {
    await core.summary
      .addHeading("Review jury", 2)
      .addRaw(stripMarker(published.body), true)
      .write();
  }
  return {
    review: published.review,
    tally,
    comments: published.comments,
    outside: outside.length,
    replies,
    resolved: resolved.size,
  };
}

module.exports = {
  JURORS,
  MAJORITY,
  MARKER,
  attributedBody,
  buildJurorContext,
  createClerk,
  dedupeFindings,
  extractVerdict,
  fetchReviewState,
  formatReviewBody,
  indexFiles,
  parsePatch,
  placeComment,
  publishJuryReview,
  readJurorResults,
  recordJurorResult,
  redactSecrets,
  tallyVotes,
  validateVerdict,
  writeJurorContext,
};

if (require.main === module) {
  const [command, ...args] = process.argv.slice(2);
  if (command === "extract") {
    const [input, output] = args;
    const result = extractVerdict(
      fs.existsSync(input) ? fs.readFileSync(input, "utf8") : "",
    );
    if (result.ok) {
      fs.writeFileSync(output, `${JSON.stringify(result.verdict, null, 2)}\n`);
    } else {
      console.error(result.error);
      process.exitCode = 1;
    }
  } else if (command === "record") {
    const result = recordJurorResult(process.env);
    const name = jurorName(result.juror);
    if (result.status === "voted") {
      console.log(
        `${name} voted. LGTM: ${result.verdict.lgtm}. Comments: ${result.verdict.comments.length}.`,
      );
    } else {
      const level = result.status === "absent" ? "notice" : "warning";
      console.log(`::${level} title=${name} did not vote::${result.reason}`);
    }
  } else {
    console.error("Usage: review-jury.js extract <input> <output> | record");
    process.exitCode = 2;
  }
}
