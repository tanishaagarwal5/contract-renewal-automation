# Technical Architecture Document
## Contract Renewal Automation System

---

## 1. System Design

### 1.1 High-Level Architecture

```
INPUT LAYER          PROCESSING LAYER           OUTPUT LAYER
─────────────        ──────────────             ────────────
┌──────────┐         ┌──────────────────────┐  ┌───────────┐
│ Contract │         │  LANGGRAPH STATE     │  │ Extracted │
│ Document │────────>│  MACHINE             │─>│ Terms     │
└──────────┘         │  ┌────────────────┐  │  └───────────┘
                     │  │Contract Agent  │  │
                     │  └────────────────┘  │  ┌───────────┐
                     │  ┌────────────────┐  │  │Churn Risk │
                     │  │ Churn Agent    │──┼─>│Assessment │
                     │  └────────────────┘  │  └───────────┘
                     │  ┌────────────────┐  │
                     │  │ Outreach Agent │──┼─>┌───────────┐
                     │  └────────────────┘  │  │Outreach   │
                     │  ┌────────────────┐  │  │Draft      │
                     │  │ Orchestrator   │  │  └───────────┘
                     │  └────────────────┘  │
                     └──────────────────────┘
```

### 1.2 Agent Communication Pattern

**Graph-Based Execution Flow** (LangGraph):

```python
# State flows through agents sequentially:
START 
  ↓
contract_extraction_agent(state) 
  ├─ Input: state["contract_text"]
  ├─ Processing: Claude API extraction
  └─ Output: state["extracted_terms"] ✓
  ↓
churn_risk_agent(state)
  ├─ Input: state["extracted_terms"]
  ├─ Processing: Risk analysis
  └─ Output: state["churn_risk_assessment"] ✓
  ↓
outreach_draft_agent(state)
  ├─ Input: state["extracted_terms"], state["churn_risk_assessment"]
  ├─ Processing: Personalized drafting
  └─ Output: state["draft_outreach"] ✓
  ↓
workflow_orchestrator(state)
  ├─ Input: all previous outputs
  ├─ Processing: Validation & synthesis
  └─ Output: state["workflow_status"] = "COMPLETE"
  ↓
END
```

---

## 2. State Management

### 2.1 ContractState TypedDict

```python
class ContractState(TypedDict):
    """
    Immutable state object for workflow tracking.
    Each agent reads full state and returns Command with updates.
    """
    contract_text: str              # Raw contract document
    contract_id: str                # Unique identifier
    extracted_terms: dict           # Agent 1 output
    churn_risk_assessment: dict     # Agent 2 output
    draft_outreach: str             # Agent 3 output
    workflow_status: str            # Current stage
    error_message: str | None       # Failure details
```

### 2.2 State Mutations

States are immutable in LangGraph. Agents return `Command` objects:

```python
return Command(
    goto="next_agent",  # Route to next agent
    update={            # Immutable state update
        "extracted_terms": {...},
        "workflow_status": "EXTRACTION_COMPLETE"
    }
)
```

---

## 3. Agent Implementation Details

### 3.1 Agent 1: Contract Extraction

**Algorithm**:
1. **System Prompt Design**: Specify JSON structure + field definitions
2. **User Prompt**: "Extract these fields from this contract"
3. **Output Parsing**: 
   - Strip markdown fences (```json...```)
   - Parse JSON
   - Validate required fields
4. **Error Handling**: JSONDecodeError → Command(goto=END, error)

**Key Prompt Techniques**:
```python
system_prompt = """You are a contract analysis expert...
Extract and return ONLY valid JSON (no markdown, no extra text) with this exact structure:
{...}
If a field is not found, use null. Be precise with dates and numbers."""
```

**Why this works**:
- Explicit JSON format → cleaner parsing
- "ONLY JSON" instruction → reduces preamble
- Field definitions in schema → reduces hallucinations
- Use null for missing fields → predictable output

### 3.2 Agent 2: Churn Risk Scoring

**Risk Calculation Framework**:

```python
risk_score = sum([
    price_increase_factor(percentage),       # 0-30 points
    contract_length_factor(months),          # 0-20 points
    sla_performance_gap(guarantee),          # 0-20 points
    termination_flexibility_factor(),        # 0-20 points
    renewal_engagement_factor(auto_renewal)  # 0-10 points
])

# Categorical mapping:
if risk_score >= 80: category = "CRITICAL"
elif risk_score >= 60: category = "HIGH"
elif risk_score >= 40: category = "MEDIUM"
else: category = "LOW"
```

**Retention Lever Generation**:
- For HIGH price increases: "Offer multi-year locked pricing"
- For weak SLAs: "Enhance SLA guarantees"
- For poor engagement: "Add executive business reviews"

### 3.3 Agent 3: Outreach Generation

**Personalization Matrix**:

| Risk Level | Tone | Opening | Value Prop | Close |
|-----------|------|---------|-----------|-------|
| CRITICAL | Urgent, empathetic | "Let's reset..." | Solutions, not value | Immediate exec meeting |
| HIGH | Professional | "Let's discuss..." | Proactive solutions | Next quarter planning |
| MEDIUM | Collaborative | "Look forward to..." | Mutual success | Renewal discussion |
| LOW | Appreciative | "Great partnership..." | Expansion opportunity | Upsell discussion |

**3-Part Outreach Structure**:

1. **Opening Email**
   - Personalized greeting
   - Reference specific contract milestone
   - Transition to discussion
   - Tone matches risk level

2. **Value Recap**
   - Quantified metrics from contract terms
   - ROI/business impact
   - Risk mitigation if HIGH/CRITICAL

3. **Executive Summary**
   - C-level renewal proposal
   - Address identified risks
   - Retention levers as negotiation points
   - Clear next steps timeline

---

## 4. Claude API Integration

### 4.1 Model Selection

**claude-opus-4-6**: Selected for:
- ✅ Highest reasoning ability for complex contracts
- ✅ Structured output reliability
- ✅ Context window (200K tokens) for long contracts
- ✅ Function calling support (future enhancement)

```python
response = client.messages.create(
    model="claude-opus-4-6",           # Enterprise reasoning
    max_tokens=1500,                    # Prevent runaway generation
    system=system_prompt,               # Define role and constraints
    messages=[{"role": "user", "content": user_prompt}]
)
```

### 4.2 Prompt Engineering Best Practices

**1. Explicit Role Definition**
```python
system_prompt = """You are a [specific expert role]...
Your task is to [precise task description]..."""
```

**2. Structured Output Requests**
```python
system_prompt = """Return ONLY valid JSON with this exact structure:
{
    "field1": <type>,
    "field2": <type>,
    ...
}"""
```

**3. Field-Level Instructions**
```python
"If a field is not found, use null. Be precise with dates (YYYY-MM-DD).
Round monetary values to 2 decimal places."
```

**4. Format Constraints**
```python
"Return ONLY the JSON object, no markdown, no preamble, no trailing text."
```

---

## 5. Error Handling Strategy

### 5.1 Graceful Degradation

```
Agent Execution
    ↓
[Try block]
    ├─ API call to Claude
    ├─ Parse response
    ├─ Validate output
    └─ [Catch block]
        └─ Specific error type?
            ├─ JSONDecodeError → Log, return Command(goto=END, error)
            ├─ APIError → Retry with exponential backoff
            └─ ValidationError → Return partial data, flag for review
```

### 5.2 Validation Layers

```python
def validate_extracted_terms(terms: dict) -> bool:
    """Ensure critical fields exist"""
    required = ["renewal_date", "renewal_price"]
    return all(field in terms and terms[field] is not None 
               for field in required)

def validate_workflow_completion(state: ContractState) -> bool:
    """Ensure all agents executed"""
    return (state["extracted_terms"] and 
            state["churn_risk_assessment"] and 
            state["draft_outreach"])
```

---

## 6. Performance Optimization

### 6.1 Token Efficiency

| Agent | Typical Input Tokens | Output Tokens | Optimization |
|-------|----------------------|----------------|--------------|
| Extraction | 500-2000 | 300-500 | JSON format reduces verbosity |
| Churn Analysis | 100-300 | 200-400 | Bounded numerical outputs |
| Outreach | 200-400 | 600-800 | Structured 3-part format |

**Cost Optimization**:
```
claude-opus-4-6: $15/M input, $45/M output
Average contract: ~3K input tokens, ~1.5K output = ~0.06 cost
100 contracts: ~$6 processing cost
```

### 6.2 Batch Processing Efficiency

```python
# Process multiple contracts with:
for contract in contracts:
    result = execute_workflow(contract)  # Sequential execution
    # Alternative: Implement AsyncIO for parallel processing
    # results = asyncio.gather(*[execute_workflow_async(c) for c in contracts])
```

---

## 7. Data Flow Example

### End-to-End Execution Trace

```
INPUT:
  contract_text = "MASTER SERVICE AGREEMENT..."
  contract_id = "CONTRACT_2025_ACME_001"

AGENT 1 (EXTRACTION):
  Prompt: "Extract renewal terms as JSON from: [contract]"
  Response: {"renewal_date": "2026-01-15", "renewal_price": 500000, ...}
  
  state.extracted_terms = {
    "renewal_date": "2026-01-15",
    "renewal_price": 500000,
    "price_increase_percentage": 12.5,
    "auto_renewal": true,
    ...
  }

AGENT 2 (CHURN RISK):
  Prompt: "Assess churn risk for: [extracted terms]"
  Response: {"risk_score": 65, "risk_category": "HIGH", ...}
  
  state.churn_risk_assessment = {
    "risk_score": 65,
    "risk_category": "HIGH",
    "key_risk_factors": ["12.5% price increase", "90-day notice period"],
    "retention_levers": ["Lock 3-year pricing", "Enhanced SLA"],
    "days_until_renewal": 245,
    "outreach_urgency": "HIGH"
  }

AGENT 3 (OUTREACH):
  Prompt: "Draft renewal outreach for HIGH-risk account with $500K value"
  Response: "[OPENING EMAIL]...[VALUE RECAP]...[EXECUTIVE SUMMARY]..."
  
  state.draft_outreach = """
  Subject: Your 2026 Renewal - Let's Discuss Partnership Options
  
  Dear [Client],
  
  As we approach your January 2026 renewal, I wanted to proactively...
  [3-part structure follows]
  """

ORCHESTRATOR:
  Validates: All three agents succeeded ✓
  Status: "COMPLETE"
  Saves results to: ./results/CONTRACT_2025_ACME_001_result.json
  Saves outreach to: ./results/CONTRACT_2025_ACME_001_outreach.md

OUTPUT:
  Complete renewal package ready for account manager review
```

---

## 8. Extensibility Points

### 8.1 Adding Custom Agents

To add a fourth agent (e.g., "Legal Compliance Agent"):

```python
def legal_compliance_agent(state: ContractState) -> Command:
    """New agent checks contract compliance"""
    client = anthropic.Anthropic()
    
    # Process state["extracted_terms"]
    # Generate state["compliance_assessment"]
    
    return Command(
        goto="next_agent",  # Route to next step
        update={"compliance_assessment": {...}}
    )

# Add to workflow graph:
workflow.add_node("legal_compliance_agent", legal_compliance_agent)
workflow.add_edge("churn_risk_agent", "legal_compliance_agent")
workflow.add_edge("legal_compliance_agent", "outreach_draft_agent")
```

### 8.2 Integration Points

**Future Integrations**:
- **Salesforce CRM**: Sync contact info, historical interactions
- **DocuSign**: Track contract execution status
- **Slack**: Alert on critical renewals
- **Email Systems**: Auto-send outreach drafts
- **Data Warehouse**: Log results for analytics

---

## 9. Testing Strategy

### 9.1 Unit Testing Agents

```python
def test_contract_extraction():
    """Test extraction accuracy"""
    mock_contract = "CONTRACT EXPIRY: 2026-01-15..."
    
    state = {
        "contract_text": mock_contract,
        "contract_id": "TEST_001",
        ...
    }
    
    result = contract_extraction_agent(state)
    assert result.update["extracted_terms"]["renewal_date"] == "2026-01-15"

def test_churn_risk_scoring():
    """Test risk categorization"""
    state = {
        "extracted_terms": {
            "price_increase_percentage": 20,  # HIGH risk
            "notice_period_days": 30,         # SHORT notice = HIGH risk
        }
    }
    
    result = churn_risk_agent(state)
    assert result.update["churn_risk_assessment"]["risk_category"] == "HIGH"
```

### 9.2 Integration Testing

```python
def test_end_to_end_workflow():
    """Test complete workflow with sample contract"""
    contract = ContractDocument(
        contract_id="TEST_CONTRACT",
        client_name="Test Corp",
        contract_text=SAMPLE_CONTRACT,
        annual_value=500000,
        last_renewal_date="2023-06-01"
    )
    
    result = execute_contract_renewal_workflow(contract)
    
    assert result["workflow_status"] == "COMPLETE"
    assert len(result["extracted_terms"]) > 0
    assert result["churn_risk_assessment"]["risk_score"] > 0
    assert len(result["draft_outreach"]) > 100
```

---

## 10. Deployment Considerations

### 10.1 Environment Variables

```bash
# Required for production
export ANTHROPIC_API_KEY="sk-ant-..."
export LOG_LEVEL="INFO"
export OUTPUT_DIR="/var/contracts/results"
```

### 10.2 Scaling to Enterprise

**For 1000+ contracts/month**:
1. Implement async execution with `asyncio`
2. Add queue system (Redis/Celery) for job scheduling
3. Cache extraction templates for repeated contract types
4. Implement result database (PostgreSQL) for audit trail
5. Add monitoring (Datadog/New Relic) for performance tracking

```python
# Example async scaling:
async def process_contracts_batch(contracts: list[ContractDocument]):
    """Process contracts in parallel"""
    tasks = [
        execute_contract_renewal_workflow_async(contract)
        for contract in contracts
    ]
    results = await asyncio.gather(*tasks)
    return results
```

---

## 11. Monitoring & Observability

### 11.1 Key Metrics to Track

- **Extraction Accuracy**: % of contracts with all required fields
- **Processing Time**: Avg seconds per contract (target: <30s)
- **API Cost**: $ per contract processed
- **Risk Distribution**: % CRITICAL/HIGH/MEDIUM/LOW
- **Renewal Success Rate**: % of at-risk contracts that renew

### 11.2 Logging Strategy

```python
logger.info(f"Processing contract: {contract_id}")
logger.debug(f"Extracted terms: {extracted_terms}")
logger.warning(f"High-risk contract: {contract_id}, risk_score: {risk_score}")
logger.error(f"Workflow failed: {error_message}", exc_info=True)
```

---

## 12. Cost Analysis

### Per-Contract Processing Cost

```
Average Contract Processing:
├─ Extraction: 1500 input tokens, 400 output = $0.018
├─ Risk Analysis: 400 input, 300 output = $0.0084
├─ Outreach Draft: 600 input, 800 output = $0.021
└─ Orchestration: 200 input, 200 output = $0.0066
────────────────────────────────────
Total per contract: ~$0.055

Monthly costs (100 contracts): $5.50
Annual costs (1200 contracts): $66
```

---

**Architecture Version**: 1.0  
**Last Updated**: 2025  
**Status**: Production-Ready  
