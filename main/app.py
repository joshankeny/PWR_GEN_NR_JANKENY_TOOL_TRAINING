from __future__ import annotations

import random
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

TOOLS_FILE = DATA_DIR / "tools.csv"
FAMILIES_FILE = DATA_DIR / "tool_families.csv"
SCENARIOS_FILE = DATA_DIR / "scenarios.csv"
SCENARIO_TOOLS_FILE = DATA_DIR / "scenario_tools.csv"


# =========================================================
# Styling
# =========================================================

st.markdown(
    """
    <style>
        .block-container {
            max-width: 850px;
            padding-top: 2rem;
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
            margin-bottom: 1.5rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Utility functions
# =========================================================

def normalize_id(value: object) -> str:
    """Convert CSV IDs into consistent strings."""
    if pd.isna(value):
        return ""

    text = str(value).strip()

    if text.endswith(".0"):
        text = text[:-2]

    return text


def normalize_boolean(
    value: object,
    default: bool = False,
) -> bool:
    """Convert common CSV boolean values to Python booleans."""
    if pd.isna(value):
        return default

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
        "t",
    }


def safe_text(
    value: object,
    fallback: str = "",
) -> str:
    """Return clean text for display."""
    if pd.isna(value):
        return fallback

    text = str(value).strip()
    return text if text else fallback


def resolve_image_path(
    image_value: object,
) -> str | None:
    """Resolve a local image path or public URL."""

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
# Load CSV data
# =========================================================

@st.cache_data
def load_data() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """Load and prepare all four CSV files."""

    required_files = [
        TOOLS_FILE,
        FAMILIES_FILE,
        SCENARIOS_FILE,
        SCENARIO_TOOLS_FILE,
    ]

    missing_files = [
        str(file_path)
        for file_path in required_files
        if not file_path.is_file()
    ]

    if missing_files:
        raise FileNotFoundError(
            "Missing required CSV files:\n"
            + "\n".join(missing_files)
        )

    tools = pd.read_csv(TOOLS_FILE)
    families = pd.read_csv(FAMILIES_FILE)
    scenarios = pd.read_csv(SCENARIOS_FILE)
    scenario_tools = pd.read_csv(SCENARIO_TOOLS_FILE)

    tools.columns = tools.columns.str.strip()
    families.columns = families.columns.str.strip()
    scenarios.columns = scenarios.columns.str.strip()
    scenario_tools.columns = scenario_tools.columns.str.strip()

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

    for column, default in tool_defaults.items():
        if column not in tools.columns:
            tools[column] = default

    family_defaults = {
        "family_id": "",
        "family_name": "Uncategorized",
        "description": "",
        "is_active": True,
    }

    for column, default in family_defaults.items():
        if column not in families.columns:
            families[column] = default

    scenario_defaults = {
        "scenario_id": "",
        "scenario_name": "",
        "scenario_description": "",
        "difficulty": 1,
        "status": "PUBLISHED",
    }

    for column, default in scenario_defaults.items():
        if column not in scenarios.columns:
            scenarios[column] = default

    scenario_tool_defaults = {
        "scenario_id": "",
        "tool_id": "",
        "is_correct": True,
    }

    for column, default in scenario_tool_defaults.items():
        if column not in scenario_tools.columns:
            scenario_tools[column] = default

    tools["tool_id"] = tools["tool_id"].apply(normalize_id)
    tools["family_id"] = tools["family_id"].apply(normalize_id)

    families["family_id"] = families["family_id"].apply(
        normalize_id
    )

    scenarios["scenario_id"] = scenarios[
        "scenario_id"
    ].apply(normalize_id)

    scenario_tools["scenario_id"] = scenario_tools[
        "scenario_id"
    ].apply(normalize_id)

    scenario_tools["tool_id"] = scenario_tools[
        "tool_id"
    ].apply(normalize_id)

    tools = tools[
        tools["status"]
        .fillna("PUBLISHED")
        .astype(str)
        .str.strip()
        .str.upper()
        .eq("PUBLISHED")
    ].copy()

    scenarios = scenarios[
        scenarios["status"]
        .fillna("PUBLISHED")
        .astype(str)
        .str.strip()
        .str.upper()
        .eq("PUBLISHED")
    ].copy()

    families = families[
        families["is_active"].apply(
            lambda value: normalize_boolean(
                value,
                default=True,
            )
        )
    ].copy()

    tools["is_commonly_missed"] = tools[
        "is_commonly_missed"
    ].apply(normalize_boolean)

    scenario_tools["is_correct"] = scenario_tools[
        "is_correct"
    ].apply(
        lambda value: normalize_boolean(
            value,
            default=True,
        )
    )

    tools = tools.merge(
        families[["family_id", "family_name"]],
        on="family_id",
        how="left",
    )

    tools["family_name"] = tools["family_name"].fillna(
        "Uncategorized"
    )

    return tools, families, scenarios, scenario_tools


def get_tool_scenarios(
    tool_id: str,
    scenarios: pd.DataFrame,
    scenario_tools: pd.DataFrame,
) -> pd.DataFrame:
    """Return published scenarios associated with a tool."""

    matching_links = scenario_tools[
        (scenario_tools["tool_id"] == tool_id)
        & scenario_tools["is_correct"]
    ]

    if matching_links.empty:
        return pd.DataFrame()

    return matching_links.merge(
        scenarios,
        on="scenario_id",
        how="inner",
    )


# =========================================================
# Global navigation functions
# =========================================================

def clear_game_state() -> None:
    """Clear flashcard and multiple-choice game state."""

    keys = [
        "deck",
        "current_index",
        "show_answer",
        "known_count",
        "review_count",
        "review_ids",
        "completed",
        "mc_deck",
        "mc_index",
        "mc_score",
        "mc_answered",
        "mc_selected_answer",
        "mc_question",
        "mc_completed",
    ]

    for key in keys:
        st.session_state.pop(key, None)


def go_home() -> None:
    """Return to the application home screen."""
    clear_game_state()
    st.session_state.mode = "home"


def start_flashcard_mode() -> None:
    """Open the flashcard setup screen."""
    clear_game_state()
    st.session_state.mode = "flashcards"


def start_multiple_choice_mode() -> None:
    """Open the multiple-choice setup screen."""
    clear_game_state()
    st.session_state.mode = "multiple_choice"


# =========================================================
# Flashcard functions
# =========================================================

def initialize_flashcard_game(
    tool_ids: list[str],
) -> None:
    """Create a shuffled flashcard deck."""

    deck = tool_ids.copy()
    random.shuffle(deck)

    st.session_state.deck = deck
    st.session_state.current_index = 0
    st.session_state.show_answer = False
    st.session_state.known_count = 0
    st.session_state.review_count = 0
    st.session_state.review_ids = []
    st.session_state.completed = False


def advance_flashcard() -> None:
    """Move to the next flashcard."""

    st.session_state.current_index += 1
    st.session_state.show_answer = False

    if st.session_state.current_index >= len(
        st.session_state.deck
    ):
        st.session_state.completed = True


def mark_flashcard_known() -> None:
    """Mark the current tool as known."""

    st.session_state.known_count += 1
    advance_flashcard()


def mark_flashcard_review() -> None:
    """Add the current tool to the review pile."""

    current_tool_id = st.session_state.deck[
        st.session_state.current_index
    ]

    if current_tool_id not in st.session_state.review_ids:
        st.session_state.review_ids.append(current_tool_id)

    st.session_state.review_count += 1
    advance_flashcard()


def start_review_round() -> None:
    """Start another round using review cards only."""

    deck = st.session_state.review_ids.copy()
    random.shuffle(deck)

    st.session_state.deck = deck
    st.session_state.current_index = 0
    st.session_state.show_answer = False
    st.session_state.known_count = 0
    st.session_state.review_count = 0
    st.session_state.review_ids = []
    st.session_state.completed = False


def build_scenario_text(
    tool_scenarios: pd.DataFrame,
    show_answer: bool,
) -> str:
    """Build scenario text for a revealed flashcard."""

    if not show_answer or tool_scenarios.empty:
        return ""

    scenario_lines = []

    for _, scenario in tool_scenarios.iterrows():
        scenario_name = safe_text(
            scenario.get("scenario_name")
        )

        scenario_description = safe_text(
            scenario.get("scenario_description")
        )

        if scenario_name and scenario_description:
            scenario_lines.append(
                f"{scenario_name}: {scenario_description}"
            )
        elif scenario_name:
            scenario_lines.append(scenario_name)
        elif scenario_description:
            scenario_lines.append(scenario_description)

    return "\n\n".join(scenario_lines)


def display_flashcard(
    tool: pd.Series,
    tool_scenarios: pd.DataFrame,
    show_answer: bool,
) -> None:
    """Display one persistent flashcard."""

    image = resolve_image_path(tool.get("image_url"))

    if show_answer:
        formal_name = safe_text(tool.get("formal_name"))
        common_name = safe_text(tool.get("common_name"))
        location = safe_text(tool.get("location"))

        scenarios_text = build_scenario_text(
            tool_scenarios,
            show_answer=True,
        )
    else:
        formal_name = ""
        common_name = ""
        location = ""
        scenarios_text = ""

    tool_id = safe_text(
        tool.get("tool_id"),
        "unknown",
    )

    with st.container(border=True):
        st.subheader("Identify This Tool")

        if image:
            image_columns = st.columns([1, 4, 1])

            with image_columns[1]:
                st.image(
                    image,
                    use_container_width=True,
                )
        else:
            st.warning(
                "No image was found for this tool."
            )

        st.divider()

        st.text_input(
            "Formal Name",
            value=formal_name,
            disabled=True,
            key=f"formal_{tool_id}_{show_answer}",
        )

        st.text_input(
            "Common Name",
            value=common_name,
            disabled=True,
            key=f"common_{tool_id}_{show_answer}",
        )

        st.text_input(
            "Normally Carried or Stored",
            value=location,
            disabled=True,
            key=f"location_{tool_id}_{show_answer}",
        )

        st.text_area(
            "Scenarios",
            value=scenarios_text,
            disabled=True,
            height=130,
            key=f"scenarios_{tool_id}_{show_answer}",
        )


# =========================================================
# Multiple-choice functions
# =========================================================

# =========================================================
# Multiple-choice question engine
# =========================================================

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


def initialize_multiple_choice_game(
    tool_ids: list[str],
) -> None:
    """Create a shuffled multiple-choice deck."""

    deck = tool_ids.copy()
    random.shuffle(deck)

    st.session_state.mc_deck = deck
    st.session_state.mc_index = 0
    st.session_state.mc_score = 0
    st.session_state.mc_answered = False
    st.session_state.mc_selected_answer = None
    st.session_state.mc_question = None
    st.session_state.mc_completed = False


def get_unique_column_values(
    dataframe: pd.DataFrame,
    column: str,
    excluded_values: list[str] | None = None,
) -> list[str]:
    """Return unique, nonblank values from a column."""

    if column not in dataframe.columns:
        return []

    excluded_values = excluded_values or []

    values = (
        dataframe[column]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    return [
        value
        for value in values
        if value and value not in excluded_values
    ]


def get_available_question_types(
    correct_tool: pd.Series,
    tools: pd.DataFrame,
) -> list[str]:
    """
    Return question types that have a valid answer and
    at least one possible incorrect answer.
    """

    available_types = []

    for question_type, configuration in QUESTION_TYPES.items():
        answer_column = configuration["answer_column"]

        correct_answer = safe_text(
            correct_tool.get(answer_column)
        )

        if not correct_answer:
            continue

        possible_answers = get_unique_column_values(
            dataframe=tools,
            column=answer_column,
            excluded_values=[correct_answer],
        )

        if possible_answers:
            available_types.append(question_type)

    return available_types


def generate_distractors(
    correct_tool: pd.Series,
    tools: pd.DataFrame,
    answer_column: str,
    number_needed: int,
    prefer_same_family: bool,
) -> list[str]:
    """
    Generate incorrect answers.

    When requested, values from tools in the same family are
    used first. Remaining slots are filled from other families.
    """

    correct_tool_id = safe_text(
        correct_tool.get("tool_id")
    )

    correct_family_id = safe_text(
        correct_tool.get("family_id")
    )

    correct_answer = safe_text(
        correct_tool.get(answer_column)
    )

    selected_answers: list[str] = []

    if prefer_same_family and correct_family_id:
        same_family_tools = tools.loc[
            (tools["tool_id"] != correct_tool_id)
            & (tools["family_id"] == correct_family_id)
        ]

        same_family_answers = get_unique_column_values(
            dataframe=same_family_tools,
            column=answer_column,
            excluded_values=[correct_answer],
        )

        random.shuffle(same_family_answers)

        selected_answers.extend(
            same_family_answers[:number_needed]
        )

    remaining_slots = number_needed - len(selected_answers)

    if remaining_slots > 0:
        if prefer_same_family and correct_family_id:
            fallback_tools = tools.loc[
                (tools["tool_id"] != correct_tool_id)
                & (tools["family_id"] != correct_family_id)
            ]
        else:
            fallback_tools = tools.loc[
                tools["tool_id"] != correct_tool_id
            ]

        fallback_answers = get_unique_column_values(
            dataframe=fallback_tools,
            column=answer_column,
            excluded_values=[
                correct_answer,
                *selected_answers,
            ],
        )

        random.shuffle(fallback_answers)

        selected_answers.extend(
            fallback_answers[:remaining_slots]
        )

    # Final fallback for small or incomplete datasets.
    remaining_slots = number_needed - len(selected_answers)

    if remaining_slots > 0:
        all_remaining_answers = get_unique_column_values(
            dataframe=tools,
            column=answer_column,
            excluded_values=[
                correct_answer,
                *selected_answers,
            ],
        )

        random.shuffle(all_remaining_answers)

        selected_answers.extend(
            all_remaining_answers[:remaining_slots]
        )

    return selected_answers


def build_multiple_choice_question(
    correct_tool: pd.Series,
    tools: pd.DataFrame,
    number_of_options: int = 4,
) -> dict[str, object]:
    """
    Build one random multiple-choice question.

    The returned dictionary contains the question type,
    prompt, correct answer, and shuffled answer options.
    """

    available_types = get_available_question_types(
        correct_tool=correct_tool,
        tools=tools,
    )

    if not available_types:
        raise ValueError(
            "This tool does not have enough information "
            "to create a multiple-choice question."
        )

    question_type = random.choice(available_types)

    configuration = QUESTION_TYPES[question_type]

    answer_column = configuration["answer_column"]
    prompt = configuration["prompt"]
    prefer_same_family = configuration[
        "prefer_same_family"
    ]

    correct_answer = safe_text(
        correct_tool.get(answer_column)
    )

    wrong_answers = generate_distractors(
        correct_tool=correct_tool,
        tools=tools,
        answer_column=answer_column,
        number_needed=number_of_options - 1,
        prefer_same_family=prefer_same_family,
    )

    options = wrong_answers + [correct_answer]
    random.shuffle(options)

    return {
        "question_type": question_type,
        "answer_column": answer_column,
        "prompt": prompt,
        "correct_answer": correct_answer,
        "options": options,
    }


def submit_multiple_choice_answer(
    selected_answer: str,
) -> None:
    """Score and lock the current answer."""

    if st.session_state.mc_answered:
        return

    question = st.session_state.mc_question

    if question is None:
        return

    correct_answer = question["correct_answer"]

    st.session_state.mc_selected_answer = selected_answer
    st.session_state.mc_answered = True

    if selected_answer == correct_answer:
        st.session_state.mc_score += 1


def advance_multiple_choice() -> None:
    """Move to the next multiple-choice question."""

    st.session_state.mc_index += 1
    st.session_state.mc_answered = False
    st.session_state.mc_selected_answer = None
    st.session_state.mc_question = None

    if st.session_state.mc_index >= len(
        st.session_state.mc_deck
    ):
        st.session_state.mc_completed = True

# =========================================================
# Load application data
# =========================================================

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


# =========================================================
# Initialize navigation
# =========================================================

if "mode" not in st.session_state:
    st.session_state.mode = "home"


# =========================================================
# Home screen
# =========================================================

if st.session_state.mode == "home":
    st.title("🧰 Apprentice Tool Training")

    st.markdown(
        """
        <div class="home-description">
            Choose a training activity.
        </div>
        """,
        unsafe_allow_html=True,
    )

    mode_columns = st.columns(2, gap="large")

    with mode_columns[0]:
        with st.container(border=True):
            st.subheader("Flashcards")

            st.write(
                "Study a tool image, recall its name and location, "
                "and reveal the complete answer."
            )

            if st.button(
                "Start Flashcards",
                type="primary",
                use_container_width=True,
            ):
                start_flashcard_mode()
                st.rerun()

    with mode_columns[1]:
        with st.container(border=True):
            st.subheader("Multiple Choice")

            st.write(
                "Study a tool image and select the correct tool name "
                "from several choices."
            )

            if st.button(
                "Start Multiple Choice",
                type="primary",
                use_container_width=True,
            ):
                start_multiple_choice_mode()
                st.rerun()

    st.stop()


# =========================================================
# Shared sidebar settings
# =========================================================

st.sidebar.header("Game Settings")

family_options = sorted(
    tools["family_name"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)

selected_families = st.sidebar.multiselect(
    "Tool Families",
    options=family_options,
    default=family_options,
)

commonly_missed_only = st.sidebar.checkbox(
    "Commonly missed tools only",
    value=False,
)

filtered_tools = tools[
    tools["family_name"].isin(selected_families)
].copy()

if commonly_missed_only:
    filtered_tools = filtered_tools[
        filtered_tools["is_commonly_missed"]
    ]

maximum_cards = max(1, len(filtered_tools))

card_limit = st.sidebar.number_input(
    "Number of Questions",
    min_value=1,
    max_value=maximum_cards,
    value=min(10, maximum_cards),
    step=1,
)

if st.sidebar.button(
    "Return Home",
    use_container_width=True,
):
    go_home()
    st.rerun()


# =========================================================
# Flashcard mode
# =========================================================

if st.session_state.mode == "flashcards":
    st.title("🧰 Tool Flashcards")

    st.write(
        "Study the tool image and reveal the answer when ready."
    )

    if "deck" not in st.session_state:
        if filtered_tools.empty:
            st.warning(
                "No tools match the selected filters."
            )
            st.stop()

        st.info(
            f"{len(filtered_tools)} published tool(s) match "
            "the current settings."
        )

        if st.button(
            "Begin Flashcards",
            type="primary",
            use_container_width=True,
        ):
            selected_ids = filtered_tools[
                "tool_id"
            ].tolist()

            random.shuffle(selected_ids)

            initialize_flashcard_game(
                selected_ids[: int(card_limit)]
            )

            st.rerun()

        st.stop()

    if st.session_state.completed:
        total_cards = len(st.session_state.deck)
        known_count = st.session_state.known_count

        score = (
            round((known_count / total_cards) * 100)
            if total_cards
            else 0
        )

        st.success("Flashcard round complete!")

        metric_columns = st.columns(3)

        metric_columns[0].metric(
            "Cards Studied",
            total_cards,
        )

        metric_columns[1].metric(
            "Known",
            known_count,
        )

        metric_columns[2].metric(
            "Score",
            f"{score}%",
        )

        st.progress(score / 100)

        if st.session_state.review_ids:
            if st.button(
                "Practice Review Cards",
                type="primary",
                use_container_width=True,
            ):
                start_review_round()
                st.rerun()

        if st.button(
            "Return Home",
            use_container_width=True,
        ):
            go_home()
            st.rerun()

        st.stop()

    current_index = st.session_state.current_index
    current_tool_id = st.session_state.deck[current_index]

    matching_tools = tools[
        tools["tool_id"] == current_tool_id
    ]

    if matching_tools.empty:
        st.error(
            f"Tool ID {current_tool_id} was not found."
        )
        st.stop()

    current_tool = matching_tools.iloc[0]

    current_scenarios = get_tool_scenarios(
        tool_id=current_tool_id,
        scenarios=scenarios,
        scenario_tools=scenario_tools,
    )

    total_cards = len(st.session_state.deck)
    card_number = current_index + 1

    st.write(
        f"**Card {card_number} of {total_cards}**"
    )

    st.progress(current_index / total_cards)

    display_flashcard(
        tool=current_tool,
        tool_scenarios=current_scenarios,
        show_answer=st.session_state.show_answer,
    )

    if not st.session_state.show_answer:
        if st.button(
            "Reveal Answer",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.show_answer = True
            st.rerun()

    else:
        action_columns = st.columns(2)

        with action_columns[0]:
            if st.button(
                "🔁 Review Again",
                use_container_width=True,
            ):
                mark_flashcard_review()
                st.rerun()

        with action_columns[1]:
            if st.button(
                "✅ I Knew It",
                type="primary",
                use_container_width=True,
            ):
                mark_flashcard_known()
                st.rerun()

    st.stop()


# =========================================================
# Multiple-choice mode
# =========================================================

if st.session_state.mode == "multiple_choice":
    st.title("🧰 Multiple-Choice Tool Game")

    st.write(
        "Look at the tool image and select its formal name."
    )

    if len(filtered_tools) < 2:
        st.warning(
            "The multiple-choice game requires at least "
            "two published tools."
        )
        st.stop()

    if "mc_deck" not in st.session_state:
        st.info(
            f"{len(filtered_tools)} published tool(s) match "
            "the current settings."
        )

        if st.button(
            "Begin Multiple Choice",
            type="primary",
            use_container_width=True,
        ):
            selected_ids = filtered_tools[
                "tool_id"
            ].tolist()

            random.shuffle(selected_ids)

            initialize_multiple_choice_game(
                selected_ids[: int(card_limit)]
            )

            st.rerun()

        st.stop()

    if st.session_state.mc_completed:
        total_questions = len(
            st.session_state.mc_deck
        )

        score = st.session_state.mc_score

        percentage = (
            round((score / total_questions) * 100)
            if total_questions
            else 0
        )

        st.success("Multiple-choice round complete!")

        metric_columns = st.columns(3)

        metric_columns[0].metric(
            "Questions",
            total_questions,
        )

        metric_columns[1].metric(
            "Correct",
            score,
        )

        metric_columns[2].metric(
            "Score",
            f"{percentage}%",
        )

        st.progress(percentage / 100)

        if st.button(
            "Play Again",
            type="primary",
            use_container_width=True,
        ):
            clear_game_state()
            st.session_state.mode = "multiple_choice"
            st.rerun()

        if st.button(
            "Return Home",
            use_container_width=True,
        ):
            go_home()
            st.rerun()

        st.stop()

    current_index = st.session_state.mc_index
    current_tool_id = st.session_state.mc_deck[
        current_index
    ]

    current_tool_match = tools[
        tools["tool_id"] == current_tool_id
    ]

    if current_tool_match.empty:
        st.error(
            f"Tool ID {current_tool_id} was not found."
        )
        st.stop()

    current_tool = current_tool_match.iloc[0]

    total_questions = len(
        st.session_state.mc_deck
    )

    question_number = (
        st.session_state.mc_index + 1
    )

    st.write(
        f"**Question {question_number} "
        f"of {total_questions}**"
    )

    st.progress(
        st.session_state.mc_index
        / total_questions
    )

    image = resolve_image_path(
        current_tool.get("image_url")
    )

    # Build the question only once.
    # Streamlit reruns will continue using the same question.
    if st.session_state.mc_question is None:
        try:
            st.session_state.mc_question = (
                build_multiple_choice_question(
                    correct_tool=current_tool,
                    # Use all published tools for answer choices,
                    # even when game questions are filtered.
                    tools=tools,
                    number_of_options=4,
                )
            )

        except ValueError as error:
            st.warning(str(error))

            if st.button(
                "Skip This Tool",
                use_container_width=True,
            ):
                advance_multiple_choice()
                st.rerun()

            st.stop()

    question = st.session_state.mc_question

    question_prompt = question["prompt"]
    correct_answer = question["correct_answer"]
    answer_options = question["options"]
    question_type = question["question_type"]

    with st.container(border=True):
        st.subheader(question_prompt)

        if image:
            image_columns = st.columns(
                [1, 4, 1]
            )

            with image_columns[1]:
                st.image(
                    image,
                    use_container_width=True,
                )
        else:
            st.warning(
                "No image was found for this tool."
            )

        selected_answer = st.radio(
            "Select your answer",
            options=answer_options,
            index=None,
            disabled=(
                st.session_state.mc_answered
            ),
            key=(
                f"mc_answer_"
                f"{current_tool_id}_"
                f"{st.session_state.mc_index}_"
                f"{question_type}"
            ),
        )

        if not st.session_state.mc_answered:
            if st.button(
                "Submit Answer",
                type="primary",
                use_container_width=True,
                disabled=selected_answer is None,
            ):
                submit_multiple_choice_answer(
                    selected_answer=selected_answer,
                )

                st.rerun()

        else:
            selected = (
                st.session_state
                .mc_selected_answer
            )

            if selected == correct_answer:
                st.success("Correct!")
            else:
                st.error(
                    "Incorrect. The correct answer is "
                    f"**{correct_answer}**."
                )

            st.divider()

            formal_name = safe_text(
                current_tool.get("formal_name")
            )

            common_name = safe_text(
                current_tool.get("common_name")
            )

            location = safe_text(
                current_tool.get("location")
            )

            family_name = safe_text(
                current_tool.get("family_name")
            )

            st.write(
                f"**Formal name:** {formal_name}"
            )

            if common_name:
                st.write(
                    f"**Common name:** {common_name}"
                )

            if location:
                st.write(
                    "**Normally carried or stored:** "
                    f"{location}"
                )

            if family_name:
                st.write(
                    f"**Tool family:** {family_name}"
                )

            if st.button(
                "Next Question",
                type="primary",
                use_container_width=True,
            ):
                advance_multiple_choice()
                st.rerun()