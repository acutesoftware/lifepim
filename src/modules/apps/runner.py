import argparse
import os
import sys

from modules.apps import schema as apps_model


def _parser():
    parser = argparse.ArgumentParser(prog="lifepim-run", description="Launch a registered LifePIM App asynchronously.")
    parser.add_argument("--owner-user-id", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("app", help="App id, key, title slug, or import path.")
    parser.add_argument("app_args", nargs=argparse.REMAINDER, help="Arguments passed through to the App.")
    return parser


def _run_cli(argv):
    args = _parser().parse_args(argv)
    apps_model.ensure_apps_schema()
    app = apps_model.resolve_app_identifier(args.app, owner_user_id=args.owner_user_id)
    if not app:
        print(f"ERROR: LifePIM App not found: {args.app}", file=sys.stderr)
        return 2
    try:
        action = apps_model.launch_action(
            app["app_id"],
            extra_args=args.app_args,
            trigger_source="cli",
            owner_user_id=args.owner_user_id,
        )
    except Exception as exc:
        print(f"ERROR: Could not launch LifePIM App '{app.get('title') or args.app}': {exc}", file=sys.stderr)
        return 1
    print(f"Starting LifePIM App: {app.get('title')}")
    print(f"Run ID: {action.get('app_run_id')}")
    print("Status: Starting")
    return 0


def _run_worker(argv):
    if not argv:
        print("ERROR: Missing App Run ID.", file=sys.stderr)
        return 2
    try:
        run_id = int(argv[0])
    except ValueError:
        print(f"ERROR: Invalid App Run ID: {argv[0]}", file=sys.stderr)
        return 2
    run = apps_model.run_app_worker(run_id)
    if not run:
        print(f"ERROR: App Run not found: {run_id}", file=sys.stderr)
        return 2
    return 0 if run.get("status") == "Completed" else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_worker":
        return _run_worker(argv[1:])
    return _run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
