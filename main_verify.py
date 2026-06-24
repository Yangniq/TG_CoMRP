import re
from copy import deepcopy
from utils import ltl2digraph, validate_next_action, concat_props

# from spot_4
# 使用：success_status, details = verify_ltl_trace_fixed(LTL_FORMULA, TRACE_SUCCESS)

# 定义谓词对立组（前缀）
MUTEX_PREFIX_GROUPS = [
    {"isOpen", "isClosed"},
    {"isToggledOn", "isToggledOff"},
    {"isDirty", "isClean"},
    {"isFilledWithLiquid", "isEmptyLiquid", "isUsedUp"},
    # 位置互斥组：一个物体在同一时间只能被握住、或在里面、或在上面
    {"isHeld", "inside", "onTop"}
]

def get_formula_propositions(ltl_formula: str):
    LTL_OPS = {
    'F','G','X','U','W','R',  # temporal ops
    '!','&','|','->','<->'    # logic ops
}
    # tokenize:
    # token 1: identifiers (starts with letter, allow _ and digits)
    # token 2: operators (-> <->)
    # token 3: single symbols
    tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*|->|<->|[!&|()FGRUXW]', ltl_formula)

    props = []
    for t in tokens:
        # discard LTL op
        if t in LTL_OPS:
            continue
        # parentheses
        if t in ('(',')'):
            continue
        # everything else with letter-start is candidate AP
        if re.match(r'^[A-Za-z_]', t):
            props.append(t)
    print(f"Propositional variables: {set(props)}")

    return set(props)

# def event_to_proposition_state_FIXED(event_fact, prev_state,formula_propositions):
#     """
#     【状态映射函数】: 遵循持久性原则。
#     只在事件明确改变状态时才更新，否则保持前一状态的值。
#     """
#     # 使用深拷贝复制前一状态，而不是创建一个全新的空状态字典
#     current_state = deepcopy(prev_state)
#     if event_fact in formula_propositions:
#         current_state[event_fact] = True
#     else:
#         current_state[event_fact] = False
#
#     return current_state

def parse_prop(prop_str):
    """
    解析命题，提取谓词前缀和物体ID。
    例如: 'isOpen_fridge' -> ('isOpen', 'fridge')
    例如: 'inside_apple_box' -> ('inside', 'apple') 注意：通常以第一个物体为主体
    """
    parts = prop_str.split('_')
    prefix = parts[0]
    # 对于 inside_A_B，通常 A 是主体，我们取第一个 A
    primary_object = parts[1] if len(parts) > 1 else None
    return prefix, primary_object


def event_to_proposition_state_FIXED(event_fact, prev_state, formula_propositions):
    current_state = deepcopy(prev_state)
    if event_fact not in formula_propositions:
        return current_state
    # 1. 设置当前事件为真
    current_state[event_fact] = True
    # 2. 解析当前事件的 谓词 和 物体ID
    current_prefix, current_obj = parse_prop(event_fact)
    if not current_obj:
        return current_state
    # 3. 寻找所属的互斥组
    target_group = None
    for group in MUTEX_PREFIX_GROUPS:
        if current_prefix in group:
            target_group = group
            break
    # 4. 如果属于某个互斥组，清除【同一个物体】的其他对立命题
    if target_group:
        # 遍历当前已有的所有状态
        for prop in list(current_state.keys()):
            if prop == event_fact:
                continue
            p_prefix, p_obj = parse_prop(prop)
            # 如果物体相同，且谓词在同一个互斥组中，则设为 False
            if p_obj == current_obj and p_prefix in target_group:
                current_state[prop] = False
    return current_state

# --- 验证流程函数 ---
def verify_ltl_trace(ltl_formula, event_trace):
    print(f"--- 正在验证 LTL: {ltl_formula} ---")
    # 获取目标状态集
    formula_propositions = get_formula_propositions(ltl_formula)
    # 1. LTL 转换为 DFA
    dfa, accepting_states, curr_state = ltl2digraph(ltl_formula)
    # 2. 状态序列生成与验证
    initial_prop_state = {p: False for p in formula_propositions}
    prev_state = initial_prop_state
    state_list = []
    success = True
    # 迭代处理事件
    for i, event in enumerate(event_trace):
        if event == "stop":
            next_prop_str = "stop"
        else:
            # 使用映射函数
            new_state = event_to_proposition_state_FIXED(event, prev_state,formula_propositions)
            # 如果状态没有变化，则跳过 LTL 推进
            if new_state == prev_state and i != 0:
                state_list.append(f"Skipped (No Change): {event}")
                continue
            # 命题提取
            next_prop_str = concat_props(new_state)
            prev_state = new_state
            # 验证当前状态是否安全
        valid, next_state = validate_next_action(dfa, curr_state, next_prop_str, accepting_states)
        if valid:
            state_list.append(f"Safe ({event}): {next_prop_str}")
            curr_state = next_state
        else:
            state_list.append(f"Violated ({event}): {next_prop_str}")
            success = False
            break
    return success, state_list


# ltl_formula = "G((isToggledOn_Microwave -> inside_Bread_Microwave) & (isToggledOn_Toaster -> inside_Bread_Toaster) & (isToggledOn_StoveBurner -> (onTop_Bread_StoveBurner | inside_Bread_Pan | inside_Bread_Pot)))"
# traj = ['isOpen_Fridge', 'isHeld_Bread', 'isClosed_Fridge', 'isOpen_Microwave','inside_Bread_Microwave', 'isClosed_Microwave', 'isToggledOn_Microwave', 'isToggledOff_Microwave',  'isOpen_Microwave', 'isHeld_Bread', 'isClosed_Microwave']
# ltl_formula = "G(!isHeld_Apple U inside_Apple_SinkBasin)"
# traj = ['isClosed_Fridge', 'isOpen_Fridge', 'isHeld_Apple', 'isClosed_Fridge', 'isHeld_DishSponge', 'isClean_Apple', 'isDirty_DishSponge']
# success_status, details = verify_ltl_trace(ltl_formula,traj)
# print("LTL 验证结果: 成功" if success_status else "LTL 验证结果: 失败")
# print("\n详细步骤 (事件和命题状态):")
# for detail in details:
#     print(f"  {detail}")