
# TODO: Support webhooks
# TODO: host a webserver to support webhooks
# TODO: make some of the logs visible to the website

import sched
from build import MergeBot

s = sched.scheduler(time.time, time.sleep)
bot = MergeBot()
DEFAULT_TIMEOUT = 60 * 5

def check_for_updates(sc):
    bot.check_for_updates()
    branch = bot.merge_branches()
    if branch:
        bot.push(branch)
    s.enter(DEFAULT_TIMEOUT, 1, check_for_updates, (sc,))

if __name__ == "__main__":
    s.enter(0, 1, check_for_updates, (s,))
    s.run()
