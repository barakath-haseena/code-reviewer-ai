import os
import subprocess
import tempfile
from dotenv import load_dotenv
from typing import List, Dict, Any
import traceback

load_dotenv()

# Attempt optional imports and record availability
_have_black = True
_have_radon = True
try:
    import black
except Exception:
    _have_black = False

try:
    from radon.complexity import cc_visit
except Exception:
    _have_radon = False


class AIReviewer:
    def review_code(self, code: str) -> str:
        # Placeholder stub. Replace with actual API integration (OpenAI/LLM) as needed.
        return (
            "⚠️ AI Reviewer could not complete the review. "
            "This may be due to free-tier quota limits or rate limits. "
            "Rule-based feedback is still available."
        )


def run_flake8(code: str) -> str:
    """
    Run flake8 on a temporary file and return a readable string.
    If flake8 is not installed or fails, return a helpful fallback message.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8") as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        # Try running flake8; catch FileNotFoundError if flake8 isn't installed.
        result = subprocess.run(
            ["flake8", tmp_path, "--ignore=E501"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        return "⚠️ flake8 not found on the system. Install flake8 to enable style checks."
    except Exception as e:
        return f"⚠️ flake8 execution failed: {str(e)}"

    try:
        raw_output = result.stdout.strip()
        if not raw_output:
            return "✅ No style issues found."

        formatted_lines = []
        for line in raw_output.splitlines():
            # flake8 lines typically: path:line:col: code message
            parts = line.rsplit(":", 3)
            if len(parts) == 4:
                _, lineno, colno, msg = parts
                formatted_lines.append(f"- Line {lineno.strip()}, Col {colno.strip()}: {msg.strip()}")
            else:
                formatted_lines.append(line)
        return "Flake8 Issues:\n" + "\n".join(formatted_lines)
    finally:
        # Clean up temp file
        try:
            os.remove(tmp_path)
        except Exception:
            pass


class RuleBasedReviewer:
    def review_code(self, code: str) -> List[str]:
        feedback: List[str] = []
        lines = code.splitlines()
        for i, line in enumerate(lines, start=1):
            if "TODO" in line:
                feedback.append(f"⚠️ Line {i}: Found TODO comment. Consider resolving it.")
            if "print(" in line:
                feedback.append(f"⚠️ Line {i}: Avoid using print statements; use logging instead.")
            if ";" in line:
                feedback.append(f"⚠️ Line {i}: Contains semicolon (multiple statements on one line).")
            if len(line) > 99:
                feedback.append(f"⚠️ Line {i}: Too long ({len(line)} chars). Consider wrapping.")
        if 'if __name__ == "__main__"' not in code:
            feedback.append("⚠️ Missing `if __name__ == \"__main__\":` guard (only required for scripts).")
        # simple heuristic for hardcoded passwords: look for assignment to a name containing 'pass'
        if "password" in code.lower() or "passwd" in code.lower():
            feedback.append("⚠️ Hardcoded credential-like string found. Use environment variables or secure vaults.")
        return feedback


class FormatterReviewer:
    def format_code(self, code: str) -> Dict[str, str]:
        if not _have_black:
            return {"original": code, "formatted": code, "error": "⚠️ black not installed; skipping autoformat."}
        try:
            formatted = black.format_str(code, mode=black.FileMode(line_length=88))
            return {"original": code, "formatted": formatted}
        except black.NothingChanged:
            return {"original": code, "formatted": code}
        except Exception as e:
            return {"original": code, "formatted": code, "error": f"⚠️ Black could not format: {str(e)}"}


class StyleComplexityReviewer:
    def analyze_complexity(self, code: str) -> List[str]:
        if not _have_radon:
            return ["⚠️ radon not installed; complexity analysis unavailable."]
        try:
            results = cc_visit(code)
            feedback: List[str] = []
            for func in results:
                if getattr(func, "complexity", 0) > 10:
                    feedback.append(
                        f"⚠️ Function `{func.name}` has high complexity ({func.complexity}). Consider refactoring."
                    )
                elif getattr(func, "complexity", 0) > 5:
                    feedback.append(f"⚠️ Function `{func.name}` complexity is moderate ({func.complexity}).")
            return feedback
        except Exception as e:
            return [f"⚠️ Complexity analysis failed: {str(e)}"]


class FullReviewer:
    def __init__(self):
        self.ai = AIReviewer()
        self.rule = RuleBasedReviewer()
        self.sc = StyleComplexityReviewer()
        self.formatter = FormatterReviewer()

    def review_code(self, code: str, code_file_path: str = None) -> Dict[str, Any]:
        ai_feedback = self.ai.review_code(code)
        rule_feedback = self.rule.review_code(code)
        complexity_feedback = self.sc.analyze_complexity(code)
        flake8_feedback = run_flake8(code)
        formatting_result = self.formatter.format_code(code)

        return {
            "ai_feedback": ai_feedback,
            "rule_feedback": rule_feedback,
            "complexity_feedback": complexity_feedback,
            "flake8_feedback": flake8_feedback,
            "formatted_code": formatting_result,
        }

    def safe_review_code(self, code: str, file_path: str = None) -> Dict[str, Any]:
        """
        Safe wrapper that catches unexpected exceptions from any sub-reviews and returns
        a structured fallback so the web app doesn't crash.
        """
        try:
            return self.review_code(code, file_path)
        except Exception as e:
            print("💥 Reviewer Error:", str(e))
            traceback.print_exc()
            return {
                "ai_feedback": "⚠️ AI Reviewer could not complete the review.",
                "rule_feedback": ["⚠️ Rule-based checks unavailable due to error."],
                "complexity_feedback": ["⚠️ Complexity analysis failed."],
                "flake8_feedback": "⚠️ Style check failed.",
                "formatted_code": {"original": code, "formatted": code},
            }
