import datetime
import os
from os import system
from typing import List, Dict, Any
from openai import OpenAI

run_directory = None
first_run = True
LOG_FORMULA_PATH ='LTL_formula_log.txt'
LOG_TRACE_PATH = 'LTL_trace_log.txt'

class LLMClient():
    """
    一个抽象的LLM客户端。
    """
    def __init__(self, api_key: str, url:str, model_name: str = "gpt-4o", log_dir: str = None):
        # 初始化LLM客户端
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key, base_url=url)
        self.model_name = model_name
        self.log_dir = log_dir

    def log_interaction(self,path,conversation_history):
        """
        记录交互记录
        """
        global first_run
        log_file_path = os.path.join(self.log_dir, path)
        # 如果是第一次运行，写入启动信息
        if first_run:
            with open(log_file_path, 'a', encoding='utf-8') as file:
                file.write(f"{'-' * 100}\n")
                file.write(f"Starting interaction at {datetime.datetime.now()}\n")
                file.write(f"model: {self.model_name}\n")
                # file.write(f"temperature: {LLM_temp}\n")
                file.write(f"{'-' * 100}\n")  # 分隔线
                first_run = False
        # # 读取现有文件内容，保留启动信息
        # with open(log_file_path, 'r', encoding='utf-8') as file:
        #     existing_content = file.readlines()
        # # 只保留启动信息的部分
        # startup_info_end_index = existing_content.index(f"{'-' * 100}\n", 1) + 1
        # startup_info = existing_content[:startup_info_end_index]
        # 写入新的对话历史，覆盖原来的对话历史
        with open(log_file_path, 'a', encoding='utf-8') as file:
            # file.writelines(startup_info)  # 写入启动信息
            for interaction in conversation_history:
                role = interaction["role"]
                content = interaction["content"]
                file.write(f"{role.capitalize()}:\n{content}\n\n")

    # 通过api调用llm
    def call_llm_api(self, prompt) -> str:
        """
        通用的LLM API调用函数。
        """
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=prompt
        )
        return response.choices[0].message.content
    # 功能函数3: 调用llm将自然语言翻译为ltl公式
    def translate_to_ltl(self, natural_language_task: str, object_list: List[str]) -> str:
        """
        使用LLM将自然语言任务翻译为线性时序逻辑（LTL）公式。
        """


        user_prompt = (fr"""Your job is to read the natural language task description AND generate ONE commonsense safety constraint that should always hold during the execution of this task, and express it as an LTL (Linear Temporal Logic) formula in SPOT-compatible syntax. 
You MUST strictly follow ALL constraints below (no violation allowed):
------------------------------------------------
[Object Name Constraints]
- object names MUST EXACTLY use the same original strings from the ai2thor scene
- you MUST NOT invent any object name that is not in the given list
[Predicate Constraints] 
- you MUST ONLY use the following predicates (no additions, modifications, deletions allowed), and you MUST replace `object` in each predicate with concrete object names when forming atomic propositions: 
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
[Safety Constraint Requirement]
- You MUST output a commonsense safety constraint(such as "Food must be inside the microwave in order for it to be toggled on", "Object must be held before it can be placed") expressed in LTL formula
- A Safety LTL formula MUST prohibit unsafe states at all times. Therefore your output MUST be of the form G( ... )

[Output Format Constraints]
- Output only the final LTL formula, strictly following SPOT’s syntax.
- No explanation, no comments, no natural language, no description
------------------------------------------------

Here is the input provided to you:
### Task Instruction:
{natural_language_task}
### List of available objectTypes in the ai2thor scene:
{object_list}

Please generate the corresponding LTL formula based on the task instruction above, using only object names from the objectType list above. Please output only the formula itself.
""")
        ltl_prompt = [{"role": "user", "content": user_prompt}]
        # ltl_prompt.append({"role": "user", "content": prompt})
        ltl_formula = self.call_llm_api(ltl_prompt)
        # 假设LLM返回的内容可以直接作为LTL公式，可能需要后处理
        self.log_interaction(LOG_FORMULA_PATH, [{"role": "user", "content": user_prompt}, {"role": "assistant", "content": ltl_formula}])
        return ltl_formula.strip()

    # 功能函数4: 调用llm将任务指令转化为状态轨迹
    def generate_state_trajectory(self, task_instruction: str, object_list: List[str]) -> str:
        """
        使用LLM将任务指令转化为一系列状态和动作的轨迹（例如，用于规划）。
        """
        user_prompt = (
        fr"""You are a trajectory / plan formalization expert. 
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
{object_list}

------------------------------------------------

Now generate one possible discrete state evolution trace that can satisfy the Task Instruction,
strictly following ALL constraints above.

Output ONLY the trace.
"""
        )
        traj_prompt = [{"role": "user", "content": user_prompt}]

        trajectory_json_str = self.call_llm_api(traj_prompt)
        self.log_interaction(LOG_TRACE_PATH, [{"role": "user", "content": user_prompt}, {"role": "assistant", "content": trajectory_json_str}])
        return trajectory_json_str
