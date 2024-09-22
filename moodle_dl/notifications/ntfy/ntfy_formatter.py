from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from moodle_dl.types import Course, File


@dataclass
class NtfyMessage:
    title: str
    text: str
    source_url: Optional[str] = None


def remove_until_first_space(s: str):
    """Returns the string with first word truncated."""
    return s.split(" ", 1)[1] if " " in s else s


def iso_to_time_dmy(date_str: str, time_str: str) -> str:
    """
    Format iso-formatted date time as used in filename 
    to time-date string of the format:
    %I:%M %p %d.%m.%y

    Example:
        >>> iso_to_time_dmy("2024.09.23", "14_35")
        02:35 PM 23.09.24
    """
    time_str = time_str.replace("_", ":")
    iso_str = date_str + " " + time_str

    date_obj = datetime.strptime(iso_str, "%Y.%m.%d %H:%M")
    return date_obj.strftime("%I:%M %p %d.%m.%y")


def _get_course_name_str(course_name: str) -> str:
    return "📘 " + course_name


def _get_status_str(file: File) -> str:
    """Returns the change type for a file if other than `new`"""
    status = _get_change_type(file)
    if status != "new":
        return status
    else:
        return ""


def _get_change_type(file: File) -> str:
    if file.modified:
        return "modified"
    elif file.deleted:
        return "deleted"
    elif file.moved:
        return "moved"
    else:
        return "new"


def _get_content_type(file: File) -> str:
    map_str = {
        "assign_file": "Assigment File",
        "submission_file": "Submission File",
    }
    content_type = file.content_type
    return map_str.get(content_type, content_type)


def make_generic_message(
    file: File, course_name: str, emoji: Optional[str] = "🗂️"
) -> NtfyMessage:
    title = ""
    if emoji:
        title += emoji + " "
    title += file.content_filename
    text = _get_course_name_str(course_name)
    url = file.content_fileurl
    return NtfyMessage(title, text, url)


def make_generic_combined_message(
    files: list[File],
    course_name: str,
    keyword="misc",
    emoji: Optional[str] = "🗂️",
    add_content_type=False,
) -> NtfyMessage:
    title = ""
    if emoji:
        title += emoji + " "
    title += f"{len(files)} {keyword} updates"
    text = _get_course_name_str(course_name) + "\n"
    for file in files:
        status = _get_status_str(file)
        type_str = _get_content_type(file)

        text += f"● {file.content_filename}"
        if add_content_type:
            text += f" ({type_str})"
        if status:
            text += f" ({status})"
        text += "\n"
    text = text.rstrip()
    return NtfyMessage(title, text)


# Functions to make message based on file.module_modname

def make_resource_message(file: File, course_name: str) -> NtfyMessage:
    return make_generic_message(file, course_name, "📚")


def make_resource_combined_message(files: list[File], course_name: str) -> NtfyMessage:
    return make_generic_combined_message(files, course_name, "file", "📚")


def make_calendar_message(file: File, course_name: str) -> NtfyMessage:
    iso_date, iso_time, event_name = file.content_filename.split(" ", 2)
    time_date_str = iso_to_time_dmy(iso_date, iso_time)
    title = f"⏰ {event_name} @ {time_date_str}"
    text = _get_course_name_str(course_name)
    url = file.content_fileurl
    return NtfyMessage(title, text, url)


def make_quiz_message(file: File, course_name: str) -> NtfyMessage:
    return make_generic_message(file, course_name, "💻")


def make_assign_message(file: File, course_name: str) -> NtfyMessage:
    return make_generic_message(file, course_name, "📝")


def make_assign_combined_message(files: list[File], course_name: str) -> NtfyMessage:
    return make_generic_combined_message(
        files, course_name, "assignment file", "📝", True
    )


def make_forum_message(file: File, course_name: str) -> NtfyMessage:
    title = "✉️ " + remove_until_first_space(file.content_filepath)
    text = _get_course_name_str(course_name)
    url = file.content_fileurl
    return NtfyMessage(title, text, url)


class FileAggregatorByMod:
    """Categorizes and aggregates files by `file.module_modname`
    and stores them into a `self.map` dictionary.
    """
    def __init__(
        self,
        mod_categories=[
            "assign",
            "calendar",
            "folder",
            "forum",
            "resource",
            "quiz",
        ],
    ):
        """Initialize the aggregator.
        
        Args:
            mod_categories (list[str]): The `file.module_modname` values
              that you want to categorize and collect.
              Rest of the files would be collected under `map["misc"]`
        """
        self.map = {key: [] for key in mod_categories + ["misc"]}

    def add(self, file: File) -> None:
        if file.module_modname in self.map:
            self.map[file.module_modname].append(file)
        else:
            self.map["misc"].append(file)


def create_full_moodle_diff_messages(changes: list[Course]) -> list[NtfyMessage]:
    messages = []
    for course in changes:
        course_name = course.overwrite_name_with or course.fullname
        aggregator = FileAggregatorByMod()
        for file in course.files:
            aggregator.add(file)
        for mod, files in aggregator.map.items():
            if not files:
                continue
            if mod == "assign":
                msg = make_assign_combined_message(files, course_name)
                messages.append(msg)
            elif mod == "calendar":
                msgs = [make_calendar_message(file, course_name) for file in files]
                messages.extend(msgs)
            elif mod == "forum":
                msgs = [make_forum_message(file, course_name) for file in files]
                messages.extend(msgs)
            elif mod in ["folder", "resource"]:
                msg = make_resource_combined_message(files, course_name)
                messages.append(msg)
            elif mod == "quiz":
                msgs = [make_quiz_message(file, course_name) for file in files]
                messages.extend(msgs)
            elif mod == "misc":
                msg = make_generic_combined_message(files, course_name)
                messages.append(msg)
            else:
                raise AssertionError(
                    "Some module_modname category is left unprocessed."
                )
    return messages
