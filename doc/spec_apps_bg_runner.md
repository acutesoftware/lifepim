# LifePIM Desktop — `lifepim-run` Application Launcher

## 1. Intent

Add a small, generic application launcher to `lifepim-desktop` so LifePIM Apps can be started asynchronously.

The primary use case is long-running Apps such as FileLister.

Currently, if an App takes 20 minutes to run, the LifePIM UI should not need to keep the HTTP request open for 20 minutes.

Desired behaviour:

```text
Apps > FileLister > Run
        ↓
LifePIM records a new run
        ↓
LifePIM starts FileLister independently
        ↓
UI immediately returns
        ↓
Status shows:

Running...
Started: 22:14:03
Elapsed: 00:07:42

        ↓
FileLister eventually exits
        ↓
Run becomes:

Completed
Started:   22:14:03
Completed: 22:34:18
Duration:  00:20:15
```

The same launcher must also be callable externally, allowing the exact same LifePIM App to be started from:

* LifePIM Apps UI
* Windows BAT files
* Aggie toolbar
* PowerShell
* Windows Task Scheduler
* a terminal

For example:

```text
lifepim-run filelister
```

or, where parameters are appropriate:

```text
lifepim-run filelister --scan incremental
```

All methods should use the same application definition and create the same LifePIM run-history records.

---

# 2. Design principle

Do NOT build a general task manager.

Do NOT add:

* Celery
* Redis
* RQ
* worker queues
* a permanent background daemon
* polling services
* heartbeat infrastructure
* scheduling infrastructure
* retry queues
* job priorities
* distributed execution

The operating system remains responsible for executing the process.

LifePIM is responsible only for:

1. knowing what App should be run;
2. recording that a run was requested;
3. launching it;
4. recording when it starts;
5. recording whether it completed or failed;
6. keeping stdout/stderr logs;
7. displaying that information.

Keep the implementation small and understandable.

---

# 3. Conceptual model

LifePIM already has the concept of an **App**.

Add the concept of an **App Run**.

```text
APP
"What executable thing is this?"

        ↓

APP RUN
"What happened when it was executed?"
```

An App can have many historical runs.

Example:

```text
FileLister

Run 151
    status: Completed
    started: 2026-08-11 21:02:03
    finished: 2026-08-11 21:22:11
    duration: 00:20:08

Run 152
    status: Running
    started: 2026-08-11 22:14:03
    elapsed: 00:08:14
```

---

# 4. `lifepim-run`

Implement a reusable command-line launcher within `lifepim-desktop`.

It should be callable conceptually as:

```text
lifepim-run <app>
```

Examples:

```text
lifepim-run filelister
lifepim-run load-json
lifepim-run backup-notes
```

Support passing arguments through to Apps where required.

For example:

```text
lifepim-run filelister --scan incremental
```

Do not unnecessarily impose a new parameter schema on individual Apps.

Existing Apps should continue accepting their own normal CLI arguments.

---

# 5. Important distinction: launcher vs worker

`lifepim-run` is only a launcher.

It should:

```text
lookup App
create run record
launch detached run process
return run ID
exit
```

A small child/wrapper process can then:

```text
mark run Running
execute configured App
wait for process
capture exit code
mark run Completed or Failed
exit
```

This wrapper is not a daemon.

There is exactly one short-lived wrapper process per App execution.

Once the launched App finishes, the wrapper exits.

---

# 6. Invocation flow from LifePIM UI

When the user presses:

```text
Apps
  > FileLister
      > Run
```

the web request must NOT execute FileLister synchronously.

Instead:

```text
1. Resolve the App definition.

2. Create an App Run record.

3. Launch the detached LifePIM runner.

4. Return immediately to the browser.

5. Redirect/render the App screen showing:

   Running...
```

The HTTP request must not remain connected for the duration of FileLister.

---

# 7. External invocation flow

External tools should also be able to call the launcher.

Example BAT file:

```bat
@echo off
C:\path\to\lifepim-desktop\lifepim-run.bat filelister --scan incremental
```

Aggie may then simply execute that BAT file.

Windows Task Scheduler may execute the same BAT file.

The external caller should not need:

* the LifePIM web server to be open;
* a browser;
* knowledge of the App's actual Python script;
* knowledge of LifePIM's internal database layout.

It only needs the LifePIM installation and App identifier.

---

# 8. App lookup

Prefer using the existing LifePIM App records and existing Apps architecture.

Do NOT introduce a second independent registry of executable applications.

Inspect the existing implementation and reuse its App identifiers/configuration.

The launcher should resolve an App using a stable identifier such as its existing ID, key, slug, or equivalent.

Preferred user-facing CLI:

```text
lifepim-run filelister
```

rather than:

```text
lifepim-run 347
```

Numeric ID support may be useful internally, but humans should be able to use a readable App name/key.

If the existing App data model does not have a suitable stable executable key, add the smallest clean field required.

Do not duplicate existing fields unnecessarily.

---

# 9. App execution definition

Reuse the existing Apps execution configuration wherever possible.

An executable App will normally need enough information to determine:

```text
command / executable
script or launch target
working directory
default arguments if any
```

Examples might ultimately resolve to:

```text
python src/apps/filelister/filelister.py
```

or:

```text
C:\Tools\someutility.exe
```

or another existing executable definition.

Do not assume every LifePIM App is Python.

Do not rewrite existing Apps merely to make them compatible with the launcher unless necessary.

---

# 10. Database: App Run records

Add a run-history table using the existing LifePIM database naming conventions.

Use the project's current migration/schema mechanism rather than creating an isolated ad-hoc schema system.

Conceptually:

```text
lp_app_run
```

or the equivalent naming convention already used in the project.

Recommended fields:

```text
id
app_id

status

requested_at
started_at
finished_at

process_id

command
arguments
working_directory

exit_code

stdout_log
stderr_log

error_message

trigger_source
```

Use appropriate existing LifePIM primary-key/date conventions.

Do not blindly use these exact SQL data types or names if established project conventions differ.

---

# 11. Status values

Keep statuses intentionally simple.

Required:

```text
Starting
Running
Completed
Failed
```

Meaning:

### Starting

Run record has been created but the child runner has not yet successfully begun execution.

### Running

The application process has been started.

### Completed

The application exited normally with exit code `0`.

### Failed

The launcher failed to start the App, or the App exited with a non-zero exit code.

Do NOT implement complicated workflow states.

`Cancelled` can be added later if LifePIM eventually gains a Stop function.

There is no Stop requirement in this implementation.

---

# 12. Timestamps

Store:

```text
requested_at
started_at
finished_at
```

Use the date/time conventions already established by LifePIM.

If the application stores timestamps internally as UTC, continue using UTC and convert for presentation consistently with the rest of LifePIM.

Do not invent a special timestamp convention for App Runs.

---

# 13. Duration

Do not continuously update elapsed time in the database.

Calculate duration when presenting it.

While running:

```text
duration = current_time - started_at
```

When complete:

```text
duration = finished_at - started_at
```

Example UI:

```text
Running...
00:12:43
```

Refreshing the page naturally recalculates this value.

No JavaScript timer or live polling is required for the initial implementation.

---

# 14. Refresh behaviour

The user explicitly wants manual refresh to be sufficient.

Do not add automatic polling unless the existing UI already has an appropriate generic mechanism that can be reused trivially.

The expected workflow is:

```text
Run
↓
Running...
↓
user presses Refresh later
↓
Running... 00:14:17

or

Completed 22:34:18
```

A normal browser page refresh is also acceptable.

If there is already a LifePIM-style Refresh button/component, reuse it.

---

# 15. Process execution

Use Python's normal process facilities, such as `subprocess`.

The LifePIM HTTP/web process must not remain the parent responsible for waiting for a long-running application.

The runner should be launched independently enough that:

* the web request can end immediately;
* closing the browser does not stop the job;
* an App continues running independently of that browser request.

On Windows, use the appropriate detached/new-process-group process flags.

Keep implementation portable where reasonably easy, but LifePIM must work correctly on its current Windows deployment.

Do not add a third-party process-management dependency merely for cross-platform abstraction.

---

# 16. Runner lifecycle

Conceptual pseudo-flow:

```python
def run_app(run_id):

    run = get_run(run_id)
    app = get_app(run.app_id)

    try:
        process = start_app(app)

        update_run(
            run_id,
            status="Running",
            started_at=now(),
            process_id=process.pid
        )

        exit_code = process.wait()

        if exit_code == 0:
            update_run(
                run_id,
                status="Completed",
                finished_at=now(),
                exit_code=0
            )

        else:
            update_run(
                run_id,
                status="Failed",
                finished_at=now(),
                exit_code=exit_code
            )

    except Exception as exc:
        update_run(
            run_id,
            status="Failed",
            finished_at=now(),
            error_message=str(exc)
        )
```

Follow project architecture/style rather than copying this literally.

---

# 17. stdout and stderr

Capture stdout and stderr from Apps.

Do NOT store potentially huge console output in SQLite.

Write logs to files.

Use a predictable LifePIM data location following existing data-directory conventions.

Conceptually:

```text
data/
    app_runs/
        152/
            stdout.log
            stderr.log
```

or an equivalent existing LifePIM log path.

Store the resulting paths in the run record.

If stdout/stderr can sensibly be combined into one execution log using existing project conventions, that is also acceptable.

The main goal is:

* logs survive after execution;
* long-running output does not bloat the LifePIM database;
* troubleshooting failed runs is possible.

---

# 18. App UI changes

Enhance the existing Apps UI rather than building a new execution screen.

For an executable App, show a Run action.

Immediately after launching, show its current/latest run information.

Example:

```text
FileLister

Status
Running...

Started
11 Aug 2026 22:14:03

Elapsed
00:08:17

[Refresh]
```

After completion:

```text
Status
Completed

Started
11 Aug 2026 22:14:03

Completed
11 Aug 2026 22:34:18

Duration
00:20:15

Exit code
0
```

If failed:

```text
Status
Failed

Started
11 Aug 2026 22:14:03

Finished
11 Aug 2026 22:14:06

Exit code
1

[View Log]
```

Follow the existing LifePIM visual style.

Do not add flashy dashboards or progress animations.

---

# 19. Run history

On an App detail page, provide a small recent run history.

For example:

```text
Recent Runs

Status       Started              Duration
Completed    11 Aug 22:14:03      00:20:15
Completed    10 Aug 21:05:42      00:18:51
Failed       09 Aug 19:12:03      00:00:04
```

A modest number such as the latest 10–20 runs is sufficient.

Do not build a full job-history management subsystem.

If there is already a suitable generic list/table UI, reuse it.

---

# 20. Trigger source

Record how a run was launched.

Recommended values:

```text
manual
cli
task
scheduled
```

For the current implementation:

LifePIM Apps UI:

```text
manual
```

Direct `lifepim-run` invocation:

```text
cli
```

The `task` and `scheduled` values establish a useful convention for later but do not require implementation of task/schedule launching in this change.

If Aggie calls `lifepim-run`, it may simply be recorded as `cli`.

No Aggie-specific integration is required.

---

# 21. BAT launcher

Provide a simple Windows launcher at an appropriate project location.

For example:

```text
lifepim-run.bat
```

Its purpose is only to ensure the correct LifePIM Python environment and CLI module are called.

Conceptually:

```bat
@echo off
<LifePIM venv python> -m <lifepim runner module> %*
```

Do not hard-code the developer's machine-specific absolute paths into committed source.

Work out the LifePIM project/venv location using the same conventions as other project startup BAT files if such conventions already exist.

Review existing launcher scripts before implementing this.

---

# 22. CLI output

`lifepim-run` should give useful concise output.

Example:

```text
Starting LifePIM App: FileLister
Run ID: 152
Status: Starting
```

The launcher should then return promptly.

It should NOT wait 20 minutes and stream the entire App execution when operating in its normal asynchronous mode.

The run can subsequently be inspected in LifePIM.

---

# 23. Optional foreground/debug mode

If trivial to implement, it is acceptable to provide an explicit foreground mode such as:

```text
lifepim-run filelister --foreground
```

This could execute synchronously for debugging.

However:

* asynchronous launch is the primary behaviour;
* foreground mode is optional;
* do not complicate the implementation to provide it.

Be careful not to consume App-specific arguments accidentally.

If argument passthrough makes `--foreground` ambiguous, use another clean CLI convention or leave foreground mode out.

---

# 24. Parameters / argument passthrough

The launcher must allow external callers to provide parameters to the underlying App.

For example:

```text
lifepim-run filelister --scan incremental
```

should ultimately execute the configured FileLister App with:

```text
--scan incremental
```

Do not make LifePIM understand FileLister's parameter semantics.

The launcher merely passes them through.

This is important because Apps should remain reusable CLI programs.

---

# 25. Existing LifePIM App UI parameters

Inspect the current Apps > Run implementation.

If LifePIM already stores or collects runtime parameters, preserve that behaviour and route those parameters through `lifepim-run`.

Do not regress existing App launching functionality.

The new launcher should centralise execution rather than create a competing execution path.

Preferred architecture:

```text
                    LifePIM Apps UI
                           │
                           │
Aggie / BAT ───────────────┼────> lifepim-run
                           │
Task Scheduler ────────────┘
                                   │
                                   ↓
                            App definition
                                   │
                                   ↓
                            executable App
```

There should be one common App execution mechanism.

---

# 26. Apps remain standalone

A key architectural requirement:

> LifePIM Apps must remain ordinary executable programs.

FileLister should not need to import LifePIM's web application or manually update LifePIM's run table.

The wrapper handles lifecycle tracking.

An App should be able to remain conceptually as simple as:

```python
def main():
    args = parse_args()
    perform_work(args)

if __name__ == "__main__":
    main()
```

This separation is intentional.

---

# 27. Database locking / process safety

The runner will update the LifePIM SQLite database from a separate process.

Use the same database-access layer and connection conventions already used by the application wherever possible.

Connections should be opened and closed normally.

Do not retain a database connection inherited from the web process across process creation.

The child should establish its own database connection.

Keep transactions short:

```text
update Running
commit
close/continue

...

update Completed
commit
```

Do not hold a SQLite transaction open while the App runs for 20 minutes.

---

# 28. Concurrent runs

Do not build a queue or concurrency manager.

It is acceptable for separate Apps to run simultaneously.

For the same App, preserve the simplest sensible behaviour.

Preferred initial behaviour:

* allow another run unless existing application semantics make this unsafe;
* clearly show each execution as a separate run record.

However, if the existing App definition already has a single-instance concept, respect it.

Do not invent complex locking for this feature.

For FileLister specifically, avoid introducing FileLister-specific code into the generic launcher.

---

# 29. Stale `Running` records

Do not implement heartbeat monitoring.

Normally the wrapper will always change:

```text
Running
```

to either:

```text
Completed
```

or:

```text
Failed
```

If the entire machine crashes, a run record could remain `Running`.

That is acceptable for the first implementation.

If a very small startup/display-time PID existence check fits naturally, it may mark obviously dead runs as failed/interrupted, but this is not required.

Do not add a monitoring daemon just to solve stale records.

---

# 30. Restart behaviour

A running App should not depend on the browser remaining open.

Where practical, it should also not depend on the LifePIM web process remaining alive.

The detached wrapper/App process should be independent of the HTTP request that launched it.

If LifePIM Desktop is restarted while FileLister is running, the running process should ideally continue and eventually update its run record.

Implement this using normal OS process detachment rather than adding infrastructure.

---

# 31. Security

Do not build arbitrary shell-command execution from user-supplied web text.

LifePIM should execute commands derived from registered App definitions.

Runtime parameters should be passed as an argument list rather than concatenated into a shell command wherever possible.

Prefer:

```python
subprocess.Popen([
    executable,
    script,
    "--scan",
    "incremental",
])
```

rather than:

```python
subprocess.Popen(
    f"{executable} {script} --scan {user_value}",
    shell=True
)
```

Avoid `shell=True` unless an existing registered App explicitly requires shell execution.

---

# 32. Error cases

Handle at least:

### Unknown App

```text
lifepim-run not-a-real-app
```

Return a clear error and do not create a misleading running job.

### Executable missing

Create/finish the run as:

```text
Failed
```

and record a useful error.

### App cannot start

Status:

```text
Failed
```

### App exits non-zero

Status:

```text
Failed
```

Store exit code.

### App exits zero

Status:

```text
Completed
```

### Log directory cannot be created

Fail cleanly and record as much useful diagnostic information as possible.

---

# 33. Do not confuse Apps and Tasks

This feature is primarily an **App execution mechanism**.

Although a LifePIM Task may eventually invoke an App, do not merge the Apps and Tasks data models as part of this work.

Future relationship:

```text
Task
   ↓ invokes
App
   ↓ creates
App Run
```

For this implementation, only establish the reusable execution mechanism.

---

# 34. Future compatibility

The implementation should make these future calls straightforward:

```text
Apps UI
    → lifepim-run filelister

Task
    → lifepim-run load-json ...

Scheduled Task
    → lifepim-run backup ...

Aggie
    → lifepim-run filelister

Windows Task Scheduler
    → lifepim-run filelister
```

But only the Apps UI and direct CLI invocation are required now.

Do not build the future integrations yet.

---

# 35. Code organisation

Inspect the existing `lifepim-desktop` source tree before deciding exact module locations.

Prefer code underneath the existing Apps application/service structure.

A likely conceptual split is:

```text
Apps service
    app lookup
    create run
    query run history

Runner CLI
    parse command
    request run
    spawn detached worker

Runner worker
    execute App
    update lifecycle
    capture logs
```

These may be fewer files if the code remains clearer that way.

Do not create excessive abstraction for a small feature.

---

# 36. Preserve existing functionality

Before changing code:

1. inspect existing Apps models/tables;
2. inspect existing Apps routes;
3. inspect current Run handling;
4. inspect database migration/schema conventions;
5. inspect existing command/BAT launchers;
6. inspect configured LifePIM data/config path handling.

Reuse existing conventions.

Do not:

* rename unrelated tables;
* restructure unrelated Apps code;
* change untracked files;
* rewrite existing functionality unnecessarily;
* create duplicate application registries;
* alter other tabs unless necessary.

This should be a tightly scoped enhancement.

---

# 37. Tests

Add focused tests appropriate to the existing project test style.

At minimum verify:

### Successful App

A tiny test App exits `0`.

Expected:

```text
Starting
→ Running
→ Completed
exit_code = 0
started_at populated
finished_at populated
```

### Failed App

Test App exits non-zero.

Expected:

```text
Failed
exit_code populated
```

### Missing executable

Expected:

```text
Failed
error_message populated
```

### Asynchronous UI launch

The Apps Run endpoint must return without waiting for the test App to finish.

Use a deliberately short sleeping test process if useful.

### CLI lookup

Valid readable App identifier resolves correctly.

### Argument passthrough

Given:

```text
lifepim-run test-app --foo bar
```

the test App receives:

```text
--foo
bar
```

### Logs

stdout and stderr are written to the expected run log files.

---

# 38. Manual smoke test

Once implemented, perform a real smoke test using FileLister or another existing longer-running App.

### Test A — LifePIM UI

1. Open Apps.
2. Select FileLister.
3. Click Run.
4. Confirm the page returns promptly.
5. Confirm status shows `Running`.
6. Confirm `started_at` is visible.
7. Wait or continue using LifePIM.
8. Refresh.
9. Confirm elapsed duration updates.
10. After FileLister exits, refresh.
11. Confirm status shows `Completed`.
12. Confirm completion timestamp.
13. Confirm total duration.
14. Confirm stdout/stderr logs exist.

### Test B — command line

Run:

```text
lifepim-run filelister
```

Confirm:

1. command returns promptly;
2. run appears in LifePIM;
3. status is `Running`;
4. it later changes to `Completed`.

### Test C — BAT/Aggie-compatible invocation

Run the provided BAT wrapper manually.

Confirm it produces exactly the same type of App Run record.

No Aggie code changes are required.

---

# 39. Definition of done

This change is complete when:

* [ ] LifePIM has a reusable `lifepim-run` launcher.
* [ ] A registered App can be selected by a readable identifier.
* [ ] Apps can receive normal CLI parameters.
* [ ] An App Run record is created for every invocation.
* [ ] Run status supports Starting / Running / Completed / Failed.
* [ ] Start and finish timestamps are recorded.
* [ ] Exit codes are recorded.
* [ ] stdout/stderr are captured to files.
* [ ] LifePIM Apps > Run uses the common launcher.
* [ ] Clicking Run returns promptly instead of waiting for the App.
* [ ] Apps UI shows the latest run status.
* [ ] Running Apps show calculated elapsed time.
* [ ] Completed Apps show completion time and duration.
* [ ] Recent run history is visible on the App.
* [ ] Manual Refresh reflects the current database status.
* [ ] `lifepim-run` can be called independently of the web UI.
* [ ] A Windows BAT wrapper is available for Aggie / Task Scheduler use.
* [ ] External runs appear in the same LifePIM run history.
* [ ] Existing App execution behaviour and parameters are preserved.
* [ ] No job queue, daemon, scheduler, heartbeat service, or new task-management framework has been introduced.
* [ ] Existing unrelated LifePIM functionality remains unchanged.

---

# 40. Architectural outcome

After this change, LifePIM should have one deliberately simple execution path:

```text
                 LifePIM Apps UI
                        │
                        │
Aggie toolbar ──────────┤
                        │
BAT / PowerShell ───────┤
                        │
Task Scheduler ─────────┘
                        │
                        ▼
                   lifepim-run
                        │
             create App Run record
                        │
             launch detached wrapper
                        │
                        ▼
                   LifePIM App
                        │
                 normal CLI program
                        │
                        ▼
             Completed / Failed
```

The important architectural principle is:

> A LifePIM App is an ordinary executable program. `lifepim-run` is merely the common mechanism for launching it and recording what happened.

This gives LifePIM asynchronous execution where useful without turning LifePIM into a process manager.
