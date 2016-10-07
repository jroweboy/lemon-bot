#!/usr/bin/env python3

import subprocess
import yaml
import os, sys, stat, errno, shutil
import logging
import requests
import simplejson as json
import datetime

from urllib.parse import urlparse

logger = logging.getLogger('build')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('debug.log')
fh.setLevel(logging.DEBUG)
eh = logging.FileHandler('error.log')
eh.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(eh)
logger.addHandler(ch)

# TODO: Change this to use a yaml config file instead
# TODO: add multiple label support. Joining on a comma does an AND not an OR in github api, so we need to make multiple requests
LABEL_TO_FETCH = 'pr:bleeding-edge-merge'

GITHUB_API = 'https://api.github.com/repos'
PULL_REPOS = ['https://github.com/citra-emu/citra-bleeding-edge', 'https://github.com/citra-emu/citra']
MAIN_REPO = PULL_REPOS[1]
PUSH_REPO = 'git@github.com:citra-emu/citra-bleeding-edge'
# PUSH_REPO = 'git@github.com:jroweboy/lemon'

class TagMergeBot:
    ''' Fetches all the pull requests on a repository and merges all the pull requests with a specified tag on them. '''
    def __init__(self, main_repo, pull_repos, push_repo):
        repositories = []
        for repo in pull_repos:
            path_split = urlparse(repo).path.split("/")
            repository = {}
            repository['url'] = repo
            repository['owner'] = path_split[1]
            repository['name'] = path_split[2]
            repository['remote_name'] = '{owner}_{name}'.format(owner=repository['owner'], name=repository['name'])
            repositories.append(repository)
        self.repos = repositories
        self.previous_prs = {}
        self.current_prs = {}
        self.base_path = os.path.abspath(os.path.dirname(__file__))
        self.tracking_path = os.path.join(base_dir, 'tracking_repo')
        self.branch_name = 'bleeding_edge'
        self.main_repo = main_repo
        self.push_repo = {"name": "push_remote", "url": push_repo}

    def load_last_prs(self):
        self.previous_prs = {}
        if os.path.isfile('previous_run.json'):
            with open('previous_run.json') as infile:
                self.previous_prs = json.load(infile)

    def save_prs_to_file(self):
        with open('previous_run.json', 'w') as outfile:
            json.dump(self.current_prs, outfile)

    def fetch_latest_prs(self):
        # Fetch all the pull requests with the label (up to 100... hopefully citra doesn't ever get more than that)
        self.current_prs = {}
        for repo in self.repos:
            self.current_prs[repo['remote_name']] = []
            res = requests.get(GITHUB_API+'/{owner}/{repo}/issues?labels={labels}&per_page=100'.format(labels=LABEL_TO_FETCH, owner=repo['owner'], repo=repo['name']))
            if res.status_code != 200:
                logger.error("Could not retrive pull requests from github")
                return False
            issues = res.json()
            for issue in issues:
                pr_response = requests.get(issue['pull_request']['url'])
                if res.status_code != 200:
                    logger.warn("Couldn't fetch the PRs details for PR {pr}".format(pr=issue['']))
                    continue
                pr = pr_response.json()
                self.current_prs[repo['remote_name']].append({"number": pr['number'], "commit": pr['head']['sha'], "ref": pr['head']['ref']})
        return True

    def reclone(self):
        # TODO: Update the branches that need updating instead of wiping the folder and fresh cloning.
        if os.path.isdir(self.tracking_path):
            logger.debug("Removing tracking_repo")
            shutil.rmtree(self.tracking_path, ignore_errors=False, onerror=handleRemoveReadonly)
        logger.debug("Cloning the repository")
        _git("clone", "--recursive", self.main_repo, self.tracking_path, cwd=self.base_path)
        # setup the pull/push remotes
        for repo in self.repos:
            _git("remote", "add", repo['remote_name'], repo['url'], cwd=self.tracking_path)
        _git("remote", "add", self.push_repo['name'], self.push_repo['url'], cwd=self.tracking_path)

    def pull_branches(self):
        for repo in self.repos:
            for pr in self.current_prs[repo['remote_name']]:
                _git("fetch", repo['remote_name'], "pull/{0}/head:{1}".format(pr['number'], pr['ref']), cwd=self.tracking_path)

    def merge(self):
        # _git("branch", "-D", branch_name, cwd=self.repo_path)
        # _git("checkout", "master", cwd=self.repo_path)
        # checkout a new branch based off master
        _git("checkout", "-b", self.branch_name, cwd=self.tracking_path)
        total_failed = 0
        for repo in self.repos:
            for pr in self.current_prs[repo['remote_name']]:
                retval, _ = _git("merge", pr["ref"], cwd=self.tracking_path)
                if retval != 0:
                    _git("merge", "--abort", cwd=self.tracking_path)
                    logger.warn("Branch ({0}, {1}) failed to merge.".format(pr["ref"], pr["id"]))
                    total_failed += 1
        return total_failed

    def push(self):
        _git("push", "-f", self.push_repo["name"], self.branch_name, cwd=self.tracking_path)

# TODO: Use python git instead of calling git from the shell.
def _git(*args, cwd=None):
    command = ["git"] + list(args)
    logger.debug(" git command: " + " ".join(command))
    if not cwd:
        logger.warn("Cowardly refusing to call the previous git command without a working directory")
        return
    p = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if stdout:
        logger.debug("  stdout: " + stdout.decode("utf-8"))
    if stderr:
        logger.debug("  stderr: " + stderr.decode("utf-8"))
    return p.returncode, stdout.decode("utf-8")

def handleRemoveReadonly(func, path, exc):
  excvalue = exc[1]
  if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
      os.chmod(path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
      func(path)
  else:
      raise

if __name__ == "__main__":
    logger.info("=== Starting build at {date} ===".format(date=datetime.datetime.now()))
    logger.debug("Pulling the latest from master")
    base_dir = os.path.abspath(os.path.dirname(__file__))
    logger.debug("Checking for merge bot updates")
    _git("fetch", "origin", cwd=base_dir)
    _, stdout = _git("rev-list", "HEAD...origin/master", "--count", cwd=base_dir)
    if stdout and int(stdout) > 0:
        logger.info("=> Changes detected. Pulling latest version and restarting the application")
        _git("pull", "origin", "master", cwd=base_dir)
        os.execv(sys.executable, [sys.executable] + sys.argv)
        sys.exit(0)
    else:
        logger.debug("=> No changes to the script repo were detected. Continuing.")

    t = TagMergeBot(MAIN_REPO, PULL_REPOS, PUSH_REPO)
    ret = t.fetch_latest_prs()
    if not ret:
        logger.error("Error occurred. Aborting early")
        sys.exit(-1)
    logger.debug("Loading last run's information")
    t.load_last_prs()
    if t.previous_prs == t.current_prs:
        logger.info("No changes since last run. Exiting.")
        sys.exit(0)
    if not t.current_prs:
        logger.warn("No PRs to merge. Add the label {label} to some PRs".format(label=LABEL_TO_FETCH))
        sys.exit(0)
    # actually merge the branches and carry on.
    # TODO: Rework this whole workflow to be sane.
    # m = MergeBot(PULL_REPOS, PUSH_REPO)
    t.reclone()
    t.pull_branches()
    failed = t.merge()
    logger.info("Number of failed merges: {failed}".format(failed=failed))
    t.push()

    # save this runs information
    t.save_prs_to_file()
