from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List
import json

import requests
import yaml


BASE_URL = "http://127.0.0.1:8000"
ORCHESTRATOR_URL = f"{BASE_URL}/orchestrator/ask"

REGRESSION_FILE_PATH = Path("tests/regression_prompts.yaml")
REPORT_FILE_PATH = Path("logs/regression_report.json")


def load_regression_tests() -> List[Dict[str, Any]]:
    """
    Load regression test cases from YAML.
    """

    if not REGRESSION_FILE_PATH.exists():
        raise FileNotFoundError(
            f"Regression test file not found: {REGRESSION_FILE_PATH}"
        )

    with open(REGRESSION_FILE_PATH, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    return data.get("tests", [])


def call_orchestrator(question: str) -> Dict[str, Any]:
    """
    Send question to LangGraph orchestrator endpoint.
    """

    response = requests.post(
        ORCHESTRATOR_URL,
        json={"question": question},
        timeout=60,
    )

    response.raise_for_status()

    return response.json()


def response_contains_expected_text(
    response_data: Dict[str, Any],
    expected_values: List[str],
) -> bool:
    """
    Convert full response into text and check whether expected text exists.
    """

    response_text = json.dumps(response_data, default=str).lower()

    for expected_value in expected_values:
        if expected_value.lower() not in response_text:
            return False

    return True


def run_single_test(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run one regression test case.
    """

    question = test_case["question"]
    expected_agent = test_case["expected_agent"]
    expected_answer_type = test_case["expected_answer_type"]
    expected_contains = test_case.get("expected_contains", [])

    try:
        response_data = call_orchestrator(question)

        actual_agent = response_data.get("selected_agent")
        actual_answer_type = response_data.get("answer_type")

        agent_passed = actual_agent == expected_agent
        answer_type_passed = actual_answer_type == expected_answer_type
        content_passed = response_contains_expected_text(
            response_data,
            expected_contains,
        )

        passed = agent_passed and answer_type_passed and content_passed

        return {
            "test_name": test_case["test_name"],
            "question": question,
            "status": "PASSED" if passed else "FAILED",
            "expected_agent": expected_agent,
            "actual_agent": actual_agent,
            "expected_answer_type": expected_answer_type,
            "actual_answer_type": actual_answer_type,
            "expected_contains": expected_contains,
            "agent_passed": agent_passed,
            "answer_type_passed": answer_type_passed,
            "content_passed": content_passed,
            "error": None,
            "response": response_data,
        }

    except Exception as error:
        return {
            "test_name": test_case["test_name"],
            "question": question,
            "status": "ERROR",
            "expected_agent": expected_agent,
            "actual_agent": None,
            "expected_answer_type": expected_answer_type,
            "actual_answer_type": None,
            "expected_contains": expected_contains,
            "agent_passed": False,
            "answer_type_passed": False,
            "content_passed": False,
            "error": str(error),
            "response": None,
        }


def save_report(report: Dict[str, Any]) -> None:
    """
    Save regression test report as JSON.
    """

    REPORT_FILE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(REPORT_FILE_PATH, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4, default=str)


def run_all_tests() -> Dict[str, Any]:
    """
    Run all regression tests and create report.
    """

    test_cases = load_regression_tests()

    results = []

    for test_case in test_cases:
        result = run_single_test(test_case)
        results.append(result)

    total_tests = len(results)
    passed_tests = len(
        [
            result
            for result in results
            if result["status"] == "PASSED"
        ]
    )
    failed_tests = len(
        [
            result
            for result in results
            if result["status"] == "FAILED"
        ]
    )
    error_tests = len(
        [
            result
            for result in results
            if result["status"] == "ERROR"
        ]
    )

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "error_tests": error_tests,
        "results": results,
    }

    save_report(report)

    return report


if __name__ == "__main__":
    final_report = run_all_tests()

    print("\nRegression Test Summary")
    print("-----------------------")
    print(f"Total tests : {final_report['total_tests']}")
    print(f"Passed      : {final_report['passed_tests']}")
    print(f"Failed      : {final_report['failed_tests']}")
    print(f"Errors      : {final_report['error_tests']}")
    print(f"Report file : {REPORT_FILE_PATH}")

    for result in final_report["results"]:
        print(
            f"{result['status']} - {result['test_name']} "
            f"| expected: {result['expected_agent']} "
            f"| actual: {result['actual_agent']}"
        )