from typing import Union
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager, ConversableAgent
import os
import json
from typing_extensions import Optional, Dict
import ai2thor_controller as thor_controller
import config

# 定义记录函数
# def log_callback(agent_name, message_content):
#     with open(log_file_path, "a", encoding="utf-8") as f:
#         f.write(f"角色: {agent_name}\n消息: {message_content}\n\n")

# 自定义 GroupChatManager，继承自 ConversableAgent 以便能接收和记录消息
# GroupChatManager 本身就是 ConversableAgent 的子类
class LoggingGroupChatManager(GroupChatManager):
    def __init__(self, *args, log_file_dir: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.log_file_dir = log_file_dir

    def log_callback(self, agent_name, message_content):
        log_file_path = os.path.join(self.log_file_dir, "group_chat_log.txt")
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(f"角色: {agent_name}\n消息: {message_content}\n\n")
    def receive(
            self,
            message: Union[Dict, str],
            sender: ConversableAgent,
            request_reply: Optional[bool] = None,  # 添加 request_reply 参数
            silent: bool = False
    ):
        # 从消息字典中获取内容
        # 如果 message 是字符串，直接用于记录。如果是字典，则获取 "content"。
        if isinstance(message, dict):
            content_to_log = message.get("content", "")
        elif isinstance(message, str):
            content_to_log = message
        else:
            content_to_log = ""  # 或者作为错误/意外类型处理
        if content_to_log:  # 只记录有实质文本内容的消息
            self.log_callback(sender.name, content_to_log)
        # 调用 super().receive 时传递所有正确的参数
        super().receive(message, sender, request_reply=request_reply, silent=silent)


def read_prompt(file_path: str) -> str:
    """读取txt文件内容作为system_message"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Prompt 文件不存在: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()

def load_robot_prompt(template_path, actions):
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    actions_str = str(actions)
    return template.replace("{{AVAILABLE_ACTIONS}}", actions_str)

# llm_config = {
#         "config_list": [{ "model": "deepseek-chat",
#             "api_key": "sk-cd7244151dd14c57a93620672e7295f9",
#             "base_url": "https://api.deepseek.com/v1"}],
#         "temperature": 1,
#     }
def run_group_chat(llm_config, initial_task_message, log_file_dir):
    if not llm_config["config_list"][0]["api_key"]:
        raise ValueError("OPENAI_API_KEY 环境变量未设置。请设置 API Key。")
    # === 读取 prompt txt ===
    leader_prompt = load_robot_prompt("prompts/traj_manager.txt", config.robots_definitions[0]["skills"])
    robot_a_prompt = load_robot_prompt("prompts/traj_robot_a.txt", config.robots_definitions[1]["skills"])
    robot_b_prompt = load_robot_prompt("prompts/traj_robot_b.txt", config.robots_definitions[2]["skills"])

    leader = AssistantAgent(
        name= config.robots_definitions[0]["name"], # ai2thor robot1
        system_message= leader_prompt,
        llm_config=llm_config,
    )
    # robot A
    robot_a = AssistantAgent(
        name= config.robots_definitions[1]["name"],
        system_message=robot_a_prompt,
        llm_config=llm_config,
    )
    # robot B
    robot_b = AssistantAgent(
        name=config.robots_definitions[2]["name"],
        system_message=robot_b_prompt,
        llm_config=llm_config,
    )
    group_chat = GroupChat(
        agents=[leader, robot_a, robot_b],
        messages=[],
        max_round= 20
    )
    # 管理器负责轮流调度发言
    # 使用自定义的 LoggingGroupChatManager
    group_chat_manager = LoggingGroupChatManager(
        groupchat=group_chat,
        llm_config=llm_config,
        is_termination_msg=lambda x: x.get("content", "").strip().endswith("Task planning completed, JSON plan generated."),
        log_file_dir = log_file_dir
    )

    # 为了确保 LoggingGroupChatManager 的 receive 方法能被调用来记录初始消息，
    # 我们让 leader agent 发送消息给 group_chat_manager。
    # initiate_chat 本身会把 message 传递给 group_chat_manager.
    # GroupChatManager 也是一个 ConversableAgent，所以它的 receive 方法会被调用。
    leader.initiate_chat(
        recipient=group_chat_manager,  # 指定接收者为 manager
        message=initial_task_message,
    )


#
# with open("prompts/initial_prompt.txt", "r", encoding="utf-8") as f:
#         initial_task_message = f.read().strip()
# run_group_chat(initial_task_message)
