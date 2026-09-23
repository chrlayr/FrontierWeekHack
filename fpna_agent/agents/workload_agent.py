import json
import os

from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool, PromptAgentDefinition
from azure.identity import DefaultAzureCredential
from openai.types.responses.response_input_param import FunctionCallOutput

from fpna_agent.tools.workload_tool import get_workload


# ---------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------

load_dotenv()

PROJECT_CONNECTION_STRING = os.getenv("PROJECT_CONNECTION_STRING")
MODEL_DEPLOYMENT_NAME = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-5.4")


# ---------------------------------------------------------------------
# Foundry Function Tool
# ---------------------------------------------------------------------

GET_WORKLOAD_TOOL = FunctionTool(
    name="get_workload",
    description=(
        "Retrieve current operational workload and return structured "
        "planning-relevant evidence including remaining person days, "
        "monthly workload, external workload, and active initiatives."
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
# Workload Agent
# ---------------------------------------------------------------------

class WorkloadAgent:

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
        You are the Workload Agent in an FP&A planning system.

        Your purpose is to translate operational workload information
        into factual evidence that can be used for financial planning.

        Always use the get_workload tool before drawing conclusions
        about current or future workload.

        Focus on:
        - remaining workload
        - timing of workload by month
        - external workload that may create future cost
        - active initiatives driving workload

        Do not invent cost rates, financial values, project facts,
        or workload that are not provided by the tool.

        Clearly distinguish factual source data from interpretation.

        Produce a concise structured output suitable for another
        planning agent to consume.
        """

        self.agent = self.client.agents.create_version(
            agent_name="fpna-workload-agent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT_NAME,
                instructions=system_prompt,
                tools=[GET_WORKLOAD_TOOL],
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

                if item.name == "get_workload":
                    result = get_workload()
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