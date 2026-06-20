from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from crewai import Agent, Crew, LLM, Process, Task

from trello_crew_playground.schemas import TrelloCard, WorkflowResult
from trello_crew_playground.settings import Settings


class TrelloCrewWorkflow:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _base_context(self, card: TrelloCard, list_name: str) -> str:
        return (
            f"Card title: {card.name}\n"
            f"Card list: {list_name}\n"
            f"Card url: {card.url}\n\n"
            f"Card description:\n{card.desc or '(empty)'}\n"
        )

    def run(self, card: TrelloCard, list_name: str) -> WorkflowResult:
        llm = LLM(model=f"openai/{self.settings.openai_model}")

        analyst = Agent(
            role="Requirement Analyst",
            goal="Extract the real task from a Trello card and identify what the final document should contain.",
            backstory=(
                "You are precise, practical, and good at turning rough notes into clear requirements. "
                "You ask what is missing and produce a compact structured brief."
            ),
            verbose=True,
            llm=llm,
        )

        writer = Agent(
            role="Training Writer",
            goal="Write a clear, useful training document from the requirement brief.",
            backstory=(
                "You write simple, organized training materials with practical explanations and examples. "
                "You prefer plain language and a clean structure."
            ),
            verbose=True,
            llm=llm,
        )

        reviewer = Agent(
            role="Document Reviewer",
            goal="Improve clarity, completeness, and usefulness of the drafted training document.",
            backstory=(
                "You review documents like a senior editor. "
                "You remove ambiguity, tighten wording, and make the output easy to use."
            ),
            verbose=True,
            llm=llm,
        )

        analyst_task = Task(
            description=(
                "Analyze this Trello card and produce a concise requirement brief.\n\n"
                f"{self._base_context(card, list_name)}\n"
                "Return:\n"
                "1. The inferred objective.\n"
                "2. Important assumptions.\n"
                "3. Missing information, if any.\n"
                "4. A recommended outline for the final training document."
            ),
            expected_output="A compact structured requirement brief in markdown.",
            agent=analyst,
        )

        writer_task = Task(
            description=(
                "Using the requirement brief above, draft the training document.\n"
                "The topic should be practical and easy to follow.\n"
                "Keep the structure focused on an intro, core explanation, examples, and next steps."
            ),
            expected_output="A polished markdown training document draft.",
            agent=writer,
        )

        review_task = Task(
            description=(
                "Review the draft and produce a final version.\n"
                "Fix weak phrasing, fill obvious gaps, and make the result ready to share in Trello."
            ),
            expected_output="A final markdown training document with a short top summary.",
            agent=reviewer,
        )

        crew = Crew(
            agents=[analyst, writer, reviewer],
            tasks=[analyst_task, writer_task, review_task],
            process=Process.sequential,
            verbose=True,
        )

        result = crew.kickoff(inputs={"card_title": card.name, "card_desc": card.desc})
        raw_output = getattr(result, "raw", str(result))
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        file_name = f"{timestamp}-{card.id}.md"
        output_path = self.settings.output_dir / file_name
        output_path.write_text(raw_output, encoding="utf-8")

        comment_text = self._build_comment(card, list_name, output_path, raw_output)

        return WorkflowResult(
            card_id=card.id,
            card_name=card.name,
            list_name=list_name,
            markdown_path=str(output_path),
            comment_text=comment_text,
            raw_output=raw_output,
            meta={"file_name": file_name},
        )

    def _build_comment(self, card: TrelloCard, list_name: str, output_path: Path, raw_output: str) -> str:
        header = [
            "CrewAI result",
            f"- Card: {card.name}",
            f"- Source list: {list_name}",
            f"- Markdown file: `{output_path.as_posix()}`",
        ]

        if self.settings.comment_delivery_mode == "file":
            return "\n".join(header)

        body = raw_output.strip()
        if len(body) > self.settings.max_comment_chars:
            body = body[: self.settings.max_comment_chars - 20].rstrip() + "\n\n...[truncated]"

        if self.settings.comment_delivery_mode == "comment":
            return body

        return "\n".join(header + ["", body])
