import json
import os

from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential
from openai.types.responses.response_input_param import FunctionCallOutput

from fpna_agent.tools.actuals_tool import get_actuals


# ---------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------

load_dotenv()

PROJECT_CONNECTION_STRING = os.getenv("PROJECT_CONNECTION_STRING")
MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-5.4")


# ---------------------------------------------------------------------
# Foundry Function Tool
# ---------------------------------------------------------------------

GET_ACTUALS_TOOL = FunctionTool(
    name="get_actuals",
    description=(
        "Retrieve current ERP actuals and return FP&A-relevant evidence "
        "including mapped cost categories, confidence levels, "
        "mapping rationale, and transactions requiring human review."
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
# Actuals Agent
# ---------------------------------------------------------------------

class ActualsAgent:

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
        You are the Actuals Agent in an FP&A planning system.

        Your purpose is to translate financial actuals into reliable
        planning evidence.

        Always use the get_actuals tool before drawing conclusions
        about financial actuals.

        Focus on:
        - total actual spend
        - spend by FP&A category
        - mapping confidence
        - transactions requiring human review
        - material financial observations

        Never invent financial values, mappings, vendors, transactions,
        or explanations that are not supported by the tool output.

        A low-confidence transaction must remain flagged for human review.
        Do not autonomously override a low-confidence mapping.

        Clearly distinguish factual source data from interpretation.

        Produce concise structured output suitable for another
        planning agent to consume.
        """

        self.agent = self.client.agents.create_version(
            agent_name="fpna-actuals-agent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT_NAME,
                instructions=system_prompt,
                tools=[GET_ACTUALS_TOOL],
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

                if item.name == "get_actuals":
                    result = get_actuals()
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