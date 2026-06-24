import ast
import json
import os
import re
import threading
import time
from datetime import datetime

from prompt_toolkit.key_binding.bindings.named_commands import previous_history

import ai2thor_controller as thor_controller
from main_translate import LLMClient
from main_verify import verify_ltl_trace
from main_robotsChat import run_group_chat
import config

def log_conversation(role, content):
    with open('LOG_llm_translate_v2.txt', 'a', encoding='utf-8') as file:
        file.write(f"{role.capitalize()}:\n{content}\n\n")

def load_final_plan(file_path):
    """
    从日志文件中读取 FINAL_PLAN_START 与 FINAL_PLAN_END 之间的 JSON，
    支持 LLM 输出可能包含 ``` 或 ```json 包裹。
    并转换为 Python 对象返回。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    # 正则提取 FINAL_PLAN_START 与 FINAL_PLAN_END 之间的内容
    pattern = r"FINAL_PLAN_START(.*?)FINAL_PLAN_END"
    match = re.search(pattern, text, re.S)
    if not match:
        raise ValueError("Could not find FINAL_PLAN_START or FINAL_PLAN_END in log.")

    json_str = match.group(1).strip()

    # 如果 LLM 输出带 ``` 或 ```json，去掉包裹
    code_block_match = re.search(r"```(?:json)?\s*(.*?)\s*```", json_str, re.S)
    if code_block_match:
        json_str = code_block_match.group(1).strip()

    # 解析 JSON
    try:
        plan = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse error: {e}\nExtracted content:\n{json_str}")

    return plan

def collect_plan(plan):
    collected = {}
    for step in plan:
        step_id = step["step_id"]
        tasks = step["tasks"]
        collected[step_id] = {}
        # 收集该 step 中每个机器人动作序列
        for robot_name, actions in tasks.items():
            collected[step_id][robot_name] = actions  # 直接保存动作列表
    return collected

def execute_collected_plan(collected):
    for step_id, robots in collected.items():
        print(f"\n=== Start {step_id} ===")
        threads = []
        for robot_name, actions in robots.items():
            t = threading.Thread(
                target=execute_robot_actions,
                args=(robot_name, actions)
            )
            threads.append(t)
        # 并行将当前 step 中每个机器人的动作 push 到 queue
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        print(f"=== Finish {step_id} ===")
        time.sleep(5)
    thor_controller.ActionDone()
    print("All steps completed.")

#  单个机器人动作串行执行
def execute_robot_actions(robot_name, actions):
    for action in actions:
        action_name = action["action"]
        params = action["params"]
        # 检查机器人动作是否有定义
        robot_def = next(r for r in config.robots_definitions if r["name"] == robot_name)
        if action_name not in robot_def["skills"]:
            raise ValueError(f"Undefined action: {action_name}")
        # 根据 action 字符串调用对应函数
        func_name = action_name
        func = getattr(thor_controller, func_name)
        if func_name == "PutObject":
            func(robot_def, params["object_name"], params["receptacle_name"])
        else:
            func(robot_def, params["object_name"])
def extract_ltl_formula(text: str) -> str:
    """
    Extract an LTL formula from LLM output.
    If triple backticks exist, extract the content inside them.
    Otherwise, return the stripped text itself.
    """
    # 1. Try to extract from triple backticks
    match = re.search(r"```(?:\w+)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 2. Fallback: treat the whole text as the formula
    return text.strip()


if __name__ == "__main__":
    # 创建文件夹
    base_dir = os.path.join(os.path.dirname(__file__), "output")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    episode_folder = f"episode_{timestamp}"
    episode_path = os.path.join(base_dir, episode_folder)
    os.makedirs(episode_path, exist_ok=True)
    # 1) 初始化 LLM
    llm_client = LLMClient(
        api_key=config.ltl_api_key,
        url=config.ltl_url,
        model_name=config.ltl_model_name,
        log_dir= episode_path
    )
    # 2) 初始化 AI2THOR Controller
    robots_definitions = config.robots_definitions
    thor_scene_num =202
    thor_controller.initialize_ai2thor(floor_plan_no=thor_scene_num)
    ## 获取物品列表
    obj_list = thor_controller.get_object_list()
    print("ai2thor objects:", obj_list)
    # 任务指令
    task = "Put the tomato in the sink to wash it, then slice it"
    # 3) 利用 llm 得到 LTL 公式
    ltl_formula = llm_client.translate_to_ltl(task, obj_list)
    print("LTL formula:", ltl_formula)
    ltl = extract_ltl_formula(ltl_formula)
    print("提取LTL:", ltl)
    # 4) 利用 llm 获取轨迹
    traj_response = llm_client.generate_state_trajectory(task, obj_list)
    print("轨迹生成结果:", traj_response)
    traj = ast.literal_eval(traj_response)
    traj = json.loads(traj_response)
    print("trajectory:", traj)
    # 5) 验证轨迹
    success, details = verify_ltl_trace(ltl,traj)
    print("LTL 验证结果: 成功" if success else "LTL 验证结果: 失败")
    print("\n详细步骤 (事件和命题状态):")
    for detail in details:
        print(detail)
    output_file = os.path.join(episode_path, "ltl_verification_result.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"LTL 公式: {ltl}\n")
        f.write(f"轨迹生成结果: {traj}\n")
        result_line = "LTL 验证结果: 成功" if success else "LTL 验证结果: 失败"
        print(result_line)
        f.write(result_line + "\n")
        print("\n详细步骤 (事件和命题状态):")
        f.write("\n详细步骤 (事件和命题状态):\n")
        for detail in details:
            print(detail)
            f.write(f"{detail}\n")
    print("验证结果已保存")

    # 6) 运行组聊
    chat_llm_config = {
        "config_list": [{"model": config.chat_model_name,
                         "api_key": config.chat_api_key,
                         "price": [0.45, 2.7],
                         "base_url": config.chat_url}],
        "temperature": 1,
    }

    # previous_plan_path = os.path.join('output/episode_2026-04-15_14-42-52', "group_chat_log.txt")
    # previous_plan = load_final_plan(previous_plan_path)
    # error_action = {"action": "PutObject", "params": {"object_name": "Apple", "receptacle_name": "Fridge"}}
    # feedback_issues = f"""Error action: {json.dumps(error_action)}
    # Issues: Error Message: Can't't put object in fridge because the fridge is closed."""

    if success:
        initial_task_message = fr""" We three robots are trying to complete the task: {task}.
        We are expected to produce a complete, detailed task execution plan that can be directly executed in the AI2-THOR platform.

The objects present in the AI2-THOR scene are: {obj_list}.\

During the discussion and planning process, please jointly adhere to the following principles and constraints:
## 1. Goal-oriented planning with executability as the priority
Our goal is not to restate the reference trajectory, but to derive a logically complete, physically reasonable, and executable action sequence that achieves the task objectives. All proposed actions must be mappable to primitive actions supported by AI2-THOR.

## 2. Strict compliance with AI2-THOR interaction rules
Please pay special attention to the following known constraints and actively check for violations during planning:
- At any time, a robot may hold only one object via the PickupObject action.
- When executing SliceObject, the robot must be holding the appropriate cutting tool, and the target object must not be held. After successful execution, multiple sliced objects will appear in the scene (e.g., BreadSliced).
If you identify any potential violations or unmet preconditions, clearly point them out during the discussion and propose appropriate corrections.\

## 3. Capability-aware task allocation
Each robot may execute only the actions available in its own action library. Before the discussion begins, each participant must explicitly introduce and declare their available action set. When you are unaware of others’ capabilities, **do not arbitrarily assign tasks to them. You must ensure that each person’s tasks match their skills**.

## 4. Efficiency and parallel collaboration requirement
- The task plan must **prioritize execution efficiency** and enable **parallel collaboration** whenever multiple robots are available.
- Whenever tasks are **independent and non-conflicting**, schedule them **within the same step** to allow robots to operate simultaneously rather than sequentially.
- Avoid unnecessary waiting or idle time by maximizing concurrent actions across robots.
- The **duration of a step is determined by the robot with the longest action sequence in that step** (i.e., the maximum number of actions assigned to any robot in the step).
- Therefore, the plan should aim to **minimize the total execution time by maximizing parallelism and reducing the number of steps**, while ensuring that no object, spatial, or tool constraints are violated.\
"""

        run_group_chat(chat_llm_config, initial_task_message, episode_path)
        final_plan_path = os.path.join(episode_path, "group_chat_log.txt")
        final_plan = load_final_plan(final_plan_path)
        print(final_plan)
        collected = collect_plan(final_plan)
        print(f'collected: {collected}')
        # 启动动作执行线程
        actions_thread = threading.Thread(target=thor_controller.exec_actions,args=(episode_path,))  # 设置为守护线程
        actions_thread.start()
        print("AI2THOR 动作执行线程已启动。")
        execute_collected_plan(collected)










