## Jira ticket

https://spotinst.atlassian.net/browse/BGD-XXXX

## Checklist

- [ ] I added a Jira ticket link
- [ ] I added a changeset with the `simple-changeset add` command
- [ ] I filled in the test plan
- [ ] I executed the tests and filled in the test results
- [ ] I have filled in the performance test report for any changes made to SQL queries ([template](https://github.com/spotinst/bigdata-python-services/blob/main/.github/db_perf_template.md))
- [ ] I have reviewed the [control plane release procedure](https://spotinst.atlassian.net/wiki/spaces/BD/pages/2358902789/Control+plane+Release)

## Why

_A short description of why this change is necessary. If this is a bug fix, include steps to reproduce the issue_

## What

_What has been modified. Expose the key decisions you have made during this PR to facilitate the discussion with your reviewer_

## How to test

_Step by step instructions to test your feature/fix_

## Test plan and results

_Feel free to add screenshots showing test results_

| Test | Description       | Result | Notes                     |
| ---- | ----------------- | ------ | ------------------------- |
| 1    | Test with input A | Pass   | Some notes about the test |
| 2    | Test with input B | Pass   | Some notes about the test |
| 3    | Test with input C | Pass   | Some notes about the test |

## Rollout procedure

_Describe rollout procedure. Does the change have dependencies on e.g. configuration changes in bigdata-internal-charts, DB migrations, data plane component versions?_
_Describe rollback procedure if it needs more than a charts revert PR_

