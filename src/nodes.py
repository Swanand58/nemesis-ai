import json
import os
import pathlib
import subprocess

import jsonpatch
import yaml
from groq import Groq
from pocketflow import Node


class LoadSpec(Node):
    def prep(self, shared):
        """Extract path from shared state (when called with flow.run(path))"""
        # When flow.run(path) is called, the path becomes the shared state
        if isinstance(shared, str):
            return shared
        elif isinstance(shared, dict) and "spec_path" in shared:
            return shared["spec_path"]
        else:
            raise ValueError(
                f"Expected string path or dict with 'spec_path', got: {shared}"
            )

    def exec(self, path: str):
        """Load OpenAPI spec from file path or FastAPI project directory"""
        target_path = pathlib.Path(path)

        # Case 1: Direct OpenAPI file (YAML/JSON)
        if target_path.is_file() and target_path.suffix in [".yaml", ".yml", ".json"]:
            print(f"📄 Loading spec from file: {path}")
            return target_path.read_text(), "file", str(target_path)

        # Case 2: FastAPI project directory
        elif target_path.is_dir():
            result = self._load_from_fastapi_project(target_path)
            return result, "fastapi", str(target_path)

        else:
            raise FileNotFoundError(f"Path not found or unsupported: {path}")

    def post(self, shared, prep_result, exec_result):
        """Store metadata in shared state"""
        spec_text, source_type, source_path = exec_result

        # Convert shared to dict if it's not already
        if not isinstance(shared, dict):
            shared = {}

        shared["spec_text"] = spec_text
        shared["source_type"] = source_type
        shared["source_path"] = source_path

        if source_type == "fastapi":
            # Store additional FastAPI metadata if available
            if hasattr(self, "_fastapi_metadata"):
                shared.update(self._fastapi_metadata)

    def _load_from_fastapi_project(self, project_dir: pathlib.Path):
        """Load OpenAPI spec from openapi.json file in FastAPI project directory"""
        print(f"🚀 Loading FastAPI project from: {project_dir}")

        # Look for openapi.json file
        openapi_file = project_dir / "openapi.json"

        if not openapi_file.exists():
            raise FileNotFoundError(
                f"No openapi.json file found in {project_dir}.\n"
                f"Please generate and save your OpenAPI spec as 'openapi.json' in the project directory.\n"
                f"You can generate it by running your FastAPI app and visiting /openapi.json endpoint."
            )

        print(f"📄 Found OpenAPI spec file: {openapi_file}")

        try:
            # Read and parse the OpenAPI JSON file
            openapi_content = openapi_file.read_text()
            openapi_spec = json.loads(openapi_content)

            print("📊 OpenAPI spec info:")
            print(f"   Title: {openapi_spec.get('info', {}).get('title', 'N/A')}")
            print(f"   Version: {openapi_spec.get('info', {}).get('version', 'N/A')}")
            print(f"   Paths: {len(openapi_spec.get('paths', {}))}")
            print(f"   File size: {len(openapi_content)} characters")

            # Store metadata for later use in post method
            self._fastapi_metadata = {
                "fastapi_project_dir": str(project_dir),
                "openapi_file": str(openapi_file),
            }

            # Convert to YAML string for consistency with the rest of the pipeline
            yaml_spec = yaml.safe_dump(
                openapi_spec, sort_keys=False, default_flow_style=False
            )
            print(f"📝 Converted to YAML ({len(yaml_spec)} characters)")
            return yaml_spec

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {openapi_file}: {e}")
        except Exception as e:
            raise RuntimeError(f"Error reading {openapi_file}: {e}")


class Audit42C(Node):
    def exec(self, load_result):
        """Run 42crunch security audit on OpenAPI spec"""
        # Handle the new tuple format from LoadSpec
        if isinstance(load_result, tuple):
            spec_text = load_result[0]  # Extract just the spec text
        else:
            spec_text = load_result  # Fallback for backward compatibility

        print("🔍 Running 42crunch security audit...")

        # Check if 42c-audit CLI is available locally first
        import shutil

        if shutil.which("42c-audit"):
            print("🔧 Using local 42c-audit CLI")
            return self._run_local_audit(spec_text)

        # Check if Docker is available
        if not shutil.which("docker"):
            print("⚠️  Docker not found - using mock audit mode")
            return self._mock_audit_report(), spec_text

        print("🐳 Using Docker-based 42crunch audit")
        return self._run_docker_audit(spec_text)

    def _run_local_audit(self, spec_text):
        """Run audit using local 42c-audit CLI"""
        try:
            p = subprocess.run(
                ["42c-audit", "--output", "json", "-"],
                input=spec_text,
                text=True,
                capture_output=True,
                env={**os.environ, "C42_TOKEN": os.getenv("C42_TOKEN")},
            )
            if p.returncode != 0:
                print(f"❌ 42c-audit stderr: {p.stderr}")
                print("⚠️  Falling back to mock audit mode")
                return self._mock_audit_report(), spec_text

            report = json.loads(p.stdout)
            score = report.get("score", 0)
            findings_count = len(report.get("findings", []))

            print(f"📊 Audit Score: {score}/100")
            print(f"🔍 Found {findings_count} security issues")

            return report, spec_text
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            json.JSONDecodeError,
        ) as e:
            print(f"❌ Local audit failed: {e}")
            print("⚠️  Falling back to mock audit mode")
            return self._mock_audit_report(), spec_text

    def _run_docker_audit(self, spec_text):
        """Run audit using 42crunch Docker image"""
        try:
            # Use the official 42crunch audit Docker image
            docker_image = "42crunch/docker-api-security-audit:v4"

            print(f"🐳 Pulling Docker image: {docker_image}")

            # Pull the image first (in case it's not available locally)
            pull_cmd = ["docker", "pull", docker_image]
            pull_result = subprocess.run(pull_cmd, capture_output=True, text=True)

            if pull_result.returncode != 0:
                print(f"⚠️  Failed to pull Docker image: {pull_result.stderr}")
                print("⚠️  Falling back to mock audit mode")
                return self._mock_audit_report(), spec_text

            print("🔍 Running 42crunch audit via Docker...")

            # Run the audit via Docker
            # The 42crunch image expects the API token as environment variable
            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/amd64",  # Force x86_64 emulation on ARM64
                "-v",
                f"{os.getcwd()}:/workspace",  # Mount current directory
                "-e",
                f"X42C_API_TOKEN={os.getenv('C42_TOKEN', '')}",
                "-e",
                "X42C_REPOSITORY_URL=https://github.com/local/repo",
                "-e",
                "X42C_BRANCH_NAME=main",
                "-e",
                "X42C_PLATFORM_URL=https://platform.42crunch.com",
                docker_image,
            ]

            audit_result = subprocess.run(docker_cmd, text=True, capture_output=True)

            if audit_result.returncode != 0:
                print(
                    f"❌ Docker audit failed with return code: {audit_result.returncode}"
                )
                print(f"❌ Docker stderr: {audit_result.stderr}")
                print(f"❌ Docker stdout: {audit_result.stdout}")
                print(f"❌ Docker command was: {' '.join(docker_cmd)}")
                print("⚠️  Falling back to mock audit mode")
                return self._mock_audit_report(), spec_text

            try:
                report = json.loads(audit_result.stdout)
                score = report.get("score", 0)
                findings_count = len(report.get("findings", []))

                print(f"📊 Audit Score: {score}/100")
                print(f"🔍 Found {findings_count} security issues")

                return report, spec_text

            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse Docker audit output: {e}")
                print(f"❌ Raw output: {audit_result.stdout[:200]}...")
                print("⚠️  Falling back to mock audit mode")
                return self._mock_audit_report(), spec_text

        except Exception as e:
            print(f"❌ Docker audit failed with error: {e}")
            print("⚠️  Falling back to mock audit mode")
            return self._mock_audit_report(), spec_text

    def _mock_audit_report(self):
        """Generate a mock audit report for testing when CLI is not available"""
        print("🎭 Generating mock security audit (score: 65/100)")
        return {
            "score": 65,
            "findings": [
                {
                    "title": "Missing security schemes",
                    "description": "API does not define any security schemes",
                    "severity": 5,
                    "pointer": "/security",
                },
                {
                    "title": "Missing parameter validation",
                    "description": "Parameters lack proper validation constraints",
                    "severity": 4,
                    "pointer": "/paths",
                },
                {
                    "title": "Insufficient error responses",
                    "description": "API endpoints missing proper error response definitions",
                    "severity": 3,
                    "pointer": "/paths",
                },
            ],
        }

    def post(self, shared, _, out):
        # out should be a tuple (report, spec_text)
        if isinstance(out, tuple) and len(out) == 2:
            shared["report"] = out[0]
            shared["spec_text"] = out[1]
        else:
            # Fallback - this shouldn't happen but just in case
            shared["report"] = out
            print(
                "⚠️  Warning: Expected tuple (report, spec_text) but got different format"
            )


class LLM_PlanPatch(Node):
    def prep(self, shared):
        report = shared["report"]
        spec_text = shared["spec_text"]
        return report, spec_text

    def exec(self, inputs):
        report, spec_text = inputs
        min_score = int(os.getenv("MIN_SCORE", 90))

        current_score = report.get("score", 0)
        if current_score >= min_score:
            print(f"✅ Score {current_score} meets minimum {min_score} - Done!")
            return "done", []

        # Get top 3 most critical findings
        findings = report.get("findings", [])
        if not findings:
            print("❌ No findings to fix but score is low")
            return "done", []

        top_findings = sorted(findings, key=lambda f: -f.get("severity", 0))[:3]

        print(f"🔧 Planning fixes for {len(top_findings)} critical issues...")
        for i, finding in enumerate(top_findings, 1):
            print(
                f"  {i}. {finding.get('title', 'Unknown issue')} (severity: {finding.get('severity', 0)})"
            )

        # Use Groq instead of OpenAI
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")

        client = Groq(api_key=groq_api_key)

        # Create a focused prompt for the LLM
        issues_summary = []
        for finding in top_findings:
            issues_summary.append(
                {
                    "title": finding.get("title", ""),
                    "description": finding.get("description", ""),
                    "severity": finding.get("severity", 0),
                    "pointer": finding.get("pointer", ""),
                }
            )

        prompt = f"""You are an OpenAPI security expert. Fix the security issues in this OpenAPI specification.

CURRENT OPENAPI SPEC:
```yaml
{spec_text}
```

SECURITY ISSUES TO FIX:
{json.dumps(issues_summary, indent=2)}

Generate a JSON Patch (RFC 6902) to fix these security issues. Common fixes include:
- Adding security schemes (Bearer tokens, API keys)
- Adding parameter validation (type, format, maxLength, etc.)
- Adding proper response schemas
- Adding rate limiting info
- Fixing missing error responses

Return ONLY a valid JSON Patch array, no explanations:
[
  {{"op": "add", "path": "/security", "value": [{{"bearerAuth": []}}]}},
  {{"op": "add", "path": "/components/securitySchemes", "value": {{"bearerAuth": {{"type": "http", "scheme": "bearer"}}}}}}
]"""

        try:
            print("🤖 Asking LLM to generate security fixes...")
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an OpenAPI security expert. Return only valid JSON Patch operations, no explanations.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
            )

            patch_text = response.choices[0].message.content.strip()

            # Clean up the response - extract JSON from markdown if needed
            if "```json" in patch_text:
                patch_text = patch_text.split("```json")[1].split("```")[0].strip()
            elif "```" in patch_text:
                patch_text = patch_text.split("```")[1].split("```")[0].strip()

            # Remove any leading/trailing text that isn't JSON
            lines = patch_text.split("\n")
            start_idx = 0
            end_idx = len(lines)

            for i, line in enumerate(lines):
                if line.strip().startswith("["):
                    start_idx = i
                    break

            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip().endswith("]"):
                    end_idx = i + 1
                    break

            clean_patch = "\n".join(lines[start_idx:end_idx])

            patch_ops = json.loads(clean_patch)
            print(f"🚀 Generated {len(patch_ops)} patch operations")

            # Debug: Check the action being returned
            action = "patch"
            print(
                f"🔧 Debug: LLM_PlanPatch returning action: '{action}' with {len(patch_ops)} operations"
            )
            return action, patch_ops

        except json.JSONDecodeError as e:
            print(f"❌ LLM returned invalid JSON: {patch_text}")
            print(f"JSON Error: {e}")
            return "done", []  # Give up on this iteration
        except Exception as e:
            print(f"❌ LLM request failed: {e}")
            return "done", []

    def post(self, shared, prep_result, exec_result):
        """Handle action routing for PocketFlow"""
        print(f"🔧 Debug: LLM_PlanPatch.post called with exec_result: {exec_result}")
        action_type, patch_ops = exec_result
        print(f"🔧 Debug: LLM_PlanPatch.post returning action: '{action_type}'")
        return action_type


class WritePatch(Node):
    def prep(self, shared):
        """Get data from shared state"""
        print("🔧 Debug: WritePatch.prep called")
        spec_text = shared.get("spec_text")
        if not spec_text:
            raise ValueError("No spec_text found in shared state")
        return spec_text, shared

    def exec(self, inputs):
        """Apply the JSON patch to the OpenAPI spec"""
        print(f"🔧 Debug: WritePatch.exec called with inputs: {type(inputs)}")
        action_type, patch_ops = inputs

        if action_type == "done":
            print("✅ No patches needed - target score achieved!")
            return "done"

        if not patch_ops:
            print("❌ No patch operations to apply")
            return "no_changes"

        # Return both action_type and patch_ops for processing in post()
        print(
            f"🔧 Debug: WritePatch.exec returning {action_type} with {len(patch_ops)} operations"
        )
        return action_type, patch_ops

    def post(self, shared, prep_result, exec_result):
        """Apply patches and save results"""
        spec_text, shared_state = prep_result

        # Handle different return types from exec
        if exec_result in ["done", "no_changes"]:
            return exec_result

        # Unpack the tuple from exec
        action_type, patch_ops = exec_result

        try:
            print(f"✏️  Applying {len(patch_ops)} patch operations...")

            # Parse spec (handle both JSON and YAML)
            if spec_text.strip().startswith("{"):
                spec_json = json.loads(spec_text)
                is_yaml = False
            else:
                spec_json = yaml.safe_load(spec_text)
                is_yaml = True

            # Apply patch
            new_json = jsonpatch.apply_patch(spec_json, patch_ops)

            # Write back in original format
            if is_yaml:
                new_text = yaml.safe_dump(
                    new_json, sort_keys=False, default_flow_style=False
                )
            else:
                new_text = json.dumps(new_json, indent=2)

            # Update shared state with new spec text
            shared["spec_text"] = new_text

            # Debug: Check what's in shared_state
            print(f"🔧 Debug: shared_state keys: {list(shared_state.keys())}")
            print(
                f"🔧 Debug: 'fastapi_project_dir' in shared_state: {'fastapi_project_dir' in shared_state}"
            )

            # Determine where to save the improved spec
            if "fastapi_project_dir" in shared_state:
                # For FastAPI projects, save the improved spec
                print("🔧 Debug: Saving FastAPI improvements...")
                self._save_fastapi_improvements(new_json, new_text, shared_state)
            else:
                # For direct spec files, update the original file
                print("🔧 Debug: Saving spec file...")
                self._save_spec_file(new_text)

            print("🔄 Patches applied successfully - re-auditing...")
            # Return action indicating completion for this iteration
            return "complete"

        except Exception as e:
            print(f"❌ Patch application failed: {e}")
            raise

    def _save_fastapi_improvements(
        self, improved_spec: dict, spec_text: str, shared_state: dict
    ):
        """Save improvements for FastAPI projects"""
        project_dir = pathlib.Path(shared_state["fastapi_project_dir"])

        # Save the improved OpenAPI spec
        improved_spec_file = project_dir / "openapi_improved.yaml"
        improved_spec_file.write_text(spec_text)
        print(f"✅ Saved improved OpenAPI spec: {improved_spec_file}")

        # Generate code suggestions
        suggestions_file = project_dir / "security_improvements.md"
        suggestions = self._generate_code_suggestions(improved_spec)
        suggestions_file.write_text(suggestions)
        print(f"📋 Generated improvement suggestions: {suggestions_file}")

    def _save_spec_file(self, new_text: str):
        """Save improved spec for direct spec files"""
        spec_path = pathlib.Path(os.getenv("SPEC_PATH"))
        backup_path = spec_path.with_suffix(f"{spec_path.suffix}.backup")

        if backup_path.exists():
            backup_path.unlink()  # Remove old backup

        spec_path.rename(backup_path)
        spec_path.write_text(new_text)

        print(f"✅ Applied patch to {spec_path}")
        print(f"📁 Backup saved as {backup_path}")

    def _generate_code_suggestions(self, improved_spec: dict):
        """Generate FastAPI code improvement suggestions"""
        suggestions = """# FastAPI Security Improvements

Based on the OpenAPI audit, here are suggested improvements for your FastAPI application:

## 🔐 Security Enhancements Applied

"""

        # Check for security schemes
        if "security" in improved_spec:
            suggestions += """
### 1. Authentication/Authorization
The improved spec includes security schemes. Consider implementing:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    # Add your token verification logic here
    if not verify_jwt_token(token):  # Implement this function
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token

# Apply to your endpoints:
@app.get("/protected-endpoint", dependencies=[Depends(verify_token)])
async def protected_route():
    return {"message": "This is protected"}
```
"""

        # Check for parameter validation improvements
        if "components" in improved_spec and "schemas" in improved_spec["components"]:
            suggestions += """
### 2. Input Validation
Enhanced parameter validation has been added. Update your Pydantic models:

```python
from pydantic import BaseModel, Field, validator
from typing import Optional

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_]+$")
    email: str = Field(..., regex=r'^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$')
    age: Optional[int] = Field(None, ge=0, le=120)
    
    @validator('username')
    def username_alphanumeric(cls, v):
        assert v.isalnum(), 'Username must be alphanumeric'
        return v
```
"""

        # Rate limiting suggestions
        suggestions += """
### 3. Rate Limiting
Consider adding rate limiting to your endpoints:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/users")
@limiter.limit("10/minute")
async def get_users(request: Request):
    return {"users": []}
```
"""

        # CORS and security headers
        suggestions += """
### 4. Security Headers & CORS
Add security middleware:

```python
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific origins only
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Limit methods
    allow_headers=["*"],
)

# Trusted hosts
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["yourdomain.com", "*.yourdomain.com"])

# Security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```
"""

        suggestions += """
## 🔄 Next Steps

1. Review the improved OpenAPI spec in `openapi_improved.yaml`
2. Implement the security enhancements above
3. Test your API with the new security measures
4. Run the audit again to verify improvements

## 📚 Additional Resources

- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [42Crunch Security Guidelines](https://docs.42crunch.com/latest/openapi-security/)
"""

        return suggestions
