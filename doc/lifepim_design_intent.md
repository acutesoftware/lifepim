# LifePIM Design Intent

**Status:** Living design reference  
**Last updated:** 2026-08-09

## Purpose

LifePIM aims to provide **one canonical place for every kind of personal information, object, activity, or runnable thing**, while allowing the same object to appear in multiple useful views.

This document records the architectural intent behind LifePIM so that future features do not accidentally create parallel systems for concepts that already have a natural home.

The core rule is:

> **Prefer relationships and views over new entity types.**

If something can be accurately represented as an existing LifePIM object linked to other existing objects, reuse those objects rather than creating a second version of the same concept.

The top-level tabs should represent the **natural home of an object**, not isolated applications or silos.

---

# 1. One Place for Everything

Every real thing should have one canonical record in LifePIM.

Examples:

- A Python script that can be run belongs in **Apps**.
- A database or table belongs in **Data**.
- Something that needs to be done belongs in **Tasks**.
- Instructions explaining how to do something belong in **How**.
- The time at which something happens belongs in **Calendar**.
- A folder belongs in **Files**.
- A note belongs in **Notes**.

Other parts of LifePIM may show links or specialised views of these objects, but should not create duplicate records simply because the object is being used in a different context.

For example, a Python script used to load JSON into a database should not exist once as an App and again as a separate ETL Process executable.

There should be one App record for the runnable code.

---

# 2. Tabs Describe What a Thing Is

A useful design test is:

> **What is this thing?**

rather than:

> **What feature am I currently using it for?**

The major concepts currently map as follows.

| LifePIM area | Owns |
|---|---|
| **Apps** | Things that can be launched or executed |
| **Data** | Databases, tables, datasets, data files and other data assets |
| **Tasks** | Things that need to be done |
| **How** | Procedures and instructions for doing things |
| **Calendar** | When things occur |
| **Files** | Files and folders |
| **Notes** | Written information |
| **Areas / Projects / Collections** | Ways of organising and grouping objects |
| **Human / Agent** | Who or what performs an action |

These objects can be heavily related without losing their individual identities.

---

# 3. Apps — Things That Can Run

The Apps tab is the canonical home for **anything executable or launchable**.

Examples include:

- installed applications;
- development projects;
- Python scripts;
- PowerShell scripts;
- command-line tools;
- executables;
- utilities;
- launchable folders or working environments;
- other code that LifePIM can invoke.

The implementation technology is not important.

A Python script is not automatically a Data Process just because it processes data. It is still a runnable thing and therefore has an App record.

## Apps UI intent

Apps should remain **fast and simple**.

Its primary purpose is to answer:

> **What can I launch or work on?**

The existing list/grid interface should not grow into a second Files tab, IDE, Git client, ETL manager, or process-monitoring system.

A useful additional view is an **Icons** view.

When an Area is selected — especially Overview-style navigation — LifePIM can display the icons of the Apps available for that Area, functioning as a personal Area-aware launcher.

For example, selecting a Development Area might show icons for:

- LifePIM Desktop
- VS Code
- Blender
- a development project
- a utility script
- another frequently used tool

Apps may link to Files or other LifePIM content, but file browsing itself belongs in Files.

---

# 4. Data — Data Only

The Data tab should primarily show **the data itself**.

Examples:

- databases;
- schemas;
- tables;
- files used as datasets;
- saved datasets;
- metadata about data assets;
- table structures and contents;
- other data-oriented objects.

Data should answer:

> **What data do I have?**

It should not become a miniature Fabric, ETL platform, task scheduler, or code repository.

A Data object may expose contextual actions such as:

- Run related task
- Refresh
- Rebuild
- Import
- Validate

However, these actions should link to the canonical Task/App records rather than defining a separate processing subsystem inside Data.

---

# 5. Tasks — Things That Need to Happen

A Task represents **something that needs to be done**.

This includes actions traditionally described as:

- processes;
- jobs;
- imports;
- refreshes;
- backups;
- transformations;
- rebuilds;
- validations;
- maintenance routines.

Therefore:

> **A data process is normally a Task, not a separate LifePIM object type.**

For example:

**Load Logger JSON into database**

is a Task.

The Task may reference:

- the App that contains the runnable implementation;
- one or more Data inputs;
- one or more Data outputs;
- a How-To explaining the procedure;
- the Human or Agent that is allowed to perform it;
- Calendar recurrence or scheduled occurrences.

This avoids introducing a separate `Process` universe.

---

# 6. Task Templates and Task Occurrences

Repeatable operations should normally be represented by a **Task Template**.

For example:

## Task Template

**Load Logger JSON**

Relationships:

- **App:** Logger JSON Loader
- **Input Data:** Raw Logger JSON
- **Output Data:** Logger database
- **How-To:** Process LifePIM Logger Data
- **Default Runner:** Human or LifePIM Agent
- **Agent Allowed:** Yes/No

A particular piece of work then becomes an ordinary Task occurrence.

Example:

**Load Logger JSON — 2026-08-09 20:15**

- Status: Open, Done, or Cancelled
- Due date: when the user expects to perform it
- App Action: the executable binding, if LifePIM knows how to run it
- Parameters: the concrete values for this occurrence

The Task Template describes the reusable operation.

The ordinary Task occurrence is the work item.

Task Templates and ordinary Task occurrences may share the same Task storage
model. Execution history/logging is not automatically a Tasks-owned concept. Do
not introduce `lp_task_run` or a parallel process/run subsystem unless a future
generic LifePIM activity/execution design establishes a canonical home for that
information.

---

# 7. How — Instructions, Not Execution

A How-To describes **how something should be done**.

It is documentation/procedure, not the executable thing and not the task itself.

For example:

**How-To:** Process LifePIM Logger Data

may describe:

1. where incoming JSON files are stored;
2. what validation should occur;
3. which App is normally used;
4. expected outputs;
5. troubleshooting steps;
6. recovery procedure.

The Task can link to this How-To.

The App can also link to it where useful.

This keeps executable code, work to perform, and documentation as separate but connected concepts.

---

# 8. Calendar Owns When

Scheduling belongs to **Calendar**.

A Task should not invent an independent scheduling universe merely because it is automated.

For example:

> **Task:** Backup Database  
> **Occurs:** Weekly at 9:00 PM  
> **Performed by:** LifePIM Agent

Conceptually:

```text
Task: Backup Database
        |
        +---- uses ----> App: Backup Utility
        |
        +---- acts on --> Data: LifePIM Database
        |
        +---- follows --> How: Backup LifePIM
        |
        +---- occurs ---> Calendar: Weekly, 21:00
        |
        +---- runner ---> Agent
```

This rule prevents schedule information being independently implemented in Apps, Data Processes, backups, imports, pipelines, and other future systems.

> **Calendar owns when.**

Tasks and other objects may refer to Calendar recurrence/occurrence information, but should not create competing scheduling models.

---

# 9. Humans and Agents — Who Runs It

The difference between a manually run utility and an automated process is often not the executable itself.

It is:

> **Who is allowed to run it?**

An App may begin life as something run manually during development.

For example:

```text
file_namer.py
    |
    v
App: File Namer
    |
    +-- Human can run
    |
    +-- tested/debugged
    |
    +-- approved for unattended use
    |
    v
Task may now be performed by an Agent
```

This avoids maintaining separate manual and automated copies of the same program.

Useful concepts may include:

- Human runnable
- Agent runnable
- Requires confirmation
- Ready for automation
- Not approved for unattended use

The exact implementation can evolve later, but the architectural intent is that **automation is a permission/execution policy around existing Apps and Tasks**, not a duplicate category of executable.

---

# 10. Data Processing Examples


## Example 1 - Scan Media Files

App → FileLister
input → media folders
output → file listing data

## Example 2 - Refresh Media Tables

App → Media Metadata Loader
input → FileLister output
output → LifePIM media tables
depends on → "Scan Media Files" (Example 1 above)

## Example 3 - Backup Notes

### Apps

LifePIM Backup / backup.py / whatever executable actually performs it

### Files

Notes folder(s)
Backup destination(s)

### Task Template

Backup Notes
- uses App → LifePIM Backup
- source → Notes folders
- destination → NAS/backup folder
- How → Backup LifePIM Notes

Run manually:
 - Tasks → Backup Notes → Run

Scheduled later:
 - Calendar → Backup Notes → weekly Sunday 9 PM → Agent

The backup itself doesn't belong in Files. Files owns the source/destination folders; Task owns "back these up".


## Example 4 - (Detailed) Import Mobile Logger

The logger-processing workflow demonstrates the intended architecture.


Load raw LifePIM Logger JSON files into a database.


### App

**Logger JSON Loader**

The executable implementation, for example:

```text
/src/logger/load_logger_json.py
```

The App record owns information such as:

- command;
- script/executable location;
- working directory;
- launch arguments;
- runtime requirements.

### Data

**Raw Logger JSON**

The input data source.

### Data

**Logger Database**

The resulting database and its tables.

### Task Template

**Load Logger JSON**

The thing that needs to be performed.

It references the App and the relevant Data objects.

### How

**Process LifePIM Logger Data**

Documentation explaining the process.

### Calendar

Defines when the Task occurs if it becomes scheduled.

### Runner

A Human during development and testing.

Later, potentially a LifePIM Agent once the Task/App has been approved for unattended execution.

### Relationship

```text
                   HOW
        Process Logger Data
                   |
                   v
DATA ---------> TASK ---------> DATA
Raw JSON       Load Logger      logger.db
                  |
                  | uses
                  v
                 APP
        Logger JSON Loader
                  |
          performed by
                  v
          HUMAN or AGENT
                  |
             occurs on
                  v
              CALENDAR
```

No additional Process entity is required.

### Example 5 - Tax Time

A Tax Time workflow demonstrates how LifePIM objects work together without creating a separate processing system.

**Project:** `Tax Time 2026`

1. **Download Bank Statement**

   * **Task:** Download Bank Statement
   * **Runner:** Human
   * **Output:** CSV stored in Files
   * **How:** Contains instructions/notes for downloading the correct statement.

2. **Load CSV into SQLite**

   * **App:** Generic `CSV to SQLite Loader` Python script.
   * The App defines the parameters it accepts, such as `input_file`, `database`, `table_name`, and `load_mode`.
   * **Task:** Load Bank Statement.
   * The Task supplies the actual runtime values (parameters), e.g.:

     * `input_file = bank_statement.csv`
     * `database = tax.sqlite`
     * `table_name = bank_transactions_raw`
   * **Data:** The resulting SQLite database/table.
   * **How:** `Load CSV into SQLite` explains usage, conventions and troubleshooting.

3. **Categorise Transactions**

   * **App:** Generic `Transaction Categoriser` Python script.
   * **Task:** Categorise Tax Transactions.
   * Task parameters specify:

     * source database/table;
     * output table;
     * category column or other options.
   * **Data:** Reads `bank_transactions_raw` and creates `bank_transactions_categorised`.
   * **How:** Documents category rules, maintenance and troubleshooting.

The important separation is:

> **How explains. App accepts parameters. Task supplies values. Human/Agent executes. Data records inputs and outputs.**

The Agent should not normally interpret a How-To to determine how to execute a job. Execution should be deterministic from the **App definition + Task parameter values**. How-To remains the human-readable knowledge and documentation associated with the activity.

This also allows the same generic Apps and How-Tos to be reused for future Tax Time projects or completely unrelated CSV/database jobs.


```
PROJECT
Tax Time 2026
│
├── TASK: Download Bank Statement
│     ├── performed by Human
│     └── produces FILE: bank_statement.csv
│
├── TASK: Load Bank Statement
│     ├── uses APP: CSV to SQLite Loader
│     ├── follows HOW: Load CSV into SQLite
│     ├── reads FILE: bank_statement.csv
│     └── writes DATA: bank_transactions_raw
│
└── TASK: Categorise Tax Transactions
      ├── uses APP: Transaction Categoriser
      ├── follows HOW: Categorise Bank Transactions
      ├── reads DATA: bank_transactions_raw
      └── writes DATA: bank_transactions_categorised
```




# 11. Task Dependencies Can Form Pipelines

A simple pipeline does not require a new fundamental object model.

For example:

```text
Load JSON
    |
    v
Clean Records
    |
    v
Aggregate Usage
    |
    v
Create Calendar Events
```

These can remain separate Task Templates with dependencies:

```text
Clean Records
requires: Load JSON

Aggregate Usage
requires: Clean Records

Create Calendar Events
requires: Aggregate Usage
```

A future Pipeline screen could visualise these relationships without changing their canonical ownership.

---

# 12. Contextual Views Are Encouraged

Although each object has one natural home, other tabs should be free to expose related objects when useful.

Examples:

## Data

Selecting `logger.db` may show:

```text
Related Tasks
-------------
Run Logger Import
Rebuild Aggregates
Generate Calendar Activity
```

## Files

Selecting a backup folder may show:

```text
Related Tasks
-------------
Backup Folder
Verify Backup
```

## Apps

Selecting LifePIM Desktop may show:

```text
Related Tasks
-------------
Run Tests
Build Release
Publish
```

These are links to the same Task records.

They are not locally defined replacements.

---

# 13. Architectural Decision Test

Before adding a new table, content type, top-level tab, or subsystem, ask:

1. **What real-world thing does this represent?**
2. **Does LifePIM already have a canonical object type for that thing?**
3. **Could this instead be a relationship between existing objects?**
4. **Could this be a filtered or specialised view?**
5. **Would the new concept create two records for the same real thing?**

If the answer to the last question is yes, the design should usually be reconsidered.

A particularly useful principle is:

> **Do not classify an object by the feature currently using it. Classify it by what it is.**

A script that processes data is still an App.

The act of running it to achieve something is a Task.

The information it operates on is Data.

The procedure is How.

The schedule is Calendar.

The runner is a Human or Agent.

---

# 14. Summary Model

The high-level LifePIM model is:

```text
                      AREA / PROJECT
                            |
                     organises things
                            |
       +--------------------+--------------------+
       |                    |                    |
      DATA                 TASK                 APP
 what exists          what must happen      what can run
                           / | \                 |
                          /  |  \                |
                         /   |   \               |
                        v    v    v              |
                      HOW  CALENDAR  RUNNER      |
                 how to do it  when   who        |
                         \      |      /          |
                          +-----+-----+-----------+
                                |
                             ACTION
```

Or, in plain language:

> **Data is what exists.**  
> **Apps are what can run.**  
> **Tasks describe what should happen.**  
> **How describes how it should happen.**  
> **Calendar describes when it happens.**  
> **Humans or Agents describe who performs it.**

---

# 15. Current Design Decisions Recorded 2026-08-09

The following decisions were specifically clarified and should be treated as current LifePIM design intent:

1. **Keep the Apps tab simple and fast.**
2. Add an **Icons** view so Apps can work as an Area-aware launcher.
3. Do not turn Apps into a file/code browser; Files owns browsing.
4. Runnable scripts and utilities belong in Apps regardless of whether they process data.
5. Do not maintain duplicate executable definitions for manual and automated use.
6. A Data Process is normally a **Task that uses an App against Data**.
7. The executable itself remains the canonical App record.
8. A repeatable operation should normally be represented as a Task Template.
9. A Task may link to one or more Apps, Data objects, and How-To records.
10. A Human may run the Task during development/testing.
11. Once approved, an Agent may be allowed to run the same Task/App unattended.
12. Scheduling belongs to Calendar.
13. A scheduled task is represented conceptually as a Task with Calendar recurrence/occurrences, not as an independent cron/process system.
14. Data should primarily show Data.
15. Data may expose contextual links to Tasks that operate on the selected Data object.
16. “Processes” or “Data Processing” may exist later as a useful **view**, but not necessarily as a new canonical entity.
17. Do not add a top-level ETL tab unless future requirements genuinely cannot be represented through existing LifePIM concepts.
18. Prefer **relationships and views over new entity types**.
19. Task Templates and ordinary Task occurrences may use the same `lp_tasks`
    table; do not infer a Task-owned run history subsystem from conceptual
    occurrence language.

---

# 16. Maintaining This Document

This file should describe **why LifePIM is structured the way it is**, rather than act as an implementation backlog.

Implementation details, schema changes, and feature sequencing belong in specifications or roadmap documents.

A useful separation is:

- `lifepim_design_intent.md` — architectural intent and enduring design rules;
- `lifepim_roadmap.md` — what should be built next;
- feature/Codex specs — how a particular change should be implemented.

When an architectural decision changes, update this document deliberately so that future work is based on the new intent rather than on assumptions.
