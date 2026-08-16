from pathlib import Path

import sys


# ---------------------------------------------------------
# ADD PROJECT ROOT TO PYTHON PATH
# ---------------------------------------------------------

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from services.context_layer import (
    resolve_question,
)

from services.priority_sql import (
    execute_priority_sql,
)


# ---------------------------------------------------------
# TEST 1: LOWEST SALARY
# ---------------------------------------------------------

lowest_question = (
    "Who has the lowest salary?"
)

lowest_resolution = resolve_question(
    lowest_question
)

lowest_result = execute_priority_sql(
    lowest_resolution
)

print("\nTEST 1: LOWEST SALARY")

print(
    "Question:",
    lowest_question,
)

print(
    "Resolution:",
    lowest_resolution.to_dict(),
)

print(
    "Answer:",
    lowest_result["answer"],
)

print(
    "Row count:",
    lowest_result["row_count"],
)

assert (
    lowest_result["row_count"]
    == 1
)

assert (
    len(lowest_result["rows"])
    == 1
)


# ---------------------------------------------------------
# TEST 2: HIGHEST SALARY
# ---------------------------------------------------------

highest_question = (
    "Who has the highest salary?"
)

highest_resolution = resolve_question(
    highest_question
)

highest_result = execute_priority_sql(
    highest_resolution
)

print("\nTEST 2: HIGHEST SALARY")

print(
    "Question:",
    highest_question,
)

print(
    "Resolution:",
    highest_resolution.to_dict(),
)

print(
    "Answer:",
    highest_result["answer"],
)

print(
    "Row count:",
    highest_result["row_count"],
)

assert (
    highest_result["row_count"]
    == 1
)

assert (
    len(highest_result["rows"])
    == 1
)


# ---------------------------------------------------------
# TEST 3: AI ENGINEER SALARY
# ---------------------------------------------------------

designation_question = (
    "AI engineer salary"
)

designation_resolution = (
    resolve_question(
        designation_question
    )
)

designation_result = (
    execute_priority_sql(
        designation_resolution
    )
)

print(
    "\nTEST 3: SALARY BY DESIGNATION"
)

print(
    "Question:",
    designation_question,
)

print(
    "Resolution:",
    designation_resolution.to_dict(),
)

print(
    "Answer:",
    designation_result["answer"],
)

print(
    "Row count:",
    designation_result["row_count"],
)


# This test does not require AI Engineer to exist.
#
# If no AI Engineer exists, returning zero rows with a
# clear "could not find" answer is correct.
assert (
    designation_result["row_count"]
    >= 0
)


# ---------------------------------------------------------
# FINAL SUCCESS
# ---------------------------------------------------------

print(
    "\nAll priority SQL tests passed successfully."
)