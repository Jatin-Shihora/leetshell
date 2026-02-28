from dataclasses import dataclass, field

from leetshell.constants import STATUS_MESSAGES


@dataclass
class TestCaseResult:
    input_data: str = ""
    expected: str = ""
    actual: str = ""
    passed: bool = False

    def to_dict(self) -> dict:
        return {
            "input_data": self.input_data,
            "expected": self.expected,
            "actual": self.actual,
            "passed": self.passed,
        }


@dataclass
class TestResult:
    run_success: bool = False
    status_code: int = 0
    status_msg: str = ""
    total_correct: int = 0
    total_testcases: int = 0
    runtime: str = ""
    memory: str = ""
    test_cases: list[TestCaseResult] = field(default_factory=list)
    compile_error: str = ""
    runtime_error: str = ""
    code_output: list[str] = field(default_factory=list)
    expected_output: list[str] = field(default_factory=list)
    std_output_list: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict, input_data: str = "") -> "TestResult":
        code_output = data.get("code_output", []) or []
        expected_output = data.get("expected_code_answer", []) or []
        std_output_list = data.get("std_output_list", []) or []

        inputs = input_data.split("\n\n") if input_data else []
        # Build test case results
        test_cases = []
        for i in range(max(len(code_output), len(expected_output))):
            actual = code_output[i] if i < len(code_output) else ""
            expected = expected_output[i] if i < len(expected_output) else ""
            inp = inputs[i] if i < len(inputs) else ""
            test_cases.append(TestCaseResult(
                input_data=inp,
                expected=expected,
                actual=actual,
                passed=actual == expected,
            ))

        return cls(
            run_success=data.get("run_success", False),
            status_code=data.get("status_code", 0),
            status_msg=data.get("status_msg", ""),
            total_correct=data.get("total_correct", 0),
            total_testcases=data.get("total_testcases", 0),
            runtime=data.get("status_runtime", ""),
            memory=data.get("status_memory", ""),
            test_cases=test_cases,
            compile_error=data.get("full_compile_error", data.get("compile_error", "")),
            runtime_error=data.get("full_runtime_error", data.get("runtime_error", "")),
            code_output=code_output,
            expected_output=expected_output,
            std_output_list=std_output_list,
        )


@dataclass
class SubmissionResult:
    status_code: int = 0
    status_msg: str = ""
    run_success: bool = False
    total_correct: int = 0
    total_testcases: int = 0
    runtime: str = ""
    memory: str = ""
    runtime_percentile: float = 0.0
    memory_percentile: float = 0.0
    # For wrong answer / runtime error
    input_data: str = ""
    expected_output: str = ""
    code_output: str = ""
    compile_error: str = ""
    runtime_error: str = ""

    @property
    def accepted(self) -> bool:
        return self.status_code == 10

    @property
    def display_status(self) -> str:
        return STATUS_MESSAGES.get(self.status_code, self.status_msg)

    @classmethod
    def from_api(cls, data: dict) -> "SubmissionResult":
        return cls(
            status_code=data.get("status_code", 0),
            status_msg=data.get("status_msg", ""),
            run_success=data.get("run_success", False),
            total_correct=data.get("total_correct", 0),
            total_testcases=data.get("total_testcases", 0),
            runtime=data.get("status_runtime", ""),
            memory=data.get("status_memory", ""),
            runtime_percentile=data.get("runtime_percentile", 0.0) or 0.0,
            memory_percentile=data.get("memory_percentile", 0.0) or 0.0,
            input_data=data.get("input", ""),
            expected_output=data.get("expected_output", ""),
            code_output=data.get("code_output", ""),
            compile_error=data.get("full_compile_error", data.get("compile_error", "")),
            runtime_error=data.get("full_runtime_error", data.get("runtime_error", "")),
        )
