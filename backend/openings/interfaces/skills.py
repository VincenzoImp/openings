"""REST routes and MCP tools of skills."""

from mcp.types import ToolAnnotations

from ..skills import SKILL_FILE, SkillLibrary, list_skills, read_skill
from .registry import Operation, Param, Route, Surface, Tool, bind_mcp, bind_rest

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

OPERATIONS = (
    Operation(
        "skills.list",
        "skills",
        "list",
        "Archive",
        "List shipped agent workflow skills",
        params=(),
        call=lambda s: list_skills(s),
        rest=(Route("GET", "/skills", "skills_list"),),
        tool=Tool(
            READ,
            "List the workflow skills this server ships for agents operating Openings:\nsetup, Inbox review, Shortlist preparation, sources, Career maintenance,\ntracking, interviews and writing, with what the owner can ask (title, summary,\nexample) and their reference files. Read one with skills_get.",
        ),
    ),
    Operation(
        "skills.read",
        "skills",
        "get",
        "Archive",
        "Read a skill or one of its reference files",
        params=(Param("name", str), Param("path", str, SKILL_FILE)),
        call=lambda s, name, path: read_skill(s, name, path),
        rest=(
            Route(
                "GET",
                "/skills/{name}",
                "skill_get",
                params=(Param("name", str),),
                call=lambda s, name: read_skill(s, name, SKILL_FILE),
            ),
            Route(
                "GET",
                "/skills/{name}/files/{path:path}",
                "skill_file_get",
                params=(Param("name", str), Param("path", str)),
            ),
        ),
        tool=Tool(
            READ,
            "Read a skill's SKILL.md, or one of its listed reference files (path), as Markdown,\nas shipped. Relative links inside a skill resolve against that skill's directory.\nThe owner's own standing instructions are in Preferences (working_with_me).",
        ),
    ),
)


SURFACES = (Surface("prompt", "<skill name>"),)


def register_api(router, library: SkillLibrary):
    bind_rest(router, OPERATIONS, library)


def register_mcp(mcp, library: SkillLibrary):
    bind_mcp(mcp, OPERATIONS, library)

    # One prompt per shipped skill: the skill's instructions.
    for item in library.list():
        mcp.prompt(name=item["name"], description=item["description"][:1024])(
            _prompt(library, item["name"])
        )


def _prompt(library: SkillLibrary, name: str):
    """The prompt of one skill: a function without parameters, so it declares no arguments."""

    def instructions() -> str:
        skill = read_skill(library, name)["content"]
        return (
            f"Follow the Openings `{name}` skill below. Read referenced files with "
            f"skills_get(name, path); `../<skill>/...` links name another skill.\n\n{skill}"
        )

    instructions.__name__ = instructions.__qualname__ = name.replace("-", "_")
    return instructions
