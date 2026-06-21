from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from crewai import Agent, Crew, LLM, Process, Task
from crewai.hooks.llm_hooks import register_after_llm_call_hook

from trello_crew_playground.schemas import TrelloCard, WorkflowResult
from trello_crew_playground.settings import Settings
from trello_crew_playground.tools import (
    extract_links,
    extract_repositories,
    fetch_webpage,
)


class TrelloCrewWorkflow:
    def __init__(self, settings: Settings):
        self.settings = settings
        # Register a global after-LLM-call hook to log responses from local LLMs
        # Ensure we only register once per process
        try:
            if self.settings.use_local_llm:
                # Hook function will be called with a LLMCallHookContext
                def _log_local_llm_response(context):
                    try:
                        response = context.response or ""
                        llm = getattr(context, "llm", None)
                        model = getattr(llm, "model", None) if llm is not None else None
                        agent_role = getattr(context.agent, "role", "direct") if hasattr(context, "agent") else "direct"
                        task_desc = getattr(context.task, "description", "") if hasattr(context, "task") else ""
                        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        log_dir = self.settings.output_dir
                        log_dir.mkdir(parents=True, exist_ok=True)
                        log_path = log_dir / "llm_responses.log"
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(f"---\n{timestamp}\nModel: {model}\nAgent: {agent_role}\nTask: {task_desc}\nResponse:\n{response}\n\n")
                    except Exception:
                        # Don't let logging interfere with LLM execution
                        pass

                register_after_llm_call_hook(_log_local_llm_response)
        except Exception:
            # Safe-guard: if hooks aren't available, continue without logging
            pass

    def _ollama_base_url(self) -> str:
        base_url = self.settings.ollama_base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        return base_url

    def _base_context(self, card: TrelloCard, list_name: str) -> str:
        return (
            f"Card title: {card.name}\n"
            f"Card list: {list_name}\n"
            f"Card url: {card.url}\n\n"
            f"Card description:\n{card.desc or '(empty)'}\n"
        )

    def run(self, card: TrelloCard, list_name: str) -> WorkflowResult:
        # Instruction to prevent models from outputting chain-of-thought
        NO_CHAIN_OF_THOUGHT = (
            "IMPORTANT: Do NOT include chain-of-thought, internal reasoning, or step-by-step\n"
            "explanations in your response. Provide only the final answer in the requested format."
        )
        if not self.settings.use_crewai:
            raw_output = self._fallback_output(card, list_name, RuntimeError("CrewAI disabled by config"))
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
                meta={"file_name": file_name, "mode": "local"},
            )

        # Use Ollama LLM (local) for all agent calls
        llm = LLM(
            model=f"ollama/{self.settings.ollama_model}",
            base_url=self._ollama_base_url(),
            api_key="ollama",  # Ollama doesn't require authentication by default
        )

        analyst = Agent(
            role="Requirement Analyst",
            goal="Extract the real task from a Trello card and identify what the final document should contain.",
            backstory=(
                "You are precise, practical, and good at turning rough notes into clear requirements. "
                "You ask what is missing and produce a compact structured brief."
            ),
            verbose=False,
            llm=llm,
        )

        web_researcher = Agent(
            role="Web Researcher",
            goal=(
                "Fetch and analyze web pages to find specific information and answer "
                "questions. When a web page is the primary source, produce a concise"
                " summary suitable for a Trello comment (3-6 bullets, short sentences)."
            ),
            backstory=(
                "You are skilled at browsing the web, extracting relevant information, "
                "and producing short, actionable summaries tailored for team cards. "
                "If asked, include a short bullet list of key points and the page title."
            ),
            verbose=False,
            llm=llm,
            tools=[fetch_webpage, extract_links, extract_repositories],
        )

        writer = Agent(
            role="Training Writer",
            goal="Write a clear, useful training document from the requirement brief.",
            backstory=(
                "You write simple, organized training materials with practical explanations and examples. "
                "You prefer plain language and a clean structure."
            ),
            verbose=False,
            llm=llm,
        )

        reviewer = Agent(
            role="Document Reviewer",
            goal="Improve clarity, completeness, and usefulness of the drafted training document.",
            backstory=(
                "You review documents like a senior editor. "
                "You remove ambiguity, tighten wording, and make the output easy to use."
            ),
            verbose=False,
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
                f"\n\n{NO_CHAIN_OF_THOUGHT}"
            ),
            expected_output="A compact structured requirement brief in markdown.",
            agent=analyst,
        )

        writer_task = Task(
            description=(
                "Using the requirement brief above, draft the training document.\n"
                "The topic should be practical and easy to follow.\n"
                "Keep the structure focused on an intro, core explanation, examples, and next steps."
                f"\n\n{NO_CHAIN_OF_THOUGHT}"
            ),
            expected_output="A polished markdown training document draft.",
            agent=writer,
        )

        review_task = Task(
            description=(
                "Review the draft and produce a final version.\n"
                "Fix weak phrasing, fill obvious gaps, and make the result ready to share in Trello."
                f"\n\n{NO_CHAIN_OF_THOUGHT}"
            ),
            expected_output="A final markdown training document with a short top summary.",
            agent=reviewer,
        )

        research_task = Task(
            description=(
                "If the card description contains URLs or mentions web resources, fetch and analyze them.\n\n"
                f"{self._base_context(card, list_name)}\n"
                "If a URL is mentioned, fetch it and extract relevant information.\n"
                "Produce a concise summary suitable for a Trello comment: include the page title,\n"
                "the URL, and 3–6 short bullet points with the most important facts or actions.\n"
                "Also count and list any repositories mentioned on the page.\n"
                "Return the summary in plain markdown format."
                f"\n\n{NO_CHAIN_OF_THOUGHT}"
            ),
            expected_output="A summary of web research findings, or confirmation that no web research was needed.",
            agent=web_researcher,
        )

        crew = Crew(
            agents=[analyst, web_researcher, writer, reviewer],
            tasks=[analyst_task, research_task, writer_task, review_task],
            process=Process.sequential,
            verbose=False,
            tracing=False,
        )

        try:
            result = crew.kickoff(inputs={"card_title": card.name, "card_desc": card.desc})
            raw_output = getattr(result, "raw", str(result))
        except Exception as exc:
            raw_output = self._fallback_output(card, list_name, exc)
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

    def _fallback_output(self, card: TrelloCard, list_name: str, exc: Exception) -> str:
        description = (card.desc or "").strip()
        lines = [
            f"# Training Document Draft: {card.name}",
            "",
            "## Inferred Objective",
            f"Create a training document about {card.name.lower()} for the team.",
            "",
            "## Source Context",
            f"- Trello list: {list_name}",
            f"- Card URL: {card.url}",
            "",
            "## Key Notes",
            description or "- No card description was provided.",
            "",
            "## Suggested Outline",
            "1. Introduction",
            "2. Core concepts",
            "3. Practical examples",
            "4. Common mistakes",
            "5. Next steps",
            "",
            "## Delivery Note",
            f"LLM execution failed, so this draft was generated locally. Error: {exc}",
        ]
        return "\n".join(lines)

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
