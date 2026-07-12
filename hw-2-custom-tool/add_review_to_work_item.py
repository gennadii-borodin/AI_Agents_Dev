from __future__ import annotations

from typing import Any

from dataclasses import dataclass

# TODO use Pydantic for the tool schema
TOOL_SCHEMA = {
    "name": "add_review_to_work_item",
    "description": "Adds review to test case after the review is done and condensed report is ready",
    "parameters": {
        "type": "object",
        "required": ["text", "workItemId"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Text of the review",
            },
            "workItemId": {
                "type": "string",
                "description": "UUID of the test case to comment",
            },
        },
        "additionalProperties": False
    },
}

SOP = """

SOP: add_review_to_work_item

1. Use comment_work_item tool when the test case review is finished and report is ready.
2. Required input: email, workItemId.
3. Validate that text is present and is a string.
4. Validate that workItemId is present and is an UUID fromatted string
5. If no test cases is found by workItemId return NOT_FOUND
6. If the test case alerady has a comment and the CONFLICT error is returned ask the human operator to confirm action. 
7. On validation_error, write log with detailed description
8. On time out error, retry once then escalate to a human operator.
9. Safety: DO NOT CREATE TEST CASES WITH MISSED workItemIds
10. Safety: NEVER USE overwrite = True WITHOUT HUMAN OPERATOR CONFIRMATION

"""

@dataclass
class TestCaseComment:
    work_item_id: str
    text: str

TEST_CASES = {
    TestCaseComment(work_item_id="3fa85f64-5717-4562-b3fc-2c963f66afa6", text=""),
    TestCaseComment(work_item_id="5fa85f64-5717-4562-b3fc-2c963f66afa6", text="The case violates the company rules for test casees. Expeceted results is missing")
}

# TODO Use Pydantic as a shcema validator
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


def add_review_to_work_item(text: str, work_item_id: str, overwrite: bool = False) -> dict[str, Any]:

    normalized_id = work_item_id.lower()

    test_case = TEST_CASES.get(normalized_id)
        
    if not test_case:
        return {
            "status": "NOT_FOUND",
            "work_item_id": work_item_id,
            "message": f"No test cases was found",
        }
    
    if not test_case.text:
        test_case.text = text
        return {
            "status": "SUCCESS",
            "work_item_id": work_item_id,
            "message": f"Review has been added to the test case",
        }    
    
    if not overwrite:
        return {
            "status": "CONFLICT",
            "work_item_id": work_item_id,
            "message": f"Test case already has a review attached",
        }    
    
    test_case.text = text
    return {
        "status": "CHANGED",
        "work_item_id": work_item_id,
        "message": f"Review has been changed",
    }
        


def fake_llm(user_request: str) -> dict[str, Any]:
    """В образовательных целях если нет доступа к LLM: возвращает вызов инструмента. Синтаксис response может отличаться у разных моделей"""
    email = "anna@example.com" if "anna" in user_request.lower() else "missing@example.com"
    return {
        "type": "tool_call",
        "tool": "find_customer_by_email",
        "arguments": {
            "email": email,
        },
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
    result = run_agent("Add review to TC with workritem id 3fa85f64-5717-4562-b3fc-2c963f66afa6")
    print(result)
