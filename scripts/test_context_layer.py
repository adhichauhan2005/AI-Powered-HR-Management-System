from pathlib import Path

import sys


# ---------------------------------------------------------
# ADD BACKEND TO PYTHON PATH
# ---------------------------------------------------------

BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(BACKEND_DIR),
)


from services.context_layer import (
    detect_concepts,
    extract_job_title,
    resolve_question,
)


# ---------------------------------------------------------
# TEST 1: EMPLOYEE AND DEPARTMENT ALIASES
# ---------------------------------------------------------

question_1 = (
    "Show emp count by dept"
)

concepts_1 = detect_concepts(
    question_1
)

print("\nTEST 1")
print("Question:", question_1)
print("Concepts:", concepts_1)

assert "employee" in concepts_1

assert "department" in concepts_1


# ---------------------------------------------------------
# TEST 2: LOWEST SALARY
# ---------------------------------------------------------

question_2 = (
    "Who has the lowest salary?"
)

resolution_2 = resolve_question(
    question_2
)

print("\nTEST 2")
print("Question:", question_2)
print(
    "Resolution:",
    resolution_2.to_dict(),
)

assert (
    resolution_2.route
    == "priority_sql"
)

assert (
    resolution_2.action
    == "salary_superlative"
)

assert (
    resolution_2.parameters[
        "direction"
    ]
    == "ASC"
)

assert (
    resolution_2.parameters[
        "result_limit"
    ]
    == 1
)


# ---------------------------------------------------------
# TEST 3: HIGHEST PAY
# ---------------------------------------------------------

question_3 = (
    "Find the employee with the highest pay"
)

resolution_3 = resolve_question(
    question_3
)

print("\nTEST 3")
print("Question:", question_3)
print(
    "Resolution:",
    resolution_3.to_dict(),
)

assert (
    resolution_3.route
    == "priority_sql"
)

assert (
    resolution_3.parameters[
        "direction"
    ]
    == "DESC"
)


# ---------------------------------------------------------
# TEST 4: AI ENGINEER DESIGNATION
# ---------------------------------------------------------

question_4 = (
    "AI engineer salary"
)

resolution_4 = resolve_question(
    question_4
)

print("\nTEST 4")
print("Question:", question_4)
print(
    "Resolution:",
    resolution_4.to_dict(),
)

assert (
    resolution_4.route
    == "priority_sql"
)

assert (
    resolution_4.action
    == "salary_by_job_title"
)

assert (
    resolution_4.parameters[
        "job_title"
    ]
    == "AI Engineer"
)


# ---------------------------------------------------------
# TEST 5: PLURAL JOB TITLE
# ---------------------------------------------------------

question_5 = (
    "What is the salary of data analysts?"
)

job_title_5 = extract_job_title(
    question_5
)

print("\nTEST 5")
print("Question:", question_5)
print("Extracted title:", job_title_5)

assert (
    job_title_5
    == "Data Analyst"
)


# ---------------------------------------------------------
# TEST 6: POLICY QUESTION
# ---------------------------------------------------------

question_6 = (
    "What is the maternity leave policy?"
)

resolution_6 = resolve_question(
    question_6
)

print("\nTEST 6")
print("Question:", question_6)
print(
    "Resolution:",
    resolution_6.to_dict(),
)

# This should continue to the existing orchestrator.
assert resolution_6.route is None

assert resolution_6.action is None


# ---------------------------------------------------------
# FINAL SUCCESS MESSAGE
# ---------------------------------------------------------

print(
    "\nAll context-layer tests passed successfully."
)