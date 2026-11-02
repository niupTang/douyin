# 关键词找对标：先查看、后入库

页面“自动找对标”现在提交候选搜索任务，后台依次搜索账号、读取主页及指定数量的作品。
候选账号和作品快照保存在独立候选表中，不写入正式对标账号或作品表。
用户展开候选查看作品，通过共享自动化会话打开主页或作品，认为合适后点击“加入对标库”。

## 接口

- POST /benchmark/douyin/discovery-tasks：keywords、limit（1–20）、maxVideos（1–30），返回任务 ID。
- GET /benchmark/douyin/discovery-tasks/{task_id}：进度、候选、作品、失败原因及是否已入库。
- POST /benchmark/douyin/discovery-tasks/{task_id}/candidates/{candidate_id}/import：仅导入服务器保存且读取成功的候选快照。

旧 auto-discover 路径现为候选搜索的别名，也只创建候选任务，不再自动入库。
旧调用方需要适配 HTTP 202 和返回的任务 ID，再查询任务并显式确认候选；旧 synced 返回结构不再使用。
同时保留 keyword / keywords 和 max_videos / maxVideos 参数别名。

## 数据与执行

首次使用时自动创建 benchmark_discovery_tasks 和 benchmark_discovery_candidates 两张表。
不修改已有对标数据；每个任务最多 20 个账号，每个账号最多 30 条作品。
后台最多同时执行两个候选搜索任务。页面离开后任务继续，返回页面恢复最后一个任务的查看。
后端重启时将未完成任务标为 interrupted，保留已读取的候选；不伪装为自动恢复执行。

确认入库使用单个 SQLite 事务写入账号、作品和候选状态。重复确认返回已入库账号，不重复采集或新增重复记录。
失败、无作品或仍待读取的候选不能入库。数据写入失败会整体回滚。

当前“好不好”由用户查看后判断，没有加入 AI 评分或自动质量阈值。
点赞列来自现有页面提取逻辑，明确标注“待核对”；未获取显示为未获取，不冒充零，也不用于自动评分。
平台登录、验证码和网络可能影响采集，失败原因在候选区展示。

## 验证

pytest 覆盖搜索不入库、确认导入、重复确认、失败候选拒绝、事务回滚、持久化及跨任务拒绝。
前端构建通过，并用本地模拟 API 验证搜索、展开作品、预览调用、确认入库和重复按钮禁用。
页面示例截图位于 .cache/benchmark-discovery-preview.png；截图数据为测试样例，不是真实采集结果。
