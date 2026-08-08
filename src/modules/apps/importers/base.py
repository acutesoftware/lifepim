from dataclasses import dataclass, field


STATUS_NEW = "NEW"
STATUS_EXISTS = "EXISTS"
STATUS_INVALID = "INVALID"

SOURCE_DEV_FOLDER = "DEV_FOLDER"
SOURCE_TASKBAR = "TASKBAR"
SOURCE_DESKTOP = "DESKTOP"


@dataclass
class AppImportCandidate:
    candidate_id: str
    source_type: str
    name: str
    kind: str
    area_id: str = ""
    target: str = ""
    arguments: str = ""
    working_directory: str = ""
    icon: str = ""
    source_path: str = ""
    status: str = STATUS_NEW
    selected: bool = True
    metadata: dict = field(default_factory=dict)
    action_name: str = "Open"
    action_type: str = "SYSTEM_DEFAULT"
    description: str = ""

    def as_dict(self):
        return {
            "candidate_id": self.candidate_id,
            "source_type": self.source_type,
            "name": self.name,
            "kind": self.kind,
            "area_id": self.area_id,
            "target": self.target,
            "arguments": self.arguments,
            "working_directory": self.working_directory,
            "icon": self.icon,
            "source_path": self.source_path,
            "status": self.status,
            "selected": bool(self.selected),
            "metadata": dict(self.metadata or {}),
            "action_name": self.action_name,
            "action_type": self.action_type,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            candidate_id=str(data.get("candidate_id") or ""),
            source_type=str(data.get("source_type") or ""),
            name=str(data.get("name") or ""),
            kind=str(data.get("kind") or "Other"),
            area_id=str(data.get("area_id") or ""),
            target=str(data.get("target") or ""),
            arguments=str(data.get("arguments") or ""),
            working_directory=str(data.get("working_directory") or ""),
            icon=str(data.get("icon") or ""),
            source_path=str(data.get("source_path") or ""),
            status=str(data.get("status") or STATUS_NEW),
            selected=bool(data.get("selected", True)),
            metadata=dict(data.get("metadata") or {}),
            action_name=str(data.get("action_name") or "Open"),
            action_type=str(data.get("action_type") or "SYSTEM_DEFAULT"),
            description=str(data.get("description") or ""),
        )

    @property
    def importable(self):
        return self.status == STATUS_NEW and bool(self.name.strip()) and bool(self.target.strip())


@dataclass
class ImportScanResult:
    candidates: list[AppImportCandidate] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class AppImportResult:
    imported_count: int = 0
    skipped_existing_count: int = 0
    skipped_unselected_count: int = 0
    skipped_invalid_count: int = 0
    created_app_ids: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
