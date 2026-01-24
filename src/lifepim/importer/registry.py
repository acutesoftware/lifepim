"""Target writer registry."""

from lifepim.targets import contacts, files, media

TARGET_WRITERS = {
    "contacts": contacts,
    "files": files,
    "media": media,
}


def get_writer(target: str):
    writer = TARGET_WRITERS.get(target)
    if not writer:
        raise ValueError(f"Unknown import target: {target}")
    return writer
