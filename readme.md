# TG-CoMRP：基于轨迹引导的大语言模型协同多机器人任务规划框架

本仓库为论文 **Trajectory-Guided Collaborative LLM-based Multi-Robot Task Planning (TG-CoMRP)** 的官方代码实现。

## 项目简介

TG-CoMRP 是一个融合**大语言模型（Large Language Model，LLM）**与**线性时序逻辑（Linear Temporal Logic，LTL）**的多机器人协同任务规划框架，面向具身智能场景中的复杂任务规划问题。

相比传统 LLM 规划方法，TG-CoMRP 通过引入形式化约束和多机器人协商机制，提高了任务规划的正确性、可执行性和协同效率。

整个框架主要由三个模块组成：

* **参考轨迹生成模块**

  * 将自然语言任务转换为 LTL 逻辑公式；
  * 生成对应的目标状态轨迹；
  * 对 LTL 与轨迹进行一致性验证。

* **多机器人协同规划模块**

  * 多个机器人智能体基于协商完成任务分解；
  * 自动完成任务分配；
  * 生成支持并行执行的协同计划。

* **执行反馈模块**

  * 根据执行结果检测失败原因；
  * 利用 LLM 对规划进行自动修正；
  * 实现闭环规划。

目前项目基于 **AI2-THOR** 仿真平台进行验证。

---

# 项目结构

```text
TG_CoMRP/
│
├── main_translate.py          # 自然语言→LTL公式与参考轨迹生成
├── main_verify.py             # LTL与轨迹一致性验证
├── main_robotsChat.py         # 多机器人协同规划
├── ai2thor_controller.py      # AI2-THOR接口
├── collection_run_action.py   # 动作执行模块
├── try_function_calling.py    # 参考轨迹生成阶段环境信息查询接口
├── config.py                  # 机器人配置
├── prompts/                   # Prompt模板
├── requirements.txt           # Python依赖
└── README.md
```

---

# 环境配置

建议使用 **Python 3.9.21**

## 1. 克隆项目

```bash
git clone https://github.com/yourname/TG_CoMRP.git
cd TG_CoMRP
```

## 2. 创建虚拟环境

```bash
python -m venv venv
```

Linux

```bash
source venv/bin/activate
```

## 3. 安装依赖

```bash
pip install -r requirements.txt
```

---

# API 配置

运行前，请配置对应的大语言模型 API。

可以在配置文件中填写：

```python
API_KEY = "你的API Key"
BASE_URL = "模型服务地址"
MODEL_NAME = "模型名称"
```

支持根据实际情况替换不同的大语言模型。

---

# 使用流程

整个系统在main.py中按照以下流程运行。

## 第一步：生成参考轨迹

运行：

```bash
main_translate.py
```

该模块负责：

* 自然语言任务解析；
* LTL公式生成；
* 目标状态轨迹生成；
* 保存生成结果。

---

## 第二步：轨迹验证

运行：

```bash
main_verify.py
```

验证内容包括：

* LTL是否满足；
* 状态转换是否合法；
* 是否违反互斥约束；
* 轨迹是否可执行。

---

## 第三步：多机器人协同规划

运行：

```bash
main_robotsChat.py
```

系统将自动完成：

* 任务分解；
* 机器人协商；
* 任务分配；
* 并行执行计划生成。

---

## 第四步：AI2-THOR执行

生成的动作计划可通过 AI2-THOR 控制器执行，并返回执行反馈用于后续规划修正。

---

# Prompt 模板

所有 Prompt 模板位于：

```text
prompts/
```

主要包括：

* 群组初始讨论Prompt：initial_chat_prompt.txt
* 群组讨论反馈Prompt：feedbackPrompt.txt
* 管理者和各机器人Prompt：traj_xxx.txt
* 消融实验部分（w/o traj.）管理者和各机器人Prompt：wo_traj_xxx.txt

用户可以根据需求自行修改 Prompt，以适配不同模型或不同任务。

---

# 机器人配置

机器人能力定义位于：

```python
config.py
```

每个机器人可以定义：

* 名称
* 技能集合
* 可执行动作

支持异构机器人协同规划。

---

# 实验平台

* Python 3.9.21
* AI2-THOR
* OpenAI API（或兼容接口）
* AutoGen
* Spot（LTL验证）

---


# 致谢

本项目参考或使用了以下优秀开源项目：

* AI2-THOR
* AutoGen
* Spot
* OpenAI API

感谢上述项目开发者的开源贡献。

---

