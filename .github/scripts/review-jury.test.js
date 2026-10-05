const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { describe, it } = require("node:test");

const jury = require("./review-jury.js");

const {
  JURORS,
  MARKER,
  buildJurorContext,
  createClerk,
  dedupeFindings,
  extractVerdict,
  formatReviewBody,
  indexFiles,
  parsePatch,
  placeComment,
  publishJuryReview,
  readJurorResults,
  recordJurorResult,
  tallyVotes,
  validateVerdict,
} = jury;

const REPO_ROOT = path.resolve(__dirname, "..", "..");

const PATCH = [
  "@@ -1,3 +1,4 @@",
  " a",
  "-b",
  "+B",
  "+C",
  " d",
  "@@ -10,2 +11,2 @@ function f() {",
  " x",
  "-y",
  "+Y",
  "\\ No newline at end of file",
].join("\n");

function verdict(overrides = {}) {
  return {
    fixed_threads: [],
    thread_replies: [],
    comments: [],
    lgtm: true,
    ...overrides,
  };
}

function comment(overrides = {}) {
  return {
    path: "src/a.ts",
    line: 2,
    start_line: null,
    side: "RIGHT",
    body: "Handle the null case.",
    ...overrides,
  };
}

function quietCore() {
  const log = { info: [], warning: [], failed: [] };
  return {
    log,
    info: (message) => log.info.push(message),
    warning: (message) => log.warning.push(message),
    setFailed: (message) => log.failed.push(message),
  };
}

function resultsMap(entries) {
  return new Map(
    Object.entries(entries).map(([id, result]) => [
      id,
      { juror: id, ...result },
    ]),
  );
}

describe("parsePatch", () => {
  it("maps each side's line numbers to their hunk", () => {
    const lines = parsePatch(PATCH);
    assert.deepEqual(
      [...lines.RIGHT],
      [
        [1, 0],
        [2, 0],
        [3, 0],
        [4, 0],
        [11, 1],
        [12, 1],
      ],
    );
    assert.deepEqual(
      [...lines.LEFT],
      [
        [1, 0],
        [2, 0],
        [3, 0],
        [10, 1],
        [11, 1],
      ],
    );
  });

  it("returns null for files without a patch", () => {
    assert.equal(parsePatch(undefined), null);
    assert.equal(parsePatch(""), null);
  });
});

describe("placeComment", () => {
  const files = indexFiles([
    { filename: "src/a.ts", patch: PATCH },
    { filename: "image.png" },
  ]);

  it("keeps a line comment that is in the diff", () => {
    assert.deepEqual(placeComment(comment({ path: "./src/a.ts" }), files), {
      placement: "thread",
      subjectType: "LINE",
      path: "src/a.ts",
      line: 2,
      startLine: null,
      side: "RIGHT",
      body: "Handle the null case.",
    });
  });

  it("keeps a range in one hunk and drops a range across hunks", () => {
    assert.equal(
      placeComment(comment({ line: 4, start_line: 2 }), files).startLine,
      2,
    );
    assert.equal(
      placeComment(comment({ line: 12, start_line: 2 }), files).startLine,
      null,
    );
  });

  it("checks deleted lines against the base version", () => {
    assert.equal(
      placeComment(comment({ line: 11, side: "LEFT" }), files).subjectType,
      "LINE",
    );
    const placed = placeComment(comment({ line: 12, side: "LEFT" }), files);
    assert.equal(placed.subjectType, "FILE");
    assert.match(placed.body, /^\*\*Line 12 \(base version\)\*\*\n\n/);
  });

  it("turns a line outside the diff into a file comment that names the line", () => {
    const placed = placeComment(comment({ line: 7 }), files);
    assert.equal(placed.subjectType, "FILE");
    assert.equal(placed.body, "**Line 7**\n\nHandle the null case.");
  });

  it("turns a line comment on a file without a patch into a file comment", () => {
    const placed = placeComment(comment({ path: "image.png", line: 1 }), files);
    assert.equal(placed.subjectType, "FILE");
    assert.match(placed.body, /^\*\*Line 1\*\*/);
  });

  it("keeps a file comment", () => {
    const placed = placeComment(comment({ line: null }), files);
    assert.equal(placed.subjectType, "FILE");
    assert.equal(placed.body, "Handle the null case.");
  });

  it("moves a comment on an unchanged file to the review body", () => {
    assert.equal(
      placeComment(comment({ path: "src/other.ts" }), files).placement,
      "outside",
    );
  });
});

describe("extractVerdict", () => {
  const value = verdict({ lgtm: false, comments: [comment()] });

  it("reads a bare verdict", () => {
    assert.deepEqual(extractVerdict(JSON.stringify(value)), {
      ok: true,
      verdict: value,
    });
  });

  it("reads the Grok Build envelope", () => {
    for (const envelope of [
      { structured_output: value, text: "" },
      { structuredOutput: value },
      {
        text: `\`\`\`json\n${JSON.stringify(value)}\n\`\`\``,
        stopReason: "EndTurn",
      },
    ]) {
      assert.deepEqual(extractVerdict(JSON.stringify(envelope)).verdict, value);
    }
  });

  it("fills in missing thread lists", () => {
    const result = extractVerdict(JSON.stringify({ comments: [], lgtm: true }));
    assert.deepEqual(result.verdict, verdict());
  });

  it("rejects output without a valid verdict", () => {
    assert.equal(extractVerdict("not json").ok, false);
    assert.equal(extractVerdict(JSON.stringify({ text: "Done." })).ok, false);
    const invalid = extractVerdict(
      JSON.stringify({ comments: [comment({ line: 0 })], lgtm: false }),
    );
    assert.equal(invalid.ok, false);
    assert.match(invalid.error, /comments\[0\]\.line/);
  });
});

describe("validateVerdict", () => {
  it("clears start_line on a file comment", () => {
    const result = validateVerdict(
      verdict({ comments: [comment({ line: null, start_line: 3 })] }),
    );
    assert.equal(result.verdict.comments[0].start_line, null);
  });

  it("requires a reply for each fixed thread", () => {
    const result = validateVerdict(
      verdict({ fixed_threads: [{ thread_id: "T1", reply: " " }] }),
    );
    assert.equal(result.ok, false);
  });
});

describe("tallyVotes and formatReviewBody", () => {
  it("posts LGTM with two of three approvals", () => {
    const tally = tallyVotes(
      resultsMap({
        opus: { status: "voted", verdict: verdict() },
        astra: { status: "voted", verdict: verdict() },
        grok: {
          status: "voted",
          verdict: verdict({ lgtm: false, comments: [comment()] }),
        },
      }),
    );
    assert.equal(tally.approvals, 2);
    assert.equal(tally.lgtm, true);
    const body = formatReviewBody({ tally });
    assert.match(body, /^LGTM\n\nJury vote: 2 of 3 approve\.\n/);
    assert.match(body, /- Grok: does not approve \(1 comment\)\./);
    assert.ok(body.endsWith(MARKER));
  });

  it("does not post LGTM with one approval", () => {
    const tally = tallyVotes(
      resultsMap({
        opus: { status: "voted", verdict: verdict() },
        astra: {
          status: "absent",
          reason: "The caller did not pass `OPENAI_API_KEY`.",
        },
        grok: { status: "failed", reason: "The review did not finish." },
      }),
    );
    assert.equal(tally.lgtm, false);
    const body = formatReviewBody({ tally });
    assert.doesNotMatch(body, /LGTM/);
    assert.match(body, /Jury vote: 1 of 3 approve\. Approval needs 2\./);
    assert.match(
      body,
      /- Astra: did not vote\. The caller did not pass `OPENAI_API_KEY`\./,
    );
    assert.match(body, /- Grok: did not vote\. The review did not finish\./);
  });

  it("does not count an LGTM vote that also raises comments", () => {
    const tally = tallyVotes(
      resultsMap({
        opus: { status: "voted", verdict: verdict({ comments: [comment()] }) },
        astra: { status: "voted", verdict: verdict() },
        grok: { status: "voted", verdict: verdict({ lgtm: false }) },
      }),
    );
    assert.equal(tally.approvals, 1);
    assert.equal(tally.lgtm, false);
  });

  it("lists findings on unchanged files in the body", () => {
    const tally = tallyVotes(
      resultsMap({ opus: { status: "voted", verdict: verdict() } }),
    );
    const body = formatReviewBody({
      tally,
      outside: [
        {
          path: "src/other.ts",
          line: 4,
          body: "Update this caller.",
          jurors: ["grok"],
        },
      ],
    });
    assert.match(
      body,
      /### Findings on files that this pull request does not change\n\n#### `src\/other\.ts` line 4\n\nUpdate this caller\.\n\n<sub>Juror: Grok<\/sub>/,
    );
  });
});

describe("dedupeFindings", () => {
  const finding = (id, juror, key, body, order) => ({
    id,
    juror,
    key,
    body,
    order,
  });

  it("merges duplicates that the clerk groups and credits every juror", async () => {
    const findings = [
      finding("c1", "opus", "file:a", "Null check missing.", 0),
      finding("c2", "astra", "file:a", "Different issue.", 1),
      finding("c3", "grok", "file:a", "`x` can be null here.", 2),
      finding("c4", "grok", "file:b", "Only one here.", 3),
    ];
    const asked = [];
    const clerk = async (items) => {
      asked.push(items.map((item) => item.id));
      return [
        { ids: ["c1", "c3"], keep: "c3" },
        { ids: ["c2"], keep: "c2" },
      ];
    };
    const { findings: result, merged } = await dedupeFindings({
      findings,
      clerk,
    });
    assert.deepEqual(asked, [["c1", "c2", "c3"]]);
    assert.deepEqual(
      result.map((item) => [item.id, item.jurors]),
      [
        ["c2", ["astra"]],
        ["c3", ["opus", "grok"]],
        ["c4", ["grok"]],
      ],
    );
    assert.equal(merged, 1);
  });

  it("drops a finding that an open thread already covers", async () => {
    const { findings: result, covered } = await dedupeFindings({
      findings: [finding("c1", "opus", "file:a", "Null check missing.", 0)],
      existing: [{ id: "e1", key: "file:a", body: "Add a null check." }],
      clerk: async () => [{ ids: ["c1", "e1"], keep: "c1" }],
    });
    assert.deepEqual(result, []);
    assert.equal(covered, 1);
  });

  it("never merges items with different keys", async () => {
    const { findings: result } = await dedupeFindings({
      findings: [
        finding("c1", "opus", "file:a", "Same text.", 0),
        finding("c2", "astra", "file:a", "Other.", 1),
        finding("c3", "grok", "file:b", "Same text.", 2),
      ],
      clerk: async () => [{ ids: ["c1", "c2", "c3"], keep: "c3" }],
    });
    assert.deepEqual(
      result.map((item) => [item.id, item.jurors]),
      [
        ["c1", ["opus", "astra"]],
        ["c3", ["grok"]],
      ],
    );
  });

  it("merges only identical text when the clerk fails", async () => {
    const core = quietCore();
    const { findings: result } = await dedupeFindings({
      findings: [
        finding("c1", "opus", "file:a", "Null check   missing.", 0),
        finding("c2", "grok", "file:a", "null check missing.", 1),
        finding("c3", "astra", "file:a", "Something else.", 2),
      ],
      clerk: async () => {
        throw new Error("overloaded");
      },
      core,
    });
    assert.deepEqual(
      result.map((item) => [item.id, item.jurors]),
      [
        ["c1", ["opus", "grok"]],
        ["c3", ["astra"]],
      ],
    );
    assert.match(core.log.warning[0], /overloaded/);
  });

  it("does not ask the clerk when no key has two items", async () => {
    const { findings: result } = await dedupeFindings({
      findings: [finding("c1", "opus", "file:a", "One.", 0)],
      clerk: async () => assert.fail("The clerk must not run."),
    });
    assert.equal(result.length, 1);
  });
});

describe("createClerk", () => {
  it("sends a forced tool call and reads the groups", async () => {
    let request;
    const fetchImpl = async (url, options) => {
      request = { url, ...options, body: JSON.parse(options.body) };
      return {
        ok: true,
        json: async () => ({
          content: [
            {
              type: "tool_use",
              name: "report_duplicates",
              input: { groups: [{ ids: ["c1"], keep: "c1" }] },
            },
          ],
        }),
      };
    };
    const clerk = createClerk({
      apiKey: "key",
      model: "claude-test",
      fetchImpl,
    });
    assert.deepEqual(await clerk([{ id: "c1" }]), [
      { ids: ["c1"], keep: "c1" },
    ]);
    assert.equal(request.url, "https://api.anthropic.com/v1/messages");
    assert.equal(request.headers["x-api-key"], "key");
    assert.equal(request.body.model, "claude-test");
    assert.deepEqual(request.body.tool_choice, {
      type: "tool",
      name: "report_duplicates",
    });
  });

  it("retries once and then fails", async () => {
    let calls = 0;
    const fetchImpl = async () => {
      calls += 1;
      return { ok: false, status: 529, text: async () => "overloaded" };
    };
    const clerk = createClerk({ apiKey: "key", model: "m", fetchImpl });
    await assert.rejects(clerk([]), /529/);
    assert.equal(calls, 2);
  });
});

describe("recordJurorResult and readJurorResults", () => {
  const temp = () => fs.mkdtempSync(path.join(os.tmpdir(), "review-jury-"));

  it("records each juror status", () => {
    const dir = temp();
    const output = path.join(dir, "github-output");
    const verdictFile = path.join(dir, "verdict.json");
    fs.writeFileSync(
      verdictFile,
      JSON.stringify({ structured_output: verdict() }),
    );
    const base = { GITHUB_OUTPUT: output, VERDICT_FILE: verdictFile };

    const voted = recordJurorResult({
      ...base,
      JUROR: "grok",
      AVAILABLE: "true",
      SUCCEEDED: "true",
      RESULT_FILE: path.join(dir, "results", "grok.json"),
    });
    assert.equal(voted.status, "voted");

    const absent = recordJurorResult({
      ...base,
      JUROR: "astra",
      AVAILABLE: "false",
      MISSING_SECRET: "OPENAI_API_KEY",
      RESULT_FILE: path.join(dir, "results", "astra.json"),
    });
    assert.equal(absent.reason, "The caller did not pass `OPENAI_API_KEY`.");

    assert.deepEqual(fs.readFileSync(output, "utf8").split("\n"), [
      "status=voted",
      "status=absent",
      "",
    ]);

    const results = readJurorResults(path.join(dir, "results"));
    assert.deepEqual(
      [...results].map(([id, result]) => [id, result.status]),
      [
        ["opus", "failed"],
        ["astra", "absent"],
        ["grok", "voted"],
      ],
    );
    assert.equal(
      results.get("opus").reason,
      "The juror job did not return a result.",
    );
  });

  it("fails a juror whose run succeeded with an invalid result", () => {
    const dir = temp();
    const verdictFile = path.join(dir, "verdict.json");
    fs.writeFileSync(verdictFile, "{}");
    const result = recordJurorResult({
      JUROR: "opus",
      AVAILABLE: "true",
      SUCCEEDED: "true",
      VERDICT_FILE: verdictFile,
      RESULT_FILE: path.join(dir, "opus.json"),
    });
    assert.equal(result.status, "failed");
    assert.match(result.reason, /not valid/);
  });
});

describe("buildJurorContext", () => {
  it("marks jury items and finds the last jury review commit", () => {
    const state = {
      reviews: [
        {
          author: "claude",
          body: "LGTM",
          state: "COMMENTED",
          commitId: "c1",
          submittedAt: "2026-01-01T00:00:00Z",
          jury: true,
        },
        {
          author: "github-actions",
          body: `x${MARKER}`,
          state: "COMMENTED",
          commitId: "c2",
          submittedAt: "2026-01-03T00:00:00Z",
          jury: true,
        },
        {
          author: "alice",
          body: "",
          state: "APPROVED",
          commitId: "c3",
          submittedAt: "2026-01-04T00:00:00Z",
          jury: false,
        },
      ],
      threads: [],
      issueComments: [],
    };
    const result = buildJurorContext({
      pullRequest: {
        number: 7,
        title: "Title",
        body: null,
        user: { login: "alice" },
        base: { ref: "main" },
        head: { sha: "head" },
        draft: false,
      },
      state,
    });
    assert.equal(result.last_jury_review_commit, "c2");
    assert.equal(result.pull_request.body, "");
    assert.deepEqual(
      result.reviews.map((review) => review.jury),
      [true, true, false],
    );
  });
});

function fakeGitHub({
  files,
  threads = [],
  reviews = [],
  pendingReviews = [],
  rejectThread = () => false,
  failSubmit = false,
}) {
  const calls = [];
  const connection = (nodes) => ({
    pageInfo: { hasNextPage: false, endCursor: null },
    nodes,
  });
  const github = {
    rest: {
      pulls: {
        listFiles: "listFiles",
        listReviews: "listReviews",
        deletePendingReview: async (args) =>
          calls.push({ name: "deletePendingReview", args }),
        createReview: async (args) => {
          calls.push({ name: "createReview", args });
          return {
            data: { node_id: "PRR_rest", html_url: "https://github.test/rest" },
          };
        },
      },
      issues: { listComments: "listComments" },
    },
    paginate: async (method) =>
      ({ listFiles: files, listReviews: pendingReviews, listComments: [] })[
        method
      ],
    graphql: async (query, variables) => {
      const name = /(\w+)\(\s*input|(reviewThreads|reviews)\(first/.exec(query);
      const operation = name[1] ?? name[2];
      calls.push({ name: operation, args: variables });
      switch (operation) {
        case "reviewThreads":
          return {
            repository: { pullRequest: { reviewThreads: connection(threads) } },
          };
        case "reviews":
          return {
            repository: { pullRequest: { reviews: connection(reviews) } },
          };
        case "addPullRequestReview":
          return {
            addPullRequestReview: { pullRequestReview: { id: "PRR_new" } },
          };
        case "addPullRequestReviewThread":
          if (rejectThread(variables.input)) {
            throw new Error(
              "pull_request_review_thread.line must be part of the diff",
            );
          }
          return { addPullRequestReviewThread: { thread: { id: "PRRT_new" } } };
        case "submitPullRequestReview":
          if (failSubmit) {
            throw new Error("submit failed");
          }
          return {
            submitPullRequestReview: {
              pullRequestReview: {
                id: "PRR_new",
                url: "https://github.test/review",
              },
            },
          };
        default:
          return {};
      }
    },
  };
  return {
    github,
    calls,
    named: (name) => calls.filter((call) => call.name === name),
  };
}

function thread(
  id,
  author,
  body,
  { resolved = false, path: filePath = "src/a.ts", reviewId = null } = {},
) {
  return {
    id,
    isResolved: resolved,
    isOutdated: false,
    path: filePath,
    line: 2,
    startLine: null,
    diffSide: "RIGHT",
    comments: {
      nodes: [
        {
          author: { login: author },
          body,
          createdAt: "2026-01-01T00:00:00Z",
          pullRequestReview: { id: reviewId },
        },
      ],
    },
  };
}

function writeResults(results) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "review-jury-results-"));
  for (const [id, result] of Object.entries(results)) {
    fs.writeFileSync(
      path.join(dir, `${id}.json`),
      JSON.stringify({ juror: id, ...result }),
    );
  }
  return dir;
}

const CONTEXT = {
  repo: { owner: "foxglove", repo: "app" },
  payload: {
    pull_request: {
      number: 7,
      node_id: "PR_7",
      head: { sha: "headsha" },
      base: { ref: "main" },
    },
  },
};

describe("publishJuryReview", () => {
  const files = [{ filename: "src/a.ts", patch: PATCH }];

  it("publishes merged comments, resolves majority-fixed threads, and minimizes old reviews", async () => {
    const fake = fakeGitHub({
      files,
      pendingReviews: [
        { id: 11, state: "PENDING", user: { login: "github-actions[bot]" } },
        { id: 12, state: "PENDING", user: { login: "alice" } },
      ],
      threads: [
        thread("T_fixed", "github-actions", `Old issue.${MARKER}`, {
          reviewId: "R_old",
        }),
        thread("T_one_vote", "claude", "Legacy issue.", { reviewId: "R_open" }),
        thread("T_human", "alice", "Why this name?"),
      ],
      reviews: [
        {
          id: "R_old",
          author: { login: "github-actions" },
          body: `Jury vote${MARKER}`,
          state: "COMMENTED",
          isMinimized: false,
          commit: { oid: "c1" },
        },
        {
          id: "R_open",
          author: { login: "claude" },
          body: "Old review",
          state: "COMMENTED",
          isMinimized: false,
          commit: { oid: "c0" },
        },
        {
          id: "R_human",
          author: { login: "alice" },
          body: "Looks fine",
          state: "COMMENTED",
          isMinimized: false,
          commit: { oid: "c1" },
        },
      ],
    });
    const resultsDir = writeResults({
      opus: {
        status: "voted",
        verdict: verdict({
          fixed_threads: [
            { thread_id: "T_fixed", reply: "The new guard fixes this." },
            { thread_id: "T_human", reply: "Fixed." },
          ],
          thread_replies: [
            { thread_id: "T_human", body: "The name matches `Foo`." },
          ],
        }),
      },
      astra: {
        status: "voted",
        verdict: verdict({
          fixed_threads: [
            { thread_id: "T_fixed", reply: "Fixed by the guard." },
            { thread_id: "T_human", reply: "Fixed." },
          ],
        }),
      },
      grok: {
        status: "voted",
        verdict: verdict({
          lgtm: false,
          fixed_threads: [
            { thread_id: "T_one_vote", reply: "Fixed." },
            { thread_id: "T_human", reply: "Fixed." },
          ],
          thread_replies: [
            { thread_id: "T_human", body: "It matches the `Foo` type." },
          ],
          comments: [
            comment(),
            comment({ path: "src/other.ts", body: "Update the caller." }),
          ],
        }),
      },
    });
    // Groups the two replies that both name `Foo` and leaves every other item alone.
    const clerk = async (items) => {
      const foo = items.filter((item) => item.body.includes("`Foo`"));
      const rest = items.filter((item) => !item.body.includes("`Foo`"));
      return [
        { ids: foo.map((item) => item.id), keep: foo[0]?.id ?? null },
        ...rest.map((item) => ({
          ids: [item.id],
          keep: item.source === "new" ? item.id : null,
        })),
      ];
    };
    const core = quietCore();

    const result = await publishJuryReview({
      github: fake.github,
      context: CONTEXT,
      core,
      resultsDir,
      clerk,
    });

    assert.deepEqual(
      fake.named("deletePendingReview").map((call) => call.args.review_id),
      [11],
    );
    assert.deepEqual(
      fake.named("resolveReviewThread").map((call) => call.args.threadId),
      ["T_fixed"],
    );
    const replies = fake.named("addPullRequestReviewThreadReply");
    assert.deepEqual(
      replies.map((call) => call.args.threadId),
      ["T_fixed", "T_human"],
    );
    assert.match(
      replies[0].args.body,
      /^The new guard fixes this\.\n\n<sub>Jurors: Opus, Astra<\/sub>/,
    );
    assert.match(replies[1].args.body, /<sub>Jurors: Opus, Grok<\/sub>/);

    const added = fake.named("addPullRequestReviewThread");
    assert.equal(added.length, 1);
    assert.deepEqual(
      { ...added[0].args.input, body: undefined },
      {
        pullRequestReviewId: "PRR_new",
        path: "src/a.ts",
        body: undefined,
        subjectType: "LINE",
        line: 2,
        side: "RIGHT",
      },
    );
    assert.ok(added[0].args.input.body.includes(MARKER));

    const [submit] = fake.named("submitPullRequestReview");
    assert.match(submit.args.body, /^LGTM\n\nJury vote: 2 of 3 approve\./);
    assert.match(
      submit.args.body,
      /#### `src\/other\.ts` line 2\n\nUpdate the caller\./,
    );

    assert.deepEqual(
      fake.named("minimizeComment").map((call) => call.args.subjectId),
      ["R_old"],
    );
    assert.equal(result.resolved, 1);
    assert.equal(result.replies, 1);
    assert.equal(result.comments, 1);
    assert.deepEqual(core.log.failed, []);
  });

  it("falls back to a file comment, then to the review body", async () => {
    const fake = fakeGitHub({
      files,
      rejectThread: (input) =>
        input.subjectType === "LINE" || input.body.includes("Second"),
    });
    const resultsDir = writeResults({
      opus: {
        status: "voted",
        verdict: verdict({
          lgtm: false,
          comments: [
            comment({ body: "First." }),
            comment({ line: 3, body: "Second." }),
          ],
        }),
      },
    });
    const core = quietCore();
    const result = await publishJuryReview({
      github: fake.github,
      context: CONTEXT,
      core,
      resultsDir,
      clerk: null,
    });

    const accepted = fake
      .named("addPullRequestReviewThread")
      .filter(
        (call) =>
          call.args.input.subjectType === "FILE" &&
          !call.args.input.body.includes("Second"),
      );
    assert.equal(accepted.length, 1);
    assert.match(accepted[0].args.input.body, /^\*\*Line 2\*\*\n\nFirst\./);
    const [submit] = fake.named("submitPullRequestReview");
    assert.match(
      submit.args.body,
      /### Findings that GitHub did not accept as review comments/,
    );
    assert.match(submit.args.body, /Second\./);
    assert.doesNotMatch(submit.args.body, /LGTM/);
    assert.equal(result.comments, 1);
  });

  it("posts a body-only review when the pending review fails", async () => {
    const fake = fakeGitHub({ files, failSubmit: true });
    const resultsDir = writeResults({
      opus: {
        status: "voted",
        verdict: verdict({ lgtm: false, comments: [comment()] }),
      },
    });
    const result = await publishJuryReview({
      github: fake.github,
      context: CONTEXT,
      core: quietCore(),
      resultsDir,
      clerk: null,
    });
    assert.equal(fake.named("deletePullRequestReview").length, 1);
    const [create] = fake.named("createReview");
    assert.equal(create.args.event, "COMMENT");
    assert.equal(create.args.commit_id, "headsha");
    assert.match(create.args.body, /Handle the null case\./);
    assert.equal(result.review.url, "https://github.test/rest");
  });

  it("publishes nothing when no juror voted", async () => {
    const fake = fakeGitHub({ files });
    const core = quietCore();
    const resultsDir = writeResults({
      opus: { status: "failed", reason: "The review did not finish." },
      astra: {
        status: "absent",
        reason: "The caller did not pass `OPENAI_API_KEY`.",
      },
    });
    assert.equal(
      await publishJuryReview({
        github: fake.github,
        context: CONTEXT,
        core,
        resultsDir,
      }),
      null,
    );
    assert.deepEqual(fake.calls, []);
    assert.equal(core.log.failed.length, 1);
  });
});

describe("configuration", () => {
  it("matches the juror matrix in the workflow", () => {
    const workflow = fs.readFileSync(
      path.join(REPO_ROOT, ".github/workflows/review.yml"),
      "utf8",
    );
    const matrix = [
      ...workflow.matchAll(/^\s+- juror: (\w+)\n\s+name: (\w+)$/gm),
    ].map((match) => ({
      id: match[1],
      name: match[2],
    }));
    assert.deepEqual(matrix, JURORS);
  });

  it("uses a schema that strict structured output accepts", () => {
    const text = fs.readFileSync(
      path.join(REPO_ROOT, "prompts/review-verdict.schema.json"),
      "utf8",
    );
    // The workflow passes the schema to Claude Code inside single quotes.
    assert.doesNotMatch(text, /'/);
    const visit = (schema) => {
      if (schema.type === "object") {
        assert.equal(schema.additionalProperties, false);
        assert.deepEqual(
          [...schema.required].sort(),
          Object.keys(schema.properties).sort(),
        );
        Object.values(schema.properties).forEach(visit);
      }
      if (schema.type === "array") {
        visit(schema.items);
      }
    };
    visit(JSON.parse(text));
  });
});
