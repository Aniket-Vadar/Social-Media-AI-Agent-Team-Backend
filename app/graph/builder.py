from typing import Optional, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.graph.state import AgentState
from app.graph.supervisor import supervisor_node
from app.graph.nodes.researcher import researcher_node
from app.graph.nodes.creator import creator_node
from app.graph.nodes.scheduler import scheduler_node
from app.graph.nodes.analytics import analytics_node
import logging

logger = logging.getLogger(__name__)


def route_supervisor(state: AgentState) -> str:
    """Conditional routing based on state['next']."""
    next_node = state.get("next")
    if next_node in ["researcher", "creator", "scheduler", "analytics"]:
        return next_node
    if next_node == "supervisor":
        return "supervisor"
    return END


def create_agent_graph(checkpointer: Optional[Any] = None) -> Any:
    """
    Builds the LangGraph multi-agent office workflow:
    - Master Agent (Supervisor) evaluates goals, builds plans, and routes tasks.
    - Specialized sub-agents (Researcher, Creator, Scheduler, Analytics) execute tasks
      and return control back to Supervisor.
    """
    workflow = StateGraph(AgentState)

    # 1. Add Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("creator", creator_node)
    workflow.add_node("scheduler", scheduler_node)
    workflow.add_node("analytics", analytics_node)

    # 2. Add Edges
    workflow.add_edge(START, "supervisor")

    # Dynamic routing from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "supervisor": "supervisor",
            "researcher": "researcher",
            "creator": "creator",
            "scheduler": "scheduler",
            "analytics": "analytics",
            END: END
        }
    )

    # Workers always return to supervisor
    workflow.add_edge("researcher", "supervisor")
    workflow.add_edge("creator", "supervisor")
    workflow.add_edge("scheduler", "supervisor")
    workflow.add_edge("analytics", "supervisor")

    # In production, uses AsyncPostgresSaver; in development/fallback uses MemorySaver
    saver = checkpointer or MemorySaver()
    app = workflow.compile(checkpointer=saver)
    return app


# Global compiled workflow instance
agent_graph = create_agent_graph()
