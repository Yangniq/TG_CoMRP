ltl_api_key = ''
ltl_url = ''
ltl_model_name = ''
chat_api_key = ''
chat_url = ''
chat_model_name = ''

all_skills = ['GoToObject', 'OpenObject', 'CloseObject', 'BreakObject', 'SliceObject', 'ToggleObjectOff','ToggleObjectOn','PickupObject', 'PutObject',  'ThrowObject', 'PushObject', 'PullObject','CleanObject']
# 协作
# robots_definitions = [
#         {'name': 'Robot1',
#          'skills': ['GoToObject', 'OpenObject', 'CloseObject', 'BreakObject', 'PushObject', 'PullObject','CleanObject']},
#         {'name': 'Robot2',
#          'skills': ['GoToObject',  'BreakObject',  'ToggleObjectOff','ToggleObjectOn','PickupObject', 'PutObject',  'ThrowObject', 'PushObject', 'PullObject','CleanObject']},
#         {'name': 'Robot3',
#          'skills': ['GoToObject',  'BreakObject', 'SliceObject','PickupObject', 'PutObject',  'ThrowObject', 'PushObject', 'PullObject','CleanObject']}
#     ]

robots_definitions = [
        {'name': 'Robot1',
         'skills': ['GoToObject', 'OpenObject', 'CloseObject', 'BreakObject', 'SliceObject', 'ToggleObjectOff','ToggleObjectOn','PickupObject', 'PutObject',  'ThrowObject', 'PushObject', 'PullObject','CleanObject']},
        {'name': 'Robot2',
         'skills': ['GoToObject', 'OpenObject', 'CloseObject', 'BreakObject', 'SliceObject', 'ToggleObjectOff','ToggleObjectOn','PickupObject', 'PutObject',  'ThrowObject', 'PushObject', 'PullObject','CleanObject']},
        {'name': 'Robot3',
         'skills': ['GoToObject', 'OpenObject', 'CloseObject', 'BreakObject', 'SliceObject', 'ToggleObjectOff','ToggleObjectOn','PickupObject', 'PutObject',  'ThrowObject', 'PushObject', 'PullObject','CleanObject']}
    ]
