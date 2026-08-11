# Apps Tab

The Apps tab is a catalogue and launcher for things the user opens to do work.
It is not limited to installed programs. An App can be an application, code
project, repository, script, command, website, database, service, or other
launchable object.

Apps are stored in SQLite. The Apps tab stores metadata, launch actions, Area
membership, and icon references. It does not copy source projects or application
install folders into LifePIM.

The Apps routes are implemented in `src/modules/apps/routes.py`. The database
model is implemented in `src/modules/apps/schema.py`. Importers live under
`src/modules/apps/importers/`.

## Use

Open:

```text
http://127.0.0.1:9741/apps/
```

Main views:

- All: all enabled Apps in the selected Area.
- Favorites: Apps marked as favourite.
- Recent: Apps launched through LifePIM, ordered by last used date.
- Projects: `Development Project` and `Repository` Apps.
- Scripts: `Script`, `Command`, `SQL Script`, and `Utility` Apps.
- Applications: traditional application-like Apps.

Display modes:

- Grid: launcher-style cards with icon, name, kind, and Area summary.
- List: table view for scanning names, kinds, Areas, locations, recent usage,
  and favourite status.

The right inspector shows the selected App, its icon, kind, Areas, path,
repository URL, website URL, language, usage counts, tags, description,
configured actions, latest run status, and recent run history.

## Finding Apps

Use the left Area/sidebar navigation to filter Apps by Area. Apps can belong to
more than one Area, so the same App can appear under each relevant Area.

Use the saved view tabs across the Apps page to narrow by purpose:

```text
All | Favorites | Recent | Projects | Scripts | Applications
```

The Apps list also supports free-text search. Search matches App metadata and
action metadata, including:

- title
- description
- kind
- path
- repository URL
- website URL
- language
- tags
- action command
- action arguments
- action name

## Launching Apps

Each App can have one or more launch actions. The default action is used by the
main `Run` button.

Current action types:

| Action type | Behavior |
| --- | --- |
| `EXECUTABLE` | Starts the configured executable with optional arguments. |
| `COMMAND` | Runs the configured command through the shell. |
| `OPEN_FILE` | Opens a file, or opens a URL if the target is a web URL. |
| `OPEN_FOLDER` | Opens a local folder. |
| `OPEN_URL` | Opens a URL in the default browser. |
| `SYSTEM_DEFAULT` | Lets the operating system open the target with its default handler. |

Launching an App through LifePIM updates:

- `lp_app.last_used_date`
- `lp_app.usage_count`

Those fields drive the Recent saved view.

Launching also creates an App Run record in `lp_app_run`. The run record stores
what was requested, when it was requested, when it started, when it finished,
the process ID when available, exit code, trigger source, and stdout/stderr log
file paths.

The Apps page does not keep the browser request open while a long-running App
executes. LifePIM creates the run record, starts a short-lived background runner
process, and returns to the browser. The runner starts the configured App,
captures stdout and stderr to log files, waits for the App to exit, and marks
the run `Completed` or `Failed`.

For quick launch actions, this may appear as if nothing visible happened beyond
the App opening or the page returning. That is expected. The action is still
recorded as an App Run, but it may move from `Starting` to `Completed` very
quickly.

For long-running Apps, such as the LifePIM File Inventory Scanner / FileLister,
the selected App inspector shows:

- Status: `Starting`, `Running`, `Completed`, or `Failed`
- Requested time
- Started time
- Elapsed time while running
- Finished time after completion
- Duration after completion
- Exit code when available
- links to stdout and stderr logs

LifePIM does not auto-refresh the Apps page for this initial implementation. To
check whether a long-running App has finished, use the inspector's `Refresh`
link or refresh the browser page. While the App is still running, the elapsed
duration is recalculated from the stored start time. After it exits, the run
history shows the final status and total duration.

Recent runs are shown in the selected App inspector. This gives a small history
of the latest runs for that App without turning Apps into a general job manager.

### Parameterized Actions

An App Action can optionally define runtime parameters in
`lp_app_action.parameter_schema_json`. Supported parameter types are:

```text
text
integer
number
boolean
file
folder
select
```

Parameter names must be simple identifiers such as `input_file` or
`table_name`. Select parameters must define their allowed options.

The existing `arguments` field acts as a simple argument template when
parameters are present. Placeholders use `{name}` syntax only:

```text
--input "{input_file}" --database "{database}" --table "{table_name}"
```

LifePIM validates required values, select options, and unknown placeholders
before launching. It does not evaluate code, shell substitutions, expressions,
loops, conditions, or Jinja templates.

Actions also store execution-policy metadata:

- `agent_allowed`: whether the action is considered safe for future unattended
  Agent use.
- `requires_confirmation`: whether an automated caller should require user
  confirmation.

These fields are metadata only. They do not implement a scheduler or Agent
runtime.

## Add and Edit

Use:

```text
Apps -> + Add
Apps -> Edit
```

The App form stores:

- Name
- Kind
- Icon
- Favorite / Enabled
- Description
- Path
- Repository URL
- Website URL
- Language
- Version
- Tags
- Areas
- Actions
- Comments

Actions are edited as child rows. Each row has:

- default flag
- action name
- action type
- target / command
- working directory
- arguments
- execution parameters
- agent allowed
- requires confirmation

If no action is explicitly marked as default, LifePIM makes the first action the
default when saving.

Existing App Action IDs are preserved across normal edits. Saving an App updates
existing action rows, inserts new rows, and deletes only actions removed by the
user. If a Task uses an action, LifePIM refuses to delete that action or its App
until the Task binding is changed.

## Tasks That Use Apps

Tasks can bind directly to one `lp_app_action` through
`lp_tasks.app_action_id`. The Task supplies runtime values in
`lp_tasks.parameters_json`; the App Action owns the parameter definition and
argument template.

The App inspector shows related Tasks that use its actions. Each App Action also
offers `Create Task`, which opens the normal Tasks add screen with that action
preselected.

Running a parameterized action directly from Apps shows a small parameter form.
Running the same action from a Task uses the same validation and launch helper.
Launching does not mark any Task complete.

When a Task launches an App, LifePIM records the App Run with trigger source
`task`. The App execution is still asynchronous. A quick Task launch may return
with no obvious visible change except normal Task page behavior. A long-running
Task-launched App can be checked from the related App's inspector in the Apps
tab by refreshing the page and looking at Latest Run or Recent Runs.

Tasks do not own App Run history. The relationship remains:

```text
Task -> App Action -> App Run
```

This keeps Tasks and Apps separate while still showing what happened when an App
was executed.

## App Kinds

Current App kinds are:

```text
Application
Development Project
Repository
Script
Executable
Command
Web App
Website
Database
SQL Script
Development Environment
Service
Connection
Utility
Other
```

Kinds drive the saved views and fallback icon text. They do not restrict what
actions an App can have.

## Areas

Apps use a many-to-many Area relationship:

- `lp_app` stores the App record.
- `lp_app_area` stores Area membership.

This means one App can be visible in several contexts. For example, Blender can
belong to Design and 3D, while VS Code can belong to Development, AI, and
LifePIM.

The left sidebar filter matches Area IDs stored in `lp_app_area`. Parent Area
selection also includes child Area paths where the query uses the current Apps
Area filtering rules.

## Import Apps

Use:

```text
Apps -> Import
```

Import is an explicit user-driven workflow:

```text
Choose source
Scan
Review candidates
Select/deselect candidates
Adjust Kind and Area
Import Selected
```

Scanning does not create App records. Only `Import Selected` writes to the
database.

Current import sources:

- Dev Folders
- Taskbar
- Desktop

The import screen shows source tabs, scan controls, scan messages/errors, and a
candidate table. Candidates can be selected or unselected, and their Kind and
Area can be changed before import.

Candidate statuses:

| Status | Meaning |
| --- | --- |
| `NEW` | Candidate can be imported. |
| `EXISTS` | An equivalent App/action target already exists. |
| `INVALID` | The candidate could not be resolved or has no usable launch target. |

Existing and invalid candidates are disabled for import.

## Dev Folder Import

Dev Folder import is for code/software project folders.

Use:

```text
Apps -> Import -> Dev Folders
```

Choose:

- Root Folder
- Default Area
- Default Kind

The scanner reads immediate child folders only. It does not recursively turn
every source-code subfolder into an App.

Imported Dev Folder Apps usually get:

- Kind: selected default, normally `Development Project`
- Default action name: `Open Folder`
- Action type: `OPEN_FOLDER`
- Target: the project folder

The scanner records simple project hints when marker files are present, such as
`.git`, `package.json`, `pyproject.toml`, `requirements.txt`, Visual Studio
project files, Gradle files, or `Cargo.toml`.

If a Git remote URL can be found, it is stored as repository metadata.

## Taskbar Import

Taskbar import is for Windows applications pinned to the Taskbar.

Use:

```text
Apps -> Import -> Taskbar
```

The importer scans the Windows Taskbar pinned shortcut folder when available.
It resolves `.lnk` shortcut metadata through Windows shortcut handling and tries
to find:

- display name
- shortcut path
- executable target
- arguments
- working directory
- shortcut icon location

Imported Taskbar Apps usually get:

- Kind: `Application`
- Default action name: `Open`
- Action type: `EXECUTABLE`, when the resolved target is an executable
- Target: the resolved executable path

If a shortcut cannot be resolved, it is shown as `INVALID` instead of aborting
the whole scan.

## Desktop Import

Desktop import is for launchable shortcuts on the user and public Windows
Desktop.

Use:

```text
Apps -> Import -> Desktop
```

The importer scans supported shortcut files:

- `.lnk`
- `.url`

It ignores ordinary Desktop files such as documents, images, and text files.

Imported Desktop `.lnk` Apps usually become application records. Imported `.url`
shortcuts become web Apps with:

- Kind: `Web App`
- Action type: `OPEN_URL`
- Target: the shortcut URL

## Duplicate Detection

The importer checks candidates against existing Apps and App actions before
import.

Duplicate matching uses normalized values:

- executable/file/folder paths are expanded, normalized, lower-cased, and
  compared without trailing separators
- URL values are normalized by scheme, host, and trailing slash handling

The duplicate key is based on the launch target, not the title. This avoids
creating duplicate records for the same executable, folder, or website while
still allowing similarly named but different tools.

## Import Results and Provenance

When selected candidates are imported, LifePIM creates normal App records. There
is no separate imported-App mode in the main Apps UI.

For each imported candidate, LifePIM writes:

- `lp_app` row
- `lp_app_area` row when an Area is selected
- `lp_app_action` default action
- import source fields
- import metadata JSON

Provenance fields:

| Field | Meaning |
| --- | --- |
| `import_source` | Source type such as `DEV_FOLDER`, `TASKBAR`, or `DESKTOP`. |
| `import_source_path` | Folder or shortcut path the candidate came from. |
| `imported_date` | UTC import timestamp. |
| `import_metadata` | JSON metadata from the scanner/importer. |

The import result message shows how many Apps were imported and how many
existing Apps were skipped.

## Icons

Apps can show either an image icon or fallback text.

Image icon values are rendered when the stored `lp_app.icon` starts with:

```text
/static/
/media/
static/
media/
```

If no image URL is available, Apps show the stored icon text or a fallback based
on App kind, such as `A`, `P`, `S`, `DB`, or `App`.

## Imported Icon Materialisation

When importing executable Apps, LifePIM tries to extract the executable's
associated Windows icon.

The extraction flow is:

1. Resolve the executable path.
2. Extract the associated icon to a temporary/static LifePIM icon cache under:

```text
src/static/app_icons/
```

3. Convert that static icon value into a Media-backed icon.
4. Copy the icon file into:

```text
<DATA folder>/Media/imported/icons/
```

5. Register or update a matching `lp_media` row.
6. Store the App icon as:

```text
/media/file/<media_id>
```

The copied icon filename is content-hashed, so importing the same icon again
reuses the same materialised file instead of creating arbitrary duplicates.

The Media row stores the copied icon path, filename, extension, media type,
size, modified time, created time, and hash. The icon file itself remains on
disk under `Media/imported/icons`.

Imported App metadata records both:

- `extracted_icon`: the original extracted `/static/app_icons/...` value
- `media_icon`: the final `/media/file/<media_id>` value, when materialisation
  succeeds

## Seeing Materialised Icons

After materialisation, the Apps UI loads the icon through the Media route:

```text
/media/file/<media_id>
```

The icon should appear in:

- Apps grid cards
- Apps list icon column
- the selected App inspector

The materialised icon is also a normal Media-backed file row. It can be found in
the Media database by its `lp_media.path`, usually under:

```text
Media/imported/icons
```

If an App still shows a text fallback instead of an image, use:

```text
Apps -> Refresh Icons
```

Refresh Icons does two things:

1. For Apps with blank icons, it tries to extract and materialise an executable
   icon from the default executable action.
2. For Apps that still store old `/static/app_icons/...` icon values, it copies
   those icons into `Media/imported/icons`, creates the Media row, and updates
   the App to `/media/file/<media_id>`.

If a stored static icon file no longer exists and executable extraction also
fails, the App keeps its existing text/fallback display.

## Data Model

Core tables:

| Table | Purpose |
| --- | --- |
| `lp_app` | Main App metadata. |
| `lp_app_area` | Many-to-many App Area membership. |
| `lp_app_action` | Launch actions for Apps. |
| `lp_app_run` | Historical execution records for App launches. |
| `lp_media` | Media rows used for materialised imported icons. |

Important `lp_app` fields:

- `title`
- `app_key`
- `kind`
- `description`
- `icon`
- `favorite`
- `enabled`
- `path`
- `repository_url`
- `website_url`
- `language`
- `version`
- `tags`
- `comments`
- `import_source`
- `import_source_path`
- `imported_date`
- `import_metadata`
- `last_used_date`
- `usage_count`

Important `lp_app_action` fields:

- `action_name`
- `action_type`
- `command`
- `working_directory`
- `arguments`
- `parameter_schema_json`
- `agent_allowed`
- `requires_confirmation`
- `sort_order`
- `is_default`

Important `lp_app_run` fields:

- `app_id`
- `app_action_id`
- `status`
- `requested_at`
- `started_at`
- `finished_at`
- `process_id`
- `command`
- `arguments`
- `working_directory`
- `exit_code`
- `stdout_log`
- `stderr_log`
- `error_message`
- `trigger_source`

Supported App Run statuses:

```text
Starting
Running
Completed
Failed
```

`Completed` means the App exited with code `0`. `Failed` means the App could not
be started or exited with a non-zero code.

`app_key` is a readable identifier used by external launchers where available.
The built-in File Inventory Scanner uses:

```text
filelister
```

This allows the same registered App to be launched from outside the web UI.

## Command-Line Launching

LifePIM includes a reusable launcher:

```text
lifepim-run <app>
```

Examples:

```text
lifepim-run filelister
lifepim-run filelister --scan incremental
```

The launcher resolves the App from LifePIM's registered App records, creates an
App Run, starts the detached runner, prints the run ID, and exits promptly. It
does not wait for the App to finish.

On Windows, use the BAT wrapper from the LifePIM install folder:

```bat
C:\apps\LifePIM_Prod\lifepim-run.bat filelister
```

Arguments after the App identifier are passed through to the configured App.
LifePIM does not interpret App-specific arguments such as `--scan incremental`.
They are stored in the App Run record and passed to the App process.

## Operational Notes

Apps is a curated catalogue, not a full installed-software inventory. The current
importers deliberately scan high-value sources:

- Dev Folders: software projects the user maintains.
- Taskbar: applications the user has pinned.
- Desktop: shortcuts the user has explicitly placed.

Do not expect Apps import to scan the whole disk, Windows registry, Start Menu,
or every installed executable. Those would create noisy inventory data rather
than a useful launcher.

Scanning is safe to run repeatedly because it does not write database rows.
Importing is the step that writes records, and duplicate detection prevents
normal repeated imports from creating duplicate Apps.

Imported Apps can be edited normally after import. Add extra actions, change
Areas, set favorites, add tags, or replace icons through the standard Apps edit
form.
