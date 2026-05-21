"""
Contract Renewal Automation - Production Features
Extended implementation with persistence, batch processing, and observability
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import asdict
import csv

from contract_renewal_workflow import (
    ContractState,
    ContractDocument,
    execute_contract_renewal_workflow,
    print_workflow_results
)


# ============================================================================
# Logging & Monitoring
# ============================================================================

def setup_logging(log_dir: str = "./logs"):
    """Configure logging for workflow execution tracking"""
    Path(log_dir).mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'{log_dir}/contract_renewal_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)


logger = setup_logging()


# ============================================================================
# Persistence Layer
# ============================================================================

class WorkflowResultsPersistence:
    """Handles saving and loading workflow results"""
    
    def __init__(self, output_dir: str = "./results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def save_workflow_result(self, state: ContractState, contract_id: str):
        """Save complete workflow result to JSON"""
        output_file = self.output_dir / f"{contract_id}_result.json"
        
        # Convert state to serializable format
        result = {
            "contract_id": state["contract_id"],
            "timestamp": datetime.now().isoformat(),
            "workflow_status": state["workflow_status"],
            "extracted_terms": state["extracted_terms"],
            "churn_risk_assessment": state["churn_risk_assessment"],
            "draft_outreach": state["draft_outreach"],
            "error_message": state["error_message"]
        }
        
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Workflow result saved: {output_file}")
        return output_file
    
    def save_churn_summary(self, summaries: list[dict]):
        """Save churn risk summary for all contracts"""
        output_file = self.output_dir / f"churn_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'contract_id', 'risk_score', 'risk_category', 'annual_value',
                'renewal_date', 'days_until_renewal', 'outreach_urgency'
            ])
            writer.writeheader()
            writer.writerows(summaries)
        
        logger.info(f"Churn summary saved: {output_file}")
        return output_file
    
    def save_outreach_package(self, contract_id: str, outreach: str):
        """Save outreach draft as markdown file"""
        output_file = self.output_dir / f"{contract_id}_outreach.md"
        
        with open(output_file, 'w') as f:
            f.write(outreach)
        
        logger.info(f"Outreach package saved: {output_file}")
        return output_file


# ============================================================================
# Batch Processing
# ============================================================================

class ContractRenewalBatchProcessor:
    """Processes multiple contracts in batch with summary reporting"""
    
    def __init__(self, output_dir: str = "./results"):
        self.persistence = WorkflowResultsPersistence(output_dir)
        self.results = []
        self.summaries = []
    
    def process_contracts(self, contracts: list[ContractDocument]) -> dict:
        """
        Process multiple contracts and generate summary report
        
        Args:
            contracts: List of ContractDocument objects
            
        Returns:
            Dictionary with batch processing summary
        """
        logger.info(f"Starting batch processing of {len(contracts)} contracts")
        
        successful = 0
        failed = 0
        critical_renewals = []
        medium_risk_contracts = []
        
        for contract in contracts:
            try:
                logger.info(f"Processing: {contract.contract_id}")
                
                # Execute workflow
                result = execute_contract_renewal_workflow(contract)
                
                if result["workflow_status"] == "COMPLETE":
                    successful += 1
                    
                    # Save individual result
                    self.persistence.save_workflow_result(result, contract.contract_id)
                    self.persistence.save_outreach_package(
                        contract.contract_id, 
                        result["draft_outreach"]
                    )
                    
                    # Track summary
                    risk = result["churn_risk_assessment"]
                    summary = {
                        "contract_id": contract.contract_id,
                        "risk_score": risk.get("risk_score", 0),
                        "risk_category": risk.get("risk_category", "UNKNOWN"),
                        "annual_value": contract.annual_value,
                        "renewal_date": result["extracted_terms"].get("renewal_date", "N/A"),
                        "days_until_renewal": risk.get("days_until_renewal", 0),
                        "outreach_urgency": risk.get("outreach_urgency", "N/A")
                    }
                    self.summaries.append(summary)
                    
                    # Flag for action
                    if risk.get("risk_category") == "CRITICAL":
                        critical_renewals.append(contract.contract_id)
                    elif risk.get("risk_category") == "HIGH":
                        medium_risk_contracts.append(contract.contract_id)
                    
                    self.results.append(result)
                else:
                    failed += 1
                    logger.error(f"Workflow failed: {result.get('error_message')}")
                    
            except Exception as e:
                failed += 1
                logger.error(f"Error processing {contract.contract_id}: {str(e)}", exc_info=True)
        
        # Save churn summary
        self.persistence.save_churn_summary(self.summaries)
        
        # Generate report
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_contracts": len(contracts),
            "successful": successful,
            "failed": failed,
            "success_rate": f"{(successful / len(contracts) * 100):.1f}%",
            "critical_renewals": critical_renewals,
            "high_risk_contracts": medium_risk_contracts,
            "total_at_risk_value": sum([
                s["annual_value"] for s in self.summaries 
                if s["risk_category"] in ["HIGH", "CRITICAL"]
            ]),
            "average_risk_score": sum([s["risk_score"] for s in self.summaries]) / len(self.summaries) if self.summaries else 0
        }
        
        return report
    
    def print_batch_report(self, report: dict):
        """Pretty-print batch processing report"""
        print(f"\n{'='*70}")
        print(f"BATCH PROCESSING REPORT")
        print(f"{'='*70}")
        print(f"Timestamp: {report['timestamp']}")
        print(f"Total Contracts: {report['total_contracts']}")
        print(f"Successful: {report['successful']} | Failed: {report['failed']}")
        print(f"Success Rate: {report['success_rate']}")
        print(f"\nAverage Risk Score: {report['average_risk_score']:.1f}/100")
        print(f"Total At-Risk Revenue: ${report['total_at_risk_value']:,.2f}")
        
        if report['critical_renewals']:
            print(f"\n🚨 CRITICAL RENEWALS (Immediate Action Required):")
            for contract_id in report['critical_renewals']:
                print(f"   • {contract_id}")
        
        if report['high_risk_contracts']:
            print(f"\n⚠️  HIGH RISK CONTRACTS (Action Required):")
            for contract_id in report['high_risk_contracts'][:5]:
                print(f"   • {contract_id}")
            if len(report['high_risk_contracts']) > 5:
                print(f"   ... and {len(report['high_risk_contracts']) - 5} more")
        
        print(f"\n{'='*70}\n")


# ============================================================================
# Dashboard & Metrics
# ============================================================================

class RenewalMetricsDashboard:
    """Generates dashboard data for contract renewal metrics"""
    
    def __init__(self, summaries: list[dict]):
        self.summaries = summaries
    
    def get_risk_distribution(self) -> dict:
        """Get distribution of risk categories"""
        distribution = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0
        }
        
        for summary in self.summaries:
            category = summary["risk_category"]
            if category in distribution:
                distribution[category] += 1
        
        return distribution
    
    def get_upcoming_renewals(self, days_threshold: int = 90) -> list[dict]:
        """Get contracts renewing within threshold days"""
        upcoming = [
            s for s in self.summaries 
            if 0 < s["days_until_renewal"] <= days_threshold
        ]
        return sorted(upcoming, key=lambda x: x["days_until_renewal"])
    
    def get_revenue_at_risk(self) -> dict:
        """Calculate revenue at risk by category"""
        at_risk = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0
        }
        
        for summary in self.summaries:
            category = summary["risk_category"]
            if category in at_risk:
                at_risk[category] += summary["annual_value"]
        
        return at_risk
    
    def print_dashboard(self):
        """Print formatted dashboard"""
        print(f"\n{'='*70}")
        print(f"CONTRACT RENEWAL METRICS DASHBOARD")
        print(f"{'='*70}\n")
        
        # Risk Distribution
        distribution = self.get_risk_distribution()
        print("📊 RISK DISTRIBUTION:")
        for category, count in distribution.items():
            pct = (count / len(self.summaries) * 100) if self.summaries else 0
            print(f"   {category}: {count} contracts ({pct:.1f}%)")
        
        # Revenue at Risk
        print(f"\n💰 REVENUE AT RISK:")
        revenue_risk = self.get_revenue_at_risk()
        total_at_risk = sum(revenue_risk.values())
        for category, amount in revenue_risk.items():
            pct = (amount / sum([s["annual_value"] for s in self.summaries]) * 100) if self.summaries else 0
            print(f"   {category}: ${amount:,.0f} ({pct:.1f}%)")
        print(f"   TOTAL AT RISK: ${total_at_risk:,.0f}")
        
        # Upcoming Renewals
        print(f"\n📅 UPCOMING RENEWALS (Next 90 days):")
        upcoming = self.get_upcoming_renewals()
        if upcoming:
            for renewal in upcoming[:10]:
                print(f"   {renewal['contract_id']} - {renewal['renewal_date']} ({renewal['days_until_renewal']} days)")
        else:
            print("   No renewals in next 90 days")
        
        print(f"\n{'='*70}\n")


# ============================================================================
# Sample Batch Data
# ============================================================================

def get_sample_contracts() -> list[ContractDocument]:
    """Generate sample contracts for batch processing demo"""
    
    contracts = [
        ContractDocument(
            contract_id="CONTRACT_2025_TECHCORP_001",
            client_name="TechCorp Inc.",
            contract_text="""
MASTER SERVICE AGREEMENT - TechCorp Inc.
Agreement Date: January 15, 2023
Expiration Date: January 14, 2026
Annual Service Fee: $250,000
Proposed Renewal Fee: $287,500 (15% increase)
Renewal notice deadline: October 15, 2025
Auto-renewal for 3-year terms unless notice given 90 days prior
99.99% uptime SLA guarantee
Early Termination Fee: 30% of remaining contract value
""",
            annual_value=250000.0,
            last_renewal_date="2023-01-15"
        ),
        ContractDocument(
            contract_id="CONTRACT_2025_FINSERV_002",
            client_name="FinServe Solutions",
            contract_text="""
DATA ANALYTICS PLATFORM AGREEMENT - FinServe Solutions
Effective Date: June 1, 2023
Expiration Date: May 31, 2026
Annual Fee: $500,000
Renewal Price: $575,000 (15% increase)
Renewal notice deadline: February 28, 2025
Monthly reporting required
Custom dashboard development (40 hours/month)
99.95% uptime SLA
Early termination: 6 months notice + 50% penalty
""",
            annual_value=500000.0,
            last_renewal_date="2023-06-01"
        ),
        ContractDocument(
            contract_id="CONTRACT_2025_RETAIL_003",
            client_name="RetailCo Network",
            contract_text="""
POINT OF SALE INTEGRATION AGREEMENT - RetailCo Network
Start Date: March 1, 2024
End Date: February 28, 2027
Annual Cost: $150,000
Renewal Cost: $157,500 (5% increase)
Auto-renewal with 60-day cancellation window
99.9% uptime guarantee
Standard support included
Custom integrations: 3 per year included
Migration assistance at renewal
""",
            annual_value=150000.0,
            last_renewal_date="2024-03-01"
        ),
    ]
    
    return contracts


# ============================================================================
# Main Execution
# ============================================================================

def main():
    """Execute batch processing with full reporting"""
    
    # Setup
    logger.info("Starting Contract Renewal Automation Batch Processing")
    
    # Get sample contracts
    contracts = get_sample_contracts()
    
    # Process batch
    processor = ContractRenewalBatchProcessor()
    report = processor.process_contracts(contracts)
    
    # Display report
    processor.print_batch_report(report)
    
    # Display dashboard
    if processor.summaries:
        dashboard = RenewalMetricsDashboard(processor.summaries)
        dashboard.print_dashboard()
    
    logger.info("Batch processing complete")


if __name__ == "__main__":
    main()
