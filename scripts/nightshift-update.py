#!/usr/bin/env python3
"""Release selection and cooperative, between-run updates for symlink installs."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

COMMUNITY = "https://github.com/doctor-ew/nightshift-community.git"


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE,
        timeout=30, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}).strip()


def config_path():
    return Path(os.environ.get("NIGHTSHIFT_HOME", str(Path.home() / ".nightshift"))) / "updates.json"


def settings():
    path = config_path()
    data = json.loads(path.read_text()) if path.exists() else {}
    return {**data, "source": os.environ.get("NIGHTSHIFT_UPDATE_SOURCE", data.get("source", COMMUNITY)),
            "channel": os.environ.get("NIGHTSHIFT_UPDATE_CHANNEL", data.get("channel", "stable"))}


def validate(data):
    if not data["source"] or data["source"].startswith("-"):
        raise ValueError("invalid update source")
    channel = data["channel"]
    if channel != "stable" and not channel.startswith("branch:"):
        raise ValueError("channel must be stable or branch:<name>")
    if channel.startswith("branch:"):
        subprocess.run(["git", "check-ref-format", "refs/heads/" + channel[7:]],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def select(root, data):
    source, channel = data["source"], data["channel"]
    if channel == "stable":
        tags = git(root, "ls-remote", "--tags", "--refs", source).splitlines()
        versions = []
        for line in tags:
            match = re.fullmatch(r"[0-9a-f]+\s+refs/tags/v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", line)
            if match:
                versions.append(tuple(map(int, match.groups())))
        if not versions:
            raise ValueError("no stable release tags; retaining installed build")
        ref = "refs/tags/v" + ".".join(map(str, max(versions)))
    else:
        ref = "refs/heads/" + channel[7:]
    git(root, "fetch", "--quiet", "--no-tags", source, ref)
    revision = git(root, "rev-parse", "FETCH_HEAD^{commit}")
    version = git(root, "show", revision + ":VERSION")
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("invalid release VERSION")
    if channel == "stable" and ref != "refs/tags/v" + version:
        raise ValueError("release tag and VERSION disagree")
    return revision, ref


def update(root, data, apply):
    pending = Path(git(root, "rev-parse", "--absolute-git-dir")) / "nightshift-install-pending.json"
    if apply and pending.exists():
        refresh_install(root, json.loads(pending.read_text()))
        pending.unlink()
    revision, ref = select(root, data)
    result = {**data, "ref": ref, "revision": revision, "status": "available"}
    if revision == git(root, "rev-parse", "HEAD"):
        result["status"] = "current"
    elif apply:
        expected = "main" if data["channel"] == "stable" else data["channel"][7:]
        branch = git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
        if branch != expected or git(root, "status", "--porcelain"):
            result["status"] = "deferred-dirty-or-development-checkout"
        else:
            # No checkout, reset, force, merge commit, or implicit source fallback.
            git(root, "merge", "--ff-only", revision)
            result["status"] = "updated"
            if data.get("install_args"):
                # New adapter/helper files also need installation, not merely
                # fast-forwarding existing symlink targets. Retain custom targets.
                pending.write_text(json.dumps(data["install_args"]))
                refresh_install(root, data["install_args"])
                pending.unlink()
    print(json.dumps(result), file=sys.stderr)
    return result


def refresh_install(root, args):
    try:
        subprocess.run(["bash", str(root / "install.sh"), *args],
                       check=True, stdout=sys.stderr)
    except subprocess.SubprocessError as exc:
        # Launching after a partial adapter refresh is not safe. Keep a retry
        # marker and require a successful repair before the next factory run.
        raise RuntimeError("adapter refresh failed; run sync --apply to retry") from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--configure", action="store_true")
    parser.add_argument("--source")
    parser.add_argument("--channel")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--run", nargs=argparse.REMAINDER)
    parser.add_argument("--install-args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    data = settings()
    for key in ("source", "channel"):
        if getattr(args, key) is not None:
            data[key] = getattr(args, key)
    validate(data)
    if args.install_args is not None:
        data["install_args"] = args.install_args
    if args.configure:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as out:
            json.dump(data, out)
        os.replace(out.name, path)
        print(json.dumps(data))
        return 0
    root = args.project.resolve()
    try:
        common = Path(git(root, "rev-parse", "--git-common-dir"))
    except subprocess.SubprocessError:
        # Copy installs remain usable, but cannot be updated with Git.
        common = config_path().parent
        common.mkdir(parents=True, exist_ok=True)
    if not common.is_absolute():
        common = root / common
    with (common / "nightshift-update.lock").open("a") as lock:
        exclusive = False
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            exclusive = True
        except BlockingIOError:
            print("nightshift: active run; update application deferred", file=sys.stderr)
        try:
            if args.run is None or os.environ.get("NIGHTSHIFT_SYNC_CHECK", "on") != "off":
                if exclusive:
                    update(root, data, args.apply or (args.run is not None and not args.check))
                elif args.run is None:
                    return 75
        except RuntimeError as exc:
            print("nightshift: " + str(exc), file=sys.stderr)
            return 1
        except (subprocess.SubprocessError, ValueError) as exc:
            # Avoid echoing source URLs or credential-bearing command arguments.
            print("nightshift: update unavailable or unsafe; installed build retained (" + type(exc).__name__ + ")", file=sys.stderr)
            if args.run is None:
                return 1
        if args.run is None:
            return 0
        fcntl.flock(lock, fcntl.LOCK_SH)
        os.set_inheritable(lock.fileno(), True)
        env = {**os.environ, "NIGHTSHIFT_UPDATE_GUARD": "1"}
        child = subprocess.Popen(["bash", str(root / "scripts/nightshift-factory.sh"), *args.run],
                                 env=env, pass_fds=(lock.fileno(),))
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda number, _frame: child.send_signal(number))
        return child.wait()


if __name__ == "__main__":
    sys.exit(main())
