from pathlib import Path

from legal.evals.conversation_eval import CASES_PATH, ConversationEvalRunner, SCHEMA_PATH


def test_conversation_eval_schema_and_case_files_exist() -> None:
    assert Path(SCHEMA_PATH).is_file()
    assert Path(CASES_PATH).is_file()


def test_conversation_eval_cases_validate_against_local_schema_rules() -> None:
    runner = ConversationEvalRunner()
    assert runner.validate_schema() == []
    assert len(runner.load_cases()) >= 22
