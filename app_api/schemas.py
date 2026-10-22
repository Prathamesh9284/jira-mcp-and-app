from pydantic import BaseModel


class WorklogRow(BaseModel):
    date: str
    timeSpent: str
    endTime: str


class SubtaskCreate(BaseModel):
    storyKey: str
    projectKey: str
    issueTypeId: str | None = None
    title: str
    description: str = "-"
    acceptance: str = "-"
    startDate: str
    endDate: str
    logTime: bool = False
    date: str | None = None
    timeSpent: str | None = None
    endTime: str | None = None
    close: bool = False
    worklogs: list[WorklogRow] = []
    closeAfter: bool = False


class StoryCreate(BaseModel):
    projectKey: str
    issueTypeId: str
    title: str
    description: str = "-"
    acceptance: str = "-"  # required "Acceptance Criteria" field on some issue types (e.g. Bug)
    epicKey: str | None = None
    startDate: str | None = None
    endDate: str | None = None


class TimelogCreate(BaseModel):
    subtaskKey: str
    date: str
    timeSpent: str
    endTime: str
    description: str = ""
    close: bool = False
