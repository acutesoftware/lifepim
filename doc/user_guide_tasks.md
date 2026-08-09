# User Guide: Tasks

Tasks are things that need to happen.

Some Tasks are simple human reminders, such as buying milk. Other Tasks can be
connected to an App Action so LifePIM knows what software can run the work.

The basic rule is:

```text
App = what can run
Task = what needs doing
Task parameters = the values for this specific job
```

## Example 1: Add a Simple Human Task

To add a quick personal Task:

1. Open `Tasks`.
2. Type the title into the quick-add box:

```text
Buy milk
```

3. Select `Add`.

LifePIM creates a normal open Task:

```text
Title            Buy milk
Status           open
Kind             task
Run With         None / Human Task
```

There is no App setup, no parameters, and no automation involved. When the task
is finished, select `Mark Done`.

## Example 2: Add a Task That Runs With an App

Executable Tasks are useful when the work needs to be done, and LifePIM already
has an App Action that can run it.

For example:

```text
Task: Load Bank Statement
App:  CSV to SQLite Loader
Action: Load CSV
```

The App Action defines what inputs it accepts. The Task supplies the actual
values for this run.

### App Action Setup

In `Apps`, create or edit an App:

```text
Name: CSV to SQLite Loader
Kind: Script
```

Add an Action:

```text
Action name: Load CSV
Action type: EXECUTABLE
Target / command: python
Working directory: D:\dev\csv_loader
Arguments:
load_csv.py --input "{input_file}" --database "{database}" --table "{table_name}" --mode "{load_mode}"
```

Under `Execution Parameters`, add:

| Name | Type | Required | Default / Options |
| --- | --- | --- | --- |
| `input_file` | file | yes | |
| `database` | file | yes | |
| `table_name` | text | yes | |
| `load_mode` | select | yes | `append`, `replace` |

The placeholders in `Arguments`, such as `{input_file}`, must match the
parameter names.

### Task Setup

In `Tasks`, add a new Task:

```text
Title: Load Bank Statement
Area: Money
Due: 2026-08-12
Run With: CSV to SQLite Loader -> Load CSV
```

After selecting the App Action, fill in the parameter values:

```text
input_file = D:\Tax\bank_august.csv
database   = D:\Tax\tax.sqlite
table_name = bank_transactions_raw
load_mode  = replace
```

Save the Task.

### Running the Task

Open the Task and select `Run`.

LifePIM validates the required parameters, resolves the argument placeholders,
and launches the App Action. In this example, it launches roughly:

```text
python load_csv.py --input "D:\Tax\bank_august.csv" --database "D:\Tax\tax.sqlite" --table "bank_transactions_raw" --mode "replace"
```

Running the App does not automatically mark the Task done. Mark it done yourself
after you confirm the work is complete.

## Task Templates

For repeatable work, create a Task with:

```text
Kind: template
```

Example:

```text
Title: Backup Notes
Run With: LifePIM Backup -> Backup Folder
Parameters:
  source_folder = D:\LifePIM\Notes
  destination_folder = N:\Backups\LifePIM\Notes
```

Templates appear under `Tasks -> Templates`. Use `Create Task` to make a normal
open Task from the template, then adjust dates or parameter values before
running it.

## Notes

- Human Tasks do not need an App.
- Executable Tasks bind to one App Action.
- The App Action defines parameter names and argument placeholders.
- The Task stores the actual parameter values.
- Scheduling and recurrence belong to Calendar, not Tasks.
- Task completion is explicit; launching an App is not the same as finishing the
  Task.
