#!/usr/bin/env python3

import subprocess
import yaml
import os
import logging
# create logger with 'spam_application'
logger = logging.getLogger('build')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('debug.log')
fh.setLevel(logging.DEBUG)
# create file handler with a higher log level
eh = logging.FileHandler('error.log')
eh.setLevel(logging.WARN)
# create a stream handler for debugging
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(eh)
logger.addHandler(ch)

class MergeBot():
    def __init__(self, config_file="merge_list.yml"):
        self.base_dir = os.path.abspath(os.path.dirname(__file__))
        self._tracking_dirname = "tracking_repo"
        self._config_file = os.path.join(self.base_dir, config_file)
        self._reload_config()

    def _reload_config(self):
        yml = None
        with open(self._config_file) as f:
            yml = yaml.safe_load(f)
        if not yml:
            logger.error("Failed to open and parse the yaml file")
            return False

        self.tracking_repo = {"name": yml["tracking_repository"][0]["name"], "url": yml["tracking_repository"][0]["url"]}
        self.repo_path = os.path.join(self.base_dir, self._tracking_dirname)
        if not os.path.exists(self.repo_path):
            _git("clone", "--recursive", self.tracking_repo["url"], self._tracking_dirname, cwd=self.base_dir)
        _git("remote", "add", self.tracking_repo["name"], self.tracking_repo["url"], cwd=self.repo_path)
        self.push_repo = {"name": yml["push_repository"][0]["name"], "url": yml["push_repository"][0]["url"]}
        _git("remote", "add", self.push_repo["name"], self.push_repo["url"], cwd=self.repo_path)

        for remote in yml["other_remotes"]:
            _git("remote", "add", remote["name"], remote["url"], cwd=self.repo_path)

        # update to the latest master
        _git("checkout", "master", cwd=self.repo_path)
        _git("fetch", self.tracking_repo["name"], "master", cwd=self.repo_path)
        _git("reset", "--hard", self.tracking_repo["name"] + "/master", cwd=self.repo_path)

        self._branches = [{
            "name": branch.get("branch"),
            # TODO: make this a proper class. There are two kinds of branches here.
            # One is a remote/name branch the other is a fetch pull/ID/HEAD:name
            # Can easily be two different classes with the same interface
            "pr_id": branch.get("pr_id"),
            "remote": branch.get("remote"),
            "required": branch.get("required", False),
        } for branch in yml["merge_list"]]
        branch_name = ",".join([branch["name"] for branch in self._branches]) or "no branches?"
        logger.info("Merging the following branches: " + branch_name)

    def check_for_updates(self):
        self._check_self_for_updates()
        self._check_remotes_for_updates()
        # TODO Actually determine if we need to update
        return True

    def _check_self_for_updates(self):
        _git("pull", "origin", "master", cwd=self.base_dir)
        # if changed...
        self._reload_config()

    def _check_remotes_for_updates(self):
        for branch in self._branches:
            if branch["remote"]:
                _git("fetch", branch["remote"], ":".join([branch["name"], branch["name"]]), cwd=self.repo_path)
                # _git("branch", branch["name"], "/".join([branch["remote"],branch["name"]]), cwd=self.repo_path)
            else:
                _git("fetch", self.tracking_repo["name"], "pull/{0}/head:{1}".format(branch["pr_id"], branch["name"]), cwd=self.repo_path)

    def merge_branches(self):
        branch_name = ",".join((branch["name"] for branch in self._branches))
        # delete the previous branch if one exists
        _git("branch", "-D", branch_name, cwd=self.repo_path)
        # checkout a new branch based off master
        _git("checkout", "master", cwd=self.repo_path)
        _git("checkout", "-b", branch_name, cwd=self.repo_path)
        new_branch_name = branch_name
        # merge them all in
        for branch in self._branches:
            retval = _git("merge", branch["name"], cwd=self.repo_path)
            if retval != 0:
                _git("merge", "--abort", cwd=self.repo_path)
                if branch["required"]:
                    logger.error("ABORT! Required branch ({0}, {1}) failed to merge".format(branch["pr_id"] or branch["remote"], branch["name"]))
                    return False
                else:
                    logger.warn("Non required branch ({0}, {1}) failed to merge.".format(branch["pr_id"] or branch["remote"], branch["name"]))
                    # change the branch name to reflect it failed
                    new_branch_name.replace(branch["name"], branch["name"]+"(FAILED)")
        # checkout the new branch_name including failed
        if not branch_name == new_branch_name:
            _git("checkout", "-b", new_branch_name, cwd=self.repo_path)
            _git("branch", "-D", branch_name, cwd=self.repo_path)
        return new_branch_name

    def push(self, branch_name):
        _git("push", "--delete", self.push_repo["name"], branch_name, cwd=self.repo_path)
        _git("push", "-f", self.push_repo["name"], branch_name, cwd=self.repo_path)

def _git(*args, cwd=None):
    command = ["git"] + list(args)
    logger.debug(" git command: " + " ".join(command))
    if not cwd:
        logger.warn("Cowardly refusing to call the previous git command without a working directory")
        return
    p = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if stdout:
        logger.debug("  stdout: " + str(stdout))
    if stderr:
        logger.debug("  stderr: " + str(stderr))
    return p.returncode

if __name__ == "__main__":
    bot = MergeBot()
    bot.check_for_updates()
    branch = bot.merge_branches()
    if branch:
        bot.push(branch)

# Reloading config
# Git Command: git remote add tracking https://github.com/citra-emu/citra
# Git Command: git remote add push_repo https://github.com/jroweboy/lemon
# Git Command: git remote add jroweboy https://github.com/jroweboy/citra
# Git Command: git remote add lemon https://github.com/jroweboy/lemon
# Git Command: git pull origin master
# Reloading config
# Git Command: git remote add tracking https://github.com/citra-emu/citra
# Git Command: git remote add push_repo https://github.com/jroweboy/lemon
# Git Command: git remote add jroweboy https://github.com/jroweboy/citra
# Git Command: git remote add lemon https://github.com/jroweboy/lemon
# Git Command: git fetch jroweboy squirrel
# Git Command: git fetch tracking pull/2042/head:dynarmic
# Git Command: git fetch tracking pull/1995/head:inputcore
# Git Command: git fetch tracking pull/1753/head:framelayouts
# Git Command: git fetch tracking pull/2006/head:pause_exit2
# Git Command: git fetch tracking pull/2024/head:update-boss-code
# Git Command: git fetch https://github.com/citra-emu/citra
# Git Command: git reset --hard tracking/master
# #Git Command: git clean -ffdx
# Git Command: git branch -d squirrel|dynarmic|inputcore|framelayouts|pause_exit2|update-boss-code
# Git Command: git checkout -b squirrel|dynarmic|inputcore|framelayouts|pause_exit2|update-boss-code
