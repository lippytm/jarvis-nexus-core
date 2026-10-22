# Engineering improvements — October 22, 2026

## Goal and authority

Charles requested continued creative improvements and implementation of the
three priorities in section 6 of the daily update: dependable diagnostics,
a measurable membership/referral journey, and a Control Tower advanced from a
verified source version. This change is a reviewable development update to
the existing PR #5, based on commit
`b304e0864cd01993957b2e9b6cf252babb7cc4aa`.

## Changes and why they matter

1. **Malformed data becomes a rejection instead of a crashed report.** Event
   validation checks field types, finite JSON, bounded size/depth, known sensitive
   field names, and evidence URL shape. Reports do not echo rejected payloads.
   Field-name filtering is not comprehensive personal-data detection.
2. **Simulation evidence stays explicitly synthetic.** Round trips require a
   fixture marker, count exact duplicates and reject conflicting reuse. A bad
   event does not prevent valid events in the batch from producing a report.
3. **Membership state has meaningful acceptance gates.** Unpaid access, incorrect
   receipts, reused payments, provider retries and conflicting event IDs are
   covered. Optional marketing consent is separate from requested service.
4. **AI builder proposals stay bounded.** Roles, capabilities, numeric budgets,
   task depth and duplicates are checked. The evaluator accepts only exact known
   templates. No generated code is executed or installed.
5. **Connection records describe observations honestly.** Registry configuration
   does not establish live access. Recorded reads have scope, time, source revision,
   response digest and freshness checks; hashes check integrity, not authenticity.
6. **Verification can be repeated.** `scripts/verify_control_tower.py` checks
   syntax before running behavior tests and the offline demonstration, then saves
   source hashes, counts, errors, scope and limitations. CI uses pinned action
   revisions, read-only permissions, a timeout, and retains verification artifacts.

No new runtime dependency is required for the Control Tower. The implementation
uses the Python standard library. Review scope excludes the preexisting Node
servers and installer; they were neither executed nor deployed for this task.

## 6. The next three engineering priorities

| Priority | Concrete work in this update | Completion evidence still required |
| --- | --- | --- |
| Restore dependable diagnostics | Repair the separate `Chatlippytm.ai.Bots` missing-credential path in its existing PR #31; keep skipped/failed AI coverage explicit and preserve available findings. This Nexus change hardens event/report failure handling. | Review PR #31 and its exact-revision tests; a merged scheduled scan has not yet run the new repair. |
| Finish a measurable membership or referral journey | `journeys.py`, its regression tests, the fixture in `examples/`, and the exact page edit specification in `WEBSITE_CONVERSION_REVIEW.md`. | Actual supported website editing, form receipt, provider verification, member access, cancellation policy and attribution. |
| Advance the Control Tower from a verified version | Recover and reconcile the 24-test v1.0 archive with the 27-test GitHub baseline; strengthen the existing source; preserve verification evidence and recorded-read scope. | New GitHub revision and CI evidence, independent human security review, and supported provider-specific round trips. |

The seven management workflows retain their existing numbering: GitHub (1),
AI Building AI (2), Hostinger membership/connections (3), social integrations (4),
funding/affiliates (5), revenue intelligence (6), and daily intelligence (7).
Section 6 above is the daily report section, not a new eighth workflow.

## Source observations and review

- [Prior branch and PR](https://github.com/lippytm/jarvis-nexus-core/pull/5)
- [Prior exact-branch test run](https://github.com/lippytm/jarvis-nexus-core/actions/runs/39687000277/job/119523491173)
- [Bot failure motivating the separate repair](https://github.com/lippytm/Chatlippytm.ai.Bots/actions/runs/39701228345/job/119570673280)
- [Membership page](https://aievolutionaryevolutions.com/membership)
- [Funding copy discrepancy](https://lippytmai.getbizfunds.com/business-line-of-credit-7841)
- [Python URL parsing security](https://docs.python.org/3.11/library/urllib.parse.html#url-parsing-security)
- [GitHub integration best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)

An independent AI reviewer reproduced the baseline failure paths and checked the
new implementation. This is a separate AI review, not the independent human
security or accessibility review still required for release. Verification details
are in `docs/evidence/control_tower_2026_10_22.json` and its test log.

The final local result is **72 tests passed**, with 24 Python files checked for
syntax. The independent AI reviewer reran all 72 tests, the separate bot suite
(99 tests), and 608 adverse-input combinations for event and journey validation.
Those combinations are review probes, not 608 additional unit tests.

`docs/evidence/github_read_observation_2026_10_22.json` packages a retained
GitHub connector response for the baseline commit. The digest covers the exact
response body in the adjacent `github_baseline_response_2026_10_22.json`, excluding
the added trailing newline. Its scope is public commit metadata; it does not
establish credentials, write permission, or current availability. Publication
readback and exact-revision CI are recorded separately on the pull request.

## Recovery and next bounded task

The changes remain on a draft development branch. No production data migration or
deployed-service rollback is needed. If a regression is found, revert the update
commit on that branch through a normal reviewed commit; do not reset shared history.
The recovered archive is unchanged and the baseline SHA above remains the reference.

The next bounded integration task is to review the recorded GitHub read/write
round trip and select one supported Hostinger form delivery mechanism. No
credential should be stored in these source files, evidence records or chat.
