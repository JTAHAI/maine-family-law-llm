from legal.evals.evaluation_orchestrator import EvaluationOrchestrator

def test_evaluation_orchestrator():
    orchestrator = EvaluationOrchestrator()

    result = orchestrator.run_all()

    assert result["status"] == "pass"
