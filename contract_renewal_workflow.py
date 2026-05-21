"""
Contract Renewal Automation - Agentic Workflow
Multi-agent system that autonomously processes contracts, extracts terms, 
scores churn risk, and drafts outreach communications.

Architecture:
1. Contract Extraction Agent - Parses contract documents and extracts renewal terms
2. Churn Risk Agent - Analyzes account health and predicts churn probability
3. Outreach Draft Agent - Generates personalized stakeholder communications
4. Orchestrator Agent - Coordinates workflow and validates outputs

Tech Stack: LangGraph + Claude API + Python
"""

import json
import re
from typing import TypedDict, Annotated
from datetime import datetime, timedelta
from dataclasses import dataclass

# Third-party imports
import anthropic
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

# ============================================================================
# Type Definitions & State Management
# ============================================================================

class ContractState(TypedDict):
    """State object passed through the agentic workflow"""
    contract_text: str
    contract_id: str
    extracted_terms: dict
    churn_risk_assessment: dict
    draft_outreach: str
    workflow_status: str
    error_message: str | None


@dataclass
class ContractDocument:
    """Represents a contract document"""
    contract_id: str
    client_name: str
    contract_text: str
    annual_value: float
    last_renewal_date: str


@dataclass
class RenewalTerms:
    """Extracted renewal terms from contract"""
    renewal_date: str
    notice_period_days: int
    renewal_price: float
    price_increase_percentage: float
    key_deliverables: list[str]
    auto_renewal: bool
    termination_clause_type: str


@dataclass
class ChurnRiskScore:
    """Churn risk assessment"""
    risk_score: float  # 0-100
    risk_category: str  # LOW, MEDIUM, HIGH, CRITICAL
    key_risk_factors: list[str]
    retention_levers: list[str]
    recommended_action: str


# ============================================================================
# Agent 1: Contract Extraction Agent
# ============================================================================

def contract_extraction_agent(state: ContractState) -> Command:
    """
    Extracts structured renewal terms from unstructured contract text.
    Uses Claude to intelligently parse contract language.
    """
    client = anthropic.Anthropic()
    
    system_prompt = """You are a contract analysis expert specializing in SaaS and enterprise agreements.
Your task is to extract key renewal terms from the contract text provided.

Extract and return ONLY valid JSON (no markdown, no extra text) with this exact structure:
{
    "renewal_date": "YYYY-MM-DD",
    "notice_period_days": <int>,
    "renewal_price": <float>,
    "price_increase_percentage": <float>,
    "key_deliverables": [<list of strings>],
    "auto_renewal": <boolean>,
    "termination_clause_type": "<string>",
    "payment_terms": "<string>",
    "sla_uptime_guarantee": "<string>",
    "early_termination_fee_percentage": <float>,
    "contract_length_months": <int>
}

If a field is not found, use null. Be precise with dates and numbers."""

    user_prompt = f"""Extract renewal terms from this contract:

CONTRACT ID: {state['contract_id']}
---
{state['contract_text']}
---

Return ONLY the JSON object, no other text."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    
    response_text = response.content[0].text.strip()
    
    # Parse the JSON response
    try:
        # Remove markdown code blocks if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        extracted_terms = json.loads(response_text)
    except json.JSONDecodeError as e:
        return Command(
            goto=END,
            update={
                "workflow_status": "FAILED",
                "error_message": f"Failed to parse contract extraction: {str(e)}"
            }
        )
    
    return Command(
        goto="churn_risk_agent",
        update={
            "extracted_terms": extracted_terms,
            "workflow_status": "EXTRACTION_COMPLETE"
        }
    )


# ============================================================================
# Agent 2: Churn Risk Scoring Agent
# ============================================================================

def churn_risk_agent(state: ContractState) -> Command:
    """
    Analyzes contract and account metrics to predict churn risk.
    Identifies key risk factors and recommends retention strategies.
    """
    client = anthropic.Anthropic()
    
    terms = state["extracted_terms"]
    
    # Build context from extracted terms
    context = f"""
Contract Analysis Summary:
- Renewal Date: {terms.get('renewal_date', 'N/A')}
- Annual Value: ${terms.get('renewal_price', 0):,.2f}
- Price Increase: {terms.get('price_increase_percentage', 0)}%
- Notice Period: {terms.get('notice_period_days', 0)} days
- Auto-Renewal: {terms.get('auto_renewal', False)}
- Early Termination Fee: {terms.get('early_termination_fee_percentage', 0)}%
- SLA Guarantee: {terms.get('sla_uptime_guarantee', 'Not specified')}
- Contract Length: {terms.get('contract_length_months', 0)} months
"""

    system_prompt = """You are a customer success strategist with expertise in SaaS contract retention.
Analyze the contract details provided and assess churn risk. Consider:
1. Price increase impact (>15% is typically high-risk)
2. Contract renewal frequency (shorter = higher risk)
3. SLA terms and performance obligations
4. Early termination flexibility
5. Auto-renewal provisions

Return ONLY valid JSON (no markdown) with this structure:
{
    "risk_score": <0-100>,
    "risk_category": "<LOW|MEDIUM|HIGH|CRITICAL>",
    "key_risk_factors": [<list of specific risk factors>],
    "retention_levers": [<list of retention strategies>],
    "recommended_action": "<specific action summary>",
    "days_until_renewal": <int>,
    "outreach_urgency": "<LOW|MEDIUM|HIGH>"
}"""

    user_prompt = f"""Assess churn risk for this contract:

{context}

Return ONLY the JSON object."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    
    response_text = response.content[0].text.strip()
    
    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        churn_assessment = json.loads(response_text)
    except json.JSONDecodeError as e:
        return Command(
            goto=END,
            update={
                "workflow_status": "FAILED",
                "error_message": f"Failed to parse churn assessment: {str(e)}"
            }
        )
    
    return Command(
        goto="outreach_draft_agent",
        update={
            "churn_risk_assessment": churn_assessment,
            "workflow_status": "CHURN_ANALYSIS_COMPLETE"
        }
    )


# ============================================================================
# Agent 3: Outreach Draft Agent
# ============================================================================

def outreach_draft_agent(state: ContractState) -> Command:
    """
    Generates personalized stakeholder outreach communications.
    Creates contextual, data-driven messaging for renewal discussions.
    """
    client = anthropic.Anthropic()
    
    terms = state["extracted_terms"]
    risk = state["churn_risk_assessment"]
    
    # Determine tone and strategy based on risk level
    risk_category = risk.get("risk_category", "MEDIUM")
    outreach_urgency = risk.get("outreach_urgency", "MEDIUM")
    
    tone_instructions = {
        "LOW": "Positive, appreciative tone. Focus on partnership expansion.",
        "MEDIUM": "Professional, collaborative. Address concerns proactively.",
        "HIGH": "Urgent, empathetic. Acknowledge challenges, emphasize solutions.",
        "CRITICAL": "Executive-level, immediate action. Propose partnership reset."
    }
    
    system_prompt = f"""You are a seasoned account manager drafting renewal outreach.
Tone: {tone_instructions.get(risk_category, 'Professional')}

Create a compelling 3-part outreach sequence:
1. Opening Email - Initial renewal discussion
2. Value Recap - Business impact summary
3. Executive Summary - C-level renewal proposal

Be specific, reference contract details, and propose solutions to identified risks.
Use professional but warm language. Include clear next steps.

Format your response as:
[OPENING EMAIL]
<email>

[VALUE RECAP]
<summary>

[EXECUTIVE SUMMARY]
<proposal>"""

    user_prompt = f"""Draft outreach for this contract renewal:

Client Annual Value: ${terms.get('renewal_price', 0):,.2f}
Renewal Date: {terms.get('renewal_date', 'N/A')}
Price Increase: {terms.get('price_increase_percentage', 0)}%
Risk Category: {risk_category}
Key Risks: {', '.join(risk.get('key_risk_factors', [])[:3])}
Retention Levers: {', '.join(risk.get('retention_levers', [])[:3])}

Create urgency-appropriate, compelling outreach."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    
    draft_outreach = response.content[0].text
    
    return Command(
        goto="workflow_orchestrator",
        update={
            "draft_outreach": draft_outreach,
            "workflow_status": "OUTREACH_DRAFTED"
        }
    )


# ============================================================================
# Orchestrator: Workflow Coordinator & Validator
# ============================================================================

def workflow_orchestrator(state: ContractState) -> Command:
    """
    Final validation and synthesis step.
    Ensures all agents completed successfully and outputs final result.
    """
    client = anthropic.Anthropic()
    
    # Validate all agents completed
    if not state.get("extracted_terms"):
        return Command(
            goto=END,
            update={"workflow_status": "FAILED", "error_message": "Missing extracted terms"}
        )
    
    if not state.get("churn_risk_assessment"):
        return Command(
            goto=END,
            update={"workflow_status": "FAILED", "error_message": "Missing churn assessment"}
        )
    
    if not state.get("draft_outreach"):
        return Command(
            goto=END,
            update={"workflow_status": "FAILED", "error_message": "Missing draft outreach"}
        )
    
    # Synthesis prompt for final validation
    system_prompt = """You are a contract renewal strategist providing final validation.
Review the complete renewal package and confirm readiness for execution.
Provide a brief executive summary with confidence level and any final recommendations."""

    synthesis_prompt = f"""Validate this complete renewal package:

EXTRACTED TERMS:
{json.dumps(state['extracted_terms'], indent=2)}

CHURN RISK ASSESSMENT:
{json.dumps(state['churn_risk_assessment'], indent=2)}

Provide: 
1. Validation Status (READY/NEEDS_REVIEW)
2. Confidence Level (0-100%)
3. Critical Actions Required
4. Timeline Recommendation"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=800,
        system=system_prompt,
        messages=[{"role": "user", "content": synthesis_prompt}]
    )
    
    validation_summary = response.content[0].text
    
    return Command(
        goto=END,
        update={
            "workflow_status": "COMPLETE",
            "extracted_terms": state["extracted_terms"],
            "churn_risk_assessment": state["churn_risk_assessment"],
            "draft_outreach": state["draft_outreach"]
        }
    )


# ============================================================================
# LangGraph Workflow Construction
# ============================================================================

def build_contract_renewal_workflow():
    """
    Constructs the LangGraph state machine for contract renewal automation.
    Defines the multi-agent orchestration flow.
    """
    workflow = StateGraph(ContractState)
    
    # Add agent nodes
    workflow.add_node("contract_extraction_agent", contract_extraction_agent)
    workflow.add_node("churn_risk_agent", churn_risk_agent)
    workflow.add_node("outreach_draft_agent", outreach_draft_agent)
    workflow.add_node("workflow_orchestrator", workflow_orchestrator)
    
    # Define edges (sequential execution)
    workflow.add_edge(START, "contract_extraction_agent")
    
    # Graph is configured in agents to use Command pattern for conditional routing
    
    return workflow.compile()


# ============================================================================
# Execution & Demo
# ============================================================================

def execute_contract_renewal_workflow(contract: ContractDocument) -> ContractState:
    """
    Executes the complete contract renewal automation workflow.
    """
    graph = build_contract_renewal_workflow()
    
    initial_state: ContractState = {
        "contract_text": contract.contract_text,
        "contract_id": contract.contract_id,
        "extracted_terms": {},
        "churn_risk_assessment": {},
        "draft_outreach": "",
        "workflow_status": "INITIALIZED",
        "error_message": None
    }
    
    print(f"\n{'='*70}")
    print(f"CONTRACT RENEWAL AUTOMATION WORKFLOW")
    print(f"{'='*70}")
    print(f"Processing: {contract.contract_id} | Client: {contract.client_name}")
    print(f"Annual Value: ${contract.annual_value:,.2f}")
    print(f"{'='*70}\n")
    
    # Execute workflow
    final_state = graph.invoke(initial_state)
    
    return final_state


def print_workflow_results(state: ContractState):
    """Pretty-prints the workflow results"""
    print(f"\n{'='*70}")
    print(f"WORKFLOW RESULTS: {state['workflow_status']}")
    print(f"{'='*70}\n")
    
    if state["error_message"]:
        print(f"❌ ERROR: {state['error_message']}\n")
        return
    
    print("📋 EXTRACTED RENEWAL TERMS:")
    print("-" * 70)
    for key, value in state["extracted_terms"].items():
        if isinstance(value, list):
            print(f"  {key}:")
            for item in value:
                print(f"    • {item}")
        else:
            print(f"  {key}: {value}")
    
    print(f"\n⚠️  CHURN RISK ASSESSMENT:")
    print("-" * 70)
    risk = state["churn_risk_assessment"]
    print(f"  Risk Score: {risk.get('risk_score', 'N/A')}/100")
    print(f"  Risk Category: {risk.get('risk_category', 'N/A')}")
    print(f"  Urgency: {risk.get('outreach_urgency', 'N/A')}")
    print(f"  Days Until Renewal: {risk.get('days_until_renewal', 'N/A')}")
    print(f"  Key Risk Factors:")
    for factor in risk.get('key_risk_factors', []):
        print(f"    • {factor}")
    print(f"  Retention Levers:")
    for lever in risk.get('retention_levers', []):
        print(f"    • {lever}")
    
    print(f"\n✉️  STAKEHOLDER OUTREACH DRAFT:")
    print("-" * 70)
    print(state["draft_outreach"])
    print(f"\n{'='*70}\n")


# ============================================================================
# Sample Contract Data (for testing)
# ============================================================================

SAMPLE_CONTRACT = """
MASTER SERVICE AGREEMENT
Agreement Date: January 15, 2023
Effective Date: January 15, 2023
Expiration Date: January 14, 2026

CLIENT: TechCorp Inc.
VENDOR: CloudSolutions Inc.

1. SERVICES
Vendor shall provide Cloud Infrastructure and Data Analytics Platform with the following:
- 99.99% uptime SLA guarantee
- 24/7 technical support
- Monthly analytics reports
- Custom dashboard development (up to 20 hours/month)
- Data backup and disaster recovery

2. FINANCIAL TERMS
Annual Service Fee: $250,000
Payment Terms: Net 30 (quarterly billing)
Proposed Renewal Fee: $287,500 (15% increase)
Early Termination Fee: 30% of remaining contract value
Price increases effective yearly: 5% + inflation

3. RENEWAL TERMS
- Automatic renewal for 3-year terms unless notice given 90 days prior
- Renewal notice deadline: October 15, 2025
- All terms and conditions remain the same unless mutually agreed upon

4. TERMINATION FOR CONVENIENCE
- Either party may terminate with 180 days written notice
- Early termination incurs 30% penalty on remaining fees
- Client data shall be returned within 30 days of termination

5. PERFORMANCE STANDARDS
- System Uptime: 99.99% monthly availability (excluding scheduled maintenance)
- Response Time: <2 hours for critical issues, <8 hours for standard issues
- Monthly reporting of performance metrics
- Annual health check meetings with C-level stakeholders

6. KEY DELIVERABLES
- Real-time analytics dashboard with custom KPIs
- Weekly performance optimization reports
- Quarterly business reviews
- Annual strategic planning sessions
- Custom API integrations (up to 5 per year)

7. GENERAL TERMS
- Governing Law: Delaware
- Term: 3 years from effective date
- Confidentiality: 3 years post-termination
- Liability Cap: 12 months of annual fees
"""


def main():
    """Demo execution"""
    # Create sample contract
    sample_contract = ContractDocument(
        contract_id="CONTRACT_2025_TECHCORP_001",
        client_name="TechCorp Inc.",
        contract_text=SAMPLE_CONTRACT,
        annual_value=250000.0,
        last_renewal_date="2023-01-15"
    )
    
    # Execute workflow
    result = execute_contract_renewal_workflow(sample_contract)
    
    # Display results
    print_workflow_results(result)


if __name__ == "__main__":
    main()
