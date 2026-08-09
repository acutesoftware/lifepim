# Tasks Tab

The Tasks tab answers:

```text
What needs doing?
```

Tasks are stored in one table, `lp_tasks`. There are no Task-run, Job, Process,
Pipeline, or scheduler tables for this feature.

## Human Tasks

A human Task can be created with only a title:

```text
Buy milk
```

That creates a normal open Task:

```text
task_kind        task
status           open
app_action_id    NULL
parameters_json  NULL
```

Human Tasks do not show execution controls.

## Executable Tasks

A Task may optionally bind to one App Action:

```text
lp_tasks.app_action_id -> lp_app_action.app_action_id
```

The owning App is derived through `lp_app_action.app_id`; Tasks do not duplicate
`app_id`.

The App Action defines accepted parameters and an argument template. The Task
stores actual runtime values in `parameters_json`.

Design rule:

```text
App accepts parameters.
Task supplies values.
```

Running an executable Task delegates to the Apps launch helper. The normal App
usage fields, such as `last_used_date` and `usage_count`, still update.

Launching an App does not automatically complete the Task. The user marks the
Task done when the work is actually complete.

## Templates

Task Templates are ordinary `lp_tasks` rows:

```text
task_kind = template
```

They appear under `Tasks -> Templates`. Creating a Task from a Template creates
a new normal Task row with:

```text
task_kind = task
status    = open
```

The new Task copies title, details, Area, App Action binding, parameter values,
and outgoing generic links where possible. It is the work item; no run record is
created.

## Status

V1 statuses are:

```text
open
done
cancelled
```

Marking a Task done sets `completed_date`. Reopening clears it.

## Relationships

Tasks continue to use the generic Links drawer for contextual relationships,
such as:

```text
Task -> How
Task -> File
Task -> Data
Task -> Person
Task -> Place
Task -> Task dependency
```

Project assignment continues through the existing Project item relationship.
`project_id` is not stored directly on `lp_tasks`.

## Scheduling Boundary

`start_date` and `due_date` are planning fields. They do not mean "run this
command at this time".

Calendar remains the future canonical owner of recurrence and scheduled
occurrences. Tasks and Apps do not add cron, recurrence, next-run, last-run, or
scheduler metadata.

## Core Model

```text
APP
What can run?

TASK
What needs doing?

TASK + APP ACTION
Something needs doing and LifePIM knows what software can perform it.
```
