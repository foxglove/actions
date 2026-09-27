# Packet 1: plan ticket actions without external access

## What this packet does

This packet reads the result of one test run. It decides what Attack Runner should do with each finding.

It can propose these actions:

- Create a ticket for a new exploit.
- Add evidence to an open ticket.
- Reopen a ticket when new evidence contradicts a fix claim.
- Record that an exploit was not seen in this run.
- Send unclear or unsafe input for review.

The packet also prepares a run summary. The summary lists the proposed actions, test coverage, and items that need review.

## What this packet does not do

This packet does not connect to Strix, Linear, Google Cloud Storage, or any other network service. It does not create or change tickets. It does not run an attack. It does not read credentials.

Later packets will deliver approved actions to Linear and store the run summary. Those packets must check this packet's proposals before they make external changes.

## Why this packet uses Node.js

Node.js is the program that runs the JavaScript files in this packet. The number 24 identifies a major Node.js release. The code was checked with Node.js 24.15.0.

The repository already uses JavaScript, Node.js tools, and the Yarn package manager. It contains a JavaScript helper for its pull request workflow. The workflow also supports Node.js and Yarn commands.

Packet 1 uses only functions that are built into Node.js. It adds no runtime package. It also uses the Node.js test tool. Thus, Node.js keeps the packet consistent with the repository and avoids a second application toolchain.

[Node.js 24 is a Long-Term Support release](https://nodejs.org/en/about/previous-releases). The Node.js project plans to support it through April 2028. The `.node-version` file and `package.json` now select Node.js 24. The pull request check runs the tests with that version.

The Node.js version does not change the product behavior.

## How to run the example

From the repository root, run:

```sh
yarn attack-runner plan \
  --input test/attack-runner/fixtures/F1-new.json \
  --output new-plan.json
```

JSON is a text format for structured data. The command reads one JSON input file. It writes one JSON plan file. The command refuses to replace an existing output file.

If you omit `--output`, the command prints the plan in the terminal.

The supplied example describes this test:

1. A non-admin user in organization A lists exports.
2. The user learns the identifier of an export from organization B.
3. The user downloads the organization B export.
4. The evidence shows a cross-tenant access failure.

For this example, the planner proposes one new ticket. The ticket contains both steps in the attack chain. It marks production impact as unknown because the example uses test data.

## The decisions to review

| Input condition                                       | Planner result                                                                                       |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| The evidence proves a new exploit.                    | Propose one new ticket.                                                                              |
| The evidence matches one open ticket.                 | Propose new evidence for that ticket. Count this run once.                                           |
| The evidence contradicts a stated fix.                | Propose new evidence and reopen the same ticket if it is closed.                                     |
| The run does not find a known exploit.                | Add the result to the run summary. Do not change the ticket. Do not claim that the exploit is fixed. |
| The evidence can match more than one exploit.         | Ask for review. Do not guess.                                                                        |
| One finding is invalid, but other findings are valid. | Reject the invalid finding. Continue with the valid findings.                                        |
| Shared run data is invalid.                           | Reject the complete input. Do not produce ticket proposals.                                          |
| The same event was already applied.                   | Do not propose the same action again.                                                                |
| A previous external action has an unknown result.     | Stop and request a check of the external system. Do not retry the action.                            |

Different wording must not create a second ticket for the same exploit. The planner compares the actor, resource, broken security rule, result, and required attack steps. A repository name, title, model name, run ID, or generated resource ID does not define the exploit.

Two independent security failures must remain separate. If one raw finding contains two independent failures, the input must identify each cause. The planner then proposes one ticket for each cause.

## Input requirements

The input must contain:

- The run ID and the approved environment.
- The instruction file's digital fingerprint, which is also called a hash.
- The private evidence location.
- The test coverage and stop reason.
- The findings and their evidence references.
- The relevant existing tickets.
- The external actions that were already applied or have an unknown result.

The input must not contain passwords, session cookies, magic links, or other credentials.

A separate input component must remove secrets. It must also prove which session produced the evidence. This packet checks the supplied session record. It cannot prove that the live target was approved. It also cannot prove that cloud storage is private. Later packets must make those checks.

## Command results

An exit code is the number that a command returns when it stops.

| Exit code | Meaning                                                                                            |
| --------- | -------------------------------------------------------------------------------------------------- |
| `0`       | The planner processed all items.                                                                   |
| `1`       | The input file or shared run data is invalid. The planner does not produce a plan.                 |
| `2`       | The planner produced a plan, but one or more items need review.                                    |
| `3`       | The planner could not write the requested output file. It prints the error code to standard error. |

The planner does not replace an existing output file. It returns exit code `3` and leaves that file unchanged. Choose a new path or remove the existing file, and then run the command again. If another write error occurs after the planner creates the output file, it removes that incomplete file. If removal also fails, the error says that incomplete output may remain. When `--output` is present, a write failure does not print the plan to standard output.

## How to review this packet

Run the tests:

```sh
yarn test:attack-runner
```

Review these questions:

1. Does each proven exploit produce the correct ticket proposal?
2. Does a repeat finding update the correct ticket instead of creating a duplicate?
3. Does new evidence against a fix claim target the same ticket?
4. Does a run with no finding leave the existing ticket unchanged?
5. Does unclear evidence stop for review instead of guessing?
6. Does the planner avoid repeat actions after a replay?
7. Does invalid shared run data stop all ticket proposals?
8. Does the output contain no credential values?

The automated tests cover these cases with test data. They do not prove that authentication, Strix, Linear, or cloud storage works. Those checks belong to later packets.

For the final review, record the exact code revision, test command, exit result, and reviewer result. If the code changes after review, run the affected checks again.
