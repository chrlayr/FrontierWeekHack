import json
import os

from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential
from openai.types.responses.response_input_param import FunctionCallOutput

from fpna_agent.tools.planning_tool import get_forecast


# ---------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------

load_dotenv()

PROJECT_CONNECTION_STRING = os.getenv("PROJECT_CONNECTION_STRING")
MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-5.4")


# ---------------------------------------------------------------------
# Foundry Function Tool
# ---------------------------------------------------------------------

GET_FORECAST_TOOL = FunctionTool(
    name="get_forecast",
    description=(
        "Build a fact-based financial forecast using ERP actuals, "
        "operational workload and budget assumptions. Returns the "
        "forecast, variance to budget and supporting evidence."
    ),
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
    strict=False,
)


# ---------------------------------------------------------------------
# Planning Agent
# ---------------------------------------------------------------------

class PlanningAgent:

    def __init__(self):
        self.agent = None
        self.client = None
        self.openai = None

    def create(self):

        self.client = AIProjectClient(
            endpoint=PROJECT_CONNECTION_STRING,
            credential=DefaultAzureCredential(),
        )

        self.openai = self.client.get_openai_client()

        system_prompt = """
        You are the Planning Agent in an FP&A multi-agent system.

        Your purpose is to turn financial and operational evidence
        into a concise, management-ready forecast.

        Always use the get_forecast tool before providing a forecast.

        The forecast calculation returned by the tool is authoritative.
        Do not recalculate, replace or invent financial values.

        Explain:
        - forecast versus annual budget
        - magnitude and direction of the variance
        - key operational and financial drivers
        - relevant uncertainties or items requiring human review
        - evidence supporting the conclusion

        Clearly distinguish facts from interpretation.

        If the source data contains an item requiring human review,
        explicitly flag it rather than making an autonomous assumption.

        Never invent missing data.

        Produce a concise output suitable for an FP&A professional
        or management audience.
        """

        self.agent = self.client.agents.create_version(
            agent_name="fpna-planning-agent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT_NAME,
                instructions=system_prompt,
                tools=[GET_FORECAST_TOOL],
            ),
        )

        return self.agent

    def run(self, input_text: str) -> str:

        conversation = self.openai.conversations.create()

        response = self.openai.responses.create(
            input=input_text,
            conversation=conversation.id,
            extra_body={
                "agent_reference": {
                    "name": self.agent.name,
                    "type": "agent_reference",
                }
            },
        )

        while True:

            function_calls = [
                item for item in response.output
                if item.type == "function_call"
            ]

            if not function_calls:
                break

            input_list = []

            for item in function_calls:

                if item.name == "get_forecast":
                    result = get_forecast()
                else:
                    result = json.dumps(
                        {"error": f"Unknown tool '{item.name}'"}
                    )

                input_list.append(
                    FunctionCallOutput(
                        type="function_call_output",
                        call_id=item.call_id,
                        output=result,
                    )
                )

            response = self.openai.responses.create(
                input=input_list,
                conversation=conversation.id,
                extra_body={
                    "agent_reference": {
                        "name": self.agent.name,
                        "type": "agent_reference",
                    }
                },
            )

        self.openai.conversations.delete(
            conversation_id=conversation.id
        )

        return response.output_text