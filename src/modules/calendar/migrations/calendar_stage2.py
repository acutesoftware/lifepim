from modules.calendar.services.calendar_index import run_calendar_migration


def migrate(conn=None):
    run_calendar_migration(conn)

