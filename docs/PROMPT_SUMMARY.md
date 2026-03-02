# PDR 室内导航增强 — Prompt 总结（供迭代使用）

以下为与客户需求对应的**精简 prompt**，便于后续与 AI 或团队迭代时复制使用。

---

## 项目背景（一句话）

在现有 PDR WebApp（单页、IMU+步数+航向+轨迹）基础上，面向 SFO 机场级室内做增强：米级精度、航向 &lt;20°、支持多姿态、滤波、在线校准、路网约束与地图可视化。

---

## 需求清单（可直接粘贴给 AI）

1. **姿态适应**: 支持手持看屏、握持、口袋等多种持机方式；用幅值 |a|、低通、峰值检测、谷峰要求、自适应阈值（近 N 步统计）优化步检测，避免姿态固定假设。
2. **滤波**: 在经典 PDR 上增加滤波；考虑卡尔曼、互补滤波或 Madgwick；航向用陀螺积分 + 磁力计辅助，磁干扰大时自动降权磁力计。
3. **在线校准**: 支持用户通过地标确认（如“我到达此地标”）、已知距离（A→B）在线校准步长系数 K，并重置位置以防发散。
4. **自适应步长**: 采用 Weinberg 等模型 step_length = K×(a_max−a_min)^0.25；K 可通过已知距离段自动/半自动更新，并做异常步过滤。
5. **环境约束**: 利用 SFO 路网（OSM 或自采）；航向可量化到走廊方向；位置通过 Map Matching（如粒子滤波）吸附到路网，抑制漂移。
6. **行为识别**: 区分直梯/扶梯（无步数但位移）、跑步、上/下楼梯、电梯等，并记录到导出数据。
7. **测试与 baseline**: 支持 baseline 轨迹 JSON；回放或在线比对时计算 APE/RPE（或类似 EVO 的指标），并输出测试 log。
8. **标定**: 提供流程与数据格式，便于用真实物理距离标定轨迹与步长。
9. **PoC 可视化**: 使用 SFO 真实地图（OSM）；用户提供初始朝向与地图对齐；实时轨迹叠加在地图上。
10. **漂移与矫正**: 算法能判断漂移风险，在可能发散时提示用户进行地标/朝向等交互矫正。
11. **UI 规范**: 底层为 DR 引擎（IMU→步态→步长+航向→位置）；可视化为 SVG/平面图、绿色轨迹、路标、蓝点吸附路网、步数/距离实时更新。

---

## 技术栈与约束

- **前端**: 纯浏览器 Web API（DeviceMotionEvent / DeviceOrientationEvent），无后端依赖；可选 Leaflet/OSM 做地图。
- **传感器**: 陀螺仪、加速度计、磁力计（可选）；步数由算法计算。
- **目标**: 米级定位；航向误差 &lt; 20°；通过用户交互抑制发散。

---

## 当前代码位置与扩展点

- **步检测**: `index.html` 内 `stepDetect(accG)`，基于幅值 + 谷峰 + 最小周期。
- **步长**: 当前为常数 `STEP_LENGTH_M`；扩展为 Weinberg，并记录每步 a_max/a_min。
- **航向**: 当前直接用 `lastOrientation.alpha`；扩展为陀螺积分 + 磁互补，并做漂移检测。
- **轨迹**: `trajectory.path`、`updateTrajectory()`、`drawTrajectory()`；后续可接路网投影与地图坐标。
- **导出**: `recordBuffer`、`meta`；扩展为含 step_length_per_step、behavior、heading_fused、便于 APE/RPE 的轨迹序列。

---

## 迭代时可用的具体指令示例

- “在现有 stepDetect 上增加最近 5 步峰值滑动平均，用于自适应阈值。”
- “用陀螺 rotationRate 积分得到 heading_gyro，再与 orientation.alpha 做互补滤波，α 根据磁场强度动态调整。”
- “每步记录 a_max、a_min，用 Weinberg 公式计算当步步长，并支持从地标 A→B 已知距离更新 K。”
- “增加‘我到达地标’按钮和初始朝向输入；点击地标时重置位置并可选更新 K。”
- “检测到 |heading_mag − heading_gyro| 持续偏大时，提示用户进行校准。”
- “导出 JSON 增加 trajectory_ts、positions、headings 和每步 step_length、a_max、a_min，便于 APE/RPE 和 baseline 比对。”
- “增加 behavior 字段：根据步周期与幅值区分 walk/run，无步数长时间标记为 elevator/escalator。”
- “加入 Leaflet 和 SFO 区域 OSM 底图；将 PDR 轨迹转换到地图坐标并叠加；支持用户设置初始朝向对齐地图。”

---

## 文档与设计引用

- 完整方案与算法细节: `docs/SOLUTION.md`
- 本 prompt 总结: `docs/PROMPT_SUMMARY.md`

迭代时优先说明：当前在做哪一阶段（Phase 1–5）、要改的文件/函数、以及希望保持兼容的导出格式或 UI 行为。

---

## 最终 Prompt 总结（可直接用于下一轮迭代）

**角色**: 你是室内导航专家算法工程师，具备 PDR/Map Matching/室内定位经验。

**项目**: 在现有 PDR WebApp（单页、浏览器 IMU API）上做增强，目标为 SFO 机场级室内、米级精度、航向误差 &lt;20°。传感器仅用陀螺仪、加速度计、磁力计；步数由算法计算；通过用户交互（地标、初始朝向）抑制发散。

**当前代码状态**:
- `index.html`: 已实现 Weinberg 步长、陀螺积分+磁力计互补航向、漂移检测与提示、地标“我到达”校准（K 更新）、初始航向偏移、行为标签（walk/run/elevator）、导出含 `trajectory_for_ape` 与 `stepHistory`。
- `docs/SOLUTION.md`: 完整方案（11 点需求对应的系统设计、算法设计、分阶段实现计划）。
- `docs/PROMPT_SUMMARY.md`: 本文件，需求清单与迭代指令。

**下一阶段可执行指令示例**:
- “在 index.html 中增加 SFO OSM 地图（Leaflet），将轨迹叠加到地图上，支持用户设置初始朝向与地图北对齐。”
- “实现路网 JSON 加载与简单 Map Matching：将 PDR 位置投影到最近边，航向量化到边方向。”
- “增加 baseline 轨迹加载与 APE/RPE 计算脚本（Node 或 Python），输出 tests/log/。”
- “细化行为分类：根据无步时长与加速度模式区分 escalator/stairs_up/stairs_down。”

**约束**: 纯前端、无后端；保持导出 JSON 结构兼容；优先鲁棒性与用户可校准。
