from __future__ import annotations

import random
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st


# =========================================================
# Application configuration
# =========================================================

st.set_page_config(
    page_title="Apprentice Tool Training",
    page_icon="🧰",
    layout="centered",
)

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

TOOLS_FILE = DATA_DIR / "tools.csv"
FAMILIES_FILE = DATA_DIR / "tool_families.csv"
SCENARIOS_FILE = DATA_DIR / "scenarios.csv"
SCENARIO_TOOLS_FILE = DATA_DIR / "scenario_tools.csv"
PROGRESS_DB = DATA_DIR / "training_progress.db"

DEMO_LEARNERS = [
    ("AP001", "Apprentice 001"),
    ("AP002", "Apprentice 002"),
    ("AP003", "Apprentice 003"),
    ("DEMO", "Instructor Demo"),
]

QUESTION_TYPES = {
    "formal_name": {
        "answer_column": "formal_name",
        "prompt": "What is the formal name of this tool?",
        "prefer_same_family": True,
    },
    "common_name": {
        "answer_column": "common_name",
        "prompt": "What is the common name of this tool?",
        "prefer_same_family": True,
    },
    "location": {
        "answer_column": "location",
        "prompt": "Where is this tool normally carried or stored?",
        "prefer_same_family": True,
    },
    "family_name": {
        "answer_column": "family_name",
        "prompt": "Which tool family does this tool belong to?",
        "prefer_same_family": False,
    },
}


# =========================================================
# Styling
# =========================================================

st.markdown(
    """
    <style>
        .block-container {
            max-width: 900px;
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }
        div[data-testid="stTextInput"] input:disabled,
        div[data-testid="stTextArea"] textarea:disabled {
            color: inherit;
            -webkit-text-fill-color: inherit;
            opacity: 1;
            background-color: rgba(128, 128, 128, 0.08);
        }
        div.stButton > button {
            min-height: 3rem;
            font-weight: 600;
        }
        .home-description {
            text-align: center;
            margin-bottom: 1rem;
        }
        .learner-banner {
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 0.6rem;
            padding: 0.75rem 1rem;
            margin-bottom: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# General utility functions
# =========================================================


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_id(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def normalize_boolean(value: object, default: bool = False) -> bool:
    if pd.isna(value):
        return default
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def safe_text(value: object, fallback: str = "") -> str:
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def resolve_image_path(image_value: object) -> str | None:
    if pd.isna(image_value):
        return None
    image_text = str(image_value).strip()
    if not image_text:
        return None
    if image_text.startswith(("http://", "https://")):
        return image_text

    image_path = APP_DIR / image_text
    if image_path.is_file():
        return str(image_path)

    image_stem = image_path.with_suffix("")
    for extension in [".png", ".jpg", ".jpeg", ".webp"]:
        candidate = image_stem.with_suffix(extension)
        if candidate.is_file():
            return str(candidate)
    return None


# =========================================================
# SQLite learner/progress storage
# =========================================================


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(PROGRESS_DB)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS learners (
                learner_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS training_sessions (
                session_id TEXT PRIMARY KEY,
                learner_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (learner_id) REFERENCES learners(learner_id)
            );

            CREATE TABLE IF NOT EXISTS attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                learner_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                tool_id TEXT NOT NULL,
                question_type TEXT NOT NULL,
                selected_answer TEXT,
                correct_answer TEXT,
                is_correct INTEGER NOT NULL,
                attempted_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES training_sessions(session_id),
                FOREIGN KEY (learner_id) REFERENCES learners(learner_id)
            );

            CREATE INDEX IF NOT EXISTS idx_attempts_learner
                ON attempts(learner_id);
            CREATE INDEX IF NOT EXISTS idx_attempts_tool
                ON attempts(tool_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_learner
                ON training_sessions(learner_id);
            """
        )

        for learner_id, display_name in DEMO_LEARNERS:
            conn.execute(
                """
                INSERT OR IGNORE INTO learners
                    (learner_id, display_name, created_at, active)
                VALUES (?, ?, ?, 1)
                """,
                (learner_id, display_name, utc_now()),
            )


def get_active_learners() -> pd.DataFrame:
    with get_db_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT learner_id, display_name
            FROM learners
            WHERE active = 1
            ORDER BY display_name
            """,
            conn,
        )


def add_learner(learner_id: str, display_name: str) -> tuple[bool, str]:
    learner_id = learner_id.strip().upper()
    display_name = display_name.strip()

    if not learner_id or not display_name:
        return False, "Learner ID and display name are required."

    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO learners
                    (learner_id, display_name, created_at, active)
                VALUES (?, ?, ?, 1)
                """,
                (learner_id, display_name, utc_now()),
            )
        return True, "Learner created."
    except sqlite3.IntegrityError:
        return False, "That learner ID already exists."


def create_training_session(learner_id: str, mode: str) -> str:
    session_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO training_sessions
                (session_id, learner_id, mode, started_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, learner_id, mode, utc_now()),
        )
    return session_id


def complete_training_session(session_id: str | None) -> None:
    if not session_id:
        return
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE training_sessions
            SET completed_at = COALESCE(completed_at, ?)
            WHERE session_id = ?
            """,
            (utc_now(), session_id),
        )


def record_attempt(
    *,
    session_id: str,
    learner_id: str,
    mode: str,
    tool_id: str,
    question_type: str,
    selected_answer: str,
    correct_answer: str,
    is_correct: bool,
) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO attempts (
                session_id,
                learner_id,
                mode,
                tool_id,
                question_type,
                selected_answer,
                correct_answer,
                is_correct,
                attempted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                learner_id,
                mode,
                tool_id,
                question_type,
                selected_answer,
                correct_answer,
                int(is_correct),
                utc_now(),
            ),
        )


def get_learner_attempts(learner_id: str) -> pd.DataFrame:
    with get_db_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT *
            FROM attempts
            WHERE learner_id = ?
            ORDER BY attempted_at DESC, attempt_id DESC
            """,
            conn,
            params=(learner_id,),
        )


def get_learner_session_count(learner_id: str) -> int:
    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS session_count
            FROM training_sessions
            WHERE learner_id = ?
            """,
            (learner_id,),
        ).fetchone()
    return int(row["session_count"])


# =========================================================
# Load CSV training content
# =========================================================


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    required_files = [TOOLS_FILE, FAMILIES_FILE, SCENARIOS_FILE, SCENARIO_TOOLS_FILE]
    missing_files = [str(path) for path in required_files if not path.is_file()]
    if missing_files:
        raise FileNotFoundError("Missing required CSV files:\n" + "\n".join(missing_files))

    tools = pd.read_csv(TOOLS_FILE)
    families = pd.read_csv(FAMILIES_FILE)
    scenarios = pd.read_csv(SCENARIOS_FILE)
    scenario_tools = pd.read_csv(SCENARIO_TOOLS_FILE)

    for df in [tools, families, scenarios, scenario_tools]:
        df.columns = df.columns.str.strip()

    tool_defaults = {
        "tool_id": "",
        "formal_name": "",
        "common_name": "",
        "use_description": "",
        "family_id": "",
        "location": "",
        "difficulty": 1,
        "image_url": "",
        "is_commonly_missed": False,
        "status": "PUBLISHED",
    }
    family_defaults = {
        "family_id": "",
        "family_name": "Uncategorized",
        "description": "",
        "is_active": True,
    }
    scenario_defaults = {
        "scenario_id": "",
        "scenario_name": "",
        "scenario_description": "",
        "difficulty": 1,
        "status": "PUBLISHED",
    }
    scenario_tool_defaults = {
        "scenario_id": "",
        "tool_id": "",
        "is_correct": True,
    }

    for column, default in tool_defaults.items():
        if column not in tools.columns:
            tools[column] = default
    for column, default in family_defaults.items():
        if column not in families.columns:
            families[column] = default
    for column, default in scenario_defaults.items():
        if column not in scenarios.columns:
            scenarios[column] = default
    for column, default in scenario_tool_defaults.items():
        if column not in scenario_tools.columns:
            scenario_tools[column] = default

    tools["tool_id"] = tools["tool_id"].apply(normalize_id)
    tools["family_id"] = tools["family_id"].apply(normalize_id)
    families["family_id"] = families["family_id"].apply(normalize_id)
    scenarios["scenario_id"] = scenarios["scenario_id"].apply(normalize_id)
    scenario_tools["scenario_id"] = scenario_tools["scenario_id"].apply(normalize_id)
    scenario_tools["tool_id"] = scenario_tools["tool_id"].apply(normalize_id)

    tools = tools[
        tools["status"].fillna("PUBLISHED").astype(str).str.strip().str.upper().eq("PUBLISHED")
    ].copy()
    scenarios = scenarios[
        scenarios["status"].fillna("PUBLISHED").astype(str).str.strip().str.upper().eq("PUBLISHED")
    ].copy()
    families = families[
        families["is_active"].apply(lambda value: normalize_boolean(value, default=True))
    ].copy()

    tools["is_commonly_missed"] = tools["is_commonly_missed"].apply(normalize_boolean)
    scenario_tools["is_correct"] = scenario_tools["is_correct"].apply(
        lambda value: normalize_boolean(value, default=True)
    )

    tools = tools.merge(
        families[["family_id", "family_name"]],
        on="family_id",
        how="left",
    )
    tools["family_name"] = tools["family_name"].fillna("Uncategorized")

    return tools, families, scenarios, scenario_tools


def get_tool_scenarios(tool_id: str, scenarios: pd.DataFrame, scenario_tools: pd.DataFrame) -> pd.DataFrame:
    matching_links = scenario_tools[
        (scenario_tools["tool_id"] == tool_id) & scenario_tools["is_correct"]
    ]
    if matching_links.empty:
        return pd.DataFrame()
    return matching_links.merge(scenarios, on="scenario_id", how="inner")


# =========================================================
# Navigation/session-state helpers
# =========================================================


def clear_game_state() -> None:
    keys = [
        "deck", "current_index", "show_answer", "known_count", "review_count",
        "review_ids", "completed", "flashcard_session_id", "mc_deck", "mc_index",
        "mc_score", "mc_answered", "mc_selected_answer", "mc_question",
        "mc_completed", "mc_session_id",
    ]
    for key in keys:
        st.session_state.pop(key, None)


def go_home() -> None:
    clear_game_state()
    st.session_state.mode = "home"


def switch_learner() -> None:
    complete_training_session(st.session_state.get("flashcard_session_id"))
    complete_training_session(st.session_state.get("mc_session_id"))
    clear_game_state()
    st.session_state.pop("learner_id", None)
    st.session_state.pop("learner_name", None)
    st.session_state.mode = "home"


def initialize_flashcard_game(tool_ids: list[str]) -> None:
    # The incoming list is already ordered using learner-specific adaptive
    # weighting. Preserve that order rather than reshuffling it here.
    deck = tool_ids.copy()
    st.session_state.deck = deck
    st.session_state.current_index = 0
    st.session_state.show_answer = False
    st.session_state.known_count = 0
    st.session_state.review_count = 0
    st.session_state.review_ids = []
    st.session_state.completed = False
    st.session_state.flashcard_session_id = create_training_session(
        st.session_state.learner_id, "flashcards"
    )


def advance_flashcard() -> None:
    st.session_state.current_index += 1
    st.session_state.show_answer = False
    if st.session_state.current_index >= len(st.session_state.deck):
        st.session_state.completed = True
        complete_training_session(st.session_state.get("flashcard_session_id"))


def mark_flashcard_known() -> None:
    current_tool_id = st.session_state.deck[st.session_state.current_index]
    record_attempt(
        session_id=st.session_state.flashcard_session_id,
        learner_id=st.session_state.learner_id,
        mode="flashcards",
        tool_id=current_tool_id,
        question_type="self_rating",
        selected_answer="I Knew It",
        correct_answer="I Knew It",
        is_correct=True,
    )
    st.session_state.known_count += 1
    advance_flashcard()


def mark_flashcard_review() -> None:
    current_tool_id = st.session_state.deck[st.session_state.current_index]
    record_attempt(
        session_id=st.session_state.flashcard_session_id,
        learner_id=st.session_state.learner_id,
        mode="flashcards",
        tool_id=current_tool_id,
        question_type="self_rating",
        selected_answer="Review Again",
        correct_answer="I Knew It",
        is_correct=False,
    )
    if current_tool_id not in st.session_state.review_ids:
        st.session_state.review_ids.append(current_tool_id)
    st.session_state.review_count += 1
    advance_flashcard()


def start_review_round() -> None:
    deck = st.session_state.review_ids.copy()
    random.shuffle(deck)
    st.session_state.deck = deck
    st.session_state.current_index = 0
    st.session_state.show_answer = False
    st.session_state.known_count = 0
    st.session_state.review_count = 0
    st.session_state.review_ids = []
    st.session_state.completed = False
    st.session_state.flashcard_session_id = create_training_session(
        st.session_state.learner_id, "flashcards_review"
    )


def initialize_multiple_choice_game(tool_ids: list[str]) -> None:
    # The incoming list is already ordered using learner-specific adaptive
    # weighting. Preserve that order rather than reshuffling it here.
    deck = tool_ids.copy()
    st.session_state.mc_deck = deck
    st.session_state.mc_index = 0
    st.session_state.mc_score = 0
    st.session_state.mc_answered = False
    st.session_state.mc_selected_answer = None
    st.session_state.mc_question = None
    st.session_state.mc_completed = False
    st.session_state.mc_session_id = create_training_session(
        st.session_state.learner_id, "multiple_choice"
    )


def advance_multiple_choice() -> None:
    st.session_state.mc_index += 1
    st.session_state.mc_answered = False
    st.session_state.mc_selected_answer = None
    st.session_state.mc_question = None
    if st.session_state.mc_index >= len(st.session_state.mc_deck):
        st.session_state.mc_completed = True
        complete_training_session(st.session_state.get("mc_session_id"))


# =========================================================
# Flashcard display helpers
# =========================================================


def build_scenario_text(tool_scenarios: pd.DataFrame, show_answer: bool) -> str:
    if not show_answer or tool_scenarios.empty:
        return ""
    lines = []
    for _, scenario in tool_scenarios.iterrows():
        name = safe_text(scenario.get("scenario_name"))
        description = safe_text(scenario.get("scenario_description"))
        if name and description:
            lines.append(f"{name}: {description}")
        elif name:
            lines.append(name)
        elif description:
            lines.append(description)
    return "\n\n".join(lines)


def display_flashcard(tool: pd.Series, tool_scenarios: pd.DataFrame, show_answer: bool) -> None:
    image = resolve_image_path(tool.get("image_url"))
    formal_name = safe_text(tool.get("formal_name")) if show_answer else ""
    common_name = safe_text(tool.get("common_name")) if show_answer else ""
    location = safe_text(tool.get("location")) if show_answer else ""
    use_description = safe_text(tool.get("use_description")) if show_answer else ""
    scenarios_text = build_scenario_text(tool_scenarios, show_answer)
    tool_id = safe_text(tool.get("tool_id"), "unknown")

    with st.container(border=True):
        st.subheader("Identify This Tool")
        if image:
            image_columns = st.columns([1, 4, 1])
            with image_columns[1]:
                st.image(image, use_container_width=True)
        else:
            st.warning("No image was found for this tool.")

        st.divider()
        st.text_input("Formal Name", value=formal_name, disabled=True, key=f"formal_{tool_id}_{show_answer}")
        st.text_input("Common Name", value=common_name, disabled=True, key=f"common_{tool_id}_{show_answer}")
        st.text_input("Normally Carried or Stored", value=location, disabled=True, key=f"location_{tool_id}_{show_answer}")
        st.text_area("What It Is Used For", value=use_description, disabled=True, height=100, key=f"use_{tool_id}_{show_answer}")
        st.text_area("Scenarios", value=scenarios_text, disabled=True, height=120, key=f"scenarios_{tool_id}_{show_answer}")


# =========================================================
# Multiple-choice engine
# =========================================================


def get_unique_column_values(dataframe: pd.DataFrame, column: str, excluded_values: list[str] | None = None) -> list[str]:
    if column not in dataframe.columns:
        return []
    excluded_values = excluded_values or []
    values = dataframe[column].dropna().astype(str).str.strip().unique().tolist()
    return [value for value in values if value and value not in excluded_values]


def get_available_question_types(correct_tool: pd.Series, tools: pd.DataFrame) -> list[str]:
    available = []
    for question_type, config in QUESTION_TYPES.items():
        answer_column = config["answer_column"]
        correct_answer = safe_text(correct_tool.get(answer_column))
        if not correct_answer:
            continue
        possible_answers = get_unique_column_values(tools, answer_column, [correct_answer])
        if possible_answers:
            available.append(question_type)
    return available


def generate_distractors(
    correct_tool: pd.Series,
    tools: pd.DataFrame,
    answer_column: str,
    number_needed: int,
    prefer_same_family: bool,
) -> list[str]:
    correct_tool_id = safe_text(correct_tool.get("tool_id"))
    correct_family_id = safe_text(correct_tool.get("family_id"))
    correct_answer = safe_text(correct_tool.get(answer_column))
    selected_answers: list[str] = []

    if prefer_same_family and correct_family_id:
        same_family = tools.loc[
            (tools["tool_id"] != correct_tool_id) & (tools["family_id"] == correct_family_id)
        ]
        candidates = get_unique_column_values(same_family, answer_column, [correct_answer])
        random.shuffle(candidates)
        selected_answers.extend(candidates[:number_needed])

    remaining = number_needed - len(selected_answers)
    if remaining > 0:
        fallback = tools.loc[tools["tool_id"] != correct_tool_id]
        candidates = get_unique_column_values(
            fallback, answer_column, [correct_answer, *selected_answers]
        )
        random.shuffle(candidates)
        selected_answers.extend(candidates[:remaining])

    return selected_answers


def build_scenario_question(
    correct_tool: pd.Series,
    tools: pd.DataFrame,
    scenarios: pd.DataFrame,
    scenario_tools: pd.DataFrame,
    number_of_options: int = 4,
) -> dict[str, object] | None:
    """Build a scenario-to-tool question for the current tool when possible.

    A scenario may have more than one correct tool. All tools marked correct for
    the selected scenario are excluded from the distractor pool so the learner
    is never presented with two defensible answers.
    """
    correct_tool_id = safe_text(correct_tool.get("tool_id"))
    correct_answer = safe_text(correct_tool.get("formal_name"))

    if not correct_tool_id or not correct_answer:
        return None

    matching_links = scenario_tools[
        (scenario_tools["tool_id"] == correct_tool_id)
        & scenario_tools["is_correct"]
    ]

    if matching_links.empty:
        return None

    candidate_scenarios = matching_links.merge(
        scenarios,
        on="scenario_id",
        how="inner",
    )

    if candidate_scenarios.empty:
        return None

    scenario = candidate_scenarios.sample(n=1).iloc[0]
    scenario_id = safe_text(scenario.get("scenario_id"))

    valid_tool_ids = set(
        scenario_tools.loc[
            (scenario_tools["scenario_id"] == scenario_id)
            & scenario_tools["is_correct"],
            "tool_id",
        ].astype(str)
    )

    distractor_tools = tools[~tools["tool_id"].isin(valid_tool_ids)].copy()
    distractors = get_unique_column_values(
        distractor_tools,
        "formal_name",
        [correct_answer],
    )
    random.shuffle(distractors)
    distractors = distractors[: number_of_options - 1]

    if len(distractors) < number_of_options - 1:
        return None

    options = distractors + [correct_answer]
    random.shuffle(options)

    return {
        "question_type": "scenario",
        "answer_column": "formal_name",
        "prompt": "Which tool would be an appropriate choice for this scenario?",
        "scenario_id": scenario_id,
        "scenario_name": safe_text(scenario.get("scenario_name")),
        "scenario_description": safe_text(scenario.get("scenario_description")),
        "correct_answer": correct_answer,
        "options": options,
    }


def build_multiple_choice_question(
    correct_tool: pd.Series,
    tools: pd.DataFrame,
    scenarios: pd.DataFrame,
    scenario_tools: pd.DataFrame,
    number_of_options: int = 4,
) -> dict[str, object]:
    """Build a regular tool question or a scenario-based tool-selection question."""
    available_types = get_available_question_types(correct_tool, tools)

    scenario_question = build_scenario_question(
        correct_tool=correct_tool,
        tools=tools,
        scenarios=scenarios,
        scenario_tools=scenario_tools,
        number_of_options=number_of_options,
    )

    selectable_types = available_types.copy()
    if scenario_question is not None:
        selectable_types.append("scenario")

    if not selectable_types:
        raise ValueError("This tool does not have enough information to create a multiple-choice question.")

    question_type = random.choice(selectable_types)

    if question_type == "scenario":
        return scenario_question

    config = QUESTION_TYPES[question_type]
    answer_column = config["answer_column"]
    correct_answer = safe_text(correct_tool.get(answer_column))
    wrong_answers = generate_distractors(
        correct_tool,
        tools,
        answer_column,
        number_of_options - 1,
        config["prefer_same_family"],
    )
    options = wrong_answers + [correct_answer]
    random.shuffle(options)
    return {
        "question_type": question_type,
        "answer_column": answer_column,
        "prompt": config["prompt"],
        "correct_answer": correct_answer,
        "options": options,
    }


def submit_multiple_choice_answer(selected_answer: str, current_tool_id: str) -> None:
    if st.session_state.mc_answered or st.session_state.mc_question is None:
        return

    question = st.session_state.mc_question
    correct_answer = str(question["correct_answer"])
    is_correct = selected_answer == correct_answer

    record_attempt(
        session_id=st.session_state.mc_session_id,
        learner_id=st.session_state.learner_id,
        mode="multiple_choice",
        tool_id=current_tool_id,
        question_type=str(question["question_type"]),
        selected_answer=selected_answer,
        correct_answer=correct_answer,
        is_correct=is_correct,
    )

    st.session_state.mc_selected_answer = selected_answer
    st.session_state.mc_answered = True
    if is_correct:
        st.session_state.mc_score += 1


# =========================================================
# Adaptive learning / mastery
# =========================================================


def build_tool_learning_status(learner_id: str, tools: pd.DataFrame) -> pd.DataFrame:
    """Return one row per tool with learner-specific mastery and selection weight.

    Mastered requires:
      * at least 3 attempts,
      * at least 80% lifetime accuracy, and
      * the learner's most recent attempt on that tool was successful.

    Adaptive deck weights:
      * needs review: 4x
      * not yet practiced: 3x
      * learning / not mastered: 2x
      * mastered: 1x

    The commonly-missed content flag adds a small additional boost so those
    tools remain visible across learners.
    """
    status = tools[[
        "tool_id", "formal_name", "family_name", "is_commonly_missed"
    ]].copy()

    attempts = get_learner_attempts(learner_id)
    if attempts.empty:
        status["attempts"] = 0
        status["correct"] = 0
        status["accuracy"] = 0.0
        status["latest_correct"] = False
    else:
        attempts["is_correct"] = attempts["is_correct"].astype(int)

        summary = (
            attempts.groupby("tool_id")
            .agg(
                attempts=("attempt_id", "count"),
                correct=("is_correct", "sum"),
            )
            .reset_index()
        )
        summary["accuracy"] = summary["correct"] / summary["attempts"] * 100

        # get_learner_attempts is ordered newest first, so the first row for
        # each tool is the most recent result.
        latest = (
            attempts.drop_duplicates(subset=["tool_id"], keep="first")
            [["tool_id", "is_correct"]]
            .rename(columns={"is_correct": "latest_correct"})
        )

        status = status.merge(summary, on="tool_id", how="left")
        status = status.merge(latest, on="tool_id", how="left")
        status["attempts"] = status["attempts"].fillna(0).astype(int)
        status["correct"] = status["correct"].fillna(0).astype(int)
        status["accuracy"] = status["accuracy"].fillna(0.0)
        status["latest_correct"] = status["latest_correct"].fillna(False).astype(bool)

    status["mastered"] = (
        (status["attempts"] >= 3)
        & (status["accuracy"] >= 80)
        & status["latest_correct"]
    )

    # A recent miss immediately returns a practiced tool to review, even if
    # its lifetime accuracy remains high. Low lifetime accuracy also qualifies.
    status["needs_review"] = (
        (status["attempts"] > 0)
        & ((status["accuracy"] < 70) | (~status["latest_correct"]))
    )

    status["learning_state"] = "Learning"
    status.loc[status["attempts"] == 0, "learning_state"] = "New"
    status.loc[status["needs_review"], "learning_state"] = "Needs Review"
    status.loc[status["mastered"], "learning_state"] = "Mastered"

    status["selection_weight"] = 2.0
    status.loc[status["attempts"] == 0, "selection_weight"] = 3.0
    status.loc[status["needs_review"], "selection_weight"] = 4.0
    status.loc[status["mastered"], "selection_weight"] = 1.0

    # Keep globally commonly-missed tools slightly more prominent without
    # overwhelming the learner-specific history.
    status.loc[status["is_commonly_missed"], "selection_weight"] *= 1.25

    return status


def build_adaptive_deck(
    learner_id: str,
    candidate_tools: pd.DataFrame,
    card_limit: int,
) -> list[str]:
    """Select tools without replacement using learner-specific weights."""
    if candidate_tools.empty or card_limit <= 0:
        return []

    status = build_tool_learning_status(learner_id, candidate_tools)
    remaining = status[["tool_id", "selection_weight"]].copy()
    deck: list[str] = []
    target = min(int(card_limit), len(remaining))

    # Sequential weighted sampling gives a weighted deck with no duplicate
    # tools in the same round.
    while len(deck) < target and not remaining.empty:
        ids = remaining["tool_id"].tolist()
        weights = remaining["selection_weight"].astype(float).tolist()
        chosen = random.choices(ids, weights=weights, k=1)[0]
        deck.append(chosen)
        remaining = remaining[remaining["tool_id"] != chosen]

    return deck


# =========================================================
# Progress calculations and display
# =========================================================


def build_progress_tables(learner_id: str, tools: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int | float]]:
    attempts = get_learner_attempts(learner_id)

    if attempts.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "attempts": 0,
            "accuracy": 0.0,
            "tools_practiced": 0,
            "tools_mastered": 0,
            "needs_review": 0,
        }

    attempts["is_correct"] = attempts["is_correct"].astype(int)
    enriched = attempts.merge(
        tools[["tool_id", "formal_name", "family_name"]],
        on="tool_id",
        how="left",
    )

    by_tool = (
        enriched.groupby(["tool_id", "formal_name", "family_name"], dropna=False)
        .agg(
            attempts=("attempt_id", "count"),
            correct=("is_correct", "sum"),
            last_attempt=("attempted_at", "max"),
        )
        .reset_index()
    )
    by_tool["accuracy"] = (by_tool["correct"] / by_tool["attempts"] * 100).round(0)

    latest_results = (
        enriched.sort_values(["attempted_at", "attempt_id"], ascending=[False, False])
        .drop_duplicates(subset=["tool_id"], keep="first")
        [["tool_id", "is_correct"]]
        .rename(columns={"is_correct": "latest_correct"})
    )
    by_tool = by_tool.merge(latest_results, on="tool_id", how="left")
    by_tool["latest_correct"] = by_tool["latest_correct"].fillna(0).astype(bool)

    by_tool["mastered"] = (
        (by_tool["attempts"] >= 3)
        & (by_tool["accuracy"] >= 80)
        & by_tool["latest_correct"]
    )
    by_tool["needs_review"] = (
        (by_tool["accuracy"] < 70) | (~by_tool["latest_correct"])
    )

    by_family = (
        enriched.groupby("family_name", dropna=False)
        .agg(attempts=("attempt_id", "count"), correct=("is_correct", "sum"), tools_practiced=("tool_id", "nunique"))
        .reset_index()
    )
    by_family["accuracy"] = (by_family["correct"] / by_family["attempts"] * 100).round(0)
    by_family = by_family.sort_values(["accuracy", "family_name"], ascending=[True, True])

    metrics = {
        "attempts": int(len(enriched)),
        "accuracy": float(round(enriched["is_correct"].mean() * 100)),
        "tools_practiced": int(enriched["tool_id"].nunique()),
        "tools_mastered": int(by_tool["mastered"].sum()),
        "needs_review": int(by_tool["needs_review"].sum()),
    }
    return by_tool, by_family, metrics


def display_progress(learner_id: str, tools: pd.DataFrame) -> None:
    by_tool, by_family, metrics = build_progress_tables(learner_id, tools)
    session_count = get_learner_session_count(learner_id)

    st.title("📈 My Progress")
    st.caption("Progress is calculated from this learner's saved flashcard and quiz attempts.")

    cols = st.columns(4)
    cols[0].metric("Sessions", session_count)
    cols[1].metric("Attempts", metrics["attempts"])
    cols[2].metric("Accuracy", f"{metrics['accuracy']:.0f}%")
    cols[3].metric("Tools Practiced", f"{metrics['tools_practiced']} / {len(tools)}")

    cols2 = st.columns(2)
    cols2[0].metric("Mastered", metrics["tools_mastered"])
    cols2[1].metric("Needs Review", metrics["needs_review"])

    if by_tool.empty:
        st.info("No training attempts have been recorded for this learner yet.")
        return

    st.subheader("Progress by Tool Family")
    family_display = by_family.rename(
        columns={
            "family_name": "Tool Family",
            "tools_practiced": "Tools Practiced",
            "attempts": "Attempts",
            "accuracy": "Accuracy %",
        }
    )[["Tool Family", "Tools Practiced", "Attempts", "Accuracy %"]]
    st.dataframe(family_display, use_container_width=True, hide_index=True)

    review = by_tool[by_tool["needs_review"]].sort_values(["accuracy", "attempts"], ascending=[True, False])
    st.subheader("Tools to Review")
    if review.empty:
        st.success("No practiced tools are currently below the review threshold.")
    else:
        review_display = review.rename(
            columns={
                "formal_name": "Tool",
                "family_name": "Family",
                "attempts": "Attempts",
                "accuracy": "Accuracy %",
            }
        )[["Tool", "Family", "Attempts", "Accuracy %"]]
        st.dataframe(review_display, use_container_width=True, hide_index=True)

    with st.expander("All practiced tools"):
        all_tools_display = by_tool.sort_values(["family_name", "formal_name"]).rename(
            columns={
                "formal_name": "Tool",
                "family_name": "Family",
                "attempts": "Attempts",
                "accuracy": "Accuracy %",
                "mastered": "Mastered",
            }
        )[["Tool", "Family", "Attempts", "Accuracy %", "Mastered"]]
        st.dataframe(all_tools_display, use_container_width=True, hide_index=True)


# =========================================================
# Initialize database and application data
# =========================================================

initialize_database()

try:
    tools, families, scenarios, scenario_tools = load_data()
except FileNotFoundError as error:
    st.error("The application could not find its CSV files.")
    st.code(str(error))
    st.stop()
except pd.errors.ParserError as error:
    st.error("One of the CSV files could not be parsed.")
    st.code(str(error))
    st.stop()
except Exception as error:
    st.error("The application could not load its data.")
    st.exception(error)
    st.stop()

if tools.empty:
    st.warning("No published tools were found.")
    st.stop()

if "mode" not in st.session_state:
    st.session_state.mode = "home"


# =========================================================
# Learner selection screen
# =========================================================

if "learner_id" not in st.session_state:
    st.title("🧰 Apprentice Tool Training")
    st.write("Select a learner profile to begin. For this proof of concept, these are demo profiles rather than authenticated City accounts.")

    learners = get_active_learners()
    learner_lookup = {
        f"{row.display_name} ({row.learner_id})": row.learner_id
        for row in learners.itertuples(index=False)
    }

    selected_label = st.selectbox("Learner", options=list(learner_lookup.keys()))

    if st.button("Continue", type="primary", use_container_width=True):
        selected_id = learner_lookup[selected_label]
        selected_row = learners[learners["learner_id"] == selected_id].iloc[0]
        st.session_state.learner_id = selected_id
        st.session_state.learner_name = selected_row["display_name"]
        st.rerun()

    with st.expander("Add a demo learner"):
        new_id = st.text_input("Learner ID", placeholder="AP004")
        new_name = st.text_input("Display Name", placeholder="Apprentice 004")
        if st.button("Add Learner", use_container_width=True):
            success, message = add_learner(new_id, new_name)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    st.stop()


# =========================================================
# Shared learner banner/sidebar
# =========================================================

st.markdown(
    f"""
    <div class="learner-banner">
        <strong>Current learner:</strong> {st.session_state.learner_name}
        &nbsp; <small>({st.session_state.learner_id})</small>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.header("Learner")
st.sidebar.write(f"**{st.session_state.learner_name}**")
st.sidebar.caption(st.session_state.learner_id)

if st.sidebar.button("My Progress", use_container_width=True):
    clear_game_state()
    st.session_state.mode = "progress"
    st.rerun()

if st.sidebar.button("Switch Learner", use_container_width=True):
    switch_learner()
    st.rerun()


# =========================================================
# Home screen
# =========================================================

if st.session_state.mode == "home":
    st.title("🧰 Apprentice Tool Training")
    st.markdown('<div class="home-description">Choose a training activity.</div>', unsafe_allow_html=True)

    progress_by_tool, _, home_metrics = build_progress_tables(st.session_state.learner_id, tools)
    metric_cols = st.columns(3)
    metric_cols[0].metric("Attempts", home_metrics["attempts"])
    metric_cols[1].metric("Accuracy", f"{home_metrics['accuracy']:.0f}%")
    metric_cols[2].metric("Tools Practiced", f"{home_metrics['tools_practiced']} / {len(tools)}")

    row1 = st.columns(2, gap="large")
    with row1[0]:
        with st.container(border=True):
            st.subheader("Flashcards")
            st.write("Study a tool image, reveal the answer, then mark whether you knew it or need to review it.")
            if st.button("Start Flashcards", type="primary", use_container_width=True):
                clear_game_state()
                st.session_state.mode = "flashcards"
                st.rerun()

    with row1[1]:
        with st.container(border=True):
            st.subheader("Multiple Choice")
            st.write("Answer randomized questions about tool names, locations, and families. Results are saved automatically.")
            if st.button("Start Multiple Choice", type="primary", use_container_width=True):
                clear_game_state()
                st.session_state.mode = "multiple_choice"
                st.rerun()

    with st.container(border=True):
        st.subheader("My Progress")
        st.write("See performance by tool family and identify the tools that need more practice.")
        if st.button("View My Progress", use_container_width=True):
            clear_game_state()
            st.session_state.mode = "progress"
            st.rerun()

    st.stop()


# =========================================================
# Progress mode
# =========================================================

if st.session_state.mode == "progress":
    display_progress(st.session_state.learner_id, tools)
    if st.button("Return Home", use_container_width=True):
        go_home()
        st.rerun()
    st.stop()


# =========================================================
# Shared game settings
# =========================================================

st.sidebar.divider()
st.sidebar.header("Game Settings")

family_options = sorted(tools["family_name"].dropna().astype(str).unique().tolist())
selected_families = st.sidebar.multiselect(
    "Tool Families",
    options=family_options,
    default=family_options,
)
commonly_missed_only = st.sidebar.checkbox("Commonly missed tools only", value=False)

filtered_tools = tools[tools["family_name"].isin(selected_families)].copy()
if commonly_missed_only:
    filtered_tools = filtered_tools[filtered_tools["is_commonly_missed"]]

maximum_cards = max(1, len(filtered_tools))
card_limit = st.sidebar.number_input(
    "Number of Questions",
    min_value=1,
    max_value=maximum_cards,
    value=min(10, maximum_cards),
    step=1,
)

if st.sidebar.button("Return Home", use_container_width=True):
    go_home()
    st.rerun()


# =========================================================
# Flashcard mode
# =========================================================

if st.session_state.mode == "flashcards":
    st.title("🧰 Tool Flashcards")
    st.write("Study the tool image and reveal the answer when ready. Your self-rating is saved to your learner history.")
    st.caption("Adaptive practice: tools needing review appear most often; mastered tools remain in rotation at a lower rate.")

    if "deck" not in st.session_state:
        if filtered_tools.empty:
            st.warning("No tools match the selected filters.")
            st.stop()

        st.info(f"{len(filtered_tools)} published tool(s) match the current settings.")
        if st.button("Begin Flashcards", type="primary", use_container_width=True):
            selected_ids = build_adaptive_deck(
                learner_id=st.session_state.learner_id,
                candidate_tools=filtered_tools,
                card_limit=int(card_limit),
            )
            initialize_flashcard_game(selected_ids)
            st.rerun()
        st.stop()

    if st.session_state.completed:
        total_cards = len(st.session_state.deck)
        known_count = st.session_state.known_count
        score = round((known_count / total_cards) * 100) if total_cards else 0

        st.success("Flashcard round complete!")
        metric_columns = st.columns(3)
        metric_columns[0].metric("Cards Studied", total_cards)
        metric_columns[1].metric("Known", known_count)
        metric_columns[2].metric("Self-Rated Score", f"{score}%")
        st.progress(score / 100)

        if st.session_state.review_ids:
            if st.button("Practice Review Cards", type="primary", use_container_width=True):
                start_review_round()
                st.rerun()

        if st.button("View My Progress", use_container_width=True):
            clear_game_state()
            st.session_state.mode = "progress"
            st.rerun()

        if st.button("Return Home", use_container_width=True):
            go_home()
            st.rerun()
        st.stop()

    current_index = st.session_state.current_index
    current_tool_id = st.session_state.deck[current_index]
    matching_tools = tools[tools["tool_id"] == current_tool_id]
    if matching_tools.empty:
        st.error(f"Tool ID {current_tool_id} was not found.")
        st.stop()

    current_tool = matching_tools.iloc[0]
    current_scenarios = get_tool_scenarios(current_tool_id, scenarios, scenario_tools)
    total_cards = len(st.session_state.deck)
    card_number = current_index + 1

    st.write(f"**Card {card_number} of {total_cards}**")
    st.progress(current_index / total_cards)
    display_flashcard(current_tool, current_scenarios, st.session_state.show_answer)

    if not st.session_state.show_answer:
        if st.button("Reveal Answer", type="primary", use_container_width=True):
            st.session_state.show_answer = True
            st.rerun()
    else:
        action_columns = st.columns(2)
        with action_columns[0]:
            if st.button("🔁 Review Again", use_container_width=True):
                mark_flashcard_review()
                st.rerun()
        with action_columns[1]:
            if st.button("✅ I Knew It", type="primary", use_container_width=True):
                mark_flashcard_known()
                st.rerun()
    st.stop()


# =========================================================
# Multiple-choice mode
# =========================================================

if st.session_state.mode == "multiple_choice":
    st.title("🧰 Multiple-Choice Tool Game")
    st.write("Answer questions about each tool. Every submitted answer is saved to this learner's history.")
    st.caption("Adaptive practice: tools needing review appear most often; mastered tools remain in rotation at a lower rate.")

    if len(filtered_tools) < 2:
        st.warning("The multiple-choice game requires at least two published tools.")
        st.stop()

    if "mc_deck" not in st.session_state:
        st.info(f"{len(filtered_tools)} published tool(s) match the current settings.")
        if st.button("Begin Multiple Choice", type="primary", use_container_width=True):
            selected_ids = build_adaptive_deck(
                learner_id=st.session_state.learner_id,
                candidate_tools=filtered_tools,
                card_limit=int(card_limit),
            )
            initialize_multiple_choice_game(selected_ids)
            st.rerun()
        st.stop()

    if st.session_state.mc_completed:
        total_questions = len(st.session_state.mc_deck)
        score = st.session_state.mc_score
        percentage = round((score / total_questions) * 100) if total_questions else 0

        st.success("Multiple-choice round complete!")
        metric_columns = st.columns(3)
        metric_columns[0].metric("Questions", total_questions)
        metric_columns[1].metric("Correct", score)
        metric_columns[2].metric("Score", f"{percentage}%")
        st.progress(percentage / 100)

        if st.button("Play Again", type="primary", use_container_width=True):
            clear_game_state()
            st.session_state.mode = "multiple_choice"
            st.rerun()

        if st.button("View My Progress", use_container_width=True):
            clear_game_state()
            st.session_state.mode = "progress"
            st.rerun()

        if st.button("Return Home", use_container_width=True):
            go_home()
            st.rerun()
        st.stop()

    current_index = st.session_state.mc_index
    current_tool_id = st.session_state.mc_deck[current_index]
    current_tool_match = tools[tools["tool_id"] == current_tool_id]
    if current_tool_match.empty:
        st.error(f"Tool ID {current_tool_id} was not found.")
        st.stop()

    current_tool = current_tool_match.iloc[0]
    total_questions = len(st.session_state.mc_deck)
    question_number = st.session_state.mc_index + 1
    st.write(f"**Question {question_number} of {total_questions}**")
    st.progress(st.session_state.mc_index / total_questions)

    image = resolve_image_path(current_tool.get("image_url"))

    if st.session_state.mc_question is None:
        try:
            st.session_state.mc_question = build_multiple_choice_question(
                correct_tool=current_tool,
                tools=tools,
                scenarios=scenarios,
                scenario_tools=scenario_tools,
                number_of_options=4,
            )
        except ValueError as error:
            st.warning(str(error))
            if st.button("Skip This Tool", use_container_width=True):
                advance_multiple_choice()
                st.rerun()
            st.stop()

    question = st.session_state.mc_question
    question_prompt = str(question["prompt"])
    correct_answer = str(question["correct_answer"])
    answer_options = question["options"]
    question_type = str(question["question_type"])

    with st.container(border=True):
        st.subheader(question_prompt)

        if question_type == "scenario":
            scenario_name = str(question.get("scenario_name", "")).strip()
            scenario_description = str(question.get("scenario_description", "")).strip()

            if scenario_name:
                st.markdown(f"**{scenario_name}**")
            if scenario_description:
                st.write(scenario_description)
        else:
            if image:
                image_columns = st.columns([1, 4, 1])
                with image_columns[1]:
                    st.image(image, use_container_width=True)
            else:
                st.warning("No image was found for this tool.")

        selected_answer = st.radio(
            "Select your answer",
            options=answer_options,
            index=None,
            disabled=st.session_state.mc_answered,
            key=f"mc_answer_{current_tool_id}_{st.session_state.mc_index}_{question_type}",
        )

        if not st.session_state.mc_answered:
            if st.button(
                "Submit Answer",
                type="primary",
                use_container_width=True,
                disabled=selected_answer is None,
            ):
                submit_multiple_choice_answer(str(selected_answer), current_tool_id)
                st.rerun()
        else:
            selected = st.session_state.mc_selected_answer
            if selected == correct_answer:
                st.success("Correct!")
            else:
                st.error(f"Incorrect. The correct answer is **{correct_answer}**.")

            st.divider()
            formal_name = safe_text(current_tool.get("formal_name"))
            common_name = safe_text(current_tool.get("common_name"))
            location = safe_text(current_tool.get("location"))
            family_name = safe_text(current_tool.get("family_name"))
            use_description = safe_text(current_tool.get("use_description"))

            st.write(f"**Formal name:** {formal_name}")
            if common_name:
                st.write(f"**Common name:** {common_name}")
            if use_description:
                st.write(f"**Used for:** {use_description}")
            if location:
                st.write(f"**Normally carried or stored:** {location}")
            if family_name:
                st.write(f"**Tool family:** {family_name}")

            if st.button("Next Question", type="primary", use_container_width=True):
                advance_multiple_choice()
                st.rerun()
