from __future__ import annotations

import json

from typing import Any

from dataclasses import dataclass, asdict

# TODO use Pydantic for the tool schema
TOOL_SCHEMA = {
    "name": "add_review_to_work_item",
    "description": "Adds review to test case after the review is done and condensed report is ready",
    "parameters": {
        "type": "object",
        "required": ["text", "work_item_id"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Text of the review",
            },
            "work_item_id": {
                "type": "string",
                "description": "UUID of the test case to comment",
            },
            "overwrite": {
                "type": "boolean",
                "description": "Overwrite existing review",
            },
        },
    },
}




SOP = """
SOP: add_review_to_work_item

1. Use add_review_to_work_item tool when the test case review is finished and report is ready.
2. Required input: text, work_item_id.
3. Validate that text is present and is a non-empty string.
4. Validate that work_item_id is present and is a valid UUID formatted string.
5. If no test case is found by work_item_id, return NOT_FOUND.
6. If the test case already has a review and overwrite=False, return CONFLICT.
7. On validation_error, write log with detailed description.
8. On timeout error, retry once then escalate to a human operator.
9. Safety: DO NOT CREATE TEST CASES WITH MISSING work_item_id.
10. Safety: NEVER USE overwrite=True WITHOUT HUMAN OPERATOR CONFIRMATION.
"""


@dataclass
class TestCaseComment:
    work_item_id: str
    text: str


TEST_CASES: dict[str, TestCaseComment] = {
    "3fa85f64-5717-4562-b3fc-2c963f66afa6": TestCaseComment(
        work_item_id="3fa85f64-5717-4562-b3fc-2c963f66afa6", text=""
    ),
    "5fa85f64-5717-4562-b3fc-2c963f66afa6": TestCaseComment(
        work_item_id="5fa85f64-5717-4562-b3fc-2c963f66afa6",
        text="The case violates the company rules for test cases. Expected results is missing",
    ),
}


# TODO Use Pydantic as a schema validator
def validate(schema: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    parameters = schema["parameters"]

    for field in parameters.get("required", []):
        if field not in args:
            return {
                "status": "ERROR",
                "error_type": "validation_error",
                "message": f"Missing required field: {field}",
            }

    allowed = set(parameters.get("properties", {}).keys())
    
    extra = set(args.keys()) - allowed
    if extra:
        return {
            "status": "ERROR",
            "error_type": "validation_error",
            "message": f"Unexpected fields: {sorted(extra)}",
        }

    for field, value in args.items():
        expected_type = parameters["properties"][field]["type"]
        if expected_type == "string" and not isinstance(value, str):
            return {
                "status": "ERROR",
                "error_type": "validation_error",
                "message": f"{field} must be a string",
            }

    return {"status": "OK"}


def add_review_to_work_item(
    text: str, work_item_id: str, overwrite: bool = False
) -> dict[str, Any]:

    normalized_id = work_item_id.lower()

    test_case = TEST_CASES.get(normalized_id)

    if not test_case:
        return {
            "status": "NOT_FOUND",
            "work_item_id": work_item_id,
            "message": "No test case was found",
        }

    if not test_case.text:
        test_case.text = text
        return {
            "status": "SUCCESS",
            "work_item_id": work_item_id,
            "message": "Review has been added to the test case",
        }

    if not overwrite:
        return {
            "status": "CONFLICT",
            "work_item_id": work_item_id,
            "message": "Test case already has a review attached",
        }

    test_case.text = text
    return {
        "status": "CHANGED",
        "work_item_id": work_item_id,
        "message": "Review has been changed",
    }


def fake_llm(user_request: str) -> dict[str, Any]:
    """В образовательных целях если нет доступа к LLM: возвращает вызов инструмента. Синтаксис response может отличаться у разных моделей"""
    if "Add review to TC" in user_request and "3fa85f64-5717-4562-b3fc-2c963f66afa6" in user_request:
        return {
            "type": "tool_call",
            "tool": "add_review_to_work_item",
            "arguments": {
                "work_item_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "text": "This is a new review",
                "overwrite": False,
            },
        }
    if "Update review to TC" in user_request and "5fa85f64-5717-4562-b3fc-2c963f66afa6" in user_request:
        return {
            "type": "tool_call",
            "tool": "add_review_to_work_item",
            "arguments": {
                "work_item_id": "5fa85f64-5717-4562-b3fc-2c963f66afa6",
                "text": "This is an updated review",
                "overwrite": True
                }
        }
    if "Get review from TC" in user_request and "6fa85f64-5717-4562-b3fc-2c963f66afa6" in user_request:
        return {
            "type": "tool_call",
            "tool": "get_review_from_work_item",
            "arguments": {
                "work_item_id": "6fa85f64-5717-4562-b3fc-2c963f66afa6",
            },
        }
    
    return {
            "type": "fallback",
            "suggestion": "Please provide more specific information."
        }

def run_agent(user_request: str) -> dict[str, Any]:
    decision = fake_llm(user_request)
    if decision.get("type") != "tool_call":
        return {
            "status": "ERROR",
            "error_type": "invalid_llm_output",
            "message": "Expected a tool_call decision.",
        }

    if decision.get("tool") != TOOL_SCHEMA["name"]:
        return {
            "status": "ERROR",
            "error_type": "unknown_tool",
            "message": f"Unknown tool: {decision.get('tool')}",
        }

    args = decision.get("arguments", {})
    validation = validate(TOOL_SCHEMA, args)
    if validation["status"] != "OK":
        return validation

    try:
        tool_result = add_review_to_work_item(**args)
    except Exception as exc:
        return {
            "status": "ERROR",
            "error_type": "tool_error",
            "message": str(exc),
        }

    return {
        "status": "OK",
        "tool_call": decision,
        "tool_result": tool_result,
        "sop": SOP.strip(),
    }


if __name__ == "__main__":
    print("\nCASE: Add a new review to TC with workritem id 3fa85f64-5717-4562-b3fc-2c963f66afa6")
    result = run_agent("Add review to TC with workritem id 3fa85f64-5717-4562-b3fc-2c963f66afa6")
    print(json.dumps(result, indent=4))
    print("\nTest cases dumps")
    print(json.dumps(asdict(TEST_CASES["3fa85f64-5717-4562-b3fc-2c963f66afa6"]), indent=4))
    

    print("\nCASE: Update a review to TC with workritem id 5fa85f64-5717-4562-b3fc-2c963f66afa6")
    result = run_agent("Update review to TC with workritem id 5fa85f64-5717-4562-b3fc-2c963f66afa6")
    print(json.dumps(result, indent=4))
    print("\nTest cases dumps")
    print(json.dumps(asdict(TEST_CASES["5fa85f64-5717-4562-b3fc-2c963f66afa6"]), indent=4))


    print("\nCASE: Unknown tool call")
    result = run_agent("Get review from TC with workritem id 6fa85f64-5717-4562-b3fc-2c963f66afa6")
    print(json.dumps(result, indent=4))
    print("\nTest cases dumps")
    print(json.dumps(asdict(TEST_CASES["3fa85f64-5717-4562-b3fc-2c963f66afa6"]), indent=4))
    print(json.dumps(asdict(TEST_CASES["5fa85f64-5717-4562-b3fc-2c963f66afa6"]), indent=4))
