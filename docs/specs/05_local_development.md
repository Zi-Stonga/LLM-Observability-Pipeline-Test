# 05 Local Development

```bash
# 1. Install Python 3.12 (Microsoft Store on Windows)
python3.12 -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# source .venv/bin/activate     # Mac/Linux

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Run tests
pytest

# 4. Lint and format
ruff check src/ cdk_stack/ tests/
black src/ cdk_stack/ tests/

# 5. CDK synth (validates infra without deploying)
cdk synth -c alert_email=you@example.com -c allowed_origins=https://localhost:3000

# 6. Deploy
cdk deploy -c alert_email=you@example.com -c allowed_origins=https://your-app.example.com
```
