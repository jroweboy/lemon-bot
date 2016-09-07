# lemon-bot
Simple built bot for citra to make unofficial builds of popular branches

People with admin access can just edit the merge_list.yml to update
what branches are going to be built on the next run. Currently without webhooks
this bot just checks every 5 minutes for updates.

Pull requests to update the merge list is not accepted at this time.

Pull requests to fix issues with the bot are more than welcome.

## What does it do?

The bot essentially runs the following git commands to build a merge of the branches

```
TODO:
```
In the event of a failed merge, that branch is marked as failed merge and left out of the final build.

Branches can be marked as required to signify that if this branch fails to merge than the build should fail/

Branches are merged in order from top to bottom. Because of this, you should put the most important branches first
in order to increase their priority.

## Example merge_list.yml

``` yaml
# changes to these require a restart to take effect.
tracking_repository: "https://github.com/foo/bar"
push_repository: "https://github.com/whoknows/beta"

merge_list:
    - pr_id: 1234
      branch: prerequiste-changes
      required: true
    - pr_id: 2468
      branch: cool-feature-but-not-necessary
    - pr_id: 1567
      branch: fails-to-merge-build-will-continue
    - pr_id: 1492
      branch: fails-to-merge-build-fails-too
      required: true
    - pr_id: 2001
      branch: a-space-odyssey
    - remote: baz
      branch: too-cool-to-pr-this

# Someday I would like to have these option as well
enable_trusted_prs: true
auto_remove_merged: true

tracking_remotes:
    - name: baz
      url: "https://github.com/baz/bar"
      # use the scheduled checkup instead of webhook
      web_hook: false
    - name: contributor
      url: "https://github.com/contributor/bar"
```

## Future goals

* Webhook support. Need to get a webhook setup first though.
* Trusted PRs. Auto add prs submitted by members of the repositories organization
* Auto remove PRs that were merged into master since the last build
* Remove the need for branch names in the yaml. They can be swapped out for the commit hash I bet if they are left blank.
* Add different tracking remotes that can be pulled from
