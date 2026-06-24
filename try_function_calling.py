import datetime
import os
from os import system
from typing import List, Dict, Any
import config
from openai import OpenAI
from ai2thor.controller import Controller
controller = Controller(scene="FloorPlan303")
event = controller.step(action="Pass")  # 任意 step 都可以
object_types = sorted(list(set(obj['objectType'] for obj in event.metadata['objects'])))
task_instruction = """
Place all high tech electronics on the bed
"""

def query_object_parent_receptacles(object_name: str):
    for obj in controller.last_event.metadata["objects"]:
        if object_name.lower() in obj["objectId"].lower():
            return {
                "objectId": obj["objectId"],
                "parentReceptacles": obj.get("parentReceptacles", [])
            }
    return {"error": "object not found"}


def query_receptacle_object_ids(receptacle_name: str):
    for obj in controller.last_event.metadata["objects"]:
        if receptacle_name.lower() in obj["objectId"].lower():
            return {
                "receptacleId": obj["objectId"],
                "receptacleObjectIDs": obj.get("receptacleObjectIds", [])
            }
    return {"error": "receptacle not found"}

tools = [
    {
        "type": "function",
        "function": {
            "name": "query_object_parent_receptacles",
            "description": "Query the parent receptacles of an object",
            "parameters": {
                "type": "object",
                "properties": {
                    "object_name": {"type": "string"}
                },
                "required": ["object_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_receptacle_object_ids",
            "description": "Query objects contained in a receptacle",
            "parameters": {
                "type": "object",
                "properties": {
                    "receptacle_name": {"type": "string"}
                },
                "required": ["receptacle_name"]
            }
        }
    }
]

def run_with_tools(
    client,
    model: str,
    system_prompt: str,
    user_prompt: str,
    tools: list,
    tool_impls: dict,
    max_rounds: int = 5,
):
    """
    Run an LLM with tool-calling support.

    Logic:
    - If LLM does NOT call any tool → directly return output
    - If LLM calls tool(s):
        - Execute tool(s) in Python
        - Feed results back to LLM
        - Call LLM again
    - Repeat until no tool is requested

    Returns:
        Final LLM output (string)
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for _ in range(max_rounds):
        # ① Call LLM
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        msg = response.choices[0].message

        # ② Case 1: No tool called → finish
        if not msg.tool_calls:
            print(f"NOT TOOL CALLS! Final LLM output: {msg.content}")

            return msg.content

        # ③ Case 2: Tool(s) requested
        messages.append(msg)


        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            tool_args = eval(tool_call.function.arguments)

            if tool_name not in tool_impls:
                raise RuntimeError(f"Tool '{tool_name}' not implemented")

            # Execute tool in Python
            tool_result = tool_impls[tool_name](**tool_args)
            print(f"Tool '{tool_name}' called with args: {tool_args}/n"
                  f"content '{str(tool_result)}'")

            # Feed tool result back to LLM
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": str(tool_result),
            })

    raise RuntimeError("Exceeded maximum tool-calling rounds")

tool_impls = {
    "query_object_parent_receptacles": query_object_parent_receptacles,
    "query_receptacle_object_ids": query_receptacle_object_ids,
}

system_prompt = (fr"""
                You are a symbolic trajectory and precondition reasoning module.

You do NOT have direct access to the AI2-THOR environment.
If you need any environment information to correctly generate a valid state evolution trace,
you MUST call the corresponding tool before producing the final output.
You are strictly forbidden to guess or hallucinate environment states.

Environment information that REQUIRES tool calls includes:
- Whether an object is inside a receptacle (parentReceptacles)
- Whether a receptacle contains a specific object (receptacleObjectIDs)

Available tools:
- query_object_parent_receptacles(object_name)
- query_receptacle_object_ids(receptacle_name)

Precondition reasoning rules:
1. If an object is located inside a receptacle that requires opening (e.g., Fridge, Cabinet, Drawer), the receptacle MUST be opened before any subsequent state involving that object (e.g., isHeld_object, isClean_object).
2. If an object is located on or in an open surface or open receptacle (e.g., CounterTop, TableTop, Desk), the opening action can be ignored.
**Special rule for food and vegetables**:
3. If the task involves food items that are vegetables or perishable food (e.g., Apple, Tomato, Lettuce, Potato, Onion), you MUST call the tool to determine whether the object is inside a Fridge before generating any predicate involving that object.
   You are NOT allowed to assume the storage location of such objects without verification.
**Tool usage constraint**:
4. If you call any tool, you MUST first use the tool result to infer the correct environment state,
   and then ensure that the FINAL generated trajectory is CONSISTENT with the tool results.
   The trajectory MUST implicitly reflect the verified environment information (e.g., opening a Fridge if the object is inside it).
   You MUST NOT ignore or contradict any tool result.
**Global Constraint (Non-assumption Principle)**:
5. If the location of any object is unknown or not explicitly specified, you MUST query the environment using the appropriate tool before making any inference. You are strictly prohibited from assuming that an object is inside any receptacle or located on any surface without verification.
 """)
user_prompt = (
    fr"""You are a trajectory formalization expert. 
Your job is to transform natural language task goals into a discrete state evolution trace.
You MUST strictly follow ALL constraints below (no violation allowed):

[Object Name Constraints]
- object names MUST EXACTLY use the same original strings from ai2thor scene
- you MUST NOT invent any object name that is not in the given list

[Predicate Constraints]
- you MUST ONLY use the following predicates (no additions, modifications, deletions allowed):

  isOpen_object
  isClosed_object
  isBroken_object
  isCooked_object
  isSliced_object
  isHeld_object
  isToggledOn_object
  isToggledOff_object
  isDirty_object
  isClean_object
  isFilledWithLiquid_object
  isEmptyLiquid_object
  isUsedUp_object
  inside_objectA_objectB
  onTop_objectA_objectB

(NOTE: all predicates are unary, MUST use parentheses, and MUST contain exactly one objectType name inside)
[Tool Usage Requirement]
- If you call any tool, you MUST:
  1. First interpret and summarize the tool results internally.
  2. Ensure the generated trajectory STRICTLY reflects the tool results.
  3. For example:
     - If an object is inside a Fridge → trajectory MUST include opening the Fridge before interacting with the object.
     - If an object is on a CounterTop → DO NOT include unnecessary opening actions.

[Output Format Constraints]
- You MUST generate a commonsense-consistent safe trajectory.
- Only output state-change propositions (i.e. only predicates that change compared to the previous step)
    - Example: use ['isOpen_Fridge', 'isHeld_Apple','isClean_Apple'], NOT ['isClosed_Fridge','isOpen_Fridge', 'inside_Apple_Fridge','isHeld_Apple','isDirty_Apple','isClean_Apple']
- The output MUST be a single JSON-like list:
  ["predicates1", "predicates2", ..., "predicatesN"]
- Each `" "` MUST contain exactly ONE instantiated predicate.
- No step index, no comments, no natural language.
- ONLY output this one list.
- NO extra text before or after the list.
- Example format (do NOT copy content, this is structure only):
["isOpen_Fridge", "isHeld_Apple","isClean_Apple"]

------------------------------------------------
INPUTS:

### Task Instruction:
{task_instruction}

### ai2thor ObjectType List (from metadata):
{object_types}

------------------------------------------------

Now generate one possible discrete state evolution trace that can satisfy the Task Instruction,
strictly following ALL constraints above.

Output ONLY the trace and summarize the tool results.
"""
)
api_key=config.ltl_api_key
url=config.ltl_url
client = OpenAI(api_key=api_key, base_url=url)
result = run_with_tools(
    client=client,
    model="gpt-5",
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    tools=tools,
    tool_impls=tool_impls
)

print(result)