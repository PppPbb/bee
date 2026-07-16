# Cloud-Hive Meadow 算法端接口与待办文档

本文档用于把当前 Maya 静态视觉原型升级为“可自己运作”的采集、判断、运输系统。目标是让算法端先实现可测试的纯 Python 状态逻辑，再由 Maya 视觉端读取状态并播放动画。

## 1. 当前状态

当前 `maya_scripts/cloud_hive_meadow.py` 已完成：

- 六边形蜂巢网格生成。
- 蜂巢格类型分配：`honey`、`pollen`、`empty`、`capped`。
- 云粒子群、蜂蜜雨、花蜜/花粉颗粒。
- 小长方体蜜蜂占位模型。
- 简单 BFS 路径展示。

当前还没有完成：

- 蜜蜂自主选择任务。
- 云资源随时间减少/再生。
- 蜜蜂按状态机飞行、采集、返回、运输。
- 资源落点判定后进入任务队列。
- 蜂巢资源库存、容量、消耗循环。
- 每帧/每 tick 的系统更新。

## 2. 推荐架构

建议拆成四层：

```text
cloud_hive_meadow.py        Maya 入口、UI、视觉创建
chm_state.py                数据结构和系统状态
chm_simulation.py           任务生成、BFS、蜜蜂状态机、资源更新
chm_visual_adapter.py       把 state 映射成 Maya 模型、曲线、动画
```

最重要的原则：

- 算法端不要直接依赖 Maya `cmds`。
- 算法端只处理数字、字典、列表和状态更新。
- Maya 视觉端只根据算法状态创建/移动/高亮对象。

这样算法可以在普通 Python 里测试，最后再接回 Maya。

## 3. 核心数据结构

### 3.1 Cell

```python
cell = {
    "id": 12,
    "q": 0,
    "r": 1,
    "position": (1.73, 0.0, 1.5),
    "type": "honey",          # honey / pollen / empty / capped
    "nectar": 0.0,
    "pollen": 0.0,
    "capacity": 1.0,
    "neighbors": [(1, 1), (-1, 1)],
    "is_blocked": False,
    "visual_node": "chm_cell_honey_0_1"
}
```

说明：

- `q, r` 是 axial coordinates。
- `position` 用 Maya 世界坐标，建议统一为 `(x, y, z)`。
- `is_blocked=True` 时 BFS 不可通过。
- `capped` 默认视为 blocked。

### 3.2 Cloud

```python
cloud = {
    "id": 3,
    "position": (2.0, 6.2, -4.0),
    "nectar_amount": 1.0,
    "pollen_amount": 0.8,
    "nectar_regen": 0.02,
    "pollen_regen": 0.01,
    "visual_group": "Cloud_03_GRP"
}
```

### 3.3 Bee

```python
bee = {
    "id": 5,
    "state": "idle",
    "position": (0.0, 1.0, 0.0),
    "current_cell": (0, 0),
    "target_cloud": None,
    "target_cell": None,
    "task_id": None,
    "carrying_type": None,    # nectar / pollen / None
    "carrying_amount": 0.0,
    "path": [],
    "path_index": 0,
    "speed": 0.08,
    "visual_group": "Bee_05_GRP"
}
```

建议状态：

```text
idle
to_cloud
collecting
returning_to_hive
moving_inside_hive
depositing
transporting
blocked
```

### 3.4 Task

```python
task = {
    "id": 18,
    "type": "collect_nectar",     # collect_nectar / collect_pollen / transport_nectar / transport_pollen / clean
    "source_cloud": 2,
    "source_cell": None,
    "target_type": "honey",
    "target_cell": None,
    "amount": 0.25,
    "priority": 1.0,
    "status": "queued",           # queued / assigned / done / failed
    "assigned_bee": None
}
```

### 3.5 SimulationState

```python
state = {
    "time": 0,
    "cells": {},
    "clouds": [],
    "bees": [],
    "tasks": [],
    "settings": {},
    "events": []
}
```

`events` 用于通知视觉端生成临时效果，例如：

```python
{"type": "path_created", "bee_id": 2, "points": [...]}
{"type": "drop_landed", "resource_type": "nectar", "cell": (1, -2), "is_wrong": True}
{"type": "cell_resource_changed", "cell": (0, 1), "nectar": 0.6}
```

## 4. 算法端需要提供的接口

### 4.1 初始化

```python
def create_initial_state(settings):
    """生成 cells、clouds、bees、tasks 的初始数据。"""
```

输入：

- `hive_radius`
- `cell_size`
- `cell_type_ratios`
- `cloud_count`
- `bee_count`
- `random_seed`

输出：

- `SimulationState`

### 4.2 单步更新

```python
def step_simulation(state, dt):
    """推进系统一个 tick，返回更新后的 state。"""
```

每个 tick 做：

1. 云资源再生。
2. 蜂巢资源消耗。
3. 判断是否需要新采集任务。
4. 生成云下资源落点。
5. 检查落点是否正确。
6. 错误落点生成运输/清理任务。
7. 空闲蜜蜂领取任务。
8. 更新蜜蜂移动和任务状态。
9. 写入 `events` 供视觉端消费。

### 4.3 BFS 路径

```python
def bfs_find_path(cells, start_key, target_filter):
    """从 start_key 找到满足 target_filter(cell) 的最近 cell。"""
```

建议 `target_filter` 支持：

```python
lambda cell: cell["type"] == "honey" and cell["nectar"] < cell["capacity"]
lambda cell: cell["type"] == "pollen" and cell["pollen"] < cell["capacity"]
```

返回：

```python
[(0, 0), (1, 0), (1, -1), (2, -1)]
```

### 4.4 任务生成

```python
def create_collection_tasks(state):
    """库存不足时生成 collect_nectar / collect_pollen。"""

def create_transport_task(state, source_cell, resource_type, amount):
    """资源落错格子时生成 transport_nectar / transport_pollen。"""
```

### 4.5 任务分配

```python
def select_task_for_bee(state, bee):
    """为空闲蜜蜂选择最合适任务。"""
```

评分建议：

```python
score = priority + amount * 0.5 - distance * 0.05
```

先实现简单版本：

- 优先级高的任务先做。
- 距离更近的任务优先。
- 已 assigned 的任务不再分配。

### 4.6 云目标选择

```python
def select_cloud_for_resource(state, resource_type, bee_position):
    """根据资源量和距离选择目标云。"""
```

评分：

```python
score = resource_amount - distance * distance_cost
```

### 4.7 资源落点

```python
def generate_resource_drop(state, cloud, resource_type):
    """根据云位置、随机偏移、风向生成落点。"""

def map_drop_to_cell(cells, drop_position):
    """把落点映射到最近蜂巢格。"""

def validate_resource_cell(cell, resource_type):
    """判断 nectar 是否进入 honey，pollen 是否进入 pollen。"""
```

### 4.8 蜜蜂状态机

```python
def update_bee(state, bee, dt):
    """根据 bee.state 推进蜜蜂任务。"""
```

最小状态流：

```text
idle
-> assigned task
-> to_cloud
-> collecting
-> returning_to_hive
-> moving_inside_hive
-> depositing
-> idle
```

运输任务状态流：

```text
idle
-> move to source_cell
-> pick up resource
-> bfs to target cell
-> moving_inside_hive
-> depositing
-> idle
```

## 5. 视觉端需要暴露的接口

这些函数由 Maya 端实现，算法端只调用或通过 `events` 间接触发。

```python
def visual_create_scene(state):
    """根据初始 state 创建蜂巢、云、蜜蜂和资源对象。"""

def visual_update_bee(bee):
    """移动蜜蜂占位模型。"""

def visual_update_cell(cell):
    """更新蜂巢格颜色、高亮、资源颗粒数量。"""

def visual_spawn_drop(event):
    """显示云下落点颗粒。"""

def visual_draw_path(event):
    """显示 BFS 或飞行路径曲线。"""

def visual_clear_finished_events(state):
    """清理已播放的临时视觉效果。"""
```

Maya 端建议保留映射表：

```python
visual_nodes = {
    "cells": {(0, 0): "chm_cell_honey_0_0"},
    "bees": {0: "Bee_00_GRP"},
    "clouds": {0: "Cloud_00_GRP"},
    "paths": {}
}
```

## 6. Maya 动画对接建议

有两种方式：

### 方案 A：实时 tick 更新

使用 Maya `scriptJob` 或 timer，每隔固定时间调用：

```python
state = step_simulation(state, 1.0 / 24.0)
visual_apply_state(state)
```

优点：

- 看起来像系统在实时运行。
- UI 参数可以动态影响系统。

缺点：

- 需要处理暂停、重置和性能。

### 方案 B：预计算关键帧

先运行算法 N 步，得到轨迹，再批量打 keyframe。

```python
history = simulate_for_frames(state, frame_count=240)
visual_bake_animation(history)
```

优点：

- 更稳定，适合作业展示和录屏。
- 容易得到可重复结果。

缺点：

- 交互性弱。

建议第一阶段采用方案 B，先做 10 秒可播放动画；之后再做方案 A。

## 7. 最小可运行闭环 MVP

第一版算法不要追求复杂，先实现这个闭环：

1. 初始化蜂巢、云、蜜蜂。
2. 找到一个 nectar 采集任务。
3. 蜜蜂从入口飞到云。
4. 云的 `nectar_amount` 减少。
5. 蜜蜂携带 nectar 返回入口。
6. BFS 找最近可用 `honey` cell。
7. 蜜蜂沿蜂巢路径移动。
8. 目标格 `nectar` 增加。
9. 蜜蜂回到 `idle`。
10. 视觉端显示飞行线、BFS 路径、资源增加。

这个闭环跑通后，再加：

- pollen 任务。
- 错误落点和运输任务。
- 资源消耗。
- 多蜜蜂并发。
- 云资源再生。

## 8. 算法端待办清单

### P0：必须完成

- [ ] 把当前脚本里的 `generate_hex_grid`、`assign_cell_types`、`bfs_find_path` 拆到 `chm_simulation.py`。
- [ ] 给每个 cell 增加 `nectar`、`pollen`、`capacity`、`is_blocked`。
- [ ] 实现 `SimulationState`。
- [ ] 实现 `Bee` 数据和 `idle -> task -> done` 状态机。
- [ ] 实现云资源选择 `select_cloud_for_resource`。
- [ ] 实现 BFS 找最近 honey/pollen cell。
- [ ] 实现采集任务完整闭环。
- [ ] 输出 `events` 给视觉端。

### P1：展示效果增强

- [ ] 云下随机 drop 映射到最近 cell。
- [ ] 判断资源落点是否正确。
- [ ] 错误落点生成 transport task。
- [ ] 蜜蜂沿 BFS 路径运输资源。
- [ ] 蜂巢格根据库存改变颜色或颗粒数量。
- [ ] 路径曲线按任务类型区分颜色。

### P2：系统循环

- [ ] 蜂蜜库存随 `bee_count * bee_activity * consumption_rate` 消耗。
- [ ] 库存低于阈值自动生成采集任务。
- [ ] 云资源按 regen 速率恢复。
- [ ] capped cell 阻挡路径，观察 BFS 绕路。
- [ ] 多蜜蜂任务分配避免抢同一个任务。

### P3：可选加分

- [ ] 不规则蜂巢边缘和破损格。
- [ ] 风向影响资源落点分布。
- [ ] 路径搜索过程逐步高亮，而不只是显示最终路径。
- [ ] 任务面板显示 queued / assigned / done。
- [ ] 导出一段固定种子的展示动画。

## 9. 建议文件拆分

```text
maya_scripts/
  cloud_hive_meadow.py       # Maya UI 和入口
  chm_state.py               # 数据结构、默认参数
  chm_simulation.py          # 纯算法
  chm_visual_adapter.py      # Maya cmds 映射
  chm_demo.py                # 一键播放/烘焙演示
```

## 10. 与当前视觉脚本的对接点

当前函数可以保留并改造：

| 当前函数 | 后续用途 |
| --- | --- |
| `generate_hex_grid` | 移到算法层，成为 state 初始化 |
| `assign_cell_types` | 移到算法层，支持比例参数 |
| `bfs_find_path` | 移到算法层，改成接受 `target_filter` |
| `create_honeycomb` | 留在视觉层，读 cell state |
| `create_clouds` | 留在视觉层，读 cloud state |
| `create_bees` | 留在视觉层，读 bee state |
| `create_resource_drops` | 改成响应 `drop_landed` event |
| `create_bfs_paths` | 改成响应 `path_created` event |

## 11. 验收标准

算法端完成后，至少应能演示：

- 点击 Generate 后场景生成。
- 点击 Start Simulation 后蜜蜂自动领取任务。
- 蜜蜂飞向云，采集 nectar 或 pollen。
- 蜜蜂返回蜂巢入口。
- BFS 路径显示到正确储存格。
- 蜜蜂沿路径移动并存入资源。
- 错误落点会触发运输任务。
- 蜂巢资源数量会随时间变化。

## 12. 第一阶段接口草案

算法端先交付这些函数即可：

```python
def create_initial_state(settings):
    pass

def step_simulation(state, dt):
    pass

def bfs_find_path(cells, start_key, target_filter):
    pass

def select_task_for_bee(state, bee):
    pass

def update_bee(state, bee, dt):
    pass

def generate_resource_drop(state, cloud, resource_type):
    pass

def consume_resources(state, dt):
    pass
```

视觉端负责：

```python
def visual_create_scene(state):
    pass

def visual_apply_state(state):
    pass

def visual_apply_events(events):
    pass
```

先把这两个方向对齐，整个项目就可以从“静态模型”自然升级成“会运行的资源系统”。
