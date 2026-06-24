from datetime import datetime
import math
import re
import shutil
import subprocess
import time
import threading
import cv2
import numpy as np
from ai2thor.controller import Controller
from scipy.spatial import distance
from typing import Tuple
from collections import deque
import random
import os
from glob import glob
import config


def closest_node(node, nodes, no_robot, clost_node_location):
    crps = []
    distances = distance.cdist([node], nodes)[0]
    dist_indices = np.argsort(np.array(distances))
    for i in range(no_robot):
        pos_index = dist_indices[(i * 5) + clost_node_location[i]]
        crps.append(nodes[pos_index])
    return crps

def distance_pts(p1: Tuple[float, float, float], p2: Tuple[float, float, float]):
    return ((p1[0] - p2[0]) ** 2 + (p1[2] - p2[2]) ** 2) ** 0.5

def generate_video(input_path, prefix, char_id=0, image_synthesis=['normal'], frame_rate=5, output_path=None):
    """ Generate a video of an episode """
    if output_path is None:
        output_path = input_path

    vid_folder = '{}/{}/{}/'.format(input_path, prefix, char_id)
    if not os.path.isdir(vid_folder):
        print("The input path: {} you specified does not exist.".format(input_path))
    else:
        for vid_mod in image_synthesis:
            command_set = ['ffmpeg', '-i',
                           '{}/Action_%04d_0_{}.png'.format(vid_folder, vid_mod),
                           '-framerate', str(frame_rate),
                           '-pix_fmt', 'yuv420p',
                           '{}/video_{}.mp4'.format(output_path, vid_mod)]
            subprocess.call(command_set)
            print("Video generated at ", '{}/video_{}.mp4'.format(output_path, vid_mod))



# --- 全局 AI2THOR 控制器 ---
robots = config.robots_definitions
num_robot = len(robots)
c: Controller = None
reachable_positions = []
action_queue = []  # 使用 deque 以获得更高效的 pop(0)
task_over = False
actions_thread = None

# --- AI2THOR 初始化函数 ---
def initialize_ai2thor(floor_plan_no):
    global c, reachable_positions, actions_thread
    print("正在初始化 AI2THOR 环境...")
    c = Controller(height=1000, width=1000, quality='Ultra')  # 可按需调整质量
    c.reset("FloorPlan" + str(floor_plan_no))
    # 初始化 n 个智能体到场景中
    c.step(dict(action='Initialize', agentMode="default", snapGrid=False, gridSize=0.25, rotateStepDegrees=20,
                visibilityDistance=100, fieldOfView=90, agentCount=num_robot))
    # 添加一个顶视摄像头
    event = c.step(action="GetMapViewCameraProperties")
    event = c.step(action="AddThirdPartyCamera", **event.metadata["actionReturn"])
    # 获取可到达位置
    reachable_positions_meta = c.step(action="GetReachablePositions").metadata["actionReturn"]
    reachable_positions = [(p["x"], p["y"], p["z"]) for p in reachable_positions_meta]
    # 随机化智能体的位置
    for i in range(num_robot):
        init_pos = random.choice(reachable_positions_meta)
        c.step(dict(action="Teleport", position=init_pos, agentId=i))
    print(f"{num_robot} 个智能体已初始化并随机放置。")


def get_object_list() :
    """
    获取场景中的所有物体类型。
    """
    global c
    if not c:
        return ["Error: AI2-THOR Controller not initialized."]
        # 获取场景中的所有物体状态
        # event = self.controller.step(action="GetObjects")
    event = c.step(action="Pass")  # 任意 step 都可以
    # 从 metadata 中提取所有物体的类型
    if event.metadata['objects']:
       object_types = sorted(list(set(obj['objectType'] for obj in event.metadata['objects'])))
       return object_types
    else:
       return ["No objects found in the scene."]
# --- AI2THOR 执行动作函数 ---
def exec_actions(episode_path):
    global task_over, c
    # 所有输出统一放到 output/ 目录
    # base_dir = os.path.join(os.path.dirname(__file__), "output")
    # timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # episode_folder = f"episode_{timestamp}"
    # episode_path = os.path.join(base_dir, episode_folder)
    # os.makedirs(episode_path, exist_ok=True)
    # 为每个 agent 创建子目录
    for i in range(num_robot):
        agent_path = os.path.join(episode_path, f"agent_{i + 1}")
        os.makedirs(agent_path, exist_ok=True)
    # 创建 top_view 文件夹
    top_view_path = os.path.join(episode_path, "top_view")
    os.makedirs(top_view_path, exist_ok=True)
    img_counter = 0
    while not task_over:
        if len(action_queue) > 0:
            try:
                act = action_queue[0]
                if act['action'] == 'ObjectNavExpertAction':
                    multi_agent_event = c.step(
                        dict(action=act['action'], position=act['position'], agentId=act['agent_id']))
                    next_action = multi_agent_event.metadata['actionReturn']

                    if next_action != None:
                        multi_agent_event = c.step(action=next_action, agentId=act['agent_id'], forceAction=True)

                elif act['action'] == 'MoveAhead':
                    multi_agent_event = c.step(action="MoveAhead", agentId=act['agent_id'])

                elif act['action'] == 'MoveBack':
                    multi_agent_event = c.step(action="MoveBack", agentId=act['agent_id'])

                elif act['action'] == 'RotateLeft':
                    multi_agent_event = c.step(action="RotateLeft", degrees=act['degrees'], agentId=act['agent_id'])

                elif act['action'] == 'RotateRight':
                    multi_agent_event = c.step(action="RotateRight", degrees=act['degrees'], agentId=act['agent_id'])

                elif act['action'] == 'OpenObject':
                    multi_agent_event = c.step(action="OpenObject", objectId=act['objectId'], agentId=act['agent_id'],
                                               forceAction=True)
                elif act['action'] == 'CloseObject':
                    multi_agent_event = c.step(action="CloseObject", objectId=act['objectId'], agentId=act['agent_id'],
                                               forceAction=True)

                elif act['action'] == 'PickupObject':
                    objs = list(set([obj["objectId"] for obj in c.last_event.metadata["objects"]]))
                    pick_obj = act['objectId']
                    for obj in objs:
                        # match = re.match(pick_obj, obj) #从字符串obj的开头匹配
                        # match = re.search(pick_obj, obj)  # 在字符串任意位置匹配
                        obj_name = obj.split('|')[0]
                        if obj_name == pick_obj:
                        # if match is not None:
                            pick_obj_id = obj
                            break  # find the first instance
                    multi_agent_event = c.step(action="PickupObject", objectId=pick_obj_id, agentId=act['agent_id'],
                                               forceAction=True)
                elif act['action'] == 'PutObject':
                    multi_agent_event = c.step(action="PutObject", objectId=act['objectId'], agentId=act['agent_id'],
                                               forceAction=True)
                elif act['action'] == 'BreakObject':
                    multi_agent_event = c.step(action="BreakObject", objectId=act['objectId'], agentId=act['agent_id'],
                                               forceAction=True)
                elif act['action'] == 'SliceObject':
                    multi_agent_event = c.step(action="SliceObject", objectId=act['objectId'], agentId=act['agent_id'],
                                               forceAction=True)
                    # 1. 获取当前 Agent 的手中物品列表
                    inventory = multi_agent_event.metadata['inventoryObjects']
                    # 2. 检测手里是否有东西，且该东西是否为刀具
                    is_holding_knife = False
                    if inventory:
                        held_object_type = inventory[0]['objectType']
                        if 'knife' in held_object_type.lower():
                            is_holding_knife = True
                    # 3. 根据检测结果执行动作或抛出异常
                    if not is_holding_knife:
                        print(f"Action Failed: Agent {act['agent_id']} cannot slice because it is not holding a knife.")
                        current_held = inventory[0]['objectType'] if inventory else "Nothing"
                        raise Exception(
                            f"Action Failed: Agent {act['agent_id']} cannot slice because it is holding: {current_held}")
                elif act['action'] == 'CleanObject':
                    multi_agent_event = c.step(action="CleanObject", objectId=act['objectId'], agentId=act['agent_id'],
                                               forceAction=True)
                elif act['action'] == 'ToggleObjectOn':
                    multi_agent_event = c.step(action="ToggleObjectOn", objectId=act['objectId'],
                                               agentId=act['agent_id'], forceAction=True)
                elif act['action'] == 'ToggleObjectOff':
                    multi_agent_event = c.step(action="ToggleObjectOff", objectId=act['objectId'],
                                               agentId=act['agent_id'], forceAction=True)

                elif act['action'] == 'Done':
                    multi_agent_event = c.step(action="Done")
                print("Executing action: ", act)
                flag = multi_agent_event.metadata['lastActionSuccess']
                if flag:
                    print("Action successful: ", act)
                else:
                    # 检查具体错误原因 #如果要重新执行，需要将 actionQueue 清空
                    print(f"Error Message: {multi_agent_event.metadata['errorMessage']}")
                    print(multi_agent_event.metadata['inventoryObjects'])
            except Exception as e:
                print(e)

            for i, e in enumerate(multi_agent_event.events):
                cv2.imshow('agent%s' % i, e.cv2img)
                f_name = os.path.join(episode_path, "agent_" + str(i + 1),
                                              "img_" + str(img_counter).zfill(5) + ".png")
                cv2.imwrite(f_name, e.cv2img)
            top_view_rgb = cv2.cvtColor(c.last_event.events[0].third_party_camera_frames[-1], cv2.COLOR_BGR2RGB)
            cv2.imshow('Top View', top_view_rgb)
            f_name = os.path.join(episode_path, "top_view", "img_" + str(img_counter).zfill(5) + ".png")
            cv2.imwrite(f_name, top_view_rgb)
            if cv2.waitKey(25) & 0xFF == ord('q'):
                break
            img_counter += 1
            action_queue.pop(0)



def GoToObject(robot, dest_obj):
    print("Going to ", dest_obj)
    # check if robots is a list

    if not isinstance(robot, list):
        # convert robot to a list
        robots = [robot]
    no_agents = len(robots)
    # robots distance to the goal
    dist_goals = [10.0] * len(robots)
    prev_dist_goals = [10.0] * len(robots)
    count_since_update = [0] * len(robots)
    clost_node_location = [0] * len(robots)

    # list of objects in the scene and their centers
    objs = list([obj["objectId"] for obj in c.last_event.metadata["objects"]])
    objs_center = list([obj["axisAlignedBoundingBox"]["center"] for obj in c.last_event.metadata["objects"]])

    # look for the location and id of the destination object
    for idx, obj in enumerate(objs):
        obj_name = obj.split('|')[0]
        if obj_name == dest_obj:
            dest_obj_id = obj
            dest_obj_center = objs_center[idx]
            break  # find the first instance

    dest_obj_pos = [dest_obj_center['x'], dest_obj_center['y'], dest_obj_center['z']]

    # closest reachable position for each robot
    # all robots cannot reach the same spot
    # differt close points needs to be found for each robot
    crp = closest_node(dest_obj_pos, reachable_positions, no_agents, clost_node_location)

    goal_thresh = 0.3
    # at least one robot is far away from the goal

    while all(d > goal_thresh for d in dist_goals):
        for ia, robot in enumerate(robots):
            robot_name = robot['name']
            agent_id = int(robot_name[-1]) - 1

            # get the pose of robot
            metadata = c.last_event.events[agent_id].metadata
            location = {
                "x": metadata["agent"]["position"]["x"],
                "y": metadata["agent"]["position"]["y"],
                "z": metadata["agent"]["position"]["z"],
                "rotation": metadata["agent"]["rotation"]["y"],
                "horizon": metadata["agent"]["cameraHorizon"]}

            prev_dist_goals[ia] = dist_goals[ia]  # store the previous distance to goal
            dist_goals[ia] = distance_pts([location['x'], location['y'], location['z']], crp[ia])

            dist_del = abs(dist_goals[ia] - prev_dist_goals[ia])
            print(ia, "Dist to Goal: ", dist_goals[ia], dist_del, clost_node_location[ia])
            if dist_del < 0.2:
                # robot did not move
                count_since_update[ia] += 1
            else:
                # robot moving
                count_since_update[ia] = 0

            if count_since_update[ia] < 15:
                action_queue.append(
                    {'action': 'ObjectNavExpertAction', 'position': dict(x=crp[ia][0], y=crp[ia][1], z=crp[ia][2]),
                     'agent_id': agent_id})
            else:
                # updating goal
                clost_node_location[ia] += 1
                count_since_update[ia] = 0
                crp = closest_node(dest_obj_pos, reachable_positions, no_agents, clost_node_location)

            time.sleep(0.5)

    # align the robot once goal is reached
    # compute angle between robot heading and object
    metadata = c.last_event.events[agent_id].metadata
    robot_location = {
        "x": metadata["agent"]["position"]["x"],
        "y": metadata["agent"]["position"]["y"],
        "z": metadata["agent"]["position"]["z"],
        "rotation": metadata["agent"]["rotation"]["y"],
        "horizon": metadata["agent"]["cameraHorizon"]}

    robot_object_vec = [dest_obj_pos[0] - robot_location['x'], dest_obj_pos[2] - robot_location['z']]
    y_axis = [0, 1]
    unit_y = y_axis / np.linalg.norm(y_axis)
    unit_vector = robot_object_vec / np.linalg.norm(robot_object_vec)

    angle = math.atan2(np.linalg.det([unit_vector, unit_y]), np.dot(unit_vector, unit_y))
    angle = 360 * angle / (2 * np.pi)
    angle = (angle + 360) % 360
    rot_angle = angle - robot_location['rotation']

    if rot_angle > 0:
        action_queue.append({'action': 'RotateRight', 'degrees': abs(rot_angle), 'agent_id': agent_id})
    else:
        action_queue.append({'action': 'RotateLeft', 'degrees': abs(rot_angle), 'agent_id': agent_id})

    print("Reached: ", dest_obj)

# def get_closest_position(dest_obj_pos_tuple,reachable_positions):
#     return min(reachable_positions, key=lambda pos: distance_pts(pos, dest_obj_pos_tuple))

def PickupObject(robot, pick_obj):
    robot_name = robot['name']
    agent_id = int(robot_name[-1]) - 1
    # objs = list(set([obj["objectId"] for obj in c.last_event.metadata["objects"]]))
    # for obj in objs:
    #     # match = re.match(pick_obj, obj) #从字符串obj的开头匹配
    #     match = re.search(pick_obj, obj) # 在字符串任意位置匹配
    #     if match is not None:
    #         pick_obj_id = obj
    #         break  # find the first instance
    action_queue.append({'action': 'PickupObject', 'objectId': pick_obj, 'agent_id': agent_id})

def PutObject(robot, put_obj, recp):
    robot_name = robot['name']
    agent_id = int(robot_name[-1]) - 1
    objs = list(set([obj["objectId"] for obj in c.last_event.metadata["objects"]]))
    objs_center = list([obj["axisAlignedBoundingBox"]["center"] for obj in c.last_event.metadata["objects"]])
    objs_dists = list([obj["distance"] for obj in c.last_event.metadata["objects"]])

    metadata = c.last_event.events[agent_id].metadata
    robot_location = [metadata["agent"]["position"]["x"], metadata["agent"]["position"]["y"],
                      metadata["agent"]["position"]["z"]]
    dist_to_recp = 9999999  # distance b/w robot and the recp obj
    for idx, obj in enumerate(objs):
        obj_name = obj.split('|')[0]
        if obj_name == recp:
            dist = objs_dists[idx]  # distance_pts(robot_location, [objs_center[idx]['x'], objs_center[idx]['y'], objs_center[idx]['z']])
            if dist < dist_to_recp:
                recp_obj_id = obj
                dest_obj_center = objs_center[idx]
                dist_to_recp = dist
    action_queue.append({'action': 'PutObject', 'objectId': recp_obj_id, 'agent_id': agent_id})


def ToggleObjectOn(robot, sw_obj):
    robot_name = robot['name']
    agent_id = int(robot_name[-1]) - 1
    objs = list(set([obj["objectId"] for obj in c.last_event.metadata["objects"]]))
    for obj in objs:
        obj_name = obj.split('|')[0]
        if obj_name == sw_obj:
            sw_obj_id = obj
            break  # find the first instance
    action_queue.append({'action': 'ToggleObjectOn', 'objectId': sw_obj_id, 'agent_id': agent_id})

def SwitchOn(robot, sw_obj):
    robot_name = robot['name']
    agent_id = int(robot_name[-1]) - 1
    objs = list(set([obj["objectId"] for obj in c.last_event.metadata["objects"]]))
    for obj in objs:
        obj_name = obj.split('|')[0]
        if obj_name == sw_obj:
            sw_obj_id = obj
            break  # find the first instance
    action_queue.append({'action': 'SwitchOn', 'objectId': sw_obj_id, 'agent_id': agent_id})


def ToggleObjectOff(robot, sw_obj):
    robot_name = robot['name']
    agent_id = int(robot_name[-1]) - 1
    objs = list(set([obj["objectId"] for obj in c.last_event.metadata["objects"]]))
    for obj in objs:
        obj_name = obj.split('|')[0]
        if obj_name == sw_obj:
            sw_obj_id = obj
            break  # find the first instance
    action_queue.append({'action': 'ToggleObjectOff', 'objectId': sw_obj_id, 'agent_id': agent_id})
def SwitchOff(robot, sw_obj):
    robot_name = robot['name']
    agent_id = int(robot_name[-1]) - 1
    objs = list(set([obj["objectId"] for obj in c.last_event.metadata["objects"]]))
    for obj in objs:
        obj_name = obj.split('|')[0]
        if obj_name == sw_obj:
            sw_obj_id = obj
            break  # find the first instance
    action_queue.append({'action': 'SwitchOff', 'objectId': sw_obj_id, 'agent_id': agent_id})


def OpenObject(robot, sw_obj):
    robot_name = robot['name']
    agent_id = int(robot_name[-1]) - 1
    objs = list(set([obj["objectId"] for obj in c.last_event.metadata["objects"]]))
    for obj in objs:
        obj_name = obj.split('|')[0]
        if obj_name == sw_obj:
            sw_obj_id = obj
            break  # find the first instance
    action_queue.append({'action': 'OpenObject', 'objectId': sw_obj_id, 'agent_id': agent_id})


def CloseObject(robot, sw_obj):
    robot_name = robot['name']
    agent_id = int(robot_name[-1]) - 1
    objs = list(set([obj["objectId"] for obj in c.last_event.metadata["objects"]]))
    for obj in objs:
        obj_name = obj.split('|')[0]
        if obj_name == sw_obj:
            sw_obj_id = obj
            break  # find the first instance
    action_queue.append({'action': 'CloseObject', 'objectId': sw_obj_id, 'agent_id': agent_id})


def BreakObject(robot, sw_obj):
    robot_name = robot['name']
    agent_id = int(robot_name[-1]) - 1
    objs = list(set([obj["objectId"] for obj in c.last_event.metadata["objects"]]))
    for obj in objs:
        obj_name = obj.split('|')[0]
        if obj_name == sw_obj:
            sw_obj_id = obj
            break  # find the first instance
    action_queue.append({'action': 'BreakObject', 'objectId': sw_obj_id, 'agent_id': agent_id})


def SliceObject(robot, sw_obj):
    robot_name = robot['name']
    agent_id = int(robot_name[-1]) - 1
    objs = list(set([obj["objectId"] for obj in c.last_event.metadata["objects"]]))
    for obj in objs:
        obj_name = obj.split('|')[0]
        if obj_name == sw_obj:
            sw_obj_id = obj
            break  # find the first instance
    action_queue.append({'action': 'SliceObject', 'objectId': sw_obj_id, 'agent_id': agent_id})


def CleanObject(robot, sw_obj):
    robot_name = robot['name']
    agent_id = int(robot_name[-1]) - 1
    objs = list(set([obj["objectId"] for obj in c.last_event.metadata["objects"]]))
    for obj in objs:
        obj_name = obj.split('|')[0]
        if obj_name == sw_obj:
            sw_obj_id = obj
            break  # find the first instance
    action_queue.append({'action': 'CleanObject', 'objectId': sw_obj_id, 'agent_id': agent_id})

def ActionDone( ):
    action_queue.append({'action': 'Done'})

