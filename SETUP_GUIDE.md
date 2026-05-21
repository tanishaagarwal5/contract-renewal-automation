# Setup Guide

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Anthropic API key (get one at https://console.anthropic.com)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/contract-renewal-automation.git
cd contract-renewal-automation
```

### 2. Create Virtual Environment

```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
touch .env
```

Add your API key to `.env`:

```
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

**Important**: Never commit `.env` to GitHub. It's already in `.gitignore`.

### 5. Verify Installation

```bash
python -c "import anthropic; print('✓ Anthropic SDK installed')"
python -c "import langgraph; print('✓ LangGraph installed')"
```

---

## Running the Project

### Basic Usage

```bash
# Run single contract workflow
python contract_renewal_workflow.py
```

**Output**: 
- Extracted renewal terms (JSON)
- Churn risk assessment (0-100 score)
- Generated outreach draft (3-part email sequence)

### Batch Processing

```bash
# Process multiple contracts with dashboard
python contract_renewal_advanced.py
```

**Output**:
- Batch processing report (success rate, critical alerts)
- CSV summary of all contracts
- Individual outreach files for each contract
- Risk dashboard with metrics

---

## Troubleshooting

### Issue: "No module named 'anthropic'"

**Solution**: Reinstall dependencies
```bash
pip install --upgrade -r requirements.txt
```

### Issue: "ANTHROPIC_API_KEY not found"

**Solution**: Verify `.env` file exists and has correct format
```bash
cat .env
# Should show: ANTHROPIC_API_KEY=sk-ant-...
```

### Issue: "Connection timeout to API"

**Solution**: Check your internet connection and API key validity
```bash
export ANTHROPIC_API_KEY="your-key-here"
python -c "import anthropic; print(anthropic.Anthropic().api_key[:10])"
```

### Issue: "LangGraph state errors"

**Solution**: Ensure Python version is 3.11+
```bash
python --version
```

---

## Configuration

### Adjusting Risk Thresholds

Edit `contract_renewal_workflow.py` in the `churn_risk_agent` function:

```python
# Change price increase threshold (default: 15%)
price_increase_threshold = 20  # More aggressive

# Change risk scoring weights
risk_score = (
    price_increase_factor * 0.3 +  # Adjust weight
    contract_length_factor * 0.2 +
    sla_performance_gap * 0.3 +
    termination_flexibility * 0.2
)
```

### Custom Contract Data

Create a new `ContractDocument`:

```python
from contract_renewal_workflow import ContractDocument, execute_contract_renewal_workflow

contract = ContractDocument(
    contract_id="YOUR_CONTRACT_ID",
    client_name="Your Client Name",
    contract_text="<full contract text here>",
    annual_value=500000.0,
    last_renewal_date="2023-01-15"
)

result = execute_contract_renewal_workflow(contract)
```

---

## Performance Notes

**Processing time per contract**: 20-40 seconds (depends on contract length)

**API costs**: ~$0.05 per contract

**For 100 contracts**: ~$5 processing cost

---

## Next Steps

1. **Read the docs**:
   - Architecture: `ARCHITECTURE.md`
   - Portfolio: `PORTFOLIO_PRESENTATION.md`

2. **Explore the code**:
   - Main system: `contract_renewal_workflow.py`
   - Advanced features: `contract_renewal_advanced.py`

3. **Customize**:
   - Modify prompts in agent functions
   - Add new risk factors
   - Integrate with your CRM

---

## Getting Help

- **Claude API Docs**: https://docs.claude.com
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **Issues**: Open an issue on GitHub

---

## Updating Dependencies

```bash
pip install --upgrade -r requirements.txt
```

---

## Uninstalling

```bash
deactivate  # Deactivate virtual environment
rm -rf venv  # Remove virtual environment
```

---

## License

MIT License - See LICENSE file for details
