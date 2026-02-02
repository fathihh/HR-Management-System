# main_agent.py - REFACTORED VERSION

from agents.policy.policy_agent import PolicyAgent
from agents.employee.employee_agent import EmployeeAgent
from agents.sql.sql_agent import SQLAgent

class MainAgent:
    """Main orchestrator agent with fusion capabilities and augmented responses"""
    
    def __init__(self, llm):
        self.llm = llm
        
        self.sql_agent = SQLAgent(llm)
        self.employee_agent = EmployeeAgent(self.sql_agent)
        self.policy_agent = PolicyAgent(llm)
        
        self.current_user_id = None
        self.current_user_role = None
    
    def set_user(self, user_id: str = None, user_role: str = "employee"):
        """Set user context (HR vs Employee)"""
        self.current_user_id = user_id
        self.current_user_role = user_role
        print(f"✅ User set: {user_role} | ID: {user_id}")
    
    def classify_intent(self, question: str) -> dict:
        """Use LLM to classify user intent and required agents"""
        
        classification_prompt = f"""
You are an intent classifier for an HR system. Analyze the user question and determine:
1. Which agents are needed: SQL, POLICY, or BOTH (fusion)
2. The primary action: query_data, generate_payslip, send_email, policy_question, fusion_query

User role: {self.current_user_role}
User question: {question}

Examples:
- "What is my salary?" -> agents: ["SQL"], action: "query_data"
- "What is the leave policy?" -> agents: ["POLICY"], action: "policy_question"
- "Am I eligible for leave based on policy?" -> agents: ["SQL", "POLICY"], action: "fusion_query"
- "Generate my payslip" -> agents: ["SQL"], action: "generate_payslip"
- "Send my payslip to email" -> agents: ["SQL"], action: "send_email"
- "Can I get promotion based on company policy?" -> agents: ["SQL", "POLICY"], action: "fusion_query"

Respond in this EXACT format:
AGENTS: [list of agents]
ACTION: action_name
FUSION: true/false
"""
        
        response = self.llm._call(classification_prompt).strip()
        
        agents_needed = []
        action = "query_data"
        is_fusion = False
        
        for line in response.split('\n'):
            line = line.strip()
            if line.startswith("AGENTS:"):
                agents_text = line.replace("AGENTS:", "").strip()
                if "SQL" in agents_text:
                    agents_needed.append("SQL")
                if "POLICY" in agents_text:
                    agents_needed.append("POLICY")
            elif line.startswith("ACTION:"):
                action = line.replace("ACTION:", "").strip().lower()
            elif line.startswith("FUSION:"):
                is_fusion = "true" in line.lower()
        
        return {
            "agents": agents_needed,
            "action": action,
            "is_fusion": is_fusion or len(agents_needed) > 1
        }
    
    def execute_fusion_query(self, question: str) -> str:
        """Execute query requiring both SQL and Policy agents"""
        
        print("🔀 FUSION MODE: Using SQL + Policy agents")
        
        sql_result = self.sql_agent.execute_sql(
            self.sql_agent.generate_sql(question, self.current_user_id)
        )
        
        policy_result = self.policy_agent.query(question)
        
        fusion_prompt = f"""
You are an HR assistant providing comprehensive answers by combining employee data and company policies.

EMPLOYEE DATA:
{self._format_sql_result(sql_result)}

POLICY INFORMATION:
{policy_result.get('answer', 'No policy information found')}

ORIGINAL QUESTION: {question}

Provide a clear, comprehensive answer that:
1. Uses specific employee data where relevant
2. References applicable policies
3. Gives actionable guidance
4. Is personalized and helpful

Answer:"""
        
        augmented_response = self.llm._call(fusion_prompt).strip()
        
        sources = []
        if "success" in sql_result:
            sources.append("📊 Employee Database")
        if policy_result.get("source_documents"):
            sources.append("📋 Company Policy Documents")
        
        final_response = f"{augmented_response}\n\n---\n📚 Sources: {', '.join(sources)}"
        
        return final_response
    
    def execute_sql_query(self, question: str) -> str:
        """Execute SQL query and augment response"""
        
        print("🔍 SQL MODE: Querying employee database")
        
        sql = self.sql_agent.generate_sql(question, self.current_user_id, self.current_user_role)
        result = self.sql_agent.execute_sql(sql, self.current_user_role)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        if result.get("operation") in ["UPDATE", "INSERT", "DELETE"]:
            return result.get("message", "✅ Operation completed successfully")
        
        augmentation_prompt = f"""
Convert this database query result into a natural, conversational response.

ORIGINAL QUESTION: {question}
SQL QUERY: {result.get('sql', 'N/A')}
DATA: {result.get('data', [])}

Provide a friendly, clear answer that:
1. Directly answers the question
2. Presents data in readable format
3. Adds helpful context where appropriate
4. Is concise but complete

Response:"""
        
        augmented_response = self.llm._call(augmentation_prompt).strip()
        
        return f"{augmented_response}\n\n---\n📊 Source: Employee Database"
    
    def execute_policy_query(self, question: str) -> str:
        """Execute policy query and format response"""
        
        print("📋 POLICY MODE: Searching policy documents")
        
        result = self.policy_agent.query(question)
        
        if "error" in result:
            return f"❌ {result['error']}"
        
        answer = result.get("answer", "No answer found")
        sources = result.get("source_documents", [])
        
        response = f"{answer}\n\n---\n📚 Source: Company Policy Documents"
        
        if sources:
            response += "\n📄 Referenced Sections:"
            for i, doc in enumerate(sources[:3], 1):
                response += f"\n  {i}. {doc['content'][:100]}..."
        
        return response
    
    def handle_payslip_generation(self, question: str) -> str:
        """Generate payslip with augmented response"""
        
        print("📄 Generating payslip...")
        
        emp_id = self.current_user_id
        
        if self.current_user_role == "hr":
            extract_prompt = f"""
Extract the employee ID from this question. If no specific ID is mentioned, return "NONE".
Question: {question}
Employee ID:"""
            extracted_id = self.llm._call(extract_prompt).strip()
            if extracted_id != "NONE" and extracted_id:
                emp_id = extracted_id
        
        if not emp_id:
            return "❌ Please specify an employee ID for payslip generation."
        
        result = self.employee_agent.handle_query(
            f"generate payslip for {emp_id}",
            user_role=self.current_user_role,
            user_id=emp_id
        )
        
        if isinstance(result, dict) and result.get("success"):
            return f"✅ Payslip generated successfully for employee {emp_id}!\n\n{result.get('message', '')}\n\n📁 File saved: {result.get('filename', 'payslip.pdf')}"
        else:
            return f"❌ Error generating payslip: {result}"
    
    def handle_email_sending(self, question: str) -> str:
        """Handle email sending with augmented response"""
        
        print("📧 Sending email...")
        
        emp_id = self.current_user_id
        
        if self.current_user_role == "hr":
            extract_prompt = f"""
Extract the employee ID from this question. If no specific ID is mentioned, return "NONE".
Question: {question}
Employee ID:"""
            extracted_id = self.llm._call(extract_prompt).strip()
            if extracted_id != "NONE" and extracted_id:
                emp_id = extracted_id
        
        if not emp_id:
            return "❌ Please specify an employee ID for sending email."
        
        result = self.employee_agent.handle_query(
            f"send payslip email to {emp_id}",
            user_role=self.current_user_role,
            user_id=emp_id
        )
        
        if isinstance(result, dict) and result.get("success"):
            return f"✅ Email sent successfully to employee {emp_id}!\n\n{result.get('message', '')}"
        else:
            return f"❌ Error sending email: {result}"
    
    def _format_sql_result(self, result: dict) -> str:
        """Format SQL result for fusion prompts"""
        if "error" in result:
            return f"Error: {result['error']}"
        if "data" in result:
            return str(result["data"])
        return "No data available"
    
    def query(self, question: str) -> str:
        """Main query handler with intelligent routing"""
        
        try:
            intent = self.classify_intent(question)
            
            print(f"🎯 Intent: {intent}")
            
            action = intent["action"]
            
            if action == "generate_payslip":
                return self.handle_payslip_generation(question)
            
            elif action == "send_email":
                return self.handle_email_sending(question)
            
            elif intent["is_fusion"]:
                return self.execute_fusion_query(question)
            
            elif "POLICY" in intent["agents"]:
                return self.execute_policy_query(question)
            
            elif "SQL" in intent["agents"]:
                return self.execute_sql_query(question)
            
            else:
                return "❌ Could not determine how to handle this query. Please try rephrasing."
        
        except Exception as e:
            return f"❌ Error processing query: {str(e)}"