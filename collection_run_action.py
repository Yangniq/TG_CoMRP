# test-ai2thor-control
import json
import re
import threading
import ai2thor.controller
import ai2thor_controller as thor_controller

# 阶段1：收集所有 step 的动作集（不执行）
def load_final_plan(file_path):
    """
    从日志文件中读取 FINAL_PLAN_START 与 FINAL_PLAN_END 之间的 JSON，
    并转换为 Python 对象返回。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    # 正则提取
    pattern = r"FINAL_PLAN_START(.*?)FINAL_PLAN_END"
    match = re.search(pattern, text, re.S)
    if not match:
        raise ValueError("Could not find FINAL_PLAN_START or FINAL_PLAN_END in log.")
    json_str = match.group(1).strip()
    # 解析 JSON 并返回 Python 对象
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
        for robot_name, actions in robots.items():
            print(f"=== Start robot name ===")
            print(robot_name)
            print(f"=== Start actions ===")
            print(actions)

final_plan = load_final_plan("test_AI.txt")
print(final_plan)
collected = collect_plan(final_plan)
print(collected)
execute_collected_plan(collected)

# #  单个机器人动作串行执行
# def execute_robot_actions(robot_name, actions):
#     for action in actions:
#         action_name = action["action"]
#         params = action["params"]
#         # 根据 action 字符串调用对应函数
#         if action_name not in ACTION_MAP:
#             raise ValueError(f"Undefined action: {action_name}")
#         func_name = action_name
#         func = getattr(thor_controller, func_name)
#         if func_name == "PutObject":
#             func(robot_name, params["object_name"], params["receptacle_name"])
#         else:
#             func(robot_name, params["object_name"])

