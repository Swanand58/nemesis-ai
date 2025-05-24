# OpenAPI Security Enhancement Agent

An intelligent agent that automatically improves OpenAPI specification security using 42crunch audits and AI-powered fixes.

## 🎯 What It Does

1. **Loads OpenAPI specs** from direct files or FastAPI projects
2. **Runs 42crunch security audits** to identify vulnerabilities
3. **Uses AI** (Groq) to generate security fixes when score < target
4. **Applies patches** and re-tests until security standards are met
5. **Generates improvement guides** for FastAPI projects

## 🚀 Features

- **Direct OpenAPI Files**: Process `.yaml`, `.yml`, or `.json` specs directly
- **FastAPI Projects**: Process FastAPI projects using static `openapi.json` files
- **AI-Powered Fixes**: Uses Groq's free `llama-3.1-70b-versatile` model
- **Iterative Improvement**: Loops until target security score is achieved
- **Detailed Logging**: Shows exactly what's happening at each step
- **FastAPI Integration**: Generates code suggestions for FastAPI projects

## 📋 Prerequisites

1. **42crunch CLI**: For security auditing

   ```bash
   npm install -g @42crunch/audit-cli
   ```

2. **42crunch API Token**: Get from [42crunch.com](https://42crunch.com)

3. **Groq API Key**: Get free key from [console.groq.com](https://console.groq.com)

## 📦 Installation

```bash
git clone <your-repo>
cd openapi-security-agent
pip install -e .
```

## ⚙️ Configuration

Create a `.env` file in the project root:

```env
# Required
C42_TOKEN=your_42crunch_token_here
GROQ_API_KEY=your_groq_api_key_here

# Target OpenAPI spec (file or FastAPI project directory)
SPEC_PATH=/path/to/your/openapi.yaml
# OR for FastAPI projects:
SPEC_PATH=/path/to/your/fastapi/project

# Optional settings
MIN_SCORE=90
```

## 📁 Usage

### For Direct OpenAPI Files

Point `SPEC_PATH` to your OpenAPI file:

```env
SPEC_PATH=./my-api-spec.yaml
```

### For FastAPI Projects

1. **Generate your OpenAPI spec** and save it as `openapi.json` in your FastAPI project directory:

   **Method 1**: Start your FastAPI app and download:

   ```bash
   cd /path/to/your/fastapi/project
   uvicorn main:app --reload &
   curl http://localhost:8000/openapi.json > openapi.json
   ```

   **Method 2**: Generate programmatically:

   ```python
   from your_fastapi_app import app
   import json

   with open("openapi.json", "w") as f:
       json.dump(app.openapi(), f, indent=2)
   ```

2. **Point to your FastAPI project directory**:

   ```env
   SPEC_PATH=/path/to/your/fastapi/project
   ```

3. **Run the agent**:
   ```bash
   python main.py
   ```

## 🔄 How It Works

### Flow Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Load OpenAPI    │    │ 42crunch Audit  │    │ AI Fix          │
│ Spec            │ -> │ Security Check  │ -> │ Generation      │
│                 │    │                 │    │ (if needed)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       v
         │                       │              ┌─────────────────┐
         │                       │              │ Apply Patches   │
         │                       │              │ & Save Results  │
         │                       │              └─────────────────┘
         │                       │                       │
         │                       └───────────────────────┘
         │                            (Loop until score >= target)
         v
┌─────────────────┐
│ ✅ Done!        │
│ Security Score  │
│ Target Achieved │
└─────────────────┘
```

### For FastAPI Projects

When processing FastAPI projects, the agent:

1. **Loads** the `openapi.json` file from your project directory
2. **Audits** the security and generates fixes
3. **Saves** improved specs and implementation guides:
   - `openapi_improved.yaml` - Enhanced OpenAPI spec
   - `security_improvements.md` - FastAPI code suggestions

## 📊 Example Output

```
🚀 Starting OpenAPI Security Enhancement Agent...
📄 Found OpenAPI spec file: /path/to/project/openapi.json
📊 OpenAPI spec info:
   Title: My FastAPI App
   Version: 1.0.0
   Paths: 12
   File size: 3542 characters
📝 Converted to YAML (4123 characters)

🔍 Running 42crunch security audit...
📊 Audit Score: 68/100
🔍 Found 8 security issues

🔧 Planning fixes for 3 critical issues...
  1. Missing security scheme (severity: 5)
  2. No input validation (severity: 4)
  3. Missing error responses (severity: 3)

🤖 Asking LLM to generate security fixes...
🚀 Generated 6 patch operations

✏️  Applying 6 patch operations...
✅ Saved improved OpenAPI spec: /path/to/project/openapi_improved.yaml
📋 Generated improvement suggestions: /path/to/project/security_improvements.md

🔍 Running 42crunch security audit...
📊 Audit Score: 94/100
✅ Score 94 meets minimum 90 - Done!
```

## 🛠️ Troubleshooting

### "No openapi.json file found"

Make sure you have generated and saved your OpenAPI spec as `openapi.json` in your FastAPI project directory.

### "42c-audit command failed"

Ensure you have:

- Installed 42crunch CLI: `npm install -g @42crunch/audit-cli`
- Valid C42_TOKEN in your `.env` file

### "GROQ_API_KEY environment variable is required"

Get a free API key from [console.groq.com](https://console.groq.com) and add it to your `.env` file.

## 🏗️ Architecture

- **LoadSpec**: Loads OpenAPI specs from files or FastAPI projects
- **Audit42C**: Runs 42crunch security audits
- **LLM_PlanPatch**: Uses Groq AI to generate security fixes
- **WritePatch**: Applies patches and saves results

Built with:

- **PocketFlow**: Lightweight workflow orchestration
- **42crunch**: Industry-leading OpenAPI security analysis
- **Groq**: Fast, free LLM inference
- **JSONPatch**: Precise OpenAPI modifications

## 📚 Resources

- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [42crunch Documentation](https://docs.42crunch.com/)
- [OpenAPI Security Best Practices](https://owasp.org/www-project-api-security/)
- [Groq Documentation](https://console.groq.com/docs)
